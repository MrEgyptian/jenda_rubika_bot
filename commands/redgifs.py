import asyncio
from pathlib import Path
from urllib.parse import quote_plus

from rubpy.bot import filters
import asyncio
from pathlib import Path
from urllib.parse import quote_plus

from rubpy.bot import filters

try:
      import yt_dlp
except Exception:  # pragma: no cover
      yt_dlp = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
GIF_DIR = PROJECT_ROOT / "downloads" / "gifs"


def _search_redgifs(query, limit=5):
      if yt_dlp is None:
            return []

      options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
      }
      if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
            options["cookiefile"] = str(COOKIES_FILE)

      search_url = f"https://www.redgifs.com/browse?tags={quote_plus(query)}"
      with yt_dlp.YoutubeDL(options) as ydl:
            result = ydl.extract_info(search_url, download=False)
            entries = result.get("entries") or []

      gifs = []
      for item in entries:
            if not item:
                  continue
            gifs.append(
                  {
                        "title": item.get("title") or "Unknown title",
                        "url": item.get("url") or item.get("webpage_url") or "",
                        "duration": item.get("duration") or 0,
                        "uploader": item.get("uploader") or "Unknown",
                  }
            )
            if len(gifs) >= limit:
                  break
      return gifs


def _download_redgif(url):
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
      if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
            options["cookiefile"] = str(COOKIES_FILE)

      with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if info.get("entries"):
                  info = info["entries"][0]

            file_path = Path(ydl.prepare_filename(info))
            if file_path.exists():
                  return file_path

            info_id = info.get("id")
            if info_id:
                  for candidate in GIF_DIR.glob(f"*{info_id}*"):
                        if candidate.is_file():
                              return candidate

      return None


async def _search_redgifs_async(query, limit=5, timeout=25):
      return await asyncio.wait_for(
            asyncio.to_thread(_search_redgifs, query, limit),
            timeout=timeout,
      )


async def _download_redgif_async(url, timeout=90):
      return await asyncio.wait_for(
            asyncio.to_thread(_download_redgif, url),
            timeout=timeout,
      )


async def _safe_send_file(message, file_path, caption):
      try:
          try:
            await message.reply_video(file_path, text=caption)
            return True
          except Exception:
            await message.reply_file(file_path, text=caption)
            return True
      except Exception:
            try:
                  await message.reply(f"Found result but failed to upload file.\n{caption}")
                  return False
            except Exception:
                  return False


def _extract_query(message):
      text = _get_text(message)
      parts = text.split(maxsplit=1)
      if len(parts) < 2:
            return ""
      print(f"Extracted query: {parts[1].strip()}")
      return parts[1].strip()


def _get_text(message):
      new_message = getattr(message, "new_message", None)
      if not new_message:
            return ""
      return (getattr(new_message, "text", "") or "").strip()


def register(app):
      @app.on_update(filters.commands(["redgifs", "rg", "redgif", "red"]))
      async def redgifs_search_command(client, message):
            if yt_dlp is None:
                  await message.reply("yt-dlp is not installed. Install it with: pip install yt-dlp")
                  return

            query = _extract_query(message)
            if not query:
                  await message.reply("Usage: /redgifs <search query>")
                  return

            await message.reply(f"Searching RedGifs for {query}...")

            try:
                  gifs = await _search_redgifs_async(query, limit=5)
            except asyncio.TimeoutError:
                  await message.reply("Search timed out. Try again.")
                  return
            except Exception as exc:
                  await message.reply(f"Search failed: {exc}")
                  return

            if not gifs:
                  await message.reply("No results found.")
                  return
            for idx, item in enumerate(gifs, start=1):
                  title = item["title"]
                  uploader = item["uploader"]
                  duration = item["duration"]
                  url = item["url"]
                  await message.reply(f"{idx}. {title}\nby: {uploader}\nDuration: {duration} seconds\n{url}")
                  try:
                      file_path = await _download_redgif_async(item["url"])
                  except asyncio.TimeoutError:
                      await message.reply("Download timed out. Try another query.")
                      continue
                  except Exception as exc:
                      await message.reply(f"Download failed: {exc}")
                      continue
                  if not file_path:
                      await message.reply("Found result but could not download media.")
                      continue
                  caption = f"{item['title']}\nby: {item['uploader']}"
                  sent = await _safe_send_file(message, file_path, caption)
                  if not sent:
                      continue

            await message.reply("Sent from RedGifs.")


if __name__ == "__main__":
      results = _search_redgifs("funny cat", limit=3)
      for result in results:
            print(result)