# sim_flow part: VCR — film recording and playback (AP.EXE)

**Status: complete (2026-09-26).** Part of `sim_flow` (lead file `sim_flow.md`). Target `work/AP_flat.exe`,
DGROUP `3EA4`. Owner of segments `1c0f 5b93 5c5f 5c9b 5d3c 5d46 5d56 5dd0 5e06 5ea5 5fef 606e 6163 618d
48c7 63ed 4d15 6922 6de4 6a63 51e7 36ee 5155 4bcd`. Symbols: `...\scratchpad\sf\parts\vcr_symbols.csv`.
Scratch tools (Python, reproducible): `...\sf\parts\vcr\huf.py` (Huffman tables), `vcrdump.py` (film
decoder), `strpool.py` (STR_POOL text lookup).

Confidence tags: **verified** (read in the disassembly and, where marked, confirmed by decoding the four
demo films), **likely**, **guess**.

## Index

1. Overview — what a film is, how playback works
2. Film file format `TAPES/*.VCR` (settled, verified on all four demos)
3. Bit stream (`63ed`, `48c7`) and Huffman coding (`4d15`, `6922`, `6de4`, `618d:0768`)
4. Frame record codec (`6a63`) — the event stream
5. Tape file layer (`618d` vcr_tape.c)
6. Session driver `5c9b:0000` (vcr3.c) and vcr2.c (`5c5f`) — full state machine
7. Recording inside the flight loop (what the lead's `5cde:0405` does for the VCR)
8. VCR runtime (`5b93`): playback step, rewind, views, UI modes
9. VCR UI modes: play / pause / step / FF / seek / full screen (`5b93`, `6163`, `5dd0`, `1c0f`, `51e7`, `5d46`, `5d3c`)
10. VCR panel drawing (`5ea5` vcr_gfx.c), helpers `606e` (rlsmgfx.c)
11. Tape files, dialogs and list box (`5e06` vcr_file.c, `5fef` vcr_list.c, `5155` modules.c, `4bcd` findfile.c, `36ee`)
12. Demo mode `-d` (`5d56` vcr_demo.c)
13. Determinism: what the port must reproduce (RNG, dt, ticks, frame pacing)
14. Data: globals and structures
15. Port notes
16. Hand-offs
17. Open questions

---

## 1. Overview

**A film is a recording of the player's inputs, not of object states.** Per simulated frame the
recorder writes the 20-byte *control record* that the control mapping `5f2c:05d1` produced for the sim
step (stick, rudder, throttle, buttons, command code, frame tick count), optionally an 8-byte *view
record* (camera key / pan), and occasional *data blocks* (realism settings, the prefs slider, map
changes). Playback re-runs the whole mission: the mission script embedded in the film is loaded,
the world is initialised exactly as for flying (`4e0d:03e9`, which re-seeds both RNGs from a constant
table), and every frame the recorded control record is fed to the same sim step `5440:1317`, with the
frame time `dt` re-derived from the recorded tick count (`362b:008f(ticks*4)`). Nothing about object
positions is stored (**verified**: the frame codec `6a63` only knows the three record kinds of §4; the
four demos decode completely, 692–1014 control frames each, and the stream ends exactly at the file
end).

Consequences (§13): playback is only correct if the port's sim is bit-exact deterministic with respect
to (mission script, SIM.IN/realism/prefs, recorded controls, recorded ticks). Seeking backwards is done
by re-initialising the world and re-simulating from frame 0 (`5b93:0528`); seeking forward just
simulates frames without drawing (`5dd0`).

Every flight in single / career mode is recorded ("Mission Recorder": `TAPES\_TAPE_.TMP`), and after
the mission the player is offered *SAVE THE MISSION TO TAPE / REPLAY THIS MISSION / END MISSION*
(§6). The `-w` sim mode (SIM.IN+1 = 2) opens the VCR on a chosen tape; `-d` (mode 3) loops the
`TAPES\DEMO*.VCR` films with a title screen. From the VCR the player can *Enter Simulation*: the world
continues from the current playback frame under live control, and (in *director mode*) the recording
continues into a new temp tape.

---

## 2. Film file format `TAPES/*.VCR`  (verified)

The whole file is one LSB-first bit stream (§3.1) written by `618d:0430`; because the first fields are
whole bytes it can also be read with plain byte I/O (`618d:011f`, `5155:00fa` do so).

| Off | Size | Contents | Written by |
|---|---|---|---|
| 000 | 66 | header (§2.1) | `618d:0430`, patched by `618d:0502` |
| 042 | 364 | module block (§2.2) — zero in all four demos | zeros at `0430`, filled by `0502` |
| 1AE | 2 | u16 `n` = mission script length | `0430` (DS:5014) |
| 1B0 | n | mission script bytes (the SCRIPT.DAT image, data.md §2 format), fed to `4e0d:038e(ptr, n)` | `0430` (DS:5010) |
| 1B0+n | … | event stream: Huffman/bit coded records (§4), terminated by an END record, then zero padding to the byte boundary | `6a63:04d0` |

The event stream starts at bit `(0x1B0 + n) * 8` — records are **not** byte aligned.

### 2.1 Header (66 bytes; DS:504A while recording, DS:508C after reading)

| Off | Type | Meaning | Value in demos |
|---|---|---|---|
| +00 | u16 | flags: bit 0 = film complete (set by the finaliser `618d:0502`; `618d:011f`/`0653` refuse a film without it: fatal `vcr_tape.c` line DCh/21Fh) | 0001 |
| +02 | u16 | format version, written as **12h**; `5155:00fa` returns it and `5155:0207` marks every tape with version != 12h as unusable (`*` prefix) | 0012 |
| +04 | s16 | prefs slider 0 value (`5613:0161(0)`, restored with `5613:01e9(0,v)` + `4b9f:0000` apply) — Likely the time-scale slider (the one recorded again as data block subtype 1 after the in-flight prefs dialog) | 50 |
| +06 | 16 bytes | copy of DS:42C8..42D7 (realism settings, see `606e:0137`); restored to DS:42C8 on playback | `01 01 01 01 01 01 00 01 00 01 02 02 00 00 00 00` (DEMODS) |
| +16 | u32 | number of control frames in the film (DS:5060 ← DS:0887 or DS:50A2) | 841 / 1014 / 783 / 692 |
| +1A | s32 | mission clock at the end (DS:5064 ← `4ca7:0045()`) | 113 / 61 / 119 / 62 |
| +1E | 6 bytes | DS:5068..506D, never written by any code (zero) | 0 |
| +24 | 13 bytes | copy of SIM.IN (data.md §1) of the flight (DS:506E ← DS:4E2E or DS:4E21) | e.g. `ff 00 05 03 28 00 06 00 02 00 04 00 00` |
| +31 | 17 bytes | DS:507B..508B, never written (zero) | 0 |

Header +2B (= SIM.IN+7, the add-on module mask): bit 0 → DS:51EC on playback (`618d:0653`), the same
flag `5c5f:0000` derives from the real SIM.IN (read by AI code through `6a63:0000`).

### 2.2 Module block (364 bytes)

Built at finalisation by `5155:0000(block, mask)` with `mask = header[+2B] | 618d:04e4(0)` (the
SIM.IN module mask ORed with the accumulated DS:0BDC bits): the block is zeroed, byte +168h = mask
(low byte), and for each set bit *k* (k = 0..8) the first 40 bytes of `M<k+1>SHL.DYN` (the add-on's
identification record) are copied to `+40·k`. `5155:03a4` uses it to explain which add-ons a tape
needs ("This tape was created using expansion…"). All four demos: zero (no add-ons).

### 2.3 Decoding the demos (verified)

`vcrdump.py` (scratch) decodes all four demos end to end:

| Film | bytes | script | control frames | view records | END at bit / file bits | ticks range (×4 PIT) |
|---|---|---|---|---|---|---|
| DEMOAG | 4133 | 216 | 841 | 912 | 33057 / 33064 | 5..24 |
| DEMODS | 3985 | 527 | 1014 | 517 | 31875 / 31880 | 3..25 |
| DEMOFLAK | 2899 | 1031 | 783 | 257 | 23185 / 23192 | 5..32 |
| DEMOPAP | 3829 | 444 | 692 | 581 | 30625 / 30632 | 4..21 |

The control-frame count equals header +16 in every film and the END record ends in the last byte.
First frames of DEMOAG: frame 1 = `{flags 10h, throttle absolute 60, ticks 24}`, frames 2.. =
`{flags 0, ticks 8, 5, 5, …}`, frame 18 is followed by a view record `{VIEW flags 2, key 37}`, frame 22
carries command code 10. DEMODS starts with 25 view records *before* its first control frame (view
edits made at frame 0 in director mode). No film contains data blocks (types 2/3).
`Game/TAPES/_TAPE_.TMP` is 0 bytes: the temp tape of a flight whose recording was never finalised (§6,
END MISSION path).

---

## 3. Bit stream and Huffman coding

### 3.1 Bit order (verified)

Both the bit writer `63ed:0000` and reader `63ed:00e7` use the mask table DS:0C7A = `01 02 04 08 10 20
40 80`: stream bit *p* is bit `p & 7` of byte `p >> 3` (LSB first), and an *n*-bit field is transferred
from/to the value's memory bit by bit starting at bit 0 of its first byte. So an n-bit field is the
value's low n bits, least significant bit first; multi-byte values are little-endian. A reader
clears/sets only the n destination bits (`or`/`and` per bit), so callers zero the destination first
where it matters.

### 3.2 `63ed` bstream.c — bit I/O on a stream struct

Stream struct `BSTREAM` (0x3B bytes, table of 2 at DS:3CDA, found by `48c7:0190`):

| Off | Type | Meaning |
|---|---|---|
| +00 | u16 | mode: 1 = read, 2 = write, 4 = in use |
| +02 | far ptr | bit buffer (caller supplied: DS:5030 read / DS:5038 write, 200 bytes = DS:0BD6) |
| +06 | u32 | buffer size in bytes |
| +0A | u32 | bit position in the buffer |
| +0E | u32 | bit limit (write: size·8; read: number of valid bits) |
| +12 | FILE* | temporary handle |
| +14 | char[25] | file name (relative; opened as DS:4032 work dir + name) |
| +2D | u32 | read: file offset of the next cache fill |
| +31 | u16 | EMS handle of the 16000-byte cache (size DS:0100 = 3E80h for reads, DS:0C78 = 3E80h for writes) |
| +33 | u16 | bytes used in the cache |
| +35 | u32 | read: bytes delivered by the last fill |
| +39 | u16 | read: number of cache fills (0 → rewind needs no reload) |

| Addr | Name | Behaviour |
|---|---|---|
| `63ed:0000` | `bs_write_bits(void *src, int nbits, BSTREAM *s)` → 1/0 | while nbits > 0: avail = limit − pos; if 0 → `bs_flush(s, 0)` (0 → return 0); k = min(nbits, avail); nbits −= k; copy k bits (src bit i → buffer bit pos, pos++). Returns 1. |
| `63ed:00e7` | `bs_read_bits(void *dst, int nbits, BSTREAM *s)` → bits read | same with `bs_refill` (`04f8`); if it returns 0 → return the number of bits read so far (**end of data returns short; the destination keeps its old bits**). |
| `63ed:0395` | `bs_flush(s, final)` → 1 | bytes = pos>>3; remember the partial byte `buf[bytes]` if pos&7; `63ed:02b1(buf, bytes, s, final)`; pos &= 7; partial byte moved to `buf[0]`. |
| `63ed:02b1` | `bs_cache_put(far src, n, s, final)` | append n bytes to the EMS cache; when it is full (DS:0C78 bytes) write the cache to the file (`01c3`) and continue; if `final` also write the remaining cache. Fatal via `2494:00a9` on a write error. |
| `63ed:01c3` | `bs_file_append(s, far buf, n)` → ok | fopen(DS:4032+name, "ab" DS:0C82), fputc n bytes, fclose; fatal "bstream.c" 19Bh if the open fails. |
| `63ed:04f8` | `bs_refill(s)` → valid bits after refill | `0570` compact; then `0405(buf + (limit>>3), size − (limit>>3), s)` bytes; limit += got·8; returns limit − pos. |
| `63ed:0570` | `bs_compact(s)` | move the unread bytes `[pos>>3, limit>>3)` to the buffer start; pos &= 7; limit −= (pos_bytes·8). |
| `63ed:0405` | `bs_cache_get(far dst, n, s)` → bytes | copy from the EMS cache; when exhausted `48c7:0000` refills it from the file (offset +2D). Returns bytes copied (0 at end of file). |

### 3.3 `48c7` bstream.c — open / close

| Addr | Name | Behaviour |
|---|---|---|
| `48c7:0190` | `bs_open(char *name, u16 mode, far buf, u32 size)` → BSTREAM* / 0 | find a free slot among the 2 at DS:3CDA (mode bit 2 clear), zero its 0x3B bytes, copy the name to +14. mode&1 (read): fopen(name,"rb") [mode 3 returns early, unused]; else fopen(name,"wb") (truncates; fatal if it fails). Close the handle, +2D = 0, allocate the EMS cache (`24e5:0000(DS:0100)`; fatal "bstream.c" 8Ch), +33 = 0, read mode: first cache fill `0127`. +06 = size, +02 = buf, +00 = mode\|4, write mode: +0E = size·8. |
| `48c7:0000` | `bs_file_fill(s, far cache)` | fopen(DS:4032+name "rb", else name "rb"; fatal 3Ch), fseek(+2D), fgetc up to DS:0100 bytes into the cache, +35 = count, +2D += count, +39++, fclose. |
| `48c7:0127` | `bs_fill_cache(s)` | map the EMS page, `0000`, +39 = 0 (sic: reset after the fill), unmap. |
| `48c7:02dd` | `bs_close(s)` → ok | write mode: round pos up to a byte, `bs_flush(s, 1)` (fatal on error); mode = 0; free the EMS handle. |
| `48c7:0329` | `bs_rewind(s)` | +2D = +0A = +0E = 0, +33 = 0; if +39 != 0 refill the cache (`0127`). |
| `48c7:035e` | `bs_abort(s)` → 1 | mode = 0, free EMS (nothing flushed). |
| `48c7:0161` | debug `fprintf("c:\\aotp.txt","%s")` | no callers — not ported. |

`PORT:` the whole EMS/200-byte-buffer machinery is replaced by a plain buffered file reader/writer
with the same bit semantics (§15).

### 3.4 Huffman tables `.HUF` (verified)

Eight tables are loaded once per session by `618d:07b3` (`618d:0768(name)` = `4d15:0036(55a4:0000(name,
"HUF"))`, fatal "vcr_tape.c" 298h on failure), from SIM2 (`work/dyn/SIM2/*.HUF`):

| Table | ptr | n | symbols | used for |
|---|---|---|---|---|
| RUD | DS:5000 | 32 | −16..15 | control +04 rudder |
| PAN | DS:5002 | 16 | −8..7 | view +04, +06 |
| VIEW | DS:5004 | 8 | 0..7 | view record flags |
| JOY | DS:5006 | 64 | −32..31 | control +00, +02 stick |
| TICKS | DS:5008 | 128 | 0..127 | control +12 XOR previous |
| BTN | DS:500A | 15 | 1..15 | control +0E buttons |
| SIM | DS:500C | 32 | 0..31 | control record flags |
| SOUT | DS:500E | 5 | 0..4 | record type |

File: `s16 n` (1 < n ≤ 800h), then n × (`u16 symbol`, `u32 frequency`) — all eight files list the
symbols in ascending order.

Table object (near, `4d15:01ca(n)`, size `((n+6)>>3) + 10h`):

| Off | Type | Meaning |
|---|---|---|
| +00 | s16 | n (leaf capacity) |
| +02 | s16 | m, number of distinct symbols inserted |
| +04 | s32 | total frequency |
| +08 | near ptr | code bit buffer (= object + 10h) |
| +0A | u16 | memory handle of the node array (`1d32:22f4`, locked by `1d32:2571`, unlocked `25a5`) |
| +0C | far ptr | root node = node[2n−2] |
| +10 | bytes | code bit buffer, (n+6)>>3 bytes |

Node (10 bytes, array of 2n−1, zeroed at creation): `+0 s32 freq`, `+4 u16 parent` (0 = none / not yet
merged), `+6 s16` leaf: symbol / internal: child 0, `+8 s16` leaf: code length / internal: child 1.
Leaves occupy nodes 0..n−1 sorted by signed symbol, internal nodes n..2n−2.

`4d15:0036 huff_load(path)` → table / 0: fopen "rb" (DS:0314); read n; `01ca(n)`; for each of the n
entries read sym, freq and `02f6(tab, sym, freq)`; stop at a short read or a 0 return; close; if fewer
than n entries were added → `02d8` free, return 0; else `03e4` build.

`4d15:02f6 huff_add(tab, s16 sym, s32 freq)` → 1/0: 0 if freq < 1 or total + freq > 7FFFFFFEh;
`6de4:0000(tab, sym, &i)`; if not found: 0 if m == n; move leaves i..m−1 up by one node (10-byte copies
from the top down), m++. Then total += freq, **leaf[i].freq += freq** (quirk: an inserted slot keeps the
displaced leaf's old frequency and adds to it — harmless for the shipped, ascending files), leaf[i].sym =
sym.

`6de4:0000 huff_find(tab, sym, int *idx)` → found: if m == 0 → *idx = 0, 0. Else i = first index in
0..m−1 with `sym <= leaf[i].sym` (signed; i = m if none); *idx = i; found = i < m && leaf[i].sym == sym.

`4d15:03e4 huff_build(tab)` — exact algorithm (tie-breaking matters for the codes):
```
for i in 0..n-1: node[i].parent = 0
k = n
repeat n-1 times:
    m1 = m2 = 0x7FFFFFFF; c = d = -1
    for i in 0..k-1:
        if node[i].parent != 0: continue
        f = node[i].freq
        if f < m1:   d = c; m2 = m1; c = i; m1 = f      (signed compares)
        elif f < m2: d = i; m2 = f
    if m1 == m2 and node[c].w6 > node[d].w6: swap(c, d)   (w6 = symbol or child-0 index, signed)
    node[d].parent = k; node[c].parent = k
    node[k] = {freq: m1+m2, parent: 0, w6: c, w8: d}; k++
for i in 0..n-1: node[i].w8 = depth(i)  (4d15:0000: steps from i to the root 2n-2)
```
`4d15:0112` writes a table back to a file (n, then sym/freq per leaf) — no callers (tool leftover).
`4d15:02d8` frees a table.

**Code of a symbol** (`6922:0000(tab, sym, int *nbits)` → bit buffer): find the leaf; clear
(n+6)>>3 bytes of the buffer; L = leaf depth, *nbits = L; walk up from the leaf: for each step
`L--`, and if the node is its parent's child 1 (`w8`) set bit L of the buffer. So bit 0 of the code =
the decision at the root, 1 = child 1. Written with `63ed:0000(buf, L)` — root decision first. Symbol
not in the table → *nbits = 0, returns 0, and the caller `6a63:0046` reports failure (nothing
written).

**Decoding** (`6a63:0008` with `6922:00dd/0105/0155`): `00dd(tab)` stores DS:51A8 = tab, DS:51A0 =
locked node base, DS:51A4 = root; then repeat { read 1 bit b (into a zeroed word); `0105(b)`: child =
node(51A4).word[+6 + 2b]; if child < n: DS:519E = node[child].sym, return 1; else 51A4 = &node[child],
return 0 }; `0155` unlocks and returns DS:519E. At end of data the bit reads 0 (the word stays 0).

Example codes (verified with `huf.py`): SOUT 0 = `1`, 1 = `01`, 4 = `001`, 2 = `0000`, 3 = `0001`;
VIEW 0 = `1`, 5 = `01`, 4 = `001`; BTN 2 = `1`, 4 = `00`; RUD all 5 bits. Code lengths: JOY 2–10,
TICKS 1–10, SIM 1–9, PAN 2–7, BTN 1–7.

---

## 4. Frame record codec `6a63` (the event stream)

Every record starts with a SOUT-coded **type**. Writer `6a63:04d0(type, ptr)`, reader
`6a63:05aa(u16 *sub, u16 *len)`.

| Type | Record | Writer | Reader result |
|---|---|---|---|
| 0 | control record (20 bytes) | `04d0(0, rec)` → `0256` | decoded into DS:5044, DS:5048 = 14h |
| 1 | view record (8 bytes) | `04d0(1, rec)` → `00a5` | decoded into DS:5044, DS:5048 = 8 |
| 2 | data block: u16 subtype, u16 len, len bytes | `0515(sub, len, ptr)` | *sub, *len, bytes into DS:5044, DS:5048 = len |
| 3 | nothing (never written) | — | DS:5048 unchanged |
| 4 | END of film | `04d0(4, …)` | DS:5048 = 0 |

`6a63:04d0 vcr_put(type, ptr)` → ok: writes SOUT(type) via `0046`; then type 0 → `0256(ptr)`, 1 →
`00a5(ptr)`, other (4) → nothing. Returns the AND of all write results.
`6a63:0515 vcr_put_data(sub, len, ptr)` → ok: SOUT(2) (`04a3(2)`), 16 bits sub, 16 bits len, then len ×
8 bits from ptr (stops at the first failed write).
`6a63:05aa vcr_get(u16 *sub, u16 *len)` → type: type = `04b8()` (SOUT decode); 0 → DS:5048 = 14h,
`036b(DS:5044)`; 1 → DS:5048 = 8, `015a(DS:5044)`; 2 → 16 bits → *sub, 16 bits → *len, DS:5048 = *len,
len·8 bits → DS:5044 (buffer allocated by `618d:02c4(10h)`: max(size, 14h) = 20 bytes, DS:5046 = 20 —
**a data block longer than 20 bytes would overflow it**; the game writes 2, 12 or 16); 4 → DS:5048 =
0; 3 → nothing. Returns the type (types > 4 fall through unchanged).
`6a63:0576 vcr_take(dst, len)` → 1/0: copies DS:5048 bytes from DS:5044 to dst only if `len ==
DS:5048` and `len <= DS:5046`.
`6a63:0046 huff_put(tab, sym)` → ok (0 if the symbol is not in the table). `6a63:0008 huff_get(tab)` →
symbol. `6a63:0084 sext(v, bits)`: if bit (bits−1) of v is set, OR in all higher bits.
`6a63:0000` returns DS:51EC (add-on flag, see §2.1).

### 4.1 Control record (20 bytes, `CTRL`) — encoder `6a63:0256`, decoder `6a63:036b` (verified)

Field meaning from the codec (names from the lead's control mapping `5f2c:05d1`; **likely**):

| Off | Type | Meaning | Coding |
|---|---|---|---|
| +00 | s16 | stick x, −32..31 | JOY if flag bit 0 |
| +02 | s16 | stick y, −32..31 | JOY if flag bit 0 |
| +04 | s16 | rudder, −16..15 | RUD if flag bit 3 |
| +06 | s16 | — | **not recorded** (decoder leaves 0) |
| +08 | s8 | throttle absolute 0..127, −1 = none | flag bit 4 |
| +09 | s8 | throttle step (±1..±8), 0 = none | flag bit 4 |
| +0A | s16 ×2 | — | **not recorded** (0) |
| +0E | s16 | button bits 1..15 | BTN if flag bit 2 |
| +10 | s16 | command code 0..127 | 7 raw bits if flag bit 1 |
| +12 | s16 | frame ticks = elapsed PIT ticks >> 2 (0..127) | TICKS(ticks XOR previous), always |

Encoder `0256(rec)`:
```
t = rec[+12] XOR DS:5042 ; DS:5042 = rec[+12]          (DS:5042 = 0Fh at 618d:0430)
f = 0
if rec[+0] or rec[+2]:            f |= 1
if rec[+10]:                      f |= 2
if rec[+0E]:                      f |= 4
if rec[+4]:                       f |= 8
if (s8)rec[+8] >= 0 or rec[+9]:   f |= 16
put SIM(f)
if f&1:  put JOY(rec[+0]); put JOY(rec[+2])
if f&2:  put 7 bits of rec[+10]          (bitlen(7Fh)+1 via 277a:3ec8 = floor(log2))
if f&4:  put BTN(rec[+0E])
put TICKS(t)                              (always)
if f&8:  put RUD(rec[+4])
if f&16: 6a63:01df(rec):
           b = ((s8)rec[+8] >= 0); put 1 bit b
           if b: put 7 bits of rec[+8]           (bitlen(40h)+1)
           else: v = (s8)rec[+9]; if v > 0: v--; put 4 bits of v
```
Decoder `036b(rec)`: zero 20 bytes; rec[+8] = FFh; f = SIM; bit 0 → +0, +2 = JOY; bit 1 → 7 bits into
+10; bit 2 → +0E = BTN; t = TICKS, `rec[+12] = t XOR DS:5040; DS:5040 = rec[+12]` (DS:5040 = 0Fh at
`618d:0653`); bit 3 → +4 = RUD; bit 4 → b = 1 bit; b: 7 bits into the byte +8 (so +8 = 0..127, +9 = 0);
else: v = sext(4 bits, 4); rec[+9] = v + (v >= 0 ? 1 : 0) (−8..−1, 1..8).

Symbols outside a table (e.g. a stick value outside −32..31, ticks ≥ 128) cannot be encoded: `0046`
returns 0 and the record is silently corrupted/short (the results are only ANDed, never checked by
the flight loop). The control mapping must therefore keep stick in −32..31, rudder in −16..15, button
bits in 1..15, and ticks < 128 (the flight loop's elapsed ticks >> 2; a frame longer than 511 PIT
ticks cannot be recorded — the loop's countdown starts at 1FFh).

### 4.2 View record (8 bytes, `VIEWREC`) — encoder `6a63:00a5`, decoder `6a63:015a` (verified)

| Off | Type | Meaning (from `5f2c:08fd` / presets DS:08D8; likely) | Coding |
|---|---|---|---|
| +00 | u16 | view key / command code (1Ch..2Bh seen) | 6 raw bits (bitlen(2Bh)+1) if flag bit 1 |
| +02 | u16 | pan mode (2 or 3 in the presets) | 2 raw bits if flag bit 2 |
| +04 | s16 | pan x (±7) | PAN if flag bit 0 |
| +06 | s16 | pan y | PAN if flag bit 0 |

Flags f: bit 0 = (+4 or +6 != 0), bit 1 = (+0 != 0), bit 2 = (+2 != 0); order: VIEW(f), PAN(+4),
PAN(+6), 6 bits +0, 2 bits +2. Decoder zeroes the 8 bytes first.

### 4.3 Data blocks (type 2)

| Subtype | Len | Payload | Recorded by | Applied at playback (`5b93:0231`) |
|---|---|---|---|---|
| 0 | 16 | DS:42C8 realism settings | `5cde:0080` after the in-flight realism dialog `606e:0137` changed them | copy to DS:42C8, `606e:012d` (= `522c:0162` recompute the realism score multiplier) |
| 1 | 2 | prefs slider 0 value | `5cde:0080` after the prefs dialog `6b4d:0f95` | `5613:01e9(0, v)`; `4b9f:0000` apply slider effects |
| 2 | 12 | map state for `6cdc:0de1(buf)` | `5cde:0080` when the in-flight map (fltmap.c) state changed | `6cdc:0de1(buf)` |
| 3 | 0 | — map closed | `5cde:0080` | `6cdc:0de1(NULL)` |

---

## 5. Tape file layer `618d` (vcr_tape.c)

Globals: DS:5010 far ptr + DS:5014 u16 = mission script of the current tape; DS:5016 write stream;
DS:5018 char[] its name; DS:502E read stream; DS:5030/5034 read bit buffer (far ptr, size), DS:5038/503C
write bit buffer; DS:504A header being written; DS:508C header of the tape being read (DS:50A2 = +16
frames, DS:50A6 = +1A clock, DS:50B0 = +24 SIM.IN copy).

| Addr | Name / signature | Behaviour |
|---|---|---|
| `618d:0000` | `char *tape_path_to(char *dst, char *name)` | strcpy(dst, "TAPES\\" DS:0C06); strcat(dst, name). |
| `618d:0043` | `char *tape_path(char *name)` | i = DS:0BDA & 3; DS:0BDA = i+1; return `0000(DS:4FA8 + i·16h, name)` (4 rotating 22-byte buffers). |
| `618d:0067` | `int load_script_file(char *file, far **ptr, int *len)` → 1 | open `file` (the caller passes DS:0534 → "SCRIPT.DAT"; fatal "vcr_tape.c" ABh), DS:5014 = filelength, DS:5010 = `24b2:013d(len)` far alloc, `55a4:0108` read all, close; *ptr, *len. |
| `618d:00fb` | `int free_script(void)` → 1 | `24b2:01c0(DS:5010)`; DS:5014 = DS:5010 = 0. |
| `618d:0210` | same as `00fb` | wrapper. |
| `618d:011f` | `int tape_read_script(char *name, far **ptr, int *len)` → 1 | fopen(TAPES\name, "rb"; fatal D8h); fread 66 bytes → DS:508C; bit 0 of +00 clear → fatal DCh; fread 364 bytes (discarded); fread u16 → DS:5014; alloc; read script → DS:5010; close. |
| `618d:021c` | `int alloc_bit_buffers(void)` → ok | once: DS:5034 = DS:503C = DS:0BD6 (200); DS:5030 / DS:5038 = `24b2:013d(200)`. Returns both non-null. |
| `618d:0281` | `free_bit_buffers` | frees both, zeroes the globals — no callers. |
| `618d:02c4` | `void alloc_decode_buffer(int size)` | size ≤ 14h → 14h; DS:5046 = size; DS:5044 = near alloc (`24b2:0074`). |
| `618d:0300` | `int wopen(char *name)` | strcpy(DS:5018, name); DS:5016 = `48c7:0190(tape_path(name), 2, DS:5038, DS:503C)`. |
| `618d:0358` | `int wclose(int commit)` → ok | if DS:5016: commit ? `48c7:02dd` : `48c7:035e`; DS:5016 = 0. Returns 1 if no stream. |
| `618d:0393` | `int ropen(char *name)` | DS:502E = `48c7:0190(tape_path(name), 1, DS:5030, DS:5034)`. |
| `618d:03c8` | `void rclose(void)` | `48c7:02dd(DS:502E)`; DS:502E = 0. |
| `618d:03e5` | `int put_bytes(far p, int n, BSTREAM *s)` | n × `63ed:0000(byte, 8)`, 0 at the first failure. |
| `618d:0430` | `int rec_begin(char *name)` → ok | `wopen`; zero a 364-byte block; DS:5042 = 0Fh; header DS:504A = 0 (flags), DS:504C = 12h, DS:504E = `5613:0161(0)`, DS:5050..505F = DS:42C8..; write 210h bits from DS:504A (DS:5060..508B as they are — stale, patched later), B60h bits zeros, 10h bits DS:5014, then the DS:5010 script bytes. |
| `618d:04e4` | `u16 module_flags(u16 bits)` | bits != 0: returns DS:0BDC \| bits (**does not store**, so the OR-in by `17fe:000b`/`496a:160c` is lost — **verified** quirk); bits == 0: returns DS:0BDC and clears it. `4e0d:03e9` calls it with 0 at world init. |
| `618d:0502` | `int rec_finish(void)` → ok | `wclose(1)` (0 → return 0); fopen(TAPES\DS:5018, "r+b"); fread header (66) and block (364); rewind; header.flags \|= 1; header +16 = DS:5060, +1A = DS:5064, +24..+41 = DS:506E..508B (30 bytes); fwrite header; block = `5155:0000(block, header[+2B] \| module_flags(0))`; fwrite block; fclose. Returns 1 if both reads and writes were complete and fclose ok. |
| `618d:0629` | `int rec_abort(void)` | `wclose(0)`; unlink(TAPES\DS:5018). |
| `618d:0653` | `int play_read_header(void)` (near) | DS:5040 = 0Fh; read 210h bits header (local); DS:51EC = header[+2B] & 1; read B60h bits (block, ignored); DS:42C8..D7 = header+06..15; `5613:01e9(0, DS:5090)` — note: the slider comes from DS:508C+4, i.e. the header last read by `011f` (the same tape in all callers), not from the local copy; `4b9f:0000`; flags bit 0 clear → fatal 21Fh; read 16 bits n and skip n × 8 bits (script); copy the 66-byte header to DS:508C. |
| `618d:0726` | `int play_open(char *name)` | `ropen(name)` && `0653()`. |
| `618d:0742` | `int play_rewind(void)` → 1 | `48c7:0329(DS:502E)`; `0653()`. |
| `618d:0759` | `void play_close(void)` | `rclose()`. |
| `618d:0768` | `tab *huff_table(char *name)` | see §3.4. |
| `618d:07b3` | `void load_huff_tables(void)` | DS:500A BTN, 5006 JOY, 5002 PAN, 5000 RUD, 500C SIM, 500E SOUT, 5008 TICKS, 5004 VIEW. |
| `618d:0820` | `void vcr_tape_exit(void)` | empty. |

---

## 6. Session driver `5c9b:0000` (vcr3.c) and vcr2.c `5c5f`

### 6.1 `5c9b:0000 int vcr_session(int sim_mode)` — called from main with DS:43DC (SIM.IN+1)

Locals: `state` = DS:093C[sim_mode] (table `01 01 00 04`: mode 0 single → 1, 1 career → 1, 2 recorder
`-w` → 0, 3 demo `-d` → 4), `done` = 0, `ret` = 1, `first` = 1. Globals: DS:4010 = 0, DS:4E20 = sim_mode
(VCR mode byte; 2 = playing, see §14), DS:4E01 = 0 (review requested).

Setup: sim_mode 0/1 → `5c5f:0000` (read SIM.IN into DS:4E2E, DS:51EC). All modes: `618d:07b3` (HUF
tables), `5c5f:00bd` (panel resources), `5ea5:085b` (panel item 12Dh = 3), `618d:021c` (bit buffers;
fatal "vcr3.c" 6Fh if it fails).

```
while !done:
  switch state:
  0 CHOOSE TAPE (-w):
      name = 5c5f:00f5()                        // disk check + tape picker
      if name: 5b93:04fa(name); 5c5f:0298(name) (load film + mission, prime); state = 2
      else:    done = 1; ret = 0
  1 FLY AND RECORD (single / career):
      DS:4010 = 1
      if first: 618d:0067(DS:0534 "SCRIPT.DAT", &p, &n); 4e0d:038e(p, n) (load mission); first = 0
      if 36ee:0003(0) free bytes < 30000: alert(text 3966:0 = ids 49h–4Eh "WARNING… less than 30K…",
                                                buttons 3957:0 = [15h OK])
      DS:0886 = 1                                // record frames
      618d:0430("_tape_.tmp") (fatal B6h)        // new temp film
      4e0d:03e9()                                // world init (RNG seeds, objects, 5b93:0000, 5c5f:0083)
      5d56:0000()                                // one-time screen fade-in helper
      r = 5cde:0405()                            // FLIGHT LOOP (lead); 0 = aborted
      if r == 0: ret = 0
      DS:506E..507A = DS:4E2E (SIM.IN)           // for the film header
      saved = 0
      draw 5440:018c(DS:4090, 0); 368f:017f(2)
      6210:05e0(&text, &buf)                     // results text list (stdalert, other writer)
      loop:
        c = alert(text, buttons = 3965:(saved*2))  // [57h SAVE THE MISSION TO TAPE,] 58h REPLAY THIS MISSION, 59h END MISSION
        if c == 0: c = 2
        switch c + saved:
          1 SAVE:   if 5c5f:0165() (name chosen, film finalised and renamed): saved = 1
                    continue loop
          2 REPLAY: 5b93:0032(); 5b93:045a(); 618d:0629() (abort + delete temp film);
                    4e0d:058e() (world teardown); leave loop  → state stays 1: fly again
                    (mission script kept, first == 0)
          3 END:    5254:04f1() (write SIM.OUT); 4e0d:058e(); 4e0d:03b4() (free mission);
                    618d:00fb() (free script); done = 1; leave loop
  2 VCR:
      5d56:0000()
      r = 5b93:0bf1(4)                           // VCR UI, starting paused (mode 4)
      if r == 0: 4e0d:058e(); 4e0d:03b4(); ret = 0; done = 1     // EJECT / exit VCR
      if r == 1: state = 3                                       // ENTER SIMULATION
  3 ENTER SIMULATION (continue the played mission live):
      DS:4010 = 1
      strcpy(DS:4E58, DS:4E04)                   // remember the tape name
      DS:4E21..2D = DS:50B0..BC                  // SIM.IN copy from the film header
      DS:0886 = DS:092F                          // keep recording only in director mode
      DS:0887 = DS:4E3B                          // frame counter continues
      618d:0759()                                // close the film being played
      5b93:00f1() (hide panel); 5cde:0000(); draw; 368f:017f(2)
      r = 5cde:0405()                            // FLIGHT LOOP from the current world state
      DS:506E..507A = DS:4E21
      6210:05e0(&text, &buf); terminate text at the first 0 entry
      5b93:084e(1); alert(text, [OK])            // results
      name = 5c5f:0165()                         // offer to save (if >= 3 frames)
      if !name: 5b93:04dd() (END record + finalise the temp film; fatal 154h)
      5b93:084e(1)
      c = alert(3963:0 [5Ah "Would you like to:"], 3964:0 [5Bh SEE MISSION REVIEW, 5Ch RETURN TO VCR])
      if c == 1: DS:4E01 = 1; DS:4E22 = 0 (SIM.IN+1 of the copy := single mission);
                 5254:04f1() (SIM.OUT); 4e0d:058e(); 4e0d:03b4(); 618d:0210();
                 done = 1; if r == 0: ret = 0
      else:      if !name: name = DS:4E58 (the original tape)
                 5c5f:0242(name) (reopen it, re-simulate from frame 0); state = 2; DS:4010 = 0
  4 DEMO (-d):
      5d56:01b5() (loop over the demo films until a key); done = 1; ret = 0

618d:0820(); 5c5f:0238(); 5c5f:002a()           // SIM.IN written back if DS:4E01
return ret
```

Notes:
* **No path of `5c9b:0000` calls `sim_exit` itself**; it returns `ret` to main (lead: main's use of it).
  `ret` = 0 when no tape was chosen, the flight loop was aborted (state 1/3 with r = 0), the VCR was
  exited (state 2), or after the demo.
* SIM.OUT (`5254:04f1`) is written on END MISSION (state 1) and on SEE MISSION REVIEW (state 3). In
  state 3 SIM.IN is also rewritten from the film's copy (with +1 = 0) by `5c5f:002a`, so the shell
  reviews the played mission.
* Mission load/unload: `4e0d:038e(script, len)` = load the mission (state 1 first time; `5c5f:0298`
  for a film); `4e0d:03e9` = world init (every fly / replay / rewind / film open); `4e0d:058e` = world
  teardown; `4e0d:03b4` = free the mission (before leaving the session).
* END MISSION without saving leaves the temp film's write stream open and unfinalised (nothing flushed
  → `_TAPE_.TMP` of 0 bytes, as in the installed game) — **verified**; the port may close it (§15).
* The "30K" check uses `36ee:0003(0)` (free bytes of the work drive) < 30000 (7530h).

### 6.2 vcr2.c `5c5f`

| Addr | Name | Behaviour |
|---|---|---|
| `5c5f:0000` | `void vcr_read_simin(void)` | `519d:0000(DS:4E2E, 13, 1, "sim.in" DS:0932)` (load 13 bytes); DS:51EC = DS:4E35 & 1 (SIM.IN+7 bit 0). |
| `5c5f:002a` | `void vcr_write_simin(void)` | if DS:4E01: fopen("sim.in", "wb" DS:0939; fatal "vcr2.c" 57h), fwrite(DS:4E21, 13, 1), fclose. |
| `5c5f:0083` | `void vcr_world_init_hook(void)` | called by `4e0d:03e9`: `5cde:0000` (DS:4E71 = DS:4090); DS:4E56 = 0; `4899:0009(DS:2DAC−1)` (panel top = full screen); `5f2c:0c11` (control reset); DS:4E1C = 30000 (u32); `4ca7:0000` (mission clock reset); DS:4E6F = 0; `5cde:0076` (DS:4E6E = 0). |
| `5c5f:00bd` | `void vcr_gfx_init(void)` | `244d:0101`; `6396:0000(15h, 38E6:0025, 55a4:0000("VCR","BOX"), 25h)` — loads the VCR panel box `VCR.BOX` into the dialog item list at 38E6:0025 (37 items of 16h bytes); `5fef:0710` (list boxes); `618d:02c4(10h)`. |
| `5c5f:00f5` | `char *vcr_choose_tape(void)` | disk check (< 30000 → alert 3967:0 = ids 4Fh–54h "…make sure that 'Director Mode' is turned off", [OK]); name = `5e06:0191(96h, 97h)` (tape picker, title ids); if name: strcpy(DS:4E40, name), return DS:4E40; else 0. |
| `5c5f:0165` | `char *vcr_offer_save(void)` | `5a75:0e96` (sound off); draw `5440:018c(DS:4090,0)`; `368f:017f(2)`; if DS:0887 (frames) >= 3: name = `5e06:04f4()` (name dialog); if name: `5b93:04dd()` (END + finalise; fatal BDh); if TAPES\name exists: unlink it; rename TAPES\_tape_.tmp → TAPES\name. Else (< 3 frames): unlink TAPES\_tape_.tmp (stream left open). Returns name or 0. |
| `5c5f:0238` | `void vcr_exit_gfx(void)` | `368f:03e2`. |
| `5c5f:0242` | `int vcr_reopen(char *name)` → 4 | same mission already loaded: `5b93:045a`; `5ea5:0784(name)` (title); `4e0d:058e`; `618d:0726(name)`; `5b93:04fa(name)`; `4e0d:03e9`; `5b93:0063` (panel); if DS:092F: `618d:0430("_tape_.tmp")`; `5b93:0475` (prime first frame). |
| `5c5f:0298` | `int vcr_load(char *name)` → ok | `5b93:045a`; `5ea5:0784(name)`; `618d:011f(name,&p,&n)` (fatal 101h); `4e0d:038e(p, n)`; `618d:0726(name)` (fatal 105h); `4e0d:03e9`; `5b93:0063`; if DS:092F: `618d:0430("_tape_.tmp")` (fatal 10Bh); `5b93:0475`; `5b93:04fa(name)`. |
| `5c5f:0378` | `int vcr_unload(int close)` → ok | close: ok = `618d:0759()`; `4e0d:058e`; `4e0d:03b4`; `618d:0210`. |
| `5c5f:03a0` | `int vcr_switch(char *name, int close)` → 1 | `0378(close)`; `0298(name)`. |

---

## 7. Recording inside the flight loop (lead's `5cde:0405`, VCR-relevant order, verified)

Per frame (the lead documents the loop itself):
1. input `60a9:02c4`; pre-frame `5cde:0080` (dialogs; may record data blocks §4.3; returns 2 = abort
   or 3 = quit → if DS:0886 write END (`6a63:04d0(4)`), DS:5060 = DS:0887, DS:5064 = mission clock,
   return (3 → 1, 2 → 0));
2. countdown DS:31E5 = 1FFh; `5f2c:05d1(&input, &ctrl)`; view record from `5f2c:08fd(&view, &input, 1)`
   (or DS:0940 after the mission ended);
3. **sim step `5440:1317(&ctrl)`**; DS:0887++ (frame counter);
4. view keys `1c30:09d9(&view)` → changed? `1c30:0ad5` apply; draw `5440:018c(DS:4E71, 1)`;
5. wait: `q = elapsed PIT ticks` (≥ 8; or q = 25 when DS:0530 != 0 — fixed-rate mode); `ctrl.ticks
   (+12) = q >> 2`; `q = (q >> 2) << 2`;
6. **if DS:0886: `6a63:04d0(0, &ctrl)`**, and if the view changed `6a63:04d0(1, &view)`, and if the
   mission ended (step result bit 1) and the 4000-dt end countdown is 0: `6a63:04d0(4)`;
7. `362b:008f(q)` → dt for the **next** frame.

So record *N* holds the controls used by step *N* and the tick count measured after step *N*; that
tick count determines dt of step *N+1*. Playback reproduces this exactly (§8.1).

---

## 8. VCR runtime `5b93`

### 8.1 Playback step `5b93:0231 int vcr_play_frame(int ignore_views, int unused, int no_sim, int rerecord)` (verified)

```
5b93:01ed(no_sim, rerecord):                       // simulate the frame read last time
    if DS:4DFD == 0:                               // not priming
        if !no_sim: 5440:1317(&DS:4DE9)            // sim step with the recorded control record
        if rerecord: 6a63:04d0(0, &DS:4DE9)        // copy it into the new film
        DS:4E3B++                                  // frames played (u32)
        362b:008f(DS:4DFB << 2)                    // dt from the recorded ticks (DS:4DFB = 4DE9+12h)
done = 0
do:
    type = 6a63:05aa(&sub, &len)
    0 CTRL: 6a63:0576(&DS:4DE9, 14h); done = 1
    1 VIEW: 6a63:0576(&v, 8)
            if !ignore_views: r = 5b93:0166(&v) (apply, re-record if DS:092D); if r & 1: 5b93:01e2()
            (else v is overwritten with DS:0918.. and dropped)
    2 DATA: switch sub:
            0: 6a63:0576(buf,16); if !no_sim: DS:42C8 = buf; 606e:012d()
               if rerecord: 6a63:0515(0, 16, buf)
            1: 6a63:0576(&v,2);  if !no_sim: 5613:01e9(0, v); 4b9f:0000()
               if rerecord: 6a63:0515(1, 2, &v)
            2: 6a63:0576(buf,12); if !no_sim: 6cdc:0de1(buf); if rerecord: 6a63:0515(2, 12, buf)
            3: if !no_sim: 6cdc:0de1(0); if rerecord: 6a63:0515(3, 0, 0)
    3: nothing
    4 END: done = 1
until done
5d3c:003a(1)                                      // sound update
return type == 4                                  // 1 = end of film
```
Types > 4 loop again (none exist). `5b93:0436 vcr_play(void)` = `60a9:0abd()` (input housekeeping);
return `0231(DS:092B, 0, 0, DS:092E)`.

Priming `5b93:0475 vcr_prime(void)`: `01e2`; DS:4E3B = 0; DS:092B = DS:0930 = 0; DS:08D6 = 0; DS:0928 =
DS:0929 = DS:092A = 0; zero DS:4DE9 (20 bytes); DS:4DFD = 1; `0231(0, 0, 0, DS:092E)` (no step: reads
view records written before the first control record, then control record 1); DS:4DFD = 0;
`5ea5:04ff(0)`. After priming, each `0231` simulates one frame; the frame counter DS:4E3B then equals
the recorder's DS:0887 at the same point.

Rewind `5b93:0528 int vcr_rewind(int reopen)` → 4: clear both pages (DS:26C3 = 0, draw page DS:26D2 then
DS:26D4, `1d32:6ab0` full 320×200), `0032` (queue reset), `045a`, `4e0d:058e` (teardown), reopen ?
`618d:0726(DS:4E04)` : `618d:0742()` (rewind stream + re-read header, which restores realism and slider
0), `4e0d:03e9` (world init: fresh RNG seeds), `0063` (panel), if DS:092F `618d:0430("_tape_.tmp")`
(restart the director film), `0475`.

`5b93:04dd int vcr_finish_recording(void)` = `6a63:04d0(4, …)` && `618d:0502()`.
`5b93:04fa char *vcr_set_name(char *n)` = strcpy(DS:4E04, n).
`5b93:045a void vcr_apply_director_request(void)`: if DS:092C: `5d3c:0084(1)`, DS:092C = 0.
`5b93:0000 void vcr_world_reset(void)` (from `4e0d:03e9`): DS:0886 = 1, DS:4E1C = 0 (u32), DS:4E1A = 0,
DS:0887 = 0 (u32), DS:4E02 = 0, DS:088B = 1, DS:088C = 0.
`5b93:0032 void vcr_queue_reset(void)`: DS:0891 = DS:0892 = 0 (read/write index of the queue DS:088F).
`5b93:0153 int vcr_is_playing(void)` = DS:4E20 == 2 (used by the input poll `60a9:02c4`).
`5b93:0be9 int vcr_mode(void)` = DS:4DE6.

### 8.2 Views during playback

`5b93:0166 int vcr_view(VIEWREC *v)` → flags: saves DS:19F2, `1c30:0780()` (view kind) and
`1c30:09a9()`; if `1c30:09d9(v)` (key is a view command): r = `1c30:0ad5(v)` and if DS:092D (director)
`6a63:04d0(1, v)` (record into the new film); else r = 0. If DS:19F2 changed → `5ea5:04b0` (swap button
labels); if the view kind or `09a9` changed → `5ea5:0597` (update view name). Returns r (bit 0 = full
redraw needed, bit 2 = view changed; lead's `1c30:0ad5`).
`5b93:01e2 void vcr_redraw_all(void)`: DS:4DFF = DS:4090 (number of full-cockpit redraws to do; the
lead's DS:4E71 equivalent).
`5b93:0406 void vcr_draw(void)`: `5440:018c(DS:4DFF, 1)`; `368f:009f(&DS:4DFF)` (decrement, floor 0).
`5b93:0424 void vcr_draw_pending(void)`: while DS:4DFF: `0406`.
`5b93:05b2 void vcr_mark_edited(void)`: DS:092B = 1 (ignore the film's views from now), DS:0930 = 1
(film modified).

`5b93:05c1 void vcr_view_button(EVENT *e)` — camera buttons of the panel (event type 18h..2Dh; `e+2` =
view key); start from `v = DS:0918` (8 bytes):

| Event | DS:19F2 != 0 → view key | else preset record |
|---|---|---|
| 18h | 1Ch | DS:0908 `{0,3,0,−7}` |
| 19h | 1Eh | if view kind (`1c30:0780`) == 18h: DS:08F8 `{0,3,−7,0}` |
| 1Ah | 1Fh | if view kind == 18h: DS:0900 `{0,3,7,0}` |
| 1Bh | 1Dh | DS:0910 `{0,3,0,7}` |
| 1Ch | 20h | DS:08E8 `{0,2,0,−7}` |
| 1Dh | 22h | DS:08D8 `{0,2,−7,0}` |
| 1Eh | 23h | DS:08E0 `{0,2,7,0}` |
| 1Fh | 21h | DS:08F0 `{0,2,0,7}` |
| 21h/22h/23h/24h | key 25h/26h/27h/28h | — |
| 26h..2Dh | DS:08D6 = 0 (stop the preset) | |

Preset: v.+2 = preset.+2; r = `0166(&v)` \| `0166(preset)`; DS:0929 = 1; DS:08D6 = preset (re-applied
every frame by `074b`); `05b2`. Key: v.+0 = key; r = `0166(&v)`; `05b2`. If r & 1: DS:0928 = 1.
(DS:19F2 is the lead's/sim_world's flag — probably "player shot down / external camera" — guess.)

`5b93:074b int vcr_track_views(int *redraw, u8 flag)`: DS:092A = flag; *redraw = 0; if DS:0930: if
DS:08D6: if !DS:0929 && !DS:19F2: `0166(DS:08D6)`; ret = 1; elif flag && `1c30:0780()`: zero DS:0918,
`0166(DS:0918)`; if DS:0928: ret = 1, DS:0928 = 0; *redraw = 1 (the test `(di | 1) != 0` is always
true); DS:0929 = 0. Returns ret.
`5b93:07ee`: `074b(&c, 0)`; c → `01e2`; ret → draw once (`5440:018c(DS:4DFF,1)`, `368f:009f`).
`5b93:082f`: `074b(&c, 1)`; c → `01e2`.
`5b93:08d6 u8 vcr_view_is_edit(VIEWREC *v)`: if v.+2 bit 1: if view kind ≤ 5: r = bit 0 ? 0 : (v.+4 \|\|
v.+6); else r = bit 0 ? (v.+6 != 0) : (v.+4 \|\| v.+6); elif v.+0: r = 1; else 0.

### 8.3 Panel geometry helpers

`5b93:003f` full-screen clip (DS:26C4 = 0, DS:26C3 = 1, DS:26C6 = DS:2DAA−1, DS:26C8 = 79h, DS:26CA =
DS:2DAC−1); `5b93:010d` panel region DS:0B16 = 0, DS:0B18 = DS:2DAA−10, DS:0B1A = 79h, DS:0B1C =
DS:2DAC−10; `5b93:0130` same with DS:0B1A = 0.
`5b93:0063 void vcr_panel_show(void)`: `1c0f:0032` (reset change detection), `010d`, `53a6:02cf(15h,
38E6:0000?, 25h)` (activate the panel item list), DS:088D = number of halvings until DS:50A2 ≤ 7FFFh;
slider 3 range = `5613:026a(3, 0, DS:50A2 >> DS:088D)` (the tape position slider); timeout DS:016C (0
ticks); `1c0f:0028` (DS:5E04 = 1); DS:08D5 = 1; `4899:0009(78h)` (3D view height 120 lines); `5ea5:04b0`;
`5ea5:0597`.
`5b93:00f1 void vcr_panel_hide(void)`: DS:08D5 = 0; `0130`; `4899:0009(DS:2DAC−1)`.
`5b93:084e void vcr_refresh_screen(int full)`: `606e:000d`; if `5440:018c(DS:4090, 0)` returned 0:
`368f:03b6`, `368f:01cf`, clear (DS:26CC = 1, colours 0), `1d32:6ab0(0,0,DS:2DAA,DS:2DAC)`, if full
`5440:083a`; if DS:08D5: draw page = DS:26D2, `003f`, `606e:000d`, `53a6:0393(15h, 38E6, 25h)` (redraw
the panel).
`5b93:08c8 int vcr_fullscreen(u8 playing)`: DS:4DE8 = playing; return 8.

---

## 9. VCR UI modes

### 9.1 Mode dispatcher `5b93:0bf1 int vcr_ui(int mode)` → 0 exit / 1 enter simulation

DS:4E20 = 2; DS:4DE6 = mode; `0063`; `1c0f:000a` (panel polling on). Loop: DS:4DE6 = mode; switch:

| Mode | Handler | Meaning |
|---|---|---|
| 1 | `0ace(1)` | play |
| 2 | `5dd0:01bb` | fast forward with picture (every 12th frame drawn) |
| 3 | `5dd0:02b3` | fast forward blank ("FAST FORWARDING TAPE") |
| 4 | `6163:0050` | paused |
| 5 | `6163:0187` | end of tape |
| 6 | — | nothing (mode unchanged: endless loop; never produced) |
| 7 | `5dd0:00d2` | seek to position ("SEEKING LOCATION") |
| 8 | `096c` | full-screen view (panel hidden) |
| 9 | — | exit → return 0 |
| 10 | `0166(DS:0920 = {1Ch,0,0,0})` | enter simulation (cockpit view) → return 1 |
| 11 | `0ace(0)` | single step |

Exit: `1c0f:0014` (panel polling off).

### 9.2 Panel buttons (event types; hot-region ids of the `VCR.BOX` items)

Verified from the handlers and the disable lists (§9.6): **10h REWIND, 11h PAUSE, 12h PLAY, 13h STEP,
14h FAST FORWARD, 15h SEEK (go to slider position), 16h EJECT (exit, with save prompt), 17h TAPE MENU,
18h–1Fh and 21h–24h camera buttons (§8.2), 20h ENTER SIMULATION.** (Labels are guesses from behaviour;
the box text is in `VCR.BOX`.)

### 9.3 Play `5b93:0ace int vcr_mode_play(u8 continuous)`

`5d46:0086(DS:09FE = {13h,10h,17h}, 2000h)` (disable STEP, REWIND, TAPE MENU); `5ea5:0039(0)`; `0032`.
Loop until m != 0: `1c0f:0053` (poll panel); end = `0436()`; if end: m = 5; elif !continuous: m = 4.
Events (`51e7:0076(DS:088F)`) while m == 0: 11h → 4; 14h → 2; 20h → 10; 16h → if `0aaf()` return 9;
17h → if `5e06:090a()` m = 4; other → `05c1(e)`. If !end && m == 0 && e.esc (+4) && !DS:08D6: m =
`08c8(1)` (= 8, full screen, playing). After events: `082f`; `0406` (draw). Return m.
**There is no frame-rate wait: playback runs as fast as it draws** (dt comes from the film).

`5b93:0aaf int vcr_eject(void)`: r = `5e06:03a2()` (save changes?); if r && r != 3: `618d:0759`.
Returns r (0 = cancelled).

### 9.4 Paused / end of tape `6163`

`6163:0050 int vcr_mode_paused(void)`: disable list DS:0A07 {11h} (or DS:0A09 {11h,10h} at frame 0);
clear bit 40h of 38E6:01F0; `5b93:0032`; `003c`; `1c0f:0053`; `5b93:0424`. Loop until m: `1c0f:0053`;
`60a9:0abd`; events: 10h → `0000` (rewind: 4 if done); 12h → 1; 13h → 11; 14h → 3; 15h → if
`5dd0:0000()` 7; 16h → if `0aaf()` 9; 17h → if `5e06:090a()` 4; 20h → 10; other → `05c1`; if m == 0 &&
e.esc && !DS:08D6: m = `08c8(0)`. Then `5b93:07ee`.
`6163:0187 int vcr_mode_end(void)`: `5b93:0032`; disable DS:0A02 {13h,11h,12h,14h}; clear 38E6:01F0 bit
40h; ended = `5440:0944()` (mission over?); `5ea5:04ff(ended)`; `003c`; `5b93:0424`. Events: 10h rewind
→ 4; 15h seek → 7; 17h tape menu → 4; 16h eject → 9; 20h → if ended: alert(3958:0 = ids 21h–25h "You
may not 'Enter Simulation' now…", [OK]) else 10; other → `05c1`. Then `07ee`.
`6163:0000 int vcr_rewind_prompt(void)`: if DS:4E3B != 0: r = `5e06:03a2()`; if r: `5b93:0528(r == 3)`,
return 1. Else 0.
`6163:003c void vcr_sound_idle(void)`: `5a75:0a0a()`; `5d3c:003a(1)`.

### 9.5 Fast forward / seek `5dd0`

`5dd0:0000 int vcr_seek_setup(void)`: target = (s32)`5613:0161(3)` → DS:4E82; if target <= DS:4E3B
return 0 (**no backward seek**); DS:4E7E = target − DS:4E3B; DS:4E7A = 0; DS:4E76 = DS:4E7E / 40;
`ltoa(target, DS:0AA0, 10)`; return 1. (The slider value is used unscaled although its range was set
to DS:50A2 >> DS:088D — for films longer than 32767 frames the target is too small; quirk.)
`5dd0:005e int seek_progress(void)` = (DS:4E7E − DS:4E7A + DS:4E76) · 20 / DS:4E7E (s32).
`5dd0:008a void seek_draw_bar(int n)`: `368f:03e2`; DS:26C3 = 0; for i = 19 down to 0 at x = AAh +
7·(19−i), y = 70h, 4×4: colour C5h if i >= n else CFh (`6396:0159` + `1d32:6ab0`).
`5dd0:00d2 int vcr_mode_seek(void)`: if DS:4E82 == 0 → 4. Disable DS:09EB (all but 11h,12h,15h);
`5ea5:0039(0)`; banner `606e:0396("SEEKING LOCATION" DS:0A8F)`; bar; `5b93:0032`. Loop: `1c0f:0053`;
if `5b93:0436()` (end) m = 5; else DS:4E7A++, if DS:4E3B == DS:4E82 m = 4, else redraw the bar if the
progress changed. Events: 11h → 4, 12h → 1. `5b93:082f`. Exit: `5b93:01e2`. No drawing of the 3D view.
`5dd0:01bb int vcr_mode_ff(void)`: disable DS:09DB; `5ea5:0039(0)`; `0032`; k = 0. Loop: `1c0f:0053`;
draw = (k-- == 0), then k = 12; if `0436()`: `01e2`, m = 5. Events: 12h → 1; 20h → 10; 11h → draw = 1,
4; 16h → if `0aaf()` return 9. `082f`; if draw: `0406`.
`5dd0:02b3 int vcr_mode_ff_blank(void)`: disable DS:09D9; `5ea5:0039(0)`; `0032`; banner `606e:0396("FAST
FORWARDING TAPE" DS:0A7A)`. Loop: `1c0f:0053`; `0436()` → end: `01e2`, 5. Events: 12h → `01e2`, 1;
11h → `01e2`, 4. `082f`. Never draws.

### 9.6 Full-screen view `5b93:096c int vcr_mode_fullscreen(void)`

`01e2`; `1c0f:0014` (panel polling off); `00f1` (hide panel); end = DS:4E3B == DS:50A2; end → DS:4DE8 =
0. Loop until m: `60a9:0abd`; if DS:4DE8 (playing): end = `0436()`, redraw = 1; end → DS:4DE8 = 0, m =
5; poll input; `5f2c:08fd(&view, &input, 1)`; if input+1Bh == 1 (Esc): m = end ? 5 : DS:4DE8 ? 1 : 4;
if `1c30:09d9(&view)` and (DS:0930 or `08d6(&view)`): `05b2`; r = `0166(&view)`; r & 5 → redraw; r & 1 →
`01e2`. If redraw or DS:4DFF: `0406`. Exit: if anything was drawn `368f:03ed/03b6/01f2`; `0063`;
`1c0f:000a`; `01e2`. Return m.

### 9.7 Panel event pump `1c0f`, queue `51e7`, buttons `5d46`, glue `5d3c`

`1c0f:0053 void vcr_poll_panel(void)` (near entry reached by far calls; also called at the start of
every sim step `5440:1317` and from `5440:0269`): `60a9:0000` (input update); return unless DS:19EE
(panel polling on); unless timeout DS:016C expired (`4b31:0000`) or DS:19EF (forced), return. Restart
the timeout (4 ticks); if `5ea5:02f7()` (counter/time/buttons changed) DS:19EF = 1. Poll input
(`60a9:02c4`, 25h bytes) and mouse (`5f2c:01d8` → 8 bytes); compare with the previous copies DS:5E0D
(25h) / DS:5E05 (8); nothing changed and not forced → return; store both. `5f2c:08fd(&view, &input, 0)`
→ key = view.+0 != 0; esc = input+1Bh == 1. If none of (key, mouse changed, esc, forced) → return.
DS:19EF = 0; save gfx context (`244d:0126`, `244d:000b`); `0962:0c7f`; `5b93:003f`; `606e:0018(&mouse)`
(click sound + `53a6:0255`); type = `46de:00ee(mouse x, y, buttons, DS:5E04)` (hot region hit);
`5d3c:003a(1)`; if type or key or esc: push the event `{type, view.+0, esc}` (6 bytes) into the queue
DS:088F (`51e7:0000`); `46de:02f3`; DS:5E04 = 0; `0962:0bf1`; restore gfx context.
`1c0f:000a` DS:19EE = 1; `1c0f:0014` DS:19EE = 0; `1c0f:001e` DS:19EF = 1; `1c0f:0028` DS:5E04 = 1;
`1c0f:0032` fill DS:5E0D (25h bytes) and DS:5E05 (8) with FFh (force change detection).

Queue `51e7` (DS:088F: +0 u8 element size = 6, +1 u8 capacity = 10, +2 u8 read index, +3 u8 write
index, +4 data; indices count **down** with wrap to capacity−1): `51e7:0000 q_push(q, src)` → 0 if full
(`009e`), else copy element to slot[+3], `0109(q,3)` (decrement with wrap), 1. `51e7:0076 q_pop(q)` →
ptr/0: `0052` (0 if +2 == +3, else slot[+2]) then `0109(q,2)`. `51e7:009e q_full`: r = +2, w = +3: r <=
w ? r+1 == w : capacity == r−w (quirk: with r > w the full state is not detected; an 11th push then
makes the queue look empty). `51e7:00e2 slot(q,i)` = q + 4 + i·size. `51e7:0109 dec_wrap(q, off)`.

`5d46` (panel button states; items of 16h bytes at 38E6:0025 + id·16h, word +0 flags, byte +21h... ):
`5d46:0086 void panel_disable(u8 *ids, u16 bits)`: remember for the 20 ids of DS:09B2 whether enabled
(`004b`: (flags & 7000h) == 0); clear `bits` in all DS:09B2 items (`0001(list, bits, 0)`), set `bits`
in the listed items (`0001(ids, bits, 1)`); for each item whose state changed mark it for redraw
(`006c`: item+21h... byte at +21h of the 16h record = 43h); `1c0f:001e`. `5d46:0001(ids, bits, set)`
(near) and/or per item; `5d46:004b(id)` = enabled; `5d46:006c(id)` = mark dirty; `5d46:0000` stub.
Master list DS:09B2: 10 11 12 13 14 20 18 19 1A 1B 17 1C 1D 1E 1F 16 23 21 22 24.

`5d3c:0000` / `0023`: if the panel is shown: draw page = DS:26D2, `5b93:003f`, `46de:04bc` / `46de:04de`
(show/hide the mouse over the panel; called from `5440:07e1`). `5d3c:003a void vcr_sound_frame(int on)`:
`5a75:095e(DS:43D8→+2 + 2, on ? !DS:19F2 : 0)`. `5d3c:0064 u32 vcr_frame(void)` = DS:4E20 == 2 ?
DS:4E3B : DS:0887 (used by `1c30:09bc`, `1c30:0ad5` and **AI `4edf:068a`** — same value in recording
and playback). `5d3c:0084 void vcr_set_director(u8 on)`: DS:092F = DS:092E = DS:092D = DS:088B = on.

---

## 10. Panel drawing `5ea5` (vcr_gfx.c) and helpers `606e`

The panel is a dialog item list (`VCR.BOX`, far segment 38E6, items of 16h bytes, a byte 43h at item
offset +?? = "dirty"); `5ea5` holds its draw callbacks (called through the dialog library `3dab:*`
stubs — other writer) and state setters. Offsets below are into segment 38E6.

| Addr | Name | Behaviour |
|---|---|---|
| `5ea5:0000` | item callback | *(DS:3BCF)+0Ch = 74h |
| `5ea5:0020` | callback | `47a8:00ce()` |
| `5ea5:002a` | callback | `5613:0489(3)` (tape slider) |
| `5ea5:0039` | `panel_slider_enable(int on)` | 38E6:01F0 bit 40h cleared if on, set if off |
| `5ea5:005c` / `0079` / `009b` / `0839` | button callbacks | set DS:3BC1 (dialog result) = DS:3BCD (+0Eh for `009b` with flag 30h) when `6396:0335` / `47a8:0cb0(0)` / `6396:0548` report a click |
| `5ea5:00ca` | `hms(int out[3], s32 secs)` | out[2] = secs mod 60 … via `277a:3dc1(x, 60)` (divide returning quotient in AX, remainder in DX): out[2] = sec, out[1] = min, out[0] = hours |
| `5ea5:0123` | draw callback | draws the 8 characters of DS:0ACB ("00:00:00") at x offsets DS:0AD4 {4,9,0Eh,10h,15h,1Ah,1Ch,21h} (font DS:3F2E, colour CCh) |
| `5ea5:017f` | draw callback (play/record lamp) | by 38E6:012D (0 → icon B0Ah, colour 8Fh; 1 → B0Ch; else none); frame box colours C5h; mode 3 → extra box |
| `5ea5:027e` | `blink_timer()` | timeout DS:0166 = 3Bh ticks |
| `5ea5:0291` | `put_2digits(int v, char *dst)` | itoa; single digit → keeps the leading '0' |
| `5ea5:02ca` | `s32 panel_time(void)` | slider 3 dragged (`5613:0247(3)`) ? `4ca7:0045()` (mission clock) : `5613:0161(3)` |
| `5ea5:02f7` | `int panel_update(void)` → changed | slider 3 = DS:4E3B >> DS:088D (`5613:01e9`; changed → 38E6:01EF = 43h); every 0Fh ticks (timeout DS:0160): t = mode ∈ DS:0ADC {1,2,3,7} ? mission clock : `02ca()`; if t != DS:0ABE: DS:0ABE = t, DS:0ACB = "00:00:00", `00ca` → `0291` into hh/mm/ss, 38E6:013F = 43h. Lamp state 38E6:012D by mode: 1 → 0, 2 → 1, 3/4/7 → blink (1/2 alternate on timeout DS:0166 via `027e`: si = di ^ 3), 5 → 1 …, 6 → 3 (table 5ea5:046C). |
| `5ea5:047a` | draw callback | frame (colour B8h) + `5247:0070` (title) |
| `5ea5:04b0` | `panel_view_labels(void)` | DS:19F2 ? items 38E6:00BD/00D3 = 5Fh/60h : 61h/62h; mark dirty |
| `5ea5:04ff` | `panel_end_label(int ended)` | 38E6:02E3 = ended ? 63h : 64h; dirty |
| `5ea5:0530` / `0560` | near: strcpy / strcat into DS:0AE0 | |
| `5ea5:0597` | `char *panel_view_name(void)` | builds DS:0AE0 from the view kind `1c30:0780()` (STR_POOL `0ab0:0066(65h+k)`, `6Bh`, `6Ch`, `61h+k`, `76h`, `77h`, `78h`, `8Eh`, `8Ch+obj[+26h]`, the tracked object's name from the type tables DS:55D2/55D0, "a Ghost" DS:0B0E); disables a view-dependent button list (DS:09C7/09C9/09D3/09D6 with 4000h); DS:0B09 = 0; if the text changed mark 38E6:0155 |
| `5ea5:0784` | `panel_set_title(char *name)` | strcpy(DS:4EC8, name), cut at '.', mark 38E6:016B |
| `5ea5:07df` | draw callback | title text in the box (`53ec:01e6`, colours C1h/B1h/C0h) |
| `5ea5:085b` | `panel_init_lamp()` | 38E6:012D = 3 |

`606e` (rlsmgfx.c + VCR/dialog helpers):

| Addr | Name | Behaviour |
|---|---|---|
| `606e:0000` | `char *tape_tmp_name(void)` | returns "_tape_.tmp" (DS:4F08−? string at 606e's data) |
| `606e:0008` | stub | |
| `606e:000d` | `void dlg_force_redraw(void)` | DS:4F08 = 1 |
| `606e:0018` | `void panel_click(MOUSE *m)` | if 0 < m.+6 < 5 (button): sound `5a75:0eea(10h,0,0)`; `53a6:0255(m.x, m.y, m.+6 − 1)` |
| `606e:0057` | `void dlg_redraw_all(void)` | `60a9:0aa7`; `5b93:084e(0)`; `368f:017f(2)`; `60a9:0ab2` |
| `606e:007a` | `int dlg_poll(void)` → item | if `60a9:09d8()` (mode switch / resize?): `0057`, `60a9:0a04`, DS:3BB8 = 1, `000d`; `5d3c:003a(0)`; poll input; Esc (input+1Bh == 1) → `5f2c:00b6(A0h, 64h)` (mouse to centre), return 9; else mouse → `0018`, `368f:03b6`, `53a6:044d(key, …)`, return `46de:00ee(x, y, buttons, DS:4F08)`; `46de:02f3`; DS:4F08 = 0 |
| `606e:012d` | `void realism_changed(void)` | `522c:0162()` |
| `606e:0137` | `int realism_dialog_in_flight(void)` → changed | (called by the lead's `5cde:0080`) copy DS:42C8 (32 bytes); `6e9f:02d5` (realism dialog); `53a6:02cf(15h, 38A4:?, 24h)`; `000d`; loop `007a` until 9 (0Fh → `000d`); if DS:42CA/42CB/42D1/42CF changed: `1614:02c3` (clear messages); if !DS:42D1: zero DS:57DD (13 bytes), DS:57E8 = FFFFh; `012d`; `5cde:0000`; return memcmp(old, DS:42C8, 32) != 0 |
| `606e:01e6` | `void pause_screen(void)` | draw `5440:018c(DS:4090,1)`; `368f:00e6(1Eh)` (wait 30·13 PIT ticks or a key); `5cde:0000` |
| `606e:0208` | `int key_or_click(void)` | poll input; 1 if input+1Bh (key) != 0 or input+23h bit 5 or 6 (mouse buttons) |
| `606e:0243` | `void wait_key_release(void)` | poll until input+1Bh == 0 |
| `606e:025f` | `void banner_text(char *s)` | font DS:3F32, colour CFh, centred at y = DS:2DAA−width−14h… (`1d32:5570` width, `1d32:5845` draw) |
| `606e:029d` | `void banner(char *s)` | save gfx ctx; DS:26C3 = 0; page DS:26D4; if s: `025f(s)`; if DS:0B72 (palette fade enabled): read palette (`0000:185e`), 18 steps scaling 20Dh bytes by (i−1)/18, set (`0000:189b`), `1c0f:0053` each step; `6396:0159`; page DS:26D2; clear 0..DS:2DAA × 0..79h; `025f(s)`; `368f:03e2`; `368f:03c1`; `1d32:53fe(468F?,0,DS:2DAA,79h)`; restore palette; restore gfx ctx |
| `606e:0396` | `banner` wrapper | |

---

## 11. Tape files, dialogs, list box

### 11.1 vcr_file.c `5e06`

| Addr | Name | Behaviour |
|---|---|---|
| `5e06:0000` | `void tape_rename(char *from, char *to)` | rename(DS:4032+from, DS:4032+to) |
| `5e06:00ba` | `void tape_unlink(char *name)` | unlink(DS:4032+name) |
| `5e06:0120` | `void modal_depth(int d)` | if the panel is shown: d == 1 and DS:0AB8 == 0 → `5b93:0130`, `1c0f:0014`, `606e:000d`; d == −1 and DS:0AB8 == 1 → `5b93:010d`, `53a6:02cf(15h, 38E6:0000?, 25h)`, `1c0f:000a`; DS:0AB8 += d |
| `5e06:0175` / `0183` | `modal_enter()` / `modal_leave()` | `0120(1)` / `0120(−1)` |
| `5e06:0191` | `char *tape_pick(int title1, int title2)` | enter; sound off; n = `4bcd:01ce("TAPES\\*.VCR")` (list to `_files_.out`); `5155:0207()` (mark bad versions); list box `5fef:07c2(…, title, n)`; loop `606e:007a`: 1 (cancel) → 0; 2 (OK): name = `5155:0098(buf, 5fef:029f())` (strip '*'), path `368f:02e6(name,"VCR")`; not found → `5fef:03a5(DS:0ABA)` message; entry marked '*' → `5155:03a4(name)` (explain add-ons), redraw; else strcpy(DS:4E86, name), return it. Leave: `5b93:084e(0)`, `368f:017f(2)`, leave. |
| `5e06:02d9` | `int director_mode(int set)` | set 1 / 0 → `5d3c:0084(set)`; returns DS:088B (called from results `5254`) |
| `5e06:0304` | `int tape_commit_copy(void)` → ok | copy the rest of the source film into the director film: once, record the current view (DS:0918) unless the view kind is 0 or 18h; while DS:4E3B < DS:50A2: `5b93:0231(1, 0, 1, 1)` (no sim, no views, re-record) until END; DS:506E..508B = DS:50B0.. (30 bytes); DS:5060 = DS:50A2; DS:5064 = DS:50A6; `5b93:04dd()` (fatal "vcr_file.c" 161h) |
| `5e06:03a2` | `int tape_save_changes(void)` → 0 cancel / 2 discarded / 3 saved | enter; !DS:092F → 2; !DS:0930 → `618d:0629` (drop temp), 2; else alert(395A:0 = ids 1Ch–1Eh "You have made changes to the current tape. Would you like to save them?", 3959:0 = [17h SAVE, 18h DISCARD, 16h CANCEL]): SAVE → `0304`, `618d:0759`, unlink TAPES\DS:4E04, rename TAPES\_tape_.tmp → TAPES\DS:4E04, 3; DISCARD → `618d:0629`, 2; else 0. Leave. |
| `5e06:044f` | `int tape_menu_load(void)` → loaded | loop: name = `0191()`; none → return; same as DS:4E04 → alert(ids 1Fh–20h "This tape is already loaded!"); else r = `03a2()`; r → `5c5f:03a0(name, r != 3)`, return 1 |
| `5e06:04f4` | `char *tape_ask_name(void)` | enter; list existing tapes with an edit field (`5fef:07c2`, titles 91h/92h); OK: name = edit text + ".VCR"? (`5fef:029f`, `368f:02e6(…,"VCR")`) into DS:4EB2; reserved DOS name (`4bcd:020c`) → `5fef:03a5(DS:0ABB)`, retry; exists → alert(ids 2Ah–2Ch "This tape name already exists. Do you want to replace it?", [19h REPLACE, 16h CANCEL]); REPLACE → accept; cancel → 0. Leave. |
| `5e06:06a2` | `int tape_menu_save(void)` | !DS:092D → alert(ids 2Dh–2Fh "not in director mode, so changes can't be saved"); !DS:0930 → alert(ids 44h–46h "No changes have been made…"); else name = `04f4()`; if name: `0304`, `618d:0759`, unlink existing, rename _tape_.tmp → name, `5b93:04fa(name)`, `5c5f:0242(name)`. Returns name |
| `5e06:0755` | `int list_other_tapes(char *pat)` | `4bcd:007f(pat, DS:4E04)` (exclude the current tape) |
| `5e06:0768` | `void tape_menu_delete(void)` | n = `0755("TAPES\\*.VCR")`; n == 0 → alert(ids 26h–29h "…is the last one on the disk. It may not be deleted."); list (titles 93h/94h); OK: selected == current → alert(ids 47h–48h "The current tape cannot be deleted!"); else unlink; loop |
| `5e06:08e8` | `void tape_menu_backdrop(void)` | `368f:03ed`, `368f:03b6`, `1d32:53fe(0,0,DS:2DAA,DS:2DAC)` |
| `5e06:090a` | `u8 tape_menu(void)` → reload happened | enter; sound off; backdrop; loop: activate box 38E6:0343 (6 items); `606e:007a` − 1: 0 LOAD → `044f` (→ result 1, exit); 1 SAVE → `06a2` (→ 1, exit); 2 DELETE → `0768`; 3 EXIT → exit. Leave with screen restore (`368f:03c1/03e2/017f(2)`). |

### 11.2 vcr_list.c `5fef` (list box of `_files_.out`; 32-byte records, §11.4)

List state: DS:4EFD count, DS:4EFF max first row (count − 12, ≥ 0), DS:4F01 visible rows (≤ 12),
DS:0B40 first row, DS:4F05 cursor row, DS:4F03 selected index = DS:0B40 + DS:4F05, DS:4EF0 edit text,
DS:0B44 max length, DS:0B46 caret, DS:0B48 text length, DS:4EFB/0B42 caret blink.

| Addr | Behaviour |
|---|---|
| `5fef:0000` | scroll-button callback: `47a8:0cb0(0)` → DS:3BC1 = item+10h |
| `5fef:001e` | scroll arrows: on click (repeat every 3Bh ticks, timeout DS:0154): item 5 = up (cursor−1 or first−1), else down; changed → DS:4F03 = first + cursor, `02a7`, mark 3934:005C |
| `5fef:00cd` | (near) row under the mouse = (DS:3BBD − (DS:3BC7+2)) / rowh clamped to 0..DS:4F01−1 |
| `5fef:0105` | draw the rows: open `_files_.out` (DS:4032 + name, fallback plain; fatal "vcr_list.c" D0h), cursor from the mouse, seek to first·32, for each visible row: highlight the cursor row (colours B9h/BEh), draw the 32-byte record's name at y += 6 |
| `5fef:029f` | returns DS:4EF0 (edit text) |
| `5fef:02a8` | (near) read record DS:4F03 from `_files_.out` (fatal 143h) and `03a5(name)` |
| `5fef:03a5` | `int set_edit(char *s)`: len ≤ DS:0B44 → strcpy(DS:4EF0, s), caret = end, DS:4EFB = 1, mark 3934:00CA; else 0 |
| `5fef:0406` | (near) `is_name_char(c)`: ctype(c) & 0Eh or '_' |
| `5fef:0425` | (near) `edit_key(scan, ch)`: printable → insert (max 8 characters before the extension; `0000:3e34` memmove); 4Dh → right; 4Bh → left; 0Eh backspace; 53h delete |
| `5fef:058b` | draw the edit field with a blinking caret (colours C0h/B9h) |
| `5fef:0655` | key handler + caret blink every 3Bh ticks (DS:015A) |
| `5fef:06d5` | `0655(DS:3BBB, DS:3BB9)` |
| `5fef:06e9` | clear callback (`1d32:6ab0`) |
| `5fef:0710` | `6396:0000(24h, 3934:?, 55a4:0000("lbox","BOX"), 0Bh)`; `6396:0000(343h, 38E6, 55a4:0000("tapes","BOX"), 6)` — the list-box dialog and the tape menu |
| `5fef:0757` | `list_init(int n)`: DS:4EFD = n, cursor = first = selected = 0, DS:4EFF = max(n−12, 0), DS:4F01 = n − DS:4EFF, timeout, `02a7`, mark |
| `5fef:07ad` | re-init with the same count |
| `5fef:07c2` | `list_open(…, titles, n)`: titles into the box, `0757(n)` |

### 11.3 modules.c `5155` (add-on modules required by a film)

| Addr | Behaviour |
|---|---|
| `5155:0000` | `void module_block(u8 block[364], u16 mask)` — §2.2 (`M#SHL.DYN` with '#' = '1'+k, via `55a4:0000`, 40 bytes each) |
| `5155:0082` | `int is_marked(char *rec)` = rec[0] == '*' |
| `5155:0098` | `char *unmarked_name(char *dst, char *rec)` = strcpy(dst, rec[0]=='*' ? rec+1 : rec) |
| `5155:00fa` | `int tape_version(u8 block[364], char *name)` → header +02: fopen(TAPES\name.VCR "rb"; fatal "modules.c" 65h), fread header (66) + block (364) into `block`; on a short read returns … (the header word +2 of the local copy); fclose |
| `5155:0207` | `int validate_tape_list(void)` → valid count: open `_files_.out` "r+b" (`55a4:0429` path; fatal 7Eh); for each 32-byte record: `00fa` != 12h → shift the name right by one (`memmove(rec+1, rec, strlen+1)`), rec[0] = '*', rewrite the record in place; else count++ |
| `5155:0369` | `void text_ids(far *list, int from, u16 group_id…)` builds a far-pointer list of STR_POOL texts (`0ab0:000b`) |
| `5155:03a4` | `void explain_tape(char *name)`: version 12h → text "This tape was created using expansion…" (ids from `0369(…, 500C1h)`) followed by the names (40-byte records) of the add-ons in the block's mask that are not installed (`~55a4:0429()` mask); else "The selected tape was created with…" (`300BEh`); formatted by `5a01:00e9`, shown with `53a6:02cf(16h, 38BF:?, …)` until `606e:007a` returns 9 |

### 11.4 findfile.c `4bcd` and getdfree `36ee`

`_files_.out` record (32 bytes): `char stem[28]` (name up to the '.', zero padded), `char ext[4]` at
+1Ch (extension without the dot).

| Addr | Behaviour |
|---|---|
| `4bcd:0000` | `void write_name_rec(FILE *f, char *filename)`: zero 32 bytes, copy the stem, copy the extension to +1Ch, fwrite 32 bytes |
| `4bcd:0077` | returns "_files_.out" (DS:0254) |
| `4bcd:007f` | `int list_files(char *pattern, char *exclude)` → count: fopen(DS:4032 + "_files_.out", "wb"; fatal "findfile.c"? 77h); findfirst(DS:4032 + pattern, attr 0); for each match whose ff_name differs from `exclude` (exact strcmp; exclude may be 0): `0000(f, ff_name)`, count++; findnext; fclose |
| `4bcd:01ce` | `list_files(pattern, 0)` |
| `4bcd:01df` | `int file_exists(char *path)`: fopen "rb" → close, 1; else 0 |
| `4bcd:020c` | `int reserved_dos_name(char *s)`: strlen < 3 → 0; strnicmp(s, "CON"/"AUX"/"PRN", 3) == 0 → 1; "NUL"/"PRT"/"COM" → 1 only if s[3] is a digit (ctype bit 2) for… (exact: NUL/PRT/COM mismatch all → 0; a match → s[3] digit ? 1 : 0) |
| `4bcd:02c0` | DS:3F28 = 1, DS:3F26 = 4 |
| `36ee:0003` | `s32 disk_free(int drive)`: drive 0 → from DS:4032[0] if it is a letter (& EFh, 'A'..'Z' → letter − 40h) else current drive + 1; `getdfree(drive, &d)`; d.total == −1 (error) → −1; return avail_clusters · sectors · bytes (16-bit products as in Borland: `d[0]*d[2]*d[3]` in 16-bit ints — **overflows above 32767 bytes**; the callers compare the s32 result with 30000, so a disk with more than 64 K free can report a wrapped value — quirk; `PORT:` return real free space capped at 7FFFFFFFh) |

`4bcd:020c` exact: for "NUL", "PRT", "COM": if none of them match → 0; if one matches → returns 1 when
ctype(s[3]) & 2 (digit), else 0. (**likely**; decompile flow checked against the disassembly.)

---

## 12. Demo mode `-d` (`5d56` vcr_demo.c)

`5d56:01b5 void demo_loop(void)`:
```
4bcd:01ce("TAPES\\DEMO*.VCR")                     // list into _files_.out
n = 5155:0207()                                   // valid demo films
if n == 0: return
copy every unmarked 32-byte record of _files_.out (DS:4032 path, fallback plain; "rb")
  into ___demo_.out ("wb"); fatal "vcr_demo.c" B5h if either open fails; fatal BCh if the count != n
i = 0
loop:
    f = fopen(DS:4032 + "___demo_.out", "rb") (fallback; fatal C8h)
    fseek(f, i*32); fread(rec, 32); fclose
    i = (i + 1) % n
    name = 368f:02e6(rec, "VCR")
    if !5d56:00c2(): break                         // title screen, key → stop
    if !5d56:004b(name): break                     // play the film, key → stop
unlink("___demo_.out")
```
`5d56:00c2 int demo_title(void)` → 1 = no key: draw page DS:26D2; `4b9e:0000` (debug stub); load
`DEMO.SCR` (`715b:0000`, fatal 86h) and `DEMO.PAL` (`1d32:3e0b`); `368f:01a3`; set palette
(`1d32:400e`); `368f:017f(4)`; DS:31E5 = 1D8h (472 PIT ticks ≈ 2.0 s); wait while the countdown runs
(`368f:00b7`) and no key (`606e:0208`); free the palette; return !key.
`5d56:004b int demo_play(char *name)` → 1 = no key: `4b9e:0000`; `4e0d:03d9`; DS:4E20 = 2; director off
(`5d3c:0084(0)`); `5c5f:0298(name)` (load + world init + prime); `5b93:00f1` (no panel); `0000`
(fade-in once); loop: end = `5b93:0436()`; `5b93:0406()`; key = `606e:0208()`; until key or end.
Sound off `5a75:0e96`; `5c5f:0378(1)` (close, teardown, free mission). Return !key.
**No frame pacing** (as in §9.3).
`5d56:0000 void demo_fade_once(void)`: once (DS:0A0C): if !`50c8:0000()` and DS:26DF: `368f:01a3`,
`368f:03ed`, `368f:03b6`, `368f:01f2`, and if DS:408A (far palette) `1d32:400e(DS:408A)`. (Called by
the session driver before flying/VCR too; likely the first-time palette setup after the shell.)

---

## 13. Determinism — what the port must reproduce

Playback is re-simulation, so every input of the sim must be identical to the recording:

1. **Initial state.** `4e0d:03e9` (world init) runs before recording and before every playback /
   rewind. It seeds both lagged-Fibonacci RNGs (`1889:0002` on DS:4454 and DS:43DE) from the constant
   table at far 3A60:0000 (56 words, indices 18h/37h) — so the RNG sequence is a pure function of the
   frame history. The mission comes from the film's embedded script; SIM.IN (13 bytes), realism
   (DS:42C8, header +06) and prefs slider 0 (header +04) come from the header. `4e0d:03e9` also resets
   the mission clock (`5c5f:0083` → `4ca7:0000`), control state (`5f2c:0c11`), dt (`362b:002d`) and the
   VCR counters (`5b93:0000`).
2. **Per-frame input.** Only the 20-byte control record (§4.1) reaches the sim; the fields +06, +0A,
   +0C are not recorded, so the sim step must not depend on them (hand-off). Nothing else read by
   `5440:1317` may come from live input during playback (`5b93:0153` lets the input poll know).
   Data blocks re-apply mid-flight realism/prefs/map changes at the same frame.
3. **Time base.** dt of frame N+1 = `362b:008f(ticks_N · 4)` where ticks_N = (elapsed PIT ticks of
   frame N) >> 2 is recorded; playback calls the same function with the recorded value. The
   conversion depends on the current time-scale (slider), which is restored from the header / data
   blocks. The mission clock DS:4086 advances by dt, so it replays exactly. **The port must derive dt
   exclusively from this quantised tick count (a multiple of 4 PIT ticks at 1193182/5040 ≈ 236.7 Hz)
   in both live flight and playback**, never from wall-clock floats, and must feed the recorded value
   unchanged when playing.
4. **Frame counter.** `5d3c:0064` gives the AI (`4edf:068a`) and views the frame number (DS:0887 while
   flying/recording, DS:4E3B while playing); both are 0 at world init and increment after the step.
5. **Rendering must not influence the sim.** Playback skips drawing (FF: 11 of 12 frames; blank FF and
   seek: all frames) and the user may change cameras. Therefore the draw path (`5440:018c`) must not
   consume the sim RNG or change sim state, and camera-dependent culling in the effect pool `05a9`
   (updated from the sim step) must not feed back into the sim (hand-off to render3d / sim_world).
6. **Enter Simulation** continues from the replayed state with live input; the director film just
   continues recording, and the frame counter continues (DS:0887 = DS:4E3B).

Frame pacing: the original recording loop waits ≥ 8 PIT ticks per frame (or exactly 25 with DS:0530);
playback has **no wait** at all (runs as fast as the machine draws; on 1992 hardware roughly real
time). The port should pace playback to the recorded tick count (§15).

---

## 14. Data: globals (DS offsets) and structures

VCR state (DGROUP; initial values from the image):

| DS | Type | Name | Meaning |
|---|---|---|---|
| 0886 | u8 | vcr_recording | 1 = the flight loop records frames (init 1) |
| 0887 | u32 | vcr_frames_flown | frames simulated in the flight loop (reset by `5b93:0000`) |
| 088B | u8 | vcr_director | director mode (init 1; mirror of 092D..092F) |
| 088C | u8 | — | cleared by `5b93:0000` |
| 088D | u8 | vcr_slider_shift | halvings to fit the frame count into the slider |
| 088F | QUEUE (6×10) | vcr_events | panel event queue (+0 size 6, +1 cap 10, DS:0891 read, DS:0892 write, data 0893..08CE) |
| 08D5 | u8 | vcr_panel_shown | |
| 08D6 | near ptr | vcr_preset | active camera preset (re-applied each frame) |
| 08D8..0917 | VIEWREC[8] | vcr_presets | `{0,2,−7,0} {0,2,7,0} {0,2,0,−7} {0,2,0,7} {0,3,−7,0} {0,3,7,0} {0,3,0,−7} {0,3,0,7}` |
| 0918 | VIEWREC | vcr_view_base | zero |
| 0920 | VIEWREC | vcr_view_enter | `{1Ch,0,0,0}` (view applied on Enter Simulation) |
| 0928 | u8 | — | redraw requested by a camera button |
| 0929 | u8 | — | preset just started |
| 092A | u8 | — | flag of `074b` |
| 092B | u8 | vcr_ignore_film_views | set once the user edits views |
| 092C | u8 | vcr_director_request | applied by `5b93:045a` |
| 092D | u8 | vcr_record_views | (init 1) |
| 092E | u8 | vcr_rerecord | copy frames into the director film (init 1) |
| 092F | u8 | vcr_director_film | write `_tape_.tmp` while playing (init 1) |
| 0930 | u8 | vcr_modified | film edited |
| 0932 | char[] | "sim.in" | |
| 093C | u8[4] | vcr_initial_state | `01 01 00 04` |
| 09B2.. | u8 lists | panel button id lists | 09B2 master (20), 09C7/09C9/09D3/09D6 view-dependent, 09D9/09DB/09EB/09FE/0A02/0A07/0A09 per mode |
| 0A0C | u8 | demo_faded | |
| 0AA0 | char[11] | seek target text | |
| 0AB8 | u8 | vcr_modal_depth | |
| 0ABE | s32 | panel_time_shown | FFFFFFFFh initially |
| 0ACB | char[9] | panel time "00:00:00" | template at 0AC2 |
| 0AE0 | char[] | view name text | |
| 0B40..0B48 | | list box state (§11.2) | |
| 0BD6 | u16 | bit buffer size | 200 |
| 0BDA | u16 | tape_path rotation | |
| 0BDC | u16 | module flag accumulator | |
| 0C78 | u16 | write cache size | 3E80h |
| 0C7A | u8[8] | bit masks | 01..80 |
| 0100 | u16 | read cache size | 3E80h |
| 19EE | u8 | panel polling on | |
| 19EF | u8 | panel refresh forced | |
| 3CDA | BSTREAM[2] | bit streams | |
| 4DE6 | u16 | vcr_ui_mode | |
| 4DE8 | u8 | fullscreen_playing | |
| 4DE9 | CTRL (20) | vcr_ctrl | control record for the next playback step (4DFB = ticks) |
| 4DFD | u16 | vcr_priming | 1 while `0475` primes |
| 4DFF | u16 | vcr_redraw | full redraws pending |
| 4E01 | u8 | vcr_review | write SIM.IN back at exit |
| 4E04 | char[] | vcr_tape_name | current film |
| 4E1A, 4E1C | u16, u32 | — | reset by `5b93:0000`; 4E1C = 30000 by `5c5f:0083` (lead) |
| 4E20 | u8 | vcr_session_mode | set to the sim mode by `5c9b`; 2 = VCR playing (`5b93:0bf1`, `5d56:004b`), 0 = flying (`5cde:0405`) |
| 4E21 | u8[13] | film SIM.IN copy | written back by `5c5f:002a` |
| 4E2E | u8[13] | SIM.IN | |
| 4E3B | u32 | vcr_frames_played | |
| 4E40, 4E86, 4EB2 | char[] | name buffers | |
| 4E58 | char[] | tape to return to after Enter Simulation | |
| 4E76/4E7A/4E7E/4E82 | s32 | seek step, done, total, target | |
| 4EC8 | char[] | panel title | |
| 4EF0 | char[] | edit field | |
| 4EFB..4F05 | | list box | |
| 4F08 | u8 | dialog redraw flag | |
| 4FA8 | char[4][22] | tape path buffers | |
| 5000..500E | tab* | HUF tables | §3.4 |
| 5010 / 5014 | far ptr / u16 | script / length | |
| 5016 / 5018 | BSTREAM* / char[] | write stream / name | |
| 502E | BSTREAM* | read stream | |
| 5030/5034, 5038/503C | far ptr, u16 | read / write bit buffers | |
| 5040 / 5042 | u16 | previous ticks (decoder / encoder) | 0Fh at start |
| 5044 / 5046 / 5048 | near ptr / u16 / u16 | decode buffer / size / last length | |
| 504A..508B | HEADER | header being written | 5060 frames, 5064 clock, 506E SIM.IN+reserved |
| 508C..50CD | HEADER | header read | 50A2 frames, 50A6 clock, 50B0 SIM.IN |
| 519E..51A8 | | Huffman decode state | |
| 51EC | u16 | add-on 1 flag | SIM.IN+7 bit 0 |
| 5E04 | u8 | panel first poll | |
| 5E05 / 5E0D | u8[8] / u8[25h] | last mouse / input snapshots | |

Structures: `CTRL` (§4.1), `VIEWREC` (§4.2), film `HEADER` (§2.1), `BSTREAM` (§3.2), Huffman table and
node (§3.4), `QUEUE` (§9.7), panel event `{u16 type, u16 view_key, u16 esc}`.

---

## 15. Port notes

* `/* PORT: */` **bit streams**: replace `48c7`/`63ed` (EMS cache, 200-byte buffers, `_files_`
  style fopen per block) with a buffered file bit reader/writer keeping the exact bit order (§3.1) and
  the "short read leaves the destination unchanged" behaviour. The file bytes must be identical.
* `/* PORT: */` **playback pacing**: the original plays films without any wait. The port should wait
  per played frame until `ticks·4` PIT periods (1/236.7 s each) have elapsed since the previous frame
  (the recorded pace), in modes play (1), full-screen playing (8) and demo; FF/seek stay unpaced.
  Optional speed multiplier. This does not affect the simulation.
* `/* PORT: */` **live frame pacing** (lead's loop): keep the quantisation `ticks = elapsed >> 2`,
  `dt = 362b:008f(ticks·4)`, minimum 8 PIT ticks (≈ 29.6 fps cap) and the 25-tick fixed mode; derive
  "elapsed" from a 236.7 Hz virtual PIT counter. Clamp a frame to < 512 PIT ticks (the original's
  countdown) so ticks stays < 128 and remains encodable.
* `/* PORT: */` close (commit or abort) the temp film on END MISSION instead of leaking the write
  stream (§6.1) — optional; faithful behaviour leaves a 0-byte `_TAPE_.TMP`.
* `/* PORT: */` `36ee:0003`: compute real free space (64-bit), clamp to 7FFFFFFFh (the 16-bit
  products overflow on modern disks and can trigger the "less than 30K" warning spuriously).
* `/* PORT: */` `51e7` queue: keep the original index arithmetic (the full-state bug only matters
  with 10+ unread panel events).
* The Huffman tables must be built exactly as `4d15:03e4` does; the eight `.HUF` files ship in SIM2.
  Porting tip: verify with `vcrdump.py` that the four demos decode to END at the file's last byte and
  that the port's encoder reproduces the demo bytes from the decoded records.
* The panel (VCR.BOX, 38E6 item list) and list boxes use the dialog library (`46de`, `47a8`, `53a6`,
  `6396`, stdalert `6210`), specified by another writer.

---

## 16. Hand-offs

* **Lead (`sim_flow.md`, flight loop / time base / controls):**
  - `5cde:0405` must record exactly as in §7 (control record after the step with ticks = elapsed>>2,
    view record when `1c30:09d9` fired, END when the mission ended and the 4000-dt countdown hit 0 or
    on abort/quit via `5cde:0080`), and set DS:5060 = DS:0887, DS:5064 = `4ca7:0045()` on exit.
  - `5cde:0080` records data blocks: subtype 1 after `6b4d:0f95` (prefs), subtype 0 after
    `606e:0137` (realism), subtypes 2/3 for the in-flight map (`6cdc`) — only when DS:0886.
  - `5f2c:05d1` must produce control values inside the Huffman alphabets (stick −32..31, rudder
    −16..15, buttons 1..15, command 0..127, throttle +8 = −1 or 0..127, +9 = 0 or ±1..±8); the step
    `5440:1317` must not read the unrecorded fields +06, +0A, +0C (or they must be derived).
  - `60a9:02c4` consults `5b93:0153` (playing) — document what it suppresses.
  - `4e0d:03e9` calls `618d:04e4(0)`, `5b93:0000` and `5c5f:0083`; `17fe:000b` / `496a:160c` call
    `618d:04e4(bits)` whose result is discarded (flags never stored).
  - main: return value of `5c9b:0000` (1 normal, 0 aborted/exit) and `sim_exit`.
* **render3d:** the draw path (`5440:018c`, effects `05a9`, `1560:06e9`) must not use the sim RNGs
  (DS:4454, DS:43DE) or alter sim state; playback skips draws and changes cameras freely.
* **sim_world:** AI `4edf:068a` reads the frame counter through `5d3c:0064`; `6a63:0000` (DS:51EC,
  add-on flag) is read by `0deb:060d`, `0deb:13ac`, `1142:0ba7`, `1660:07bb`.
* **Dialog library writer:** VCR panel = `VCR.BOX` loaded by `5c5f:00bd` into 38E6:0025 (37 items),
  tape menu `tapes.BOX` (38E6:0343, 6 items), list box `lbox.BOX` (3934:?, 0Bh items); callbacks in
  `5ea5` and `5fef` (§10, §11.2) are reached through the `3dab`/`3dbd` stub tables.
* **formats (data.md §5):** superseded by §2 here (header fields, module block, event stream).

---

## 17. Open questions

* Exact meaning of control fields +0E (button bits) and +10 (command codes), and of view +00/+02 — they
  are defined by the lead's `5f2c`; the codec here is exact regardless.
* Slider 0 = time scale? (header +04 = 50 in all demos; applied through `4b9f:0000`.)
* DS:19F2 meaning (camera/ejected flag) — affects only camera buttons.
* The dialog item offsets used for "dirty" marks in 38E6 (bytes set to 43h) belong to the dialog
  library's item layout.
* `5d56:0000` / `50c8:0000`: exact purpose of the one-time fade (palette DS:408A).
