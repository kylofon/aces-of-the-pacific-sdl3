# World areas: `AW<n>.WD3`, `AW<n>.MBL`, `AW<n>.FLT`, `TARGET.n`, `CARRIER.n`, `.BMD` effects

Addresses: AP.EXE `SSSS:OOOO` in `work/AP_flat.exe` (see shapes.md). Tags **Verified** / **Likely** /
**Unknown** as in shapes.md.

Tool: `tools/dynworld.py` — `list`, `dump AREA objects|mbl|macros`, `targets AREA`, `flt AREA`,
`render AREA [--zoom X,Y,HALF] [--labels]`, `all` → `work/world/AW<n>.png` + `work/world/sheet.png`.
Maps: north (+y) up, east (+x) right, islands/terrain first, then everything else, most detailed
LOD, top view, targets = red crosses, carrier-group positions = yellow squares.
Best images: `work/world/AW9.png` (Hawaii, `--labels`: Pearl Harbor airfields),
`work/world/AW1.png` (Japan, Korea, Okinawa, Bonins), `work/world/AW1_zoom.png` (harbour macros
at Yokosuka), `work/world/sheet.png`.

## 1. Areas (Verified by the renders)

| Area | Files | Region |
|---|---|---|
| AW1 | SIM1 `.WD3 .FLT .DAT`, SIM2 `.MBL`, COMMON1 `.TBL`, `TARGET.1`, `CARRIER.1` | Japan, Korea, Okinawa, Iwo/Bonins |
| AW2 | | Formosa, Philippines |
| AW3 | | Leyte / southern Philippines, Borneo, Celebes, western New Guinea |
| AW4 | | Marianas, Carolines (Truk, Palau) |
| AW5 | | New Guinea, New Britain (Rabaul) |
| AW6 | | Solomons |
| AW7 | | Marshalls / Gilberts atolls |
| AW8 | | Wake, Marcus |
| AW9 | | Hawaiian islands |
| AW10 | | Midway |
| AW11 | M1SIM `.WD3 .FLT .DAT .MBL`, M1CMN `.TBL`, `TARGET.11`, `CARRIER.11` | 1946 add-on: Japan (same OB0 as AW1, 339 instead of 307 macro instances) |
| AW0 | SIM1 `AW0.TBL` only | test objects (`islegrnd`, `runway`, `f4ulg`, `york`) |
| AW13 | SIM2 `AW13.MBL` only (same size as AW1.MBL, differs) | no `.WD3`: unused |

The loader (`62d2:049e`) builds `AW<n>` + `.wd3` / `.flt` and `target.XX` with the area number,
loads `WD2:` (`35ad:000f`, `35ad:00f8`), `TARGET.n` (`628f:0144`), the macros (`34f1:0310`),
the `.FLT` file (`333b:000d`) and the shape table.

World coordinates: i32, x east, y north, z up. AW1 spans about −13 M…+13 M on both axes;
Oahu–Hilo ≈ 5.6 M units (≈ 350 km) → ≈ 0.06 m per unit (Likely).

## 2. `AW<n>.WD3` = `WD2:{WHD: OB0: MBL:}` (Verified)

### WHD: (533 bytes)

| Off | Type | Field |
|---|---|---|
| 0 | u8 | n = 2 |
| 1 | u16[n] | class ids `00FFh`, `00FEh` (skipped by the loader) |
| 5 | u16[256] | object count per class: `[c]` = number of `OBx:` objects whose shape has class byte c (shapes.md §2), `[FEh]` = number of `MBL:` records, `[FFh]` = number of 40-byte `MBL:` records |
| 517 | u16 | total `OBx:` objects |
| 519 | 14 bytes | 0 |

The loader reads the 512-byte table into a far buffer `DS:7114` (`35ad:0087`–`00b0`).
AW1: `[1]`=20 islands, `[2]`=53 mountains, `[5]`=4 bridges, `[10]`=13 roads (= 90 objects), `[FEh]`=307.

### OB0: … OB5: — static objects (26-byte records)

