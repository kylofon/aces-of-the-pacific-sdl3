# sim_flow part: results — RNG, mission goals and scoring, SIM.OUT, skip-ahead (AP.EXE)

Part of `sim_flow` (lead file `sim_flow.md`). Target `work/AP_flat.exe`, DGROUP `3EA4`, addresses as in
`port/RE_GUIDE.md`. Written 2026-09-26 from the disassembly (`tools/x86dis.py`); confidence
**verified** unless tagged *likely* / *guess*. Symbols: `sim_flow_results_symbols.csv`.

Segments: `1889` (RNG), `14b8` (random table, XOR checksum), `1899` (goal tracking, kill and target
credit, goal completion), `5254` (`results.c`: end-of-mission evaluation, fate, `SIM.OUT`), `496a` +
`082a` (skip-ahead, the "A" key).

## Index

1. Overview
2. RNG `1889` (lagged Fibonacci) and `14b8`
3. Object lists and result globals (`5254:0000`)
4. Per-frame goal tracking `1899:0012` (object status bits)
5. Kill and target credit `1899:0cf0`, `1899:102f`
6. Goal helpers: `10f8`, `11aa`, `139f`, `13c9`, goal completion `152e`
7. Results `5254`: mission result code per mission type, fate, score, `SIM.OUT`
8. Skip-ahead `496a`, `082a`
9. Port notes
10. Hand-offs
11. Open questions

---

## 1. Overview

* During the flight the sim step (`5440:1317`, lead §6.1) calls `goal_update 1899:0012` once per
  frame. It keeps a set of **status bits in every aircraft and ship** (`obj+1C..+1F`) and in every
  ground place (`place+1E`) — engaged, safe, reached the target area, objective done — plus the
  "combat nearby" flags that switch the ground detail (`DS:5C90..5C93`) and the "mission over" flag
  `DS:5CC9`.
* When an object is destroyed or hit, the damage/crash code (sim_world `088a:054f`, weapon impacts)
  calls `kill_credit 1899:0cf0` / `target_credit 1899:102f`: they add to the **score** `DS:5CA1`
  (player) / `DS:5C9F` (player's flight), to the SIM.OUT counters (kept directly in the SIM.OUT
  image at `DS:5CA3`), and set the friendly-fire bits.
* At the end of the mission, the end dialog (`6210:05e0`, ui part) calls `fate_record 5254:0161`
  (killed / bailed / ditched / captured / rescued / landed; sets the SIM.OUT fate bits), and the VCR
  session driver calls `results_write 5254:04f1`, which evaluates the **mission result code** for the
  mission type (`5254:08d9`), computes merit and final score, and writes `SIM.OUT` (36 bytes).

Notation: `P` = the player's plane (`DS:3B09`); `F.x` = byte/word at offset x of a flight record
(0x56 bytes, `DS:4753[i]`, layout in `sim_world_dmg.md` §1.3.3: `+00` kind 0 aircraft / 1 ship group,
`+02` role, `+03` carrier-based, `+04` base object, `+06` member count, `+08` member pointer array,
`+0E` reference count, `+10` references[], `+16` waypoint cursor, `+3B` flags, `+43` reference kind
0 flights / 1 places / 2 ships / 3 planes); `obj.x` = byte of an aircraft (0x107) or ship (0x88)
object; `dead(o)` = `o.1A & 40h || o.1A & 1`; `side(o)` = `o.26`; `DAT(o)` = the aircraft `.DAT`
image `DS:55D2[DS:54BC[o.19]]`; `SDAT(o)` = the ship `.DAT` `DS:55D0[DS:555B[o.19]]`;
`dist(a, b)` = `277a:3b3c(&a.04, &b.04)` (u32 3-D distance, render3d math). Weapon class ids
(runtime, from `488e:007a`): `DS:1344` bomb, `DS:193A` rocket, `DS:19EC` torpedo, `DS:1348` bullet.

---

## 2. RNG `1889` (lagged Fibonacci) and `14b8`

State (0x76 bytes): `u16 s[56]` (+00), `u8 j` (+70h), `u8 k` (+71h), far hook (+72h). Two instances:
`DS:4454` (the sim RNG; almost every AI/weapon caller) and `DS:43DE`; both reseeded by
`mission_start 4e0d:03e9` (lead §3.3), which also sets their hooks (`DS:44C6`, `DS:4450`) to the stub
of the empty `4e0d:03e4`.

| Address | Name | Behaviour |
|---|---|---|
| `1889:0002` | `rng_seed(st)` | copy the 56 words of the constant table far `3A60:0000` into `s`; `j = 37h` (55), `k = 18h` (24); hook = 0 |
| `1889:0044` | `rng_skip(st, s32 n)` | `while (--n >= 0) rng_next(st)` (runs n times) |
| `1889:005f` | `rng_next(st)` → u16 | if `(s8)k < 0`: call the hook if non-null, return FFFFh. Else `a = s[k++]; s[j] += a; r = s[j]; j++`; then **if `j == 56` → `j = 0`, else if `k == 56` → `k = 0`** (only one wrap test per call — harmless because j and k are 31 apart); return r (16-bit wrapping add) |
| `1889:00b4` | `rng_mod(st, n)` | `n <= 1` → 0; else `(rng_next(st) & 7FFFh) % n` (signed `idiv`, n > 1) |
| `1889:00db` | `rng_chance(st, p)` | `(rng_next(st) & 0FFFh) < 41·p` (signed compare): p in percent (41·100 = 4100 ≥ 4096 → p ≥ 100 always true) |
| `1889:010d` | — | empty (`push bp / pop bp / retf`; indexed as part of `1899`) |

Seed table far `3A60:0000` (56 words, verified): `23dd 3395 cdf3 c24b e2f7 dfa2 70aa aa60 4b14 4889
2a19 0d6b 0b9e f1fb 0786 5d46 f4ea fd69 446c 271b 71db 8fe3 b4ab 47dc de0f 8e4d 7dfc 388d 4859 6fe3 22aa
262f fa43 a5b5 eb20 85ed c3f5 9f81 9c2d 6db2 2be9 d597 a13d ed89 f4e3 b574 2c00 5fd3 083b f50d 7ef2
70c2 8925 8b2e 5263 2dda`.

`14b8` (sim_flow):

| Address | Name | Behaviour |
|---|---|---|
| `14b8:000d` | `rand_table_init()` | local RNG state: `rng_seed`, `rng_skip(20)`; fill far `3A0D:0000` with 256 words `rng_next()` (called once by `sim_init`) |
| `14b8:0057` | `xor_bytes(u8 *p, int n)` → u8 | XOR of n bytes (callers `33d1:0140/02eb`, `490a:030d`) |
| `14b8:0072` | `rand_table_pair()` → u32 | `DS:5822 += 13; hi = tab[DS:5822 & FFh]; DS:5822 += 13; lo = tab[DS:5822 & FFh]`; returns `hi << 16 | lo` (caller `490a:030d`; `DS:5822` is never reset by sim_flow — it is a free-running index) |

**Borland `rand()`** (`0000:21ed`: `seed = seed·015A4E35h + 1`, returns `(seed >> 16) & 7FFFh`,
seed `DS:3A12/3A14` = 1 at load; `srand` `0000:21dc` has **no callers**) is used by `5254:0161`
(bail-out fate), `644a:0b0c` (cockpit) and `678a:0005` (gauges). It is not part of the VCR
determinism (§9).

---

## 3. Object lists and result globals (`5254:0000 results_init`, from `mission_start`)

