# Copyright 2018 Cloudbase Solutions Srl
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

from nova.compute import power_state
from nova.conductor.tasks import base
from nova import exception
from nova import objects


class LiveResizeTask(base.TaskBase):

    def __init__(self, context, instance, flavor, image, reservations,
                 compute_rpcapi):
        super(LiveResizeTask, self).__init__(context, instance)
        self.flavor = flavor
        self.image = image
        self.reservations = reservations
        self.compute_rpcapi = compute_rpcapi
        self.quotas = None

    def _execute(self):
        self._check_instance_is_active()

        self.quotas = objects.Quotas.from_reservations(self.context,
                                                       self.reservations,
                                                       instance=self.instance)

        self.compute_rpcapi.live_resize_instance(
            self.context, self.instance, self.flavor, self.image,
            self.reservations)

    def _check_instance_is_active(self):
        if self.instance.power_state not in (power_state.RUNNING,
                                             power_state.PAUSED):
            raise exception.InstanceInvalidState(
                instance_uuid=self.instance.uuid,
                attr='power_state',
                state=self.instance.power_state,
                method='live resize')

    def rollback(self):
        if self.quotas:
            self.quotas.rollback()
