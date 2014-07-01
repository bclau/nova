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
"""
Image caching and management.
"""
import mock

from nova import test
from nova.virt.hyperv import constants
from nova.virt.hyperv import imagecache


class ImageCacheTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V ImageCache class."""

    _FAKE_ROOT_VHD_PATH = 'Fake root'
    _FAKE_CONTEXT = 'Fake context'
    _FAKE_INSTANCE = 'Fake instance'

    def setUp(self):
        super(ImageCacheTestCase, self).setUp()
        self._imagecache = imagecache.ImageCache()

    def _test_get_image_vm_generation(self, mock_get_image_details, vm_gen,
                                      expected_vm_gen):
        image_meta = {"properties": {imagecache.IMAGE_PROP_VM_GEN: vm_gen}}
        mock_get_image_details.return_value = image_meta

        response = self._imagecache.get_image_vm_generation(
            self._FAKE_ROOT_VHD_PATH,
            self._FAKE_CONTEXT,
            self._FAKE_INSTANCE)

        mock_get_image_details.assert_called_once_with(self._FAKE_CONTEXT,
                                                       self._FAKE_INSTANCE)
        self.assertEquals(response, expected_vm_gen)

    @mock.patch("nova.virt.hyperv.imagecache.ImageCache.get_image_details")
    def test_get_image_vm_generation_1(self, mock_get_image_details):
        self._test_get_image_vm_generation(mock_get_image_details,
                                           "hyperv-gen1", constants.VM_GEN_1)

    @mock.patch("nova.virt.hyperv.hostutils.HostUtils."
                "check_min_windows_version")
    @mock.patch("nova.virt.hyperv.imagecache.ImageCache.get_image_details")
    def test_get_image_vm_generation_2(self, mock_get_image_details,
                                       mock_check_min_windows_version):
        mock_check_min_windows_version.return_value = False
        self._test_get_image_vm_generation(mock_get_image_details,
                                           "hyperv-gen2", constants.VM_GEN_1)

    @mock.patch("nova.virt.hyperv.vhdutils.VHDUtils.get_vhd_format")
    @mock.patch("nova.virt.hyperv.hostutils.HostUtils."
                "check_min_windows_version")
    @mock.patch("nova.virt.hyperv.imagecache.ImageCache.get_image_details")
    def test_get_image_vm_generation_2_vhd(self, mock_get_image_details,
                                           mock_check_min_windows_version,
                                           mock_get_vhd_format):
        mock_check_min_windows_version.return_value = True
        mock_get_vhd_format.return_value = constants.DISK_FORMAT_VHD
        self._test_get_image_vm_generation(mock_get_image_details,
                                           "hyperv-gen2", constants.VM_GEN_1)

    @mock.patch("nova.virt.hyperv.vhdutils.VHDUtils.get_vhd_format")
    @mock.patch("nova.virt.hyperv.hostutils.HostUtils."
                "check_min_windows_version")
    @mock.patch("nova.virt.hyperv.imagecache.ImageCache.get_image_details")
    def test_get_image_vm_generation_2_vhdx(self, mock_get_image_details,
                                            mock_check_min_windows_version,
                                            mock_get_vhd_format):
        mock_check_min_windows_version.return_value = True
        mock_get_vhd_format.return_value = constants.DISK_FORMAT_VHDX
        self._test_get_image_vm_generation(mock_get_image_details,
                                           "hyperv-gen2", constants.VM_GEN_2)
