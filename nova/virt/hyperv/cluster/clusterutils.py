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

from oslo.config import cfg

from nova import exception
from nova.i18n import _, _LE
from nova.openstack.common import log as logging

LOG = logging.getLogger(__name__)

cluster_opts = [
    cfg.StrOpt('cluster_name',
               default='Test-Cluster',
               help='Used for managing the cluster.'),
]

CONF = cfg.CONF
CONF.register_opts(cluster_opts, 'hyperv')


class _fixed_wmi_namespace(wmi._wmi_namespace):
    """WMI Namespace class fix necessary to connect to the
    /root/MSCluster namespace.
    """

    def __nonzero__(self):
        """This is called each time this object is an argument to a conditional
        statement. If this method is not present, __getattr__ would be called
        instead. That would cause an endless recursive call.
        Strangely, this was not an issue before.

        Error encountered running:
        conn = wmi.WMI(moniker='//./root/MSCluster')
        conn.MSCluster_Cluster

        Also, this should improve performance as well, since it avoids useless
        recursive calls.
        """

        return True


# replace the WMI module's _wmi_namespace with this fix.
wmi._wmi_namespace = _fixed_wmi_namespace


class ClusterUtilsBase(object):

    _MSCLUSTER_NODE = 'MSCluster_Node'
    _MSCLUSTER_RES = 'MSCluster_Resource'
    _MSCLUSTER_RES_GROUP = 'MSCluster_ResourceGroup'
    _MSCLUSTER_RES_TYPE = 'MSCluster_ResourceType'

    _CLUSTER_RUNNING = 'OK'

    _NODE_ACTIVE = 0

    _VM_BASE_NAME = 'Virtual Machine %s'
    _VM_TYPE = 'Virtual Machine'
    _VM_GROUP_TYPE = 111

    _MS_CLUSTER_NAMESPACE = '//%s/root/MSCluster'

    def __init__(self, host='.'):
        print "creating ClusterUtils"
        if sys.platform == 'win32':
            cluster_name = CONF.hyperv.cluster_name
            self._init_hyperv_conn(cluster_name, host)

    def _init_hyperv_conn(self, cluster_name, host):
        self._conn = wmi.WMI(moniker=self._MS_CLUSTER_NAMESPACE % host)
        self._cluster = self._conn.MSCluster_Cluster(Name=cluster_name)[0]

        #extract this node name from cluster's path
        path = self._cluster.path_()
        self._this_node = re.search(r'\\\\(.*)\\root', path,
                                    re.IGNORECASE).group(1)

    def check_cluster_state(self):
        if not self._cluster:
            raise Exception(_("No cluster found."))
        if len(self._get_cluster_nodes()) < 1:
            raise Exception(_("Not enough cluster nodes."))

        #if self._cluster.Status != self._CLUSTER_RUNNING:
        #    # Start the Cluster Service for the cluster.
        #    self._cluster.MSCluster_Service()[0].Start()
        #   #raise Exception("The cluster is not running.")

    def get_node_name(self):
        return self._this_node

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

    def _lookup_vm_group_check(self, vm_name):
        vm = self._lookup_vm_group(vm_name)
        if not vm:
            raise exception.NotFound(_('VM not found: %s') % vm_name)
        return vm

    def _lookup_vm_group(self, vm_name):
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

    def _lookup_vm_check(self, vm_name):
        vm = self._lookup_vm(vm_name)
        if not vm:
            raise exception.NotFound(_('VM not found: %s') % vm_name)
        return vm

    def _lookup_vm(self, vm_name):
        vm_name = self._VM_BASE_NAME % vm_name
        # might want ResourceGroup? :/
        # migration will work osamli.
        vms = self._conn.MSCluster_Resource(Name=vm_name)
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
        return [n.Name for n in nodes if n.State == self._NODE_ACTIVE]

    def get_vm_host(self, vm_name):
        self._lookup_vm_group_check(vm_name).OwnerNode

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
            vm.DestroyGroup(1)

    def vm_exists(self, vm_name):
        return self._lookup_vm(vm_name) is not None

    def live_migrate_vm(self, vm_name, new_host):
        self._migrate_vm(vm_name, new_host, self._LIVE_MIGRATION_TYPE)

    def _migrate_vm(self, vm_name, new_host, migration_type):
        vm_group = self._lookup_vm_group_check(vm_name)
        try:
            vm_group.MoveToNewNodeParams(self._IGNORE_LOCKED, new_host,
                                         [migration_type])
        except Exception as e:
            LOG.error(_LE('Exception during cluster live migration of %s '
                          'to %s: %s'), vm_name, new_host, e)


class ClusterFailoverMonitor(ClusterUtilsBase):

    _WMI_EVENT_TIMEOUT_MS = 100
    _WMI_EVENT_CHECK_INTERVAL = 2
    _MODIFICATION = 'modification'

    def __init__(self, host='.'):
        super(ClusterFailoverMonitor, self).__init__(host)

        if sys.platform == 'win32':
            self._listener = None
            self._vm_map = {}

            # listen for any OwnerNode modifications occur (failover) for any
            # VMs within _WMI_EVENT_CHECK_INTERVAL + 1 seconds.
            # Resource or ResourceGroup?
            self._watcher = self._conn.MSCluster_Resource.watch_for(
                self._MODIFICATION,
                delay_secs=(self._WMI_EVENT_CHECK_INTERVAL + 1),
                fields=['OwnerNode'], Type=self._VM_TYPE)

            self._update_vm_map()

    def _update_vm_map(self):
        for vm_name, vm_host in self._list_vm_hosts():
            self._vm_map[vm_name] = vm_host

    def _list_vm_hosts(self):
        return ((r.Name, r.OwnerNode) for r in self._get_vms())

    def add_to_cluster_map(self, vm_name, vm_id):
        self._vm_map[vm_name] = self._this_node

    def get_from_cluster_map(self, vm_name):
        return self._vm_map.get(vm_name, None)

    def clear_from_cluster_map(self, vm_name):
        if vm_name in self._vm_map:
            del self._vm_map[vm_name]

    def monitor(self, callback):
        """Creates a looping call to check for new WMI MSCluster_Resource
        events.

        This method will poll the last _WMI_EVENT_CHECK_INTERVAL + 1
        seconds for new events and listens for _WMI_EVENT_TIMEOUT_MS
        miliseconds, since listening is a thread blocking action.

        Any event object caught will then be processed.
        """
        vm_name = None
        new_host = None
        try:
            # wait for new event for _WMI_EVENT_TIMEOUT_MS miliseconds.
            wmi_object = self._watcher(self._WMI_EVENT_TIMEOUT_MS)
            print "wmi_object modified:"
            print wmi_object
            vm_name = wmi_object.Name.split()[-1]
            new_host = wmi_object.OwnerNode

            callback(new_host, vm_name)

            if vm_name:
                # update the vm map, to remain consistent with any change.
                self._vm_map[vm_name] = new_host

        except wmi.x_wmi_timed_out:
            # wmi watcher is blocking, so a timeout is necessary.
            # TODO(claudiub): find a better way?
            pass