# coding: UTF-8

import asyncio
import logging

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

    t = Template(data['message']).render(rule_context)
    context.command('slack', t)
