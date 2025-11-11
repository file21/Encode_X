import logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
LOGGER = logging.getLogger(__name__)

import asyncio
import os
import time
import re
import json
import subprocess
import math
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.helper_funcs.display_progress import TimeFormatter
from bot.localisation import Localisation
from bot import (
    FINISHED_PROGRESS_STR,
    UN_FINISHED_PROGRESS_STR,
    DOWNLOAD_LOCATION,
    crf,
    resolution,
    audio_b,
    preset,
    codec,
    pid_list
)


async def convert_video(video_file, output_directory, total_time, bot, message, chan_msg):
    kk = os.path.basename(video_file)
    ext = kk.split(".")[-1]
    out_put_file_name = kk.replace(f".{ext}", ".mkv")
    progress = os.path.join(output_directory, "progress.txt")

    # Clear old progress
    open(progress, "w").close()

    # Set defaults if not already defined
    if not crf:
        crf.append("24")
    if not codec:
        codec.append("libx265")  # use HEVC for smaller size
    if not resolution:
        resolution.append("1920x1080")
    if not preset:
        preset.append("slow")
    if not audio_b:
        audio_b.append("128k")

    # FFmpeg command (overlay optional watermark)
    file_generator_command = (
        f"ffmpeg -hide_banner -loglevel quiet -progress '{progress}' "
        f"-i '{video_file}' "
        f"-i https://graph.org/file/b41a33cfdde9349b322b7.png "
        f"-filter_complex '[0:v][1:v] overlay=W-w-20:H-h-20:format=auto[out]' "
        f"-map '[out]' -map 0:a? -map 0:s? "
        f"-c:v {codec[0]} -crf {crf[0]} -pix_fmt yuv420p "
        f"-s {resolution[0]} -c:a libopus -b:a {audio_b[0]} "
        f"-preset {preset[0]} "
        f"-metadata title='' -metadata:s:v title='' -metadata:s:a title='' "
        f"-metadata:s:s title='' '{out_put_file_name}' -y"
    )

    COMPRESSION_START_TIME = time.time()
    process = await asyncio.create_subprocess_shell(
        file_generator_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    LOGGER.info(f"FFmpeg process started: PID {process.pid}")
    pid_list.insert(0, process.pid)

    # write status.json
    status_path = os.path.join(output_directory, "status.json")
    with open(status_path, "r+") as f:
        statusMsg = json.load(f)
        statusMsg["pid"] = process.pid
        statusMsg["message"] = message.id
        f.seek(0)
        json.dump(statusMsg, f, indent=2)

    # progress loop
    while True:
        await asyncio.sleep(3)
        if process.returncode is not None:
            break

        try:
            with open(progress, "r+") as file:
                text = file.read()
            frame = re.findall(r"frame=(\d+)", text)
            time_in_us = re.findall(r"out_time_ms=(\d+)", text)
            progress_flag = re.findall(r"progress=(\w+)", text)
            speed = re.findall(r"speed=(\d+\.?\d*)", text)

            frame = int(frame[-1]) if frame else 1
            speed = float(speed[-1]) if speed else 1
            elapsed_time = int(time_in_us[-1]) / 1_000_000 if time_in_us else 1

            if progress_flag and progress_flag[-1] == "end":
                LOGGER.info("FFmpeg encoding complete.")
                break

            difference = max(0, math.floor((total_time - elapsed_time) / speed))
            ETA = TimeFormatter(difference * 1000) if difference else "-"
            percentage = min(100, math.floor(elapsed_time * 100 / total_time))

            progress_str = "💽 Progress: {0}%\n[{1}{2}]".format(
                round(percentage, 2),
                FINISHED_PROGRESS_STR * math.floor(percentage / 10),
                UN_FINISHED_PROGRESS_STR * (10 - math.floor(percentage / 10)),
            )
            stats = (
                f"❄️ ENCODING IN PROGRESS\n\n"
                f"⌛ TIME LEFT: {ETA}\n\n"
                f"{progress_str}\n"
            )

            try:
                await message.edit_text(
                    text=stats,
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("Cancel", callback_data="fuckingdo")]]
                    ),
                )
            except Exception:
                pass
        except Exception as e:
            LOGGER.warning(f"Progress read failed: {e}")
            continue

    stdout, stderr = await process.communicate()
    del pid_list[0]

    if process.returncode != 0:
        err = stderr.decode().strip()
        LOGGER.error(f"FFmpeg failed:\n{err}")
        try:
            await message.edit_text(
                f"❌ **Encoding Failed**\n\n`{err}`\n\nContact @its_Oreki_Hotarou"
            )
        except Exception:
            pass
        return None

    if os.path.lexists(out_put_file_name):
        LOGGER.info(f"Encoding finished: {out_put_file_name}")
        return out_put_file_name
    else:
        return None


async def media_info(saved_file_path):
    process = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-i", saved_file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    stdout, _ = process.communicate()
    output = stdout.decode(errors="ignore")
    duration = re.search(r"Duration:\s*(\d*):(\d*):(\d+\.?\d*)", output)
    bitrates = re.search(r"bitrate:\s*(\d+)", output)

    if duration:
        hours, minutes, seconds = (
            int(duration.group(1)),
            int(duration.group(2)),
            float(duration.group(3)),
        )
        total_seconds = int(hours * 3600 + minutes * 60 + seconds)
    else:
        total_seconds = None

    bitrate = bitrates.group(1) if bitrates else None
    return total_seconds, bitrate


async def take_screen_shot(video_file, output_directory, ttl):
    out_put_file_name = os.path.join(output_directory, f"{time.time()}.jpg")
    if video_file.upper().endswith(("MKV", "MP4", "WEBM")):
        file_gen_command = [
            "ffmpeg",
            "-ss",
            str(ttl),
            "-i",
            video_file,
            "-vframes",
            "1",
            out_put_file_name,
        ]
        process = await asyncio.create_subprocess_exec(
            *file_gen_command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()

    return out_put_file_name if os.path.lexists(out_put_file_name) else None


def get_width_height(video_file):
    metadata = extractMetadata(createParser(video_file))
    if metadata and metadata.has("width") and metadata.has("height"):
        return metadata.get("width"), metadata.get("height")
    return 1280, 720
