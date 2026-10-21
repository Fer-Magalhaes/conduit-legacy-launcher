# Launcher interface languages. The source text is Brazilian Portuguese: locales\source.json lists every
# string shown, and locales\<code>.json holds the translations in the same order (an empty or missing
# entry shows the English one, then the Portuguese). tools\i18n_check.py keeps them in step.
# The language is read once at start-up (settings "ui_lang", else Windows' language), so module-level
# labels can be translated too; changing it restarts the launcher.
import ctypes, json, locale, os, sys

LANGS = [('pt-BR', 'Português (Brasil)'), ('en', 'English')]

if getattr(sys, 'frozen', False):
    _ROOT = os.path.dirname(sys.executable)
    _RES = getattr(sys, '_MEIPASS', _ROOT)
else:
    _RES = os.path.dirname(os.path.abspath(__file__))
    _ROOT = os.path.dirname(_RES)
LOCALES = os.path.join(_RES, 'locales')

_lang = 'pt-BR'
_table, _fallback = {}, {}


def _system():
    try:
        name = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), '')
    except (AttributeError, OSError):
        name = ''
    name = name.replace('_', '-')
    codes = [c for c, _ in LANGS]
    if name in codes:
        return name
    return 'pt-BR' if name.startswith('pt') else 'en'


def _load(code):
    try:
        src = json.load(open(os.path.join(LOCALES, 'source.json'), encoding='utf-8'))
        tr = json.load(open(os.path.join(LOCALES, code + '.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {a: b for a, b in zip(src, tr) if b}


def init():
    global _lang, _table, _fallback
    try:
        code = json.load(open(os.path.join(_ROOT, 'user', 'settings.json'), encoding='utf-8')).get('ui_lang')
    except (OSError, ValueError):
        code = None
    _lang = code if code in dict(LANGS) else _system()
    _table = {} if _lang == 'pt-BR' else _load(_lang)
    _fallback = {} if _lang in ('pt-BR', 'en') else _load('en')


def current():
    return _lang


def _(text):
    return _table.get(text) or _fallback.get(text) or text


init()
