# Resources: Dynamix Volume Files, tagged chunks, compression, pictures

Addresses are INTRO.EXE `SSSS:OOOO` (file segments as in `port/intro_functions.csv` /
`work/intro_segmap.txt`; `volume.c` = segment `049D`, DGROUP = `17E0`). PS.EXE and AP.EXE carry the
same `volume.c` (source paths `f:\s\sys\volume.c`, `d:\aces1946\code\sim\s\b\volume.c`).
Tags: **Verified** = read in the code and/or decoded consistently over every entry of every volume
(and pictures checked by eye); **Likely**; **Unknown**.

Tools: `tools/dynvol.py` (volumes), `tools/dynchunk.py` (chunks, decompression),
`tools/dynimg.py` (palettes, bitmaps, screens, fonts → `work/img/`), `tools/dynsurvey.py`
(entry-type table).

## 1. Dynamix Volume File `*.DYN` (Verified)

All little-endian. Seven volumes, 1612 entries, 1599 distinct names.

| Offset | Type | Field |
|---|---|---|
| 00 | char[20] | `"Dynamix Volume File\0"` |
| 14 | u16 | `001A` (^Z). The open routine reads 16h bytes (20 + these 2) into `DS:0794` and `strcmp`s with `"Dynamix Volume File"` |
| 16 | u16 | flags: bits 13–15 volume class, bits 0–11 product id (1) |
| 18 | u16[4] | hash keys (rotate counts), copied to the volume record |
| 20 | u16 | entry count *n* |
| 22 | u16 | 0 — padding: the reader seeks forward one byte at a time until `ftell % 4 == 0` |
| 24 | u32[n] | directory, in file order: low word = name hash, high word = *delta* |
| … | | entries, each at a 4-byte boundary, zero bytes between (0–3) |

Entry: `char name[13]` (NUL-padded 8.3 name), `u32 size`, `u8 data[size]`. The next entry starts at
the next multiple of 4; the file ends at the last entry's end rounded up to 4.

Entry offset: `off[i] = 4 * Σ_{j ≤ i} delta[j]` (the first delta counts from the file start, e.g.
M1CMN: delta 0016h → P80.TBL at 58h, next delta 07D6h → F8F.TBL at 58h + 1F58h = 1FB0h). These
"unexplained 2 bytes between entries" are this 4-byte alignment.

| Volume | Flags | Keys | Entries | Contents |
|---|---|---|---|---|
| COMMON1 | E001 | 1,1,2,2 | 110 | fonts, `ACES/CLOUDS/FLTMAP.PAL`, `SHADES.DAT`, 3D shape tables `.TBL`, `TARGET.n`, name lists `.TXT` |
| SHELL1 | 4001 | 1,4,1,4 | 360 | shell screens/pictures/palettes, `.SCD` menus, `.TTM` scripts (intro, awards, newspapers), text tables `.DAT`, missions `MISS*.DAT`, `SHELL.SX`/`TTD.SX` sounds, `VMCODE.OVL`, `SXCODE.OVL` |
| SIM1 | 8001 | 1,1,3,7 | 500 | cockpit art + `.TTM` cockpit scripts, `.BMD` effects, `.BXL/.DMG` per model, world `AW*.WD3/.MBL/.FLT`, `.BOX/.BL/.BND` sim UI, `.WND` wind, `.MEC` weapons |
| SIM2 | 8001 | 1,1,2,2 | 392 | `.EDG`, `.GL/.GLT`, `.GAU` gauges, `.FMD`, `.PLT` pilots, `.HUF`, `SIMSNDS.SNG`, `SX.OVL`, `VMCODE2.OVL` |
| M1CMN / M1SHL / M1SIM | E001 / 4001 / 8001 | … | 13 / 110 / 135 | "1946" add-on (WWII: 1946): P-80, F8F, F7F, F2G, Ki-83, Kikka, J7W; `AW11`, `INTACE3x` intro, war-end screens |

Flags: COMMON = E001, shell volumes 4001, sim volumes 8001. The volume scan (`049D:0C50`,
`findfirst("*.DYN")`, at most 10 volumes) passes a mask (default 2001 when the caller passes 0);
`049D:0A2C` opens a volume only if `(flags & mask) & F000` and `(flags & mask) & 0FFF` are both
non-zero. Which program passes which mask is not traced yet (INTRO's scripts are in SHELL1, class
4000, so INTRO must include 4000).

Two SIM1 entries have no extension and size 0: `12-12-91`, `9388` (date/build stamps).
21 names exist in two volumes (e.g. `W1.BMP`…`W10.BMP` in SHELL1 and SIM1, `CLOUDS.SCR`,
`FLTMAP.SCR` in SHELL1 and SIM2, `EMILY.TBL`, `ZERO_22.TBL`); the program opens the one of the
volume class it has loaded.

