# coding: utf-8

import yaml

from core.items import Items
from core.rules import Rule

rule = '''
- name: 'rule1'
  trigger:
    time: '0 * * * *'
    items:
    - item1
    - item_id: item2
      to: 'on'
- name: 'rule2'
  trigger:
    items:
    - item1
    - item_id: item2
      to: 'on'
- name: 'rule3'
  trigger:
    items:
    - item1
    - item_id: item2
      to: 'on'
      for:
        seconds: 10
'''

rule2 = '''
- name: 'rule1'
  trigger:
    items:
    - item1
    - item_id: item2
      to: 1
- name: 'rule2'
  trigger:
    items:
    - item1
    - item_id: item2
      from: 1
'''


class TestContext(object):
    def __init__(self):
        self.items = Items()

    def get_item_value(self, name):
        item = self.items.get_item(name)
        return item.value if item is not None else None


class TestItem(object):
    def __init__(self, name, v):
        self.name = name
        self.value = v
        self.age = 0


def test_trigger_time_based():
    t = yaml.load(rule)[0]
    r = Rule(t)
    assert r.time_based

    t = yaml.load(rule)[1]
    r = Rule(t)
    assert r.time_based is False

    t = yaml.load(rule)[2]
    r = Rule(t)
    assert r.time_based


def test_item_for():
    i1 = TestItem('item1', 5)
    i2 = TestItem('item2', 5)
    context = TestContext()
    context.items.add_item(i1)
    context.items.add_item(i2)

    t = yaml.load(rule)[2]
    r = Rule(t)
    assert r.name == 'rule3'
    r.context = context

    i2.value = 'on'
    i2.age = 5
    assert r.check_time() is None, r.triggered

    i2.value = 'off'
    i2.age = 10
    assert r.check_time() is None

    i2.value = 'on'
    i2.age = 10
    assert r.check_time() is not None

    i2.value = 'on'
    i2.age = 10
    assert r.check_time() is None

    i2.value = 'off'
    i2.age = 10
    assert r.check_time() is None

    i2.value = 'on'
    i2.age = 10
    assert r.check_time() is not None


def test_item():
    t = yaml.load(rule2)[0]
    r = Rule(t)
    assert r.check_item_change('item1', 1, 2, 0) is True
    assert r.check_item_change('item3', 1, 2, 0) is False
    assert r.check_item_change('item2', 2, 1, 0) is False
    assert r.check_item_change('item2', 1, 2, 0) is True

    t = yaml.load(rule2)[1]
    r = Rule(t)
    assert r.check_item_change('item2', 2, 1, 0) is True
    assert r.check_item_change('item2', 1, 2, 0) is False


def test_condition_numeric():
    c = TestContext()
    i = TestItem('item1', '23')
    c.items.add_item(i)

    cond = yaml.load('''
condition_type: numeric_state
item_id: item1
above: 17
below: 25
''')
    i.value = 23
    assert Rule.check_condition(cond, c) is True

    i.value = 16
    assert Rule.check_condition(cond, c) is False

    i.value = '23'
    assert Rule.check_condition(cond, c) is True

    i.value = '16'
    assert Rule.check_condition(cond, c) is False

    i.value = '23.1'
    assert Rule.check_condition(cond, c) is True

    i.value = '16.1'
    assert Rule.check_condition(cond, c) is False


def test_condition_or():
    c = TestContext()
    i = TestItem('item1', '23')
    c.items.add_item(i)

    cond = yaml.load('''
condition_type: or
conditions:
  - condition_type: numeric_state
    item_id: item1
    below: 17
  - condition_type: numeric_state
    item_id: item1
    above: 25
''')
    i.value = 23
    assert Rule.check_condition(cond, c) is False

    i.value = 16
    assert Rule.check_condition(cond, c) is True

    i.value = 26
    assert Rule.check_condition(cond, c) is True
