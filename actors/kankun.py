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

        self.session = aiohttp.ClientSession(loop=self.loop)

    @asyncio.coroutine
    def req(self, params=None):
        p = {}
        if params:
            p.update(params)

        resp = yield from self.session.get('http://%s/cgi-bin/json.cgi' % self.addr, params=p, timeout=self.timeout)

        if resp.status != 200:
            raise Exception('http %s' % resp.status)
        try:
            res = yield from resp.json()
            return res
        finally:
            yield from resp.release()

    @asyncio.coroutine
    def get_serial(self, name):
        res = yield from self.req('VideoLibrary.GetTVShows')
        for r in res.get('tvshows', []):
            if name in r.get('label'):
                return r

    @asyncio.coroutine
    def post_command(self, c):
        cmd = ['off', 'on'][str(c).lower() in ('on', 'true', '1')]
        yield from self.req({'set': cmd})


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

    @asyncio.coroutine
    def loop(self):
        while self.running:
            res = None
            try:
                res = yield from self.switch.req({'get': 'state'})
            except asyncio.TimeoutError:
                LOG.error('timeout talking to %s', self.addr)
            except Exception as e:
                LOG.exception('loop')
            if res:
                for item in self.context.items:
                    if item.input == 'kankun:%s' % self.name:
                        self.context.set_item_value(item.name, res['state'])
            yield from asyncio.sleep(10)

    @asyncio.coroutine
    def command(self, args):
        yield from self.switch.post_command(args)
