#  Copyright 2014 Cloudbase Solutions Srl
#
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

import contextlib
import os

import mock

from nova import exception
from nova import test
from nova.tests.virt.hyperv import db_fakes
from nova.virt.hyperv import vmutils
from nova.virt.hyperv import volumeops

FAKE_TARGET_PORTAL = 'fakeportal:3260'
FAKE_VOLUME_ID = 'fake_volume_id'


class VolumeOpsTestCase(test.NoDBTestCase):
    """Unit tests for VolumeOps class."""

    def setUp(self):
        patched_func = mock.patch.object(volumeops.utilsfactory,
                                         "get_hostutils")
        patched_func.start()
        self.addCleanup(patched_func.stop)
        self.volumeops = volumeops.VolumeOps()
        super(VolumeOpsTestCase, self).setUp()

    def test_get_volume_driver_exception(self):
        fake_conn_info = {'driver_volume_type': 'gluster'}
        self.assertRaises(exception.VolumeDriverNotFound,
                          self.volumeops._get_volume_driver,
                          fake_conn_info)

    def test_fix_instance_volume_disk_paths(self):
        block_device_info = db_fakes.get_fake_block_device_info(
            FAKE_TARGET_PORTAL, FAKE_VOLUME_ID)
        fake_vol_conn_info = (
            block_device_info['block_device_mapping'][0]['connection_info'])

        with contextlib.nested(
            mock.patch.object(self.volumeops,
                              '_get_volume_driver'),
            mock.patch.object(self.volumeops,
                              'ebs_root_in_block_devices')
            ) as (mock_get_volume_driver,
                  mock_ebs_in_block_devices):

            fake_vol_driver = mock_get_volume_driver.return_value
            mock_ebs_in_block_devices.return_value = False

            self.volumeops.fix_instance_volume_disk_paths(
                mock.sentinel.instance_name,
                block_device_info)

            func = fake_vol_driver.fix_instance_volume_disk_path
            func.assert_called_once_with(
                mock.sentinel.instance_name,
                fake_vol_conn_info, 0)


class ISCSIVolumeDriverTestCase(test.NoDBTestCase):
    """Unit tests for Hyper-V ISCSIVolumeDriver class."""

    def setUp(self):
        patched_func = mock.patch.object(volumeops.utilsfactory,
                                         "get_hostutils")
        patched_func.start()
        self.addCleanup(patched_func.stop)
        self._volume_driver = volumeops.ISCSIVolumeDriver()
        super(ISCSIVolumeDriverTestCase, self).setUp()

    def test_get_mounted_disk_from_lun(self):
        with contextlib.nested(
            mock.patch.object(self._volume_driver._volutils,
                              'get_device_number_for_target'),
            mock.patch.object(self._volume_driver._vmutils,
                              'get_mounted_disk_by_drive_number')
            ) as (mock_get_device_number_for_target,
                  mock_get_mounted_disk_by_drive_number):

            mock_get_device_number_for_target.return_value = 0
            mock_get_mounted_disk_by_drive_number.return_value = (
                mock.sentinel.disk_path)

            disk = self._volume_driver._get_mounted_disk_from_lun(
                mock.sentinel.target_iqn,
                mock.sentinel.target_lun)
            self.assertEqual(disk, mock.sentinel.disk_path)

    def test_fix_instace_volume_disk_path(self):
        block_device_info = db_fakes.get_fake_block_device_info(
            FAKE_TARGET_PORTAL, FAKE_VOLUME_ID)
        fake_vol_conn_info = (
            block_device_info['block_device_mapping'][0]['connection_info'])

        with contextlib.nested(
            mock.patch.object(self._volume_driver,
                              '_get_mounted_disk_from_lun'),
            mock.patch.object(self._volume_driver._vmutils,
                              'get_vm_scsi_controller'),
            mock.patch.object(self._volume_driver._vmutils,
                              'set_disk_host_resource')
            ) as (mock_get_mounted_disk_from_lun,
                  mock_get_vm_scsi_controller,
                  mock_set_disk_host_resource):

            mock_get_mounted_disk_from_lun.return_value = (
                mock.sentinel.mounted_path)
            mock_get_vm_scsi_controller.return_value = (
                mock.sentinel.controller_path)

            self._volume_driver.fix_instance_volume_disk_path(
                mock.sentinel.instance_name,
                fake_vol_conn_info,
                mock.sentinel.disk_address)

            mock_get_mounted_disk_from_lun.assert_called_with(
                'iqn.2010-10.org.openstack:volume-' + FAKE_VOLUME_ID,
                1, True)
            mock_get_vm_scsi_controller.assert_called_with(
                mock.sentinel.instance_name)
            mock_set_disk_host_resource.assert_called_once_with(
                mock.sentinel.instance_name, mock.sentinel.controller_path,
                mock.sentinel.disk_address, mock.sentinel.mounted_path)

    @mock.patch('time.sleep')
    def test_get_mounted_disk_from_lun_failure(self, fake_sleep):
        self.flags(mounted_disk_query_retry_count=1, group='hyperv')

        with mock.patch.object(self._volume_driver._volutils,
                               'get_device_number_for_target') as m_device_num:
            m_device_num.side_effect = [None, -1]

            self.assertRaises(exception.NotFound,
                              self._volume_driver._get_mounted_disk_from_lun,
                              mock.sentinel.target_iqn,
                              mock.sentinel.target_lun)


class SMBFSVolumeDriverTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V SMBFSVolumeDriver class."""

    _FAKE_SHARE = '//1.2.3.4/fake_share'
    _FAKE_SHARE_NORMALIZED = _FAKE_SHARE.replace('/', '\\')
    _FAKE_DISK_NAME = 'fake_volume_name.vhdx'
    _FAKE_USERNAME = 'fake_username'
    _FAKE_PASSWORD = 'fake_password'
    _FAKE_SMB_OPTIONS = '-o username=%s,password=%s' % (_FAKE_USERNAME,
                                                        _FAKE_PASSWORD)
    _FAKE_CONNECTION_INFO = {'data': {'export': _FAKE_SHARE,
                                      'name': _FAKE_DISK_NAME,
                                      'options': _FAKE_SMB_OPTIONS}}

    def setUp(self):
        patched_func = mock.patch.object(volumeops.utilsfactory,
                                         "get_hostutils")
        patched_func.start()
        self.addCleanup(patched_func.stop)
        self._volume_driver = volumeops.SMBFSVolumeDriver()
        super(SMBFSVolumeDriverTestCase, self).setUp()

    def _test_attach_volume(self, volume_exists):
        with contextlib.nested(
            mock.patch.object(self._volume_driver,
                              '_parse_credentials'),
            mock.patch.object(self._volume_driver,
                              'ensure_share_mounted'),
            mock.patch.object(self._volume_driver,
                              '_get_disk_path'),
            mock.patch.object(self._volume_driver._vmutils,
                              'get_vm_scsi_controller'),
            mock.patch.object(self._volume_driver._vmutils,
                              'get_free_controller_slot'),
            mock.patch.object(self._volume_driver._vmutils,
                              'attach_drive'),
            ) as (mock_parse_credentials,
                  mock_ensure_share_mounted,
                  mock_get_disk_path,
                  mock_get_vm_scsi_controller,
                  mock_get_free_controller_slot,
                  mock_attach_drive):

            mock_parse_credentials.return_value = (
                self._FAKE_USERNAME, self._FAKE_PASSWORD)
            mock_get_vm_scsi_controller.return_value = (
                mock.sentinel.controller_path)
            mock_get_free_controller_slot.return_value = (
                mock.sentinel.controller_slot)
            mock_get_disk_path.return_value = (
                mock.sentinel.disk_path)

            if volume_exists:
                self._volume_driver.attach_volume(
                    self._FAKE_CONNECTION_INFO,
                    mock.sentinel.instance_name)

                mock_ensure_share_mounted.assert_called_with(
                    self._FAKE_CONNECTION_INFO)
                mock_get_disk_path.assert_called_with(
                    self._FAKE_CONNECTION_INFO)
                mock_get_vm_scsi_controller.assert_called_with(
                    mock.sentinel.instance_name)
                mock_get_free_controller_slot.assert_called_with(
                    mock.sentinel.controller_path)
                mock_attach_drive.assert_called_with(
                    mock.sentinel.instance_name, mock.sentinel.disk_path,
                    mock.sentinel.controller_path,
                    mock.sentinel.controller_slot)
            else:
                mock_attach_drive.side_effect = (
                    vmutils.HyperVException())
                self.assertRaises(vmutils.HyperVException,
                                  self._volume_driver.attach_volume,
                                  self._FAKE_CONNECTION_INFO,
                                  mock.sentinel.instance_name)

    def test_attach_volume_volume_exists(self):
        self._test_attach_volume(volume_exists=True)

    def test_attach_non_existing_volume(self):
        self._test_attach_volume(volume_exists=False)

    def test_detach_volume(self):
        with contextlib.nested(
            mock.patch.object(self._volume_driver,
                              '_get_disk_path'),
            mock.patch.object(self._volume_driver._vmutils,
                              'detach_vm_disk'),
            ) as (mock_get_disk_path,
                  mock_detach_vm_disk):

            mock_get_disk_path.return_value = (
                mock.sentinel.disk_path)

            self._volume_driver.detach_volume(self._FAKE_CONNECTION_INFO,
                                              mock.sentinel.instance_name)

            mock_detach_vm_disk.assert_called_once_with(
                mock.sentinel.instance_name, mock.sentinel.disk_path,
                is_physical=False)

    def test_parse_credentials(self):
        username, password = self._volume_driver._parse_credentials(
            self._FAKE_SMB_OPTIONS)
        self.assertEqual(self._FAKE_USERNAME, username)
        self.assertEqual(self._FAKE_PASSWORD, password)

    def test_get_disk_path(self):
        expected = os.path.join(self._FAKE_SHARE_NORMALIZED,
                                self._FAKE_DISK_NAME)

        disk_path = self._volume_driver._get_disk_path(
            self._FAKE_CONNECTION_INFO)

        self.assertEqual(expected, disk_path)

    def _test_ensure_mounted(self, is_mounted):
        with contextlib.nested(
            mock.patch.object(self._volume_driver._pathutils,
                              'check_smb_mapping'),
            mock.patch.object(self._volume_driver._pathutils,
                              'mount_smb_share'),
            mock.patch.object(self._volume_driver,
                              '_parse_credentials')
            ) as (mock_check_smb_mapping,
                  mock_mount_smb_share,
                  mock_parse_credentials):

            mock_check_smb_mapping.return_value = is_mounted
            mock_parse_credentials.return_value = (
                self._FAKE_USERNAME, self._FAKE_PASSWORD)

            self._volume_driver.ensure_share_mounted(
                self._FAKE_CONNECTION_INFO)

            if is_mounted:
                self.assertFalse(
                    mock_mount_smb_share.call_count)
            else:
                mock_mount_smb_share.assert_called_once_with(
                    self._FAKE_SHARE_NORMALIZED,
                    username=self._FAKE_USERNAME,
                    password=self._FAKE_PASSWORD)

    def test_ensure_already_mounted(self):
        self._test_ensure_mounted(is_mounted=True)

    def test_ensure_mounted_new_share(self):
        self._test_ensure_mounted(is_mounted=False)
