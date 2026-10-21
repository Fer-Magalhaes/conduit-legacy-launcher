# Trophies as RPCS3 keeps them: dev_hdd0\home\00000001\trophy\<NPWR...>\ with TROPCONF.SFM (the list, XML)
# and TROPUSR.DAT (which are unlocked and when, big-endian tables; type 6 holds the unlock state).
import datetime, glob, os, re, struct

import core

GRADES = {'P': 'platinum', 'G': 'gold', 'S': 'silver', 'B': 'bronze'}


def folder(game):
    for d in glob.glob(os.path.join(core.TROPHY, '*')):
        try:
            conf = open(os.path.join(d, 'TROPCONF.SFM'), encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        m = re.search(r'<title-name>([^<]*)</title-name>', conf)
        if m and re.search(core.GAMES[game]['trophy_title'], m.group(1).strip(), re.I):
            return d
    return None


def _unlocked(path):
    """{trophy id: unlock time (datetime or None)}"""
    try:
        b = open(path, 'rb').read()
    except OSError:
        return {}
    if b[:4] != b'\x81\x8f\x54\xad':
        return {}
    out = {}
    tables = struct.unpack('>I', b[8:12])[0]
    off = 48
    for _t in range(tables):
        kind, esz, _u, n, start, _r = struct.unpack('>IIIIQQ', b[off:off + 32])
        off += 32
        if kind != 6:
            continue
        for k in range(n):
            e = b[start + k * (esz + 16):start + (k + 1) * (esz + 16)]
            if len(e) < 48:
                break
            tid, state, _a, _b, t1, _t2 = struct.unpack('>IIIIQQ', e[16:48])
            if state:
                when = None
                try:
                    when = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=t1) if t1 else None
                except OverflowError:
                    pass
                out[tid] = when.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None) if when else None
    return out


def load(game):
    """(list of {id, name, detail, grade, hidden, unlocked, when, icon}, folder) or ([], None)."""
    d = folder(game)
    if not d:
        return [], None
    conf = open(os.path.join(d, 'TROPCONF.SFM'), encoding='utf-8', errors='replace').read()
    done = _unlocked(os.path.join(d, 'TROPUSR.DAT'))
    out = []
    for m in re.finditer(r'<trophy\s+([^>]*)>(.*?)</trophy>', conf, re.S):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        tid = int(attrs.get('id', '0'))
        name = re.search(r'<name>(.*?)</name>', m.group(2), re.S)
        detail = re.search(r'<detail>(.*?)</detail>', m.group(2), re.S)
        icon = os.path.join(d, 'TROP%03d.PNG' % tid)
        out.append({'id': tid, 'name': (name.group(1) if name else '').strip(),
                    'detail': (detail.group(1) if detail else '').strip(),
                    'grade': GRADES.get(attrs.get('ttype', 'B'), 'bronze'), 'hidden': attrs.get('hidden') == 'yes',
                    'unlocked': tid in done, 'when': done.get(tid), 'icon': icon if os.path.isfile(icon) else None})
    out.sort(key=lambda t: (not t['unlocked'], -(t['when'].timestamp() if t['when'] else 0), t['id']))
    return out, d
