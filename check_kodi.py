import asyncio

from actors.kodi import Kodi

if __name__ == '__main__':
    async def st(k):
        await k.init()

        res = await k.get_status()
        print(res)
        await k.stop()


    print(asyncio.iscoroutinefunction(st))
    loop = asyncio.get_event_loop()
    k = Kodi('127.0.0.1:8080', loop)
    loop.run_until_complete(st(k))
