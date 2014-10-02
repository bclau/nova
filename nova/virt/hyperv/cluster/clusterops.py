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
Management class for Cluster VM operations.
"""

from nova.i18n import _LE
from nova.openstack.common import log as logging
from nova.virt.hyperv.cluster import clusterutils
from nova.virt.hyperv import vmops

LOG = logging.getLogger(__name__)


class ClusterOps(vmops.VMOps):

    def __init__(self, host='.'):
        super(ClusterOps, self).__init__(host)
        self._clustutils = clusterutils.ClusterUtils(host)
        self._clustutils.check_cluster_state()

        self._failoverutils = clusterutils.ClusterFailoverUtils(host)
        self._failoverutils.start_failover_listener_daemon()

    def get_instance_host(self, instance):
        return self._clustutils.get_instance_host(instance.name)

    def create_instance(self, instance, network_info, block_device_info,
                        root_vhd_path, eph_vhd_path):
        super(ClusterOps, self).create_instance(instance, network_info,
                                                block_device_info,
                                                root_vhd_path, eph_vhd_path)
        try:
            self._clustutils.add_vm_to_cluster(instance.name)
            self._failoverutils.add_to_cluster_map(instance.name, instance.id)
        except Exception as e:
            LOG.error(_LE('Creating config drive failed with error: %s'),
                      e, instance=instance)

    def destroy(self, instance, network_info=None, block_device_info=None,
                destroy_disks=True):
        try:
            self._clustutils.delete(instance.name)
            self._failoverutils.clear_from_cluster_map(instance.name)
        except Exception as e:
            LOG.error(_LE('Creating config drive failed with error: %s'),
                      e, instance=instance)

        super(ClusterOps, self).destroy(instance, network_info,
                                        block_device_info, destroy_disks)

    def power_off(self, instance, timeout=0, retry_interval=0):
        super(ClusterOps, self).power_off(instance, timeout, retry_interval)
        #self._clustutils.take_offline(instance.name)

    def power_on(self, instance, block_device_info=None):
        super(ClusterOps,self).power_on(instance, block_device_info)
        #self._clustutils.bring_online(instance.name)
