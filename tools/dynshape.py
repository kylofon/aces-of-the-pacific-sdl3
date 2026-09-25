"""3Space shape tables (*.TBL) -> dumps and PNG renders.

  dynshape.py list [TBL ...]                 -> every table: shapes, LODs, parts, polygons
  dynshape.py dump TBL [SHAPE]               -> full structure of one table (or one shape by name/index)
  dynshape.py render TBL [SHAPE] [opts]      -> PNG to work/shapes/<tbl>_<shape>.png
        --lod N (default: most detailed)  --yaw DEG --pitch DEG  --size WxH  --state S=V,...
        --wire (outlines only)  --top (plan view, for AW terrain pieces)  --out PATH
  dynshape.py sheet                          -> work/shapes/sheet_<group>.png for every model table
  dynshape.py check                          -> parse every .TBL of every volume, report problems

TBL is a file name (P80.TBL, "AW1"), searched in work/dyn/<vol>/ (run `dynvol.py all` first), or a path.
Layout: port/formats/shapes.md.  Reader/renderer in AP.EXE (flattened, work/AP_flat.exe):
  7074:0154 / 7074:02d8  load "DAT:", relocate the far-pointer list  (ts_utilo.c)
  2f0e:08e9  draw one object: LOD pick, part list          (ts_draw.c)
  2f0e:033d  part depth sort,  2f0e:071f  part/child walk, variant (state) select
  277a:05c6  polygon list: cull, colour, shade, transform;  277a:01ba colour + shading
  70e8:0000  type-1 group (disc),  2edf:0119  type-2 group (bitmap sprite)
"""
import glob, math, os, struct, sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynchunk

OUT = os.path.join('work', 'shapes')

# 277a:21f8 - shade offset per (number of shades 1..8, lighting level -16..15)
SHADE_OFS = [
    [-1] * 16 + [0] * 16,
    [-2] * 10 + [-1] * 6 + [0] * 6 + [1] * 10,
    [-3] * 8 + [-2] * 4 + [-1] * 4 + [0] * 4 + [1] * 4 + [2] * 8,
    [-4] * 6 + [-3] * 4 + [-2] * 4 + [-1] * 2 + [0] * 2 + [1] * 4 + [2] * 4 + [3] * 6,
    [-5] * 6 + [-4] * 2 + [-3] * 2 + [-2] * 2 + [-1] * 4 + [0] * 2 + [1] * 2 + [2] * 2 + [3] * 4 + [4] * 6,
    [-6] * 6 + [-5, -5, -4, -4, -3, -3, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4] + [5] * 6,
    [-7] * 5 + [-6, -6, -5, -4, -4, -3, -3, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 3, 3, 4, 5, 5] + [6] * 5,
    [-8] * 5 + [-7, -7, -6, -5, -5, -4, -3, -3, -2, -1, -1, 0, 0, 1, 2, 2, 3, 4, 4, 5, 6, 6] + [7] * 5,
]


def u16(d, o):
    return struct.unpack_from('<H', d, o)[0]


def i16(d, o):
    return struct.unpack_from('<h', d, o)[0]


# ---------------------------------------------------------------- files

def find_file(name):
    if os.path.exists(name):
        return name
    n = name.upper()
    if '.' not in n:
        n += '.TBL'
    hits = sorted(glob.glob(os.path.join('work', 'dyn', '*', n)))
    if not hits:
        raise SystemExit('%s not found in work/dyn/*/ (run tools/dynvol.py all)' % name)
    return hits[0]


def load_pal(name='SIM.PAL'):
    import dynimg
    p = find_file(name)
    return dynimg.pal_vga(dynchunk.parse(open(p, 'rb').read()))


def load_shades():
    return open(find_file('SHADES.DAT'), 'rb').read()


# ---------------------------------------------------------------- structure

class Poly:
    def __init__(self, d, seg, o):
        self.off = o - seg
        self.flags = d[o]
        self.col = tuple(d[o + 1:o + 5])       # VGA edge, VGA fill, EGA edge, EGA fill
        self.normal = d[o + 5]                 # vertex-list index of the normal (FF = none)
        self.idx_off = u16(d, o + 6)
        q = seg + self.idx_off
        self.idx = []
        while d[q] != 0xFF:
            self.idx.append(d[q])
            q += 1


