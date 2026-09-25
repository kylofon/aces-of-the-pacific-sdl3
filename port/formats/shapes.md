# 3D shapes: `.TBL` shape tables (3Space, "ts2" library)

Addresses are AP.EXE `SSSS:OOOO` in the flattened image `work/AP_flat.exe` (`tools/unovl.py`,
segments as in `work/ap_segmap.txt`, DGROUP `3EA4`, `DS:xxxx`). The shape code is the Dynamix
3Space library (`c:\work\ts2\s\ts_*.c`): `ts_utilo.c` 7074, `ts_file.c` 7039, `ts_draw.c` 2f0e,
`ts_bm.c` 2e33, `ts_util.c` 271b, and the assembly core in segment `277a` (own data, `CS:09A2..0A51`
object state, `CS:21B6..` scratch).
Tags: **Verified** = read in the code and/or decoded over every file and rendered correctly;
**Likely**; **Unknown**.

Tool: `tools/dynshape.py` (`list`, `dump TBL [SHAPE]`, `render TBL [SHAPE] --yaw --pitch --lod --state
--wire --top`, `sheet`, `check`) → `work/shapes/`. Contact sheets: `work/shapes/sheet_aircraft.png`,
`sheet_ships.png`, `sheet_misc.png`; single renders `work/shapes/<TBL>_<shape>.png`.
`check` parses all 112 tables (1175 shapes, 7214 parts, 29 833 polygons): no index out of range.

## 1. Table file (Verified)

A `.TBL` is a chunk list (resources.md §2): `MAP:` `APP:` `GID:` `DAT:` (`APP:` missing in 8:
`ALWAYS`, `SPOLY`, `DYNAMIC`, `SHAD`, `JCRUISE`, `JDSTROY`, `JTANKER`, `SIM1:AW0`).

| Chunk | Layout | Reader |
|---|---|---|
| `MAP:` | `u16 n`, `u16 x` (0 for single-shape tables, = n for `AW*`/`LAND`/`?_SHIP`), `u16 ofs[n]`, `u16 names_size`, NUL-terminated lower-case names at `4+2n+2+ofs[i]` | — (names only; the program addresses shapes by index) |
| `APP:` | `u16 n`, `u16 recsize`, `n × recsize` bytes, one per shape | `1641:000e` (`misctbl.c`, areas) |
| `GID:` | far-pointer list like `DAT:` (below), one entry per shape, zero-terminated; entries point into the chunk | `3368:000a`, used by `3368:0069`/`0169` |
| `DAT:` | far-pointer list + shape data | `7074:0154`, `7074:02d8` (`ts_utilo.c`) |

### DAT: pointer list

