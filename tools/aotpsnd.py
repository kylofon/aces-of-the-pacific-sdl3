"""Aces of the Pacific sound: SX / SNG banks, SCI1 sound resources, SCI sound drivers, AdLib render.

  aotpsnd.py list                  -> every sound of every bank: id, name, flags, size, device tracks
  aotpsnd.py extract               -> work/sound/<BANK>/<id>_<NAME>.snd (standalone SCI sound resources,
                                      '84 00' patch-file header), PATCH.003/.001/.101 and the driver
                                      chunks of every OVL to work/sound/<OVL>/, work/sound/index.txt
  aotpsnd.py dump BANK ID          -> one sound: track table, channel headers, event listing
  aotpsnd.py dro [BANK [ID ...]]   -> render through the models of the game's SCI1 sequencer
                                      (INTRO 1373:*, same code in PS/AP) and AdLib driver (SSM:ADL:
                                      of SXCODE/SX/SX1.OVL) to DOSBox raw OPL v2 files
                                      work/sound/<BANK>/<id>_<NAME>.dro (+ .txt with the driver calls)
  aotpsnd.py all                   -> extract + dro for everything

BANK = SHELL (SHELL1:SHELL.SX), TTD (SHELL1:TTD.SX), SIM (SIM2:SIMSNDS.SNG), SIM1 (M1SIM:SIMSNDS1.SNG).
Options for dro: --passes N (looping sounds: stop after N passes, default 2), --max S (seconds cap,
default 300), --tail S (release time after the stop, default 1.5).

Format and driver notes: port/formats/sound.md.
"""
import os, struct, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynvol, dynchunk

OUT = os.path.join('work', 'sound')

# bank key -> (volume, entry, OVL volume, OVL entry that the program using the bank loads)
BANKS = {
    'SHELL': ('SHELL1', 'SHELL.SX', 'SHELL1', 'SXCODE.OVL'),     # PS.EXE (shell)
    'TTD':   ('SHELL1', 'TTD.SX', 'SHELL1', 'SXCODE.OVL'),       # INTRO.EXE ("ttd.sx")
    'SIM':   ('SIM2', 'SIMSNDS.SNG', 'SIM2', 'SX.OVL'),          # AP.EXE
    'SIM1':  ('M1SIM', 'SIMSNDS1.SNG', 'M1SIM', 'SX1.OVL'),      # AP.EXE with the 1946 add-on
}
OVLS = [('SHELL1', 'SXCODE.OVL'), ('SIM2', 'SX.OVL'), ('M1SIM', 'SX1.OVL')]

DEVICES = {0x00: 'AdLib', 0x06: 'Amiga/Mac', 0x07: 'GM', 0x09: 'CMS/SB?', 0x0C: 'MT-32',
           0x12: 'PC speaker', 0x13: 'Tandy/PS1', 0xF0: 'digital'}

# PIT: divisor 0x10000/13 = 5041 (05da:2374), sound service every 4th interrupt (05da:2307)
PIT_HZ = 1193182.0
TICK_S = 4 * 5041 / PIT_HZ                  # 16.900 ms, 59.17 Hz
TICK_MS = TICK_S * 1000.0

_vols = {}


def volume(name):
    if name not in _vols:
        _vols[name] = dynvol.Volume(os.path.join('Game', name + '.DYN'))
    return _vols[name]


def entry(vol, name):
    v = volume(vol)
    e = v.find(name)
    if e is None:
        raise SystemExit('%s: no %s' % (vol, name))
    return v.get(e)


def cstr(d, p):
    e = d.index(b'\0', p)
    return d[p:e].decode('latin1'), e + 1


# ---------------------------------------------------------------- containers

class SoundRec:
    """One sound of a bank. data = the unpacked resource including its 2-byte '84 00' header."""
    def __init__(self, bank, index, sid, name, src, prio, flags, data):
        self.bank, self.index, self.id, self.name, self.src = bank, index, sid, name, src
        self.prio, self.flags, self.data = prio, flags, data

    @property
    def loop(self):
        return bool(self.flags & 2)

    @property
    def fname(self):
        return '%04d_%s' % (self.id, self.name) if self.name else '%04d' % self.id


def load_bank(key):
    vol, name = BANKS[key][:2]
    d = entry(vol, name)
    top = dynchunk.parse(d)[0]
    out = []
    if top.tag == 'SND:':
        # SND:{INF: TAG: FNM: DAT:*n}
        kids = top.children
        inf = next(c.raw for c in kids if c.tag == 'INF:')
        ver, n = struct.unpack_from('<HH', inf)
        ids = struct.unpack_from('<%dH' % n, inf, 4)
        names, srcs = {}, {}
        for c in kids:
            if c.tag in ('TAG:', 'FNM:'):
                m, = struct.unpack_from('<H', c.raw)
                p = 2
                for _ in range(m):
                    i, = struct.unpack_from('<H', c.raw, p)
                    s, p = cstr(c.raw, p + 2)
                    (names if c.tag == 'TAG:' else srcs)[i] = s
        dats = [c.raw for c in kids if c.tag == 'DAT:']
        for k, raw in enumerate(dats):
            # DAT: u16 id, u8 priority, u8 flags (bit 0 memory class, bit 1 loop), u8 method, u32 size, data
            sid, prio, fl, meth, size = struct.unpack_from('<HBBBI', raw)
            data = dynchunk.decompress(meth, raw[9:], size)
            out.append(SoundRec(key, k, sid, names.get(sid, ''), srcs.get(sid, ''), prio, fl, data))
        assert [s.id for s in out] == list(ids), 'INF ids do not match DAT order'
    else:
        # SSM:{SNG:*n INF:} ; INF = n x (u8 flags, u8 priority)
        sngs = [c for c in top.children if c.tag == 'SNG:']
        inf = next(c.raw for c in top.children if c.tag == 'INF:')
        for k, c in enumerate(sngs):
            fl, prio = inf[2 * k], inf[2 * k + 1]
            # AP 3280:09ef: INF byte 0 -> node loop flag (15Dh), byte 1 -> priority (15Ch)
            out.append(SoundRec(key, k, k, '', '', prio, 2 if fl & 1 else 0, c.data))
    return out


def load_ovl(vol, name):
    top = dynchunk.parse(entry(vol, name))[0]
    return {c.tag[:3]: c.data for c in top.children}


# ---------------------------------------------------------------- SCI1 sound resource

def tracks(res):
    """res = resource without the 2-byte header. -> (priority or None, [(device, [(u16 a, off, size)])])"""
    p = 0
    prio = None
    if res[0] == 0xF0:
        prio = res[1]
        p = 8
    out = []
    while res[p] != 0xFF:
        dev = res[p]
        p += 1
        chans = []
        while res[p] != 0xFF:
            chans.append(struct.unpack_from('<HHH', res, p))
            p += 6
        p += 1
        out.append((dev, chans))
    return prio, out


EVLEN = {0x80: 2, 0x90: 2, 0xA0: 2, 0xB0: 2, 0xC0: 1, 0xD0: 1, 0xE0: 2}


