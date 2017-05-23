#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime, date
from operator import attrgetter

import time

from core import functions

LOG = logging.getLogger(__name__)

THRESHOLD = 48 * 60 * 60

ON = 'On'
OFF = 'Off'


class Items(object):
    def __init__(self):
        self._items = []

    def __iter__(self):
        for s in self._items:
            yield s

    def add_item(self, s):
        assert isinstance(s, Item), "invalid item class"
        assert not self.get_item(s.name), "already have this item"
        self._items.append(s)

    @property
    def num(self):
        return len(self._items)

    def get_item(self, name):
        for s in self._items:
            if s.name == name:
                return s
        return None

    def set_item_value(self, name, value):
        """
        Return pair od old_val, new_val if value was changed, else None
        """

        item = self.get_item(name)
        if not item:
            raise Exception('not found item %s' % name)
        old_val = item.value
        if item.set_value(value):
            new_val = item.value
            return old_val, new_val

    def as_list(self, tag=None):
        if tag:
            return [x.to_dict() for x in sorted(self._items, key=attrgetter('name')) if tag in x.tags]
        else:
            return [x.to_dict() for x in sorted(self._items, key=attrgetter('name'))]

    def value_is(self, name, val):
        return self.get_item(name) and self.get_item(name).value == val

    def __str__(self):
        return self.as_list()


def read_item(d):
    item = None
    if d['type'] == 'switch':
        item = SwitchItem(d['name'])
    if d['type'] == 'number':
        item = NumberItem(d['name'])
    if d['type'] == 'text':
        item = TextItem(d['name'])
    if d['type'] == 'date':
        item = DateItem(d['name'])
    if d['type'] == 'select':
        item = SelectItem(d['name'])
    if item:
        item.config = d
        item.input = d.get('input')
        item.output = d.get('output')
        item.ttl = d.get('ttl', 0)
        item.ui = bool(d.get('ui', False))
        item.tags = d.get('tags', [])
        if 'default' in d:
            item.set_value(d['default'])
    return item


class Item(object):
    input = None
    output = None
    ttl = 0
    ui = False
    tags = []
    config = {}

    def __init__(self, name, value=None, ttl=None):
        self.name = name
        if ttl is not None:
            self.ttl = ttl
        if value is not None:
            self.set_value(value)
        else:
            self._value = None
            self.checked = 0
            self.changed = 0

    def __str__(self):
        return "%s is %s for %s seconds" % (self.name, self._value, self.age)

    def __getitem__(self, item):
        return getattr(self, item)

    def to_dict(self):
        return {'name': self.name,
                'class': self.__class__.__name__,
                'ttl': self.ttl,
                'value': self.value,
                '_value': self._value,
                'age': self.age,
                'checked': self.checked,
                'changed': self.changed,
                'tags': self.tags,
                'formatted': self.formatted,
                'h_name': self.h_name,
                'ui': self.ui,
                }

    def is_value(self, st, for_time=1.0):
        return self._value == st and self.age >= for_time

    @property
    def age(self):
        if self.changed:
            return time.time() - self.changed
        else:
            return -1

    @property
    def is_fresh(self):
        if self.ttl and time.time() - self.checked > self.ttl:
            return False
        return True

    @property
    def value(self):
        return self._value if self.is_fresh else None

    def set_value(self, value):
        val = self.convert_value(value)
        self.checked = time.time()
        if val is not None and self._value != val:
            LOG.info('%s changed from %s to %s', self.name, self._value, val)
            self._value = val
            self.changed = time.time()
            return True
        else:
            return False

    def convert_value(self, val):
        return val

    def command(self, cmd):
        if not self.config.get('output'):
            self.set_value(cmd)

    @property
    def formatted(self):
        if self.value is None:
            return None
        frm = self.config.get('format')
        if frm:
            if frm in dir(functions):
                return getattr(functions, frm)(self.value)
            else:
                return frm.format(self.value)
        else:
            return self.value

    @property
    def h_name(self):
        return self.config.get('h_name') or self.name


class TextItem(Item):
    def convert_value(self, val):
        return val


class NumberItem(Item):
    def convert_value(self, val):
        v = float(val)

        if self.config.get('decimals'):
            d = self.config['decimals']
            if d == 0:
                return int(v)
            else:
                n = pow(10, self.config['decimals'])
                return int(v * n) / float(n)

        return v


class SwitchItem(Item):
    def convert_value(self, val):
        if str(val).lower() in ('click', 'switch'):
            return ON if self._value == OFF else OFF

        return ON if str(val).lower() in ('on', 'true', '1', 'open') else OFF


class SelectItem(Item):
    def convert_value(self, val):
        nv = str(val).lower()
        for v in self.config['choices']:
            if v.lower() == nv:
                return v
        return None


class DateItem(Item):
    def convert_value(self, val):
        if isinstance(val, (datetime, date)):
            return time.mktime(val.timetuple())
        return int(val)

    @property
    def formatted(self):
        if self.value is None:
            return None
        now = datetime.now()
        d = datetime.fromtimestamp(self.value)
        if now.date() == d.date():
            return d.strftime('%H:%M')
        else:
            return d.strftime('%d.%m %H:%M')
