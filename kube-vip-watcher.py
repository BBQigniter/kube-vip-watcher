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
from kubernetes import client, config, watch


# initialize globally
# Configs can be set in Configuration class directly or using helper utility
# for loading config if script executed manually from commandline
# config.load_kube_config()
# for loading config if script is running as pod/container
config.load_incluster_config()

v1_core = client.CoreV1Api()
v1_coordination = client.CoordinationV1Api()

w = watch.Watch()


def check_node_state(node_name):
    try:
        node_status = v1_core.read_node_status(node_name)
        node_conditions = node_status.status.conditions
    except Exception as e:
        print("Exception when calling CoreV1Api->read_node_status: %s\n" % e)
        node_conditions = []
    # endtry

    for condition in node_conditions:
        # print("%s condition:\n%s" % (node_name, condition))
        # we check for type "Ready" and look at the status
        if condition.type == "Ready":
            if condition.status == "True":
                print("Node %s marked as 'Ready'" % node_name)
                return True
        # endif
    # endfor
    return False
# enddef


def check_container_state(pod_container_statuses):
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
    try:
        services = v1_core.list_namespaced_service(namespace)
    except Exception as e:
        print("Exception when calling CoreV1Api->list_namespaced_service: %s\n" % e)
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
        print("None-Explicitly pod named service(s) found")
        return list_of_services
    else:
        print("Explicit pod named service found")
        return [single_service]
    # endif
# enddef


def get_namespaced_leases(service_name, namespace):
    try:
        # leases created by kube-vip are prefixed with "kubevip-"
        lease = v1_coordination.read_namespaced_lease("kubevip-" + service_name, namespace)
        lease_name = lease.metadata.name
        lease_holder = lease.spec.holder_identity
        print("Lease: %s - Node: %s" % (lease_name, lease_holder))
        return lease_holder
    except:
        print("No Lease kubevip-%s found" % service_name)
        return None
    # endtry
# enddef


def get_namespaced_pods_with_label_on_node(namespace, pod_labels_app, pod_node_name):
    try:
        pods = v1_core.list_namespaced_pod(namespace)
    except Exception as e:
        print("Exception when calling CoreV1Api->list_namespaced_pod: %s\n" % e)
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

    print("Number of suitable pods on node %s: %d" % (pod_node_name, len(list_of_pods)))
    return list_of_pods
# enddef


