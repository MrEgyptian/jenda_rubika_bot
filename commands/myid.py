from rubpy.bot import filters



def register(app):
    @app.on_update(filters.commands("myid"))
    async def myid_command(client, message):
     user_id = message.chat_id
     await message.reply(f"your id: `{user_id}`")
