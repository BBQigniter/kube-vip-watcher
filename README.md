# kube-vip-watcher

The script watches pods with/where annotation `kubeVipBalanceIP: "true"` is set. The services **and** pods also need an app-label
set - for example: `app: logstash-buffer` 

Additionally, the configured service(s) need an annotation `kubeVipBalancePriority: "vkube-6, vkube-4, vkube-5"` set,
which holds, in order, the nodes where the VIP should be hosted. In the example above, this means the Kubernetes node `vkube-6` is 
the primary node. If it's not reachable or the pod on that node has an issue, the watch-script will look for another pod on the next
defined node and moves the VIP.

This particularily can be useful for pods where the services need kube-vip's `externalTrafficPolicy: Local` option configured. And
for better loadbalancing to pods (exposed with multiple VIPs - ergo RR-DNS) running on different nodes.

> It can take up to about 20 seconds until traffic reaches a local-pod after failover. I assume this is in connection to default ARP-timeout
settings.

## Workload examples

see folder `workload-examples`

Prerequisites: Kubernetes Cluster with 3 nodes named `vkube-4`, `vkube-5` and `vkube-5`

### Logstash-Buffer

* File: `logstash-buffer-statefulset-example.yaml`
* Type: StatefulSet
* Traffic-Policy: Local

Full example with a Logstash-config - A `StatefulSet` with 3 pods, each with one persistent-volume on one Kubernetes node.
Create the partitions needed as configured in the corresponding yaml manifest-parts before applying

### Echo-Server

* Type: Deployment
* Traffic-Policy: Local or Cluster (Switch it in the yaml by un-/commenting)

A simple echoserver example.

# Known Issues

* possibly a few test-cases are not covered
* better logging needed
