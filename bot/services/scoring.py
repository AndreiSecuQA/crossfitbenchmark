"""
Scoring logic for exercises.

Each exercise returns a raw score (0-100), then a global score is the
weighted average across all completed exercises.

For strength exercises, we apply a body-weight multiplier using allometric
scaling (weight^0.67) so heavier athletes are not penalized.
"""

REFERENCE_WEIGHT_KG = 70.0

EXERCISE_MAX = {
    "pull_ups": 25,
    "push_ups": 60,
    "dips": 30,
    "sit_ups": 60,
    "plank": 300,
    "leg_raises": 30,
    "running": 4.0,  # m/s (roughly 15 km/h)
    "burpees": 30,
    "jump_rope": 200,
    "squats": 60,
    "lunges": 60,
    "box_jumps": 30,
}

STRENGTH_EXERCISES = {"pull_ups", "dips", "push_ups"}


def _bw_factor(weight_kg: float) -> float:
    if not weight_kg or weight_kg <= 0:
        return 1.0
    return (weight_kg / REFERENCE_WEIGHT_KG) ** 0.67


def score_measurement(exercise_key: str, value_reps=None, value_seconds=None,
                       value_distance_m=None, value_time_seconds=None,
                       weight_kg: float = REFERENCE_WEIGHT_KG) -> float:
    max_val = EXERCISE_MAX.get(exercise_key)
    if max_val is None:
        return 0.0

    if exercise_key == "plank":
        raw = min(value_seconds or 0, max_val) / max_val
    elif exercise_key == "running":
        if value_distance_m and value_time_seconds and value_time_seconds > 0:
            speed = value_distance_m / value_time_seconds
            raw = min(speed, max_val) / max_val
        else:
            raw = 0.0
    else:
        raw = min(value_reps or 0, max_val) / max_val

    if exercise_key in STRENGTH_EXERCISES:
        raw *= _bw_factor(weight_kg)
        raw = min(raw, 1.0)

    return round(raw * 100, 2)


def global_score(exercise_scores: list[float]) -> float:
    if not exercise_scores:
        return 0.0
    return round(sum(exercise_scores) / len(exercise_scores), 1)


def format_measurement(exercise_key: str, value_reps=None, value_seconds=None,
                        value_distance_m=None, value_time_seconds=None) -> str:
    if exercise_key == "plank":
        secs = value_seconds or 0
        return f"{secs}s ({secs // 60}m {secs % 60}s)" if secs >= 60 else f"{secs}s"
    elif exercise_key == "running":
        dist = value_distance_m or 0
        secs = value_time_seconds or 0
        if secs > 0:
            speed = dist / secs * 3.6
            mins, sec = divmod(secs, 60)
            return f"{int(dist)}m în {int(mins)}:{int(sec):02d} ({speed:.1f} km/h)"
        return f"{int(dist)}m"
    else:
        return f"{value_reps or 0} reps"
