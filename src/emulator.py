# RPCS3 (GPL-2.0) and the PS3 system software, downloaded from their official sources into rpcs3\.
# Nothing of either ships with the launcher.
#   RPCS3: the newest Windows build from github.com/RPCS3/rpcs3-binaries-win (a .7z; Windows' own tar.exe
#          extracts it)
#   firmware: PS3UPDAT.PUP from Sony's update server (the same file playstation.com offers), installed by
#          RPCS3 itself (--installfw)
#   Visual C++ runtime: RPCS3 needs it; Microsoft's installer when it's missing
import json, os, re, shutil, subprocess, urllib.request

import core

REPO = 'RPCS3/rpcs3-binaries-win'
SOURCE = 'https://github.com/RPCS3/rpcs3'
API = 'https://api.github.com/repos/%s/releases/latest' % REPO
FW_LIST = 'http://fus01.ps3.update.playstation.net/update/ps3/list/us/ps3-updatelist.txt'
VCREDIST = 'https://aka.ms/vs/17/release/vc_redist.x64.exe'
VERSION = os.path.join(core.RPCS3, 'conduit_version.txt')
UA = {'User-Agent': 'Conduit-Legacy-Launcher'}
TAR = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'tar.exe')


def installed():
    return os.path.isfile(core.RPCS3_EXE)


def installed_version():
    try:
        return open(VERSION, encoding='utf-8').read().strip() or None
    except OSError:
        return None


def firmware_installed():
    return os.path.isfile(os.path.join(core.RPCS3, 'dev_flash', 'vsh', 'etc', 'version.txt'))


def firmware_version():
    try:
        t = open(os.path.join(core.RPCS3, 'dev_flash', 'vsh', 'etc', 'version.txt'), encoding='utf-8',
                 errors='replace').read()
        m = re.search(r'release:([\d.]+)', t)
        return '%.2f' % float(m.group(1)) if m else '?'
    except OSError:
        return None


def vcredist_installed():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64') as k:
            return bool(winreg.QueryValueEx(k, 'Installed')[0])
    except OSError:
        return os.path.isfile(os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32',
                                           'msvcp140_atomic_wait.dll'))


def _get(url, dest, progress, total=0):
    req = urllib.request.Request(url, headers=UA)
    done = 0
    with urllib.request.urlopen(req, timeout=60) as r, open(dest + '.part', 'wb') as f:
        total = total or int(r.headers.get('Content-Length') or 0)
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            progress(done, total)
    if total and done != total:
        os.remove(dest + '.part')
        raise RuntimeError('Download incomplete (%d of %d bytes)' % (done, total))
    os.replace(dest + '.part', dest)
    return dest


def latest():
    """(tag, version, url, size) of the newest RPCS3 build."""
    rel = json.load(urllib.request.urlopen(urllib.request.Request(API, headers=dict(
        UA, Accept='application/vnd.github+json')), timeout=20))
    for a in rel.get('assets', []):
        if a['name'].endswith('.7z'):
            m = re.match(r'rpcs3-(v[\d.]+-\d+)', a['name'])
            return rel['tag_name'], m.group(1) if m else rel['tag_name'], a['browser_download_url'], a['size']
    raise RuntimeError('No .7z in the latest RPCS3 release')


def install(progress=lambda done, total: None):
    """Downloads RPCS3 and extracts it over rpcs3\\ (keeping dev_hdd0, saves, config). Returns the version."""
    _tag, ver, url, size = latest()
    os.makedirs(core.OUT, exist_ok=True)
    arc = _get(url, os.path.join(core.OUT, 'rpcs3.7z'), progress, size)
    tmp = os.path.join(core.OUT, 'rpcs3_new')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    r = subprocess.run([TAR, '-xf', arc, '-C', tmp], capture_output=True, text=True, creationflags=core.NO_WINDOW)
    if r.returncode != 0 or not os.path.isfile(os.path.join(tmp, 'rpcs3.exe')):
        raise RuntimeError('Extraction failed: %s' % (r.stderr or r.stdout)[:300])
    os.makedirs(core.RPCS3, exist_ok=True)
    for dp, _d, fn in os.walk(tmp):
        for f in fn:
            src = os.path.join(dp, f)
            dst = os.path.join(core.RPCS3, os.path.relpath(src, tmp))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(src, dst)
    shutil.rmtree(tmp, ignore_errors=True)
    os.remove(arc)
    quiet_gui()
    open(VERSION, 'w', encoding='utf-8').write(ver)
    core.log('RPCS3 %s instalado de %s' % (ver, url))
    return ver


def firmware_url():
    req = urllib.request.Request(FW_LIST, headers=dict(UA, **{'User-Agent': 'Mozilla/5.0'}))
    text = urllib.request.urlopen(req, timeout=20).read().decode('ascii', 'replace')
    for line in text.splitlines():
        m = re.search(r'SystemSoftwareVersion=([\d.]+);CDN=(\S+PS3UPDAT\.PUP);', line)
        if m:
            return m.group(1), m.group(2)
    raise RuntimeError('PS3 update list without PS3UPDAT.PUP')


def install_firmware(progress=lambda done, total: None):
    """Downloads the PS3 system software from Sony and has RPCS3 install it. Returns its version."""
    ver, url = firmware_url()
    pup = _get(url, os.path.join(core.OUT, 'PS3UPDAT.PUP'), progress)
    quiet_gui()
    # headless: no "Install firmware?" question waiting for a click (its exit code is not meaningful)
    try:
        subprocess.run([core.RPCS3_EXE, '--headless', '--installfw', pup], cwd=core.RPCS3, env=core._clean_env(),
                       creationflags=core.NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=900)
    finally:
        os.remove(pup)
    if not firmware_installed():
        raise RuntimeError('RPCS3 did not install the firmware (see rpcs3\\log\\RPCS3.log)')
    core.log('firmware %s instalado' % ver)
    return '%.2f' % float(ver)


def quiet_gui():
    """Turns off RPCS3's own welcome, update and confirmation boxes, which would wait for a click."""
    p = os.path.join(core.RPCS3, 'GuiConfigs', 'CurrentSettings.ini')
    want = {'[main_window]': {'infoBoxEnabledWelcome': 'false', 'infoBoxEnabledInstallPUP': 'false',
                              'infoBoxEnabledInstallPKG': 'false', 'confirmationBoxExitGame': 'false',
                              'confirmationBoxBootGame': 'false', 'confirmationObsoleteCfg': 'false',
                              'confirmationRestart': 'false'},
            '[Meta]': {'checkUpdateStart': 'false'}}
    try:
        lines = open(p, encoding='utf-8').read().splitlines()
    except OSError:
        lines = []
    for section, keys in want.items():
        if section not in lines:
            lines += ['', section]
        i = lines.index(section) + 1
        end = next((j for j in range(i, len(lines)) if lines[j].startswith('[')), len(lines))
        have = {lines[j].split('=', 1)[0]: j for j in range(i, end) if '=' in lines[j]}
        for k, v in keys.items():
            if k in have:
                lines[have[k]] = '%s=%s' % (k, v)
            else:
                lines.insert(i, '%s=%s' % (k, v))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')


def install_vcredist():
    """Downloads Microsoft's Visual C++ runtime installer and runs it (it asks for admin rights)."""
    exe = _get(VCREDIST, os.path.join(core.OUT, 'vc_redist.x64.exe'), lambda d, t: None)
    subprocess.run([exe, '/install', '/passive', '/norestart'])
    return vcredist_installed()
