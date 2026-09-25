# Game data: hand-off files, missions, preferences, records, films, per-model sim data

Addresses: `SSSS:OOOO` file segments (`port/*_functions.csv`); PS.EXE unless stated (DGROUP
`4D08`), AP = de-overlaid `work/AP_flat.exe` (DGROUP `3EA4`; many sim globals are in the far
data segment `4253`). Tags: **Verified** (code read and/or consistent over all files),
**Likely**, **Unknown**. Dumps: `tools/dyndata.py all` → `work/data/<VOL|game>/<NAME>.txt`.
All little-endian.

## 1. The shell ⇄ sim hand-off

GCD.COM loops PS ⇄ AP on exit codes (RE_GUIDE §startup). PS and AP are separate processes, so
everything that crosses is in files in the game directory:

| File | Written by | Read by | Contents |
|---|---|---|---|
| `SCRIPT.DAT` | PS `3164:23E3` (`miss\script.c`), or a copy of a `MISS*.DAT`/`TRN*.DAT` | AP (`snario.c`, header → `4253:0C8B`) | **the mission** (§2) |
| `SIM.IN` | PS `1193:093E` just before `exit(3)` | AP `50C8:0008` (mode); **PS `1193:08F6` when it restarts** after the sim | 13 bytes: what was flown, for the shell's debrief |
| `SIM.OUT` | AP `5254:04F1` → `5254:0859` (`results.c`) | PS `1193:09FE` → `DS:4227` (`simend.c` etc.) | 36 bytes: outcome and counters |
| `?REAL.PRF` | PS | AP `4E0D:05E0` picks `mreal.prf` or `creal.prf` (career) | realism settings |
| `SIMPREFS.PRF` | AP | AP `4E0D:09D0` | sim preferences |

### 1.1 `SIM.IN` (13 bytes, `DS:4B86`) — Verified (PS writer), Likely (meanings)

