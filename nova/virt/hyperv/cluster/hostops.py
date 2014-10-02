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
Management class for cluster host operations.
"""
import datetime
import os
import platform
import time

from oslo.config import cfg

from nova.compute import arch
from nova.compute import hvtype
from nova.compute import vm_mode
from nova.openstack.common import jsonutils
from nova.openstack.common import log as logging
from nova.openstack.common import units
from nova.virt.hyperv import clusterutils
from nova.virt.hyperv import constants
from nova.virt.hyperv import hostops
from nova.virt.hyperv import utilsfactory

CONF = cfg.CONF
CONF.import_opt('my_ip', 'nova.netconf')
LOG = logging.getLogger(__name__)


class ClusterHostOps(hostops.HostOps):
    def __init__(self, host='.'):
        super(ClusterHostOps, self).__init__(host)
        self._clusterutils = clusterutils.ClusterUtils()
        self._nodes = {}

        for host in self._clusterutils.get_cluster_node_names():
            self._nodes[host] = utilsfactory.get_hostutils(host)

    def _get_cpu_info(self):
        """Get the CPU information.
        :returns: A dictionary containing the main properties
        of the central processor in the hypervisor.
        """

        sockets = 0
        cores = 0
        threads = 0

        for hutils in self._nodes.values():
            processors = self._hostutils.get_cpus_info()
            sockets += len(processors)
            cores += processors[0]['NumberOfCores']
            threads += (processors[0]['NumberOfLogicalProcessors'] /
                        processors[0]['NumberOfCores'])

        hutils = self._nodes.values()[0]
        processors = hutils.get_cpus_info()

        cpu_info = dict()

        w32_arch_dict = constants.WMI_WIN32_PROCESSOR_ARCHITECTURE
        cpu_info['arch'] = w32_arch_dict.get(processors[0]['Architecture'],
                                             'Unknown')
        cpu_info['model'] = processors[0]['Name']
        cpu_info['vendor'] = processors[0]['Manufacturer']

        topology = dict()
        topology['sockets'] = sockets
        topology['cores'] = cores
        topology['threads'] = threads
        cpu_info['topology'] = topology

        features = list()
        for fkey, fname in constants.PROCESSOR_FEATURE.items():
            if hutils.is_cpu_feature_present(fkey):
                features.append(fname)
        cpu_info['features'] = features

        return cpu_info

    def _get_memory_info(self):
        (total_mem_kb, total_free_mem_kb) = 0, 0

        for hutils in self._nodes.values():
            (mem_kb, free_mem_kb) = hutils.get_memory_info()
            total_mem_kb += mem_kb
            total_free_mem_kb += free_mem_kb

        total_mem_mb = total_mem_kb / 1024
        total_free_mem_mb = total_free_mem_kb / 1024
        return (total_mem_mb, total_free_mem_mb,
                total_mem_mb - total_free_mem_mb)

    def _get_local_hdd_info_gb(self):
        drive = os.path.splitdrive(self._pathutils.get_instances_dir())[0]
        (total_size, total_free_space) = 0, 0

        for hutils in self._nodes.values():
            (size, free_space) = self._hostutils.get_volume_info(drive)
            total_size += size
            total_free_space += free_space

        total_gb = total_size / units.Gi
        free_gb = total_free_space / units.Gi
        used_gb = total_gb - free_gb
        return (total_gb, free_gb, used_gb)

    # TODO(claudiub): what hypervisor_version should it be returned?
    # Allow multiple hypervisor versions?
    # Technically, clusters allow only same hypervisor version.
    #def _get_hypervisor_version(self):
    #    pass