`35ad:0135`: chunks `WD2:OB0:`…`WD2:OB5:` (the loader patches the digit), `size / 26` records, each
passed to the record handler (`DS:7110` → `3de9:0034` → `62d2:0199`). Only `OB0:` exists.

| Off | Type | Field |
|---|---|---|
| 00 | u16 | flags: 4000h = no rotation (the handler recomputes it: set when +10h and +14h are 0, `62d2:0171`) |
| 02 | u16 | shape index in `AW<n>.TBL` |
| 04 | i32 ×3 | position x, y, z |
| 10 | u16 | angle (pitch? — 0 in all files) |
| 12 | u16 | angle (roll? — 0 in all files) |
| 14 | u16 | heading, 10000h = 360°, counter-clockwise seen from above (bridges, rotated mountains) |
| 16 | 4 bytes | 0 (not copied) |

`62d2:0133` turns it into a 24-byte instance (`0801h|4000h`, shape, position, three angles).
Example AW1 `OB0:` +0: `00 40 12 00 C0 5C CA FF 00 00 4B 00 …` = `rd1` at (−3 515 200, 4 915 200, 0).

### MBL: — macro instances

`u16 n`, then n records of 16 + 6 bytes, or 16 + 24 bytes when `(type & C000h) == C000h`
(`35ad:01fb`; one such record in AW3):

| Off | Type | Field |
|---|---|---|
| 00 | u16 | flags (5000h in all files) |
| 02 | u16 | type: 8000h + macro index (`34f1:0163`: `& 3FFFh`) |
| 04 | i32 ×3 | position |
| 10 | u16 | heading |
| 12 | 4 bytes | 0 (long form: 22 more bytes, 12 of them a second position at +1Ch, `62d2:0033`) |

Expansion (`34f1:0155`): every member of the macro is copied, its x/y are rotated by the instance
heading (`367b:0006`) and added to the instance x/y (z is not added), and the member heading
becomes the instance heading. For 8000h records the loader also samples the area (`628f:031f`,
target lookup by position) and builds a 42-byte group record (`62d2:001d`).

## 3. `AW<n>.MBL` — macro definitions (SIM2 / M1SIM, not a chunk file) (Verified)

`34f1:0310`:

```
u8   0
u16  nmacros
nmacros x {
    char name[8]            "airbase", "aa_base", "air_fact", "oil_ref", "supply", "naval", "fort",
                            "village", "city1".."city3", "harbor", "shipyard", "farm1", "farm2",
                            "coastbat", "jungle1", "jungle2", "fields1", "RIVER1".."RIVER5", "airbase2", ...
    u16  count
    i32  box[3]             extent (x, y, z), e.g. airbase 30400 x 42400 x 1020
    count x 22-byte member  same layout as an OBx record without the 4 pad bytes
                            (flags 4800h / 0800h, shape, x, y, z relative, angles, heading);
                            members with shape FFFFh are dropped
}
```

Macro table in memory: 18-byte entries at `DS:36AE` (`u16 count, i32 box[3], far ptr members`).
AW1 macro 0 `airbase`: 20 members (`bs_hang` ×3, `bs_fuel`, `bs_flag`, `bs_hq`, `bs_tent`,
`bs_rnwy1`, 12 × `palm`).

## 4. `AW<n>.FLT` — per-class detail table (408 bytes = 17 × 24) (Likely)

`333b:000d` reads 24-byte records; `333b:0098` stores each in an 85-byte entry of `DS:36E0`
indexed by `+0`:

| Off | Type | Field |
|---|---|---|
| 00 | u16 | object class (= shape header byte 1; 0–0Bh, 0Eh–12h) |
| 02 | u16 | threshold (0, 55h, 100h), compared with the detail level in `333b:01b9` |
| 04 | u8 | mode: 1 = one range (+06, +08), 0 = three ranges (+0A/+0C, +0E/+10, +12/+14) |
| 06–15 | u16 pairs | ranges, each fed to `33a1:0055` with limit FFh |
| 16 | u16 | range end (3FFh, 0Ah for class 0) |

`333b:0158` re-evaluates the table for a level (called with 80h at area load) — Likely visibility
distances per object class and detail setting. Exact meaning Unknown.

