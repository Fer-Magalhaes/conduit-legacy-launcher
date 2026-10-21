# Adds the games to the Steam library as non-Steam shortcuts, with artwork and Steam Input off.
import os, re, shutil, struct, subprocess, time, winreg, zlib

from i18n import _

NO_WINDOW = 0x08000000


def steam_root():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as k:
        return os.path.normpath(winreg.QueryValueEx(k, 'SteamPath')[0])


def user_config():
    """config folder of the Steam account that logged in last."""
    root = os.path.join(steam_root(), 'userdata')
    dirs = [os.path.join(root, d, 'config') for d in os.listdir(root) if d.isdigit()]
    dirs = [d for d in dirs if os.path.isfile(os.path.join(d, 'localconfig.vdf'))]
    if not dirs:
        raise RuntimeError(_('Nenhuma conta da Steam encontrada.'))
    return max(dirs, key=lambda d: os.path.getmtime(os.path.join(d, 'localconfig.vdf')))


# binary VDF (shortcuts.vdf)
def _parse(b, i=0):
    d = {}
    while True:
        t = b[i]
        i += 1
        if t == 8:
            return d, i
        j = b.index(b'\0', i)
        key = b[i:j].decode('utf-8', 'replace')
        i = j + 1
        if t == 0:
            d[key], i = _parse(b, i)
        elif t == 1:
            j = b.index(b'\0', i)
            d[key] = b[i:j].decode('utf-8', 'replace')
            i = j + 1
        elif t == 2:
            d[key] = struct.unpack('<I', b[i:i + 4])[0]
            i += 4
        else:
            raise ValueError('unknown vdf type %d' % t)


def _dump(d):
    out = b''
    for k, v in d.items():
        kb = k.encode() + b'\0'
        if isinstance(v, dict):
            out += b'\0' + kb + _dump(v)
        elif isinstance(v, int):
            out += b'\2' + kb + struct.pack('<I', v)
        else:
            out += b'\1' + kb + str(v).encode() + b'\0'
    return out + b'\x08'


def _running():
    r = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq steam.exe', '/NH'], capture_output=True, text=True,
                       creationflags=NO_WINDOW)
    return 'steam.exe' in r.stdout.lower()


def add(name, exe, args, art_dir):
    return add_many([(name, exe, args, art_dir)])[0]


def add_many(items):
    """Adds/replaces shortcuts given as (name, exe, args, art dir). Closes Steam while editing and reopens it."""
    cfg = user_config()
    steam_exe = os.path.join(steam_root(), 'steam.exe')
    was_running = _running()
    if was_running:
        subprocess.run([steam_exe, '-shutdown'], creationflags=NO_WINDOW)
        for _ in range(60):
            if not _running():
                break
            time.sleep(1)
        time.sleep(2)
    vdf = os.path.join(cfg, 'shortcuts.vdf')
    if os.path.isfile(vdf):
        shutil.copy2(vdf, vdf + '.bak-collection')
        root, _ = _parse(open(vdf, 'rb').read(), 0)
        keep = list(root.get('shortcuts', {}).values())
    else:
        keep = []
    ids = [_add(cfg, keep, *it) for it in items]
    open(vdf, 'wb').write(_dump({'shortcuts': {str(i): v for i, v in enumerate(keep)}}))
    for appid in ids:
        _no_steam_input(cfg, appid)
    if was_running:
        subprocess.Popen([steam_exe], creationflags=NO_WINDOW)
    return ids


def _add(cfg, keep, name, exe, args, art_dir):
    exe_q = '"%s"' % exe
    appid = zlib.crc32((exe_q + name).encode()) | 0x80000000
    keep[:] = [v for v in keep if v.get('AppName', v.get('appname', '')).lower() != name.lower()]
    grid = os.path.join(cfg, 'grid')
    os.makedirs(grid, exist_ok=True)
    icon = ''
    for src, suffix in (('cover', 'p'), ('wide', ''), ('hero', '_hero'), ('logo', '_logo'), ('icon', '_icon')):
        for ext in ('.png', '.jpg'):
            p = os.path.join(art_dir, src + ext)
            if os.path.isfile(p):
                dst = os.path.join(grid, '%d%s%s' % (appid, suffix, ext))
                shutil.copy2(p, dst)
                if src == 'icon':
                    icon = dst
                break
    keep.append({
        'appid': appid, 'AppName': name, 'Exe': exe_q, 'StartDir': '"%s"' % os.path.dirname(exe),
        'icon': icon, 'ShortcutPath': '', 'LaunchOptions': args, 'IsHidden': 0, 'AllowDesktopConfig': 1,
        'AllowOverlay': 1, 'OpenVR': 0, 'Devkit': 0, 'DevkitGameID': '', 'DevkitOverrideAppID': 0,
        'LastPlayTime': 0, 'FlatpakAppID': '', 'sortas': '', 'tags': {},
    })
    return appid


def _no_steam_input(cfg, appid):
    # Steam Input off for this shortcut: the games read the controller through RPCS3's XInput handler
    lc = os.path.join(cfg, 'localconfig.vdf')
    text = open(lc, encoding='utf-8').read()
    if '\t\t"%d"\n\t\t{\n\t\t\t"UseSteamControllerConfig"' % appid not in text:
        anchor = '\t"apps"\n\t{\n'
        if text.count(anchor) == 1:
            shutil.copy2(lc, lc + '.bak-collection')
            text = text.replace(anchor, anchor + '\t\t"%d"\n\t\t{\n\t\t\t"UseSteamControllerConfig"\t\t"2"\n'
                                '\t\t\t"SteamControllerRumble"\t\t"-1"\n\t\t\t"SteamControllerRumbleIntensityV2"\t\t"0"\n'
                                '\t\t}\n' % appid)
            open(lc, 'w', encoding='utf-8', newline='\n').write(text)
