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

import functools

from nova.i18n import _
from nova.openstack.common import log as logging
from nova.virt.hyperv import driver
from nova.virt.hyperv.cluster import clusterops
from nova.virt.hyperv.cluster import hostops
from nova.virt.hyperv.cluster import livemigrationops

LOG = logging.getLogger(__name__)


def call_on_proper_driver(function):
    @functools.wraps(function)
    def wrapper(self, *args, **kwargs):
        instance = None
        driver = self._get_host_driver(instance)
        getattr(driver, function.__name__)(*args, **kwargs)

    return wrapper


class HyperVClusterDriver(driver.HyperVDriver):
    def __init__(self, virtapi):
        super(HyperVClusterDriver, self).__init__(virtapi)

        self._vmops = clusterops.ClusterOps()
        self._hostops = hostops.ClusterHostOps()
        self._livemigrationops = livemigrationops.ClusterLiveMigrationOps()

        print "done with driver"

    """
    #@call_on_proper_driver
    def spawn(self, context, instance, image_meta, injected_files,
              admin_password, network_info=None, block_device_info=None):
        super(HyperVClusterDriver, self).spawn(context, instance, image_meta,
                                               injected_files, admin_password,
                                               network_info, block_device_info)
        self._clusterops.register_instance(instance)


    @call_on_proper_driver
    def reboot(self, context, instance, network_info, reboot_type,
               block_device_info=None, bad_volumes_callback=None):
        self._vmops.reboot(instance, network_info, reboot_type)

    @call_on_proper_driver
    def snapshot(self, context, instance, image_id, update_task_state):
        pass

    #@call_on_proper_driver
    def pause(self, instance):
        pass

    #@call_on_proper_driver
    def unpause(self, instance):
        pass

    #@call_on_proper_driver
    def suspend(self, instance):
        pass

    #@call_on_proper_driver
    def resume(self, context, instance, network_info, block_device_info=None):
        pass

    #@call_on_proper_driver
    def power_off(self, instance, timeout=0, retry_interval=0):
        super(HyperVClusterDriver, self).power_off(instance, timeout,
                                                   retry_interval)
        #self._clusterops.power_off(instance, timeout, retry_interval)

    #@call_on_proper_driver
    def power_on(self, context, instance, network_info,
                 block_device_info=None):
        super(HyperVClusterDriver, self).power_on(context, instance,
                                                  network_info,
                                                  block_device_info)
        #self._clusterops.power_on(instance, block_device_info)
    """

    #@call_on_proper_driver
    def live_migration(self, context, instance, dest, post_method,
                       recover_method, block_migration=False,
                       migrate_data=None):
        print "live_migration"
        print dest
        super(HyperVClusterDriver, self).live_migration(
                    context, instance, dest, post_method, recover_method,
                    block_migration, migrate_data)

    #@call_on_proper_driver
    def pre_live_migration(self, context, instance, block_device_info,
                           network_info, disk_info, migrate_data=None):

        print "pre_live_migration"
        print instance
        super(HyperVClusterDriver, self).pre_live_migration(
                    context, instance, block_device_info, network_info,
                    disk_info, migrate_data)

    #@call_on_proper_driver
    def post_live_migration_at_destination(self, context, instance,
                                           network_info,
                                           block_migration=False,
                                           block_device_info=None):
        print "post_live_migration_at_destination"
        print instance
        super(HyperVClusterDriver, self).post_live_migration_at_destination(
                    context, instance, network_info,
                    block_migration, block_device_info)

    #@call_on_proper_driver
    def check_can_live_migrate_destination(self, context, instance,
                                           src_compute_info, dst_compute_info,
                                           block_migration=False,
                                           disk_over_commit=False):
        print "check_can_live_migrate_destination"
        print instance
        super(HyperVClusterDriver, self).check_can_live_migrate_destination(
                    context, instance, src_compute_info, dst_compute_info,
                    block_migration, disk_over_commit)

    #@call_on_proper_driver
    def check_can_live_migrate_destination_cleanup(self, context,
                                                   dest_check_data):
        print "check_can_live_migrate_destination_cleanup"
        print instance
        super(HyperVClusterDriver,
              self).check_can_live_migrate_destination_cleanup(
                    context, instance, dest_check_data)

    def check_can_live_migrate_source(self, context, instance,
                                      dest_check_data):

        print "check_can_live_migrate_source"
        print instance
        super(HyperVClusterDriver, self).check_can_live_migrate_source(
            context, instance, dest_check_data)

    #@call_on_proper_driver
    def migrate_disk_and_power_off(self, context, instance, dest,
                                   flavor, network_info,
                                   block_device_info=None,
                                   timeout=0, retry_interval=0):
        print "migrate_disk_and_power_off"
        print instance
        super(HyperVClusterDriver, self).migrate_disk_and_power_off(
            context, instance, dest, flavor, network_info,
            block_device_info, timeout, retry_interval)

    #@call_on_proper_driver
    def confirm_migration(self, migration, instance, network_info):
        print "confirm_migration"
        print instance
        super(HyperVClusterDriver, self).confirm_migration(
            migration, instance, network_info)

    #@call_on_proper_driver
    def finish_revert_migration(self, context, instance, network_info,
                                block_device_info=None, power_on=True):
        print "finishing revert migration"
        print instance
        super(HyperVClusterDriver, self).finish_revert_migration(
            context, instance, network_info, block_device_info, power_on)

    #@call_on_proper_driver
    def finish_migration(self, context, migration, instance, disk_info,
                         network_info, image_meta, resize_instance,
                         block_device_info=None, power_on=True):
        print "finishing migration"
        print instance
        super(HyperVClusterDriver, self).finish_migration(
            context, migration, instance, disk_info, network_info, image_meta,
            resize_instance, block_device_info, power_on)