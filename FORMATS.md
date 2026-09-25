# Aces of the Pacific (1992, Dynamix; CD 1.2) — file formats & internals

Addresses as in `port/RE_GUIDE.md` / `port/*_functions.csv` (`SSSS:OOOO` file segments of the
unpacked image; INTRO.EXE unless stated, DGROUP `17E0`).
Status tags: **Verified** (decoded and checked visually or byte-exact), **Likely**, **Unknown**.

## Tools (run from the repository root; Python 3.12 + Pillow, capstone for `x86dis.py`)

| Tool | Does |
|---|---|
| `tools/dynvol.py list [VOL.DYN…]` / `extract VOL.DYN [dir]` / `all` / `check` | Dynamix Volume File directory; extraction to `work/dyn/<vol>/`; `check` verifies every hash and the layout |
| `tools/dynchunk.py tree VOL.DYN NAME` / `dump VOL.DYN NAME [dir]` / `check` | tagged chunk tree of an entry (or of an extracted file); leaf chunks decompressed to files; `check` unpacks all 325 packed chunks |
| `tools/dynimg.py all` / `one VOL.DYN NAME [PAL]` | palettes, bitmaps (all frames), screens, fonts → `work/img/<vol>/*.png`, contact sheets `work/img/<vol>/sheet_{pal,bmp,scr,fnt}.png`, `work/img/report.txt` (encoding + palette used per picture) |
| `tools/dynsurvey.py [EXT]` | table of all entry types (below) / every entry of one extension with its first bytes |
| `tools/x86dis.py EXE dis SSSS:OOOO LEN` | disassembly (used for the volume and SCN code) |
| `tools/rawdis.py FILE [start len]` / `EXE SSSS:OOOO len` | linear disassembly with resync, for raw drivers (origin 0) and MZ images |
| `tools/dynshape.py list [TBL…]` / `dump TBL [SHAPE]` / `render TBL [SHAPE] [--yaw --pitch --lod --state --wire --top]` / `sheet` / `check` | 3Space shape tables → structure dumps, PNG renders `work/shapes/`, sheets `work/shapes/sheet_{aircraft,ships,misc}.png` |
| `tools/dynworld.py list` / `dump AREA objects\|mbl\|macros` / `targets AREA` / `flt AREA` / `render AREA [--zoom X,Y,HALF] [--labels]` / `all` | world areas (WD3 + MBL macros + TBL + TARGET/CARRIER) → dumps, top-down maps `work/world/AW<n>.png`, `work/world/sheet.png` |
| `tools/dynttm.py all` / `dis FILE.TTM` / `ops` | TTM scripts → disassembly per frame `work/ttm/<vol>/<NAME>.TTM.txt`, opcode usage `work/ttm/_opcodes.txt` |
| `tools/dyndata.py all` / `one FILE` | missions, SIM.IN/SIM.OUT, preferences, records, films, string tables, name lists, per-model sim data → `work/data/<vol\|game>/*.txt` |
| `tools/aotpsnd.py list` / `extract` / `dump BANK ID` / `dro [BANK [ID…]]` / `all` | sound banks → standalone SCI sound resources, patches, drivers (`work/sound/`); AdLib renders to DOSBox `.dro` through models of the game's SCI1 sequencer and AdLib driver |

Detailed format documents:

