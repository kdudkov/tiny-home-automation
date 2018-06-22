import asyncio

from actors.kodi import Kodi

if __name__ == '__main__':
    @asyncio.coroutine
    def st(k):
        yield from k.init()

        res = yield from k.get_status()
        print(res)


    loop = asyncio.get_event_loop()
    k = Kodi('127.0.0.1:8080', loop)
    loop.run_until_complete(st(k))
