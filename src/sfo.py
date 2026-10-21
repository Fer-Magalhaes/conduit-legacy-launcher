import struct


def parse_sfo(b):
    if b[:4] != b'\0PSF':
        raise ValueError('not a PARAM.SFO')
    ko, do, n = struct.unpack('<III', b[8:20])
    out = {}
    for i in range(n):
        k, fmt, ln, mx, off = struct.unpack('<HHIII', b[20 + i * 16:36 + i * 16])
        key = b[ko + k:b.index(b'\0', ko + k)].decode()
        v = b[do + off:do + off + ln]
        out[key] = struct.unpack('<I', v[:4])[0] if fmt == 0x404 else v.rstrip(b'\0').decode('utf8', 'replace')
    return out


def read_sfo(path):
    return parse_sfo(open(path, 'rb').read())
