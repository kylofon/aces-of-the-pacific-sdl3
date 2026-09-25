"""Aces of the Pacific game data (non-graphics, non-3D, non-sound) -> readable text.

  dyndata.py all            -> every supported entry of work/dyn/<VOL>/ and the loose files of Game/
                               to work/data/<VOL>/<NAME>.txt (+ work/data/_summary.txt)
  dyndata.py one FILE       -> dump one file (type chosen by name/extension) to stdout

Formats: port/formats/data.md (missions, hand-off files, per-aircraft data) and
port/formats/scripts.md (.SCD / string tables).  Field names marked '?' are guesses; 'u' = unknown.
Needs the extracted volumes (tools/dynvol.py all).
"""
import glob, os, re, struct, sys, collections

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
GAME = os.path.join(ROOT, 'Game')


def u16(d, o): return struct.unpack_from('<H', d, o)[0]
def s16(d, o): return struct.unpack_from('<h', d, o)[0]
def u32(d, o): return struct.unpack_from('<I', d, o)[0]
def s32(d, o): return struct.unpack_from('<i', d, o)[0]
def cstr(d, o, n=None):
    e = d.index(b'\0', o) if b'\0' in d[o:o + (n or len(d))] else o + (n or len(d) - o)
    return d[o:e].decode('latin1')
def hexs(b): return b.hex(' ')
def words(b, signed=True):
    n = len(b) // 2
    return list(struct.unpack_from('<%d%s' % (n, 'h' if signed else 'H'), b))


# ---------------------------------------------------------------- string tables
def strtab(d):
    """.SCD and text .DAT tables -> list of strings or None.  Variant A (.SCD): u32 n, u16 end[n]
    (relative to 4+2n; string i = [end[i-1], end[i]), end[-1] = 0).  Variant A' (shell .DAT):
    u32 n, u16 start[n-1] of strings 1..n-1, strings at 4+2(n-1).  Variant B / B' (1946 add-on):
    u32 text size, u16 n, u32 (B) or u16 (B') start[n], strings at 6+4n / 6+2n."""
    if len(d) >= 6:
        n = u32(d, 0)
        if 0 < n < 2000 and 4 + 2 * n <= len(d):
            base = 4 + 2 * n
            ends = struct.unpack_from('<%dH' % n, d, 4)
            if ends[-1] + base == len(d) and all(a < b for a, b in zip((0,) + ends, ends)):
                out, s = [], 0
                for e in ends:
                    out.append(d[base + s:base + e].rstrip(b'\0').decode('latin1'))
                    s = e
                return out
        # variant A' (shell text .DAT): u32 n, u16 start[n-1] of strings 1..n-1, string 0 at 4+2(n-1)
        if 1 < n < 2000 and 4 + 2 * n <= len(d):
            base = 4 + 2 * (n - 1)
            st = (0,) + struct.unpack_from('<%dH' % (n - 1), d, 4)
            if all(a < b for a, b in zip(st, st[1:])) and base + st[-1] < len(d) and \
                    all(d[base + s - 1] == 0 for s in st[1:]):
                return [cstr(d, base + s) for s in st]
    if len(d) >= 12:   # variant B (1946 add-on): u32 text size, u16 n, u32 start[n], strings at 6+4n
        size, n = u32(d, 0), u16(d, 4)
        if 0 < n < 2000 and 6 + 4 * n <= len(d):
            base = 6 + 4 * n
            st = struct.unpack_from('<%dI' % n, d, 6)
            if st[0] == 0 and all(a < b for a, b in zip(st, st[1:])) and base + st[-1] < len(d) and \
                    all(d[base + s - 1] == 0 for s in st[1:]):
                return [cstr(d, base + s) for s in st]
        if 0 < n < 2000 and 6 + 2 * n <= len(d):   # variant B'
            base = 6 + 2 * n
            st = struct.unpack_from('<%dH' % n, d, 6)
            if st[0] == 0 and all(a < b for a, b in zip(st, st[1:])) and base + st[-1] < len(d) and                     all(d[base + s - 1] == 0 for s in st[1:]):
                return [cstr(d, base + s) for s in st]
    return None


