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

    def _test_host_power_action(self, action):
        fake_win32 = mock.MagicMock()
        fake_win32.Win32Shutdown = mock.MagicMock()

        self._hostutils._conn_cimv2.Win32_OperatingSystem.return_value = [
            fake_win32]

        self._hostutils.host_power_action(action)

        if action == "shutdown":
            fake_win32.Win32Shutdown.assert_called_with(
                self._hostutils._HOST_FORCED_SHUTDOWN)
        else:
            fake_win32.Win32Shutdown.assert_called_with(
                self._hostutils._HOST_FORCED_REBOOT)

    def test_host_shutdown(self):
        self._test_host_power_action(action="shutdown")

    def test_host_reboot(self):
        self._test_host_power_action(action="reboot")
