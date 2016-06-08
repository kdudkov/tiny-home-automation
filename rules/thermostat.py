import asyncio
import logging
import time

from . import abstract

LOG = logging.getLogger(__name__)


class Thermostat(abstract.Rule):
    timeout = 90

    def __init__(self, switch_item, temp_item, thermostat_item, actor_item, is_cooler=False, gist=1):
        self.on_change = [switch_item, temp_item, thermostat_item]
        self.switch_item = switch_item
        self.temp_item = temp_item
        self.thermostat_item = thermostat_item
        self.actor_item = actor_item
        self.is_cooler = is_cooler
        self.gist = float(gist)
        self.last_switch = 0

    @asyncio.coroutine
    def process(self, name, old_val, val):
        if self.get_val_or_none(self.switch_item) != 'On':
            return

        t = self.get_val_or_none(self.temp_item)
        t_d = self.get_val_or_none(self.thermostat_item)

        if t is None or t_d is None:
            LOG.error('emergency: temp sensor %s or thermostat %s value is None', self.temp_item, self.thermostat_item)
            self.command(self.actor_item, 'Off')
            return

        if time.time() - self.last_switch < self.timeout:
            # do not switch too fast
            return

        LOG.debug('temp %s, target %s, switch %s', t, t_d, self.get_val_or_none(self.actor_item))
        if t >= t_d + self.gist / 2:
            target_sw = 'On' if self.is_cooler else 'Off'
            if self.get_val_or_none(self.actor_item) != target_sw:
                self.last_switch = time.time()
                LOG.info('too hot (%s), setting %s to %s', t, self.actor_item, target_sw)
                self.command(self.actor_item, target_sw)

        if t <= t_d - self.gist / 2:
            target_sw = 'Off' if self.is_cooler else 'On'
            if self.get_val_or_none(self.actor_item) != target_sw:
                self.last_switch = time.time()
                LOG.info('too cold (%s), setting %s to %s', t, self.actor_item, target_sw)
                self.command(self.actor_item, target_sw)
