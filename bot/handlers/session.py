from datetime import datetime

from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from bot.database import async_session_factory
from bot.exercises import EXERCISES
from bot.models import Exercise, Measurement, Session, User, UserSession, Weight
from bot.services.i18n import t
from bot.services.scoring import format_measurement, global_score, score_measurement

AWAIT_WEIGHT, AWAIT_EXERCISE, AWAIT_DISTANCE, AWAIT_TIME = range(10, 14)


def _get_exercise_def(key: str) -> dict | None:
    return next((e for e in EXERCISES if e["key"] == key), None)


async def _get_user(tg_id: int):
    async with async_session_factory() as db:
        result = await db.execute(
            select(User).where(User.telegram_id == tg_id)
        )
        return result.scalar_one_or_none()


async def session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg = update.effective_user
    user = await _get_user(tg.id)
    if not user:
        await update.message.reply_text(t("not_registered", "en"))
        return ConversationHandler.END

    lang = user.language

    async with async_session_factory() as db:
        sessions = await db.execute(
            select(Session).order_by(Session.triggered_at.desc()).limit(1)
        )
        latest_session = sessions.scalar_one_or_none()

        if not latest_session:
            await update.message.reply_text(t("no_active_session", lang))
            return ConversationHandler.END

        us_result = await db.execute(
            select(UserSession).where(
                UserSession.session_id == latest_session.id,
                UserSession.user_id == user.id,
            )
        )
        user_session = us_result.scalar_one_or_none()

        if user_session and user_session.status == "completed":
            await update.message.reply_text(t("session_already_completed", lang))
            return ConversationHandler.END

        if not user_session:
            user_session = UserSession(
                session_id=latest_session.id,
                user_id=user.id,
                status="in_progress",
                started_at=datetime.utcnow(),
            )
            db.add(user_session)
            await db.commit()
            await db.refresh(user_session)
        else:
            user_session.status = "in_progress"
            await db.commit()

    context.user_data["session_id"] = latest_session.id
    context.user_data["user_session_id"] = user_session.id
    context.user_data["user_id"] = user.id
    context.user_data["lang"] = lang
    context.user_data["exercise_index"] = 0
    context.user_data["scores"] = []
    context.user_data["results_text"] = ""

    await update.message.reply_text(
        t("session_intro", lang, count=len(EXERCISES))
    )
    await update.message.reply_text(t("ask_weight", lang))
    return AWAIT_WEIGHT


async def receive_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    try:
        weight = float(update.message.text.replace(",", "."))
        if not 30 <= weight <= 300:
            await update.message.reply_text(t("invalid_weight", lang))
            return AWAIT_WEIGHT
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return AWAIT_WEIGHT

    context.user_data["weight"] = weight
    user_id = context.user_data["user_id"]

    async with async_session_factory() as db:
        db.add(Weight(user_id=user_id, weight_kg=weight))
        await db.commit()

    return await _send_next_exercise(update, context)


async def _send_next_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    idx = context.user_data.get("exercise_index", 0)

    if idx >= len(EXERCISES):
        return await _finish_session(update, context)

    ex = EXERCISES[idx]
    ex_lang = ex["translations"].get(lang, ex["translations"]["en"])
    total = len(EXERCISES)

    if ex["measurement_type"] == "reps":
        hint = t("input_hint_reps", lang)
    elif ex["measurement_type"] == "seconds":
        hint = t("input_hint_seconds", lang)
    else:
        hint = t("input_hint_distance", lang)

    keyboard = [[InlineKeyboardButton(t("skip_btn", lang), callback_data=f"skip_{idx}")]]

    msg = t(
        "exercise_prompt", lang,
        current=idx + 1,
        total=total,
        name=ex_lang["name"],
        description=ex_lang["description"],
        input_hint=hint,
    )
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    if ex["measurement_type"] == "distance_time":
        context.user_data["pending_distance"] = None
        return AWAIT_DISTANCE

    return AWAIT_EXERCISE


