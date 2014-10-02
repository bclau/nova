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
Management class for cluster live migration VM operations.
"""

from nova import exception
from nova.openstack.common import excutils
from nova.openstack.common import log as logging
from nova.virt.hyperv.cluster import clusterutils
from nova.virt.hyperv import livemigrationops

LOG = logging.getLogger(__name__)


class ClusterLiveMigrationOps(livemigrationops.LiveMigrationOps):
    def __init__(self, host='.'):
        super(ClusterLiveMigrationOps, self).__init__(host)
        self._clustutils = clusterutils.ClusterUtils()

    def _is_instance_clustered(self, instance_name):
        return self._clustutils.vm_exists(instance_name)

    def live_migration(self, context, instance_ref, dest, post_method,
                       recover_method, block_migration=False,
                       migrate_data=None):
        LOG.debug("live_migration called", instance=instance_ref)
        instance_name = instance_ref.name
        clustered = self._is_instance_clustered(instance_name)

        if (dest not in self._clustutils.get_cluster_node_names()
                or not clustered):
            # destination is not in same cluster or instance not clustered.
            # do a normal live migration.
            # TODO(claudiub): add another case if the VM is in another,
            # reachable cluster.
            if clustered:
                # remove VM from cluster.
                self._clustutils.delete(instance_name)

            super(ClusterLiveMigrationOps, self).live_migrate_vm(
                context, instance_ref, dest, post_method, recover_method,
                block_migration, migrate_data)
            return
        elif self._clustutils.get_vm_host(instance_name) == dest:
            # VM is already migrated. Do nothing.
            # this can happen when the VM has been failovered.
            return

        # destination is in the same cluster.
        # perform a clustered live migration.

        try:
            self._clustutils.live_migrate_vm(instance_name, dest)
        except exception.NotFound:
            with excutils.save_and_reraise_exception():
                LOG.debug("Calling live migration recover_method "
                          "for instance: %s", instance_name)
                recover_method(context, instance_ref, dest, block_migration)

        LOG.debug("Calling live migration post_method for instance: %s",
                  instance_name)
        post_method(context, instance_ref, dest, block_migration)

    def post_live_migration_at_destination(self, ctxt, instance_ref,
                                           network_info, block_migration):
        if not self._is_instance_clustered(instance_ref.name):
            super(ClusterLiveMigrationOps,
                  self).post_live_migration_at_destination(
                ctxt, instance_ref, network_info, block_migration)
        # TODO(claudiub): problem setting up the log pipe. Skip it for now.

    def pre_live_migration(self, context, instance, block_device_info,
                           network_info):
        # TODO(claudiub): adapt live migration:
        # login_storage_targets
        if not self._is_instance_clustered(instance.name):
            super(ClusterLiveMigrationOps, self).pre_live_migration(
                context, instance, block_device_info, network_info)
            return

        # don't have to get the image from glance.
        # it already exists on the configured share.
        # just login storage targets, if any.

        self._volumeops.initialize_volumes_connection(block_device_info)
