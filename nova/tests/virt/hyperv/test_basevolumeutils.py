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
from nova.virt.hyperv import basevolumeutils


def _exception_thrower():
    raise Exception("Testing exception handling.")


class BaseVolumeUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V BaseVolumeUtils class."""

    _FAKE_KEY = 'fake_key'
    _FAKE_TARGET_NAME = 'fake_target_name'
    _FAKE_COMPUTER_NAME = 'fake_computer_name'
    _FAKE_SESSION_ID = 'fake_session_id'
    _FAKE_INITIATOR_NAME = 'fake_initiator_name'
    _FAKE_INITIATOR_IQN_NAME = "iqn.1991-05.com.microsoft:fake_computer_name"
    _FAKE_IQN = 'fake_iqn'
    _FAKE_LUN = 'fake_lun'
    _FAKE_DEVICE_NUMBER = 2
    _FAKE_DISK_PATH = 'fake_path DeviceID="123\\\\2"'
    _FAKE_MOUNT_DEVICE = '/dev/fake/mount'
    _FAKE_DEVICE_NAME = '/dev/fake/path'
    _FAKE_BLOCK_DEVICE_INFO = 'fake_block_device_info'
    _FAKE_SWAP = {'device_name': '/dev/fake/path'}

    def setUp(self):
        self._volutils = basevolumeutils.BaseVolumeUtils()
        self._conn_wmi = self._volutils._conn_wmi = mock.MagicMock()
        self._conn_cimv2 = self._volutils._conn_cimv2 = mock.MagicMock()
        basevolumeutils._winreg = mock.MagicMock()
        basevolumeutils.driver = mock.MagicMock()
        self._nova_driver = basevolumeutils.driver

        super(BaseVolumeUtilsTestCase, self).setUp()

    def test_get_iscsi_initiator_ok(self):
        self._test_get_iscsi_initiator(
            mock.MagicMock(return_value=self._FAKE_KEY),
            self._FAKE_INITIATOR_NAME)

    def test_get_iscsi_initiator_exception(self):
        self._test_get_iscsi_initiator(_exception_thrower,
                                       self._FAKE_INITIATOR_IQN_NAME)

    def _test_get_iscsi_initiator(self, winreg_method, expected):
        mock_computer = mock.MagicMock()
        mock_computer.name = self._FAKE_COMPUTER_NAME
        self._conn_cimv2.Win32_ComputerSystem.return_value = [mock_computer]

        basevolumeutils._winreg.OpenKey = winreg_method
        basevolumeutils._winreg.QueryValueEx = mock.MagicMock(
            return_value=[expected])

        initiator_name = self._volutils.get_iscsi_initiator()
        self.assertEqual(expected, initiator_name)

    def test_volume_in_mapping(self):
        self._nova_driver.block_device_info_get_mapping = mock.MagicMock(
            return_value=[{'mount_device': self._FAKE_MOUNT_DEVICE}])
        self._nova_driver.block_device_info_get_swap = mock.MagicMock(
            return_value=self._FAKE_SWAP)
        self._nova_driver.block_device_info_get_ephemerals = mock.MagicMock(
            return_value=[{'device_name': self._FAKE_DEVICE_NAME}])

        self._nova_driver.swap_is_usable = mock.MagicMock(return_value=True)

        self.assertTrue(self._volutils.volume_in_mapping(
            self._FAKE_MOUNT_DEVICE, self._FAKE_BLOCK_DEVICE_INFO))

    def test_get_session_id_from_mounted_disk(self):
        mock_initiator_session = self._create_initiator_session()
        self._conn_wmi.query.return_value = [mock_initiator_session]
        session_id = self._volutils.get_session_id_from_mounted_disk(
            self._FAKE_DISK_PATH)

        self.assertEqual(session_id, self._FAKE_SESSION_ID)

    def test_get_device_number_for_target(self):
        init_session = self._create_initiator_session()
        self._conn_wmi.query.return_value = [init_session]
        device_number = self._volutils.get_device_number_for_target(
            self._FAKE_IQN, self._FAKE_LUN)

        self.assertEqual(self._FAKE_DEVICE_NUMBER, device_number)

    def test_get_target_from_disk_path(self):
        init_sess = self._create_initiator_session()
        self._conn_wmi.MSiSCSIInitiator_SessionClass.return_value = [init_sess]

        (target_name, scsi_lun) = self._volutils.get_target_from_disk_path(
            self._FAKE_DISK_PATH)

        self.assertEqual(self._FAKE_TARGET_NAME, target_name)
        self.assertEqual(self._FAKE_LUN, scsi_lun)

    def _create_initiator_session(self):
        device = mock.MagicMock()
        device.ScsiLun = self._FAKE_LUN
        device.DeviceNumber = self._FAKE_DEVICE_NUMBER
        device.TargetName = self._FAKE_TARGET_NAME
        init_session = mock.MagicMock()
        init_session.Devices = [device]
        init_session.SessionId = self._FAKE_SESSION_ID

        return init_session
