from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from bot.config import REMINDER_HOURS
from bot.database import async_session_factory
from bot.models import Session, User, UserSession
from bot.services.i18n import t

scheduler = AsyncIOScheduler()


async def check_and_send_reminders(bot):
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=REMINDER_HOURS)

    async with async_session_factory() as db:
        sessions_r = await db.execute(
            select(Session).where(
                Session.triggered_at <= cutoff,
                Session.reminder_sent_at == None,
            )
        )
        pending_sessions = sessions_r.scalars().all()

        for session in pending_sessions:
            us_r = await db.execute(
                select(UserSession, User)
                .join(User, UserSession.user_id == User.id)
                .where(
                    UserSession.session_id == session.id,
                    UserSession.status != "completed",
                )
            )
            rows = us_r.all()

            for us, user in rows:
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=t("reminder_text", user.language),
                    )
                except Exception:
                    pass

            session.reminder_sent_at = now
            await db.commit()


def start_scheduler(bot):
    scheduler.add_job(
        check_and_send_reminders,
        "interval",
        minutes=30,
        args=[bot],
        id="reminder_check",
        replace_existing=True,
    )
    scheduler.start()
