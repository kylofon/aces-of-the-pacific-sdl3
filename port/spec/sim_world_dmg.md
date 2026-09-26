# sim_world — objects, scenario, damage, collisions, crashes, ships

Part of the `sim_world` spec (index: `sim_world.md`). Segments (ownership per `sim_flow.md` §0):
`56ac` snario.c, `45cc` acedata.c, `465c` object creation (not 04ee/0589), `637f` alive tests
(not 00af), `1641` misctbl.c, `36ce–36ea` utilities, `4b3a` damage.c, `655d` damage application,
fuel/engine, crash states (not 038a), `085b` proximity / mid-air collisions, `088a` impact /
crash handling, `0916` parachutes and debris, `10bf` death states, `14e0` collision support,
`0fd4` G load and blackout, `5410` ship movement, `490a` clouds (hit boxes, line of sight).
Confidence: **verified** = read in the disassembly, **likely** = decompile, **guess**.

## 1. Mission set-up (`56ac` snario.c, `45cc` acedata.c, `465c`)

Called from `sim_init`/mission start (`4e0d`, sim_flow):

```
56ac:010b scenario_module_init   AOP_COMM.TBL (7074), DS:07DF..: cleared, DS:3F22 = 70, DS:3F24 = 66
56ac:0236 scenario_scan(buf, seg, len)      pass 1 over SCRIPT.DAT (counts, loads models/areas)
56ac:089e scenario_build()                  pass 2: creates planes, ships, places, flights
56ac:18e5 scenario_free / 56ac:07b4 scenario_unload
```

### 1.1 Record reader (`56ac:0184/019e/01dc`, `36ce`)

`36ce` is a byte-stream reader over the in-memory script (`DS:715C` far cursor, `DS:715A` bytes
left): `36ce:0008 rd_open(far p, n)`, `36ce:001b rd_skip(n)`, `36ce:002d rd_read(dst, size,
count)` (copies up to `count` records of `size` while enough bytes remain, returns records
read), `36ce:0076 rd_tell()`. `56ac:0184 script_open(far p, len)` = `rd_open` + `DS:450E = 0`.
`56ac:019e script_next()`: when the current block is exhausted (`DS:450E == 0`) read `u16 type`
→ `DS:4510` and `u16 count` → `DS:450E` (returns 0 at the end), then `DS:450E−−`, return 1.
`56ac:01dc script_skip_record()`: skips one record of the current type — **quirk**: only type 7
(waypoint) is skipped by reading its 2-byte head (and nothing more) — every other type is skipped
by `rd_skip(<size of the type>)` through `36ce:001b` with the size left in a register (read with
x86dis before porting).

### 1.2 `56ac:0236 scenario_scan(far script, int len)` — verified (disassembly)

Zeroes `DS:4513..4744` (0x119 words), `DS:477B..47D4` (header), a local pilot-used table, and
the counters `DS:4763[4]` (groups per kind), `DS:476B` groups, `DS:476E` places, `DS:4770`
type-3 records, `DS:4772` ship groups, `DS:4774` ships, `DS:4776` planes, `DS:4778`. Skips the
leading u16 version (`script + 2`, `len − 2`). Per record (switch table `56ac:07A0`):

| Type | Reads | Effect |
|---|---|---|
| 0 header | 5Ah bytes → `DS:477B` | mission header (§1.4) |
| 1 aircraft | 16h bytes | `DS:4601[type]++` (count per aircraft type; first use of a type counts a new model); pilot slot marked used; pilot 44 (player): `player_type = type`, `DS:44F8 = rec+7`; `DS:4776++` |
| 2 ship | 10h bytes | `DS:451B[type]++` (new model), `DS:4774++` |
| 3 | nothing | `DS:4770++` (never present) |
| 4 place | 0Ah bytes | place list (12 bytes: i32 x, i32 y, 0), `DS:476E++` |
| 5 group | 3Ah bytes | `DS:476B++`; kind 1 (ship group): `DS:4772++`, `DS:451B[0] = 1`; `DS:4763[kind]++` |
| 6 | — | nothing (invalid type is simply not skipped: a script with type 6 desynchronises) |
| 7 waypoint | 2-byte head (+0Ch or +4) | `DS:473F += 14` (kind 0) or `+= 8`, `DS:4741++` |
| 8 msg offsets | — | remembers the stream position in `DS:4745` (first time), skips |
| 9 msg text | — | `DS:4749` likewise |

