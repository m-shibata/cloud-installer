# Copyright 2014 Canonical, Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import logging

from macumba import MacumbaError
from cloudinstall.charms import CharmBase, DisplayPriorities

log = logging.getLogger('cloudinstall.charms.ceph')


class CharmCeph(CharmBase):
    """ Ceph directives """

    charm_name = 'ceph'
    display_name = 'Ceph'
    menuable = True
    display_priority = DisplayPriorities.Storage
    related = ['glance', 'mysql', 'rabbitmq-server']
    deploy_priority = 5
    default_instances = 3
    optional = True
    disabled = False
    allow_multi_units = True

    def has_quorum(self):
        return len(self.juju_state.machines_allocated()) >= 3

    def setup(self):
        """ Custom setup for ceph """
        if not self.has_quorum():
            log.debug("Insufficient machines allocated - ceph can't deploy.")
            return True
        if not self.is_multi:
            log.debug("Ceph not currently supported on single installs")
            return True
        try:
            self.juju.deploy(charm=self.charm_name,
                             service_name=self.charm_name,
                             num_units=self.default_instances)
        except MacumbaError:
            log.exception("Error deploying")
            return True
        return False


__charm_class__ = CharmCeph
