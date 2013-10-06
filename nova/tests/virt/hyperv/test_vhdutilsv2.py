# vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright 2013 Cloudbase Solutions Srl
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

from nova.tests.virt.hyperv import test_vhdutils
from nova.virt.hyperv import constants
from nova.virt.hyperv import vhdutilsv2


class VHDUtilsV2TestCase(test_vhdutils.VHDUtilsTestCase):
    """Unit tests for the Hyper-V VHDUtilsV2 class."""

    _FAKE_VHD_PATH = "C:\\fake_path.vhdx"
    _FAKE_PARENT_VHD_PATH = "C:\\fake_parent_path.vhdx"
    _FAKE_BLOCK_SIZE = 33554432L
    _FAKE_LOGICAL_SECTOR_SIZE = 512L
    _FAKE_PHYSICAL_SECTOR_SIZE = 4096L

    _VHD_TYPE = constants.DISK_FORMAT_VHDX

    _GET_VHD_INFO = 'GetVirtualHardDiskSettingData'
    _CREATE_DYNAMIC_VHD = 'CreateVirtualHardDisk'
    _CREATE_DIFFERENCING_VHD = 'CreateVirtualHardDisk'
    _RECONNECT_PARENT_VHD = 'SetVirtualHardDiskSettingData'
    _RESIZE_VHD = 'ResizeVirtualHardDisk'

    def setUp(self):
        super(VHDUtilsV2TestCase, self).setUp()
        self._vhdutils = vhdutilsv2.VHDUtilsV2()
        self._vhdutils._conn = mock.MagicMock()
        self._vhdutils._vmutils = mock.MagicMock()

        self._fake_vhd_info = {
            'Path': self._FAKE_VHD_PATH,
            'ParentPath': self._FAKE_PARENT_VHD_PATH,
            'Format': self._FAKE_FORMAT,
            'MaxInternalSize': self._FAKE_MAX_INTERNAL_SIZE,
            'Type': self._FAKE_TYPE,
            'BlockSize': self._FAKE_BLOCK_SIZE,
            'LogicalSectorSize': self._FAKE_LOGICAL_SECTOR_SIZE,
            'PhysicalSectorSize': self._FAKE_PHYSICAL_SECTOR_SIZE}

    def _mock_get_vhd_info(self):
        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._GET_VHD_INFO).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL, self._fake_vhd_info_xml)

    def test_reconnect_parent_vhd(self):
        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        self._vhdutils._get_vhd_info_xml = mock.MagicMock(
            return_value=self._fake_vhd_info_xml)

        getattr(mock_img_svc, self._RECONNECT_PARENT_VHD).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vhdutils.reconnect_parent_vhd(self._FAKE_VHD_PATH,
                                            self._FAKE_PARENT_VHD_PATH)
        getattr(mock_img_svc,
                self._RECONNECT_PARENT_VHD).assert_called_once_with(
            VirtualDiskSettingData=self._fake_vhd_info_xml)
