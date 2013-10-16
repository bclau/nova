# vim: tabstop=4 shiftwidth=4 softtabstop=4

#  Copyright 2013 Cloudbase Solutions Srl
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
from nova.virt.hyperv import networkutils
from nova.virt.hyperv import vmutils


class NetworkUtilsTestCase(test.NoDBTestCase):
    """Unit tests for the Hyper-V NetworkUtils class."""

    _FAKE_VSWITCH_NAME = "fake_vswitch_name"
    _FAKE_VSWITCH_PATH = "fake_vswitch_path"
    _FAKE_PORT_NAME = "fake_port_name"
    _FAKE_PORT = {'Name': "fake_port_name"}
    _FAKE_RET_VALUE = 0

    _MSVM_VIRTUAL_SWITCH = 'Msvm_VirtualSwitch'

    def setUp(self):
        self._networkutils = networkutils.NetworkUtils()
        self._networkutils._conn = mock.MagicMock()

        super(NetworkUtilsTestCase, self).setUp()

    def test_get_external_vswitch(self):
        mock_vswitch = mock.MagicMock()
        mock_vswitch.path_.return_value = self._FAKE_VSWITCH_PATH
        getattr(self._networkutils._conn,
                self._MSVM_VIRTUAL_SWITCH).return_value = [mock_vswitch]

        switch_path = self._networkutils.get_external_vswitch(
            self._FAKE_VSWITCH_NAME)

        self.assertEqual(self._FAKE_VSWITCH_PATH, switch_path)

    def test_get_external_vswitch_not_found(self):
        self._networkutils._conn.Msvm_VirtualEthernetSwitch.return_value = []

        self.assertRaises(vmutils.HyperVException,
                          self._networkutils.get_external_vswitch,
                          self._FAKE_VSWITCH_NAME)

    def test_get_external_vswitch_no_name(self):
        mock_vswitch = mock.MagicMock()
        mock_vswitch.path_.return_value = self._FAKE_VSWITCH_PATH

        mock_ext_port = self._networkutils._conn.Msvm_ExternalEthernetPort()[0]
        self._prepare_external_port(mock_vswitch, mock_ext_port)

        switch_path = self._networkutils.get_external_vswitch(None)
        self.assertEqual(self._FAKE_VSWITCH_PATH, switch_path)

    def _prepare_external_port(self, mock_vswitch, mock_ext_port):
        mock_lep = mock_ext_port.associators()[0]
        mock_lep.associators.return_value = [mock_vswitch]

    def test_create_vswitch_port(self):
        svc = self._networkutils._conn.Msvm_VirtualSwitchManagementService()[0]
        svc.CreateSwitchPort.return_value = (
            self._FAKE_PORT, self._FAKE_RET_VALUE)

        port = self._networkutils.create_vswitch_port(self._FAKE_VSWITCH_PATH,
                                                      self._FAKE_PORT_NAME)
        self.assertEqual(self._FAKE_PORT, port)

    def test_vswitch_port_needed(self):
        self.assertTrue(self._networkutils.vswitch_port_needed())
