#!/usr/bin/env python3
# -*- encoding: utf-8; py-indent-offset: 4 -*-
#
# kube-vip-watcher - Watcher for rescheduling kube-vip VIPs
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import time
import random
import lib.settings
from lib.cplogging import Cplogging
from kubernetes import client, config, watch


# OVERRIDE GLOBAL SETTINGS from lib/settings.py
# log-level may be set to: "info" (default), "warning", "debug", "critical", "error"
# lib.settings.global_log_level = "info"
# enable or disable sending to syslog
# lib.settings.global_log_server_enable = False
# where should the syslogs be sent - IP/FQDN and port (UDP)
# lib.settings.global_log_server = ("log-destination.example.com", 1714)

# initialize globally
# Configs can be set in Configuration class directly or using helper utility
# for loading config if script executed manually from commandline
# place the "admin.conf" from one of the master-nodes as "~/.kube/config" in your home-folder
#   if the "server:" is pointing to an IP/hostname managed via haproxy, haproxy might
#   disconnect the session after a defined period set in the "haproxy.cfg". If possible you
#   can change the "server:" value pointing directly to one of the master-nodes' API-port to
#   simulate pretty much the same condition, like if the script is running as a pod.
# config.load_kube_config()
# for loading config if script is running as pod/container
config.load_incluster_config()

v1_core = client.CoreV1Api()
v1_coordination = client.CoordinationV1Api()

w = watch.Watch()


def check_node_state(node_name):
    logger_name = "check_node_state"
    logger = Cplogging(logger_name)
    try:
        node_status = v1_core.read_node_status(node_name)
        node_conditions = node_status.status.conditions
    except Exception as e:
        logger.error("Exception when calling CoreV1Api->read_node_status: %s\n" % e)
        node_conditions = []
    # endtry

    for condition in node_conditions:
        logger.debug("Node %s condition: %s" % (node_name, str(condition).replace("\n", "")))  # ouput in single line which may be easier to be parsed by log-pattern analyzers
        # logger.debug("Node %s condition: %s" % (node_name, condition))  # tried with "pretty=False" but somehow it's still "pretty-printed"
        # we check for type "Ready" and look at the status
        if condition.type == "Ready":
            if condition.status == "True":
                logger.info("Node %s marked as 'Ready'" % node_name)
                return True
        # endif
    # endfor
    return False
# enddef


def check_container_state(pod_container_statuses):
    logger_name = "check_container_state"
    logger = Cplogging(logger_name)
    number_of_containers = len(pod_container_statuses)
    ready_containers = 0

    for container_status in pod_container_statuses:
        # container_status.ready is a boolean value
        if container_status.ready:
            ready_containers += 1
        # endif
    # endfor

    if ready_containers == number_of_containers:
        return True
    else:
        return False
    # endif
# enddef


def get_namespaced_services_with_label(namespace, pod_labels_app, pod_name):
    logger_name = "get_namespaced_services_with_label"
    logger = Cplogging(logger_name)
    try:
        services = v1_core.list_namespaced_service(namespace)
    except Exception as e:
        logger.error("Exception when calling CoreV1Api->list_namespaced_service: %s\n" % e)
        services = []
    # endtry
    list_of_services = []

    # get all services with app-label
    for service in services.items:
        try:
            if service.metadata.labels['app'] == pod_labels_app:
                list_of_services.append(service)
            # endif
        except:
            # app-label not found for current service being checked - just skip
            continue
        # endtry
    # endfor

    # now check if there is a service named exactly like the pod
    single_service = next((item for item in list_of_services if item.metadata.name == pod_name), None)
    # we need to return a list for the next function - it can be empty if no service with app-label was found
    if single_service is None:
        logger.info("None-Explicit pod named service(s) found")
        logger.debug("Service(s): %s" % str(list_of_services))
        #logger.debug("Service(s): %s" % list_of_services)
        return list_of_services
    else:
        logger.info("Explicit pod named service found")
        logger.debug("Service(s): %s" % str(single_service))
        #logger.debug("Service(s): %s" % single_service)
        return [single_service]
    # endif
