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

    def live_migration(self, context, instance, dest, post_method,
                       recover_method, block_migration=False,
                       migrate_data=None):
        LOG.info("live_migration")
        LOG.info(dest)
        super(HyperVClusterDriver, self).live_migration(
                    context, instance, dest, post_method, recover_method,
                    block_migration, migrate_data)

    def pre_live_migration(self, context, instance, block_device_info,
                           network_info, disk_info, migrate_data=None):

        LOG.info("pre_live_migration")
        LOG.info(instance)
        super(HyperVClusterDriver, self).pre_live_migration(
                    context, instance, block_device_info, network_info,
                    disk_info, migrate_data)

    def post_live_migration_at_destination(self, context, instance,
                                           network_info,
                                           block_migration=False,
                                           block_device_info=None):
        LOG.info("post_live_migration_at_destination")
        LOG.info(instance)
        super(HyperVClusterDriver, self).post_live_migration_at_destination(
                    context, instance, network_info,
                    block_migration, block_device_info)

    def check_can_live_migrate_destination(self, context, instance,
                                           src_compute_info, dst_compute_info,
                                           block_migration=False,
                                           disk_over_commit=False):
        LOG.info("check_can_live_migrate_destination")
        LOG.info(instance)
        return super(HyperVClusterDriver, self).check_can_live_migrate_destination(
                    context, instance, src_compute_info, dst_compute_info,
                    block_migration, disk_over_commit)

    def check_can_live_migrate_destination_cleanup(self, context,
                                                   dest_check_data):
        LOG.info("check_can_live_migrate_destination_cleanup")
        super(HyperVClusterDriver,
              self).check_can_live_migrate_destination_cleanup(
                    context, dest_check_data)

    def check_can_live_migrate_source(self, context, instance,
                                      dest_check_data, block_device_info=None):

        LOG.info("check_can_live_migrate_source")
        LOG.info(instance)
        return super(HyperVClusterDriver, self).check_can_live_migrate_source(
            context, instance, dest_check_data, block_device_info)

    def migrate_disk_and_power_off(self, context, instance, dest,
                                   flavor, network_info,
                                   block_device_info=None,
                                   timeout=0, retry_interval=0):
        LOG.info("migrate_disk_and_power_off")
        LOG.info(instance)
        return super(HyperVClusterDriver, self).migrate_disk_and_power_off(
            context, instance, dest, flavor, network_info,
            block_device_info, timeout, retry_interval)

    def confirm_migration(self, migration, instance, network_info):
        LOG.info("confirm_migration")
        LOG.info(instance)
        super(HyperVClusterDriver, self).confirm_migration(
            migration, instance, network_info)

    def finish_revert_migration(self, context, instance, network_info,
                                block_device_info=None, power_on=True):
        LOG.info("finishing revert migration")
        LOG.info(instance)
        super(HyperVClusterDriver, self).finish_revert_migration(
            context, instance, network_info, block_device_info, power_on)

    def finish_migration(self, context, migration, instance, disk_info,
                         network_info, image_meta, resize_instance,
                         block_device_info=None, power_on=True):
        LOG.info("finishing migration")
        LOG.info(instance)
        super(HyperVClusterDriver, self).finish_migration(
            context, migration, instance, disk_info, network_info, image_meta,
            resize_instance, block_device_info, power_on)