from configparser import ConfigParser
from importlib import import_module
from pathlib import Path
from rubpy.bot import BotClient
import asyncio

config = ConfigParser()
config.read("config.ini")

app = BotClient(config.get("bot", "token"))

owners_value = config.get("bot", "owners", fallback="")
app.owners = {
    owner.strip()
    for owner in owners_value.split(",")
    if owner.strip()
}


def register_commands(app: BotClient) -> None:
	commands_dir = Path(__file__).parent / "commands"
	for file_path in sorted(commands_dir.glob("*.py")):
		if file_path.stem.startswith("_"):
			continue

		module = import_module(f"commands.{file_path.stem}")
		register = getattr(module, "register", None)
		if callable(register):
			register(app)
def hook_register(func, module_name):
    async def wrapper(client, message):
        print(f"[HOOK] {module_name}.{func.__name__}")
        print(f"[HOOK] chat_id =", message.chat_id)
        return await func(client, message)
    return wrapper

def register_owner_commands(app: BotClient) -> None:
    commands_dir = Path(__file__).parent / "owner_commands"
    for file_path in sorted(commands_dir.glob("*.py")):
        if file_path.stem.startswith("_"):
            continue
        module = import_module(f"owner_commands.{file_path.stem}")
        register = getattr(module, "register", None)
        if callable(register):
            #module.register = hook_register(register, file_path.stem)

            register(app)
async def main():
    
    register_commands(app)
    register_owner_commands(app)
    print("Bot is running...")
    me=await app.get_me()
    print(dir(me))
    print(f"Logged in as: [{me.bot_title}](@{me.username})")
    await app.run()
if __name__ == "__main__":
    
    asyncio.run(main())