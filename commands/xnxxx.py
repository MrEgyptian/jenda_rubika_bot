import asyncio
import inspect

from rubpy.bot import filters

try:
    from xnxx_api import Client
except Exception:  # pragma: no cover
    Client = None


client = Client() if Client else None


def _get_text(message):
    new_message = getattr(message, "new_message", None)
    if not new_message:
        return ""
    return (getattr(new_message, "text", "") or "").strip()


def _extract_query(message):
    text = _get_text(message)
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip()


async def _maybe_await(value):
    if inspect.isawaitable(value):
        return await value
    return value


def _normalize_video(video):
    return {
        "title": getattr(video, "title", None) or "Unknown title",
        "url": getattr(video, "url", None) or "",
        "duration": getattr(video, "duration", None),
        "uploader": getattr(video, "uploader", None) or "Unknown",
    }


def _format_duration(value):
    if value is None:
        return "--:--"
    try:
        total = int(value)
    except Exception:
        return str(value)

    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


async def _search_videos(query, limit=5):
    if client is None:
        return []

    result = await client.search(query)
    videos = await _maybe_await(getattr(result, "videos", []))
    if videos is None:
        return []

    normalized = []
    for video in videos:
        normalized.append(_normalize_video(video))
        if len(normalized) >= limit:
            break
    return normalized


async def _search_videos_with_timeout(query, limit=5, timeout=30):
    return await asyncio.wait_for(_search_videos(query, limit), timeout=timeout)


def register(app):
    @app.on_update(filters.commands(["xnxx", "xnxxsearch", "xnxx_video", "searchvideo",'sx']))
    async def search_video_command(client_obj, message):
        if Client is None or client is None:
            await message.reply(" xnxx_api is not installed. Install it with: pip install xnxx_api")
            return

        query = _extract_query(message)
        if not query:
            await message.reply("Usage: /searchvideo <query>")
            return

        await message.reply("Searching videos...")

        try:
            videos = await _search_videos_with_timeout(query, limit=5)
        except asyncio.TimeoutError:
            await message.reply("Search timed out. Try a shorter query.")
            return
        except Exception as exc:
            await message.reply(f"Search failed: {exc}")
            return

        if not videos:
            await message.reply("No results found.")
            return

        lines = [f"Top results for: {query}", ""]
        for idx, video in enumerate(videos, start=1):
            lines.append(
                f"{idx}. {video['title']} | {video['uploader']} | {_format_duration(video['duration'])}"
            )
            lines.append(f"   {video['url']}")

        await message.reply("\n".join(lines))