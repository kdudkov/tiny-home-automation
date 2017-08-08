import asyncio
import collections
import functools
import logging

from rules.abstract import Rule
from .items import Items

CB_ONCHANGE = 'onchange'
CB_ONCHECK = 'oncheck'

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
        LOG.info('external command %s', name)
        self.commands.append((name, cmd))

    def item_command(self, name, cmd):
        item = self.items.get_item(name)

        if not item:
            LOG.error('no item %s', name)
            return

        if item.config.get('output'):
            self.commands.append((item.config.get('output'), cmd))

            if item.config.get('fast_change'):
                LOG.info('fast change set %s to %s', name, cmd)
                self.set_item_value(name, cmd)
        else:
            LOG.info('directly set %s to %s', name, cmd)
            self.set_item_value(name, cmd, True)

    def add_rule(self, rule):
        assert isinstance(rule, Rule)
        rule.context = self
        self.rules.append(rule)

    def get_item_value(self, name):
        item = self.items.get_item(name)
        return item.value if item is not None else None

    def set_item_value(self, name, value, force=False):
        item = self.items.get_item(name)
        if not item:
            raise Exception('not found item %s' % name)

        old_value = item.value
        age = item.age

        changed = self.items.set_item_value(name, value)

        self.run_cb(CB_ONCHECK, item, changed)

        if changed or force:
            self.run_cb(CB_ONCHANGE, name, value, old_value, age)

    def add_delayed(self, seconds, fn):
        if self.loop:
            t = self.loop.time() + seconds
            return self.loop.call_at(t, fn)

    @staticmethod
    def remove_delayed(d):
        LOG.info('remove delayed %s', d)
        if d:
            d.cancel()

    def run_cb(self, name, *args):
        for cb in self.callbacks.get(name, []):
            if cb:
                self.do(cb, *args)
