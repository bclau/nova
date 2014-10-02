# Copyright 2014 Cloudbase Solutions Srl
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Utility class for VM related operations on Hyper-V.
"""

import re
import sys

if sys.platform == 'win32':
    import wmi

import novaclient.client
from oslo.config import cfg

from nova import exception
from nova.i18n import _, _LW
from nova.openstack.common import log as logging
from nova.openstack.common import loopingcall

CONF = cfg.CONF
LOG = logging.getLogger(__name__)

cluster_opts = [
    cfg.StrOpt('cluster_name',
               default='Test-Cluster',
               help='Required for managing the cluster. Will create one if '
                    'not exists. Will start the cluster if necessary.'),
]

CONF = cfg.CONF
CONF.register_opts(cluster_opts, 'hyperv')


class ClusterUtilsBase(object):

    _MSCLUSTER_NODE = 'MSCluster_Node'
    _MSCLUSTER_RES = 'MSCluster_Resource'
    _MSCLUSTER_RES_GROUP = 'MSCluster_ResourceGroup'
    _MSCLUSTER_RES_TYPE = 'MSCluster_ResourceType'

    _CLUSTER_RUNNING = 'OK'

    _VM_BASE_NAME = 'Virtual Machine %s'
    _VM_TYPE = 'Virtual Machine'
    _VM_GROUP_TYPE = 111

    _MS_CLUSTER_NAMESPACE = '//%s/root/MSCluster'

    def __init__(self, host='.'):
        print "creating ClusterUtils"
        if sys.platform == 'win32':
            cluster_name = CONF.hyperv.cluster_name
            self._init_hyperv_conn(cluster_name, host)
            self._check_cluster_state()
        print "done"

    def _init_hyperv_conn(self, cluster_name, host):
        self._conn = wmi.WMI(moniker=self._MS_CLUSTER_NAMESPACE % host)
        print cluster_name, host
        self._cluster = self._conn.MSCluster_Cluster(Name=cluster_name)[0]

        #extract this node name from cluster's path
        path = self._cluster.path_()
        self._this_node = re.search(r'\\\\(.*)\\root', path,
                                    re.IGNORECASE).group(1)

    def _check_cluster_state(self):
        if not self._cluster:
            raise Exception("No cluster found.")
        if len(self._get_cluster_nodes()) < 1:
            raise Exception("Not enough cluster nodes.")

        #if self._cluster.Status != self._CLUSTER_RUNNING:
        #    # Start the Cluster Service for the cluster.
        #    self._cluster.MSCluster_Service()[0].Start()
        #   #raise Exception("The cluster is not running.")

    def _get_cluster_nodes(self):
        return self._cluster.associators(
            wmi_result_class=self._MSCLUSTER_NODE)

    def _get_vms(self):
        resources = self._cluster.associators(
            wmi_result_class=self._MSCLUSTER_RES_GROUP)
        return (r for r in resources
                if hasattr(r, 'Type') and r.Type == self._VM_GROUP_TYPE)


class ClusterUtils(ClusterUtilsBase):

    _LIVE_MIGRATION_TYPE = 4

    _IGNORE_LOCKED = 1
    _NOT_IGNORE_LOCKED = 0 # there should be a better name..

    def _lookup_vm_check(self, vm_name):
        vm = self._lookup_vm(vm_name)
        if not vm:
            raise exception.NotFound(_('VM not found: %s') % vm_name)
        return vm

    def _lookup_vm(self, vm_name):
        # vm_name = self._VM_BASE_NAME % vm_name
        # might want ResourceGroup? :/
        # migration will work osamli.
        vms = self._conn.MSCluster_ResourceGroup(Name=vm_name)
        n = len(vms)
        if n == 0:
            return None
        elif n > 1:
            raise vmutils.HyperVException(_('Duplicate VM name '
                                            'found: %s') % vm_name)
        else:
            return vms[0]

    def get_cluster_node_names(self):
        nodes = self._get_cluster_nodes()
        return [n.Name for n in nodes]

    def get_vm_host(self, vm_name):
        self._lookup_vm_check(vm_name).OwnerNode

    def list_instances(self):
        return [r.Name for r in self._get_vms()]

    def list_instance_uuids(self):
        return [r.Id for r in self._get_vms()]

    def add_vm_to_cluster(self, vm_name):
        self._cluster.AddVirtualMachine(vm_name)

    def bring_online(self, vm_name):
        vm = self._lookup_vm_check(vm_name)
        vm.BringOnline()

    def take_offline(self, vm_name):
        vm = self._lookup_vm(vm_name)
        if vm:
            vm.TakeOffline()

    def delete(self, vm_name):
        # TODO(claudiub): name might be confusing.
        vm = self._lookup_vm(vm_name)
        if vm:
            # or DestroyGroup?
            vm.DestroyGroup()

    def vm_exists(self, vm_name):
        return self._lookup_vm(vm_name) is not None

    def live_migrate_vm(self, vm_name, new_host):
        self._migrate_vm(vm_name, new_host, self._LIVE_MIGRATION_TYPE)

    def _migrate_vm(self, vm_name, new_host, migration_type):
        vm = self._lookup_vm_check(vm_name)
        try:
            vm.MoveToNewNodeParams(self._IGNORE_LOCKED, new_host,
                                   [migration_type])
        except Exception as e:
            # It throws Exception in Powershell, so I'm expecting it does
            # here as well. It works though.
            print e


class ClusterFailoverUtils(ClusterUtilsBase):

    _WMI_EVENT_TIMEOUT_MS = 100
    _WMI_EVENT_CHECK_INTERVAL = 2
    _MODIFICATION = 'modification'

    _INSTANCE_NAME_ATTR = 'OS-EXT-SRV-ATTR:instance_name'

    def __init__(self, host='.'):
        super(ClusterFailoverUtils, self).__init__(host)

        if sys.platform == 'win32':
            self._compute_client = self._create_compute_client()

            self._listener = None
            self._instance_map = {}
            self._vm_map = {}

            self._update_instance_map()
            self._update_vm_map()

    def _create_compute_client(self):
        # Novaclient will not execute operations for anyone but the
        # identified user, so a new client needs to be created for

        nova_version = '3'
        auth_url = "https://192.168.40.140:5000/v2.0/"
        dscv = False
        region = None

        client_args = ('admin', 'Passw0rd', 'admin',
                       'http://192.168.40.140:35357/v2.0/')

        # Create our default Nova client to use in testing
        service_type = "compute"
        endpoint_type = "publicURL"
        return novaclient.client.Client(nova_version,
                                        *client_args,
                                        service_type=service_type,
                                        endpoint_type=endpoint_type,
                                        region_name=region,
                                        no_cache=True,
                                        insecure=dscv,
                                        http_log_debug=True)

    def _update_instance_map(self):
        for server in self._compute_client.servers.list():
            s_dict = server.to_dict()
            self._instance_map[s_dict[self._INSTANCE_NAME_ATTR]] = server.id

    def _update_vm_map(self):
        for vm_name, vm_host in self._list_vm_hosts():
            self._vm_map[vm_name] = vm_host

    def _list_vm_hosts(self):
        return ((r.Name, r.OwnerNode) for r in self._get_vms())

    def add_to_cluster_map(self, vm_name, vm_id):
        self._instance_map[vm_name] = vm_id
        self._vm_map[vm_name] = self._this_node

    def clear_from_cluster_map(self, vm_name):
        if vm_name in self._instance_map:
            del self._instance_map[vm_name]
        if vm_name in self._vm_map:
            del self._vm_map[vm_name]

    def start_failover_listener_daemon(self):
        if self._listener:
            return

        # listen for any OwnerNode modifications occur (failover) for any VMs
        # within _WMI_EVENT_CHECK_INTERVAL + 1 seconds.
        # Resource or ResourceGroup?
        self._watcher = self._conn.MSCluster_Resource.watch_for(
            self._MODIFICATION,
            delay_secs=(self._WMI_EVENT_CHECK_INTERVAL + 1),
            fields=['OwnerNode'], Type=self._VM_TYPE)

        def _looper():
            try:
                # wait for new event for _WMI_EVENT_TIMEOUT_MS miliseconds.
                wmi_object = self._watcher(self._WMI_EVENT_TIMEOUT_MS)
                print "wmi_object modified:"
                print wmi_object
                vm_name = wmi_object.Name.split()[-1]
                new_host = wmi_object.OwnerNode
                self._failover_migrate(vm_name, new_host)

                # update the vm map, to remain consistent with any change.
                self._vm_map[vm_name] = new_host
            except wmi.x_wmi_timed_out:
                # wmi watcher is blocking, so a timeout is necessary.
                # TODO(claudiub): find a better way?
                pass
            except Exception as e:
                print e

        print "starting failover daemon"
        self._running_daemon = True
        self._listener = loopingcall.FixedIntervalLoopingCall(_looper)

        # check for events every _WMI_EVENT_CHECK_INTERVAL period.
        self._listener.start(interval=self._WMI_EVENT_CHECK_INTERVAL)
        print "done"

    def _failover_migrate(self, vm_name, new_host):
        if self._vm_map[vm_name] == new_host:
            # OwnerNode did not change.
            return
        elif self._vm_map[vm_name] != self._this_node:
            # the failovered VM did not originate from this node.
            return

        compute_vm = self._get_compute_vm_by_instance_name(vm_name)
        print "Failovering %s to %s" % (vm_name, new_host)
        #compute_vm.live_migrate(host=new_host)

    def _get_compute_vm_by_instance_name(self, instance_name):
        vm_id = self._instance_map.get(instance_name, None)
        if not vm_id:
            self._update_instance_map()

        vm_id = self._instance_map.get(instance_name, None)
        if not vm_id:
            return

        return self._compute_client.servers.get(vm_id)
