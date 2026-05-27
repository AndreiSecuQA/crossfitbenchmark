import asyncio
import logging

from sqlalchemy import select
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import BOT_TOKEN
from bot.database import async_session_factory, init_db
from bot.exercises import EXERCISES
from bot.handlers.admin import (
    AWAIT_TRIGGER_MSG,
    add_admin,
    admin,
    list_admins,
    list_users,
    remove_admin,
    trigger_send,
    trigger_start,
)
from bot.handlers.session import (
    AWAIT_DISTANCE,
    AWAIT_EXERCISE,
    AWAIT_TIME,
    AWAIT_WEIGHT,
    receive_distance,
    receive_exercise,
    receive_time,
    receive_weight,
    session_command,
    skip_exercise,
)
from bot.handlers.start import (
    ASK_HEIGHT,
    ASK_WEIGHT,
    CHOOSE_LANG,
    ask_height,
    ask_weight,
    cancel,
    choose_language,
    start,
)
from bot.handlers.stats import help_command, leaderboard, stats, update_weight
from bot.models import Exercise
from bot.services.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_exercises():
    from bot.exercises import EXERCISES as EX_LIST
    async with async_session_factory() as db:
        for ex_data in EX_LIST:
            result = await db.execute(select(Exercise).where(Exercise.key == ex_data["key"]))
            if not result.scalar_one_or_none():
                db.add(Exercise(
                    key=ex_data["key"],
                    measurement_type=ex_data["measurement_type"],
                    sort_order=ex_data["sort_order"],
                ))
        await db.commit()


async def post_init(application):
    await init_db()
    await seed_exercises()
    start_scheduler(application.bot)


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    registration_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_LANG: [CallbackQueryHandler(choose_language, pattern="^lang_")],
            ASK_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_height)],
            ASK_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_weight)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    session_conv = ConversationHandler(
        entry_points=[
            CommandHandler("session", session_command),
            CallbackQueryHandler(session_command, pattern="^start_session$"),
        ],
        states={
            AWAIT_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_weight)],
            AWAIT_EXERCISE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_exercise),
                CallbackQueryHandler(skip_exercise, pattern="^skip_"),
            ],
            AWAIT_DISTANCE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_distance),
                CallbackQueryHandler(skip_exercise, pattern="^skip_"),
            ],
            AWAIT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    trigger_conv = ConversationHandler(
        entry_points=[CommandHandler("trigger", trigger_start)],
        states={
            AWAIT_TRIGGER_MSG: [MessageHandler(filters.TEXT, trigger_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(registration_conv)
    app.add_handler(session_conv)
    app.add_handler(trigger_conv)
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("listadmins", list_admins))
    app.add_handler(CommandHandler("listusers", list_users))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("weight", update_weight))
    app.add_handler(CommandHandler("help", help_command))

    logger.info("Bot started.")
    app.run_polling()


if __name__ == "__main__":
    main()
