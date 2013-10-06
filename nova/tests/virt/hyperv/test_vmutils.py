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
import sys

from nova import exception
from nova import test
from nova.virt.hyperv import constants
from nova.virt.hyperv import vmutils


class VMUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V VMUtils class."""

    _FAKE_VM_NAME = 'fake_vm'
    _FAKE_MEMORY_MB = 2
    _FAKE_VCPUS_NUM = 4
    _FAKE_JOB_PATH = 'fake_job_path'
    _FAKE_RET_VAL = 0
    _FAKE_RET_VAL_BAD = -1
    _FAKE_CTRL_PATH = 'fake_ctrl_path'
    _FAKE_CTRL_ADDR = 0
    _FAKE_DRIVE_ADDR = 0
    _FAKE_MOUNTED_DISK_PATH = 'fake_mounted_disk_path'
    _FAKE_VM_PATH = "fake_vm_path"
    _FAKE_ENABLED_STATE = 1
    _FAKE_SNAPSHOT_PATH = "_FAKE_SNAPSHOT_PATH"
    _FAKE_RES_DATA = "fake_res_data"
    _FAKE_HOST_RESOURCE = "fake_host_resource"
    _FAKE_CLASS = "FakeClass"
    _FAKE_RES_PATH = "fake_res_path"
    _FAKE_ADDRESS = "fake_address"
    _FAKE_JOB_STATUS_DONE = 7
    _FAKE_JOB_DESCRIPTION = "fake_job_description"
    _FAKE_ERROR = "fake_error"
    _FAKE_ELAPSED_TIME = 0
    _CONCRETE_JOB = "Msvm_ConcreteJob"
    _FAKE_DYNAMIC_MEMORY_RATIO = 1.0

    _FAKE_SUMMARY_INFO = {'NumberOfProcessors': 4,
                          'EnabledState': 2,
                          'MemoryUsage': 2,
                          'UpTime': 1}

    _DEFINE_SYSTEM = 'DefineVirtualSystem'
    _DESTROY_SYSTEM = 'DestroyVirtualSystem'
    _DESTROY_SNAPSHOT = 'RemoveVirtualSystemSnapshot'
    _ADD_RESOURCE = 'AddVirtualSystemResources'
    _REMOVE_RESOURCE = 'RemoveVirtualSystemResources'
    _SETTING_TYPE = 'SettingType'

    def setUp(self):
        self._mock_wmi = mock.MagicMock()
        self._wmi_patcher = mock.patch.dict(sys.modules, wmi=self._mock_wmi)
        self._platform_patcher = mock.patch('sys.platform', 'win32')
        self._platform_patcher.start()
        self._wmi_patcher.start()

        reload(vmutils)
        self._vmutils = vmutils.VMUtils()
        self._vmutils._conn = mock.MagicMock()

        super(VMUtilsTestCase, self).setUp()

    def tearDown(self):
        super(VMUtilsTestCase, self).tearDown()
        self._wmi_patcher.stop()
        self._platform_patcher.stop()
        reload(vmutils)

    def test_enable_vm_metrics_collection(self):
        self.assertRaises(NotImplementedError,
                          self._vmutils.enable_vm_metrics_collection,
                          self._FAKE_VM_NAME)

    def test_get_vm_summary_info(self):
        self._lookup_vm()
        mock_svc = self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]

        mock_summary = mock.MagicMock()
        mock_svc.GetSummaryInformation.return_value = (self._FAKE_RET_VAL,
                                                       [mock_summary])

        for (key, val) in self._FAKE_SUMMARY_INFO.items():
            setattr(mock_summary, key, val)

        summary = self._vmutils.get_vm_summary_info(self._FAKE_VM_NAME)
        self.assertEqual(self._FAKE_SUMMARY_INFO, summary)

    def _lookup_vm(self):
        mock_vm = mock.MagicMock()
        self._vmutils._lookup_vm_check = mock.MagicMock(return_value=mock_vm)
        mock_vm.path_.return_value = self._FAKE_VM_PATH
        return mock_vm

    def test_lookup_vm_ok(self):
        mock_vm = mock.MagicMock()
        self._vmutils._conn.Msvm_ComputerSystem.return_value = [mock_vm]
        vm = self._vmutils._lookup_vm_check(self._FAKE_VM_NAME)
        self.assertEqual(mock_vm, vm)

    def test_lookup_vm_multiple(self):
        mockvm = mock.MagicMock()
        self._vmutils._conn.Msvm_ComputerSystem.return_value = [mockvm, mockvm]
        self.assertRaises(vmutils.HyperVException,
                          self._vmutils._lookup_vm_check,
                          self._FAKE_VM_NAME)

    def test_lookup_vm_none(self):
        self._vmutils._conn.Msvm_ComputerSystem.return_value = []
        self.assertRaises(exception.NotFound,
                          self._vmutils._lookup_vm_check,
                          self._FAKE_VM_NAME)

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

    def test_create_vm(self):
        mock_svc = self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]
        getattr(mock_svc, self._DEFINE_SYSTEM).return_value = (
            None, self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vmutils._get_wmi_obj = mock.MagicMock()
        mock_vm = self._vmutils._get_wmi_obj.return_value
        self._vmutils._conn.Msvm_ComputerSystem.return_value = [mock_vm]

        mock_s = mock.MagicMock()
        setattr(mock_s,
                self._SETTING_TYPE,
                self._vmutils._VIRTUAL_SYSTEM_TYPE_REALIZED)
        mock_vm.associators.return_value = [mock_s]

        self._vmutils._set_vm_memory = mock.MagicMock()
        self._vmutils._set_vm_vcpus = mock.MagicMock()

        self._vmutils.create_vm(self._FAKE_VM_NAME, self._FAKE_MEMORY_MB,
                                self._FAKE_VCPUS_NUM, False,
                                self._FAKE_DYNAMIC_MEMORY_RATIO)

        self.assertTrue(getattr(mock_svc, self._DEFINE_SYSTEM).called)
        self._vmutils._set_vm_memory.assert_called_with(
            mock_vm, mock_s, self._FAKE_MEMORY_MB,
            self._FAKE_DYNAMIC_MEMORY_RATIO)

        self._vmutils._set_vm_vcpus.assert_called_with(mock_vm, mock_s,
                                                       self._FAKE_VCPUS_NUM,
                                                       False)

    def test_get_vm_scsi_controller(self):
        self._prepare_get_vm_controller(self._vmutils._SCSI_CTRL_RES_SUB_TYPE)
        path = self._vmutils.get_vm_scsi_controller(self._FAKE_VM_NAME)
        self.assertEqual(self._FAKE_RES_PATH, path)

    def test_get_vm_ide_controller(self):
        self._prepare_get_vm_controller(self._vmutils._IDE_CTRL_RES_SUB_TYPE)
        path = self._vmutils.get_vm_ide_controller(self._FAKE_VM_NAME,
                                                   self._FAKE_ADDRESS)
        self.assertEqual(self._FAKE_RES_PATH, path)

    def _prepare_get_vm_controller(self, resource_sub_type):
        mock_vm = self._lookup_vm()
        mock_vm_settings = mock.MagicMock()
        mock_rasds = mock.MagicMock()
        mock_rasds.path_.return_value = self._FAKE_RES_PATH
        mock_rasds.ResourceSubType = resource_sub_type
        mock_rasds.Address = self._FAKE_ADDRESS
        mock_vm_settings.associators.return_value = [mock_rasds]
        mock_vm.associators.return_value = [mock_vm_settings]

    def _prepare_resources(self, mock_path, mock_subtype, mock_vm_settings):
        mock_rasds = mock_vm_settings.associators.return_value[0]
        mock_rasds.path_.return_value = mock_path
        mock_rasds.ResourceSubType = mock_subtype
        return mock_rasds

    def test_attach_ide_drive(self):
        self._lookup_vm()
        self._vmutils._get_vm_ide_controller = mock.MagicMock()
        self._vmutils._get_new_resource_setting_data = mock.MagicMock()
        self._vmutils._add_virt_resource = mock.MagicMock()

        self._vmutils.attach_ide_drive(self._FAKE_VM_NAME,
                                       self._FAKE_CTRL_PATH,
                                       self._FAKE_CTRL_ADDR,
                                       self._FAKE_DRIVE_ADDR)

        self.assertTrue(self._vmutils._get_vm_ide_controller.called)
        self.assertTrue(self._vmutils._get_new_resource_setting_data.called)
        self.assertTrue(self._vmutils._add_virt_resource.called)

    def test_attach_volume_to_controller(self):
        self._lookup_vm()
        self._vmutils._add_virt_resource = mock.MagicMock()

        self._vmutils.attach_volume_to_controller(self._FAKE_VM_NAME,
                                                  self._FAKE_CTRL_PATH,
                                                  self._FAKE_CTRL_ADDR,
                                                  self._FAKE_MOUNTED_DISK_PATH)

        self.assertTrue(self._vmutils._add_virt_resource.called)

    def test_create_scsi_controller(self):
        self._lookup_vm()
        self._vmutils._add_virt_resource = mock.MagicMock()
        self._vmutils.create_scsi_controller(self._FAKE_VM_NAME)

        self.assertTrue(self._vmutils._add_virt_resource.called)

    def test_destroy(self):
        self._lookup_vm()

        mock_svc = self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]
        getattr(mock_svc, self._DESTROY_SYSTEM).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vmutils.destroy_vm(self._FAKE_VM_NAME)

        getattr(mock_svc, self._DESTROY_SYSTEM).assert_called_with(
            self._FAKE_VM_PATH)

    def test_get_vm_state(self):
        self._vmutils.get_vm_summary_info = mock.MagicMock(
            return_value={'EnabledState': self._FAKE_ENABLED_STATE})

        enabled_state = self._vmutils.get_vm_state(self._FAKE_VM_NAME)
        self.assertEqual(self._FAKE_ENABLED_STATE, enabled_state)

    def test_set_vm_state(self):
        mock_vm = self._lookup_vm()
        mock_vm.RequestStateChange.return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vmutils.set_vm_state(self._FAKE_VM_NAME,
                                   constants.HYPERV_VM_STATE_ENABLED)
        mock_vm.RequestStateChange.assert_called_with(
            constants.HYPERV_VM_STATE_ENABLED)

    def test_get_vm_storage_paths(self):
        mock_vm = self._lookup_vm()
        mock_vm_settings = mock.MagicMock()
        mock_disk = self._prepare_mock_disk()
        mock_disk.Connection = [self._FAKE_MOUNTED_DISK_PATH]

        mock_volume = mock.MagicMock()
        mock_volume.ResourceSubType = self._vmutils._PHYS_DISK_RES_SUB_TYPE
        mock_volume.HostResource = [self._FAKE_HOST_RESOURCE]

        mock_vm_settings.associators.return_value = [mock_volume, mock_disk]
        mock_vm.associators.return_value = [mock_vm_settings]

        disk_files, volume_files = self._vmutils.get_vm_storage_paths(
            self._FAKE_VM_NAME)

        self.assertEqual([self._FAKE_HOST_RESOURCE], volume_files)
        self.assertEqual([self._FAKE_MOUNTED_DISK_PATH], disk_files)

    def test_check_ret_val_exception(self):
        self.assertRaises(vmutils.HyperVException,
                          self._vmutils.check_ret_val,
                          self._FAKE_RET_VAL_BAD,
                          self._FAKE_JOB_PATH)

    def test_wait_for_job_done(self):
        mock_job = self._prepare_wait_for_job(self._FAKE_JOB_STATUS_DONE)
        job = self._vmutils._wait_for_job(self._FAKE_JOB_PATH)
        self.assertEqual(mock_job, job)

    def test_wait_for_job_exception_concrete_job(self):
        mock_job = self._prepare_wait_for_job()
        mock_job.path.return_value.Class = self._CONCRETE_JOB
        self.assertRaises(vmutils.HyperVException,
                          self._vmutils._wait_for_job,
                          self._FAKE_JOB_PATH)

    def test_wait_for_job_exception_with_error(self):
        mock_job = self._prepare_wait_for_job()
        mock_job.GetError.return_value = (self._FAKE_ERROR, self._FAKE_RET_VAL)
        self.assertRaises(vmutils.HyperVException,
                          self._vmutils._wait_for_job,
                          self._FAKE_JOB_PATH)

    def test_wait_for_job_exception_no_error(self):
        mock_job = self._prepare_wait_for_job()
        mock_job.GetError.return_value = (None, None)
        self.assertRaises(vmutils.HyperVException,
                          self._vmutils._wait_for_job,
                          self._FAKE_JOB_PATH)

    def _prepare_wait_for_job(self, state=-1):
        mock_job = mock.MagicMock()
        mock_job.JobState = state
        mock_job.Description = self._FAKE_JOB_DESCRIPTION
        mock_job.ElapsedTime = self._FAKE_ELAPSED_TIME

        self._vmutils._get_wmi_obj = mock.MagicMock(return_value=mock_job)
        return mock_job

    @mock.patch.object(vmutils, 'wmi')
    def test_take_vm_snapshot(self, mock_wmi):
        self._lookup_vm()

        mock_svc = self._get_snapshot_service()
        mock_svc.CreateVirtualSystemSnapshot.return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL, mock.MagicMock())

        self._vmutils.take_vm_snapshot(self._FAKE_VM_NAME)

        mock_svc.CreateVirtualSystemSnapshot.assert_called_with(
            self._FAKE_VM_PATH)

    def test_remove_vm_snapshot(self):
        mock_svc = self._get_snapshot_service()
        getattr(mock_svc, self._DESTROY_SNAPSHOT).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)

        self._vmutils.remove_vm_snapshot(self._FAKE_SNAPSHOT_PATH)
        getattr(mock_svc, self._DESTROY_SNAPSHOT).assert_called_with(
            self._FAKE_SNAPSHOT_PATH)

    def test_set_nic_connection(self):
        self._lookup_vm()
        nic = mock.MagicMock()
        self._vmutils._get_nic_data_by_name = mock.MagicMock(return_value=nic)
        self._vmutils._modify_virt_resource = mock.MagicMock()

        self._vmutils.set_nic_connection(self._FAKE_VM_NAME, None, None)
        self._vmutils._modify_virt_resource.assert_called_with(
            nic, self._FAKE_VM_PATH)

    def test_add_virt_resource(self):
        mock_svc = self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]
        getattr(mock_svc, self._ADD_RESOURCE).return_value = (
            self._FAKE_JOB_PATH, mock.MagicMock(), self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.GetText_.return_value = self._FAKE_RES_DATA

        self._vmutils._add_virt_resource(mock_res_setting_data,
                                         self._FAKE_VM_PATH)
        self._assert_add_resources(mock_svc)

    def test_clone_wmi_obj(self):
        mock_obj = mock.MagicMock()
        mock_class = mock.MagicMock()
        mock_class.new.return_value = mock_obj
        setattr(self._vmutils._conn, self._FAKE_CLASS, mock_class)
        new_obj = self._vmutils._clone_wmi_obj(self._FAKE_CLASS, mock_obj)
        self.assertEqual(mock_obj, new_obj)

    def test_modify_virt_resource(self):
        mock_svc = self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_svc.ModifyVirtualSystemResources.return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.GetText_.return_value = self._FAKE_RES_DATA

        self._vmutils._modify_virt_resource(mock_res_setting_data,
                                            self._FAKE_VM_PATH)

        mock_svc.ModifyVirtualSystemResources.assert_called_with(
            ResourceSettingData=[self._FAKE_RES_DATA],
            ComputerSystem=self._FAKE_VM_PATH)

    def test_remove_virt_resource(self):
        mock_svc = self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]
        getattr(mock_svc, self._REMOVE_RESOURCE).return_value = (
            self._FAKE_JOB_PATH, self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.path_.return_value = self._FAKE_RES_PATH

        self._vmutils._remove_virt_resource(mock_res_setting_data,
                                            self._FAKE_VM_PATH)
        self._assert_remove_resources(mock_svc)

    def test_detach_vm_disk(self):
        self._lookup_vm()
        mock_disk = self._prepare_mock_disk()
        self._vmutils._remove_virt_resource = mock.MagicMock()
        self._vmutils.detach_vm_disk(self._FAKE_VM_NAME,
                                     self._FAKE_HOST_RESOURCE)

        self._vmutils._remove_virt_resource.assert_called_with(
            mock_disk, self._FAKE_VM_PATH)

    def test_get_controller_volume_paths(self):
        self._prepare_mock_disk()
        mock_disks = {self._FAKE_RES_PATH: self._FAKE_HOST_RESOURCE}
        disks = self._vmutils.get_controller_volume_paths(self._FAKE_RES_PATH)
        self.assertEqual(mock_disks, disks)

    def _prepare_mock_disk(self):
        mock_disk = mock.MagicMock()
        mock_disk.HostResource = [self._FAKE_HOST_RESOURCE]
        mock_disk.path.return_value.RelPath = self._FAKE_RES_PATH
        mock_disk.ResourceSubType = self._vmutils._IDE_DISK_RES_SUB_TYPE
        self._vmutils._conn.query.return_value = [mock_disk]

        return mock_disk

    def _get_snapshot_service(self):
        return self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]

    def _assert_add_resources(self, mock_svc):
        getattr(mock_svc, self._ADD_RESOURCE).assert_called_with(
            [self._FAKE_RES_DATA], self._FAKE_VM_PATH)

    def _assert_remove_resources(self, mock_svc):
        getattr(mock_svc, self._REMOVE_RESOURCE).assert_called_with(
            [self._FAKE_RES_PATH], self._FAKE_VM_PATH)
