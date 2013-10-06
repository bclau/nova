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

from nova.tests.virt.hyperv import test_basevolumeutils
from nova.virt.hyperv import vmutils
from nova.virt.hyperv import volumeutils


class VolumeUtilsTestCase(test_basevolumeutils.BaseVolumeUtilsTestCase):
    """Unit tests for the Hyper-V VolumeUtils class."""

    _FAKE_STDOUT_VALUE_FAILED = 'fake_stdout_value_failed'
    _FAKE_STDOUT_VALUE = 'The operation completed successfully'
    _FAKE_STDERR_VALUE = 'fake_stderr_value'
    _FAKE_TARGET_PORTAL = 'fake_target_portal'
    _FAKE_TARGET_ADDRESS = 'fake_target_address'
    _FAKE_TARGET_PORT = 'fake_target_port'

    def setUp(self):
        super(VolumeUtilsTestCase, self).setUp()
        self._volutils = volumeutils.VolumeUtils()
        self._conn_wmi = self._volutils._conn_wmi = mock.MagicMock()
        self._conn_cimv2 = self._volutils._conn_cimv2 = mock.MagicMock()
        volumeutils.utils = mock.MagicMock()

    def test_execute_fail(self):
        volumeutils.utils.execute.return_value = (
            self._FAKE_STDOUT_VALUE_FAILED, self._FAKE_STDERR_VALUE)

        self.assertRaises(
            vmutils.HyperVException, self._volutils.execute, (None, None))

    def test_login_storage_target(self):
        volumeutils.utils.execute.return_value = (self._FAKE_STDOUT_VALUE,
                                                  self._FAKE_STDERR_VALUE)

        volumeutils.utils.parse_server_string.return_value = (
            self._FAKE_TARGET_ADDRESS, self._FAKE_TARGET_PORT)
        self._volutils.login_storage_target(
            self._FAKE_LUN, self._FAKE_IQN, self._FAKE_TARGET_PORTAL)

        self.assertTrue(volumeutils.utils.execute.called)

    def test_logout_storage_target(self):
        volumeutils.utils.execute.return_value = (self._FAKE_STDOUT_VALUE,
                                                  self._FAKE_STDERR_VALUE)
        session = mock.MagicMock()
        session.SessionId = self._FAKE_SESSION_ID
        self._conn_wmi.query.return_value = [session]

        self._volutils.logout_storage_target(self._FAKE_IQN)
        self.assertTrue(volumeutils.utils.execute.called)