### Name hash (Verified, `049D:0E32`)

```
buf = strupr(strncpy(basename(name), 13)); len = strlen(buf)
h = 0 (u32)
for i in 0..12:  h = _lrotl(h, keys[i % 4]) ^ (i32)(i8)buf[i % len]     // 0000:0996 = _lrotl
hash = (u16)(h % 0x1003F)                                               // 0000:065C = LUMOD
```

Every one of the 1612 stored hashes matches (`dynvol.py check`); no collisions inside a volume.

### Lookup and reads (Verified)

`my_fopen` (`049D:00BB`): if no volume is open, a plain `fopen`. Otherwise tries the current volume,
then the others, alternately above and below the current index (Likely), each with `049D:0E32`: walk the directory,
summing deltas, stop at the **first** entry with a matching hash; seek there, read the 13-byte name
and the u32 size, and `stricmp` the stored name with the base name; a mismatch counts as "not in
this volume". The per-open record keeps volume index, entry data offset, size and position;
`my_fread` (`049D:0411`) / the huge read `049D:04F4` clamp reads to the entry size. Not found in any
volume → falls back to opening the name as a plain file (Likely; not traced).

Volume record (26h bytes, far array at `DS:2520`, count `DS:251E`): +00 file name[14], +0E index,
+10 FILE*, +12 u32 current file position, +18 keys[4], +20 entry count, +22 far pointer to the
directory (u32[n]).

## 2. Tagged chunks (Verified)

Most entries are a list of chunks, as in DGDS (ScummVM `dgds`):

| Offset | Type | Field |
|---|---|---|
| 0 | char[4] | tag, three characters + `:` (`BMP:`, `INF:`, …) |
| 4 | u32 | bit 31 = container (payload is again a chunk list); bits 0–30 = payload size |
| 8 | u8[size] | payload |

Chunk lists fill their parent exactly (every chunk entry of every volume parses without leftover).
Tags are only meaningful with their parent: `BMP:{INF: BIN: VGA:}` etc. The executables look chunks
up by the 8-character path string, e.g. `"PAL:VGA:"`, `"BMP:SCN:"` (`DS:1ADE`), `"SCR:VQT:"`.

Example `SHELL1:ACE2.BMP` (entry data at 0DF8F0h + 11h):

```
000000 BMP: 80004C42 {                       container, 19522 bytes
  000008 INF: 30          07 00 | 48 00 ×7 | 3C 00 ×6 3B 00     7 frames, widths, heights
  00002E BIN: 15990       02 | EC 3A 00 00 | LZW …             packed, method 2, 15084 bytes
  003EAC VGA: 3478        02 | EC 3A 00 00 | LZW …
```

### Packed chunks (Verified)

