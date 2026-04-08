from rubpy.bot import filters
import asyncio
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

try:
    import yt_dlp
except Exception:  # pragma: no cover
    yt_dlp = None


HELP_TEXT = (
    "Available commands:\n"
    "/start - Welcome message and overview of the bot\n"
    "/help - Instructions on how to use the bot\n"
    "/download - Initiate the video download process\n"
    "/download_audio - Download audio from a video URL\n"
    "/song <name> - Search YouTube music\n"
    "/songdl <url or name> - Download a song\n"
    "/supported_sources - List of supported video sources\n"
    "/settings - Customize your experience (if applicable)\n"
    "\nFavorites:\n"
    "/add_favorite <url> [title] - Save a video URL\n"
    "/my_favorites - View all saved favorites\n"
    "/remove_favorite <url> - Remove a favorite\n"
    "/clear_favorites - Clear all favorites\n"
    "\nMore:\n"
    "/history - View your download history\n"
    "/contact - Get in touch for support or feedback\n"
    "/faq - Frequently asked questions about the bot\n"
    "/support - Support and donation information"
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COOKIES_FILE = PROJECT_ROOT / "cookies.txt"
MAX_UPLOAD_PART_SIZE = 30 * 1024 * 1024


def _extract_command_parts(message):
    print("Extracting command parts from message:", message)
    new_message = getattr(message, "new_message", None)
    if new_message:
        text = getattr(new_message, "text", "")
        print("Extracted text from new_message:", text)
        parts = text.split()
        print("Extracted parts from new_message:", parts)
        if isinstance(parts, list):
            return parts
    return None


def _is_valid_url(value):
    try:
        parsed = urlparse(value)
    except Exception:
        return False

    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _split_file_into_parts(file_path, max_part_size=MAX_UPLOAD_PART_SIZE):
    file_path = Path(file_path)
    if file_path.stat().st_size <= max_part_size:
        return [file_path]

    if shutil.which("ffmpeg"):
        parts = _split_file_with_ffmpeg(file_path, max_part_size)
        if len(parts) > 1:
            return parts

    return _split_file_by_bytes(file_path, max_part_size)


def _split_file_by_bytes(file_path, max_part_size=MAX_UPLOAD_PART_SIZE):
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    if file_size <= max_part_size:
        return [file_path]

    parts_dir = file_path.parent / f"{file_path.stem}_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    part_paths = []
    with file_path.open("rb") as source:
        part_number = 1
        while True:
            chunk = source.read(max_part_size)
            if not chunk:
                break

            part_path = parts_dir / f"{file_path.stem}.part{part_number:03d}{file_path.suffix}"
            with part_path.open("wb") as part_file:
                part_file.write(chunk)

            part_paths.append(part_path)
            part_number += 1

    return part_paths


def _probe_duration_seconds(file_path):
    if not shutil.which("ffprobe"):
        return None

    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]

    try:
        output = subprocess.check_output(cmd, text=True).strip()
        duration = float(output)
        if duration > 0:
            return duration
    except Exception:
        return None

    return None


def _split_file_with_ffmpeg(file_path, max_part_size=MAX_UPLOAD_PART_SIZE):
    file_path = Path(file_path)
    file_size = file_path.stat().st_size
    if file_size <= max_part_size:
        return [file_path]

    duration = _probe_duration_seconds(file_path)
    if not duration:
        return [file_path]

    # Estimate segment time to target part size using average bytes per second.
    estimated_segment_time = max(1, int(duration * (max_part_size / file_size)))

    parts_dir = file_path.parent / f"{file_path.stem}_parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    output_pattern = parts_dir / f"{file_path.stem}.part%03d{file_path.suffix}"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(file_path),
        "-map",
        "0",
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_time",
        str(estimated_segment_time),
        "-reset_timestamps",
        "1",
        str(output_pattern),
    ]

    try:
        subprocess.run(cmd, check=True)
    except Exception:
        return [file_path]

    part_paths = sorted(parts_dir.glob(f"{file_path.stem}.part*{file_path.suffix}"))
    if len(part_paths) > 1:
        return part_paths

    return [file_path]


def _cleanup_paths(paths):
    for path in paths:
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass


async def _send_file_with_split(message, file_path, title, kind="video"):
    file_path = Path(file_path)
    part_paths = _split_file_into_parts(file_path)

    if len(part_paths) == 1:
        single_part = part_paths[0]
        if kind == "video":
            await _send_video_with_fallback(message, single_part, title)
            return
        if kind == "music":
            await _send_audio_with_fallback(message, single_part, title)
            return

        await message.reply_video(str(single_part), text=f"Download completed: {title}")
        return

    try:
        for index, part_path in enumerate(part_paths, start=1):
            caption = f"{title} - part {index}/{len(part_paths)}"
            print(f"Sending part {index}/{len(part_paths)}: {part_path}")
            try:
                await message.reply_video(str(part_path), text=caption)
            except Exception as exc:
                print(f"Failed to send part {index}: {exc}")
    finally:
        _cleanup_paths(part_paths)


