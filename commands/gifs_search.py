import asyncio
from pathlib import Path
from urllib.parse import quote_plus

from rubpy.bot import filters

try:
    import yt_dlp
except Exception:  # pragma: no cover
    yt_dlp = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GIF_DIR = PROJECT_ROOT / "downloads" / "gifs"
GIF_SEARCH_URLS = (
    "https://giphy.com/search/{query}",
    "https://tenor.com/search/{query}-gifs",
)


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


async def _safe_edit(message, text):
    edit = getattr(message, "edit", None)
    if callable(edit):
        return await edit(text)

    edit_text = getattr(message, "edit_text", None)
    if callable(edit_text):
        return await edit_text(text)

    reply = getattr(message, "reply", None)
    if callable(reply):
        return await reply(text)

    return None


def _build_search_urls(query):
    encoded_query = quote_plus(query)
    return [template.format(query=encoded_query) for template in GIF_SEARCH_URLS]


def _search_gifs(query, limit=5):
    if yt_dlp is None:
        return []

    options = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "skip_download": True,
    }

    gifs = []
    with yt_dlp.YoutubeDL(options) as ydl:
        for search_url in _build_search_urls(query):
            try:
                result = ydl.extract_info(search_url, download=False)
            except Exception:
                continue

            entries = result.get("entries") or []
            for item in entries:
                if not item:
                    continue

                url = item.get("url") or item.get("webpage_url") or ""
                if not url:
                    continue

                gifs.append(
                    {
                        "title": item.get("title") or "GIF",
                        "url": url,
                        "webpage_url": item.get("webpage_url") or url,
                    }
                )
                if len(gifs) >= limit:
                    return gifs

    return gifs


def _download_gif(url):
    if yt_dlp is None:
        return None

    GIF_DIR.mkdir(parents=True, exist_ok=True)
    output_template = str(GIF_DIR / "%(title).80s-%(id)s.%(ext)s")

    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "format": "bestvideo[ext=mp4][height<=720]/best[ext=mp4]/best",
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if info.get("entries"):
            info = info[0]

        file_path = Path(ydl.prepare_filename(info))
        if file_path.exists():
            return file_path

        info_id = info.get("id")
        if info_id:
            for candidate in GIF_DIR.glob(f"{info_id}.*"):
                if candidate.is_file():
                    return candidate

    return None


async def _search_gifs_async(query, limit=5, timeout=20):
    return await asyncio.wait_for(
        asyncio.to_thread(_search_gifs, query, limit),
        timeout=timeout,
    )


async def _download_gif_async(url, timeout=60):
    return await asyncio.wait_for(
        asyncio.to_thread(_download_gif, url),
        timeout=timeout,
    )


def register(app):
    @app.on_update(filters.commands(["gifs", "gifsearch", "gif"]))
    async def gifs_search_command(client, message):
        if yt_dlp is None:
            await message.reply("yt-dlp is not installed. Install it with: pip install yt-dlp")
            return

        query = _extract_query(message)
        if not query:
            await message.reply("Usage: /gifs <query>")
            return

            await _safe_edit(message, "Searching for GIFs with yt-dlp...")

        try:
            gifs = await _search_gifs_async(query, limit=5)
            if not gifs:
                await _safe_edit(message, "No GIFs found.")
                return

            gif = gifs[0]
            file_path = await _download_gif_async(gif["url"])
            if file_path:
                await message.reply_file(file_path, caption=gif["title"])
                await _safe_edit(message, "GIF sent.")
                return

            lines = [f"{idx}. {item['title']}" for idx, item in enumerate(gifs, start=1)]
            lines.append("")
            lines.append("Search found results, but sending failed.")
            await _safe_edit(message, "\n".join(lines))
        except asyncio.TimeoutError:
            await _safe_edit(message, "Search timed out.")
        except Exception as exc:
            await _safe_edit(message, f"Error: {exc}")