def channel_events(res, off, size):
    """Walk one channel like 1373:1932 (without the loop jumps): header 2 bytes, delta, events.
    -> header, [(tick, pos, status, data bytes)], end tick"""
    hdr = res[off:off + 2]
    p = off + 2
    end = off + size
    t = 0
    ev = []
    rs = 0xB0 | (hdr[0] & 0x0F)
    # first delta
    while p < end:
        d = res[p]
        p += 1
        if d == 0xF8:
            t += 240
            continue
        t += d
        break
    while p < end:
        st = res[p]
        if st >= 0x80:
            p += 1
            rs = st
        else:
            st = rs
        if st == 0xFC:
            ev.append((t, p - 1, st, b''))
            break
        hi = st & 0xF0
        if hi == 0xF0:
            q = p
            while q < end and res[q] != 0xF7:
                q += 1
            ev.append((t, p, st, res[p:q + 1]))
            p = q + 1
        else:
            n = EVLEN[hi]
            ev.append((t, p, st, res[p:p + n]))
            p += n
        while p < end:
            d = res[p]
            p += 1
            if d == 0xF8:
                t += 240
                continue
            t += d
            break
    return hdr, ev, t


def describe(st, db):
    hi, ch = st & 0xF0, st & 0x0F
    if st == 0xFC:
        return 'end'
    if hi == 0x80:
        return 'ch%-2d note off %3d vel %d' % (ch, db[0], db[1])
    if hi == 0x90:
        return 'ch%-2d note on  %3d vel %d' % (ch, db[0], db[1])
    if hi == 0xB0:
        names = {1: 'modulation', 7: 'volume', 10: 'pan', 0x40: 'sustain', 0x4B: 'voices',
                 0x4E: 'mute', 0x50: 'reverb', 0x52: 'hold point', 0x60: 'cue', 0x7B: 'all notes off'}
        return 'ch%-2d ctrl %02X %s = %d' % (ch, db[0], names.get(db[0], ''), db[1])
    if hi == 0xC0:
        if ch == 15:
            return 'ch15 %s %d' % ('LOOP POINT' if db[0] == 0x7F else 'signal', db[0])
        return 'ch%-2d program %d' % (ch, db[0])
    if hi == 0xE0:
        return 'ch%-2d pitch bend %d' % (ch, (db[1] << 7 | db[0]) - 0x2000)
    if hi == 0xD0:
        return 'ch%-2d channel pressure %d' % (ch, db[0])
    if hi == 0xA0:
        return 'ch%-2d key pressure %d %d' % (ch, db[0], db[1])
    return 'sysex/%02X %s' % (st, db.hex(' '))


def summary(rec):
    res = rec.data[2:]
    prio, trk = tracks(res)
    parts = []
    for dev, chans in trk:
        cs = []
        for a, off, size in chans:
            if off + 1 < len(res):
                c = res[off]
                cs.append('%X%s' % (c & 0x0F, '' if c < 0x10 else '/%X' % (c >> 4)) if c != 0xFE else 'dig')
        parts.append('%02X:%s' % (dev, ','.join(cs)))
    return prio, ' '.join(parts)


# ---------------------------------------------------------------- AdLib driver model (SSM:ADL:)

