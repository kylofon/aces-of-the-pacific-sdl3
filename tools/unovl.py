"""Flatten the Borland VROOMM overlays of AP.EXE into one plain MZ program.

AP.EXE (Borland C++ 3.0, TLINK /o) = a resident MZ image followed by an `FBOV` block that holds the
code of 129 overlay segments. Layout, verified against the bytes (see port/RE_GUIDE.md, "Overlays"):

  FBOV header at the end of the MZ load image (file 0x49AC0), 16 bytes:
    char  sig[4]   "FBOV"
    u32   size     bytes of overlay data that follow the header (0x2EF00)
    u32   segtab   FILE offset of the segment table __SEGTABLE__ (0x3F310 = image 0x3B510, in DGROUP)
    u32   nsegs    entries in the segment table (0x20D = 525)
  Segment table, 8 bytes per entry (index i; relocations inside overlays refer to entries as i*8):
    u16 seg (file segment of the segment or of its stub), u16 maxoff, u16 flags, u16 minoff
    flags 1 = resident code, 3 = overlay (seg is its stub), 0 = data (DGROUP 3EA4, far data, stack),
          4 = segments at the end of DGROUP (overlay manager / emulator data)
  Stub segment (resident, one per overlay segment, paragraph aligned):
    +00 CD 3F      int 3Fh (overlay manager, reached if the stub header itself is called)
    +02 u16        memswap (0)
    +04 u32        offset of the overlay's code, relative to the byte after the FBOV header
    +08 u16        code size
    +0A u16        relocation bytes (u16 offsets into the code, directly after the code)
    +0C u16        number of entries
    +0E u16        prevstub (0 in the file; runtime chain) ; +10..+1F runtime work area (0)
    +20 entries, 5 bytes each: CD 3F <u16 offset of the entry in the overlay code> 00
  Overlay relocations: the word at each listed code offset holds segment-table index * 8; the loader
  replaces it with the segment of that entry (for an overlay entry: its stub segment, so far calls
  between overlays go through the stubs).

This tool appends every overlay segment's code after the resident image (paragraph aligned, first at
the paragraph after the image), turns every relocation into an ordinary MZ relocation of the real
segment, and rewrites each stub entry `CD 3F off 00` into `EA off newseg` (JMP FAR, 5 bytes, plus a
relocation). With --direct (the default) `call far stub:entry` instructions (9A) in resident and
overlay code, and `mov r16,entry / mov r16,stub` far code pointer pairs, are retargeted straight to
the overlay code, so the call graph does not go through the thunks (the thunks stay valid for code
pointers kept in data). The FBOV block is dropped.

usage: unovl.py Game/AP.EXE work/AP_flat.exe [--thunks-only]
       writes work/AP_flat.exe and port/ap_overlays.csv (segment map) + port/ap_overlay_entries.csv
       (stub entry -> overlay code); prints a summary.
"""
import csv, os, struct, sys

src, dst = sys.argv[1], sys.argv[2]
direct = '--thunks-only' not in sys.argv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(src, 'rb').read()
(sig, lastp, npages, nrel, hdrp, minalloc, maxalloc, ss, sp, csum, ip, cs, reloff, ovno) = \
    struct.unpack_from('<14H', d, 0)
hdr = hdrp * 16
load_end = (npages - 1) * 512 + (lastp or 512)
img = bytearray(d[hdr:load_end])
relocs = [struct.unpack_from('<HH', d, reloff + 4 * i) for i in range(nrel)]
rel_lin = set(s * 16 + o for o, s in relocs)

fb = load_end
assert d[fb:fb + 4] == b'FBOV', 'no FBOV block'
ov_size, segtab, nsegs = struct.unpack_from('<III', d, fb + 4)
OV = fb + 16
assert OV + ov_size == len(d)
ents = [struct.unpack_from('<4H', d, segtab + 8 * i) for i in range(nsegs)]

