"""3Space world areas: AW<n>.WD3 (+ AW<n>.MBL macros, AW<n>.TBL shapes) -> dumps and top-down maps.

  dynworld.py list                      -> every area: object counts, macros, extent
  dynworld.py dump AREA [objects|macros|mbl]  -> records of AW<n>.WD3 / AW<n>.MBL (AREA = 1..11 or AW1)
  dynworld.py render AREA [--size N] [--zoom X,Y,HALFWIDTH] [--noshapes] [--labels] -> work/world/AW<n>.png
                                        (targets = red crosses, carrier-group positions = yellow squares)
  dynworld.py targets AREA              -> TARGET.n and CARRIER.n entries (names, dated positions, lists)
  dynworld.py all                       -> render every area, plus work/world/sheet.png
  dynworld.py flt AREA                  -> AW<n>.FLT records

Layout: port/formats/world.md.  Code in AP.EXE (work/AP_flat.exe):
  35ad:000f  WD2:WHD:  (u8 n, skip n words, read 512 bytes)           obwload.c
  35ad:00f8  WD2:OB0:..OB5: (26-byte records), WD2:MBL: (u16 n, 16+6 or 16+24 bytes)
  62d2:049e  area load: target.XX / wd3 / flt; record handler 62d2:0199 (via 3de9:0034)
  34f1:0310  macro file AW<n>.MBL, 34f1:0155 macro expansion (macros.c)
  333b:000d  AW<n>.FLT (24-byte records)
"""
import glob, math, os, struct, sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynchunk, dynshape

OUT = os.path.join('work', 'world')
SEA = (16, 40, 88)


def area_name(a):
    a = a.upper()
    return a if a.startswith('AW') else 'AW' + a


def find(name):
    hits = sorted(glob.glob(os.path.join('work', 'dyn', '*', name)))
    # prefer the add-on volume for AW11, the base sim volumes otherwise
    return hits[0] if hits else None


class Obj:
    """22-byte placement record (OBx: 26 bytes = 22 + 4 unused; macro members: 22 bytes)."""
    def __init__(self, d, o, long=False):
        self.flags, self.shape = struct.unpack_from('<HH', d, o)
        self.x, self.y, self.z = struct.unpack_from('<3i', d, o + 4)
        self.a0, self.a1, self.heading = struct.unpack_from('<3H', d, o + 16)
        self.raw = d[o:o + (26 if long else 22)]


class MblRec:
    """WD2:MBL: record: u16 flags, u16 type (8000h|macro), 3 x i32 position, u16 heading, 4 bytes."""
    def __init__(self, d, o):
        self.flags, self.type = struct.unpack_from('<HH', d, o)
        self.x, self.y, self.z = struct.unpack_from('<3i', d, o + 4)
        self.heading = struct.unpack_from('<H', d, o + 16)[0]
        self.size = 40 if self.type & 0xC000 == 0xC000 else 22
        self.raw = d[o:o + self.size]


class Macro:
    def __init__(self, name, box, members):
        self.name, self.box, self.members = name, box, members


def load_macros(path):
    """34f1:0310: u8 ?, u16 n; n x (char name[8], u16 count, i32[3], count x 22-byte records);
    records whose type word is FFFF are dropped."""
    if not path:
        return []
    d = open(path, 'rb').read()
    n = struct.unpack_from('<H', d, 1)[0]
    p = 3
    out = []
    for _ in range(n):
        name = d[p:p + 8].split(b'\0')[0].decode('latin1')
        cnt = struct.unpack_from('<H', d, p + 8)[0]
        box = struct.unpack_from('<3i', d, p + 10)
        p += 22
        mem = []
        for _ in range(cnt):
            r = Obj(d, p)
            if r.shape != 0xFFFF:
                mem.append(r)
            p += 22
        out.append(Macro(name, box, mem))
    return out


