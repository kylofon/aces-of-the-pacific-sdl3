# sim_world — flight model (`0b01`, `4bf9`, `362b`, `.FMD`)

Part of the `sim_world` spec (index: `sim_world.md`). Scope: the aircraft flight model of AP.EXE —
the full model used for the player (`0b01:0134`), the simplified model used for AI aircraft
(`0b01:1d33`), the per-aircraft step and control layer (`4bf9`), the frame-time scaling helpers
(`362b`) and the `.FMD` data. Target `work/AP_flat.exe`, DGROUP `3EA4`. Everything was read from
the Ghidra decompile and checked against `tools/x86dis.py` where arithmetic matters (tags
**verified** = read in the disassembly, **likely**, **guess**).

## 1. Overview

Every aircraft object (`Plane`, 0x107 bytes, `sim_world.md` §3) carries:

* a **posture** at `Plane+02` (the 3Space object's position and angles, see §2.1): i32 x, y, z
  (`z` = altitude, up), u16 pitch, roll, heading;
* a **flight-model state** `FmState` at `Plane+64` (0x48 bytes, §2.2), whose word 0 points back to
  the posture and word 1 to the aircraft's `.FMD` (214 bytes, §2.4);
* a **controls block** `Controls` at `Plane+AC` (§2.3): aileron, elevator, rudder, throttle, mass,
  ground height, flap/brake/gear bits — written by the player's input code (sim_flow) or by the AI
  steering primitives of `4bf9` (§4).

Per frame each flying aircraft's behaviour handler (the `4edf` state handlers reached through the
`3cdd` thunks, the AI routines, ships' planes on deck…) ends up in `plane_fly` `4bf9:0257`, which
picks the model and calls `fm_step` `0b01:1860`:

```
plane_fly 4bf9:0257 (Plane *p)
 ├ player: mode = fm_mode_by_realism[DS:42D3] (DS:02CE = {1,2,3}); AI: mode 4
 ├ clamp aileron/elevator/rudder to ±0x100 (277a:3f27)
 ├ AI only: coordination factor k (0x3B6..0x400) from the pilot profile and DS:42D2
 ├ 365a:000c  (rebuild the orientation matrix pointer)
 ├ fm_step 0b01:1860 (&p->fm, &p->ctl, mode, k, 0, wings_level_hold)
 │    mode 4  -> fm_simple 0b01:1d33
 │    mode 1-3-> copy FMD to DS:568E, apply the realism edits, fm_full 0b01:0134
 │               (twice with half the time step if DS:711E >= 100h)
 ├ p->ctl_request (Plane+C1) = 0
 └ plane_engine_sound 4bf9:0017 (player engine note, gear touch, fly-by sound; sound hooks)
```

`fm_full`/`fm_simple` in one call: control surfaces → angular rates (rate targets with separate
acceleration limits per direction), ground handling, orientation update through a rotation matrix,
angle of attack and sideslip from the body velocity, lift, side force, thrust, drag, gravity,
acceleration = force·1024/mass, body velocity integration with fractional carries, body → world
velocity, position integration (trapezoid of old and new world velocity), ground contact /
landing test, stall/overspeed flags.

### 1.1 Time base (as used here)

The frame loop (sim_flow, `5b93:01ed`, `5cde:0405`) calls `362b:008f(ticks)` once per frame; it sets
**`DS:711E` = frame time scale, 100h = one nominal frame**: `clamp((ticks << 8) / DS:7118, 40h,
1C2h)` (`362b:005b`, a saturating division), with `DS:7118` = nominal ticks per frame (set by
`4b9f:0000` from a slider, 1 after `362b:002d`). `DS:711A` is the same with `DS:3712`,
`DS:711C = log2-ish(DS:711E) − 7` (`3684:00a1`), `DS:7116` = last ticks. All per-frame rates in
sim_world are multiplied by `DS:711E/256` through the `362b` helpers (§5). The flight model runs
once per frame with `DS:711E` as is when `DS:711E < 100h`, else **twice with `DS:711E >> 1`**
(`0b01:1860`), then restores it.

Two further constants, set once by `56ac:010b` (scenario init): **`DS:3F22` = 46h (70)**, the
distance-per-frame scale of velocities (position += v·70/1024 per nominal frame, `0b01:1c4f`,
`0b01:1cb5`) and **`DS:3F24` = 42h (66)**, gravity (force units per 1024 mass).

### 1.2 Units (likely)

| Quantity | Encoding |
|---|---|
| Angles | u16 binary angles, 10000h = 360°; pitch +up, roll, heading. `4000h` = 90° |
| Position | i32 world units; altitude band table `DS:1442` = 10000, 30000 … 170000 (9 breakpoints 20000 apart). If a unit is ¼ ft the bands are 2 500 … 42 500 ft (consistent with FMD ceilings `+B0`: B-29 134 400 = 33 600 ft) — **guess** |
| Velocities | body `FmState[17h..19h]` (lateral, forward, vertical), world `[1Ah..1Ch]` (x, y, z); position per nominal frame = v·70/1024 |
| Angular rates | binary-angle units per nominal frame (scaled by `DS:711E/256` when applied) |
| Controls | aileron/elevator/rudder ±100h (±1.0), throttle 0..100h, mass (FMD-independent, from the aircraft `.DAT`), force/1024 |
| Coefficients | mostly 1.0 = 400h (`>>10` products) |

## 2. Data structures

### 2.1 Posture (`Plane+02`, used through `FmState.posture`)

| Off (posture) | Off (Plane) | Type | Meaning |
|---|---|---|---|
| +00 | +02 | u16 | (3Space object word: shape/model handle, not used by the FM) |
| +02 | +04 | i32 | x |
| +06 | +08 | i32 | y |
| +0A | +0C | i32 | z = altitude (compared with ground height + gear height) |
| +0E | +10 | u16 | pitch |
| +10 | +12 | u16 | roll (|roll| folded: `if |r| > 4000h: 7FFFh − |r|`) |
| +12 | +14 | u16 | heading (yaw rate is added here) |

### 2.2 `FmState` (`Plane+64`, 0x48 bytes; zeroed and initialised by `fm_init` `0b01:00d0`)

| Word | Off | Plane | Meaning |
|---|---|---|---|
| 0 | +00 | +64 | posture pointer (`Plane+02`) |
| 1 | +02 | +66 | `.FMD` pointer (temporarily DS:568E during `fm_full`) |
| 2 | +04 | +68 | orientation matrix pointer (3Space 19-byte matrix: 9 × i16 2.14 + 1 flag byte) |
| 3–5 | +06 | +6A | body velocity per nominal frame (`[17h..19h]·DS:3F22 >> 10`, `0b01:1cb5`) |
| 6–8 | +0C | +70 | world velocity per nominal frame x, y, **z (+74 = climb rate, used by the AI)** |
| 9 | +12 | +76 | roll rate |
| 10 | +14 | +78 | pitch rate |
| 11 | +16 | +7A | angle of attack α = `atan2(v_fwd, −v_vert)` (`277a:6228`) |
| 12 | +18 | +7C | (not written by the FM) |
| 13 | +1A | +7E | filtered lift (8000h = none) |
| 14 | +1C | +80 | filtered side force (8000h = none) |
| 15–17 | +1E | +82 | 10-bit fraction accumulators of the three velocity components (`0b01:1b9b`) |
| 18 | +24 | +88 | fraction accumulator of the lateral drag |
| 19 | +26 | +8A | fraction accumulator of thrust − forward drag |
| 20 | +28 | +8C | fraction accumulator of the vertical drag |
| 21 | +2A | +8E | yaw rate (smoothed in `fm_full`) |
| 22 | +2C | +90 | (simple model) yaw rate from roll coupling |
| 23–25 | +2E | +92 | **body velocity**: lateral u, forward v (airspeed), vertical w |
| 26–28 | +34 | +98 | **world velocity** x, y, z |
| 29–31 | +3A | +9E | 10-bit fraction accumulators of the position (`0b01:1c4f`) |
| 32 | +40 | +A4 | engine 1 power factor (400h = 100 %; set to 400h by `fm_init`, lowered by damage) |
| 33 | +42 | +A6 | engine 2 power factor (used when FMD `+90` ≥ 2) |
| 34 | +44 | +A8 | prop torque factor (roll input `+= torque·throttle >> 8` unless flag 4) |
| 35 lo | +46 | +AA | **flags**: 01 stalled / departed, 02 near stall (warning), 04 recovery latch, 08 overspeed warning, 10 overspeed (over FMD `+AE`) |
| 35 hi | +47 | +AB | **landing/ground-contact damage level** 0..3 (`fm_ground_contact` `0b01:2d9c`) |

### 2.3 `Controls` (`Plane+AC`, int[8] + bytes)

| Idx | Off | Plane | Meaning |
|---|---|---|---|
| 0 | +00 | +AC | aileron (stick x) ±100h |
| 1 | +02 | +AE | elevator (stick y) ±100h |
| 2 | +04 | +B0 | rudder ±100h (the FM uses −rudder) |
| 3 | +06 | +B2 | throttle 0..100h (0 = engine off) |
| 4 | +08 | +B4 | ? |
| 5 | +0A | +B6 | **mass** (force divisor, `force << 10 / mass`); `fm_step` mode 1 temporarily uses 400h |
| 6 | +0C | +B8 | ground height under the aircraft (terrain/deck); ground level = FMD `+98` (gear height) + this |
| 7 lo | +0E | +BA | bits: 0–1 flaps (0, 1 half, 2 full), 2 dive brakes (FMD `+C8`), 3 wheel brakes (FMD `+CA`, on ground), 4 **gear down** (FMD `+C2`) |
| — | +15 | +C1 | u16 AI request bits for `plane_fly`: 01 fixed coordination 400h, 02 force mode 1, 08 wings-level hold when |roll| ≤ 5000, 10 coordination 0 (cleared every frame) |

### 2.4 `.FMD` — flight model data (214 bytes, 46 files) — layout **verified by use**, meanings likely

Loaded whole by `acedata_load_aircraft` `45cc:034f` into a near block; pointer at aircraft `.DAT`
image `+24` and in `FmState.fmd`. "band table" = 9 values at the altitude breakpoints of
`DS:1442` (10000 … 170000 step 20000); the FM interpolates between entry *i* and *i+1*, *i* =
`alt_band(z)` (§3.8).

| Off | Type | Name / meaning | Values (B-17D, F4U, Zero-22, P-51) | Used in |
|---|---|---|---|---|
| 00 | i16 | version? (always 2) | 2 | — |
| 02 | i16 | **stall AoA** (α above which the aircraft stalls; ¾ of it = warning) | 3276 (18°) | full, simple |
| 04 | i16[9] | **lift coefficient** per band | 357…368 / 576…206 | lift |
| 16 | i16[9] | **side-force coefficient** per band (all 30) | 30 | side force |
| 28 | i16 | **max thrust** (× throttle >> 8) | 36 / 59 / 57 / 72? | thrust |
| 2A | i16[9][3] | **drag coefficients** per band: +0 lateral (150), +2 forward (9–26), +4 vertical (150) | 150, 12, 150 | drag |
| 60 | i16 | ground rolling drag (10) | 10 | forward drag on ground |
| 62 | i16[9] | **control effectiveness** per band (400h = 1.0; 700–1024) | 1024…700 | scales stick/rudder |
| 74 | i16 | roll acceleration toward/away (same sign) | 500 / 1166 / 1400 | |
| 76 | i16 | roll acceleration against the current rate (×2 in the simple model) | 1000 / 2333 / 2800 | |
| 78 | i16 | pitch acceleration (same sign) | 160 / 346 | |
| 7A | i16 | pitch acceleration (reversing) | 321 / 692 | |
| 7C | i16 | **max roll rate** (×stick >> 8) | 2000 / 4666 / 7000 | |
| 7E | i16 | **max pitch rate** | 642 / 1384 | |
| 80 | i16 | yaw from sideslip (weathervane) | 160 | yaw |
| 82 | i16 | roll input boost (added ±stick·k/1024) | 0 / 102 / 153 | |
| 84 | i16 | pitch-from-AoA correction (auto trim) | 60 | pitch target |
| 86 | i16 | auto roll-levelling rate below 2000h pitch | 200 / 100 / 0 | roll |
| 88 | i16 | bank angle above which sideslip yaw fades (6000) | 6000 | yaw |
| 8A | i16 | throttle yaw (torque yaw) | 0 | yaw |
| 8C | i16 | (0; zeroed by mode 1) | 0 | — |
| 8E | i16 | stall possible (1); copy: `DS:571C` = 1 | 1 | stall |
| 90 | i16 | **number of engines** (≥ 2: thrust uses the mean of both engine factors) | 4 / 1 | thrust |
| 92, 94 | i16 | (1200, 10000 …; 0 for many; zeroed by mode 1) — not used by the FM | | ? |
| 96 | i16 | 4200 | | — |
| 98 | i16 | **gear height** above ground (49–81) | 75 | ground |
| 9A | i16 | **ground (three-point) pitch** (0 = tricycle: B-24, B-25, B-29) | 1092 / 1638 / 2002 | ground |
| 9C | i16 | 0 | | — |
| 9E | i16 | landing: max forward speed for damage level 1 (1500; ×2 → 3) | 1500 | 2d9c |
| A0 | i16 | landing: max sink rate (200; ×2, ×4 → levels) | 200 | 2d9c |
| A2 | i16 | landing: max |roll| (4000) | | 2d9c |
| A4 | i16 | landing: max pitch (4000) | | 2d9c |
| A6 | i16 | landing: min pitch (−1050 / −2100) | | 2d9c |
| A8 | i16 | ground attitude return rate (440) | | ground |
| AA | i16 | **lift-off speed**: on the ground, controls act only above it (307) | | ground |
| AC | i16 | ground turn (nose-wheel) drag factor (7) | | drag |
| AE | i16 | **never-exceed speed** (0 = none: bombers); over it flag 10h, over 7/8 flag 8 (only if `DS:576B`) | 0 / 5880 / 6240 / 7200 | overspeed |
| B0 | i32 | **ceiling**: lift fades over the last 2600 units below `ceiling+1496` | 65536−8672 = 56864 | lift |
| B4 | i16 | 500 | | — |
| B6 | i16 | roll→yaw coupling (right) | 222 / 545 / 600 | yaw |
| B8 | i16 | roll→yaw coupling (left) | same | yaw |
| BA | i16 | pitch damping from heading change (23–45) | | lift |
| BC | i16 | small-angle snap: |roll| below it is zeroed when idle (160) | | |
| BE | i16 | **engine torque roll** (850) | | roll |
| C0 | i16 | speed above which all controls are ¼ (6720) — zeroed by mode 1 | | |
| C2 | i16 | **gear drag** (2–6) | | drag |
| C4 | i16 | **flap drag** (full; half = >>1) | | drag |
| C6 | i16 | speed above which aileron is ¼ (0 = never) | | |
| C8 | i16 | **dive-brake drag** (D3A 28, D4Y 21, else 0) | | drag |
| CA | i16 | wheel-brake drag (60) | | drag |
| CC, CE | i16 | thrust fades linearly from 100 % at speed `CC` to 0 at `CE` (propeller limit) | 5160, 7800 | thrust |
| D0, D2 | i16 | drag rises linearly ×1 → ×2 between speeds `D0` and `D2` (compressibility) | 5160, 13560 | drag |
| D4 | i16 | lift AoA offset (zero-lift angle, −576) | −576 | lift |

`fm_step` modes 1 and 2 (realism "flight model" easy / medium) edit a copy of this record, §3.1.

## 3. Functions of `0b01` (flight model core)

### 3.1 `0b01:1860 fm_step(FmState *fm, Controls *ctl, int mode, int coord, int p5, int level_hold)` — verified

```
saved_mass = ctl[5]
if mode == 4: fm_simple(fm, ctl, level_hold, coord, p5); return
fmd_saved = fm->fmd
memcpy(DS:568E, fm->fmd, 0xD6)            // SCOPY@ 0000:1c7a
fm->fmd = DS:568E
DS:571C (= copy+8E, stall possible) = (p5 == 0)
if mode == 1:                              // "easy"
    copy.9E..A6 (5 landing limits) <<= 1
    ctl[5] (mass) = 400h
    copy.16..26 (side force, 9 words) <<= 1
    copy.62..72 (control effectiveness, 9 words) = 400h
    copy.76 += copy.76 >> 1;  copy.7A += copy.7A >> 1
    copy.8C = copy.8A = copy.82 = copy.94 = copy.92 = 0
    copy.AE (Vne) = copy.C0 = copy.C6 = 0
elif mode == 2:                            // "medium"
    copy.9E += >>2; copy.A0 += >>2; copy.A2, A4, A6 += >>1
    copy.88 = 0; copy.8C = copy.8A = 0; copy.94 = copy.92 = 0
    copy.AE = copy.C0 = copy.C6 = 0
elif mode == 3:  copy.88 = 0
t = DS:711E
if t < 100h: fm_full(fm, ctl)
else: DS:711E = t >> 1; fm_full(fm, ctl); fm_full(fm, ctl); DS:711E = t
if DS:5764 && mode == 1: fm->dmg_level (+47) = 0; DS:5764 = 0   // easy: no landing damage
fm->fmd = fmd_saved; ctl[5] = saved_mass
```
Mode 1/2/3 = `DS:02CE[DS:42D3]` (realism "flight model" 0/1/2); mode 4 = AI. Note mode 3 still
zeroes `+88` (the bank-angle fade of the weathervane yaw).

### 3.2 `0b01:0134 fm_full(FmState *fm, Controls *ctl)` — near-called (`push cs; call`), likely (control flow from Ghidra, arithmetic spot-checked)

Notation: `P` = posture, `F` = FMD (copy), `abs16(x)` = |x| with 8000h → 7FFFh, `fold(r)` =
`abs16(r)`, and if > 4000h then `7FFFh − it` (distance of roll from level), `clampS(x, m)` =
`0b01:1b14` (x limited to [−m, m]), `toward(a, b, m)` = `0b01:1b3b` (step from a to b limited to m),
`dt(x)` = `362b:00be` (x·DS:711E >> 8, saturated ±7FFFh), `interp(i, tbl)` =
`277a:41c4((i16)P.z, 0, 20000, tbl[i], tbl[i+1])` — **quirk: the interpolation variable is the low
16 bits of the absolute altitude, not the altitude minus the band start**, so the value is
`tbl[i] + (i16)z·(tbl[i+1]−tbl[i])/20000` (16-bit `imul`/`idiv`, can raise #DE on overflow; keep
the arithmetic exactly).

```
old_pitch, old_roll, old_head = P.pitch, P.roll, P.heading
ail = ctl[0]; elev = ctl[1]; rud = −ctl[2]; flaps = ctl[7] & 3
yaw_s = pitch_s = roll_s = torq_yaw = 0; lat_acc = 0 (local_28)
v_old = fm->v_world[0..2]
Fz = Fy = Fx = 0                           // local_1a (vertical), local_1c (forward), local_1e (lateral)
alpha = fm[0B] = atan2(fm->v[1] (fwd), −fm->v[2] (vert))      // 277a:6228
beta  = atan2(fm->v[1], fm->v[0])          ; if abs16(beta) < B6h: beta = 0
gnd   = F.98 + ctl[6]
on_ground = (P.z <= gnd)                   // i32 compare
i = alt_band(P.z)  (0..7)

// 0. elevator shaping (c1 = ctl[1]; c0 = ctl[0] aileron; c2 = −ctl[2] rudder)
if c1 < 0:
    if abs16(P.pitch) > 1000h: c1 >>= 1          // (arithmetic shift)
elif F.BE != 0 and c1 > 0:                       // positive elevator loses authority when banked
    a = min(abs16(P.pitch) >> 3, 400h); r = fold(P.roll)
    c1 -= c1·((((F.BE·(400h−a) >> 10)·(r >> 4) >> 10)·600 >> 10) >> 10
```
(`local_48` = c0, `local_46` = c1, `local_4a` = c2 in the decompile.)

The remaining steps, in order (all verified against the Ghidra output, which is structurally
reliable for this function; recheck any line with `x86dis.py 0b01:0134 5932` while porting):

1. **Control effectiveness**: `e = interp(i, F.62)`; `c0 = c0·e >> 10`, `c1 = c1·e >> 10`,
   `c2 = c2·e >> 10` (c0 = ctl[0], c1 = ctl[1] after step above, c2 = −ctl[2]). If `F.C6 != 0 &&
   F.C6 < v_fwd`: `c0 >>= 2`. If `F.C0 != 0 && F.C0 < v_fwd`: `c0, c1, c2 >>= 2`. Then `c0 =
   clampS(c0, 100h)`, `c1 = clampS(c1, 100h)`.
2. **Roll rate** (only if not stalled (flag 1 clear) and airborne): `b = c0·F.82 >> 10`, negated if
   `c0 < 1`; `target = (c0 + b)·F.7C >> 8`. If `rate9 != target`: acceleration `a` = `F.76` when
   moving the rate back through zero (rate < 0 going up, or rate > 0 going down), else `F.74`,
   with sign of the change; `s = satdiv((target − rate9) << 8, F.7C)`, `s = clamp(abs16(s), 20h,
   100h)`; `a = a·s >> 8`; `rate9 += dt(a)`; don't overshoot the target. Then, if `F.86 != 0` and
   `abs16(P.pitch) < 2000h`: roll-levelling `ls = dt(P.roll < 1 ? F.86 : −F.86)` limited so that
   it does not pass level, and zeroed if `abs16(ls) < 10`.
3. **Pitch rate** (if airborne, or `v_fwd > F.AA`): if `abs16(alpha) < 12000`: `k = 4B0h`, reduced
   by `fold(P.roll) >> 3` when `fold(roll) > 800h`, ≥ 0, forced 0 on the ground; `corr = 0` if
   `abs16(alpha) < k` else `alpha − sign(alpha)·k`; else (deep stall) `corr = sign(alpha)·max(7FFFh
   − abs16(alpha), 200)` and the elevator input is dropped. If not stalled `corr = corr·F.84 >> 10`.
   `target = clampS(c1 − (corr >> 2), 200h)·F.7E >> 8`; approach with `F.78`/`F.7A` exactly as the
   roll rate (divisor `F.7E`).
4. **Roll→yaw coupling** (airborne, not stalled, `F.B6 != 0`): `p = abs16(P.pitch)`, `p = (p >> 1) +
   (p >> 3)`; if `p < 2000h`: `r = fold(roll) + (fold(roll) >> 1)` clamped 4000h; `r = sin(r)`
   (`277a:5e66`); `k = r·(2000h − p) >> 14`; coefficient `F.B8` if roll < 1 else `−F.B6`; if `k > 0`
   `lat_acc = (coef·k >> 13)·800 >> 10`.
5. If `c2 == 0` and on the ground: `c2 = −c0` (steer with the stick). If flag 4 clear and
   `fm[22h] != 0`: `c2 += fm[22h]·throttle >> 8` (prop torque). `c2 = c2·500 >> 10`; `c2 += c2·(2000h
   − min(fold(roll), 2000h)) >> 14`; `c2 = clampS(c2, 100h)`.
6. **Weathervane yaw** from sideslip: if `abs16(beta) < 12000`: `b = beta`, faded to 0 when `F.88 !=
   0`, not stalled and `fold(roll) > F.88`, else `b = beta·(F.88 − fold(roll)) / F.88`; `y = b −
   16·(on_ground ? 2·c2 : c2)`; else `y = sign(beta)·2·clamp(7FFFh − abs16(beta), 50, 3000)`.
   `yaw = F.80·(−y) >> 10`; on the ground below `F.AA >> 2`: `yaw = satdiv(yaw·v_fwd, F.AA >> 2)`.
   If on the ground, or `abs16(pitch) < 800h && fold(roll) < 800h`: `lat_acc += yaw` and the
   matrix yaw input is the previous one, else the matrix yaw input = `yaw`.
7. **Torque yaw** (`throttle != 0`, `F.8A != 0`): `q = |lat_acc·fold(roll) >> 14|`; `yaw_s =
   (q + pitch_rate)·(F.8A·throttle >> 8) >> 10`.
8. **On the ground**: clear flag 1; roll → 0: `d = toward(P.roll, 0, F.A8)`; if `abs16(d) < F.BC`
   `rate9 = 0` else `rate9 += dt(toward(rate9, d, F.A8 >> 2))`; if `v_fwd <= F.AA`: pitch → `F.9A`
   the same way on `rate10`.
9. **Rotate**: if any of rate9, rate10, yaw input, pitch_s, yaw_s, roll_s ≠ 0: build a delta matrix
   from the angles (`dt(rate10 + pitch_s)`, `dt(rate9) + roll_s`, `dt(yaw_in + yaw_s)`) with
   `277a:457a`, multiply into the orientation (`277a:41e0`), extract the posture angles
   (`277a:49a4`). Idle snap: if all rates 0, not stalled, `abs16(pitch) < E38h` and `abs16(roll) <
   F.BC`: `P.roll = 0`.
10. **Heading**: if `abs16(lat_acc) > abs16(fm[15h])`: `lat_acc = (3·fm[15h] + lat_acc) >> 2`;
    `fm[15h] = lat_acc`; `P.heading += dt(lat_acc)`. On the ground `P.pitch ≤ F.9A` (rate10 = 0 when
    clamped).
11. **Matrix / body velocity**: if no posture angle changed by more than 15 (`& FFF0h` compare), `M' =
    transpose(copy of M)`, body velocity = old body velocity; else rebuild `M` from the posture
    (`277a:457a`), `M' = transpose(M)`, body velocity = `M'·v_world` (`277a:4ae5`) — i.e. velocity
    is kept in the world frame and re-expressed in the new body frame.
12. **Stall logic**: `st = abs16(alpha) > F.02`. If `F.8E == 0` or on the ground: clear flag 1. Else
    if flag 1 clear: flag 1 = `st && flag 2` (i.e. a second consecutive frame above the stall
    angle); entering a stall zeroes `rate10` and clears flag 4. Else if flag 4 clear: flag 1 = st.
    Flag 10 (overspeed) forces flag 1 and clears 4. Flag 2 = not stalled, airborne and `abs16(alpha)
    > F.02 − F.02/4`.
13. **Ceiling**: `cf = −1` if `F.B0 == 0` or `P.z <= F.B0 − 2600`; else `cf = max(F.B0lo + 1496 −
    P.zlo, 0)` (16-bit).
14. **Lift** (`Fz`, not stalled, not `st`, `cf != 0`, and (airborne or `v_fwd > 2·F.AA` with c1 >
    0)): `a = clampS(alpha, 1000h)`; `v = max(v_fwd + F.D4, 0)`; `L = satdiv(v << 14, cos(a))`
    (`277a:5e71`), times `interp(i, F.04) >> 10`; ceiling: `L = L·cf >> 12` if `cf != −1`; `ang =
    alpha + (flaps == 2 ? 444h : flaps == 1 ? 222h : 0)`; `L = L·clampS((ang·600 >> 10) + (F.02 >>
    2), 1000h) >> 12`; filter `L = (fm[0D] + L) >> 1` unless `fm[0D] == 8000h`; `fm[0D] = L`; `Fz +=
    L`. Otherwise `fm[0D] = 8000h`.
15. **Side force** (`F.16[i]` and `F.18[i]` ≠ 0, not stalled, `beta != 0`, airborne): `S = v_fwd ·
    interp(i, F.16) >> 10`, `S = S·(−clampS(beta, 5DCh)) >> 12`, filtered in `fm[0E]` like the lift;
    `Fx += S`.
16. **Thrust**: `T = F.28·throttle >> 8`; if `F.CC != 0 && v_fwd >= F.CC`: `T = T·max(0,
    lerp(v_fwd, CC..CE → 400h..0)) >> 10`; engines: `T = T·fm[20h] >> 10` (1 engine) or
    `T·((fm[20h] + fm[21h]) >> 1) >> 10`; engine factors below 0 are set to 0 first. `Fy += T`.
17. **Gravity**: `g = (0, 0, −DS:3F24·mass >> 10)` (`ctl[5]` = mass); `gb = M'·g`; `Fy += gb.y`,
    `Fx += gb.x`, `Fz += gb.z`.
18. **Drag** (per axis, `drag(v, k, &frac)` = `0b01:1aaf`: `k = min(k, 800)`, `p = v·k`, returns
    `−(p >> 10)` with the 10-bit remainder accumulated in `frac` (carry ±1)): lateral `Fx +=
    drag(v_lat, interp(i, F.2A lateral))`; forward: `k = interp(i, F.2C)` + extra: airborne, not
    `st`, `F.BA != 0`, `abs16(pitch) < 6000`: `min(|Δheading this frame|, 300)·F.BA >> 10`; on the
    ground: `(min(abs16(pitch), 800h)·F.AC >> 11) + F.60`; + dive brakes `F.C8` (ctl bit 2) + flaps
    `F.C4` (2) / `F.C4 >> 1` (1) + wheel brakes `F.CA` (bit 3, on ground) + gear `F.C2` (bit 4);
    compressibility `k = k·lerp(v_fwd, D0..D2 → 400h..800h) >> 10` when `F.D0 != 0 && v_fwd >= F.D0`;
    `Fy += drag(v_fwd, k)`; vertical `Fz += drag(v_vert, interp(i, F.2E))`.
19. **Acceleration**: `Fx, Fy, Fz = satdiv(F << 10, mass)`; integrate body velocity (`0b01:1b9b`):
    per axis `a = dt'(F)` (`362b:0256`, also returns a 10-bit fraction `(|F·711E| & FFh) << 2`),
    `v += a + carry(frac += fraction)`. Then `v_lat` decays by 1 toward 0 each call.
20. **World velocity** `v_world = M·v_body`; position: unless (on the ground, throttle ≤ 28h and
    `v_fwd ≤ 0Ch`) — parked — `P.x += step(dt((v_world.x + v_old.x) >> 1))` etc. with `step` =
    `0b01:1c4f` (`v·DS:3F22`, 10-bit remainder carried); parked: all velocities = 0.
21. **Ground contact**: if `P.z <= gnd`: `fm_ground_contact(F, fm, ctl, P)` (§3.4); `P.z = gnd`;
    `v_world.z = max(v_world.z, 0)`; `v_body = M'·v_world`; `v_lat = 0`; clear flags 1, 2, 4.
22. Clear flag 8; if `F.AE != 0 && DS:576B`: flag 10 if `v_fwd > F.AE`, else flag 8 if `v_fwd >
    F.AE − F.AE/8`. `fm_per_frame_velocity(fm)` (`0b01:1cb5`).

### 3.3 `0b01:1d33 fm_simple(FmState *fm, Controls *ctl, int level_hold, int coord, int p5)` — likely

The AI model: same skeleton as `fm_full` with these differences (all from the decompile):
- elevator/aileron/rudder scaled by the band effectiveness, `F.C6` limit only (no `F.C0`), all three
  clamped to ±100h;
- roll/pitch rate approach **without** the proportional factor: `a = F.74`, `2·F.76`, `−F.74`,
  `−2·F.76` (pitch `F.78`/`2·F.7A`), `rate += dt(a)`, no overshoot;
- when stalled, the pitch input is replaced by the recovery term `sign(alpha)·max(7FFFh −
  |alpha|, 200)` if `|alpha| > 12000`;
- roll→yaw coupling uses `coord` (`Controls` coordination factor from `plane_fly`): `k = sin(fold(roll))
  ·(2000h − p) >> 14`, `k += k >> 1`, `yaw = (coef·coord >> 10)·k >> 13` (p = |pitch|, reduced
  `(p>>1)+(p>>3)` only when pitch < 0); stored in `fm[16h]`;
- weathervane yaw: if `|alpha| < 12000`, beta is zeroed unless not stalled, `fold(roll) <= F.88`
  and `|beta| > B5h`; `y = beta − 16·c2`; else `y = sign·4·clamp(...)`; `yaw = −(y >> 4) − (y >> 5)`;
- no torque yaw, no prop torque, no engine-2 factor (only `fm[20h]`), gravity's lateral and vertical
  parts are applied only when `level_hold == 0`, lift and side force only when `level_hold == 0`
  (with the flap boost `+ >>2` (full) / `+ >>3` (half) applied to the lift magnitude instead of the
  angle, side force ×2);
- stall flag: `st = !on_ground && |alpha| > F.02`; `p5 == 0`: stalled → rate10 = 0; flag 1 = st;
  otherwise flag 1 cleared; flag 10 forces flag 1; flag 2 = ¾ threshold;
- if `p5 != 0 && st`: `v_world.z = max(old v_world.z, 0)`;
- ground contact identical (flags 1 and 2 cleared).

### 3.4 `0b01:2d9c fm_ground_contact(Fmd *F, FmState *fm, Controls *ctl, Posture *P)` — verified

```
if !(F.A6 <= P.pitch <= F.A4 && abs16(P.roll) <= F.A2):      // bad attitude
    lvl = v_fwd > F.9E ? 3 : v_fwd > F.9E >> 1 ? 2 : 1
    fm.dmg_level (+47) = max(fm.dmg_level, lvl)
s = −v_world.z
if s > F.A0:                                                  // sink rate
    lvl = s > 4·F.A0 ? 3 : s > 2·F.A0 ? 2 : 1;  fm.dmg_level = max(...)
if !(ctl.flags & 10h):                                        // gear up: belly landing
    fm.dmg_level = max(fm.dmg_level, 1); DS:5764 = 1
```
`DS:5764` (belly-landing latch) is cleared by `fm_step` in mode 1 together with the damage level.
The damage level is consumed by the aircraft state code (obj/dmg parts, `sim_world.md`).

### 3.5 Other `0b01` functions

| Address | Name | Signature | Does | Conf. |
|---|---|---|---|---|
| 0b01:000a | fm_module_init | far void() | empty | verified |
| 0b01:000f | fm_reset_globals | far void() | `DS:576B = DS:5769 = DS:5767 = DS:5765 = 0`, `DS:5764 = 0` | verified |
| 0b01:0031 | fm_set_cruise | far (FmState*, Fmd*, int k, i32 alt) | `d = interp(alt_band(alt), F.2C forward drag)`; if d≠0: `fm->v_body[y] (+30) = satdiv((k << 2)·F.28, d)` — the speed where thrust `4k/256` equals drag; then `v_world = M·v_body` and `fm_per_frame_velocity` | likely |
| 0b01:00d0 | fm_init | far (FmState*, Posture*, Fmd*, Matrix*, int k) | zero 0x48 bytes; posture/fmd/matrix pointers; `fm[0D] = fm[0E] = 8000h`; build M from the posture angles (`277a:457a`); engine factors 400h; `fm_set_cruise(fm, fmd, k, P.z)` | verified |
| 0b01:19ff | copy_vec4 | far void() | copies 4 × 6 bytes `DS:028E → DS:02AE` (no caller found) | verified |
| 0b01:1a28 | fm_cruise_speed | far int (Fmd*, i32 alt) | `satdiv(F.28 << 10, interp(band, F.2C))` = level speed at full throttle. `acedata` stores `(fm_cruise_speed(fmd, 10000)·700 >> 10)·DS:3F22 >> 10` at aircraft `.DAT`+73 | verified |
| 0b01:1a95 | fm_cruise_speed_here | far int (FmState*) | `fm_cruise_speed(fm->fmd, P.z)` | verified |
| 0b01:1aaf | fm_drag | near int (int v, int k, int *frac) | see §3.2 step 18 (k clamped to 800) | verified |
| 0b01:1b14 | clamp_sym | near int (x, m) | clamp x to [−m, m] | verified |
| 0b01:1b3b | step_toward | near int (a, b, m) | `b−a` limited to `[−m, m]` (returns the step, not the value) | verified |
| 0b01:1b78 | alt_band | far int (i32 z) | count of `DS:1446[k] <= z`, k < 8 (callers turn 8 into 7) | verified |
| 0b01:1b9b | fm_integrate_vel | near (int v[3], int frac[3], int F[3]) | §3.2 step 19 | verified |
| 0b01:1c22 | frac_carry | near int (int *acc, int add) | `acc += add`; ≥ 400h → −400h, return 1; < −3FFh → +400h, return −1; else 0 | verified |
| 0b01:1c4f | pos_step | near (i32 *pos, int *frac, int v) | `p = v·DS:3F22` (32-bit); frac add = `(|p| & 3FFh)`, negated if v < 0; `*pos += (p >> 10) + carry` | verified |
| 0b01:1cb5 | fm_per_frame_velocity | near (FmState*) | `fm[3..8] = fm[17h..1Ch]·DS:3F22 >> 10` | verified |

The near helpers `1aaf 1b14 1b3b 1b9b 1c22 …` are entered with a leading `inc bp` byte
(`45`) in front of `push bp` (Borland far-frame marker); the index lists both the 1-byte stub and
the body (`0b01:1b14`/`1b15` etc.) — same function.

## 4. `4bf9` — per-aircraft step and AI steering primitives

AI code never writes the stick directly with a model of the aircraft; it calls these primitives
every frame with a desired attitude, and they set `Controls` (aileron `+AC`, elevator `+AE`, rudder
`+B0`, throttle `+B2`) for `plane_fly`.

| Address | Name | Signature | Does | Conf. |
|---|---|---|---|---|
| 4bf9:0000 | fly_module_init | far void() | empty (called from `sim_init`) | verified |
| 4bf9:0010 | fly_player_is_ai | far int() | returns 0 (debug hook: player flown by the AI when ≠ 0) | verified |
| 4bf9:0017 | plane_engine_sound | far (Plane*) | see §4.2 | verified |
| 4bf9:0257 | plane_fly | far (Plane*) | §4.1 | verified |
| 4bf9:03ce | steer_roll_to | far int (Plane*, int roll, int tol) | if `P.pitch < −14000` return 1 (steep dive: no roll control); `ail = (roll − P.roll) >> 4`; return `|ail| < tol` (`277a:3f0e`: 1 when `−tol < ail < tol`) | verified |
| 4bf9:0401 | steer_pitch_to | far (Plane*, int pitch, int tol) | `d = pitch − P.pitch`; if `(u16)(P.roll + 8000) < 16000` (|roll| < 8000): `elev = d >> 5`; else `rud = (P.roll >= 0 ? −d : d) >> 5`; (tolerance test result discarded) | verified |
| 4bf9:044b | steer_heading | far (Plane*, Plane *tgt, int dhead, int lead) | bank-to-turn: `b = dhead·45 >> 10`; with a target and `lead` and `Plane+D7 == tgt` and `Plane+CE != 80h`: `b += Plane[CE]·(−2000) >> 10`; with a target: `vz = Plane.fm[+90]` (−) `lencos(tgt.fm.?, head_diff)`…; `b −= dt(vz)·400 >> 10`; small corrections (|b| < 45 and |roll| < 2000): roll level (steer_roll_to 0) when b and roll have the same sign, `rud = −16b`; else bank limit = `min(DS:02C6[aircraft.class], pilot.max_bank (+0C))`, `r = satdiv(b << 9, FMD.74)`, `r = satdiv(r << 10, FMD.74)`, squared-soft below 100h (`r·|r| >> 7`), and steer_roll_to(±limit) at the limit else `ail = −r` | likely |
| 4bf9:061b | steer_heading_lead | far (Plane*, Plane*, int) | `steer_heading(.., 1)` | verified |
| 4bf9:0632 | steer_heading_nolead | far (Plane*, Plane*, int) | `steer_heading(.., 0)` | verified |
| 4bf9:0649 | steer_climb | far (Plane*, Plane *tgt, int dpitch, int limited) | pitch limits: `limited == 0`: ±4000h; else min = aircraft `.DAT`+3A, max = `.DAT`+57 or `+6B` when `Plane+4A→+06 & 10h` (carrying ordnance?); `e = dpitch·100 >> 10 − climb·750 >> 10` (+ target climb·750 >> 10); at the limits `steer_pitch_to(limit)`; else if |roll| < 4000: `elev = e`, else `rud = ±2e` | likely |
| 4bf9:0762 | steer_altitude | far int (Plane*, i32 dz) | `d = atan2(dz, 5000)` (`35ff:0041`) − P.pitch; `steer_climb(p, 0, d, 1)`; returns d | verified |
| 4bf9:07a1 | steer_intercept | far (Plane*, Plane *tgt, int pursuit, int, int facing, Aim *out) | relative position of the target in own axes (`277a:5368` + `50c0`), horizontal range `sqrt` (`277a:3c36` of `labs` sums), bearing `atan2 − heading`; facing: when both headings within 90° and the bearing behind, mirror (`−8000h − b`) if `277a:5588`; elevation `atan2(−dz, 5000)`; close (< 8000) and elevation outside ±2000h → `steer_roll_to`, else `steer_heading_nolead`; `steer_climb(p, tgt, elev, 1)`; `out+2` = range (i32), `+6` = elevation, `+10` = bearing | likely |
| 4bf9:08d5 | steer_to_point | far int (Plane*, Point*) | bearing to the point (`3629:0004`) − heading; `steer_heading_nolead(b/2)`; `steer_altitude(P.z − pt.z)`; throttle = `plane_cruise_throttle` (and `277a:3f3c` min with it when climbing) | likely |
| 4bf9:0961 | plane_cruise_throttle | far int (Plane*) | 100h when `Plane+42 & 10h`, else pilot profile `+10` (`DS:55CE[Plane+BB]`) | verified |
| 4bf9:098b | steer_speed_match | far (Plane*, Plane *lead, int, int head, int dist) | `t = throttle + ((lencos(dist?, head − lead.head) − dist) >> 3) + (lead.vz − own.vz)·8` clamped to `[8Ch, cruise]` (`35ff:0009`) | likely |
| 4bf9:09f4 | controls_neutral | far (Controls*) | aileron = elevator = rudder = 0; clears flap bits 0–1, dive brakes, wheel brakes | verified |
| 4bf9:0a18 | fly_module_end | far void() | empty | verified |

### 4.1 `4bf9:0257 plane_fly(Plane *p)` — verified

```
k = 400h
*(u8*)p->state16 (Plane+16 → byte 0) = (byte != 0) ? 0 : 1        // toggles an "flew this frame" byte
if p->pilot (+BB) == 44 (player) and !fly_player_is_ai():
    mode = DS:02CE[DS:42D3]           // 1, 2 or 3
else:
    (not player) 362b:0146 no-ops on rudder, aileron, elevator
    mode = 4
ail = clampS(ail, 100h); elev = clampS(elev, 100h); rud = clampS(rud, 100h)   // 277a:3f27
if mode == 4:
    if p->req (+C1) & 10h: k = 0
    elif p->req & 1:       k = 400h
    else: k = ((pilot[+0E] − 3B6h)·DS:02E0[DS:42D2] >> 10) + 3B6h     // DS:02E0 = {750, 875, 1024}
if p->req & 2: mode = 1
level = (p->req & 8) && (u16)(P.roll + 1389h) <= 2711h                  // |roll| <= 5000
365a:000c()                                                              // matrix pointer
fm_step(&p->fm, &p->ctl, mode, k, 0, level)
p->req = 0
plane_engine_sound(p)
```
`DS:42D3` = realism "flight model" (0 easy, 1 medium, 2 realistic), `DS:42D2` = realism "combat
level"/enemy skill index 0..2 (also read by `04c4`, `0769`, `1142`, `1284`).

### 4.2 `4bf9:0017 plane_engine_sound(Plane *p)` — verified (sound-side hooks; hand-off to sound)

For the player only: engine note = `DS:3FDE` (engine 1 rpm gauge value from `678a`, averaged with
`DS:3FE0` when FMD `+90` > 1); by aircraft `.DAT`+75 (engine sound type 0..5; 5 → 2 when `DS:269D
== 0`, `acedata`): pitch `= rpm·{13B0h, DFAh, 578h, DFAh}[type] >> 10 + {28A0h, 28A0h, 3908h,
28A0h}` (types 1, 2, 3, 4; others: unchanged), `5a75:0f72(DS:02D4[type], &p.pos, pitch,
&p.v_world, 0, 1)`. Gear-touch: when `DS:3F26 <= 0`, on the ground (`FMD.98 + ctl[6] >= P.z`) and
the latch `DS:3F28` was clear and the gear is down → `5a75:0eea(16h, &pos, &v_world, 1)` once
(latch cleared when airborne); `DS:3F26` counts down otherwise. Unless `DS:19F2` (sound off?),
find the nearest other aircraft of engine class < 3 with throttle ≠ 0 within 100000 of the
listener (`5440:008d` camera position, `277a:3b3c` distance); within 5000 play the fly-by sound
1Fh at it. Non-player aircraft: `5a75:0eea(DS:02DA[type], &pos, &v_world, 0)`.

## 5. `362b` — frame-time scaling helpers (used by all of sim_world)

| Address | Name | Signature | Does | Conf. |
|---|---|---|---|---|
| 362b:000d | ts_set | far (int s) | `DS:711E = s; DS:711C = 3684:00a1(s) − 7` | verified |
| 362b:002d | ts_reset | far () | `ts_set(100h); DS:711A = 100h; DS:7118 = 1` | verified |
| 362b:0048 | ts_set_nominal | far (int n) | `DS:7118 = n` | verified |
| 362b:0053 | ts_last_ticks | far int () | `DS:7116` | verified |
| 362b:005b | ts_ratio | near int (int nominal, int ticks) | `clamp(satdiv(ticks << 8, nominal), 40h, 1C2h)` | verified |
| 362b:008f | ts_frame | far (int ticks) | `ts_set(ts_ratio(DS:7118, ticks)); DS:711A = ts_ratio(DS:3712, ticks); DS:7116 = ticks` | verified |
| 362b:00be | dt_scale | far int (int x) | `clamp((i32)x·DS:711E >> 8, −7FFFh, 7FFFh)` | verified |
| 362b:0106 | dt_scale2 | far int (int x) | same with `DS:711A`, low clamp 8001h | verified |
| 362b:0146 | dt_nop | far int (int x) | returns x (debug stub) | verified |
| 362b:0165 | timer_dec | far int (int *t) | `*t −= DS:711E`, 0 on signed overflow… **quirk**: only on overflow, negative results stay | verified |
| 362b:017c | timer_dec32 | far int (i32 *t) | same, 32-bit | verified |
| 362b:01a0 | timer_dec_b | far int (int *t) | = 0165 | verified |
| 362b:01bb, 01e7 | timer_inc | far int (int *t) | `*t += DS:711E` | verified |
| 362b:01cc, 023b | timer_inc32 | far int (i32 *t) | `*t += DS:711E` | verified |
| 362b:01f8 | timer_expired32 | far int (i32 *t) | `*t −= DS:711E`; if result ≤ 0 (or overflow): `*t = 0`, return 1; else 0 | verified |
| 362b:021c | timer_expired | far int (int *t) | 16-bit version of 01f8 | verified |
| 362b:0256 | dt_scale_frac | far (int *x, int *frac) | `p = x·DS:711E`; `*x = clamp(p >> 8, ±7FFFh)`; `*frac = (|p| & FFh) << 2` (3FFh when clamped), negated if the result < 0 | verified |
| 362b:02e3 | dt_mul | far int (int x) | `x·DS:711E` (16-bit) | verified |

Note on `timer_dec` (`0165/017c/01a0`): the decompile's `SBORROW` test is the signed-overflow
check of `sub`; the result is only forced to 0 when the subtraction overflows, so these timers go
negative. `timer_expired*` are the ones that stop at 0.

## 6. Small math helpers (`35ff`–`3684`) used by the sim

These are general utilities (probably the 3Space library's, see Hand-offs); one line each:

| Address | Name | Does |
|---|---|---|
| 35ff:0009 | clamp_range(v, lo, hi) | `v < lo ? lo : v > hi ? hi : v` |
| 35ff:0029 | in_range(v, lo, hi) | `lo <= v <= hi` (byte) |
| 35ff:0041 | atan2_l(i32 x, i32 y) | binary-angle atan2 of two longs (scaled to 16 bits first) |
| 3604:0009 | vec_scale14(v[3], k) | `v[i] = v[i]·k >> 14` |
| 3604:0051 | vec_rot_z(v, angle) | rotate x/y by an angle (`cos`/`sin` 2.14) |
| 3609:0001 | vec_… | (used by AI; see ai part) |
| 3611, 361d | … | small vector ops (render/AI) |
| 3614:0009 | dist_xy? | used for ranges (AI) |
| 3624:0000 | … | |
| 3629:0004 | bearing_to(i32 a[2], i32 b[2]) | `atan2_l(a.x − b.x, a.y − b.y)` — heading from b to a |
| 365a:000c | plane_matrix(Plane*) | returns the orientation matrix pointer (`Plane+20`) (in_BX calling convention) |
| 365a:0032, 0074 | object_… | `+26 = 0, +28 = AX` (object init) |
| 3662, 3666, 3678, 3684:000c | … | vector/angle helpers (distance between two rotated points…) |
| 3684:0042 | box_outcode(p, lo, hi) | 3 × in_range → bits 1/2/4 |
| 3684:00a1 | ilog2(i32) | bit length (used for `DS:711C` and the aircraft `.DAT`+08) |

## Math primitives used (render3d `277a`)

| Entry | Semantics (as used) |
|---|---|
| 277a:3b3c | `dist3(i32 a[3], i32 b[3])` → i32 (octagonal/approximate 3-D distance) |
| 277a:3bfc | `dist2(a, b)` → i32 (x/y… ground distance approximation) |
| 277a:3c36 | `isqrt32` |
| 277a:3dc1 | **`satdiv(i32 n, int d)`**: `idiv` with saturation: if `|n| > |d|·7FFFh` → 7FFFh (positive quotient) / 8000h (negative); d = 0 with n ≠ 0 saturates, n = d = 0 faults (#DE) |
| 277a:3f0e | `within(x, tol)` → 1 if `−tol < x < tol` |
| 277a:3f27 | `clamp_sym(x, m)` |
| 277a:3f3c / 3f55 | `min(a, b)` / `max(a, b)` |
| 277a:41c4 | `lerp(x, x0, x1, y0, y1)` = `y0 + (x−x0)(y1−y0)/(x1−x0)` (16-bit imul/idiv) |
| 277a:41e0 | `mat_mul(A, B, out)` |
| 277a:4556 | `mat_transpose(M)` (in place) |
| 277a:457a | `mat_from_angles(u16 ang[3] (pitch, roll, yaw), M)` |
| 277a:49a4 | `angles_from_mat(M, u16 ang[3])` |
| 277a:4ae5 | `mat_vec(v, M, out)`: `out = M·v` (i16 vectors, 2.14 matrix) |
| 277a:4e76 | `lencos(len, angle)` = `len·cos(angle) >> 14` |
| 277a:5e66 / 5e71 | `sin(a)` / `cos(a)` → 2.14 (table, 4096 steps) |
| 277a:6228 | `atan2(y, x)` → u16 binary angle (16-bit args) |
| 277a:5368, 50c0, 5588, 530c, 533a, 53ae, 5434, 563a, 5004, 4f18, 4f38, 4f7c, 4fb2, 526a, 55f0, 5612 | object-relative vector ops (world → object axes, rotations of offsets, direction vectors); see the AI and weapons parts where used |

## Port notes

* `/* PORT: */` `satdiv` and `lerp` must reproduce the x86 `idiv` exactly, including #DE cases
  (`lerp` with the altitude-low-word quirk can overflow 16 bits at altitudes where
  `(i16)z·Δ/20000` exceeds 32767: then the original takes the divide-error interrupt). AP installs
  its own INT 0 handler (`divzero_install` `1d32:69a2`, platform): the port's `idiv16` must return
  what that handler makes the program continue with (platform spec). Keep a single `idiv16()`
  helper.
* The flight model's double step when `DS:711E ≥ 100h` means the port's frame pacing directly
  changes the physics; keep the original `ticks → DS:711E` mapping (sim_flow).

## Hand-offs

* **render3d**: 277a math entries listed above (exact semantics: matrix format 9 × i16 2.14 + flag
  byte, `mat_from_angles` rotation order, `atan2` table, `sin/cos` table, `dist3` approximation). The
  small helper segments `35ff 3604 3609 3611 3614 361d 3624 3629 365a 3662 3666 3678 3684` are
  general math/object utilities also used outside the sim; they are listed in
  `sim_world_symbols.csv` but may be better owned by render3d.
* **sim_flow**: time base — `362b:008f ts_frame(ticks)` called from `5b93:01ed` (`DS:4DFB << 2`) and
  `5cde:0405`; nominal `DS:7118` from `4b9f:0000` (`5613:0161(0)` slider); `DS:3712` second nominal.
  The player's control input must write `Plane+AC..+BA` of `DS:3B09` (§2.3) — the FM reads nothing
  else. `DS:576B` (overspeed warnings enabled) is written by `522c:011c/0162`.
* **sound**: `plane_engine_sound` `4bf9:0017` (§4.2): `5a75:0f72`/`5a75:0eea` call sites, tables
  `DS:02D4`, `DS:02DA` (sound ids per engine type), `DS:3F26`/`DS:3F28` gear-touch latch.

## Open questions

* World unit (¼ ft is a guess from the FMD ceilings); speed unit.
* FMD `+92`, `+94`, `+96`, `+9C`, `+B4`: not read by the flight model — maybe by the AI (dive
  speeds?) or unused.
* `Controls[4]` (`Plane+B4`).
* Whether the altitude-low-word interpolation is intended (it is what the code does).
