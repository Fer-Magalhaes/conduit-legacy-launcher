# Mods: packages in mods\<game>\<name>\, each a manifest.json that replaces files inside the game's
# .psarc archives (checked by MD5, so a mod for another release is skipped) or loose files:
#   {"version": 1,
#    "psarc": [{"path": "DISC/PS3_GAME/USRDIR/.../infamous1.psarc_s",
#               "entries": {"core.xpp": {"orig": "<md5>", "mod": "<md5>", "file": "core.xpp"}}}],
#    "files": [{"path": "DISC/PS3_GAME/USRDIR/...", "orig": "<md5 or empty>", "file": "x.bsub"}]}
# Paths start with DISC (a disc folder) or the installed folder's name (e.g. NPUA80657).
# A .zip dropped in the mods folder is installed by itself (its mod.json says which game) and removed
# when the .zip is taken out. Nothing of the games ships with the launcher: mods are the user's own.
import json, os, shutil, zipfile

import core
from i18n import _

STATE = os.path.join(core.USER, 'mods_zips.json')


def packages(game):
    """[{dir, name, desc, author, path}] installed for the game."""
    base = os.path.join(core.MODS, game)
    out = []
    if os.path.isfile(os.path.join(base, 'manifest.json')):  # one mod straight in the game's folder
        out.append({'dir': '.', 'name': _('Mod da pasta mods\\%s') % game, 'desc': '', 'author': '', 'path': base})
    try:
        entries = sorted(os.scandir(base), key=lambda e: e.name.lower())
    except OSError:
        entries = []
    for e in entries:
        if e.is_dir() and os.path.isfile(os.path.join(e.path, 'manifest.json')):
            try:
                info = json.load(open(os.path.join(e.path, 'mod.json'), encoding='utf-8-sig'))
            except (OSError, ValueError):
                info = {}
            out.append({'dir': e.name, 'name': info.get('name') or e.name, 'desc': info.get('description', ''),
                        'author': info.get('author', ''), 'path': e.path})
    return out


def enabled(game, gs):
    """Packages that are on (all of them until the user switches one off)."""
    pk = packages(game)
    if gs.get('mods_on') is None:
        return pk
    return [p for p in pk if p['dir'] in gs['mods_on']]


def manifest(game, gs):
    """The enabled packages merged; 'file' values become full paths. Later packages win."""
    out = {'psarc': [], 'files': []}
    by_path = {}
    for p in enabled(game, gs):
        try:
            m = json.load(open(os.path.join(p['path'], 'manifest.json'), encoding='utf-8'))
        except (OSError, ValueError):
            continue
        for ent in m.get('psarc', []):
            dst = by_path.setdefault(ent['path'], {'path': ent['path'], 'entries': {}})
            for name, e in ent.get('entries', {}).items():
                dst['entries'][name] = dict(e, file=os.path.join(p['path'], e['file']))
        for ent in m.get('files', []):
            out['files'].append(dict(ent, file=os.path.join(p['path'], ent['file'])))
    out['psarc'] = list(by_path.values())
    return out


# ---------------------------------------------------------------- drop-in .zip

def _stamp(path):
    st = os.stat(path)
    return '%d|%d' % (st.st_size, int(st.st_mtime))


def _install(path):
    name = os.path.splitext(os.path.basename(path))[0]
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        meta = [n for n in names if n.split('/')[-1].lower() == 'mod.json']
        if not meta:
            raise RuntimeError(_('O .zip não tem mod.json dizendo de qual jogo ele é.'))
        info = json.loads(z.read(meta[0]).decode('utf-8-sig'))
        game = info.get('game')
        if game not in core.GAMES:
            raise RuntimeError(_('mod.json: "game" deve ser infamous1, infamous2 ou fob.'))
        root = meta[0][:-len('mod.json')]
        dst = os.path.join(core.MODS, game, name)
        tmp = dst + '.tmp'
        shutil.rmtree(tmp, ignore_errors=True)
        for n in names:
            if not n.startswith(root):
                continue
            rel = n[len(root):]
            if '..' in rel.split('/') or ':' in rel:
                continue
            out = os.path.join(tmp, *rel.split('/'))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(n) as src, open(out, 'wb') as f:
                shutil.copyfileobj(src, f)
    if not os.path.isfile(os.path.join(tmp, 'manifest.json')):
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(_('O .zip não tem manifest.json.'))
    shutil.rmtree(dst, ignore_errors=True)
    os.replace(tmp, dst)
    return {'game': game, 'dir': name, 'name': info.get('name') or name}


def sync_zips(s):
    """Installs new or changed .zip files in the mods folder, removes what came from ones taken out."""
    try:
        state = json.load(open(STATE, encoding='utf-8'))
    except (OSError, ValueError):
        state = {}
    try:
        zips = {f: os.path.join(core.MODS, f) for f in os.listdir(core.MODS) if f.lower().endswith('.zip')}
    except OSError:
        zips = {}
    done = []
    for f in list(state):
        if f not in zips:
            rec = state.pop(f)
            shutil.rmtree(os.path.join(core.MODS, rec['game'], rec['dir']), ignore_errors=True)
            done.append((f, 'removido'))
    for f, path in sorted(zips.items()):
        stamp = _stamp(path)
        if state.get(f, {}).get('stamp') == stamp:
            continue
        try:
            rec = _install(path)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as e:
            core.log('mod %s: falhou: %s' % (f, e))
            done.append((f, 'erro: %s' % e))
            continue
        rec['stamp'] = stamp
        state[f] = rec
        gs = s['games'][rec['game']]
        if gs.get('mods_on') is not None and rec['dir'] not in gs['mods_on']:
            gs['mods_on'] = gs['mods_on'] + [rec['dir']]
        core.log('mod %s instalado para %s' % (f, rec['game']))
        done.append((f, rec['game']))
    if done:
        os.makedirs(core.USER, exist_ok=True)
        json.dump(state, open(STATE, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    return done


def add_zip(path):
    os.makedirs(core.MODS, exist_ok=True)
    shutil.copy2(path, os.path.join(core.MODS, os.path.basename(path)))


def remove(game, d):
    """Deletes a package, and its .zip when it came from one."""
    try:
        state = json.load(open(STATE, encoding='utf-8'))
    except (OSError, ValueError):
        state = {}
    for f, rec in list(state.items()):
        if rec['game'] == game and rec['dir'] == d:
            try:
                os.remove(os.path.join(core.MODS, f))
            except OSError:
                pass
            state.pop(f)
            json.dump(state, open(STATE, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    target = os.path.join(core.MODS, game) if d == '.' else os.path.join(core.MODS, game, d)
    if d == '.':
        for f in os.listdir(target):
            p = os.path.join(target, f)
            if os.path.isfile(p):
                os.remove(p)
    else:
        shutil.rmtree(target, ignore_errors=True)