class Area:
    def __init__(self, a):
        self.name = area_name(a)
        self.wd3 = find(self.name + '.WD3')
        raw = open(self.wd3, 'rb').read()
        top = dynchunk.parse(raw)[0]
        ch = {c.tag: c for c in top.children}
        w = ch['WHD:'].raw
        n = w[0]
        self.whd_ids = struct.unpack_from('<%dH' % n, w, 1)
        self.whd_counts = struct.unpack_from('<256H', w, 1 + 2 * n)
        self.whd_obcount = struct.unpack_from('<H', w, 1 + 2 * n + 512)[0]
        self.objects = []
        for k in range(6):
            c = ch.get('OB%d:' % k)
            if c:
                self.objects += [Obj(c.raw, i, True) for i in range(0, len(c.raw) - 25, 26)]
        self.mbl = []
        c = ch.get('MBL:')
        if c:
            d = c.raw
            cnt = struct.unpack_from('<H', d, 0)[0]
            p = 2
            for _ in range(cnt):
                r = MblRec(d, p)
                self.mbl.append(r)
                p += r.size
        self.macros = load_macros(find(self.name + '.MBL'))
        tp = find(self.name + '.TBL')
        self.table = dynshape.Table(tp) if tp else None

    def placements(self):
        """(shape index, x, y, z, heading, source) for every drawable object, macros expanded
        as 34f1:0155 does (member x/y += instance x/y, rotated by the instance heading)."""
        out = [(o.shape, o.x, o.y, o.z, o.heading, 'OB') for o in self.objects]
        for r in self.mbl:
            if r.type & 0xC000 != 0x8000:
                continue
            m = r.type & 0x3FFF
            if m >= len(self.macros):
                continue
            a = r.heading * 2 * math.pi / 65536.0
            ca, sa = math.cos(a), math.sin(a)
            for mb in self.macros[m].members:
                dx, dy = mb.x, mb.y
                if r.heading:
                    dx, dy = dx * ca - dy * sa, dx * sa + dy * ca
                out.append((mb.shape & 0x1FFF, r.x + dx, r.y + dy, mb.z, (mb.heading + r.heading) & 0xFFFF, 'M%d' % m))
        return out


# ---------------------------------------------------------------- TARGET.n / CARRIER.n

def date_str(days):
    """Dates in these files are days since 1 Jan 1900 (3BD4h = 7 Dec 1941)."""
    import datetime
    return (datetime.date(1900, 1, 1) + datetime.timedelta(days=days - 1)).isoformat()


class Target:
    def __init__(self, tid):
        self.id, self.name = tid, ''
        self.lists = [[] for _ in range(5)]      # list 0: (date, [(x,y,z)...]); 1: (date, a, b); 2-4: (date, v)


def load_targets(n, kind='TARGET'):
    """628f:0144 (wdata.c) reads TARGET.n; CARRIER.n (shell) has the same layout.
    INF: u16 P (points per position entry, 1).  DAT: u16 count, per entry: u16 id, then 5 lists
    {u16 m; m x (u16 date, payload)}: payload = P x 3 i32 position (list 0), 2 x u16 (list 1),
    1 x u16 (lists 2-4).  TAG: u16 count, count x (u16 id, char name[]).  Dates: days since 1900."""
    p = find('%s.%d' % (kind, n))
    if not p:
        return []
    ch = {c.tag: c for c in dynchunk.parse(open(p, 'rb').read())}
    P = struct.unpack_from('<H', ch['INF:'].raw, 0)[0]
    d = ch['DAT:'].raw
    cnt = struct.unpack_from('<H', d, 0)[0]
    o = 2
    out = []
    for _ in range(cnt):
        t = Target(struct.unpack_from('<H', d, o)[0])
        o += 2
        for k in range(5):
            m = struct.unpack_from('<H', d, o)[0]
            o += 2
            for _ in range(m):
                date = struct.unpack_from('<H', d, o)[0]
                o += 2
                if k == 0:
                    pts = [struct.unpack_from('<3i', d, o + 12 * j) for j in range(P)]
                    o += 12 * P
                    t.lists[0].append((date, pts))
                elif k == 1:
                    t.lists[1].append((date,) + struct.unpack_from('<2H', d, o))
                    o += 4
                else:
                    t.lists[k].append((date, struct.unpack_from('<H', d, o)[0]))
                    o += 2
        out.append(t)
    names = {}
    if 'TAG:' in ch:
        g = ch['TAG:'].raw
        q = 2
        for _ in range(struct.unpack_from('<H', g, 0)[0]):
            i = struct.unpack_from('<H', g, q)[0]
            e = g.index(b'\0', q + 2)
            names[i] = g[q + 2:e].decode('latin1')
            q = e + 1
    for t in out:
        t.name = names.get(t.id, '')
    assert o == len(d), (p, o, len(d))
    return out