class Group:
    """8-byte variant entry: type 0 = polygon list, 1 = disc, 2 = bitmap sprite."""
    def __init__(self, d, seg, o):
        self.off = o - seg
        self.raw = d[o:o + 8]
        self.type = d[o]
        self.polys = []
        if self.type == 0:
            n, po = u16(d, o + 2), u16(d, o + 4)
            self.polys = [Poly(d, seg, seg + po + 8 * k) for k in range(n)]
        elif self.type == 1:
            self.size, self.vertex, self.col_vga, self.col_ega = u16(d, o + 2), d[o + 4], d[o + 5], d[o + 6]
        else:
            self.bitmap, self.bmflags, self.scale, self.vertex = i16(d, o + 2), u16(d, o + 4), d[o + 6], d[o + 7]


class Part:
    """14-byte part (sub-object) record."""
    def __init__(self, d, seg, o, depth=0):
        self.off = o - seg
        self.state, self.sort_n, self.sort_p, nv = d[o], d[o + 1], d[o + 2], d[o + 3]
        self.vofs, ng, go, nc, co = u16(d, o + 4), u16(d, o + 6), u16(d, o + 8), u16(d, o + 10), u16(d, o + 12)
        self.nverts, self.gofs, self.cofs = nv, go, co
        self.verts = [struct.unpack_from('<3h', d, seg + self.vofs + 6 * i) for i in range(nv)]
        self.groups = [Group(d, seg, seg + go + 8 * g) for g in range(ng)]
        self.children = [Part(d, seg, seg + co + 14 * c, depth + 1) for c in range(nc)] if depth < 8 else []


class Lod:
    def __init__(self, d, seg, o):
        self.off = o - seg
        self.dist, n, po = u16(d, o), u16(d, o + 2), u16(d, o + 4)
        self.parts = [Part(d, seg, seg + po + 14 * p) for p in range(n)]


class Shape:
    def __init__(self, d, ptr, name='', index=0):
        self.name, self.index, self.ptr = name, index, ptr
        seg = ptr & ~15                         # far pointer seg:off with off < 16 -> base paragraph
        s = ptr
        self.flags, self.b1, self.b2, self.shift = d[s], d[s + 1], d[s + 2], d[s + 3]
        nst, sto = u16(d, s + 4), u16(d, s + 6)
        self.variants = list(d[seg + sto:seg + sto + nst]) if nst else []
        nlod, lo = u16(d, s + 8), u16(d, s + 10)
        self.radius = u16(d, s + 12)
        if self.flags & 0x20:                   # no box stored: 1560:086f uses +-radius*94h/256
            b = self.radius * 0x94 >> 8
            self.bbox = [-b, -b, -b, b, b, b]
        else:
            self.bbox = [i16(d, s + 14 + 2 * i) for i in range(6)]
        self.lods = [Lod(d, seg, seg + lo + 6 * l) for l in range(nlod)]


class Table:
    def __init__(self, path):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0].upper()
        raw = open(path, 'rb').read()
        self.chunks = {c.tag: c for c in dynchunk.parse(raw)}
        d = self.dat = self.chunks['DAT:'].raw + bytes(32)   # stub shapes at the very end are 14 bytes
        self.ptrs = []
        o = 0
        while True:
            off, seg = struct.unpack_from('<HH', d, o)
            if off == 0 and seg == 0:
                break
            self.ptrs.append(seg * 16 + off)
            o += 4
        self.names = self.map_names()
        self.app = self.app_records()
        self.gid = self.chunks['GID:'].raw
        self.shapes = []
        for i, p in enumerate(self.ptrs):
            nm = self.names[i] if i < len(self.names) else '#%d' % i
            self.shapes.append(Shape(d, p, nm, i))

    def map_names(self):
        d = self.chunks['MAP:'].raw
        n = u16(d, 0)
        offs = [u16(d, 4 + 2 * i) for i in range(n)]
        base = 4 + 2 * n + 2                   # u16 n, u16 ?, u16 ofs[n], u16 names size, names
        return [d[base + o:d.index(b'\0', base + o)].decode('latin1') for o in offs]

    def app_records(self):
        c = self.chunks.get('APP:')
        if not c:
            return []
        d = c.raw
        n, sz = u16(d, 0), u16(d, 2)
        return [d[4 + sz * i:4 + sz * (i + 1)] for i in range(n)]

    def shape(self, key):
        if key is None:
            return self.shapes[0]
        for s in self.shapes:
            if s.name.lower() == key.lower():
                return s
        return self.shapes[int(key)]


