from rubpy.bot import filters


def register(app):
    @app.on_update(filters.commands("start"))
    async def start_command(client, message):
        await message.reply(
            "Welcome to the bot. Use /help to see available commands."
        )
