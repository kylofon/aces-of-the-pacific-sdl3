"""Dynamix TTM scripts ("4.09") of Aces of the Pacific: disassembler.

  dynttm.py all                 -> every .TTM of every extracted volume to work/ttm/<VOL>/<NAME>.txt,
                                   opcode usage table work/ttm/_opcodes.txt
  dynttm.py dis FILE.TTM        -> disassembly of one extracted file to stdout
  dynttm.py ops                 -> the opcode table (as known) to stdout

Entry = chunks  VER: "4.09\\0" | PAG: u16 frames | TT3: packed (u8 method=1 RLE, u32 size) opcodes |
TTI:{ TAG: u16 n, n x (u16 id, NUL-terminated name) }.
Opcode word: high 12 bits = operation, low nibble = argument count (u16 each); nibble F = one
NUL-terminated string argument, padded so that string+NUL has even length (PS 3B02:0381);
AF1F/AF2F (polygons) instead take u16 n and n (x, y) pairs.
A "frame" (PAG counts them) runs up to and including 0FF0.  The interpreter (PS 3BAF:0540,
INTRO 11D2:053F, AP 2595:038B) is given a frame index; 1101/1111 <tag> mark frames that
GOTO/GOSUB can find (PS 3BAF:1547).  See port/formats/scripts.md.
"""
import glob, os, struct, sys, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynchunk

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