| Document | Covers |
|---|---|
| [port/formats/resources.md](port/formats/resources.md) | volume file layout and name hash, lookup, tagged chunks, RLE/LZW compression, palettes, BMP (nibble planes, VQT, SCN), SCR, FNT; structure of TTM/SX/SNG/OVL |
| [port/formats/shapes.md](port/formats/shapes.md) | `.TBL` shape tables: chunks, far-pointer list, shape header, LODs, parts (BSP-style sort, state variants), polygons, colours and shading (AP.EXE addresses) |
| [port/formats/world.md](port/formats/world.md) | `AW<n>.WD3` (WHD/OB0/MBL), `AW<n>.MBL` macros, `.FLT`, `TARGET.n`/`CARRIER.n`, `.BMD` structure |
| [port/formats/scripts.md](port/formats/scripts.md) | TTM scripts (layout, encoding, interpreter, opcode table, which script runs where), `.SCD` and text `.DAT` string tables |
| [port/formats/data.md](port/formats/data.md) | shell ⇄ sim hand-off (`SCRIPT.DAT`, `SIM.IN`, `SIM.OUT`), missions, `.PRF`, roster/records, `.EVT`, `TTMS0.DAT`, per-model sim data (`.PLT .GL .DMG .BXL .GAU .HUF …`), VCR films |
| [port/formats/sound.md](port/formats/sound.md) | SX/SNG banks, SCI1 sound resources, the SCI sound module (`1373`), driver loading and interface, the AdLib driver, renders |

## Game directory

See `PLAN.md` (recon table). Game data other than the drivers, preferences, rosters and films is in
seven **Dynamix Volume Files** (`*.DYN`, 5.5 MB, 1612 entries).

## Volumes (Verified, resources.md §1)

`"Dynamix Volume File\0"`, `u16 1Ah`, `u16 flags` (class E000/4000/8000 + product 1), `u16 keys[4]`,
`u16 count` (+2 pad), `u32 dir[count]` (lo = name hash, hi = distance from the previous entry in
dwords), then entries `name[13], u32 size, data` at 4-byte boundaries. Name hash: 13 rounds of
`h = rotl32(h, key[i&3]) ^ (signed char)NAME[i % len]`, result `h % 1003Fh` (`049D:0E32`).

| Volume | Class | Entries | Holds |
|---|---|---|---|
| COMMON1 | all | 110 | fonts, main palettes, 3D shape tables, targets, name lists |
| SHELL1 / M1SHL | 4000 | 360 / 110 | shell & intro: screens, pictures, menus, scripts, texts, missions, sounds, video drivers |
| SIM1, SIM2 / M1SIM | 8000 | 500, 392 / 135 | simulator: cockpits, effects, worlds, flight/damage/gun data, pilots, sound |
| M1CMN | all | 13 | add-on (1946) shape tables and name lists |

`M1*` = the "WWII: 1946" add-on (P-80, F8F, F7F, F2G, Ki-83, Kikka, J7W, area `AW11`).

## Chunks and compression (Verified, resources.md §2)

DGDS-style chunks: `tag[4] ("XXX:")`, `u32 size` (bit 31 = container), payload. Packed payloads
(`BMP:BIN/VGA`, `SCR:BIN/VGA`, `TT3:`, `SSM:SNG`, `OVL:*`, `SSM:<driver>`, inside `FNT:` and
`SND:DAT:`): `u8 method, u32 unpacked size, data`; method 1 = RLE, 2 = LZW (DGDS variant: 9–12
bit codes, 100h = clear with skip to the end of the current 8-code group, first free code 101h).

## Pictures (Verified, resources.md §3–6)

| Kind | Encoding | Count |
|---|---|---|
| `.PAL` | `PAL:{VGA:}` 256 × 6-bit RGB (+ `EGA:`, `CGA:` for 4 intro palettes) | 55 |
| `.BMP` | `BMP:{INF: …}` frames; pixels as `BIN:`+`VGA:` nibble planes (70), `VQT:`+`OFF:` quadtree bit stream (135), `SCN:`+`OFF:` run/skip lines with a run-time colour base (22) | 229 |
| `.SCR` | 320×200, `SCR:{VQT:}` (30) or `SCR:{BIN: VGA:}` (5) | 35 |
| `.FNT` | `FNT:` FF = proportional 1 bpp, FD = proportional 8 bpp, else fixed 1 bpp | 11 |