## 5. `TARGET.n` (COMMON1 / M1CMN) and `CARRIER.n` (SHELL1 / M1SHL) (Verified)

Chunks `INF: DAT: TAG:`, read by `628f:0144` (`wdata.c`). Both files use the same layout:

```
INF:  u16 P                 points per position entry (1 in all files)
DAT:  u16 count
      count x {
          u16 id
          5 lists, each: u16 m, m x { u16 date, payload }
              list 0: P x (i32 x, i32 y, i32 z)   position valid from `date`
              list 1: u16, u16                    (empty in all files)
              list 2: u16                         kind (0 airfield, 4 troops, 5 harbour, 6 naval base,
                                                  8 aircraft factory, 0Ah refinery, 0Bh city/port …) — Likely
              list 3: u16                         owner/state by date (0, 1, 0Ah, 0Bh; 99 = any side): PS
                                                  `wd_side_matches` compares it with a side (shell_data_emd1
                                                  §2); AP `target_state` uses it as the ground group's state
                                                  / type bits, 0Ah = destroyed (group suppressed)
                                                  (render3d_world §6, §7) — Verified (both readers)
              list 4: u16                         service code / service set (3, 4, 16h, 17h …), PS
                                                  `wd_find_for_service` (shell_data_emd1 §2) — Verified
                                                  (list 2: 99 = none, `wd_kind`)
      }
TAG:  u16 count, count x (u16 id, char name[])      "Naha Field", "Kadena Airfield", "Yorktown (CV-10)"
```

**Dates** are days since 1 Jan 1900: `3BD4h` = 7 Dec 1941 (the first date of most targets),
`4081h` = 18 Mar 1945 (Yorktown off Kyushu). The lists are kept sorted by date (`62ca:0000`);
`628f:031f` finds the entry valid at a date. Carrier groups have 3–26 dated positions (a track);
(1 400 000, 0, 0) is a parking position off the map. All 22 files parse exactly
(`dynworld.py targets 1..11`).

## 6. `AW<n>.DAT` (SIM1, 33–160 bytes) (Unknown)

Starts with the area name (`"Japan\0"` padded to 8), then i32 pairs (−11 000 … 19 000) — not read here.

## 7. `.BMD` effect animations (SIM1, 31 files) (structure only)

`241c:000a` (with a shape id): chunks `VER:` (2 bytes, must start with `'4'`: `"40"`), `EXT:`
(36 bytes; the first two u16 are copied to `DS:648A` / `DS:6488`, e.g. `1, 1Eh` / `0, 64h`),
`PRF:` (u16 id, name pairs: `1 EXPLOSN`, `2 SHAPE`/`SHIP`), `BMD:` (`char name[8]` = `"EXPLOSN"`,
then data). The loader copies the 1Ah-byte header of an existing shape, appends the `EXT:` words and
the `BMD:` data, sets header byte 0 = 30h (no box + **bitmap shape**) and registers it as a shape
(`271b:011d`); it is drawn by `ts_bm.c` (`2e33:001c`). The `BMD:` payload (`00 01 09 00 02 00 83 00
77 00 12 00 E2 00 …` then 4-byte groups) is not decoded.
Files: `BULSPL DFIRSM DIRTPUF DISMOKE DSMKSTR FIRBALL FIRE FIRSMK FLACK1-4 FLAK1-4 FRSMKST GRFIRSM
GRFSMST GRNDSMK GRSMSTR MEDSPLA PARA_AL PARA_JP PARA_US PLANEXP PLANFIR PLFRSTR PUFF TOREXPL TORSPLA`.

## Open questions

* WD3: the angle order at +10h/+12h (always 0); the 40-byte `MBL:` record (AW3); `WHD` ids FFh/FEh.
* Target lists 2–4 meaning (kind values only roughly match the macro list); how `CARRIER.n` is used (shell only?).
* `.FLT` field meaning; `AW<n>.DAT`; `.BMD` payload (`ts_bm.c`).
* Terrain height: areas are flat polygons at z = 0 plus mountain shapes; `GID:` (shapes.md) is the
  only other candidate for ground data.
