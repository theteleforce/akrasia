from asyncio import sleep
from discord import Game
from random import choice


async def status_loop(client):
    while True:
        if client.ws is None: # don't throw errors while the client is still starting up
            await sleep(5)
        else:
            await client.change_presence(activity=Game(name=choice(client.status_list)))
            await sleep(client.change_status_timer)
