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
from nova.virt.hyperv import utilsfactory
from nova.virt.hyperv import vmutils


class UtilsFactoryTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V utilsfactory module."""

    @mock.patch.object(utilsfactory, "get_hostutils")
    def test_get_vmutils_2008(self, mock_get_hostutils):
        mock_hostutils = mock_get_hostutils.return_value
        mock_hostutils.check_min_windows_version.return_value = False

        actual_vmutils = utilsfactory.get_vmutils()

        self.assertEqual(vmutils.VMUtils2008, type(actual_vmutils))

    @mock.patch.object(utilsfactory, "_get_class")
    @mock.patch.object(utilsfactory, "get_hostutils")
    def test_get_vmutils_200(self, mock_get_hostutils, mock_get_class):
        mock_get_class.return_value = vmutils.VMUtils
        actual_vmutils = utilsfactory.get_vmutils()

        self.assertEqual(vmutils.VMUtils, type(actual_vmutils))
