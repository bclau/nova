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

import socket

import cinderclient.client
import novaclient.client
from oslo.config import cfg

from nova.i18n import _LI, _LE
from nova import conductor
from nova import context
from nova import exception
from nova import network
from nova import objects
from nova.openstack.common import log as logging
from nova.openstack.common import loopingcall
from nova.virt import block_device
from nova.virt.hyperv.cluster import clusterutils
from nova.virt.hyperv import utilsfactory
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
               default='compute',
               help='Service Type.'),
    cfg.StrOpt('endpoint_type',
               default='publicURL',
               help='Endpoint Type.'),
]

CONF = cfg.CONF
CONF.register_opts(nova_client_opts, 'nova_client')


class ClusterOps(object):

    # TODO(claudiub): make configurable instead.
    _EVENT_CHECK_INTERVAL = 2

    _INSTANCE_HOST_ATTR = 'OS-EXT-SRV-ATTR:host'
    _INSTANCE_NAME_ATTR = 'OS-EXT-SRV-ATTR:instance_name'
    _INSTANCE_VOLUMES_ATTR = 'os-extended-volumes:volumes_attached'
    _ALL_TENANTS = 1

    _SEARCH_OPS = {'all_tenants': _ALL_TENANTS}

    def __init__(self, driver, host='.', cluster_monitor=False):
        self._clustutils = clusterutils.ClusterUtils(host)
        self._clustutils.check_cluster_state()

        self._daemon = None
        self._instance_map = {}
        self.use_legacy_block_device_info = True
        self._cluster_connectors = {}

        if cluster_monitor:
            self._failovermon = clusterutils.ClusterFailoverMonitor(host)
            self._this_node = self._failovermon.get_node_name()
            self._refresh_connectors_map()

            self._volops = volumeops.VolumeOps()

            self._context = context.get_admin_context()
            self._compute_client = self._create_compute_client()
            self._volume_client = self._create_volume_client()
            self._network_api = network.API()
            #self._volume_api = volume.API()
            self._compute_task_api = conductor.ComputeTaskAPI()
            self._driver = driver

            self._start_failover_listener_daemon()

            # for testing purposes:
            vm_name = 'instance-00000002'
            host_name = 'WIN-HYPERV-R2'
            instance = self._get_instance_by_name(vm_name)
            instance = objects.Instance.get_by_uuid(self._context, instance.id)
            print instance
            self._compute_task_api.failover_migrate_instance(
                self._context, instance, host_name)

    def _refresh_connectors_map(self):
        # TODO(claudiub): find a better way.
        # TODO(claudiub): iterate only over the nodes that are not already
        # in the map.
        for host in self._clustutils.get_cluster_node_names():
            try:
                vol_utils = utilsfactory.get_volumeutils(host)
                iscsi_initiator = vol_utils.get_iscsi_initiator()
                host_ip = socket.gethostbyname(host)
                self._cluster_connectors[host] = {
                    'ip': host_ip,
                    'host': host,
                    'initiator': iscsi_initiator,
                }
            except Exception as e:
                LOG.exception(_LE('Exception during iscsi connector fetching: '
                                  '%s'), e)

    def _create_compute_client(self):
        nova_version = CONF.nova_client.version
        service_type = CONF.nova_client.service_type
        nova_username = CONF.nova_client.admin_username

        (client_args,
         client_kwargs) = self._get_client_config_opts(nova_username)
        client_kwargs['service_type'] = service_type
        return novaclient.client.Client(nova_version,
                                        *client_args,
                                        **client_kwargs)

    def _create_volume_client(self):
        client_args, client_kwargs = self._get_client_config_opts('cinder')
        return cinderclient.client.Client('1', *client_args, **client_kwargs)

    def _get_client_config_opts(self, username):
        endpoint_type = CONF.nova_client.endpoint_type

        client_args = (username,
                       CONF.nova_client.admin_password,
                       CONF.nova_client.admin_tenant_name,
                       CONF.nova_client.admin_auth_url)

        if not all(client_args):
            raise Exception(_('No nova / cinder credentials provided for '
                              'failover.'))

        client_kwargs = {'endpoint_type': endpoint_type,
                         'region_name': None,
                         'no_cache': True,
                         'insecure': False,
                         'http_log_debug': True}

        return client_args, client_kwargs

    def get_instance_host(self, instance):
        return self._clustutils.get_vm_host(instance.name)

    def add_to_cluster(self, instance):
        try:
            self._clustutils.add_vm_to_cluster(instance.name)
            self._failovermon.add_to_cluster_map(instance.name)
            self._instance_map[instance.name] = instance.id
        except Exception as e:
            LOG.error(_LE('Adding instance to cluster failed with error: %s'),
                      e, instance=instance)

    def remove_from_cluster(self, instance):
        try:
            self._clustutils.delete(instance.name)
            self._failovermon.clear_from_cluster_map(instance.name)
        except Exception as e:
            LOG.error(_LE('Removing instance from cluster failed with error: '
                          '%s'), e, instance=instance)

    def post_migration(self, instance):
        # skip detecting false posive failovers events due to
        # cold / live migration.
        self._failovermon.add_to_cluster_map(instance.name)
        self._instance_map[instance.name] = instance.id

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

    def _failover_migrate(self, new_host, instance_name):
        """ This method will check if the generated event is a legitimate
        failover to this node. If it is, it will proceed to prepare the
        failovered VM if necessary and update the owner of the compute vm in
        nova and ports in neutron.
        """
        LOG.info(_LI('Check Failover %s to %s'), instance_name, new_host)
        old_host = self._failovermon.get_from_cluster_map(instance_name)
        LOG.info(_LI('Vm known to be on: %s'), old_host)

        if old_host == new_host:
            # Owner did not change.
            LOG.debug('Owner did not change.')
            return
        elif new_host != self._this_node:
            LOG.debug('Did not failover to this node.')
            # the failovered VM did not originate from this node.
            return

        instance = self._get_instance_by_name(instance_name)
        if not instance:
            LOG.debug('Instance %s does not exist in nova. Skipping.',
                      instance_name)
            return

        LOG.info(_LI('Failovering %s to %s'), instance_name, new_host)

        self._post_failover_setup(instance_name, instance)

        LOG.info(_LI('After post failover setup'))
        self._compute_task_api.failover_migrate_instance(
            self._context, instance, new_host)
        #instance.failover_migrate(new_host)
        LOG.info(_LI('After nova failover'))

        self._failover_migrate_networks(instance, old_host)
        LOG.info(_LI('After neutron '))
        #instance.live_migrate(host=new_host)

    def _post_failover_setup(self, instance_name, instance):
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

        try:
            volumes = self._prepare_instance_volumes(instance)
            block_device_mapping = {'block_device_mapping': volumes}

            self._volops.initialize_volumes_connection(block_device_mapping)
            self._volops.fix_instance_volume_disk_paths(instance_name,
                                                        block_device_mapping)
            self._clustutils.bring_online(instance_name)
        except Exception as e:
            LOG.exception('Exception during volume init or startup: %s', e)

    def _prepare_instance_volumes(self, instance):
        volume_ids = instance.to_dict().get(self._INSTANCE_VOLUMES_ATTR, [])

        if not volume_ids:
            return []

        volume_ids = [v['id'] for v in volume_ids]
        instance = objects.Instance.get_by_uuid(self._context, instance.id)
        old_host = instance.host  # or instance.node
        bdms = self._get_instance_block_device_mappings(volume_ids)

        connector = self._cluster_connectors.get(old_host, None)
        if not connector:
            # this can happen if new nodes are added to the cluster.
            # or if a node was previously not running.
            self._refresh_connectors_map()

        connector = self._cluster_connectors[old_host]
        new_connector = self._cluster_connectors[self._this_node]

        for bdm in bdms:
            try:
                self._volume_client.volumes.terminate_connection(bdm.volume_id,
                                                                 connector)
            except Exception as e:
                LOG.exception(_LE('Exception during volume disconnect: %s'), e)
            try:
                conn_info = self._volume_client.volumes.initialize_connection(
                    bdm.volume_id, new_connector)

                if 'serial' not in conn_info:
                    conn_info['serial'] = bdm.volume_id

                bdm._preserve_multipath_id(conn_info)
                bdm['connection_info'] = conn_info
            except Exception as e:
                LOG.exception(_LE('Exception during connection refresh: %s'),
                              e)

        return bdms

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

        self._network_api.setup_networks_on_host(
            self._context, instance, self._this_node)

        self._network_api.migrate_instance_start(
            self._context, instance, migration)

        self._network_api.setup_networks_on_host(
            self._context, instance, self._this_node)

        self._network_api.migrate_instance_finish(
            self._context, instance, migration)

        self._network_api.setup_networks_on_host(
            self._context, instance, self._this_node)
        self._network_api.setup_networks_on_host(
            self._context, instance, source, teardown=True)

    def _get_instance_by_name(self, instance_name):
        vm_id = self._instance_map.get(instance_name, None)
        if not vm_id:
            self._update_instance_map()

        vm_id = self._instance_map.get(instance_name, None)
        if not vm_id:
            return

        return self._compute_client.servers.get(vm_id)

    def _get_instance_block_device_mappings(self, volume_ids):
        """Transform block devices to the driver block_device format."""
        return [block_device.DriverVolumeBlockDevice(
                objects.BlockDeviceMapping.get_by_volume_id(
                    self._context, vol_id)) for vol_id in volume_ids]

    def _update_instance_map(self):
        for server in self._compute_client.servers.list(
                search_opts=self._SEARCH_OPS):
            s_dict = server.to_dict()
            self._instance_map[s_dict[self._INSTANCE_NAME_ATTR]] = server.id
