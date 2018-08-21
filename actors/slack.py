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

    async def send_message(self, msg):
        session = aiohttp.ClientSession(loop=self.context.loop)
        try:
            r = await session.post(self.url, data=json.dumps(dict(text=msg)), timeout=60)

            if r.status != 200:
                text = await r.text()
                LOG.error('slack error %s %s', r.status, text)
        finally:
            await session.close()

    async def command(self, args):
        await self.send_message(args)
