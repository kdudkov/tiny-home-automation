import asyncio
import json
import os

from aiohttp import web

BASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class Server(web.Application):
    context = None

    def init(self):
        self.router.add_static('/static/', os.path.join(BASE_PATH, 'static'), name='static')
        self.router.add_route('GET', '/', self.index)
        self.router.add_route('GET', '/2', self.index2)
        self.router.add_route('GET', '/items/', self.get_items)
        self.router.add_route('GET', '/items/{tag}', self.get_items)
        self.router.add_route('GET', '/item/{name}', self.get_item)
        self.router.add_route('GET', '/item/{name}/', self.get_item)
        self.router.add_route('PUT', '/item/{name}', self.put_item)
        self.router.add_route('PUT', '/item/{name}/', self.put_item)
        self.router.add_route('POST', '/item/{name}', self.post_item)
        self.router.add_route('POST', '/item/{name}/', self.post_item)

    def json_resp(self, s):
        headers = {'content-type': 'application/json'}
        return web.Response(body=json.dumps(s).encode('UTF-8'), headers=headers)

    def resp_404(self, s):
        return web.Response(body=s.encode('UTF-8'), status=404)

    @asyncio.coroutine
    def index(self, request):
        return web.Response(body=open('static/index.html').read().encode('UTF-8'))

    @asyncio.coroutine
    def index2(self, request):
        return web.Response(body=open('static/index2.html').read().encode('UTF-8'))

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
        val = yield from request.payload.read()
        self.context.command(name, val.decode('utf-8'))
        return self.json_resp(item.to_dict())


def get_app(context):
    s = Server()
    s.context = context
    s.init()

    return s
