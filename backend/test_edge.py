import asyncio
import edge_tts

async def test():
    comm = edge_tts.Communicate('Hello world, I am Genie!', 'en-US-JennyNeural')
    async for msg in comm.stream():
        print(msg)

asyncio.run(test())
