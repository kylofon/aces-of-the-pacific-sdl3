# sim_world — weapons (guns, bullets, bombs, rockets, torpedoes, flak, impacts)

Part of the `sim_world` spec (index: `sim_world.md`). Segments (AP_flat.exe, ownership per
`sim_flow.md` §0): `488e` weapon class registry, `05d6` ordnance pool / damage-event queue,
`48ff` bulletso.c, `0769` guns, `4cda` gunlist.c, `0ff4` weapon stations, `0688` bombs.c,
`1a32` rockets.c, `1baa` torps.c, `04c4` flak/AA, `1560` impacts/explosions, `6cc2` drop tanks,
`6ac7` segment vs hit-box. Damage *application* (`655d:0bd9`) is in `sim_world_dmg.md` §4.
Confidence: **verified** = read in the disassembly, **likely** = from the decompile, **guess**.

## 1. Overview

All weapons in flight are 3Space objects allocated from one pool (`DS:00E6`, pool.c `3546`,
50 = 32h-byte records, capacity `n+2` given to `weapons_init 488e:0000`). Each weapon object has a
**class id** in the low nibble of `+18` (registered at init by `488e:007a`, which stores two far
function pointers per class: `update` at `DS:3C28[id]`, `draw` at `DS:3BE8[id]`):

| Class global | Registered by | update | draw | What |
|---|---|---|---|---|
| `DS:1344` | `0688:0004 bombs_load` | `0688:04e3 bomb_update` | — | bombs (`BOMBS.MEC`) |
| `DS:1348` | `48ff:0000 bullets_load` | `0769:0637 bullet_update` | `0769:08a3 bullet_draw` | bullets / shells (`BULLETS.MEC`) |
| `DS:193A` | `1a32:000b rockets_load` | `1a32:02f4 rocket_update` | `1a32:0531 rocket_draw` | rockets (`ROCKETS.MEC`) |
| `DS:19EC` | `1baa:001e torps_load` | `1baa:026e torp_update` | `1baa:05f0 torp_draw` | torpedoes (`TORPS.MEC`) |
| `DS:54B5` | `04c4:0057 flak_register` | `04c4:0910 flak_burst_update` | `04c4:0bf0 flak_burst_draw` | flak bursts |

Per frame (`5440:1317` order, see `sim_world.md` §2): `04c4:0098 flak_fire_all` (skipped in
training missions: header type 5, or when `DS:4791 == 2Fh`) → … → `05d6:0002 ordnance_update`
(deletes last frame's hit weapons, runs every weapon's `update`, deletes expired ones) → … →
`655d:0bd9 damage_apply` (consumes the **damage-event queue** filled by the updates this frame).
Firing is started by the player's trigger (sim_flow `5440:096a` → `0769:009a`, bombs `0deb:000a`,
rockets `0deb:0221`) and by the AI (`1284:0435`, g_attack `0deb`, flak `04c4`).

### 1.1 Weapon object (3Space object, 32h bytes, pool `DS:00E6`)

| Off | Type | Meaning |
|---|---|---|
| 00 | u16 | 3Space flags/class: 0805h bullet, 0005h bomb/rocket/torpedo, 2805h flak burst; bit 2000h = hidden/delete |
| 02 | u16 | shape (`DS:474D` + n: bullet +4, bombs +7+mec[0], rockets +0Bh+mec[0], torps +5+mec[0], flak +0Ch..+0Fh) |
| 04/08/0C | i32 | x, y, z |
| 10/12/14 | u16 | pitch, roll, heading |
| 16 | ptr | owner Plane (the shooter; 0 = none) |
| 18 | u16 | **kind**: bits 0–3 class id, bits 4–9 `.MEC`/gun-type index, 2000h skip first update, 4000h first of a stick / "armed" (bombs, torps: see below), 8000h followed by the weapon camera |
| 1A | u16 | shape flags (`mec[1] | 0Fh`, or `rec[2] | owner flag`) |
| 1C.. | | per class: velocity (1C/1E/20), gravity step 22, timers 24/28, … (below) |

### 1.2 Damage-event queue (`DS:00E8`, 8-byte entries, count `DS:00EA`, capacity `DS:3C68`)

`05d6:0419 dmg_event_alloc()` returns the next free entry or 0 when full: `{ far weapon (0 =
none: collision/proximity), Plane *target, i16 damage }`. Producers: bullet/rocket/torpedo hits
(`1560:000a`), bomb blasts (`0688:0d40`), flak (`04c4:0910`), mid-air/proximity (`085b:0085`,
damage 8000 = 1F40h, special-cased), ground/ship impact (`088a:01d3`, 8000). Consumer:
`655d:0bd9` once per frame; then `05d6:0002` (next frame) deletes each event's weapon unless it
is a flak burst.

## 2. Registry and pool (`488e`, `05d6`)

