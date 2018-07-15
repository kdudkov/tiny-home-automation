import asyncio
import logging
import math

from astral import Location

from actors import AbstractActor

LOG = logging.getLogger('mahno.' + __name__)

radians = lambda x: x * math.pi / 180
deg = lambda x: x * 180 / math.pi


class AstroActor(AbstractActor):
    name = 'astro'

    def init(self, config, context):
        self.config = config
        self.context = context
        coords = self.config.get('coords', {'lat': 59.5, 'lon': 30.19})
        self.lat = coords['lat']
        self.lon = coords['lon']
        self.alt = coords.get('alt', 0)

    @asyncio.coroutine
    def loop(self):
        while self.running:
            try:
                self.compute()
            except:
                LOG.exception('')
            yield from asyncio.sleep(300)

    def compute(self):
        location = Location(('name', 'reg', self.lat, self.lon, 'Europe/Moscow', self.alt))

        # 15' sun bottom + 35' refraction
        alt = location.solar_elevation()
        daytime = 'day'
        daytime_ext = 'day'
        if -6 <= alt < -5. / 6:
            daytime = 'twilight'
            daytime_ext = 'civil_twilight'
        elif -12 <= alt < -6:
            daytime = 'night'
            daytime_ext = 'nautical_twilight'
        elif -18 <= alt < -12:
            daytime = 'night'
            daytime_ext = 'astro_twilight'
        elif alt < -18:
            daytime = 'night'
            daytime_ext = 'night'

        self.context.set_item_value('daytime', daytime)
        self.context.set_item_value('daytime_ext', daytime_ext)
        self.context.set_item_value('sun_alt', alt)
        self.context.set_item_value('sun_az', location.solar_azimuth())

        sun = location.sun()
        self.context.set_item_value('sunrise', sun['sunrise'])
        self.context.set_item_value('sunset', sun['sunset'])
        self.context.set_item_value('noon', sun['noon'])

        self.context.set_item_value('moon_phase', location.moon_phase())
