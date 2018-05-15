import asyncio
import json
import logging
import os

from aiohttp import web

BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LOG = logging.getLogger('mahno.' + __name__)


class WebSocket(web.View):
    @asyncio.coroutine
    def get(self):
        ws = web.WebSocketResponse()
        h = hash(ws)
        yield from ws.prepare(self.request)
        LOG.info('ws client connected, %s clients', len(self.request.app['websockets']) + 1)
        self.request.app['websockets'][h] = {'ws': ws, 'tag': ''}

        try:
            while 1:
                msg = yield from ws.receive_str()
                if ';' in msg:
                    tag, name, cmd = msg.split(';')
                    self.request.app['websockets'][h]['tag'] = tag
                    self.request.app.context.item_command(name, cmd)
                else:
                    self.request.app['websockets'][h]['tag'] = msg
                    LOG.info('got tag %s for %s', msg, h)
                LOG.debug('ws msg: %s', msg)
                yield from asyncio.sleep(0.01)
        finally:
            if not ws.closed:
                try:
                    ws.close()
                except:
                    pass
            del(self.request.app['websockets'][h])
            LOG.debug('websocket connection closed')


class Server(web.Application):
    context = None

    def init(self):
        self['websockets'] = {}
        self.router.add_static('/static/', os.path.join(BASE_PATH, 'static'), name='static')
        self.router.add_route('GET', '/ws', WebSocket, name='chat')
        self.router.add_route('GET', '/', self.index)
        self.router.add_route('GET', '/2', self.index2)
        self.router.add_route('GET', '/items', self.get_items)
        self.router.add_route('GET', '/items/', self.get_items)
        self.router.add_route('GET', '/items/{name}', self.get_item)
        self.router.add_route('GET', '/items/{name}/', self.get_item)
        self.router.add_route('GET', '/items/{name}/value', self.get_item_value)
        self.router.add_route('GET', '/items/{name}/value/', self.get_item_value)
        self.router.add_route('PUT', '/items/{name}', self.put_item)
        self.router.add_route('PUT', '/items/{name}/', self.put_item)
        self.router.add_route('POST', '/items/{name}', self.post_item)
        self.router.add_route('POST', '/items/{name}/', self.post_item)
        self.router.add_route('GET', '/rules', self.get_rules)
        self.router.add_route('GET', '/rules/', self.get_rules)

    def get_app(self, config, loop):
        LOG.info('server on port %s', config['server']['port'])
        return loop.create_server(self.make_handler(loop=loop), host='0.0.0.0', port=config['server']['port'])

    def json_resp(self, s):
        headers = {'Content-Type': 'application/json'}
        return web.Response(body=json.dumps(s).encode('UTF-8'), headers=headers)

    def resp_404(self, s):
        return web.Response(body=s.encode('UTF-8'), status=404)

    @asyncio.coroutine
    def index(self, request):
        return web.Response(body=open('static/index.html').read().encode('UTF-8'), content_type='text/html')

    @asyncio.coroutine
    def index2(self, request):
        return web.Response(body=open('static/index2.html').read().encode('UTF-8'), content_type='text/html')

    @asyncio.coroutine
    def get_items(self, request):
        tag = request.match_info.get('tag')
        return self.json_resp(self.context.items.as_list(tag))

    @asyncio.coroutine
    def get_item(self, request):
        name = request.match_info['name']
        item = self.context.items.get_item(name)
        if not item:
            return self.resp_404('item %s not found' % name)
        return self.json_resp(item.to_dict())

    @asyncio.coroutine
    def get_item_value(self, request):
        name = request.match_info['name']
        item = self.context.items.get_item(name)
        if not item:
            return self.resp_404('item %s not found' % name)
        return web.Response(body=str(item.value).encode('UTF-8'))

    @asyncio.coroutine
    def put_item(self, request):
        name = request.match_info['name']
        item = self.context.items.get_item(name)
        if not item:
            return self.resp_404('')
        val = yield from request.payload.read()
        self.context.set_item_value(name, val.decode('utf-8'))
        return self.json_resp(item.to_dict())

    @asyncio.coroutine
    def post_item(self, request):
        name = request.match_info['name']
        item = self.context.items.get_item(name)
        if not item:
            return self.resp_404('')
        val = yield from request.content.read()
        self.context.item_command(name, val.decode('utf-8'))
        return self.json_resp(item.to_dict())

    @asyncio.coroutine
    def get_rules(self, request):
        res = []
        for r in self.context.rules:
            res.append(r.to_dict())

        return self.json_resp(res)

    @asyncio.coroutine
    def on_check(self, item, changed):
        s = json.dumps(item.to_dict())
        for ws in self['websockets'].values():
            if ws['tag'] and ws['tag'] in item.tags:
                try:
                    yield from ws['ws'].send_str(s)
                except:
                    pass


def get_app(context, config, loop):
    s = Server(loop=loop)
    s.context = context
    s.init()
    context.add_cb('oncheck', s.on_check)
    return s.get_app(config, loop)