# ---------------------------------------------------------------- text output

def walk_parts(parts):
    for p in parts:
        yield p
        yield from walk_parts(p.children)


def cmd_list(names):
    paths = [find_file(n) for n in names] if names else sorted(glob.glob(os.path.join('work', 'dyn', '*', '*.TBL')))
    for p in paths:
        t = Table(p)
        vol = os.path.basename(os.path.dirname(p))
        print('%-7s %-12s %3d shape(s)  APP %s  GID %d bytes' % (vol, t.name, len(t.shapes),
              '%dx%d' % (len(t.app), len(t.app[0])) if t.app else '-', len(t.gid)))
        if len(t.shapes) <= 12 or names:
            for s in t.shapes:
                lods = ' '.join('%d:%dp/%dpoly' % (l.dist, len(l.parts), sum(len(g.polys) for pt in walk_parts(l.parts) for g in pt.groups)) for l in s.lods)
                print('    %-12s flags %02x %02x %02x shift %d  r %5d  variants %s  lods %s' % (
                    s.name, s.flags, s.b1, s.b2, s.shift, s.radius, s.variants, lods))


def dump_part(p, ind):
    sp = '  ' * ind
    print('%spart @%04x state %s sort (n %s, p %s)  %d verts @%04x  %d group(s) @%04x  %d child(ren) @%04x' % (
        sp, p.off, '%02x' % p.state if p.state != 0xFF else '--', '%02x' % p.sort_n if p.sort_n != 0xFF else '--',
        '%02x' % p.sort_p if p.sort_p != 0xFF else '--', p.nverts, p.vofs, len(p.groups), p.gofs, len(p.children), p.cofs))
    for gi, g in enumerate(p.groups):
        if g.type == 0:
            print('%s  variant %d @%04x: %d polygon(s)' % (sp, gi, g.off, len(g.polys)))
            for q in g.polys:
                print('%s    @%04x flags %02x col %02x %02x %02x %02x n %s  %s' % (
                    sp, q.off, q.flags, *q.col, '%02x' % q.normal if q.normal != 0xFF else '--', q.idx))
        elif g.type == 1:
            print('%s  variant %d @%04x: disc size %d at vertex %d colour %02x (EGA %02x)' % (sp, gi, g.off, g.size, g.vertex, g.col_vga, g.col_ega))
        else:
            print('%s  variant %d @%04x: type %d %s' % (sp, gi, g.off, g.type, g.raw.hex()))
    for c in p.children:
        dump_part(c, ind + 1)


def cmd_dump(name, key=None):
    t = Table(find_file(name))
    print('%s: MAP %d names, APP %s, GID %d bytes, DAT %d bytes, %d shapes' % (
        t.name, len(t.names), '%d x %d' % (len(t.app), len(t.app[0])) if t.app else '-', len(t.gid), len(t.dat), len(t.shapes)))
    shapes = [t.shape(key)] if key is not None else t.shapes
    for s in shapes:
        print('shape %d "%s" @%05x (seg %04x): flags %02x b1 %02x b2 %02x shift %d radius %d bbox %s variants/state %s' % (
            s.index, s.name, s.ptr, s.ptr >> 4, s.flags, s.b1, s.b2, s.shift, s.radius, s.bbox, s.variants))
        if s.index < len(t.app):
            print('  APP %s' % t.app[s.index].hex(' '))
        for li, l in enumerate(s.lods):
            print(' LOD %d @%04x: up to size %d, %d part(s)' % (li, l.off, l.dist, len(l.parts)))
            for p in l.parts:
                dump_part(p, 1)


# ---------------------------------------------------------------- renderer