def dump_strings_found(d, out):
    """Fallback for record+text files: every printable NUL-terminated run of >= 3 characters."""
    out.append('record/text file (%d bytes): layout not decoded; printable strings:' % len(d))
    for m in re.finditer(rb'[\x20-\x7e]{3,}\x00', d):
        out.append('  @%05x  %s' % (m.start(), m.group()[:-1].decode('latin1')))


def dump_strtab(d, out):
    t = strtab(d)
    if t is None:
        return False
    out.append('string table, %d strings' % len(t))
    for i, s in enumerate(t):
        out.append('%4d  %s' % (i, s.replace('\n', '\\n').replace('\r', '\\r')))
    return True


def dump_names(d, out):
    """.TXT name lists: NUL-separated words."""
    w = [x.decode('latin1') for x in d.split(b'\0') if x]
    out.append('%d names' % len(w))
    out.append(', '.join(w))


# ---------------------------------------------------------------- missions
REC = {0: 90, 1: 22, 2: 16, 3: 6, 4: 10, 5: 58, 8: 2, 9: 1}
RECNAME = {0: 'header', 1: 'aircraft', 2: 'ship', 3: '(unused)', 4: 'place', 5: 'group',
           7: 'waypoint', 8: 'message offset', 9: 'message text'}


def mission_parse(d):
    """-> version, [(type, [record bytes])]."""
    ver = u16(d, 0)
    p, blocks = 2, []
    while p < len(d):
        t, n = struct.unpack_from('<HH', d, p)
        p += 4
        recs = []
        for _ in range(n):
            if t == 7:
                s = 2 + (12 if d[p] == 0 else 4)
            else:
                s = REC[t]
            recs.append(d[p:p + s])
            p += s
        blocks.append((t, recs))
    return ver, blocks


def dump_mission(d, out):
    ver, blocks = mission_parse(d)
    out.append('mission script, version %d, blocks: %s' % (ver, ' '.join('%d x%d' % (t, len(r)) for t, r in blocks)))
    text = b''.join(r[0] for t, rs in blocks if t == 9 for r in [rs] if rs) if False else None
    pool = b''
    offs = []
    for t, rs in blocks:
        if t == 9:
            pool = b''.join(rs)
        if t == 8:
            offs = [u16(r, 0) for r in rs]
    for t, rs in blocks:
        out.append('')
        out.append('== type %d (%s) x %d' % (t, RECNAME.get(t, '?'), len(rs)))
        if t == 0:
            h = rs[0]
            out.append('  +00 kind %d (0 in files; set by the shell: 0 single/training, 1 career, 2 historical, 3/4 recorder)' % h[0])
            out.append('  +01 u8 %d   +02 u8 %d   +03 u8 %d   +04 wind %d (still/light/strong/stormy)   +05 u8 %d' % tuple(h[1:6]))
            out.append('  +06 name-list mask %02x (bit n -> PFNAMEn/SFNAMEn.TXT)   +07 u8 %d' % (h[6], h[7]))
            out.append('  +08 u16 %d   +0A u16 %d   +0C u32 %d   +10 u32 %08x' % (u16(h, 8), u16(h, 10), u32(h, 12), u32(h, 16)))
            out.append('  +14 %s' % hexs(h[20:]))
        elif t == 7:
            for i, r in enumerate(rs):
                if r[0] == 0:
                    out.append('  %3d  point  idx %3s  x %9d  z %9d  alt %7d' % (i, r[1] if r[1] != 255 else '-', s32(r, 2), s32(r, 6), s32(r, 10)))
                else:
                    out.append('  %3d  cmd %d  idx %3s  %d %d' % (i, r[0], r[1] if r[1] != 255 else '-', s16(r, 2), s16(r, 4)))
        elif t == 8:
            for i, o in enumerate(offs):
                s = cstr(pool, o) if o < len(pool) else '?'
                out.append('  %3d  @%4d  %s' % (i, o, s))
        elif t == 9:
            out.append('  %d bytes of NUL-terminated message text ("|" separates lines)' % len(pool))
        elif t == 1:
            for i, r in enumerate(rs):
                out.append('  %3d  type %3d  b1 %d  w2 %d  w4 %d  w6 %d  w8 %d | %s' % (i, r[0], r[1], u16(r, 2), u16(r, 4), u16(r, 6), u16(r, 8), hexs(r[10:])))
        elif t == 2:
            for i, r in enumerate(rs):
                out.append('  %3d  type %3d  b1 %d  w2 %d  w4 %d  w6 %d  x %d  z %d' % (i, r[0], r[1], u16(r, 2), s16(r, 4), u16(r, 6), s32(r, 8), s32(r, 12)))
        elif t == 4:
            for i, r in enumerate(rs):
                out.append('  %3d  b0 %d  b1 %d  x %d  z %d' % (i, r[0], r[1], s32(r, 2), s32(r, 6)))
        else:
            for i, r in enumerate(rs):
                out.append('  %3d  %s' % (i, hexs(r)))


