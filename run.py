#!/usr/bin/env python3
# coding: utf-8

import argparse
import asyncio
import functools
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
from core import http_server
from core.context import CB_ONCHECK, CB_ONCHANGE
from core.items import read_item
from core.rules import Rule, ThermostatRule

LOG = logging.getLogger('mahno.' + __name__)
RULES_LOG = logging.getLogger('mahno.core.rules')

BASE_PATH = os.path.dirname(os.path.abspath(__file__))
DUMP_FILE = os.path.join(BASE_PATH, 'mahno.dump')


class Main(object):
    running = True
    coroutines = []
    actors = {}

    def __init__(self, args):
        signal.signal(signal.SIGUSR1, self.load_items_rules)
        signal.signal(signal.SIGTERM, self.stop)
        self.loop = None

        self.context = Context()
        self.context.config = {'server': {'port': 8880}}
        self.context.add_cb(CB_ONCHANGE, self.on_item_change)

        self.conf_dir = args.config_dir or os.path.join(BASE_PATH, 'config')
        self.load_config()

    def init_actors(self):
        mqtt_act = MqttActor()
        self.actors = {'mqtt': mqtt_act, 'astro': AstroActor()}

        if self.context.config['mqtt'].get('out_topic'):
            self.context.add_cb(CB_ONCHECK, mqtt_act.send_out)

        if 'modbus' in self.context.config:
            LOG.info('add modbus actor host %s', self.context.config['modbus']['host'])
            self.actors['modbus'] = ModbusActor(self.context.config['modbus']['host'],
                                                self.context.config['modbus']['port'])

        if 'kodi' in self.context.config:
            for k, v in self.context.config['kodi'].items():
                LOG.info('add kodi actor %s, addr %s', k, v)
                self.actors['kodi_' + k] = KodiActor(k, v)

        if 'kankun' in self.context.config:
            for k, v in self.context.config['kankun'].items():
                LOG.info('add kankun actor %s, addr %s', k, v)
                self.actors['kankun' + k] = KankunActor(k, v)

        for actor in self.actors.values():
            self.do(actor.init, self.context.config, self.context)

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
        LOG.info('loading config files from %s', self.conf_dir)

        if not os.path.isfile(os.path.join(self.conf_dir, 'config.yml')):
            LOG.error('no config.yml in {}'.format(self.conf_dir))
            sys.exit(1)

        self.context.config = yaml.load(open(os.path.join(self.conf_dir, 'config.yml'), 'r', encoding='UTF-8'))
        self.load_items_rules()

    def load_items_rules(self):
        LOG.info('loading items and rules')
        self.context.rules = []

        for s in os.listdir(self.conf_dir):
            if s.startswith('items_') and s.endswith('.yml'):
                try:
                    self.load_items_file(os.path.join(self.conf_dir, s))
                except:
                    LOG.exception('yml items load')
            elif s.startswith('rules_') and s.endswith('.yml'):
                try:
                    self.load_rules_file(os.path.join(self.conf_dir, s))
                except:
                    LOG.exception('yml rules load')

    def load_items_file(self, fname):
        conf = yaml.load(open(fname, 'r', encoding='UTF-8'))

        n = 0
        for item in conf:
            s = read_item(item)
            if s:
                self.context.items.add_item(s)
                n += 1
        LOG.info('load %s items from config %s', n, fname)

    def load_rules_file(self, fname):
        LOG.info('load rules from file %s', fname)
        conf = yaml.load(open(fname, 'r', encoding='UTF-8'))

        n = 0
        for r in conf:
            rule = None

            if 'trigger' in r:
                rule = Rule(r)
            if 'thermostat' in r:
                rule = ThermostatRule(r)

            if not rule:
                LOG.error('cannon make rule from definition %s', r)
                continue

            self.context.add_rule(rule)
            n += 1
        LOG.info('load %s rules from file %s', n, fname)

    @asyncio.coroutine
    def cron_checker(self):
        while self.running:
            for rule in self.context.rules:
                try:
                    v = rule.check_time()
                    if v is not None:
                        self.do(rule.process_cron, v)
                except:
                    RULES_LOG.exception('cron worker on rule %s', rule.name)

            yield from asyncio.sleep(0.5)

    @asyncio.coroutine
    def on_item_change(self, name, val, old_val, age):
        for rule in self.context.rules:
            if rule.check_item_change(name, val, old_val, age):
                try:
                    self.do(rule.process_item_change, name, val, old_val, age)
                except:
                    RULES_LOG.exception('item change on rule %s', rule.name)

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
        self.init_actors()

        for s in [self.cron_checker(), self.commands_processor()]:
            self.coroutines.append(asyncio.async(s, loop=self.loop))

        for actor in self.actors.values():
            self.coroutines.append(asyncio.async(actor.loop(), loop=self.loop))

        if self.actors.get('mqtt') and self.context.config['mqtt'].get('out_topic'):
            self.coroutines.append(asyncio.async(self.actors.get('mqtt').periodical_sender(), loop=self.loop))

        try:
            srv = http_server.get_app(self.context, self.context.config, self.loop)
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
    parser.add_argument('-c', dest='config_dir')
    parser.add_argument('--debug', dest='debug', action='store_true')
    args = parser.parse_args()

    log_format = '%(asctime)-15s %(levelname)s %(module)s %(funcName)s %(message)s'
    log_format_rules = '%(asctime)-15s %(levelname)s %(message)s'

    lvl = logging.INFO
    if args.debug:
        lvl = logging.DEBUG

    main_file_handler = logging.handlers.RotatingFileHandler(filename=os.path.join(BASE_PATH, 'mahno.log'),
                                                             maxBytes=2 * 1024 * 1024,
                                                             backupCount=2)
    main_file_handler.setFormatter(logging.Formatter(log_format))
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))

    logger = logging.getLogger()
    logger.setLevel(logging.ERROR)
    logger.addHandler(main_file_handler)
    logger.addHandler(console_handler)

    logger = logging.getLogger('mahno').setLevel(lvl)
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)

    # events
    handler = logging.handlers.RotatingFileHandler(filename=os.path.join(BASE_PATH, 'events.log'),
                                                   maxBytes=2 * 1024 * 1024,
                                                   backupCount=2)
    handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger('mahno.core.items').addHandler(handler)

    # rules
    handler = logging.handlers.RotatingFileHandler(filename=os.path.join(BASE_PATH, 'rules.log'),
                                                   maxBytes=2 * 1024 * 1024,
                                                   backupCount=2)
    handler.setFormatter(logging.Formatter(log_format_rules))
    RULES_LOG.addHandler(handler)

    Main(args).run()
