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
from oslo.config import cfg

from nova.i18n import _, _LI, _LE
from nova.compute import power_state
from nova.compute import vm_states
#from nova import conductor
from nova import context
from nova import exception
from nova import network
from nova import objects
from nova.objects import base as nova_object
from nova.openstack.common import log as logging
from nova.openstack.common import loopingcall
from nova.virt import block_device
from nova.virt.hyperv.cluster import clusterutils
from nova.virt.hyperv import utilsfactory
from nova.virt.hyperv import volumeops
from nova import volume

LOG = logging.getLogger(__name__)

cinder_opts = [
    cfg.StrOpt('version',
               default='1',
               help='Cinder client version used.'),
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
    cfg.StrOpt('endpoint_type',
               default='publicURL',
               help='Endpoint Type.'),
]

CONF = cfg.CONF
CONF.register_opts(cinder_opts, 'cinder')


class ClusterOps(object):

    # TODO(claudiub): make configurable instead.
    _EVENT_CHECK_INTERVAL = 2

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
            self._volume_client = self._create_volume_client()
            self._context = context.get_admin_context()
            self._network_api = network.API()
            #self._volume_api = volume.API()
            #self._compute_task_api = conductor.ComputeTaskAPI()
            self._driver = driver

            self._start_failover_listener_daemon()

            self._update_instance_map()

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

    def _create_volume_client(self):
        client_args = (CONF.cinder.admin_username,
                       CONF.cinder.admin_password,
                       CONF.cinder.admin_tenant_name,
                       CONF.cinder.admin_auth_url)

        if not all(client_args):
            raise Exception(_('No nova / cinder credentials provided for '
                              'failover.'))

        client_kwargs = {'endpoint_type': CONF.cinder.endpoint_type,
                         'region_name': None,
                         'no_cache': True,
                         'insecure': False,
                         'http_log_debug': True}

        return cinderclient.client.Client(CONF.cinder.version,
                                          *client_args, **client_kwargs)

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

        self._post_failover_setup(instance)
        self._nova_failover_server(instance, new_host)
        #self._compute_task_api.failover_migrate_instance(
        #    self._context, instance, new_host)
        self._failover_migrate_networks(instance, old_host)

    def _post_failover_setup(self, instance):
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
            if not volumes:
                LOG.debug('No volumes to refresh.')
                return

            block_device_mapping = {'block_device_mapping': volumes}

            # initialize connections on Hyper-V side.
            self._volops.initialize_volumes_connection(block_device_mapping)
            self._volops.fix_instance_volume_disk_paths(instance.name,
                                                        block_device_mapping)
            self._clustutils.bring_online(instance.name)
        except Exception as e:
            LOG.exception('Exception during volume init or startup: %s', e)

    def _prepare_instance_volumes(self, instance):
        # TODO(claudiub): this looks like a volumeops job.
        bdms = self._get_instance_block_device_mappings(instance)
        if not bdms:
            return []

        old_host = instance.host  # or instance.node
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
                # initialize connection on cinder side.
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

        return objects.Instance.get_by_id(self._context, vm_id)

    def _get_instance_block_device_mappings(self, instance):
        """Transform block devices to the driver block_device format."""
        bdms = objects.BlockDeviceMappingList.get_by_instance_uuid(
            self._context, instance.id)
        return [block_device.DriverVolumeBlockDevice(bdm) for bdm in bdms]

    def _update_instance_map(self):
        expected_attrs = ['id', 'uuid', 'name', 'project_id', 'host',
                          'hostname', 'node', 'availability_zone']

        for server in objects.InstanceList.get_by_filters(
                self._context, {'deleted': False},
                expected_attrs=expected_attrs):
            self._instance_map[server.name] = server.id

    def _nova_failover_server(self, instance, new_host):
        # TODO(claudiub): this method has no place here. It will be removed
        # once the equivalent commit to nova-conductor is merged.
        if instance and not isinstance(instance, nova_object.NovaObject):
            attrs = ['metadata', 'system_metadata', 'info_cache',
                     'security_groups']
            instance = objects.Instance._from_db_object(
                context, objects.Instance(), instance,
                expected_attrs=attrs)

        if instance.vm_state == vm_states.ERROR:
            instance.vm_state = vm_states.ACTIVE
        if instance.power_state == power_state.NOSTATE:
            instance.power_state = power_state.RUNNING

        instance.host = new_host
        instance.node = new_host
        instance.save(expected_task_state=[None])
