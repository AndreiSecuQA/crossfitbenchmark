from datetime import datetime

from sqlalchemy import select
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.database import async_session_factory
from bot.models import Session, User, UserSession
from bot.services.i18n import t

AWAIT_TRIGGER_MSG = 20


async def _get_user(tg_id: int):
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.telegram_id == tg_id))
        return result.scalar_one_or_none()


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user or not user.is_admin:
        await update.message.reply_text(t("not_admin", user.language if user else "en"))
        return
    await update.message.reply_text(t("admin_panel", user.language), parse_mode="Markdown")


async def trigger_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user or not user.is_admin:
        await update.message.reply_text(t("not_admin", user.language if user else "en"))
        return ConversationHandler.END

    context.user_data["admin_lang"] = user.language
    context.user_data["admin_user_id"] = user.id
    await update.message.reply_text(t("trigger_ask_message", user.language))
    return AWAIT_TRIGGER_MSG


async def trigger_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("admin_lang", "en")
    admin_id = context.user_data.get("admin_user_id")

    text = update.message.text.strip()
    custom_msg = "" if text == "/skip" else text

    async with async_session_factory() as db:
        session = Session(
            triggered_by=admin_id,
            custom_message=custom_msg,
            triggered_at=datetime.utcnow(),
        )
        db.add(session)
        await db.flush()

        users_result = await db.execute(select(User))
        users = users_result.scalars().all()

        for u in users:
            db.add(UserSession(session_id=session.id, user_id=u.id, status="pending"))

        await db.commit()
        session_id = session.id

    bot = context.bot
    count = 0
    display_msg = custom_msg or "💪 New CrossFit session!"

    for u in users:
        try:
            user_lang = u.language
            await bot.send_message(
                chat_id=u.telegram_id,
                text=t("session_started", user_lang, message=display_msg),
                reply_markup=_start_session_keyboard(user_lang),
            )
            count += 1
        except Exception:
            pass

    context.bot_data["active_session_id"] = session_id
    await update.message.reply_text(t("session_triggered", lang, count=count))
    return ConversationHandler.END


def _start_session_keyboard(lang: str):
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(t("start_session_btn", lang), callback_data="start_session")
    ]])


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user or not user.is_admin:
        await update.message.reply_text(t("not_admin", user.language if user else "en"))
        return

    lang = user.language
    if not context.args:
        await update.message.reply_text("Usage: /addadmin <telegram_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.telegram_id == target_id))
        target = result.scalar_one_or_none()
        if not target:
            await update.message.reply_text(t("user_not_found", lang))
            return
        target.is_admin = True
        await db.commit()

    await update.message.reply_text(t("admin_added", lang, id=target_id))


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user or not user.is_admin:
        await update.message.reply_text(t("not_admin", user.language if user else "en"))
        return

    lang = user.language
    if not context.args:
        await update.message.reply_text("Usage: /removeadmin <telegram_id>")
        return

    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.telegram_id == target_id))
        target = result.scalar_one_or_none()
        if not target:
            await update.message.reply_text(t("user_not_found", lang))
            return
        target.is_admin = False
        await db.commit()

    await update.message.reply_text(t("admin_removed", lang, id=target_id))


async def list_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user or not user.is_admin:
        await update.message.reply_text(t("not_admin", user.language if user else "en"))
        return

    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.is_admin == True))
        admins = result.scalars().all()

    lines = [f"• {a.first_name} (@{a.username}) — ID: {a.telegram_id}" for a in admins]
    await update.message.reply_text("🔧 Admins:\n" + "\n".join(lines))


async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user or not user.is_admin:
        await update.message.reply_text(t("not_admin", user.language if user else "en"))
        return

    async with async_session_factory() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()

    lines = [f"• {u.first_name} (@{u.username}) — {u.telegram_id}" for u in users]
    await update.message.reply_text(f"👥 Users ({len(users)}):\n" + "\n".join(lines))
