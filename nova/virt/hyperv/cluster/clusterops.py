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

from oslo.config import cfg

from nova.api.metadata import base as instance_metadata
from nova import exception
from nova.i18n import _, _LI, _LW
from nova.openstack.common import log as logging
from nova.virt.hyperv.cluster import clusterutils
from nova.virt.hyperv import constants
from nova.virt.hyperv import utilsfactory
from nova.virt.hyperv import vmutils

from nova.virt.hyperv import vmops

LOG = logging.getLogger(__name__)
CONF = cfg.CONF


class ClusterOps(vmops.VMOps):

    def __init__(self, host='.'):
        super(ClusterOps, self).__init__(host)
        self._clustutils = clusterutils.ClusterUtils(host)
        self._failoverutils = clusterutils.ClusterFailoverUtils(host)
        self._failoverutils.start_failover_listener_daemon()

    def get_instance_host(self, instance):
        return self._clustutils.get_instance_host(instance.name)

    #def register_instance(self, instance):
    #    self._clustutils.add_vm_to_cluster(instance.name, instance.id)

    #def list_instance_uuids(self):
    #    self._clustutils.list_uuids()

    #def list_instances(self):
    #    self._clustutils.list_instances()

    # def get_info(self, instance):

    def create_instance(self, instance, network_info, block_device_info,
                        root_vhd_path, eph_vhd_path):
        super(ClusterOps, self).create_instance(instance, network_info,
                                                block_device_info,
                                                root_vhd_path, eph_vhd_path)
        self._clustutils.add_vm_to_cluster(instance.name)
        self._failoverutils.add_to_cluster_map(instance.name, instance.id)

    def destroy(self, instance, network_info=None, block_device_info=None,
                destroy_disks=True):
        self._clustutils.delete(instance.name)
        self._failoverutils.clear_from_cluster_map(instance.name)
        super(ClusterOps, self).destroy(instance, network_info,
                                        block_device_info, destroy_disks)

    """
    def reboot(self, instance, network_info, reboot_type):

    def pause(self, instance):
        super(ClusterOps, self).pause(instance)

    def unpause(self, instance):
        super(ClusterOps, self).unpause(instance)

    def suspend(self, instance):
        super(ClusterOps, self).suspend(instance)

   	def resume(self, instance):
        super(ClusterOps, self).resume(instance)
    """

    def power_off(self, instance, timeout=0, retry_interval=0):
        super(ClusterOps, self).power_off(instance, timeout, retry_interval)
        self._clustutils.take_offline(instance.name)

    def power_on(self, instance, block_device_info=None):
        super(ClusterOps,self).power_on(instance, block_device_info)
        self._clustutils.bring_online(instance.name)