```
DS:5CC7 = 0                                   // goal_update phase
zero DS:5CA3..DS:5CC6 (the SIM.OUT image, 36 bytes)
DS:5CA1 = DS:5C9F = 0                         // scores (player, player's flight)
DS:5C8E..5C99, 5C9B..5C9E = 0, DS:5CC9 = 0
buf = 24d3:0059(2·DS:4778)                    // one pointer per object (planes + ships)
lo = buf, hi = buf + 2·DS:4778
for each plane o in DS:475B[0..DS:4776): side(o) == 0 ? *lo++ = o (DS:5CD8++) : *--hi = o (DS:5CD4++)
DS:5CD0 = buf (side-0 planes), DS:5CCC = hi (side-1 planes)
for each ship  o in DS:4759[0..DS:4774): side(o) == 0 ? *lo++ = o (DS:5CD6++) : *--hi = o (DS:5CD2++)
DS:5CCE = start of the side-0 ships, DS:5CCA = hi (side-1 ships)
(an empty list's pointer is set to 0)
```

| DS | Type | Meaning |
|---|---|---|
| 5CD0 / 5CD8 | ptr[] / u16 | side-0 planes / count |
| 5CCC / 5CD4 | ptr[] / u16 | side-1 planes / count |
| 5CCE / 5CD6 | ptr[] / u16 | side-0 ships / count |
| 5CCA / 5CD2 | ptr[] / u16 | side-1 ships / count |
| 5CC7 | u16 | `goal_update` phase 0..3 |
| 5CC9 | u8 | mission over (the player is done: `P.1D & 4` and safe or dead) |
| 5CA1 | s16 | player's score (kills, ships, targets) |
| 5C9F | s16 | player's flight score (wingmen) — not written to SIM.OUT |
| 5C8E | u8 | 1 = final evaluation (set by `results_write`; changes `152e`) |
| 5C8F | u8 | player bailed out (set by the bail-out command, lead §7) |
| 5C90 / 5C91 / 5C92 | u8 | combat near the player: ground targets / ships / aircraft (hysteresis, §4) |
| 5C93 | u8 | combat in progress (ground detail switch, `4b9f:00d0`) |
| 5C94 / 5C95 / 5C96 | u8 | player's bombs/torpedoes hit a target ship: any / class 1 (capital) / class 0, 3, 4 |
| 5C97 | u8 | carrier landing state: 1 landed on the carrier, 2 landed with `P.1C & 8` and not `& 10h`, 3 ditched (`10bf:0039`) |
| 5C98 | u8 | landed at the home airfield |
| 5C99 | near ptr | name of the ace who shot the player down (pilot profile +58h), or 0 |
| 5C9B | u8 | the player was shot down by an ace (pilot index > 44) |
| 5C9C | u8 | the player shot down an ace |
| 5C9D | u8 | the player's fate counts as "aircraft lost" (set by `5254:0161`) |
| 5C9E | u8 | the player was shot down by gunfire (enemy plane or ship, bullet class) |
| 5CA3..5CC6 | 36 bytes | **SIM.OUT image** (§7.4): 5CA3 +00, 5CA5 +02 fate bits, 5CA7 +04, 5CA9 +06, 5CB1 +0E, 5CB3 +10 … 5CC1 +1E, 5CC3 +20, 5CC5 +22 |

`5254:065e` (`results_cleanup`, from `mission_end`) is empty.

---

## 4. Per-frame goal tracking `1899:0012 goal_update()`

One phase per call (phase `DS:5CC7`: 0 → 1 → 2 → 3 → 0), then a common tail. `near(d)` = `d < 25000`
(u32). `minD` = the smallest distance involving the player seen in this phase (u32, starts FFFFFFFFh).
`ok_air(o)` = `!dead(o) && !(o.1B & 80h)`. Object status bits (all in the object; names are
proposals):

| Bit | Name | Set by |
|---|---|---|
| `1C & 20h` | `crippled` | player: `!can_reach_home 69d0:0285(P)`; any plane: damage word `*(u16*)o.2A ≥ 333h` (80 %) |
| `1C & 40h` | `engaged` | an enemy is near, or an enemy flight has it (or its escorted target) as a target |
| `1C & 80h` | `safe` | not engaged (or the player who can still reach home) |
| `1D & 80h` | `in_area` | within 50000 of one of its flight's targets (`13c9`) |
| `1E & 1` | `left_area` | after `in_area`: no longer within 150000 |
| `1D & 2` | `objective` | `objective_done 11aa(o)` |
| `1D & 4` | `done` | objective, crippled or dead |
| `1F & 1` | `contact` | an armed enemy within 25000 (not set for the player once landed, `DS:5C97`/`5C98`) |
| ship `1D & 1` | `unthreatened` | ship with no enemy near / targeting it, not sunk |
| place `1E & 8/1/2` | `contact` / `engaged` / `intact` | as for ships; `intact` = not engaged and damage `0deb:1daf < 400h` |

**Phase 0 — aircraft against aircraft.** `outer` = the larger plane list (side 0 if `DS:5CD8 >
DS:5CD4`, else side 1), `inner` = the other one.
```
for i, A in outer:
    status_prefix(A); A.1C &= ~80h                   // (see below)
    for B in inner:
        if i == 0: status_prefix(B); B.1C |= 80h     // first pass initialises B
        d = dist(B, A); nr = near(d)
        if A == P or B == P: minD = min(minD, d)
        mark_contact(A, B, nr); mark_contact(B, A, nr)
        // B's safe bit after this pair:
        if (B.1C & 80h) and (B.1C & 40h): B.1C &= ~80h
        elif crash_imminent 139f(B) or dead(B) or (B == P and !can_reach_home(B)): B.1C &= ~80h
        if i == 0: update_done(B)
    if !(A.1C & 40h) and !crash_imminent(A): A.1C |= 80h
    elif !dead(A) and A == P and can_reach_home(A): A.1C |= 80h
    update_done(A)
if minD != FFFFFFFFh:  DS:5C92 ? (minD > 30000 → DS:5C92 = 0) : (minD < 8000 → DS:5C92 = 1)
```
`status_prefix(X)`: if `!(X.1C & 20h)`: set it when `(X == P && !can_reach_home(X)) || *(u16*)X.2A
≥ 333h` (order: for the player the reach test first, then the damage word). If `X.1D & 80h`: if
`!(X.1E & 1) && !13c9(X, 150000)` → `X.1E |= 1`; else if `13c9(X, 50000)` → `X.1D |= 80h`. Then
`X.1F &= ~1; X.1C &= ~40h`.
`mark_contact(X, Y, nr)` (Y is the other plane): `y_ok = ok_air(Y)`;
if `!(X.1F & 1) && y_ok && nr && !(X == P && (DS:5C97 || DS:5C98))` → `X.1F |= 1`;
if `!(X.1C & 40h) && y_ok`: `nr` → `X.1C |= 40h`; else if (`targets(Y.flight, X)` or
(`X.flight.02 == 3` and `targets(Y.flight, X.flight.10[0])`)) and `!(Y.1D & 4)` → `X.1C |= 40h`
(`targets` = `10f8`, §6).
`update_done(X)`: if `!(X.1D & 2) && objective_done(X)` → `|= 2`; if `!(X.1D & 4)` and
(`X.1D & 2 || X.1C & 20h || X.1A & 1`) → `X.1D |= 4`.

**Phase 1 — ships against aircraft.** For each side-0 ship S, against every side-1 plane A; then
each side-1 ship against every side-0 plane:
```
S.1F &= ~1; S.1C &= ~40h; S.1D &= ~1
for A: d = dist(A, S); nr = near(d); if A == P: minD = min(minD, d)
    a_ok = !dead(A) and (0deb:1490(A) or 0deb:1500(A) or 0deb:14dc(A) or !(A.1B & 80h))
    if !(S.1F & 1) and a_ok and nr: S.1F |= 1
    if !(S.1C & 40h) and a_ok: nr ? S.1C |= 40h : (targets(A.flight, S) and !(A.1D & 4) → S.1C |= 40h)
if !(S.1C & 40h) and !(S.1B & 2 /*sunk*/): S.1D |= 1
```
Hysteresis `DS:5C91`: set → cleared when `minD > 30000`; clear → set when `minD < 20000`.

