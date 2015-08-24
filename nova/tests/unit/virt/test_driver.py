# Copyright (c) 2013 Citrix Systems, Inc.
# Copyright 2013 OpenStack Foundation
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
from oslo_config import fixture as fixture_config

from nova import test
from nova.virt import driver


class DriverMethodTestCase(test.NoDBTestCase):

    def setUp(self):
        super(DriverMethodTestCase, self).setUp()
        self.CONF = self.useFixture(fixture_config.Config()).conf

    def test_is_xenapi_true(self):
        self.CONF.set_override('compute_driver', 'xenapi.XenAPIDriver',
                               enforce_type=True)
        self.assertTrue(driver.is_xenapi())

    def test_is_xenapi_false(self):
        driver_names = ('libvirt.LibvirtDriver', 'fake.FakeDriver',
                        'ironic.IronicDriver', 'vmwareapi.VMwareVCDriver',
                        'hyperv.HyperVDriver', None)
        for driver_name in driver_names:
            self.CONF.set_override('compute_driver', driver_name,
                                   enforce_type=True)
            self.assertFalse(driver.is_xenapi())


class DriverTestCase(test.NoDBTestCase):

    def setUp(self):
        super(DriverTestCase, self).setUp()
        self.driver = driver.ComputeDriver(virtapi=mock.Mock())

    def test_live_migration_cleanup_flags(self):
        do_cleanup, destroy_disks = self.driver.live_migration_cleanup_flags(
            mock.sentinel.migrate_data)
        self.assertFalse(do_cleanup)
        self.assertFalse(destroy_disks)
