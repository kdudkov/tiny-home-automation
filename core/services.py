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
def slack_service(data, rule_context, context):
    if 'message' not in data:
        RULES_LOG.warning('empty message')
        return

    if not context.config.get('slack', {}).get('url'):
        RULES_LOG.warning('slack in not configured')
        return

    session = yield from aiohttp.ClientSession(loop=context.loop)
    try:
        url = context.config['slack']['url']
        t = Template(data['message']).render(rule_context)
        r = yield from session.post(url, data=json.dumps(dict(message=t)), timeout=60)

        if r.status != 200:
            text = yield from r.text()
            RULES_LOG.error('slack error %s %s', r.status, text)
    finally:
        yield from session.close()
