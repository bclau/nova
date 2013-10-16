#  Copyright 2014 Cloudbase Solutions Srl
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

from nova.openstack.common import units
from nova.tests.virt.hyperv import test_vhdutils
from nova.virt.hyperv import constants
from nova.virt.hyperv import vhdutilsv2


class VHDUtilsV2TestCase(test_vhdutils.VHDUtilsTestCase):
    """Unit tests for the Hyper-V VHDUtilsV2 class."""

    _FAKE_VHD_PATH = "C:\\fake_path.vhdx"
    _FAKE_PARENT_VHD_PATH = "C:\\fake_parent_path.vhdx"
    _FAKE_MAK_INTERNAL_SIZE = units.Gi
    _FAKE_VHD_FORMAT = 'vhdx'
    _FAKE_BAD_TYPE = vhdutilsv2.VHDUtilsV2._VHD_TYPE_DIFFERENCING
    _FAKE_LOG_SIZE = 1048576
    _FAKE_METADATA_SIZE = 1048576
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

        self._fake_file_handle = mock.MagicMock()

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

    @mock.patch('nova.virt.hyperv.vhdutils.VHDUtils.get_vhd_format')
    def test_get_vhdx_internal_size(self, mock_get_vhd_format):
        mock_get_vhd_format = self._VHD_TYPE
        self._mock_get_vhd_info()
        self._vhdutils._get_vhdx_log_size = mock.MagicMock(
            return_value=self._FAKE_LOG_SIZE)
        self._vhdutils._get_vhdx_metadata_size_and_offset = mock.MagicMock(
            return_value=(self._FAKE_METADATA_SIZE, 1024))
        self._vhdutils._get_vhdx_block_size = mock.MagicMock(
            return_value=self._FAKE_BLOCK_SIZE)

        file_mock = mock.MagicMock()
        with mock.patch('__builtin__.open', file_mock):
            internal_size = (
                self._vhdutils.get_internal_vhd_size_by_file_size(
                    self._FAKE_VHD_PATH, self._FAKE_MAK_INTERNAL_SIZE))

        self.assertEqual(self._FAKE_MAK_INTERNAL_SIZE - self._FAKE_BLOCK_SIZE,
                         internal_size)

    def test_get_vhdx_current_header(self):
        VHDX_HEADER_OFFSETS = [64 * 1024, 128 * 1024]
        fake_sequence_numbers = ['\x01\x00\x00\x00\x00\x00\x00\x00',
                                 '\x02\x00\x00\x00\x00\x00\x00\x00']
        self._fake_file_handle.read = mock.MagicMock(
            side_effect=fake_sequence_numbers)

        offset = self._vhdutils._get_vhdx_current_header_offset(
            self._fake_file_handle)
        self.assertEqual(offset, VHDX_HEADER_OFFSETS[1])

    def test_get_vhdx_metadata_size(self):
        fake_metadata_offset = '\x01\x00\x00\x00\x00\x00\x00\x00'
        fake_metadata_size = '\x01\x00\x00\x00'
        self._fake_file_handle.read = mock.MagicMock(
            side_effect=[fake_metadata_offset, fake_metadata_size])

        metadata_size, metadata_offset = (
            self._vhdutils._get_vhdx_metadata_size_and_offset(
                self._fake_file_handle))
        self.assertEqual(metadata_size, 1)
        self.assertEqual(metadata_offset, 1)

    def test_get_block_size(self):
        self._vhdutils._get_vhdx_metadata_size_and_offset = mock.MagicMock(
            return_value=(self._FAKE_METADATA_SIZE, 1024))
        fake_block_size = '\x01\x00\x00\x00'
        self._fake_file_handle.read = mock.MagicMock(
            return_value=fake_block_size)

        block_size = self._vhdutils._get_vhdx_block_size(
            self._fake_file_handle)
        self.assertEqual(block_size, 1)

    def test_get_log_size(self):
        fake_current_header_offset = 64 * 1024
        self._vhdutils._get_vhdx_current_header_offset = mock.MagicMock(
            return_value=fake_current_header_offset)
        fake_log_size = '\x01\x00\x00\x00'
        self._fake_file_handle.read = mock.MagicMock(
            return_value=fake_log_size)

        log_size = self._vhdutils._get_vhdx_log_size(self._fake_file_handle)
        self.assertEqual(log_size, 1)
