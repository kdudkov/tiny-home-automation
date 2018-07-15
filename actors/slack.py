import asyncio
import json
import logging

import aiohttp

from actors import AbstractActor

LOG = logging.getLogger('mahno.' + __name__)


class SlackActor(AbstractActor):
    name = 'slack'

    def __init__(self, url):
        self.url = url

    def init(self, config, context):
        self.config = config
        self.context = context

    @asyncio.coroutine
    def send_message(self, msg):
        session = aiohttp.ClientSession(loop=self.context.loop)
        try:
            r = yield from session.post(self.url, data=json.dumps(dict(text=msg)), timeout=60)

            if r.status != 200:
                text = yield from r.text()
                LOG.error('slack error %s %s', r.status, text)
        finally:
            yield from session.close()

    @asyncio.coroutine
    def command(self, args):
        yield from self.send_message(args)
