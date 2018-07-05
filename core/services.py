# coding: UTF-8

import asyncio
import json
import logging

import aiohttp
from jinja2 import Template

LOG = logging.getLogger('mahno.' + __name__)
RULES_LOG = logging.getLogger('mahno.core.rules')


def log_service(data, context):
    if 'message' in data:
        t = Template(data['message'])
        RULES_LOG.info(t.render(context))
    else:
        RULES_LOG.warning('empty message')


@asyncio.coroutine
def slack_service(data, context):
    if not 'message' in data:
        RULES_LOG.warning('empty message')
        return

    if not context.config.get('slack', {}).get('url'):
        RULES_LOG.warning('slack in not configured')
        return

    session = yield from aiohttp.ClientSession(loop=context.loop)
    try:
        url = context.config['slack']['url']
        t = Template(data['message']).render(context)
        r = yield from session.post(url, data=json.dumps(dict(message=t)), timeout=60)
        text = yield from r.text()
        if r.status != 200:
            RULES_LOG.error('slack error %s %s', r.status, text)
    finally:
        yield from session.close()
