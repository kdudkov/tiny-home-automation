# coding: UTF-8

import logging

from jinja2 import Template

LOG = logging.getLogger('mahno.' + __name__)


def log_service(data, context):
    if 'message' in data:
        t = Template(data['message'])
        logging.getLogger('mahno.__rules').info(t.render(context))
    else:
        logging.getLogger('mahno.__rules').warning('empty message')