async def receive_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    idx = context.user_data.get("exercise_index", 0)
    ex = EXERCISES[idx]

    try:
        value = int(update.message.text.strip())
        if value < 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return AWAIT_EXERCISE

    weight = context.user_data.get("weight", 70)

    if ex["measurement_type"] == "reps":
        score = score_measurement(ex["key"], value_reps=value, weight_kg=weight)
        formatted = format_measurement(ex["key"], value_reps=value)
        await _save_measurement(context, ex_key=ex["key"], value_reps=value)
    else:
        score = score_measurement(ex["key"], value_seconds=value, weight_kg=weight)
        formatted = format_measurement(ex["key"], value_seconds=value)
        await _save_measurement(context, ex_key=ex["key"], value_seconds=value)

    ex_name = ex["translations"].get(lang, ex["translations"]["en"])["name"]
    context.user_data["scores"].append(score)
    context.user_data["results_text"] += t("stats_exercise", lang, name=ex_name, value=formatted)

    await update.message.reply_text(t("exercise_saved", lang))
    context.user_data["exercise_index"] = idx + 1
    return await _send_next_exercise(update, context)


async def receive_distance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    try:
        dist = float(update.message.text.strip())
        if dist <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return AWAIT_DISTANCE

    context.user_data["pending_distance"] = dist
    await update.message.reply_text(t("input_hint_time", lang))
    return AWAIT_TIME


async def receive_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    idx = context.user_data.get("exercise_index", 0)
    ex = EXERCISES[idx]

    try:
        secs = int(update.message.text.strip())
        if secs <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return AWAIT_TIME

    dist = context.user_data.get("pending_distance", 0)
    weight = context.user_data.get("weight", 70)

    score = score_measurement(ex["key"], value_distance_m=dist, value_time_seconds=secs, weight_kg=weight)
    formatted = format_measurement(ex["key"], value_distance_m=dist, value_time_seconds=secs)

    await _save_measurement(context, ex_key=ex["key"], value_distance_m=dist, value_time_seconds=secs)

    ex_name = ex["translations"].get(lang, ex["translations"]["en"])["name"]
    context.user_data["scores"].append(score)
    context.user_data["results_text"] += t("stats_exercise", lang, name=ex_name, value=formatted)

    await update.message.reply_text(t("exercise_saved", lang))
    context.user_data["exercise_index"] = idx + 1
    return await _send_next_exercise(update, context)


async def skip_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang", "en")
    idx = context.user_data.get("exercise_index", 0)

    await query.edit_message_text(t("session_skipped", lang))
    context.user_data["exercise_index"] = idx + 1
    return await _send_next_exercise(query, context)


async def _save_measurement(context: ContextTypes.DEFAULT_TYPE, ex_key: str,
                             value_reps=None, value_seconds=None,
                             value_distance_m=None, value_time_seconds=None):
    async with async_session_factory() as db:
        ex_result = await db.execute(select(Exercise).where(Exercise.key == ex_key))
        exercise = ex_result.scalar_one_or_none()
        if not exercise:
            return

        m = Measurement(
            user_session_id=context.user_data["user_session_id"],
            user_id=context.user_data["user_id"],
            exercise_id=exercise.id,
            value_reps=value_reps,
            value_seconds=value_seconds,
            value_distance_m=value_distance_m,
        )
        if value_time_seconds is not None:
            m.value_seconds = value_time_seconds
            m.value_distance_m = value_distance_m
        db.add(m)
        await db.commit()


async def _finish_session(update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "en")
    scores = context.user_data.get("scores", [])
    results_text = context.user_data.get("results_text", "—")
    weight = context.user_data.get("weight", "?")
    g_score = global_score(scores)

    async with async_session_factory() as db:
        us_result = await db.execute(
            select(UserSession).where(UserSession.id == context.user_data["user_session_id"])
        )
        user_session = us_result.scalar_one_or_none()
        if user_session:
            user_session.status = "completed"
            user_session.completed_at = datetime.utcnow()
            await db.commit()

    summary = t(
        "session_summary", lang,
        results=results_text,
        weight=weight,
        score=g_score,
    )
    msg = update if hasattr(update, "reply_text") else update.message
    await msg.reply_text(summary, parse_mode="Markdown")
    return ConversationHandler.END