# op -> (mnemonic, args, note).  Handlers: PS 3BAF:0540 (tables CS:147B, CS:1423, CS:1537),
# draw class A000 -> 3BAF:01A7 (table CS:04DC), sound class C000 -> 3BAF:000D (table CS:0101).
OPS = {
    0x0000: ('END', '', 'end of script (only in INTACE2)'),
    0x0010: ('NOP10', '', 'no-op'),
    0x0020: ('SAVE_BG', '', 'copy screen to the background buffer (3B02:0A2D); also done after LOAD_SCR'),
    0x0070: ('FREE_PAL', '', 'free palette of the current palette slot'),
    0x0080: ('FREE_BMP', '', 'free bitmap of the current bitmap slot'),
    0x0090: ('FREE_FONT', '', 'free font of the current font slot'),
    0x00C0: ('FREE_GETPUT', '', 'free saved region of the current get/put slot'),
    0x00E0: ('ANIM_CLOSE', '', 'close the 39BD animation player if open (unused)'),
    0x0110: ('PURGE', '', 'set purge flag DS:7606 (script ends / caller unloads)'),
    0x0400: ('PAL_RESET', '', 'reset palette fade state, re-apply palette (unused)'),
    0x0500: ('FLAG3864_ON', '', 'DS:3864 = 1 (unused)'),
    0x0510: ('FLAG3864_OFF', '', 'DS:3864 = 0 (unused)'),
    0x0FF0: ('FRAME_END', '', 'end of frame: interpreter returns'),
    0x1011: ('OP1011', 'a', '16E3:35C9(a) (unused)'),
    0x1021: ('SET_DELAY', 'ticks', 'frame delay DS:76A4 = ticks'),
    0x1031: ('SET_BRUSH', 'n', 'context +1C = n'),
    0x1041: ('OP1041', 'a', 'DS:7672 = a'),
    0x1051: ('SEL_BMP', 'slot', 'current bitmap slot (context +14)'),
    0x1061: ('SEL_PAL', 'slot', 'current palette slot (context +12); made active'),
    0x1071: ('SEL_FONT', 'slot', 'current font slot (context +10)'),
    0x1101: ('TAG', 'tag', 'frame label (no-op when executed); GOTO/GOSUB target'),
    0x1111: ('TAG2', 'tag', 'frame label (same handler as 1101)'),
    0x1121: ('SEL_GETPUT', 'slot', 'current get/put slot (context +16)'),
    0x1201: ('GOTO', 'tag', 'next frame = frame labelled tag (DS:7608)'),
    0x2002: ('SET_COLORS', 'fg bg', 'drawing colours (context +1E/+1F)'),
    0x2012: ('SET_FRAME', 'a b', '2221:0111(a, b) (Likely: ScummVM SET FRAME)'),
    0x2022: ('RAND_DELAY', 'min max', 'delay = min + rand() % (max - min)'),
    0x2032: ('ANIM_2032', 'a b', '39BD:03D1(a, b) animation player (unused)'),
    0x2302: ('PAL_BLOCK0', 'first last', 'palette-cycle block 0 = colours first..last'),
    0x2312: ('PAL_BLOCK1', 'first last', 'palette-cycle block 1'),
    0x2322: ('PAL_BLOCK2', 'first last', 'palette-cycle block 2'),
    0x2402: ('PAL_CYCLE', 'mask step', 'rotate blocks whose bit is set in mask by step'),
    0x3003: ('GOSUB', 'dx dy tag', 'run frame tag with drawing offset (dx, dy)'),
    0x3103: ('OP3103', 'a b c', '30B5:000F(a, b, c) + full update (unused)'),
    0x4004: ('SET_CLIP', 'x1 y1 x2 y2', 'clip window'),
    0x4114: ('FADE_OUT', 'first n col speed', 'fade colours first..first+n-1 towards col'),
    0x4124: ('FADE_IN', 'first n col speed', 'fade colours first..first+n-1 in from col'),
    0x4136: ('FADE_PART', 'first n col from% to% steps', 'partial fade between two levels'),
    0x4204: ('STORE_AREA', 'x y w h', 'copy area to the background buffer'),
    0x4214: ('SAVE_GETPUT', 'x y w h', 'save screen area into the current get/put slot'),
    0x5005: ('NOP5005', 'a b c d e', 'no-op'),
    0xA002: ('PIXEL', 'x y', 'pixel in fg colour'),
    0xA0A4: ('LINE', 'x1 y1 x2 y2', 'line in fg colour'),
    0xA104: ('RECT_FILL', 'x y w h', 'filled rectangle, fg colour'),
    0xA114: ('RECT', 'x y w h', 'rectangle outline'),
    0xA304: ('OPA304', 'x y w h', '3A5A:000D(x, y, w, h) (unused)'),
    0xA404: ('CIRCLE_FILL', 'x y w h', 'filled circle r = h/2, centre (x+r, y+r)'),
    0xA424: ('CIRCLE', 'x y w h', 'circle outline'),
    0xA504: ('SPRITE', 'x y frame slot', 'draw bitmap frame'),
    0xA514: ('SPRITE_F1', 'x y frame slot', 'draw bitmap frame, flip flag 1'),
    0xA524: ('SPRITE_F2', 'x y frame slot', 'draw bitmap frame, flip flag 2'),
    0xA534: ('SPRITE_F3', 'x y frame slot', 'draw bitmap frame, flip flags 1+2'),
    0xA505: ('SPRITE_C', 'x y frame slot col', 'draw SCN frame with base colour col'),
    0xA515: ('SPRITE_C_F1', 'x y frame slot col', ''),
    0xA525: ('SPRITE_C_F2', 'x y frame slot col', ''),
    0xA535: ('SPRITE_C_F3', 'x y frame slot col', ''),
    0xA506: ('SPRITE_S', 'x y frame slot w h', 'draw frame scaled to w x h'),
    0xA516: ('SPRITE_S_F1', 'x y frame slot w h', ''),
    0xA526: ('SPRITE_S_F2', 'x y frame slot w h', ''),
    0xA536: ('SPRITE_S_F3', 'x y frame slot w h', ''),
    0xA5A7: ('SPRITE_R', 'x y frame slot w h angle', 'draw frame rotated (angle 0-FFFF) / scaled (Likely)'),
    0xA601: ('PUT_GETPUT', 'slot', 'redraw the area saved in get/put slot'),
    0xA704: ('ANIM_A704', 'x y w h', '39BD:02D3 animation player (unused)'),
    0xAF02: ('FLOOD', 'x y', 'flood fill with bg colour'),
    0xAF1F: ('POLY', 'n pts', 'polygon outline'),
    0xAF2F: ('POLY_FILL', 'n pts', 'filled polygon'),
    0xB000: ('OPB000', '', '3A48:0001 (unused)'),
    0xB013: ('OPB013', 'a b c', '3A48:0059 (unused)'),
    0xB606: ('COPY_AREA', 'x y w h src dst', 'copy area between screen buffers (unused)'),
    0xC01F: ('SND_NAME1', 'name', 'sound name -> DS:7681 (unused)'),
    0xC02F: ('SND_BANK', 'name', 'sound bank name (.SX) -> DS:7674'),
    0xC031: ('SND_LOAD', 'id', 'load sound id from the bank (45F0:000C)'),
    0xC041: ('SND_C041', 'id', '4609:000C(id)'),
    0xC051: ('SND_PLAY', 'id', 'play sound id (464D:0002); old opcode 1301 is mapped here'),
    0xC061: ('SND_STOP', 'id', 'stop sound id (467E:0000); old opcode 1311 is mapped here'),
    0xC0E3: ('SND_FADE', 'id a b', '463B:0003(id, a, b): sound fade (sound.md, video_ttm.md)'),
    0xF01F: ('LOAD_SCR', 'name', 'load .SCR as the background, then SAVE_BG'),
    0xF02F: ('LOAD_BMP', 'name', 'load .BMP into the current bitmap slot'),
    0xF04F: ('LOAD_FONT', 'name', 'load .FNT into the current font slot'),
    0xF05F: ('LOAD_PAL', 'name', 'load .PAL into the current palette slot'),
    0xF08F: ('ANIM_OPEN', 'name', 'open 39BD animation (unused)'),
}
for i in range(9):   # F10F..F19F: string slot i (then clears slots i+1..8); A2x4: draw string slot x
    OPS[0xF10F + 16 * i] = ('SET_STR%d' % i, 'text', 'string slot %d = text, slots %d..8 cleared' % (i, i + 1))
    OPS[0xA204 + 16 * i] = ('TEXT%d' % i, 'x y w h', 'draw string slot %d with the current font' % i)
