#  Copyright 2014 IBM Corp.
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

from nova import exception
from nova import test
from nova.tests import fake_instance
from nova.virt.hyperv import constants
from nova.virt.hyperv import vmops
from nova.virt.hyperv import vmutils


class VMOpsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V VMOps class."""

    _FAKE_VM_NAME = "Fake name"
    _FAKE_VM_UUID = "Fake uuid"
    _FAKE_TIMEOUT = 0

    def __init__(self, test_case_name):
        super(VMOpsTestCase, self).__init__(test_case_name)

    def setUp(self):
        super(VMOpsTestCase, self).setUp()
        self.context = 'fake-context'
        self.flags(force_hyperv_utils_v1=True, group='hyperv')
        self.flags(force_volumeutils_v1=True, group='hyperv')
        self._vmops = vmops.VMOps()

    def test_attach_config_drive(self):
        instance = fake_instance.fake_instance_obj(self.context)
        self.assertRaises(exception.InvalidDiskFormat,
                          self._vmops.attach_config_drive,
                          instance, 'C:/fake_instance_dir/configdrive.xxx')

    def test_reboot_hard(self):
        self._test_reboot(constants.REBOOT_TYPE_HARD,
                          constants.HYPERV_VM_STATE_REBOOT)

    @mock.patch("nova.virt.hyperv.vmops.VMOps.soft_shutdown")
    def test_reboot_soft(self, mock_soft_shutdown):
        self._test_reboot(constants.REBOOT_TYPE_SOFT,
                          constants.HYPERV_VM_STATE_ENABLED)

    @mock.patch("nova.virt.hyperv.vmops.VMOps.soft_shutdown")
    def test_reboot_exception(self, mock_soft_shutdown):
        mock_soft_shutdown.side_effect = vmutils.HyperVException(
            'Expected failure')
        self._test_reboot(constants.REBOOT_TYPE_SOFT,
                          constants.HYPERV_VM_STATE_REBOOT)

    def _test_reboot(self, reboot_type, vm_state):
        instance = self._prepare_instance()
        with mock.patch.object(self._vmops, '_set_vm_state') as mock_set_state:
            self._vmops.reboot(instance, {}, reboot_type)
            mock_set_state.assert_called_once_with(self._FAKE_VM_NAME,
                                                   vm_state)

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.soft_shutdown_vm")
    @mock.patch("nova.virt.hyperv.vmops.VMOps._wait_for_power_off")
    def test_soft_shutdown(self, mock_wait_for_power_off, mock_shutdown_vm):
        instance = self._prepare_instance()
        mock_wait_for_power_off.return_value = True

        result = self._vmops.soft_shutdown(instance, self._FAKE_TIMEOUT)

        mock_shutdown_vm.assert_called_once_with(self._FAKE_VM_NAME)
        mock_wait_for_power_off.assert_called_once_with(self._FAKE_VM_NAME,
                                                        self._FAKE_TIMEOUT)

        self.assertTrue(result)

    @mock.patch("nova.virt.hyperv.vmutils.VMUtils.soft_shutdown_vm")
    def test_soft_shutdown_failed(self, mock_shutdown_vm):
        instance = self._prepare_instance()
        mock_shutdown_vm.side_effect = vmutils.HyperVException(
            "Expected failure.")

        result = self._vmops.soft_shutdown(instance, self._FAKE_TIMEOUT)

        mock_shutdown_vm.assert_called_once_with(self._FAKE_VM_NAME)
        self.assertFalse(result)

    def _prepare_instance(self):
        instance = {'name': self._FAKE_VM_NAME,
                    'uuid': self._FAKE_VM_UUID}

        return instance

    def test_get_vm_state(self):
        summary_info = {'EnabledState': constants.HYPERV_VM_STATE_DISABLED}

        with mock.patch.object(self._vmops._vmutils,
                               'get_vm_summary_info') as mock_get_summary_info:
            mock_get_summary_info.return_value = summary_info

            response = self._vmops._get_vm_state(self._FAKE_VM_NAME)
            self.assertEqual(response, constants.HYPERV_VM_STATE_DISABLED)

    def _test_wait_for_power_off(self, vm_state, expected):
        with mock.patch.object(self._vmops, '_get_vm_state') as mock_get_state:
            mock_get_state.return_value = vm_state
            result = self._vmops._wait_for_power_off(self._FAKE_VM_NAME, 1)
            mock_get_state.assert_called_with(self._FAKE_VM_NAME)
            self.assertEqual(expected, result)

    @mock.patch('time.sleep')
    def test_wait_for_power_off_true(self, mock_sleep):
        self._test_wait_for_power_off(constants.HYPERV_VM_STATE_DISABLED, True)

    @mock.patch('time.sleep')
    def test_wait_for_power_off_false(self, mock_sleep):
        self._test_wait_for_power_off(constants.HYPERV_VM_STATE_ENABLED, False)