# ---- read overlays ----
ovls = []                                   # dict per overlay
stub_by_seg = {}
for i, (seg, maxoff, flags, minoff) in enumerate(ents):
    if flags != 3:
        continue
    b = seg * 16
    assert img[b:b + 2] == b'\xcd\x3f', 'stub %04x' % seg
    memswap, fo, csize, rsize, nent, prev = struct.unpack_from('<HIHHHH', img, b + 2)
    entries = []
    for k in range(nent):
        e = b + 0x20 + 5 * k
        assert img[e:e + 2] == b'\xcd\x3f' and img[e + 4] == 0, 'entry %04x:%04x' % (seg, 0x20 + 5 * k)
        entries.append(struct.unpack_from('<H', img, e + 2)[0])
    code = bytearray(d[OV + fo:OV + fo + csize])
    rel = list(struct.unpack_from('<%dH' % (rsize // 2), d, OV + fo + csize))
    o = dict(index=i, stub=seg, maxoff=maxoff, fileoff=fo, size=csize, relsize=rsize, entries=entries,
             code=code, rel=rel, memswap=memswap, prev=prev)
    ovls.append(o)
    stub_by_seg[seg] = o

# ---- place ----
cur = (len(img) + 15) // 16
for o in ovls:
    o['seg'] = cur
    cur += (o['size'] + 15) // 16
new_img = bytearray(img) + bytes(cur * 16 - len(img))
new_rel = set(rel_lin)                      # linear addresses of relocated words (load segment 0)
stats = dict(ovl_relocs=0, to_code=0, to_stub=0, to_data=0, direct_calls=0, direct_ptrs=0, bad=0)


def entry_target(stubseg, off):
    """stub segment + offset of an entry -> linear address of the overlay code, or None."""
    o = stub_by_seg.get(stubseg)
    if o is None or off < 0x20 or (off - 0x20) % 5 or (off - 0x20) // 5 >= len(o['entries']):
        return None
    return o['seg'], o['entries'][(off - 0x20) // 5]


for o in ovls:
    code, base = o['code'], o['seg'] * 16
    for r in o['rel']:
        v = struct.unpack_from('<H', code, r)[0]
        stats['ovl_relocs'] += 1
        if v % 8 or v // 8 >= nsegs:
            stats['bad'] += 1
            print('odd overlay reloc %04x:%04x value %04x' % (o['stub'], r, v))
            continue
        tseg, _, tflags, _ = ents[v // 8]
        stats['to_stub' if tflags == 3 else 'to_code' if tflags == 1 else 'to_data'] += 1
        struct.pack_into('<H', code, r, tseg)
        new_rel.add(base + r)
    new_img[base:base + o['size']] = code
    # stub entries -> JMP FAR
    for k, off in enumerate(o['entries']):
        e = o['stub'] * 16 + 0x20 + 5 * k
        new_img[e:e + 5] = b'\xea' + struct.pack('<HH', off, o['seg'])
        new_rel.add(e + 3)

if direct:
    for p in sorted(new_rel):
        if p < 3:
            continue
        sv = struct.unpack_from('<H', new_img, p)[0]
        if sv not in stub_by_seg:
            continue
        if new_img[p - 3] == 0x9A:                                   # call far off:stub
            t = entry_target(sv, struct.unpack_from('<H', new_img, p - 2)[0])
            if t:
                struct.pack_into('<HH', new_img, p - 2, t[1], t[0])
                stats['direct_calls'] += 1
        elif 0xB8 <= new_img[p - 1] <= 0xBF and 0xB8 <= new_img[p - 4] <= 0xBF:   # mov r,off / mov r,stub
            t = entry_target(sv, struct.unpack_from('<H', new_img, p - 3)[0])
            if t:
                struct.pack_into('<H', new_img, p - 3, t[1])
                struct.pack_into('<H', new_img, p, t[0])
                stats['direct_ptrs'] += 1

# ---- write MZ ----
rl = sorted(new_rel)
assert len(rl) < 0x10000
rel_bytes = b''.join(struct.pack('<HH', p & 0xF, p >> 4) if (p >> 4) < 0x10000 else b'' for p in rl)
# relocation entries as seg:off with small offsets; segment = p>>4 fits 16 bits for < 1 MB
hdr_size = (0x1C + 4 + len(rel_bytes) + 511) // 512 * 512
total = hdr_size + len(new_img)
h = bytearray(hdr_size)
struct.pack_into('<14H', h, 0, sig, total % 512, (total + 511) // 512, len(rl), hdr_size // 16,
                 minalloc, maxalloc, ss, sp, 0, ip, cs, 0x20, 0)
h[0x20:0x20 + len(rel_bytes)] = rel_bytes
os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
open(dst, 'wb').write(bytes(h) + bytes(new_img))

port = os.path.join(ROOT, 'port')
with open(os.path.join(port, 'ap_overlays.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['segtab_index', 'stub_seg', 'code_seg', 'code_image', 'size', 'entries', 'relocs',
                'fbov_offset'])
    for o in ovls:
        w.writerow([o['index'], '%04x' % o['stub'], '%04x' % o['seg'], '%05x' % (o['seg'] * 16),
                    o['size'], len(o['entries']), len(o['rel']), '%05x' % o['fileoff']])
with open(os.path.join(port, 'ap_overlay_entries.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['stub_entry', 'code'])
    for o in ovls:
        for k, off in enumerate(o['entries']):
            w.writerow(['%04x:%04x' % (o['stub'], 0x20 + 5 * k), '%04x:%04x' % (o['seg'], off)])

print('resident image %05x bytes, %d relocs; FBOV %d bytes, segment table at file %05x, %d entries'
      % (len(img), nrel, ov_size, segtab, nsegs))
print('%d overlay segments, %d bytes of code, %d entries -> segments %04x-%04x; image now %05x bytes'
      % (len(ovls), sum(o['size'] for o in ovls), sum(len(o['entries']) for o in ovls),
         ovls[0]['seg'], cur - 1, len(new_img)))
print('overlay relocs %(ovl_relocs)d: to resident code %(to_code)d, to stubs %(to_stub)d, to data %(to_data)d,'
      ' odd %(bad)d; direct calls %(direct_calls)d, direct code pointers %(direct_ptrs)d' % stats)
print('relocations written: %d -> %s' % (len(rl), dst))
