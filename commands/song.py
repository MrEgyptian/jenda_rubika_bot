from pathlib import Path
import asyncio

from rubpy.bot import filters

try:
	import yt_dlp
except Exception:  # pragma: no cover
	yt_dlp = None


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
MUSIC_DIR = PROJECT_ROOT / "downloads" / "music"


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


def _search_youtube_music(query, limit=5):
	options = {
		"quiet": True,
		"no_warnings": True,
		"extract_flat": True,
		"skip_download": True,
	}
	if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
		options["cookiefile"] = str(COOKIES_FILE)

	with yt_dlp.YoutubeDL(options) as ydl:
		result = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
		entries = result.get("entries") or []

	songs = []
	for item in entries:
		if not item:
			continue
		songs.append(
			{
				"title": item.get("title") or "Unknown title",
				"url": item.get("url") or item.get("webpage_url") or "",
				"duration": item.get("duration") or 0,
				"uploader": item.get("uploader") or "Unknown",
			}
		)
	return songs


def _download_song(query_or_url):
	MUSIC_DIR.mkdir(parents=True, exist_ok=True)
	output_template = str(MUSIC_DIR / "%(title).120s-%(id)s.%(ext)s")
	source = query_or_url
	if not (query_or_url.startswith("http://") or query_or_url.startswith("https://")):
		source = f"ytsearch1:{query_or_url}"

	options = {
		"outtmpl": output_template,
		"noplaylist": True,
		"quiet": True,
		"no_warnings": True,
		"format": "bestaudio[ext=m4a]/bestaudio",
	}
	if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
		options["cookiefile"] = str(COOKIES_FILE)

	with yt_dlp.YoutubeDL(options) as ydl:
		info = ydl.extract_info(source, download=True)
		if info.get("entries"):
			info = info["entries"][0]
		file_path = Path(ydl.prepare_filename(info))
		return info, file_path


def _format_duration(seconds):
	if not seconds:
		return "--:--"
	minutes, sec = divmod(int(seconds), 60)
	hours, minutes = divmod(minutes, 60)
	if hours:
		return f"{hours}:{minutes:02d}:{sec:02d}"
	return f"{minutes}:{sec:02d}"


async def _search_youtube_music_async(query, limit=5, timeout=45):
	return await asyncio.wait_for(
		asyncio.to_thread(_search_youtube_music, query, limit),
		timeout=timeout,
	)


async def _download_song_async(query_or_url, timeout=300):
	return await asyncio.wait_for(
		asyncio.to_thread(_download_song, query_or_url),
		timeout=timeout,
	)


def register(app):
	@app.on_update(filters.commands(["song", "search",'yt_song','ytsearch','yt']))
	async def song_search_command(client, message):
		if yt_dlp is None:
			await message.reply("yt-dlp is not installed. Install it with: pip install yt-dlp")
			return

		query = _extract_query(message)
		if not query:
			await message.reply("Usage: /song <name or artist>")
			return

		try:
			songs = await _search_youtube_music_async(query)
		except asyncio.TimeoutError:
			await message.reply("Search timed out. Try a shorter query.")
			return
		except Exception as exc:
			await message.reply(f"Search failed: {exc}")
			return

		if not songs:
			await message.reply("No results found.")
			return

		lines = [f"Top results for: {query}", ""]
		for idx, song in enumerate(songs, start=1):
			lines.append(
				f"{idx}. {song['title']} | {song['uploader']} | {_format_duration(song['duration'])}"
			)
			lines.append(f"   {song['url']}")

		lines.append("")
		lines.append("Download with: /songdl <url or search text>")
		await message.reply("\n".join(lines))

	@app.on_update(filters.commands(["songdl", "songdownload"]))
	async def song_download_command(client, message):
		if yt_dlp is None:
			await message.reply("yt-dlp is not installed. Install it with: pip install yt-dlp")
			return

		query = _extract_query(message)
		if not query:
			await message.reply("Usage: /songdl <url or song name>")
			return

		await message.reply("Downloading audio, please wait...")
		try:
			info, file_path = await _download_song_async(query)
		except asyncio.TimeoutError:
			await message.reply("Download timed out. Try another song.")
			return
		except Exception as exc:
			await message.reply(f"Download failed: {exc}")
			return

		if not file_path.exists():
			await message.reply("Download completed but file was not found on disk.")
			return

		title = info.get("title") or file_path.stem
		await message.reply_music(str(file_path), text=f"Downloaded: {title}")
