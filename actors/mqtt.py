import asyncio
import logging
import time

import hbmqtt.client

from core.items import ON, OFF
from . import AbstractActor

LOG = logging.getLogger(__name__)


class MqttActor(AbstractActor):
    def __init__(self):
        self.mqtt_client = None
        self.send_time = {}

    def init(self, config, context):
        self.config = config
        self.context = context

        self.mqtt_client = hbmqtt.client.MQTTClient(config={'auto_reconnect': False})

    @asyncio.coroutine
    def loop(self):
        connected = False
        while self.running:
            if not connected:
                connected = yield from self.connect()
            try:
                message = yield from self.mqtt_client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name
                value = packet.payload.data.decode('utf-8')
                self.check_topic(topic, value)
            except hbmqtt.client.ClientException as ce:
                LOG.error('Client exception: %s' % ce)
                connected = False
            except Exception as e:
                LOG.error('%s' % e)
                connected = False
            if not connected:
                yield from self.disconnect()
                yield from asyncio.sleep(1)
        yield from self.disconnect()

    @asyncio.coroutine
    def connect(self):
        try:
            yield from self.mqtt_client.connect(self.config['mqtt']['url'])
            yield from self.mqtt_client.subscribe([
                ('#', 0),
                ('#', 1),
            ])
            LOG.info('connected')
            return True
        except OSError:
            LOG.error('connect failed')
            return False
        except hbmqtt.client.ConnectException:
            LOG.error('connect exception')
            return False
        except:
            LOG.exception('error on connect')
            return False

    @asyncio.coroutine
    def disconnect(self):
        try:
            yield from self.mqtt_client.disconnect()
        except:
            LOG.exception('error on disconnect')

    def check_topic(self, topic, value):
        LOG.debug('got topic %s, message %s', topic, value)
        if topic.startswith(self.config['mqtt'].get('in_topic')):
            cmd = topic.split('/')[-1]
            if value:
                LOG.info('got command %s %s', cmd, value)
                self.context.command(cmd, value)
                return
        for t in self.context.items:
            if t.input == 'mqtt:%s' % topic:
                self.context.set_item_value(t['name'], value, True)

    def is_my_command(self, cmd, arg):
        return cmd.startswith('mqtt:')

    @asyncio.coroutine
    def send_out(self, item, changed):
        t = self.send_time.get(item.name, 0)
        if time.time() - t < self.config['mqtt'].get('min_send_time', 30) and not changed:
            return
        self.send_time[item.name] = time.time()
        topic = self.config['mqtt'].get('out_topic')
        if topic:
            yield from self.mqtt_client.publish(topic.format(item.name), str(item.value).encode('UTF-8'),
                                                1 if changed else 0)

    @asyncio.coroutine
    def command(self, cmd, arg):
        yield from self.mqtt_client.publish(cmd[5:], arg.encode('UTF-8'), 0)
