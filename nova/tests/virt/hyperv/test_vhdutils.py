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

from nova import test

from nova.virt.hyperv import constants
from nova.virt.hyperv import vhdutils


class VHDUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V VHDUtils class."""

    _FAKE_VHD_PATH = "C:\\fake_path.vhd"
    _FAKE_PARENT_VHD_PATH = "C:\\fake_parent_path.vhd"
    _FAKE_FORMAT = 3
    _FAKE_MAX_INTERNAL_SIZE = 1000L
    _FAKE_TYPE = 3
    _FAKE_JOB_PATH = 'fake_job_path'
    _FAKE_RET_VAL = 0

    _VHD_TYPE = constants.DISK_FORMAT_VHD

    _GET_VHD_INFO = 'GetVirtualHardDiskInfo'
    _VALIDATE_VHD = 'ValidateVirtualHardDisk'
    _CREATE_DYNAMIC_VHD = 'CreateDynamicVirtualHardDisk'
    _CREATE_DIFFERENCING_VHD = 'CreateDifferencingVirtualHardDisk'
    _RECONNECT_PARENT_VHD = 'ReconnectParentVirtualHardDisk'
    _MERGE_VHD = 'MergeVirtualHardDisk'
    _RESIZE_VHD = 'ExpandVirtualHardDisk'

    def setUp(self):
        self._vhdutils = vhdutils.VHDUtils()
        self._vhdutils._conn = mock.MagicMock()
        self._vhdutils._vmutils = mock.MagicMock()

        self._fake_vhd_info_xml = (
            '<INSTANCE CLASSNAME="Msvm_VirtualHardDiskSettingData">'
            '<PROPERTY NAME="BlockSize" TYPE="uint32">'
            '<VALUE>33554432</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="Caption" TYPE="string">'
            '<VALUE>Virtual Hard Disk Setting Data</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="Description" TYPE="string">'
            '<VALUE>Setting Data for a Virtual Hard Disk.</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="ElementName" TYPE="string">'
            '<VALUE>fake_path.vhdx</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="Format" TYPE="uint16">'
            '<VALUE>%(format)s</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="InstanceID" TYPE="string">'
            '<VALUE>52794B89-AC06-4349-AC57-486CAAD52F69</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="LogicalSectorSize" TYPE="uint32">'
            '<VALUE>512</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="MaxInternalSize" TYPE="uint64">'
            '<VALUE>%(max_internal_size)s</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="ParentPath" TYPE="string">'
            '<VALUE>%(parent_path)s</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="Path" TYPE="string">'
            '<VALUE>%(path)s</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="PhysicalSectorSize" TYPE="uint32">'
            '<VALUE>4096</VALUE>'
            '</PROPERTY>'
            '<PROPERTY NAME="Type" TYPE="uint16">'
            '<VALUE>%(type)s</VALUE>'
            '</PROPERTY>'
            '</INSTANCE>' %
            {'path': self._FAKE_VHD_PATH,
             'parent_path': self._FAKE_PARENT_VHD_PATH,
             'format': self._FAKE_FORMAT,
             'max_internal_size': self._FAKE_MAX_INTERNAL_SIZE,
             'type': self._FAKE_TYPE})

        self._fake_vhd_info = {
            'ParentPath': self._FAKE_PARENT_VHD_PATH,
            'MaxInternalSize': self._FAKE_MAX_INTERNAL_SIZE,
            'Type': self._FAKE_TYPE}

        super(VHDUtilsTestCase, self).setUp()

    def test_validate_vhd(self):
        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._VALIDATE_VHD).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vhdutils.validate_vhd(self._FAKE_VHD_PATH)
        getattr(mock_img_svc, self._VALIDATE_VHD).assert_called_once_with(
            Path=self._FAKE_VHD_PATH)

    def test_get_vhd_info(self):
        self._mock_get_vhd_info()
        vhd_info = self._vhdutils.get_vhd_info(self._FAKE_VHD_PATH)
        self.assertEqual(self._fake_vhd_info, vhd_info)

    def _mock_get_vhd_info(self):
        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._GET_VHD_INFO).return_value = (
            self._fake_vhd_info_xml, self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

    def test_create_dynamic_vhd(self):
        self._vhdutils.get_vhd_info = mock.MagicMock(
            return_value={'Format': self._FAKE_FORMAT})

        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._CREATE_DYNAMIC_VHD).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vhdutils.create_dynamic_vhd(self._FAKE_VHD_PATH,
                                          self._FAKE_MAX_INTERNAL_SIZE,
                                          self._VHD_TYPE)

        self.assertTrue(getattr(mock_img_svc, self._CREATE_DYNAMIC_VHD).called)

    def test_create_differencing_vhd(self):
        self._vhdutils.get_vhd_info = mock.MagicMock(
            return_value={'ParentPath': self._FAKE_PARENT_VHD_PATH,
                          'Format': self._FAKE_FORMAT})

        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._CREATE_DIFFERENCING_VHD).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vhdutils.create_differencing_vhd(self._FAKE_VHD_PATH,
                                               self._FAKE_PARENT_VHD_PATH)

        self.assertTrue(
            getattr(mock_img_svc, self._CREATE_DIFFERENCING_VHD).called)

    def test_reconnect_parent_vhd(self):
        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._RECONNECT_PARENT_VHD).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vhdutils.reconnect_parent_vhd(self._FAKE_VHD_PATH,
                                            self._FAKE_PARENT_VHD_PATH)
        getattr(mock_img_svc,
                self._RECONNECT_PARENT_VHD).assert_called_once_with(
            ChildPath=self._FAKE_VHD_PATH,
            ParentPath=self._FAKE_PARENT_VHD_PATH,
            Force=True)

    def test_merge_vhd(self):
        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._MERGE_VHD).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vhdutils.merge_vhd(self._FAKE_VHD_PATH, self._FAKE_VHD_PATH)
        getattr(mock_img_svc, self._MERGE_VHD).assert_called_once_with(
            SourcePath=self._FAKE_VHD_PATH,
            DestinationPath=self._FAKE_VHD_PATH)

    def test_resize_vhd(self):
        mock_img_svc = self._vhdutils._conn.Msvm_ImageManagementService()[0]
        getattr(mock_img_svc, self._RESIZE_VHD).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vhdutils._get_internal_vhd_size_by_file_size = mock.MagicMock(
            return_value=self._FAKE_MAX_INTERNAL_SIZE)

        self._vhdutils.resize_vhd(self._FAKE_VHD_PATH,
                                  self._FAKE_MAX_INTERNAL_SIZE)

        getattr(mock_img_svc, self._RESIZE_VHD).assert_called_once_with(
            Path=self._FAKE_VHD_PATH,
            MaxInternalSize=self._FAKE_MAX_INTERNAL_SIZE)

    def test_get_supported_vhd_format(self):
        format = self._vhdutils.get_best_supported_vhd_format()
        self.assertEqual(self._VHD_TYPE, format)
