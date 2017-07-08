#!/usr/bin/env python3
# coding: utf-8

import argparse
import asyncio
import functools
import inspect
import json
import logging.handlers
import os
import pickle
import signal
import sys
import traceback

import yaml

from actors.astro import AstroActor
from actors.kankun import KankunActor
from actors.kodi import KodiActor
from actors.modbus import ModbusActor
from actors.mqtt import MqttActor
from core import Context
from core import cron
from core import http_server
from core.context import CB_ONCHECK, CB_ONCHANGE
from core.items import *
from rules.abstract import Rule

LOG = logging.getLogger(__name__)

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DUMP_FILE = os.path.join(BASE_PATH, 'mahno.dump')


class Main(object):
    running = True

    def __init__(self):
        signal.signal(signal.SIGUSR1, self.debug)
        signal.signal(signal.SIGTERM, self.stop)
        self.loop = None
        self.config = {'server': {'port': 8880}}

        self.context = Context()
        self.context.add_cb(CB_ONCHANGE, self.on_item_change)

        self.load_config()

        self.load_rules()

        mqtt_act = MqttActor()
        self.actors = {'mqtt': mqtt_act, 'astro': AstroActor()}

        if self.config['mqtt'].get('out_topic'):
            self.context.add_cb(CB_ONCHECK, mqtt_act.send_out)

        if 'modbus' in self.config:
            LOG.info('add modbus actor host %s', self.config['modbus']['host'])
            self.actors['modbus'] = ModbusActor(self.config['modbus']['host'], self.config['modbus']['port'])

        if 'kodi' in self.config:
            for k, v in self.config['kodi'].items():
                LOG.info('add kodi actor %s, addr %s', k, v)
                self.actors['kodi_' + k] = KodiActor(k, v)

        if 'kankun' in self.config:
            for k, v in self.config['kankun'].items():
                LOG.info('add kankun actor %s, addr %s', k, v)
                self.actors['kankun' + k] = KankunActor(k, v)

        for actor in self.actors.values():
            actor.init(self.config, self.context)

        try:
            self.load_dump(DUMP_FILE)
        except:
            LOG.exception('cannot load state')

    def debug(self, sig, stack):
        LOG.info('DEBUG!!!')
        with open('running_stack', 'w') as f:
            f.write('Mahno debug\n\n')
            traceback.print_stack(stack, file=f)
            f.write('\n')
            f.write(self.context.items.as_list())
            f.write('\n')

    def stop(self, *args):
        self.save_dump(DUMP_FILE)
        sys.exit(0)

    def save_dump(self, fn):
        LOG.info('saving state')
        dump = self.context.items.as_list()
        with open(fn, 'wb') as f:
            pickle.dump(dump, f)

    def load_dump(self, fn):
        if not os.path.isfile(fn):
            LOG.info('no dump file')
            return

        LOG.info('loading state from dump')

        with open(fn, 'rb') as f:
            dump = pickle.load(f)

        for st in dump:
            s = self.context.items.get_item(st['name'])
            if s:
                s._value = s.convert_value(st['value'])
                s.changed = st['changed']
                s.checked = st['checked']
                # s.ttl = st.get('ttl', 0)

    def load_config(self):
        if os.path.isfile(os.path.join(BASE_PATH, 'config', 'config.yml')):
            self.config = yaml.load(open(os.path.join(BASE_PATH, 'config', 'config.yml'), 'r'))
        for s in os.listdir(os.path.join(BASE_PATH, 'config')):
            if s.startswith('items') and s.endswith('.yml'):
                try:
                    self.load_items_file(os.path.join(BASE_PATH, 'config', s))
                except:
                    LOG.exception('yml load')

    def load_rules(self):
        for fn in os.listdir('rules'):
            if fn.startswith('.') or fn.startswith('_') or not fn.endswith('.py'):
                continue
            mod = __import__('rules.' + fn[:-3])
            submod = getattr(mod, fn[:-3])
            for name1 in dir(submod):
                classes = Rule.__subclasses__()
                classes.append(Rule)
                if inspect.isclass(getattr(submod, name1)):
                    r = getattr(submod, name1)
                    if issubclass(r, tuple(classes)) and r != Rule and 'Abstract' not in name1:
                        LOG.info('loading rule %s.%s', fn[:-3], name1)
                        self.context.add_rule(r())

    def load_items_file(self, fname):
        conf = yaml.load(open(fname, 'r'))

        n = 0
        for item in conf:
            s = read_item(item)
            if s:
                self.context.items.add_item(s)
                n += 1
        LOG.info('load %s items from config %s', n, fname)

    @asyncio.coroutine
    def cron_checker(self):
        minute = 0

        while self.running:
            new_m = int(time.time() / 60)

            if minute != new_m:
                LOG.debug('check cron')
                minute = new_m
                dump = self.context.items.as_list()
                json.dump(dump, open('items.json', 'w'), indent=4)
                dt = time.time()

                for rule in self.context.rules:
                    try:
                        if rule.on_time and cron.check_cron_value(rule.on_time, dt):
                            LOG.info('running rule %s on cron %s', rule.__class__.__name__, rule.on_time)
                            asyncio.async(rule.try_process(cron.name, None, dt), loop=self.loop)
                    except:
                        LOG.exception('cron worker')

            yield from asyncio.sleep(30)

    @asyncio.coroutine
    def on_item_change(self, name, old_val, val, time):
        for rule in self.context.rules:
            if name in rule.on_change:
                LOG.info('running rule %s on %s change', rule.__class__.__name__, name)
                asyncio.async(rule.try_process(name, old_val, val), loop=self.loop)

    @asyncio.coroutine
    def commands_processor(self):
        while self.running:
            if self.context.commands:
                cmd, arg = self.context.commands.popleft()
                for actor in self.actors.values():
                    if actor.is_my_command(cmd, arg):
                        self.do(actor.command, cmd, arg)

            yield from asyncio.sleep(0.01)

    def do(self, fn, *args):
        if asyncio.iscoroutinefunction(fn):
            asyncio.async(fn(*args), loop=self.loop)
        else:
            self.loop.call_soon(functools.partial(fn, *args))

    def run(self):
        self.loop = asyncio.get_event_loop()
        self.context.loop = self.loop
        self.coroutines = []

        for s in [self.cron_checker(), self.commands_processor()]:
            self.coroutines.append(asyncio.async(s, loop=self.loop))

        for actor in self.actors.values():
            self.coroutines.append(asyncio.async(actor.loop(), loop=self.loop))

        if self.actors.get('mqtt') and self.config['mqtt'].get('out_topic'):
            self.coroutines.append(asyncio.async(self.actors.get('mqtt').periodical_sender(), loop=self.loop))

        try:
            srv = http_server.get_app(self.context, self.config, self.loop)
            asyncio.async(srv, loop=self.loop)
            self.loop.run_forever()
        finally:
            for actor in self.actors.values():
                actor.stop()
            self.running = False
            asyncio.wait(self.coroutines)
            self.save_dump(DUMP_FILE)
            self.loop.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', dest='debug', action='store_true')
    args = parser.parse_args()

    log_format = '%(asctime)-15s %(levelname)-8s %(name)-8s %(message)s'
    if args.debug:
        logging.basicConfig(level='INFO')
    else:
        logger = logging.getLogger()
        handler = logging.handlers.RotatingFileHandler(filename=os.path.join(BASE_PATH, 'mahno.log'),
                                                       maxBytes=2 * 1024 * 1024,
                                                       backupCount=2)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(handler)

        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(handler)

        handler = logging.handlers.RotatingFileHandler(filename=os.path.join(BASE_PATH, 'events.log'),
                                                       maxBytes=2 * 1024 * 1024,
                                                       backupCount=2)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger('core.items').addHandler(handler)

        handler = logging.handlers.RotatingFileHandler(filename=os.path.join(BASE_PATH, 'rules.log'),
                                                       maxBytes=2 * 1024 * 1024,
                                                       backupCount=2)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger('rules').addHandler(handler)

        logger.setLevel(logging.INFO)
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    Main().run()