All 229 bitmaps, 35 screens and 11 fonts decode; palettes are assigned from the TTM scripts
(F05Fh load-palette before F01Fh/F02Fh load-bitmap/screen), name matches and a short override list.
Good sheets: `work/img/SHELL1/sheet_scr.png`, `work/img/SHELL1/sheet_bmp.png`,
`work/img/SIM1/sheet_bmp.png`, `work/img/M1SHL/sheet_bmp.png`, `work/img/SHELL1/sheet_fnt.png`.
Cockpit art (SIM1/M1SIM `PANEL*`, `BACK*`, `SSTR*`, `WING*`, …) is shown with `SIM.PAL`; the game
loads `COCPAL.PAL`/`COCKPIT.PAL`/`GUNPAL.PAL`, which are in no volume (made at run time, Likely),
and tints `SCN` pictures with a caller-supplied base colour.

## 3D shapes `.TBL` (Verified, shapes.md; AP.EXE `ts_*.c` + asm core `277a`)

`MAP:` names, `APP:` per-shape (areas: kind + wreck shape), `GID:` per-shape ground data (Likely),
`DAT:` = zero-terminated list of normalised far pointers (`off, seg`, shape at `seg*16+off`; offsets
inside a shape are relative to `seg*16`). Shape: `u8 flags` (40h sort parts, 20h no box → 14-byte
header, 10h bitmap shape), `u8 class`, `u8 ?`, `u8 scale shift`, `u16 nstates, u16 ofs` (variants per
state slot), `u16 nlod, u16 ofs`, `u16 radius`, `i16 box[6]`. LOD = `u16 size, u16 nparts, u16 ofs`
(first with size ≥ apparent size). Part (14 bytes) = state slot, sort normal/point (BSP-like
descending sort), `nverts, u16 vofs`, `nvariants, ofs` (8-byte variants: 0 polygon list, 1 disc,
2 sprite), `nchildren, ofs`. Vertices `i16 x,y,z` (x right, y forward, z up; normals length 2048 in
the same array). Polygon (8 bytes) = flags (bits 0–1 cull mode, 20h shaded, 80h filled), VGA
edge/fill, EGA edge/fill, normal index, index-list offset (`FFh`-terminated). Shading via
`SHADES.DAT` (shades per colour) and an 8×32 offset table. All 112 tables / 1175 shapes parse; renders
`work/shapes/sheet_aircraft.png`, `sheet_ships.png`, `sheet_misc.png`.

## World areas (Verified, world.md)

`AW<n>.WD3` = `WD2:{WHD: OB0: MBL:}`: `WHD:` object counts per shape class; `OB0:` 26-byte static
objects (`flags, shape, i32 x,y,z, 3 × u16 angles`, heading at +14h); `MBL:` 22-byte instances of
macros (`type = 8000h + macro`, position, heading). `AW<n>.MBL` (SIM2/M1SIM) = macro definitions
(`name[8]`, members in the OB layout: airbase, harbor, city, jungle …). `TARGET.n` / `CARRIER.n` =
`INF: DAT: TAG:`: per id five date-keyed lists (positions, kind, state …; dates = days since 1900),
names in `TAG:`. `AW<n>.FLT` = 17 × 24-byte per-class detail/visibility records (Likely). Maps of
all areas: `work/world/sheet.png`, e.g. `work/world/AW9.png` (Hawaii), `AW1.png` (Japan).

## Sound (Verified, sound.md)

Sierra SCI1 sound system, linked and loaded unchanged: the sound module `midi.s` (INTRO `1373`, same
code in PS/AP) plays SCI1 sound resources through a Sierra "dude" driver loaded from an OVL.

* Banks: `SHELL.SX` (PS, 13), `TTD.SX` (INTRO, 20) = `SND:{INF: TAG: FNM: DAT:×n}`, DAT = `u16 id, u8
  priority, u8 flags (bit 1 loop)` + LZW resource; `SIMSNDS.SNG` / `SIMSNDS1.SNG` (AP, 35/38) =
  `SSM:{SNG:×n INF:}`, INF = n × (`u8 loop, u8 priority`). Resources = SCI patch header `84 00`, then
  per-device track lists (`u8 device`, 6-byte channel entries, `FF`); AdLib track 00 in every sound;
  channels = 2-byte header (channel|flags, voices|priority) + fixed preamble + MIDI events with
  delta bytes (`F8` = 240+), channel 15 = control (loop point `CF 7F`, signals, reverb). No samples.
