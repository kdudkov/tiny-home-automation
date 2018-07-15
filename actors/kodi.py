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
    session = None

    def __init__(self, addr, loop):
        self.addr = addr
        self.loop = loop

    @asyncio.coroutine
    def init(self):
        self.session = aiohttp.ClientSession(auth=aiohttp.BasicAuth(self.user, self.passwd),
                                             loop=self.loop)

    @asyncio.coroutine
    def req(self, fn, params=None):
        req = {'jsonrpc': '2.0', 'id': 1, 'method': fn}

        if params:
            req['params'] = params

        if self.session is None:
            raise Exception('no session!')

        resp = yield from self.session.get(
            'http://%s/jsonrpc' % self.addr, params={'request': json.dumps(req)}, timeout=self.timeout)

        if resp.status != 200:
            raise Exception('http %s' % resp.status)
        try:
            res = yield from resp.json()
            if 'result' not in res:
                raise Exception('error')
            return res['result']
        finally:
            yield from resp.release()

    @asyncio.coroutine
    def find_serial(self, name):
        res = yield from self.req('VideoLibrary.GetTVShows')
        for r in res.get('tvshows', []):
            if name in r.get('label'):
                return r

    @asyncio.coroutine
    def get_serial_episodes(self, sid, season=None):
        r = {'tvshowid': sid, 'properties': ['showtitle', 'season', 'episode', 'title', 'playcount']}
        if season:
            r['season'] = season

        res = yield from self.req('VideoLibrary.GetEpisodes', r)
        return [x for x in res.get('episodes', [])]

    @asyncio.coroutine
    def get_episode_details(self, eid):
        r = {'episodeid': eid}

        res = yield from self.req('VideoLibrary.GetEpisodeDetails', r)
        return res

    @asyncio.coroutine
    def get_status(self):
        try:
            res = yield from self.req('Player.GetActivePlayers')
        except Exception as e:
            LOG.debug('error: %s', e)
            return {'state': 'OFF'}

        if res:
            pid = res[0]['playerid']
            ans = yield from self.req('Player.GetProperties', {'playerid': pid, 'properties': ['speed']})
            res = {'state': 'PAUSE' if ans['speed'] == 0 else 'PLAY'}
            ans = yield from self.req('Player.GetItem',
                                      {'playerid': pid,
                                       'properties': ['showtitle', 'season', 'episode', 'title']})
            res.update(ans)
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
            LOG.warning('%s is off', self.addr)
            return

        ser = yield from self.find_serial(name)
        if not ser:
            LOG.warning('%s is not found', name)
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
        self.loop_time = 3

    @asyncio.coroutine
    def init(self, config, context):
        self.config = config
        self.context = context
        self.kodi = Kodi(self.addr, self.context.loop)
        yield from self.kodi.init()

    @asyncio.coroutine
    def loop(self):
        while self.running:
            res = None
            try:
                res = yield from self.kodi.get_status()
            except asyncio.TimeoutError:
                LOG.error('timeout talking to %s', self.addr)
            except Exception as e:
                LOG.exception('loop')
            if res:
                self.context.set_item_value(self.get_item_name('state'), res['state'])
                name = ''

                item = res.get('item', {})

                if item.get('type') == 'movie':
                    name = item.get('label')

                if item.get('type') == 'episode':
                    name = '{} {}.{} {}'.format(
                        item.get('showtitle'),
                        item.get('season'),
                        item.get('episode'),
                        item.get('title'))

                self.context.set_item_value(self.get_item_name('item'), name)

            yield from asyncio.sleep(self.loop_time)

    @asyncio.coroutine
    def command(self, args):
        if args.get('cmd') == 'random':
            yield from self.kodi.play_random(args.get('name'))

    def get_item_name(self, s):
        return 'kodi_%s_%s' % (self.name, s)
