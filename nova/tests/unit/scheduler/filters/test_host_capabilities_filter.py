# Copyright 2015 Cloudbase Solutions Srl
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

from nova.scheduler.filters import host_capabilities_filter
from nova import test
from nova.tests.unit.scheduler import fakes


class TestHostCapabilitiesFilter(test.NoDBTestCase):

    def setUp(self):
        super(TestHostCapabilitiesFilter, self).setUp()
        self.filt_cls = host_capabilities_filter.HostCapabilitiesFilter()

    def test_host_capabilities_passes_with_matching_prop(self):
        img_props = {'properties': {'hw_property': 'required'}}
        filter_properties = {'request_spec': {'image': img_props}}

        capabilities = {'capabilities': {'hw_property': 'required'}}
        host = fakes.FakeHostState('host1', 'node1', capabilities)
        self.assertTrue(self.filt_cls.host_passes(host, filter_properties))

    def test_host_capabilities_fails_with_unmatching_prop(self):
        img_props = {'properties': {'hw_property': 'required'}}
        filter_properties = {'request_spec': {'image': img_props}}

        capabilities = {'capabilities': {'hw_property': 'other'}}
        host = fakes.FakeHostState('host1', 'node1', capabilities)
        self.assertFalse(self.filt_cls.host_passes(host, filter_properties))

    def test_host_capabilities_passes_with_found_in_list_prop(self):
        img_props = {'properties': {'hw_property': 'required'}}
        filter_properties = {'request_spec': {'image': img_props}}

        capabilities = {'capabilities': {'hw_property': ['required']}}
        host = fakes.FakeHostState('host1', 'node1', capabilities)
        self.assertTrue(self.filt_cls.host_passes(host, filter_properties))

    def test_host_capabilities_fails_with_missing_in_list_prop(self):
        img_props = {'properties': {'hw_property': 'required'}}
        filter_properties = {'request_spec': {'image': img_props}}

        capabilities = {'capabilities': {'hw_property': ['other']}}
        host = fakes.FakeHostState('host1', 'node1', capabilities)
        self.assertFalse(self.filt_cls.host_passes(host, filter_properties))
