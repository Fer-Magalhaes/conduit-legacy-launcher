# Installs the user's own copies of the games from .pkg and .iso files into jogos\<game>\.
# Only the releases this launcher was tested with are accepted (SUPPORTED); anything else is refused.
# PKGs are installed by RPCS3 itself, into a scratch dev_hdd0 so the real one is never touched.
# Disc images must be plain (decrypted) dumps: an encrypted image is refused, nothing is decrypted here.
import os, shutil, subprocess, time

import core
from i18n import _
from ps3iso import Iso
from sfo import parse_sfo

# file kind -> {title id: game}. For a PKG the id is the one in its content id (UP9000-NPUA80657_00-...).
SUPPORTED = {
    'pkg': {'NPUA80657': 'fob', 'NPUA98125': 'infamous2', 'BCUS98125': 'infamous2'},
    'iso': {'BCES00609': 'infamous1'},
}
FOLDERS = {'infamous1': 'inFAMOUS', 'infamous2': 'inFAMOUS 2', 'fob': 'Festival of Blood'}
VFS = os.path.join(core.RPCS3, 'config', 'vfs.yml')
VFS_BACKUP = VFS + '.conduit'  # holds the user's vfs.yml (or the word "none") while a PKG installs
WORK = os.path.join(core.OUT, 'install')


def supported_text():
    lines = []
    for kind, ids in SUPPORTED.items():
        for tid, game in ids.items():
            lines.append('%s  ·  %s  (.%s)' % (core.GAMES[game]['name'], tid, kind))
    return '\n'.join(sorted(lines))


def game_folder(game):
    return os.path.join(core.JOGOS, FOLDERS[game])


def pkg_info(path):
    """(content id, title id) from a PS3 PKG header."""
    with open(path, 'rb') as f:
        h = f.read(0x60)
    if len(h) < 0x60 or h[:4] != b'\x7fPKG':
        raise ValueError(_('"%s" não é um PKG de PS3.') % os.path.basename(path))
    cid = h[0x30:0x54].split(b'\0')[0].decode('ascii', 'replace')
    return cid, cid[7:16]


def check(paths):
    """Sorts the chosen files into [(kind, path, title id, game)], refusing anything unsupported."""
    out = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        name = os.path.basename(p)
        if ext == '.pkg':
            tid = pkg_info(p)[1]
        elif ext == '.rap':
            tid = name[7:16].upper()  # licences are named after the content id
        elif ext == '.iso':
            tid = iso_title(p)
        else:
            raise ValueError(_('"%s": escolha arquivos .pkg, .iso ou .rap.') % name)
        game = SUPPORTED['iso' if ext == '.iso' else 'pkg'].get(tid)
        if not game:
            raise ValueError(_('"%s" (%s) não é uma versão suportada. O instalador aceita só estas:\n\n%s')
                             % (name, tid or '?', supported_text()))
        out.append((ext[1:], p, tid, game))
    # licences go in after their game, updates after the game itself
    order = {'iso': 0, 'pkg': 1, 'rap': 2}
    out.sort(key=lambda x: (order[x[0]], x[2].startswith('BC')))
    return out


def iso_title(path):
    iso = Iso(path)
    try:
        sfo = iso.find('PS3_GAME/PARAM.SFO')
        if not iso.find('PS3_DISC.SFB') or not sfo:
            raise ValueError(_('"%s" não é a imagem de um disco de PS3.') % os.path.basename(path))
        try:
            return parse_sfo(iso.read(sfo)).get('TITLE_ID', '')
        except (ValueError, IndexError):
            raise ValueError(_('"%s" está criptografada. Use uma cópia decriptada, feita com a sua ferramenta '
                               'de dump.') % os.path.basename(path))
    finally:
        iso.close()


def _free(path, need):
    os.makedirs(path, exist_ok=True)
    free = shutil.disk_usage(path).free
    if free < need + (512 << 20):
        raise RuntimeError(_('Falta espaço: precisa de %.1f GB livres em %s.') % ((need >> 20) / 1024, path))


