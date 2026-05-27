from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.database import async_session_factory
from bot.models import User, Weight
from bot.services.i18n import t
from bot.config import FIRST_ADMIN_ID

CHOOSE_LANG, ASK_HEIGHT, ASK_WEIGHT = range(3)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    async with async_session_factory() as db:
        from sqlalchemy import select
        result = await db.execute(select(User).where(User.telegram_id == tg.id))
        user = result.scalar_one_or_none()

    if user:
        lang = user.language
        await update.message.reply_text(t("already_registered", lang))
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🇷🇴 Română", callback_data="lang_ro")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
    ]
    await update.message.reply_text(
        t("ask_language", "en"),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOOSE_LANG


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    await query.edit_message_text(t("welcome", lang))
    await query.message.reply_text(t("ask_height", lang))
    return ASK_HEIGHT


async def ask_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    try:
        height = float(update.message.text.replace(",", "."))
        if not 100 <= height <= 250:
            await update.message.reply_text(t("invalid_height", lang))
            return ASK_HEIGHT
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return ASK_HEIGHT

    context.user_data["height"] = height
    await update.message.reply_text(t("ask_weight", lang))
    return ASK_WEIGHT


async def ask_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    try:
        weight = float(update.message.text.replace(",", "."))
        if not 30 <= weight <= 300:
            await update.message.reply_text(t("invalid_weight", lang))
            return ASK_WEIGHT
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return ASK_WEIGHT

    tg = update.effective_user
    height = context.user_data["height"]

    async with async_session_factory() as db:
        is_first_admin = tg.id == FIRST_ADMIN_ID
        user = User(
            telegram_id=tg.id,
            username=tg.username,
            first_name=tg.first_name or tg.username or str(tg.id),
            height_cm=height,
            language=lang,
            is_admin=is_first_admin,
        )
        db.add(user)
        await db.flush()
        db.add(Weight(user_id=user.id, weight_kg=weight))
        await db.commit()

    await update.message.reply_text(
        t("profile_created", lang, name=tg.first_name, height=height, weight=weight)
    )
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    await update.message.reply_text("Anulat." if lang == "ro" else "Cancelled.")
    return ConversationHandler.END
