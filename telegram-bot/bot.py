import asyncio
import logging
import os
import signal
import sys
from subprocess import Popen

from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN, SESSION, LOG_CHANNEL, OWNER_ID, RESULTS_CHANNEL
from database import create_indexes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _session_name():
    sessions_dir = os.environ.get("SESSIONS_DIR", "sessions")
    try:
        os.makedirs(sessions_dir, exist_ok=True)
        test = os.path.join(sessions_dir, ".write_test")
        open(test, "w").close()
        os.remove(test)
        return os.path.join(sessions_dir, "bot")
    except Exception:
        return ":memory:"


class Bot(Client):
    def __init__(self):
        name = _session_name()
        kwargs = dict(
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            plugins={"root": "plugins"},
            sleep_threshold=60,
        )
        if name == ":memory:":
            kwargs["in_memory"] = True
            name = "bot"
        super().__init__(name=name, **kwargs)

    async def start(self):
        await super().start()
        await create_indexes()

        if SESSION:
            await _start_user_session()
        else:
            logger.warning("⚠️  No SESSION set — search will not work.")

        if not RESULTS_CHANNEL:
            logger.warning("⚠️  RESULTS_CHANNEL not set — search results cannot be posted.")

        _start_autodelete_worker()

        from pyrogram.types import BotCommand
        await self.set_bot_commands([
            BotCommand("start",       "Check if I'm alive"),
            BotCommand("id",          "Get channel/group ID"),
            BotCommand("verify",      "Request group verification"),
            BotCommand("connect",     "Connect a channel for searching"),
            BotCommand("disconnect",  "Disconnect a channel"),
            BotCommand("connections", "List connected channels"),
            BotCommand("fsub",        "Set force-subscribe channel"),
            BotCommand("nofsub",      "Remove force-subscribe"),
            BotCommand("autodelete",  "Set result auto-delete timer"),
            BotCommand("ping",        "Check bot speed"),
            BotCommand("help",        "Show all commands"),
        ])

        me = await self.get_me()
        logger.info("✅ CineRequestBot started as @%s (%d)", me.username, me.id)

        if LOG_CHANNEL:
            try:
                await self.send_message(
                    LOG_CHANNEL,
                    f"✅ <b>CineRequestBot Started</b>\n\n"
                    f"🤖 @{me.username} (<code>{me.id}</code>)\n"
                    f"📺 Results channel: <code>{RESULTS_CHANNEL}</code>",
                )
            except Exception:
                pass

    async def stop(self, *args):
        if SESSION:
            try:
                from client import User
                if User.is_connected:
                    await User.stop()
            except Exception:
                pass
        await super().stop()
        logger.info("Bot stopped")


async def _start_user_session():
    try:
        from client import User
        if not User.is_connected:
            await User.start()
        me = await User.get_me()
        logger.info("✅ User session: @%s", me.username or me.first_name)
        count = 0
        async for _ in User.get_dialogs():
            count += 1
            if count >= 200:
                break
        logger.info("✅ Peer cache warmed (%d dialogs)", count)
    except Exception as e:
        logger.warning("⚠️  User session failed: %s", e)


async def _session_watchdog():
    while True:
        await asyncio.sleep(300)
        if not SESSION:
            continue
        try:
            from client import User
            if not User.is_connected:
                logger.warning("Watchdog: session disconnected — reconnecting")
                await _start_user_session()
            else:
                await User.get_me()
        except Exception as e:
            logger.warning("Watchdog error: %s", e)
            try:
                await _start_user_session()
            except Exception:
                pass


def _start_autodelete_worker():
    try:
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        Popen([sys.executable, "-m", "utils.delete"], cwd=bot_dir)
        logger.info("✅ Auto-delete worker started")
    except Exception as e:
        logger.warning("Auto-delete worker failed: %s", e)


async def main():
    from health import start_health_server
    start_health_server()

    bot = Bot()
    await bot.start()

    watchdog = asyncio.create_task(_session_watchdog())
    stop_event = asyncio.Event()

    def _handle_signal():
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    await stop_event.wait()
    watchdog.cancel()
    try:
        await watchdog
    except asyncio.CancelledError:
        pass
    await bot.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