class AdlibDriver:
    """The SCI1 AdLib driver of SXCODE/SX/SX1.OVL ('dude', 18 functions, table at 1419h).
    State lives in a copy of the driver image at the same offsets (so out-of-range reads behave
    like the original); addresses in comments are driver offsets."""

    def __init__(self, image, write):
        self.m = bytearray(image) + bytearray(0x400)
        self.write = write                  # write(reg, val)
        self.dropped = 0                    # note-ons without a free or stealable voice

    # memory helpers
    def b(self, o):
        return self.m[o & 0xFFFF]

    def sb(self, o, v):
        self.m[o & 0xFFFF] = v & 0xFF

    def w(self, o):
        return self.m[o & 0xFFFF] | self.m[(o + 1) & 0xFFFF] << 8

    def sw(self, o, v):
        self.m[o & 0xFFFF] = v & 0xFF
        self.m[(o + 1) & 0xFFFF] = (v >> 8) & 0xFF

    def out(self, reg, val):                # 1b13: index 388h, data 389h (6 / 35 status reads)
        self.write(reg & 0xFF, val & 0xFF)

    # ---- entry points (BP = function number, 143d)
    def patch_req(self):                    # fn 0, 1f7d: AH=1 AL=3 (PATCH.003) CH=0 (play id) CL=9 voices
        return 0x0103, 9, 0, 1

    def init(self, patch):                  # fn 1, 1f2e
        patch = bytes(patch)
        self.m[0x8F2:0x8F2 + 0x540] = patch[:0x540]
        if len(patch) >= 0x542 and patch[0x540] == 0xAB and patch[0x541] == 0xCD:
            self.m[0x8F2 + 0x540:0x8F2 + 0xA80] = patch[0x542:0x542 + 0x540]
        self.reset()
        self.master_volume(15)
        return 0, 0, 15                     # AX, CL = first channel, CH = last channel

    def terminate(self):                    # fn 2, 15d6
        self.reset()

    def service(self):                      # fn 3, 188f: age of every sounding voice + 1
        for v in range(9):
            if self.b(0x73E + v) != 0xFF:
                self.sw(0x75F + 2 * v, self.w(0x75F + 2 * v) + 1)

    def note_off(self, ch, note, vel=0):    # fn 4, 145a
        for v in range(9):
            if self.b(0x733 + v) == ch and self.b(0x73E + v) == note:
                if self.b(0x6E3 + ch):
                    self.sb(0x754 + v, 1)
                else:
                    self.voice_off(v)
                return

    def note_on(self, ch, note, vel):       # fn 5, 1490
        if vel == 0:
            self.note_off(ch, note)
            return
        if note < 0x0C or note > 0x6B:
            return
        vel >>= 1
        for v in range(9):
            if self.b(0x733 + v) == ch and self.b(0x73E + v) == note:
                self.voice_off(v)
                self.voice_on(v, note, vel)
                return
        v = self.alloc(ch)
        if v != 0xFF:
            self.voice_on(v, note, vel)
        else:
            self.dropped += 1

    def controller(self, ch, ctl, val):     # fn 7, 14d8
        if ctl == 7:                        # 1762
            self.sb(0x6C3 + ch, val >> 1)
            self._update_channel(ch)
        elif ctl == 10:                     # 1799 (pan: stored, no audible effect on OPL2)
            self.sb(0x6D3 + ch, val)
            self._update_channel(ch)
        elif ctl == 0x40:                   # 17ca hold pedal
            self.sb(0x6E3 + ch, val)
            if val == 0:
                for v in range(9):
                    if self.b(0x733 + v) == ch and self.b(0x754 + v):
                        self.voice_off(v)
        elif ctl == 0x4B:                   # 1641 voice mapping
            self.voice_map(ch, val)
        elif ctl == 0x7B:                   # all notes off
            for v in range(9):
                if self.b(0x733 + v) == ch and self.b(0x73E + v) != 0xFF:
                    self.voice_off(v)

    def _update_channel(self, ch):
        for v in range(9):
            if self.b(0x733 + v) == ch and self.b(0x73E + v) != 0xFF:
                self.set_note(v, self.b(0x73E + v), 1)

    def program(self, ch, prog):            # fn 8, 1522: used at the next note-on
        self.sb(0x6B3 + ch, prog)

    def pitch_bend(self, ch, lsb, msb):     # fn 10, 1530
        self.sw(0x703 + 2 * ch, (msb << 7 | lsb) & 0xFFFF)
        for v in range(9):
            if self.b(0x733 + v) == ch:
                self.set_note(v, self.b(0x73E + v), 1)

    def reverb(self, val):                  # fn 11, 15c5 (stored only)
        old = self.b(0x6B0)
        if val != 0xFF:
            self.sb(0x6B0, val)
        return old

    def master_volume(self, val):           # fn 12, 1595
        old = self.b(0x6B2)
        if val != 0xFF:
            self.sb(0x6B2, val)
            for v in range(9):
                if self.b(0x73E + v) != 0xFF:
                    self.set_note(v, self.b(0x73E + v), 1)
        return old

    def sound_on(self, val):                # fn 13, 1565
        old = self.b(0x6B1)
        if val != 0xFF:
            self.sb(0x6B1, val)
            for v in range(9):
                if self.b(0x73E + v) != 0xFF:
                    self.set_note(v, self.b(0x73E + v), 1)
        return old

    # ---- voices
    def alloc(self, ch):                    # 15da
        dx = 0
        cl = 0
        last = self.b(0x723 + ch)
        bl = last
        while True:
            bl += 1
            if bl == 9:
                bl = 0
            stop = bl == last
            if self.b(0x733 + bl) == ch:
                if self.b(0x73E + bl) == 0xFF:
                    self.sb(0x723 + ch, bl)
                    return bl
                if self.w(0x75F + 2 * bl) >= dx:
                    dx = self.w(0x75F + 2 * bl)
                    cl = bl
            if stop:
                break
        if dx == 0:
            return 0xFF
        self.voice_off(cl)
        self.sb(0x723 + ch, cl)
        return cl

    def voice_on(self, v, note, vel):       # 17f9
        self.sw(0x75F + 2 * v, 0)
        prog = self.b(0x6B3 + self.b(0x733 + v))
        if prog != self.b(0x775 + v) and self.b(0x6B1):
            self.sb(0x775 + v, prog)
            self.load_patch(v, 0x8F2 + prog * 28)
        self.sb(0x749 + v, vel)
        self.set_note(v, note, 1)

    def voice_off(self, v):                 # 1865
        self.sb(0x754 + v, 0)
        self.set_note(v, self.b(0x73E + v), 0)
        self.sb(0x73E + v, 0xFF)
        self.sw(0x75F + 2 * v, 0)

    def set_note(self, v, note, keyon):     # 18ab: frequency + key, then volume
        self.sb(0x73E + v, note)
        ch = self.b(0x733 + v)
        cx = (note << 2) & 0xFFFF
        cx = self.bend(ch, cx)              # 1958
        if cx == 0xFFFF:
            return
        fnum = self.w(0x236 + 2 * cx)
        self.out(0xA0 + v, fnum & 0xFF)
        al = ((keyon << 3 | self.b(0x39 + cx)) << 2) & 0xFF
        self.out(0xB0 + v, al | fnum >> 8)
        al = (self.b(0x6C3 + ch) + 1) & 0xFF
        cl = (self.b(0x630 + self.b(0x749 + v)) + 1) & 0xFF
        ax = (al * cl) >> 6
        ax = ((ax & 0xFF) * ((self.b(0x6B2) + 1) & 0xFF)) >> 4
        al = ax & 0xFF
        if al:
            al -= 1
        if self.b(0x6B1) == 0:
            al = 0
        self.set_volume(v, al)              # 19b2

    def bend(self, ch, cx):                 # 1958: 1/4 semitone steps, +-48 over the bend range
        di = self.w(0x703 + 2 * (ch & 0xFF))
        if di == 0x2000:
            return cx if cx < 0x1FC else 0xFFFF
        up = di > 0x2000
        d = ((di - 0x2000) if up else (0x2000 - di)) // 0xAA & 0xFF
        cx = (cx + d if up else cx - d) & 0xFFFF
        return cx if cx < 0x1FC else 0xFFFF

    def set_volume(self, v, al):            # 19b2: TL = 63 - vol * (63 - patch TL) / 63
        al = self.b(0x670 + al)
        cl = self.w(0x13A0 + 2 * v) & 0xFF
        q = ((al * cl) & 0xFFFF) // 0x3F & 0xFF
        tl = (0x3F - q) & 0xFF
        tl |= (self.w(0x138A + 2 * v) << 6) & 0xFF
        self.out(0x40 + self.b(0x7A4 + self.b(0x780 + v)), tl)
        if self.b(0x13F8 + v):
            cl = self.w(0x13E2 + 2 * v) & 0xFF
            q = ((al * cl) & 0xFFFF) // 0x3F & 0xFF
            tl = (0x3F - q) & 0xFF
            tl |= (self.w(0x13CC + 2 * v) << 6) & 0xFF
            self.out(0x40 + self.b(0x7A4 + self.b(0x789 + v)), tl)

    def load_patch(self, v, p):             # 1a4e: 28-byte SCI AdLib instrument at driver offset p
        m = self.m
        self.sb(0x13F8 + v, 1)
        if m[p + 0x0C]:
            self.sb(0x13F8 + v, 0)          # FM: modulator TL not scaled by volume
        else:
            self.sw(0x13CC + 2 * v, m[p])
            tlc = (0x3F - m[p + 8]) & 0xFF
            self.sw(0x13E2 + 2 * v, tlc)
            self.sw(0x1403 + 2 * v, tlc // 15)
        self.sw(0x138A + 2 * v, m[p + 0x0D])
        tlc = (0x3F - m[p + 0x15]) & 0xFF
        self.sw(0x13A0 + 2 * v, tlc)
        self.sw(0x13B6 + 2 * v, tlc // 15)
        self.write_op(self.b(0x7C8 + 2 * v), p, m[p + 0x1A])
        self.write_op(self.b(0x7C9 + 2 * v), p + 0x0D, m[p + 0x1B])

    def write_op(self, op, p, wf):          # 1c20 + 1c69
        s = 0x7F6 + 14 * op
        self.m[s:s + 13] = self.m[p:p + 13]
        self.sb(s + 13, wf & 3)
        off = self.b(0x7A4 + op)
        self.write_bd()                                                     # 1bcf
        self.out(0x08, 0x40 if self.b(0x1380) else 0)                       # 1cca
        self.out(0x40 + off, (self.b(s) << 6 | self.b(s + 8) & 0x3F) & 0xFF)  # 1c82 KSL/TL
        if self.b(0x792 + op) == 0:                                         # 1ce2 (modulator only)
            c = (self.b(s + 2) << 1) + (1 if self.b(s + 12) == 0 else 0)
            self.out(0xC0 + self.b(0x7B6 + op), c & 0x0F)
        self.out(0x60 + off, (self.b(s + 3) << 4 | self.b(s + 6) & 0x0F) & 0xFF)  # 1d32 AR/DR
        self.out(0x80 + off, (self.b(s + 4) << 4 | self.b(s + 7) & 0x0F) & 0xFF)  # 1d78 SL/RR
        c = ((0x80 if self.b(s + 9) else 0) | (0x40 if self.b(s + 10) else 0) |
             (0x20 if self.b(s + 5) else 0) | (0x10 if self.b(s + 11) else 0) | self.b(s + 1) & 0x0F)
        self.out(0x20 + off, c)                                             # 1dbe
        if self.w(0x1385):
            self.out(0xE0 + off, self.b(s + 13))                            # 1e2c

    def write_bd(self):                     # 1bcf
        c = (0x80 if self.b(0x1381) else 0) | (0x40 if self.b(0x1382) else 0) | self.b(0x1384)
        self.out(0xBD, c)

    def reset(self):                        # 1e6b
        self.out(0x01, 0)
        self.sb(0x1383, 0)                  # 1b53
        self.sb(0x1384, 0)
        for op in range(18):
            src = 0x7E8 if self.b(0x792 + op) else 0x7DA
            self.m[0x1372:0x1372 + 13] = self.m[src:src + 13]
            self.write_op(op, 0x1372, 0)
        self.write_bd()
        self.sb(0x1381, 0)
        self.sb(0x1382, 0)
        self.sb(0x1380, 0)
        self.write_bd()
        self.out(0x08, 0x40 if self.b(0x1380) else 0)
        for v in range(9):                  # 1afb
            self.out(0xA0 + v, 0)
            self.out(0xB0 + v, 0)
        self.sw(0x1385, 0x20)               # 1b90(1)
        for op in range(18):
            self.out(0xE0 + self.b(0x7A4 + op), 0)
        self.out(0x01, 0x20)

    # ---- 1641: controller 4Bh, number of voices wanted by a channel
    def voice_map(self, ch, n):
        dl = sum(1 for v in range(9) if self.b(0x733 + v) == ch) + self.b(0x6F3 + ch)
        dl &= 0xFF
        if dl == n:
            return
        if dl < n:
            self._assign(ch, n - dl)
        else:
            self._release(ch, dl - n)
            self._redistribute()

    def _assign(self, ch, cl):              # 16d4
        for v in range(9):
            if self.b(0x733 + v) == 0xFF:
                self.sb(0x733 + v, ch)
                cl -= 1
                if cl == 0:
                    break
        self.sb(0x6F3 + ch, self.b(0x6F3 + ch) + cl)

    def _release(self, ch, cl):             # 16ff
        ex = self.b(0x6F3 + ch)
        if ex >= cl:
            self.sb(0x6F3 + ch, ex - cl)
            return
        cl -= ex
        self.sb(0x6F3 + ch, 0)
        for v in range(9):
            if self.b(0x733 + v) == ch and self.b(0x73E + v) == 0xFF:
                self.sb(0x733 + v, 0xFF)
                cl -= 1
                if cl == 0:
                    return
        for v in range(9):
            if self.b(0x733 + v) == ch:
                self.voice_off(v)
                self.sb(0x733 + v, 0xFF)
                cl -= 1
                if cl == 0:
                    return

    def _redistribute(self):                # 167d
        cl = sum(1 for v in range(9) if self.b(0x733 + v) == 0xFF)
        if cl == 0:
            return
        for si in range(16):
            ch = self.b(0x6F3 + si)
            if ch == 0:
                continue
            if ch < cl:
                cl -= ch
                self.sb(0x6F3 + si, 0)
                self._assign(si, ch)
            else:
                self.sb(0x6F3 + si, ch - cl)
                self._assign(si, cl)
                return


# ---------------------------------------------------------------- sequencer model (INTRO 1373:*)

class Node:
    """Sound node (0x17a bytes, 1593:019c). Only the fields the sequencer uses; per-channel tables are
    kept in one bytearray at the original offsets because they overlap (stride 15, index = MIDI
    channel, the control channel 15 spills into the next table)."""
    def __init__(self, res, prio=0, loop=0, vol=0x7F):
        self.res = bytearray(res)           # resource after the '84 00' header
        self.n = bytearray(0x180)
        self.n[0x15E] = vol
        self.n[0x15C] = prio
        self.n[0x15D] = loop
        self.restarts = 0

    def b(self, o):
        return self.n[o]

    def sb(self, o, v):
        self.n[o] = v & 0xFF

    def w(self, o):
        return self.n[o] | self.n[o + 1] << 8

    def sw(self, o, v):
        self.n[o] = v & 0xFF
        self.n[o + 1] = (v >> 8) & 0xFF

    def tab(self, i):                       # channel offset table written by prepare()
        return self.res[2 * i] | self.res[2 * i + 1] << 8


def scale_vol(v, sv):                       # 1fb5
    ax = ((v + 1) & 0xFF) * ((sv + 1) & 0xFF)
    c = ((ax >> 8) << 1) & 0xFF
    return c - 1 if c else 0


class Sequencer:
    def __init__(self, drv, patch, log=None):
        self.drv = drv
        self.log = log                      # list for driver-call trace, or None
        self.list = [None] * 16             # 18f
        self.newmap = [0xFF] * 16           # 20f
        self.oldchan = [0x0F] * 16          # 2df
        self.oldowner = [None] * 16         # 29f
        self.pendvol = [0xFF] * 16          # 32f
        self.rr = 0                         # 385
        self.remap_flag = 0                 # 383
        self.seeking = 0                    # 388
        self.default_reverb = 0             # 37b
        self.tick_no = 0
        # 0398: fn 0 patch request
        _, self.voices, self.play_id, ah = drv.patch_req()   # 378, 375
        self.digital = (ah & 0xF0) >> 4                        # 379
        # 03c8: fn 1 init with the patch, then fn 11 reverb 0
        _, self.minch, self.maxch = drv.init(patch)            # 37c, 37e
        self.call('reverb', 0)

    def call(self, fn, *a):
        if self.log is not None:
            self.log.append((self.tick_no, fn, a))
        return getattr(self.drv, fn)(*a)

    # ---- 1fef: point the channel table at the device's track (done in place, once)
    def prepare(self, node):
        r = node.res
        if r[0x21:0x24] == b'\xfc\xfd\xfe':
            return
        tab = [0] * 16
        prio = 0xFF
        p = 0
        if r[0] == 0xF0:
            prio = r[1]
            p = 8
        si = 0
        while True:
            c = r[p]
            if c == self.play_id:
                p += 1
                while True:
                    c = r[p]
                    p += 1
                    if c == 0xFF:
                        break
                    p += 1
                    tab[si] = r[p] | r[p + 1] << 8
                    p += 4
                    si += 1
                break
            if c == 0xFF:
                break
            p += 1
            while True:
                c = r[p]
                p += 1
                if c == 0xFF:
                    break
                p += 5
        for i in range(16):
            r[2 * i] = tab[i] & 0xFF
            r[2 * i + 1] = tab[i] >> 8
        r[0x20] = prio
        r[0x21:0x24] = b'\xfc\xfd\xfe'

    # ---- 0528: play(node, cx); the game always passes cx = 1 (1708:0008, 16ac:01ee)
    def play(self, node, cx=1):
        if node in self.list:
            self.stop(node)
            self.remap()
        node.sb(0x159, 2 if cx else 1)
        self.prepare(node)
        n = node
        for si in range(15):
            n.sw(0x0C + 2 * si, 0x0D); n.sw(0x2C + 2 * si, 3)
            n.sw(0x4C + 2 * si, 0); n.sw(0x6C + 2 * si, 0); n.sw(0xBC + 2 * si, 0x2000)
            n.sb(0x8C + si, 0xFF); n.sb(0x9C + si, 0); n.sb(0xAC + si, 0)
            n.sb(0xDA + si, 0xFF); n.sb(0xE9 + si, 0); n.sb(0x116 + si, 0xFF)
            n.sb(0x107 + si, 0xFF); n.sb(0xF8 + si, 0xFF); n.sb(0x125 + si, 0xFF)
            n.sb(0x134 + si, 0); n.sb(0x143 + si, 0)
        si = 15
        n.sb(0x8C + si, 0xFF); n.sb(0x9C + si, 0); n.sb(0xAC + si, 0)
        n.sb(0x165, 0); n.sb(0x15A, 0); n.sb(0x15F, 0x7F)
        n.sw(0x0C + 2 * si, 0x0D); n.sw(0x2C + 2 * si, 3); n.sw(0x4C + 2 * si, 0)
        n.sw(0x156, 0)
        r = n.res
        if r[0x20] != 0xFF and n.b(0x15B) == 0:
            n.sb(0x15C, r[0x20])
        for si in range(16):
            off = n.tab(si)
            if off == 0:
                break
            dl = r[off]
            if dl == 0xFE:
                if self.digital == 0:
                    n.sw(0x0C + 2 * si, 0); n.sw(0x2C + 2 * si, 0); n.sb(0x8C + si, 0xFE)
                    continue
                n.sb(0x165, si + 1)
                break
            n.sb(0x8C + si, dl)
            n.sb(0x9C + si, dl | 0xB0)
            d = r[off + 0x0C]
            n.sw(0x4C + 2 * si, 0x80F0 if d == 0xF8 else d)
            n.sb(0x8C + si, dl & 0x0F)
            c = dl & 0x0F
            if dl & 0x10:
                n.sw(0x0C + 2 * si, 3); n.sw(0x4C + 2 * si, 0)
                n.sb(0x134 + c, n.b(0x134 + c) | 2)
                continue
            if dl & 0x20:
                n.sb(0x134 + c, n.b(0x134 + c) | 1)
            if dl & 0x40:
                n.sb(0x143 + c, 1)
            if c == 15:
                if n.b(0x15F) == 0x7F:
                    n.sb(0x15F, r[off + 8])
                    continue
            else:
                if n.b(0xDA + c) == 0xFF: n.sb(0xDA + c, r[off + 1])
                if n.b(0x116 + c) == 0xFF: n.sb(0x116 + c, r[off + 4])
                if n.b(0x107 + c) == 0xFF: n.sb(0x107 + c, r[off + 8])
            if n.b(0xF8 + c) == 0xFF: n.sb(0xF8 + c, r[off + 0x0B])
        if n.b(0x159) == 2:
            for si in range(15):
                n.sb(0x134 + si, n.b(0x134 + si) | 1)
        # insert into the list, highest priority value first
        dl = n.b(0x15C)
        for di in range(16):
            o = self.list[di]
            if o is None or o.b(0x15C) <= dl:
                if o is not None:
                    for i in range(14, di - 1, -1):
                        self.list[i + 1] = self.list[i]
                self.list[di] = n
                break
        else:
            return
        if self.seeking:
            return
        n.sw(0x152, 0); n.sw(0x154, 0); n.sb(0x158, 0)
        for o in (0x160, 0x161, 0x162, 0x163, 0x164):
            n.sb(o, 0)
        self.remap()

    # ---- 0b6a: take a node out of the list
    def stop(self, node):
        if node not in self.list:
            return
        i = self.list.index(node)
        self.list[i:15] = self.list[i + 1:16]
        self.list[15] = None
        node.sb(0x158, 0xFF)
        node.sb(0x159, 0)

    def stop_and_remap(self, node):         # 080c
        self.stop(node)
        self.remap()

    # ---- 0c1e: distribute the 16 device channels and the driver voices over the playing sounds
    def remap(self):
        self.remap_flag = 0
        new = [0xFF] * 16
        t21, t22, t23, t24 = [0] * 16, [0] * 16, [0] * 16, [0xFF] * 16
        if self.list[0] is None:
            self._finish([0xFF] * 16)
            return
        cl = self.list[0].b(0x15F)
        if cl == 0x7F:
            cl = self.default_reverb
        self.call('reverb', cl)
        al = self.voices
        for idx in range(16):
            node = self.list[idx]
            if node is None:
                break
            if node.b(0x164):
                continue
            if node.b(0x165):
                continue                    # digital sample sounds (not on AdLib)
            bak = (t24[:], t22[:], t23[:], t21[:], al)
            bp = idx * 16
            rollback = False
            for di in range(16):
                c = node.b(0x8C + di)
                if c in (0xFF, 0xFE, 0x0F):
                    continue
                if node.b(0x134 + c) & 2 or node.b(0x143 + c):
                    continue
                dl = (idx << 4 | c) & 0xFF
                ah = node.b(0xDA + c) & 0x0F
                ch = node.b(0xDA + c) >> 4
                if ch:
                    ch = (0x10 - ch + bp) & 0xFF
                dh = 0xFF
                if node.b(0x134 + c) & 1 and t24[c] == 0xFF:
                    dh = c
                else:
                    skip = False
                    for d in range(16):
                        if t24[d] == 0xFF:
                            if self.minch <= d <= self.maxch:
                                dh = d
                        elif t24[d] == dl:
                            skip = True
                            break
                    if skip:
                        continue
                    if dh == 0xFF:
                        if ch:
                            break           # 0f71: rest of this sound skipped, no rollback
                        dh = self._steal(t21, t22, t23, t24)
                        if dh is None:
                            rollback = True
                            break
                        al = (al + dh[1]) & 0xFF
                        dh = dh[0]
                # fc8: enough voices?
                if ah > al:
                    if ch:
                        continue
                    while ah > al:
                        s = self._steal(t21, t22, t23, t24)
                        if s is None:
                            rollback = True
                            break
                        al = (al + s[1]) & 0xFF
                    if rollback:
                        break
                t24[dh] = dl; t23[dh] = ah; al = (al - ah) & 0xFF; t22[dh] = ch
                if not node.b(0x134 + c) & 1:
                    t21[dh] = 0
                    continue
                t21[dh] = 1
                if dh == c:
                    continue
                if t21[c] == 0:
                    for t in (t24, t22, t23, t21):
                        t[dh], t[c] = t[c], t[dh]
                    continue
                if ch:
                    t24[dh] = 0xFF; t22[dh] = 0; t23[dh] = 0; t21[dh] = 0
                    al = (al + ah) & 0xFF
                    continue
                if t22[c] == 0:
                    rollback = True
                    break
                al = (al + t23[c]) & 0xFF
                t24[dh] = 0xFF; t23[dh] = 0; t22[dh] = 0; t21[dh] = 0
                t24[c] = dl; t22[c] = ch; t23[c] = ah
                al = (al - ah) & 0xFF
            if rollback:
                t24, t22, t23, t21, al = bak[0], bak[1], bak[2], bak[3], bak[4]
        # phase 2 (1258): locked channels, and channels that keep their device channel
        for si in range(16):
            if t24[si] == 0xFF:
                continue
            e = t24[si]
            node = self.list[e >> 4]
            c = e & 0x0F
            if t21[si]:
                t24[si] = 0xFF
                new[si] = e
                if not (self.oldchan[si] == c and self.oldowner[si] is node):
                    self._setup(si, node, c)
            else:
                d = self.minch
                while True:
                    if self.oldowner[d] is node and self.oldchan[d] == c:
                        if t21[d] == 0:
                            new[d] = e
                            t24[si] = 0xFF
                        break
                    if d == self.maxch:
                        break
                    d += 1
        # phase 3 (1402): the rest from the top free device channel downwards
        di = self.maxch + 1
        for si in range(16):
            if t24[si] == 0xFF:
                continue
            bx = di - 1
            while new[bx] != 0xFF:
                bx -= 1
            di = bx
            e = t24[si]
            new[di] = e
            self._setup(di, self.list[e >> 4], e & 0x0F)
        self._finish(new)

    def _steal(self, t21, t22, t23, t24):
        """0f74: free the mapped channel with the largest priority value -> (index, its voices)."""
        best, dh = 0, None
        for d in range(16):
            if best < t22[d]:
                best = t22[d]
                dh = d
        if dh is None:
            return None
        v = t23[dh]
        t24[dh] = 0xFF; t23[dh] = 0; t22[dh] = 0; t21[dh] = 0
        return dh, v

    def _setup(self, d, node, c):           # 12b3 / 1441: bring device channel d up to date
        self.call('controller', d, 0x7B, 0)
        self.call('controller', d, 0x4B, node.b(0xDA + c) & 0x0F)
        self.call('program', d, node.b(0x116 + c))
        self.pendvol[d] = 0xFF
        self.call('controller', d, 7, scale_vol(node.b(0x107 + c), node.b(0x15E)))
        self.call('controller', d, 10, node.b(0xF8 + c))
        self.call('controller', d, 1, node.b(0xE9 + c))
        w = node.w(0xBC + 2 * c)
        self.call('controller', d, 0x40, 0x7F if w >= 0x8000 else 0)
        self.call('pitch_bend', d, w & 0x7F, (w >> 7) & 0x7F)
        self.call('controller', d, 0x4E, node.b(0x125 + c))

    def _finish(self, new):                 # 1514
        for si in range(15, -1, -1):
            if self.oldchan[si] != 0x0F and new[si] == 0xFF:
                self.call('controller', si, 0x40, 0)
                self.call('controller', si, 0x7B, 0)
                self.call('controller', si, 0x4B, 0)
        self.newmap = new
        for i in range(16):
            self.oldchan[i] = new[i] & 0x0F
            self.oldowner[i] = None if new[i] == 0xFF else self.list[new[i] >> 4]

    # ---- 17de: the 59.17 Hz service
    def service(self):
        self.tick_no += 1
        if self.remap_flag:
            self.remap()
        si = 0
        while si < 16:
            node = self.list[si]
            if node is None:
                break
            if node.b(0x164) == 0:
                if node.b(0x163):
                    self.fade(node)
                    if node.b(0x158) == 0xFF:
                        continue
                if not node.b(0x165):
                    self.process(node, si)
                if node.b(0x158) == 0xFF:
                    continue
            si += 1
        self.send_pending()                 # 1796
        self.call('service')                # driver fn 3

    def send_pending(self):                 # 1796: at most 2 queued volume changes per tick
        bl = 0
        si = self.rr
        while True:
            v = self.pendvol[si]
            if v != 0xFF:
                self.pendvol[si] = 0xFF
                self.call('controller', si, 7, v)
                bl += 1
                if bl == 2:
                    break
            si = (si + 1) & 15
            if si == self.rr:
                break
        self.rr = si

    def fade(self, n):                      # 15fc (not used by the renders; kept for completeness)
        if n.b(0x162):
            n.sb(0x162, n.b(0x162) - 1)
            return
        n.sb(0x162, n.b(0x161))
        tgt = n.b(0x160) & 0x7F
        vol = n.b(0x15E)
        if tgt < vol:
            if vol - tgt <= n.b(0x163):
                self.set_volume(n, tgt, 1)
            else:
                self.set_volume(n, vol - n.b(0x163), 1)
                return
        elif tgt > vol:
            if tgt - vol <= n.b(0x163):
                self.set_volume(n, tgt, 1)
            else:
                self.set_volume(n, vol + n.b(0x163), 1)
                return
        n.sb(0x163, 0)
        if n.b(0x160) & 0x80:
            self.stop(n)
            self.remap_flag = 1

    def set_volume(self, n, vol, queue):    # 16b8
        if vol == n.b(0x15E):
            return
        n.sb(0x15E, vol)
        if n not in self.list:
            return
        idx = self.list.index(n) << 4
        for d in range(16):
            e = self.newmap[d]
            if e != 0xFF and e & 0xF0 == idx:
                v = scale_vol(n.b(0x107 + (e & 0x0F)), vol)
                if queue:
                    self.pendvol[d] = v
                else:
                    self.pendvol[d] = 0xFF
                    self.call('controller', d, 7, v)
        for si in range(16):
            c = n.b(0x8C + si)
            if c == 0xFF:
                break
            if n.b(0x134 + c) & 2 and self.newmap[c] == 0xFF:
                v = scale_vol(n.b(0x107 + c), vol)
                if queue:
                    self.pendvol[c] = v
                else:
                    self.pendvol[c] = 0xFF
                    self.call('controller', c, 7, v)

    # ---- 1932: one tick of one sound
    def process(self, n, idx):
        r = n.res
        tag = (idx << 4) & 0xFF
        n.sw(0x154, n.w(0x154) + 1)
        for si in range(16):
            c = n.b(0x8C + si)
            if c == 0xFF:
                break
            if c == 0xFE:
                continue
            dev, fixed = 0xFF, 0
            if n.b(0x134 + c) & 2:
                dev, fixed = c, 1
            else:
                look = (c & 0x0F) | tag
                for d in range(16):
                    if self.newmap[d] == look:
                        dev = d
                        break
            pos = n.w(0x0C + 2 * si)
            if pos == 0:
                continue
            base = n.tab(si)
            dly = n.w(0x4C + 2 * si)
            if dly:
                dly = (dly - 1) & 0xFFFF
                if dly == 0x8000:
                    d = r[base + pos]
                    n.sw(0x0C + 2 * si, pos + 1)
                    dly = 0x80F0 if d == 0xF8 else d
                n.sw(0x4C + 2 * si, dly)
                continue
            self._events(n, si, c, dev, fixed, base)
        # 1b03: sound finished when every channel has ended
        for si in range(16):
            if n.b(0x8C + si) == 0xFF:
                break
            if n.w(0x0C + 2 * si):
                return
        if n.b(0x15A) == 0 and n.b(0x15D) == 0:
            self.stop(n)
            self.remap_flag = 1
            return
        n.restarts += 1
        n.sw(0x154, n.w(0x156))
        for si in range(16):
            n.sw(0x0C + 2 * si, n.w(0x2C + 2 * si))
            n.sw(0x4C + 2 * si, n.w(0x6C + 2 * si))
            n.sb(0x9C + si, n.b(0xAC + si))

    def _events(self, n, si, c, dev, fixed, base):
        r = n.res

        def rd():
            pos = n.w(0x0C + 2 * si)
            v = r[base + pos]
            n.sw(0x0C + 2 * si, pos + 1)
            return v

        while True:
            st = rd()
            if st < 0x80:
                st = n.b(0x9C + si)
                n.sw(0x0C + 2 * si, n.w(0x0C + 2 * si) - 1)
            else:
                n.sb(0x9C + si, st)
            hi, lo = st & 0xF0, st & 0x0F
            if st == 0xFC:
                n.sw(0x0C + 2 * si, 0)
                return
            if lo == 0x0F:
                self._control(n, si, hi, rd)
                if n.w(0x0C + 2 * si) == 0:
                    return
            else:
                cc = c & 0x0F
                if hi == 0x80 or hi == 0x90:
                    note, vel = rd(), rd()
                    if hi == 0x90 and vel:
                        if dev < 0x10:
                            n.sb(0x125 + cc, note)
                        if dev != 0xFF and not self.seeking:
                            self.call('note_on', dev & 0x0F, note, vel)
                    else:
                        if dev < 0x10 and n.b(0x125 + cc) == note:
                            n.sb(0x125 + cc, 0xFF)
                        if dev != 0xFF and not self.seeking:
                            self.call('note_off', dev & 0x0F, note, vel)
                elif hi == 0xA0:
                    rd(); rd()                          # fn 6: nothing on AdLib
                elif hi == 0xB0:
                    ctl, val = rd(), rd()
                    if not (fixed and self.newmap[dev & 0x0F] != 0xFF):
                        send = True
                        if ctl == 7:
                            n.sb(0x107 + cc, val)
                            val = scale_vol(val, n.b(0x15E))
                            if dev < 0x20:
                                self.pendvol[dev] = 0xFF
                            else:
                                send = False
                        elif ctl == 10:
                            n.sb(0xF8 + cc, val)
                        elif ctl == 1:
                            n.sb(0xE9 + cc, val)
                        elif ctl == 0x40:
                            w = n.w(0xBC + 2 * cc)
                            n.sw(0xBC + 2 * cc, (w | 0x8000) if val else (w & 0x7FFF))
                        elif ctl == 0x4B:
                            n.sb(0xDA + cc, (n.b(0xDA + cc) & 0xF0) | val)
                            self.remap_flag = 1
                        elif ctl == 0x4E:
                            n.sb(0x143 + cc, (n.b(0x143 + cc) & 0xF0) | (1 if val else 0))
                            self.remap_flag = 1
                        if send and dev < 0xFF and not self.seeking:
                            self.call('controller', dev & 0x0F, ctl, val)
                elif hi == 0xC0:
                    pr = rd()
                    if not (fixed and self.newmap[dev & 0x0F] != 0xFF):
                        n.sb(0x116 + cc, pr)
                        if dev < 0xFF and not self.seeking:
                            self.call('program', dev & 0x0F, pr)
                elif hi == 0xD0:
                    rd()                                # fn 9: nothing on AdLib
                elif hi == 0xE0:
                    lsb, msb = rd(), rd()
                    if not (fixed and self.newmap[dev & 0x0F] != 0xFF):
                        w = (msb << 7 | lsb) | (n.w(0xBC + 2 * cc) & 0x8000)
                        n.sw(0xBC + 2 * cc, w)
                        if dev < 0xFF and not self.seeking:
                            self.call('pitch_bend', dev & 0x0F, lsb, msb)
                elif hi == 0xF0:
                    while rd() != 0xF7:
                        pass
                else:
                    n.sw(0x0C + 2 * si, 0)
                    return
            d = rd()
            if d == 0:
                continue
            n.sw(0x4C + 2 * si, 0x80EF if d == 0xF8 else d - 1)
            return

    def _control(self, n, si, hi, rd):      # 1e66: status nibble F (control channel)
        if hi == 0xC0:
            v = rd()
            if v == 0x7F:                   # loop point
                d = rd()
                n.sw(0x4C + 2 * si, 0x80F0 if d == 0xF8 else d)
                n.sb(0x9C + si, 0xCF)
                for i in range(16):
                    n.sw(0x2C + 2 * i, n.w(0x0C + 2 * i))
                    n.sw(0x6C + 2 * i, n.w(0x4C + 2 * i))
                    n.sb(0xAC + i, n.b(0x9C + i))
                n.sw(0x156, n.w(0x154))
                n.sw(0x0C + 2 * si, n.w(0x0C + 2 * si) - 1)
                n.sw(0x4C + 2 * si, 0)
            elif not self.seeking:
                n.sb(0x158, v)              # signal to the game
        elif hi == 0xB0:
            ctl, val = rd(), rd()
            if ctl == 0x50:
                if val == 0x7F:
                    val = self.default_reverb
                n.sb(0x15F, val)
                self.call('reverb', val)
            elif ctl == 0x60:
                if not self.seeking:
                    n.sw(0x152, n.w(0x152) + 1)
            elif ctl == 0x52:
                if n.b(0x15A) == val:
                    for i in range(16):
                        n.sw(0x0C + 2 * i, 0)
        elif hi == 0xF0:
            while rd() != 0xF7:
                pass
        else:
            if hi not in (0xC0, 0xD0):
                rd()
            rd()


# ---------------------------------------------------------------- DRO

def write_dro(path, writes, total_ms):
    """writes = [(ms, reg, val)] -> DOSBox raw OPL v2.0 (OPL2)."""
    regs = sorted({r for _, r, _ in writes})
    code = {r: i for i, r in enumerate(regs)}
    sdc, ldc = len(regs), len(regs) + 1
    pairs = bytearray()
    done = 0

    def delay(ms):
        while ms > 0:
            if ms > 256:
                k = min(ms // 256, 256)
                pairs.extend((ldc, k - 1))
                ms -= k * 256
            else:
                pairs.extend((sdc, ms - 1))
                ms = 0
    for t, r, v in writes:
        t = int(round(t))
        if t > done:
            delay(t - done)
            done = t
        pairs.extend((code[r], v))
    end = int(round(total_ms))
    if end > done:
        delay(end - done)
        done = end
    hdr = (b'DBRAWOPL' + struct.pack('<HHII', 2, 0, len(pairs) // 2, done)
           + bytes((0, 0, 0, sdc, ldc, len(regs))) + bytes(regs))
    with open(path, 'wb') as f:
        f.write(hdr + pairs)


def render(rec, ovl, passes=2, max_s=300.0, tail_s=1.5, min_loop_s=8.0):
    """-> (writes [(ms, reg, val)], length ms, driver-call log, info dict)"""
    writes = []
    clock = [0.0]
    drv = AdlibDriver(ovl['ADL'], lambda r, v: writes.append((clock[0], r, v)))
    patch = ovl['003']
    patch = patch[2 + patch[1]:]            # SCI patch file: 89h, header length, description
    log = []
    seq = Sequencer(drv, patch, log)
    node = Node(rec.data[2:], rec.prio, 1 if rec.loop else 0)
    # INTRO/PS start SX sounds with play(node, 1) (1708:0008: every channel 'locked' to its own
    # number), AP starts SNG sounds with play(node, 0) (AP 3280:0a44)
    seq.play(node, 0 if rec.bank.startswith('SIM') else 1)
    ticks = 0
    max_ticks = int(max_s / TICK_S)
    stopped_by = 'end'
    while node in seq.list:
        ticks += 1
        clock[0] = ticks * TICK_MS
        seq.service()
        if node.restarts >= passes and ticks * TICK_S >= min_loop_s:
            stopped_by = 'passes'
            break
        if ticks >= max_ticks:
            stopped_by = 'cap'
            break
    if node in seq.list:
        seq.stop_and_remap(node)
    for _ in range(int(tail_s / TICK_S)):
        ticks += 1
        clock[0] = ticks * TICK_MS
        seq.service()
    info = {'ticks': ticks, 'stop': stopped_by, 'restarts': node.restarts,
            'notes': sum(1 for _, f, a in log if f == 'note_on' and a[2]),
            'writes': len(writes), 'dropped': drv.dropped}
    return writes, ticks * TICK_MS, log, info


# ---------------------------------------------------------------- commands

def all_recs():
    for key in BANKS:
        for rec in load_bank(key):
            yield rec


def cmd_list(out=None):
    lines = ['bank  idx    id  name       prio flags  bytes  loop  tracks (device:channels; /n = header flags)']
    for key in BANKS:
        for rec in load_bank(key):
            prio, s = summary(rec)
            lines.append('%-5s %3d %5d  %-10s %4d  %04x %6d  %-4s  %s%s' % (
                key, rec.index, rec.id, rec.name or '-', rec.prio, rec.flags, len(rec.data),
                'yes' if rec.loop else '', s, '' if prio is None else '  (F0 prio %d)' % prio))
    txt = '\n'.join(lines)
    if out:
        with open(out, 'w') as f:
            f.write(txt + '\n')
    print(txt)


def cmd_extract():
    os.makedirs(OUT, exist_ok=True)
    for key in BANKS:
        d = os.path.join(OUT, key)
        os.makedirs(d, exist_ok=True)
        for rec in load_bank(key):
            with open(os.path.join(d, rec.fname + '.snd'), 'wb') as f:
                f.write(rec.data)
    for vol, name in OVLS:
        d = os.path.join(OUT, os.path.splitext(name)[0])
        os.makedirs(d, exist_ok=True)
        for tag, data in load_ovl(vol, name).items():
            fn = 'PATCH.' + tag if tag[0].isdigit() else tag + '.DRV'
            with open(os.path.join(d, fn), 'wb') as f:
                f.write(data)
    cmd_list(os.path.join(OUT, 'index.txt'))


def find_rec(key, sid):
    for rec in load_bank(key.upper()):
        if rec.id == sid:
            return rec
    raise SystemExit('%s: no sound %d' % (key, sid))


def dump_text(rec):
    res = rec.data[2:]
    prio, trk = tracks(res)
    o = ['%s %d %s  (%s)  prio %d flags %04x loop %s, %d bytes' % (
        rec.bank, rec.id, rec.name, rec.src or '-', rec.prio, rec.flags, rec.loop, len(rec.data))]
    if prio is not None:
        o.append('F0 header: priority %d' % prio)
    for dev, chans in trk:
        o.append('track %02X (%s): %d channels' % (dev, DEVICES.get(dev, '?'), len(chans)))
        for a, off, size in chans:
            c = res[off]
            if c == 0xFE:
                rate, sz, s0, s1 = struct.unpack_from('<HHHH', res, off + 2)
                o.append('  %04x %5d  digital: rate %d, size %d, loop %d-%d' % (off, size, rate, sz, s0, s1))
                continue
            o.append('  %04x %5d  channel %d flags %X voices %d prio %d | prog %d vol %d pan %d' % (
                off, size, c & 15, c >> 4, res[off + 1] & 15, res[off + 1] >> 4,
                res[off + 4], res[off + 8], res[off + 0x0B]))
    # events of the AdLib track
    for dev, chans in trk:
        if dev != 0:
            continue
        for a, off, size in chans:
            if res[off] == 0xFE:
                continue
            hdr, ev, end = channel_events(res, off, size)
            o.append('')
            o.append('channel %d (offset %04x): %d events, %d ticks = %.1f s' % (
                hdr[0] & 15, off, len(ev), end, end * TICK_S))
            for t, p, st, db in ev:
                o.append('  %6d %7.2fs %04x  %02X %-9s %s' % (t, t * TICK_S, p, st, db.hex(' '), describe(st, db)))
    return '\n'.join(o)


def cmd_dro(keys=None, ids=None, passes=2, max_s=300.0, tail_s=1.5):
    ovls = {}
    rows = []
    for key in keys or list(BANKS):
        ov = BANKS[key][2:]
        if ov not in ovls:
            ovls[ov] = load_ovl(*ov)
        d = os.path.join(OUT, key)
        os.makedirs(d, exist_ok=True)
        for rec in load_bank(key):
            if ids and rec.id not in ids:
                continue
            writes, ms, log, info = render(rec, ovls[ov], passes, max_s, tail_s)
            base = os.path.join(d, rec.fname)
            write_dro(base + '.dro', writes, ms)
            with open(base + '.txt', 'w') as f:
                f.write(dump_text(rec) + '\n\ndriver calls (tick, function, args):\n')
                for t, fn, a in log:
                    if fn == 'service':
                        continue
                    f.write('%6d %-12s %s\n' % (t, fn, ' '.join('%d' % x for x in a)))
            rows.append('%-5s %5d %-10s %7.1fs %-6s notes %5d  dropped %4d  writes %6d' % (
                key, rec.id, rec.name or '-', ms / 1000, info['stop'], info['notes'], info['dropped'],
                info['writes']))
            print(rows[-1])
    return rows


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return

    def opt(name, default):
        if name in a:
            i = a.index(name)
            v = float(a[i + 1])
            del a[i:i + 2]
            return v
        return default
    passes = int(opt('--passes', 2))
    max_s = opt('--max', 300.0)
    tail_s = opt('--tail', 1.5)
    cmd = a[0]
    if cmd == 'list':
        cmd_list()
    elif cmd == 'extract':
        cmd_extract()
    elif cmd == 'dump':
        print(dump_text(find_rec(a[1], int(a[2]))))
    elif cmd == 'dro':
        keys = [a[1].upper()] if len(a) > 1 else None
        ids = [int(x) for x in a[2:]] or None
        cmd_dro(keys, ids, passes, max_s, tail_s)
    elif cmd == 'all':
        cmd_extract()
        rows = cmd_dro(None, None, passes, max_s, tail_s)
        with open(os.path.join(OUT, 'render.txt'), 'w') as f:
            f.write('\n'.join(rows) + '\n')
    else:
        print(__doc__)


if __name__ == '__main__':
    main()
