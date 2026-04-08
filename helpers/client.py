from rubpy.bot.models import InlineMessage, MessageId, Update


async def _edit_alias(self, text, *args, **kwargs):
    new_message = getattr(self, "new_message", None)
    if new_message is not None:
        edit_text = getattr(new_message, "edit_text", None)
        if callable(edit_text):
            return await edit_text(text, *args, **kwargs)

    edit_text = getattr(self, "edit_text", None)
    if callable(edit_text):
        return await edit_text(text, *args, **kwargs)

    reply = getattr(self, "reply", None)
    if callable(reply):
        return await reply(text)

    return None


if not hasattr(MessageId, "edit"):
    async def _message_id_edit(self, text, *args, **kwargs):
        edit_text = getattr(self, "edit_text", None)
        if callable(edit_text):
            return await edit_text(text, *args, **kwargs)
        return None

    MessageId.edit = _message_id_edit


if not hasattr(Update, "edit"):
    Update.edit = _edit_alias


if not hasattr(InlineMessage, "edit"):
    InlineMessage.edit = _edit_alias
