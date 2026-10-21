# Reads PS3 disc images (ISO 9660 with Joliet names), enough to list and extract their files.
# Only plain images are supported: a disc image that is still encrypted is detected and refused, the
# launcher never decrypts discs.
import os, struct

SECTOR = 2048


class Iso:
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.files = {}  # 'PS3_GAME/USRDIR/EBOOT.BIN' -> [(lba, size), ...] (big files have several extents)
        root = None
        for n in range(16, 64):
            d = self._read(n * SECTOR, SECTOR)
            if len(d) < SECTOR or d[1:6] != b'CD001' or d[0] == 255:
                break
            if d[0] == 1 and root is None:
                root = (d[156:190], False)
            elif d[0] == 2 and d[88:90] == b'%/' and d[90:91] in b'@CE':
                root = (d[156:190], True)  # Joliet keeps the real file names
        if root is None:
            raise ValueError('not an ISO 9660 image')
        self.joliet = root[1]
        lba, size = struct.unpack('<I', root[0][2:6])[0], struct.unpack('<I', root[0][10:14])[0]
        self._walk(lba, size, '', set())

    def _read(self, pos, n):
        self.f.seek(pos)
        return self.f.read(n)

    def _walk(self, lba, size, prefix, seen):
        if lba in seen:
            return
        seen.add(lba)
        data = self._read(lba * SECTOR, size)
        pos = 0
        while pos < len(data):
            ln = data[pos]
            if ln == 0:  # records never cross a sector: the rest of this one is padding
                pos = (pos // SECTOR + 1) * SECTOR
                continue
            r = data[pos:pos + ln]
            pos += ln
            nl = r[32]
            raw = r[33:33 + nl]
            if raw in (b'\0', b'\1'):
                continue
            name = raw.decode('utf-16-be' if self.joliet else 'ascii', 'replace').split(';')[0].rstrip('.')
            elba, esize, flags = struct.unpack('<I', r[2:6])[0], struct.unpack('<I', r[10:14])[0], r[25]
            path = prefix + name
            if flags & 2:
                self._walk(elba, esize, path + '/', seen)
            else:
                self.files.setdefault(path, []).append((elba, esize))

    def find(self, path):
        """Case-insensitive lookup; returns the stored name or None."""
        low = path.lower()
        return next((p for p in self.files if p.lower() == low), None)

    def size(self, path):
        return sum(s for _l, s in self.files[path])

    def read(self, path, n=None):
        out = b''
        for lba, s in self.files[path]:
            out += self._read(lba * SECTOR, s if n is None else min(s, n - len(out)))
            if n is not None and len(out) >= n:
                break
        return out

    def extract(self, dest, progress=lambda done, total: None):
        total = sum(self.size(p) for p in self.files)
        done = 0
        for path in self.files:
            out = os.path.join(dest, *path.split('/'))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, 'wb') as w:
                for lba, s in self.files[path]:
                    self.f.seek(lba * SECTOR)
                    while s:
                        chunk = self.f.read(min(s, 8 << 20))
                        if not chunk:
                            raise IOError('image is truncated: %s' % path)
                        w.write(chunk)
                        s -= len(chunk)
                        done += len(chunk)
                        progress(done, total)
        return total

    def close(self):
        self.f.close()