Built from the mission header (`DS:626B`, = SCRIPT.DAT type-0 record) and the flight table
(`DS:62C5`, 3 × 4 flights × 24h bytes, the player's flight first):

| Off | Type | Source | Meaning |
|---|---|---|---|
| 00 | u8 | career: `DS:4774`, else FF | roster index of the career pilot |
| 01 | u8 | header+00 (kind) mapped 0→0, 1→1, 2→0, 3→2, 4→3 | **sim mode**: 0 single/historical mission, 1 career, 2/3 mission-recorder paths (AP: `-w` forces 2, `-d` forces 3) |
| 02 | u8 | header+01 | mission type (§2.2) |
| 03 | u8 | set by `flymiss2.c` (`100E:0648`: 4 or `DS:4B3D`) | Unknown (PS tests `+02 == 5 && +03 != 4`) |
| 04 | u16 | header+08 | Unknown |
| 06 | u8 | header+02 | world area n (`AW<n>`) |
| 07 | u8 | header+06, OR the player's service bit (career and historical) | name-list/service mask; AP reads bit 0 (`6C5F:0000`) |
| 08 | u8 | flight[0]+00 | player's side/nation (0 US, 3 Japan?) |
| 09 | u8 | flight[side-slot 1][0]+00 | first enemy flight's side |
| 0A | u16 | flight[0]+18 | player's aircraft type (index; same as the type-1 record byte 0) |
| 0C | u8 | — | never written (0) |

Example `Game/SIM.IN` = `FF 00 05 00 2800 09 2A 00 03 0800 00`: no roster pilot, mode 0,
mission type 5 (training), area 9, mask 2Ah, US player against side 3, aircraft type 8 — it
matches `SCRIPT.DAT` = `TRN0.DAT`. The AP itself only uses +01 and bit 0 of +07; the rest is the
shell's memory across the sim run. The VCR films keep a copy (§5).

### 1.2 `SIM.OUT` (36 bytes; AP `4253:21B3`, PS `DS:4227`) — Verified layout, Likely meanings

| Off | Type | AP source | Meaning |
|---|---|---|---|
| 00 | u16 | `5254:08D9` result | fate code: low nibble 1 / 2 / 3 / 4 (4 = back normally; 1..3 = shot down, bailed out/ditched, … — which is which Unknown), high nibble 10h–80h = detail (captured, rescued, …) |
| 02 | u8 | flags | bits 0–2 fate (01 set with "killed/captured" outcomes, 02 rescue, 04 …), **10 shot down a friendly aircraft, 20 sank a friendly ship, 40 destroyed a friendly ground target** (`2899:0CF0`, `2899:102F`) |
| 03 | u8 | 0 | |
| 04 | u16 | `5254:149C()` | Unknown |
| 06 | u16[4] | FFFF | Unknown (always FFFF when written) |
| 0E | u16 | player's flight flag | 1 if the player's flight has a flag +03 and its leader has bit 1 at +1B (Unknown meaning) |
| 10 | s16 | player | ground targets destroyed |
| 12 | s16 | player | ships hit by bomb/torpedo (first hit, or sunk by one) |
| 14 | s16 | player | ships sunk |
| 16 | s16 | player | aircraft shot down |
| 18–1E | s16 ×4 | player's flight (including the player) | same four counters |
| 20 | s16 | `(DS:0C93 × t) >> 10` | Unknown (time-based?) |
| 22 | s16 | score | mission score: flight score (air kills, ships, targets, bonuses) × realism % (`622C:0038`) / 100, clamped to 0..900 |

PS (segment `0542`, `simend.c`) adds +16 to the pilot's air kills, +14 ships, +10 ground,
+16 + +14 to the total, +1E/+1C/+18 to the squadron totals and +22 to the 32-bit score.
Example `Game/SIM.OUT`: fate 0004, flags 04, all counters 0.

## 2. Missions: `MISS0`–`73.DAT`, `TRN*.DAT`, `SCRIPT.DAT` (Verified structure)

74 historical missions (`MISS0`–`58` SHELL1, `MISS59`–`73` M1SHL), 19 training/quick missions
`TRN*` and the hand-off `SCRIPT.DAT` share one format; all 94 files parse exactly.

```
u16 version = 4
repeat until EOF:  u16 type, u16 count, count records of type
```

Record sizes (PS `1F06:02C4` prescan, table `DS:1024`; AP `snario.c 56AC:0236`):

| Type | Size | Name | Fields (Likely unless marked) |
|---|---|---|---|
| 0 | 90 | header (×1) | = PS `DS:626B..62C4` (§2.1) |
| 1 | 22 | aircraft | +00 aircraft type (Verified < 9Fh), +01 side, +02 pilot/name id, +04..07 (`80 00 80 xx` / `80 00 19 00`), +07 skill, +0A u16 FFFF, +0C..15 ordnance slots (FF = none) — writer `3164:23E3` |
| 2 | 16 | ship | +00 ship type (Verified < 73h), +01 group, +02 u16 name id?, +04 u16 FFFF, +08 s32 x, +0C s32 z (offsets in the group?) |
| 3 | 6 | — | never present (the PS prescan does not even skip it) |
| 4 | 10 | place | +00, +01 index, +02 s32 x, +06 s32 z (targets / home bases) |
| 5 | 58 | group (flight) | +0A u16 aircraft count?, +0C u16 group index, +0E u16 first waypoint, +1A u16, +1C u16 …; the in-memory flight is 24h bytes (`DS:62C5`) |
| 6 | — | invalid (error) | |
| 7 | 2 + 12 or 2 + 4 | waypoint | u8 kind, u8 index/FF; kind 0: s32 x, s32 z, s32 altitude (feet); other kinds (3 seen): s16, s16 (an action with parameter, e.g. `03 FF 0000 01F4`) |
| 8 | 2 | message offset | u16 offset into the type-9 text |
| 9 | 1 | message text | bytes of NUL-terminated strings, lines split by `|` ("Get airborne.", "You've reached Ewa Air Base. Shoot down the Val dive bombers!") |

World coordinates are s32 (feet?); e.g. MISS1 waypoints around (−150 000, −150 000).

### 2.1 Header (type 0, 90 bytes)

| Off | Type | Meaning | Status |
|---|---|---|---|
| 00 | u8 | kind: 0 in all files; the shell sets 0 single/quick (`TRN`), 1 career, 2 historical (`MISS`), 3/4 recorder paths (`04DF:018D`) | Verified (writes of `DS:626B`) |
| 01 | u8 | **mission type** 0..9 = `MT_DACE MT_DSQD MT_CAP MT_FSWP MT_SCRM MT_TRNG MT_ESCT MT_INTR MT_ANTI MT_GRND` (`SCREENS0.DAT`); TRN = 5, MISS1 (intercept Vals at Ewa) = 7 | Likely |
| 02 | u8 | world area n → `AW<n>` (AP `56AC:0236`: itoa into `"AW####"`; `-W<n>` overrides) | Verified |
| 04 | u8 | wind 0..3 → `STILL/LIGHT/STRONG/STORMY.WND` (AP `56AC:00CF`, 3 = stormy flag) | Verified |
| 06 | u8 | bit mask of name lists `PFNAME<n>/SFNAME<n>.TXT` to load (n = 1..8; 0 always) (AP `65A4:01F0`) | Verified |
| 08 | u16 | Unknown (40, 50, 190…) | |
| 0C | u16 | date: day number, 1 Jan 1900 = 1 (MISS1, the Pearl Harbor intercept: 15316 = 7 Dec 1941; the `.EVT` dates and the TARGET/CARRIER dates of world.md use the same count: first US paper 15317, last event 16663 = 15 Aug 1945) | Likely |
| 0E | u16 | Unknown | |
| 10 | u32 | Unknown (`0EEE7054` in many files) | |
| 14 | 70 bytes | per-slot table (`05 FF 00 00 00 00` repeated) | Unknown |

## 3. Shell data

### 3.1 Preferences (Verified sizes)

| File | Size | Reader | Layout |
|---|---|---|---|
| `CONTROL.PRF` | 37 | PS `1193:027A` → `DS:43B0` | +00 u16, +02 u16 (8, 3 here: control devices?), +04..+0C bytes (+06..+0C default 1), **joystick calibration** +0D/+0F/+11 s16 X min/centre/max, +13/+15/+17 Y (default −127/0/127), +19.. 12 bytes 0 |
| `MREAL.PRF` / `CREAL.PRF` | 16 | PS `DS:4357` (`0A8D:07CB`, `1193:0856`) | realism settings for single missions / career: the items of `REALISM.SCD` (sun blind spot, weather, gun jams, engine burnout, blackouts, ammo, fuel, damage, collisions, in-flight info, combat level, flight model); exact byte order Unknown |
| `SIMPREFS.PRF` | 70 | AP `4E0D:09D0` | +00 u16[5] → `4253:08B7` (`32 FF FF 1 1`: detail levels?), +0A 10 × (u16, u16, u16 = 1C2h) via `2C30:0007` |
| `RESOURCE.CFG` | text | INTRO/PS/AP | `key = value` lines: `soundDrv`, `joyDrv`, `mouseDrv`, `memoryDrv`, `modules`, `latest`, `toggle3..7`, `minCPU`, `minDOS`, `minEMS`, `cmd` |

### 3.2 Records

| File | Layout (Verified) | Reader/writer |
|---|---|---|
| `ROSTER.DAT` | u16 n; n × **122-byte pilot records** (read in 128-byte chunks by `1193:0A46`); u16 len (≤ 200h); len bytes (`DS:47CE`) | `1193:031E` / `1193:0421` |
| `TOPACE.DAT` | u16 n (≤ 10); n × 122-byte pilot records (best careers) | `1193:050D` / `1193:065C` |
| `TOPMISS.DAT` | u16 n (≤ 10); n × 55-byte records: char[16] pilot name, then u16 fields (+10 aircraft type?, +12 score, +16 realism %?, +18 score again, …) | `1193:05B8` / `1193:0727` |

The 122-byte pilot record (name, rank, service, kills, medals…) is not decoded yet (the
shipped roster is empty).

### 3.3 Name lists `.TXT` (Verified)

NUL-separated words. `PFNAME<n>.TXT` first names and `SFNAME<n>.TXT` surnames per service set
n (0 in COMMON1, 1–8 in SIM1, `…1_` in M1CMN), loaded by the AP per header+06 mask;
`PILOT<n>.TXT` = lists of famous-pilot (`.PLT`) names; some are stubs ("This is a stubbed out
PILOT file").

### 3.4 Career events `EVENTS0.EVT` (SHELL1, 41 events), `EVENTS1.EVT` (M1SHL) — Likely

u16 n, n × 66-byte records, then a text block. Record: +00 u8 type (5), +01 u8 side (2 US, 1
Japan), +07 u16 date, +09 u16 date (same day count as the mission header), +0B 14 × FF, +19
event letter (`'@'+i`), +1A char[9] TTM script (`USPAPER`, `JNPAPER`, `RUMUSA`, `RUMJAP`,
`WARENDA`, `WARENDJ`), then u16 fields (screen positions, text offsets into the tail).

### 3.5 Text tables, `.SCD`

See `scripts.md` §2 (four string-table variants; 67 files decode). `SCREENS0/1.DAT` hold the
shell screen names and the mission-type codes.

### 3.6 `TTMS0.DAT` (138 bytes, PS `0F35:012D`) — Verified layout

Records of 69 bytes: u8 side (0 Japan, 1 US), 4 × (char[9] TTM name, s16[4]) → `DS:45BC + side ×
44h`: `PRISJAP/PRISUSA [-1,0,0,7]`, `MEDJAP/MEDUSA [1,2,1,4]`, `JAPFLAG/USAFLAG [75,2,3,82]` ×2
(the numbers are Likely frame/tag ranges for the award scripts).

## 4. Per-model sim data (SIM1, SIM2, M1SIM)

Loaded by name `<model>.<ext>` through the AP type table `DS:05B4` (`BMP TBL DAT BOX TXT BND PAL
WLD WND BXL OVL GL MEC DMG rb BMD TTM EDG GAU FMD MBL SCR VCR`).

| Ext | n | Size | Loader | Layout |
|---|---|---|---|---|
| `.DAT` aircraft | 46 | 131 | AP `45CC:034F` | +0A name (`Corsair`, `Zero`); +04, +08, +24 (FMD pointer), +73 (speed factor from the FMD) are overwritten at load; rest Unknown | 
| `.DAT` ship | 36 | 154 | AP `45CC:05CE` | +00 4 × (u16 0, u32) positions?, +4F name (`Akagi Class CV`), rest Unknown |
| `.FMD` | 46 | 214 | AP `45CC:034F` | flight model, copied whole; `1B01:1A28(fmd, 10000, 0)` derives a performance figure at 10 000 ft. Words: +00 2, +02 3276?, then tables of 150 (0x96)-step values… Unknown |
| `.PLT` | 62 | 112 | AP `45CC:00A0` | famous pilot / AI profile: u16[17] ratings 0..1000 (each mapped by `45CC:0080(v, lo, hi)` into a skill range), bytes, +58 char[24] name (`Dick Bong`). Up to 194 pilots |
| `.GL` | 82 | 2+20n+2 | AP `4CDA:0037` | u16 n; n × 20 bytes (aircraft; 10 for ships): gun groups (count, position s16 x/y/z, …); u16 tail. Fields Unknown |
| `.GLT` | 35 | text | AP `4CDA:00F8` | NUL-separated loadout names (`(4) .50 cal machine guns`) |
| `.DMG` | 82 | | AP `4B3A:0341` | u16 header, low nibble = n; n × 10 bytes + 14 (aircraft) or n × 8 + 2 (ships): damage zones. Fields Unknown |
| `.BXL` | 84 | 6+12n | AP `48AF:0017` | u8 n, u8, u32; n × box (s16 x1 y1 z1 x2 y2 z2): hit boxes |
| `.GAU` | 35 | 32+28n | AP `4CAD:00AB` | char[14] panel background (`GBACK1.BMP`), u16 (100), char[14] common gauges (`GACMN.BMP`), u16 n; n × (u16 kind, char[14] bitmap, u16 ?, u16 x, u16 y, u16 w, u16 h, u16 ?) — kind 0 altimeter, 1 airspeed, 2 VSI, 3 heading, 4 compass, 5 RPM, …, 16 stall, 18 flaps, 19 gear (from the bitmap names) |
| `.EDG` | 149 | | AP `0962:00F1` | `F/B/L/R/D<plane>` (front/back/left/right/down): cockpit window outlines as per-line spans (u16 header + (x, y) pairs), used with `CPVW.BUF` | 
| `.MEC` | 4 | 2+16n | AP `0688:000C`, `1A32`, `1BAA`, `48FF` | `BOMBS`, `BULLETS`, `ROCKETS`, `TORPS`: u16 n; n × 16-byte ballistics records (Unknown fields) |
| `.WND` | 4 | 74 | AP `56AC:0000` | s32 800, 8000, 40000, 0, 60, then pairs of s16 … — **all four files are identical** (wind levels have no data effect) |
| `.HUF` | 8 | 2+6n | AP `618D:0768` (`vcr_tape.c`) | u16 n; n × (u16 symbol, u32 frequency): Huffman frequency tables for the film streams (`BTN JOY PAN RUD VIEW TICKS SIM SOUT`) — Verified layout |
| `.BOX` / `.BL` / `.BND` | 9/4/8 | | AP `vcr_gfx.c`, `control.c`, … | sim dialog boxes (rectangles: u16 x, y, w, h …), box lists (byte links), key bindings / result layouts: hex dumps only |
| `SHADES.DAT`, `SHADES1.DAT` | | 256 | AP `shade.c`? | 16 × 16 byte table (shading) — Unknown use |

## 5. Films `TAPES/*.VCR` (AP `vcr_*.c`)

Reader `618D:011F`: 

| Off | Size | Contents | Status |
|---|---|---|---|
| 000 | 66 | header (`4253:159C`): u16 flags (bit 0 must be set), u16 12h, u16 32h, 16 bytes of settings, u32 (841), u32 (113), …, **+24h a copy of SIM.IN** (13 bytes) | Verified (size, bit 0, SIM.IN), rest Unknown |
| 042 | 364 | zero in all four demos (read and ignored) | Verified |
| 1AE | 2 + n | u16 n, n bytes = the **mission script** (§2 format), passed to `5E0D:038E` | Verified |
| … | rest | event stream, Huffman-coded with the `.HUF` tables (`718D:0726`) | Unknown |

The four demos (`DEMOAG`, `DEMODS`, `DEMOFLAK`, `DEMOPAP`) are played by the AP with `-d`
(`TAPES\DEMO*.VCR`); the recorder writes `TAPES\_TAPE_.TMP` while recording. Their SIM.IN copies
have +07 = 0 even where the embedded header has mask 2Ah (older build or demo path).

`CPVW.BUF` (192 008 bytes, zero-filled): opened by AP `644A:0F2B`/`644A:1020` (cockpit view
buffers, 6 views × 32 000 + 8?) — Likely a disk cache for the cockpit views built by the
`<plane>.TTM` scripts.

## Open questions

* Fate code values (+00 low/high nibble) — read `5254:08D9` fully; SIM.OUT +04, +06, +0E, +20.
* The 122-byte pilot record (ROSTER/TOPACE) and the 55-byte TOPMISS record.
* Mission records 1/2/4/5 field meanings beyond the ones listed (AP `snario.c`); header +08,
  +0E, +10, +14; waypoint kinds other than 0 and 3; aircraft/ship type index tables.
* `.FMD`, `.DMG`, `.GL`, `.MEC`, `.EDG`, aircraft/ship `.DAT`: field layouts (flight-model and
  weapons phases); `.BOX/.BL/.BND`; `SHADES.DAT`.
* VCR header fields and the event stream (Huffman tree construction in `vcr_tape.c`).
* Realism byte order in `?REAL.PRF`; SIMPREFS fields.
