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
from nova.virt.hyperv import volumeutilsv2


class VolumeUtilsV2TestCase(test_basevolumeutils.BaseVolumeUtilsTestCase):
    """Unit tests for the Hyper-V VolumeUtilsV2 class."""

    _FAKE_TARGET_PORTAL = 'fake_target_portal'
    _FAKE_TARGET_ADDRESS = 'fake_target_address'
    _FAKE_TARGET_PORTAL_PORT_NUMBER = 3333

    def setUp(self):
        super(VolumeUtilsV2TestCase, self).setUp()
        self._volutils = volumeutilsv2.VolumeUtilsV2()
        self._conn_wmi = self._volutils._conn_wmi = mock.MagicMock()
        self._conn_cimv2 = self._volutils._conn_cimv2 = mock.MagicMock()
        self._conn_storage = self._volutils._conn_storage = mock.MagicMock()
        volumeutilsv2.utils = mock.MagicMock()

    def test_login_storage_target(self):
        portal = self._conn_storage.MSFT_iSCSITargetPortal
        target = self._conn_storage.MSFT_iSCSITarget

        volumeutilsv2.utils.parse_server_string.return_value = (
            self._FAKE_TARGET_ADDRESS, self._FAKE_TARGET_PORTAL_PORT_NUMBER)
        self._volutils.login_storage_target(
            self._FAKE_LUN, self._FAKE_IQN, self._FAKE_TARGET_PORTAL)

        target.Connect.assert_called_once_with(NodeAddress=self._FAKE_IQN,
                                               IsPersistent=True)

        portal.New.assert_called_once_with(
            TargetPortalAddress=self._FAKE_TARGET_ADDRESS,
            TargetPortalPortNumber=self._FAKE_TARGET_PORTAL_PORT_NUMBER)

    def test_execute_log_out(self):
        sess = mock.MagicMock()
        sess.TargetName = self._FAKE_IQN
        target = mock.MagicMock()
        target.IsConnected = True
        iscsi_session = mock.MagicMock()
        iscsi_session.IsPersistent = True

        self._conn_storage.MSiSCSIInitiator_SessionClass.return_value = [sess]
        self._conn_storage.MSFT_iSCSITarget.return_value = [target]
        self._conn_storage.MSFT_iSCSISession.return_value = [iscsi_session]

        self._volutils.execute_log_out(self._FAKE_SESSION_ID)
        self.assertTrue(iscsi_session.Unregister.called)
