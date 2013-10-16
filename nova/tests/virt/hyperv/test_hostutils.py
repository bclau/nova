# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 Cloudbase Solutions Srl
#
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

import mock

from nova import test
from nova.virt.hyperv import hostutils


class HostUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V HostUtils class."""

    _FAKE_CPU = {
        'Architecture': 'fake_architecture',
        'Name': 'fake_cpu_name',
        'Manufacturer': 'fake_cpu_manufacturer',
        'NumberOfCores': 1,
        'NumberOfLogicalProcessors': 1
    }

    _FAKE_MEMORY_TOTAL = 1024L
    _FAKE_MEMORY_FREE = 512L
    _FAKE_DRIVE = 'C'
    _FAKE_DISK_SIZE = 1024L
    _FAKE_DISK_FREE = 512L
    _FAKE_VERSION_GOOD = '6.2.0'
    _FAKE_VERSION_BAD = '6.1.9'

    def setUp(self):
        self._hostutils = hostutils.HostUtils()
        self._hostutils._conn_cimv2 = mock.MagicMock()

        super(HostUtilsTestCase, self).setUp()

    def test_get_cpus_info(self):
        cpu = mock.MagicMock()
        for (key, val) in self._FAKE_CPU.items():
            setattr(cpu, key, val)

        self._hostutils._conn_cimv2.query.return_value = [cpu]
        cpu_list = self._hostutils.get_cpus_info()

        self.assertEqual([self._FAKE_CPU], cpu_list)

    def test_get_memory_info(self):
        memory = mock.MagicMock()
        memory.TotalVisibleMemorySize = self._FAKE_MEMORY_TOTAL
        memory.FreePhysicalMemory = self._FAKE_MEMORY_FREE

        self._hostutils._conn_cimv2.query.return_value = [memory]
        total_memory, free_memory = self._hostutils.get_memory_info()

        self.assertEqual(self._FAKE_MEMORY_TOTAL, total_memory)
        self.assertEqual(self._FAKE_MEMORY_FREE, free_memory)

    def test_get_volume_info(self):
        disk = mock.MagicMock()
        disk.Size = self._FAKE_DISK_SIZE
        disk.FreeSpace = self._FAKE_DISK_FREE

        self._hostutils._conn_cimv2.query.return_value = [disk]
        (total_memory,
         free_memory) = self._hostutils.get_volume_info(self._FAKE_DRIVE)

        self.assertEqual(self._FAKE_DISK_SIZE, total_memory)
        self.assertEqual(self._FAKE_DISK_FREE, free_memory)

    def test_check_min_windows_version_true(self):
        self._test_check_min_windows_version(self._FAKE_VERSION_GOOD, True)

    def test_check_min_windows_version_false(self):
        self._test_check_min_windows_version(self._FAKE_VERSION_BAD, False)

    def _test_check_min_windows_version(self, version, expected):
        os = mock.MagicMock()
        os.Version = version
        self._hostutils._conn_cimv2.Win32_OperatingSystem.return_value = [os]
        self.assertEqual(expected,
                         self._hostutils.check_min_windows_version(6, 2))
