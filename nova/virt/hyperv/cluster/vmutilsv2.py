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
Utility class for Cluster VM related operations.
"""

from oslo.config import cfg

from nova.virt.hyperv import vmutilsv2

CONF = cfg.CONF


class ClusterVMUtilsV2(vmutilsv2.VMUtilsV2):

    def _create_vm_obj(self, vs_man_svc, vm_name, notes):
        vs_data = self._conn.Msvm_VirtualSystemSettingData.new()
        vs_data.ElementName = vm_name
        vs_data.Notes = notes
        # Don't start automatically on host boot
        vs_data.AutomaticStartupAction = self._AUTOMATIC_STARTUP_ACTION_NONE

        # Created VMs must have their ConfigurationDataRoot, SnapshotDataRoot
        # and SwapFileDataRoot in the same place as the instances' path.
        vs_data.ConfigurationDataRoot = CONF.instances_path
        vs_data.SnapshotDataRoot = CONF.instances_path
        vs_data.SwapFileDataRoot = CONF.instances_path

        (job_path,
         vm_path,
         ret_val) = vs_man_svc.DefineSystem(ResourceSettings=[],
                                            ReferenceConfiguration=None,
                                            SystemSettings=vs_data.GetText_(1))
        job = self.check_ret_val(ret_val, job_path)
        if not vm_path and job:
            vm_path = job.associators(self._AFFECTED_JOB_ELEMENT_CLASS)[0]
        return self._get_wmi_obj(vm_path)