def norm(v):
    l = math.sqrt(sum(a * a for a in v)) or 1.0
    return tuple(a / l for a in v)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class Camera:
    """Object space: x right, y forward (nose = +y), z up.  yaw 0 = looking at the nose."""
    def __init__(self, shape, yaw, pitch, w, h, top=False, dist=None):
        self.w, self.h = w, h
        r = max(shape.radius, 1)
        if top:
            yaw, pitch = 0.0, 89.9
        ya, pa = math.radians(yaw), math.radians(pitch)
        # direction from object to eye
        e = (math.sin(ya) * math.cos(pa), math.cos(ya) * math.cos(pa), math.sin(pa))
        cx = sum(shape.bbox[i] + shape.bbox[i + 3] for i in range(1)) / 2
        self.center = tuple((shape.bbox[i] + shape.bbox[i + 3]) / 2 for i in range(3))
        dist = dist or r * 3.2
        self.eye = tuple(self.center[i] + e[i] * dist for i in range(3))
        f = norm(tuple(-a for a in e))                      # forward
        up = (0, 0, 1) if abs(f[2]) < 0.99 else (0, 1, 0)
        right = norm((f[1] * up[2] - f[2] * up[1], f[2] * up[0] - f[0] * up[2], f[0] * up[1] - f[1] * up[0]))
        upv = (right[1] * f[2] - right[2] * f[1], right[2] * f[0] - right[0] * f[2], right[0] * f[1] - right[1] * f[0])
        self.f, self.r, self.u = f, right, upv
        self.focal = min(w, h) * 0.5 * dist / (r * 1.15)

    def project(self, v):
        rel = (v[0] - self.eye[0], v[1] - self.eye[1], v[2] - self.eye[2])
        z = dot(rel, self.f)
        if z < 1:
            z = 1
        return (self.w / 2 + dot(rel, self.r) * self.focal / z, self.h / 2 - dot(rel, self.u) * self.focal / z, z)


def poly_colour(q, part, shades, light, back):
    """277a:01ba, VGA path (driver flag DS:26DF set): edge = col[0], fill = col[1]; shading if flag 20h."""
    edge, fill = q.col[0], q.col[1]
    if q.flags & 0x80 and q.flags & 0x20 and q.normal != 0xFF and q.normal < len(part.verts):
        n = shades[fill] if shades else 0
        if 0 < n <= 8:
            nv = part.verts[q.normal]
            if back:
                nv = tuple(-a for a in nv)
            lvl = int(math.floor(dot(nv, light) / 65536.0))
            lvl = max(-16, min(15, lvl))
            c = (fill + SHADE_OFS[n - 1][lvl + 16]) & 0xFF
            if edge == fill:
                edge = c
            fill = c
    return edge, fill


def collect(parts, cam, states, eye, out, shades, light, wire):
    """2f0e:033d (sort) + 2f0e:071f (walk): parts sorted by n.(p - eye), largest first."""
    def key(p):
        if p.sort_n == 0xFF or p.sort_n >= len(p.verts):
            return 0
        n = p.verts[p.sort_n]
        pt = p.verts[p.sort_p] if p.sort_p != 0xFF and p.sort_p < len(p.verts) else (0, 0, 0)
        return dot(n, (pt[0] - eye[0], pt[1] - eye[1], pt[2] - eye[2]))
    vis = [p for p in parts if p.state == 0xFF or states.get(p.state, 0) != 0xFF]
    vis.sort(key=key, reverse=True)
    for p in vis:
        if p.children:
            collect_one_with_children(p, cam, states, eye, out, shades, light, wire, key)
        else:
            emit_part(p, cam, states, eye, out, shades, light, wire)


def collect_one_with_children(p, cam, states, eye, out, shades, light, wire, key):
    group = [c for c in p.children if c.state == 0xFF or states.get(c.state, 0) != 0xFF]
    lst = group + [p]
    lst.sort(key=lambda x: 0 if x is p else key(x), reverse=True)
    for x in lst:
        if x is p:
            emit_part(p, cam, states, eye, out, shades, light, wire)
        elif x.children:
            collect_one_with_children(x, cam, states, eye, out, shades, light, wire, key)
        else:
            emit_part(x, cam, states, eye, out, shades, light, wire)


