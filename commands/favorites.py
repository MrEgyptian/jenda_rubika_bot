from rubpy.bot import filters
from helpers.favorites import (
    add_favorite,
    remove_favorite,
    get_favorites_text,
    get_user_favorites,
)


def _extract_url_from_command(message):
    """Extract URL from command arguments."""
    new_message = getattr(message, "new_message", None)
    if not new_message:
        return None
    
    text = getattr(new_message, "text", "")
    parts = text.split(maxsplit=2)  # /add_favorite <url> [title]
    
    if len(parts) < 2:
        return None
    
    return parts[1]


def _extract_command_args(message):
    """Extract all arguments after command."""
    new_message = getattr(message, "new_message", None)
    if not new_message:
        return []
    
    text = getattr(new_message, "text", "")
    parts = text.split(maxsplit=1)
    
    if len(parts) < 2:
        return []
    
    return parts[1].split(maxsplit=1)


def _get_user_id(message):
    """Extract user ID from message."""
    user_id = (
        getattr(message, "author_guid", None) or
        getattr(message, "chat_id", None)
    )
    return str(user_id) if user_id else "unknown"


def register(app):
    @app.on_update(filters.commands("add_favorite"))
    async def add_favorite_command(client, message):
        user_id = _get_user_id(message)
        args = _extract_command_args(message)
        
        if not args:
            await message.reply("Usage: /add_favorite <video_url> [optional_title]")
            return
        
        url = args[0]
        title = args[1] if len(args) > 1 else url
        
        if add_favorite(user_id, url, title):
            await message.reply(f"✅ Favorite added!\n{title}")
        else:
            await message.reply("This URL is already in your favorites!")

    @app.on_update(filters.commands("remove_favorite"))
    async def remove_favorite_command(client, message):
        user_id = _get_user_id(message)
        url = _extract_url_from_command(message)
        
        if not url:
            await message.reply("Usage: /remove_favorite <video_url>")
            return
        
        if remove_favorite(user_id, url):
            await message.reply("✅ Favorite removed!")
        else:
            await message.reply("This URL is not in your favorites.")

    @app.on_update(filters.commands("my_favorites"))
    async def my_favorites_command(client, message):
        user_id = _get_user_id(message)
        text = get_favorites_text(user_id)
        await message.reply(text)

    @app.on_update(filters.commands("clear_favorites"))
    async def clear_favorites_command(client, message):
        user_id = _get_user_id(message)
        favorites = get_user_favorites(user_id)
        
        if not favorites:
            await message.reply("You have no favorites to clear.")
            return
        
        await message.reply(
            f"Are you sure? You have {len(favorites)} saved favorites.\n"
            "Use /confirm_clear to proceed, or /cancel to stop."
        )