`DAT:` starts with `u32 ptr[]`, terminated by a zero dword, one per shape (same order as `MAP:`).
Each is a **normalised far pointer** `u16 off, u16 seg` relative to the chunk start: the shape is at
`seg*16 + off` and `off < 16`. The loader adds the load address to every entry (`7074:01e9`: 32-bit
add of the chunk's far pointer). Inside a shape every `u16` offset is relative to the paragraph
`seg*16` (the code uses them as offsets in the shape's segment `CS:0A29`), so after relocation a shape is
addressed as `seg:offset`.

Example `COMMON1:F4U.TBL`: `DAT:` payload at file 44h: `08 00 00 00` (shape at 8, seg 0), `00 00 00 00`.
`AW1.TBL`: first pointers `0000:001F`, `000E:001F`, `0004:003C` … → shapes at 1F0h, 1FEh, 3C4h; the
pointer list is 124 dwords = 123 shapes + terminator, exactly `MAP:` n.

The shape table in memory: 12-byte records at `DS:647C` (`7074:0000`): far pointer to the loaded
`DAT:`, u16 shape count, u16 100h, u16 100h, u16 FFFFh. A global shape id is resolved by
`271b:0007` (first table whose cumulative count exceeds the id; `CS:0A25` = table index).

### APP: (Likely)

* Areas (`AW*`, recsize 4): `u16 kind, u16 wreck`. `wreck` is the shape index shown when the object
  is destroyed (FFFFh = none): `ct_bld1` → 76h `hlk_sml`, `bridge1` → 79h `hlk_brg`, `af_hang` → 77h
  `hlk_lrg`. `kind` groups objects (22h islands, 1Ah rivers, 1Bh roads, 18h mountains, 21h jungle,
  16h pads, 14h runway, 0Ch flag, 06h city buildings …); `1641:0172` maps kind 1 → 3, 2 → 8.
* Aircraft, ships, `LAND`, `?_SHIP`, `AOP_COMM`: recsize 16, all zero in every file (Unknown).

### GID: (Likely)

Per-shape ground/collision data for area tables (`AW*`: 2.8–24 KB; single models: 4 zero bytes).
Entry: `i16 half_x, i16 half_y` (e.g. `is_1`: 2BA0h, 1C50h = −bbox minimum), then data read by
`35a4:000f`. `3368:0169` tests `|(p − object) >> shift| <= half` on x and y before using the rest
(ground height / land test — Unknown layout).

## 2. Shape header (Verified)

| Off | Type | Field | Code |
|---|---|---|---|
| 00 | u8 | flags: 40h = sort parts (`2f0e:03bd`); 20h = no box stored, header is 14 bytes (`1560:0891`: box = ±radius·94h/256); 10h = bitmap shape (drawn by `ts_bm.c`, `2e33:08d6`; set on BMD effects) | |
| 01 | u8 | object class (`271b:02f5`): 1 island, 2 mountain/volcano, 4 ground pad/area, 5 destructible building/bridge, 6 structure / aircraft / ship, 7 jungle, 9 river, 10 road, 11 flag, 31 stub. `WD2:WHD:` counts area objects by this byte (world.md) | |
| 02 | u8 | sub-class (`271b:037a`, used by the area loader `62d2:0288`, `03ae`) — Unknown | |
| 03 | u8 | scale shift: world size = coordinate << shift; radius << shift = `271b:0539` | `2f0e:0959` |
| 04 | u16 | number of state slots *S* | `271b:03fc` |
| 06 | u16 | offset of `u8 variants[S]` (number of variants per state slot) | `271b:043d` |
| 08 | u16 | number of LODs | `2f0e:0b1b` |
| 0A | u16 | offset of the LOD table | `2f0e:0b22` |
| 0C | u16 | radius | `2f0e:0968` |
| 0E | i16[6] | box min x,y,z, max x,y,z (absent when flags & 20h) | `1560:08d0` |

`F4U`: `40 06 00 00 | 03 00 82 1E | 04 00 22 00 | C6 00 | 3E FF 3A FF BD FF C2 00 59 00 40 00`:
3 state slots, `variants` at 1E82h = `03 06 06` (the last 3 bytes of the chunk), 4 LODs at 22h,
radius 198, box (−194,−198,−67)–(194,89,64). Stub shapes `null` in area tables are 14 bytes, 0 LODs.

## 3. LOD table (Verified, `2f0e:0b18`–`0b74`)

`nlod × { u16 size, u16 nparts, u16 parts_ofs }`. The object's apparent size (`CS:0A39`, from the
distance, `2f0e:0008`) selects the **first** entry with `size >= CS:0A39`, else the last one.
LODs are ordered coarse → fine; the last usually has size FFh. `F4U`: (3, 1 part @3Ah), (9, 9 @ACh),
(25, 14 @305h), (255, 24 @8F1h).

## 4. Part (14 bytes) (Verified, `2f0e:033d` sort, `2f0e:071f` walk)

| Off | Type | Field |
|---|---|---|
| 00 | u8 | state slot; FFh = always shown. Otherwise `v = state[slot]` from the object instance (far pointer `+14h` → `CS:0A2B`); `v` = FFh hides the part, else variant `v mod nvariants` is drawn (`2f0e:07e6`–`081d`) |
| 01 | u8 | sort normal: vertex index of a normal (FFh = key 0) |
| 02 | u8 | sort point: vertex index (FFh = the object origin) |
| 03 | u8 | vertex count → `CS:09A8` |
| 04 | u16 | vertex array offset → `CS:09A6` (several parts share one array) |
| 06 | u16 | number of variants |
| 08 | u16 | offset of the variant entries (8 bytes each) |
| 0A | u16 | number of child parts |
| 0C | u16 | offset of the child parts (14 bytes each) |

Sorting (flag 40h): key = `normal · (point·2^s + O)` (`277a:4f18`, 32-bit dot), where `O` =
object origin relative to the eye in object axes (`CS:0A07`); the parts are drawn in **descending**
key order (selection sort `2f0e:057c`). A part with children is drawn by sorting its children
together with itself (itself with key 0, `2f0e:0778`, `06eb`). This is a small BSP: every part
names a plane (normal + point) and the parts behind it are drawn first.

`F4U` LOD 3: 24 parts; slot 0 = propeller blur (3 variants), slot 1 = landing gear/flaps
(6 variants), slot 2 = tail wheel/hook (6). P-38J has 5 slots (`04 07 00 02 02`).

## 5. Variant entry (8 bytes) (Verified, `2f0e:0821`–`08d7`)

`u8 type, u8 0, …`:

| Type | Layout | Drawn by |
|---|---|---|
| 0 | `+2 u16 npolys, +4 u16 poly_ofs, +6 u16 0` | `277a:05c6` (normal), `277a:03bb` (`DS:2403` set), `277a:07ae` (mode 3), `277a:361d` (modes 1–2); mode `CS:09B0` from distance, `2f0e:0a08`–`0b12` |
| 1 | `+2 u16 size, +4 u8 vertex, +5 u8 colour (VGA), +6 u8 colour (EGA)` — filled disc (ellipse, width ×1.25) of projected radius `size` at a vertex | `70e8:0000` → `1d32:6bbc` |
| 2+ | `+2 i16 bitmap id (−1 = from the object), +4 u8 flip/flags lo, +5 hi, +6 u8 scale, +7 u8 vertex` — bitmap sprite at a vertex | `2edf:0119` → `1d32:5e5b` |

In the shipped data only types 0 (8889) and 1 (19: tree/ship blobs, `01 00 0F 00 15 60 2C 00`) occur.

## 6. Vertices (Verified)

`nverts × { i16 x, i16 y, i16 z }` at the part's vertex offset. Axes: **x right, y forward (nose),
z up** (checked on renders: US star on the upper left wing, canopy up, ship wakes astern).
Normals are stored in the same array as vectors of length 2048 (`F4U` vertex 16 = (2048,0,0));
some entries are longer (4000, 3000) and only used as sort-plane normals.
The transform (`277a:06ae`, `277a:0346`) shifts coordinates right by `−CS:09AC` before adding the
eye offset.

## 7. Polygon record (8 bytes) (Verified, `277a:0609`–`07a3`, colours `277a:01ba`)

| Off | Type | Field |
|---|---|---|
| 00 | u8 | flags |
| 01 | u8 | VGA edge colour |
| 02 | u8 | VGA fill colour |
| 03 | u8 | EGA edge colour (two 4-bit colours, dithered — Likely) |
| 04 | u8 | EGA fill colour |
| 05 | u8 | normal (vertex index) for culling/lighting, FFh = none |
| 06 | u16 | offset of the vertex index list: `u8 index…`, `FFh` |

Flags:

| Bits | Meaning |
|---|---|
| `& 3` = 0 | two-sided; with 20h the back side is lit with the negated normal (`CS:09B5`) |
| `& 3` = 1 | back-face culled: skipped when `normal · (v0 + O) >= 0` (`277a:0645`) |
| `& 3` = 2 | never drawn (`277a:0619`) (55 polygons) |
| 10h | 4-vertex special fill via `2ec2:000d` (none in the data) |
| 20h | shaded (below) |
| 40h | Unknown (2458 polygons, areas/ground pads; not tested in the draw path) |
| 80h | filled (`DS:26CC`); clear = outline only (closed polyline) |

Colour choice: the video driver's info block sets `DS:26DF` (driver call `1d32:0078`, block at
`DS:26C0`); non-zero (VGA) → bytes 1/2, zero → bytes 3/4. 2-vertex polygons are lines. A filled
polygon is filled with the fill colour and, if edge ≠ fill, outlined with the edge colour
(`1d32:0a38`, `0dae`).

