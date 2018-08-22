import asyncio
import collections
import functools
import logging

from .items import Items
from .rules import AbstractRule

CB_ONCHANGE = 'onchange'
CB_ONCHECK = 'oncheck'

LOG = logging.getLogger('mahno.' + __name__)


class Context(object):
    def __init__(self):
        self.config = {}
        self.items = Items()
        self.actors = {}
        self.rules = []
        self.commands = collections.deque()
        self.loop = None
        self.callbacks = {}

    def do_async(self, fn, *args):
        if asyncio.iscoroutinefunction(fn):
            asyncio.ensure_future(fn(*args), loop=self.loop)
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
            for actor in self.actors.values():
                if actor.name == item.config['output'].get('channel'):
                    msg = actor.format_simple_cmd(item.config['output'], cmd)
                    LOG.info('sending msg %s to %s', msg, actor.name)
                    self.commands.append((item.config['output']['channel'], msg))

            if item.config.get('fast_change'):
                LOG.debug('fast change set %s to %s', name, cmd)
                self.set_item_value(name, cmd)
        else:
            LOG.info('directly set %s to %s', name, cmd)
            self.set_item_value(name, cmd, True)

    def add_rule(self, rule):
        assert isinstance(rule, AbstractRule)
        rule.context = self
        self.rules.append(rule)

    def get_item_value(self, name):
        item = self.items.get_item(name)
        return item.value if item is not None else None

    def set_item_value(self, name, value, force=False):
        item = self.items.get_item(name)

        if not item:
            LOG.error('not found item %s' % name)
            return False

        old_value = item.value
        age = item.age

        changed = self.items.set_item_value(name, value)

        self.run_cb(CB_ONCHECK, item, changed)

        if changed or force:
            self.run_cb(CB_ONCHANGE, name, item.value, old_value, age)

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
                self.do_async(cb, *args)
