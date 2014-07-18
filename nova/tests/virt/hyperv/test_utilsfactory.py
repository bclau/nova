# Copyright 2014 Cloudbase Solutions SRL
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

"""
Unit tests for the Hyper-V utils factory.
"""

import mock

from oslo.config import cfg

from nova import test
from nova.virt.hyperv import hostutils
from nova.virt.hyperv import utilsfactory
from nova.virt.hyperv import vmutils
from nova.virt.hyperv import vmutilsv2

CONF = cfg.CONF


class TestHyperVUtilsFactory(test.NoDBTestCase):

    def setUp(self):
        super(TestHyperVUtilsFactory, self).setUp()

    def test_get_vmutils_v2_r2(self):
        self._test_returned_class(vmutilsv2.VMUtilsV2, True, '6.3.0')

    def test_get_vmutils_v2(self):
        self._test_returned_class(vmutilsv2.VMUtilsV2, False, '6.2.0')

    def test_get_vmutils_v1_old_version(self):
        self._test_returned_class(vmutils.VMUtils, False, '6.1.0')

    def test_get_vmutils_v1_forced(self):
        self._test_returned_class(vmutils.VMUtils, True, '6.2.0')

    def _test_returned_class(self, expected_class, force_v1, os_version):
        CONF.hyperv.force_hyperv_utils_v1 = force_v1
        with mock.patch.object(hostutils.HostUtils,
                               'get_windows_version') as mock_get_win_version:
            mock_get_win_version.return_value = os_version

            actual_class = type(utilsfactory.get_vmutils())
            self.assertEqual(actual_class, expected_class)
