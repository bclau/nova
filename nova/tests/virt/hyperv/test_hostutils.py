#  Copyright 2014 Hewlett-Packard Development Company, L.P.
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
from nova.virt.hyperv import constants
from nova.virt.hyperv import hostutils


class HostUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V hostutils class."""

    def setUp(self):
        self._hostutils = hostutils.HostUtils()
        self._hostutils._conn_cimv2 = mock.MagicMock()
        super(HostUtilsTestCase, self).setUp()

    @mock.patch('nova.virt.hyperv.hostutils.ctypes')
    def test_get_host_tick_count64(self, mock_ctypes):
        tick_count64 = "100"
        mock_ctypes.windll.kernel32.GetTickCount64.return_value = tick_count64
        response = self._hostutils.get_host_tick_count64()
        self.assertEqual(tick_count64, response)

    def _test_get_supported_machine_types(self, is_6_3, expected):
        with mock.patch.object(self._hostutils,
                               'check_min_windows_version') as mocked:
            mocked.return_value = is_6_3
            result = self._hostutils.get_supported_vm_types()
            self.assertEqual(expected, result)

    def test_get_supported_machine_types_older(self):
        self._test_get_supported_machine_types(False,
                                               [constants.IMAGE_PROP_VM_GEN_1])

    def test_get_supported_machine_types_63(self):
        expected = [constants.IMAGE_PROP_VM_GEN_1,
                    constants.IMAGE_PROP_VM_GEN_2]
        self._test_get_supported_machine_types(True, expected)
