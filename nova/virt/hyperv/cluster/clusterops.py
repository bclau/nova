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

import novaclient.client
from oslo.config import cfg

from nova.i18n import _LI, _LE
from nova import context
from nova import network
from nova import objects
from nova.openstack.common import log as logging
from nova.openstack.common import loopingcall
from nova.virt import block_device
from nova.virt.hyperv.cluster import clusterutils
from nova.virt.hyperv import vmops
from nova.virt.hyperv import volumeops
from nova import volume

LOG = logging.getLogger(__name__)

nova_client_opts = [
    cfg.StrOpt('version',
               default='1.1',
               help='Nova client version used for failover migration '
                    'notifications.'),
    cfg.StrOpt('admin_auth_url',
               default=None,
               help='Keystone admin authentification URL.'),
    cfg.StrOpt('admin_tenant_name',
               default=None,
               help='Keystone admin tenant name.'),
    cfg.StrOpt('admin_username',
               default=None,
               help='Keystone admin user name.'),
    cfg.StrOpt('admin_password',
               default=None,
               help='Keystone admin user password.'),
    cfg.StrOpt('service_type',
               default="compute",
               help='Service Type.'),
    cfg.StrOpt('endpoint_type',
               default="publicURL",
               help='Endpoint Type.'),
]

CONF = cfg.CONF
CONF.register_opts(nova_client_opts, 'nova_client')


