# Copyright (c) 2015 Cloudbase Solutions SRL
# All Rights Reserved
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

from sqlalchemy import MetaData, Column, Table
from sqlalchemy import Text


def upgrade(migrate_engine):
    """Function adds compute_nodes capabilities field."""
    meta = MetaData(bind=migrate_engine)
    compute_nodes = Table('compute_nodes', meta, autoload=True)
    shadow_compute_nodes = Table('shadow_compute_nodes', meta, autoload=True)

    capabilities = Column('capabilities', Text, nullable=True)

    if not hasattr(compute_nodes.c, 'capabilities'):
        compute_nodes.create_column(capabilities)

    if not hasattr(shadow_compute_nodes.c, 'capabilities'):
        shadow_compute_nodes.create_column(capabilities.copy())