* Timing: PIT 236.69 Hz (divisor 5041), sound service every 4th tick = **59.17 Hz**.
* Driver: `RESOURCE.CFG soundDrv` name → index → chunk `SSM:{STD,TAN,ADL,M32,…}:` of `SXCODE.OVL`
  (INTRO/PS) or `SX1.OVL` (AP), called in place, BP = function 0–17 (0 patch request, 1 init, 2 term,
  3 service, 4/5 note off/on, 7 controller, 8 program, 10 bend, 11 reverb, 12 master volume, 13 sound
  on, 17 query). Patch bank = chunk `SSM:003:` (SCI `PATCH.003`, 96 × 28-byte OPL2 instruments). The
  loose `*.DRV` files are only for the installer (ADL.DRV v2.24 is a different build).
* AdLib driver: 9 melodic voices owned by channels via ctrl 4Bh, oldest-voice stealing, quarter-tone
  frequency table, velocity/volume curves. `tools/aotpsnd.py all` renders all 106 sounds to
  `work/sound/<BANK>/*.dro`.

## TTM scripts (scripts.md §1)

`VER:` ("4.09" ×52, "4.08" ×11), `PAG:` u16 = number of frames, `TT3:` RLE-packed opcodes,
`TTI:{TAG:}` label names. Opcode word = operation (high 12 bits) + argument count (low nibble; `F`
= NUL-terminated string padded to even length; `AF1F/AF2F` = u16 n + n points) (Verified). A frame
runs up to `0FF0`; `1111 tag` labels frames for GOTO/GOSUB. Interpreter PS `3BAF:0540` = INTRO
`11D2:053F` (47 + 25 + 18-entry case tables), reduced copy in AP `2595:038B` (21 opcodes, no sound).
41 opcodes used: resources (`F01F` screen, `F02F` bitmap, `F05F` palette, `C02F` sound bank, slots
`1051/1061`), drawing (`A5x4..A5A7` sprites incl. flip/colour/scale/rotate, `A104` rect, `A002`
pixel, wipes), palette fades `4114/4124/4136`, delay `1021`, sound `C031/C051`. INTRO runs
`INTACE1–5`, PS the award/newspaper/war-end scripts (named by `EVENTS*.EVT` and `TTMS0.DAT`), AP the
85-frame `<plane>.TTM` cockpit builds.

## Shell ⇄ sim hand-off, missions (data.md §1–2)

PS writes the mission to **`SCRIPT.DAT`** (= format of `MISS0–73.DAT`, `TRN*.DAT`: u16 version 4,
then blocks `u16 type, u16 count` of records: 0 header 90 bytes, 1 aircraft 22, 2 ship 16, 4 place 10,
5 group 58, 7 waypoint 14/6, 8 message offset 2, 9 message text 1; all 94 files parse), then
**`SIM.IN`** (13 bytes: roster pilot, sim mode, mission type, area, name-list mask, sides, player's
aircraft type) and exits to AP. AP reads SIM.IN only for the mode (the shell re-reads it on return)
and writes **`SIM.OUT`** (36 bytes: fate code, flags incl. friendly-fire bits, 2 × 4 counters —
ground targets, ship hits, ships sunk, aircraft — for the player and the flight, score 0..900).
Header: +01 mission type (`MT_DACE … MT_GRND`, 5 = training), +02 area `AW<n>`, +04 wind, +06
name-list mask, +0C date (day 1 = 1 Jan 1900). Films `TAPES/*.VCR` = 66-byte header (holds a
SIM.IN copy) + 364 zero bytes + u16 n + mission script + Huffman event stream (`.HUF` frequency
tables). Preferences `CONTROL.PRF` (37, joystick calibration), `?REAL.PRF` (16), `SIMPREFS.PRF`
(70); `ROSTER.DAT`/`TOPACE.DAT` (u16 n × 122-byte pilots), `TOPMISS.DAT` (u16 n × 55).

