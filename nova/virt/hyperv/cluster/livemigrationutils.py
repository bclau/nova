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
Utility class for cluster live migration VM operations.
"""

import sys

if sys.platform == 'win32':
    import wmi

from nova.virt.hyperv.cluster import clusterutils
from nova.virt.hyperv import livemigrationutils


class ClusterLiveMigrationUtils(livemigrationutils.LiveMigrationUtils):

    def __init__(self, host='.'):
        super(ClusterLiveMigrationUtils, self).__init__(host)
        self._clustutils = clusterutils.ClusterUtils()

    def check_live_migration_config(self):
        pass

    def live_migrate_vm(self, vm_name, dest_host):
        if not self._clustutils.vm_exists(vm_name):
            # VM not present as clustered resource.
            # may exist, but not clustered.
            # do a normal live migration.
            return super(ClusterLiveMigrationUtils, self).live_migrate_vm(
                vm_name, dest_host)

        elif self._clustutils.get_vm_host(vm_name) == dest_host:
            # VM is already migrated. Do nothing.
            # this can happen when the VM has been failovered.
            return []
        elif dest_host in self._clustutils.get_cluster_node_names():
            # destination is in the same cluster.
            # perform a clustered live migration.
            self._clustutils.live_migrate_vm(vm_name, dest_host)

            # return... what?
            return []
        else:
            # destination is not in same cluster.
            # remove VM from cluster.
            # do a normal live migration.
            # TODO(claudiub): add another case if the VM is in another,
            # reachable cluster.
            self._clustutils.delete(vm_name)
            return super(ClusterLiveMigrationUtils, self).live_migrate_vm(
                vm_name, dest_host)
