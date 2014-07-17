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
from nova.virt.hyperv import vmutils


class VMOpsTestCase(test.NoDBTestCase):
    """Uni tests for the Hyper-V VMOps class."""

    _FAKE_VM_NAME = "Fake name"
    _FAKE_VM_UUID = "Fake uuid"
    _FAKE_VHD_PATH = "VHD path"
    _FAKE_DRIVE_ADDR = "Fake addr"
    _FAKE_CTRL_DISK_ADDR = "Fake ctrl disk addr"
    _FAKE_VM_GEN = "VM Generation"

    def setUp(self):
        super(VMOpsTestCase, self).setUp()
        self._vmops = vmops.VMOps()

    def test_reboot_soft(self):
        self._test_reboot(constants.REBOOT_TYPE_HARD,
                          constants.HYPERV_VM_STATE_REBOOT)

    @mock.patch("nova.virt.hyperv.vmops.VMOps._wait_for_power_off")
    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.soft_shutdown_vm")
    def test_reboot_soft(self, mock_soft_shutdown_vm, mock_wait_for_power_off):
        self._test_reboot(constants.REBOOT_TYPE_SOFT,
                          constants.HYPERV_VM_STATE_ENABLED)

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.soft_shutdown_vm")
    def test_reboot_exception(self, mock_soft_shutdown_vm):
        mock_soft_shutdown_vm.side_effect = Exception('Expected failure')
        self._test_reboot(constants.REBOOT_TYPE_SOFT,
                          constants.HYPERV_VM_STATE_REBOOT)

    def _test_reboot(self, reboot_type, vm_state):
        instance = self._prepare_instance()
        with mock.patch.object(self._vmops, '_set_vm_state') as mock_set_state:
            self._vmops.reboot(instance, {}, reboot_type)
            mock_set_state.assert_called_once_with(self._FAKE_VM_NAME,
                                                   vm_state)

    def _prepare_instance(self):
        instance = {'name': self._FAKE_VM_NAME,
                    'uuid': self._FAKE_VM_UUID}

        return instance

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.get_vm_summary_info")
    def test_get_vm_state(self, mock_get_vm_summary_info):

        summary_info = {'EnabledState': constants.HYPERV_VM_STATE_DISABLED}
        mock_get_vm_summary_info.return_value = summary_info

        response = self._vmops._get_vm_state(self._FAKE_VM_NAME)
        self.assertEquals(response, constants.HYPERV_VM_STATE_DISABLED)

    @mock.patch('time.sleep')
    @mock.patch("nova.virt.hyperv.vmops.VMOps._get_vm_state")
    def test_wait_for_power_off(self, mock_get_vm_state, mock_sleep):
        mock_get_vm_state.return_value = constants.HYPERV_VM_STATE_DISABLED

        self._vmops._wait_for_power_off(self._FAKE_VM_NAME, time_limit=1)

        mock_get_vm_state.assert_called_once_with(self._FAKE_VM_NAME)

    @mock.patch('time.sleep')
    @mock.patch("nova.virt.hyperv.vmops.VMOps._get_vm_state")
    def test_wait_for_power_off_2(self, mock_get_vm_state, mock_sleep):
        mock_get_vm_state.return_value = constants.HYPERV_VM_STATE_ENABLED

        self.assertRaises(vmutils.HyperVException,
                          self._vmops._wait_for_power_off,
                          self._FAKE_VM_NAME, time_limit=1)

        mock_get_vm_state.assert_called_with(self._FAKE_VM_NAME)