def cmd_targets(ar):
    n = int(area_name(ar)[2:])
    for t in load_targets(n):
        print('%3d %-28s' % (t.id, t.name), end='')
        print(' pos ' + ' '.join('%s:(%d,%d,%d)' % ((date_str(dt),) + pts[0]) for dt, pts in t.lists[0]), end='')
        for k in range(1, 5):
            if t.lists[k]:
                print('  L%d ' % k + ' '.join('%s:%s' % (date_str(e[0]), ','.join('%x' % v for v in e[1:])) for e in t.lists[k]), end='')
        print()
    for t in load_targets(n, 'CARRIER'):
        print('carrier group %d %-24s %d positions: %s ...  L2-4 %s' % (t.id, t.name, len(t.lists[0]),
              ' '.join('%s:(%d,%d)' % (date_str(dt), pts[0][0], pts[0][1]) for dt, pts in t.lists[0][:3]),
              [[(date_str(e[0]), e[1]) for e in t.lists[k]] for k in (2, 3, 4)]))


# ---------------------------------------------------------------- text

def cmd_list():
    for p in sorted(glob.glob(os.path.join('work', 'dyn', '*', 'AW*.WD3')), key=lambda s: int(os.path.basename(s)[2:-4])):
        a = Area(os.path.basename(p)[:-4])
        xs = [o.x for o in a.objects] + [r.x for r in a.mbl]
        ys = [o.y for o in a.objects] + [r.y for r in a.mbl]
        counts = {i: c for i, c in enumerate(a.whd_counts) if c}
        print('%-5s OB %3d  MBL %3d  macros %2d  shapes %3d  x %9d..%9d  y %9d..%9d  WHD %s' % (
            a.name, len(a.objects), len(a.mbl), len(a.macros), len(a.table.shapes) if a.table else 0,
            min(xs), max(xs), min(ys), max(ys), counts))


def cmd_dump(ar, what='objects'):
    a = Area(ar)
    nm = a.table.names if a.table else []
    if what == 'objects':
        print('WHD ids %s  counts %s  OB count %d' % (a.whd_ids, {i: c for i, c in enumerate(a.whd_counts) if c}, a.whd_obcount))
        for i, o in enumerate(a.objects):
            s = a.table.shapes[o.shape] if a.table and o.shape < len(a.table.shapes) else None
            print('%3d flags %04x shape %3d %-10s class %2s  pos %9d %9d %6d  ang %04x %04x %04x' % (
                i, o.flags, o.shape, nm[o.shape] if o.shape < len(nm) else '?', '%02x' % s.b1 if s else '--',
                o.x, o.y, o.z, o.a0, o.a1, o.heading))
    elif what == 'mbl':
        for i, r in enumerate(a.mbl):
            m = r.type & 0x3FFF
            print('%3d flags %04x type %04x (%s)  pos %9d %9d %6d  heading %04x  %s' % (
                i, r.flags, r.type, a.macros[m].name if r.type & 0xC000 == 0x8000 and m < len(a.macros) else '?',
                r.x, r.y, r.z, r.heading, r.raw[18:].hex()))
    elif what == 'macros':
        for i, m in enumerate(a.macros):
            print('macro %2d %-8s %2d members  box %s' % (i, m.name, len(m.members), m.box))
            for o in m.members:
                print('     flags %04x shape %3d %-10s  %7d %7d %6d  ang %04x %04x %04x' % (
                    o.flags, o.shape, nm[o.shape & 0x1FFF] if (o.shape & 0x1FFF) < len(nm) else '?', o.x, o.y, o.z, o.a0, o.a1, o.heading))


