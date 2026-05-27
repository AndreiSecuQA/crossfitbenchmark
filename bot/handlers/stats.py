from sqlalchemy import select, func
from telegram import Update
from telegram.ext import ContextTypes

from bot.database import async_session_factory
from bot.exercises import EXERCISES
from bot.models import Exercise, Measurement, User, UserSession, Weight
from bot.services.i18n import t
from bot.services.scoring import format_measurement, global_score, score_measurement


async def _get_user(tg_id: int):
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.telegram_id == tg_id))
        return result.scalar_one_or_none()


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text(t("not_registered", "en"))
        return

    lang = user.language

    async with async_session_factory() as db:
        weights = await db.execute(
            select(Weight).where(Weight.user_id == user.id).order_by(Weight.measured_at.desc()).limit(1)
        )
        latest_weight = weights.scalar_one_or_none()
        weight_val = latest_weight.weight_kg if latest_weight else None

        measurements = await db.execute(
            select(Measurement, Exercise)
            .join(Exercise, Measurement.exercise_id == Exercise.id)
            .where(Measurement.user_id == user.id)
            .order_by(Measurement.created_at.desc())
        )
        rows = measurements.all()

    seen = set()
    exercise_scores = []
    results_text = ""

    for m, ex in rows:
        if ex.key in seen:
            continue
        seen.add(ex.key)
        ex_def = next((e for e in EXERCISES if e["key"] == ex.key), None)
        if not ex_def:
            continue

        ex_lang = ex_def["translations"].get(lang, ex_def["translations"]["en"])
        formatted = format_measurement(
            ex.key,
            value_reps=m.value_reps,
            value_seconds=m.value_seconds,
            value_distance_m=m.value_distance_m,
        )
        score = score_measurement(
            ex.key,
            value_reps=m.value_reps,
            value_seconds=m.value_seconds,
            value_distance_m=m.value_distance_m,
            weight_kg=weight_val or 70,
        )
        exercise_scores.append(score)
        results_text += t("stats_exercise", lang, name=ex_lang["name"], value=formatted)

    g_score = global_score(exercise_scores)

    header = t(
        "stats_header", lang,
        name=user.first_name,
        weight=weight_val or "?",
        height=user.height_cm or "?",
        score=g_score,
    )
    await update.message.reply_text(header + results_text, parse_mode="Markdown")


async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    lang = user.language if user else "en"

    async with async_session_factory() as db:
        users_result = await db.execute(select(User))
        all_users = users_result.scalars().all()

        scores_by_user = {}
        for u in all_users:
            weights_r = await db.execute(
                select(Weight).where(Weight.user_id == u.id).order_by(Weight.measured_at.desc()).limit(1)
            )
            latest_w = weights_r.scalar_one_or_none()
            weight_kg = latest_w.weight_kg if latest_w else 70

            meas_r = await db.execute(
                select(Measurement, Exercise)
                .join(Exercise, Measurement.exercise_id == Exercise.id)
                .where(Measurement.user_id == u.id)
                .order_by(Measurement.created_at.desc())
            )
            rows = meas_r.all()

            seen = set()
            ex_scores = []
            for m, ex in rows:
                if ex.key in seen:
                    continue
                seen.add(ex.key)
                s = score_measurement(
                    ex.key,
                    value_reps=m.value_reps,
                    value_seconds=m.value_seconds,
                    value_distance_m=m.value_distance_m,
                    weight_kg=weight_kg,
                )
                ex_scores.append(s)

            scores_by_user[u.id] = {
                "name": u.first_name,
                "score": global_score(ex_scores),
            }

    sorted_users = sorted(scores_by_user.values(), key=lambda x: x["score"], reverse=True)

    text = t("leaderboard_header", lang)
    medals = ["🥇", "🥈", "🥉"]
    for i, entry in enumerate(sorted_users):
        rank = medals[i] if i < 3 else f"{i + 1}."
        text += f"{rank} {entry['name']} — {entry['score']} pts\n"

    text += "\n"

    for ex_def in EXERCISES:
        ex_key = ex_def["key"]
        ex_name = ex_def["translations"].get(lang, ex_def["translations"]["en"])["name"]

        async with async_session_factory() as db:
            rows_r = await db.execute(
                select(Measurement, User)
                .join(User, Measurement.user_id == User.id)
                .where(Measurement.exercise_id == (
                    select(Exercise.id).where(Exercise.key == ex_key).scalar_subquery()
                ))
                .order_by(Measurement.created_at.desc())
            )
            rows = rows_r.all()

        seen_users = set()
        ex_entries = []
        for m, u in rows:
            if u.id in seen_users:
                continue
            seen_users.add(u.id)
            ex_entries.append((u.first_name, m))

        if not ex_entries:
            continue

        text += t("leaderboard_exercise", lang, name=ex_name)
        for i, (name, m) in enumerate(ex_entries[:5]):
            rank = medals[i] if i < 3 else f"{i + 1}."
            formatted = format_measurement(
                ex_key,
                value_reps=m.value_reps,
                value_seconds=m.value_seconds,
                value_distance_m=m.value_distance_m,
            )
            text += f"{rank} {name} — {formatted}\n"
        text += "\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def update_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    if not user:
        await update.message.reply_text(t("not_registered", "en"))
        return

    lang = user.language
    if not context.args:
        await update.message.reply_text(t("update_weight_prompt", lang))
        return

    try:
        weight = float(context.args[0].replace(",", "."))
        if not 30 <= weight <= 300:
            await update.message.reply_text(t("invalid_weight", lang))
            return
    except ValueError:
        await update.message.reply_text(t("invalid_number", lang))
        return

    async with async_session_factory() as db:
        db.add(Weight(user_id=user.id, weight_kg=weight))
        await db.commit()

    await update.message.reply_text(t("weight_updated", lang, weight=weight))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await _get_user(update.effective_user.id)
    lang = user.language if user else "en"
    await update.message.reply_text(t("help", lang), parse_mode="Markdown")
