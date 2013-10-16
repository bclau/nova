# Copyright 2014 Cloudbase Solutions Srl
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
    _FAKE_RASD_PATH = 'fake_rask_path'
    _FAKE_SASD_HOST_RESOURCE = 'fake_sasd_host_resource'
    _FAKE_IQN = 'fake_iqn'
    _FAKE_LUN = 'fake_lun'
    _FAKE_DEV_NUM = 1

    _FAKE_HOST = '127.0.0.1'
    _FAKE_REMOTE_IP_ADDR = '127.0.0.1'
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

    @mock.patch('nova.virt.hyperv.livemigrationutils.LiveMigrationUtils.'
                '_destroy_planned_vm')
    def test_check_existing_planned_vm_found(self, mock_destroy_planned_vm):
        mock_vm = mock.MagicMock()
        mock_v2 = mock.MagicMock()
        mock_v2.Msvm_PlannedComputerSystem.return_value = [mock_vm]
        self._migrutils._check_existing_planned_vm(mock_v2, mock_vm)

        mock_destroy_planned_vm.assert_called_once_with(mock_v2, mock_vm)

    @mock.patch('nova.virt.hyperv.livemigrationutils.LiveMigrationUtils.'
                '_destroy_planned_vm')
    def test_check_existing_planned_vm_none(self, mock_destroy_planned_vm):
        mock_v2 = mock.MagicMock()
        mock_v2.Msvm_PlannedComputerSystem.return_value = []
        self._migrutils._check_existing_planned_vm(mock_v2, mock.MagicMock())

        self.assertFalse(mock_destroy_planned_vm.called)

    def test_create_remote_planned_vm(self):
        mock_vsmsd = self._conn.query()[0]
        mock_vm = mock.MagicMock()
        mock_v2 = mock.MagicMock()
        mock_v2.Msvm_PlannedComputerSystem.return_value = [mock_vm]

        migr_svc = self._conn.Msvm_VirtualSystemMigrationService()[0]
        migr_svc.MigrateVirtualSystemToHost.return_value = (
            self._FAKE_RET_VAL, self._FAKE_JOB_PATH)

        resulted_vm = self._migrutils._create_remote_planned_vm(
            self._conn, mock_v2, mock_vm, [self._FAKE_REMOTE_IP_ADDR],
            self._FAKE_HOST)

        self.assertEqual(mock_vm, resulted_vm)

        migr_svc.MigrateVirtualSystemToHost.assert_called_once_with(
            ComputerSystem=mock_vm.path_.return_value,
            DestinationHost=self._FAKE_HOST,
            MigrationSettingData=mock_vsmsd.GetText_.return_value)

    @mock.patch.object(livemigrationutils, 'volumeutilsv2')
    def test_get_remote_disk_data(self, mock_vol_utils_class):
        mock_vol_utils = mock_vol_utils_class.VolumeUtilsV2.return_value
        mock_vm_utils = mock.MagicMock()
        disk_paths = {self._FAKE_RASD_PATH: self._FAKE_DISK_PATH}
        self._migrutils._volutils.get_target_from_disk_path.return_value = (
            self._FAKE_IQN, self._FAKE_LUN)
        mock_vol_utils.get_device_number_for_target.return_value = (
            self._FAKE_DEV_NUM)
        mock_vm_utils.get_mounted_disk_by_drive_number.return_value = (
            self._FAKE_DISK_PATH)

        (disk_paths, iscsi_targets) = self._migrutils._get_remote_disk_data(
            mock_vm_utils, disk_paths, self._FAKE_HOST)

        self._migrutils._volutils.get_target_from_disk_path.assert_called_with(
            self._FAKE_DISK_PATH)
        mock_vol_utils.get_device_number_for_target.assert_called_with(
            self._FAKE_IQN, self._FAKE_LUN)
        mock_vm_utils.get_mounted_disk_by_drive_number.assert_called_with(
            self._FAKE_DEV_NUM)

        self.assertEqual([(self._FAKE_IQN, self._FAKE_LUN)], iscsi_targets)
        self.assertEqual({self._FAKE_RASD_PATH: self._FAKE_DISK_PATH},
                         disk_paths)

    def test_update_planned_vm_disk_resources(self):
        mock_vm_utils = mock.MagicMock()

        self._prepare_vm_mocks(self._RESOURCE_TYPE_DISK,
                               self._RESOURCE_SUB_TYPE_DISK)
        mock_vm = self._conn.Msvm_ComputerSystem.return_value[0]
        mock_sasd = mock_vm.associators()[0].associators()[0]

        mock_vsmsvc = self._conn.Msvm_VirtualSystemManagementService()[0]

        self._migrutils._update_planned_vm_disk_resources(
            mock_vm_utils, self._conn, mock_vm, self._FAKE_VM_NAME,
            {mock_sasd.path.return_value.RelPath: self._FAKE_RASD_PATH})

        mock_vsmsvc.ModifyResourceSettings.assert_called_once_with(
            ResourceSettings=[mock_sasd.GetText_.return_value])

    def test_get_vhd_setting_data(self):
        self._prepare_vm_mocks(self._RESOURCE_TYPE_VHD,
                               self._RESOURCE_SUB_TYPE_VHD)
        mock_vm = self._conn.Msvm_ComputerSystem.return_value[0]
        mock_sasd = mock_vm.associators()[0].associators()[0]

        vhd_sds = self._migrutils._get_vhd_setting_data(mock_vm)
        self.assertEqual([mock_sasd.GetText_.return_value], vhd_sds)

    def test_private_live_migrate_vm(self):
        mock_v2 = mock.MagicMock()
        mock_vm = mock.MagicMock()
        mock_vsmsd = mock_v2.query()[0]

        mock_vsmsvc = mock_v2.Msvm_VirtualSystemMigrationService()[0]
        mock_vsmsvc.MigrateVirtualSystemToHost.return_value = (
            self._FAKE_RET_VAL, self._FAKE_JOB_PATH)

        self._migrutils._live_migrate_vm(
            mock_v2, mock_vm, None, [self._FAKE_REMOTE_IP_ADDR],
            self._FAKE_RASD_PATH, self._FAKE_HOST)

        mock_vsmsvc.MigrateVirtualSystemToHost.assert_called_once_with(
            ComputerSystem=mock_vm.path_.return_value,
            DestinationHost=self._FAKE_HOST,
            MigrationSettingData=mock_vsmsd.GetText_.return_value,
            NewResourceSettingData=self._FAKE_RASD_PATH)

    @mock.patch.object(livemigrationutils, 'vmutilsv2')
    def test_live_migrate_vm(self, mock_vm_utils):
        mock_vm_utils_remote = mock_vm_utils.VMUtilsV2.return_value
        mock_vm = self._get_vm()

        mock_migr_svc = self._conn.Msvm_VirtualSystemMigrationService()[0]
        mock_migr_svc.MigrationServiceListenerIPAddressList = [
            self._FAKE_REMOTE_IP_ADDR]

        # patches, call and assertions.
        with mock.patch.multiple(
                self._migrutils,
                _destroy_planned_vm=mock.MagicMock(),
                _get_physical_disk_paths=mock.MagicMock(),
                _get_remote_disk_data=mock.MagicMock(),
                _create_remote_planned_vm=mock.MagicMock(),
                _update_planned_vm_disk_resources=mock.MagicMock(),
                _get_vhd_setting_data=mock.MagicMock(),
                _live_migrate_vm=mock.MagicMock()):

            disk_paths = {self._FAKE_IDE_PATH: self._FAKE_SASD_HOST_RESOURCE}
            self._migrutils._get_physical_disk_paths.return_value = disk_paths

            mock_disk_paths = [mock.MagicMock()]
            mock_iscsi_targets = [mock.MagicMock()]
            self._migrutils._get_remote_disk_data.return_value = (
                mock_disk_paths, mock_iscsi_targets)

            self._migrutils._create_remote_planned_vm.return_value = mock_vm

            iscsis = self._migrutils.live_migrate_vm(self._FAKE_VM_NAME,
                                                     self._FAKE_HOST)

            self.assertEqual(iscsis, mock_iscsi_targets)

            self._migrutils._get_remote_disk_data.assert_called_once_with(
                mock_vm_utils_remote, disk_paths, self._FAKE_HOST)

            self._migrutils._create_remote_planned_vm.assert_called_once_with(
                self._conn, self._conn, mock_vm, [self._FAKE_REMOTE_IP_ADDR],
                self._FAKE_HOST)

            mocked_method = self._migrutils._update_planned_vm_disk_resources
            mocked_method.assert_called_once_with(
                mock_vm_utils_remote, self._conn, mock_vm, self._FAKE_VM_NAME,
                mock_disk_paths)

            self._migrutils._live_migrate_vm.assert_called_once_with(
                self._conn, mock_vm, mock_vm, [self._FAKE_REMOTE_IP_ADDR],
                self._migrutils._get_vhd_setting_data.return_value,
                self._FAKE_HOST)

    def _prepare_vm_mocks(self, resource_type, resource_sub_type):
        mock_vm_svc = self._conn.Msvm_VirtualSystemManagementService()[0]
        vm = self._get_vm()
        self._conn.Msvm_PlannedComputerSystem.return_value = [vm]
        mock_vm_svc.DestroySystem.return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)
        mock_vm_svc.ModifyResourceSettings.return_value = (
            None, self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        sasd = mock.MagicMock()
        bad_sasd = mock.MagicMock()
        sasd.ResourceType = resource_type
        sasd.ResourceSubType = resource_sub_type
        sasd.HostResource = [self._FAKE_SASD_HOST_RESOURCE]
        sasd.path.return_value.RelPath = self._FAKE_DISK_PATH

        vm_settings = mock.MagicMock()
        vm.associators.return_value = [vm_settings]
        vm_settings.associators.return_value = [sasd, bad_sasd]

    def _get_vm(self):
        mock_vm = mock.MagicMock()
        self._conn.Msvm_ComputerSystem.return_value = [mock_vm]
        mock_vm.path_.return_value = self._FAKE_VM_PATH
        return mock_vm