def cmd_flt(ar):
    p = find(area_name(ar) + '.FLT')
    d = open(p, 'rb').read()
    print(p, len(d), 'bytes', len(d) // 24, 'records')
    for i in range(0, len(d) - 23, 24):
        print('  ' + ' '.join('%04x' % v for v in struct.unpack_from('<12H', d, i)))


# ---------------------------------------------------------------- map

def shape_polys_top(shape, pal):
    """Top view of the most detailed LOD: list of (z, [(x,y)..], rgb) in model units (unscaled)."""
    if not shape.lods:
        return []
    out = []
    L = shape.lods[-1]
    for p in dynshape.walk_parts(L.parts):
        if not p.groups:
            continue
        g = p.groups[0]
        if g.type == 1 and g.size and g.vertex < len(p.verts):
            v = p.verts[g.vertex]
            out.append((v[2], 'disc', (v[0], v[1], g.size), pal[g.col_vga]))
            continue
        for q in g.polys:
            if not q.idx or max(q.idx) >= len(p.verts) or q.flags & 3 == 2:
                continue
            pts = [p.verts[i] for i in q.idx]
            zmax = max(v[2] for v in pts)
            filled = bool(q.flags & 0x80) and len(pts) > 2
            out.append((zmax, 'poly' if filled else 'line', [(v[0], v[1]) for v in pts], pal[q.col[1] if filled else q.col[0]]))
    out.sort(key=lambda t: t[0])
    return out


def render_area(a, size=1400, zoom=None, shapes=True, pal=None, targets=True, label=False):
    pal = pal or dynshape.load_pal()
    pl = a.placements()
    T = a.table
    if zoom:
        cx, cy, hw = zoom
        x0, x1, y0, y1 = cx - hw, cx + hw, cy - hw, cy + hw
    else:
        xs, ys = [], []
        for sh, x, y, z, hd, src in pl:
            r = (T.shapes[sh].radius << T.shapes[sh].shift) if T and sh < len(T.shapes) else 0
            xs += [x - r, x + r]
            ys += [y - r, y + r]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        m = 0.03 * max(x1 - x0, y1 - y0)
        x0, x1, y0, y1 = x0 - m, x1 + m, y0 - m, y1 + m
    span = max(x1 - x0, y1 - y0)
    k = size / span
    W, H = int((x1 - x0) * k) + 1, int((y1 - y0) * k) + 1
    SS = 2
    im = Image.new('RGB', (W * SS, H * SS), SEA)
    dr = ImageDraw.Draw(im)

    def P(x, y):                                   # north (+y) up
        return ((x - x0) * k * SS, (y1 - y) * k * SS)
    cache = {}
    # terrain first (islands class 1, then everything else by class), bigger first
    order = sorted(pl, key=lambda t: (0 if T and t[0] < len(T.shapes) and T.shapes[t[0]].b1 == 1 else 1,
                                      -(T.shapes[t[0]].radius << T.shapes[t[0]].shift) if T and t[0] < len(T.shapes) else 0))
    for sh, x, y, z, hd, src in order:
        if not T or sh >= len(T.shapes):
            continue
        s = T.shapes[sh]
        if not shapes:
            X, Y = P(x, y)
            dr.ellipse((X - 3, Y - 3, X + 3, Y + 3), outline=(255, 255, 0))
            continue
        if sh not in cache:
            cache[sh] = shape_polys_top(s, pal)
        sc = float(1 << s.shift)
        a_ = hd * 2 * math.pi / 65536.0
        ca, sa = math.cos(a_), math.sin(a_)

        def tr(px, py):
            px, py = px * sc, py * sc
            return P(x + px * ca - py * sa, y + px * sa + py * ca)
        rpix = (s.radius << s.shift) * k * SS
        if rpix < 1.5:
            X, Y = P(x, y)
            dr.point((X, Y), fill=(255, 255, 255))
            continue
        for item in cache[sh]:
            kind = item[1]
            if kind == 'disc':
                vx, vy, r = item[2]
                X, Y = tr(vx, vy)
                rr = r * sc * k * SS
                dr.ellipse((X - rr, Y - rr, X + rr, Y + rr), fill=item[3])
            elif kind == 'poly':
                dr.polygon([tr(px, py) for px, py in item[2]], fill=item[3])
            else:
                pts = [tr(px, py) for px, py in item[2]]
                dr.line(pts + ([pts[0]] if len(pts) > 2 else []), fill=item[3], width=SS)
    im = im.resize((W, H), Image.LANCZOS)
    if targets:
        dr = ImageDraw.Draw(im)
        n = int(a.name[2:])
        for kind, col in (('TARGET', (255, 64, 64)), ('CARRIER', (255, 255, 96))):
            for t in load_targets(n, kind):
                for j, (dt, pts) in enumerate(t.lists[0]):
                    x, y, z = pts[0]
                    if (x, y) == (1400000, 0):          # parking position (off the map)
                        continue
                    X, Y = (x - x0) * k, (y1 - y) * k
                    if kind == 'TARGET':
                        dr.line((X - 3, Y - 3, X + 3, Y + 3), fill=col)
                        dr.line((X - 3, Y + 3, X + 3, Y - 3), fill=col)
                        if j == 0 and label:
                            dr.text((X + 4, Y - 5), t.name, fill=col)
                    else:
                        dr.rectangle((X - 2, Y - 2, X + 2, Y + 2), outline=col)
    return im, (x0, x1, y0, y1)


def cmd_render(args):
    ar = args[0]
    size, zoom, shapes, labels = 1400, None, True, False
    i = 1
    while i < len(args):
        if args[i] == '--size':
            size = int(args[i + 1]); i += 2
        elif args[i] == '--zoom':
            zoom = tuple(float(v) for v in args[i + 1].split(',')); i += 2
        elif args[i] == '--noshapes':
            shapes = False; i += 1
        elif args[i] == '--labels':
            labels = True; i += 1
        else:
            i += 1
    a = Area(ar)
    im, ext = render_area(a, size, zoom, shapes, None, True, labels)
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, '%s%s.png' % (a.name, '_zoom' if zoom else ''))
    im.save(out)
    print(out, im.size, 'extent x %d..%d y %d..%d' % tuple(int(v) for v in ext))


