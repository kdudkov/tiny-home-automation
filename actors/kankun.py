#!/usr/bin/env python3

import asyncio
import logging

import aiohttp

from . import AbstractActor

LOG = logging.getLogger('mahno.' + __name__)


class Kankun(object):
    timeout = 3

    def __init__(self, addr, loop):
        self.addr = addr
        self.loop = loop
        self.session = None

    def init(self):
        self.session = aiohttp.ClientSession(loop=self.loop)

    async def stop(self):
        if self.session:
            try:
                await self.session.close()
            except:
                pass

    async def req(self, params=None):
        p = {}
        if params:
            p.update(params)

        resp = await self.session.get('http://%s/cgi-bin/json.cgi' % self.addr, params=p, timeout=self.timeout)

        if resp.status != 200:
            raise Exception('http %s' % resp.status)
        try:
            res = await resp.json()
            return res
        finally:
            await resp.release()

    async def get_serial(self, name):
        res = await self.req('VideoLibrary.GetTVShows')
        for r in res.get('tvshows', []):
            if name in r.get('label'):
                return r

    async def post_command(self, c):
        cmd = ['off', 'on'][str(c).lower() in ('on', 'true', '1')]
        await self.req({'set': cmd})


class KankunActor(AbstractActor):
    name = 'kankun'

    def __init__(self, name, addr):
        self.name = name
        self.addr = addr
        self.switch = None

    def init(self, config, context):
        self.config = config
        self.context = context
        self.switch = Kankun(self.addr, self.context.loop)
        self.switch.init()

    async def loop(self):
        while self.running:
            res = None
            try:
                res = await self.switch.req({'get': 'state'})
            except asyncio.TimeoutError:
                LOG.error('timeout talking to %s', self.addr)
            except Exception as e:
                LOG.exception('loop')
            if res:
                for item in self.context.items:
                    if item.input == 'kankun:%s' % self.name:
                        self.context.set_item_value(item.name, res['state'])
            await asyncio.sleep(10)

        LOG.info('kankun %s stopped', self.name)
        await self.switch.stop()

    async def command(self, args):
        await self.switch.post_command(args)