# ---------------------------------------------------------------- hand-off files
def dump_simin(d, out):
    modes = {0: 'single mission', 1: 'career', 2: 'recorder (shell kind 3)', 3: 'recorder (shell kind 4)'}
    out.append('SIM.IN (13 bytes; PS 1193:093E writes, PS 1193:08F6 re-reads, AP 50C8:0008 reads)')
    out.append('  +00 roster pilot     %d%s' % (d[0], ' (none)' if d[0] == 255 else ''))
    out.append('  +01 mode             %d  %s' % (d[1], modes.get(d[1], '?')))
    out.append('  +02 header+01        %d' % d[2])
    out.append('  +03 set by flymiss2  %d' % d[3])
    out.append('  +04 header+08 (u16)  %d' % u16(d, 4))
    out.append('  +06 header+02        %d' % d[6])
    out.append('  +07 name-list mask   %02x  (header+06 | player service bit; bit 0 read by AP VCR code)' % d[7])
    out.append('  +08 group[0] type    %d' % d[8])
    out.append('  +09 group[side1] type %d' % d[9])
    out.append('  +0A group[0]+18 (u16) %d' % u16(d, 10))
    out.append('  +0C unused           %d' % d[12])


def dump_simout(d, out):
    out.append('SIM.OUT (36 bytes; AP 5254:04F1 fills, 5254:0859 writes; PS 1193:09FE reads to DS:4227)')
    out.append('  +00 fate code        %04x  (low nibble: 1 shot down/killed?, 2 bailed out/ditched?, 3 ?, 4 returned; high nibble: 10-80 detail)' % u16(d, 0))
    out.append('  +02 flags            %02x  (01/02/04 fate bits, 10 shot down a friendly plane, 20 sank a friendly ship, 40 hit a friendly ground target)' % d[2])
    out.append('  +03 u8               %d' % d[3])
    out.append('  +04 u16 (5254:149C)  %d' % u16(d, 4))
    out.append('  +06 u16[4]           %s  (initialised to FFFF)' % words(d[6:14], False))
    out.append('  +0E flight flag      %d' % u16(d, 14))
    names = ['ground targets', 'ship hits (bomb/torpedo)', 'ships sunk', 'aircraft shot down']
    for i, n in enumerate(names):
        out.append('  +%02X player %-26s %d' % (0x10 + 2 * i, n, s16(d, 0x10 + 2 * i)))
    for i, n in enumerate(names):
        out.append('  +%02X flight %-26s %d' % (0x18 + 2 * i, n, s16(d, 0x18 + 2 * i)))
    out.append('  +20 u16 (time?)      %d' % s16(d, 0x20))
    out.append('  +22 mission score    %d  (0..900, realism-scaled)' % s16(d, 0x22))


def dump_control(d, out):
    out.append('CONTROL.PRF (37 bytes, PS 1193:027A -> DS:43B0)')
    out.append('  +00 u16 %d  +02 u16 %d' % (u16(d, 0), u16(d, 2)))
    out.append('  +04 bytes %s  (+06..+0C default 1)' % hexs(d[4:13]))
    out.append('  joystick X min/centre/max %d %d %d   Y %d %d %d' % (s16(d, 13), s16(d, 15), s16(d, 17), s16(d, 19), s16(d, 21), s16(d, 23)))
    out.append('  +19 %s' % hexs(d[25:]))


def dump_simprefs(d, out):
    out.append('SIMPREFS.PRF (70 bytes, AP 4E0D:09D0: 10 bytes -> 4253:08B7, rest via 2C30:0007)')
    out.append('  +00 u16[5] %s' % words(d[:10]))
    for i in range(10, len(d), 6):
        out.append('  +%02X %s' % (i, words(d[i:i + 6])))


