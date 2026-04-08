from rubpy.bot.models import InlineMessage, MessageId, Update


async def _edit_alias(self, text, *args, **kwargs):
    return await self.edit_text(text, *args, **kwargs)


if not hasattr(MessageId, "edit"):
    async def _message_id_edit(self, text, *args, **kwargs):
        return await self.edit_text(text)

    MessageId.edit = _message_id_edit


if not hasattr(Update, "edit"):
    Update.edit = _edit_alias


if not hasattr(InlineMessage, "edit"):
    InlineMessage.edit = _edit_alias
