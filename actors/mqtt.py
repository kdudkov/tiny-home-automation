import asyncio
import logging
import time

import hbmqtt.client

from . import AbstractActor

LOG = logging.getLogger('mahno.' + __name__)


def match_topic(mask, topic):
    mask_parts = mask.split('/')
    topic_parts = topic.split('/')

    if mask_parts[0] == '#':
        return True

    if len(topic_parts) < len(mask_parts):
        return False

    for m, t in zip(mask_parts, topic_parts):
        if m == '+':
            continue

        if m == '#':
            return True

        if t != m:
            return False

    return True


class MqttActor(AbstractActor):
    name = 'mqtt'

    def __init__(self):
        self.mqtt_client = None
        self.send_time = {}
        self.connected = False

    def init(self, config, context):
        self.config = config
        self.context = context
        self.mqtt_client = hbmqtt.client.MQTTClient(config={'auto_reconnect': False})

    @asyncio.coroutine
    def loop(self):
        self.connected = False

        while self.running:
            if not self.connected:
                self.connected = yield from self.connect()
            try:
                message = yield from self.mqtt_client.deliver_message()
                packet = message.publish_packet
                topic = packet.variable_header.topic_name
                value = packet.payload.data.decode('utf-8')
                self.check_message(topic, value)
            except hbmqtt.client.ClientException as ce:
                LOG.error('Client exception: %s' % ce)
                self.connected = False
            except Exception as e:
                LOG.error('%s' % e)
                self.connected = False

            if not self.connected:
                yield from self.disconnect()
                yield from asyncio.sleep(1)

        yield from self.disconnect()

    @asyncio.coroutine
    def stop(self):
        self.running = False
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

    def check_message(self, topic, value):
        LOG.debug('got topic %s, message %s', topic, value)

        # common topic for item commands
        if topic.startswith(self.config['mqtt'].get('in_topic')):
            cmd = topic.split('/')[-1]

            if value:
                LOG.info('got command %s %s', cmd, value)
                self.context.item_command(cmd, value)
                return

        # items input topic
        for t in self.context.items:
            if t.input == 'mqtt:%s' % topic:
                self.context.set_item_value(t['name'], value)

        # signals
        for rule in self.context.rules:
            if rule.trigger is None or 'mqtt' not in rule.trigger:
                continue

            for v in rule.trigger['mqtt']:
                if match_topic(v['topic'], topic):
                    if 'payload' in v and v['payload'] != value:
                        continue
                    LOG.info('running rule %s on signal %s, val %s', rule.__class__.__name__, topic, value)
                    asyncio.async(rule.process_signal(topic, value), loop=self.context.loop)
                    break

    @asyncio.coroutine
    def wait_connected(self):
        while not self.connected:
            yield from asyncio.sleep(1)

            if not self.running:
                break

        return self.running

    @asyncio.coroutine
    def periodical_sender(self):
        if not self.config['mqtt'].get('out_topic'):
            LOG.warning('no out topic configured')
            return

        while self.running:
            for item in self.context.items:
                if not (yield from self.wait_connected()):
                    break

                t = self.send_time.get(item.name, 0)

                if time.time() - t <= self.config['mqtt'].get('send_time', 30):
                    yield from asyncio.sleep(0.1)
                    continue

                yield from self.send_out(item, False)

                yield from asyncio.sleep(0.1)

    @asyncio.coroutine
    def send_out(self, item, changed):
        topic = self.config['mqtt'].get('out_topic')

        if not topic:
            return

        t = self.send_time.get(item.name, 0)

        if time.time() - t < self.config['mqtt'].get('min_send_time', 30) and not changed:
            return

        self.send_time[item.name] = time.time()

        try:
            val = str(item.value).encode('UTF-8') if item.value is not None else bytes()

            if not (yield from self.wait_connected()):
                return

            yield from self.mqtt_client.publish(topic.format(item.name), val, 0)

            if changed:
                yield from self.mqtt_client.publish(topic.format(item.name), val, 1)
        except:
            LOG.exception('send out error: %s:%s', item.name, item.value)

    def format_simple_cmd(self, d, cmd):
        return dict(topic=d['topic'], payload=cmd, qos=d.get('qos', 0))

    @asyncio.coroutine
    def command(self, args):
        if not (yield from self.wait_connected()):
            return

        yield from self.mqtt_client.publish(args['topic'], args['payload'].encode('UTF-8'), args.get('qos', 0))
