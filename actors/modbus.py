#!/usr/bin/env python

import asyncio
import collections
import logging

from actors import AbstractActor

LOG = logging.getLogger(__name__)


def hex_data(data):
    return ' '.join((hex(x)[2:].rjust(2, '0') for x in data))


def to_le(n):
    return (n & 0xff00) >> 8, n & 0xff


class TcpMessage(object):
    def __init__(self):
        self.tr_id = 0
        self.pr_id = 0
        self.fn = 0
        self.size = 6
        self.addr = 0
        self.payload = []

    @staticmethod
    def decode_tcp(s):
        if isinstance(s, str):
            data = [ord(x) for x in s]
        else:
            data = [x for x in s]
        if len(data) < 8:
            raise Exception('invalid tcp message size')
        tr_id = data[0] * 256 + data[1]
        pr_id = data[2] * 256 + data[3]
        size = data[4] * 256 + data[5]
        if len(data) != size + 6:
            LOG.error('invalid size')
            return {}
        addr = data[6]
        fn = data[7]
        payload = data[8:]
        LOG.debug('fn %s to addr %s, data %s', fn, addr, hex_data(payload))
        msg = TcpMessage()
        msg.tr_id = tr_id
        msg.pr_id = pr_id
        msg.addr = addr
        msg.fn = fn
        msg.size = size
        msg.payload = payload
        return msg

    def set_payload(self, data):
        self.payload = data

    def set_payload_w_size(self, data):
        self.payload = [len(data), ]
        self.payload += data

    def to_list(self):
        res = []
        res += to_le(self.tr_id)
        res += to_le(self.pr_id)
        res += to_le(len(self.payload) + 2)
        res += [self.addr, self.fn]
        res += self.payload
        return res


def write_reg(seq, addr, reg, val):
    m = TcpMessage()
    m.fn = 6
    m.tr_id = seq
    m.addr = addr
    m.payload = to_le(reg) + to_le(val)
    return m


def read_reg(seq, addr, reg, num=1):
    m = TcpMessage()
    m.fn = 3
    m.tr_id = seq
    m.addr = addr
    m.payload = to_le(reg) + to_le(num)
    return m


class ModbusActor(AbstractActor):
    opened = False
    poll_list = []
    commands = collections.deque()
    generator = None

    def __init__(self, addr, port):
        self.addr = addr
        self.port = port

    def __next_command_generator(self):
        while 1:
            for d in self.poll_list:
                while self.commands:
                    yield self.commands.popleft()
                yield d

    def init(self, config, context):
        self.config = config
        self.context = context
        self.poll_list = self.config.get('modbus', {}).get('poll', [])
        LOG.info(self.poll_list)
        self.generator = self.__next_command_generator()

    @asyncio.coroutine
    def loop(self):
        reader = None
        writer = None
        for p in self.generator:
            if not self.running:
                break
            if not self.opened:
                reader, writer = yield from asyncio.open_connection(self.addr, self.port, loop=self.context.loop)
                self.opened = True
                LOG.info('modbus connected')
            try:
                if p['fn'] == 3:
                    # LOG.debug('fn %s to %s', p['fn'], p['addr'])
                    fut = self.send_message(writer, reader, read_reg(0, p['addr'], p['reg'], p.get('size', 1)))
                    msg = yield from asyncio.wait_for(fut, timeout=2)
                    if msg:
                        yield from self.process_message(msg, p['reg'])
                if p['fn'] == 6:
                    fut = self.send_message(writer, reader, write_reg(0, p['addr'], p['reg'], p['val']))
                    msg = yield from asyncio.wait_for(fut, timeout=2)

            except:
                self.opened = False
                LOG.exception('loop error')
                yield from asyncio.sleep(3)
            yield from asyncio.sleep(0.2)

        writer.close()

    def is_my_command(self, cmd, arg):
        return cmd.startswith('modbus:')

    @asyncio.coroutine
    def command(self, cmd, arg):
        val = [0, 1][str(arg).lower() in ('1', 'on')]
        fn, addr, reg = [int(x) for x in cmd[7:].split(':')]
        self.commands.append({'fn': fn, 'addr': addr, 'reg': reg, 'val': val})

    @asyncio.coroutine
    def send_message(self, writer, reader, msg):
        try:
            writer.write(bytes(msg.to_list()))
            yield from writer.drain()
            data = yield from reader.read(256)
            return TcpMessage.decode_tcp(data)
        except Exception as e:
            try:
                writer.close()
            except:
                pass
            raise e

    @asyncio.coroutine
    def process_message(self, msg, reg):
        n = int(msg.payload[0] / 2)
        for i in range(n):
            val = msg.payload[i * 2 + 1] * 256 + msg.payload[i * 2 + 2]
            str = 'modbus:%s:%s:%s' % (msg.fn, msg.addr, reg + i)
            for item in self.context.items:
                if item.input == str:
                    self.context.set_item_value(item.name, val)
