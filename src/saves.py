# Save slots per game (RPCS3's dev_hdd0\home\00000001\savedata\<TITLE ID>_...), automatic backups before
# every session and export/import as .zip.
import hashlib, os, re, shutil, time, zipfile

import core
from i18n import _

BACKUPS = os.path.join(core.USER, 'backups')
KEEP = 20


def _dirs(game):
    ids = core.GAMES[game]['ids']
    try:
        return sorted(e.path for e in os.scandir(core.SAVEDATA) if e.is_dir() and e.name.upper().startswith(ids))
    except OSError:
        return []


def slots(game):
    """[{dir, name, mission, karma, percent, auto, time, detail}] newest first."""
    from sfo import read_sfo
    out = []
    for d in _dirs(game):
        try:
            sfo = read_sfo(os.path.join(d, 'PARAM.SFO'))
        except (OSError, ValueError, IndexError):
            sfo = {}
        sub = sfo.get('SUB_TITLE', '')
        detail = sfo.get('DETAIL', '')
        auto = sub.startswith('(')
        mission = re.sub(r'^\([^)]*\)\s*', '', sub) or os.path.basename(d)
        m = re.search(r'(\d+)\s*%', detail)
        rep = re.search(r'^(?:Reputa\w*|Reputation|Réputation|Ruf|Reputazione)\s*:\s*(.+)$', detail, re.M | re.I)
        files = [os.path.join(dp, f) for dp, _d, fn in os.walk(d) for f in fn]
        n = re.search(r'(\d+)$', os.path.basename(d))
        out.append({'dir': os.path.basename(d), 'mission': mission, 'karma': rep.group(1).strip() if rep else '',
                    'percent': int(m.group(1)) if m else None, 'auto': auto, 'detail': detail,
                    'time': max((os.path.getmtime(f) for f in files), default=0),
                    'name': _('Slot %d') % (int(n.group(1)) + 1) if n else os.path.basename(d)})
    out.sort(key=lambda x: (-x['time'], x['dir']))
    return out


def _fingerprint(game):
    h = hashlib.md5()
    for d in _dirs(game):
        for dp, _d, fn in sorted(os.walk(d)):
            for f in sorted(fn):
                st = os.stat(os.path.join(dp, f))
                h.update(('%s|%d|%d' % (os.path.relpath(os.path.join(dp, f), core.SAVEDATA), st.st_size,
                                        int(st.st_mtime))).encode())
    return h.hexdigest()


def _zip(game, dest):
    with zipfile.ZipFile(dest + '.tmp', 'w', zipfile.ZIP_DEFLATED) as z:
        for d in _dirs(game):
            for dp, _d, fn in os.walk(d):
                for f in fn:
                    p = os.path.join(dp, f)
                    z.write(p, os.path.relpath(p, core.SAVEDATA))
        z.comment = _fingerprint(game).encode()
    os.replace(dest + '.tmp', dest)
    return dest


def backups(game):
    """[(path, time, label)] newest first."""
    d = os.path.join(BACKUPS, game)
    try:
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('.zip')]
    except OSError:
        return []
    out = []
    for p in files:
        m = re.match(r'saves-(\d{8}-\d{6})(?:-(.*))?\.zip$', os.path.basename(p))
        if m:
            out.append((p, time.mktime(time.strptime(m.group(1), '%Y%m%d-%H%M%S')), (m.group(2) or '').replace('-', ' ')))
    return sorted(out, key=lambda x: -x[1])


def backup(game, label=''):
    """Zips the game's saves unless the newest backup already has them. Returns the path or None."""
    if not _dirs(game):
        return None
    fp = _fingerprint(game)
    old = backups(game)
    if old and not label:
        try:
            if zipfile.ZipFile(old[0][0]).comment.decode() == fp:
                return old[0][0]
        except (OSError, zipfile.BadZipFile):
            pass
    d = os.path.join(BACKUPS, game)
    os.makedirs(d, exist_ok=True)
    name = 'saves-%s%s.zip' % (time.strftime('%Y%m%d-%H%M%S'), '-' + label.replace(' ', '-') if label else '')
    path = _zip(game, os.path.join(d, name))
    for p, _t, lab in backups(game)[KEEP:]:
        if not lab:
            os.unlink(p)
    return path


def export(game, dest):
    return _zip(game, dest)


def restore(game, zpath, label='antes de restaurar'):
    """Replaces the game's saves with a .zip (backup or exported); the current ones are backed up first."""
    ids = core.GAMES[game]['ids']
    with zipfile.ZipFile(zpath) as z:
        names = [n.replace('\\', '/') for n in z.namelist()]
        tops = {n.split('/')[0] for n in names if n.strip('/')}
        if not tops or any(not t.upper().startswith(ids) or '..' in t or ':' in t for t in tops):
            raise RuntimeError(_('Este .zip não tem saves deste jogo.'))
        backup(game, label)
        tmp = os.path.join(core.SAVEDATA, '.restore')
        shutil.rmtree(tmp, ignore_errors=True)
        z.extractall(tmp)
    for d in _dirs(game):
        shutil.rmtree(d)
    for t in tops:
        os.replace(os.path.join(tmp, t), os.path.join(core.SAVEDATA, t))
    shutil.rmtree(tmp, ignore_errors=True)


def delete_slot(game, name):
    backup(game, 'antes de apagar slot')
    shutil.rmtree(os.path.join(core.SAVEDATA, name))