def emit_part(p, cam, states, eye, out, shades, light, wire):
    if not p.groups:
        return
    v = 0 if p.state == 0xFF else states.get(p.state, 0)
    v %= len(p.groups)
    g = p.groups[v]
    if g.type == 1:
        if g.size and g.vertex < len(p.verts):
            out.append(('disc', p.verts[g.vertex], g.size, g.col_vga))
        return
    if g.type != 0:
        return
    for q in g.polys:
        if not q.idx or max(q.idx) >= len(p.verts):
            continue
        t = q.flags & 3
        if t == 2:
            continue
        back = False
        if q.normal != 0xFF and q.normal < len(p.verts) and (t == 1 or q.flags & 0x20):
            v0 = p.verts[q.idx[0]]
            s = dot(p.verts[q.normal], (v0[0] - eye[0], v0[1] - eye[1], v0[2] - eye[2]))
            if s >= 0:
                if t == 1:
                    continue
                back = True
        edge, fill = poly_colour(q, p, shades, light, back)
        pts = [p.verts[i] for i in q.idx]
        filled = bool(q.flags & 0x80) and len(pts) > 2 and not wire
        out.append(('poly', pts, edge, fill, filled))


def render(shape, lod=None, yaw=210.0, pitch=20.0, size=(480, 360), states=None, wire=False, top=False,
           pal=None, shades=None, bg=(24, 40, 64), scale=3):
    W, H = size[0] * scale, size[1] * scale
    cam = Camera(shape, yaw, pitch, W, H, top)
    lods = shape.lods
    if not lods:
        return Image.new('RGB', size, bg)
    L = lods[-1] if lod is None else lods[min(lod, len(lods) - 1)]
    light = tuple(a * 512 for a in norm((-0.4, 0.5, 0.75)))
    items = []
    collect(L.parts, cam, states or {}, cam.eye, items, shades, light, wire)
    im = Image.new('RGB', (W, H), bg)
    dr = ImageDraw.Draw(im)
    lw = max(1, scale)
    # fit the projected drawing into the image (margin 6%)
    xs, ys = [], []
    for it in items:
        for v in ([it[1]] if it[0] == 'disc' else it[1]):
            x, y, _ = cam.project(v)
            xs.append(x)
            ys.append(y)
    k, ox, oy = 1.0, 0.0, 0.0
    if xs:
        bw, bh = max(max(xs) - min(xs), 1), max(max(ys) - min(ys), 1)
        k = min(W * 0.88 / bw, H * 0.88 / bh)
        ox = W / 2 - k * (min(xs) + max(xs)) / 2
        oy = H / 2 - k * (min(ys) + max(ys)) / 2

    def P(v):
        x, y, z = cam.project(v)
        return (ox + k * x, oy + k * y)
    for it in items:
        if it[0] == 'disc':
            x, y = P(it[1])
            r = it[2] * cam.focal * k / cam.project(it[1])[2]
            dr.ellipse((x - r * 1.25, y - r, x + r * 1.25, y + r), fill=pal[it[3]])
            continue
        _, pts, edge, fill, filled = it
        sp = [P(v) for v in pts]
        if filled:
            dr.polygon(sp, fill=pal[fill])
            if edge != fill:
                dr.line(sp + [sp[0]], fill=pal[edge], width=lw)
        elif len(sp) == 2:
            dr.line(sp, fill=pal[edge], width=lw)
        else:
            dr.line(sp + [sp[0]], fill=pal[edge], width=lw)
    if scale > 1:
        im = im.resize(size, Image.LANCZOS)
    return im


def parse_states(s):
    out = {}
    if s:
        for kv in s.split(','):
            k, v = kv.split('=')
            out[int(k, 0)] = int(v, 0)
    return out


def cmd_render(args):
    opts = {'--lod': None, '--yaw': '210', '--pitch': '20', '--size': '480x360', '--state': '', '--out': None}
    flags = set()
    pos = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in opts:
            opts[a] = args[i + 1]
            i += 2
        elif a in ('--wire', '--top'):
            flags.add(a)
            i += 1
        else:
            pos.append(a)
            i += 1
    t = Table(find_file(pos[0]))
    s = t.shape(pos[1] if len(pos) > 1 else None)
    w, h = (int(x) for x in opts['--size'].split('x'))
    im = render(s, None if opts['--lod'] is None else int(opts['--lod']), float(opts['--yaw']), float(opts['--pitch']),
                (w, h), parse_states(opts['--state']), '--wire' in flags, '--top' in flags, load_pal(), load_shades())
    os.makedirs(OUT, exist_ok=True)
    out = opts['--out'] or os.path.join(OUT, '%s_%s.png' % (t.name, s.name))
    im.save(out)
    print(out)