Payload = `u8 method`, `u32 unpacked size`, packed bytes. Which chunks are packed is fixed by the
tag path (no flag): `BMP:BIN:`, `BMP:VGA:`, `SCR:BIN:`, `SCR:VGA:`, `TT3:`, `SSM:SNG:`, all
`OVL:xxx:` and the `SSM:` driver chunks (`M32 NLD ADL TAN PS1 STD 001 003 101`). Inside other
payloads the same 5-byte header appears: `FNT:` (proportional fonts, at +8) and `SND:DAT:` (at +4).
Methods seen: **1 = RLE** (TT3, SSM:SNG, two SCR), **2 = LZW** (everything else). All 325 packed
chunks decode to exactly their stated size. (The decompressor itself is not yet located in the
code; the algorithm is DGDS's and is verified by the data.)

**RLE (method 1):** control byte `c`: `c & 80h` → the next byte repeated `c & 7Fh` times; else copy
the next `c` bytes.

**LZW (method 2):** codes LSB-first, 9 bits growing to 12; dictionary = 256 literals, first free
code 101h; code 100h = clear (back to 9 bits, free = 101h, next code is a literal). The width grows
when `free` reaches `1 << bits` (up to 12 bits, dictionary full at 4096 = no more entries).
Quirk (DGDS): codes are consumed in groups of 8 — a group of 8 *b*-bit codes is *b* bytes — and
on a clear the rest of the current group is skipped; the group count restarts at every width
change. KwKwK (code = free) handled as usual. No end code: stop at the unpacked size.

## 3. Palettes `.PAL` (Verified)

`PAL:{VGA:}` — 768 bytes, 256 × R,G,B, 6-bit (0–63; shown ×255/63). Four intro palettes
(`INTACES`, `INTDYNA`, `INTFLY1`, `INTQUOTE`, 1075 bytes) also have `EGA:` (17 bytes: 16 EGA colour
indices + 1, probably the overscan colour) and `CGA:` (258 bytes, layout Unknown: perhaps a 2-byte CGA palette selection + a 256-byte VGA→CGA colour map).
55 palettes; the cockpit scripts load `COCPAL.PAL`, `COCKPIT.PAL`, `GUNPAL.PAL`, which are in no
volume (built by the sim at run time, Likely); `SIM.PAL` (SHELL1) fits the cockpit art.

Which palette goes with which picture: the TTM scripts name them (`TT3` opcode F05Fh + palette
name, F01Fh + bitmap name, F02Fh + screen name — DGDS TTM opcodes). `dynimg.py` takes the palette
named last before the picture in any script, then the same base name (`FLTDK0.SCR`↔`FLTDK0.PAL`),
then the longest palette name that prefixes the picture name, then a small override table (portraits
`ACE*.BMP` → `DOGACE.PAL`, `OFFICERS.BMP` → `BRIEF.PAL`, `MT_HIST.BMP` → `FLYHIST.PAL`, `INT46J.BMP`
→ `INT46.PAL`, flags → `AWRDCFG.PAL`), else `ACES.PAL` (shell) / `SIM.PAL` (sim volumes).

## 4. Bitmaps `.BMP` (Verified)

`BMP:{INF: …}`. `INF:` = `u16 n`, `u16 width[n]`, `u16 height[n]` (frames). Then one of three
pixel encodings (229 bitmaps: 135 VQT, 70 nibble planes, 22 SCN, 1 `INF:+BIN:` only, 1 with an
extra empty `SCL:`):

### 4a. Nibble planes `BIN:` + `VGA:` (70)

Both packed; each holds 4 bits per pixel, two pixels per byte, first pixel in the **low** nibble.
`BIN:` = low nibbles, `VGA:` = high nibbles of the 8-bit colour. The frames are concatenated
pixel-wise (frame k starts at pixel Σ w·h of the previous frames, row-major). `ACE2.BMP`: 7 frames
72×60/72×59 → 30168 px → 15084 bytes per plane. (A BMP with only `BIN:` — one of the 71 —
is drawn with the low nibbles only: `SIM1:EALERTS.BMP`.)

### 4b. VQT `VQT:` + `OFF:` (135), also `SCR:VQT:` (30 screens)

A bit stream (LSB-first within little-endian 16-bit reads) coding each frame as a quadtree:

```
node(x,y,w,h):  if w==0 and h==0: return
    m = bits(4)
    for (bit, quadrant) in (8: TL w/2×h/2, 4: TR (w+1)/2×h/2 at x+w/2,
                            2: BL w/2×(h+1)/2 at y+h/2, 1: BR (w+1)/2×(h+1)/2):
        (node if m & bit else leaf)(quadrant)
leaf(x,y,w,h):  if w==0 or h==0: return;  if w==h==1: pixel = bits(8); return
    size = (w & FF)*(h & FF); b1 = 8 if size >= 256 else max(1, bitlen(size-1))
    k = bits(b1); b2 = bitlen(k); ncol = (k+1) & FF
    if size*8 <= size*b2 + ncol*8: size raw bytes bits(8), column-major (x outer, y inner)
    elif ncol == 1: fill with bits(8)
    else: table[ncol] = bits(8) each; then per pixel (x outer, y inner) table[bits(b2)]
```

`OFF:` = `u32` byte offset of each frame in `VQT:`, or the single word `FFFF` = frames follow each
other, each starting at the next byte boundary after the previous frame's last bit (checked: all
FFFF bitmaps end exactly at the chunk end, e.g. `INTA546.BMP` 171 frames = 32527 bytes).
`SCR:VQT:` is one 320×200 frame at bit 0. The loader (`0EAD:0002`) looks for `BMP:SCN:` first,
then `BMP:OFF:`/`BMP:VQT:`, and marks the frames' length field −2 (SCN) or −1 (VQT).

### 4c. SCN `SCN:` + `OFF:` (22, cockpit wings/tails/sights)

`OFF:` = u32 byte offset per frame. Frame = `u8 base`, then ops, pen at (0,0)
(draw routine `05DA:1E3C`, entered via `05DA:1E38`):

| Byte | Meaning |
|---|---|
| `00nnnnnn` | next line, x −= n; if the following byte is `00mmmmmm` with m ≠ 0 it is consumed too: x −= 64·m |
| `01000000` | end of frame |
| `01nnnnnn` | skip n (transparent) |
| `10nnnnnn` v | run of n pixels of colour base + v |
| `11nnnnnn` … | n pixels, 4 bits each, **high nibble first**, colour base + nibble; (n+1)/2 bytes |

