# Community patches and cheats from RPCS3's own patch database (downloaded, never shipped).
# The chosen ones are re-declared in rpcs3\patches\imported_patch.yml for every release of the game and
# any app version (PSN conversions such as the inFAMOUS 2 one ship an update without APP_VER, so the
# database's "01.04" entries would never match); the PPU hash still ties each patch to its executable.
import json, os, re, urllib.request

import yaml

import core
from i18n import _

API = 'https://rpcs3.net/compatibility?patch&api=v1&v=1.2'
DB = os.path.join(core.RPCS3, 'patches', 'patch.yml')
IMPORTED = os.path.join(core.RPCS3, 'patches', 'imported_patch.yml')
PATCH_CONFIG = os.path.join(core.RPCS3, 'config', 'patch_config.yml')
PREFIX = 'Conduit - '
TITLES = {'infamous1': r'^infamous$', 'infamous2': r'^infamous 2$', 'fob': r'festival of blood'}
# Portuguese names and notes for the patches these games have; others keep their own name
NAMES = {
    'Skip Intro': (_('Pular os vídeos de abertura'), _('Vai direto ao menu.')),
    'Disable Mesh Trimming': (_('Sem corte de malha'), _('Necessário acima de 720p: sem ele aparecem buracos e '
                                                        'objetos somem.')),
    'All powers unlocked': (_('Todos os poderes desbloqueados'), _('Cheat: libera todos os poderes do Cole.')),
    'Disable speed limit': (_('Sem limite de velocidade'), _('O Cole corre e desliza mais rápido.')),
    'Disable refraction/shifting effect': (_('Sem efeito de refração'), _('Tira a distorção do ar quente e da '
                                                                         'água.')),
    'Change FOV': (_('Campo de visão maior'), _('Câmera mais aberta.')),
    'Extended FOV': (_('Campo de visão maior'), _('Câmera mais aberta.')),
    'Disable Shadows': (_('Sem sombras'), _('Mais FPS em PCs fracos.')),
    'Skip UGC Tutorial': (_('Pular tutorial de missões criadas'), ''),
    'Circular Stick Mapping (2% Deadzone)': (_('Analógico circular'), _('Zona morta de 2% nos analógicos.')),
    'High-Resolution Blur and Bloom Fix': (_('Correção de desfoque em alta resolução'), _('Brilho e desfoque '
                                                                                         'certos acima de 720p.')),
}
AUTO = {'Disable Mesh Trimming'}  # on by itself above 720p


class _Loader(yaml.SafeLoader):
    """The database redefines some anchors; YAML allows that, PyYAML's default loader doesn't."""

    def compose_node(self, parent, index):
        if not self.check_event(yaml.AliasEvent):
            ev = self.peek_event()
            if ev.anchor is not None:
                self.anchors.pop(ev.anchor, None)
        return super().compose_node(parent, index)


class _Hex(str):
    """A number kept as written (0x...): RPCS3 wants patch addresses in hex."""


def _construct_int(loader, node):
    text = loader.construct_scalar(node)
    return _Hex(text) if text.lower().startswith(('0x', '-0x')) else int(text.replace('_', ''), 0)


_Loader.add_constructor('tag:yaml.org,2002:int', _construct_int)


class _Dumper(yaml.SafeDumper):
    pass


_Dumper.add_representer(_Hex, lambda d, v: d.represent_scalar('tag:yaml.org,2002:int', str(v)))


def download():
    req = urllib.request.Request(API, headers={'User-Agent': 'Conduit-Legacy-Launcher'})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    text = d['patch']
    yaml.load(text, Loader=_Loader)  # refuse anything that isn't a patch file
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    open(DB + '.tmp', 'w', encoding='utf-8').write(text)
    os.replace(DB + '.tmp', DB)
    return len(for_game('infamous1')) + len(for_game('infamous2')) + len(for_game('fob'))


_cache = {}


def _db():
    try:
        stamp = os.path.getmtime(DB)
    except OSError:
        return {}
    if _cache.get('stamp') != stamp:
        try:
            _cache['data'] = yaml.load(open(DB, encoding='utf-8'), Loader=_Loader) or {}
        except (OSError, yaml.YAMLError):
            _cache['data'] = {}
        _cache['stamp'] = stamp
    return _cache['data']


def for_game(game):
    """[{name, title, desc, author, entries: [(hash, entry)]}] for every release of the game."""
    out = {}
    for h, patches in _db().items():
        if not str(h).startswith('PPU-') or not isinstance(patches, dict):
            continue
        for name, e in patches.items():
            if not isinstance(e, dict):
                continue
            titles = list((e.get('Games') or {}).keys())
            if not any(re.search(TITLES[game], str(t).strip(), re.I) for t in titles):
                continue
            title, desc = NAMES.get(name, (name, ''))
            p = out.setdefault(name, {'name': name, 'title': title, 'desc': desc or (e.get('Notes') or '')[:160],
                                      'author': e.get('Author', ''), 'entries': [], 'auto': name in AUTO})
            p['entries'].append((h, e))
    return sorted(out.values(), key=lambda p: (p['auto'], p['title']))


def apply(game, serial, gs):
    """Writes the enabled patches of every game into RPCS3's imported_patch.yml and patch_config.yml."""
    import copy
    settings = core.load_settings()['games']
    imported, enabled = {}, {}
    for k in core.GAMES:
        o = gs if k == game else settings[k]
        on = set(o['patches_on'])
        if int(o['res']) > 100:
            on |= AUTO
        for p in for_game(k):
            label = PREFIX + p['name']
            for h, e in p['entries']:
                e = copy.deepcopy(e)
                titles = list((e.get('Games') or {}).keys()) or [core.GAMES[k]['name']]
                e['Games'] = {titles[0]: {sid: ['All'] for sid in core.GAMES[k]['ids']}}
                e['Notes'] = str(e.get('Notes') or '')
                imported.setdefault(h, {})[label] = e
                if p['name'] in on:
                    enabled.setdefault(h, {})[label] = {titles[0]: {sid: {'All': {'Enabled': True}}
                                                                    for sid in core.GAMES[k]['ids']}}
    os.makedirs(os.path.dirname(IMPORTED), exist_ok=True)
    with open(IMPORTED, 'w', encoding='utf-8') as f:
        f.write('Version: 1.2\n\n')
        if imported:
            yaml.dump(imported, f, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=None,
                      width=200)
    os.makedirs(os.path.dirname(PATCH_CONFIG), exist_ok=True)
    with open(PATCH_CONFIG, 'w', encoding='utf-8') as f:
        if enabled:
            yaml.safe_dump(enabled, f, sort_keys=False, allow_unicode=True, default_flow_style=False)
    names = sorted({n for h in enabled.values() for n in h})
    core.log('patches: ' + (', '.join(n[len(PREFIX):] for n in names) or 'nenhum'))
