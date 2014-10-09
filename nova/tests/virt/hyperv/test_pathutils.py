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

import os

import mock

from nova import test
from nova.virt.hyperv import constants
from nova.virt.hyperv import pathutils


class PathUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V PathUtils class."""

    def setUp(self):
        self.fake_instance_dir = os.path.join('C:', 'fake_instance_dir')
        self.fake_instance_name = 'fake_instance_name'

        pathutils.PathUtils.__init__ = lambda x: None
        self._pathutils = pathutils.PathUtils()
        self._pathutils.smb_conn = mock.MagicMock()
        super(PathUtilsTestCase, self).setUp()

    def _mock_lookup_configdrive_path(self, ext):
        self._pathutils.get_instance_dir = mock.MagicMock(
            return_value=self.fake_instance_dir)

        def mock_exists(*args, **kwargs):
            path = args[0]
            return True if path[(path.rfind('.') + 1):] == ext else False
        self._pathutils.exists = mock_exists
        configdrive_path = self._pathutils.lookup_configdrive_path(
            self.fake_instance_name)
        return configdrive_path

    def test_lookup_configdrive_path(self):
        for format_ext in constants.DISK_FORMAT_MAP:
            configdrive_path = self._mock_lookup_configdrive_path(format_ext)
            fake_path = os.path.join(self.fake_instance_dir,
                                     'configdrive.' + format_ext)
            self.assertEqual(configdrive_path, fake_path)

    def test_lookup_configdrive_path_non_exist(self):
        self._pathutils.get_instance_dir = mock.MagicMock(
            return_value=self.fake_instance_dir)
        self._pathutils.exists = mock.MagicMock(return_value=False)
        configdrive_path = self._pathutils.lookup_configdrive_path(
            self.fake_instance_name)
        self.assertIsNone(configdrive_path)

    def _test_check_smb_mapping(self, existing_mappings=False,
                                share_available=False):
        with mock.patch('os.path.exists', lambda x: share_available):
            fake_mapping = mock.MagicMock()
            if existing_mappings:
                fake_mappings = [fake_mapping]
            else:
                fake_mappings = []

            self._pathutils.smb_conn.query.return_value = fake_mappings
            ret_val = self._pathutils.check_smb_mapping(
                mock.sentinel.share_path)

            if existing_mappings:
                if share_available:
                    self.assertTrue(ret_val)
                else:
                    fake_mapping.Remove.assert_called_once_with(True, True)
            else:
                self.assertFalse(ret_val)

    def test_check_mapping(self):
        self._test_check_smb_mapping()

    def test_remake_unavailable_mapping(self):
        self._test_check_smb_mapping(True, False)

    def test_available_mapping(self):
        self._test_check_smb_mapping(True, True)

    def test_mount_smb(self):
        fake_create = self._pathutils.smb_conn.Msft_SmbMapping.Create
        self._pathutils.mount_smb_share(mock.sentinel.share_path,
                                        mock.sentinel.username,
                                        mock.sentinel.password)
        fake_create.assert_called_once_with(
            RemotePath=mock.sentinel.share_path,
            UserName=mock.sentinel.username,
            Password=mock.sentinel.password)
