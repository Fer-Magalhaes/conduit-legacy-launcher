# Which controllers are plugged in, by USB/Bluetooth vendor and product id, like Steam does.
# Reads the present HID devices from Windows' device tree (cfgmgr32); no driver or library needed.
import ctypes, re
from ctypes import wintypes
from i18n import _

# (vendor, product) -> (kind, name). kind: 'xbox', 'playstation', 'nintendo'
KNOWN = {
    (0x054C, 0x05C4): ('playstation', 'DualShock 4'),
    (0x054C, 0x09CC): ('playstation', 'DualShock 4'),
    (0x054C, 0x0BA0): ('playstation', 'DualShock 4 (adaptador sem fio)'),
    (0x054C, 0x0CE6): ('playstation', 'DualSense'),
    (0x054C, 0x0DF2): ('playstation', 'DualSense Edge'),
    (0x054C, 0x0268): ('playstation', 'DualShock 3'),
    (0x057E, 0x2009): ('nintendo', 'Switch Pro Controller'),
    (0x057E, 0x2006): ('nintendo', 'Joy-Con (L)'),
    (0x057E, 0x2007): ('nintendo', 'Joy-Con (R)'),
    (0x057E, 0x2017): ('nintendo', _('Controle SNES (Switch)')),
}
VENDORS = {0x045E: ('xbox', _('Controle Xbox')), 0x054C: ('playstation', _('Controle PlayStation')),
           0x057E: ('nintendo', _('Controle Nintendo')), 0x2DC8: ('other', '8BitDo'),
           0x0F0D: ('other', 'Hori'), 0x0E6F: ('other', 'PDP'), 0x24C6: ('other', 'PowerA'),
           0x146B: ('other', 'Nacon'), 0x1532: ('other', 'Razer'), 0x046D: ('other', 'Logitech')}
KIND_NAMES = {'xbox': 'Xbox / XInput', 'playstation': 'PlayStation', 'nintendo': 'Nintendo', 'other': _('Outro')}
STEAM_VIRTUAL = 0x28DE  # Steam Input's virtual pads

_cfg = ctypes.windll.cfgmgr32


def _ids():
    flags = 0x1 | 0x100  # FILTER_ENUMERATOR | FILTER_PRESENT
    size = wintypes.ULONG()
    if _cfg.CM_Get_Device_ID_List_SizeW(ctypes.byref(size), 'HID', flags) != 0:
        return []
    buf = ctypes.create_unicode_buffer(size.value)
    if _cfg.CM_Get_Device_ID_ListW('HID', buf, size, flags) != 0:
        return []
    return [x for x in buf[:size.value].split('\0') if x]


def _hwids(dev_id):
    inst = wintypes.DWORD()
    if _cfg.CM_Locate_DevNodeW(ctypes.byref(inst), dev_id, 0) != 0:
        return []
    size = wintypes.ULONG(0)
    _cfg.CM_Get_DevNode_Registry_PropertyW(inst, 2, None, None, ctypes.byref(size), 0)  # CM_DRP_HARDWAREID
    if not size.value:
        return []
    buf = ctypes.create_unicode_buffer(size.value // 2 + 1)
    if _cfg.CM_Get_DevNode_Registry_PropertyW(inst, 2, None, buf, ctypes.byref(size), 0) != 0:
        return []
    return [x for x in buf[:size.value // 2].split('\0') if x]


_VIDPID = re.compile(r'VID_([0-9A-F]{4})&PID_([0-9A-F]{4})|VID&0002([0-9A-F]{4})_PID&([0-9A-F]{4})', re.I)


def detect():
    """[{kind, name, vid, pid, bluetooth}] one per physical controller."""
    found = {}
    for dev in _ids():
        m = _VIDPID.search(dev)
        if not m:
            continue
        vid = int(m.group(1) or m.group(3), 16)
        pid = int(m.group(2) or m.group(4), 16)
        xinput = 'IG_' in dev.upper()
        if (vid, pid) not in KNOWN and not xinput:
            hw = ' '.join(_hwids(dev)).upper()
            if not ('HID_DEVICE_SYSTEM_GAME' in hw or 'UP:0001_U:0005' in hw or 'UP:0001_U:0004' in hw):
                continue
        kind, name = KNOWN.get((vid, pid)) or (('xbox', _('Controle Xbox')) if vid == 0x045E else
                                                ('xbox', VENDORS.get(vid, ('', _('Controle')))[1] + _(' (modo XInput)'))
                                                if xinput else VENDORS.get(vid, ('other', _('Controle genérico'))))
        bt = '{00001124' in dev.upper() or 'VID&0002' in dev.upper() or 'BTH' in dev.upper()
        # one physical pad shows up as several HID interfaces and collections
        found.setdefault((vid, pid, bt), {'kind': kind, 'name': name + (' (Bluetooth)' if bt else ''), 'vid': vid,
                               'pid': pid, 'bluetooth': bt})
    pads = list(found.values())
    real = [p for p in pads if p['vid'] != STEAM_VIRTUAL]
    return real or pads


def kind_of(pads):
    """'xbox' / 'playstation' / 'nintendo' / 'other' when every pad is that kind, 'mixed', or None."""
    kinds = {p['kind'] for p in pads}
    if not kinds:
        return None
    return kinds.pop() if len(kinds) == 1 else 'mixed'
