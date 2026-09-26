# sim_world — AI (pilots, elements, flights, combat, ground attack, carrier ops)

Part of the `sim_world` spec (index: `sim_world.md`). Target `work/AP_flat.exe`, DGROUP `3EA4`.
Written 2026-09-26 (finish pass) from the Ghidra decompile, with `tools/x86dis.py` wherever the
decompile loses register arguments or is garbled (tags **verified** = read in the disassembly,
**likely** = decompile only, **guess**). Symbols: `sim_world_ai_symbols.csv` (the names there
were rewritten from this spec; the old `[guess]` placeholder rows are replaced).

Segments (ownership `sim_flow.md` §0): `69fe` state executor, `14c3` alert/radio state, `5058`
per-frame flight update, `1142` target choice, `583c` elements/spotting, `1284` combat and
gunnery, `0ac2` aiming, `12fd` dog-fight states, `1ad2` manoeuvre library, `0619`/`1027`/`1133`
tactic states, `0deb` g_attack.c (ground/ship attack), `4edf` flight-level states (take-off,
formation, waypoints, landing), `17fe` waypoints, `69d0` flight helpers, `51fb` spawn/intercept,
`6dec` midpoints, `6dfc` LSO (carrier landing), `1660` (AI part: responses to radio orders),
`07fe` ces.c. The steering primitives the states call (`4bf9`) are in `sim_world_fm.md` §4.

## 1. Architecture

### 1.1 Brains and state descriptors

Every sim object (plane or ship) has a **brain** at `obj+4A` (14 bytes):

| Off (brain) | Off (Plane) | Type | Meaning |
|---|---|---|---|
| +00 | +4A | near ptr | current **state descriptor** (a `DS:` address; the code compares these addresses, so they act as state ids) |
| +02 | +4C | i32 | think timer (counts down by `DS:711E` per frame unless desc flag 40h) |
| +06 | +50 | i32 | frames spent in this state |
| +0A | +54 | near ptr | **scratch** block (`DS:47F4` bytes = the largest descriptor scratch size; allocated once per object by `59f9:004e`, zeroed on every state change) |
| +0C | +56 | u8 | bits: 1 thought this frame, 2 acted this frame |

State descriptor (20 bytes, registered by `59f9:0000/0026`, which also sets flag 8000h and keeps
`DS:47F4 = max(scratch sizes)`):

| Off | Type | Meaning |
|---|---|---|
| +00 | i32 | think period (timer reload) |
| +04 | u16 | scratch size |
| +06 | u16 | flags (below) |
| +08 | far fn | **steer**(obj) — every frame, after the controls were neutralised; sets the stick for the next `act`; returns ≠ 0 to force a think next frame |
| +0C | far fn | **act**(obj) — every frame (usually `4edf:11f8` = `plane_fly`) |
| +10 | far fn | **think**(obj) — when the timer expires (or at once, see flag 1) |

Flags (as tested): 0001 think at once when the target `+D7` is dead/going down; 0002 may react
to "attacked" alerts (level 6) with a fight; 0004 reacts to "spotted" alerts (level 1) by taking
the source as target; 0010 fighter-sweep/combat-capable state (flight-level target code, 1142:11c3,
69fe:015c); 0020, 0040 no timer countdown; 0080 formation/cruise state; 0200 manoeuvre state
(no retarget by `1142:11c3`); 0400 no automatic target choice (`1142:100d` returns at once);
0800 ground-attack state; 1000/0100/0500 set on the take-off/deck/special states (not tested in
the AI code read; treat as data).

All descriptors (dumped from DGROUP; `4edf`/`5410`/`655d` functions reached through the VROOMM
stubs `3cdd`, `3d2e`, `3dff`, `3e46`, which in `AP_flat.exe` are plain `jmp far`):

| DS | Period | Scr | Flags | steer | act | think | State |
|---|---|---|---|---|---|---|---|
| 03B8 | 6400 | 20 | 0000 | — | 4edf:0000 | — | scripted path (cut-scene posture copy) |
| 03CC | 6400 | 6 | 1500 | — | 4edf:0370 | — | carrier take-off run |
| 03E0 | 6400 | 2 | 1500 | — | 4edf:0252 | — | runway take-off run |
| 03F4 | 5120 | 2 | 1580 | — | 4edf:06fc | — | parked on a carrier |
| 0408 | 5120 | 2 | 1500 | — | 4edf:0870 | — | parked on an airfield |
| 041C | 5120 | 2 | 0082 | 4edf:120a | 4edf:11f8 | 4edf:16ea | follow waypoints (leader) |
| 0430 | 5120 | 2 | 0082 | 4edf:12fa | 4edf:11f8 | 4edf:16ea | join formation |
| 0444 | 5120 | 2 | 0082 | 4edf:135a | 4edf:11f8 | 4edf:16ea | keep formation |
| 0458 | 5120 | 2 | 1080 | — | 4edf:11f8 | — | climb-out after take-off (fly only) |
| 046C | 5120 | 2 | 0002 | 4edf:13bd | 4edf:11f8 | 4edf:16ea | orbit/patrol a point |
| 0480 | 5120 | 2 | 0002 | 4edf:1463 | 4edf:11f8 | 4edf:16ea | go to the current waypoint |
| 0494 | 5120 | 2 | 0082 | 4edf:14a6 | 4edf:11f8 | 4edf:16ea | return to base / land |
| 04A8 | 5120 | 2 | 0082 | 4edf:153e | 4edf:11f8 | 4edf:16ea | escort (join) |
| 04BC | 5120 | 2 | 0082 | 4edf:15da | 4edf:11f8 | 4edf:16ea | escort (fly with) |
| 04D0 | 5120 | 2 | 0002 | 4edf:1413 | 4edf:11f8 | 4edf:16ea | fly to a stored point |
| 065A | 6400 | 2 | 0080 | — | 5410:01e7 | — | ship: keep station |
| 066E | 6400 | 2 | 0080 | — | 5410:018c | — | ship: follow waypoints |
| 0682 | 6400 | 2 | 0000 | — | 5410:016e | — | ship: stopped |
| 0FF5 | 0 | 10 | 1110 | — | 655d:009b | — | going down (crew bail-out) |
| 1009 | 0 | 0 | 0010 | — | — | — | ship sunk (no functions) |
| 1178 | 0 | 0 | 0000 | — | — | 6cc2:00cb | drop tank falling |
| 12DE | 6400 | 6 | 0053 | 0619:0304 | 4edf:11f8 | 1142:100d | tactic: pursue in pairs (lead) |
| 12F2 | 6400 | 2 | 0053 | 0619:0602 | 4edf:11f8 | 1142:100d | tactic: pair spread |
| 1306 | 6400 | 6 | 0053 | 0619:01dc | 4edf:11f8 | 1142:100d | tactic: bracket |
| 131A | 6400 | 4 | 0053 | 0619:04a2 | 4edf:11f8 | 1142:100d | tactic: pair attack |
| 132E | 6400 | 4 | 0050 | 0619:05a8 | 4edf:11f8 | 1142:100d | tactic: pair break |
| 1384 | 0 | 8 | 1110 | — | 088a:0007 | — | wreck on a carrier deck |
| 14A5 | 12800 | 20 | 0870 | 0deb:060d | 4edf:11f8 | 1142:100d | ground attack: dive bomb |
| 14B9 | 12800 | 20 | 0070 | 0deb:0c40 | 4edf:11f8 | 1142:100d | ground attack: torpedo run |
| 14CD | 12800 | 20 | 0870 | 0deb:0c2f | 4edf:11f8 | 1142:100d | ground attack: level bomb (variant) |
| 14E1 | 12800 | 20 | 0870 | 0deb:0c1e | 4edf:11f8 | — | ground attack: level bomb (variant, no think) |
| 14F5 | 12800 | 20 | 0870 | 0deb:0548 | 4edf:11f8 | 1142:100d | ground attack: approach/egress |
| 1509 | 12800 | 20 | 0872 | 0deb:13ac | 4edf:11f8 | 1142:100d | ground attack: strafe |
| 151D | 12800 | 20 | 0872 | 0deb:13f3 | 4edf:11f8 | 1142:100d | ground attack: rocket run |
| 1560 | 6400 | 8 | 0053 | 1027:02d3 | 4edf:11f8 | 1027:0956 | tactic 1027 A |
| 1574 | 6400 | 2 | 0073 | 1027:046b | 4edf:11f8 | 1027:0956 | tactic 1027 B (attack bombers) |
| 1588 | 6400 | 6 | 0053 | 1027:0680 | 4edf:11f8 | 1027:0956 | tactic 1027 C |
| 159C | 6400 | 8 | 0053 | 1027:0845 | 4edf:11f8 | 1027:0956 | tactic 1027 D |
| 15B0 | 6400 | 8 | 0050 | 1027:0822 | 4edf:11f8 | 1027:0956 | tactic 1027 E |
| 15CE | 0 | 4 | 1110 | 10bf:00d2 | — | — | wreck (timer) |
| 15E2 | 0 | 8 | 1110 | 10bf:01d6 | — | — | player riding the carrier (skip-ahead) |
| 15F6 | 6400 | 6 | 1100 | — | 1133:003a | — | 1133 A |
| 160A | 6400 | 2 | 1100 | 1133:00ce | — | — | 1133 B |
| 16B5 | 2560 | 2 | 0016 | 12fd:042a | 4edf:11f8 | 1142:100d | dog-fight: climb / gain altitude |
| 16C9 | 6400 | 2 | 0013 | 12fd:04ca | 4edf:11f8 | 1142:100d | dog-fight: pursue (main attack state) |
| 16DD | 6400 | 2 | 0013 | 12fd:15a3 | 4edf:11f8 | 1142:100d | dog-fight: dive on target |
| 16F1 | 6400 | 2 | 0051 | 12fd:076b | 4edf:11f8 | 1142:100d | dog-fight: overshoot / extend |
| 1705 | 6400 | 2 | 0051 | 12fd:17c4 | 4edf:11f8 | 1142:100d | dog-fight: 1705 |
| 1719 | 19200 | 2 | 0013 | 12fd:08a7 | 4edf:11f8 | 1142:100d | head-on pass (target above/left) |
| 172D | 19200 | 2 | 0013 | 12fd:08b8 | 4edf:11f8 | 1142:100d | head-on pass (other side) |
| 1741 | 6400 | 6 | 0270 | 12fd:07f7 | 4edf:11f8 | 4edf:16ea | aerobatic manoeuvre (1ad2) |
| 1755 | 6400 | 2 | 0271 | 12fd:090b | 4edf:11f8 | 4edf:16ea | 1755 |
| 1769 | 6400 | 6 | 0271 | 12fd:09e2 | 4edf:11f8 | 12fd:092d | defend (break) |
| 177D | 6400 | 2 | 0231 | 12fd:0e28 | 4edf:11f8 | 4edf:16ea | 177D |
| 1791 | 6400 | 2 | 0213 | 12fd:1438 | 4edf:11f8 | 4edf:16ea | 1791 |
| 17A5 | 6400 | 2 | 0211 | 12fd:1491 | 4edf:11f8 | 4edf:16ea | 17A5 |
| 17B9 | 6400 | 2 | 0231 | 12fd:15f4 | 4edf:11f8 | 4edf:16ea | 17B9 |
| 17CD | 19200 | 2 | 0013 | 12fd:1753 | 4edf:11f8 | 1142:100d | 17CD |
| 17E1 | 6400 | 2 | 0013 | 12fd:17fc | 4edf:11f8 | 1142:100d | 17E1 |
| 17F5 | 6400 | 4 | 0002 | 12fd:181f | 4edf:11f8 | 1142:100d | 17F5 (flight-level retarget) |
| 1809 | 500 | 12 | 0012 | 12fd:1a1e | 4edf:11f8 | 1142:100d | wingman: cover the leader |
| 181D | 2560 | 12 | 0012 | 12fd:1ad8 | 4edf:11f8 | 1142:100d | wingman: rejoin |
| 1831 | 12800 | 8 | 0073 | 12fd:1225 | 4edf:11f8 | 1142:100d | turret bomber: defend |
| 1845 | 19200 | 8 | 0070 | 12fd:115d | 4edf:11f8 | 1142:100d | 1845 |
| 1859 | 12800 | 2 | 0232 | 12fd:1b4d | 4edf:11f8 | 4edf:16ea | 1859 |
| 186D | 12800 | 2 | 0040 | 12fd:03a6 | 4edf:11f8 | 4edf:16ea | evade (under attack) |

(The names in the last column are refined in the per-segment sections below; state descriptors
are data — the port can keep them as a table of `{period, scratch, flags, steer, act, think}`
indexed by their DS address.)

`DS:5800` and `DS:57EC` are **pseudo-descriptors** used only as tags by the target chooser
(ship attack / place attack, §5); they are never installed in a brain.

### 1.2 Per-frame order