# enddef


def get_namespaced_leases(service_name, namespace):
    logger_name = "get_namespaced_leases"
    logger = Cplogging(logger_name)
    try:
        # leases created by kube-vip are prefixed with "kubevip-"
        lease = v1_coordination.read_namespaced_lease("kubevip-" + service_name, namespace)
        lease_name = lease.metadata.name
        lease_holder = lease.spec.holder_identity
        logger.info("Lease: %s - Node: %s" % (lease_name, lease_holder))
        return lease_holder
    except:
        logger.warning("No Lease kubevip-%s found" % service_name)
        return None
    # endtry
# enddef


def get_namespaced_pods_with_label_on_node(namespace, pod_labels_app, pod_node_name):
    logger_name = "get_namespaced_pods_with_label_on_node"
    logger = Cplogging(logger_name)
    try:
        pods = v1_core.list_namespaced_pod(namespace)
    except Exception as e:
        logger.error("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
        pods = []
    # endtry
    list_of_pods = []

    # get all pods with app-label and node_name
    for pod in pods.items:
        try:
            if pod.metadata.labels['app'] == pod_labels_app and pod.spec.node_name == pod_node_name:
                # we do not explicitly exclude the pod we are currently checking for - maybe it got back online and is ready?
                if check_container_state(pod.status.container_statuses):
                    list_of_pods.append(pod)
            # endif
        except:
            # app-label not found for current pod being checked - just skip
            continue
        # endtry
    # endfor

    logger.info("Number of suitable pods on node %s: %d" % (pod_node_name, len(list_of_pods)))
    return list_of_pods
# enddef


def balance(list_of_services, pod_container_statuses, pod_node_name, pod_labels_app):
    logger_name = "balance"
    logger = Cplogging(logger_name)
    if len(list_of_services) == 0:
        logger.warning("No service(s) found with needed app-label")
        return False  # end def
    else:
        for service in list_of_services:
            try:
                # get the value of annotation 'kubeVipBalancePriority' and other values
                service_name = service.metadata.name
                namespace = service.metadata.namespace
                load_balancer_ip = service.spec.load_balancer_ip
                try:
                    traffic_policy = service.spec.external_traffic_policy
                except:
                    traffic_policy = None
                # endtry
                balance_priority_string = service.metadata.annotations['kubeVipBalancePriority']
                balance_priority_order = str(balance_priority_string).split(",")
                balance_priority_order = [sub_element.strip() for sub_element in balance_priority_order]  # remove whitespaces for each element in the list fixed_section
                logger.info("Service: %s - Balance Priority: %s - Traffic Policy: %s - Loadbalancer-IP: %s" % (service_name, balance_priority_order, traffic_policy, load_balancer_ip))
            except:
                logger.warning("Service missing annotation 'kubeVipBalancePriority'")
                return False  # end def
            # endtry

            try:
                lease_holder = get_namespaced_leases(service_name, namespace)

                # no we check if pod is running and if the lease_holder is corresponding to the first node in the priority list
                # if not we patch the holder-value in the lease after checking that the node to swtich to is available and has a running pod
                if lease_holder == balance_priority_order[0] and check_container_state(pod_container_statuses) and check_node_state(pod_node_name):
                    logger.info("Lease holder OK and pod's containers are ready")
                    return True  # end def
                else:
                    logger.warning("Detected wrong lease holder, issues with pod's containers or the node - further checking if VIP must be moved")
                    for node in balance_priority_order:
                        # check if node is available and ready
                        if check_node_state(node):
                            # check if another pod with same app-label is running - this would mean no VIP must be moved
                            try:
                                list_of_pods_on_node = get_namespaced_pods_with_label_on_node(namespace, pod_labels_app, node)

                                # check if at least one ready pod was found
                                if len(list_of_pods_on_node) >= 1:
                                    for pod in list_of_pods_on_node:
                                        """
                                        logger.debug(pod)
                                        try:
                                            pod_deletion_timestamp = pod.metadata.deletion_timestamp
                                            logger.debug("pod deletion event detected: %s" % str(pod_deletion_timestamp))
                                        except:
                                            logger.debug("pod_deletion not found")
                                            logger.debug(item)
                                            pod_deletion_timestamp = None
                                        """

                                        # if the pod is on the same node where the other failed and the remaining pod is healthy, the VIP doesn't need to be moved
                                        if check_container_state(pod.status.container_statuses) \
                                                and pod.spec.node_name == pod_node_name \
                                                and lease_holder == balance_priority_order[0]:
                                            logger.info("Found healthy pod %s on node %s. Lease holder OK and no need to move VIP" % (pod.metadata.name, pod.spec.node_name))
                                            return True  # end def
                                        elif check_container_state(pod.status.container_statuses):  # else move the VIP to the node
                                            # optional possible to only move if really needed with:
                                            # if traffic_policy == "Local":  # and indent code below a little
                                            # We have found another ready pod on another node - we have to update the lease and the service manifest
                                            try:
                                                # we have to use "holderIdentity" instead of "holder_identity"
                                                lease_body_patch = {"spec": {"holderIdentity": node}}
                                                lease_patch_response = v1_coordination.patch_namespaced_lease("kubevip-" + service.metadata.name, namespace, lease_body_patch)
                                            except Exception as e:
                                                logger.error("Exception when calling CoordinationV1Api->patch_namespaced_lease: %s\n" % e)
                                                sys.exit(1)
                                            # endtry

                                            try:
                                                # if we do not patch this value kube-vip removes the VIP sometimes completely for about a minute
                                                service_body_patch = {"metadata": {"annotations": {"kube-vip.io/vipHost": node}}}
                                                service_patch_response = v1_core.patch_namespaced_service(service.metadata.name, namespace, service_body_patch)
                                            except Exception as e:
                                                logger.error("Exception when calling CoreV1Api->patch_namespaced_service: %s\n" % e)
                                                sys.exit(1)
                                            # endtry

                                            if node == balance_priority_order[0]:
                                                logger.info("HOLDER CHANGED TO PRIMARY NODE %s and service's annotation 'kube-vip.io/vipHost' updated to %s" % (
                                                    lease_patch_response.spec.holder_identity,
                                                    service_patch_response.metadata.annotations['kube-vip.io/vipHost'])
                                                )
                                                return True  # end def
                                            else:
                                                logger.warning("HOLDER CHANGED TO ALTERNATIVE NODE %s and service's annotation 'kube-vip.io/vipHost' updated to %s" % (
                                                    lease_patch_response.spec.holder_identity,
                                                    service_patch_response.metadata.annotations['kube-vip.io/vipHost'])
                                                )
                                                return True  # end def
                                            # endif
                                            # optional possible to only move if really needed with:
                                            # else:
                                            #     logger.info("Traffic-Policy not 'Local' and node %s available so no need to move VIP" % node)
                                            # endif
                                        # endif
                                    # endfor
                                else:
                                    logger.info("No remaining pods on node found - continuing with search for suitable node with healthy pods.")
                                # endif
                            except Exception as e:
                                logger.error("Exception when calling get_namespaced_pods_with_label_on_node: %s\n" % e)
                            # endtry
                        else:
                            logger.info("Node %s not available - continuing with search for suitable node with healthy pods." % node)
                        # endif
                    else:
                        logger.warning("No suitable node found")
                        return False  # end def
                    # endfor
                # endif
            except:
                logger.warning("No Lease kubevip-%s found" % service.metadata.name)
                return False
            # endtry
        # endfor
    # endif
# enddef


def main():
    logger_name = "main"
    logger = Cplogging(logger_name)

    # timeout_seconds=0 ... the connection will be closed by Kubernetes after about 1 hour
    for item in w.stream(v1_core.list_pod_for_all_namespaces, timeout_seconds=0):
        try:
            # first we get pods where we need the VIP balanced
            if bool(item['object'].metadata.annotations['kubeVipBalanceIP']):
                # testing something
                # if item['object'].metadata.deletion_timestamp is not None:
                #     logger.debug(str(item['object'].metadata.deletion_timestamp))
                # logger.debug(str(item))
                pod_name = item['object'].metadata.name
                namespace = item['object'].metadata.namespace

                try:
                    pod_labels_app = item['object'].metadata.labels['app']
                except:
                    pod_labels_app = None
                    logger.warning("App-Label not set")
                # endtry

                if pod_labels_app is not None:
                    pod_node_name = item['object'].spec.node_name
                    pod_status_phase = item['object'].status.phase
                    pod_container_statuses = item['object'].status.container_statuses

                    logger.info("Namespace %s - Pod: %s - App-Label: %s - Node-Name: %s - Status: %s - Stream-Event-Type: %s" % (namespace, pod_name, pod_labels_app, pod_node_name, pod_status_phase, item['type']))
                    # in the next step we will check if a rebalance is needed

                    # then we get the service corresponding to the pod
                    list_of_services = get_namespaced_services_with_label(namespace, pod_labels_app, pod_name)
                    if len(list_of_services) >= 1:
                        balance(list_of_services, pod_container_statuses, pod_node_name, pod_labels_app)
                    else:
                        logger.warning("No services found")
                    # endif
                else:
                    logger.warning("Ignoring %s in Namespace %s because App-Label is not set" % (pod_name, namespace))
                # endif
        except Exception as e:
            # if pod has not such annotation just skip
            pass
        # endtry
    # endfor
# endmain


if __name__ == '__main__':
    logger_name = "if_main"
    logger = Cplogging(logger_name)

    reconnect_time_threshold = 1  # if a reconnect happens within less than a second
    reconnect_count_too_fast = 0   # init counter value
    reconnect_max_tries = 5       # maximum ammount of reconnects in sequence
    reconnect_tries_left = reconnect_max_tries  # init variable to determine how many reconnects in sequence are still allowed
    reconnect_in_seq = False      # init value for dertermining if reconnect happened in sequence in set time_threshold

    try:
        # ugly solution for reconnect
        # if reconnects happen too fast in sequence, this might indicate that there is some problem. So we exit the script/pod so that we do not hammer the Kubernetes API too much :)
        while True:
            connect_start = time.time()
            main()
            connect_stop = time.time()
            connect_duration = connect_stop - connect_start

            if connect_duration < reconnect_time_threshold:
                reconnect_count_too_fast += 1
                reconnect_tries_left -= 1
                reconnect_in_seq = True
                logger.warning("reconnected to Kubernetes-API within %.5f seconds, which might indicate a problem - reconnect tries left: %d" % (connect_duration, reconnect_tries_left))
            else:
                reconnect_in_seq = False
                logger.info("reconnected to Kubernetes-API")
            # endif

            if reconnect_tries_left <= 0:
                logger.error("reconnected too often, too fast in sequence which might indicate a problem. Restarting...")
                sys.exit(1)

            # if there was a successful reconnect in between, the recconnect_tries_left variable gets reset to the initial value
            if not reconnect_in_seq:
                if reconnect_count_too_fast > 0:
                    reconnect_count_too_fast = 0
                    reconnect_tries_left = reconnect_max_tries
                    logger.info("resetting reconnect-tries - reconnect tries left: %d" % reconnect_tries_left)
                # endif
            # endif
        # endwhile
    except Exception as e:
        logger.error("Exception-Type: %s, Message: %s" % (type(e).__name__, e))
        sys.exit(1)
    # endtry
# endif
