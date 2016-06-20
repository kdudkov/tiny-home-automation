import asyncio
import logging
import math

from actors import AbstractActor
from astral import Astral, Location

LOG = logging.getLogger(__name__)

radians = lambda x: x * math.pi / 180
deg = lambda x: x * 180 / math.pi


class AstroActor(AbstractActor):

    def init(self, config, context):
        self.config = config
        self.context = context
        coords = self.config.get('coords', {'lat': 59.5, 'lon': 30.19})
        self.lat = coords['lat']
        self.lon = coords['lon']

    @asyncio.coroutine
    def loop(self):
        while self.running:
            try:
                self.compute()
            except:
                LOG.exception('')
            yield from asyncio.sleep(300)

    def compute(self):
        ast = Astral()
        l = Location(('name', 'reg', self.lat, self.lon, 'Europe/Moscow', 0))

        alt = l.solar_elevation()

        sun = l.sun()

        daytime = 'day'
        if alt < -6:
            daytime = 'night'
        elif -6 <= alt <= 0:
            daytime = 'twilight'
        self.context.set_item_value('daytime', daytime)
        self.context.set_item_value('sun_alt', alt)
        self.context.set_item_value('sun_az', l.solar_azimuth())

        self.context.set_item_value('sunrise', sun['sunrise'])
        self.context.set_item_value('sunset', sun['sunset'])
        self.context.set_item_value('noon', sun['noon'])

        self.context.set_item_value('moon_phase', l.moon_phase())