Shading (flag 20h, VGA only): `n = SHADES[fill]` (256-byte table `CS:21EC` = `COMMON1:SHADES.DAT`,
values 0–8: the number of lighter/darker neighbours of a palette index). If `1 <= n <= 8`:
`level = (normal · light) >> 16` with the light vector `CS:0A3B` (length 512, so level ∈ −16..16,
16 → 15); `fill += table[(n−1)·32 + level + 16]` from `CS:21F8` (8 × 32 signed offsets, `−n..n−1`;
copied into `tools/dynshape.py`); if edge = fill the edge follows. Finally both colours go through the
remap table `CS:21EE` (if set). Example: `F4U` body `A1 44 44 5E 00 n`: blue 44h, 4 shades → 40h–47h.

## 8. Rendering in `dynshape.py`

Most detailed LOD, state slots all 0, parts sorted and polygons culled exactly as above, VGA colours
with the shading table and a fixed light from the upper left, `SIM.PAL`, perspective camera
(default yaw 210°, pitch 20°), 3× supersampled. Results: all 48 aircraft, 38 ships/vehicles and
the `AOP_COMM`/`LAND` objects look right (`work/shapes/sheet_*.png`).

## Files

| Table | Contents |
|---|---|
| 46 aircraft (`F4U`, `ZERO_52`, `KI84`, `P38_J`, … + 1946 add-on `P80`, `F8F`, `F7F`, `F2G`, `KI83`, `KIKKA`, `J7W`) | 1 shape, 4 LODs, radius 150–600 |
| 38 ships (`AKAGI`, `ESSEX`, `YAMATO`, `LST`, …, `MIDWAY` in M1CMN) | 1 shape, 4 LODs, wakes as cyan lines |
| `AOP_COMM` (44) | clouds, bullet, torpedoes, bombs, rocket, parachute, drop tanks, debris, wrecks (`planehlk`, `shiphlk`), `dynamic1` |
| `AW1`–`AW10`, `AW11` (M1CMN), `SIM1:AW0` (test) | area objects: islands `is_n`, roads `rd n`, rivers `rv n`, mountains, jungle, bases, cities, wrecks |
| `LAND`, `A_SHIP`, `J_SHIP` (SHELL1) | shell (briefing / map) objects |
| `ALWAYS` (`zero`), `GHOST`, `SPOLY`, `DYNAMIC`, `SHAD` (`p51shad`) | player placeholder, ghost box, shadow/"spoly" outlines |
| `JCRUISE`, `JDSTROY`, `JTANKER` | leftovers without `APP:` (a boat on a water quad, a truck, a helicopter) — not ship models |

## Open questions

* Header byte 2; `APP:` of models; `GID:` entry layout; polygon flag 40h; EGA colour bytes.
* `CS:09AC` (extra shift applied to vertices) and the relation of model units to world units: world
  coordinates put Oahu–Hilo at ≈ 5.6 M units (≈ 0.06 m/unit), while the F4U is 388 units wide at
  shift 0 (≈ 0.03 m/unit if true to scale) — the scale per class is not traced.
* Group type 2 (sprites) and the bitmap-shape path (`ts_bm.c`) are only read, not exercised.