def balance(list_of_services, pod_container_statuses, pod_node_name, pod_labels_app):
    if len(list_of_services) == 0:
        print("No service(s) found with needed app-label")
        return False  # end def
    else:
        for service in list_of_services:
            try:
                # get the value of annotation 'kubeVipBalancePriority' and other values
                service_name = service.metadata.name
                namespace = service.metadata.namespace
                try:
                    traffic_policy = service.spec.external_traffic_policy
                except:
                    traffic_policy = None
                # endtry
                balance_priority_string = service.metadata.annotations['kubeVipBalancePriority']
                balance_priority_order = str(balance_priority_string).split(",")
                balance_priority_order = [sub_element.strip() for sub_element in balance_priority_order]  # remove whitespaces for each element in the list fixed_section
                print("Service: %s - Balance Priority: %s - Traffic Policy: %s" % (service_name, balance_priority_order, traffic_policy))
            except:
                print("Service missing annotation 'kubeVipBalancePriority'")
                return False  # end def
            # endtry

            try:
                lease_holder = get_namespaced_leases(service_name, namespace)

                # no we check if pod is running and if the lease_holder is corresponding to the first node in the priority list
                # if not we patch the holder-value in the lease after checking that the node to swtich to is available and has a running pod
                if lease_holder == balance_priority_order[0] and check_container_state(pod_container_statuses) and check_node_state(pod_node_name):
                    print("Lease holder OK and pod's containers are ready")
                    return True  # end def
                else:
                    print("Detected wrong lease holder, issues with pod's containers or the node - further checking if VIP must be moved")
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
                                        print(pod)
                                        try:
                                            pod_deletion_timestamp = pod.metadata.deletion_timestamp
                                            print("pod deletion event detected: %s" % str(pod_deletion_timestamp))
                                        except:
                                            # print("pod_deletion not found")
                                            # print(item)
                                            pod_deletion_timestamp = None
                                        """

                                        # if the pod is on the same node where the other failed and the remaining pod is healthy, the VIP doesn't need to be moved
                                        if check_container_state(pod.status.container_statuses) \
                                                and pod.spec.node_name == pod_node_name \
                                                and lease_holder == balance_priority_order[0]:
                                            print("Found healthy pod %s on node %s. Lease holder OK and no need to move VIP" % (pod.metadata.name, pod.spec.node_name))
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
                                                print("Exception when calling CoordinationV1Api->patch_namespaced_lease: %s\n" % e)
                                                sys.exit(1)
                                            # endtry

                                            try:
                                                # if we do not patch this value kube-vip removes the VIP sometimes completely for about a minute
                                                service_body_patch = {"metadata": {"annotations": {"kube-vip.io/vipHost": node}}}
                                                service_patch_response = v1_core.patch_namespaced_service(service.metadata.name, namespace, service_body_patch)
                                            except Exception as e:
                                                print("Exception when calling CoreV1Api->patch_namespaced_service: %s\n" % e)
                                                sys.exit(1)
                                            # endtry

                                            if node == balance_priority_order[0]:
                                                print("HOLDER CHANGED TO PRIMARY NODE %s and service's annotation 'kube-vip.io/vipHost' updated to %s" % (
                                                    lease_patch_response.spec.holder_identity,
                                                    service_patch_response.metadata.annotations['kube-vip.io/vipHost'])
                                                )
                                                return True  # end def
                                            else:
                                                print("HOLDER CHANGED TO ALTERNATIVE NODE %s and service's annotation 'kube-vip.io/vipHost' updated to %s" % (
                                                    lease_patch_response.spec.holder_identity,
                                                    service_patch_response.metadata.annotations['kube-vip.io/vipHost'])
                                                )
                                                return True  # end def
                                            # endif
                                            # optional possible to only move if really needed with:
                                            # else:
                                            #     print("Traffic-Policy not 'Local' and node %s available so no need to move VIP" % node)
                                            # endif
                                        # endif
                                    # endfor
                                else:
                                    print("No remaining pods on node found - continuing with search for suitable node with healthy pods.")
                                # endif
                            except Exception as e:
                                print("Exception when calling get_namespaced_pods_with_label_on_node: %s\n" % e)
                            # endtry
                        else:
                            print("Node %s not available - continuing with search for suitable node with healthy pods." % node)
                        # endif
                    else:
                        print("No suitable node found")
                        return False  # end def
                    # endfor
                # endif
            except:
                print("No Lease kubevip-%s found" % service.metadata.name)
                return False
            # endtry
        # endfor
    # endif
# enddef


def main():
    for item in w.stream(v1_core.list_pod_for_all_namespaces, timeout_seconds=0):
        try:
            # first we get pods where we need the VIP balanced
            if bool(item['object'].metadata.annotations['kubeVipBalanceIP']):
                # testing something
                # if item['object'].metadata.deletion_timestamp is not None:
                #     print(str(item['object'].metadata.deletion_timestamp))
                pod_name = item['object'].metadata.name
                namespace = item['object'].metadata.namespace
                try:
                    pod_labels_app = item['object'].metadata.labels['app']
                except:
                    pod_labels_app = None
                    print("App-Label not set")
                # endtry

                if pod_labels_app is not None:
                    pod_node_name = item['object'].spec.node_name
                    pod_status_phase = item['object'].status.phase
                    pod_container_statuses = item['object'].status.container_statuses

                    print("Namespace %s - Pod: %s - App-Label: %s - Node-Name: %s - Status: %s - Stream-Event-Type: %s" % (namespace, pod_name, pod_labels_app, pod_node_name, pod_status_phase, item['type']))
                    # in the next step we will check if a rebalance is needed

                    # then we get the service corresponding to the pod
                    list_of_services = get_namespaced_services_with_label(namespace, pod_labels_app, pod_name)
                    if len(list_of_services) >= 1:
                        balance(list_of_services, pod_container_statuses, pod_node_name, pod_labels_app)
                    else:
                        print("No services found")
                    # endif
                else:
                    print("Ignoring %s in Namespace %s because App-Label is not set" % (pod_name, namespace))
                # endif
        except Exception as e:
            # if pod has not such annotation just skip
            pass
        # endtry
    # endfor
# endmain


if __name__ == '__main__':
    main()
# endif
