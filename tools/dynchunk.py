"""Dynamix tagged chunks (DGDS style) inside Dynamix Volume File entries.

  dynchunk.py tree VOL.DYN NAME         -> chunk tree of one entry (sizes, compression, first bytes)
  dynchunk.py tree FILE                 -> same for an extracted file
  dynchunk.py dump VOL.DYN NAME OUTDIR  -> every leaf chunk (decompressed) to OUTDIR/<NAME>.<path>.bin
  dynchunk.py check                     -> decompress every packed chunk of every volume, report sizes

Chunk: char[4] tag ("XXX:"), u32 size (bit 31 = container: the payload is a list of chunks),
payload. Chunks that are packed (see PACKED) start with u8 method + u32 unpacked size:
  method 1 = RLE, method 2 = LZW (both below; port/formats/resources.md).
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynvol

# Leaf chunk paths whose payload is [u8 method][u32 unpacked size][packed data].
PACKED = {'BMP:BIN:', 'BMP:VGA:', 'SCR:BIN:', 'SCR:VGA:', 'TT3:', 'SSM:SNG:'} | \
         {'OVL:' + t for t in ('VGA:', 'EGA:', 'MCG:', 'CGA:', 'TAN:', 'HEG:', 'EVG:', 'EVA:')} | \
         {'SSM:' + t for t in ('M32:', 'NLD:', 'ADL:', 'TAN:', 'PS1:', 'STD:', '001:', '003:', '101:')}


class Chunk:
    def __init__(self, tag, path, off, size, container, data, children=None):
        self.tag, self.path, self.off, self.size, self.container = tag, path, off, size, container
        self.raw = data                          # payload as stored
        self.children = children or []
        self.method = None
        self.unpacked_size = None
        if not container and path in PACKED and size >= 5:
            self.method = data[0]
            self.unpacked_size = struct.unpack_from('<I', data, 1)[0]

    @property
    def data(self):
        """Payload, decompressed if packed."""
        if self.method is None:
            return self.raw
        return decompress(self.method, self.raw[5:], self.unpacked_size)

    def find(self, path):
        for c in self.walk():
            if c.path == path:
                return c
        return None

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


def is_tag(b):
    return len(b) == 4 and b[3] == 0x3A and all(0x20 <= x < 0x7F for x in b[:3])


def parse(d, off=0, end=None, prefix=''):
    """List of top-level chunks of d[off:end]. Raises ValueError if the bytes are not a chunk list."""
    end = len(d) if end is None else end
    out = []
    p = off
    while p < end:
        if p + 8 > end or not is_tag(d[p:p + 4]):
            raise ValueError('no chunk at %x' % p)
        tag = d[p:p + 4].decode('latin1')
        sz = struct.unpack_from('<I', d, p + 4)[0]
        cont = bool(sz >> 31)
        sz &= 0x7FFFFFFF
        if p + 8 + sz > end:
            raise ValueError('%s at %x overruns (%d)' % (tag, p, sz))
        path = prefix + tag
        kids = parse(d, p + 8, p + 8 + sz, path) if cont else None
        out.append(Chunk(tag, path, p, sz, cont, d[p + 8:p + 8 + sz], kids))
        p += 8 + sz
    return out


def try_parse(d):
    try:
        return parse(d) if d and is_tag(d[:4]) else None
    except ValueError:
        return None


# ---------------------------------------------------------------- decompression

def unrle(src, n):
    """Method 1. Control byte c: c & 0x80 -> repeat the next byte (c & 0x7F) times;
    otherwise copy the next c bytes."""
    out = bytearray()
    i = 0
    while len(out) < n and i < len(src):
        c = src[i]
        i += 1
        if c & 0x80:
            out += bytes([src[i]]) * (c & 0x7F)
            i += 1
        else:
            out += src[i:i + c]
            i += c
    return bytes(out[:n])


def unlzw(src, n):
    """Method 2. LZW, codes LSB-first, 9..12 bits; 100h = clear. Codes are read in groups of 8
    (a group of 8 codes of b bits is b bytes): on a clear the rest of the current group is skipped,
    and a width change starts a new group count. Dictionary: 256 literals, next free code 101h."""
    out = bytearray()
    bitpos = 0
    total = len(src) * 8
    nbits = 9
    free = 0x101
    group = 0                                    # bits read in the current group
    prefix = [0] * 4096
    suffix = [0] * 4096
    last = None
    lastchar = 0

    def getbits(k):
        nonlocal bitpos
        if bitpos + k > total:
            return None
        i = bitpos >> 3
        v = int.from_bytes(src[i:i + 3], 'little') >> (bitpos & 7)
        bitpos += k
        return v & ((1 << k) - 1)

    while len(out) < n:
        code = getbits(nbits)
        if code is None:
            break
        group += nbits
        if group >= nbits * 8:
            group -= nbits * 8
        if code == 0x100:
            if group:
                bitpos += nbits * 8 - group
            nbits, free, group, last = 9, 0x101, 0, None
            continue
        if last is None:
            out.append(code & 0xFF)
            last, lastchar = code, code & 0xFF
            continue
        cur = code
        stack = bytearray()
        if code >= free:
            stack.append(lastchar)
            cur = last
        while cur > 0xFF:
            stack.append(suffix[cur])
            cur = prefix[cur]
        stack.append(cur)
        lastchar = cur
        stack.reverse()
        out += stack
        if free < 4096:
            prefix[free] = last
            suffix[free] = lastchar
            free += 1
            if free >= (1 << nbits) and nbits < 12:
                nbits += 1
                group = 0
        last = code
    return bytes(out[:n])


def decompress(method, src, n):
    if method == 0:
        return bytes(src[:n])
    if method == 1:
        return unrle(src, n)
    if method == 2:
        return unlzw(src, n)
    raise ValueError('unknown compression method %d' % method)


# ---------------------------------------------------------------- CLI

def load_entry(args):
    """(name, bytes) from 'VOL.DYN NAME' or a plain file."""
    if len(args) >= 2 and args[0].upper().endswith('.DYN'):
        v = dynvol.Volume(args[0])
        e = v.find(args[1])
        if e is None:
            sys.exit('%s: no entry %s' % (args[0], args[1]))
        return e.name, v.get(e)
    return os.path.basename(args[0]), open(args[0], 'rb').read()


def print_tree(chunks, depth=0):
    for c in chunks:
        extra = ''
        if c.method is not None:
            extra = ' packed m%d -> %d' % (c.method, c.unpacked_size)
        head = c.raw[:16].hex(' ') if not c.container else ''
        print('%s%06x %s %d%s%s  %s' % ('  ' * depth, c.off, c.tag, c.size, ' {' if c.container else '', extra, head))
        if c.container:
            print_tree(c.children, depth + 1)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == 'tree':
        name, d = load_entry(args)
        ch = try_parse(d)
        print('%s: %d bytes' % (name, len(d)))
        if ch is None:
            print('  not a chunk file; first bytes: %s' % d[:32].hex(' '))
        else:
            print_tree(ch, 1)
    elif cmd == 'dump':
        name, d = load_entry(args[:2])
        out = args[2] if len(args) > 2 else os.path.join('work', 'chunks')
        os.makedirs(out, exist_ok=True)
        for top in parse(d):
            for c in top.walk():
                if not c.container:
                    fn = os.path.join(out, '%s.%x.%s.bin' % (name, c.off, c.path.replace(':', '')))
                    open(fn, 'wb').write(c.data)
                    print(fn, len(c.data))
    elif cmd == 'check':
        bad = n = 0
        for v in dynvol.all_volumes():
            for e in v.entries:
                ch = try_parse(v.get(e))
                for top in ch or []:
                    for c in top.walk():
                        if c.method is None:
                            continue
                        n += 1
                        got = len(c.data)
                        if got != c.unpacked_size:
                            bad += 1
                            print('%s %s %s m%d: %d of %d' % (v.name, e.name, c.path, c.method, got, c.unpacked_size))
        print('%d packed chunks, %d short' % (n, bad))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