`5440:1317` (sim_flow's frame step) calls `5058:0630 world_ai_update`:

```
flights_pre     5058:0329   per flight: members' situation flags +42 = +42 & +46, +46 = 0;
                            standby flights (F+3B & 2): scramble check 5058:0165
flights_act     5058:05b9   per active flight (F+3B & 2 clear): ship group marker, then members:
                            plane_act 5058:048e → desc.act (plane_fly …)
flights_think   5058:03d1   per active flight: aircraft flight → renumber members (+BC);
                            ship group marker and members: brain_think 69fe:04a0
                            → all_gunnery 1284:0435 → per aircraft flight: 1142:11c3
```
Element spotting (`583c:1992`) and the LSO (`6dfc:02e5`) are called separately by `5440:1317`
(sim_flow §6 gives the order). Timers are in `DS:711E` units (dt, 100h per nominal frame).

### 1.3 Calling conventions

Several functions here take register arguments (Borland `_fastcall`-like helpers): `69fe:0015`
(AX = descriptor, BX = brain), `69fe:04a0`/`05f1` (AX = object, BX = brain), `1ad2:002e/0acc/
0b20/0b82` (AX = manoeuvre, BX = plane), `4edf:0619` (BX = plane), `365a:*` (BX = object). Near
helpers with the `inc bp` marker (`45 55 8B EC`) take stack arguments at `[bp+4]`. The port uses
ordinary C parameters.

## 2. `69fe` — state executor

| Address | Name | Does | Conf. |
|---|---|---|---|
| 69fe:0000 | brain_module_init | empty | verified |
| 69fe:0005 | brain_jitter | `DS:488C += 13`; returns `DS:488C & 15` (deterministic timer jitter, not the RNG; `DS:488C = 0` at init, `59f9:0068`) | verified |
| 69fe:0015 | brain_set_state(AX = desc, BX = brain) | `brain+0 = desc`; `brain+2 (i32) = desc.period + brain_jitter()`; `brain+6 (i32) = 0`; `brain+0C (u16) = 0`; zero `DS:47F4` bytes of the scratch `brain+0A`; returns the scratch pointer | verified |
| 69fe:0073 | ai_break_toward(Plane *p) | `pt = p.pos`; `3624:0000(pt, p.heading, 3000)` (move 3000 along the heading); `attack_run_start(p, pt)` (`0deb:000a`) — used to make a plane (the one called for help) turn toward a point ahead | likely |
| 69fe:00bb | ai_call_help(AX = victim) | `n = flight_alive_members(victim's flight, list)` (`1142:0f5f`; AX = flight in the register call); for each member m with ground distance to the victim < 20000 and `has_ordnance(m)` (`0deb:1490`): the player → radio message 55h (`1815:06e7(55h, rec{victim}, 0)`); AI → `ai_break_toward(m)`, `ai_think_target(m)` (`1142:100d`) | likely |
| 69fe:015c | brain_threat_check(BX = plane) | §2.1 | likely |
| 69fe:04a0 | brain_think(AX = obj, BX = brain) | §2.2 | verified |
| 69fe:05f1 | brain_act(AX = obj, BX = brain) | `d = brain.desc`; call `d.act(obj)` if non-null; if the state did not change: `brain+0C |= 2`; `alert_tick(obj)` (`14c3:0153`) | verified |

`6a63:0000` (= the address Ghidra shows as `69fe:0650`) returns `DS:51EC`, the add-on module flag
(sim_flow VCR spec) — the AI reads it in `1142:0ba6`.

### 2.1 `69fe:015c brain_threat_check(Plane *p)` — likely

```
d = p.brain.desc; (src, lvl) = alert_get(p) (14c3:01af: AX = source +32, DX = level +2C)
timer_dec(&p+F9); if timer_dec(&p+FF) == 0: p+F2 = 0          // hit-reaction timer resets the hit count
if plane_is_down(p): return 0
if p != player:
    timer_expired32(&p+E7); timer_expired32(&p+DF)
    if (d.flags & 10h) && !(d.flags & 200h) && (flight+3B & 4): ai_think_target(p); return 1
    if ai_evade_check(p) (12fd:03e8): return 1
switch lvl:
  1 (spotted): if d.flags & 4: p+D7 = src; brain_set_state(16C9h, p.brain); return 1   (no player test)
  6 (attacked by src):
     if (d.flags & 2) or (p == player and turret_count(p) (1284:041c) != 0) or (p+45 & 20h):
        k = 0; P = pilot(p); cls = aircraft(p).DAT+38 (0 fighter, 3 bomber …)
        if (p+43 & 1) or ai_spot_reaction(p, src) (583c:09de):
            src+1B |= 4                                          // attacker is known
            if cls == 0 and !has_ordnance(p):
                if p.v(+6C) − src.v(+6C) < 200:
                    ok = can_dogfight(p, src) (12fd:0caa)
                    if P+46 != 0 and ok: k = 177Dh
                    elif ok or p+D7 == 0: k = 16C9h
            elif cls == 3:                                        // bomber: take the closest attacker
                if p+D7 == 0 or p+D7→+D7 != p: p+D7 = src
                elif dist2(p, src) < p+D3: p+D7 = src
            else:
                k = 1769h
                if cls == 0 and (L = flight_leader(flight)) != player:
                    if dist2(L, p) < 20000:
                        if dist2(L, flight+10→(escorted/protected obj)+4) > 60000: ai_call_help(p)
                    elif dist2(p, flight+10→+4) > 60000: ai_break_toward(p)
        if k: p+D7 = src; if is_pure_fighter(p) (0deb:1555): p+1C |= 1
              if p != player: brain_set_state(k, p.brain); return 1
return 0
```

### 2.2 `69fe:04a0 brain_think(obj, brain)` — verified

```
d = brain.desc; force = false
if obj == player: player_threat_update(player) (1284:01a3)
if obj+18 == 1 (ship): timer_dec(&obj+78); timer_dec(&obj+7A)
if d.flags & 1 and plane_is_down(obj+D7): force = true
if force or (d.think and brain.timer == 0):
    d.think(obj)
    if brain.desc == d: brain.timer = d.period + brain_jitter()
if obj+18 == 0 and brain_threat_check(obj): d = brain.desc
if !(d.flags & 40h): timer_expired32(&brain.timer)
if obj+18 == 0 and obj != player: controls_neutral(&obj+AC) (4bf9:09f4)
if d.steer and d.steer(obj) != 0: brain.timer = 0
if brain.desc == d: brain+0C |= 1; brain.frames++
```

## 3. `14c3` — alert and radio state (per plane, `Plane+2C..+33`)

| Off | Meaning |
|---|---|
| +2C | i8 current alert level (0 none, 1 enemy spotted, 6 attacked, 7–12 radio/comm levels, see below) |
| +2D | i8 cooldown of the level (frames; at 0 the level is cleared) |
| +2E, +2F, +30 | i8 cooldowns that pair levels 10↔7, 11↔8, 12↔9 |
| +32 | source object of the alert |

| Address | Name | Does | Conf. |
|---|---|---|---|
| 14c3:000b | alert_pair(int hi, i8 *cnt, int lo) | near. `new = DS:5826`: if `new == hi`: `*cnt = 2`; if `DS:5824+2C == lo`: `+2C = 0`; return 1. Else if `new == lo && *cnt != 0`: return 1. Else 0 | verified |
| 14c3:0054 | alert_raise(Plane *p, int lvl, …) | `DS:5826 = lvl`, `DS:5824 = p`; if `alert_pair(10, &p+2E, 7) || alert_pair(12, &p+30, 9) || alert_pair(11, &p+2F, 8)`: `lvl = 0`. If `p+2C >= lvl` return. `p+2C = lvl`; `cd = 2`; by level: 1, 5, 6, 7, 8 → `p+32 = arg1`; 9 → `p+32 = arg1`, `cd = (u8)arg2`; 2–4 nothing; then `p+2D = cd` | verified |
| 14c3:0130 | cnt_dec(i8 *c) | near: `--*c`; if `<= 0`: `*c = 0`, return −1; else 0 | verified |
| 14c3:0153 | alert_tick(Plane *p) | if `cnt_dec(&p+2D)`: `p+2C = 0`; `cnt_dec(&p+2E/+2F/+30)` (called after each act) | verified |
| 14c3:0197 | alert_clear(p) | `p+2C..+33 = 0` | verified |
| 14c3:01af | alert_get(p) | returns AX = `p+32` (source), DX = `(i8)p+2C` | verified |

## 4. `5058` — per-frame flight update

Flight record fields used here (56h bytes, `sim_world_dmg.md` data structures): `+06` members,
`+08` member list, `+10` protected/escorted object (role 6), `+16..+1B` waypoint cursor {i16 index,
i16 count, ptr list} (the cursor at `F+16` is what `17fe` operates on: `cur[0]` = index = `F+16`,
`cur[1]` = count = `F+18`, `cur[2]` = list = `F+1A`), `+3A` bits 10h (pairs made), 80h (all members
in one element), `+3B` bits 1 (fighting), 2 **standby** (flight not active: scramble reserve —
correction: the dmg part calls it "carrier task group"; it is set from the group record `R+1E`
and cleared when the flight is launched by `51fb:0199`), 4 (sweep: members may leave to fight),
`+3E` escorted flight, `+42` side, `+44/+46` linked flights.

| Address | Name | Does | Conf. |
|---|---|---|---|
| 5058:0000 | flight_leader_first | returns `F+08[0]` | verified |
| 5058:0010 | waypoint_advance(Plane *p) | (leader only, from `plane_act`) `f = p+34`; only if `f+3E == 0` (not escorting) and `f+18 != 0`: `w = wp_current_pos(&f+16)`; `near_player = f == player+34`; `hurry = DS:3F04 && (p+1C & 4) && !near_player`; radius = 100 if hurry, 10000 if `f+02 == 6`, else 5000; if `dist2(p, w) < radius` and (`!near_player` or (`DS:3F04 == 0` and `DS:069C == 0`)): `wp_cursor_advance(&f+16, 1)`; training mission (`DS:477C == 5`) and not the player's flight: `f+16 = 0` (loop the route); `hurry` → `p+1C |= 2` | likely |
| 5058:010b | ship_waypoint_advance(s, cur) | `w = wp_current_pos(cur)`; if `w` and `dist2(s, w) < 500` and `wp_cursor_advance(cur, 1)`: return; if `w` and not reached: return; else `brain_set_state(0682h, s)` (stop) | likely |
| 5058:0165 | standby_scramble_check(Flight *f) | §4.1 | likely |
| 5058:0329 | flights_pre | §1.2 | verified |
| 5058:0393 | flight_renumber(f) | `F+08[i]+BC = i` for every member; returns 0 | verified |
| 5058:03bb | flight_active(f) | `(f+3B & 2) == 0` | verified |
| 5058:03d1 | flights_think | §1.2 | verified |
| 5058:048e | plane_act(obj) | `old = obj.pos`; planes (`+18 == 0`) with `+43 & 8` clear and any of `+43 & (10h|20h|40h|80h)` (avoidance flags from `085b`): `plane_avoid_collision` (`04c4:0c53`) instead of the state's act; else `brain_act`. `clamp_world(obj)`. Planes with `+1D & 10h` and byte `(+16)[1] != 0`: `--(+16)[1]`, at 0 clear gear-down `+BA & 10h` and `+1D & 10h` (gear retraction delay). `obj+36 = old` (previous position), `365a:0082`. Aircraft flights: if `plane_in_formation(obj)` (it is the leader): `waypoint_advance(obj)`; ship groups: ships with a type (`+19 != 0`) and waypoints: `ship_waypoint_advance(obj, &f+16)` | likely |
| 5058:05b9 | flights_act | §1.2 | verified |
| 5058:0630 | world_ai_update | §1.2 | verified |
| 5058:0641 | flights_nop | empty | verified |
| 5058:0646 | objects_clamp_world | `clamp_world` on every object (`DS:475D`, `DS:4778 + DS:4772` entries) | verified |

### 4.1 `5058:0165 standby_scramble_check(Flight *f)` — likely

```
R = 4edf:1790()  (i32 scramble radius); P = player+34; side = f+42; c = f+08[0]; n = f+06
for each plane q (DS:475B[0..DS:4776)) with q+34 != f:
    qualifies = (q+26 + side == 1) (enemy) or q+34 == P (the player's flight)
                or (q+34→+02 == 6 and q+34→+10 == f) (a flight protecting f)
    and !(q+34→+3B & 2)                                   (not itself on standby)
    if not qualifies: continue
    d = dist2(q, c)
    if f+00 == 1 (ship group): hit = d < 350000 and any member m with dist2(q, m) < R
    else hit = d < R
    if hit:
        launch_intercept(f, &q.pos) (51fb:0199)
        for each linked flight g (f+46[0..f+44)): if f+3B & 2 and dist2(g→members[0], c) < 500000:
            launch_intercept(f, &g→members[0].pos)          // (sic: f, not g)
        return
```

## 5. `1142` — target choice and the common think

### 5.1 Candidate records

The chooser keeps the best candidate in `DS:5814` (12 bytes): `+0` priority class, `+2` score,
`+4` 0, `+6` (`DS:581A`) target, `+8` (`DS:581C`) state descriptor to use, `+A` 0.
`1142:027c offer(prio, desc, target, score)` builds such a record and `1142:005d` keeps it when it
is lexicographically greater in its first three words (`1142:001d`: compare 3 ints, first
difference decides, a > b → 1).

Aircraft description used by the scoring (`1142:02b8 plane_rec(out[10], p)`): x, y, z (i32),
pitch, roll, heading, speed `+6C`.

| Address | Name | Does | Conf. |
|---|---|---|---|
| 1142:0000 | plane_is_down(p) | `(p+1A & 1) || (p+1A & 40h)` | verified |
| 1142:001d | cmp3_gt(int a[3], int b[3]) | near, see above | verified |
| 1142:005d | offer_keep(rec) | near: `if cmp3_gt(rec, DS:5814)`: copy 12 bytes to `DS:5814`; returns the comparison | verified |
| 1142:008e | band_factor(int d, int r[3], int *num, int *den) | near: `r[1] < d <= r[2]` → `num = d − r[1]`, `den = r[2] − r[1]`; `r[0] <= d <= r[1]` → `num = r[1] − d`, `den = r[1] − r[0]`; return 1; else 0 | verified |
| 1142:00eb | aim_factor(rec a, rec b, int ang[3]) | `o = angles_to(a, b)` (`3614:0009`: 2 words, pitch and heading from a to b); `o −= ang` (`vsub`); `f = (0FFFFh − (abs16(o0) + abs16(o1))) >> 8` (32-bit), min 1 | verified |
| 1142:0164 | threat_score(rec a, rec b, int *out_f) | §5.2 | verified |
| 1142:027c | offer(prio, desc, target, score) | near, see above | verified |
| 1142:02b8 | plane_rec(out, p) | see above | verified |
| 1142:02f5 | offer_climb(p, tgt) | `z = max(p.z, 0)`; `k = max(0FFFh − z, 0)`; `offer((i16)(k >> 9), 16B5h, tgt, 0)` — a low plane (< 4095) gets a "climb" candidate | verified |
| 1142:0350 | pursuit_variant(p) | §5.3 | likely |
| 1142:04cc | attackers_of(t, except) | number of planes q ≠ except with `q+D7 == t` | verified |
| 1142:0500 | flight_protects_obj(obj, p) | obj in `p+34→+10[0..(i8)+0E)` | verified |
| 1142:0536 | covers(t, p) | `p+34→+43 == 0` (cover mode "list of flights") → test `t+34` instead of t; `flight_protects_obj` | verified |
| 1142:0564 | flight_all_done(f) | aircraft flight: every member down or `+1C & 80h`; ship group: every member sunk (`+1B & 2`) or `+1D & 1`; returns 1 | verified |
| 1142:05ce | target_class(p, t, is_place) | §5.4 → 0..4 | likely |
| 1142:08c2 | apply_class(int *score, p, t, is_place) | `*score = *score·DS:1634[target_class(p, t, is_place)] >> 10`, `DS:1634` = {0, 200, 400, 800, 1600} | verified |
| 1142:08fb | offer_air_target(p, t) | §5.5 | likely |
| 1142:0b73 | within_50000(t, p) | `dist2(p, t) < 50000` | verified |
| 1142:0ba6 | choose_target(p, is_bomber_type, attacks_ground) | §5.6 | likely |
| 1142:0e4e | help_msg_reset | `DS:57EA = 0` | verified |
| 1142:0e59 | help_msg(p) | once (`DS:57EA`), for a plane of the player's flight: radio 54h (player not leading) or 57h (player leads) with p | verified |
| 1142:0eab | engage_best(p) | §5.7 | verified |
| 1142:0f5f | flight_alive_members(f, out[]) | copies the members not down; returns the count | verified |
| 1142:0fb2 | bomber_cover_think(p) | `p+1C &= ~1`; `o = f+10` (first protected object); if `dist2(p, o) < 80000` and `0deb:15a2(f, o)`: return 1; else 0 | likely |
| 1142:100d | ai_think_target(p) | §5.8 — the think of most combat states | verified |
| 1142:11aa | low_power(p) | `p+A4 < 32Ah` (engine factor below 79 %) | verified |
| 1142:11c3 | flight_targets_update(f) | §5.9 | likely |
| 1142:12f5 | alert_flight(p) | (someone spotted p's enemy) if `p != player` and the state flags have neither 400h nor 10h: once per flight (`f+3A & 10h`) re-pair the elements (`583c:042b(f, 1)`); non-bombers: `ai_think_target(p)`, `p+DF = 0` | verified |
| 1142:135b | ai_forget_plane(p) | §5.10 | verified |
| 1142:1421 | targeting_nop | empty | verified |

### 5.2 `1142:0164 threat_score(a, b, out_f)` — verified

```
d = dist3(a, b) (277a:3b3c, i32); only its LOW WORD is used (quirk: > 32767 wraps)
if !band_factor((i16)d, DS:1644 → {−15000, 5000, 25000}, &num, &den): return 0
t = a.angles + DS:1622 (−1400, 0, 0)          // (pitch, roll, heading)
f1 = aim_factor(b, a, t); if out_f: *out_f = f1
f1 = (i16)((i32)f1·f1 >> 8)
t = DS:1628 (1800, 0, 0) − a.angles
f2 = aim_factor(a, b, t)
r = satdiv((den − num) << 8, den) & 0FFE0h
return (i16)(((i32)(i16)(((i32)f1·f2) >> 1)·r) >> 9)
```

### 5.3 `1142:0350 pursuit_variant(p)` → descriptor — likely

`t = p+D7` (if `t` is in state 1809h, use `t+DD`, its leader); `b = bearing(t → p)` (`3629:0004(t.pos,
p.pos)`); `rel_p = b − p.heading`, `rel_t = b − t.heading`. `tt = t+D7` (1809h → its `+DD`). Default
16C9h. Head-on option when (`t == player` or (`t` is in 16C9h and `tt == p`)) and the energy test
`((7Fh − P(p)+44)·(i8)DAT(p)+59) >> 8 <= ((7Fh − P(t)+44)·(i8)DAT(t)+59) >> 8` and `(u16)(rel_p +
8000) >= 16000` and `(u16)(rel_t + 0DDC0h) < 48000` and (`(u16)(rel_t + 9F40h) >= 16000` or
`(u16)(rel_p + 24000) < 48000`) and `(rng & 3FFh) < P(p)+1A` (**RNG**): 1719h if `p.pitch < 0`
else 172Dh.

### 5.4 `1142:05ce target_class(p, t, is_place)` — likely

`role = p+34→+02`; `bomber = role == 3`; `k = (i8)p+CA`; `ga = has_ordnance(p)`;
`L = flight_leader(p+34)`; `not_player_led = L != player`.
* If `p+E3 != 0` (i32, a ground-attack task is running) and `k != 0`: if `!is_place` and t is a
  plane: `4` if `k < 5` and `k − 1 == DAT(t)+38` (the task's target class) else `1`; if nothing
  decided and `p+BD == t`: 4.
* Else if `is_place == 0`: `air = (t+18 == 0)`:
  - role 2, or bomber flight without `is_pure_fighter`: if t is not a plane… (`!air` means
    t is a ship) and `covers(t, p)`: `not_player_led ? (bomber ? (ga ? 4 : 2) : 4) :
    help_msg(p)` (0);
  - role 0, 1 or bomber: `air ? 2 : 0`;
  - role 4: air → `covers(t, p) ? 4 : 2`;
  - role 5: air → cover mode `p+34→+43 == 2` → `covers(p+34→+10, t)`; `t+34→+43 == 2` →
    `covers(t+34→+10, p)`; else `flight_protects_obj(p+34→+10, t)`; → 4 / 2;
  - role 6: air → `g = p+34→+10`; if `flight_all_done(g)` → 2; else if t is a fighter
    (`DAT+38 == 0`): `j = first_alive(g)` (`583c:0000`), `dist2(g.members[j], t) < 30000` → 4
    else 2; else 0.
* Else (`is_place`) with bomber or role 2: `flight_protects_obj(t, p)` → as the role-2 branch.

### 5.5 `1142:08fb offer_air_target(p, t)` — likely (near; returns "keep looking")

```
w = p+DD (element leader); d = dist3(p, t)
a = plane_rec(p), b = plane_rec(t); s = threat_score(a, b, &f)
if s == 0:
    if w == 0 and d < 60000:
        s = (60000 − d) >> 4; dz = t.z − p.z; apply_class(&s, p, t, 0)
        if s == 0: stop = 1
        else offer(dz < −5000 ? 0 : 2, dz < −5000 ? 16DDh : 16C9h, t, s)
else:
    desc = 16C9h; prio = 6; apply_class(&s, p, t, 0); if s == 0: stop = 1
    if p+E3 == 0:
        if (has_ordnance(t) or DAT(t)+38 != 0) and w and 0619:00ce(t)
           and not (w+D7 == t and w in state 131Ah): s = 0; desc = 1574h
        if w:
            lim = P(p)+16
            if w == player:
                if p+E7 != 0: lim += (p+1B & 10h) ? 15000 : −5000
                if p in 1809h and f > 200 and d < 15000: lim −= 9000; desc = 1574h
            elif w in 1574h or 131Ah: lim −= 9000; desc = 1574h
    else lim = 0
    if t == player: s = min(s·DS:163E[DS:42D2] >> 10, 32000)   // {1024, 1500, 2000}
    if s != 0 and (w == 0 or lim < s):
        s = satdiv(s, attackers_of(t, p) + 1); offer(prio, desc, t, s)
return !stop
```
(`+E7` adjustment verified in the disassembly: +3A98h / −1388h.)

### 5.6 `1142:0ba6 choose_target(p, bomber_type, ga)` — likely

```
best = 0; addon = 6a63:0000() && 0deb:1500(p)
if ga or 0deb:150f(p) or addon:
    for each ship group g (flight slots 0..DS:4765, the first entries after sorting) with g+42 != p+26:
        near = 0; pick = 0; bestv = 100
        for each member s not sunk:
            if within_50000(s, p): near = 1
            if (ga or ship DAT(s)+6D != 0 or addon) and
               ((p+E3 && p+CA == 5 && p+BD == s) or (p+34→+43 == 2 && p+34→+10 == s)
                or ((v = 1660:0787(s)) < bestv and (pick = s, bestv = v, v < 0))): break
        (pick = the member the loop ended on)                     // Ghidra: local_1a = iVar1
        if near and pick: s = 10000; apply_class(&s, p, pick, 0); if s: offer(6, 5800h, pick, s); best = 1
    for each place pl (DS:4755, 20h each) with kind byte pl+1C != 0Dh:
        if 465c:00ee((i8)pl+1D) != p+26 and dist2(p, pl) < 80000:
            s = 10000; apply_class(&s, p, pl, 1); if s: offer(6, 57ECh, pl, s); best = 1
if !bomber_type and !ga:
    n = spotted_enemies(list, p, &k) (583c:0b51)
    for each t in list not down: best = offer_air_target(p, t)
    if best: offer_climb(p, 0)
return best
```

### 5.7 `1142:0eab engage_best(p)` — verified

```
t = DS:581A; lead_msg = true
if DS:581C == 5800h: 0deb:1817(p, t) (ship attack set-up); p+D7 = 0
elif DS:581C == 57ECh: 0deb:1cae(p, t) (place attack set-up); p+D7 = 0
else:
    lead_msg = false; p+D7 = t; if t: gun_solution(p) (1284:02fb)
    if DS:581C == 1574h: 1027:02b3(p)
    else: if DS:581C == 16C9h and p in 16C9h: DS:581C = pursuit_variant(p)
          brain_set_state(DS:581C, p.brain)
if lead_msg and plane_in_formation(p): help_msg(p)
```

### 5.8 `1142:100d ai_think_target(p)` — verified

```
ga = has_ordnance(p); cls = DAT(p)+38; bomber_type = cls != 0; w = p+DD; ret = 0
L = flight_leader(p+34); player_leads = (L == player)
if DS:477C == 5 (training): p+1C &= ~1; return 0
if p.desc.flags & 400h: return 0
if ga and cls == 3 and p+34→+43 == 1: return bomber_cover_think(p)
DS:5814 = 0 (12 bytes)
DS:581C = (!bomber_type and !ga) ? (w ? 1809h : 16B5h) : (w ? 0430h : 041Ch)   // default: cover/climb or formation
hold = player_leads ? player_orders_active() (1660:01b4)
                    : (is_pure_fighter(p) and (p+34→+3B & 4))
if !hold:
    if choose_target(p, bomber_type, ga): p+1C |= 1; if p != player: engage_best(p); ret = 1
    else p+1C &= ~1
else:
    if !player_leads and player+34 == p+34 and (p.desc.flags & 10h): radio 52h (L)
    p+1C &= ~1; ai_leave_combat(p) (4edf:0edb); ret = 1
return ret
```

### 5.9 `1142:11c3 flight_targets_update(Flight *f)` — likely

```
n = flight_alive_members(f, m[]); fighting = 0
for each m[i]: if m[i]+1C & 1: fighting = 1
               elif m[i] != player and (desc.flags & 10h) and !(desc.flags & 600h):
                   (f+3A & 80h) ? ai_leave_combat(m[i]) : brain_set_state(17F5h, m[i].brain)
if fighting: f+3B |= 1; return 1
f+3B &= ~1
if low_power(m[0]):                              // leader has a damaged engine: hand over the lead
    for i = 1..n−1: if !low_power(m[i]):
        swap m[0] and m[i] in f+08; st_think_combat(m[i]); st_think_combat(m[0]); return 0
return 0
```

### 5.10 `1142:135b ai_forget_plane(p)` — verified

`f = p+34`; `583c:042b(f, 0)` (re-build the elements); for each other alive member q: collect it;
if `q+DD == p`: `q+DD = first_found` (the first alive member that lost its leader becomes the new
leader, later ones follow it); the new leader (if not the player) re-thinks
(`st_think_combat` `4edf:16ea`). If exactly two remain and neither has a leader: the second
follows the first (`+DD`) and re-thinks.

## 6. `583c` — elements (sections), spotting, pairing

### 6.1 Element records

`DS:47E2` (far) = `DS:47E0` (= number of planes) records of 16 bytes (`583c:1a9b` allocates, `1ad0`
frees): `+0` used, `+1` i8 n, `+2` Plane* members[4], `+0A` i16 front scan timer, `+0C` side scan
timer, `+0E` rear scan timer. **Quirk:** `583c:0176` appends without a bound check — a fifth member
would overwrite the timers.

Per plane: `+C3` 6-byte bit set of plane serials (`+C9`) the plane knows about (spotted),
`+DD` element leader (0 = leads), `+1A` bits 20h (second wingman of a 3-plane element) / 80h
(wingman that has a second wingman).

| Address | Name | Does | Conf. |
|---|---|---|---|
| 583c:0000 | first_alive(f, i) | first index ≥ i of a member with `obj_alive` and not `+1A & 40h`; −1 | verified |
| 583c:0050 | element_alloc | first record with `used == 0` (returns the far pointer; past the end when none) | verified |
| 583c:0084 | elements_clear(f) | every record whose `members[0]` is in f's member list is zeroed (`_fmemset 16`) | verified |
| 583c:00df | element_accepts(far e, Plane *p, i32 *best) | scan members last to first: `d = dist2(member, p)`; `if d > far_: far_ = d; if d > *best: break`; `if d < 18000: ok = 1`; if ok: `*best = far_`; return ok | verified |
| 583c:0176 | element_add(far e, p) | `members[n++] = p`; `used = 1` | verified |
| 583c:0199 | element_pair(e, mode) | `m0+DD = 0`, `m0+1A &= ~20h`; n ≥ 2: `m1+DD = m0`, `m1+1A &= ~(20h|80h)`; n ≥ 3: mode 2: `m2+DD = m0`, `m2+1A |= 20h`, `m1+1A |= 80h`, done; else `m2+DD = 0` (leads a second pair), `m2+1A &= ~20h`; n ≥ 4: `m3+DD = m2`, clear 20h/80h | verified |
| 583c:0212 | elements_build(f, force_pair) | §6.2 | verified |
| 583c:042b | elements_rebuild(f, force_pair) | `elements_clear(f)`, `elements_build(f, force_pair)` | verified |
| 583c:0448 | elements_build_all | for the aircraft flights (sorted slots `DS:4765 .. DS:4765 + DS:4763 − 1`, last first): `elements_rebuild(f, 0)` | verified |
| 583c:0471 | sun_dir | `v = 6964:005b()` (sun vector when the sun is up) → `DS:47D6 = v >> 4` (`vsar 4`); returns `&DS:47D6` or 0 | verified |
| 583c:04a9 | sun_glare(Vec *eye, Vec *tgt, i32 d, Vec *sun, Plane *p) | only when `sun` and `3000 < d < 100000`: `v = (tgt − eye) >> 3` (as i16), `c = satdiv(vdot(v, sun), (i16)(d >> 3))`; returns `c > P(p)+48` (looking into the sun) | likely |
| 583c:056d | in_cone(int ang[3], int cone[4]) | `lo, hi = sorted(cone[0], cone[1])`; `(u16)(ang[0] − lo) < (u16)(hi − lo)` and the elevation `ang[2]` inside `(cone[3], cone[2])` (wrap-around when `cone[3] >= cone[2]`) | verified |
| 583c:0600 | in_blind_spot(ang, Plane *p) | `in_cone` against the two 8-byte cones at aircraft `.DAT+5B` | verified |
| 583c:0649 | body_angles(out, Vec *tgt, Vec *eye, Matrix *m) | `d = tgt − eye` halved until `linbox(d, 16000)`; as i16, rotated into the body frame (transposed matrix, `365a:0032`, `mat_vec`); `angles_to(out, eye + d', eye)` | likely |
| 583c:06ef | glare_blocks(Plane *p, Vec *tgt) | `sun = sun_dir()`; `sun_glare(tgt, &p.pos, dist2(tgt, p), sun, p)` | verified |
| 583c:0749 | can_see(Plane *p, Plane *t) | §6.3 | verified |
| 583c:0834 | my_wingman(p) | first alive member q of p's flight with `q+DD == p` | verified |
| 583c:0887 | radio_bandit_call(Plane *t, Plane *by) | player's flight radio "bandits at N o'clock" (§6.5) | likely |
| 583c:09de | ai_spot_reaction(Plane *p, Plane *t) | §6.4 | verified |
| 583c:0b51 | spotted_split(out[], Plane *p, int *n_friend) | planes whose bits are set in `p+C3` (`36dd:0009`, `36ea:000e`): enemies (side sum 1) packed at the front of `out`, friends from the back; returns the enemy count, `*n_friend` = friends | verified |
| 583c:0c01 | positions_of(Vec out[], Plane **l, n) | copies the positions | verified |
| 583c:0c40 | element_centre(out, far e) | centre of the bounding box of the members' positions (`6dec:003d`) | verified |
| 583c:0c91 | select_sector(int out[], int bear[], k, n, int head, u16 sector) | for i < n: if `((bear[i] − (head + 2000h)) & C000h) == sector`: `out[k++] = i`; returns k | verified |
| 583c:0cd4 | min_field(void **l, n, off, int *idx) | minimum of the word at `off` over `l[i]`, index of the last minimum (`<=`) | verified |
| 583c:0d1d | max_field(l, n, off, int *idx) | maximum (`>=`), start −7FFFh | verified |
| 583c:0d66 | pilots_of(out[], Plane **l, n) | pilot profiles of the planes other than the player (reverse order) | verified |
| 583c:0daa | rear_watchers(out[2], Plane **m, n) | §6.3 | verified |
| 583c:0e10 | evasive_pilots(out[], Plane **l, n) | planes whose pilot `+41 != 0` | verified |
| 583c:0e4d | spot_range(Plane *eye, far e, Vec *c, int r) | 0 if `glare_blocks(eye, c)`; bombers (`DAT(e.members[0])+38 == 3`): `r = r·1500 >> 10`; `r = ((r·DS:0858[DS:477A] >> 10)·P(eye)+00) >> 10` | verified |
| 583c:0ef0 | element_visual_size(far e) | `range_helper(max shape radius of members)` (`35d6:018a` with AX = shape, `5440:0375`: `max(100000, (r + 40) << 8)`) | verified |
| 583c:0f46 | element_spots(far e, int bearing, i32 d) | §6.3 | verified |
| 583c:1110 | contact_report(out, Plane *eye, far e) | report record for the radio text: `+0 = bearing(centre from eye) − eye.heading`, `+2 = centre.z − eye.z` (i32), `+6 = centre.z`, `+0A = type of e's first member`, `+0C = e.n`, `+0D = 0`, `+0E = 0` (i32), `+12 = dist2(eye, centre)` | verified |
| 583c:119b | element_mark_seen(far e, int quiet) | §6.3 | verified |
| 583c:132f | player_contact_report(int rel, int *out_bear, Vec *out_pos) | (radio orders 45h–48h: "report contacts at 12/6/3/9 o'clock") `h = player.heading + rel`; for every used element not containing the player: `c = element_centre(e)`, if `dist2(c, player) < element_visual_size(e)` and `(u16)(bearing(player → c) − h + 11000) < 22000`: list it; own side → flags `|= 2`, else the first enemy sets flags `|= 1`, `*out_pos = c`, `*out_bear = b + rel`. The player's own element becomes `DS:47DE`; every listed element is then `element_mark_seen(e, 0)`. Returns flags | likely |
| 583c:14e9 | element_scan(far e) | §6.3 | verified |
| 583c:1895 | forget(p, t) | clear t's bit in `p+C3` | verified |
| 583c:18bf | forget_far(p) | for every plane in p's known list not of p's flight: if `dist3(q, p) > element_visual_size-like range(35d6:018a, 5440:0375) + 12000`: forget | verified |
| 583c:1966 | forget_far_all | `forget_far` for every plane | verified |
| 583c:1992 | spotting_update | §6.6 | verified |
| 583c:1a55 | flight_leader(f) | `f+08[first_alive(f, 0)]` or 0 | verified |
| 583c:1a7c | plane_in_formation(p) → is_leader | `flight_leader(p+34) == p` (true for the flight leader; the CSV name "in formation" was wrong) | verified |
| 583c:1a9b | elements_init | `DS:47E0..47F1 = 0`, `DS:47E0 = DS:4776`, `DS:47E2 = far alloc(16·n)` | verified |
| 583c:1ad0 | elements_free | | verified |
| 583c:1ae2 | spotting_nop | empty | verified |

### 6.2 `583c:0212 elements_build(Flight *f, int force)` — verified

```
k = 0 (elements made); mask[6] = 0; i = 0
while (j = first_alive(f, i)) >= 0:
    i = j + 1; p = f+08[j]; chosen = 0; best = 7FFFFFFFh
    for each element e made so far: if element_accepts(e, p, &best): chosen = e
    if !chosen: chosen = element_alloc(); made[k++] = chosen
    element_add(chosen, p); mask |= bit(p+C9)
old80 = f+3A & 80h; f+3A |= 80h; first = −1
for each made element e (index x):
    for each member m (in order):
        if !plane_is_down(m): if first < 0: first = x elif first != x: f+3A &= ~80h
        m+C3 |= mask without m's own bit                         // members know each other
    force |= (old80 == 0 and (f+3A & 80h) and !(f+3B & 1))
    if force: element_pair(e, (f+06 == 3 and f+42 == 1) ? 2 : 1)  // Japanese 3-plane shotai
return k
```

### 6.3 Spotting — verified

`583c:14e9 element_scan(e)` (per element per frame, record copied to a local, written back at the
end):
```
A = timer_dec(&e+0A) == 0; if A: e+0A = 7500
B = timer_dec(&e+0C) == 0; if B: m = min_field(pilots_of(e.members), 2)   // pilot word +2 = alertness
                                  e+0C = 7500 + ((m·(rng & 3FFh) >> 10)·4500 >> 10)          (RNG)
C = timer_dec(&e+0E) == 0; if C: m = rear_watchers(w, e.members, e.n) ? min_field(pilots_of(w), 2) : 400h
                                  if evasive_pilots(v, e.members): m = min(m, min_field(pilots_of(v), 2))
                                  e+0E = 7500 + ((m·(rng & 3FFh) >> 10)·9000 >> 10)          (RNG)
if !(A or B or C): return
c = element_centre(e); head = e.members[0].heading
for each other used element o: oc = element_centre(o); if oc.z < 100000000 and (d = dist2(oc, c)) < 50000:
    cand += {o, bearing(oc from c) (3629:0004(oc, c)), d}
sel = []: A → select_sector(…, head, 0); B → sectors C000h and 4000h; C → sector 8000h
DS:47DE = &e (local copy); DS:47DC = head
for each selected o: if element_spots(o, bearing, d): element_mark_seen(o, 0)
```
`583c:0daa rear_watchers(out, m, n)`: `n == 2` → `out[0] = m[1]`; `n == 3/4` → `out[1] = m[n == 4 ? 3 :
2]`, `out[0] = m[1]`; `r = (n − 1) & 0FFFEh`; if `out[0] == player`: `r−−` and, if `r` was ≠ 0,
`out[0] = out[1]`; elif `out[1] == player`: `r−−`; returns r (so pairs have **no** rear watcher —
arithmetic quirk kept).

`583c:0f46 element_spots(o, bearing, d)` (spotter element `e = DS:47DE`, `rel = bearing − DS:47DC`):
```
if e.n == 1 and e.members[0] == player: return 0         // the player spots for himself
front = (u16)(rel + 4000h) < 8000h
if front and d < 3000: return 1
if front or (k = rear_watchers(w, e.members, e.n)) == 0: w = members other than the player, k = their count
eye = w[argmin pilot+2 over pilots_of(w)]                 // the most alert looker
oc = element_centre(o)
if cloud_blocks_segment(oc, eye.pos): return 0            // 490a:043e
if in_blind_spot(body_angles(oc, eye.pos, eye+20), eye): return 0
r = (i16)(element_visual_size(o) >> 3)
if (u16)(rel + 2000h) >= 4000h: r = (u16)(rel + 6000h) < C000h ? r·400 >> 10 : r·600 >> 10
return (d >> 3) < spot_range(eye, o, oc, r)
```
`583c:119b element_mark_seen(o, quiet)`: `mask` = bits of the spotted element's members; for each
member q of the spotter element `DS:47DE`: `enemy = (o.members[0]+26 + q+26 == 1)`; if q did not
know any of them yet (`36e8:000f(q+C3 & mask)`), q ≠ player, q is in the player's flight, `quiet ==
0` and `dist2(player, q) < 10000`: radio report `1815:06d0(enemy ? 1 : (o's type is a bomber ? 2 : 3),
contact_report(player, o), 0)`; then `q+C3 |= mask`; if enemy: `alert_flight(q)` (`1142:12f5`).

`583c:0749 can_see(p, t)` (used when p is attacked or checks a threat): `r = P(p)+04`; if
`glare_blocks(p, t.pos)` → 0; if `in_blind_spot(body_angles(t, p, p+20), p)` → 0; if `p+D7 != 0` and
`(u16)(p+D1 + 2000h) < 4000h` (target within ±45° of the nose): `r = r·(d = p+D3 < 8000 ? (400h −
P(p)+1E)·200 : 400) >> 10` — i.e. `p+D3 < 8000`: `r = (r·(400h − P+1E) >> 10)·200 >> 10`, else
`r = r·400 >> 10`; returns `(rng & 3FFh) < r` (**RNG**).

### 6.4 `583c:09de ai_spot_reaction(p, t)` — verified

```
w = my_wingman(p); cur = p+D7; seen = 0
if p+43 & 2: return 1
if DAT(p)+38 != 0 (not a fighter) and !glare_blocks(p, t.pos):
    if p == player: radio_bandit_call(t, 0); seen = 1
if cur == 0 and t's bit in p+C3: seen = 1
elif p+D7 == t: seen = 1
elif w and dist2(w, p) < 10000:
    if w+D7 == t or can_see(w, t): if p == player: radio_bandit_call(t, w); seen = 1
if !seen and can_see(p, t): seen = 1
if seen: p+C3 |= bit(t); if w: w+C3 |= bit(t); alert_flight(w)
return seen
```

### 6.5 `583c:0887 radio_bandit_call(t, by)` — likely

`rel = heading(t from player) − player.heading`; only when `(u16)(rel + 5500h) > A9FFh` (outside
±… of the nose, i.e. behind the 3-o'clock/9-o'clock line). Counts the attackers `a` (t itself, and
planes with `+D7 == player`, `+D3 < 10000` and their bearing within the same window) and how many of
them have `+42 & 20h` (`b`). Message: `by != 0` → id 1Ch (wingman calls it, count 1); else `b == 0 or
a < 2` → 1Eh, else `player+26 + 1Fh`. Record: `+0 rel`, `+2 dz (i32)`, `+6 t.z`, `+0A t type`, `+0C
count`, `+16 by or player`; `1815:06e7(id, rec, 0)`.

### 6.6 `583c:1992 spotting_update()` — verified

```
if !DS:47EA: DS:47EA = 1; elements_build_all()
else:
    if timer_dec(&DS:47E6) == 0: DS:47E6 = 700; elements_rebuild(flight slot DS:4765 + DS:47E8, 0);
                                  DS:47E8−− (wraps to DS:4763 − 1)       // one flight re-grouped per 700 dt
    while DS:47EE < DS:4086: DS:47EE += 80h; forget_far(DS:475B[DS:47EC]); DS:47EC−− (wraps)
for each used element: element_scan(e)
```

## 7. `1284` combat and gunnery, `0ac2` aiming

### 7.1 Aim record (`0ac2:000e aim_solution(p, t)`, static `DS:5682`, cached at `Plane+CB`)

| Off | DS | Plane | Meaning |
|---|---|---|---|
| +0 | 5682 | +CB | gun selection: 0 fixed forward guns, k ≥ 1 turret k (counted after the fixed groups), FFFFh none |
| +2 | 5684 | +CD | i8 azimuth error (80h = none) |
| +3 | 5685 | +CE | i8 elevation error (80h = none) |
| +4 | 5686 | +CF | pitch to the lead point − own pitch |
| +6 | 5688 | +D1 | heading to the lead point − own heading |
| +8 | 568A | +D3 | i32 range |

`0ac2:000e aim_solution(p, t)` — likely (Ghidra structure checked against the call graph):
```
gl = p+5E (.GL image: +0 n, +2 flags, 20-byte records from +4); st = p+60 (12-byte gun states)
fixed = ((flags & 2800h) != 0) + ((flags & 0500h) != 0); first_fixed = fixed; turret = −fixed
in_range = 0
for i in 0 .. n−1 (rec = gl+4+20i, s = st+12i):
    turret++; is_turret = (fixed == 0)
    use = is_turret or (fixed == first_fixed and p != player)   // AI aims with fixed group A only;
    if !is_turret: fixed−−                                      // the player never gets fixed-gun aim
    if !use: continue
    loaded = is_turret ? s.rounds (+0) : !(p+1B & 80h)
    if !loaded: continue
    pos = p.pos; M = matrix(p); if is_turret: pos += M·rec.xyz (+6)   (mat_vec, ladd_v)
    d = dist3(pos, t.pos); if d >= 15000: continue
    v = gun_type_speed(rec) (0769:0002); in_range = 1
    lead = t.pos + (satdiv((i16)d·t.v70[k], v) for k = x, y, z)    // t's world velocity per frame
    ba = body_angles(lead, pos, p+20) (583c:0649)
    h = angles_to(la, lead, pos); DS:568A = h; DS:5686 = la.pitch − p.pitch; DS:5688 = la.heading − p.heading
    DS:5682 = is_turret ? turret : 0
    rel = angles_to(t.pos + t.v70, pos + p.v70) − p.angles → p+FD = rel.pitch, p+FB = rel.heading
    e = (angles_to(t.pos, pos) − la) >> 4 (vsar 4)
    DS:5684 = (u16)(e.pitch + 7Eh) < 0FCh ? (i8)e.pitch : 80h; DS:5685 likewise with e.heading
    cone = {rec+0C − rec+10, rec+0C + rec+10, rec+0E − rec+12, rec+0E + rec+12}
    if in_cone(ba, cone): return &DS:5682
if !in_range:
    DS:568A = dist2(p, t); DS:5686 = bearing32(p.z − t.z, DS:568A) − p.pitch
    DS:5688 = bearing32(t.x − p.x, t.y − p.y) − p.heading; DS:5684 = DS:5685 = 80h
    p+FD = DS:5686; p+FB = DS:5688
DS:5682 = FFFFh; return &DS:5682
```
`0ac2:03fa` is an empty module stub.

### 7.2 Functions

| Address | Name | Does | Conf. |
|---|---|---|---|
| 1284:0001 | combat_init | empty | verified |
| 1284:0006 | ai_was_hit(p) | planes: `if p+FF == 0: p+FF = 2000`; `c = p+F2++`; if `P(p)+50 <= c`: `p+44 |= 2`, `p+48 |= 2` (break off) | verified |
| 1284:004d | on_tail(p, t, int ang[3]) | `ang` = `angles_to(t, p)`; `d = dist3(p, t)`: true when `d < 32000`, `(u16)(d − 300) < 1A2Ch` (300 ≤ d < 7000), `(u16)(ang.pitch − p.pitch + 0AF0h) < 15E0h`, `(u16)(ang.heading − p.heading + 4000) < 8000`, and the same two tests against **t's** pitch and heading (p is behind t, both pointing the same way) | verified |
| 1284:00f4 | nearest_in_list(Vec *pos, int side, i32 *d) | over the list `side ? DS:5CD0 (count DS:5CD8) : DS:5CCC (count DS:5CD4)` (the planes hostile to that side): nearest not down by `dist2`; `*d` = its distance (7FFFFFFFh when none) | verified |
| 1284:0184 | nearest_enemy(p, i32 *d) | `nearest_in_list(&p.pos, p+26, d)` | verified |
| 1284:01a3 | player_threat_update(pl) | `e = nearest_enemy(pl, &d)`; if `e` and `d < 20000`: `set = 0`; if `turret_count(pl) == 0` and `is_pure_fighter(pl)`: `pl+D7 = e`, `set = 1`, and if `can_dogfight(e, pl)`: `alert_raise(e, 3, pl)`. `a = angles_to(e, pl)`; if `on_tail(pl, e, a)`: `alert_victim(pl, e)` (`0619:0472`) and, if `pl+44 & 1`, `e+43 |= 2`, `e+47 |= 2`; else if `set`: `alert_raise(e, 1, pl)` | verified |
| 1284:0271 | shot_quality(aim, int base, int thr) | `e = ldist2v(|aim.az|, |aim.el|)` (277a:3c36); if `e < 100h` and `aim.range < 6000`: `v = base − 4e − (aim.range >> 4)`; `v < thr` → 0; `(rng & FFh) < v` → 1 (a real shot); else 2 (a **harmless** spray, see 1284:0353); else 0 (**RNG**) | verified |
| 1284:02fb | gun_solution(p) | once per frame (`p+1A & 10h` clear): `old = p+CB`; `p+CB..+D6 = aim_solution(p, p+D7)`; `p+1A |= 10h`; if the selection changed: `p+101 = 0`, `p+1F |= 20h`; returns `&p+CB` | verified |
| 1284:0353 | ai_fire(p, sel, int ang[3], i32 range, int spray) | `p+42 |= 20h`, `p+46 |= 20h` (firing); fire source `{owner p, 1, spray ? 0 : 50}` — **the third word becomes the bullets' `+2A`, and bullets with `+2A == 0` never test for hits (`0769:0637`): spray bursts cannot hit**. `sel == 0`: `r = (rng & 3FFh) > P+08`; trigger = `(spray == r) ? 3 : 1` (both groups or group A). Turret: trigger = `sel + 3`; if `p+1F & 20h`: `p+101 != 0` → return; else `p+101 = (rng & 3FFh) + 5DCh`, `p+1F &= ~20h`. `gun_fire(trigger, p, ang, &src)` (`0769:009a`); if it returns ≠ 0, `trigger < 4` and the fixed guns are empty (`!0deb:144e`): `p+1B |= 80h` (**RNG**) | verified |
| 1284:041c | turret_count(p) | `.GL flags & FFh` | verified |
| 1284:0435 | all_gunnery | §7.3 | likely |
| 1284:078b | combat_end | empty | verified |

### 7.3 `1284:0435 all_gunnery()` — likely (loop structure from the disassembly)

```
if DS:477C == 5: return                                   // training
for each plane p (DS:475B[0..DS:4776)):
    p+1A &= ~10h
    if (p == player and turret_count(p) == 0) or plane_is_down(p) or (t = p+D7) == 0: continue
    aim = gun_solution(p)
    if timer_dec(&p+101) == 0 and !(p+1F & 20h): p+101 = (rng & 0FFFh) + 5000; p+1F |= 20h   (RNG)
    if aim.sel >= 8000h or aim.el == 80h: continue
    P = pilot(p)
    if aim.sel == 0: base = P+08; thr = P+12; if p+43 & 4: base = base·600 >> 10
                     if t == player and glare_blocks(t, &player.pos): base = base·500 >> 10
                     (quirk: the glare test is made from the target's own position, d = 0, so it
                      never fires)
    else: b = DAT(p)+38 == 3; base = DS:1646[b] ({150, 300}); thr = DS:164A[b] ({−500, −300})
          if t == player and DS:42D2 == 0: base −= 100; thr −= 100
    q = shot_quality(aim, base, thr); if q == 0: continue
    ang = {aim.dpitch, 0, aim.dhead}; spray = 0
    if q == 2: a = rng & 7Fh; b = rng & 7Fh                                          (RNG)
               ang.pitch += aim.dpitch >= 0 ? −a : a; ang.heading += aim.dhead >= 0 ? −b : b; spray = 1
    ang += p.angles (vadd with p+10)
    t+43 |= 2; t+47 |= 2                                                             // t is under fire
    if timer_dec(&DS:5820) == 0 and t == player and DS:42D1 == 0:
        DS:5820 = 6000; message 1614:024e(0ab0:000b(1, 46h, 1, 0, 0))                 // "taking fire"
    if !is_pure_fighter(p) or fixed_guns_loaded(p) (0deb:144e):
        ai_fire(p, aim.sel, ang, aim.range, spray)
        if p == player and !(player+1E & 20h) and station_first(&player+5E) == 0:
            player+1E |= 20h; message 1614:024e(0ab0:000b(1, 39h, 3, 0ab0:000b(7, 27h)))
        if is_pure_fighter(p) and !fixed_guns_loaded(p) and p+34 == player+34 and plane_in_formation(player):
            radio 53h with p (1815:06e7)                                             // "out of ammo"
```

## 8. Tactic states `0619`, `1027`, `1133`

`0619` (tactics against fighters, pairs) and `1027` (energy tactics); both use the tactic-set
records `DS:12B6 + 6k` = {x, y, z} offsets for k = 0..3: {0, −3000, 5000}, {12000, 3000, 4000},
{10000, 2000, 2000}, {0, −8000, 3500}; `DS:12AC[k]` = break-off ranges {1500, 2000, 2000, 2000};
`DS:12CE` = {0, 18000, 3000}; `DS:1552[m]` = pitch per climb mode {−6000, −4000, −2000, 0, 800}.
Pilot words: `+10` cruise throttle, `+14` energy-fight chance, `+20` manoeuvre choice, `+28`
preferred tactic k, `+2A` head-on bomber attack allowed, `+42` aerobatics chance.

| Address | Name | Does | Conf. |
|---|---|---|---|
| 0619:000c | other_in_front(p) | t = p+D7; among the other alive members m of t's flight: `h = angles_to(o, m, p)`, `o −= p.angles`; `(u16)(o.heading + 1000h) < 2000h`, `(u16)(o.pitch + 1000h) < 2000h` and `h < 8000` → remember m (the **last** such member; the 8000 limit is never tightened) | verified |
| 0619:00ce | target_vulnerable(t) | `t` in 1769h (defending), or its state has no flag 10h and `(u16)(t+8E + 32h) < 100` (yaw rate within ±50: flying straight) | verified |
| 0619:00fc | tactic_choose(p) | `P = pilot`; `k = P+28`; `t = p+D7`; `!target_vulnerable(t)` → `tactic_energy(p, t)` (`1027:0126`). If `P+2A`: `o = angles_to(t, p) − p.angles`; if `p.z − t.z > 2500`, `(u16)(o.heading + 2000h) < 4000h`, `(u16)(o.pitch + 16000) < 16000` and `(u16)(p.heading − t.heading + 7000h) > 0DFFFh` (head-on, target below): `k = 4`. `k == 4` → state 12F2h; else state 1306h with `scratch[0] = k` | verified |
| 0619:01dc | st_bracket_steer (1306h) | `s = scratch`; `t = p+D7`; `h = target_heading(t)` (`12fd:0955`); `cloud_blocks_segment(p, t)` → return 1; `!target_vulnerable(t)` → `tactic_energy(p, t)`; else `pt = point_ahead(t.pos, h − 8000h, 12000)` (12000 behind t), `pt.z += DS:12BA[3·s[0]]` (the k record's z), `steer_to_point(p, pt)`, throttle = cruise; if `dist2(pt, p) < 5000` and `pt.z − p.z < 2500`: state 12DEh, `scratch[0] = s[0]`; return 0 | likely |
| 0619:0304 | st_pair_pursue_steer (12DEh) | scratch {k, side, timer}; `off = DS:12B6[k]` (x, y, z); `h = target_heading(t)`; cloud → 1; `!target_vulnerable(t)` → `tactic_energy`; `dh = p.heading − h`; if `side == 0`: `v = −(p+D1)`; if `(u16)(v + 4000h) >= 8000h`: `v = dh`; `side = (v < 0) + 1`; if `(u16)(p+D1 + 1000) >= 2000`: `timer = 0`. If `timer_dec(&timer) != 0`: `off.y −= 4000`. `side == 1`: `off.x = −off.x`. `vrot_z(off, h)`; `steer_intercept(p, t, off, 1, 1, out)` (`4bf9:07a1`, `0x10001` = two flags); throttle = cruise; if the timer is 0 and `out.range < 1000`: state 131Ah, `scratch[0] = k` | verified |
| 0619:0472 | alert_victim(p, t) | `p+D3 < 7000` and `p+F9 == 0`: `alert_raise(t, 6, p)`; `p+F9 = 2500` | verified |
| 0619:04a2 | st_pair_attack_steer (131Ah) | scratch {k, phase}; cloud → 1; `p+C1 |= 8`; `steer_lead(p, t)` (`12fd:0086`); `alert_victim(p, t)`; throttle = cruise; phase 0: `(u16)(p+D1 + 2000) < 4000` → phase 1. Else if `!(p+44 & 2)`: when `(u16)(p+D1 + 2000h) >= 4000h` or `p+D3 < DS:12AC[k]`: wingmen (`p+DD`) return 1; `n = other_in_front(p)`: `n` → `p+D7 = n`; else k 1 or 2 → state 132Eh scratch {k, 3000}; else `tactic_choose(p)`. Else (break-off flag) `tactic_choose(p)` | verified |
| 0619:05a8 | st_pair_break_steer (132Eh) | `steer_roll_to(p, 0)`, `steer_pitch_to(p, 1000h)`; when `timer_dec(&scratch[1]) == 0`: state 12DEh, `scratch[0]` kept | likely |
| 0619:0602 | st_spread_steer (12F2h) | `pt = t.pos`; cloud(p, pt) → 1; `!target_vulnerable` → `tactic_energy`; throttle = cruise; `pt = point_ahead(pt, target_heading(t), 18000)`, `pt.z += 3000`; `steer_to_point(p, pt)`; `p+D3 < 18000` → state 131Ah, `scratch[0] = 4` | verified |
| 0619:06e4 | tactics_register | `59f9:0026` with the list `DS:12D4` (1306h, 12DEh, 131Ah, 12F2h, 132Eh) | verified |
| 1027:0008 | energy_advantage(p, t) | `!is_pure_fighter(t)` → 0; Japanese (`p+26 == 1`) with `DAT(p)+54 == 0` → 1; if `p+DF != 0` → cached `p+1F & 10h`; else `p+DF = 56000`; `r = DAT(t)+59 <= DAT(p)+59` (i8); if `!r` and `(rng & 3FFh) < P+14`: `r = 1` (**RNG**); cache in `p+1F` bit 10h | verified |
| 1027:010b | st_c_enter(p) | state 1588h, `scratch[0] = 4` | verified |
| 1027:0126 | tactic_energy(p, t) | `aim = gun_solution(p)`; `aim.range < 12001`: `(u16)(aim.dhead + 5DCh) < 3000` → `st_b_enter(p)`; `aim.range >= 12001` and `(u16)(aim.dhead + 3000) < 6000` → `st_a_enter(p, t)`; otherwise `st_c_enter(p)` | verified |
| 1027:0188 | fight_choose(p, t) | `p+DD != 0 && is_pure_fighter(t)` → 0; t a fighter: `e = energy_advantage(p, t)`; `!e` → `tactic_energy(p, t)`; return `!e`; else `tactic_choose(p)`, return 1 | verified |
| 1027:01fe | st_a_enter(p, t) | state 1560h; scratch `{i32 p.z − t.z, 1}` | verified |
| 1027:022c | point_ahead(Vec *pt, u16 h, i32 d) | `v = vrot_z((0, 32000, 0), h)`; while `d > 32000`: `pt += v`, `d −= 32000`; `lmove_heading(pt, h, d)` | verified |
| 1027:0286 | elevation_to(a, b) | `bearing32(b.z − a.z, dist2(a, b))` | verified |
| 1027:02b3 | st_b_enter(p) | state 1574h, `scratch[0] = p.heading` | verified |
| 1027:02d3 | st_a_steer (1560h, "lag above") | §8.1 | verified |
| 1027:046b | st_b_steer (1574h, attack pass) | `s = scratch`; cloud(p, t) → 1; `p+C1 |= 8`; throttle `P+10`; `steer_lead(p, t)`; `alert_victim(p, t)`; `d = abs16((p.heading − s[0]) sar 1)`, `pz = abs16(p.pitch)`; if `d + (pz >> 1) > 3000h` or `(u16)(p+D1 + 4000h) > 7FFFh` or `p+D3 < 1000` (pass over): `c = is_pure_fighter(t)`; `p+DD` → return 1; `!c && target_vulnerable(t)` → `tactic_choose(p)`; else if `!energy_advantage(p, t)`: `n = other_in_front(p)`: `n` → `p+D7 = n`, `s[0] = p.heading`; else `st_c_enter(p)`; else state 16C9h and `p+DF = 56000` | verified |
| 1027:05b5 | climb_mode_pick(p) | `(rng & 3FFh) < P+20 ? (i8)DAT+3C : (i8)DAT+3D` (**RNG**) | verified |
| 1027:060b | try_manoeuvre6(p, t) | if `p.z − t.z > −1000` and `(rng & 3FFh) < P+42` (**RNG**) and `manoeuvre_allowed(6, p)`: state 15B0h; return `manoeuvre_start(6, p)`; else 0 | verified |
| 1027:0680 | st_c_steer (1588h, extend) | §8.2 | likely |
| 1027:0822 | st_e_steer (15B0h) | `if manoeuvre_step(p)` (done): `st_a_enter(p, p+D7)` | verified |
| 1027:0845 | st_d_steer (159Ch, zoom) | scratch {i16 timer, i32 best_dz, i16 phase}; `dz = p.z − t.z`; throttle cruise; phase 0: `steer_heading_nolead(p, 0, p+D1 − 8000h)` (turn away), `p+D3 > 50000` → phase 1; phase 1: `steer_heading_nolead(p, 0, p+D1)`, `p+D3 < 30000` → phase 0. `steer_pitch_to(p, DAT+57, 0)` (max climb). If `timer_dec(&timer) == 0` and `dz > −500`: `dz < best_dz` → done, else `best_dz = dz`. Done or `dz > 1200` → `st_a_enter(p, t)` | verified |
| 1027:0956 | tactic_think | `ai_think_target(p)`; `p+DF = 0`; return 1 | verified |
| 1027:0975 | tactic1027_register | `59f9:0026` | verified |
| 1133:0001 | skip_hook | `DS:57CF = 1` | verified |
| 1133:000b, 0013 | identity | return the argument (debug stubs) | verified |
| 1133:001b | park_far_away(Vec *pos) | `pos = (1000000000, 1000000000, 500000000)` | verified |
| 1133:003a | st_hold_act (15F6h) | scratch {phase, timer, next}; phase 0: `if timer−− == 0` (a frame count): `park_far_away(&p.pos)`, `brain_set_state(next, p)`; phase ≠ 0: `timer_dec(&timer) == 0` → phase 0, timer 2; then `plane_fly(p)` | verified |
| 1133:00a8 | st_hold_enter(p, next) | state 15F6h, scratch {1, 2300h, next} | verified |
| 1133:00ce | is_nonzero(x) | `x != 0` (steer of 160Ah: returns ≠ 0 → think; its think is null: the state just waits) | verified |
| 1133:00e0 | hold_register | `59f9:0026` | verified |

### 8.1 `1027:02d3 st_a_steer(p)` (1560h) — verified

```
t = p+D7; s = scratch (i32 dz0, flag); aim = p+CB
if cloud_blocks_segment(&p.pos, <uninitialised local>): return 1    // quirk: the second point is an
                                                                    // uninitialised stack buffer;
                                                                    // PORT: use t.pos
a = t.heading − (aim.dhead + p.heading) + 8000h; k = abs16(a) >> 7
pt = t.pos; pt.z += s.dz0
r = lmul(aim.range, k) >> 8; point_ahead(pt, t.heading, r + 1000)
rel = steer_toward(p, t, pt) (12fd:002e: low = rel pitch, high = rel heading)
p+B2 = P+10
q = lmul(aim.range >> 1, 100h − k) >> 8
e = bearing32(p.z − t.z, aim.range − q)
if aim.range < 12000 or ((u16)(e + 0C00h) >= 1800h and (u16)(rel.heading + 1000h) < 2000h):
    st_b_enter(p)
return 0
```

### 8.2 `1027:0680 st_c_steer(p)` (1588h) — likely

```
t = p+D7; s = scratch (mode, armed, timer); d = dist2(p, t)
if cloud_blocks_segment(p, t): return 1
(src, lvl) = alert_get(p); fast = (lvl == 3 and p+94 − src+94 < 120)
steer_roll_to(p, 0); p+B2 = P+10
if too_low(p, 4000) (12fd:035c) and p+6E < 0: p+AE = 100h else steer_pitch_to(p, DS:1552[s.mode], 0)
if !s.armed: if fast: s.mode = climb_mode_pick(p); s.armed = 1; s.timer = 5000
elif timer_dec(&s.timer) == 0: if !fast: s.mode = 4; s.armed = 0;  s.timer = 5000
if s.mode < 3 and too_low(p, 4000): s.mode = 3
if d > 15000: alert_raise(t, 2, p)
    if d > 20000 and !try_manoeuvre6(p, t): state 159Ch, scratch {20000, i32 p.z − t.z}
return 0
```
## 9. `12fd` — dog-fight states

Plane fields: `+D9`, `+DB` attacker slots on a target (who is diving on it / who is working it
with `steer_lead_close`); `+DF` i32 energy-decision cache timer (`1027:0008`); `+E7` i32 timer;
`+F9` alert-victim cooldown; `+FF` hit-reaction timer, `+F2` hits counter; `+101` burst timer.
Pilot words used: `+06` extend time (<< 8), `+0C` max bank, `+10` cruise throttle, `+18` chance of
extending instead of manoeuvring, `+20` skill-ish selector (see 12fd:0e28), `+22` pincer allowed,
`+24` head-on preference, `+2C[21]` manoeuvre weights (bytes), `+42` aerobatics chance, `+44`
energy rating, `+46` dog-fight allowed, `+4C`/`+4E` Thach-weave chances (US), `+50` hits before
breaking off. Aircraft `.DAT`: `+38` class (0 fighter, 2 dive bomber, 3 bomber …), `+3A` dive
pitch, `+3C/+3D` climb modes, `+3E[21]` manoeuvre skill thresholds, `+54` Japanese energy flag,
`+57` climb pitch, `+59` i8 energy rating, `+5B` 2 blind-spot cones.

| Address | Name | Does | Conf. |
|---|---|---|---|
| 12fd:0000 | steer_by_angles(p, t, int ang[3]) | `steer_heading_lead(p, t, ang[2])`; `steer_climb(p, t, ang[0], 0)` | verified |
| 12fd:002e | steer_toward(p, t, Vec *pt) | `a = angles_to(pt, p) − p.angles`; `steer_by_angles(p, t, a)`; returns DX:AX = {a.heading, a.pitch} | verified |
| 12fd:0086 | steer_lead(p, t) | `steer_by_angles(p, t, {p+FD, 0, p+FB})` (the closure direction from `aim_solution`) | verified |
| 12fd:00b5 | pursue_geometry(p, t) | §9.1 → bits 1 in position, 2 on the tail, 4 nose-on, 8 side | verified |
| 12fd:02b8 | slot1_taken(p, t) | `q = t+D9`: q alive, ≠ p and its state has flag 8 → 1; q down or not flag 8 → `t+D9 = 0`, 0 | verified |
| 12fd:030a | slot2_taken(p, t) | same with `t+DB` | verified |
| 12fd:035c | too_low(p, int margin) | `g = (i32)p+B8` (ground height); `g > 2000` → `g += 3000`; `p.z < g + margin` | verified |
| 12fd:03a6 | st_pullup_steer (186Dh) | `steer_pitch_to(p, 2000)`, `steer_roll_to(p, 0)`, throttle = cruise; returns `!too_low(p, 1500)` (think again when safe) | verified |
| 12fd:03e8 | ground_avoid_check(p) | state without flag 100h, `!(p+45 & 40h)` and `too_low(p, 1200)` → state 186Dh, return 1 (called by `brain_threat_check`; the old name "evade check" was wrong) | verified |
| 12fd:042a | st_climb_steer (16B5h) | throttle = cruise; `p+D7` → `fight_choose(p, p+D7)`; `steer_roll_to(p, −1000)`; `steer_pitch_to(p, 4000, 10)`; return 0 | verified |
| 12fd:0479 | head_on_window(p) | `t = p+D7`: `(u16)(p.heading − t.heading + 0AEE0h) < 24000` (opposite headings), `(u16)(p+D1 + 7000) < 14000`, `(u16)(p+CF + 4000) < 8000`, `p+D3 > 4500` | verified |
| 12fd:04ca | st_pursue_steer (16C9h) | §9.2 | verified |
| 12fd:06c2 | steer_lead_close(p, t, int ang[3]) | `p+C1 |= 8`; `t+DB = p`; `steer_heading_lead(p, t, ang[2])`; `steer_climb(p, t, ang[0], 0)`; `a = ang + p.angles`; `r = p+D3`; `steer_speed_match(p, t, (i16)r, a.heading, (i16)(r + 2500 − dist2(p, t)))` | verified |
| 12fd:076b | st_guns_steer (16F1h) | cloud → 1; `a = {p+CF, 0, p+D1}`; `steer_lead_close(p, t, a)`; `a += p.angles`; `on_tail(p, t, a)` → `alert_victim(p, t)`, else state 16C9h | verified |
| 12fd:07f7 | st_manoeuvre_steer (1741h) | `done = manoeuvre_step(p)`; `alert_raise(p, 11)`, `alert_raise(p, 10)` (blocks the paired radio levels); return `done != 0` (think when done) | verified |
| 12fd:082b | st_headon_pass(p, side) | `r = P+0C >> 1`; cloud → 1; `side == 0` → `r = −r`; throttle = cruise − 20; `steer_pitch_to(p, 0)`; `steer_roll_to(p, r, 0)`; return 0 | verified |
| 12fd:08a7 / 08b8 | st_headon_a/b (1719h / 172Dh) | `st_headon_pass(p, 1)` / `(p, 0)` | verified |
| 12fd:08c9 | extend_enter(p, _) | state 17A5h; brain timer `+4C = (i32)(P+06 << 8)` | verified |
| 12fd:090b | st_manoeuvre_then_extend (1755h) | when `st_manoeuvre_steer` reports done: `extend_enter(p, 1)`; return 0 | verified |
| 12fd:092d | st_defend_think (1769h) | state `p+DD ? 0430h : 041Ch` (back to formation / waypoints); return 1 | verified |
| 12fd:0955 | target_heading(t) | `t` in 1769h → its saved heading `scratch[1]`; else `t.heading` | verified |
| 12fd:0973 | weave(p, int h0, int side) | `o = side ? 3000 : −3000`; `d = h0 − p.heading`; `steer_heading_nolead(p, 0, o + d)`; `steer_pitch_to(p, 0)`; if `(u16)(d + 400) >= 800` and `(d < 0) == side`: `side = !side`; returns side | verified |
| 12fd:09e2 | st_defend_steer (1769h) | scratch {started, h0, side}; first frame: `started = 1`, `h0 = p.heading`; if `t+D7 == p`, `p+D3 < 9000` and `(u16)(t+D1 + 4000h) < 8000h` (t points at p): `side = weave(p, h0, side)`, return 0; else return 1 | verified |
| 12fd:0a44 | wingmen_ready(lead, Plane *out[]) | members m with `m+DD == lead`: AI → ready when in state 1809h; the player → a dry run of `fly_formation_slot(player, slot_offset(player, lead), lead, 3800h)` with the player's velocity words `+6A..+6F` and controls `+AC..+BA` saved and restored (and `lead+42/+46 |= 10h`), ready when the result has bits 7; returns the count | verified |
| 12fd:0b79 | pincer(lead, t) | `P(lead)+22 == 0` → 0; `wingmen_ready(lead, w) != 2` → 0; `!manoeuvre_allowed(0, lead)` → 0; if `w[0]+0 & 7` (class bits: always for planes) swap w[0], w[1]; `manoeuvre_allowed(11, w[0])` and `(12, w[1])` else 0; `d = (i16)dist3(lead, t)`; `d <= 200` → 0; `d >= 4000` → 1; else: if `w[0]` or `w[1]` is the player: radio 38h with `{w[0] == player ? 16000 : −16000}`; `manoeuvre_enter(0, lead)`, `(11, w[0])`, `(12, w[1])` (all DX 0); return 1 | verified |
| 12fd:0caa | can_dogfight(t, p) | `p+D7 == t`, `p+D3 < 9000`, `(u16)(p+D1 + 2000h) < 4000h` and `(u16)(1660:0110(p, t) + 6000h) > 0BFFFh` | verified |
| 12fd:0cf3 | thach_call(p, t) | if `can_dogfight(p, t)` (t is on p's tail), p not Japanese, `w = 1660:0065(p, 0, &w)` (a flight mate that can help), `dist3(p, w) < 8000` and (`w == player` or w's state has no flag 20h): `a = (rng & 3FFh) < P+4C`; if `a` or `(rng & 3FFh) < P+4E`: `a` → `weave_enter(p, w)`; `w == player` → radio 59h (p calls for help) else `cross_enter(w, p, t)`; return `a` (**RNG**) | verified |
| 12fd:0e0d | high_enough_4000(BX = p) | `!too_low(p, 4000)` (candidate 20's extra condition) | verified |
| 12fd:0e28 | st_dogfight_steer (177Dh) | §9.3 | verified |
| 12fd:110a | weave_enter(p, mate) | state 1845h, scratch {mate, i32 50000} | verified |
| 12fd:112e | cross_enter(w, p, t) | w: state 1831h, scratch {p, i32 50000}; `w+D7 = t` | verified |
| 12fd:115d | st_weave_steer (1845h) | scratch {mate, i32 timer, side}; cloud → 1; throttle = cruise; `side = weave(p, bearing_between(p, mate), side)`; `done = (mate == player) ? timer_expired32(&timer) : (mate not in 1831h)`; if `!done`, `t+D7 == p` and `(u16)(t+D1 + 3000h) < 6000h`: return 0; else `p+DF = 0`, return 1 | verified |
| 12fd:1225 | st_cross_steer (1831h) | §9.4 | verified |
| 12fd:1438 | st_level_steer (1791h) | throttle cruise; `steer_level(p)`; if the target's state is none of 16C9h, 1574h, 17CDh, 16F1h, 1831h and the brain timer > 3000: timer = 3000 | verified |
| 12fd:1491 | st_extend_steer (17A5h) | = `st_level_steer` | verified |
| 12fd:14a0 | dive_geometry(p) | `t = p+D7`; save `t.pos` and `p+CF`; `dz = p.z − t.z`; `slow = dz < 5000`; `off = vrot_z((0, −2500, max(dz, 5000)), t.heading)`; `t.pos += off` (temporarily); `p+CF = 0`; `r = pursue_geometry(p, t)`; `slow` → throttle = cruise; restore `p+CF` and `t.pos`; `!slot2_taken(p, t)` → state 16C9h; returns r | verified |
| 12fd:15a3 | st_dive_steer (16DDh) | `r = dive_geometry(p)`; `r & 1`: `slot1_taken(p, t)` → state 16B5h and return `st_climb_steer(p)`; else `t+D9 = p`; return 0 | verified |
| 12fd:15f4 | st_recover_steer (17B9h) | `low = too_low(p, 4000)`; throttle = cruise; if `low` or the brain timer is 0: `!low && (rng & 1) == 0` → state 17E1h; else weights `w[j]` for the candidate manoeuvres `DS:165A` = {7, 0, 0}: `w[j] = P+2C[i]` for the first i == `DS:165A[j]` with `DAT+3E[i] != 0` and `manoeuvre_allowed(i, p)`; `m = manoeuvre_pick(3, w, DS:165A)`; `m ≥ 0` → `manoeuvre_enter(m, p, 1)`, else state 17B9h (restart). Always: `steer_roll_to(p, 0)`, `steer_pitch_to(p, DAT+3A, 0)` (**RNG**) | verified |
| 12fd:1753 | st_headon_steer (17CDh) | cloud → 1; `p+C1 |= 8`; throttle cruise; `steer_lead(p, t)`; `head_on_window(p)` → `alert_victim(p, t)`, else state 16C9h | verified |
| 12fd:17c4 | st_dive2_steer (1705h) | `r = dive_geometry(p)`; `t+D9 = p`; `!(r & 2)` → state 16DDh | verified |
| 12fd:17fc | st_level2_steer (17E1h) | `steer_level(p)`; throttle = cruise − 20 | verified |
| 12fd:181f | st_regroup_steer (17F5h) | §9.5 | verified |
| 12fd:1a1e | st_cover_steer (1809h) | `w = p+DD`; `off = slot_offset(p, w)`; `p+42/+46 |= 10h`; `r = fly_formation_slot(p, off, w, 3800h, 1388h)`; `(r & 7) != 7` → state 181Dh | verified |
| 12fd:1a78 | slot_offset(p, lead, Vec *out) | `out = DS:164E` (−1500, −1500, 0); unless the flight is a Japanese three-plane shotai (`n == 3 && side == 1`): hysteresis on `p+1A` bit 80h — set when `lead.roll < −3000`, cleared when `> 3000`; bit set → `out.x = −out.x` (slide to the outside of the turn) | verified |
| 12fd:1ad8 | st_rejoin_steer (181Dh) | as 1a1e; `(r & 7) == 7` → state 1809h | verified |
| 12fd:1b31 | bank_enter(p, dir) | state 1859h, `scratch[0] = dir` | verified |
| 12fd:1b4d | st_bank_steer (1859h) | `r = P+0C`, negated when `scratch[0]`; `steer_pitch_to(p, 0)`, `steer_roll_to(p, r, 0)`; when the brain timer is 0: `p+43 |= 1`, `p+47 |= 1` (forced reaction next time) | verified |
| 12fd:1bad | dogfight_register | `59f9:0026` | verified |

### 9.1 `12fd:00b5 pursue_geometry(p, t)` — verified

```
ret = 0; tail = 0; aim = p+CB
los = aim.dhead + p.heading + 8000h            // line of sight reversed (from the lead point to p)
a = abs16(t.heading − los)                     // target aspect
if a < 2000h: off = (aim.dhead < 0 ? 8000 : −8000, 0, 0); ret |= 4       // nose-on: aim abeam
elif a < 25000: off = (0, −500, 0); ret |= 8
else: off = (0, −500, 0); tail = 1
save_z = t.z (i32); save_vz = t+74; save_pos = t.pos
o = off.x ? vrot_z(off, t.heading) : mat_vec(off, matrix(t))
steer_intercept(p, t, o, 0, out)
if !tail: t.z = save_z; t+74 = save_vz; p+B2 = P+10
else:
    tp = save_pos + o; ret = 1; d = dist2(p, tp)
    if d > 10000: p+B2 = P+10
    else:
        if (u16)((i16)d + 500 − 400) < 17D4h and on_tail(p, t, {aim.dpitch + p.pitch, ?, aim.dhead + p.heading}): ret |= 2
        steer_speed_match(p, t, (i16)d, p.heading + out.bearing (+0A), 2000)
return ret
```

### 9.2 `12fd:04ca st_pursue_steer(p)` (16C9h) — verified

```
s = scratch; t = p+D7
if cloud_blocks_segment(p, t): return 1
if !head_on_window(p): s[0] = 0
elif s[0] == 0:
    s[0] = 1
    if ((rng & 3FFh) < P+24) == ((rng & 3FFh) < P+20):                        (RNG ×2)
        if !fight_choose(p, t): state 17CDh
        return 0
r = pursue_geometry(p, t)
if (r & 1) and can_dogfight(t, p): p+C1 |= 8; alert_raise(t, 3, p)
if fight_choose(p, t): return 0
if r & 4:
    if (rng & 3FFh) < P+42 and (u16)(p.heading − t.heading + 8FA0h) < 8000
       and ((u16)(p+D1 + 28000) >= 56000 or p+D3 < 2000) and (u16)(p.roll + 3000) < 6000:
        manoeuvre_enter(p+D3 > 500 ? 3 : 6, p, 0)                              (RNG)
    p+B2 = P+10 − 5; if p+44 & 2: state 177Dh
elif r & 8: p+B2 = P+10 − 5; if p+44 & 2: state 177Dh
elif r & 2: state 16F1h; alert_victim(p, t)
return 0
```

### 9.3 `12fd:0e28 st_dogfight_steer(p)` (177Dh) — verified (control flow; the candidate table walk read in the disassembly)

```
t = p+D7; lead = p+DD ? p+DD : p; A = DAT(p)+3E (21 thresholds); aim = p+CB
if s[0] == 0: s[0] = 1; if (rng & 3FFh) < P+18: extend_enter(p, 0); return 0          (RNG)
if pincer(lead, t): return 0
if thach_call(p, t): return 0
for i < 21: w[i] = A[i] ? P+2C[i] : 0; id[i] = i
faster = !(t+6C − p+6C < 201 and p.z <= t.z + 600)
if faster and (rng & 3FFh) < P+20: w[13] = w[14] = w[15] = w[16] = w[17] = w[20] = 0      (RNG)
lower = p.z < t.z − 600 or aim.range > 4000
if lower and (rng & 3FFh) < P+20: w[7] = w[11] = w[12] = 0                                  (RNG)
if ((rng & 3FFh) < P+20) == (aim.dhead < 0): w[19] += w[18]; w[18] = 0                      (RNG)
else w[18] += w[19]; w[19] = 0
lim = min(P+20·99 >> 10, 99); for i < 20: if (i8)A[i] <= lim: w[i] = 0
for i < 21 with w[i]: ok = i < 20 ? manoeuvre_allowed(i, p) : DS:1661[i − 20](p) (12fd:0e0d)
                     if !ok: w[i] = 0
m = manoeuvre_pick(21, w, id)                                                                (RNG)
if m < 0: return st_defend_steer(p)
if m < 20: manoeuvre_enter(m, p, 1)
elif DS:160F[4m] (i16 min altitude, 5000 for m = 20) < p.z: brain_set_state(DS:160D[4m] (17B9h), p)
return 0
```

### 9.4 `12fd:1225 st_cross_steer(p)` (1831h) — verified

```
off = DS:1654 (0, −500, 0); s = {mate, i32 timer}; t = p+D7; aim = p+CB
if cloud_blocks_segment(p, t): return 1
a = {aim.dpitch + p.pitch, ?, aim.dhead + p.heading}
end = (mate == player) ? (timer_expired32(&s.timer) == 0) : (mate not in 1845h)
      // quirk: with the player as the mate the state ends while the timer still runs (at once)
if end: p+DF = 0; return 1
if on_tail(p, t, a): steer_lead_close(p, t, {aim.dpitch, ?, aim.dhead}); alert_victim(p, t)
                     t+43 |= 4; t+47 |= 4; return 0
dt_ = dist2(t, mate); dp = dist2(p, mate)
if dp < dt_ + 500:                                       // not yet across: turn away from the mate
    b = bearing_between(mate, p) − p.heading
    steer_heading_nolead(p, 0, b + (b < 0 ? 4000h : C000h))
    steer_altitude(p, p.z − mate.z, 0)
else:
    d = dist2(p, t); off.y += 5000; o = vrot_z(off, t.heading)
    steer_intercept(p, t, o, 0x10000 (flags), out)
    if d < 12000: steer_speed_match(p, t, (i16)d, out+0A + p.heading, 5000) else p+B2 = cruise
return 0
```

### 9.5 `12fd:181f st_regroup_steer(p)` (17F5h) — verified

```
s = {timer, target}; p+B2 = cruise
if timer_dec(&s.timer) == 0:
    n = flight_alive_members(f, m); s.timer = 10000; me_lead = (p == m[0]); all_in = 1; fighting = 0
    if n < 2: st_next_task(p) (4edf:0e58); return 0
    fighting = any m[i] ≠ p with m[i]+1C & 1
    if fighting or me_lead:
        mind = 10000000h; maxd = 0; best = 0
        for q in m, q ≠ p: joining = q not in 0430h; d = dist2(q, p); if joining: all_in = 0
            if fighting: if q+1C & 1 and d < mind: mind = d; best = q
            elif d > maxd and joining: maxd = d; best = q
    else best = m[0]
    if me_lead and all_in: st_next_task(p); return 0
    s.target = best
    if !fighting and !me_lead and dist2(p, best) < 8000: state 0430h; return 0
steer_to_point(p, &s.target.pos)
return 0
```

## 10. `1ad2` — manoeuvre library

`SDEF.DAT` (280 bytes, `1ad2:0003` → `DS:5CEC`) = 20 entry conditions of 14 bytes: `+0 s0, +2 s1`
(speed `Plane+6C` strictly between), `+4 p0, +6 p1` (pitch), `+8 r0, +A r1` (roll), `+C` min
altitude. The manoeuvre table `DS:193C` has 20 entries of 6 bytes {i16 coordinated, far fn}: the
function is called every frame by `manoeuvre_step` and returns 1 when finished; `coordinated ≠ 0`
sets `Plane+C1 |= 1` (fixed turn coordination, `plane_fly`). Manoeuvre scratch (the brain scratch
of state 1741h/1755h): `+0` i8 manoeuvre (FFh none), `+1` stage bits, `+2` i16 timer, `+4` start
heading.

| m | fn | coord | Manoeuvre (all set throttle = cruise unless noted) |
|---|---|---|---|
| 0 | 1ad2:00b1 | 0 | split-S: stage 0 roll level until `pitch > 0` and `|roll| >= 16000` (bit 2); stage 1 roll to 8000h until `pitch < 0` and `|roll| < 16000` (bit 4); stage 2 level wings, done when `pitch > −4000`; elevator full up (100h) throughout |
| 1, 2 | 1ad2:01f9 / 020a | 1 | aileron roll left / right (`015b(p, dir)`): aileron ∓100h, elevator 100h; bit 2 when `|roll| >= 28000`; bit 4 when roll changes sign in the rolling direction; done when `(u16)(roll + 0DACh) < 7000` |
| 3 | 1ad2:021b | 0 | half loop / Immelmann: stage 0 elevator by `|roll|` (< 13000: −80h, < 26000: 0, else 100h) and `steer_roll_to(8000h, 1Eh)` until reached; then while `|roll| < 4000h`: roll level, elevator 100h, done when `pitch > −2000`; else roll 8000h, elevator 100h |
| 4, 5 | 1ad2:03b0 / 03c1 | 0 | wing-over (`02cf(p, dir)`, s = ±1): stage 0 `steer_roll_to(s·22000, 30)`; stage 1 elevator 96h and the same roll; stage 2 aileron `−s·0BEh`, elevator 96h until `|roll| < 4000h`; stage 3 `steer_pitch_to(−1000)`, done when `steer_roll_to(0, 1Eh)` |
| 6 | 1ad2:03d2 | 0 | loop: stage 0 elevator 100h, roll level until `pitch > 0` and `|roll| >= 16000`; stage 1 roll 8000h, elevator `(pitch − 2000) >> 5` until `pitch < 3000`; stage 2 `p+C1 |= 10h` (no coordination), `|roll| < 4000h` → `steer_pitch_to(3000)` else elevator `(pitch − 1000) >> 3`; done when `steer_roll_to(0, 1Eh)` |
| 7 | 1ad2:04cb | 0 | zoom climb: roll level, `steer_pitch_to(9000, 10)`; first frame timer = 10000; then until the stall-warning flag (`Plane+AA` bit 2) or the timer runs out keep climbing; then (bit 2) `steer_pitch_to(0, 8)` → done when reached |
| 8 | 1ad2:05df | 1 | barrel roll sequence: `steer_pitch_to(0)`; first frame timer 10; then four heading kicks `056c` with (dir, bit) = (1, 2), (0, 4), (1, 8), (0, 16): each `steer_heading_nolead(p, 0, dir == 1 ? −16000 : 16000)` until its timer runs out, then timer = `((rng & 15) + 20) << 8` (**RNG**); done when `steer_roll_to(0, 8)` |
| 9, 10 | 1ad2:0710 / 0721 | 0 | skid (`0679(p, dir)`): level, rudder ±100h, aileron = yaw rate `+8E >> 1`; timer 6000 |
| 11, 12 | 1ad2:07c2 / 07d3 | 1 | climbing turn (`0732(p, dir)`): `steer_roll_to(±5000)`, `steer_pitch_to(1194h, 20)`; when reached start timer 8000; done at its end |
| 13, 14 | 1ad2:08c6 / 08d7 | 0 | slipping dive (`0814(p, dir)`): unless `recover_if_low`: level wings, rudder ±100h, aileron `+8E >> 1`, `steer_pitch_to(−8000, 20)`; when reached timer 5000; done at its end |
| 15, 16 | 1ad2:096d / 097e | 1 | diving turn (`08e8(p, dir)`): unless `recover_if_low`: `steer_roll_to(±6000)`, `steer_pitch_to(−8000, 20)`; timer 5000 when reached; done at its end |
| 17 | 1ad2:0a3c | 0 | dive at the aircraft's dive pitch: unless `recover_if_low`: roll level, `steer_pitch_to(DAT+3A, 20)`; timer 7000 |
| 18, 19 | 1ad2:0a1a / 0a2b | 1 | max-bank turn (`098f(p, dir)`): `steer_pitch_to(0)`, `steer_roll_to(±P+0C, 0)`; timer 5000; at the end `p+43/+47 |= 1` |

(The dword pushes decode as two words `(value, tolerance)`: `0x1e8000` = (8000h, 30),
`0xa2328` = (9000, 10), `0x141194` = (4500, 20), `0x14e0c0` = (−8000, 20), `0x80000` = (0, 8).)

| Address | Name | Does | Conf. |
|---|---|---|---|
| 1ad2:0003 | sdef_load | `519d:0000(DS:5CEC, 280, 1, "SDEF" DAT)` | verified |
| 1ad2:002e | manoeuvre_allowed(AX = m, BX = p) | conditions of `SDEF[m]` (all strict): `p0 < pitch < p1`, `r0 < roll < r1`, `s0 < +6C < s1`, `(i32)h < p.z` | verified |
| 1ad2:0082 | steer_level(BX = p) | `steer_roll_to(p, 0, 8) & steer_pitch_to(p, 0, 8)` | verified |
| 1ad2:00b1 … 0a2b | the manoeuvre functions above | | likely |
| 1ad2:056c | heading_kick(p, dir, bit) | see m = 8 | verified |
| 1ad2:07e4 | recover_if_low(p) | `too_low(p, 4000)` → state 1791h (level off), returns 1 | verified |
| 1ad2:0acc | manoeuvre_step(BX = p) | `m = scratch[0]`; FFh → return 1; `r = DS:193E[m](p)`; `DS:193C[m] != 0` → `p+C1 |= 1`; done → `scratch[0] = FFh`, `scratch[1] = 0`; returns r | verified |
| 1ad2:0b20 | manoeuvre_start(AX = m, BX = p) | `0 <= m < 20`, the function exists and `manoeuvre_allowed(m, p)`: scratch = {m, 0, timer 0, heading p.heading}; returns 1 | verified |
| 1ad2:0b82 | manoeuvre_enter(AX = m, DX = then_extend, BX = p) | if allowed: state `then_extend ? 1755h : 1741h`, `manoeuvre_start(m, p)`; returns allowed | verified |
| 1ad2:0bcb | manoeuvre_pick(AX = n, DX = i8 w[], BX = i8 id[]) | `T = Σ w`; `T > 0`: `r = rng_range(T)` (`1889:00b4`); walk: `r < w[i]` → return `id[i]`, else `r −= w[i]`; −1 (**RNG**) | verified |
| 1ad2:0c39 | manoeuvres_init | `sdef_load()` | verified |
## 11. `0deb` g_attack.c — ground and ship attack

Attack scratch (20 bytes, states 14A5h–151Dh): `+0` phase, `+2` target kind (1 ship, 0 place),
`+4` target object (ship Plane* / place record), `+6` torpedo side, `+8` timer / pass count,
`+0A` bits (2 = aim jitter chosen), `+0C` far sub-target (entry of the target group list `DS:5146`,
22-byte records whose byte `+12` is the damage 0..FFh; `DS:5142` = 6-byte far back pointers by
group index), `+10/+12` aim jitter x/y. Target places: `place+18` first index in `DS:5146`,
`place+1A` count, `place+1E` bit 4 destroyed. Ships: `+1B & 2` sunk, `+1E` bits 40h/80h land on
the left/right (torpedoes), `+42/+46 |= 8` under attack.

Tables: `DS:148A[side]` = {400, 2000} torpedo drop altitude; `DS:1486[side]` = {95, 135} torpedo
speed limit (×12 vs `Plane+94`); `DS:148E[k]` = {17000, 20000} dive-bomb start altitude and
`DS:1492[k]` = {6000, 9000} release range (k = 1 for places); `DS:1466[low]` = {0, 600};
strafe/rockets `DS:146A[k]` = {−100, −50} aim height, `DS:146E` = {18000, 15000} run-in range,
`DS:1472` = {8000, 8000} rocket range, `DS:1476` = {15000, 8000} gun range, `DS:147A` = {400, 300}
rocket pitch tolerance, `DS:147E` = {500, 1000} gun tolerance, `DS:1482` = {4000, 4000} break
off. `G_ATTACK.DAT`: at 208h a u16 count `DS:578A` of lists `DS:5788[i]` = {u16 n, far entries[n]
of 4 bytes: i8 object type, i8 name string id (group 6), i16 value}; per area 26 bytes at `(area −
1)·26` → `DS:576E[26]` (shape index → list index).

| Address | Name | Does | Conf. |
|---|---|---|---|
| 0deb:000a | release_ordnance(p, Vec *aim) | player: `v = M·(0, 0, 1024)` (`DS:1496`); if `v.z < 0` (inverted) → message (1, 38h) and return; sound 0 at the player if `DS:19F2`. No torpedo (`!torpedo_loaded`): bomb stick = the three stations `p+F3` (kind, count) expanded (`stick[0]` = total), source `{p, aim or 0 (12 bytes), p+6C, spacing = DAT+6D (3 words) with x·85 >> 8 and z −= 25}` → `bomb_release(stick, &p.pos, p+20, &src)`; torpedo: `torp_drop(&p.pos, −25, &p.angles, {p, side == US, p+6C})`. Unless the player with unlimited ammunition: `p+1B &= ~40h`. Player and released: message (1, 12h + torpedo). Mass `p+B6 = 400h + (p+1A & 4 ? DAT+7F : 0)` | verified |
| 0deb:0221 | rocket_release(p) | `rocket_fire(&p+EB, &p.pos, p+20, {p, 0Fh, p+6C, DAT+6D})`; the player with unlimited ammunition gets `p+EB..+EE` restored | verified |
| 0deb:02ab | target_destroyed(s) | place: `place+1E & 4`; ship: `+1B & 2` | verified |
| 0deb:02d9 | attackers_on(place, far sub) | planes in a ground-attack state (desc flag 800h), not down, with scratch `+4 == place` and `+0C == sub` | verified |
| 0deb:033d | pick_subtarget(s, hard) | place with no sub-target: `n = top_targets(place, 4, l, hard)`; `n == 0` → `place+1E |= 4`; else the entry with the fewest attackers (first minimum) → `s+0C`; returns n | verified |
| 0deb:03d0 | approach(p, Vec *pt, i32 r, int h, i32 alt) | `b = bearing(p → pt)`; `dz = pt.z + alt − p.z`; `near = dist2(p, pt) < r`; `p+45/+49 |= 20h`; if `near` or `(u16)(2h) <= (u16)((i16)dz + h)` (altitude off by ≥ h): `e = b − p.heading − 8000h` (fly away), if `!near`: `e += e < 0 ? 4000h : C000h` (circle); `steer_heading_nolead(p, 0, e)`, `steer_altitude(p, −dz, 1)`, throttle = cruise; return 0; else return 1 (far enough and at altitude) | verified |
| 0deb:049a | fly_heading_alt(p, b, i32 dz) | `steer_heading_nolead(p, 0, b)`, `steer_altitude(p, −dz, 0)`, throttle = cruise − 20 | verified |
| 0deb:04d6 | aim_jitter(p, s, Vec *pt) | first time (`s+0A & 2` clear): `r = P+0A`; `s+10 = rng_range(2r) − r`, `s+12 = rng_range(2r) − r` (**RNG**); `pt.x += s+10`, `pt.y += s+12` | verified |
| 0deb:0548 | st_bomber_steer (14F5h, level bombers on a place) | pt = sub-target `s+0C`; destroyed → 1; jitter; phase 0: `steer_to_point(p, pt)`; `dist2 < 10000` → `release_ordnance(p, pt)`, phase 1, timer 7000. Phase 1: `steer_level(p)`; timer out → `ai_think_target(p)` | verified |
| 0deb:060d | st_divebomb_steer (14A5h) | §11.1 | verified |
| 0deb:0896 | level_attack(p, low) | §11.2 (0c2f: low 0, state 14CDh; 0c1e: low 1, state 14E1h) | verified |
| 0deb:0c1e / 0c2f | st_low_attack / st_glide_attack | `level_attack(p, 1)` / `(p, 0)` | verified |
| 0deb:0c40 | st_torpedo_steer (14B9h) | §11.3 | verified |
| 0deb:10ea | strafe_run(p, rockets) | §11.4 | verified |
| 0deb:13ac | st_rocket_steer (1509h) | add-on flag and target destroyed → 1; `strafe_run(p, 1)` done → `attack_reenter(p)` | verified |
| 0deb:13f3 | st_strafe_steer (151Dh) | `strafe_run(p, 0)` done: `s+0C = 0`, `s+8++`; `< 2` → phase 0 (another pass); else `p+1B |= 20h` (no more strafing), state 16B5h | verified |
| 0deb:143c | first_gun_type(p) | `.GL+4` (type of the first gun record) | verified |
| 0deb:144e | fixed_guns_loaded(p) | group A rounds > 0 (flags 2800h) or group B rounds (entry 1, flags 0500h) | verified |
| 0deb:1490 | has_ordnance(p) | `p+1B & 40h` | verified |
| 0deb:14a2 | is_dive_bomber(p) | `DAT+38 == 2` and has ordnance | verified |
| 0deb:14dc | torpedo_loaded(p) | `p+F1 != 0` and has ordnance | verified |
| 0deb:1500 | rockets_left(p) | `(i8)p+EB` | verified |
| 0deb:150f | can_strafe(p) | `!(p+1B & 20h)`, `DAT+09 != 0`, `fixed_guns_loaded(p)` | verified |
| 0deb:1555 | is_pure_fighter(p) | `DAT+38 == 0` and no ordnance | verified |
| 0deb:15a2 | bombers_assign(f, place) | `n = flight_alive_members(f, m)`; `k = top_targets(place, n, l, −1)`; if k: every member with ordnance: `+1C |= 1`, state 14F5h, scratch `+0C = l[i]`; returns k | verified |
| 0deb:1637 | torp_side(p, ship) | `p+1E & 8` or `ship+1E & 80h` → 1; `p+1E & 10h` or `ship+1E & 40h` → 0; stopped ship: `bearing_between(p, ship) < ship.heading`; else count flight mates (not the player, not p) in 14B9h on this ship per side: fewer on side 0 → 0 … i.e. `c0 < c1` → 0, `c1 < c0` → 1, equal → `rng & 1` (**RNG**) | verified |
| 0deb:1718 | ships_land_check | ships at the end of their route (`f+16 == f+18`) or at the first waypoint: trace 100 steps of `vrot_z((100, 0, 0), heading)` both ways from the ship; land (`14e0:07aa`) → `+1E |= 80h` / `40h` | verified |
| 0deb:1817 | ship_attack_setup(p, ship) | role-2 flight → 14E1h; torpedo → 14B9h (`side = torp_side`); dive bomber → 14CDh; ordnance → 14A5h; rockets → 1509h; ship `.DAT+6D` and `can_strafe` → 151Dh; else none. State with scratch {+2 = 1, +4 = ship, +6 = side}; returns chosen | verified |
| 0deb:18e6 | g_attack_area_load(area) | `G_ATTACK` data file (`55a4:0000`, fatal if missing): seek `(area − 1)·26`, read 26 bytes → `DS:576E` | verified |
| 0deb:196e | g_attack_load | seek 208h; `DS:578A` = count; `DS:5788` = far lists as above | verified |
| 0deb:1a7b | objtype_group(far rec) | `i = rec+2 & 1FFFh`; `< 1Ah` → `(i8)DS:576E[i]`, else −1 | verified |
| 0deb:1aa0 | target_entry(far rec) | `g = objtype_group(rec)`; `type = 1641:0157(…)`; the entry of `DS:5788[g]` with that type, or 0 | verified |
| 0deb:1afc | target_value(rec) | entry `+2` or 0 | verified |
| 0deb:1b1f | target_name(rec) | entry → string (6, entry+1) (`0ab0:000b`), else 0 | verified |
| 0deb:1b50 | top_targets(place, n, far *out[], int hard) | §11.5 | verified |
| 0deb:1cae | place_attack_setup(p, place) | role 2 → 14E1h; dive bomber → 14CDh; ordnance and no torpedo → class 3 ? 14F5h : 14A5h; else rockets → 1509h; `can_strafe` → 151Dh. Scratch {+2 = 0, +4 = place} | verified |
| 0deb:1d6d | attack_reenter(p) | `s+2 ? ship_attack_setup(p, s+4) : place_attack_setup(p, s+4)`; none → state 16B5h | verified |
| 0deb:1daf | place_damage_ratio(place) | `Σ v` and `Σ (byte == FFh ? v : byte·v >> 8)` over the group's objects; `satdiv(Σd << 10, Σv)` (0 when both 0) — used by scoring (`1899`) | verified |
| 0deb:1e83 | g_attack_init | `g_attack_load()`, `59f9:0026` (descriptors) | verified |

### 11.1 `0deb:060d st_divebomb_steer(p)` (14A5h) — verified

```
s = scratch; pt = s+0C ? sub.pos : s+4.pos; k = (s+2 == 0); alt = DS:148E[k]
if target_destroyed(s): return 1
aim_jitter(p, s, pt)
phase 0: if approach(p, pt, 40000, 1000, alt): if k and s+0C == 0: pick_subtarget(s, −1) else phase += k + 1
phase 1 (ships): pt = point_ahead(pt, ship.heading + 8000h, 40000); pt.z = alt
         steer_to_point(p, pt); if dist2(p, pt) < 4000: phase++
phase 2: a = pt; if !k: a = point_ahead(a, ship.heading + 8000h, dist2(pt, p) − 5000); ship+42/+46 |= 8
         e = steer_to_point(p, a).heading_error
         steer_pitch_to(p, (u16)(e + 1000) < 2000 ? −3640 : 0, 0); throttle = cruise − 60
         if dist2(p, pt) < DS:1492[k]: release_ordnance(p, pt); phase++; s+8 = 7000
phase 3: steer_level(p); if timer_dec(&s+8) == 0: addon ? attack_reenter(p) : ai_think_target(p)
return 0
```

### 11.2 `0deb:0896 level_attack(p, low)` (14CDh / 14E1h) — verified

```
s, pt as above; dzh = pt.z + 40000 − p.z; hi = low and p.z > 15000
if target_destroyed(s): return 1
aim_jitter; b = bearing(p → pt) − p.heading
phase 0: if approach(p, pt, 40000, 2000, hi ? p.z : 40000): place without sub-target → pick_subtarget(s, −1); else phase++
phase 1: fly_heading_alt(p, b, hi ? 0 : dzh)
         if (u16)(b + 500) < 1000 and (u16)(p.roll + 500) < 1000 and elevation_to(pt, p) − p.pitch < −8000: phase++
phase 2: lead = DS:1466[low]; aim = pt; p+45/+49 |= 40h; p+C1 |= 8
         if !low: if ship: lmove_heading(pt, ship.heading, ((i16)(ship+74 sar 8)·300) >> 10); aim = pt
                  lmove_heading(pt, p.heading, 6000)
         e = elevation_to(pt, p); if lead + 8001h < e: e −= lead          (signed)
         steer_pitch_to(p, e, 0); throttle = cruise − 23; dive brakes (+BA bit 2) = !low
         steer_heading_nolead(p, 0, b)
         if !low: dz = p.z − pt.z; if dz < 7000: if has_ordnance(p): release_ordnance(p, aim)
                                  if dz < 3000: phase++
phase 3: p+45/+49 |= 40h; steer_level(p); p+AE = 100h; if p+74 > 0 (climbing): phase++
phase 4: p+45/+49 |= 40h; steer_heading_nolead(p, 0, b + 8000h); steer_altitude(p, p.z − 500, 1)
         throttle = cruise; if dist2(p, pt) > 15000: attack_reenter(p)
return 0
```
(With `low` the plane dives on the target but never releases — the 14E1h state is used for role-2
flights; kept as is.)

### 11.3 `0deb:0c40 st_torpedo_steer(p)` (14B9h) — verified

```
t = s+4 (ship); alt = DS:148A[p+26]; pt = t.pos
if target_destroyed(s): return 1
aim_jitter; dz = alt + 300 − p.z; d = dist2(p, pt); tv = (i16)(t+74 >> 16) (ship speed)
phase 0: o = 0
    if tv == 0: o = s+6 ? 16000 : −16000
        if dz > −3000 and d > 30000 and (u16)(t.heading + o + 8000h − p.heading + 0FA0h) < 1F40h: phase++; return 0
    p+45/+49 |= 60h; throttle = cruise
    pt = point_ahead(pt, t.heading + o, 45000); steer_to_point(p, pt); steer_altitude(p, −dz, 1)
    if p.z < 2000: p+C1 |= 8
    if dist2(p, pt) < 4000 and |dz| < 500: phase++
phase 1: a = tv ? 1518h : 4000h; h = t.heading + (s+6 ? a : −a)
    r = min(d, 40000) − 6000; p+45/+49 |= 40h; t+42/+46 |= 8
    pt = point_ahead(pt, h, r); pt.z = alt; steer_to_point(p, pt)
    if d < 40000 and dist2(pt, p) > 10000:
        b1 = bearing(p → pt) − p.heading; b2 = bearing(p → t) − p.heading
        if (b2 > 0) == (b1 > 0) and abs16(b2) < abs16(b1): steer_heading_nolead(p, 0, b1 > 0 ? −12000 : 12000)
    p+C1 |= 8
    e = p+94 − 12·DS:1486[p+26]; p+B2 = clamp(p+B2 − (e·1200 >> 10), 0, 100h)     // hold drop speed
    if d < 15000 and (u16)(h + 8000h − p.heading + 0FA0h) < 1F40h: release_ordnance(p, &t.pos); phase++
phase 2: p+45/+49 |= 40h; p+C1 |= 8; steer_level(p); dz = alt + 400 − p.z; steer_altitude(p, −dz, 0)
    throttle = cruise; if dz < 100: phase++  … then falls through into phase 3 in the same call
phase 3: p+45/+49 |= 40h; steer_heading_nolead(p, 0, bearing(p → t) − p.heading + 8000h)
    steer_altitude(p, p.z − alt − 400, 0); throttle = cruise; if d > 15000: attack_reenter(p)
return 0
```

### 11.4 `0deb:10ea strafe_run(p, rockets)` — verified

```
s, pt as above; k = (s+2 == 0)
if target_destroyed(s): return 1
if ship: pt.z += ShipDAT(s+4)+04
pt.z += DS:146A[k]; b = bearing(p → pt) − p.heading; dz = pt.z + 2000 − p.z; d = dist2(p, pt)
p+45/+49 |= 40h
phase 0: if approach(p, pt, 20000, 500, 2000): place without sub-target → pick_subtarget(s, rockets ? −1 : first_gun_type(p)); else phase++
phase 1: fly_heading_alt(p, b, dz); if d < DS:146E[k]: phase++
phase 2: p+C1 |= 8; e = elevation_to(pt, p) − p.pitch; steer_climb(p, 0, (e − 15Eh) sar 1, 1)
         steer_heading_nolead(p, 0, b); throttle = cruise
         R = rockets ? DS:1472[k] : DS:1476[k]; T = rockets ? DS:147A[k] : DS:147E[k]
         if d < R and (u16)(b + 1000) < 2000 and (u16)(e + T) < 2T:
             rockets ? (rockets_left(p) ? rocket_release(p) : phase++) : ai_fire(p, 0, &p.angles, d, 0)
         if d < DS:1482[k]: phase++
phase 3: steer_heading_nolead(p, 0, b + 8000h); steer_altitude(p, p.z − pt.z − 1000, 0); throttle = cruise
         if d > 16000: return 1
return 0
```

### 11.5 `0deb:1b50 top_targets(place, n, far *out[], hard)` — verified

```
taken[50] = 0; j = 0
while j < n:
    best = −1
    for i < place+1A: rec = DS:5146 + (place+18 + i)·22; grp = DS:5142[place+18 + i]
        if !taken[i] and (hard < 0 or GDAMAGE[type(rec)].hardness (DS:5A87 + 8·type) <= hard)
           and damage byte (grp→ +12) != FFh and (v = target_value(rec)) > best: pick = i; best = v
    if best < 0:
        if j == 0: return 0
        copy out[0 ..] cyclically into out[j .. n−1]; return j
    taken[pick] = 1; out[j++] = rec(pick)
return j
```
## 12. `4edf` — flight-level states (take-off, formation, waypoints, escort, landing)

Flight task codes (`4edf:0c45 flight_next_task`) and the states `4edf:0e58 st_next_task` installs:
0 → 04A8h (escort: join), 1 → 0494h (return to base), 2 → 046Ch (orbit over home), 3 → 041Ch
(follow waypoints), 4 → 0480h (orbit the last waypoint), 5 → 04BCh (escort: fly with), 6 → no
change (parked on a carrier), 7 → 04D0h with `scratch[0] = DS:402E` (fly to a ground target).
Formation offsets: far `DS:12A8` (FORMS.DAT block 1) = formations of 4 slots × 6 bytes (x, y, z);
`4edf:123f` copies one to `DS:4020`. The escort offset of a flight is the group record's `R+28`
(3 words; `flight_build` replaces an all-zero offset by (−6000, 9000, 1500), `sim_world_dmg.md`
§1.3.3).

| Address | Name | Does | Conf. |
|---|---|---|---|
| 4edf:0000 | st_path_act (03B8h) | scratch {pos (12), angles (6), next}: copy into the plane; `next == 0` → `ai_leave_combat(p)` else `brain_set_state(next, p)` (so the posture is set once and the plane continues) | verified |
| 4edf:005e | path_enter(p, Vec *pos, int ang[3], next) | state 03B8h; scratch = {pos, ang, next} | verified |
| 4edf:009f | fm_set_velocity(FmState *fm, Vec *v, Matrix *Mt) | `w = 5137:004f(v, DS:3F22)` (per-frame displacement → velocity units); `fm+2E..33 (body v) = Mt·w`; `fm+34..39 (world v) = w`; `fill_int(fm+1E, 7FFFh, 3)` (fraction accumulators) | likely |
| 4edf:010a | ship_delta(Vec *out, Plane *c) | `ldiff16(c.pos, c+36 (previous position), out)` (the carrier's motion this frame) | verified |
| 4edf:0129 | on_carrier_deck(c, Vec *pt) | `|pt.x − c.x| < 5000`, `|pt.y − c.y| < 5000` and the vertical segment from pt down to z = 0 hits c's boxes (`6ac7:0120(pt, pt', c+20, &c.pos, c+24)`) | verified |
| 4edf:01c7 | fm_reinit(p, _) | `fm_init(&p.fm, &p+2, DAT+24 (FMD), matrix(p))` keeping `+A4/+A6/+A8` | verified |
| 4edf:023a | throttle_min_f0(p) | `p+B2 = max(p+B2, F0h)` | verified |
| 4edf:0252 | st_runway_takeoff_act (03E0h) | `s = scratch`; `gh = FMD+98`; `p+43/+47 |= 8` (no avoidance); first frame (brain +0C bit 2 clear): `fm_reinit(p)`, `s[0] = fm_cruise_speed_here(p)·DS:3F22 >> 10`; throttle: player ≥ F0h, AI 100h; AI with `p+6C > s[0] >> 2`: `steer_pitch_to(p, 1000)`, flaps half (`+BA = +BA & ~3 | 2`), `p+C1 = 2` (easy flight model); `plane_fly(p)`; when `p.z > gh + (player ? 0 : 200)`: player → state 0458h; AI → gear-up flag (`p+1D |= 10h` unless `DAT+76`), and above `gh + 200` `ai_leave_combat(p)` | verified |
| 4edf:0370 | st_carrier_takeoff_act (03CCh) | §12.1 | likely |
| 4edf:057f | park_on_carrier(p, int spot) | `c = flight+04`; `o = ShipDAT(c) + 6·spot` (x, y, z; spot 0's z is the deck height `+4`); `o.z += FMD+98`; `obj_to_world(&p.pos, &c.pos, o, c+20)`; `p.heading = c.heading`; `p.pitch = FMD+9A`; `p+43/+47 |= 8` | verified |
| 4edf:0619 | plane_gone(BX = p) | `+1A & 40h`, `+1A & 1` or `+1B & 2` | verified |
| 4edf:0639 | queue_prev(p) | the last flight member before p (`p+BC − 1` down to 0) that is not gone, or 0 | verified |
| 4edf:068a | takeoff_clear(p) | mission time `5d3c:0064()` > 2 (i32); AI throttle = 100h; if throttle > 4Bh: no previous plane or `dist2(p, prev) > 1000` → 1 | verified |
| 4edf:06fc | st_parked_carrier_act (03F4h) | `park_on_carrier(p, p+BC)`; carrier afloat: `takeoff_clear` → state 03CCh; carrier sunk and (AI or damage realism `DS:42CF`): state 1384h (wreck on deck) with `scratch (i32) = (5 − p+BC)·500h`; `plane_engine_sound(p)` | verified |
| 4edf:0780 | park_on_airfield(p, int spot) | `pl = flight+04`; `r = DS:128E[3·spot]` (distance along the runway); the two runway points of the place's type (`1641:01a5`) rotated by `pl.heading` (`5137:015c`); `h = angles_to(b, a).heading`; `a += pl.pos`; `p.heading = h`, `p.pitch = FMD+9A`, `p.x = a.x + mul_cos(r, h + 4000h)`, `p.y = a.y + mul_sin(r, h + 4000h)`, `p.z = FMD+98`; `p+43/+47 |= 8` | verified |
| 4edf:0870 | st_parked_airfield_act (0408h) | first frame: `park_on_airfield(p, p+BC)`; then `takeoff_clear` → state 03E0h | verified |
| 4edf:08b7 | flight_waypoint(p) | `wp_current_pos(&flight+16)` | verified |
| 4edf:08d6 | escort_situation(p) | `e = f+10`; `DS:4026..402D = 0`; `DS:402A = first_alive_of(e)`; none → 0; `DS:4026 = dist2(p, it)`: < 20000 → 3; else 2, and `DS:402C = my waypoint`: if set: `e` on standby → 1; else `w2 = e's waypoint`: none, or `dist2(DS:402C, w2) > 5000`, or the escorted leader not in 041Ch → 1 | verified |
| 4edf:09b9 | find_ground_target(p, i32 stop, i32 *d) | over `f+10[0..(i8)f+0E)` by reference kind `f+43`: 0 flights (their members, skipping down planes / sunk ships), 1 places, 2 ships (not sunk), 3 planes (not down): nearest by `dist2`; the search ends early once `best` exists and is closer than `stop`; `*d` = distance; returns the object | verified |
| 4edf:0b6f | find_target_45000(p) | `find_ground_target(p, 45000, &d)`, 0 if `d >= 45000` | verified |
| 4edf:0b9c | near_home(p) | `dist2(p, flight_home(f)) < 10000` → 2 else 1 | verified |
| 4edf:0bda | flight_all_down(f) | latch `f+3A & 2`; else every member down (aircraft) / sunk (ships) → set the latch, 1 | verified |
| 4edf:0c45 | flight_next_task(p, flag) | §12.2 | verified |
| 4edf:0e58 | st_next_task(p) | table above | verified |
| 4edf:0edb | ai_leave_combat(p) | `plane_in_formation(p)` (p leads) → `st_next_task(p)`; else state 0430h | verified |
| 4edf:0f0a | orbit_point(p, Vec *c, i32 r) | `b = bearing_between(p.pos, c)` (heading from c to p); `DS:4014 = c + lmove_dir({0, 0, b + (b − p.heading > 0 ? −3000 : 3000)}, r)` — a point on the circle of radius r around c, 3000 ahead of the plane's radial; returns `&DS:4014` | verified |
| 4edf:0f6d | fly_to_point(p, Vec *pt, tolh, tolp, int dist) | `e = steer_to_point(p, pt)`; bits: 1 `within(e sar 4, tolh)`, 2 `within(p.pitch, tolp)`, 4 `dist3(p, pt) < (i32)dist`; `p+C1 |= 1`; throttle = cruise − (p.pitch < 600 ? 70 : 10) | verified |
| 4edf:1013 | fly_to_point_w | wrapper | verified |
| 4edf:102e | fly_formation_slot(p, Vec *off, Plane *L, tolp, tolh, i32 dist) | §12.3 | verified |
| 4edf:11da | fly_formation_slot_w | wrapper | verified |
| 4edf:11f8 | st_act_fly(p) | `plane_fly(p)`; return 0 | verified |
| 4edf:120a | st_waypoints_steer (041Ch) | `w = flight_waypoint(p)`; none → `st_next_task(p)`; else `fly_to_point(p, w, 0, 0, 4000)` (pushed as `0, 0x0FA00000`) | verified |
| 4edf:123f | formation_offset(form, slot) | `DS:4020 = far DS:12A8 [(form·4 + slot)·6]` (6 bytes); returns `&DS:4020` | verified |
| 4edf:1278 | formation_offset_of(p, slot) | `formation_offset((i8)flight+01, slot)` | verified |
| 4edf:1294 | my_formation_offset(p) | `formation_offset((i8)flight+01, (i8)p+BC)` | verified |
| 4edf:12b3 | formation_point(Vec *out, Plane *L, int off[3]) | `out = L.pos + vrot_z(off, L.heading)` | verified |
| 4edf:12fa | st_join_steer (0430h) | `L = first_alive_of(f)`; `r = fly_formation_slot(p, my_formation_offset(p), L, 800h, 800h, 3000)`; `L+42 & 1` and `(r & 7) == 7` → state 0444h — **quirk**: no code ever sets `Plane+42` bit 0 (searched the whole image), so 0444h is never entered; both states fly the same slot | verified |
| 4edf:135a | st_keep_formation_steer (0444h) | same call; `!(L+42 & 1)` or `(r & 7) != 7` → state 0430h | verified |
| 4edf:13bd | st_orbit_home_steer (046Ch) | `pt = orbit_point(p, flight_home(f), 8000)`, `pt.z = 10000`; `fly_to_point(p, pt, 0, 0, 0)` | verified |
| 4edf:1413 | st_goto_target_steer (04D0h) | `pt = orbit_point(p, &scratch[0]→pos, 8000)`, `pt.z = 10000`; `fly_to_point(p, pt, 0, 0, 0)` | verified |
| 4edf:1463 | st_orbit_waypoint_steer (0480h) | `pt = orbit_point(p, wp_cursor_pos(&f+16, −1), 10000)` (orbit the last waypoint); `fly_to_point(p, pt, 0, 0, 0)` | verified |
| 4edf:14a6 | st_return_steer (0494h) | `pt = flight_home(f)`, `pt.z = 16000`; `r = fly_to_point(p, pt, 200, 500, 500)`; `r & 4` → state 046Ch (orbit at home — AI planes never land) | verified |
| 4edf:1503 | first_alive_of(f) | first member not down, or 0 | verified |
| 4edf:153e | st_escort_join_steer (04A8h) | `c = escort_situation(p)`: 0 → `ai_leave_combat(p)`; 1 → `fly_to_point(p, DS:402C, 0, 0, 0)`; 2 → `fly_to_point(p, &DS:402A.pos, 0, 0, 0)`; 3 → `fly_formation_slot(p, escort offset, DS:402A, 0, 0, 0)`; returns 1 (think every frame) | verified |
| 4edf:15da | st_escort_fly_steer (04BCh) | `L = first_alive_of(f+3E)`; none → `ai_leave_combat(p)`; `slot = formation_point(L, escort offset)`; escorted flight low (`L.z < 2001`): `pt = orbit_point(p, &L.pos, 10000)`, `pt.z = 7000`, `fly_to_point(p, pt, 0, 0, 0)`, throttle cruise; else `dist2(p, slot) <= 20000` → `fly_formation_slot(p, off, L, 0, 0, 0)`, else `fly_to_point(p, slot, 0, 0, 0)` and cruise; returns 1 | verified |
| 4edf:16ea | st_think_combat(p) | AI: `ai_think_target(p)`; nothing chosen → `ai_leave_combat(p)`; return 0 | verified |
| 4edf:1711 | pure_fighters_of_side(Plane *out[], side) | alive pure fighters of the side; 0-terminated; returns the count | verified |
| 4edf:1774 | flight_states_register | `59f9:0026` | verified |
| 4edf:1790 | scramble_radius | returns 26000 | verified |

### 12.1 `4edf:0370 st_carrier_takeoff_act(p)` (03CCh) — likely

```
c = flight+04; SD = ShipDAT(c); t = brain frames (+50, i32); p+43/+47 |= 8
gh = FMD+98; deck = SD+04; p+B8 = deck; top = deck + gh
throttle: player ≥ F0h (throttle_min_f0), AI 100h; AI: flaps half, p+C1 |= 2
c+42/+46 |= 8                                             // deck busy
if t < 2: park_on_carrier(p, p+BC); return 0
if t == 2: fm_reinit(p); v = ship_delta(c); 5137:0000(v, v); fm_set_velocity(&p.fm, v, transpose(matrix(c)))
plane_fly(p)
if player: if p.z <= top and on_carrier_deck(c, &p.pos): return 0; state 0458h
else:
    a = p.pos; p.heading = c.heading; lmove(a, 1000, p.heading)
    if on_carrier_deck(c, a): p.z = top; return 0              // still over the deck: hold on it
    if p.z <= top + 200 and on_carrier_deck(c, &p.pos): return 0
    ai_leave_combat(p); if DAT+76 == 0: p+1D |= 10h
```

### 12.2 `4edf:0c45 flight_next_task(p, flag)` — verified

```
w = wp_current_pos(&f+16); DS:402E = 0
if p in 03F4h: return 6
if f+02 == 6 (protect):
    g = f+10
    if flight_all_down(g): return w ? 3 : near_home(p)
    L = flight_leader(g)
    if g+3B & 2 (standby): return w ? 3 : wp_cursor_pos(&f+16, −1) ? 4 : near_home(p)
    if !w: return 0
    w2 = wp_current_pos(&g+16); return (w2 and dist2(w, w2) <= 5000 and L in 041Ch) ? 0 : 3
if w:
    if f+02 == 5 (cover):
        if flag and player+34 == f: return 3
        DS:402E = find_ground_target(p, −1, &d)
        if DS:402E: (e, de) = nearest_in_list(&DS:402E.pos, p+26, &de); if d + 10000 > de: return 7
    return 3
if f+3E: return flight_all_down(f+3E) ? near_home(p) : 5
switch f+02: 2, 3 → near_home(p)
             5 → DS:402E = find_target_45000(p); if DS:402E: return 7; fall into 0
             0, 1, 4 → wp_cursor_pos(&f+16, −1) ? 4 : near_home(p)
             else → −1 (no change)
```

### 12.3 `4edf:102e fly_formation_slot(p, off, L, tolp, tolh, dist)` — verified (call arguments from the disassembly)

```
e = dir_from_heading(L.heading) sar 1 (277a:5fae, vsar 1)
o = off rotated by −L.pitch (x/z swapped around a vrot_z) and then by L.heading (vrot_z)
t1 = L.pos + L.v70; t2 = t1 + o (the slot one frame ahead); o += e; t3 = t2 + e
steer_intercept(p, L, o, 0x10001, out)
d = dist2(p, t3)
if d <= 15000 and p.pitch <= 600: steer_speed_match(p, L, (i16)d, out+0A + p.heading, 2000h)
else p+B2 = cruise
r = (abs16(p.heading − L.heading) < tolh) | (abs16(p.pitch − L.pitch) < tolp) << 1 | (dist2(p, t2) < dist) << 2
p+C1 |= 1; return r
```

## 13. `17fe` waypoints, `69d0` flight helpers, `51fb` spawning, `6dec` midpoints

Waypoint record (from SCRIPT.DAT type 7, `sim_world_dmg.md` §1.3.2): `+0` kind (0 point, 1
flight, 2 plane, 3 ship, 4 `DS:4757` object, 5 place), `+1` message index (≥ 0 → text at `DS:4749 +
DS:4745[i]`), `+2` point (kind 0) or object pointer, `+4` i32 altitude (kinds ≠ 0). A cursor is 3
words {index, count, pointer list} (the flight's `+16`).

| Address | Name | Does | Conf. |
|---|---|---|---|
| 17fe:000b | waypoint_pos(wp) | kind 0: `&wp+2`; kinds 1..5: `q` = kind 1 → the flight's first member (`(wp+2)→+08[0]`) else the object; the next of 4 rotating 12-byte buffers `DS:5C1A[DS:5C22]` (`DS:5C22 = (DS:5C22 + 1) & 3`) = `{q.x, q.y, wp+4}`; kinds > 5 dereference 0 (quirk). `DS:5C24 == 0` → `618d:04e4(1)` first (a no-op query) | verified |
| 17fe:00a1 | wp_cursor_get(cur, i) | `j = cur[0] + i`; `0 <= j < cur[1]` → `cur[2][j]`, else 0 | verified |
| 17fe:00c9 | wp_cursor_pos(cur, i) | `waypoint_pos(wp_cursor_get(cur, i))` or 0 | verified |
| 17fe:00ed | wp_current_pos(cur) | `wp_cursor_pos(cur, 0)` | verified |
| 17fe:0110 | wp_cursor_advance(cur, i) | `j = cur[0] + i`; in range → `cur[0] = j`, 1; else `cur[0] = cur[1]`, 0 | verified |
| 17fe:0137 | wp_flag_set | `DS:5C24 = 1` | verified |
| 17fe:0142 | wp_buffers_init | `DS:5BEA..` (30 words) = 0; `fill_seq(DS:5C1A, 5BEAh, 12, 4)` | verified |
| 17fe:016b | wp_init | `wp_buffers_init()` | verified |
| 69d0:0000 | helpers_nop | (14 bytes) empty stub | verified |
| 69d0:000e | ship_shape_of_type(t) | `DS:451B[t]` | verified |
| 69d0:001c | effect_frames_sum(a, b) | Σ `DS:647C[i].+4` (12-byte records) for i = a..b | verified |
| 69d0:0049 | weather_refresh | `DS:42C9 != DS:4743` → `wind_apply()` (`56ac:009d`) | verified |
| 69d0:005d | flight_first_wp_pos(f) | `f+0A ? waypoint_pos(f+0A) : 0` | verified |
| 69d0:007d | flight_home(f) | ground start (`f+03 == 0`): first waypoint or the base object's position (`f+04 + 4`); carrier start: no base → first waypoint, else the carrier position | verified |
| 69d0:00c4 | message_text(i) | `DS:4749 + DS:4745[i]` | verified |
| 69d0:00de | flight_wp_pos(f) | `wp_current_pos(&f+16)` | verified |
| 69d0:00f2 | waypoint_message(f) | current waypoint with message index ≥ 0 → its text, else 0 | verified |
| 69d0:0129 | engine_power_of(p) | player with a 2-engine `.DMG`: `(+A4 + +A6) >> 1`; else `+A4`; outside 0..400h → 0 | verified |
| 69d0:0174 | range_left(p) | player without limited fuel: 1000000000 (i32); else `v = fm_cruise_speed(FMD, 10)·DS:3F22 >> 10`; `f = max(ldiv(state+10, DMG.k5), 0) + max(ldiv(state+0C, DMG.k4), 0)` (drop tank then main tank, in frames of full-throttle burn); returns `((v·engine_power_of(p) + 3FFh) >> 10)·f` (i32) | verified |
| 69d0:0285 | can_reach_home(p) | `dist2(p, flight_home(f)) < range_left(p) + 20000` | verified |
| 69d0:02e0 | helpers_nop2 | empty | verified |
| 51fb:0000 | formation_points(Vec out[], n, Vec *c, form, int ang[3]) | `out[0] = c`; `M = mat_from_angles(ang)`; `out[i] = c + M·formation_offset(form, i)` | verified |
| 51fb:006e | spawn_intercept_point(Vec *out, Vec *tgt, i32 d) | §13.1 | verified |
| 51fb:0199 | launch_intercept(f, Vec *tgt) | §13.1 | verified |
| 51fb:0306 | spawn_nop | empty | verified |
| 6dec:0000 | midpoint(a, b) | `DS:522A = (a + b) >> 1` per i32 component; returns `&DS:522A` | verified |
| 6dec:003d | bounding_centre(Vec p[], n) | `midpoint(min, max)` of the component-wise bounds | verified |

### 13.1 Spawning (standby flights) — verified

`51fb:0199 launch_intercept(f, tgt)`: `mode = f+00 == 1 ? 1 : (far f+52)→+1E` (the group record's
standby mode); `f+3B &= ~2` (active). Only mode 2 spawns: up to 20 tries of
`h = spawn_intercept_point(pt, tgt, 22000)` keeping the candidate whose nearest plane of another
flight (`dist3`, start 1000000000) is farthest, until that distance exceeds 12000; then
`formation_points(pts, f+06, best, f+01, {0, 0, h})` and every member gets `path_enter(m, &pts[i],
{0, 0, h}, 0)` (teleported there on its next act, then `ai_leave_combat`). Other modes: the members
simply become active (e.g. parked planes start their take-off queue).

`51fb:006e spawn_intercept_point(out, tgt, d)`: `r = rng_next()`; `hi = tgt.z + 2000`; `hi <= 10000`
→ `lo = hi = 10000`; else `lo = (u16)(r + 24000) < 48000 ? tgt.z − 2000 : tgt.z + 1000`, `lo =
max(lo, 10000)`; `out = tgt`, `out.z = lo + rng_range(hi − lo)`; `point_ahead(out, player.heading
+ r, d)`; `point_ahead(out, player.heading, 4000)`; returns `(u16)(r + 6000) < 12000 ? rng_next() :
bearing_between(tgt, out) + rng_range(12000) − 6000` (the spawn heading) (**RNG** ×3–4).

## 14. `6dfc` — landing signal officer (player's carrier approach)

`DS:523B` = current LSO signal (−1 none, −2 trapped/landed, 0 wave-off, 1 too fast, 2 stall
warning, 3 too low, 4 and 7 line-up corrections (right/left of centre), 5 roger, 6 over the
ramp/cut) — copied to `DS:57E8` for the HUD; `DS:5236` wave-off cooldown, `DS:5239` request
cooldown; the player's `+1C` bits 8 (approach requested) and 10h (trapped). Ship `.DAT`: `+04` deck
height, `+66` landing area start (deck y), `+68` length, `+6A` width.

| Address | Name | Does | Conf. |
|---|---|---|---|
| 6dfc:0000 | lso_signal(p, c) | §14.1 | likely |
| 6dfc:02e5 | lso_frame | if `DS:5236`: `timer_dec` → at 0: clear it, `+1C &= ~8`, signal −1. Else if `DS:5239`: signal −1, `timer_dec` → at 0 message (1, 35h); else if the player's flight started from a carrier: trapped (`+1C & 10h`) → throttle 0, wheel brakes (`+BA |= 8`); requested (`+1C & 8`): within 60000 of the carrier `lso_signal(player, c)`: 0 → `DS:5236 = F00h`; −2 → brakes, `+1C |= 10h`; farther: `+1C &= ~8`, −1. `DS:57E8 = DS:523B` | verified |
| 6dfc:0400 | lso_request | `player+1C |= 8`; `DS:5239 = 500h` (radio command) | verified |
| 6dfc:0413 | lso_can_request | no cooldown, not yet requested, carrier start, carrier afloat, above the deck (`p.z > +B8 + FMD+98`), within 60000 → 1 | verified |
| 6dfc:0497 / 04ce | (sim_flow) LSO paddle drawing | — | — |

### 14.1 `6dfc:0000 lso_signal(p, c)` — likely (decompile; arithmetic simple)

```
rel = p.pos in the carrier's frame (277a:512e with the transposed matrix, 277a:4cb3): x lateral, y along the deck, z up
h = rel.z − SD+04 − FMD(p)+98                                      // height of the wheels over the deck
if !(SD+66 − 25000 <= y <= SD+66 + SD+68) or |x| > |y| or |p.heading − c.heading| >= 3001: return −1
if y > −9000 and gear up: return 0
if |x| < 75: L = R = 0
else: q = |y| / (|x| − 74); if q < 16: return 0; L = R = (q < 1001); if x < 1: R = 0 else L = 0
if SD+66 < y < SD+66 + SD+68 and |x| < SD+6A / 2 and h < 20: return −2        // caught the wire
if h < 1: low = 1
else: q = ((SD+66 + SD+68/2) − y) / h; if q < 4: return 0; low = (q >= 30)
v = p+94 < 1200 ? 0 : p+94 < 1500 ? 1 : 2
if v == 2: return 1; if FM flag 2 (+AA stall warning): return 2; if low: return 3
if L: return 7; if R: return 4; if v == 1: return 1
if SD+66 − 400 < y < SD+66 + SD+68: return 6
return 5
```

## 15. `1660` (AI part) — reactions to the player's radio orders, `07fe` ces.c

Order codes 33h–50h come from sim_flow's radio menu (`1660:0f85 order_send`). `DS:5BD4` = "hold
formation" order active (read by `ai_think_target` through `1660:01b4`).

| Address | Name | Does | Conf. |
|---|---|---|---|
| 1660:0009 | aircraft_name(u8 *rec, char *dst) | `STR(6, DS:18E6[rec[1]] + rec[0])` (`DS:18E6` = {0, 4, 13, 1}); `rec+8 > 1` → append `DS:190E` ("s") | verified |
| 1660:0065 | mates_of(p, int mode, Plane *out[]) | alive members m ≠ p of p's flight; `pair = (m+DD == p or p+DD == m)`; included when `mode < 0`, `mode == 2`, or `pair == (mode == 0)` (0 = my pair only, 1 = the others); returns the count | verified |
| 1660:0110 | aspect_to(a, b) | `b.heading − (a+D1 + a.heading − 8000h)` | verified |
| 1660:0130 | attacker_on_tail(t) | the first plane q with `q+D7 == t`, `q+D3 < 10000`, `(u16)(q+D1 + 4000h) < 8000h`, `(u16)(q+CF + 3000h) < 6000h` and `(u16)(aspect_to(q, t) + 5000h) > 9FFFh`, else 0 | verified |
| 1660:01b4 | player_orders_active | `DS:5BD4` | verified |
| 1660:01bc | ai_order_execute(order, mode, u8 *tgt) | §15.1 | verified |
| 1660:0706 | mates_have_bombers(p, mode, int *torp) | any mate (by `mates_of`) that is not a pure fighter → 1, and `*torp = 1` when it carries a torpedo | verified |
| 1660:0787 | ship_priority(s) | `DS:18EC[(i8)ShipDAT+6C]` = {1, 0, 7, 2, 3, 4, 8, 5, 6} (lower = preferred; carriers first) | verified |
| 1660:0bd7 | alive_count(f) | members not down | verified |
| 07fe:000a | ces_check(a, b, c) | assertion helper: unless all three are non-zero or all zero, `2494:0127` assert (`ces.c`, line 41) — used by render3d (`2ec2`) | verified |

### 15.1 `1660:01bc ai_order_execute(order, mode, tgt)` — verified

`n = mates_of(player, mode, m)`; replies are radio messages `1815:06e7(id, rec, 1)` with `rec+16h` =
subject plane and `rec+0Eh` (far) = 0 unless noted; `side = player+26`.

| Order | Effect |
|---|---|
| 33h (cover me) | `n > 0`: `w = m[0]`: `w`'s state has flag 20h → reply 4; `dist3(w, player) > 20000` → 3; `x = attacker_on_tail(player)`: none → 2; else reply 5 and `cross_enter(w, player, x)` |
| 34h, 35h (check six) | `n > 0`: reply 6; every mate with an attacker on its tail gets `+43/+47 |= 1` and reply 8 (the first such mate is the subject); message `reply + side` |
| 36h, 37h (break) | message `10 + 2·side + (order == 37h)`; `bank_enter(m[0], order == 36h)` (no check of n) |
| 38h (split) | every mate: `manoeuvre_enter(m+1A & 80h ? 12 : 11, m, 0)`; message 0Eh |
| 39h, 3Bh | `w = m[0]`: flag 20h → 13h; else `order == 39h ? 0Fh : 11h`, `w+CA = 0`, `w+E7 = 50000`, `w+1B |= 10h`; message `id + side`; `w`'s brain timer = 0 |
| 3Ah, 3Ch | every mate: `+CA = 0`, `+E7 = 50000`, `+1B |= 10h`, `ai_think_target`; message `15h + (order == 3Ch)` |
| 3Dh (resume) | every mate: `+E3 = 50000`, `+1B &= ~10h`; `DS:5BD4 = 0`; message `17h + side` |
| 40h–42h (attack target) | `DS:5BD4 = 0`; `rec+0E = aircraft_name(tgt)`; subject = mode 2 ? 0 : m[0]; id 19h; every mate: aircraft target group (`tgt[1] == 0`): if it has ordnance `ai_break_toward(m)` and id 56h; `kind = tgt[0] + 1`; else `kind = tgt[1] + 4`; `m+E3 = 250000`, `m+CA = kind`, `m+BD = tgt+0A` (the target object), `m+1B &= ~20h`, `st_think_combat(m)` |
| 43h, 44h (attack from the right / left) | `DS:5BD4 = 0`; message `1Ah + (order == 44h)`; every mate `+1E |= order == 44h ? 10h : 8` (read by `torp_side`) |
| 50h (hold formation) | `DS:5BD4 = 1`; message 51h |
| others | nothing |

`Plane+CA` (task kind 1–5 for `target_class`), `+BD` (task target), `+E3` (i32 task timer, counted
by `timer_expired32` in the threat check), `+E7` (i32 "don't engage" timer) and `+1B` bit 10h are
thus set by the player's orders.
## 16. Plane fields used by the AI (reconcile in `sim_world.md`)

| Off | Type | Meaning | Writers / readers |
|---|---|---|---|
| 1A | u8 | 10h aim solution valid this frame, 20h second wingman (3-plane element), 80h slot side / wingman with a second wingman | 1284:02fb, 583c:0199, 12fd:1a78 |
| 1B | u8 | 04 known attacker, 10h player order in force, 20h no more strafing / target order, 40h has ordnance, 80h fixed guns out | 69fe:015c, 1660:01bc, 0deb |
| 1C | u8 | 01 fighting (has a target), 02 hurried waypoint, 04 friendly to the player's flight, 08/10h LSO requested / trapped (player) | 1142:100d, 5058:0010, 6dfc |
| 1D | u8 | 10h retract the gear after the delay in `(+16)[1]` | 4edf:0252, 5058:048e |
| 1E | u8 | planes: 08 / 10h attack from the right / left (orders 43h/44h), 20h "stations empty" message shown (player); ships: 02/04 torpedo/bomb vulnerable (dmg part), 40h/80h land on that side | 1660:01bc, 1284:0435, 0deb:1718 |
| 1F | u8 | 10h cached energy advantage, 20h burst pause armed | 1027:0008, 1284 |
| 2C–33 | | alert state (§3) | 14c3 |
| 42, 46 | u32 | situation flags (latched / accumulating each frame): +42 bit 04 removed/wreck, 08 ship under attack or deck busy, 10h formation-keeping wingman, 20h firing; +43 bits 01 forced reaction, 02 under fire, 04 bullets near, 08 no avoidance, 10h–80h collision avoidance (085b); +44 bit 02 break off (hit count); +45 bits 20h attack run, 40h low attack run | many |
| 4A–57 | | brain (§1.1) | 69fe |
| 94 | i16 | forward speed (FmState body v) | 0deb:0c40, 6dfc |
| 8E | i16 | yaw rate (FmState) | 0619:00ce, 1ad2 |
| BC | i8 | index in the flight (renumbered every frame by `flight_renumber`) | 5058:0393 |
| BD | ptr | task target (orders) | 1660:01bc, 1142:05ce |
| C1 | u16 | `plane_fly` requests (01 coordinated, 02 easy FM, 08 wings-level hold, 10h no coordination) | fm §4.1 |
| C3 | u8[6] | known-plane bit set by serial `+C9` | 583c |
| CA | i8 | task kind (1–5) | 1660:01bc, 1142:05ce |
| CB–D6 | | aim record (§7.1): +CB selection, +CD/+CE errors, +CF/+D1 angles, +D3 i32 range | 1284:02fb |
| D7 | ptr | target | everywhere |
| D9, DB | ptr | attacker slots on this plane (as a target) | 12fd |
| DD | ptr | element leader | 583c:0199 |
| DF | i32 | energy decision timer | 1027 |
| E3 | i32 | task timer (orders; `timer_expired32` in the threat check) | 1660, 69fe |
| E7 | i32 | engage-restriction timer | 1660, 1142:08fb |
| F2 | i8 | hits taken | 1284:0006 |
| F9 | i16 | alert-victim cooldown | 0619:0472 |
| FB, FD | i16 | closure heading / pitch (from `aim_solution`) | 0ac2 |
| FF | i16 | hit-reaction timer | 1284:0006 |
| 101 | i16 | burst timer | 1284 |

Pilot profile words (`DS:55CE[+BB]`, 70h bytes; see `sim_world_dmg.md` §1.7) as used by the AI:
`+00` eyesight (spot range factor), `+02` alertness (lower = faster scans), `+04` threat
visibility chance, `+06` extend time, `+08` gunnery base (fixed guns), `+0A` bombing error radius,
`+0C` max bank, `+0E` turn coordination, `+10` cruise throttle, `+12` gunnery threshold, `+14`
energy-fight chance, `+16` engage threshold, `+18` extend chance, `+1A` head-on chance, `+1E` close
spotting penalty, `+20` manoeuvre selector / flak lucky-burst, `+22` pincer allowed, `+24` head-on
preference, `+28` preferred tactic, `+2A` head-on bomber attack, `+2C[21]` manoeuvre weights,
`+41` evasive pilot flag, `+42` aerobatics chance, `+44` energy rating, `+46` dog-fight flag,
`+48` sun-glare threshold, `+4C/+4E` Thach-weave chances, `+50` hits before breaking off.

## 17. Globals

| DS | Name | Meaning |
|---|---|---|
| 47F2, 47F4, 47F6 | desc_count, scratch_max, desc_list | descriptor registry (`59f9`) |
| 488C | brain_jitter | timer jitter counter |
| 47E0, 47E2 | element_count, elements | far 16-byte element records |
| 47DC, 47DE | scan_heading, scan_element | spotting context |
| 47E6, 47E8, 47EA, 47EC, 47EE | regroup timer / flight index, init flag, forget index / clock | 583c:1992 |
| 47D6 | sun_dir | 583c:0471 |
| 5814..581F | best_candidate | target chooser (§5.1) |
| 57EA | help_msg_sent | 1142:0e59 |
| 5682..568D | aim_record | 0ac2:000e |
| 5820 | taking_fire_msg_timer | 1284:0435 |
| 5CCC/5CD0, 5CD4/5CD8 | hostile lists and counts per side | read by 1284:00f4 (built outside the AI; see Hand-offs) |
| 5CEC | sdef | SDEF.DAT (20 × 14 bytes) |
| 193C | manoeuvre_table | 20 × {coordinated, far fn} |
| 12A4, 12A8 | forms | far FORMS.DAT blocks (ships / aircraft formations) |
| 4014, 4020 | orbit_point, formation_offset buffers | 4edf |
| 4026..402F | escort situation / task target | 4edf:08d6, 0c45 |
| 5BEA, 5C1A, 5C22, 5C24 | waypoint position buffers | 17fe |
| 5BD4 | hold_formation_order | 1660 |
| 522A | midpoint buffer | 6dec |
| 5236, 5238, 5239, 523B, 57E8 | LSO state | 6dfc |
| 576E, 5788, 578A | G_ATTACK tables | 0deb |
| 1246.., 1486.., 1552, 1622, 1628, 162E, 1634, 163E, 1644, 1646, 164A, 164E, 1654, 1661, 165A, 160D, 12AC, 12B6, 12CE, 18E6, 18EC | constant tables | quoted in the sections above |

## 18. RNG call sites (state `DS:4454`, sim_flow's generator)

| Site | Decides |
|---|---|
| 1142:0350 | head-on pass variant (vs pilot `+1A`) |
| 583c:0749 | a threat is seen (`can_see`) |
| 583c:14e9 | side and rear scan intervals |
| 1284:0271 | shot quality 1 or 2 |
| 1284:0353 | trigger choice (fixed guns), turret burst pause |
| 1284:0435 | burst timer, spray offsets (×2) |
| 1027:0008, 05b5, 060b | energy fight, climb mode, manoeuvre 6 |
| 12fd:04ca | head-on preference (×2), aerobatic manoeuvre chance |
| 12fd:0cf3 | Thach weave (×2) |
| 12fd:0e28 | extend, candidate pruning (×3), manoeuvre pick |
| 12fd:15f4 | level-off coin, manoeuvre pick |
| 1ad2:056c, 0bcb | kick timers, weighted pick |
| 0deb:04d6 | bomb aim jitter (×2) |
| 0deb:1637 | torpedo side tie-break |
| 51fb:006e | spawn point and heading |

The call order of these per frame is part of the VCR determinism contract: the port must call
the RNG in exactly this order (every AI function above draws only when its guard conditions hold).

## 19. Time base

All AI timers are in `DS:711E` units (100h per nominal frame; `362b` helpers): brain think periods
(`desc.period` 500–19200 = 2–75 nominal frames … e.g. 6400 = 25 frames), element scan timers
(7500 +), burst timers (5000–9095), weave timers (50000), etc. Distances per frame (steering,
formation lead) use the flight model's per-frame velocities (`Plane+6A..+75`), i.e. the same
`DS:711E` scaling as the physics. `DS:4086` (mission clock, += dt each frame) is used by
`583c:1992` (128-unit steps for the forget pass) and the gun refire checks.

## 20. Port notes

* The descriptors are data; keep them as a table keyed by their DS offset so that equality tests
  (`p+4A == 16C9h`) keep working (the port stores descriptor *ids* in the emulated `mem[]`).
* Register-argument helpers become ordinary functions (§1.3).
* `/* PORT: */` `1027:02d3` passes an uninitialised stack buffer as the second point of the cloud
  test — use `t.pos`, and log it; the original result depends on stale stack contents (clouds only
  exist with realistic weather and wind 1 or 2).
* `583c:0176` has no bound on the element size (≤ 4 members fit); keep an assert.
* `17fe:000b` with a waypoint kind > 5 dereferences 0 — never happens in the shipped data.

## 21. Hand-offs

* **sim_flow**: order codes 33h–50h handled by `1660:01bc` (§15.1); radio message ids used here
  (`1815:06e7`/`06d0`): 1–3 contact reports, 1Ch/1Eh/1Fh+side bandit calls, 38h pincer, 52h–59h,
  51h, 0Eh–1Bh order acknowledgements; `DS:57E8` LSO signal for the HUD; `5d3c:0064` mission time
  used by `takeoff_clear`. The functions `1660:07bb`, `0bae`, `0c12`, `0c47` (radio-menu side of
  segment 1660, assigned to sim_flow by the ownership map) are **not** in `sim_flow_symbols.csv`
  yet and are not specced here either. `player+44` bit 0 (tested by `1284:01a3`) is not set by any
  AI code — find its writer on the player side.
* **render3d**: `277a:5fae dir_from_heading`, `277a:512e`/`4cb3` (world → object frame, used by the
  LSO), `5137:004f`, `5137:0000`, `277a:4eb6 mul_sin` semantics as used here.
* **whoever builds `DS:5CCC..5CD8`** (hostile plane lists per side, read by `1284:00f4`): not found
  in the AI segments.

## 22. Open questions

* `Plane+42` bit 0 is tested (`4edf:12fa/135a`) but never set, so state 0444h is unreachable —
  confirm with a VCR film if possible.
* The meaning of several pilot profile words is inferred from use only (§16).
* `1142:05ce` role 2 / bomber branches were read from the decompile; verify against x86dis before
  porting.
* `0deb:0896` with `low == 1` (state 14E1h, role-2 flights) never releases ordnance — intended?