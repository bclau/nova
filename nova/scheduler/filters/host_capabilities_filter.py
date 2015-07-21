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

from oslo_log import log as logging

from nova.scheduler import filters

LOG = logging.getLogger(__name__)


class HostCapabilitiesFilter(filters.BaseHostFilter):
    """Filter compute nodes with capabilities that satisfy instance image
    properties.

    """

    # Image Properties do not change within a request.
    run_filter_once_per_request = True

    def _satisfies_extra_features(self, host_state, image_properties):
        """Checks that the host_state provided by the compute service
        satisfies the capabilities requirements associated with the
        image_properties.
        TODO: check flavor as well.
        """

        for key, required in image_properties.iteritems():
            # expected format: os_property or hw_property
            keys = key.split('_')
            if len(keys) <= 1 and keys[0] not in ['hw', 'os']:
                # skip this property.
                continue

            compute_node_capability = host_state.capabilities.get(key, None)
            if not compute_node_capability:
                return False

            if isinstance(compute_node_capability, list):
                if required not in compute_node_capability:
                    return False
            else:
                if required != compute_node_capability:
                    return False
        return True

    def host_passes(self, host_state, filter_properties):
        """Returns True if the host_state provided has the required extra
        features required by the instance, False otherwise.
        """

        request_spec = filter_properties['request_spec']
        image = request_spec.get('image', None)
        if not image:
            # no image required for the instance
            return True

        image_properties = image.get('properties', None)
        if not image_properties:
            # no extra requirements for the instance.
            return True

        if not self._satisfies_extra_features(host_state,
                                              image_properties):
            LOG.debug('%(host_state)s fails request_spec host capabilities '
                      'requirements.', {'host_state': host_state})
            return False
        return True
