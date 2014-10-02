# Copyright (c) 2014 Cloudbase Solutions Srl
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
A Hyper-V Cluster Nova Compute driver.
"""

from nova.openstack.common import log as logging
from nova.virt.hyperv import driver
from nova.virt.hyperv.cluster import clusterops
from nova.virt.hyperv.cluster import hostops
from nova.virt.hyperv.cluster import livemigrationops

LOG = logging.getLogger(__name__)


class HyperVClusterDriver(driver.HyperVDriver):
    def __init__(self, virtapi):
        super(HyperVClusterDriver, self).__init__(virtapi)

        self._vmops = clusterops.ClusterOps(self, cluster_monitor=True)
        self._hostops = hostops.ClusterHostOps()
        self._livemigrationops = livemigrationops.ClusterLiveMigrationOps()

    def post_live_migration_at_destination(self, context, instance,
                                           network_info,
                                           block_migration=False,
                                           block_device_info=None):
        LOG.info("post_live_migration_at_destination")
        self._vmops.post_migration(instance)
        super(HyperVClusterDriver, self).post_live_migration_at_destination(
                    context, instance, network_info,
                    block_migration, block_device_info)
