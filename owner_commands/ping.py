import time
from helpers.filters import OwnerCommand


def register(app):
    @app.on_update(OwnerCommand("ping", owners=app.owners))
    async def ping_command(client, message):
        start = time.perf_counter()

        m=await message.reply("Sending ping...")
        end = time.perf_counter()
        latency = (end - start) * 1000
        await m.edit_text(f"Latency: {latency:.2f} ms")
