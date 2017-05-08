import asyncio
import logging

from core.items import ON, OFF
from . import abstract

LOG = logging.getLogger(__name__)


class NightModeRule(abstract.Rule):
    on_change = ['light_room']

    @asyncio.coroutine
    def process(self, name, old_val, val):
        if val == OFF and self.time_between('22:00', '3:00'):
            self.post_update('home_mode', 'night')

        if val == ON and self.get_val_or_none('home_mode') == 'night':
            self.post_update('home_mode', 'day')


class BtnRule(abstract.Rule):
    on_change = ['light_room_btn']

    @asyncio.coroutine
    def process(self, name, old_val, val):
        v = self.get_val_or_none('light_room')
        self.item_command('light_room', ON if v == OFF else OFF)


class NightCorridorRule(abstract.Rule):
    on_change = ['light_corridor']

    @asyncio.coroutine
    def process(self, name, old_val, val):
        if val == OFF and self.time_between('22:00', '4:00'):
            self.item_command('light_corridor_night', ON)

        if val == ON:
            self.command('light_corridor_night', OFF)
            if self.time_between('6:00', '13:00') and self.get_val_or_none('home_mode') == 'night':
                self.post_update('home_mode', 'day')


class NightMode(abstract.Rule):
    on_change = ['home_mode']

    @asyncio.coroutine
    def process(self, name, old_val, val):
        if val == 'night':
            self.item_command('light_room', OFF)
            self.item_command('light_corridor', OFF)
            self.item_command('light_corridor_night', ON)
            self.item_command('room_thermostat', ON)
