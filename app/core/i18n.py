from locales import en, uk

_locales = {"en": en.messages, "uk": uk.messages}
_default = "en"


def t(key: str, locale: str = _default) -> str:
    messages = _locales.get(locale, _locales[_default])
    return messages.get(key, _locales[_default].get(key, key))
