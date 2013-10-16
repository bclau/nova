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

from nova.tests.virt.hyperv import test_vmutils
from nova.virt.hyperv import vmutilsv2


class VMUtilsV2TestCase(test_vmutils.VMUtilsTestCase):
    """Unit tests for the Hyper-V VMUtilsV2 class."""

    _DEFINE_SYSTEM = 'DefineSystem'
    _DESTROY_SYSTEM = 'DestroySystem'
    _DESTROY_SNAPSHOT = 'DestroySnapshot'

    _ADD_RESOURCE = 'AddResourceSettings'
    _REMOVE_RESOURCE = 'RemoveResourceSettings'
    _SETTING_TYPE = 'VirtualSystemType'

    _VIRTUAL_SYSTEM_TYPE_REALIZED = 'Microsoft:Hyper-V:System:Realized'

    @classmethod
    def setUpClass(cls):
        super(VMUtilsV2TestCase, cls).setUpClass()
        reload(vmutilsv2)

    @classmethod
    def tearDownClass(cls):
        super(VMUtilsV2TestCase, cls).tearDownClass()
        reload(vmutilsv2)

    def setUp(self):
        super(VMUtilsV2TestCase, self).setUp()
        self._vmutils = vmutilsv2.VMUtilsV2()
        self._vmutils._conn = mock.MagicMock()

    def test_modify_virt_resource(self):
        mock_svc = self._vmutils._conn.Msvm_VirtualSystemManagementService()[0]
        mock_svc.ModifyResourceSettings.return_value = (self._FAKE_JOB_PATH,
                                                        mock.MagicMock(),
                                                        self._FAKE_RET_VAL)
        mock_res_setting_data = mock.MagicMock()
        mock_res_setting_data.GetText_.return_value = self._FAKE_RES_DATA

        self._vmutils._modify_virt_resource(mock_res_setting_data,
                                            self._FAKE_VM_PATH)

        mock_svc.ModifyResourceSettings.assert_called_with(
            ResourceSettings=[self._FAKE_RES_DATA])

    def test_take_vm_snapshot(self):
        self._lookup_vm()

        mock_svc = self._vmutils._conn.Msvm_VirtualSystemSnapshotService()[0]
        mock_svc.CreateSnapshot.return_value = (self._FAKE_JOB_PATH,
                                                mock.MagicMock(),
                                                self._FAKE_RET_VAL)

        self._vmutils.take_vm_snapshot(self._FAKE_VM_NAME)

        mock_svc.CreateSnapshot.assert_called_with(
            AffectedSystem=self._FAKE_VM_PATH,
            SnapshotType=self._vmutils._SNAPSHOT_FULL)

    @mock.patch('nova.virt.hyperv.vmutilsv2.VMUtilsV2._add_virt_resource')
    @mock.patch('nova.virt.hyperv.vmutilsv2.VMUtilsV2._get_new_setting_data')
    @mock.patch('nova.virt.hyperv.vmutilsv2.VMUtilsV2._get_nic_data_by_name')
    def test_set_nic_connection(self, mock_get_nic_data, mock_get_new_sd,
                                mock_add_virt_res):
        self._lookup_vm()
        fake_eth_port = mock_get_new_sd.return_value

        self._vmutils.set_nic_connection(self._FAKE_VM_NAME, None, None)
        mock_add_virt_res.assert_called_with(fake_eth_port, self._FAKE_VM_PATH)

    @mock.patch('nova.virt.hyperv.vmutils.VMUtils._get_vm_disks')
    def test_enable_vm_metrics_collection(self, mock_get_vm_disks):
        self._lookup_vm()
        mock_svc = self._vmutils._conn.Msvm_MetricService()[0]

        metric_def = mock.MagicMock()
        mock_disk = mock.MagicMock()
        mock_disk.path_.return_value = self._FAKE_RES_PATH
        mock_get_vm_disks.return_value = ([mock_disk], [mock_disk])

        fake_metric_def_paths = ["fake_0", None]
        fake_metric_resource_paths = [self._FAKE_VM_PATH, self._FAKE_RES_PATH]

        metric_def.path_.side_effect = fake_metric_def_paths
        self._vmutils._conn.CIM_BaseMetricDefinition.return_value = [
            metric_def]

        self._vmutils.enable_vm_metrics_collection(self._FAKE_VM_NAME)

        calls = []
        for i in range(len(fake_metric_def_paths)):
            calls.append(mock.call(
                Subject=fake_metric_resource_paths[i],
                Definition=fake_metric_def_paths[i],
                MetricCollectionEnabled=self._vmutils._METRIC_ENABLED))

        mock_svc.ControlMetrics.assert_has_calls(calls, any_order=True)

    def _mock_virt_resources(self):
        self._vmutils._add_virt_resource = mock.MagicMock()

    def _get_snapshot_service(self):
        return self._vmutils._conn.Msvm_VirtualSystemSnapshotService()[0]

    def _assert_add_resources(self, mock_svc):
        getattr(mock_svc, self._ADD_RESOURCE).assert_called_with(
            self._FAKE_VM_PATH, [self._FAKE_RES_DATA])

    def _assert_remove_resources(self, mock_svc):
        getattr(mock_svc, self._REMOVE_RESOURCE).assert_called_with(
            [self._FAKE_RES_PATH])