def _download_with_ytdlp(video_url, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title).120s-%(id)s.%(ext)s")

    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "format": "mp4/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
    }

    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
        options["cookiefile"] = str(COOKIES_FILE)

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(video_url, download=True)
        file_path = ydl.prepare_filename(info)
        final_path = Path(file_path)

        if not final_path.exists():
            merged_path = final_path.with_suffix(".mp4")
            if merged_path.exists():
                final_path = merged_path

    return info, final_path


def _download_audio_with_ytdlp(video_url, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(output_dir / "%(title).120s-%(id)s.%(ext)s")

    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    if COOKIES_FILE.exists() and COOKIES_FILE.stat().st_size > 0:
        options["cookiefile"] = str(COOKIES_FILE)

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(video_url, download=True)
        file_path = ydl.prepare_filename(info)
        final_path = Path(file_path)

        mp3_path = final_path.with_suffix(".mp3")
        if mp3_path.exists():
            final_path = mp3_path

    return info, final_path


async def _download_with_ytdlp_async(video_url, output_dir, timeout=900):
    return await asyncio.wait_for(
        asyncio.to_thread(_download_with_ytdlp, video_url, output_dir),
        timeout=timeout,
    )


async def _download_audio_with_ytdlp_async(video_url, output_dir, timeout=900):
    return await asyncio.wait_for(
        asyncio.to_thread(_download_audio_with_ytdlp, video_url, output_dir),
        timeout=timeout,
    )


async def _send_audio_with_fallback(message, file_path, title):
    try:
        await message.reply_music(str(file_path), text=f"Audio downloaded: {title}")
        return
    except Exception as exc:
        print(f"reply_music failed: {exc}")

    try:
        await message.reply_file(str(file_path), text=f"Audio downloaded: {title}")
        return
    except Exception as exc:
        print(f"reply_file fallback failed: {exc}")

    await message.reply(
        f"Audio downloaded: {title}\n"
        f"Saved to: {file_path}\n"
        "Upload failed on server side; you can still access the local file."
    )


async def _send_video_with_fallback(message, file_path, title):
    try:
        await message.reply_video(str(file_path), text=f"Download completed: {title}")
        return
    except Exception as exc:
        print(f"reply_video failed: {exc}")

    try:
        await message.reply_video(str(file_path), text=f"Download completed: {title}")
        return
    except Exception as exc:
        print(f"reply_video fallback failed: {exc}")

    await message.reply(
        f"Download completed: {title}\n"
        f"Saved to: {file_path}\n"
        "Upload failed on server side; you can still access the local file."
    )


def register(app):
    @app.on_update(filters.commands("help"))
    async def help_command(client, message):
        await message.reply(HELP_TEXT)

    @app.on_update(filters.commands("download"))
    async def download_command(client, message):
        if yt_dlp is None:
            await message.reply(
                "yt-dlp is not installed. Install it with: pip install yt-dlp"
            )
            return

        parts = _extract_command_parts(message)
        print("Command parts:", parts)
        if not parts or len(parts) < 2:
            await message.reply("Usage: /download <video_url>")
            return

        video_url = parts[1].strip()
        if not _is_valid_url(video_url):
            await message.reply("Please send a valid URL starting with http:// or https://")
            return

        await message.reply("Downloading video, please wait...")

        output_dir = Path(__file__).resolve().parents[1] / "downloads"
        try:
            info, file_path = await _download_with_ytdlp_async(
                video_url,
                output_dir,
            )
        except asyncio.TimeoutError:
            await message.reply("Download timed out. Please try a shorter video.")
            return
        except Exception as exc:
            await message.reply(f"Download failed: {exc}")
            return

        title = info.get("title") or "video"
        if file_path.exists():
            await _send_file_with_split(message, file_path, title, kind="video")
        else:
            await message.reply(
                f"Download completed for: {title}\n"
                "But the final file path could not be confirmed."
            )

    @app.on_update(filters.commands(["download_audio",'audio','songdl','songdownload']))
    async def download_audio_command(client, message):
        if yt_dlp is None:
            await message.reply(
                "yt-dlp is not installed. Install it with: pip install yt-dlp"
            )
            return

        parts = _extract_command_parts(message)
        if not parts or len(parts) < 2:
            await message.reply("Usage: /download_audio <video_url>")
            return

        video_url = parts[1].strip()
        if not _is_valid_url(video_url):
            await message.reply("Please send a valid URL starting with http:// or https://")
            return

        await message.reply("Downloading audio, please wait...")

        output_dir = Path(__file__).resolve().parents[1] / "downloads" / "audio"
        try:
            info, file_path = await _download_audio_with_ytdlp_async(
                video_url,
                output_dir,
            )
        except asyncio.TimeoutError:
            await message.reply("Download timed out. Please try a shorter video.")
            return
        except Exception as exc:
            await message.reply(f"Audio download failed: {exc}")
            return

        title = info.get("title") or "audio"
        if file_path.exists():
            await _send_file_with_split(message, file_path, title, kind="music")
        else:
            await message.reply(
                f"Audio download completed for: {title}\n"
                "But the final file path could not be confirmed."
            )

    @app.on_update(filters.commands("supported_sources"))
    async def supported_sources_command(client, message):
        sources = (
            "Supported platforms:\n"
            "• YouTube (youtube.com)\n"
            "• Instagram (instagram.com)\n"
            "• TikTok (tiktok.com)\n"
            "• Twitter/X (twitter.com, x.com)\n"
            "• Facebook (facebook.com)\n"
            "• Reddit (reddit.com)\n"
            "• Vimeo (vimeo.com)\n"
            "• LinkedIn (linkedin.com)\n"
            "• Dailymotion (dailymotion.com)\n"
            "• And 1000+ more platforms supported by yt-dlp!"
        )
        await message.reply(sources)

    @app.on_update(filters.commands("settings"))
    async def settings_command(client, message):
        settings_text = (
            "⚙️ Settings (Coming Soon)\n\n"
            "Planned features:\n"
            "• Quality preferences (480p, 720p, 1080p)\n"
            "• Audio-only downloads\n"
            "• Subtitle preferences\n"
            "• Download format selection\n"
            "• Storage location settings\n"
            "• Notification preferences"
        )
        await message.reply(settings_text)

    @app.on_update(filters.commands("favorites"))
    async def favorites_command(client, message):
        favorites_text = (
            "⭐ Favorites Management\n\n"
            "Commands:\n"
            "/add_favorite <url> [title] - Save a video\n"
            "/my_favorites - View your saved videos\n"
            "/remove_favorite <url> - Remove from favorites\n"
            "/clear_favorites - Remove all favorites\n\n"
            "Example:\n"
            "/add_favorite https://youtube.com/watch?v=abc123 My Video"
        )
        await message.reply(favorites_text)

    @app.on_update(filters.commands("history"))
    async def history_command(client, message):
        history_text = (
            "📜 Download History (Coming Soon)\n\n"
            "View all your past downloads and redownload them easily.\n\n"
            "Features:\n"
            "• Complete download history\n"
            "• One-click re-downloads\n"
            "• Search and filter\n"
            "• Clear history option"
        )
        await message.reply(history_text)

    @app.on_update(filters.commands("contact"))
    async def contact_command(client, message):
        contact_text = (
            "📧 Contact & Support\n\n"
            "For bug reports, feature requests, or general support:\n\n"
            "• Telegram: @MrAhmed\n"
            "• Email: me@MrEgyptian.com\n"
            "• GitHub: github.com/MrEgyptian\n\n"
            "Response time: Usually within 24 hours."
        )
        await message.reply(contact_text)

    @app.on_update(filters.commands("faq"))
    async def faq_command(client, message):
        faq_text = (
            "❓ Frequently Asked Questions\n\n"
            "Q: What formats are supported?\n"
            "A: MP4, MKV, AVI, WAV, MP3, and more.\n\n"
            "Q: Is there a file size limit?\n"
            "A: Downloads up to 2GB are supported.\n\n"
            "Q: How long do downloads take?\n"
            "A: Depends on video length and your connection.\n\n"
            "Q: Can I download playlists?\n"
            "A: Not currently, but it's planned.\n\n"
            "For more help, use /contact"
        )
        await message.reply(faq_text)

    @app.on_update(filters.commands("support"))
    async def support_command(client, message):
        support_text = (
            "🤝 Support This Project\n\n"
            "If you enjoy using this bot and want to help keep it running:\n\n"
            "Donation Options:\n"
            "• Bitcoin: bc1qjn8t704egpnjglfj7k6eqr03v2s2n5xyt9e0hx\n"
            "• Ethereum: 0x4F434eB0D5eb49BEd03CC1BC44A54B7C3376eC67\n"
            "• PayPal: paypal.me/MrEgyptian\n"
            "• LTC: LgUpfYnDunQTxm83ZRtfSfgzvNRPkNnwBW\n\n"
            "Every contribution helps maintain servers and development.\n"
            "Thank you! 🌟"
        )
        await message.reply(support_text)
