import asyncio
import collections
import functools
import logging
import time

from rules.abstract import Rule
from .items import Items

__author__ = 'madrider'

LOG = logging.getLogger(__name__)


class Context(object):
    def __init__(self):
        self.items = Items()
        self.actuators = {}
        self.rules = []
        self.listeners = []
        self.commands = collections.deque()
        self.loop = None
        self.callbacks = {}

    def do(self, fn, *args):
        if asyncio.iscoroutinefunction(fn):
            asyncio.async(fn(*args), loop=self.loop)
        else:
            self.loop.call_soon(functools.partial(fn, *args))

    def add_cb(self, name, cb):
        self.callbacks[name] = cb

    def command(self, name, cmd):
        item = self.items.get_item(name)
        if item:
            if item.config.get('output'):
                self.commands.append((item.config.get('output'), cmd))
            else:
                LOG.info('directly set %s to %s', name, cmd)
                self.set_item_value(name, cmd)
        else:
            LOG.info('external command %s', name)
            self.commands.append((name, cmd))

    def add_rule(self, rule):
        assert isinstance(rule, Rule)
        rule.context = self
        self.rules.append(rule)

    def set_item_value(self, name, value):
        t = self.items.set_item_value(name, value)
        item = self.items.get_item(name)
        cb = self.callbacks.get('oncheck')
        if cb and item:
            self.do(cb, item)
        if t:
            oldv, newv = t
            cb = self.callbacks.get('onchange')
            if cb:
                self.do(cb, name, oldv, newv, time.time())

    def add_delayed(self, seconds, fn):
        if self.loop:
            t = self.loop.time() + seconds
            return self.loop.call_at(t, fn)

    def remove_delayed(self, d):
        LOG.info('remove delayed %s', d)
        if d:
            d.cancel()
