# Live cheats: while a game runs, the launcher keeps a value in the emulated PS3 memory.
# RPCS3 maps the PS3's 4 GB address space into its own process, with the game's code at PS3 address
# 0x10000. Each cheat names the executable it was made for (a hash of the first bytes of its code), so a
# different release or update is left alone. Nothing on disk is changed.
import ctypes, ctypes.wintypes as wt, hashlib, struct, threading, time

import core
from i18n import _

# inFAMOUS 2 1.04 (BCUS98125 update): the player's progress object sits at a fixed address
INF2_104 = '5b2d8df2bcfcadf4d10b1b29b2e4c96c11828f30'
CHEATS = {
    'infamous2': [
        {'id': 'xp', 'title': _('XP infinito'),
         'desc': _('O XP disponível fica em 99.999: compre todos os poderes já liberados. O XP fica salvo.'),
         'exe': INF2_104, 'addr': 0xa64e50, 'value': struct.pack('>i', 99999)},
    ],
}
PROBE = 0x10000, 256  # PS3 address and length of the bytes hashed to recognise the executable

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.CloseHandle.argtypes = [wt.HANDLE]
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                                  ctypes.POINTER(ctypes.c_size_t)]
k32.WriteProcessMemory.argtypes = k32.ReadProcessMemory.argtypes
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.VirtualQueryEx.restype = ctypes.c_size_t
ACCESS = 0x0010 | 0x0020 | 0x0008 | 0x0400  # VM_READ | VM_WRITE | VM_OPERATION | QUERY_INFORMATION


class _MBI(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', wt.DWORD), ('PartitionId', wt.WORD), ('RegionSize', ctypes.c_size_t),
                ('State', wt.DWORD), ('Protect', wt.DWORD), ('Type', wt.DWORD)]


def for_game(game):
    return CHEATS.get(game, [])


class Trainer(threading.Thread):
    def __init__(self, game, pid, enabled):
        super().__init__(daemon=True)
        self.cheats = [c for c in for_game(game) if c['id'] in enabled]
        self.pid = pid
        self.stop = threading.Event()

    def _read(self, h, addr, n):
        buf = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)) or got.value != n:
            return None
        return buf.raw

    def _base(self, h):
        """Host address of PS3 address 0 and the hash of the game's first code bytes, or (None, None)."""
        m = _MBI()
        a = 0
        while k32.VirtualQueryEx(h, ctypes.c_void_p(a), ctypes.byref(m), ctypes.sizeof(m)):
            b = m.BaseAddress or 0
            if m.State == 0x1000 and b & 0xFFFFFFFF == PROBE[0] and m.RegionSize >= PROBE[1]:
                d = self._read(h, b, PROBE[1])
                if d and d[:4] != b'\0\0\0\0':
                    return b - PROBE[0], hashlib.sha1(d).hexdigest()
            a = b + m.RegionSize
            if a >= 1 << 47:
                break
        return None, None

    def run(self):
        if not self.cheats:
            return
        h = k32.OpenProcess(ACCESS, False, self.pid)
        if not h:
            core.log('cheats: sem acesso ao RPCS3')
            return
        try:
            base = None
            while not self.stop.wait(2) and base is None:  # the game's code shows up once it has booted
                base, exe = self._base(h)
                if base is not None:
                    self.cheats = [c for c in self.cheats if c['exe'] == exe]
                    core.log('cheats: %s' % (', '.join(c['id'] for c in self.cheats) or
                                             'executável diferente, nenhum aplicado'))
            got = ctypes.c_size_t()
            while self.cheats and not self.stop.wait(0.25):
                for c in self.cheats:
                    if self._read(h, base + c['addr'], len(c['value'])) != c['value']:
                        k32.WriteProcessMemory(h, ctypes.c_void_p(base + c['addr']), c['value'], len(c['value']),
                                               ctypes.byref(got))
        finally:
            k32.CloseHandle(h)