for op in list(range(0xA014, 0xA095, 0x10)) + [0xA0B5]:
    OPS.setdefault(op, ('WIPE_%04X' % op, 'x y w h' + (' a' if op & 15 == 5 else ''), 'screen transition (3BAF:1689)'))
# Opcodes the AP (cockpit) interpreter 2595:038B knows (others are skipped; C000 class ignored).
AP_OPS = {0x0070, 0x0080, 0x0090, 0x00C0, 0x0110, 0x1031, 0x1051, 0x1061, 0x1071, 0x1101, 0x1111,
          0x1121, 0x1201, 0x2002, 0x3003, 0x4004, 0x4214, 0xF01F, 0xF02F, 0xF04F, 0xF05F, 0x0FF0}


def load(path):
    """-> dict(ver, pag, tags{id: name}, code bytes)."""
    d = open(path, 'rb').read()
    r = {'ver': None, 'pag': None, 'tags': {}, 'code': b''}
    for c in dynchunk.parse(d):
        for x in c.walk():
            if x.path == 'VER:':
                r['ver'] = x.data.split(b'\0')[0].decode('latin1')
            elif x.path == 'PAG:':
                r['pag'] = struct.unpack_from('<H', x.data)[0]
            elif x.path == 'TT3:':
                r['code'] = x.data
            elif x.path.endswith('TAG:'):
                t = x.data
                n = struct.unpack_from('<H', t)[0]
                p = 2
                for _ in range(n):
                    tid = struct.unpack_from('<H', t, p)[0]
                    e = t.index(b'\0', p + 2)
                    r['tags'][tid] = t[p + 2:e].decode('latin1')
                    p = e + 1
    return r