The caller (`11D2:0148`) overwrites the base byte with its colour argument before drawing, so
the stored base (4, 8, 9, …) is only a default: the sim tints wings/tails at run time. Flip flags:
bit 0 = draw bottom-up, bit 1 = right-to-left. Example `SIM1:WING2.BMP` frame 0 (144×53): `04`
base, `70` skip 48, `8A 08` 10 × colour 0Ch, `C7 77 67 67 60` 7 literal pixels, `19` next line x−=25 …

## 5. Screens `.SCR` (Verified)

`SCR:{VQT:}` (30, 320×200 VQT) or `SCR:{BIN: VGA:}` (5, 320×200 nibble planes, 32000 bytes each:
`INTCLDS`, `INTDYNA` (SHELL1), `FLTMAP`, `DEMO`, `CLOUDS` (SIM2)). No size header: always 320×200.

## 6. Fonts `.FNT` (Verified)

`FNT:` payload, first byte selects the kind:

| Kind | Layout |
|---|---|
| `FF` proportional 1 bpp (FONT1–4, TALK, PAPER) | `FF, maxw, h, baseline?, first, count, u16 packed size`, then `u8 method, u32 size` + packed data = `u16 offset[count]`, `u8 width[count]`, glyph bits (per glyph h rows of ⌈w/8⌉ bytes, MSB = leftmost) |
| `FD` proportional 8 bpp (NP_HDLN, NP_TXT, SIMQ_HDL, SIMQ_SML — newspaper / sim-quit screens) | same header; glyph = h rows of w bytes (colour indices 0 = transparent, anti-aliased shades) |
| other: fixed 1 bpp (AJPAPER) | `w, h, first, count` (count 0 = 256?), then count × h × ⌈w/8⌉ bytes |

FONT1/FONT2 contain only digits and capitals (HUD/cockpit fonts); FONT3 starts at 0 with 218
characters, 8 px high.

## 7. Other chunk formats (structure only, see FORMATS.md survey)

* `TTM` = DGDS TTM scripts: `VER:` `"4.09"`, `PAG:` u16 page count, `TT3:` (RLE) opcodes
  (u16 opcode, low nibble = argument count, `F` = string argument), `TTI:{TAG:}` scene names.
* `SX` = `SND:{INF: TAG: FNM: DAT:×n}`: `INF:` u16 ver?, u16 n, u16 ids[n]; `TAG:` u16 n,
  (u16 id, name)…; `FNM:` source file names (`SFX\M_SELECT.SND`); `DAT:` = u16 id, u16 flags, then
  packed (5-byte header) SCI1-style sound resource (below).
* `SNG` = `SSM:{SNG:×n INF:}`: RLE-packed sound resources: `84 00`, then per device a device byte
  (00, 09, 0C, 12, 13 — SCI1 device ids: AdLib, …, MT-32, PC speaker, Tandy), 6-byte channel
  entries (u16, u16 offset, u16 size), `FF`.
* `SXCODE.OVL`, `SX.OVL`, `SX1.OVL` = `SSM:{M32: NLD: ADL: TAN: PS1: STD: 001: 003: 101:}`:
  LZW-packed Sierra SCI sound drivers (`E9 …`, `87654321h` signature, `"dude"` / `"tnddrv"`,
  `"Roland MT-32, MT-100, LAPC-I, CM-32L…"`).
* `VMCODE.OVL` = `OVL:{VGA: EGA: MCG: CGA: TAN: HEG: EVG: EVA:}`, `VMCODE2.OVL` = `OVL:{VGA:}`:
  LZW-packed video driver code (real-mode, `55 8B EC …`), one per adapter.
* `.TBL` = `MAP: APP: GID: DAT:` (3D shape tables, see FORMATS.md), `TARGET.n`/`CARRIER.n` =
  `INF: DAT: TAG:`, `.BMD` = `VER: EXT: PRF: BMD:`, `.WD3` = `WD2:{WHD: OB0: MBL:}`.

## Open questions

* Which mask each program passes to the volume scan; the exact meaning of classes 2000/4000/8000.
* The in-code LZW/RLE decompressor (addresses) — the algorithm is confirmed by the data only.
* `PAL:CGA:` layout; `FNT:` header byte 3 (baseline?).
* Palettes for a few bitmaps not named by any script (`ACE4.BMP`, `JAPFLAG/USAFLAG.BMP`,
  `SIMQ_CH.BMP`, `FORMPLNS.BMP`): best guesses only. Cockpit art uses run-time palettes.
