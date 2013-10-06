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
from nova.virt.hyperv import livemigrationutils


class LiveMigrationUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V LiveMigrationUtils class."""

    _FAKE_IDE_CTRL_PATH = 'fake_ide_ctrl_path'
    _FAKE_SCSI_CTRL_PATH = 'fake_scsi_ctrl_path'
    _FAKE_IDE_PATH = 'fake_ide_path'
    _FAKE_DISK_PATH = 'fake_disk_path'
    _FAKE_SASD_HOST_RESOURCE = 'fake_sasd_host_resource'
    _FAKE_IQN = 'fake_iqn'
    _FAKE_LUN = 'fake_lun'
    _FAKE_DEV_NUM = 1

    _FAKE_HOST = '127.0.0.1'
    _FAKE_VM_NAME = 'fake_vm'
    _FAKE_VM_PATH = "fake_vm_path"
    _FAKE_JOB_PATH = 'fake_job_path'
    _FAKE_RET_VAL = 0

    _RESOURCE_TYPE_VHD = 31
    _RESOURCE_TYPE_DISK = 17
    _RESOURCE_SUB_TYPE_VHD = 'Microsoft:Hyper-V:Virtual Hard Disk'
    _RESOURCE_SUB_TYPE_DISK = 'Microsoft:Hyper-V:Physical Disk Drive'

    def setUp(self):
        self._migrutils = livemigrationutils.LiveMigrationUtils()
        self._migrutils._vmutils = mock.MagicMock()
        self._migrutils._volutils = mock.MagicMock()

        self._conn = mock.MagicMock()
        self._migrutils._get_conn_v2 = mock.MagicMock(return_value=self._conn)

        super(LiveMigrationUtilsTestCase, self).setUp()

    def test_check_live_migration_config(self):
        mock_migr_svc = self._conn.Msvm_VirtualSystemMigrationService()[0]

        vsmssd = mock.MagicMock()
        vsmssd.EnableVirtualSystemMigration = True
        mock_migr_svc.associators.return_value = [vsmssd]
        mock_migr_svc.MigrationServiceListenerIPAdressList.return_value = [
            self._FAKE_HOST]

        self._migrutils.check_live_migration_config()
        self.assertTrue(mock_migr_svc.associators.called)

    @mock.patch.object(livemigrationutils, 'vmutilsv2')
    @mock.patch.object(livemigrationutils, 'volumeutilsv2')
    def test_live_migrate_vm_disk(self, mock_vm_utils, mock_vol_utils):
        self._test_live_migrate_vm(mock_vm_utils,
                                   mock_vol_utils,
                                   self._RESOURCE_TYPE_DISK,
                                   self._RESOURCE_SUB_TYPE_DISK)

    @mock.patch.object(livemigrationutils, 'vmutilsv2')
    @mock.patch.object(livemigrationutils, 'volumeutilsv2')
    def test_live_migrate_vm_vhd(self, mock_vm_utils, mock_vol_utils):
        self._test_live_migrate_vm(mock_vm_utils,
                                   mock_vol_utils,
                                   self._RESOURCE_TYPE_VHD,
                                   self._RESOURCE_SUB_TYPE_VHD)

    def _test_live_migrate_vm(self,
                              mock_vm_utils,
                              mock_vol_utils,
                              resource_type,
                              resource_sub_type):

        mock_vm_utils_remote = mock.MagicMock()
        mock_vol_utils_remote = mock.MagicMock()
        mock_vm_utils.VMUtilsV2 = mock.MagicMock(
            return_value=mock_vm_utils_remote)
        mock_vol_utils.VolumeUtilsV2 = mock.MagicMock(
            return_value=mock_vol_utils_remote)

        self._prepare_vm_mocks(resource_type, resource_sub_type)
        self._prepare_vmutils_mocks()

        mock_vm_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        mock_migr_svc = self._conn.Msvm_VirtualSystemMigrationService()[0]
        mock_migr_svc.MigrationServiceListenerIPAdressList.return_value = [
            self._FAKE_HOST]

        self._migrutils._volutils.get_target_from_disk_path.return_value = (
            self._FAKE_IQN, self._FAKE_LUN)

        gdn_for_target = mock_vol_utils_remote.get_device_number_for_target
        gmd_by_drive = mock_vm_utils_remote.get_mounted_disk_by_drive_number
        gdn_for_target.return_value = self._FAKE_DEV_NUM
        gmd_by_drive.return_value = self._FAKE_DISK_PATH

        mock_migr_svc.MigrateVirtualSystemToHost.return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        iscsis = self._migrutils.live_migrate_vm(self._FAKE_VM_NAME,
                                                 self._FAKE_HOST)

        self.assertEqual(iscsis, [(self._FAKE_IQN, self._FAKE_LUN)])
        self.assertTrue(self._conn.Msvm_PlannedComputerSystem.called)
        self.assertTrue(mock_vm_svc.DestroySystem.called)
        self.assertTrue(mock_vm_svc.ModifyResourceSettings.called)
        self.assertTrue(mock_migr_svc.MigrateVirtualSystemToHost.called)

    def _prepare_vm_mocks(self, resource_type, resource_sub_type):
        mock_vm_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        vm = self._get_vm()
        self._conn.Msvm_PlannedComputerSystem.return_value = [vm]
        mock_vm_svc.DestroySystem.return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)
        mock_vm_svc.ModifyResourceSettings.return_value = (
            None, self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        sasd = mock.MagicMock()
        sasd.ResourceType = resource_type
        sasd.ResourceSubType = resource_sub_type
        sasd.HostResource = [self._FAKE_SASD_HOST_RESOURCE]
        sasd.path.return_value.RelPath = self._FAKE_DISK_PATH

        vm_settings = vm.associators.return_value
        vm_settings.associators.return_value = [sasd]

    def _prepare_vmutils_mocks(self):
        vm_ide_controller = self._migrutils._vmutils.get_vm_ide_controller
        vm_scsi_controller = self._migrutils._vmutils.get_vm_scsi_controller
        vm_ide_controller.return_value = self._FAKE_IDE_CTRL_PATH
        vm_scsi_controller.return_value = self._FAKE_SCSI_CTRL_PATH
        self._migrutils._vmutils.get_controller_volume_paths.return_value = {
            self._FAKE_IDE_PATH: self._FAKE_SASD_HOST_RESOURCE}

    def _get_vm(self):
        mock_vm = mock.MagicMock()
        self._conn.Msvm_ComputerSystem.return_value = [mock_vm]
        mock_vm.path_.return_value = self._FAKE_VM_PATH
        return mock_vm
