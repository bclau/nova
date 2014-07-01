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

import mock

from nova import test
from nova.virt.hyperv import constants
from nova.virt.hyperv import vmops


class VMOpsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V VMOps class."""

    _FAKE_INSTANCE_NAME = "fake_name"
    _FAKE_PATH = "fake_path"
    _FAKE_DRIVE_ADDR = "fake_addr"
    _FAKE_CTRL_DISK_ADDR = "fake_ctrl_disk_addr"

    def setUp(self):
        super(VMOpsTestCase, self).setUp()
        self._vmops = vmops.VMOps()
        self._vmops._vmutils = mock.MagicMock()

    def test_attach_drive_vm_2_scsi(self):
        self._vmops._attach_drive(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, self._FAKE_DRIVE_ADDR,
            self._FAKE_CTRL_DISK_ADDR, constants.SCSI)

        self._vmops._vmutils.attach_scsi_drive.assert_called_once_with(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, constants.DISK)

    def test_attach_drive_vm_2_ide(self):
        self._vmops._attach_drive(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, self._FAKE_DRIVE_ADDR,
            self._FAKE_CTRL_DISK_ADDR, constants.IDE)

        self._vmops._vmutils.attach_ide_drive.assert_called_once_with(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, self._FAKE_DRIVE_ADDR,
            self._FAKE_CTRL_DISK_ADDR, constants.DISK)

    def _test_get_image_vm_generation(self, vm_gen, expected_vm_gen):
        image_meta = {"properties": {constants.IMAGE_PROP_VM_GEN: vm_gen}}

        response = self._vmops.get_image_vm_generation(self._FAKE_PATH,
                                                       image_meta)

        self.assertEquals(response, expected_vm_gen)

    def test_get_image_vm_generation_1(self):
        self._test_get_image_vm_generation(constants.IMAGE_PROP_VM_GEN_1,
                                           constants.VM_GEN_1)

    @mock.patch("nova.virt.hyperv.hostutils.HostUtils."
                "check_min_windows_version")
    def test_get_image_vm_generation_2(self, mock_check_min_win_version):
        mock_check_min_win_version.return_value = False
        self._test_get_image_vm_generation(constants.IMAGE_PROP_VM_GEN_2,
                                           constants.VM_GEN_1)

    @mock.patch("nova.virt.hyperv.vhdutils.VHDUtils.get_vhd_format")
    @mock.patch("nova.virt.hyperv.hostutils.HostUtils."
                "check_min_windows_version")
    def test_get_image_vm_generation_2_vhd(self, mock_check_min_win_version,
                                           mock_get_vhd_format):
        mock_check_min_win_version.return_value = True
        mock_get_vhd_format.return_value = constants.DISK_FORMAT_VHD
        self._test_get_image_vm_generation(constants.IMAGE_PROP_VM_GEN_2,
                                           constants.VM_GEN_1)

    @mock.patch("nova.virt.hyperv.vhdutils.VHDUtils.get_vhd_format")
    @mock.patch("nova.virt.hyperv.hostutils.HostUtils."
                "check_min_windows_version")
    def test_get_image_vm_generation_2_vhdx(self, mock_check_min_win_version,
                                            mock_get_vhd_format):
        mock_check_min_win_version.return_value = True
        mock_get_vhd_format.return_value = constants.DISK_FORMAT_VHDX
        self._test_get_image_vm_generation(constants.IMAGE_PROP_VM_GEN_2,
                                           constants.VM_GEN_2)