def dump_real(d, out):
    out.append('?REAL.PRF (16 bytes; MREAL = single mission, CREAL = career; PS DS:4357, AP picks m/c by mode)')
    out.append('  bytes %s' % hexs(d))


def dump_roster(d, out):
    n = u16(d, 0)
    out.append('ROSTER.DAT: u16 n=%d, n x 122-byte pilot records, u16 len, len bytes (PS 1193:031E)' % n)
    p = 2
    for i in range(n):
        r = d[p:p + 122]
        out.append('  %2d %-20s %s' % (i, cstr(r, 0, 20), hexs(r[20:])))
        p += 122
    if p + 2 <= len(d):
        k = u16(d, p)
        out.append('  extra %d bytes: %s' % (k, hexs(d[p + 2:p + 2 + k])))


def dump_topace(d, out):
    n = u16(d, 0)
    out.append('TOPACE.DAT: u16 n=%d (<=10), n x 122-byte pilot records (PS 1193:050D)' % n)
    for i in range(n):
        r = d[2 + 122 * i:2 + 122 * (i + 1)]
        out.append('  %2d %-20s %s' % (i, cstr(r, 0, 20), hexs(r[20:])))


def dump_topmiss(d, out):
    n = u16(d, 0)
    out.append('TOPMISS.DAT: u16 n=%d (<=10), n x 55-byte records (PS 1193:05B8)' % n)
    for i in range(n):
        r = d[2 + 55 * i:2 + 55 * (i + 1)]
        out.append('  %2d %-16s w %s  tail %s' % (i, cstr(r, 0, 16), words(r[16:52]), hexs(r[52:])))


def dump_vcr(d, out):
    n = u16(d, 0x1ae)
    out.append('VCR film (AP 618D:011F): 66-byte header, 364 bytes (zero), u16 n, n-byte mission script, event stream')
    h = d[:0x42]
    out.append('  +00 u16 %d (bit 0 required)  +02 u16 %d  +04 u16 %d' % (u16(h, 0), u16(h, 2), u16(h, 4)))
    out.append('  +06 bytes %s' % hexs(h[6:0x16]))
    out.append('  +16 u32 %d   +1A u32 %d   +1E %s' % (u32(h, 0x16), u32(h, 0x1a), hexs(h[0x1e:0x24])))
    out.append('  +24 SIM.IN copy: %s' % hexs(h[0x24:0x31]))
    out.append('  +31 %s' % hexs(h[0x31:]))
    out.append('  mission script %d bytes at 1B0h; event stream %d bytes at %Xh (Huffman, SIM2 *.HUF tables)' % (n, len(d) - 0x1b0 - n, 0x1b0 + n))
    sub = []
    dump_mission(d[0x1b0:0x1b0 + n], sub)
    out.extend('  | ' + s for s in sub)


# ---------------------------------------------------------------- per-model sim data
def dump_plt(d, out):
    out.append('.PLT pilot (112 bytes, AP 45CC:00A0; ratings 0..1000 mapped by 45CC:0080 to ranges)')
    out.append('  u16[17] %s' % words(d[:34]))
    out.append('  +22 %s' % hexs(d[34:0x58]))
    out.append('  +58 name "%s"' % cstr(d, 0x58))


def dump_gl(d, out):
    n = u16(d, 0)
    out.append('.GL guns: u16 n=%d, n x 20 bytes (aircraft; 10 for ships), u16 tail (AP 4CDA:0037)' % n)
    for i in range(n):
        r = d[2 + 20 * i:22 + 20 * i]
        out.append('  %d  %s   words %s' % (i, hexs(r[:2]), words(r[2:])))
    out.append('  tail %s' % hexs(d[2 + 20 * n:]))


def dump_dmg(d, out):
    h = u16(d, 0)
    n = h & 15
    out.append('.DMG: u16 hdr %04x (n = low nibble = %d), n x 10 bytes + 14 (aircraft) / n x 8 + 2 (ships) (AP 4B3A:0341)' % (h, n))
    out.append('  %s' % words(d[2:]))