Then: `45cc:0056 model_slots_assign(DS:4601, DS:451B)` (§1.5); `DS:4778 = planes + ships`;
`DS:4513 = number of models + 2`; `56ac:00cf(1)` (wind, §1.6); `45cc:00a0 pilots_load(used,
DS:4781)` (§1.7); area number `DS:477D` (overridden by `DS:0536` from `-W<n>`) → `"AW####"`;
**`DS:55D6 = name list "pfname<mask>"` (0x9F entries): the *plane file names* of the aircraft
types** (`PFNAME<n>.TXT`, `n` = `DS:4781` header+06 bit mask — data.md §3.3 calls these "pilot
first names"; they are model base names, as `SFNAME<n>` = *ship file names*, 0x73 entries);
cockpit for the player's type (`644a:0000`), LSO bitmaps (`50c0:0000`); area `AW<n>.TBL` shapes
(`7074:02d8(0, name)`), `AW<n>.MBL` macros (`34f1:0310`), world objects and targets
(`62d2:049e("AW##", places, DS:44FA, n)`), `G_ATTACK.DAT` for the area (`0deb:18e6(area)`),
terrain `GID:` (`3368:0001`), misc tables (`1641:000c`), effect shapes (`69d0:001c`), damage /
gun list / box list tables (`4b3a:028f`, `4cda:0021`, `48af:0000` with `DS:4778 + DS:4772`
slots), aircraft data (`45cc:0510`), then the shape tables `<type>.TBL` of every used aircraft
(bank 2, `DS:4601[type]` becomes the shape handle), `DS:3F0E/3F0C/3F0A` bank numbers, ship data
(`45cc:0632`) and ship shape tables (bank 3, `DS:451B[type]` = handle), `DS:3F08`.

### 1.3 `56ac:089e scenario_build()` — verified

```
DS:3B09 = DS:3B07 = 0
plane pool (465c:0336, DS:4776 × 107h), ship pool (465c:04a3, (ships + ship groups) × 88h)
DS:475B = DS:475D = calloc(2·(DS:4778 + DS:4772)): object list (planes first, then ships);
DS:4759 = &list[DS:4776] (ships)
DS:4761 = calloc(DS:473F) waypoint storage, DS:475F = calloc(2·DS:4741) waypoint pointers
DS:4753 = calloc(56h · groups) flight records, DS:4751 = pointer array to them
DS:4755 = calloc(20h · places)
465c:001c(40) (DS:00BC list of 40 moving things), 4963:000a, fm_reset_globals, 56ac:00cf(0)
pass A: type 1 → 465c:015f plane_create(rec) into the list; type 2 → 465c:0395 ship_create;
        type 4 → place (+4 x, +8 y, +0C z = 0, +1C/+1D kind bytes)
56ac:0809 places_link: place i with DS:44FA[i] ≠ 0 gets shape/position of world target i
pass B: type 7 → waypoint pointers, 56ac:0b78 waypoint_read (14-byte kind-0 records: kind,
        index, i32 x, i32 y, i32 z; other kinds 8 bytes: kind, index, i16, i32?) — Ghidra garbles
        0b78, read x86dis
pass C: type 5 → 56ac:0c6a flight_build(&DS:4753[i], rec, stream pos)
56ac:0fc2 flights_place (§1.3.1)
56ac:009d copy the flight-map name (0x14 or 0x5E + … `DS:4743 = DS:42C9`)
if the player's flight has a carrier (+3) whose ship group is flagged (+3B & 2) and the player is
   within 40000 (9C40h, 277a:3bfc) of it: 51fb:0199(flight, 0) (carrier deck spawn)
```

#### 1.3.1 Flight placement (`56ac:0fc2`, `10a8`, `1483`, `1783`)

`56ac:0f96` sorts the flight pointers (`qsort` 0000:450c with comparator `56ac:0f26`: by
`DS:0815[kind]`, escorts after their charges) and sets `DS:474F = &flights[DS:4765]`.
For each flight: `56ac:1783 flight_link(f)` collects every flight transitively linked to `f`
(`56ac:16f9`: same-side pairs where one escorts the other (`+3E`), a role-6 flight protects it
(`+10[0..2]`), or a role-5 flight covers it (`+43` mode 0: its list; mode 2: the other's
waypoints)); all linked aircraft flights get cruise speed `+30 = min(aircraft .DAT +73)`; the
list goes to `f+44` (count) / `f+46`.
* aircraft flight → `56ac:10a8 flight_place_planes`: for each member i: `Plane+34 = f`, `+BC = i`,
  `+66 = FMD pointer`, `f+42 = side`; **on the ground** (`f+26 == 0`): parked/spot position by
  `4edf:0780` (airfield) or `4edf:057f` (carrier deck, `f+3` set), shape state bytes from the
  shape's state count, gear down (`+BA |= 10h`); **airborne**: heading `f+1C`, leader at the
  waypoint (`17fe:000b`) or `69d0:007d`, altitude `f+26` if the waypoint has none; wingmen at the
  formation slot (`4edf:1278` + `3678:0004`); throttle `+B2` = E6h airborne / 0 parked;
  `f+4E` = leader altitude (min 10000); `fm_init`; brain `69fe:0015`; add to `DS:00BC` list;
  ordnance defaults from the flight record (`+EB/+EC/+ED`, `+F1` torpedo, `+F3` 3 × (station
  kind, count)); **mass** `Plane+B6 = 400h + old + (Σ DS:0819[kind]·count + torpedo·TORPS[side]
  .+04) << (10 − DAT[5Ah]) / DAT[0]` (+ `.DAT+7F` with a drop tank, `Plane+1A & 4`) — `.DAT+0` is
  the empty weight;
* ship group → `56ac:1483 flight_place_ships`: leader at the waypoint, ships at their formation
  offsets `+68/+6C` (default offsets from `DS:12A4` table when both are < 2), brains via
  `5410:02c0`.
Finally `DS:3B07 = player's flight`; planes whose flight is the player's or linked to it get
`Plane+1C |= 4` (friendly to the player's flight).

### 1.4 Mission header (`DS:477B`, 90 bytes = SCRIPT.DAT type 0) — fields used by the sim

| Off | DS | Meaning (sim use) |
|---|---|---|
| 00 | 477B | kind (0 single/quick; `== 1` → `DS:476D`) |
| 01 | 477C | mission type (5 = training: no flak, no fuel burn, …) |
| 02 | 477D | area n |
| 04 | 477F | wind 0..3 (`DS:4512 = (wind == 3)` stormy); `DS:477A = wind` |
| 06 | 4781 | name-list mask (pfname/sfname file number) |
| … | | see data.md §2.1 |

### 1.5 `45cc` acedata.c — model data

| Address | Name | Signature | Does | Conf. |
|---|---|---|---|---|
| 45cc:0000 | slots_from_counts | far int (int count[], u8 slot[], int n) | `slot[] = FFh`; every type with count ≠ 0 gets the next slot; returns the number of slots | verified |
| 45cc:0056 | model_slots_assign | far (planes[], ships[]) | `DS:54BA = slots(planes, DS:54BC, 9Fh)`, `DS:54B8 = slots(ships, DS:555B, 73h)` | verified |
| 45cc:0080 | rating_lerp | far int (v, lo, hi) | `((hi − lo)·v >> 10) + lo` (v = 0..1000 rating, 32-bit product) | verified |
| 45cc:00a0 | pilots_load | far (u8 used[0xC2], int mask) | name list `PILOT<mask>` (0xC2 names); `DS:55CE = malloc(0xC2·70h + 184h)`: pointer table + one 70h record per used pilot (`<name>.PLT`); converts ratings (§1.7) | verified |
| 45cc:032a | pilots_free | far () | | verified |
| 45cc:034f | aircraft_load | far ptr (int type) | 131-byte `<name>.DAT` + 214-byte `<name>.FMD`: `.DAT+24 = FMD copy`; `.DAT+08 = ilog2(.DAT+04) + 1`; `.DAT+73 = (fm_cruise_speed(fmd, 10000)·700 >> 10)·DS:3F22 >> 10`; `.GL` (`4cda:0037`), `.DMG` (`4b3a:0341`), `.BXL` (`48af:0017`) into the slot tables; engine sound type `.DAT+75`: 5 → 2 when `DS:269D == 0` | verified |
| 45cc:0510 | aircraft_load_all | far (int count[]) | `DS:55D2 = calloc(2·slots)`; `DS:55D2[slot] = aircraft_load(type)` | verified |
| 45cc:0556 / 059e | aircraft_free / _all | | | verified |
| 45cc:05ce | ship_load | far ptr (int type) | 154-byte ship `.DAT` (name list `DS:55D4`) | verified |
| 45cc:0632 | ship_load_all | far (int count[]) | `DS:55D0[slot] = ship_load`; `.GL`/`.DMG`/`.BXL` with slot `slot + DS:54BA` and the ship flag | verified |
| 45cc:0748 / 076e | ship_free / _all | | | verified |
| 45cc:079e | file_load_far | far ptr (name) | whole file into a far block (`24b2:013d`) | verified |
| 45cc:0822 | forms_load | far () | `FORMS.DAT`: 0x198 + 0x1C0 bytes → far blocks `DS:12A8`/`DS:12A4` (formation offset tables: `DS:12A4` = ship group offsets used by `56ac:1483`) | verified |
| 45cc:0900 | view_cycle_reset | far () | `DS:3B01 = FFFFh` (sim_flow's object cycling) | verified |

### 1.6 Wind (`56ac:0000/00cf`)

`56ac:00cf(load)`: `DS:4512 = (header.wind == 3)`; if `load`: `DS:477A = wind`,
`wind_load(wind)`: loads the named `.WND` (74 bytes) **twice** into `DS:0014..` and `DS:005E..`
(37 words each — the name is built by `368f:02e6`; both copies come from the same file). All four
`.WND` files are identical, so wind has no effect beyond `DS:4512`/`DS:477A` (clouds: §7).
`DS:476D = (kind == 1)`. — verified

### 1.7 Pilot profiles (`.PLT` → 70h-byte records, `DS:55CE[pilot]`)

`.PLT` = 112 bytes: u16 ratings `r[0..16]` (0..1000), …, +58h name. `pilots_load` converts in
place (`rating_lerp`):

| Word | From | Range | Used as |
|---|---|---|---|
| 0 | r0 | 200h..44Ch | aggressiveness? (`+48` = r0 → 334h..3B6h) |
| 1, 2 | r1 | 500..400h, 100..44Ch | |
| 3 | r3 | 150..−30 | |
| 4 | r4 | 100..1000 | |
| 5 | r5 | 600..−200 (≥ 0) | |
| 6 (+0C) | r6 | 8000..14000 | **max bank** (`steer_heading`) |
| 7 (+0E) | r6 | 1000..1800 | **turn coordination** k (`plane_fly`) |
| 8 (+10) | r8 | F3h..100h | **cruise throttle** |
| 9, 10, 11 | r9 | −300..70, 900..−240, 7500..11000 | |
| 15 (+1E) | r9 | 400h..1 | gunnery (hit chance reduction, `56ac:0b78`/AI) |
| 12, 13 | r12 | 500..−150 | |
| 14 | r12 | 200h..400h | |
| 16 (+20) | r12 | 500..900 | flak "lucky burst" threshold (`04c4:0860`) |
| +41 | byte | | evasive pilot (flak aims poorly) |
| +46 | word | | used by `69fe:015c` (engage) |
| +58 | char[24] | | name (kill messages) |

Pilot 44 = the player (`PLAYER.PLT`). Names of the remaining ratings: open.

### 1.8 Object creation (`465c`)

| Address | Name | Does | Conf. |
|---|---|---|---|
| 465c:0000 | objects_module_init | | verified |
| 465c:000b | movers_reset | `DS:00BA = DS:00BE = 0` | verified |
| 465c:001c | movers_alloc(n) | `DS:00BC = calloc(2n)` | verified |
| 465c:0032 | angles_from_bytes(int out[3], i8 b[2]) | `out = {b0 << 8, 0, b1 << 8}` | verified |
| 465c:005a | object_init_common(obj, size, has_22) | `+20 = calloc(2Ah)` (matrix cache, `365a:0074`), `+16 = calloc(size)`, optional `+22 = calloc(12)` (ships: `{1000h, 4000h, radius (1c30:00ee: max(1.5·shape radius, 400))}`), brain scratch (`59f9:004e`) | verified |
| 465c:00ee | plane_c0(p) | `(i8)p+C0` | verified |
| 465c:00fd | plane_setup(p, pilot, type, side_idx, angles*) | `+26 = DS:00C0[side]`, `+19 = type`, `+02 = shape DS:4601[type]`, `+BB = pilot` (44 → `DS:3B09 = p`), angles | verified |
| 465c:015f | plane_create(rec22) | §1.8.1 | verified |
| 465c:0322/0336/034c | plane_free / pool_create / pool_destroy | pool `DS:3B05` (107h) | verified |
| 465c:0381/04a3/04b9 | ship_free / pool_create / pool_destroy | pool `DS:3B03` (88h) | verified |
| 465c:0395 | ship_create(rec16) | §1.8.2 | verified |
| 465c:04ee | (sim_flow) cockpit `.LBM` name | | — |
| 465c:0589 | (render3d) draw sort comparator | | — |
| 465c:0818 | objects_module_end | empty | verified |

**1.8.1 `plane_create(u8 *rec)`** (SCRIPT.DAT type 1): alloc from `DS:3B05`, flags `|= 8800h`,
`+18 = 0`, class 3 (`637f:0015`); angles from `rec+8` when `rec+0A ≥ 0`; `plane_setup(p, rec[2],
rec[0], rec[1], angles)`; `object_init_common(p, 8, 1)`; `rec[3]` → `+1A |= 4` (drop tank);
player with `.DAT+39` → `+1B |= 8` (armour/gunsight?); gun list `4cda:00f8`, damage state
`4b3a:03ff(slot, &+28, &+2A, p)`, box list; `+C9 = DS:00BA++`; ordnance: `rec[0C] == FFh` →
`+EC = FFh` else `+EB = +EC = rec[0D]`, `+ED = (1 << rec[0D]) − 1` (rocket/bomb bitmask); `+F1 =
rec[0E] == FFh ? FFh : rec[0F]` (torpedo); `+F3..F8 = rec[10..15]` (3 stations: kind, count);
`rec[5] != 0` → initial damage `655d:1f03(p, rec[5] << 3)`.

**1.8.2 `ship_create(u8 *rec)`** (type 2): pool `DS:3B03`, `+18 = 1`, `+19 = type`, `+26` =
side byte of flight `rec[1]` (`+C0`), class 4; shape `DS:451B[type]` unless type 0; `+68 = rec+8`,
`+6C = rec+0C` (i32 formation offsets); `object_init_common(s, 0Ch, 1)`; gun list, damage state
(ship flavour), box list `+24`; `rec+2 != 0` → initial damage `655d:1f69(s, rec+2 << 3)`;
`rec[6]` → `+1E |= 2` (torpedoes do extra damage), `rec[7]` → `+1E |= 4` (bombs do extra damage).

### 1.9 Alive tests (`637f`), misc tables (`1641`), utilities (`36d6..36ea`)

| Address | Name | Does | Conf. |
|---|---|---|---|
| 637f:0015 | obj_set_class(obj, c) | `obj+0 = c | (obj+0 & FFE0h)` | verified |
| 637f:002b | obj_alive(obj) | ship: `+19 != 0`; plane: `+18 == 0 && !(+1A & 1) && !(+1B & 1)` | verified |
| 637f:0073 | ship_is_real(obj) | `+19 != 0` | verified |
| 637f:008a | list_next(i) | `(i+1) % DS:4778` | verified |
| 637f:009a | flight_is_carrier_group(obj) | `obj+34 → +3B & 2` | verified |
| 1641:000c | misctbl_load(area) | `<area>.TBL` table (`7039:020a`) → `DS:18D6`; `<area>.DAT` object type table → far `DS:18DA`, 26-byte records, `DS:18DE` count, FFFFh terminator | verified |
| 1641:0109 | misctbl_free | | verified |
| 1641:0142 | objtype_shape(i) | `DS:18D6 + 4i + 6` | verified |
| 1641:0157 | objtype_class(shape) | stub (returns the argument's type index; used ×8 into `DS:5A82` damage table) | verified |
| 1641:0172 | objtype_aa(i) | `DS:18D6[4i+4]`: 1 → 3 (heavy flak), 2 → 8 (light AA), else 0 | verified |
| 1641:01a5 | objtype_names(id, a, b) | copy the two names of type `id` | verified |
| 36d6:0002 | fill_seq(int *a, v, step, n) | `a[i] = v + i·step` | verified |
| 36d8:000a | find_int(int *a, v, n) | index or −1 | verified |
| 36db:0009 | fill_int(a, v, n) | | verified |
| 36dd:0009 | bits_to_list(int *out, u8 *bits, n) | indices of set bits; returns count | verified |
| 36e3:0005 / 0032 | bytes_or / bytes_and(dst, a, b, n) | | verified |
| 36e8:000f | all_zero(char *p, n) | | verified |
| 36ea:000e | gather(int *out, int *tbl, int *idx, n) | `out[i] = tbl[idx[i]]` | verified |

## 2. Damage data (`4b3a` damage.c)

`4b3a:025c damage_init`: effect shapes bank (`7032:0039`), `DAMAGE.BMP` sprites
(`243d:004c` → `DS:519C`), `DS:474D = 0`, then `4b3a:0061` registers the effect animations
(`<name>.BMD`, `241c:0005`) at `DS:474D + 0Ch … + 20h`: flak1–4 (+0C..+0F, 200), explosn/torexpl
(+10, 1800), … (pairs of name/duration from `DS:0174..`: see the string list in the index:
bulspl, dirtpuf, explosn, firball, fire, firsmk, flak1–4, frsmkst, grfirsm, grfsmst, grndsmk,
grsmstr, medspla, planexp, planfir, plfrstr, puff, torexpl, torspla). Effect indices used in the
code: +10 torpedo explosion, +11 torpedo splash, +12/+13 splash/dust, +14 crash on land, +18
wreck fire, +1C fire/explosion, +1D..+20 burning ground objects, +21..+24 parachutes/debris, +27
bullet spark, +29/+2B wrecks (plane/ship).

`4b3a:028f damage_tables_alloc(n)`: `DS:0172 = calloc(2n)`.
`4b3a:0341 dmg_load(slot, name, is_ship)`: reads the u16 header, size `(n & 0Fh)·10 + 10h`
(aircraft) or `·8 + 4` (ships) including the header, stores `DS:0172[slot]`. — verified
`4b3a:03ff dmg_state_create(slot, &dmg, &state, obj, FlightRec *f)`: state (14h bytes aircraft,
8 ships): `+0 total = 0`, `+2 obj`, `+4 = calloc(2n)` zone damage, `+6 = malloc(n)` zone bytes
(FFh); aircraft with a flight record: **fuel** `+0C i32 = (f[4] << 10 >> 8) << 18` without a
drop tank (`f[3] == 0`); with one: `u = f[4] << 11 >> 8`: `u ≤ 200h` → `+0C = u << 18`, else
`+0C = 800_0000h` (full) and `+10 = (u − 200h) << 18` (drop tank); `+08 = 0`. — verified
`4b3a:02aa damage_reset`: player engine/oil globals: oil `DS:5196 = DS:5190 = 7FFFh`, temps
`DS:5198 = DS:5192 = 200h`, leak/wound flags `DS:0FE8..0FF4 = 0`, warning timers
(`1ba4:0003`), engine-stop timers `DS:515C = DS:5160 = −1`.

### 2.1 `.DMG` layout (verified by use; 82 files)

```
aircraft: u16 hdr; i16 k[7]; n × zone (10 bytes)
   hdr bits 0–3 n zones, 8–11 number of engines (zones 0..e−1 are engines), 12–15 flags
       (8000h, 4000h, 2000h: see 4.3 — structural-failure / fire types)
   k0 +02 airframe vulnerability (damage × k0 >> 10; F4U 1050, Zero-22 2250, B-17 720)
   k1 +04 engine vulnerability (3000)
   k2 +06, k3 +08 (204/153 …) ?
   k4 +0A main-tank fuel burn factor (× throttle), k5 +0C drop-tank burn factor
   k6 +0E ?
   zone: i16 x, y, z (position in model units), i16 ?, i16 ?
ships: u16 hdr; i16 k; n × zone (8 bytes: i16 x, y, z, i16 ?)
   hdr bits 0–3 n, 4–7 armour: bullets of gun type < armour do nothing (Yamato 15, tanks 0),
       8–11 kind (2 = two-engine? for planes), 15 = leaves a wreck (else explodes)
   k +02 vulnerability (Yamato 2, tank 800; damage × k >> 10, ≤ 400h per hit)
```

## 3. Damage state and totals

Every object's damage state `+2A → [0]` is **0..400h (1024 = destroyed)**. Ships sink at 400h;
aircraft at 400h are shot down. Zone damage words also saturate at 400h.

## 4. Damage application (`655d`)

### 4.1 `655d:0bd9 damage_apply()` (per frame) — verified (disassembly)

```
for each plane p (DS:475B[0..4776)) alive:             // fuel burn
    if p == player and !DS:42CE (limited fuel off): skip
    s = p.dmg_state; burn = dt(throttle(+B2)·k[drop ? +0C : +0A] >> 10)·2
    drop tank (s+10) non-zero ? s+10 −= burn : s+0C −= burn   (floor 0)
    player with no fuel left: throttle = 0
    s+0C + s+10 < 666666h → p+1A |= 8 (low fuel)
for each event {w, t, dmg} (DS:00E8[0..DS:00EA)):
    player = (t == DS:3B09); class = w ? w.kind & 0Fh : FFFFh
    d = (dmg == 1F40h (8000)) ? 7A120h (500000) : (class is bomb or torpedo) ? dmg << 4 : dmg
    if player && w && !DS:42CF (damage off): hit sound only (088a:045f); continue
    if !alive(t) or t+1A & 40h: continue
    rel = the hit position in t's frame (w.pos − t.pos rotated by t's matrix) or (0,0,0)
    ship (t+18 == 1):
        bullets below the ship's armour class: continue
        before = total
        if total < 400h:
            if (t+1E & 2 and torpedo) or (t+1E & 4 and bomb): d ·= rng_range(7) + 1   (RNG)
            ship_hit_zone(t, rel, d) (655d:1e2f)
            if total − before ≥ CDh and rng_range(400h) < 136h: total = 400h        (RNG: magazine)
            torpedo: spawn a torpedo-explosion effect at the hit
        else total = 400h
        if total ≥ 400h: hdr & 8000h ? wreck shape (10bf:001a) : explosion + fire
            effect (+18) at the ship, 655d:1f69(t, 400h) (all zones 400h), t+1B |= 2 (sunk),
            brain → state 1009h (69fe:0015)
    plane:
        z = plane_hit_zone(t, rel, d) (655d:1c75); before = total (saved first)
        if z ≥ engines and the zone is already 400h: total = 400h
        if w: s+0A += total − before            (damage by weapons, for credit)
        if total == before: nothing more
        if total ≥ 400h:
            player: DS:0FED = 1 (break-up); w → DS:3EF7 = 1; 655d:1f03(player, 400h)
            else: hdr & 8000h ? (rng_range(400h) < 200h ? 1 : 2) : (r < 155h ? 0 : r < 2AAh ? 1 : 2)
                  0 → 655d:0887 (engine fire → falls), 1 → 655d:022e(t, 8000h) (spins down),
                  2 → 655d:022e(t, 1) (breaks up)
        else:
            first time over 3FFh… (engine zone reaching 3FFh): player → 655d:0842(zone) engine power −9Ah
                                                      AI with 1 engine → t+1A |= 2 (smoking)
            AI multi-engine, hdr & 2000h, zone < engines and zone at 400h: bail-out chance:
                0916:02cc (debris), a parachute effect, t+16 bytes: [0] = 3, [1] = 0, [3/+1] = 1,
                t+26 == 0 → [5] = 0; total = 400h; 655d:022e(t, 1)
            if s+08 (hit counter, ≥ before…): per hit s+08 += 100h; with r = rng_range(400h)
                (RNG) below DS:0FD8/0FE0[(s+08 >> 8) & 3] ({100, 200, 400, 600}) a **critical**:
                player: pick c by walking DS:0FB8 = {140, 99, 140, 156, 222, 222, 48} with a
                second random 0..3FFh → 655d:08fd(c, …) (§4.2)
                AI: table by aircraft class (DS:0F8E fighters {250 ×5}, DS:0F98 torpedo/dive,
                DS:0FA2 bombers {200, 200, 500, 200, 200}) → 655d:0b08(c, …) (§4.3)
    AI shot by the player on the player's side: "friendly" message (string 3, 3)
    total changed: 088a:054f credit/kill messages (t, w, delta)
spawn the queued hit effects (up to 3 × 30h-byte records, 05a9:005a)
655d:159d player_engine_update()
```
`655d:1c75 plane_hit_zone(Plane*, Vec *rel, i32 d)`: nearest zone (`3684:000c` distance to
zone position, zones at `dmg+10h`, 10 bytes); `dd = d·(zone < engines && engines != 1 ? k1 : k0)
>> 10` capped 400h; zone damage `+= dd` (≤ 400h, `655d:1f98`); a non-engine zone (or single
engine) sets `total = zone damage`; engine hits reduce the engine power factor `Plane+A4`
(`/engines` for AI; for the player zone 0 → `+A4`, zone 1 → `+A6`), floor 0; player with 2
engines: prop torque `Plane+A8 = (sign(zone0.x)·A4 + sign(zone1.x)·A6) >> 2` (asymmetric
thrust). Returns the zone. — verified
`655d:1e2f ship_hit_zone(obj*, Vec *rel, i32 d)`: nearest zone (8-byte zones at `dmg+4`); `dd =
min(d·k >> 10, 400h)`; `total = min(total + dd, 400h)`; zone += dd; if the zone reached 400h,
total = 400h. — verified

### 4.2 Player criticals `655d:08fd(c, …)` — verified

| c | Effect |
|---|---|
| 0 | pilot wounded: `DS:0FEB = 1` (message 3,0) |
| 1 | oil / hydraulics: if the DMG hdr lacks 8000h: `DS:0FED = 1` structural (message 3,4) |
| 2 | fuel leak: `DS:0FEA = 1` (message 3,1) |
| 3 | fire: if `+1A & 4` (drop tank): clear it, drop-tank fuel = 0, fire effect, sound 5, damage 150 at a fixed offset `DS:0FC6` = (0, 0, −100) through `plane_hit_zone`, `s+08 += 100h` if total > it; message (3,3) |
| 4 | oil leak on an engine: 2-engine type: the side by `r & 1` → `DS:0FE8`/`DS:0FE9`; else `DS:0FE8`; message (3,2) once |
| 5 | weapon station destroyed: `0ff4:0186(player guns, 0)`, `DS:3EF5 = 1` |
| 6 | engine hit: `655d:0842` (engine power −9Ah) |
| 7 | (total > 1C2h) pilot hit badly: `DS:0FEB = 1`, `DS:0FF2 = 7` (fade out), `DS:0FF4 = 0`, `DS:0FEE = 0` |

### 4.3 AI criticals `655d:0b08(c, …)`

| c | Effect |
|---|---|
| 0 | (only for type 1 hdr…) engine 1 power −100h, `+1A |= 2` (smoke) |
| 1 | fire/explosion `655d:0887` unless (hdr & 8000h and `r < DS:0FAC[kind]` = 409) |
| 2 | station destroyed `0ff4:0186(p.guns, rel)` |
| 3 | spin down: `655d:022e(p, 8000h)`, total = 400h |
| 4 | (hdr & 4000h, `r >= DS:0FB2[kind]`): engine dead: `+A4 = 0`, `655d:022e(p, 1)`, total 400h |

### 4.4 Going down (`655d:0000/009b/01e7/022e/0842/0887`)

| Address | Name | Does | Conf. |
|---|---|---|---|
| 655d:0000 | crash_effect(Plane*, i32 ground) | ground < 0 (water): effect `+14` with size `DS:0FCC[class]` = {200, 400, 600}; land: `+1C` with `DS:0FD2` = {100, 200, 300}; class = DMG hdr >> 4 & 3 | verified |
| 655d:009b | state_going_down(Plane*) | brain state (via `DS:3DFF` thunk): at the ground: crash effect, `10bf:0039(p, ground ≠ 0)`; `state & 8000h` clear (spinning): pitch to −(steep) (`steer_pitch_to(32C000h)`), throttle FFh, aileron FFh, `+C1 |= 10h`; set (gliding): elevator 200, flips when stalled/near stall, pitch > 8000 or |roll| > 2000; `state & 2000h` (crew bailing out, above 8000): timer; `state & 1000h` clear: 30% (`rng_range(400h) < 134h`, **RNG**) start bailing else wait 1900h; bailing: parachute (`0916:00b3`), count−−, next in F00h; `plane_fly` | verified |
| 655d:01e7 | plane_mark_down(Plane*) | player's wingman: radio "going down" (1815:06e7(58h)); `+1A |= 40h`; AI bookkeeping `1142:135b` | verified |
| 655d:022e | plane_shoot_down(Plane*, u16 how) | crew = stations still loaded (`0ff4:0289`) + `how` low byte (0 in training), −1 for the player; mark down; at the ground → crash now; brain state `how | 2000h` (crew) (`| 3000h` for pilots ≥ 45: famous aces bail out immediately; else wait 1900h); how & 8000h: elevator 200, throttle 0; else elevator −FFh, throttle FFh; player: `DS:0FEC = 1`, `DS:42BF = 1` | verified |
| 655d:0842 | player_engine_hit(zone*, r) | engine 2 (kind 2 DMG and `r & 1`) power `+A6 −= 9Ah` else `+A4 −= 9Ah` (floor 0) | verified |
| 655d:0887 | plane_fire(Plane*, state*, r) | fire flag byte `(+16)[3 + (r&1)] = 1`, fire effect, sound 5, total = 400h, zone `r & 1` = 400h, `plane_shoot_down(p, 1)` | verified |
| 655d:0322 | damage_tables_load | `GDAMAGE.DAT` → `DS:5A82` (13h × 8-byte object damage classes: +2 fire effect, +4 fire shape, +5 hardness, +6 damage factor), `SHIPSIZ.DAT` → `DS:5178` (3 × 8), three effect classes (`59f9:0000`), `2e33:0006(200h)` | verified |
| 655d:1ada, 1b0a, 1bb7 | effect callbacks | animation step / attached effect follow / drifting smoke (render3d side) | likely |
| 655d:1f03 | plane_damage_all(Plane*, v) | total and every zone = v; engine power `−= v` (player 2-engine: both) | verified |
| 655d:1f69 | obj_damage_all(obj*, v) | total and zones = v | verified |
| 655d:1f98 | zone_add(state*, z, d) | `zone = min(zone + d, 400h)` unless already 400h; returns it | verified |
| 655d:1fd0 | clamp_word(int *p, lo, hi) | | verified |
| 655d:038a | (render3d) muzzle flash / tracers | | — |

### 4.5 `655d:159d player_engine_update()` — likely

* Pilot wounded (`DS:0FEB`): screen-tint pulses (`1792:0032`) every `DS:0FEE` ticks, after 8
  stages → mission over (`5da1:0000(1)`).
* Unless the player is down (`DS:0FEC`): oil leaks `DS:5196`/`DS:5190 −= dt(6)`; fuel leak: main
  fuel `−= dt(B6h)·400h`; gauges `DS:3FE8/3FEA = fuel >> 17`; no fuel → `DS:42BE = DS:57DF = 1`;
  low fuel (< 666666h) → gauge bit 80h, message `DS:57E0`; drop tank empty → `DS:57E1`.
  Damage level `total` 500/2A3h/352h → `DS:3EF9 = DS:3EFB` = 1/2/3 (cockpit damage), > 100h →
  `DS:3EF8`. Two engines: split throttle by the oil ratio into `Plane+B4`.
  Realistic flight model (`DS:42D3 == 2`) with damage on: overspeed flag 8 → warning; flag 10h
  → "aircraft broke up" (message 1,37h), `plane_shoot_down(player, 4001h)`; speeds over FMD `+C6`
  / `+C0` → message flags `DS:57E2` / `DS:57DD`.
* **Engine burnout** (`DS:42CB`): temperature `DS:5198 += dt(throttle + FFh − (oil >> 7) ≥ F5h ?
  10 : ≥ E8h ? 0 : −10)`, clamped 0..5000; > 682h overheating (gauge bits 1/2, message); > 9C4h:
  every 3200h ticks engine power `−= 66h`. Second engine the same with `DS:5192`/`DS:5194`.
* An engine below 7Dh power stops after 12C00h ticks (`DS:5160`/`DS:515C`); warning message.

## 5. Collisions

### 5.1 Ground / water / ships (`088a:01d3 impacts_update`, per frame) — likely

For each alive plane `p` (not landed-damaged, or the player when collisions are off):
`ground = collision_ground(p.pos)` (`14e0:06c0`: terrain/objects height below, 0 at sea, i32);
if none: `p+EF = ship under p` (`088a:00b1`: ships within 5000 whose boxes the vertical segment
down to 708h crosses, returning the deck point) and ground = deck height; `p+B8 = ground`
(Controls ground height for the FM). **Crash** when `p.z < ground`, or on a ship deck with the
ship flagged `+1B & 2` (sunk): sound 12h, a proximity event `{0, ship, 8000}` against the ship,
`crash_effect`, `10bf:0039 plane_die(p, ground ≠ 0)`, `1142:135b`. Landed normally
(`z == ground + gear height`): `z = ground + 1`, and the landing state `DS:0453` table dispatch
(two entries) — read x86dis.

`088a:045f hit_sound(far w, Plane *by)`: remembers 6 positions `DS:5604`; sound by weapon class:
bombs 4/5/6 by MEC index (< 4, 4, ≥ 5), torpedo 6, rockets 4, bullets: 14h if the player fired,
18h if the player was hit (only with `DS:19F2`), flak 8.
`088a:054f kill_credit(Plane *t, far w, int delta)`: messages to the player ("You just shot
down <ace name>" for pilots > 44 of the other side; friendly-fire notices; per target kind:
fighter/bomber (class 3 → 7)/ship/carrier (`.DAT+6C == 1` → 9), +4 for Japanese); radio from
flight mates; `088a:045f`; **`1899:0cf0(shooter, t, class, mec, delta, destroyed)`** (scoring,
sim_flow). `088a:07ab ground_credit(obj, far rec, idx, far w, delta)`: player hitting a friendly
target (US `+0` / Japan `+1` target type 2 / 10h) → warning; destroyed ones: name from
`0deb:1b1f` in a message; `1899:102f` (score).

### 5.2 Mid-air (`085b`) — verified

`085b:0085 proximity_update()`: for each alive AI plane within 1000 (3-D) of the player:
`085b:000b(p, player)` sets avoidance flags; with realism mid-air collisions (`DS:42D0`), within
200 and no grace time (`DS:1382 == 0`): events `{0, player, 8000}` and `{0, p, 8000}`, sound 1;
`rng_next & 3FFh < 100h` (**RNG**) → `DS:0FEB = 1` (pilot hurt). Then every pair of AI planes
within 600: flags on the non-bomber (bombers — class 3 — don't dodge each other).
`085b:000b proximity_flags(a, b)`: above 200 altitude: `+43/+47 |= 20h` if b's bearing (3614:0009)
minus a's heading < 1 else 10h (turn away); a below b: above 500 → 40h (dive); else 80h (climb).
`085b:02c3/02ce/02e5`: grace timer `DS:1382` (reset / count down / `max(timer, v)`, set by the
skip-ahead code).

### 5.3 Collision support (`14e0`)

`14e0:0002/006d`: allocate/free the near-object lists (`DS:18B5` far 474h, `DS:18B0` 800 words,
`DS:18B2` far 15E0h). `14e0:008c near_grid_update()`: every 1900h ticks or after moving 3000 from
`DS:582C`: rebuild an 8×… bit grid `DS:583A` of cells (size `DS:0C2E` shift, origin
`DS:0C4C/0C50`) occupied by low (< 20000) non-carrier-group planes. `14e0:0233 near_grid_test`.
`14e0:0286 near_objects_build()`: static objects of the current tiles near those planes (or
within 2904h/7B0Ch of the camera) into `DS:18B0` (max 200), expanding macro groups; AA sites
into `DS:18B5` (26h records, max 30, kind from `1641:0172`, side 1 for type 10h). `14e0:06c0
collision_ground(Vec *out, Vec *p, bool planes)`: above D700h nothing; below 36Ch: terrain
(`3368:0069` over the tile objects), then near objects / ships (`DS:513C`); else near objects.
`14e0:07aa ground_under` / `14e0:07db ground_height_at`: same queries. `14e0:01d3
clamp_world(obj)`: keep x/y within ±C16EC0h (12 676 800) unless above 5F5E100h.

### 5.4 Clouds (`490a`) — likely

Clouds exist with realistic weather (`DS:42C9`) and wind level 1 or 2 (`DS:477A`): grid cell
size `2^DS:3ECA` (12h = 262144), masks `DS:3EC2/3EBA/3EBE`; the counts per cloud kind from
`DS:0128`/`DS:0120` are shuffled (`277a:410d`) into the 32-entry kind table `DS:3D74`. Three
cloud objects (`DS:3E1E`, 1Ah words each, shapes `DS:474D + 1..3`, box lists `CLOUD0..2.BXL`
loaded by `490a:0137`) are re-positioned per cell by a hash of the cell (`14b8:0057/0072`):
`490a:030d cloud_at_cell` (altitude 50000). `490a:03fb point_in_cloud(p)`, `490a:043e
cloud_blocks_segment(a, b)` (line of sight for spotting, ≤ 15 × 15 cells), `490a:017f
camera_in_cloud`, `490a:0509 clouds_draw` (render), `490a:0590` shadows.

## 6. Aircraft death and parachutes (`10bf`, `0916`)

| Address | Name | Does | Conf. |
|---|---|---|---|
| 10bf:0005 | death_classes_register | two object classes (`59f9:0000`) | verified |
| 10bf:001a | wreck_shape(obj) | ship `DS:474D + 2Bh`, plane `+29h` | verified |
| 10bf:0039 | plane_die(obj, hidden) | hidden: flag 2000h, `+28 = 0`; else wreck shape; velocities 0; `+1A |= 1`; camera follow bookkeeping (`DS:1AFF`); brain → wreck state (timer 8000); player: `DS:42BF = 1`, `DS:523B = −1`, ditching flag `DS:5C97 = 3` if `+1C & 8` and above 1 | verified |
| 10bf:00d2 | wreck_update | wreck timer; at 0: hide; player → mission over; AI: z = 989680h (moved away), flags, brain | verified |
| 10bf:013a / 01d6 | carrier_rel_save / restore | save/restore the player's position relative to the carrier `+EF` (sim_flow uses them for the skip/LSO) | verified |
| 0916:000d | effect_set_anim(e, dur) | | verified |
| 0916:002e | para_load | `CHUTES.BMP`, `PARA_US/PARA_JP.BMD` → `DS:474D + 22h/23h` | verified |
| 0916:00b3 | parachute_spawn(Plane*) | not for flights of role 2; effect at the plane with its velocity, vz 8, gravity −20, callback `0916:0173` | verified |
| 0916:0173 | parachute_update(e) | above 1000: canopy opening: vz += g (g −= 20 while < 60) until ≤ −200, then 5 stages: at 4 vz >>= 1, at 5 vz = −10; horizontal drift decays >> 2; pos += v | verified |
| 0916:0273 | parachute_draw | | verified |
| 0916:02cc | debris_spawn(Plane*, zone*) | a piece (`DS:474D + 24h`) thrown sideways (sign of the zone x) with the plane's velocity, callback `03f7` | verified |
| 0916:03f7 | debris_update(e) | above 500: vz −= 20 (to −300), horizontal decays by 5, pos += v | verified |

## 7. G load / blackout (`0fd4`) — likely

`0fd4:0033 g_load_update()` (player): velocity change since the previous frame (`DS:578C..`) ×
100h plus gravity, rotated into the aircraft frame → **G = `DS:579B`** (signed, the vertical
component; `0fd4:0007` resets, waits 2 frames). With realism blackouts (`DS:42CC`): between
−3CFh and 514h nothing (`DS:5798` eases to 0 with `0590:004b`); above 514h (black-out) or below
−3CFh (red-out): `a = excess − excess/4`, ramp `DS:5798` toward 3FFFh at rate `a`; at 3FFFh
`DS:579A = 1` (blacked out, recovery timer 9C4h) until G is back inside the band and the timer
expired. The screen effect uses `DS:5798` (sim_flow/render).

## 8. Ship movement (`5410`) — likely

| Address | Name | Does |
|---|---|---|
| 5410:0010 | approach_hi(i32 v, int target, int step) | moves the high word of `v` toward `target` by `dt_mul(step)`; returns 0 when reached |
| 5410:0078 | ship_speed_update(s, target, accel) | `s+74 (i32 speed) = approach_hi(...)`; returns `s+76` |
| 5410:00a3 | ship_steer(s, Vec *dest, int speed) | turn toward `dest` (`0590:004b` on the heading with `.DAT+48` turn rate, 0 when `s+42 & 8`); `DS:4332` = on course; speed toward `speed` with `.DAT+4C`; move `pos += dir(heading)·dt(speed)` (`3611:0007`); returns the distance |
| 5410:016e | ship_stop(s) | speed → 0 |
| 5410:018c | ship_follow_waypoints(s) | brain state: next waypoint of the group (`17fe:00ed`); none → stop, idle state; else steer at `.DAT+4A` (max speed) |
| 5410:01e7 | ship_keep_station(s) | brain state: formation point = leader position + rotated offset `+68`; speed = leader speed ×(−3) if closer than D556h, ×5 beyond 12AAAh (catch up), else leader's; `.DAT+4A == 682h` → state change |
| 5410:02c0 | ship_brain_init(s) | type 0 (group marker) vs real ship: different initial state |
| 5410:02ed | ship_classes_register | |

Ship `.DAT` fields used: `+48` turn rate, `+4A` max speed, `+4C` acceleration, `+4F` name, `+6C`
carrier flag (= 1). **No zig-zag code** was found in `5410`.

## Data structures

### Plane fields established here (reconcile in `sim_world.md`)

| Off | Meaning | Evidence |
|---|---|---|
| 1A | 01 dead, 02 smoking/engine out, 04 drop tank, 08 low fuel, 40h going down | 10bf:0039, 655d |
| 1B | 01 wreck removed, 02 sunk (ships) / on landing damaged, 08 player armour flag, 40h has ordnance | 465c, 56ac:10a8, 088a |
| 1C | 01 engaged, 04 friendly to the player's flight, 08 ditching | 56ac:0fc2, 10bf |
| 1E | (ships) 02 torpedo-vulnerable, 04 bomb-vulnerable | 465c:0395 |
| 22 | (ships) 12-byte block | 465c:005a |
| 24 | box list (`.BXL`) | 465c:0395 |
| 26 | side 0 US, 1 Japan | 088a:054f |
| 28 | `.DMG` image | 465c |
| 2A | damage state (§2) | 4b3a:03ff |
| 34 | flight record (56h) | 56ac:10a8 |
| 43, 47 | proximity avoidance flags (10h right, 20h left, 40h dive, 80h climb) | 085b:000b |
| 4A | brain record (AI state) | 69fe |
| 54 | brain scratch (crash state word) | 655d:009b |
| 5E, 60 | gun list, gun state | 4cda |
| 68, 6C | (ships) formation offset x, y (i32) | 465c:0395 |
| 74 | (ships) i32 speed (high word = speed) | 5410:0078 |
| A4, A6, A8 | engine power factors, prop torque (= FmState words 32–34) | 655d:1c75 |
| AB | landing damage level (FmState +47) | 088a:01d3 |
| B4 | engine 2 throttle (player, 2 engines) | 655d:159d |
| B6 | mass | 56ac:10a8 |
| B8 | ground height | 088a:01d3 |
| BC | index in flight | 56ac:10a8 |
| EB, EC, ED | rocket rack: rockets left, rack size, loaded-station bitmask | 465c:015f |
| EF | ship (carrier) under the plane | 088a:01d3 |
| F1 | torpedo loaded (FFh none) | 465c |
| F3 | 3 × (station kind, count) | 465c, 56ac:10a8 |

### Flight record (56h bytes, `DS:4753[i]`, built by `56ac:0c6a` from the 58-byte type-5 record)

| Off | Meaning |
|---|---|
| 00 | kind: 0 aircraft flight, 1 ship group |
| 01 | type/side byte (ship groups: formation table row `×0Eh − 0EEh`) |
| 02 | role (5 cover, 6 protect, …) |
| 03 | starts on a carrier |
| 06 | member count |
| 08 | member list (Plane*) |
| 0A | first waypoint |
| 0E | count of protected flights; 10 3 × protected flight |
| 1C | heading |
| 26 | i32 start altitude (0 = parked) |
| 2E | (ship groups) group marker object |
| 30 | cruise speed |
| 31, 33, 34.. | default ordnance for members (rack, torpedo, 3 stations) |
| 3B | flags (2 = carrier task group, 4 = …) |
| 3E | escorted flight |
| 42 | side |
| 43 | cover mode |
| 44, 46 | linked flights count and list |
| 4E | i32 cruise altitude |
| 52 | far pointer (group's source record) |

## Globals

| DS | Name | Meaning |
|---|---|---|
| 0172 | dmg_tables | near ptr[slot] |
| 0FE8/0FE9/0FEA/0FEB/0FEC/0FED | oil leak 1/2, fuel leak, pilot wounded, player down, structural failure | |
| 0FF2/0FF4/0FEE | wound fade stage / phase / timer | |
| 1382 | midair_grace | |
| 3B01/3B03/3B05/3B07/3B09 | view cycle idx / ship pool / plane pool / player flight / player plane | |
| 4454 | rng_state | (sim_flow's RNG) |
| 4510/450E/4513/4515/4517 | script reader state | |
| 4601[9Fh] | per aircraft type: count, then shape handle | |
| 451B[73h] | per ship type: count, then shape handle | |
| 473F/4741/4745/4749 | waypoint bytes, waypoint count, message offset/text positions | |
| 474D | effect shape base | |
| 4751/4753/4755/4759/475B/475D/475F/4761 | flight ptrs, flights, places, ship list, object list (×2), waypoint ptrs, waypoint data | |
| 4763[4], 476B, 476E, 4770, 4772, 4774, 4776, 4778 | counts | |
| 477A..47D4 | header copy (`DS:477B` = header +0) | |
| 4512, 476D | stormy, kind == 1 | |
| 5190/5192/5194/5196/5198/519A | player engine 2 oil/temp/timer, engine 1 oil/temp/timer | |
| 515C/5160 | engine stop timers | |
| 5798/579A/579B | blackout level / latch / G | |
| 5A82 | object damage classes (GDAMAGE.DAT) | |

## RNG call sites (state `DS:4454`)

| Site | Decides |
|---|---|
| 655d:0bd9 | ship damage multiplier 1..7 for vulnerable ships; ship magazine explosion (≥ CDh damage in one hit, 136h/400h); plane kill type (fire / spin / break-up); critical-hit rolls and which critical |
| 655d:009b | crew starts bailing out (134h/400h) |
| 085b:0085 | pilot hurt in a mid-air collision (100h/400h) |

## Hand-offs

* **sim_flow**: `DS:0FEB..0FED`, `DS:42BD..42BF`, `DS:57DD..57E7`, `DS:3EF5..3EFB` are flags its
  message/HUD/results code reads; `1899:0cf0`/`1899:102f` receive every kill and ground hit
  (arguments in §5.1); `5da1:0000(1)` ends the mission (pilot dead / out of fuel); `10bf:013a/01d6`.
* **render3d**: effect object (`05a9:005a` record 30h bytes), `GID:` terrain query `3368:0069`
  used by `14e0:06c0` — **GID: is the terrain/ground collision data** as far as the sim is
  concerned (height query over the tile objects); cloud drawing `490a:0509`.
* **data.md** corrections: `PFNAME<n>/SFNAME<n>.TXT` are plane/ship *file name* lists (0x9F /
  0x73 entries), not pilot names; `.MEC` record sizes: BULLETS 16, BOMBS 10, ROCKETS 10, TORPS 18;
  aircraft `.DAT+0` = empty weight; `.WND` is loaded twice but all files are identical.

## Open questions

* `56ac:0b78` (waypoint reader) and `56ac:0c6a` (flight builder): Ghidra garbles both — the
  exact field mapping of the 58-byte group record to the 56h flight record needs x86dis.
* `.DMG` aircraft `k2 k3 k6` and zone words 3–4; ship zone word 3; hdr flags 2000h/4000h exact.
* The landing dispatch table `DS:0453` in `088a:01d3`.
* PLT ratings r2, r7, r10, r11, r13–r16 and their users.
