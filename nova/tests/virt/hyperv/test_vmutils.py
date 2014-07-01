# Copyright 2013 Cloudbase Solutions Srl
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
from nova.virt.hyperv import vmutils


class VMUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V VMUtils class."""

    _FAKE_VM_NAME = 'fake_vm'
    _FAKE_MEMORY_MB = 2
    _FAKE_VM_PATH = "fake_vm_path"
    _FAKE_VHD_PATH = "fake_vhd_path"
    _FAKE_DVD_PATH = "fake_dvd_path"
    _FAKE_VOLUME_DRIVE_PATH = "fake_volume_drive_path"
    _FAKE_SCSI_CONTROLLER_PATH = "fake_scsi_controller_path"

    _FAKE_PATH = "fake_path"
    _FAKE_CTRL_PATH = "fake_ctrl_path"
    _FAKE_CTRL_ADDR = "fake_ctrl_addr"
    _FAKE_DRIVE_ADDR = "fake_drive_addr"

    def setUp(self):
        self._vmutils = vmutils.VMUtils()
        self._vmutils._conn = mock.MagicMock()

        super(VMUtilsTestCase, self).setUp()

    def test_enable_vm_metrics_collection(self):
        self.assertRaises(NotImplementedError,
                          self._vmutils.enable_vm_metrics_collection,
                          self._FAKE_VM_NAME)

    def _lookup_vm(self):
        mock_vm = mock.MagicMock()
        self._vmutils._lookup_vm_check = mock.MagicMock(
            return_value=mock_vm)
        mock_vm.path_.return_value = self._FAKE_VM_PATH
        return mock_vm

    def test_set_vm_memory_static(self):
        self._test_set_vm_memory_dynamic(1.0)

    def test_set_vm_memory_dynamic(self):
        self._test_set_vm_memory_dynamic(2.0)

    def _test_set_vm_memory_dynamic(self, dynamic_memory_ratio):
        mock_vm = self._lookup_vm()

        mock_s = self._vmutils._conn.Msvm_VirtualSystemSettingData()[0]
        mock_s.SystemType = 3

        mock_vmsetting = mock.MagicMock()
        mock_vmsetting.associators.return_value = [mock_s]

        self._vmutils._modify_virt_resource = mock.MagicMock()

        self._vmutils._set_vm_memory(mock_vm, mock_vmsetting,
                                     self._FAKE_MEMORY_MB,
                                     dynamic_memory_ratio)

        self._vmutils._modify_virt_resource.assert_called_with(
            mock_s, self._FAKE_VM_PATH)

        if dynamic_memory_ratio > 1:
            self.assertTrue(mock_s.DynamicMemoryEnabled)
        else:
            self.assertFalse(mock_s.DynamicMemoryEnabled)

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.get_attached_disks")
    def test_get_free_controller_slot(self, mock_get_attached_disks):
        mock_disk = mock.MagicMock()
        mock_disk.AddressOnParent = 3
        mock_get_attached_disks.return_value = [mock_disk]

        response = self._vmutils.get_free_controller_slot(
            self._FAKE_SCSI_CONTROLLER_PATH)

        mock_get_attached_disks.assert_called_once_with(
            self._FAKE_SCSI_CONTROLLER_PATH)

        self.assertEquals(response, 0)

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.get_attached_disks")
    def test_get_free_controller_slot_exception(self, mock_get_attached_disks):
        mock_disks = [mock.MagicMock(AddressOnParent=i) for i in
                      range(constants.SCSI_CONTROLLER_SLOTS_NUMBER)]
        mock_get_attached_disks.return_value = mock_disks

        self.assertRaises(vmutils.HyperVException,
                          self._vmutils.get_free_controller_slot,
                          self._FAKE_SCSI_CONTROLLER_PATH)

        mock_get_attached_disks.assert_called_once_with(
            self._FAKE_SCSI_CONTROLLER_PATH)

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.get_free_controller_slot")
    @mock.patch("nova.virt.hyperv.vmutils.VMUtils._get_vm_scsi_controller")
    def test_attach_scsi_drive(self, mock_get_vm_scsi_controller,
                               mock_get_free_controller_slot):
        mock_vm = self._lookup_vm()
        mock_get_vm_scsi_controller.return_value = self._FAKE_CTRL_PATH
        mock_get_free_controller_slot.return_value = self._FAKE_DRIVE_ADDR

        with mock.patch.object(self._vmutils,
                               '_attach_drive') as mock_attach_drive:
            self._vmutils.attach_scsi_drive(mock_vm, self._FAKE_PATH,
                                            constants.DISK)

            mock_get_vm_scsi_controller.assert_called_once_with(mock_vm)
            mock_get_free_controller_slot.assert_called_once_with(
                self._FAKE_CTRL_PATH)
            mock_attach_drive.assert_called_once_with(
                mock_vm, self._FAKE_PATH, self._FAKE_CTRL_PATH,
                self._FAKE_DRIVE_ADDR, constants.DISK)

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils._get_vm_ide_controller")
    def test_attach_ide_drive(self, mock_get_vm_ide_controller):
        mock_vm = self._lookup_vm()
        mock_get_vm_ide_controller.return_value = self._FAKE_CTRL_PATH

        with mock.patch.object(self._vmutils,
                               '_attach_drive') as mock_attach_drive:
            self._vmutils.attach_ide_drive(
                self._FAKE_VM_NAME, self._FAKE_PATH, self._FAKE_CTRL_ADDR,
                self._FAKE_DRIVE_ADDR, constants.DISK)

            mock_get_vm_ide_controller.assert_called_once_with(
                mock_vm, self._FAKE_CTRL_ADDR)
            mock_attach_drive.assert_called_once_with(
                mock_vm, self._FAKE_PATH, self._FAKE_CTRL_PATH,
                self._FAKE_DRIVE_ADDR, constants.DISK)

    @mock.patch('nova.virt.hyperv.vmutils.VMUtils._get_vm_disks')
    def test_get_vm_storage_paths(self, mock_get_vm_disks):
        self._lookup_vm()
        mock_rasds = self._create_mock_disks()
        mock_get_vm_disks.return_value = ([mock_rasds[0]], [mock_rasds[1]])

        storage = self._vmutils.get_vm_storage_paths(self._FAKE_VM_NAME)
        (disk_files, volume_drives) = storage

        self.assertEqual([self._FAKE_VHD_PATH], disk_files)
        self.assertEqual([self._FAKE_VOLUME_DRIVE_PATH], volume_drives)

    def test_get_vm_disks(self):
        mock_vm = self._lookup_vm()
        mock_vmsettings = [mock.MagicMock()]
        mock_vm.associators.return_value = mock_vmsettings

        mock_rasds = self._create_mock_disks()
        mock_vmsettings[0].associators.return_value = mock_rasds

        (disks, volumes) = self._vmutils._get_vm_disks(mock_vm)

        mock_vm.associators.assert_called_with(
            wmi_result_class=self._vmutils._VIRTUAL_SYSTEM_SETTING_DATA_CLASS)
        mock_vmsettings[0].associators.assert_called_with(
            wmi_result_class=self._vmutils._STORAGE_ALLOC_SETTING_DATA_CLASS)
        self.assertEqual([mock_rasds[0]], disks)
        self.assertEqual([mock_rasds[1]], volumes)

    def _create_mock_disks(self):
        mock_rasd1 = mock.MagicMock()
        mock_rasd1.ResourceSubType = self._vmutils._HARD_DISK_RES_SUB_TYPE
        mock_rasd1.Connection = [self._FAKE_VHD_PATH]

        mock_rasd2 = mock.MagicMock()
        mock_rasd2.ResourceSubType = self._vmutils._PHYS_DISK_RES_SUB_TYPE
        mock_rasd2.HostResource = [self._FAKE_VOLUME_DRIVE_PATH]

        return [mock_rasd1, mock_rasd2]