def dump_bxl(d, out):
    n = d[0]
    out.append('.BXL: u8 n=%d, u8 %d, u32 %d, n x 12 = boxes (s16 x1 y1 z1 x2 y2 z2) (AP 48AF:0017)' % (n, d[1], u32(d, 2)))
    for i in range(n):
        out.append('  %d %s' % (i, words(d[6 + 12 * i:18 + 12 * i])))


def dump_gau(d, out):
    out.append('.GAU gauges (AP 4CAD:00AB): char[14] back "%s", u16 %d, char[14] common "%s", u16 n' % (cstr(d, 0, 14), u16(d, 14), cstr(d, 16, 14)))
    n = u16(d, 30)
    for i in range(n):
        r = d[32 + 28 * i:60 + 28 * i]
        if len(r) < 28:
            break
        out.append('  %2d kind %2d  %-12s  %s' % (i, u16(r, 0), cstr(r, 2, 14), words(r[16:])))


def dump_mec(d, out):
    n = u16(d, 0)
    out.append('.MEC weapons: u16 n=%d, n x 16 bytes' % n)
    for i in range(n):
        out.append('  %d %s' % (i, hexs(d[2 + 16 * i:18 + 16 * i])))


def dump_huf(d, out):
    n = u16(d, 0)
    out.append('.HUF: u16 n=%d, n x (u16 symbol, u32 frequency) -> Huffman tree for VCR streams' % n)
    rows = [(u16(d, 2 + 6 * i), u32(d, 4 + 6 * i)) for i in range(n)]
    out.append('  ' + ' '.join('%d:%d' % r for r in rows))


def dump_wnd(d, out):
    out.append('.WND (74 bytes, AP 56AC:0000): s32[5] %s' % [s32(d, 4 * i) for i in range(5)])
    out.append('  +14 %s' % words(d[20:]))


def dump_evt(d, out):
    n = u16(d, 0)
    out.append('.EVT career events: u16 n=%d, n x 66-byte records, then text (Likely)' % n)
    for i in range(n):
        r = d[2 + 66 * i:68 + 66 * i]
        out.append('  %2d  %s  dates %d %d  id %s  ttm "%s"  %s' % (i, hexs(r[:7]), u16(r, 7), u16(r, 9), repr(chr(r[25])), cstr(r, 26, 9), words(r[35:65])))
    out.append('  tail %d bytes' % (len(d) - 2 - 66 * n))


def dump_acdat(d, out):
    out.append('aircraft .DAT (131 bytes, AP 45CC:034F; +04/+08/+24/+73 overwritten at run time)')
    out.append('  +00 %s  name "%s"' % (hexs(d[:10]), cstr(d, 10)))
    out.append('  +22 %s' % words(d[0x22:0x3a]))
    out.append('  +3A %s' % hexs(d[0x3a:]))


def dump_shipdat(d, out):
    out.append('ship .DAT (154 bytes, AP 45CC:05CE): name "%s"' % cstr(d, 0x4f))
    out.append('  %s' % hexs(d))


def dump_ttms(d, out):
    out.append('TTMS0.DAT (PS 0F35:012D): records u8 idx + 4 x (char[9] ttm, s16[4])')
    for i in range(0, len(d) - 68, 69):
        r = d[i:i + 69]
        out.append('  idx %d: ' % r[0] + ' | '.join('%s %s' % (cstr(r, 1 + 17 * k, 9), words(r[10 + 17 * k:18 + 17 * k])) for k in range(4)))


def dump_hex(d, out, what):
    out.append('%s (%d bytes), raw:' % (what, len(d)))
    for i in range(0, len(d), 16):
        out.append('  %04x  %s' % (i, hexs(d[i:i + 16])))