**Phase 2 — ground places against aircraft.** For each place Q (`DS:4755`, 20h bytes, count
`DS:476E`) with `Q.1C != 0Dh`: `s = (s8)DS:00C0[Q.1D]` (`465c:00ee`: side of the place's country);
`Q.1E &= ~(8|1|2)`; the planes of the other side (s == 0 → side-1 list, else side-0 list):
`a_ok = !dead(A) and (0deb:1490(A) or 0deb:1500(A) or !(A.1B & 80h))` (no `14dc` here);
`!(Q.1E & 8) && a_ok && nr` → `Q.1E |= 8`; `!(Q.1E & 1) && a_ok`: nr → `|= 1`, else
`targets(A.flight, Q) && !(A.1D & 4)` → `|= 1`. After the planes: if `!(Q.1E & 1)` and
`0deb:1daf(Q) < 400h` → `Q.1E |= 2`. Hysteresis `DS:5C90`: clear when > 45000, set when < 32000.

**Phase 3 — flights.** For each aircraft flight F (`F.00 == 0`) with `!(F.3B & 4)`: over its alive
members (`!dead(m)`): the player sets `pf = 1` if `m.1A & 8`; every other alive member counts `n++`
and, if `m.1B & 80h && !(m.1B & 40h)`, `k++`. If `pf || (n + 1) >> 1 <= k` → `F.3B |= 4` (the flight
has broken off / is going home). Phase back to 0.

**Tail (every call).** Combat detail: if `DS:5C93`: when none of `5C90..5C92` is set → `DS:5C93 = 0`
and `world_detail_apply(slider_value(1))` (lead §4.3); else if any is set → `DS:5C93 = 1` and the
same call. Then if `!DS:5CC9 && P.1D & 4 && (P.1C & 80h || P.1A & 1)` → `DS:5CC9 = 1` (mission over:
the end prompt of `flight_keys` can start, lead §4.5).

`1899:000d` (`goal_init`, from `sim_init`) is empty.

---

## 5. Kill and target credit

### 5.1 `1899:0cf0 kill_credit(Object *killer, Object *victim, int wclass, …, u8 destroyed /*+10h*/)`

Called by the crash/kill code (`088a:054f`). `friendly = side(killer) == side(victim)`.
```
if killer == P:
   if victim.18 == 0 (aircraft):
       if friendly: if destroyed: DS:5CA5 |= 10h            // shot down a friendly aircraft
                    return
       if !destroyed: return
       DS:5CA1 += DAT(victim).7Dh
       if victim.BB > 44 (a named ace): DS:5C9C = 1; DS:5CA1 += 100
       else DS:5CA1 += DS:1930[victim.BB & 3]               // {0, 10, 20, 30}
       DS:5CB9++ (SIM.OUT +16); DS:5CC1++ (+1E)
   elif victim.18 == 1 (ship):
       if friendly: if destroyed: DS:5CA5 |= 20h; return      // sank a friendly ship
       if destroyed: DS:5CA1 += SDAT(victim).98h; DS:5CB7++ (+14); DS:5CBF++ (+1C)
                     if wclass in {bomb, torpedo}: DS:5CB5++ (+12); DS:5CBD++ (+1A)
       elif wclass in {bomb, torpedo}:
           if targets(P.flight, victim): c = SDAT(victim).6Ch
               c == 1 → DS:5C95 = 1; c ∈ {0, 3, 4} → DS:5C96 = 1; DS:5C94 = 1
           if victim.78h == 0: victim.78h = 1500; DS:5CA1 += SDAT(victim).98h >> 1 (sar)
                               DS:5CB5++; DS:5CBD++                // first hit only
elif killer.flight == P.flight (a wingman):
   aircraft: destroyed → DS:5C9F += DAT.7Dh + (BB > 44 ? 100 : DS:1930[BB & 3]); DS:5CC1++
   ship: destroyed → DS:5C9F += SDAT.98h; DS:5CBF++; bomb/torpedo → DS:5CBD++
         not destroyed, bomb/torpedo → the same target flags as above; if victim.7Ah == 0:
         victim.7Ah = 1500; DS:5C9F += SDAT.98h >> 1; DS:5CBD++
elif side(P) != side(killer):
   if killer.18 == 0 and victim == P and destroyed and wclass == bullet:
       DS:5C9E = 1; if (s8)killer.BB > 44: DS:5C9B = 1;
                    pr = DS:55CE[killer.BB]; DS:5C99 = pr.41h ? pr + 58h : 0
   if killer.18 == 1 and victim == P and destroyed and wclass == bullet: DS:5C9E = 1
```
(`victim.78h` / `.7Ah` are per-ship "already credited" words; nothing in sim_flow counts them down.)

### 5.2 `1899:102f target_credit(Object *o, far Target *t, …, int wclass /*+10h*/, …, u8 destroyed /*+16h*/)`

No direct callers (called through a pointer by the weapon impact code, sim_world). `k = t->0 & 1Fh`.
```
if o == P:
    if (side(P) == 0 and k == 2) or (side(P) == 1 and k == 10h):   // own side's ground object
        if destroyed: DS:5CA5 |= 40h
        return
    if destroyed: DS:5CA1 += 0deb:1afc(t)                           // target value
                  if wclass in {bomb, rocket}: DS:5CB3++ (+10); DS:5CBB++ (+18)
elif o.flight == P.flight:
    if destroyed: DS:5C9F += 0deb:1afc(t); if wclass in {bomb, rocket}: DS:5CBB++
```
(Ground object class `2` = side 0's, `10h` = side 1's; the friendly test runs before `destroyed`.)

---

## 6. Goal helpers

| Address | Name | Behaviour |
|---|---|---|
| `1899:10f8` | `targets(Flight *F, void *x)` → u8 | switch `F.43`: 0 → for each reference flight g (`i < F.0E`, `F.10[i]`): `g == x` → 1; any member of g (`g.08[0..g.06)`) `== x` → 1. 1, 2, 3 → any `F.10[i] == x` → 1. Else 0 |
| `1899:139f` | `crash_imminent(o)` → int | `o.0C (i32 altitude) <= 1200 && (s16)o.10 (pitch) < −1820 (F8E4h) && (s16)o.94h > 1200` |
| `1899:13c9` | `near_targets(o, u32 r)` → u8 | `F = o.34`, `p = o.04` (copy): switch `F.43`: 0 → any member m of any reference flight with `277a:5434(&p, &m.04, r)` (within r); 1, 2, 3 → any reference `x` with `5434(&p, &x.04, r)`; returns the last test result (0 when there are none; kind > 3 → 0) |
| `1899:11aa` | `objective_done(o)` → u8 | by the flight role `o.34.02`, below |
| `1899:152e` | `goal_fraction(Flight *F)` → 0..400h | fraction of F's targets destroyed (×1024), below |

`objective_done(o)`, `F = o.34`, `r0 = F.10[0]`:

| Role | Result |
|---|---|
| 0 | `o.1C & 20h` |
| 1 | `17fe:00ed(F + 16h) == 0` (no current waypoint left) |
| 2 | `o.1A & 1` |
| 3 | `goal_fraction(F) == 400h` → 1; else if `0deb:1490(o) || 0deb:1500(o) || !(o.1B & 80h)` → `o.1B & 20h != 0`; else if `F.43 == 1` → 1; else `0deb:14dc(o)` ? (`o.1B & 20h != 0`) : 1 |
| 4 | `goal_fraction(F) == 400h || o.1E & 1 || o.1B & 80h` |
| 5 | `F.43 == 0`: if `r0.00 == 1` (a ship group): `all(m.1D & 1) || all(m.1B & 2)` over its members; otherwise **undefined** (returns the caller's DL — quirk; the port returns 0). `F.43 == 1`: `r0.1E & 2 || 0deb:1daf(r0) == 400h`. `F.43 == 2`: `r0.1D & 1 || r0.1B & 2`. `F.43 == 3`: undefined (DL) |
| 6 | every member m of the flight `r0`: `m.1D & 4 && m.1C & 80h` (1 if the list is empty) |
| > 6 | undefined (DL) |

`goal_fraction(F)` (`me` = `side(P)`, `fin` = `DS:5C8E && !DS:5CC9`):
* `F.43 == 0`, first reference an aircraft flight: over the members m of all reference flights:
  `n += 1`; `sum += 400h` if `dead(m)`, or if `fin && side(m) == me` and (`g == P.flight` ?
  `m.1F & 1` : `!(m.1C & 80h)`). Result `min(satdiv(sum, n), 400h)` (`277a:3dc1`).
* `F.43 == 0`, first reference a ship group: over all member ships m: `v = SDAT(m).98h`; `tot += v`;
  `dm = (fin && side(m) == me && !(m.1D & 1)) ? 400h : *(u16*)m.2A`; `acc += dm == 400h ? v :
  (dm·v) >> 10` (s32). Result `min(satdiv(acc << 10, tot), 400h)`. Other first-reference kinds → 0.
* `F.43 == 1` (a place `r0`): `DS:5C8E && (!DS:5CC9 || 5da1:00cb(P)) && DS:00C0[r0.1D] == me &&
  !(r0.1E & 2)` → 400h; else `min(0deb:1daf(r0), 400h)`.
* `F.43 == 2` (ships): as the ship-group rule over the reference ships.
* `F.43 == 3` (planes): per reference plane as the aircraft rule (`F == P.flight` picks `1F & 1`);
  then **n == 2 → sum >> 2** (quirk: a quarter, not a half), n > 2 → `satdiv(sum, n)`, n ≤ 1 → sum;
  `min(…, 400h)`.

`5254:1301 quartile(f)`: 0 → 0; < 133h → 1; < 2CCh → 2; < 400h → 3; else 4.
Flight counts (5254): `size(g) 5254:1332` = `g ? g.06 : 0`; `active(g) 5254:1348` below;
`lost(g) 5254:1473` = `g ? size(g) − active(g) : 0`.
`active(g)`: `own = (g == P.flight)`; aircraft flight (`g.00 == 0`): members m with `!dead(m)` and
(`DS:5CC9` or `side(m) != side(P)` or (`own` ? `!(m.1F & 1)` : `m.1C & 80h`)). Ship group
(`g.00 == 1`): members with `!(m.1B & 2)` and (`DS:5CC9` or `side(m) != side(P)` or `m.1D & 1`).
Other kinds → 0.
`5254:081e reached_area()`: any member of `P.flight` with `m.1D & 80h`.
`5254:149c aircraft_lost()`: members m of `P.flight` with `dead(m)` or (`m == P && DS:5C9D`) or
(`!DS:5CC9 && m.1F & 1`).

---

## 7. Results `5254` (`results.c`)

### 7.1 `5254:08d9 mission_result(int *code, int *frac)`

`D = P.flight`, `r0 = D.10[0]`. By the mission type `DS:477C` (SCRIPT header +01; jump table
`5254:12eb`); `code` is the 1-based `DEBRIEF.DAT` sentence (shell_data §3.4), −1 = none; `frac` is
the goal completion 0..400h used for merit. Divisions are 16-bit signed `idiv` (a zero divisor
**faults** in the original — `n`, `E`, `S` below can be 0 only in malformed missions; the port
returns frac 0).

* **0 ace duel.** `ownDown = active(D) == 0`; `tgtDown = D.43 == 0 ? active(r0) == 0 : D.43 == 3 ?
  dead(r0) : (uninitialised)`. Code: `!(P.1D & 80h)` → 1; `ownDown && tgtDown` → 2; `!ownDown &&
  !tgtDown` → 3; `tgtDown && DS:5C9C && !ownDown` → 4; `!tgtDown && DS:5C9B` → 5; `tgtDown &&
  !ownDown` → 6; `!tgtDown && ownDown` → 7; else −1. `frac = !tgtDown ? 0 : DS:5C9C ? 400h : 200h`.
* **1 squadron dogfight** / **3 fighter sweep** (`a = lost(D)`, `l = lost(r0)`, `n = size(r0)`,
  `h = (n + 1) >> 1`): type 1: `!reached_area()` → 1; `a == 0 && l == 0` → 2; `a == 0 && l == n` → 3;
  `l == n` → 4; `l == 0` → 5; `h <= l` → 6; `l == 1` → 7; `l > 0 && h > l` → 8; else −1.
  Type 3: `!reached_area()` → 1; `a == 0 && l == n` → 2; `l == n` → 3; `l == 0` → 4; `h < l` → 5;
  `l == 1` → 6; `l > 0 && h >= l` → 7; else −1. Both: `frac = (l << 10) / n`.
* **2 CAP.** `wp = 17fe:00ed(D + 16h) == 0`, `c = lost(D)`, `k = DS:5CC1` (flight kills), `E` =
  enemy plane count (`side(P) == 0 ? DS:5CD4 : DS:5CD8`): `k == 0 && c == 0` → wp ? 1 : 2; `k == 0 &&
  c > 0` → 3; `k < c` → 4; `k == c` → 5; `c + 4 < k` → 6; `c + 1 < k` → 7; `c + 1 == k` → 8; else −1.
  `frac = (k << 10) / E`.
* **4 scramble** / **7 intercept.** `f = goal_fraction(D)`, `q = quartile(f)`, `a = lost(D)`; over all
  other flights G (`DS:4753[0..DS:476B)`, G ≠ D): `t = D.43 == 0 ? (targets(G, m) for some member m
  of r0) : targets(G, r0)`; if t: `L += lost(G)`, `S += size(G)` (the attackers of what we defend).
  Code: `q == 0 && L == S` → (a == 0 ? 1 : 2); else `q + 3` for q = 0..4 (3..7). Frac: type 4 `(400h −
  f)·3 / 4 + ((L << 10) / S) / 4`; type 7 `(400h − f) / 2 + ((L << 10) / S) / 2` (signed halving
  toward zero). `L << 10` is 16-bit (wraps for L ≥ 32).
* **5 training.** Code by `DS:5C97`: 1 → 1, 2 → 2, 3 → 3, 0 → 4, else −1; `frac = 0`.
* **6 escort.** `a = lost(D)`, `al = active(r0)`, `lg = lost(r0)`, `n = size(r0)`, `h = (n+1) >> 1`:
  `lg == 0` → (a == 0 ? 1 : 2); `al == 0` → 3; `h <= al` → 4; `al > 0 && h > al` → 5; else −1.
  `frac = (al << 10) / n`.
* **8 anti-shipping.** Count the target ships (D.43 == 0: members of every reference flight; D.43
  == 2: the reference ships; else none): `T` all, `C` class 1 (`SDAT.6Ch == 1`), `S` classes 0, 3, 4,
  and the sunk ones (`m.1B & 2`) `Ts`, `Cs`, `Ss`. `f = goal_fraction(D)`, `q = quartile(f)`.
  `!reached_area()` → (1, 0). `T == 1`: `Cs == 1 && C == 1` → (2, 400h); `DS:5C95 && Cs == 0 && C == 1`
  → (3, 200h); `Ts == 1` → (4, 400h); `DS:5C94 && Ts == 0` → (5, 199h); `!DS:5C94` → (6, 0); else
  (−1, 0). Else: `q == 0` → (7, 0); `T == Ts` → (8, 400h); `C > 0 && DS:5C95 && Cs == 0` → (9, 200h);
  `C > 0 && Cs > 0` → (0Ah, 333h); `S > 0 && C == 0 && DS:5C96 && Ss == 0` → (0Bh, 200h); `S > 0 &&
  C == 0 && Ss > 0` → (0Ch, 333h); q == 1 → (0Dh, 133h); q == 2 → (0Eh, 200h); q == 3 → (0Fh, 333h);
  else (−1, 0).
* **9 ground attack.** `f = goal_fraction(D)`; `!reached_area()` → 1; else `quartile(f) + 2`
  (2..6); `frac = f`.
* **10 (kamikaze defence, debrief group 7).** `f = goal_fraction(D)`, `q = quartile(f)`, `a =
  lost(D)`: q == 0 → (a == 0 ? 1 : 2); q == 1 → 3; q == 2 → 4; q == 3 or 4 → 5; else −1.
  `frac = 400h − f`.
* **> 10**: code and frac uninitialised (never occurs).

### 7.2 `5254:0161 fate_record(u16 out[5])` → out

Called by the end-of-mission text builder `6210:05e0` (ui part) **before** `results_write`. Output:
`out[0]` fate word, `out[1..2]` far pointer to the player's aircraft name (`DAT(P) + 0Ah`), `out[3..4]`
far pointer to the ace's name (`DS:5C99`) or 0. It also sets the SIM.OUT fate bits `DS:5CA5` and
`DS:5C9D`.
```
ground = (s32)(DAT-model(P.66).98h + P.B8h) >= P.0C          // at or below gear height
nt = DS:477C != 5                                             // not training
a = b = 0; s = (s8)P.AB                                       // player status (sim_world)
if DS:0FEB == 2 or s == 3: s = 3
elif s == 2 or P.1A & 40h or P.1A & 1: s = 2
elif !(P.1C & 10h) and !ground and !DS:5C97 and !DS:5C98 and (DS:0FEB or crash_imminent(P)): s = 2
elif P.1F & 1: s = 2
elif s == 1: s = 1
elif (DS:0FE8 or DS:0FE9 or DS:0FEA or !can_reach_home(P) or health < 200h)
     and !(P.1C & 10h) and !ground and !DS:5C97 and !DS:5C98: s = 1
elif P.flight.03 and P.flight.04->1B & 2 (home carrier sunk): s = 1; nt = 0
else: s = 0
      if !(P.1C & 10h) and !ground and !DS:5C8F and !DS:5C97 and !DS:5C98: nt = 0
      P.flight.03 ? a = 1 : b = 1
   // health = model.90h > 1 ? (P.A4h + P.A6h) >> 1 : P.A4h   (engine condition, sim_world;
   // model = DAT-model P.66, the FMD); "nt = 0" = still airborne, cannot be captured
if DS:5C9E and !DS:5C8F:        w = 1;  DS:5CA5 |= 1; DS:5C9D = 1;  if DS:5C99: w |= 10h, out[3..4] = DS:5C99
elif DS:5C8F (bailed out):      w = 3;  DS:5C9D = 1
     if DS:0FEB: r = rand() & 3;  r == 1 → w |= 20h, 5CA5 |= 1
                                  elif nt and captured() → w |= 40h, 5CA5 |= 2; else w |= 50h, 5CA5 |= 4
     else:       r = rand() % 10; r == 1 → w |= 30h, 5CA5 |= 1
                                  elif nt and captured() → w |= 40h, 5CA5 |= 2; else w |= 60h
elif s != 0:                    w = 2;  DS:5C9D = 1
     s == 3 → w |= 20h, 5CA5 |= 1; elif nt and captured() → w |= 40h, 5CA5 |= 2
     elif s == 2 → w |= 50h, 5CA5 |= 4; elif s == 1 → w |= 60h
else:                           w = 4
     nt and captured() → w |= 40h, 5CA5 |= 2; elif DS:0FEB → w |= 50h, 5CA5 |= 4
     elif DS:5C98 or b → w |= 70h; elif DS:5C97 or a → w |= 80h; else w |= 60h
```
(Order verified against `5254:01e5..0345`: when any of `P.1C & 10h`, `ground`, `DS:5C97`, `DS:5C98`
holds, the `DS:0FEB` / `crash_imminent` test is skipped and only `P.1F & 1` can give 2.)
Fate word: low nibble 1 shot down, 2 crashed / forced down, 3 bailed out, 4 returned; high nibble
10h by an ace (name in out[3]), 20h killed, 30h killed after bailing out, 40h captured, 50h wounded,
60h rescued / unhurt, 70h landed at an airfield (or land-based), 80h landed on a carrier. SIM.OUT +02:
1 killed, 2 captured, 4 wounded (plus 10h/20h/40h friendly fire from §5).

`5254:0663 captured()` → u8: `best = 1 000 000 000`, `cap = 0`; over the ground objects of the far
list `DS:06F3` (far pointer to far pointers, indices `DS:5130 .. DS:512E−1`): `d = dist(P.04,
obj.04)`; class `k = obj->0 & 1Fh`: enemy (`side(P) == 0 && k == 10h` or `side(P) == 1 && k == 2`)
→ `d <<= 1`, flag 1; own (`k == 2` / `10h` the other way) → flag 0; other classes skipped; `d < best`
(unsigned) → `best = d, cap = flag`. Then every ship (`DS:4759[0..DS:4774)`): enemy → `d << 1`,
flag 1, else flag 0, same minimum. Returns `cap` — captured when the nearest (enemy distances
doubled) object is enemy.

### 7.3 `5254:04f1 results_write()`

```
DS:5C8E = 1
mission_result(&code, &frac)
merit = ((s32)DS:4783 · frac) >> 10                 // DS:4783 = SCRIPT header +08: merit value
sc = DS:5CA1 − (DS:5C9E ? 20 : 0)
if P.DDh == 0: for each member m of P.flight, m != P:
    if dead(m) or (!DS:5CC9 and m.1F & 1): sc −= 20        // each lost wingman
sc += 2·merit
if DS:5C98 and !(DS:5CA5 & 2): sc += 10              // landed at the base
if DS:5C97 and !(DS:5CA5 & 2): sc += 30              // landed on the carrier
sc = max(sc, 0); sc = (s32)sc · realism_percent 522c:0038() / 100; sc = min(sc, 900)
SIM.OUT: +00 = code; +03 = 0; +04 = aircraft_lost(); +06..+0D = FFFFh ×4;
         +0E = (P.flight.03 and P.flight.04->1B & 2) ? 1 : 0     // home carrier sunk
         +20 = merit; +22 = sc     (+02, +10..+1E were accumulated during the flight)
sim_out_write(DS:5CA3)                               // 5254:0859
```
`5254:0859 sim_out_write(buf)`: `fopen("SIM.OUT", "wb")` (fatal `results.c` 7DCh), `fwrite(buf, 24h, 1)`
(fatal 7E0h if ≠ 1), `fclose`.

### 7.4 SIM.OUT (36 bytes) — settled from the writer

| Off | DS | Meaning |
|---|---|---|
| 00 | 5CA3 | mission result code (§7.1), 1-based debrief sentence, −1 none |
| 02 | 5CA5 | fate bits: 1 killed, 2 captured, 4 wounded, 10h friendly aircraft shot down, 20h friendly ship sunk, 40h friendly ground target destroyed |
| 03 | 5CA6 | 0 |
| 04 | 5CA7 | aircraft lost in the player's flight (incl. the player when `DS:5C9D`) |
| 06 | 5CA9 | FFFFh ×4 (unused by AP) |
| 0E | 5CB1 | 1 = the player's home carrier was sunk |
| 10 | 5CB3 | player: ground targets destroyed with bombs/rockets |
| 12 | 5CB5 | player: ships hit with bombs/torpedoes (first hit per ship, or sunk by one) |
| 14 | 5CB7 | player: ships sunk |
| 16 | 5CB9 | player: aircraft shot down |
| 18..1E | 5CBB..5CC1 | the same four for the player's flight (the player included) |
| 20 | 5CC3 | merit = header +08 · goal fraction / 1024 |
| 22 | 5CC5 | score 0..900 |

**Corrections to `port/formats/data.md` §1.2**: +00 is the mission result code (not a fate code;
the fate word goes to the end dialog only); +0E is "home carrier sunk" (not a flight flag of the
leader — the test is `flight.03 && flight.04 (base) ->1B & 2`, i.e. the base ship is sunk); +20 is
merit (header +08 scaled by the goal fraction); +22's bonuses are +10 base / +30 carrier landing,
−20 per lost wingman or when shot down, +2·merit.

---

## 8. Autopilot ("skip-ahead", key A) `496a`, `082a`

The "A" key (command 3, lead §5.3) is the **autopilot**: after a short delay it jumps the whole
world forward in one frame — every flight moves along its route by the same time, fuel is burnt,
the time of day advances — until the destination, an encounter or low fuel. The lead's §6.1 calls
it "skip-ahead"; the texts (STR group 1, 27h–34h) name it *Autopilot*.

### 8.1 Driving state (in the sim step `5440:1317`, lead §6.1) — verified

Globals: `DS:069C` state (0 off, 1 engaged/waiting, 2 jump this frame), `DS:069D` view-override
countdown, `DS:069E` free-camera frames, `DS:06A9` frames to wait before A works again, `DS:4382`
wait timer (dt units), `DS:4346` / `DS:433A` the map target at engagement (pointer / 12-byte copy).
* Engage (state 0, `ctl.10 == 3`, `DS:06A9 == 0`): `r = autopilot_check()`; if `r == 8` and
  `w = 17fe:00c9(P.flight + 16h, −1)` exists and `P` is **not** within 50000 of it (`277a:5434`) and
  `17fe:0110(P.flight + 16h, −1)` succeeds → `r = 0` (fall back to the previous waypoint). `r != 0` →
  `autopilot_msg(r, 0)` (reason + "Autopilot is not available now."). `r == 0` →
  `1c30:0ab4(1)`, `1c30:0aca(21h)` (external chase view), `DS:069C = 1`, `autopilot_announce()`,
  `DS:069D = 1`, `DS:069E = 2`, `DS:4382 = 3000`, `085b:02e5(0FA0h)`, `DS:4346 = 6cdc:0db1()` and
  its 12 bytes copied to `DS:433A`.
* State 1, every frame: `r = autopilot_check()`; `r != 0` → `DS:069C = 0`, `1c30:0aca(1Ch)` (front
  cockpit), `autopilot_msg(r, 1)` ("… Autopilot disengaged."). Else: if `DS:069E` →
  `1c30:0aca(28h)` (free camera), `DS:069E--`; `timer16_dec(&DS:4382) == 0` → `DS:069C = 2`. (So
  the jump happens 3000 dt units ≈ 11.7 nominal steps after the key.)
* Any state ≠ 0, first thing in the step: if the map target changed (none ↔ some, or a different
  12-byte target than `DS:433A`, `5440:12f3`): `skip_cancel 5440:12b9`, message STR(1, 34h) "Autopilot
  halted due to path change…", `DS:069D = 2`.
* State 2: `autopilot_jump 496a:170e()`, then `skip_cancel` (`1c30:0aca(1Ch)`, `DS:069C = 0`,
  full redraw, `camera_follow(P)`, `DS:06A9 = 3`).

### 8.2 `496a:0e07 autopilot_check()` → reason (0 = may engage)

| r | Test (in this order) | STR(1, 28h + r) |
|---|---|---|
| 1 | mission type `DS:477C` is 0 or 1 (`496a:0ded`) | "Autopilot is not available in dogfight missions." (no suffix) |
| 2 | `friends_in_danger()` (`0169`) | "Your friends are in danger." |
| 3 | `P.0C <= 1100`, or `P.0C <= 2500` and `(s16)P.10 < −1820` (pitch) | "You're too low." |
| 4 | `low_fuel()` (`0dc7`: `69d0:0174(P)` range left `< 40000`) | "You are low on fuel." |
| 5 | `approach_hit(0, P, 0, 41600, 0)` (`07b5`: an enemy plane within 41600) | "There are nearby enemies." |
| 6 | (only from the jump: a friendly encounter) | "Friendlies encountered." |
| 7 | `5da1:00cb(P)` (damage check, ui part) | "You're damaged." |
| 8 | `destination() == 0` (`0da9`) | "You don't have a destination." |

`496a:0f9b autopilot_msg(r, stopped)`: `buf = STR(1, 28h + r)` (`0000:4b91` copies the far string);
if `r != 1`: append `" "` (`DS:0146`) and STR(1, stopped ? 28h "Autopilot disengaged." : 27h
"Autopilot is not available now.") (`0000:4b22` strcat); `1614:024e(buf, 1, 0, 0)` (message line).
`496a:0f65 autopilot_announce()`: map target set → STR(1, 33h) "Proceeding to selected destination.";
else `waypoint_text(2)`.
`496a:0ef5 waypoint_text(n)`: `t = 69d0:00f2(P.flight)` (far text of the current waypoint); if t:
copy it, `p = field(buf, n)` (`0eb4`: skips n `|`-separated fields, 0 if missing), terminate p at the
next `|` (`368f:020a`); if `t == 0` → p = "Bad path text" (`DS:0138`); if p: `1614:024e(p, 1, 0, 0)`.
`496a:0da9 destination()` → `6cdc:0db1()` (map target) or else `69d0:00de(P.flight)` (current
waypoint position). `496a:0dc7 low_fuel()` as above; `496a:0ded dogfight_mission()` as above.

Helpers (`d2` = `ldist2` `277a:3bfc`, horizontal):

| Address | Name | Behaviour |
|---|---|---|
| `496a:0005` | `three_quarters(i32 x)` | `x − (x >> 2)` |
| `496a:0022` | `nearest(i32 *d, lvec *p, Object **l, int n)` → Object* | minimum `d2(p, &o.04)` (strictly less, start 7FFFFFFFh); `*d` = it (if d) |
| `496a:008a` | `charge_in_danger(o)` → u8 | if `!1142:0000(o)` and `!(o.1D & 2)` and `near_targets(o, 50000)` → 1; else enemies = `4edf:1711(buf, side(o) == 0 ? 1 : 0)`; `nearest(&d, &o.04, buf, n)`; `d < 30000` |
| `496a:0106` | `clear_danger_marks()` | `bits_clear(DS:475B, DS:4776, 2Bh)` (all planes: `1F & 8`) |
| `496a:011d` | `mark_charges()` | if `P.flight.02 == 6` (escort): each member m of `P.flight.10[0]` with `charge_in_danger(m)` → `m.1F |= 8` |
| `496a:0169` | `friends_in_danger()` → u8 | escort role only: `mark_charges()`; g = the escorted flight; if `bits_clear(g.08, g.06, 2Bh) != 0` and `nearest(&d, &P.04, g.08, g.06)` with `d < 30000` → 1; `clear_danger_marks()` |
| `496a:0d4c` | `bits_clear(Object **l, int n, int bit)` → count | for each object: byte `o.1A + (bit >> 3)`, mask `1 << (bit & 7)`: if set, clear it and count |
| `496a:01cf` | `burn_fuel(o, i32 dist)` | `f = o.28` (fuel rates), `t = o.2A` (fuel block); the player with realism fuel off (`DS:42CE == 0`) → nothing. `v = ((0b01:1a28(o.66, 10) · 69d0:0129(o)) + 3FFh) >> 10`; `v = (v · DS:3F22) >> 10` (distance per frame, 70/1024); 0 → 1; `frames = ldiv(dist, v) >> 1`; drop tank `t.10 != 0` → `t.10 −= f.0C · frames` (floor 0), else main `t.0C −= f.0A · frames` (floor 0) |
| `496a:02c9` | `mark_cluster(lvec *p, Object **l, int n, int bit, u32 r)` | objects within r of p get `1F |= 4` and `bit`; then repeatedly every unmarked object within r of a marked one gets them too, until nothing changes; finally `bits_clear(l, n, 2Ah)` (removes the temporary `1F & 4`) |
| `496a:0400` | `save_positions(u8 buf[16·planes])` | per plane: `buf[i] = {pos (12), .A4h, .A6h}`, `.56 |= 4`; `DS:3F00` = max `DAT.73h`; per aircraft flight (`DS:474F[0..DS:4763)`): L = leader (`583c:1a55`), members ≠ L, ≠ P with `d2(m, L) != 0` → `m.1D |= 8` (out of formation), others `&= ~8`; carrier-based flights with a member in state `+4Ah == 3CCh`: members in state 3CCh/3F4h (not P, alive `!4edf:0619`) → `m.0C = 10000`, `4edf:0edb(m)` (launched) |
| `496a:05ca` | `finish_positions(buf)` | per plane: if `ldist3(buf[i].pos, o.04) > 500` → `o.10 = o.12 = 0`, `o.14 = 3629:0004(buf pos, o.04)` (bearing of the move); `4edf:01c7(o, o.B2)`; `o.56 &= ~4`; if `o.0C > 400` and the gear state byte `[o.16]+1 != 0` → `o.1D |= 10h`, `o.BA &= ~10h` (gear up). Then `DS:3FEF &= ~8`, `DS:06B5 = 0` (gear animation), `10e5:04e1()`, every flight `.3A &= ~40h`, `bits_clear(DS:475D, DS:4778 + DS:4772, 11h)` (`1C & 2`) |
| `496a:06b8` | `jump_flight_ok(F)` → u8 | mode `DS:3F04`: 1 → friendly flights (`F.42 + side(P) != 1`), 2 → enemy flights, 0 → all; never carrier task groups (`F.3B & 2`) or stopped flights (`F.3A & 40h`) |
| `496a:070e` | `nearest_enemy(o, i32 *d)` → Object* | over `DS:475D[0..DS:4778)`: not `1F & 2`, opposite side, alive (`!4edf:0619`); min `d2`, start 1 000 000 000 |
| `496a:07b5` | `approach_hit(lvec *hit, o, lvec *to, i32 r, u8 ships)` → Object* | over planes (and ships if `ships`) not `1F & 2`: candidates are enemies, or members of a carrier task group that `o`'s flight targets (`o.34.10 == x.34`); alive. Radius `r` (carrier groups: `three_quarters(26000)` = 19500). With `to`: `082a:010e(&pt, &x.04, r, &o.04, to)` hit → `dist = d2(o.04, pt)`; without: `d2(x.04, o.04) < r` → dist. Minimum (start 1 000 000 001) → returns the object, `*hit = pt` |
| `496a:093c` | `advance_point(lvec *out, lvec *from, lvec *to, i32 d)` → i32 | `D = ldist3(from, to)`; `d >= D` → `*out = *to`, return 0; else `*out = 082a:0007(from, d, from, to)` (point at distance d, bisection) and return `D − d` |
| `496a:09a8` / `09c6` | `move_dist(o)` | `o.34.30 · DS:3F02` (cruise speed × jump time) / ship `SDAT.4Ah · DS:3F02` |
| `496a:09f8` | `set_level(o, hdg)` | `o.10 = o.12 = 0; o.14 = hdg` |
| `496a:0a0a` | `ship_advance(s, lvec *to, hdg)` | `r = advance_point(&t, &s.04, to, move_dist(s))`; `r < 300` → `s.04 = *to`, `s.14 = hdg`; else `s.04 = t` |
| `496a:0a8e` | `place_object(o, lvec *p)` | aircraft: `burn_fuel(o, d2(o.04, p))`; `o.36 = o.04` (previous position); `o.04 = *p` |
| `496a:0ae8` | `fly_toward(o, lvec *to, u16 ang[3])` | `r = advance_point(&t, &o.04, to, move_dist(o))`; `r < 300` → `t = *to`, and if `ang`: `set_level(o, ang[2])`; `place_object(o, &t)` |
| `496a:0b63` | `near_old_or_new(lvec *p, o, u32 r)` → 0/1/2 | 1 if `d2(p, o.36) < r`, 2 if `d2(p, o.04) < r`, else 0 |
| `496a:0bbe` | `free_to_move(o)` → u8 | `!(o.1C & 2) && !(o.34.3A & 40h)` |
| `496a:0be3` | `stop_flight(o)` | `o.34.3A |= 40h` and the same for every linked flight (`F.44` count, `F.46` list); `o.1C |= 2` |
| `496a:0c14` | `engage_scan(i32 r)` → i32 | over all pairs of objects (`DS:475D`, planes + ship groups) of opposite sides with at least one `free_to_move`: `d = d2`; `d < r` → each of the two without `1C & 4` gets `stop_flight`, one with `1C & 4` (linked to the player's flight) sets a flag; pairs that are far, or near with the flag, update `min(d)` (start 10 000 000); returns the minimum |
| `496a:0eb4` | `field(char *s, int n)` | pointer after the n-th `|` (0 if there are fewer) |
| `496a:1020` | `regroup(F)` | members ≠ leader, alive: `place_object(m, formation slot 4edf:12b3(&p, L, 4edf:1294(m)))` |
| `496a:1096` | `regroup_player_flight()` | as `regroup(P.flight)` but only members within 60000 (EA60h) of the leader |
| `496a:112e` | `place_relative(A, B, i16 off[3])` | `LB.04 = LA.04 + rotate(off, matrix(LA.20))` (`365a:000c`, `277a:4ae5`, `277a:5368`); `regroup(B)` |
| `496a:118f` | `jump_air_flight(F)` | §8.3 |
| `496a:1487` | `jump_ship_group(F)` | `w = 17fe:00ed(F.16)` (current waypoint) or return; marker `M = F.2E`: `ship_advance(M, w, 3629:0004(w, &M.04))`; `5058:010b(M, F.16)`; each member ship s alive: `s.04 = M.04 + 3666:0073(s.68 offset, matrix(M.20))` |
| `496a:153f` | `jump_flights(mode, i16 t)` | `DS:3F04 = mode, DS:3F02 = t`; each flight `DS:4751[i]` with `jump_flight_ok`: kind 0 → `jump_air_flight`, else `jump_ship_group`; then both globals = 0 |
| `496a:15a8` | `limit_time(i16 *t, i32 *dist, i32 d, i16 spd)` → int | `q = satdiv(d, spd ? spd : 1)`; `q == 7FFFh` → `d = spd·7FFFh`; if `*t < 0 || q < *t` → `*t = q, *dist = d`, return 1; else 0 |
| `496a:160c` | `dest_is_target(lvec *dest)` → u8 | mission type 6 (escort): leader of the escorted flight moved to `dest` with z 0, `near_targets(L, 10000)`, position restored (no leader → `618d:04e4(1)`, 0); types 8, 9: the same with P; else 0 |
| `082a:0007` | `bisect_radius(lvec *out, lvec *c, i32 r, lvec *a, lvec *b)` | endpoints ordered (nearer to c first by `d2`); up to 12 times: `m = lmid(p0, p1)` (`277a:53e2`), replace p1 if `d2(c, m) > r` else p0; stop when `|d2(c, m) − r| < 5`; `*out = m` |
| `082a:010e` | `segment_circle(lvec *out, lvec *c, i32 r, lvec *a, lvec *b)` → out / 0 | 2-D: both ends inside → the end farther from c; one inside → `bisect_radius`; both outside: angles `atan2_32` of `c − b`, `b − a`… — if c is not "between" (either angle difference ≥ 4000h) → 0; perpendicular distance `mul_sin(|a–c| normalised, diff)` ≥ r → 0; else the projection of c on the segment (`mul_cos`) and `bisect_radius(out, c, r, a, proj)` |

### 8.3 `496a:170e autopilot_jump()`

```
if P.4Ah != 458h: return                              // not in normal flight
DS:3EFE = (6cdc:0db1() != 0); DS:3EFF = 0; arrived = 1; low = 0; far_esc = 0
if P.flight.02 == 6 and !DS:3EFE and nearest(&d, &P.04, esc.08, esc.06) with d > 30000: far_esc = 1
mark_charges()
T0 = 26000 − 3000                                      // 5058:0000() = 26000 (engagement range)
dest = *destination()
stop = dest_is_target(&dest) ? 50000 : 20000
L = 583c:1a7c(P) ? P : 583c:1a55(P.flight)            // the player or his leader
mark_cluster(&P.04, ships, DS:4774, 29h, 35000)       // ships near the player: 1F & 2 (left alone)
save_positions(buf)
loop:
    spd = P.flight.30; t = −1
    d = max(engage_scan(T0) − T0, 10000);        limit_time(&t, &dist, d, spd)
    d = d2(L.04, dest) − stop; if d < 0: break    // arrived
    d = max(d, 800); d = min(d, max(69d0:0174(P) − 40000, 10000))
    limit_time(&t, &dist, d, spd); limit_time(&t, &dist, 250000, spd)
    advance_point(&to, &L.04, &dest, dist)
    e = approach_hit(&hit, L, &to, 26000, 1)
    if e and !limit_time(&t, &dist, d2(L.04, hit), spd): e = 0
    jump_flights(1, t)                            // friendly flights
    dest = *destination(); 6964:0000(t)           // time of day
    if e: break
    low = low_fuel(); if low: break
    engage_scan(T0); jump_flights(2, t)           // enemy flights
    dest = *destination()
    e = nearest_enemy(L, &nd); if e and nd < T0: break; e = 0
    if d2(L.04, dest) < stop: break
clear_danger_marks(); bits_clear(ships, DS:4774, 29h)
finish_positions(buf); 085b:02e5(0F00h)
for each aircraft flight G with G.02 == 6 (escort) whose leader and escorted leader exist and are
    within 80000 (d2): E = G.10[0]
    E == P.flight → place_relative(E, G, {4000, −6000, 1000})      // escort joins the player
    G == P.flight → if DS:3EFF and !far_esc: place_relative(G, E, {−4000, 6000, −1000})
    else          → place_relative(G, E, {−4000, 6000, −1000})
regroup_player_flight()
if e or low: if d2(L.04, dest) > 40000: arrived = 0
             e ? autopilot_msg(side(e) + side(P) == 1 ? 5 : 6, 1) : autopilot_msg(4, 1)
if arrived: DS:3EFE ? (6cdc:0de1(0); message STR(1, 32h) "You have reached your selected destination.")
                    : (waypoint_text(0); 17fe:0110(P.flight + 16h, 1))   // next waypoint
```
Units: `t` = time in nominal frames (distance / cruise speed `F.30`, distance per frame); each
flight moves `F.30 · t` along its route. `6964:0000(t)` advances the sun/time of day (render3d).

`496a:118f jump_air_flight(F)`: `L = leader(F)`; return unless L, `free_to_move(L)` and
`!(L.1F & 8)`. State `s`: other flights `4edf:0c45(L, 1)` (their AI behaviour); the player's flight:
map target → 9999 (270Fh); else `4edf:0c45(L, 1)`, and 0 → `DS:3EFF = 1`, s = 3.
* s 0 (formation on a flight): `off` = 3 words at far `F.52 + 28h` (script record), `T = leader(F.10[0])`,
  `p = 4edf:12b3(T, off)`; `near_old_or_new(&L.04, T, 20000)` → `place_object(L, p)`, `set_level(L,
  L.14)`; else `fly_toward(L, p, &T.10)`. moved.
* s 1: `fly_toward(L, 69d0:007d(F), 0)`. moved.
* s 3 / 9999: `ang = *(u16(*)[3])DS:3716`; `w` = 9999 ? `destination()` : `17fe:00ed(F.16)`;
  `ang[2] = 3629:0004(w, &L.04)`; `fly_toward(L, w, ang)`. moved.
* s 5 (escort): as s 0 with `T = leader(F.3E)` and radius 15000. moved.
* s 6: each member `4edf:057f(m, m.BC)` (parked on the deck). Other s: nothing.
Then unless s == 9999 `5058:0010(L)`; if moved: each member m ≠ L, alive: `p = 4edf:12b3(L,
4edf:1294(m))`; `m.1D & 8` → `fly_toward(m, p, &L.10)`, else `place_object(m, p)`,
`set_level(m, L.14)`.
`496a:0000` (`autopilot_init`, from `sim_init`) is empty.

---

## 9. Port notes

* The RNG (§2) and the goal tracking must be bit-exact for film playback (the VCR re-simulates;
  `goal_update` feeds `DS:5CC9` and the ground detail switch, which is part of the sim state through
  `4b9f:00d0` → `333b:0158`).
* `rand()` (Borland LCG, seed 1, never reseeded) decides the bail-out fate and is also consumed by
  the cockpit (`644a:0b0c`) and the gauges (`678a:0005`), so the fate differs between a flight and
  its replay. Faithful port: one shared LCG with seed 1 for the process lifetime and the same call
  sites. The fate is decided once (the end dialog) and written to SIM.OUT; a replay does not rewrite
  SIM.OUT unless "SEE MISSION REVIEW" is chosen.
* Division by zero in `mission_result` (§7.1) faults in DOS; `/* PORT: */` return frac 0.
* The undefined `objective_done` cases (role 5 with a non-ship first reference, role > 6) return
  the caller's DL; `/* PORT: */` return 0 (no shipped mission is known to use them — *guess*).

## 10. Hand-offs

* **sim_world**: object status bits written by `goal_update` (§4: `1C & 20h/40h/80h`, `1D & 80h/2/4`,
  `1E & 1`, `1F & 1`, ship `1D & 1`, place `1E & 1/2/8`, flight `3B & 4`) — the AI reads several of
  them (`1B & 80h/40h/20h` are sim_world's own). `kill_credit 1899:0cf0` is called from `088a:054f`
  with (killer, victim, weapon class, …, destroyed at +10h); `target_credit 1899:102f` is reached
  through a pointer (weapon impacts). Ship words `+78h`/`+7Ah` are the player/flight hit-credit
  markers. `DS:5C97` is written by `10bf:0039` (3 = ditched) and `5440:0aee`.
* **shell_data**: SIM.OUT meanings above (§7.4) — +0E = home carrier sunk (the shell advances the
  career date), +20 merit = header +08 × completion; header +08 = mission merit value.
* **formats (data.md §1.2)**: corrections listed in §7.4.

## 11. Open questions

* `P.AB` status values 1..3 (sim_world) and `DS:0FEB == 2`.
* `obj.1B & 80h` / `& 40h` / `& 20h` (read here, set by sim_world: likely "going home", "fleeing",
  "ordnance expended").
