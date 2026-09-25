"""Dynamix pictures (DGDS style) -> PNG.

  dynimg.py all                    -> every .PAL/.BMP/.SCR/.FNT of every volume to work/img/<vol>/,
                                      plus contact sheets work/img/<vol>/sheet_<kind>.png
  dynimg.py one VOL.DYN NAME [PAL] -> one picture to work/img/one/ (PAL: palette entry name)

Formats (port/formats/resources.md):
  PAL:{VGA: 256 x RGB 6-bit, EGA: 16 bytes, CGA: ...}
  BMP:{INF: u16 n, u16 w[n], u16 h[n];  then one of
       BIN:+VGA: packed low / high nibbles of all frames (row-major, frame after frame),
       VQT:+OFF: quadtree "vector quantisation" bit stream, OFF = u32 byte offset per frame or FFFF,
       SCN:+OFF: run/skip scan-line coding}
  SCR:{BIN:+VGA: 320x200 nibble planes, or VQT: 320x200}
  FNT: FF = proportional 1 bpp, FD = proportional 8 bpp, else fixed-width 1 bpp
"""
import os, struct, sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynvol, dynchunk

OUT = os.path.join('work', 'img')


# ---------------------------------------------------------------- palettes

def pal_vga(chunks):
    """768 bytes, 6-bit components -> list of 256 RGB tuples (8-bit, c*255/63)."""
    for c in chunks:
        v = c.find('PAL:VGA:')
        if v:
            d = v.data
            return [tuple((d[3 * i + k] & 63) * 255 // 63 for k in range(3)) for i in range(256)]
    return None


def grey_pal():
    return [(i, i, i) for i in range(256)]


def pal_image(pal):
    im = Image.new('RGB', (16 * 12, 16 * 12))
    dr = ImageDraw.Draw(im)
    for i, c in enumerate(pal):
        x, y = (i % 16) * 12, (i // 16) * 12
        dr.rectangle((x, y, x + 11, y + 11), fill=c)
    return im


# ---------------------------------------------------------------- nibble planes

def nibble_frames(lo, hi, sizes):
    """BIN: low nibbles, VGA: high nibbles, 2 pixels per byte (first pixel in the low nibble
    of each byte), frames one after another; a frame's pixel count is w*h (odd counts share
    a byte with the next frame)."""
    frames = []
    pos = 0
    for w, h in sizes:
        n = w * h
        px = bytearray(n)
        for i in range(n):
            j = pos + i
            b = j >> 1
            sh = 4 * (j & 1)
            l = (lo[b] >> sh) & 15 if b < len(lo) else 0
            hh = (hi[b] >> sh) & 15 if hi is not None and b < len(hi) else 0
            px[i] = l | (hh << 4)
        pos += n
        frames.append(bytes(px))
    return frames


# ---------------------------------------------------------------- VQT

class Bits:
    def __init__(self, data, bitpos=0):
        self.d = bytes(data) + b'\0\0\0\0'
        self.pos = bitpos

    def get(self, n):
        i = self.pos >> 3
        v = (self.d[i] | self.d[i + 1] << 8) >> (self.pos & 7)
        self.pos += n
        return v & ((1 << n) - 1)


def vqt_leaf(bs, img, W, x, y, w, h):
    if w == 0 or h == 0:
        return
    if w == 1 and h == 1:
        img[y * W + x] = bs.get(8)
        return
    size = (w & 0xFF) * (h & 0xFF)
    nb1 = 8
    if size < 256:
        nb1 = max(1, (size - 1).bit_length())
    first = bs.get(nb1)
    nb2 = first.bit_length()
    ncol = (first + 1) & 0xFF
    if size * 8 <= size * nb2 + ncol * 8:
        for xx in range(x, x + w):
            for yy in range(y, y + h):
                img[yy * W + xx] = bs.get(8)
        return
    if ncol == 1:
        v = bs.get(8)
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                img[yy * W + xx] = v
        return
    tab = [bs.get(8) for _ in range(ncol)]
    for xx in range(x, x + w):
        for yy in range(y, y + h):
            img[yy * W + xx] = tab[bs.get(nb2)]


def vqt_node(bs, img, W, x, y, w, h):
    if w == 0 and h == 0:
        return
    mask = bs.get(4)
    quads = ((x, y, w // 2, h // 2), (x + w // 2, y, (w + 1) // 2, h // 2),
             (x, y + h // 2, w // 2, (h + 1) // 2), (x + w // 2, y + h // 2, (w + 1) // 2, (h + 1) // 2))
    for bit, q in zip((8, 4, 2, 1), quads):
        (vqt_node if mask & bit else vqt_leaf)(bs, img, W, *q)


def vqt_frame(data, bitpos, w, h):
    img = bytearray(w * h)
    bs = Bits(data, bitpos)
    vqt_node(bs, img, w, 0, 0, w, h)
    return bytes(img), bs.pos


def vqt_frames(data, offs, sizes):
    frames = []
    pos = 0
    for k, (w, h) in enumerate(sizes):
        if offs is not None:
            pos = offs[k] * 8
        px, pos = vqt_frame(data, pos, w, h)
        pos = (pos + 7) & ~7                  # OFF = FFFF: next frame at the next byte
        frames.append(px)
    return frames


# ---------------------------------------------------------------- SCN

SCN_NIBBLE_HI_FIRST = True


def scn_frames(data, offs, sizes):
    """OFF: u32 byte offset of each frame in SCN:."""
    return [scn_frame(data, offs[k] if offs else 0, w, h) for k, (w, h) in enumerate(sizes)]


def scn_frame(d, p, w, h, mask=None):
    """Scan-line coding (INTRO.EXE draw routine 05da:1e38): byte 0 = colour base added to every
    4-bit pixel value (the draw call overwrites it with its colour argument before drawing);
    then ops (top 2 bits, n = low 6 bits), pen starting at (0, 0):
      00 n: next line, x -= n (pen moves back n pixels); if the next byte is 00mmmmmm with
            m != 0 it is consumed too: x -= 64*m
      01 n: n = 0 end of frame, else x += n (transparent skip)
      10 n: run of n pixels, value = next byte + base
      11 n: n literal pixels, 4 bits each, high nibble first, (n+1)/2 bytes."""
    img = bytearray(w * h)
    add = d[p]
    p += 1
    x = y = 0
    while p < len(d):
        c = d[p]
        p += 1
        op, n = c >> 6, c & 0x3F
        if op == 0:
            x -= n
            y += 1
            if p < len(d) and d[p] and not (d[p] & 0xC0):   # extension byte: back 64*m more
                x -= 64 * d[p]
                p += 1
        elif op == 1:
            if n == 0:
                break
            x += n
        elif op == 2:
            v = (d[p] + add) & 0xFF
            p += 1
            for i in range(n):
                if 0 <= x < w and y < h:
                    img[y * w + x] = v
                    if mask is not None:
                        mask[y * w + x] = 1
                x += 1
        else:
            for i in range(n):
                b = d[p + (i >> 1)]
                hi = (i & 1) == (0 if SCN_NIBBLE_HI_FIRST else 1)
                v = ((b >> 4) if hi else (b & 15)) + add
                if 0 <= x < w and y < h:
                    img[y * w + x] = v & 0xFF
                    if mask is not None:
                        mask[y * w + x] = 1
                x += 1
            p += (n + 1) >> 1
    return bytes(img)


# ---------------------------------------------------------------- BMP / SCR

def bmp_frames(chunks):
    bmp = chunks[0]
    inf = bmp.find('BMP:INF:').data
    n = struct.unpack_from('<H', inf)[0]
    ws = struct.unpack_from('<%dH' % n, inf, 2)
    hs = struct.unpack_from('<%dH' % n, inf, 2 + 2 * n)
    sizes = list(zip(ws, hs))
    offc = bmp.find('BMP:OFF:')
    offs = None
    if offc is not None and offc.size >= 4:
        offs = struct.unpack_from('<%dI' % (offc.size // 4), offc.raw)
    kind = None
    if bmp.find('BMP:BIN:'):
        kind = 'nib'
        vga = bmp.find('BMP:VGA:')
        frames = nibble_frames(bmp.find('BMP:BIN:').data, vga.data if vga else None, sizes)
    elif bmp.find('BMP:VQT:'):
        kind = 'vqt'
        frames = vqt_frames(bmp.find('BMP:VQT:').data, offs, sizes)
    elif bmp.find('BMP:SCN:'):
        kind = 'scn'
        frames = scn_frames(bmp.find('BMP:SCN:').data, offs, sizes)
    else:
        return None, sizes, None
    return kind, sizes, frames


def scr_frame(chunks):
    scr = chunks[0]
    if scr.find('SCR:VQT:'):
        return 'vqt', vqt_frame(scr.find('SCR:VQT:').data, 0, 320, 200)[0]
    lo = scr.find('SCR:BIN:').data
    hi = scr.find('SCR:VGA:').data
    return 'nib', nibble_frames(lo, hi, [(320, 200)])[0]


def to_image(px, w, h, pal, transparent=None):
    im = Image.frombytes('P', (w, h), px)
    flat = []
    for c in pal:
        flat += c
    im.putpalette(flat)
    return im


def strip(frames, sizes, pal, maxw=320):
    """All frames of a BMP side by side (wrapped), 2 px gaps, magenta background."""
    rows, row, rw, rh = [], [], 0, 0
    for px, (w, h) in zip(frames, sizes):
        if row and rw + w > maxw:
            rows.append((row, rw, rh))
            row, rw, rh = [], 0, 0
        row.append((px, w, h))
        rw += w + 2
        rh = max(rh, h)
    if row:
        rows.append((row, rw, rh))
    W = max(r[1] for r in rows) if rows else 1
    H = sum(r[2] + 2 for r in rows) if rows else 1
    im = Image.new('RGB', (max(1, W), max(1, H)), (80, 0, 80))
    y = 0
    for r, _, rh in rows:
        x = 0
        for px, w, h in r:
            if w and h:
                im.paste(to_image(px, w, h, pal).convert('RGB'), (x, y))
            x += w + 2
        y += rh + 2
    return im


# ---------------------------------------------------------------- fonts

def font_image(raw):
    """-> (kind, PIL image of the whole character set, 16 per row)."""
    magic = raw[0]
    glyphs = []
    if magic in (0xFF, 0xFD):
        maxw, h, base, first, count = raw[1:6]
        method = raw[8]
        usize = struct.unpack_from('<I', raw, 9)[0]
        d = dynchunk.decompress(method, raw[13:], usize)
        offs = struct.unpack_from('<%dH' % count, d)
        widths = d[2 * count:3 * count]
        bits = d[3 * count:]
        for i in range(count):
            w = widths[i]
            g = bytearray(w * h)
            o = offs[i]
            if magic == 0xFF:
                bpr = (w + 7) // 8
                for y in range(h):
                    for x in range(w):
                        if bits[o + y * bpr + (x >> 3)] & (0x80 >> (x & 7)):
                            g[y * w + x] = 255
            else:
                for y in range(h):
                    for x in range(w):
                        g[y * w + x] = bits[o + y * w + x]
            glyphs.append((first + i, w, g))
        kind = 'prop1' if magic == 0xFF else 'prop8'
    else:
        w, h, first, count = raw[0:4]
        count = count or 256
        bpr = (w + 7) // 8
        d = raw[4:]
        for i in range(count):
            g = bytearray(w * h)
            for y in range(h):
                for x in range(w):
                    o = i * h * bpr + y * bpr + (x >> 3)
                    if o < len(d) and d[o] & (0x80 >> (x & 7)):
                        g[y * w + x] = 255
            glyphs.append((first + i, w, g))
        kind = 'fixed'
    cw = max([g[1] for g in glyphs] + [1]) + 2
    ch = h + 2
    cols = 16
    rows = (len(glyphs) + cols - 1) // cols
    im = Image.new('L', (cols * cw, rows * ch), 40)
    for k, (c, w, g) in enumerate(glyphs):
        if w:
            gi = Image.frombytes('L', (w, h), bytes(g))
            if kind == 'prop8':                   # colour indices: stretch for visibility
                gi = gi.point(lambda v: 0 if v == 0 else min(255, 60 + v * 12))
            im.paste(gi, ((k % cols) * cw + 1, (k // cols) * ch + 1))
    return kind, im


# ---------------------------------------------------------------- palette choice

DEFAULT_PAL = {'SIM1': 'SIM.PAL', 'SIM2': 'SIM.PAL', 'M1SIM': 'SIM.PAL'}   # else ACES.PAL

# Pictures whose palette is not the one with the same base name (found by looking).
PAL_OVERRIDE = {'ACE0.BMP': 'DOGACE.PAL', 'ACE1.BMP': 'DOGACE.PAL', 'ACE2.BMP': 'DOGACE.PAL',
                'ACE3.BMP': 'DOGACE.PAL', 'ACE5.BMP': 'DOGACE.PAL', 'ACE6.BMP': 'DOGACE.PAL',
                'ACE7.BMP': 'DOGACE.PAL', 'OFFICERS.BMP': 'BRIEF.PAL', 'MT_HIST.BMP': 'FLYHIST.PAL',
                'JAPFLAG.BMP': 'AWRDCFG.PAL', 'INT46J.BMP': 'INT46.PAL', 'USAFLAG.BMP': 'AWRDCFG.PAL'}


SCRIPT_PAL = {}          # picture -> palette, from the TTM scripts (filled by script_pals)


def script_pals(pals):
    """Walk every TTM script's TT3 bytes: a picture gets the last palette named before it.
    Palettes that are not in any volume (COCPAL.PAL, COCKPIT.PAL, GUNPAL.PAL: built at run time
    by the sim) are replaced by SIM.PAL."""
    import re
    for v in dynvol.all_volumes():
        for e in v.entries:
            if not e.name.endswith('.TTM'):
                continue
            ch = dynchunk.try_parse(v.get(e))
            tt3 = ch and [c for c in ch if c.tag == 'TT3:']
            if not tt3:
                continue
            cur = None
            for m in re.finditer(rb'[A-Z0-9_&]{1,8}\.(?:PAL|SCR|BMP)', tt3[0].data.upper()):
                n = m.group().decode()
                if n.endswith('.PAL'):
                    cur = n if n in pals else 'SIM.PAL'
                elif cur:
                    SCRIPT_PAL.setdefault(n, cur)


def choose_pal(name, pals, vol=''):
    base = os.path.splitext(name)[0]
    if name in PAL_OVERRIDE and PAL_OVERRIDE[name] in pals:
        return PAL_OVERRIDE[name]
    if name in SCRIPT_PAL:
        return SCRIPT_PAL[name]
    if base + '.PAL' in pals:
        return base + '.PAL'
    # longest palette name that is a prefix of the picture name (FLTDK0.SCR -> FLTDK0.PAL, INTA346 -> INTA.PAL)
    best = None
    for p in pals:
        pb = os.path.splitext(p)[0]
        if len(pb) >= 3 and base.startswith(pb) and (best is None or len(pb) > len(os.path.splitext(best)[0])):
            best = p
    return best or DEFAULT_PAL.get(vol, 'ACES.PAL')


# ---------------------------------------------------------------- sheets

def sheet(items, path, cell=(160, 100), cols=6):
    """items: list of (label, PIL image). Each image scaled to fit the cell (never enlarged > 2x)."""
    if not items:
        return
    cw, chh = cell
    rows = (len(items) + cols - 1) // cols
    im = Image.new('RGB', (cols * (cw + 6), rows * (chh + 18)), (40, 40, 40))
    dr = ImageDraw.Draw(im)
    for k, (label, pic) in enumerate(items):
        x, y = (k % cols) * (cw + 6), (k // cols) * (chh + 18)
        pic = pic.convert('RGB')
        s = min(cw / pic.width, chh / pic.height, 2)
        pic = pic.resize((max(1, int(pic.width * s)), max(1, int(pic.height * s))), Image.NEAREST)
        im.paste(pic, (x, y + 14))
        dr.text((x + 2, y + 1), label[:26], fill=(255, 255, 0))
    im.save(path)


# ---------------------------------------------------------------- main

def all_pals():
    pals = {}
    for v in dynvol.all_volumes():
        for e in v.entries:
            if e.name.endswith('.PAL'):
                p = pal_vga(dynchunk.parse(v.get(e)))
                if p:
                    pals.setdefault(e.name, p)
    script_pals(pals)
    return pals


def do_all():
    pals = all_pals()
    report = []
    for v in dynvol.all_volumes():
        vn = os.path.splitext(v.name)[0]
        od = os.path.join(OUT, vn)
        os.makedirs(od, exist_ok=True)
        items = {'pal': [], 'bmp': [], 'scr': [], 'fnt': []}
        for e in v.entries:
            ext = e.name.rsplit('.', 1)[-1]
            if ext not in ('PAL', 'BMP', 'SCR', 'FNT'):
                continue
            ch = dynchunk.try_parse(v.get(e))
            base = os.path.join(od, e.name.replace('.', '_'))
            try:
                if ext == 'PAL':
                    im = pal_image(pal_vga(ch))
                    im.save(base + '.png')
                    items['pal'].append((e.name, im))
                elif ext == 'FNT':
                    kind, im = font_image(ch[0].raw)
                    im.save(base + '.png')
                    items['fnt'].append(('%s %s' % (e.name, kind), im))
                elif ext == 'SCR':
                    pn = choose_pal(e.name, pals, vn)
                    kind, px = scr_frame(ch)
                    im = to_image(px, 320, 200, pals[pn])
                    im.save(base + '.png')
                    items['scr'].append(('%s %s' % (e.name, pn[:-4]), im))
                    report.append('%s %s scr %s pal %s' % (vn, e.name, kind, pn))
                else:
                    pn = choose_pal(e.name, pals, vn)
                    kind, sizes, frames = bmp_frames(ch)
                    if frames is None:
                        report.append('%s %s bmp: no pixel chunk' % (vn, e.name))
                        continue
                    im = strip(frames, sizes, pals[pn])
                    im.save(base + '.png')
                    items['bmp'].append(('%s %s' % (e.name, pn[:-4]), im))
                    report.append('%s %s bmp %s %d frames pal %s' % (vn, e.name, kind, len(frames), pn))
            except Exception as ex:                # keep going, list the failure
                report.append('%s %s FAILED %s: %s' % (vn, e.name, type(ex).__name__, ex))
        for k, it in items.items():
            if it:
                cell = (192, 192) if k in ('pal', 'fnt') else (160, 100)
                sheet(it, os.path.join(od, 'sheet_%s.png' % k), cell)
        print('%s: %s' % (vn, ', '.join('%d %s' % (len(i), k) for k, i in items.items() if i)))
    open(os.path.join(OUT, 'report.txt'), 'w').write('\n'.join(report) + '\n')
    print('\n'.join(r for r in report if 'FAILED' in r or 'no pixel' in r))


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    if sys.argv[1] == 'all':
        do_all()
    elif sys.argv[1] == 'one':
        v = dynvol.Volume(sys.argv[2])
        e = v.find(sys.argv[3])
        ch = dynchunk.parse(v.get(e))
        pals = all_pals()
        pn = sys.argv[4] if len(sys.argv) > 4 else choose_pal(e.name, pals, os.path.splitext(v.name)[0])
        od = os.path.join(OUT, 'one')
        os.makedirs(od, exist_ok=True)
        fn = os.path.join(od, '%s_%s.png' % (e.name.replace('.', '_'), pn[:-4]))
        if e.name.endswith('.SCR'):
            to_image(scr_frame(ch)[1], 320, 200, pals[pn]).save(fn)
        else:
            kind, sizes, frames = bmp_frames(ch)
            strip(frames, sizes, pals[pn]).save(fn)
        print(fn)
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
