"""Dynamix Volume File (*.DYN) reader.

  dynvol.py list VOL.DYN [...]          -> header + directory (hash, offset, size, name)
  dynvol.py extract VOL.DYN [OUTDIR]    -> every entry to OUTDIR (default work/dyn/<vol>/)
  dynvol.py check [VOL.DYN ...]         -> verify every stored hash and the file layout
  dynvol.py all                         -> extract every Game/*.DYN to work/dyn/<vol>/

Layout (port/formats/resources.md):
  00  char[20] "Dynamix Volume File\\0"   (INTRO.EXE volume.c: read 0x16 bytes, strcmp)
  14  u16      0x001A                    (^Z, part of the 0x16-byte signature read)
  16  u16      flags: bits 13/14/15 = volume class (COMMON1 E001, SHELL1/M1SHL 4001, SIM*/M1SIM 8001),
               low 12 bits = product id (1). The open routine (INTRO 049d:0c50) takes a mask
               (default 2001 when the caller passes 0) and opens a volume only if (flags & mask)
               has a bit in both the class nibble and the low 12 bits.
  18  u16[4]   hash keys (rotate counts)
  20  u16      entry count, then padding to a 4-byte boundary (0x24)
  24  u32[n]   directory: lo = name hash, hi = distance to this entry from the previous one
               (from 0 for the first), in 4-byte units
  then entries, each at a 4-byte boundary (zero padding between):
      char[13] name (NUL-padded), u32 size, u8[size] data
"""
import glob, os, struct, sys

SIG = b'Dynamix Volume File\0'


def rotl32(h, k):
    k &= 31
    return ((h << k) | (h >> (32 - k))) & 0xffffffff if k else h


def name_hash(name, keys):
    """volume.c lookup (INTRO.EXE 049d:0e32): name upper-cased and cut to 13 chars, 13 rounds."""
    b = name.upper().encode('latin1')[:13]
    h = 0
    for i in range(13):
        c = b[i % len(b)]
        if c >= 128:
            c -= 256                      # signed char, sign-extended to 32 bits
        h = rotl32(h, keys[i % 4]) ^ (c & 0xffffffff)
    return (h % 0x1003F) & 0xffff


class Entry:
    def __init__(self, index, hash_, off, name, size, data_off):
        self.index, self.hash, self.off, self.name, self.size, self.data_off = index, hash_, off, name, size, data_off


class Volume:
    def __init__(self, path):
        self.path = path
        self.name = os.path.basename(path)
        d = self.data = open(path, 'rb').read()
        if d[:20] != SIG or d[20:22] != b'\x1a\0':
            raise ValueError('%s: not a Dynamix Volume File' % path)
        self.flags = struct.unpack_from('<H', d, 0x16)[0]
        self.keys = struct.unpack_from('<4H', d, 0x18)
        self.count = struct.unpack_from('<H', d, 0x20)[0]
        self.pad = struct.unpack_from('<H', d, 0x22)[0]
        self.entries = []
        off = 0
        for i in range(self.count):
            h, delta = struct.unpack_from('<HH', d, 0x24 + 4 * i)
            off += 4 * delta
            name = d[off:off + 13].split(b'\0')[0].decode('latin1')
            size = struct.unpack_from('<I', d, off + 13)[0]
            self.entries.append(Entry(i, h, off, name, size, off + 17))

    def get(self, e):
        return self.data[e.data_off:e.data_off + e.size]

    def find(self, name):
        """As the game does: first entry whose hash matches, then a name compare."""
        h = name_hash(os.path.basename(name), self.keys)
        for e in self.entries:
            if e.hash == h:
                return e if e.name.upper() == os.path.basename(name).upper() else None
        return None

    def users(self):
        return '+'.join(n for b, n in ((0x2000, '2000'), (0x4000, '4000'), (0x8000, '8000')) if self.flags & b)

    def check(self):
        errs = []
        end = 0x24 + 4 * self.count
        for e in self.entries:
            if e.hash != name_hash(e.name, self.keys):
                errs.append('%s: hash %04x, computed %04x' % (e.name, e.hash, name_hash(e.name, self.keys)))
            if e.off % 4 or e.off < end or any(self.data[end:e.off]):
                errs.append('%s: at %x, previous end %x' % (e.name, e.off, end))
            end = e.data_off + e.size
        tail = len(self.data) - end
        if not 0 <= tail < 4 or any(self.data[end:]):
            errs.append('file end %x, last entry end %x' % (len(self.data), end))
        return errs


def all_volumes(root='Game'):
    return [Volume(p) for p in sorted(glob.glob(os.path.join(root, '*.DYN')))]


def cmd_list(paths):
    for p in paths:
        v = Volume(p)
        print('%s: flags %04x (class %s, product %d), keys %s, %d entries' % (
            v.name, v.flags, v.users(), v.flags & 0xfff, ','.join(map(str, v.keys)), v.count))
        print('   #  hash   offset     size  name')
        for e in v.entries:
            print('%4d  %04x  %07x  %7d  %s' % (e.index, e.hash, e.off, e.size, e.name))


def cmd_extract(path, out=None):
    v = Volume(path)
    out = out or os.path.join('work', 'dyn', os.path.splitext(v.name)[0])
    os.makedirs(out, exist_ok=True)
    for e in v.entries:
        open(os.path.join(out, e.name), 'wb').write(v.get(e))
    print('%s: %d entries -> %s' % (v.name, v.count, out))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'list':
        cmd_list(args or sorted(glob.glob('Game/*.DYN')))
    elif cmd == 'extract':
        cmd_extract(args[0], args[1] if len(args) > 1 else None)
    elif cmd == 'all':
        for p in sorted(glob.glob('Game/*.DYN')):
            cmd_extract(p)
    elif cmd == 'check':
        bad = 0
        for p in args or sorted(glob.glob('Game/*.DYN')):
            v = Volume(p)
            errs = v.check()
            names = {}
            for e in v.entries:
                names.setdefault(e.hash, []).append(e.name)
            coll = [n for n in names.values() if len(n) > 1]
            print('%s: %d entries, %s%s' % (v.name, v.count, 'OK' if not errs else '%d errors' % len(errs),
                                           ', hash collisions: %s' % coll if coll else ''))
            for m in errs:
                print('   ' + m)
            bad += len(errs)
        sys.exit(1 if bad else 0)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
