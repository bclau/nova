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

    _FAKE_INSTANCE_NAME = "Fake name"
    _FAKE_PATH = "Fake path"
    _FAKE_DRIVE_ADDR = "Fake addr"
    _FAKE_CTRL_DISK_ADDR = "Fake ctrl disk addr"
    _FAKE_VM_GEN = "VM Generation"

    def setUp(self):
        super(VMOpsTestCase, self).setUp()
        self._vmops = vmops.VMOps()
        self._vmops._vmutils = mock.MagicMock()

    def test_attach_drive_vm_2_scsi(self):
        response = self._vmops._attach_drive(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, self._FAKE_DRIVE_ADDR,
            self._FAKE_CTRL_DISK_ADDR, constants.VM_GEN_2)

        self._vmops._vmutils.attach_scsi_drive.assert_called_once_with(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, constants.IDE_DISK)
        self.assertEquals(response, True)

    def test_attach_drive_vm_2_ide(self):
        response = self._vmops._attach_drive(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, self._FAKE_DRIVE_ADDR,
            self._FAKE_CTRL_DISK_ADDR, self._FAKE_VM_GEN)

        self._vmops._vmutils.attach_ide_drive.assert_called_once_with(
            self._FAKE_INSTANCE_NAME, self._FAKE_PATH, self._FAKE_DRIVE_ADDR,
            self._FAKE_CTRL_DISK_ADDR, constants.IDE_DISK)
        self.assertEquals(response, True)
