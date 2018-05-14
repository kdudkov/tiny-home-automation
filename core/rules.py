# coding: UTF-8
import asyncio
import logging
import time
from datetime import datetime as dt

from jinja2 import Template

from core.cron import check_cron_values
from core.items import ON
from core.services import log_service

LOG = logging.getLogger('mahno.' + __name__)


class Rule(object):
    def __init__(self, c):
        self.context = None
        self.active = False
        self.last_run = 0
        self.triggered = ''
        self.busy = False
        self.last_time = 0
        self.data = c
        self.name = c['name']

        self.trigger = c['trigger']

        self.time_based = False
        if self.trigger.get('time'):
            self.time_based = True
        else:
            for i in self.trigger.get('items', []):
                if isinstance(i, dict) and i.get('for') is not None:
                    self.time_based = True

    def check_time(self, t=None):
        """
        check if rule must be fired
        """
        if t is None:
            t = time.time()

        if not self.time_based:
            return None

        tr = None

        # check cron
        if self.trigger.get('time') and t - self.last_run > 60:
            cron_value = self.trigger['time'].strip()

            v = check_cron_values(cron_value, t, self.last_run)
            if v is not None:
                tr = 'cron {}'.format(cron_value)

        # check items
        for i in self.trigger.get('items', []):
            if isinstance(i, dict) and i.get('item_id') is not None and i.get('for') is not None:
                item = self.context.items.get_item(i['item_id'])

                if item is None:
                    continue

                td = i['for'].get('hours', 0) * 3600 + i['for'].get('minutes', 0) * 60 + i['for'].get('seconds', 0)

                if item.value == i.get('to', ON) and item.age >= td:
                    tr = 'item {} {} for {} s'.format(item.name, item.value, int(item.age))
                    break

        if tr is not None and not self.active:
            self.active = True
            return tr

        self.active = tr is not None
        return None

    def check_item_change(self, name, val, old_val, age):
        for i in self.trigger.get('items', []):
            if isinstance(i, str):
                if i == name:
                    return True

            if isinstance(i, dict) and i.get('for') is None:
                if i.get('item_id') != name:
                    continue

                if i.get('from') is not None and i.get('from') != old_val:
                    continue

                if i.get('to') is not None and i.get('to') != val:
                    continue

                return True
        return False

    @asyncio.coroutine
    def process_item_change(self, name, val, old_val, age):
        d = dict(
            rule_name=self.name,
            items=self.context.items,
            type='item_change',
            name=name,
            value=val,
            old_value=old_val,
            triggered='item {} {} -> {}'.format(name, old_val, val)
        )
        yield from self._try_process(d)

    @asyncio.coroutine
    def process_signal(self, topic, val):
        d = dict(
            rule_name=self.name,
            items=self.context.items,
            type='mqtt',
            name=topic,
            value=val,
            old_value=None,
            triggered='mqtt {}: {}'.format(topic, val)
        )
        yield from self._try_process(d)

    @asyncio.coroutine
    def process_cron(self, v):
        d = dict(
            rule_name=self.name,
            items=self.context.items,
            type='cron',
            name=None,
            value=None,
            old_value=None,
            triggered=v
        )
        yield from self._try_process(d)

    @asyncio.coroutine
    def _try_process(self, d):
        if self.busy:
            LOG.warning('rule %s is busy', self.name)
            return

        if not self.check_conditions():
            return

        start = time.time()
        self.busy = True
        try:
            self.last_run = time.time()
            self.triggered = d['triggered']
            yield from self.do_actions(d)
        except:
            LOG.exception('error in rule %s', self.name)
        finally:
            self.last_time = time.time() - start
            self.busy = False

    @asyncio.coroutine
    def do_actions(self, context):
        for act in self.data.get('action', []):
            if 'service' in act:
                LOG.info('running service %s', act['service'])
                yield from self.do_service(act, context)
            elif 'condition' in act:
                if not self.check_condition(act, self.context):
                    LOG.info('break on condition %s', act)
                    break

    @asyncio.coroutine
    def do_service(self, act, context):
        s_name = act['service']
        if s_name == 'set_item':
            name = act['item_id']
            value = self.get_value(act, context)
            self.context.set_item_value(name, value)
        elif s_name == 'command':
            name = act['item_id']
            value = self.get_value(act, context)
            LOG.info('sending command \'%s\' to %s', value, name)
            self.context.item_command(name, value)
        elif s_name == 'log':
            log_service(act.get('data'), context)

        else:
            LOG.error('invalid service name: %s', s_name)

    @staticmethod
    def get_value(act, context):
        if not isinstance(act, dict):
            return act

        if 'value_template' in act:
            t = Template(act['value_template'])
            return t.render(**context)
        else:
            return act.get('value')

    def check_conditions(self):
        if 'condition' not in self.data:
            return True

        return self.check_condition(self.data['condition'], self.context)

    def to_dict(self):
        return dict(name=self.name,
                    busy=self.busy,
                    last_run=self.last_run,
                    triggered=self.triggered,
                    last_time=self.last_time,
                    active=self.active)

    @staticmethod
    def check_condition(condition, context):
        if condition['condition'] == 'state':
            return context.get_item_value(condition['item_id']) == condition['state']

        if condition['condition'] == 'numeric_state':
            return Rule.check_condition_numeric(condition, context)

        if condition['condition'] == 'time':
            return Rule.check_condition_time(condition)

        if condition['condition'] == 'or':
            return any(map(lambda x: Rule.check_condition(x, context), condition['conditions']))

        if condition['condition'] == 'and':
            return all(map(lambda x: Rule.check_condition(x, context), condition['conditions']))

        print(condition['condition'])
        return True

    @staticmethod
    def check_condition_numeric(condition, context):
        assert condition['condition'] == 'numeric_state'

        val = context.get_item_value(condition['item_id'])

        if val is None:
            return False

        if isinstance(val, str):
            if '.' in val:
                val = float(val)
            elif ',' in val:
                val = float(val.replace(',', '.'))
            else:
                val = int(val)

        for k, v in condition.items():
            if k in ('item_id', 'condition'):
                continue

            if k == 'above':
                if not val > v:
                    return False

            elif k == 'below':
                if not val < v:
                    return False

            else:
                raise Exception('invalid operator \'{}\' in numeric_state'.format(k))

        return True

    @staticmethod
    def check_condition_time(condition, t=None):
        assert condition['condition'] == 'time'

        if t is None:
            t = dt.now()

        m = t.hour * 60 + t.minute

        for k, v in condition.items():
            if k == 'condition':
                continue

            if k == 'after':
                h1, m1 = [int(x) for x in v.split(':', 1)]
                m1 += h1 * 60

                if m < m1:
                    return False

            elif k == 'before':
                h1, m1 = [int(x) for x in v.split(':', 1)]
                m1 += h1 * 60

                if m > m1:
                    return False

            elif k == 'between':
                h1, m1 = [int(x) for x in v[0].split(':', 1)]
                h2, m2 = [int(x) for x in v[1].split(':', 1)]

                m1 += h1 * 60
                m2 += h2 * 60

                if m1 < m2:
                    if not m1 <= m <= m2:
                        return False
                else:
                    if not m > m1 or m < m2:
                        return False

            else:
                raise Exception('invalid operator \'{}\' in time'.format(k))
