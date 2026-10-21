# Conduit Legacy Launcher core: finds the games, builds a modded view of them for RPCS3, writes RPCS3's
# settings and controller config, and starts the game.
# The user's game folders are never written to: RPCS3 sees junctions/hard links to them, and modded or
# decrypted files are built under out\ and linked in their place.
import hashlib, json, os, shutil, subprocess, sys, time, _winapi

import yaml

import psarc, repack
from i18n import _
from sfo import read_sfo

if getattr(sys, 'frozen', False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RPCS3 = os.path.join(ROOT, 'rpcs3')
RPCS3_EXE = os.path.join(RPCS3, 'rpcs3.exe')
HDD = os.path.join(RPCS3, 'dev_hdd0')
HDD_GAME = os.path.join(HDD, 'game')
HOME = os.path.join(HDD, 'home', '00000001')
SAVEDATA = os.path.join(HOME, 'savedata')
TROPHY = os.path.join(HOME, 'trophy')
EXDATA = os.path.join(HOME, 'exdata')
DISC_GAMES = os.path.join(RPCS3, 'games')
OUT = os.path.join(ROOT, 'out')
MODS = os.path.join(ROOT, 'mods')
ART = os.path.join(ROOT, 'art')
USER = os.path.join(ROOT, 'user')
JOGOS = os.path.join(ROOT, 'jogos')
SETTINGS = os.path.join(USER, 'settings.json')
STATE = os.path.join(USER, 'state.json')
LOG = os.path.join(USER, 'last_run.log')
NO_WINDOW = 0x08000000

# RPCS3 system languages: (label, value). The US releases of inFAMOUS 2 and Festival of Blood load their
# Brazilian Portuguese files with "Portuguese (Portugal)"; "Portuguese (Brazil)" hangs inFAMOUS 2.
_LANGS = [('English (US)', 'English (US)'), ('English (UK)', 'English (UK)'), ('Français', 'French'),
          ('Español', 'Spanish'), ('Deutsch', 'German'), ('Italiano', 'Italian'), ('Nederlands', 'Dutch'),
          ('Polski', 'Polish'), ('Русский', 'Russian'), ('Türkçe', 'Turkish'), ('日本語', 'Japanese'),
          ('한국어', 'Korean'), ('中文 (繁體)', 'Chinese (Traditional)')]
# The settings RPCS3's compatibility database recommends for each game (same for all its releases)
_REC_STRICT = {'Video': {'Vulkan': {'Asynchronous Texture Streaming': True}, 'Strict Rendering Mode': True,
                         'Accurate ZCULL stats': False, 'Relaxed ZCULL Sync': True},
               'Core': {'SPU Block Size': 'Mega', 'Sleep Timers Accuracy': 'As Host'}}
_REC_MT = {'Video': {'Vulkan': {'Asynchronous Texture Streaming': True}, 'Multithreaded RSX': True,
                     'Accurate ZCULL stats': False, 'Relaxed ZCULL Sync': True},
           'Core': {'Sleep Timers Accuracy': 'As Host'}}

GAMES = {
    'infamous1': {
        'name': 'inFAMOUS', 'year': 2009, 'trophy_title': r'^infamous$',
        'ids': ('BCES00609', 'BCUS98119', 'BCES00220', 'BCES00591', 'NPUA80480', 'NPEA00252'),
        'state': 'Cole MacGrath · Empire City',
        'langs': [('Português (Portugal)', 'Portuguese (Portugal)')] + _LANGS,
        # dirs the game writes itself under dev_hdd0\game: (generated file, file it is copied from)
        'generated': {'BCES00609': [('BCES00609/USRDIR/cache/psarc/install1/infamous1.psarc_s',
                                     'DISC/PS3_GAME/USRDIR/cache/psarc/install1/infamous1.psarc_s')]},
        'recommended': {'Video': dict(_REC_MT['Video']),
                        'Core': {'SPU Block Size': 'Mega', 'SPU XFloat Accuracy': 'Accurate',
                                 'Sleep Timers Accuracy': 'As Host'}},
        'colors': ((40, 120, 255), (120, 200, 255)),
    },
    'infamous2': {
        'name': 'inFAMOUS 2', 'year': 2011, 'trophy_title': r'^infamous 2$',
        'ids': ('BCUS98125', 'NPUA80638', 'NPEA00318', 'BCES01143', 'BCES01144'),
        'state': 'Cole MacGrath · New Marais',
        'langs': [('Português (Brasil)', 'Portuguese (Portugal)')] + _LANGS,
        'generated': {'BCUS98125_INSTALL': [('BCUS98125_INSTALL/USRDIR/cache/psarc/install2/infamous2.psarc_s',
                                             'NPUA98125/USRDIR/cache/psarc/install2/infamous2.psarc_s')]},
        'recommended': _REC_STRICT,
        'colors': ((226, 69, 43), (255, 150, 60)),
    },
    'fob': {
        'name': 'inFAMOUS: Festival of Blood', 'year': 2011, 'trophy_title': r'festival of blood',
        'ids': ('NPUA80657', 'NPEA00322'),
        'state': 'Cole MacGrath · Pyre Night',
        'langs': [('Português (Brasil)', 'Portuguese (Portugal)')] + _LANGS,
        'generated': {},
        'recommended': _REC_MT,
        'colors': ((150, 20, 40), (210, 60, 90)),
    },
}

# graphics presets: (key, name, description, settings)
PRESETS = [
    ('potato', _('Batata'), _('PC fraco: 720p, sem filtros'),
     {'res': 100, 'fsr': False, 'aniso': 0, 'msaa': 'Disabled', 'vsync': 'Disabled'}),
    ('ps3', _('Como no PS3'), _('720p, como o console'),
     {'res': 100, 'fsr': False, 'aniso': 0, 'msaa': 'Auto', 'vsync': 'Full'}),
    ('performance', _('Desempenho'), _('720p ampliado com FSR'),
     {'res': 100, 'fsr': True, 'aniso': 8, 'msaa': 'Auto', 'vsync': 'Disabled'}),
    ('balanced', _('Equilibrado'), _('1080p, bom meio-termo'),
     {'res': 150, 'fsr': False, 'aniso': 8, 'msaa': 'Auto', 'vsync': 'Disabled'}),
    ('quality', _('Qualidade'), _('1440p, filtro 16x'),
     {'res': 200, 'fsr': False, 'aniso': 16, 'msaa': 'Auto', 'vsync': 'Disabled'}),
    ('ultra', _('Ultra'), _('4K, para placas fortes'),
     {'res': 300, 'fsr': False, 'aniso': 16, 'msaa': 'Auto', 'vsync': 'Disabled'}),
]
RESOLUTIONS = [(_('720p (nativo do PS3)'), 100), ('1080p', 150), ('1440p', 200), ('4K', 300)]
FPS = [(_('Automático'), 'Auto'), ('30 FPS', '30'), ('60 FPS', '60'), (_('Sem limite'), 'Off')]
VSYNC = [(_('Desligado'), 'Disabled'), (_('Adaptativo'), 'Adaptive'), (_('Ligado'), 'Full')]
ANISO = [(_('Automático'), 0), ('2x', 2), ('4x', 4), ('8x', 8), ('16x', 16)]
AUDIO_FORMATS = [(_('Estéreo'), 'Stereo'), ('Surround 5.1', 'Surround 5.1'), ('Surround 7.1', 'Surround 7.1')]
SCHEDULERS = [(_('Windows (padrão)'), 'Operating System'), (_('RPCS3'), 'RPCS3 Scheduler'),
              (_('RPCS3 alternativo (CPUs híbridas)'), 'RPCS3 Alternative Scheduler')]
PRIORITIES = [(_('Normal'), 'normal'), (_('Acima do normal'), 'above'), (_('Alta'), 'high')]
PAD_MODES = [(_('Detectar sozinho'), 'auto'), (_('Xbox / XInput (8BitDo, etc.)'), 'xbox'),
             ('DualShock 4', 'ds4'), ('DualSense', 'dualsense'), (_('Só teclado'), 'keyboard')]

GAME_DEFAULTS = {'folder': '', 'lang': '', 'res': 150, 'fsr': False, 'aniso': 8, 'msaa': 'Auto',
                 'vsync': 'Disabled', 'fps': 'Auto', 'patches_on': [], 'cheats_on': [], 'mods_on': None}
DEFAULTS = {'fullscreen': True, 'show_fps': False, 'sharpness': 50, 'stretch': False,
            'spu_threads': 0, 'low_end': False, 'scheduler': 'Operating System', 'priority': 'normal',
            'volume': 100, 'audio_format': 'Stereo', 'buffering': True, 'time_stretch': False,
            'pad_mode': 'auto', 'vibration': True, 'led': 'karma', 'trophy_popups': True, 'discord': True,
            'last': 'infamous1'}


def log(msg):
    os.makedirs(USER, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(time.strftime('[%H:%M:%S] ') + msg + '\n')


def load_settings():
    try:
        s = json.load(open(SETTINGS, encoding='utf-8'))
    except (OSError, ValueError):
        s = {}
    s = dict(DEFAULTS, **s)
    games = s.get('games') or {}
    for k, g in GAMES.items():
        gs = dict(GAME_DEFAULTS, **games.get(k, {}))
        if not gs['lang']:
            gs['lang'] = g['langs'][0][1]
        games[k] = gs
    s['games'] = games
    return s


def save_settings(s):
    os.makedirs(USER, exist_ok=True)
    tmp = SETTINGS + '.tmp'
    json.dump(s, open(tmp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    os.replace(tmp, SETTINGS)


def current_preset(gs):
    for key, _n, _d, vals in PRESETS:
        if all(gs.get(k) == v for k, v in vals.items()):
            return key
    return None


def _state():
    try:
        return json.load(open(STATE, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def _save_state(st):
    os.makedirs(USER, exist_ok=True)
    json.dump(st, open(STATE, 'w', encoding='utf-8'), indent=1)


# ---------------------------------------------------------------- detection

def _unit(path):
    """A game unit: a disc folder (PS3_GAME inside) or an installed HDD folder (PARAM.SFO inside)."""
    sfo = os.path.join(path, 'PS3_GAME', 'PARAM.SFO')
    if os.path.isfile(sfo):
        return {'kind': 'disc', 'path': path, 'name': 'DISC', 'sfo': read_sfo(sfo)}
    sfo = os.path.join(path, 'PARAM.SFO')
    if os.path.isfile(sfo):
        return {'kind': 'hdd', 'path': path, 'name': os.path.basename(path).upper(), 'sfo': read_sfo(sfo)}
    return None


def detect(game, folder):
    """Returns (units, message). The first unit is the bootable one."""
    g = GAMES[game]
    if not folder or not os.path.isdir(folder):
        return [], _('Escolha a pasta com os arquivos do jogo.')
    cands = [folder]
    for d in (folder, os.path.join(folder, 'dev_hdd0', 'game')):
        try:
            cands += [e.path for e in os.scandir(d) if e.is_dir()]
        except OSError:
            pass
    units = []
    for c in cands:
        u = _unit(c)
        if not u or u['sfo'].get('TITLE_ID') not in g['ids'] or u['name'] in g['generated']:
            continue
        if u['kind'] == 'disc' and any(x['kind'] == 'disc' for x in units):
            continue
        if any(os.path.normcase(x['path']) == os.path.normcase(u['path']) for x in units):
            continue
        units.append(u)
    boot = [u for u in units if u['kind'] == 'disc' or u['sfo'].get('CATEGORY') in ('HG', 'DG')]
    if not boot:
        return [], _('Nenhum arquivo do %s encontrado nesta pasta.') % g['name']
    units.remove(boot[0])
    units.insert(0, boot[0])
    s = boot[0]['sfo']
    ver = s.get('APP_VER') or s.get('VERSION') or ''
    msg = '%s · v%s' % (s.get('TITLE_ID'), ver)
    if units[1:]:
        msg += _(' · com atualização/DLC')
    if not os.path.isfile(eboot_of(boot[0])):
        return [], _('A pasta não tem o EBOOT.BIN do jogo.')
    return units, msg


def serial_of(game, folder):
    units = detect(game, folder)[0]
    return units[0]['sfo'].get('TITLE_ID') if units else None


def eboot_of(unit):
    if unit['kind'] == 'disc':
        return os.path.join(unit['path'], 'PS3_GAME', 'USRDIR', 'EBOOT.BIN')
    return os.path.join(unit['path'], 'USRDIR', 'EBOOT.BIN')


def autodetect(settings):
    """Fills in empty game folders from the jogos\\ folder and the folders next to the launcher."""
    changed = False
    bases = [JOGOS, os.path.dirname(ROOT)]
    cands = []
    for b in bases:
        try:
            for e in os.scandir(b):
                # an emulator folder holds views made by a launcher, not the user's own game files
                if e.is_dir() and e.name.lower() != 'rpcs3' and not _is_link(e.path):
                    cands.append(e.path)
                    try:
                        cands += [x.path for x in os.scandir(e.path) if x.is_dir() and x.name.lower() != 'rpcs3'
                                  and not _is_link(x.path)]
                    except OSError:
                        pass
        except OSError:
            pass
    for k in GAMES:
        gs = settings['games'][k]
        if gs['folder'] and detect(k, gs['folder'])[0]:
            continue
        for c in cands:
            if detect(k, c)[0]:
                gs['folder'] = os.path.normpath(c)
                changed = True
                break
    return changed


# ---------------------------------------------------------------- file helpers

def _is_link(p):
    return os.path.islink(p) or os.path.isjunction(p)


def safe_remove(p):
    """Deletes a prepared tree without ever following a junction into the user's files."""
    if not os.path.lexists(p):
        return
    if _is_link(p):
        try:
            os.rmdir(p)
        except OSError:
            os.unlink(p)
    elif os.path.isdir(p):
        for e in os.scandir(p):
            safe_remove(e.path)
        os.rmdir(p)
    else:
        try:
            os.chmod(p, 0o666)
        except OSError:
            pass
        os.unlink(p)


def link_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        os.link(src, dst)
        return
    except OSError:
        pass
    shutil.copy2(src, dst)


def mirror(src, dst, overrides):
    """dst becomes a view of src; overrides maps lower-case relative paths to replacement files."""
    prefixes = {''}
    for r in overrides:
        parts = r.split('/')
        for i in range(1, len(parts)):
            prefixes.add('/'.join(parts[:i]))

    def rec(s, d, rel):
        if rel not in prefixes:
            _winapi.CreateJunction(s, d)
            return
        os.mkdir(d)
        for e in os.scandir(s):
            r = (rel + '/' if rel else '') + e.name.lower()
            if e.is_dir():
                rec(e.path, os.path.join(d, e.name), r)
            else:
                link_file(overrides.get(r, e.path), os.path.join(d, e.name))

    rec(os.path.abspath(src), os.path.abspath(dst), '')


def _md5(b):
    return hashlib.md5(b).hexdigest()


def _file_md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def _stamp(p):
    st = os.stat(p)
    return [os.path.normcase(os.path.abspath(p)), st.st_size, int(st.st_mtime)]


# ---------------------------------------------------------------- SDAT (PSN conversions)

SKIP_SDAT = ('.edat', '.sdat', '.rap', '.bin', '.self', '.sprx', '.elf')


def find_sdat(unit):
    found = []
    for dp, _d, fn in os.walk(unit['path']):
        for f in fn:
            if f.lower().endswith(SKIP_SDAT):
                continue
            p = os.path.join(dp, f)
            try:
                with open(p, 'rb') as h:
                    if h.read(4) == b'NPD\0':
                        found.append(p)
            except OSError:
                pass
    return found


def decrypt_sdat(src, dst):
    """Decrypts one SDAT-wrapped file with RPCS3 into dst (src is left untouched)."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + '.enc'
    for p in (tmp, tmp + '.unedat'):
        if os.path.exists(p):
            os.unlink(p)
    link_file(src, tmp)
    subprocess.run([RPCS3_EXE, '--headless', '--decrypt', tmp], cwd=RPCS3, timeout=600, env=_clean_env(),
                   creationflags=NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.unlink(tmp)
    out = tmp + '.unedat'
    if not os.path.isfile(out) or open(out, 'rb').read(4) == b'NPD\0':
        raise RuntimeError(_('Não foi possível decriptar %s') % os.path.basename(src))
    os.replace(out, dst)


# ---------------------------------------------------------------- prepare

def _locate(units, path):
    """'UNIT/rel/path' -> (unit, rel) for a mod manifest path."""
    head, _s, rel = path.partition('/')
    for u in units:
        if (u['kind'] == 'disc' and head == 'DISC') or (u['kind'] == 'hdd' and u['name'] == head.upper()):
            return u, rel
    return None, None


def prepare(game, settings, progress=lambda pct, msg: None):
    """Builds RPCS3's view of the game, its config, patches and controller. Returns (eboot, config path)."""
    import installer, mods, patches
    installer.restore_vfs()  # in case a PKG install was cut short
    gs = settings['games'][game]
    g = GAMES[game]
    units, msg = detect(game, gs['folder'])
    if not units:
        raise RuntimeError(msg)
    log('prepare %s: %s' % (game, msg))
    gout = os.path.join(OUT, game)
    os.makedirs(gout, exist_ok=True)
    cache = os.path.join(gout, 'cache.json')
    try:
        built = json.load(open(cache, encoding='utf-8'))
    except (OSError, ValueError):
        built = {}

    # 1. files wrapped in SDAT by PSN conversions (RPCS3 hands them to the game still encrypted)
    overrides = {}  # (unit name, lower rel) -> prepared file
    progress(2, _('Verificando arquivos do jogo…'))
    for u in units:
        if u['kind'] != 'hdd':
            continue
        enc = find_sdat(u)
        for i, p in enumerate(enc):
            rel = os.path.relpath(p, u['path']).replace('\\', '/')
            dst = os.path.join(gout, 'dec', u['name'], rel)
            key = 'dec:' + u['name'] + '/' + rel
            if built.get(key) != _stamp(p) or not os.path.isfile(dst):
                progress(2 + 40 * i // len(enc), _('Decriptando %s (%d/%d)…') % (os.path.basename(p), i + 1, len(enc)))
                decrypt_sdat(p, dst)
                built[key] = _stamp(p)
                json.dump(built, open(cache, 'w', encoding='utf-8'))
            overrides[(u['name'], rel.lower())] = dst

    # 2. mods: replacement entries inside the game's psarc archives, and loose files
    man = mods.manifest(game, gs)
    for n, ent in enumerate(man['psarc']):
        u, rel = _locate(units, ent['path'])
        if not u:
            continue
        src = overrides.get((u['name'], rel.lower())) or os.path.join(u['path'], rel)
        if not os.path.isfile(src):
            continue
        progress(45 + 40 * n // max(1, len(man['psarc'])), _('Aplicando mods em %s…') % os.path.basename(rel))
        f, _e, names, data, _i = psarc.read(src)
        repl, unknown = {}, []
        for i, nm in enumerate(names, 1):
            e = ent['entries'].get(nm.lstrip('/'))
            if not e:
                continue
            h = _md5(data(i))
            if h == e['orig']:
                repl[nm.lstrip('/')] = e['file']
            elif h != e['mod']:
                unknown.append(nm)
        f.close()
        if unknown:
            log('  %s: versão diferente, mantidos originais: %s' % (rel, unknown))
        if not repl:
            continue
        dst = os.path.join(gout, 'mod', u['name'], rel)
        key = 'mod:' + ent['path']
        want = [_stamp(src), sorted((k, _stamp(v)) for k, v in repl.items())]
        if built.get(key) != want or not os.path.isfile(dst):
            progress(45 + 40 * n // max(1, len(man['psarc'])),
                     _('Montando %s (só na primeira vez)…') % os.path.basename(rel))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            repack.repack(src, dst + '.tmp', repl)
            os.replace(dst + '.tmp', dst)
            built[key] = want
            json.dump(built, open(cache, 'w', encoding='utf-8'))
        overrides[(u['name'], rel.lower())] = dst
    for ent in man['files']:
        u, rel = _locate(units, ent['path'])
        if not u:
            continue
        src = os.path.join(u['path'], rel)
        if os.path.isfile(src) and (not ent.get('orig') or _file_md5(src) == ent['orig']):
            overrides[(u['name'], rel.lower())] = ent['file']

    # 3. RPCS3's view: dev_hdd0\game\<dir> for installed games, rpcs3\games\<id> for discs
    progress(88, _('Preparando o jogo…'))
    st = _state()
    old = st.get(game, {}).get('views', [])
    views = []
    for u in units:
        dst = os.path.join(DISC_GAMES, u['sfo']['TITLE_ID']) if u['kind'] == 'disc' else os.path.join(HDD_GAME, u['name'])
        views.append(dst)
    for v in set(old) | set(views):
        if os.path.lexists(v):
            safe_remove(v)
    for u, dst in zip(units, views):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        mirror(u['path'], dst, {r: p for (n, r), p in overrides.items() if n == u['name']})
    st[game] = {'views': views}
    _save_state(st)

    # 4. files the game copies into dev_hdd0 by itself on first boot
    for gen_dir, pairs in g['generated'].items():
        for gen_rel, src_path in pairs:
            gp = os.path.join(HDD_GAME, gen_rel)
            if not os.path.isfile(gp) or _is_link(os.path.dirname(gp)):
                continue
            u, rel = _locate(units, src_path)
            if not u:
                continue
            want = overrides.get((u['name'], rel.lower())) or os.path.join(u['path'], rel)
            if os.path.isfile(want) and not os.path.samefile(gp, want):
                os.unlink(gp)
                link_file(want, gp)

    # 5. licences (.rap) next to the game files
    for base in {gs['folder'], os.path.dirname(gs['folder'])}:
        for dp, dn, fn in os.walk(base):
            if dp.count(os.sep) - base.count(os.sep) > 1:
                dn[:] = []
            for f in fn:
                if f.lower().endswith('.rap'):
                    os.makedirs(EXDATA, exist_ok=True)
                    if not os.path.isfile(os.path.join(EXDATA, f)):
                        shutil.copy2(os.path.join(dp, f), EXDATA)

    serial = units[0]['sfo']['TITLE_ID']
    if not os.path.isfile(patches.DB):  # above 720p these games need the community "mesh trimming" patch
        try:
            progress(90, _('Baixando os patches do RPCS3…'))
            patches.download()
        except Exception as e:
            log('patches não baixados: %s' % e)
    cfg = write_config(game, serial, settings)
    patches.apply(game, serial, gs)
    write_input(settings)
    import emulator
    emulator.quiet_gui()
    progress(100, _('Pronto'))
    boot = eboot_of(units[0])
    return os.path.join(views[0], os.path.relpath(boot, units[0]['path'])), cfg


# ---------------------------------------------------------------- RPCS3 config

def _merge(a, b):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _merge(a[k], v)
        else:
            a[k] = v
    return a


def write_config(game, serial, s):
    """RPCS3's own config (if any) + the game's recommended settings + the launcher's options."""
    gs = s['games'][game]
    try:
        cfg = yaml.safe_load(open(os.path.join(RPCS3, 'config', 'config.yml'), encoding='utf-8')) or {}
    except (OSError, yaml.YAMLError):
        cfg = {}
    _merge(cfg, json.loads(json.dumps(GAMES[game]['recommended'])))
    core_opts = {'Preferred SPU Threads': int(s['spu_threads']), 'Thread Scheduler Mode': s['scheduler'],
                 'SPU loop detection': bool(s['low_end'])}
    if s['low_end']:
        core_opts['Max LLVM Compile Threads'] = 2
    _merge(cfg, {
        'Core': core_opts,
        'Video': {'Renderer': 'Vulkan', 'Resolution Scale': int(gs['res']), 'Frame limit': gs['fps'],
                  'VSync Mode': gs['vsync'], 'MSAA': gs['msaa'], 'Anisotropic Filter Override': int(gs['aniso']),
                  'Output Scaling Mode': 'FidelityFX Super Resolution' if gs['fsr'] else 'Bilinear',
                  'FidelityFX CAS Sharpening Intensity': int(s['sharpness']),
                  'Stretch To Display Area': bool(s['stretch']),
                  'Performance Overlay': {'Enabled': bool(s['show_fps'])}},
        'Audio': {'Master Volume': int(s['volume']), 'Audio Format': s['audio_format'],
                  'Enable Buffering': bool(s['buffering']), 'Enable Time Stretching': bool(s['time_stretch'])},
        'System': {'Language': gs['lang']},
        'Miscellaneous': {'Show shader compilation hint': False, 'Show PPU compilation hint': False,
                          'Show trophy popups': bool(s['trophy_popups']),
                          'Prevent display sleep while running games': True},
    })
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, 'config_%s.yml' % game)
    yaml.safe_dump(cfg, open(p, 'w', encoding='utf-8'), sort_keys=False, allow_unicode=True, default_flow_style=False)
    log('config %s (%s): %dp, %s FPS, idioma %s' % (game, serial, int(gs['res']) * 720 // 100, gs['fps'], gs['lang']))
    return p


# ---------------------------------------------------------------- controller (RPCS3 input config)

_BUTTONS = ['Start', 'Select', 'PS Button', 'Square', 'Cross', 'Circle', 'Triangle', 'Left', 'Down', 'Right', 'Up',
            'R1', 'R2', 'R3', 'L1', 'L2', 'L3']
_STICKS = {'Left Stick Left': 'LS X-', 'Left Stick Down': 'LS Y-', 'Left Stick Right': 'LS X+',
           'Left Stick Up': 'LS Y+', 'Right Stick Left': 'RS X-', 'Right Stick Down': 'RS Y-',
           'Right Stick Right': 'RS X+', 'Right Stick Up': 'RS Y+'}
_XBOX = dict(zip(_BUTTONS, ['Start', 'Back', 'Guide', 'X', 'A', 'B', 'Y', 'Left', 'Down', 'Right', 'Up',
                            'RB', 'RT', 'RS', 'LB', 'LT', 'LS']))
_SONY = dict(zip(_BUTTONS, ['Options', 'Share', 'PS Button', 'Square', 'Cross', 'Circle', 'Triangle', 'Left',
                            'Down', 'Right', 'Up', 'R1', 'R2', 'R3', 'L1', 'L2', 'L3']))
# RPCS3's own keyboard defaults (keyboard_pad_handler.cpp)
_KEYS = dict(zip(_BUTTONS, ['Return', 'Space', 'Backspace', 'Z', 'X', 'C', 'V', 'Left', 'Down', 'Right', 'Up',
                            'E', 'T', 'G', 'Q', 'R', 'F']))
_KEY_STICKS = {'Left Stick Left': 'A', 'Left Stick Down': 'S', 'Left Stick Right': 'D', 'Left Stick Up': 'W',
               'Right Stick Left': 'Del', 'Right Stick Down': 'End', 'Right Stick Right': 'PgDown',
               'Right Stick Up': 'Home'}
# handler, device, buttons, sticks, deadzone, anti-deadzone, trigger threshold
HANDLERS = {
    'xbox': ('XInput', 'XInput Pad #1', _XBOX, _STICKS, 7849, 4259, 30),
    'ds4': ('DualShock 4', 'DS4 Pad #1', _SONY, _STICKS, 40, 33, 0),
    'dualsense': ('DualSense', 'DualSense Pad #1', _SONY, _STICKS, 40, 33, 0),
    'keyboard': ('Keyboard', 'Keyboard', _KEYS, _KEY_STICKS, 0, 0, 0),
}
LED = {'karma': (0, 90, 255), 'evil': (255, 20, 10), 'off': (0, 0, 0), 'white': (255, 255, 255)}


def pad_kind(s, pads):
    """Handler for this session from the setting and the connected controllers (controllers.detect)."""
    if s['pad_mode'] != 'auto':
        return s['pad_mode']
    for p in pads:
        if p['kind'] == 'playstation':
            return 'dualsense' if 'DualSense' in p['name'] else 'ds4'
    return 'xbox' if pads else 'keyboard'


def write_input(s):
    import controllers
    kind = pad_kind(s, controllers.detect())
    handler, device, buttons, sticks, dz, adz, trig = HANDLERS[kind]
    r, g, b = LED.get(s['led'], LED['karma'])
    vib = 100 if s['vibration'] else 0
    lines = ['Player 1 Input:', '  Handler: %s' % handler, '  Device: "%s"' % device, '  Config:']
    lines += ['    %s: %s' % (k, v) for k, v in sticks.items()]
    lines += ['    %s: %s' % (k, buttons[k]) for k in _BUTTONS]
    lines += ['    Left Stick Deadzone: %d' % dz, '    Right Stick Deadzone: %d' % dz,
              '    Left Stick Anti-Deadzone: %d' % adz, '    Right Stick Anti-Deadzone: %d' % adz,
              '    Left Trigger Threshold: %d' % trig, '    Right Trigger Threshold: %d' % trig,
              '    Color Value R: %d' % r, '    Color Value G: %d' % g, '    Color Value B: %d' % b,
              '    Large Vibration Motor Multiplier: %d' % vib, '    Small Vibration Motor Multiplier: %d' % vib,
              '    Vendor ID: 1356', '    Product ID: 616', '  Buddy Device: ""']
    for n in range(2, 8):
        lines += ['Player %d Input:' % n, '  Handler: "Null"', '  Device: "Null"', '  Buddy Device: "Null"']
    d = os.path.join(RPCS3, 'config', 'input_configs', 'global')
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, 'Default.yml'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    open(os.path.join(RPCS3, 'config', 'input_configs', 'active_input_configurations.yml'), 'w',
         encoding='utf-8').write('Active Configurations:\n  global: Default\n')
    log('controle: %s (%s)' % (handler, device))
    return kind


# ---------------------------------------------------------------- running

def _clean_env():
    """The packaged launcher points Windows' DLL search at its own _internal folder, and child
    processes inherit it: RPCS3 would then load the launcher's VCRUNTIME140.dll and refuse to run."""
    import ctypes
    ctypes.windll.kernel32.SetDllDirectoryW(None)
    env = dict(os.environ)
    internal = os.path.normcase(getattr(sys, '_MEIPASS', '') or '\0')
    env['PATH'] = os.pathsep.join(p for p in env.get('PATH', '').split(os.pathsep)
                                  if not os.path.normcase(p).startswith(internal))
    for k in ('TCL_LIBRARY', 'TK_LIBRARY', '_MEIPASS2', '_PYI_APPLICATION_HOME_DIR', '_PYI_PARENT_PROCESS_LEVEL'):
        env.pop(k, None)
    return env


def rpcs3_running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq rpcs3.exe', '/NH'], capture_output=True, text=True,
                       creationflags=NO_WINDOW)
    return 'rpcs3.exe' in r.stdout.lower()


_PRIORITY = {'normal': 0x20, 'above': 0x8000, 'high': 0x80}


def launch(eboot, cfg, s):
    args = [RPCS3_EXE, '--no-gui']
    if s['fullscreen']:
        args.append('--fullscreen')
    args += ['--config', cfg, eboot]
    log('launch: ' + ' '.join(args))
    proc = subprocess.Popen(args, cwd=RPCS3, env=_clean_env(), creationflags=_PRIORITY.get(s['priority'], 0x20))
    return proc


def play_time(game):
    """Seconds played, as RPCS3 records them (GuiConfigs\\persistent_settings.dat, milliseconds per title ID)."""
    total = 0
    try:
        section = None
        for line in open(os.path.join(RPCS3, 'GuiConfigs', 'persistent_settings.dat'), encoding='utf-8',
                         errors='replace'):
            line = line.strip()
            if line.startswith('['):
                section = line
            elif section == '[Playtime]' and '=' in line:
                k, v = line.split('=', 1)
                if k in GAMES[game]['ids'] and v.isdigit():
                    total += int(v) // 1000
    except OSError:
        pass
    return total
