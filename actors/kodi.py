#!/usr/bin/env python3

import asyncio
import json
import logging
import random

import aiohttp

from . import AbstractActor

LOG = logging.getLogger('mahno.' + __name__)


class Kodi(object):
    timeout = 3
    user = 'kodi'
    passwd = 'kodi'

    def __init__(self, addr, loop):
        self.addr = addr
        self.loop = loop

        self.session = aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.user, self.passwd),
                                             loop=self.loop)

    @asyncio.coroutine
    def req(self, fn, params=None):
        req = {'jsonrpc': '2.0', 'id': 1, 'method': fn}
        if params:
            req['params'] = params
        with aiohttp.Timeout(self.timeout):
            resp = yield from self.session.get('http://%s/jsonrpc' % self.addr, params={'request': json.dumps(req)})
        if resp.status != 200:
            raise Exception('http %s' % resp.status)
        try:
            res = yield from resp.json()
            if not 'result' in res:
                print(res)
                raise Exception('error')
            return res['result']
        finally:
            yield from resp.release()

    @asyncio.coroutine
    def get_serial(self, name):
        res = yield from self.req('VideoLibrary.GetTVShows')
        for r in res.get('tvshows', []):
            if name in r.get('label'):
                return r

    @asyncio.coroutine
    def get_serial_episodes(self, sid, season):
        res = yield from self.req('VideoLibrary.GetEpisodes', {'tvshowid': sid, 'season': season})
        return res.get('episodes', [])

    @asyncio.coroutine
    def get_status(self):
        try:
            res = yield from self.req('Player.GetActivePlayers')
        except Exception as e:
            print(e)
            return {'state': 'OFF'}
        if res:
            pid = res[0]['playerid']
            ans = yield from self.req('Player.GetProperties', {'playerid': pid, 'properties': ['speed']})
            res = {}
            res['state'] = 'PAUSE' if ans['speed'] == 0 else 'PLAY'
            ans = yield from self.req('Player.GetItem', {'playerid': pid})
            res.update(ans)
            if ans['item']['type'] == 'episode':
                ans = yield from self.req('VideoLibrary.GetEpisodeDetails', {'episodeid': ans['item']['id'],
                                                                             'properties': ['showtitle', 'season',
                                                                                            'episode', 'title']})
                res['item'].update(ans['episodedetails'])
            return res
        else:
            return {'state': 'STOP'}

    @asyncio.coroutine
    def play_episode(self, epid):
        res = yield from self.req('Player.Open', {'item': {'episodeid': epid}})
        return res

    @asyncio.coroutine
    def play_random(self, name, max_season=3):
        stat = yield from self.get_status()
        if stat['state'] == 'OFF':
            LOG.warn('%s is off', self.addr)
            return

        ser = yield from self.get_serial(name)
        if not ser:
            LOG.warn('%s is not found', name)
            return
        sid = ser['tvshowid']

        episodes = []
        for i in range(max_season + 1):
            res = yield from self.get_serial_episodes(sid, i)
            for r in res:
                episodes.append(r)

        random.seed()
        e = random.choice(episodes)
        LOG.info('playing %s', e.get('label'))
        yield from self.play_episode(e['episodeid'])
        return e


class KodiActor(AbstractActor):
    def __init__(self, name, addr):
        self.name = name
        self.addr = addr
        self.kodi = None

    def init(self, config, context):
        self.config = config
        self.context = context
        self.kodi = Kodi(self.addr, self.context.loop)

    @asyncio.coroutine
    def loop(self):
        while self.running:
            res = None
            try:
                res = yield from self.kodi.get_status()
            except Exception as e:
                LOG.exception('loop')
            if res:
                self.context.set_item_value(self.get_name('state'), res['state'])
            yield from asyncio.sleep(5)

    def is_my_command(self, cmd, arg):
        return cmd.startswith('kodi:%s' % self.name)

    @asyncio.coroutine
    def command(self, cmd, arg):
        if cmd == 'kodi:%s:random' % self.name:
            yield from self.kodi.play_random(arg)

    def get_name(self, s):
        return 'kodi_%s_%s' % (self.name, s)