# ---------------------------------------------------------------- dispatch
def classify(name, d):
    up = name.upper()
    base, ext = os.path.splitext(up)
    if up == 'SIM.IN':
        return dump_simin
    if up == 'SIM.OUT':
        return dump_simout
    if up == 'CONTROL.PRF':
        return dump_control
    if up == 'SIMPREFS.PRF':
        return dump_simprefs
    if up in ('MREAL.PRF', 'CREAL.PRF'):
        return dump_real
    if up == 'ROSTER.DAT':
        return dump_roster
    if up == 'TOPACE.DAT':
        return dump_topace
    if up == 'TOPMISS.DAT':
        return dump_topmiss
    if ext == '.VCR':
        return dump_vcr
    if up == 'SCRIPT.DAT' or re.match(r'(MISS\d+|TRN\d+)\.DAT$', up):
        return dump_mission
    if up == 'TTMS0.DAT':
        return dump_ttms
    if ext == '.PLT':
        return dump_plt
    if ext == '.GL':
        return dump_gl
    if ext == '.DMG':
        return dump_dmg
    if ext == '.BXL':
        return dump_bxl
    if ext == '.GAU':
        return dump_gau
    if ext == '.MEC':
        return dump_mec
    if ext == '.HUF':
        return dump_huf
    if ext == '.WND':
        return dump_wnd
    if ext == '.EVT':
        return dump_evt
    if ext == '.TXT':
        return dump_names
    if ext == '.GLT':
        return lambda d, out: out.append('gun loadout texts: ' + ' | '.join(x.decode('latin1') for x in d.split(b'\0') if x))
    if ext in ('.SCD', '.DAT') and strtab(d) is not None:
        return dump_strtab
    if ext == '.DAT' and len(d) == 131 and d[10:11].isalpha():
        return dump_acdat
    if ext == '.DAT' and len(d) == 154 and d[0x4f:0x50].isalpha():
        return dump_shipdat
    if ext == '.DAT' and len(d) > 32 and sum(1 for x in d if 32 <= x < 127) > 0.5 * len(d):
        return dump_strings_found
    if ext in ('.FMD', '.EDG', '.BOX', '.BL', '.BND', '.DAT', '.PRF', '.FLT', '.WLD'):
        return lambda d, out: dump_hex(d, out, ext[1:])
    return None


def dump_file(path, name=None):
    name = name or os.path.basename(path)
    d = open(path, 'rb').read()
    f = classify(name, d)
    if f is None:
        return None
    out = ['; %s  %d bytes' % (name, len(d))]
    try:
        r = f(d, out)
        if r is False:
            out.append('(not a string table)')
    except Exception as e:  # keep going over the whole corpus
        out.append('!! decode error: %r' % e)
    return out


LOOSE = ['SIM.IN', 'SIM.OUT', 'CONTROL.PRF', 'SIMPREFS.PRF', 'MREAL.PRF', 'CREAL.PRF', 'ROSTER.DAT',
         'TOPACE.DAT', 'TOPMISS.DAT', 'SCRIPT.DAT', 'MAINMENU.SCD']


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if cmd == 'one':
        out = dump_file(sys.argv[2])
        print('\n'.join(out) if out else 'unsupported')
        return
    if cmd != 'all':
        print(__doc__)
        return
    summ = collections.Counter()
    errs = []
    todo = [(p, os.path.basename(os.path.dirname(p))) for p in sorted(glob.glob(os.path.join(ROOT, 'work', 'dyn', '*', '*')))]
    todo += [(os.path.join(GAME, n), 'game') for n in LOOSE if os.path.exists(os.path.join(GAME, n))]
    todo += [(p, 'game') for p in sorted(glob.glob(os.path.join(GAME, 'TAPES', '*.VCR')))]
    for p, vol in todo:
        out = dump_file(p)
        if out is None:
            continue
        od = os.path.join(ROOT, 'work', 'data', vol)
        os.makedirs(od, exist_ok=True)
        open(os.path.join(od, os.path.basename(p) + '.txt'), 'w', encoding='latin1').write('\n'.join(out) + '\n')
        kind = out[1].split(' ')[0] if len(out) > 1 else '?'
        summ[os.path.splitext(p)[1].upper() or '(none)'] += 1
        if any(s.startswith('!!') for s in out):
            errs.append(p)
    with open(os.path.join(ROOT, 'work', 'data', '_summary.txt'), 'w') as o:
        for k, v in sorted(summ.items()):
            o.write('%-6s %4d\n' % (k, v))
        for e in errs:
            o.write('decode error: %s\n' % e)
    print('%d files -> work/data/, %d decode errors' % (sum(summ.values()), len(errs)))
    for e in errs:
        print('  error:', e)


if __name__ == '__main__':
    main()
