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
from cloudinstall.charms import (CharmBase, CHARM_CONFIG,
                                 CHARM_CONFIG_RAW,
                                 DisplayPriorities)

log = logging.getLogger('cloudinstall.charms.compute')


class CharmSwift(CharmBase):
    """ swift directives """

    charm_name = 'swift-storage'
    display_name = 'Swift'
    menuable = True
    display_priority = DisplayPriorities.Storage
    related = ['swift-proxy']
    deploy_priority = 5
    default_replicas = 3
    isolate = True
    optional = True
    allow_multi_units = True

    def setup(self):
        """Custom setup for swift-storage to get replicas from config"""
        if 'swift-proxy' in CHARM_CONFIG:
            num_replicas = CHARM_CONFIG.get('replicas',
                                            self.default_replicas)
        else:
            num_replicas = self.default_replicas

        log.debug('Deployed {c}'.format(
            c=self.charm_name))
        try:
            self.juju.deploy(charm=self.charm_name,
                             service_name=self.charm_name,
                             num_units=num_replicas,
                             config_yaml=CHARM_CONFIG_RAW)
        except MacumbaError:
            log.exception("Error during deploy")
            return True
        return False

    def post_proc(self):
        self.juju.set_config('glance-simplestreams-sync',
                             {'use_swift': True})

__charm_class__ = CharmSwift
