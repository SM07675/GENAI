import asyncio
import websockets
import json

async def test():
    async with websockets.connect('ws://127.0.0.1:8765/ws') as ws:
        await ws.send(json.dumps({'type':'manual_wake'}))
        print("Sent manual_wake")
        while True:
            msg = await ws.recv()
            print("Received:", msg)

asyncio.run(test())
