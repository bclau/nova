# Copyright 2014, 2017 IBM Corp.
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

from __future__ import absolute_import

import fixtures
import mock
from pypowervm import exceptions as pvm_exc
from pypowervm.helpers import log_helper as pvm_log
from pypowervm.tasks import power
from pypowervm.tests import test_fixtures as pvm_fx
from pypowervm.utils import lpar_builder as lpar_bld
from pypowervm.wrappers import base_partition as pvm_bp
from pypowervm.wrappers import logical_partition as pvm_lpar

from nova.compute import power_state
from nova import exception
from nova import test
from nova.tests.unit.virt import powervm
from nova.virt.powervm import vm


class TestVM(test.NoDBTestCase):
    def setUp(self):
        super(TestVM, self).setUp()

        self.apt = self.useFixture(pvm_fx.AdapterFx()).adpt

        mock_entries = [mock.Mock(), mock.Mock()]
        self.resp = mock.MagicMock()
        self.resp.feed = mock.MagicMock(entries=mock_entries)

        self.get_pvm_uuid = self.useFixture(fixtures.MockPatch(
            'nova.virt.powervm.vm.get_pvm_uuid')).mock

        self.inst = powervm.TEST_INSTANCE

    @mock.patch('pypowervm.utils.lpar_builder.DefaultStandardize',
                autospec=True)
    @mock.patch('pypowervm.util.sanitize_partition_name_for_api',
                autospec=True)
    @mock.patch('nova.virt.powervm.vm.get_pvm_uuid')
    @mock.patch('pypowervm.utils.lpar_builder.LPARBuilder', autospec=True)
    def test_vm_builder(self, mock_lpar_bldr, mock_uuid2pvm, mock_san,
                        mock_def_stdz):
        inst = mock.Mock()
        inst.configure_mock(name='lpar_name', uuid='lpar_uuid',
                            flavor=mock.Mock(memory_mb='mem', vcpus='vcpus'))
        vmb = vm.VMBuilder('host', 'adap')
        mock_def_stdz.assert_called_once_with('host')
        self.assertEqual(mock_lpar_bldr.return_value,
                         vmb.lpar_builder(inst))
        mock_san.assert_called_once_with('lpar_name')
        mock_uuid2pvm.assert_called_once_with(inst)
        mock_lpar_bldr.assert_called_once_with(
            'adap', {'name': mock_san.return_value,
                     'uuid': mock_uuid2pvm.return_value,
                     'memory': 'mem',
                     'vcpu': 'vcpus'}, mock_def_stdz.return_value)

    def test_translate_vm_state(self):
        self.assertEqual(power_state.RUNNING,
                         vm._translate_vm_state('running'))
        self.assertEqual(power_state.RUNNING,
                         vm._translate_vm_state('migrating running'))
        self.assertEqual(power_state.RUNNING,
                         vm._translate_vm_state('starting'))
        self.assertEqual(power_state.RUNNING,
                         vm._translate_vm_state('open firmware'))
        self.assertEqual(power_state.RUNNING,
                         vm._translate_vm_state('shutting down'))
        self.assertEqual(power_state.RUNNING,
                         vm._translate_vm_state('suspending'))

        self.assertEqual(power_state.SHUTDOWN,
                         vm._translate_vm_state('migrating not active'))
        self.assertEqual(power_state.SHUTDOWN,
                         vm._translate_vm_state('not activated'))

        self.assertEqual(power_state.NOSTATE,
                         vm._translate_vm_state('unknown'))
        self.assertEqual(power_state.NOSTATE,
                         vm._translate_vm_state('hardware discovery'))
        self.assertEqual(power_state.NOSTATE,
                         vm._translate_vm_state('not available'))

        self.assertEqual(power_state.SUSPENDED,
                         vm._translate_vm_state('resuming'))
        self.assertEqual(power_state.SUSPENDED,
                         vm._translate_vm_state('suspended'))

        self.assertEqual(power_state.CRASHED,
                         vm._translate_vm_state('error'))

    def test_instance_info(self):
        inst_info = vm.InstanceInfo(self.apt, 'inst')
        self.get_pvm_uuid.assert_called_once_with('inst')
        # Test the static properties
        self.assertEqual(inst_info.id, self.get_pvm_uuid.return_value)

        # Check that we raise an exception if the instance is gone.
        self.apt.read.side_effect = pvm_exc.HttpError(
            mock.MagicMock(status=404))
        self.assertRaises(exception.InstanceNotFound,
                          inst_info.__getattribute__, 'state')

        # Reset the test inst_info
        inst_info = vm.InstanceInfo(self.apt, 'inst')

        class FakeResp2(object):
            def __init__(self, body):
                self.body = '"%s"' % body

        resp = FakeResp2('running')

        def return_resp(*args, **kwds):
            return resp

        self.apt.read.side_effect = return_resp
        self.assertEqual(inst_info.state, power_state.RUNNING)

        # Check the __eq__ method
        self.get_pvm_uuid.return_value = 'pvm-uuid1'
        inst_info1 = vm.InstanceInfo(self.apt, 'inst')
        inst_info2 = vm.InstanceInfo(self.apt, 'inst')
        self.assertEqual(inst_info1, inst_info2)
        self.get_pvm_uuid.return_value = 'pvm-uuid2'
        inst_info2 = vm.InstanceInfo(self.apt, 'inst2')
        self.assertNotEqual(inst_info1, inst_info2)

    @mock.patch('pypowervm.wrappers.logical_partition.LPAR', autospec=True)
    def test_get_lpar_names(self, mock_lpar):
        inst1 = mock.Mock()
        inst1.configure_mock(name='inst1')
        inst2 = mock.Mock()
        inst2.configure_mock(name='inst2')
        mock_lpar.search.return_value = [inst1, inst2]
        self.assertEqual({'inst1', 'inst2'}, set(vm.get_lpar_names('adap')))
        mock_lpar.search.assert_called_once_with(
            'adap', is_mgmt_partition=False)

    @mock.patch('pypowervm.tasks.vterm.close_vterm', autospec=True)
    def test_dlt_lpar(self, mock_vterm):
        """Performs a delete LPAR test."""
        vm.delete_lpar(self.apt, 'inst')
        self.get_pvm_uuid.assert_called_once_with('inst')
        self.apt.delete.assert_called_once_with(
            pvm_lpar.LPAR.schema_type, root_id=self.get_pvm_uuid.return_value)
        self.assertEqual(1, mock_vterm.call_count)

        # Test Failure Path
        # build a mock response body with the expected HSCL msg
        resp = mock.Mock()
        resp.body = 'error msg: HSCL151B more text'
        self.apt.delete.side_effect = pvm_exc.Error(
            'Mock Error Message', response=resp)

        # Reset counters
        self.apt.reset_mock()
        mock_vterm.reset_mock()

        self.assertRaises(pvm_exc.Error, vm.delete_lpar, self.apt, 'inst')
        self.assertEqual(1, mock_vterm.call_count)
        self.assertEqual(1, self.apt.delete.call_count)

        self.apt.reset_mock()
        mock_vterm.reset_mock()

        # Test HttpError 404
        resp.status = 404
        self.apt.delete.side_effect = pvm_exc.HttpError(resp=resp)
        vm.delete_lpar(self.apt, 'inst')
        self.assertEqual(1, mock_vterm.call_count)
        self.assertEqual(1, self.apt.delete.call_count)

        self.apt.reset_mock()
        mock_vterm.reset_mock()

        # Test Other HttpError
        resp.status = 111
        self.apt.delete.side_effect = pvm_exc.HttpError(resp=resp)
        self.assertRaises(pvm_exc.HttpError, vm.delete_lpar, self.apt, 'inst')
        self.assertEqual(1, mock_vterm.call_count)
        self.assertEqual(1, self.apt.delete.call_count)

        self.apt.reset_mock()
        mock_vterm.reset_mock()

        # Test HttpError 404 closing vterm
        resp.status = 404
        mock_vterm.side_effect = pvm_exc.HttpError(resp=resp)
        vm.delete_lpar(self.apt, 'inst')
        self.assertEqual(1, mock_vterm.call_count)
        self.assertEqual(0, self.apt.delete.call_count)

        self.apt.reset_mock()
        mock_vterm.reset_mock()

        # Test Other HttpError closing vterm
        resp.status = 111
        mock_vterm.side_effect = pvm_exc.HttpError(resp=resp)
        self.assertRaises(pvm_exc.HttpError, vm.delete_lpar, self.apt, 'inst')
        self.assertEqual(1, mock_vterm.call_count)
        self.assertEqual(0, self.apt.delete.call_count)

    @mock.patch('nova.virt.powervm.vm.VMBuilder', autospec=True)
    @mock.patch('pypowervm.utils.validation.LPARWrapperValidator',
                autospec=True)
    def test_crt_lpar(self, mock_vld, mock_vmbldr):
        mock_bldr = mock.Mock(spec=lpar_bld.LPARBuilder)
        mock_vmbldr.return_value.lpar_builder.return_value = mock_bldr
        mock_pend_lpar = mock.create_autospec(pvm_lpar.LPAR, instance=True)
        mock_bldr.build.return_value = mock_pend_lpar

        vm.create_lpar(self.apt, 'host', self.inst)
        mock_vmbldr.assert_called_once_with('host', self.apt)
        mock_vmbldr.return_value.lpar_builder.assert_called_once_with(
            self.inst)
        mock_bldr.build.assert_called_once_with()
        mock_vld.assert_called_once_with(mock_pend_lpar, 'host')
        mock_vld.return_value.validate_all.assert_called_once_with()
        mock_pend_lpar.create.assert_called_once_with(parent='host')

    @mock.patch('pypowervm.wrappers.logical_partition.LPAR', autospec=True)
    def test_get_instance_wrapper(self, mock_lpar):
        resp = mock.Mock(status=404)
        mock_lpar.get.side_effect = pvm_exc.Error('message', response=resp)
        # vm.get_instance_wrapper(self.apt, instance, 'lpar_uuid')
        self.assertRaises(exception.InstanceNotFound, vm.get_instance_wrapper,
                          self.apt, self.inst)

    @mock.patch('pypowervm.tasks.power.power_on', autospec=True)
    @mock.patch('oslo_concurrency.lockutils.lock', autospec=True)
    @mock.patch('nova.virt.powervm.vm.get_instance_wrapper')
    def test_power_on(self, mock_wrap, mock_lock, mock_power_on):
        entry = mock.Mock(state=pvm_bp.LPARState.NOT_ACTIVATED)
        mock_wrap.return_value = entry

        vm.power_on(None, self.inst)
        mock_power_on.assert_called_once_with(entry, None)
        mock_lock.assert_called_once_with('power_%s' % self.inst.uuid)

        mock_power_on.reset_mock()
        mock_lock.reset_mock()

        stop_states = [
            pvm_bp.LPARState.RUNNING, pvm_bp.LPARState.STARTING,
            pvm_bp.LPARState.OPEN_FIRMWARE, pvm_bp.LPARState.SHUTTING_DOWN,
            pvm_bp.LPARState.ERROR, pvm_bp.LPARState.RESUMING,
            pvm_bp.LPARState.SUSPENDING]

        for stop_state in stop_states:
            entry.state = stop_state
            vm.power_on(None, self.inst)
            mock_lock.assert_called_once_with('power_%s' % self.inst.uuid)
            mock_lock.reset_mock()
        self.assertEqual(0, mock_power_on.call_count)

    @mock.patch('pypowervm.tasks.power.power_on', autospec=True)
    @mock.patch('nova.virt.powervm.vm.get_instance_wrapper')
    def test_power_on_negative(self, mock_wrp, mock_power_on):
        mock_wrp.return_value = mock.Mock(state=pvm_bp.LPARState.NOT_ACTIVATED)

        # Convertible (PowerVM) exception
        mock_power_on.side_effect = pvm_exc.VMPowerOnFailure(
            reason='Something bad', lpar_nm='TheLPAR')
        self.assertRaises(exception.InstancePowerOnFailure,
                          vm.power_on, None, self.inst)

        # Non-pvm error raises directly
        mock_power_on.side_effect = ValueError()
        self.assertRaises(ValueError, vm.power_on, None, self.inst)

    @mock.patch('pypowervm.tasks.power.power_off', autospec=True)
    @mock.patch('oslo_concurrency.lockutils.lock', autospec=True)
    @mock.patch('nova.virt.powervm.vm.get_instance_wrapper')
    def test_power_off(self, mock_wrap, mock_lock, mock_power_off):
        entry = mock.Mock(state=pvm_bp.LPARState.NOT_ACTIVATED)
        mock_wrap.return_value = entry

        vm.power_off(None, self.inst)
        self.assertEqual(0, mock_power_off.call_count)
        mock_lock.assert_called_once_with('power_%s' % self.inst.uuid)

        stop_states = [
            pvm_bp.LPARState.RUNNING, pvm_bp.LPARState.STARTING,
            pvm_bp.LPARState.OPEN_FIRMWARE, pvm_bp.LPARState.SHUTTING_DOWN,
            pvm_bp.LPARState.ERROR, pvm_bp.LPARState.RESUMING,
            pvm_bp.LPARState.SUSPENDING]
        for stop_state in stop_states:
            entry.state = stop_state
            mock_power_off.reset_mock()
            mock_lock.reset_mock()
            vm.power_off(None, self.inst)
            mock_power_off.assert_called_once_with(
                entry, None, force_immediate=power.Force.ON_FAILURE)
            mock_lock.assert_called_once_with('power_%s' % self.inst.uuid)
            mock_power_off.reset_mock()
            mock_lock.reset_mock()
            vm.power_off(None, self.inst, force_immediate=True, timeout=5)
            mock_power_off.assert_called_once_with(
                entry, None, force_immediate=True, timeout=5)
            mock_lock.assert_called_once_with('power_%s' % self.inst.uuid)

    @mock.patch('pypowervm.tasks.power.power_off', autospec=True)
    @mock.patch('nova.virt.powervm.vm.get_instance_wrapper')
    def test_power_off_negative(self, mock_wrap, mock_power_off):
        """Negative tests."""
        mock_wrap.return_value = mock.Mock(state=pvm_bp.LPARState.RUNNING)

        # Raise the expected pypowervm exception
        mock_power_off.side_effect = pvm_exc.VMPowerOffFailure(
            reason='Something bad.', lpar_nm='TheLPAR')
        # We should get a valid Nova exception that the compute manager expects
        self.assertRaises(exception.InstancePowerOffFailure,
                          vm.power_off, None, self.inst)

        # Non-pvm error raises directly
        mock_power_off.side_effect = ValueError()
        self.assertRaises(ValueError, vm.power_off, None, self.inst)

    @mock.patch('pypowervm.tasks.power.power_on', autospec=True)
    @mock.patch('pypowervm.tasks.power.power_off', autospec=True)
    @mock.patch('oslo_concurrency.lockutils.lock', autospec=True)
    @mock.patch('nova.virt.powervm.vm.get_instance_wrapper')
    def test_reboot(self, mock_wrap, mock_lock, mock_pwroff, mock_pwron):
        entry = mock.Mock(state=pvm_bp.LPARState.NOT_ACTIVATED)
        mock_wrap.return_value = entry

        # No power_off
        vm.reboot('adap', self.inst, False)
        mock_lock.assert_called_once_with('power_%s' % self.inst.uuid)
        mock_wrap.assert_called_once_with('adap', self.inst)
        mock_pwron.assert_called_once_with(entry, None)
        self.assertEqual(0, mock_pwroff.call_count)

        mock_pwron.reset_mock()

        # power_off (no power_on)
        entry.state = pvm_bp.LPARState.RUNNING
        for force in (False, True):
            mock_pwroff.reset_mock()
            vm.reboot('adap', self.inst, force)
            self.assertEqual(0, mock_pwron.call_count)
            mock_pwroff.assert_called_once_with(
                entry, None, force_immediate=force, restart=True)

        # PowerVM error is converted
        mock_pwroff.side_effect = pvm_exc.TimeoutError("Timed out")
        self.assertRaises(exception.InstanceRebootFailure,
                          vm.reboot, 'adap', self.inst, True)

        # Non-PowerVM error is raised directly
        mock_pwroff.side_effect = ValueError
        self.assertRaises(ValueError, vm.reboot, 'adap', self.inst, True)

    @mock.patch('oslo_serialization.jsonutils.loads')
    def test_get_vm_qp(self, mock_loads):
        self.apt.helpers = ['helper1', pvm_log.log_helper, 'helper3']

        # Defaults
        self.assertEqual(mock_loads.return_value,
                         vm.get_vm_qp(self.apt, 'lpar_uuid'))
        self.apt.read.assert_called_once_with(
            'LogicalPartition', root_id='lpar_uuid', suffix_type='quick',
            suffix_parm=None)
        mock_loads.assert_called_once_with(self.apt.read.return_value.body)

        self.apt.read.reset_mock()
        mock_loads.reset_mock()

        # Specific qprop, no logging errors
        self.assertEqual(mock_loads.return_value,
                         vm.get_vm_qp(self.apt, 'lpar_uuid', qprop='Prop',
                                      log_errors=False))
        self.apt.read.assert_called_once_with(
            'LogicalPartition', root_id='lpar_uuid', suffix_type='quick',
            suffix_parm='Prop', helpers=['helper1', 'helper3'])

        resp = mock.MagicMock()
        resp.status = 404
        self.apt.read.side_effect = pvm_exc.HttpError(resp)
        self.assertRaises(exception.InstanceNotFound, vm.get_vm_qp, self.apt,
                          'lpar_uuid', log_errors=False)

        self.apt.read.side_effect = pvm_exc.Error("message", response=None)
        self.assertRaises(pvm_exc.Error, vm.get_vm_qp, self.apt,
                          'lpar_uuid', log_errors=False)

        resp.status = 500
        self.apt.read.side_effect = pvm_exc.Error("message", response=resp)
        self.assertRaises(pvm_exc.Error, vm.get_vm_qp, self.apt,
                          'lpar_uuid', log_errors=False)