def decode(code):
    """Yield (offset, op, args) with args a tuple of ints, a str, or ('poly', [(x, y)...])."""
    p = 0
    while p < len(code):
        off = p
        op = struct.unpack_from('<H', code, p)[0]
        p += 2
        n = op & 15
        if op in (0xAF1F, 0xAF2F):
            k = struct.unpack_from('<H', code, p)[0]
            pts = struct.unpack_from('<%dh' % (2 * k), code, p + 2)
            p += 2 + 4 * k
            yield off, op, ('poly', list(zip(pts[::2], pts[1::2])))
        elif n == 15:
            e = code.index(b'\0', p)
            s = code[p:e].decode('latin1')
            p = e + 1
            if p & 1:
                p += 1
            yield off, op, s
        else:
            yield off, op, struct.unpack_from('<%dh' % n, code, p)
            p += 2 * n


def fmt_args(op, a):
    if isinstance(a, str):
        return '"%s"' % a
    if isinstance(a, tuple) and a and a[0] == 'poly':
        return '%d: ' % len(a[1]) + ' '.join('(%d,%d)' % q for q in a[1])
    return ' '.join(str(x) for x in a)


def disasm(path, out):
    r = load(path)
    out.write('; %s  VER "%s"  PAG %s frames  TT3 %d bytes\n' % (os.path.basename(path), r['ver'], r['pag'], len(r['code'])))
    for k in sorted(r['tags']):
        out.write(';   tag %d = "%s"\n' % (k, r['tags'][k]))
    frame = 0
    newframe = True
    for off, op, a in decode(r['code']):
        if newframe:
            out.write('\nframe %d:\n' % frame)
            newframe = False
        name, argn, _ = OPS.get(op, ('OP%04X' % op, '', ''))
        extra = ''
        if op in (0x1101, 0x1111) and a and a[0] in r['tags']:
            extra = '   ; "%s"' % r['tags'][a[0]]
        out.write('  %04x  %04X %-12s %s%s\n' % (off, op, name, fmt_args(op, a), extra))
        if op == 0x0FF0:
            frame += 1
            newframe = True
    return r


def all_files():
    return sorted(glob.glob(os.path.join(ROOT, 'work', 'dyn', '*', '*.TTM')))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if cmd == 'dis':
        disasm(sys.argv[2], sys.stdout)
    elif cmd == 'ops':
        for op in sorted(OPS):
            n, a, note = OPS[op]
            print('%04X %-12s %-26s %s' % (op, n, a, note))
    elif cmd == 'all':
        use = collections.Counter()
        files = collections.defaultdict(set)
        for f in all_files():
            vol = os.path.basename(os.path.dirname(f))
            od = os.path.join(ROOT, 'work', 'ttm', vol)
            os.makedirs(od, exist_ok=True)
            with open(os.path.join(od, os.path.basename(f) + '.txt'), 'w') as o:
                r = disasm(f, o)
            for _, op, _ in decode(r['code']):
                use[op] += 1
                files[op].add(vol + ':' + os.path.basename(f))
        with open(os.path.join(ROOT, 'work', 'ttm', '_opcodes.txt'), 'w') as o:
            o.write('op   mnemonic      uses files AP  args / example files\n')
            for op in sorted(use):
                n, a, note = OPS.get(op, ('OP%04X' % op, '', ''))
                ex = sorted(files[op])
                o.write('%04X %-12s %5d %4d  %s  %-24s %s\n' % (op, n, use[op], len(ex), 'y' if op in AP_OPS or op & 0xF000 == 0xA000 else '-',
                                                          a, ', '.join(ex[:4]) + (' ...' if len(ex) > 4 else '')))
        print('%d scripts -> work/ttm/, %d distinct opcodes' % (len(all_files()), len(use)))
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