def install_iso(path, game, progress):
    iso = Iso(path)
    try:
        boot = iso.find('PS3_GAME/USRDIR/EBOOT.BIN')
        if not boot or iso.read(boot, 4) != b'SCE\0':
            raise RuntimeError(_('"%s" está criptografada. Use uma cópia decriptada, feita com a sua ferramenta '
                                 'de dump.') % os.path.basename(path))
        tid = parse_sfo(iso.read(iso.find('PS3_GAME/PARAM.SFO')))['TITLE_ID']
        dest = os.path.join(game_folder(game), tid)
        if os.path.exists(dest):
            raise RuntimeError(_('Já existe %s. Apague ou renomeie essa pasta para instalar de novo.') % dest)
        _free(game_folder(game), sum(iso.size(p) for p in iso.files))
        part = dest + '.parcial'
        if os.path.lexists(part):
            core.safe_remove(part)
        iso.extract(part, progress)
    finally:
        iso.close()
    os.replace(part, dest)
    return dest


def _redirect_hdd(hdd):
    if not os.path.exists(VFS_BACKUP):
        if os.path.isfile(VFS):
            shutil.copy2(VFS, VFS_BACKUP)
        else:
            open(VFS_BACKUP, 'w').write('none')
    os.makedirs(os.path.dirname(VFS), exist_ok=True)
    with open(VFS, 'w', encoding='utf-8') as f:
        f.write('/dev_hdd0/: %s/\n' % hdd.replace('\\', '/').rstrip('/'))


def restore_vfs():
    """Puts back the user's RPCS3 folders; also runs before every game in case an install was cut short."""
    if not os.path.exists(VFS_BACKUP):
        return
    if open(VFS_BACKUP, 'rb').read() == b'none':
        if os.path.exists(VFS):
            os.unlink(VFS)
        os.unlink(VFS_BACKUP)
    else:
        os.replace(VFS_BACKUP, VFS)


def _size(path):
    total = 0
    for dp, _d, fn in os.walk(path):
        for f in fn:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except OSError:
                pass
    return total


def _merge(src, dst):
    """Moves src's files into dst, replacing older ones (an update over its game)."""
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.replace(src, dst)
        return
    for dp, _d, fn in os.walk(src):
        target = os.path.join(dst, os.path.relpath(dp, src))
        os.makedirs(target, exist_ok=True)
        for f in fn:
            os.replace(os.path.join(dp, f), os.path.join(target, f))
    core.safe_remove(src)


def install_pkg(path, game, progress):
    import emulator
    if not emulator.installed():
        raise RuntimeError(_('Instale o RPCS3 primeiro (quadro Emulador): é ele que instala os PKGs.'))
    size = os.path.getsize(path)
    _free(core.OUT, size)
    _free(game_folder(game), size)
    if os.path.lexists(WORK):
        core.safe_remove(WORK)
    hdd = os.path.join(WORK, 'hdd')
    os.makedirs(hdd)
    _redirect_hdd(hdd)
    try:
        p = subprocess.Popen([core.RPCS3_EXE, '--headless', '--installpkg', path], cwd=core.RPCS3,
                             env=core._clean_env(), creationflags=core.NO_WINDOW,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        games = os.path.join(hdd, 'game')
        while p.poll() is None:
            time.sleep(1)
            progress(min(_size(games), size), size)
    finally:
        restore_vfs()
    cid, tid = pkg_info(path)
    src = os.path.join(hdd, 'game', tid)
    if not os.path.isfile(os.path.join(src, 'PARAM.SFO')):
        raise RuntimeError(_('O RPCS3 não conseguiu instalar "%s". Veja rpcs3\\log\\RPCS3.log.')
                           % os.path.basename(path))
    dest = os.path.join(game_folder(game), tid)
    _merge(src, dest)
    core.safe_remove(WORK)
    return dest


def install(paths, progress=lambda done, total: None):
    """Installs the chosen files. Returns (games installed, notes for the user)."""
    if core.rpcs3_running():
        raise RuntimeError(_('Feche o jogo antes de instalar.'))
    items = check(paths)
    games, notes = [], []
    for kind, path, tid, game in items:
        core.log('instalando %s (%s) para %s' % (path, tid, game))
        if kind == 'iso':
            install_iso(path, game, progress)
        elif kind == 'pkg':
            install_pkg(path, game, progress)
        else:
            os.makedirs(game_folder(game), exist_ok=True)
            shutil.copy2(path, os.path.join(game_folder(game), os.path.basename(path)))
        if game not in games:
            games.append(game)
    if 'fob' in games and not any(f.lower().endswith('.rap') for f in os.listdir(game_folder('fob'))):
        notes.append(_('O Festival of Blood precisa da licença .rap da sua conta: instale o arquivo .rap também.'))
    return games, notes
