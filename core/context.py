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
        self.commands = collections.deque()
        self.loop = None
        self.callbacks = {}

    def do(self, fn, *args):
        if asyncio.iscoroutinefunction(fn):
            asyncio.async(fn(*args), loop=self.loop)
        else:
            self.loop.call_soon(functools.partial(fn, *args))

    def add_cb(self, name, cb):
        self.callbacks.setdefault(name, []).append(cb)

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

    def get_item_value(self, name):
        item = self.items.get_item(name)
        return item.value if item is not None else None

    def set_item_value(self, name, value):
        t = self.items.set_item_value(name, value)
        item = self.items.get_item(name)
        self.run_cb('oncheck', item)
        if t:
            oldv, newv = t
            self.run_cb('onchange', name, oldv, newv, time.time())

    def add_delayed(self, seconds, fn):
        if self.loop:
            t = self.loop.time() + seconds
            return self.loop.call_at(t, fn)

    def remove_delayed(self, d):
        LOG.info('remove delayed %s', d)
        if d:
            d.cancel()

    def run_cb(self, name, *args):
        for cb in self.callbacks.get(name, []):
            if cb:
                self.do(cb, *args)
