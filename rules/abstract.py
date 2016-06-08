import asyncio
import logging
from datetime import datetime as dt

LOG = logging.getLogger(__name__)


class Rule(object):
    on_change = []
    on_time = ''
    context = None

    def add_delayed(self, seconds, fn):
        self.context.add_delayed(seconds, fn)

    def remove_delayed(self, d):
        self.context.remove_delayed(d)

    def post_update(self, item_name, value):
        self.context.set_item_value(item_name, value)

    def get_val_or_none(self, name):
        item = self.context.items.get_item(name)
        return item.value if item else None

    def command(self, name, cmd):
        self.context.command(name, cmd)

    @asyncio.coroutine
    def try_process(self, name, old_val, val):
        try:
            if asyncio.iscoroutinefunction(self.process):
                yield from self.process(name, old_val, val)
            else:
                self.process(name, old_val, val)
        except:
            LOG.exception('error in rule %s', self.__class__.__name__)

    def process(self, name, old_val, val):
        pass

    @staticmethod
    def time_between(t1, t2):
        h1, m1 = [int(x) for x in t1.split(':', 1)]
        h2, m2 = [int(x) for x in t2.split(':', 1)]

        m1 = h1 * 60 + m1
        m2 = h2 * 60 + m2

        now = dt.now()
        m = now.hour * 60 + now.minute

        if m1 < m2:
            return m1 <= m <= m2
        else:
            return m > m1 or m < m2

