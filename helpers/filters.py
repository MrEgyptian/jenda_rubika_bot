from rubpy.bot.filters import Filter, commands as CommandFilter


class OwnerCommand(Filter):
    def __init__(self, *commands, prefixes=None, case_sensitive=False, owners=None):
        command_names = []
        for command in commands:
            if isinstance(command, (list, tuple, set)):
                command_names.extend(command)
            else:
                command_names.append(command)

        self.command_filter = CommandFilter(
            command_names,
            prefixes=prefixes or ["/"],
            case_sensitive=case_sensitive,
        )
        self.owners = {
            str(owner).strip()
            for owner in (owners or [])
            if str(owner).strip()
        }

    async def check(self, update):
        if not await self.command_filter.check(update):
            return False

        chat_id = getattr(update, "chat_id", None)
        author_guid = getattr(update, "author_guid", None)

        return str(chat_id) in self.owners or str(author_guid) in self.owners