# ---------------------------------------------------------------- sheets / check

SHIPS = set('AKAGI CAL DAKOTA ESSEX FLETCH FLUSH FUBUKI HAMPTON HIRYU INDEP JCRUISE JDSTROY JFRT JTANK JTANK2 '
            'JTANKER JTRP KONGO LCI LCM LEX LST MOGAMI RYUJO SC_1009 TYPE_51 TYPE_C TYPE_E TYPE_G UFRT UTANK '
            'UTANK2 UTRP YAMATO YORK ZUIHO ZUIKAKU MIDWAY'.split())
MISC = {'SPOLY', 'DYNAMIC', 'SHAD', 'ALWAYS', 'GHOST'}
GROUPS = {
    'aircraft': lambda t: len(t.shapes) == 1 and t.name not in SHIPS | MISC,
    'ships': lambda t: t.name in SHIPS,
    'misc': lambda t: t.name in MISC or (len(t.shapes) > 1 and not t.name.startswith('AW')),
}


def cmd_sheet():
    from PIL import ImageFont
    pal, shades = load_pal(), load_shades()
    os.makedirs(OUT, exist_ok=True)
    seen = set()
    tables = []
    for p in sorted(glob.glob(os.path.join('work', 'dyn', '*', '*.TBL'))):
        n = os.path.basename(p).upper()
        if n in seen:
            continue
        seen.add(n)
        tables.append(Table(p))
    for gname, pred in GROUPS.items():
        cells = []
        for t in tables:
            if not pred(t):
                continue
            for s in t.shapes:
                if not s.lods:
                    continue
                im = render(s, None, 210, 20, (240, 180), None, False, False, pal, shades, scale=2)
                cells.append(('%s/%s' % (t.name, s.name), im))
                im.save(os.path.join(OUT, '%s_%s.png' % (t.name, s.name)))
        if not cells:
            continue
        cols = 6
        rows = (len(cells) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * 240, rows * 196), (0, 0, 0))
        dr = ImageDraw.Draw(sheet)
        for k, (lab, im) in enumerate(cells):
            x, y = (k % cols) * 240, (k // cols) * 196
            sheet.paste(im, (x, y))
            dr.text((x + 2, y + 182), lab, fill=(255, 255, 255))
        path = os.path.join(OUT, 'sheet_%s.png' % gname)
        sheet.save(path)
        print(path, len(cells))


def cmd_check():
    import collections
    st = collections.Counter()
    bad = 0
    for p in sorted(glob.glob(os.path.join('work', 'dyn', '*', '*.TBL'))):
        try:
            t = Table(p)
        except Exception as e:
            print('FAIL', p, e)
            bad += 1
            continue
        st['tables'] += 1
        for s in t.shapes:
            st['shapes'] += 1
            for sv, l in enumerate(s.lods):
                for pt in walk_parts(l.parts):
                    st['parts'] += 1
                    for g in pt.groups:
                        st['group type %d' % g.type] += 1
                        for q in g.polys:
                            st['polys'] += 1
                            st['poly flags %02x' % q.flags] += 1
                            if q.idx and max(q.idx) >= pt.nverts:
                                st['index out of range'] += 1
                            if q.normal != 0xFF and q.normal >= pt.nverts:
                                st['normal out of range'] += 1
                    if pt.state != 0xFF and s.variants and pt.state < len(s.variants) and len(pt.groups) > s.variants[pt.state]:
                        st['more variants than state count'] += 1
    for k, v in sorted(st.items()):
        print('%-32s %d' % (k, v))
    print('failed tables:', bad)


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    c = a[0]
    if c == 'list':
        cmd_list(a[1:])
    elif c == 'dump':
        cmd_dump(a[1], a[2] if len(a) > 2 else None)
    elif c == 'render':
        cmd_render(a[1:])
    elif c == 'sheet':
        cmd_sheet()
    elif c == 'check':
        cmd_check()
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
