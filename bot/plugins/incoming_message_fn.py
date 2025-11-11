import datetime
import logging
import os
import time
import asyncio
import json

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
LOGGER = logging.getLogger(__name__)

from bot.localisation import Localisation
from bot import (
    DOWNLOAD_LOCATION,
    AUTH_USERS,
    LOG_CHANNEL,
    UPDATES_CHANNEL,
    SESSION_NAME,
    data,
    resolution, 
    app,
)
from bot.helper_funcs.ffmpeg import (
    convert_video,
    media_info,
    take_screen_shot,
)
from bot.helper_funcs.display_progress import (
    progress_for_pyrogram,
    TimeFormatter,
    humanbytes,
)

from pyrogram import enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors.exceptions.bad_request_400 import (
    UserNotParticipant,
    UsernameNotOccupied,
    ChatAdminRequired,
    PeerIdInvalid,
)

os.system(
    "wget https://telegra.ph/file/23bcc5673d1697dd2b3dd.jpg -O thumb.jpg"
)

bot = app

async def encode_all_qualities(video, duration, bot, sent_message, compress_start):
    """
    Run convert_video 3 times with different resolutions:
    480p, 720p, 1080p.
    Returns (status, [(label, path), ...])
    """
    qualities = [
        ("480p", "854x480"),
        ("720p", "1280x720"),
        ("1080p", "1920x1080"),
    ]

    outputs = []

    original_res = resolution[0] if resolution else None

    for label, res in qualities:
        if resolution:
            resolution[0] = res
        else:
            resolution.append(res)

        out_path = await convert_video(
            video,
            DOWNLOAD_LOCATION,
            duration,
            bot,
            sent_message,
            compress_start,
        )

        if out_path == "stopped":
            if original_res is not None:
                resolution[0] = original_res
            return "stopped", []

        if out_path is not None:
            outputs.append((label, out_path))
    if original_res is not None:
        resolution[0] = original_res

    return "ok", outputs


async def incoming_start_message_f(bot, update):
    """/start command"""

    await bot.send_message(
        chat_id=update.chat.id,
        text=Localisation.START_TEXT,
        parse_mode=enums.ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Supreme", url="https://t.me/voxin_sama"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "Updates", url="https://t.me/AnimeChidori"
                    ),
                    InlineKeyboardButton(
                        "Network", url="https://t.me/Uchiha_x_clan"
                    ),
                ],
            ]
        ),
        reply_to_message_id=update.id,
    )


async def incoming_compress_message_f(update):
    """/compress command"""

    d_start = time.time()
    c_start = time.time()
    u_start = time.time()

    sent_message = await bot.send_message(
        chat_id=update.chat.id,
        text=Localisation.DOWNLOAD_START,
        reply_to_message_id=update.id,
    )

    chat_id = LOG_CHANNEL
    utc_now = datetime.datetime.utcnow()
    ist_now = utc_now + datetime.timedelta(minutes=30, hours=5)
    ist = ist_now.strftime("%d/%m/%Y, %H:%M:%S")
    bst_now = utc_now + datetime.timedelta(minutes=0, hours=6)
    bst = bst_now.strftime("%d/%m/%Y, %H:%M:%S")
    now = f"\n{ist} (GMT+05:30)`\n`{bst} (GMT+06:00)"

    download_start = await bot.send_message(
        chat_id,
        f"**Bot Become Busy Now !!** \n\nDownload Started at `{now}`",
        parse_mode=enums.ParseMode.MARKDOWN,
    )
    status_path = os.path.join(DOWNLOAD_LOCATION, "status.json")

    try:
        with open(status_pa_
