import asyncio
import logging

import time

from core.items import ON, OFF
from . import abstract

LOG = logging.getLogger(__name__)


class AbstractThermostat(abstract.Rule):
    timeout = 90

    def __init__(self, switch_item, sensor_item, thermostat_item, actor_item, is_cooler=False, gist=1):
        self.on_change = [switch_item, sensor_item, thermostat_item]
        self.switch_item = switch_item
        self.sensor_item = sensor_item
        self.thermostat_item = thermostat_item
        self.actor_item = actor_item
        self.is_cooler = bool(is_cooler)
        self.gist = float(gist)
        self.last_switch = 0

    @asyncio.coroutine
    def process(self, name, old_val, val):
        if self.get_val_or_none(self.switch_item) != ON:
            return

        t = self.get_val_or_none(self.sensor_item)
        t_d = self.get_val_or_none(self.thermostat_item)

        if t is None or t_d is None:
            LOG.error('emergency: temp sensor %s or thermostat %s value is None', self.sensor_item, self.thermostat_item)
            self.item_command(self.actor_item, OFF)
            return

        if time.time() - self.last_switch < self.timeout:
            # do not switch too fast
            return

        LOG.debug('temp %s, target %s, switch %s', t, t_d, self.get_val_or_none(self.actor_item))

        target_sw = None

        if t >= t_d + self.gist / 2:
            target_sw = ON if self.is_cooler else OFF
        elif t <= t_d - self.gist / 2:
            target_sw = OFF if self.is_cooler else ON

        if target_sw is not None and self.get_val_or_none(self.actor_item) != target_sw:
            self.last_switch = time.time()
            LOG.info('value is %s, range is %s - %s, setting %s to %s', t, t_d - self.gist / 2, t_d + self.gist / 2,
                     self.actor_item, target_sw)
            self.item_command(self.actor_item, target_sw)

class RoomThermostat(AbstractThermostat):
    def __init__(self):
        AbstractThermostat.__init__(self, 'room_thermostat_switch', 'room_temp_pi', 'room_thermostat', 'kankun_switch',
                                    False)