| Address | Name | Signature | Does | Conf. |
|---|---|---|---|---|
| 488e:0000 | weapons_init | far (int n) | `n += 2`; `DS:00E6 = pool_create(n, 32h)` (`3546:0006`); `DS:00E8 = calloc(8n)`; `DS:00EA = DS:00EE = 0`; `DS:3C68 = n`; `DS:3BE6 = 0` (class count); `DS:00F4 = 0` | verified |
| 488e:004b | weapons_free | far () | pool free, globals 0 | verified |
| 488e:007a | weapon_class_register | far int (far update, far draw) | `DS:3C28[DS:3BE6] = update`, `DS:3BE8[DS:3BE6] = draw`; returns the id and increments | verified |
| 488e:00b0 | cockpit_fullscreen_flag | far int () | returns `(i8)DS:00F8` (sim_flow's flag, read here) | verified |
| 05d6:0002 | ordnance_update | far () | §2.1 | likely |
| 05d6:01d3 | ordnance_draw | far (far obj) | calls the class draw if any and not hidden (2000h); if it returns 0 skip; else draw the object (`2f0e:08e9`) — render3d | likely |
| 05d6:023e | ordnance_make_room | far (int n) | when the pool has fewer than `n` free: count live weapons per `+1A & FF` bucket, free the oldest weapons of the largest buckets until `n` are free (`3546:0333`) | likely |
| 05d6:036c | weapon_cam_remember | far (far obj) | sim_flow (weapon camera): `DS:00F0 = obj; DS:00F4 = DS:4086` | verified |
| 05d6:0381 | weapon_cam_follow | far ptr () | sim_flow: if a weapon was dropped < 0C81h ticks ago and not followed yet: mark 8000h, copy it to `DS:3C6E`, `DS:3C6A = obj` | verified |
| 05d6:03fc | weapon_cam_release | far () | sim_flow | verified |
| 05d6:0419 | dmg_event_alloc | far ptr () | §1.2 | verified |

### 2.1 `05d6:0002 ordnance_update()`

```
DS:3CB0 &= DS:3CB4; DS:3CB4 = 0; DS:00EC = local 300-entry delete list
for each event (from last to first, DS:00EA → 0):
    w = event.weapon
    if w && class(w) != flak:
        if w == DS:00F0: DS:00F0 = 0
        if w.kind & 8000h (followed by camera): DS:3CB0 |= 2, DS:3CB4 |= 2, DS:3C6A = 0,
            camera record +6 = 1, +8 = DS:4086 + 8000         // camera lingers 8000 ticks
        if class(w) != bombs: pool_free(DS:00E6, w)          // bombs free themselves
for each live pool object o: DS:3C28[class(o)](o) if non-null     // the class updates
camera bookkeeping (1c30:1021 = weapon camera active): copy the followed weapon position to
    DS:3C72, or flag DS:3CB0/3CB4 |= 4 when the linger time is over
for each entry of the delete list (DS:00EE → 0): same camera bookkeeping; pool_free
```
Updates put finished weapons on the delete list `DS:00EC[DS:00EE++]`.

## 3. Guns

### 3.1 Data

**`BULLETS.MEC`** (`48ff:0000 bullets_load`, `DS:1346`, 9 records × 16 bytes; verified sizes,
field use from the code):

| Off | Type | Use | Values |
|---|---|---|---|
| 00 | i16 | ? (0) | 0 |
| 02 | u16 | shape flags → weapon `+1A` (`2F00h`) | 12032 |
| 04 | i16 | **damage per round** (× the burst's gun count) | 10, 10, 10, 15, 15, 100, 100, 150, 200 |
| 06 | i16 | **refire interval** in mission-clock ticks (`DS:4086`) | 210 (MGs), 315 (cannon), 1260 (ship guns) |
| 08 | i16 | **muzzle speed** (per nominal frame, dt-scaled) | 1400, 700 (type 8) |
| 0A | i16 | lifetime timer (dt units) | 3200 |
| 0C | i32 | effective range (used by flak aiming, `0769:0032`) | 21000, 10500 |

Gun types (index = `.GL` record +0): 0–2 7.7 mm / .30 cal class (10), 3–4 .50 cal (15), 5–6 20 mm
(100), 7 37 mm? (150), 8 ship/AA gun (200) — **likely**. Rounds per burst consumed:
`DS:134E[type]` = {3,3,3,3,3,2,2,1,1}. Firing sound id `DS:1362[type]` (bytes 0C 0C 0C 09 09 0A
09 0B 0B).

**`.GL` gun lists** (`4cda:0037 gunlist_load(slot, name, is_ship)`, per model, pointer table
`DS:030C[slot]`; 82 files) — **verified layout**:

```
u16 n, u16 flags, n × record (20 bytes aircraft, 10 bytes ships)
flags: bits 0–7 number of flexible (turret) groups; 2000h|0800h = fixed group A exists
       (0800h = A fires both sides alternately? state 0xC000), 0400h|0100h = fixed group B
       (0100h likewise); groups are stored A, B, then turrets
aircraft record: +0 gun type, +2 guns in the group (mirrored left/right), +4 rounds per gun,
       +6/+8/+A x, y, z offset, +C turret centre heading, +E turret arc (7FF8h = full / 65 fixed),
       +10, +12 elevation limits (750/750 for fixed guns)
ship record: +0 gun type (8 = AA), +2 count, +4/+6/+8 x, y, z
```
Examples: F4U `2C00h` = groups A (.50 ×4) + B (.50 ×2) (trigger 1/2); Zero-22 `2400h` = A 7.7 mm
+ B 20 mm; SBD `2001h` = A + 1 rear turret; B-17D `0005h` = 5 turrets, no fixed guns.
`.GLT` (NUL-separated loadout names, `4cda:00f8` for the player → `DS:1546`/`DS:154A`/`DS:154E`).

Per-plane **gun state** (`4cda:00f8 gunlist_attach(slot, &Plane+5E, &Plane+60, Plane)`): `Plane+5E`
= `.GL` image, `Plane+60` = calloc(n × 0Ch) (aircraft) / n × 26h (ships: +4 owner, +24 side byte
from `Plane+26`, +25 gun type). Aircraft entries (12 bytes): `+0 i16 rounds left` (= `.GL` rounds
<< 1 for AI planes (`4cda:02f3(.., 1)`), unchanged for the player), `+2 i32 time of last shot`,
`+A u16` flags (8000h valid, 4000h alternate side). For the player: `DS:3FE2`/`DS:3FE4` = rounds
of groups A/B (gauges), `DS:3FEE` bits 20h/40h = group A/B present.

### 3.2 `0769:009a gun_fire(int trigger, Plane *p, Vec *aim, FireSrc *src)` — likely

`trigger`: 0 = both (uses the saved alternate bits), bit 0 group A, bit 1 group B, ≥ 4 = turret
`trigger − 4` (index after the fixed groups). For each selected fixed group with guns:
* player and the group jammed (`DS:4366` A / `DS:4364` B): message "guns jammed" (string 1,5)
  and return;
* if rounds left: `side = (group is single-sided (flags == 0800h / 0100h) or state 8000h) ? 0 : 1`;
  `fired = bullet_spawn(side, …)`; player: **gun jam** when fired and `Plane+1B & 8` and G load
  `DS:579B < −441h` (negative G) and realism "gun jams" (`DS:42CA`): set the jam flag, message
  (`5440:0a8d`); update gauges `DS:3FE2/3FE4`; out of ammo → `DS:57E4 = 1` (message), clear the
  gauge bit; `DS:1360` records which side fired; toggle the alternate bits (`^= C000h`);
* player, realism "limited ammunition" (`DS:42CD`) and both groups empty → `DS:42BD = 1`;
* play the firing sound of the group's type (`0769:004c`: player `5a75:0f2c`, others `5a75:0eea`).

### 3.3 `0769:0400 bullet_spawn(side, dx, dz, Vec *pos, Vec *ang, FireSrc *src)` — likely

```
g = BULLETS[type]; if rounds <= 0: return
if DS:4086 − last_shot < g.refire: return
player: make room in the pool (05d6:023e(1)) if full
b = pool_alloc(DS:00E6)
if not (player && !DS:42CD): rounds −= DS:134E[type] (floor 0)     // player with unlimited ammo keeps them
last_shot = DS:4086
b.flags = 0805h; b.shape = DS:474D + 4; b.angles = *ang; b.pos = *pos
player (side ≥ 0): b.pitch += grp.+0C; b.heading += side ? grp.+0E : −grp.+0E    // convergence
else: b.heading += side ? −dz : dz; b.pitch += dx
if src.owner: offset = (grp.x (negated for side 1), grp.y, grp.z) rotated by the owner's matrix;
    b.pos += offset (5137:00b3)
b.dir (+22) = direction vector from b.angles (5137:00e2)
b.owner (+16) = src.owner; b.+1A = g.+02 | src.flags; b.kind = type << 4 | DS:1348
b.timer (+28) = g.+0A; b.+2A = src.+04; b.count (+2C) = grp guns (+2)
```

### 3.4 `0769:0637 bullet_update(far b)` — likely

```
if b.timer (+28) <= 0: delete (list); return
timer_dec(b.timer)
new = b.pos + dir · dt(g.speed) (277a:5612 + 3662:000d + 526a + 5038)
if b.owner: g_obj = segment_hits_ground_object(b.pos, new) (1560:08fe)
    if hit: splash if below 0 (1560:0352); b.timer = 0; ground_object_damage(&hit, g.damage,
            type, b) (1560:03dd); return
b.velocity (+1C..+20) = new − old
6ac7:0115(player ? 2 − DS:42D2 : 3)          // hit-box tolerance by combat level
dmg = g.damage · b.count
if b.+2A: t = segment_hits_object(new, b.pos, …, b, dmg) (1560:000a)
    if t: hit_spark(t, …, DS:474D+27h) (1560:024a); ai_was_hit(t) (1284:0006); return
if new.z < 0: water splash (1560:0352), b.timer = 0, splash effect (1560:0179); return
if ground_height_at(new) (14e0:07db) and ground.z < new.z: b.timer = 0
```

### 3.5 Other gun functions

| Address | Name | Does | Conf. |
|---|---|---|---|
| 0769:0002 | gun_type_speed(int *type) | `BULLETS[*type].+08` | verified |
| 0769:001a | gun_type_refire(int *type) | `BULLETS[*type].+06` | verified |
| 0769:0032 | gun_type_range(int type) | `(i16)BULLETS[type].+0C` | verified |
| 0769:004c | gun_sound(Plane*, type) | §3.2 | verified |
| 0769:03c6 | gun_ready(int *type, GunState*) | rounds > 0 and refire elapsed | verified |
| 0769:08a3 | bullet_draw(far b) | tracer: draw from pos to pos+velocity (render) | likely |
| 48ff:009a | bullets_reset | `DS:1360 = 0` | verified |
| 4cda:0000 | gunlist_loadout_free | `24b2:01c0(DS:1546)` (free the `.GLT` names); `DS:1546 = DS:154A = DS:154E = 0` | verified |
| 4cda:0021 | gunlists_alloc(int n) | `DS:030C = calloc-like 24d3:0059(2n)` (pointer per model slot) | verified |
| 4cda:02f3 | gun_state_init(GunRef *g, u8 shift) | `g[0]` = `.GL` image, `g[1]` = state array (12-byte entries). `flags = .GL+2 &= 3FFFh`. Group A present (`flags & 2800h`): entry `+0A |= (flags & 0800h) ? C000h : 8000h`, rounds `+0 = rec.+4 << shift`, `.GL+2 |= 4000h`; next record/entry. Group B (`flags & 0500h`): the same with 0100h, and when there is no group A `.GL+2 |= 8000h`. Turrets (`flags & FFh` of them): rounds `= rec.+4 << shift`. Records are 20 bytes; `shift` = 1 for AI planes (double ammunition), 0 for the player | verified |
| 1baa:0005 | torp_speed_limit(int side) | `TORPS[1 − side].+04` (`DS:19EA + (1 − side)·12h + 4`) | verified |

## 4. Bombs (`0688` bombs.c)

**`BOMBS.MEC`** (`DS:1342`, 7 × **10-byte** records; data.md said 16 — wrong):

| Off | Use | Values (0–6) |
|---|---|---|
| 00 | shape offset / size class (0 small, 1 medium, 2 large) | 0 1 0 0 1 2 2 |
| 02 | weight (lb × 40.96: 100, 500, 100, 200, 500, 1000, 1100 lb) → weapon `+1A` | 4096 … |
| 04 | damage to ships/objects (per hit, used by `1560:000a`) | 1250 3750 1250 2500 3750 6250 12500 |
| 06 | blast damage to aircraft | same as +04 |
| 08 | blast radius | 200 400 200 400 600 1000 800 |

### 4.1 `0688:009d bomb_release(u8 *stick, Vec *pos, Plane *carrier(matrix src), FireSrc *src)` — likely

`stick[0]` = number of bombs n, `stick[1..n]` = MEC index of each. Make room if needed.
`lead = rng_range(DS:4454, n)` (**RNG**: which bomb of the stick is the "aim" bomb for AI
dispersion). The stick is laid out along the carrier's axis (spacing vector from the plane's
velocity rotated; n = 1: half; n = 2: /3; else /n, odd n centred). For each bomb: object kind
0005h, shape `DS:474D + mec[0] + 7`, kind `idx << 4 | DS:1344 | 2000h` (+4000h for the first),
angles = carrier's, owner = src.owner.
* **player**: velocity (+1C..+20) = the plane's world velocity per frame (`Plane+70..74`), vz =
  −|vz|; gravity step (+22) = `(rng & 7) + 0Dh` (**RNG**); `weapon_cam_remember`.
* **AI**: `s = isqrt(|vz_carrier|)`; `+24 = s << 8` (fall time); `+28 = (n − i)·5 − Plane+74`;
  impact point = src point + lead offsets `(lead − i)·lencos(s, heading)` + `rng_range(s/n)`
  (**RNG**, dispersion, both axes) + rotated spacing; stored as target (+1C, +20 as i32).

### 4.2 `0688:04e3 bomb_update(far b)` — likely

Skip the first frame (clears 2000h). **Player bombs**: `pitch = satdiv(vz · −2000h, 60)`;
horizontal velocity decays by `v >> 3` while |v| > 2; `vz −= g; if g < 61: g += 13`; `pos +=
dt(v)` per axis; the lead bomb plays the whistle sound (`5a75:0eea(2, …)`) while above 0.
**AI bombs**: fall time and horizontal move toward the precomputed impact point with a
per-frame limit (`0688:0ce2 clamp_toward(cur, step, target)`), `pitch = −atan2(t >> 8, vz)`.
Then `t = segment_hits_object(… , mec.damage)` (`1560:000a`, class filter 1 = ships): hit →
`bomb_blast` (`0688:0d40`) and delete; else if `z < 1`: `z = 0`, `bomb_explode` (`0688:08b7`),
delete.

### 4.3 `0688:08b7 bomb_explode(far b)` and `0688:0d40 bomb_blast(far b)` — likely

`bomb_explode`: `water = splash_or_dust(pos)` (`1560:0179`); if on land: `bomb_blast(b)`; then damage
ground objects within `radius = mec.+08`:
* player's bomb: collect static objects of the current world tiles within `radius + 100000`
  (`1560:0755`), and for each object group within `size + radius + 50000`, each sub-object
  (22-byte records, damage byte at `+12`) within `size + radius`: `d = byte + mec.+06 ·
  DS:5A88[type·8] >> 8` (type = `1641:0157(shape & 1FFFh)`); `d ≥ 255` → byte = FFh (destroyed)
  and a fire effect (`1560:04d7(pos, DS:5A84[type·8], DS:474D + 1Ch)`); report
  `088a:07ab` (score) with the damage done;
* AI bomb: the same test over the target list `DS:5146` (count `DS:5140`, 22-byte entries,
  with `DS:5142` 6-byte back pointers).
No object hit → sound/explosion only (`088a:045f`).

`bomb_blast`: every aircraft within `mec.+08` (3-D distance `277a:3b3c`) gets a damage event
`{b, plane, mec.+06}`; the player caught by his own bomb with realism "aircraft may be damaged"
(`DS:42CF`) sets `DS:57E7`.

## 5. Rockets (`1a32` rockets.c)

`ROCKETS.MEC` (pointer `DS:1938`, class id `DS:193A` — corrected from 1937/1939; 1 × 10 bytes: shape 0, flags 4096, speed? 10000, 498, damage 4200).

`1a32:00a7 rocket_fire(u8 *rack, Vec *pos, Matrix *m, FireSrc *src)`: `rack[0]` rockets left,
`rack[1]` rack size n, `rack[2..]` bitmask of loaded stations; pick a random loaded station
(`rng_range(DS:4454, n)` until the bit is set — **RNG**); unless player with unlimited ammo,
clear it and decrement (player: `DS:3FE6` = rockets left). Position = interpolated between the
two wing ends by the station index; kind `DS:193A`, shape `DS:474D + mec[0] + 0Bh`, speed `+22` =
src `+04`, burn/lifetime `+24 = mec.+08`; followed by the weapon camera for the player.

`1a32:02f4 rocket_update`: lifetime 0 → delete (camera flag 4); accelerate `+22 += dt(100)` up
to `mec.+06`; move along the direction; ground object hit (`1560:08fe`) → splash if below 0,
`ground_object_damage(…, mec.+04, 200)`; object hit (`1560:000a`) → ship: `hit_spark`; below 0
→ splash + lifetime 0; below ground → lifetime 0. `1a32:0531 rocket_draw` toggles the exhaust frame.

## 6. Torpedoes (`1baa` torps.c)

**`TORPS.MEC`** (`DS:19EA`, 2 × **18-byte** records — US Mk 13, Japanese Type 91 **likely**):

| Off | Values | Use |
|---|---|---|
| 00 | 0, 0 | shape offset |
| 02 | 8000h | shape flags |
| 04 | 1764, 1927 | returned by `1baa:0005(side)` = `TORPS[1 − side].+04` (AI drop speed limit?) |
| 06 | 12500, 12500 | damage when the warhead works (else dud → 0) |
| 08 | 165, 121 | max drop speed (vs `Plane+94 / 12`) |
| 0A | 2600, 600 | max drop altitude |
| 0C | 36, 28 | running speed (per frame, dt-scaled, `×dir >> 8`) |
| 0E | 10000, 10000 | max run distance |
| 10 | 120, 120 | run time (`<< 8`) |

`1baa:00ba torp_drop(Vec *pos, int dz, Vec *ang, TorpSrc *s)`: object kind 0005h, shape
`DS:474D + rec[0] + 5`, position with `z += dz` (min 2), velocity = the plane's per-frame
velocity, `vz = −|vz|`, gravity 0Dh, heading vector `(sin, cos)·100h` of the aircraft heading
(`3609:0001`), kind `type << 4 | DS:19EC | 2000h`, run time `+24 = rec.+10 << 8`. **Dud**
(`+4000h` → no damage): altitude `> rec.+0A`, or speed `rec.+08 < Plane+94 / 12`, or `|vz| > 50`.

`1baa:026e torp_update`: in the air: same fall as a player bomb (drag `v >> 4`); on hitting a ship
on the way down (`088a:00b1`) → delete; on reaching the water (`z < 2`): `z = 1`, surface flag
(or sink if the side byte ≠ 0: object hidden), splash (`1560:0179`); a dud or a failed splash
test deletes it (`DS:57E6 = 1`, message "torpedo broke"). In the water: run time `−= dt(40h)`,
`pos += dir·dt(rec.+0C) >> 8`, distance run `+2C += step`, beyond `rec.+0E` → dud; hits land
(`14e0:07aa`) → delete; ship hit (`1560:000a`) → dud: delete (`DS:57E5` for the player's), else
explosion `1560:04d7(pos, 2000, DS:474D + 10h)`. `1baa:05f0 torp_draw`: wake animation (`+31 ^= 3`).

## 7. Weapon stations (`0ff4`) and drop tanks (`6cc2`)

| Address | Name | Does | Conf. |
|---|---|---|---|
| 0ff4:0001 | station_cycle | (command handler) select the next bomb/rocket station | guess |
| 0ff4:0186 | station_drop(GunRef *g, Vec *near) | `near == 0`: mark the first station after the fixed groups as empty (`FFFFh`); else the loaded turret/station nearest to `near` (`3684:000c`) | likely |
| 0ff4:0277 | station_count(GunRef*) | `.GL flags & FFh` | verified |
| 0ff4:0289 | station_loaded_count(GunRef*) | number of turret/station entries with rounds > 0 | verified |
| 0ff4:02ea | station_first(GunRef*) | rounds of the first entry after the fixed groups | verified |
| 6cc2:0000 | drop_tank_release | spawn a falling tank object (sim_flow's `5440` calls it on the jettison key) | guess |
| 6cc2:00cb | drop_tank_update(far o) | `s = dt(o+26)`; `o+28 += 1` (≤ 7FFFh); `pos += dir(+20..+24)·s >> 14`; `z −= o+28 · 64` (falls faster each frame); `o+26 −= o+26 >> 3`; returns z | verified |

## 8. Flak and AA (`04c4`)

Ground AA sites come from the world's AA list (`DS:18B5` far array of 26h-byte records, count
`DS:18BB`, built by `14e0:0286`: static objects whose type has an AA class `1641:0172` = 3 or 8);
ship AA from each ship's gun list (`Plane+5E`/`+60`, 26h-byte entries). Per frame
`04c4:0098 flak_fire_all`: for each site, each gun whose cooldown (`+4` / `362b:021c`) expired
fires at most one shot per site per frame via `04c4:02be flak_fire(gun, pos)`; ships skip when
sunk (`Ship+1B & 2`).

`04c4:062e flak_pick_target(gun)`: keep the current target while `flak_in_range` and it has been
engaged ≤ 4 times (then reset; after 2 shots, other guns of the site drop the same target);
else scan enemy aircraft (side ≠ site side `DS:54A7`) not already targeted by the site: first
one in range wins; otherwise pick a random one of those already targeted (**RNG**
`rng_range(DS:4454, n)`).

`04c4:07a2 flak_in_range(Plane*)`: heavy flak (`DS:54A8 < 4`): target altitude between 9C4h and
the ceiling `DS:1266[kind]` (= {20000, 35000, 64000, 45000}, or 34BCh when `0802:000c` (cloud /
visibility) says hidden) and ground range `277a:3bfc < DS:1276[kind]` = {10000, 20000, 30000,
25000}; light AA (kind ≥ 4): altitude 100..3000 and 3-D range < 12000.

`04c4:02be flak_fire`:
* **heavy flak** (kind < 4): no target → cooldown `4B0h + DS:5494++`; else skill `k = 0` when the
  target dives (`pitch < −2000h`) or the pilot profile `+41` ≠ 0 (evasive pilot), else
  `min(gun+4, 2)` (the number of salvos already fired at it): spread `s = DS:1246[k]` = {3000,
  1500, 500}; cooldown = `(rng & FFFh) + C00h` (**RNG**); lead `t = (range >> 11) + 4`, aim point
  = target + velocity(+6C)·t + `DS:124C[k]` (vertical offset), plus a random offset `rng_range(2s)
  − s` in x and y (**RNG** ×2) rotated by the target's matrix; spawn a burst `flak_burst_spawn(aim,
  t, target)`;
* **light AA** (kind ≥ 4, ship/ground guns of type `kind − 4`): gun spec = BULLETS[kind − 4];
  cooldown = 10000 with probability 100/1024 (**RNG**: pause) else `refire·2000 >> 10`; lead the
  target by its velocity × `range / muzzle speed`; aim error from `1284:0271(…,
  DS:125A[level], DS:1260[level])` (level = `DS:42D2`, errors {200, 350, 500}/{−250, −150, −50});
  result 0 → no shot; 2 → no spread; else fire a bullet from the gun position
  (`0769:0400(0, …)`).

`04c4:0860 flak_burst_spawn(Vec *aim, int fuse, Plane *tgt)`: object 2805h, shape `DS:474D + 0Ch +
(rng & 3)` (**RNG**), kind `DS:54B5`, `+1C = target`, `+1E = fuse << 8`, state `+22 = FEh`; for
AI targets, `rng & 3FFh < pilot.+20` → `+4000h` (the burst is "lucky"? — **guess**).
`04c4:0910 flak_burst_update`: fuse counting down (`+1E −= DS:711E`), at 0: visible, animation
from frame 0, `+1E = 157Ch`, explosion sound; then the animation frame follows the time, and
**damage to the player** (only when `DS:42D2 != 0` and realism damage `DS:42CF` and the burst
was aimed at the player): within 400 of the player, once per animation step: event damage
`DS:1252[type]` = {90, 180, 270, 180} (halved at combat level 1). AI targets are not damaged by
flak here (**verified** — only `puVar7[0xe] == DS:3B09`).
`04c4:0a9f flak_player_scale(i32 r, Vec *p)`: near the point 4 × ahead of the player (`DS:5495`
cache, reset by `DS:549D`), within 800h: `r << 3` when < 400h, else `r·(400h − (d − 400h)) >> 7`.
`04c4:0b53 flak_visible_test(far o, Vec *eye)`: cull by range `DS:548C` (player) / `DS:5490`.
`04c4:000b flak_set_range(int detail)`: `DS:5490 = lerp(detail, 55h..100h → 0..100h)·10000 >> 8 +
1000`, `DS:548C = DS:5490`. `04c4:0073 flak_reset`. `04c4:0bf0 flak_burst_draw`.
`04c4:0c53 plane_avoid_collision(Plane*)` (AI, called by the formation code): proximity flags
`Plane+43` (set by `085b:000b`): 80h → climb (`steer_climb(p, 0, 8000)`), 40h → dive (`−1F40h`);
10h → turn right (`steer_heading_nolead(1F40h)`), 20h → left; then `plane_fly`.

## 9. Impacts and explosions (`1560`)

| Address | Name | Signature | Does | Conf. |
|---|---|---|---|---|
| 1560:000a | segment_hits_object | far Plane* (Vec *from, Vec *to, int filter, far weapon, int damage, Vec *hitpos) | filter 0: aircraft (`DS:475D[0..4776)`), 1: ships (`[4776..4778)`), FFFFh: all. Skips the shooter, the player when the shooter is on the player's side (**no friendly fire against the player**), dead objects. Ships use the hit-box test `6ac7:0120` (with `6ac7:0115(0)` tolerance), objects without boxes use the position. First hit: move the weapon to the hit point, copy it to `hitpos`, queue `{weapon, target, damage}` if damage ≠ 0, return the target | likely |
| 1560:0179 | splash_or_dust | far int (Vec *p, int land_fx, int water_fx) | cycles 6 slots `DS:5A3A`; `14e0:07aa` = over land? land: effect `land_fx`; water: splash sound 17h and effect `water_fx`; effect object 080Ch (`05a9:005a`, callback `DS:4DFF:0057`) | likely |
| 1560:024a | hit_spark | far (Plane *t, Vec *p, int fx) | hits on non-player targets (or player with fx < 27h): short effect attached to the target (relative offset kept in its frame) | likely |
| 1560:0352 | splash_point | far (Vec *from, Vec *to) | moves `to` back to the z = 0 crossing | verified |
| 1560:03dd | ground_object_damage | far (HitRef *h, int dmg, int weapon_level, far weapon) | static object hit: if the type's hardness `DS:5A87[type·8] <= weapon_level`: damage byte `+= dmg·DS:5A88 >> 10`, 255 = destroyed + fire effect `DS:5A84`; report `088a:07ab` | likely |
| 1560:04d7 | explosion_spawn | far (Vec *p, int smoke, int shape) | effect object 0800h, flags 0Eh with a smoke column of `smoke` duration, else 0Ch | likely |
| 1560:055b | burning_objects_update | far () | render3d (per `sim_flow.md`): fire/smoke on destroyed static objects | likely |
| 1560:06e9 | effect_draw | far (far o) | render3d | likely |
| 1560:0755 | collect_objects_near | int (…, Vec *p, far *out, int max, i32 r) | static object groups with |dx|, |dy| ≤ r | verified |
| 1560:07eb | collect_planes_near | int (Plane **list, int n, Vec *p, Plane **out, int max, i32 r) | same for planes | verified |
| 1560:086f | shape_box | far (int shape, Vec *lo, Vec *hi) | shape bounding box (flag 20h: cube of radius·94h >> 8) | likely |
| 1560:08fe | segment_hits_ground_object | far int (Vec *from, Vec *to) | only below 36Bh altitude: nearby ground objects (≤ 10), outcode test of both ends against each object's box in its frame (Cohen–Sutherland style: both outside on the same side → miss) | likely |

## 10. Segment vs hit box (`6ac7`)

| Address | Name | Does | Conf. |
|---|---|---|---|
| 6ac7:0000 | point_in_boxes | far int (BoxList*, Vec *p, Matrix*, Vec *obj_pos) | `p` in any box of the object's `.BXL` list (object frame) — used for clouds (490a) | likely |
| 6ac7:0115 | hitbox_set_enlarge | far (int t) | `DS:51FA = t` — one-shot box enlargement for the next `0120` call: 1 → every box coordinate × 1.5, 2 or 3 → × 2 (`277a:4f9c`), 0 → exact; reset to 0 by `0120`. Bullets set it to `2 − DS:42D2` for the player's (novice ×2, intermediate ×1.5, expert exact) and 3 for AI bullets (×2) | verified |
| 6ac7:0120 | segment_hits_boxes | far ptr (Vec *a, Vec *b, BoxList *bxl, Vec *obj_pos, Matrix*) | reject if the object is farther from the segment's closest point (`277a:53e2`) than `bxl.+2` (i32 radius) + the segment length; copy the `bxl.n` boxes (12 bytes each, `bxl.+6` pointer) scaled by `6ac7:0704` (distance-based shift) and the enlargement; transform both ends into the object frame (`50c0`, `526a`, `55f0`); clip against each box (`6ac7:03e7`); return the hit point or 0 | likely |
| 6ac7:03e7 | segment_box_clip | near | slab clipping of the segment against one box (with tolerance) | guess |
| 6ac7:0704 | box_near | near | quick distance reject (`277a:3b3c` vs box radius) | guess |

## RNG call sites (state `DS:4454`)

| Site | Decides |
|---|---|
| 0688:009d | which bomb of an AI stick is the aim bomb; AI bomb dispersion (x, y); player bomb gravity step `(rng & 7) + 13` |
| 1a32:00a7 | which rack station fires |
| 04c4:02be | heavy-flak cooldown `(rng & FFFh) + C00h`; burst aim offset (x, y); light AA pause (100/1024) |
| 04c4:062e | random re-target among already engaged aircraft |
| 04c4:0860 | burst shape frame (0–3); "lucky" burst vs pilot profile `+20` |

## Data structures and globals

| DS | Name | Meaning |
|---|---|---|
| 00E6 | weapon_pool | pool.c pool of 32h-byte weapon objects |
| 00E8, 00EA, 3C68 | dmg_events, dmg_event_count, dmg_event_max | damage-event queue |
| 00EC, 00EE | weapon_delete_list, count | per-frame delete list |
| 00F0, 00F4 | weapon_cam_obj, weapon_cam_time | weapon camera (sim_flow) |
| 030C | gunlists | near ptr[slot] → `.GL` images |
| 1342, 1344 | bombs_mec, bomb_class | |
| 1346, 1348 | bullets_mec, bullet_class | |
| 1938, 193A | rockets_mec, rocket_class (written by `1a32:000b`) | |
| 19EA, 19EC | torps_mec, torp_class | |
| 54B5 | flak_class | |
| 134A, 134C | gun_cur_rec, gun_cur_state | current gun group pointers during firing |
| 134E | rounds_per_burst[9] | |
| 1360 | gun_fired_sides | |
| 1362 | gun_sound[9] | |
| 1246, 124C | flak_spread[3], flak_zoff[3] | |
| 1252 | flak_damage[4] | |
| 125A, 1260 | aa_err_a[3], aa_err_b[3] | by combat level |
| 1266, 1276 | flak_ceiling[4], flak_range[4] | |
| 3BE6, 3BE8, 3C28 | weapon_class_count, class_draw[], class_update[] | |
| 3FE2, 3FE4, 3FE6, 3FEE | player ammo gauges A/B, rockets, weapon bits (80h low fuel, 1/2 overheat, 4/8 oil) | |
| 4364, 4366 | gun_jam_b, gun_jam_a | |
| 5490, 548C, 5494, 549D, 54A1..54A9 | flak ranges and the current site context | |
| 57E4..57E7 | player event flags (out of ammo, torpedo dud, torpedo broke, own bomb blast) | read by the message code |

## Port notes

None beyond the shared ones (satdiv/idiv16).

## Hand-offs

* **sim_flow**: firing entry points `0769:009a` (guns; trigger bits), `0deb:000a`/`0deb:0221` (the
  player's bomb/rocket release goes through g_attack helpers), `0ff4:0001` (station cycle),
  `6cc2` (jettison); weapon camera `05d6:036c/0381/03fc` (+ `DS:3C6A`, `DS:3C6E`, `DS:3CB0/3CB4`);
  message flags `DS:57E4..57E7`, `DS:42BD`; gauges `DS:3FE2/3FE4/3FE6/3FEE`.
* **render3d**: `05d6:01d3`, class draw callbacks (`0769:08a3`, `1a32:0531`, `1baa:05f0`,
  `04c4:0bf0`), effects `05a9:005a` (effect object layout 30h bytes: +0 flags, +2 shape, +4 pos,
  +16 frame, +18/+1A far callback, +20 attach object, +22 offset, +2A smoke), `1560:055b`, `1560:06e9`.
* **sound**: `5a75:0eea(id, pos, vel, is_player)` / `5a75:0f2c` ids used here: 1 (collision), 2 (bomb
  whistle), 5 (engine hit), 8 (flak), 12h (crash), 17h (splash), gun sounds `DS:1362`.

## Open questions

* BULLETS `+00`, `+02`; BOMBS `+00`; ROCKETS fields beyond `+06`/`+08`; TORPS `+04` use by the AI.
* `04c4:0860` burst flag 4000h (pilot profile `+20`) effect.
* The exact `6ac7` box clip arithmetic (tolerance, units) — read `6ac7:03e7` before porting.
