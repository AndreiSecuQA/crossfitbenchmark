import json
import os

_translations: dict[str, dict] = {}

_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "locales")


def _load(lang: str) -> dict:
    if lang not in _translations:
        path = os.path.join(_BASE, f"{lang}.json")
        with open(path, encoding="utf-8") as f:
            _translations[lang] = json.load(f)
    return _translations[lang]


def t(key: str, lang: str = "en", **kwargs) -> str:
    data = _load(lang)
    text = data.get(key, _load("en").get(key, key))
    return text.format(**kwargs) if kwargs else text