def cmd_all():
    pal = dynshape.load_pal()
    os.makedirs(OUT, exist_ok=True)
    thumbs = []
    for p in sorted(glob.glob(os.path.join('work', 'dyn', '*', 'AW*.WD3')), key=lambda s: int(os.path.basename(s)[2:-4])):
        a = Area(os.path.basename(p)[:-4])
        im, ext = render_area(a, 1400, None, True, pal)
        out = os.path.join(OUT, a.name + '.png')
        im.save(out)
        print(out, im.size)
        t = im.copy()
        t.thumbnail((400, 400))
        thumbs.append((a.name, t))
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * 410, rows * 425), (0, 0, 0))
    dr = ImageDraw.Draw(sheet)
    for i, (n, t) in enumerate(thumbs):
        x, y = (i % cols) * 410, (i // cols) * 425
        sheet.paste(t, (x, y))
        dr.text((x + 4, y + 406), n, fill=(255, 255, 255))
    sheet.save(os.path.join(OUT, 'sheet.png'))
    print(os.path.join(OUT, 'sheet.png'))


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == 'list':
        cmd_list()
    elif a[0] == 'dump':
        cmd_dump(a[1], a[2] if len(a) > 2 else 'objects')
    elif a[0] == 'render':
        cmd_render(a[1:])
    elif a[0] == 'all':
        cmd_all()
    elif a[0] == 'flt':
        cmd_flt(a[1])
    elif a[0] == 'targets':
        cmd_targets(a[1])
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