class ClusterOps(vmops.VMOps):

    # TODO(claudiub): make configurable instead.
    _EVENT_CHECK_INTERVAL = 2

    _INSTANCE_NAME_ATTR = 'OS-EXT-SRV-ATTR:instance_name'
    _INSTANCE_VOLUMES_ATTR = 'os-extended-volumes:volumes_attached'
    _ALL_TENANTS = 1

    _SEARCH_OPS = {'all_tenants': _ALL_TENANTS}

    def __init__(self, driver, host='.', cluster_monitor=False):
        super(ClusterOps, self).__init__(host)
        self._clustutils = clusterutils.ClusterUtils(host)
        self._clustutils.check_cluster_state()

        self._daemon = None
        self._instance_map = {}
        self.use_legacy_block_device_info = True

        if cluster_monitor:
            self._failovermon = clusterutils.ClusterFailoverMonitor(host)
            self._this_node = self._failovermon.get_node_name()

            self._volops = volumeops.VolumeOps()

            self._context = context.get_admin_context()
            self._compute_client = self._create_compute_client()
            self._network_api = network.API()
            self._volume_api = volume.API()
            self._driver = driver

            self._start_failover_listener_daemon()

    def _create_compute_client(self):
        nova_version = CONF.nova_client.version
        service_type = CONF.nova_client.service_type
        endpoint_type = CONF.nova_client.endpoint_type

        client_args = (CONF.nova_client.admin_username or 'neutron',
                       CONF.nova_client.admin_password or 'Passw0rd',
                       CONF.nova_client.admin_tenant_name or 'service',
                       CONF.nova_client.admin_auth_url or 'http://192.168.40.140:35357/v2.0')

        if not all(client_args):
            raise Exception(_('No nova credentials provided for failover.'))

        return novaclient.client.Client(nova_version,
                                        *client_args,
                                        service_type=service_type,
                                        endpoint_type=endpoint_type,
                                        region_name=None,
                                        no_cache=True,
                                        insecure=False,
                                        http_log_debug=True)

    def _update_instance_map(self):
        for server in self._compute_client.servers.list(
                search_opts=self._SEARCH_OPS):
            s_dict = server.to_dict()
            self._instance_map[s_dict[self._INSTANCE_NAME_ATTR]] = server.id

    def get_instance_host(self, instance):
        return self._clustutils.get_instance_host(instance.name)

    def create_instance(self, instance, network_info, block_device_info,
                        root_vhd_path, eph_vhd_path):
        super(ClusterOps, self).create_instance(instance, network_info,
                                                block_device_info,
                                                root_vhd_path, eph_vhd_path)
        try:
            self._clustutils.add_vm_to_cluster(instance.name)
            self._failovermon.add_to_cluster_map(instance.name, instance.id)
        except Exception as e:
            LOG.error(_LE('Creating config drive failed with error: %s'),
                      e, instance=instance)

    def destroy(self, instance, network_info=None, block_device_info=None,
                destroy_disks=True):
        try:
            self._clustutils.delete(instance.name)
            self._failovermon.clear_from_cluster_map(instance.name)
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

    def _get_instance_block_device_mapping(self, instance):
        """Transform block devices to the driver block_device format."""

        bdms = objects.BlockDeviceMappingList.get_by_instance_uuid(
            self._context, instance.id)
        block_device_mapping = (
            block_device.convert_volumes(bdms) +
            block_device.convert_snapshots(bdms) +
            block_device.convert_images(bdms))

        # if the block_device_mapping has no value in connection_info
        # (returned as None), don't include in the mapping
        block_device_mapping = [bdm for bdm in block_device_mapping
                                if bdm.get('connection_info')]
        block_device_mapping = block_device.legacy_block_devices(
                block_device_mapping)

        return block_device_mapping

    def _get_instance_block_device_info(self, instance, bdms,
                                        do_check_attach=True):
        """Set up the block device for an instance with error logging."""
        # this is copied from compute.manager
        # can't use compute manager, can result in a circular dependency import
        try:
            block_device_info = {
                'root_device_name': instance['root_device_name'],
                'swap': block_device.convert_swap(bdms),
                'ephemerals': block_device.convert_ephemerals(bdms),
                'block_device_mapping': (
                    block_device.attach_block_devices(
                        block_device.convert_volumes(bdms),
                        self._context, instance, self._volume_api,
                        self._driver, do_check_attach=do_check_attach) +
                    block_device.attach_block_devices(
                        block_device.convert_snapshots(bdms),
                        self._context, instance, self._volume_api,
                        self._driver, self._await_block_device_map_created,
                        do_check_attach=do_check_attach) +
                    block_device.attach_block_devices(
                        block_device.convert_images(bdms),
                        self._context, instance, self._volume_api,
                        self._driver, self._await_block_device_map_created,
                        do_check_attach=do_check_attach) +
                    block_device.attach_block_devices(
                        block_device.convert_blanks(bdms),
                        self._context, instance, self._volume_api,
                        self._driver, self._await_block_device_map_created,
                        do_check_attach=do_check_attach))
            }

            if self.use_legacy_block_device_info:
                for bdm_type in ('swap', 'ephemerals', 'block_device_mapping'):
                    block_device_info[bdm_type] = \
                        block_device.legacy_block_devices(
                        block_device_info[bdm_type])

            # Get swap out of the list
            block_device_info['swap'] = block_device.get_swap(
                block_device_info['swap'])
            return block_device_info

        except exception.OverQuota:
            msg = _LW('Failed to create block device for instance due to '
                      'being over volume resource quota')
            LOG.warn(msg, instance=instance)
            raise exception.InvalidBDM()

        except Exception:
            LOG.exception(_LE('Instance failed block device setup'),
                          instance=instance)
            raise exception.InvalidBDM()

    def _start_failover_listener_daemon(self):
        """Starts the daemon failover listener."""

        if self._daemon:
            return

        def _looper():
            # have monitor return values or do a callback?
            # maybe set the callback in __init__?
            try:
                self._failovermon.monitor(self._failover_migrate)
            except Exception as e:
                LOG.exception(_LE('Failover observation / migration '
                                  'exception: %s'), e)

        self._daemon = loopingcall.FixedIntervalLoopingCall(_looper)

        # check for events every _EVENT_CHECK_INTERVAL period.
        self._daemon.start(interval=self._EVENT_CHECK_INTERVAL)

    def _failover_migrate(self, instance_name, new_host):
        """ This method will check if the generated event is a legitimate
        failover to this node. If it is, it will proceed to prepare the
        failovered VM if necessary and update the owner of the compute vm in
        nova and ports in neutron.
        """
        LOG.info(_LI("Check Failover %s to %s"), instance_name, new_host)
        old_host = self._failovermon.get_from_cluster_map(instance_name)
        LOG.info(_LI("Vm known to be on: %s"), old_host)

        if old_host == new_host:
            # Owner did not change.
            LOG.debug("Owner did not change.")
            return
        elif new_host != self._this_node:
            LOG.debug("Did not failover to this node.")
            # the failovered VM did not originate from this node.
            return

        instance = self._get_instance_by_name(instance_name)
        LOG.info(_LI("Failovering %s to %s"), instance_name, new_host)

        self._post_failover_setup(instance, instance_name)

        instance.failover_migrate(new_host)
        self._failover_migrate_networks(instance, old_host)
        #instance.live_migrate(host=new_host)

    def _post_failover_setup(self, instance, instance_name):
        """ This is called after a VM failovered to this node.
        The failovered VM can have volumes attached. The storage targets must
        be logged in.
        The VM can be down because the storage targets were not logged so. So,
        we must reattach the volumes and start the VM.

        TODO(claudiub): don't start the VM if it was supposed to be down.
        TODO(claudiub): starting the VM might generate a new WMI event for
                        failover. Ignore it?

        :return: final state of the VM.
        """

        bdms = self._get_instance_block_device_mapping(instance)
        print block_device_mapping

        block_device_info = self._get_instance_block_device_info(instance,
                                                                 bdms)

        self._volops.login_storage_targets(block_device_info)

        self._clustutils.bring_online(instance_name)

        # would it be enough to just login the targets?
        #self._volops.detach_volumes(block_device_mapping[0], instance_name)

        #ebs_root = False
        #if self._volumeops.ebs_root_in_block_devices(block_device_mapping[0]):
        #    ebs_root = True

        #self._volops.attach_volumes(block_device_mapping[0], instance_name,
        #                            ebs_root)

    def _failover_migrate_networks(self, instance, source):
        """ This is called after a VM failovered to this node.
        This will change the owner of the neutron ports to this node.
        """
        # this is the destination node.
        instance = instance.to_dict()
        instance['uuid'] = instance['id']
        instance['project_id'] = instance['tenant_id']
        migration = {'source_compute': source,
                     'dest_compute': self._this_node, }

        self._network_api.setup_networks_on_host(self._context,
                                                 instance,
                                                 self._this_node)

        self._network_api.migrate_instance_start(self._context,
                                                 instance,
                                                 migration)

        self._network_api.setup_networks_on_host(self._context,
                                                 instance,
                                                 self._this_node)

        self._network_api.migrate_instance_finish(self._context,
                                                  instance,
                                                  migration)

        self._network_api.setup_networks_on_host(self._context,
                                                 instance,
                                                 self._this_node)

        self._network_api.setup_networks_on_host(self._context,
                                                 instance,
                                                 source,
                                                 teardown=True)

    def _get_instance_by_name(self, instance_name):
        vm_id = self._instance_map.get(instance_name, None)
        if not vm_id:
            self._update_instance_map()

        vm_id = self._instance_map.get(instance_name, None)
        if not vm_id:
            return

        return self._compute_client.servers.get(vm_id)