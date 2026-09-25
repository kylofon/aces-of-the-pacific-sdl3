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

Detailed format documents:

| Document | Covers |
|---|---|
| [port/formats/resources.md](port/formats/resources.md) | volume file layout and name hash, lookup, tagged chunks, RLE/LZW compression, palettes, BMP (nibble planes, VQT, SCN), SCR, FNT; structure of TTM/SX/SNG/OVL |

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

## Entry types (survey: `tools/dynsurvey.py`)

`*` = packed chunk. Meaning column: first guesses unless marked.

| Ext | n | Volumes | Structure | Meaning |
|---|---|---|---|---|
| `.PAL` | 55 | COMMON1, SHELL1, M1SHL, SIM1 | `PAL:{VGA:}` | palettes (Verified) |
| `.BMP` | 229 | SHELL1, SIM1, SIM2, M1SHL, M1SIM | `BMP:{INF: VQT: OFF:}` / `{INF: BIN:* VGA:*}` / `{INF: SCN: OFF:}` | multi-frame bitmaps (Verified) |
| `.SCR` | 35 | SHELL1, SIM2 | `SCR:{VQT:}` / `{BIN:* VGA:*}` | full screens (Verified) |
| `.FNT` | 11 | COMMON1, SHELL1, SIM1 | `FNT:` | fonts (Verified) |
| `.TTM` | 63 | SHELL1, SIM1, M1SHL, M1SIM | `VER:"4.09" PAG: TT3:* TTI:{TAG:}` | DGDS TTM animation scripts: intro (`INTACE*`), awards, newspapers, war end; SIM1/M1SIM `<plane>.TTM` = cockpit build scripts (panel, sights, wings, tail, emblems) |
| `.SX` | 2 | SHELL1 | `SND:{INF: TAG: FNM: DAT:×n}` | sound banks `SHELL.SX`, `TTD.SX` (intro): ids, names (`SELECT`, `TAB`, …), source names `SFX\M_*.SND`, LZW-packed SCI1-style sound resources |
| `.SNG` | 2 | SIM2, M1SIM | `SSM:{SNG:*×35–38 INF:}` | sim sounds/music, RLE-packed SCI1-style sound resources (device track lists 00/09/0C/12/13) |
| `.OVL` | 5 | SHELL1, SIM2, M1SIM | `SSM:{M32 NLD ADL TAN PS1 STD 001 003 101}*` / `OVL:{VGA EGA MCG CGA TAN HEG EVG EVA}*` | `SXCODE/SX/SX1.OVL`: Sierra SCI sound drivers (87654321h, MT-32, AdLib, Tandy, PS/1, speaker…); `VMCODE.OVL`/`VMCODE2.OVL`: video drivers per adapter (Verified by content) |
| `.TBL` | 112 | COMMON1, SHELL1, SIM1, M1CMN | `MAP: APP: GID: DAT:` (8 without `APP:`) | 3Space shape tables: aircraft (`F4U`, `ZERO_22`), ships (`AKAGI`, `LEX`), `AW*` areas, `ALWAYS`; `MAP:` holds the lower-case name, `DAT:` the shape data |
| `.WD3` | 11 | SIM1, M1SIM | `WD2:{WHD: OB0: MBL:}` | world / area database per `AW<n>` (islands, objects) |
| `<n>` (`TARGET.1`–`11`, `CARRIER.1`–`10`) | 32 | COMMON1, SHELL1, M1CMN, M1SHL | `INF: DAT: TAG:` | target / carrier-group sets per area; `TAG:` has place names ("Naha Field") |
| `.BMD` | 31 | SIM1 | `VER: EXT: PRF: BMD:` | bitmap effect animations (fire, flak, smoke, splash); `PRF:` names `EXPLOSN`, `SHIP` |
| `.DAT` | 326 | all but M1CMN/SIM2 | raw (287), text (39) | mixed: string tables `*TXT*.DAT`, `HIST*`, `CMPTEXT*` (u32 size, u32 count, offsets, NUL strings); missions `MISS0`–`73`; aircraft/ship data (`F4U.DAT`, `AKAGI.DAT`); `SHADES.DAT` (256 bytes, colour shading table), `CGACOL/EGACOL.DAT`, `STR_POOL`, `TABLES`, `SND.DAT` … |
| `.SCD` | 34 | SHELL1, M1SHL | text (26); raw (8): `u32 n, u16 offsets[n]`, strings | shell screen / menu definitions (button labels `PREV`, `VIEW`, `EXIT`, …) |
| `.TXT` | 30 | COMMON1, SIM1, M1CMN | NUL-separated words | name lists: `PFNAME*` pilot first names, `SFNAME*` surnames, `PILOT*`; some are stubs ("This is a stubbed out PILOT file") |
| `.EVT` | 2 | SHELL1, M1SHL | raw, strings (`USPAPER`) | career events (newspaper headlines, dates) |
| `.BXL` | 84 | SIM1, M1SIM | raw 18–66 | per model (aircraft, ships, clouds): bounding boxes / hit volumes? |
| `.DMG` | 82 | SIM1, M1SIM | raw 4–66 | per model damage model |
| `.EDG` | 149 | SIM1, SIM2, M1SIM | raw 290–2878 | `B<plane>`, … per aircraft: edge/outline data? (cockpit frame, gunner view?) |
| `.GL` / `.GLT` | 82 / 35 | SIM2, M1SIM | raw / text | gun layout per model / gun loadout text ("(4) 20mm cannons") |
| `.FMD` | 46 | SIM2, M1SIM | raw, 214 bytes | flight model per aircraft |
| `.GAU` | 35 | SIM2, M1SIM | raw 396–564, names `GBACK1.BMP`, `GA*.BMP` | cockpit gauge layout per aircraft |
| `.PLT` | 62 | SIM2, M1SIM | raw, 112 bytes | famous pilots / AI skill profiles (`BONG`, `BOYINGT`, `FOSS`, `IWAMOTO`) |
| `.MBL` | 12 | SIM2, M1SIM | raw 8.5–12 KB | per area `AW<n>`: map blocks (terrain?) |
| `.FLT` | 11 | SIM1, M1SIM | raw, 408 bytes | per area `AW<n>` |
| `.MEC` | 4 | SIM2 | raw | weapons: `BOMBS`, `BULLETS`, `ROCKETS`, `TORPS` |
| `.WND` | 4 | SIM1 | raw, 74 bytes | wind: `LIGHT`, `STILL`, `STORMY`, `STRONG` |
| `.WLD` | 2 | SHELL1 | raw | `LAND`, `SEA` world settings |
| `.HUF` | 8 | SIM2 | raw, (code, u16 FFE0+i, …) pairs | Huffman tables for film (VCR) streams: `BTN`, `JOY`, `PAN`, `RUD`, `VIEW`, `TICKS`, `SIM`, `SOUT` (Likely) |
| `.BOX` / `.BL` / `.BND` | 9 / 4 / 8 | SIM1 | raw | sim dialog boxes (`VCR`, `PREFSIM`, `SIMMAP`), box lists, key/event bindings? |
| `.TFA` | 1 | SIM1 | "Turbo Profiler areas file" | developer leftover |
| (none) | 2 | SIM1 | empty | `12-12-91`, `9388`: stamps |

## Open questions

* Which program opens which volume class (mask passed to `049D:0C50`).
* The in-code LZW/RLE decompressor has not been located; the algorithm is DGDS's, verified by data.
* `PAL:CGA:` layout; `FNT:` header byte 3; palettes of a few unscripted bitmaps (`ACE4`,
  `JAPFLAG`, `USAFLAG`, `SIMQ_CH`, `FORMPLNS`).
* All non-picture types above (shapes, worlds, sounds, scripts, missions) — later phase-2 steps.
