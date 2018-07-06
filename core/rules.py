# coding: UTF-8
import asyncio
import logging
import time
from datetime import datetime as dt

from jinja2 import Template

from core.cron import check_cron_values
from core.items import ON, OFF
from core.services import log_service, slack_service

LOG = logging.getLogger('mahno.' + __name__)


class AbstractRule(object):
    name = 'unnamed'
    data = None
    context = None
    last_run = 0
    last_time = 0
    triggered = ''
    busy = False
    time_based = False
    active = False
    trigger = None

    def check_time(self, t=None):
        pass

    def check_item_change(self, name, val, old_val, age):
        pass

    @asyncio.coroutine
    def process_item_change(self, name, val, old_val, age):
        d = dict(
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
            LOG.debug('rule %s running on %s fail conditions', self.name, d['triggered'])
            return

        LOG.info('running rule %s on %s', self.name, d['triggered'])
        start = time.time()
        self.busy = True
        try:
            self.last_run = time.time()
            self.triggered = d['triggered']
            yield from self._run(d)
        except:
            LOG.exception('error in rule %s', self.name)
        finally:
            self.last_time = time.time() - start
            self.busy = False

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
                    active=self.active,
                    condition=self.data.get('condition'))

    @staticmethod
    def check_condition(condition, context):
        if 'condition_type' not in condition:
            LOG.error('no condition type in condition %s', condition)
            return False

        ct = condition['condition_type']

        if ct == 'state':
            item = context.items.get_item(condition['item_id'])

            if item is None:
                LOG.warning('no item %s', condition['item_id'])
                return False

            op = condition.get('check', 'is')

            if op == 'is':
                return item.value == condition['state']
            
            elif op == 'not':
                return item.value != condition['state']

            elif op == 'in':
                assert isinstance(condition['state'], (list, tuple))

                return item.value in condition['state']
            else:
                LOG.error('invalid check \'%s\'', op)
                return False

        elif ct == 'numeric_state':
            return Rule.check_condition_numeric(condition, context)

        elif ct == 'time':
            return Rule.check_condition_time(condition)

        elif ct == 'or':
            return any(map(lambda x: Rule.check_condition(x, context), condition['conditions']))

        elif ct == 'and':
            return all(map(lambda x: Rule.check_condition(x, context), condition['conditions']))

        else:
            LOG.error('invalid condition type \'%s\'', ct)
        return False

    @staticmethod
    def check_condition_numeric(condition, context):
        assert condition['condition_type'] == 'numeric_state'

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
            if k in ('item_id', 'condition_type'):
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
        assert condition['condition_type'] == 'time'

        if t is None:
            t = dt.now()

        m = t.hour * 60 + t.minute

        for k, v in condition.items():
            if k == 'condition_type':
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

    @asyncio.coroutine
    def _run(self, d):
        pass


class ThermostatRule(AbstractRule):
    def __init__(self, c):
        self.name = c['name']
        self.data = c
        self.active = False
        self.switch_item = c['thermostat']['switch_item']
        self.sensor_item = c['thermostat']['sensor_item']
        self.target_value_item = c['thermostat']['target_value_item']
        self.actor_item = c['thermostat']['actor_item']
        self.is_cooler = bool(c['thermostat'].get('is_cooler', False))
        self.gist = float(c['thermostat'].get('gist', 1.0))
        self.timeout = int(c['thermostat'].get('timeout', 60))
        self.last_switch = 0

    def check_item_change(self, name, val, old_val, age):
        return name in (self.sensor_item, self.switch_item, self.target_value_item)

    @asyncio.coroutine
    def _run(self, d):
        if self.context.get_item_value(self.switch_item) != ON:
            return

        t = self.context.get_item_value(self.sensor_item)
        t_d = self.context.get_item_value(self.target_value_item)

        if t is None or t_d is None:
            LOG.error('emergency: temp sensor %s or thermostat %s value is None', self.sensor_item,
                      self.target_value_item)
            self.context.item_command(self.actor_item, OFF)
            return

        if time.time() - self.last_switch < self.timeout:
            # do not switch too fast
            return

        LOG.debug('temp %s, target %s, switch %s', t, t_d, self.context.get_item_value(self.actor_item))

        target_sw = None

        if t >= t_d + self.gist / 2:
            target_sw = ON if self.is_cooler else OFF
        elif t <= t_d - self.gist / 2:
            target_sw = OFF if self.is_cooler else ON

        if target_sw is not None and self.context.get_item_value(self.actor_item) != target_sw:
            self.last_switch = time.time()
            LOG.info('value is %s, range is %s - %s, setting %s to %s', t, t_d - self.gist / 2, t_d + self.gist / 2,
                     self.actor_item, target_sw)
            self.context.item_command(self.actor_item, target_sw)

    def to_dict(self):
        d = AbstractRule.to_dict(self)
        d['is_cooler'] = self.is_cooler
        return d


class Rule(AbstractRule):
    def __init__(self, c):
        self.name = c['name']
        self.data = c
        self.context = None
        self.active = False
        self.last_run = 0
        self.triggered = ''
        self.busy = False
        self.last_time = 0

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
    def _run(self, rule_context):
        for act in self.data.get('action', []):
            if 'service' in act:
                LOG.info('running service %s', act['service'])
                yield from self._do_service(act, rule_context)
            elif 'condition' in act:
                if not self.check_condition(act, self.context):
                    LOG.info('break on condition %s', act)
                    break

    @asyncio.coroutine
    def _do_service(self, act, rule_context):
        s_name = act['service']

        if s_name == 'set_state':
            name = act['item_id']
            value = self.get_value(act, rule_context)
            self.context.set_item_value(name, value)

        elif s_name == 'command':
            name = act['item_id']
            value = self.get_value(act, rule_context)
            LOG.info('sending command \'%s\' to %s', value, name)
            self.context.item_command(name, value)

        elif s_name == 'log':
            log_service(act.get('data'), rule_context)

        elif s_name == 'slack':
            yield from slack_service(act.get('data'), rule_context, self.context)

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
