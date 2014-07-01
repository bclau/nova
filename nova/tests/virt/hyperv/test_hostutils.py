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
from nova.virt.hyperv import hostutils


class HostUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V HostUtils class."""

    def setUp(self):
        super(HostUtilsTestCase, self).setUp()
        self._hostutils = hostutils.HostUtils()

    def _test_get_supported_machine_types(self, is_6_3, expected):
        with mock.patch.object(self._hostutils,
                               'check_min_windows_version') as mocked:
            mocked.return_value = is_6_3
            result = self._hostutils.get_supported_vm_types()
            self.assertEqual(expected, result)

    def test_get_supported_machine_types_older(self):
        self._test_get_supported_machine_types(False,
                                               [constants.IMAGE_PROP_VM_GEN_1])

    def test_get_supported_machine_types_63(self):
        expected = [constants.IMAGE_PROP_VM_GEN_1,
                    constants.IMAGE_PROP_VM_GEN_2]
        self._test_get_supported_machine_types(True, expected)