## Entry types (survey: `tools/dynsurvey.py`)

`*` = packed chunk. Meaning column: first guesses unless marked.

| Ext | n | Volumes | Structure | Meaning |
|---|---|---|---|---|
| `.PAL` | 55 | COMMON1, SHELL1, M1SHL, SIM1 | `PAL:{VGA:}` | palettes (Verified) |
| `.BMP` | 229 | SHELL1, SIM1, SIM2, M1SHL, M1SIM | `BMP:{INF: VQT: OFF:}` / `{INF: BIN:* VGA:*}` / `{INF: SCN: OFF:}` | multi-frame bitmaps (Verified) |
| `.SCR` | 35 | SHELL1, SIM2 | `SCR:{VQT:}` / `{BIN:* VGA:*}` | full screens (Verified) |
| `.FNT` | 11 | COMMON1, SHELL1, SIM1 | `FNT:` | fonts (Verified) |
| `.TTM` | 63 | SHELL1, SIM1, M1SHL, M1SIM | `VER:"4.09" PAG: TT3:* TTI:{TAG:}` | DGDS TTM animation scripts: intro (`INTACE*`), awards, newspapers, war end; SIM1/M1SIM `<plane>.TTM` = cockpit build scripts (Verified, scripts.md) |
| `.SX` | 2 | SHELL1 | `SND:{INF: TAG: FNM: DAT:×n}` | sound banks `SHELL.SX`, `TTD.SX` (intro): ids, names (`SELECT`, `TAB`, …), source names `SFX\M_*.SND`, LZW-packed SCI1-style sound resources |
| `.SNG` | 2 | SIM2, M1SIM | `SSM:{SNG:*×35–38 INF:}` | sim sounds/music, RLE-packed SCI1-style sound resources (device track lists 00/09/0C/12/13) |
| `.OVL` | 5 | SHELL1, SIM2, M1SIM | `SSM:{M32 NLD ADL TAN PS1 STD 001 003 101}*` / `OVL:{VGA EGA MCG CGA TAN HEG EVG EVA}*` | `SXCODE/SX/SX1.OVL`: Sierra SCI sound drivers (87654321h, MT-32, AdLib, Tandy, PS/1, speaker…); `VMCODE.OVL`/`VMCODE2.OVL`: video drivers per adapter (Verified by content) |
| `.TBL` | 112 | COMMON1, SHELL1, SIM1, M1CMN | `MAP: APP: GID: DAT:` (8 without `APP:`) | 3Space shape tables: aircraft, ships, `AOP_COMM` weapons/clouds/wrecks, `AW*` area objects (Verified, shapes.md) |
| `.WD3` | 11 | SIM1, M1SIM | `WD2:{WHD: OB0: MBL:}` | area database: object counts, static objects, macro instances (Verified, world.md) |
| `<n>` (`TARGET.1`–`11`, `CARRIER.1`–`10`) | 32 | COMMON1, SHELL1, M1CMN, M1SHL | `INF: DAT: TAG:` | targets / carrier groups per area: dated positions and states, names (Verified, world.md §5) |
| `.BMD` | 31 | SIM1 | `VER: EXT: PRF: BMD:` | bitmap effect animations, registered as bitmap shapes (header only, world.md §7) |
| `.DAT` | 326 | all but M1CMN/SIM2 | raw (287), text (39) | mixed: string tables `*TEXT*`, `*TXT*`, `HIST*`, `CMPTEXT*` (4 variants, 67 decode, scripts.md §2); missions `MISS0`–`73`, `TRN*` (Verified, data.md §2); aircraft/ship data (`F4U.DAT`, `AKAGI.DAT`); `SHADES.DAT` (256 bytes, colour shading table), `CGACOL/EGACOL.DAT`, `STR_POOL`, `TABLES`, `SND.DAT` … |
| `.SCD` | 34 | SHELL1, M1SHL | `u32 n, u16 end[n]`, strings | labels of one shell screen (`PREV`, `VIEW`, `EXIT`, …) (Verified, scripts.md §2) |
| `.TXT` | 30 | COMMON1, SIM1, M1CMN | NUL-separated words | name lists: `PFNAME*` pilot first names, `SFNAME*` surnames, `PILOT*`; some are stubs ("This is a stubbed out PILOT file") |
| `.EVT` | 2 | SHELL1, M1SHL | u16 n, n × 66-byte records (date, side, TTM name), text | career events: newspapers, rumours, war end (Likely, data.md §3.4) |
| `.BXL` | 84 | SIM1, M1SIM | u8 n, u8, u32, n × 6 s16 | per model hit boxes (Likely, data.md §4) |
| `.DMG` | 82 | SIM1, M1SIM | u16 (n in low nibble), n × 10 + 14 / n × 8 + 2 | per model damage zones (layout Verified, fields Unknown) |
| `.EDG` | 149 | SIM1, SIM2, M1SIM | raw 290–2878 | `F/B/L/R/D<plane>`: cockpit window outlines per view (Likely) |
| `.GL` / `.GLT` | 82 / 35 | SIM2, M1SIM | u16 n, n × 20 (+2) / NUL-separated text | gun groups per model / loadout names ("(4) 20mm cannons") |
| `.FMD` | 46 | SIM2, M1SIM | raw, 214 bytes | flight model per aircraft |
| `.GAU` | 35 | SIM2, M1SIM | 32-byte header (background, common bitmap, n) + n × 28 (kind, bitmap, x, y, w, h) | cockpit gauge layout per aircraft (Likely) |
| `.PLT` | 62 | SIM2, M1SIM | 112 bytes: u16[17] ratings 0..1000, …, +58 name | famous pilots / AI skill profiles (`BONG`, `BOYINGT`, `FOSS`, `IWAMOTO`) |
| `.MBL` | 12 | SIM2, M1SIM | raw 8.5–12 KB | per area `AW<n>`: macro (object group) definitions (Verified, world.md §3) |
| `.FLT` | 11 | SIM1, M1SIM | raw, 408 bytes | per area `AW<n>`: 17 per-class detail records (Likely, world.md §4) |
| `.MEC` | 4 | SIM2 | u16 n, n × 16 | weapon ballistics: `BOMBS`, `BULLETS`, `ROCKETS`, `TORPS` |
| `.WND` | 4 | SIM1 | raw, 74 bytes | wind (header+04 picks one): all four files identical |
| `.WLD` | 2 | SHELL1 | raw | `LAND`, `SEA` world settings |
| `.HUF` | 8 | SIM2 | u16 n, n × (u16 symbol, u32 frequency) | Huffman frequency tables for film (VCR) streams: `BTN`, `JOY`, `PAN`, `RUD`, `VIEW`, `TICKS`, `SIM`, `SOUT` (Verified layout) |
| `.BOX` / `.BL` / `.BND` | 9 / 4 / 8 | SIM1 | raw | sim dialog boxes (`VCR`, `PREFSIM`, `SIMMAP`), box lists, key/event bindings? |
| `.TFA` | 1 | SIM1 | "Turbo Profiler areas file" | developer leftover |
| (none) | 2 | SIM1 | empty | `12-12-91`, `9388`: stamps |

## Open questions

* Which program opens which volume class (mask passed to `049D:0C50`).
* The in-code LZW/RLE decompressor has not been located; the algorithm is DGDS's, verified by data.
* `PAL:CGA:` layout; `FNT:` header byte 3; palettes of a few unscripted bitmaps (`ACE4`,
  `JAPFLAG`, `USAFLAG`, `SIMQ_CH`, `FORMPLNS`).
* Shapes/worlds: see the open questions in shapes.md and world.md (GID: layout, polygon flag 40h,
  target list meanings, `.BMD` payload, model vs world scale).
* Scripts / game data: see the open questions in scripts.md and data.md (SIM.OUT fate codes, pilot
  record, mission record fields, FMD/DMG/GL/MEC fields, VCR event stream).
