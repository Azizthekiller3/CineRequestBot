from config import API_ID, API_HASH, BOT_TOKEN, SESSION
from pyrogram import Client

User = Client(
    name="user",
    session_string=SESSION,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True,
)

DlBot = Client(
    name="auto-delete",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)
