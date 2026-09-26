# sim_flow part: cockpit — views, cameras, cockpit, gauges, HUD overlays, messages (AP.EXE)

**Status: in progress (2026-09-26).** Part of `port/spec/sim_flow.md` (lead). Target
`work/AP_flat.exe`, DGROUP `3EA4`; `DS:xxxx` = DGROUP offsets, `SSSS:OOOO` code as in
`port/RE_GUIDE.md`. Everything was read from the disassembly (`tools/x86dis.py`); confidence is
**verified** unless tagged *likely* / *guess*. Near helpers that start with `inc bp; push bp; mov bp,sp`
and end `dec bp; ret` (Borland's far-frame marker on near functions) are listed at the `inc bp`
address (the function index lists the body 1 byte later as a separate "function").

## Index

1. Overview (frame order, who draws what)
2. Views and cameras (`1c30`, `05d6:036c/0381/03fc`, `637f:00af`, `0590` servos)
3. Cockpit build (`644a` cockpit.c, `465c:04ee`, `4899`, CPVW.BUF)
4. Cockpit window outlines / edge masks (`0962`, `0a7b`, `.EDG`)
5. Gauges (`4963`, `4cad`, `678a`, `.GAU`)
6. Messages and text (`0ab0`, `4bb7` STR_POOL, `1614`, `6939`, `1815`, `1ba4`, `10e5`)
7. Radio menus (`6e5a`, `1660` radio-command subset)
8. LSO paddle overlay (`6dfc:0497/04ce`, `50c0:0000/004a`)
9. File formats (`.EDG`, `.GAU`, `STR_POOL.DAT`, SIMPREFS saved views)
10. Port notes
11. Hand-offs
12. Open questions

-----------------------------------------------------------------------------------------------

## 1. Overview

### 1.1 Per-frame order (views and HUD)

In the flight loop `5cde:0405` (lead), after the sim step `5440:1317`:

```
view_rec = {cmd, flags, pan_x, pan_y}          // built by 5f2c:08fd (lead) from the input record, §2.3
if (view_input_pending(&view_rec))             // 1c30:09d9
    if (view_update(&view_rec) & 1)            // 1c30:0ad5, bit 0 = view changed
        DS:4E71 = DS:4090                      // number of full redraws still to do (= page count, 2)
5d3c:003a(1)                                   // sound listener = camera (sound/VCR glue, not ours)
5440:018c(DS:4E71, 1)                          // draw; then DS:4E71-- (min 0)
```

**Correction to the brief:** `DS:4090` is not the view number. It is the number of full-screen
redraws needed after a change (default 2 = one per video page); `DS:4E71` counts them down and is
passed as the first argument of the draw `5440:018c` ("redraw everything" while > 0). The view
number is **`DS:5EBB`** (0..19h), read by everybody through `view_get` `1c30:0780`.

The draw `5440:018c(redraw, 1)` (lead) does, in order: … `644a:0271(redraw)` (cockpit/panel
background, §3), `1614:019a` (message line restore, §6), `6dfc:0497` (LSO overlay erase, §8),
then `switch (view_get())`: views **0–3** → `0962:0bf1` (cockpit window mask on), 3D world
`5440:03aa`, `0962:0c7f` (mask off); other views → `5440:03aa` only; then `644a:0584(redraw)`
(cockpit overlay + gauges, §3/§5), `1614:005b(redraw)` (messages), `6dfc:04ce` (LSO signal),
`6e5a:01a0(redraw)` when the radio menu is open (`DS:1206`), `17ce:0013` (palette) unless
`DS:069F`, and the page flip `5440:07e1`.

### 1.2 View numbers (`DS:5EBB`)

| View | Kind | Camera | Per-frame fn (`DS:1AF4`) | `DS:19F6` | `DS:19F2` |
|---|---|---|---|---|---|
| 0 | cockpit, front | the player's aircraft itself (render record +02 restored) | none | 0 | 1 |
| 1 | cockpit, rear | player aircraft + head angles (0, 7D00h) | `1c30:0638` | 2 | 1 |
| 2 | cockpit, left | head (0, 3E80h) | `1c30:0638` | 1 | 1 |
| 3 | cockpit, right | head (0, C180h) | `1c30:0638` | 1 | 1 |
| 4 | cockpit, head pitch C180h (−88°; down, *likely*) | head (C180h, 0) | `1c30:0638` | 1 | 1 |
| 5 | cockpit, head pitch 2EE0h (+66°; up, *likely*) | head (2EE0h, 0) | `1c30:0638` | 1 | 1 |
| 6 | external preset "front" (looks back at the target, heading +7D00h) | orbit, servo | `1c30:05c1` (relative pitch) | 3 | 0 |
| 7 | external preset "chase" (behind the target) | orbit, servo | `1c30:05c1` | 3 | 0 |
| 8 | external preset side (heading −16000) | orbit, servo | `1c30:05fc` | 3 | 0 |
| 9 | external preset side (heading +16000) | orbit, servo | `1c30:05fc` | 3 | 0 |
| 0Ah | external preset, pitch +16000 (from below, *likely*) | orbit, servo | `1c30:05fc` | 3 | 0 |
| 0Bh | external preset, pitch −16000 (from above, *likely*) | orbit, servo | `1c30:05fc` | 3 | 0 |
| 0Ch–15h | the 10 saved views (slots 1–10, `DS:1AB8`) | orbit, servo | `1c30:05fc` | 3 | 0 |
| 16h | orbit with the target's own remembered orbit (target+22h record) | orbit, servo | `1c30:05fc` | 3 | 0 |
| 17h | trailing view: the player's position and attitude of ~24 nominal frames ago | history ring | `1c30:0668` | 3 | 0 |
| 18h | free camera, flown with the pan controls | free | `1c30:06a3` | 3 | 0 |
| 19h | death / impact camera (swoops in, no servo snap) | orbit, servo | `1c30:05fc` | 3 | 0 |

"Orbit" = camera at `target.pos − dir(pitch, heading)·dist` looking at the target, the four
parameters driven by rate-limited servos (§2.6). Views 0–5 keep the camera in the player's aircraft
(`DS:19F2 = 1`: cockpit drawn, the player's own shape not drawn — render3d reads `1c30:09a9`).

-----------------------------------------------------------------------------------------------

## 2. Views and cameras

### 2.1 Globals

| Address | Type | Name | Meaning |
|---|---|---|---|
| `DS:5EBB` | i16 | `view` | current view 0..19h (§1.2); init 0 |
| `DS:5E4B` | ptr | `view_target` | object the external camera looks at; init 0 |
| `DS:19F2` | i16 | `view_inside` | 1 = views 0–5 (camera = own cockpit); init 1 |
| `DS:19F4` | i16 | — | set 0 at init, no other use in this part |
| `DS:19F6` | i16 | `view_class` | 0 front cockpit, 1 cockpit side/up/down, 2 cockpit rear, 3 external — selects the head angles in `1c30:0a73` |
| `DS:1AF4` | far fn ptr | `view_frame_fn` | per-frame camera placement function (0 = none) |
| `DS:1AF8` | i16 | `view_force` | 1 = next `view_set` re-initialises even if the view is unchanged |
| `DS:5E49` | ptr | `saved_rrec` | render record pointer saved when leaving view 0 |
| `DS:5E4D` | ptr | `saved_rrec_eye` | the render record's +02 (eye) saved with it |
| `DS:5E4F` | struct | `cam` | camera placement, same layout as object+02: +02 `DS:5E51` position (3 × i32 x, y, z = altitude), +0E `DS:5E5D` pitch, +10 `DS:5E5F` roll, +12 `DS:5E61` heading (i16 binary angles, 10000h = 360°) |
| `DS:5E3D` | 3 × i32 | `freecam_vel` | per-frame displacement of the free camera (view 18h) |
| `DS:5E65` | i16 | `orbit_dist` | orbit distance (feet?), 400 ≤ … ≤ 10000 when zoomed |
| `DS:5E67` | i16 | `orbit_heading` | heading offset from the target's heading |
| `DS:5E69` | i16 | `orbit_roll` | always 0 |
| `DS:5E6B` | i16 | `orbit_pitch` | pitch, ±16000 |
| `DS:5E6D` | servo | `servo_dist` | 12h-byte servo (§2.6) for the distance |
| `DS:5E7F` | servo | `servo_heading` | … heading |
| `DS:5E91` | servo | `servo_roll` | … roll |
| `DS:5EA3` | servo | `servo_pitch` | … pitch |
| `DS:5EB5` | i16 | `deathcam_first` | 1 at init; view 19h uses preset `DS:1A88` once, then `DS:1AA0` |
| `DS:5EB7`, `DS:5EB9` | i16 | — | set 0 / 1 at init, not read in this part |
| `DS:1B20` | i16 | `view_set` | 0 = cockpit set, 1 = external set (F-key meaning, pan grid) |
| `DS:1B22` | i16 | `pan_moved` | pan input used since the pan button went down |
| `DS:1B24` | i16 | `pan_held` | pan button (view record flags bit 1) was down last frame |
| `DS:1B26` | i16 | `orbit_pan` | orbit-by-pan mode active in an external view |
| `DS:1B28` | i16 | `view_req` | requested view this frame, −1 none, −2 "leave weapon camera" |
| `DS:1B2A` | i16 | `view_reset_req` | set by `1c30:099e`: go to view 0 next update |
| `DS:1B2C` | u32 | `view_frame` | frame number (`5d3c:0064`) of the last `view_update`; init −1 |
| `DS:1AFA` | i16 | `view_override` | 1 = view record replaced by `DS:1AFC` (set by the sim step) |
| `DS:1AFC` | i16 | `view_forced_cmd` | forced view command, −1 none (cleared after every update) |
| `DS:1AFE` | u8 | `wcam_impact` | set by `05d6:0002` (sim_world) when the followed weapon hits |
| `DS:1AFF` | u8 | `deathcam_req` | set by `10bf:0039` / `088a` (sim_world) on the player's death/crash |
| `DS:5E3C` | u8 | `wcam_active` | weapon camera on (F8) |
| `DS:5E38` | ptr | `wcam_saved_target` | target before the weapon camera |
| `DS:5E3A` | i16 | `wcam_saved_view` | view before it, −1 = "recompute" |
| `DS:3C6E` | object | `wcam_proxy` | 24-byte copy of the followed weapon object (+22h → `DS:3CCC` orbit record, +42h flags `DS:3CB0`, +46h `DS:3CB4`); `DS:3C6A` = far ptr to the real weapon, `DS:3CD2` byte |
| `DS:00F0` | far ptr | `last_weapon` | last dropped/fired weapon (`05d6:036c`) |
| `DS:00F4` | u32 | `last_weapon_time` | mission clock `DS:4086` at that moment |
| `DS:5E32` | i16 | `trail_lag` | lag of view 17h in frames = min(62h, `362b:0146(18h)`) |
| `DS:5E34` | i16 | `trail_rd` | read index into the history ring (0..99) |
| `DS:5E36` | i16 | `trail_wr` | write index (0..99) |
| `3A73:0000` | char[] | — | "Current view saved..." |
| `3A73:0016` | 100 × 3 × i16 | `trail_ang` | ring of the player's angles (+10h..+15h) |
| `3A73:026E` | 100 × 3 × i32 | `trail_pos` | ring of the player's positions (+04h..+0Fh) |
| `DS:43D8` | ptr | `rrec` | render3d's view record: +02 ptr to the eye placement (object+02 layout), +04 head pitch, +06 head roll, +08 head heading (render3d) |
| `DS:3714` | ptr | — | → `DS:7120`, a 12-byte vector copied as the free camera's base velocity each frame (also read by `51fb:0199`); *guess*: wind drift |

Object fields used (sim_world layout): +02 shape id, +04/+08/+0C position (+0C = altitude),
+10 pitch, +12 roll, +14 heading, +18 byte kind (0 aircraft?, 1 ship?; *likely*), +19, +1A/+1B
flags (bit 0 dead), +22h ptr to a 6-byte orbit record {pitch, heading, dist}, +34h flight ptr
(+3Bh bit 1 = hidden flight), +42h flags (bit 2 = object gone → camera leaves it), +66h model data
(+98h gear/ground height), +0B8h, +0BBh byte.

### 2.2 Tables

**External presets** `DS:1968 + 18h·view` (views 6..0Bh; words): vmax of the pitch, roll, heading,
distance servos; shifts (bytes at +08, +0A, +0C, +0E; low byte used) of pitch, roll, heading,
distance; +10 pitch, +12 roll, +14 heading offset, +16 distance (overwritten at every use by
`orbit_min_dist(target)` except for view 19h):

| View | @ | vmax p, r, h, d | shifts | pitch | roll | heading | dist |
|---|---|---|---|---|---|---|---|
| 6 | 19F8 | 500, 500, 500, 30 | 2,2,2,2 | −1000 | 0 | 32000 (7D00h) | 450 |
| 7 | 1A10 | 4000 ×4 | 2,2,2,2 | −1000 | 0 | 0 | 450 |
| 8 | 1A28 | 500, 500, 5000, 30 | 2,2,2,2 | −1000 | 0 | −16000 | 450 |
| 9 | 1A40 | 500, 500, 5000, 30 | 2,2,2,2 | −1000 | 0 | 16000 | 450 |
| 0Ah | 1A58 | 5000, 500, 500, 50 | 2,2,2,2 | 16000 | 0 | 0 | 450 |
| 0Bh | 1A70 | 5000, 500, 500, 50 | 2,2,2,2 | −16000 | 0 | 0 | 450 |
| 19h first | 1A88 | 500, 500, 2000, 50 | 2,2,2,2 | −3000 | 0 | −10000 | 20000 |
| 19h later | 1AA0 | 500, 500, 2000, 50 | 2,2,2,2 | −3000 | 0 | 20000 | 3600 |

(DS:1968..19F7 is an unrelated table of far pointers into `1ad2`; views < 6 never reach this path.)

**Saved views** `DS:1A70 + 6·view` for views 0Ch..15h = `DS:1AB8 + 6·(slot)`, slot 0..9:
{pitch, heading, dist}; initial {0, 0, 450} ×10. Saved/loaded as 60 bytes by `1c30:0007`/`0020`
(= `SIMPREFS.PRF` +0Ah, §9.4). `view_preset` stores back max(dist, min_dist).

**F-key view map** `DS:1AEB + 7·view_set + cmd` for cmd 15h..1Bh (i.e. bytes `DS:1B00`..):
set 0: `00 01 02 03 05 04 17`, set 1: `06 07 08 09 0A 0B 17`.

**Pan grid** `DS:1B0E + 9·view_set + (4 + dx + 3·dy)` (dx, dy ∈ {−1, 0, 1} from the pan
direction, dy = +1 when pan_y > 4): set 0 `02 00 03 / 02 FF 03 / FF 01 FF`, set 1
`FF 06 FF / 08 FF 09 / FF 07 FF` (FF = no change). So in the cockpit, pan forward/back/left/right
select the front (0), rear (1), left (2), right (3) views (diagonals forward-left/right also left/right).

**Cockpit head angles** `DS:1B2C + 4·view` {pitch, heading} for views 1..5: 1 (0, 7D00h),
2 (0, 3E80h), 3 (0, C180h), 4 (C180h, 0), 5 (2EE0h, 0). (Entry 0 overlaps `view_frame`; unused.)

### 2.3 View commands and keys

The per-frame view record (4 words, built by `5f2c:08fd`, lead) is
`{+0 cmd, +2 flags (bit 1 = pan active, bit 0 = pan modifier: zoom / move), +4 pan_x, +6 pan_y}`.
`5f2c:08fd(rec, input, allow_pan)` (summary for the lead's section; verified):

* rec = 0. If `view_get() > 5` and no Ctrl/Alt and input+1Ah (throttle-key byte, ±7Fh/81h … ) ≠ 0:
  pan flags = 2 (| 1 after the first frame, `DS:4ED6`), pan_y from input+1Ah (external views only).
* If the radio menu is **not** open (`DS:1206 == 0`) and the scancode input+1Bh is 3Bh..44h
  (F1..F10), n = scancode − 3Bh:
  * exactly one of input+21h bit 7 / input+22h bit 0 set (from `1d32:0939` shift flags bit 2 / bit 3:
    **Ctrl / Alt**, *likely*): Ctrl → cmd = n + 1 (1..10, **save** view slot n), Alt → cmd = n + 0Bh
    (0Bh..14h, **recall** slot n);
  * otherwise F1..F7 → cmd = n + 15h (15h..1Bh), **F8 → cmd 2Ah**, F9/F10 → nothing.
* Otherwise, if `5f2c:015e()` (`DS:0B30`, view keys enabled): external views (> 5) take input+1Dh
  1..4 (hat / keypad direction) as a pan of ±7Fh (ramped) on y+, x+, y−, x−; cockpit views take
  input+1Eh 1..5 → cmd from `DS:0B36` = {19h, 18h, 16h, 17h, 15h} (i.e. view 4, 3, 1, 2, 0 in the
  cockpit set).
* input+23h bit 6 (pan button) with no pan yet: pan from the mouse (+8/+0Ch when input+21h bit 1)
  or the joystick (+0/+4 when `DS:0B26`), flags |= 2, bit 5 → flags |= 1. Mouse-look when
  `allow_pan && DS:0B2C && input+21h bit 0`.

**The brief's F1–F8 → commands 18h–1Fh** belong to the control record (+10h) of `5f2c:05d1`; that
path is not used by the view code. The view code gets F-keys only through `5f2c:08fd`, and not at
all while the radio menu is open (then F-keys pick radio messages, §7).

View commands handled by `view_update` (after the pan logic):

| cmd | Source | Effect |
|---|---|---|
| 1..0Ah | Ctrl+F1..F10 | message "Current view saved..." (`1614:024e(3A73:0000, 1, 0, 0)`), `view_save_slot(cmd−1)` |
| 0Bh..14h | Alt+F1..F10 | view_req = cmd + 1 (0Ch..15h), view_set = 1 |
| 15h..1Bh | F1..F7, input+1Eh | view_req = F-key map[view_set][cmd] |
| 1Ch..1Fh | forced (sim step), VCR | view_req = cmd − 1Ch (0..3), view_set = 0 |
| 20h..23h | forced, VCR | view_req = cmd − 1Ah (6..9), view_set = 1 |
| 24h | death/crash (`DS:1AFF`) | view_req = 19h, view_set = 1; if not inside, keep the target |
| 25h | — | view 0, set 0 |
| 26h | — | view 7, set 1 |
| 27h | (key, lead) | unless attached (`view_attached`), target = `next_view_object()`; view = 16h if its orbit record has dist > 0 else 7 |
| 28h | forced (skip-ahead end) | if not inside: view 18h (free camera) |
| 29h | — | if not inside: target = player; view 16h / 7 as for 27h |
| 2Ah | F8 | weapon camera toggle (§2.5) |

Forced commands from the sim step `5440:1317` (lead): `1c30:0ab4(1)` + `1c30:0aca(21h)` while the
skip-ahead runs (chase view 7), `0aca(1Ch)` (front cockpit) when it ends or from `5440:12b9`,
`0aca(28h)` (free camera) when `DS:069E`; `0ab4(0)` releases the override.

### 2.4 Functions of `1c30`

| Address | Name | Signature | Behaviour |
|---|---|---|---|
| `1c30:0007` | `views_save` | `void far (FILE *fp)` | `fwrite(DS:1AB8, 10, 6, fp)` (`0000:0945`) — the 10 saved views, 60 bytes; caller `sim_write_results` (SIMPREFS.PRF) |
| `1c30:0020` | `views_load` | `void far (FILE *fp)` | `fread(DS:1AB8, 10, 6, fp)` (`0000:0d48`); caller `4e0d:0b3e` |
| `1c30:0039` | `trail_record` | `void far (Object *pl)` | per sim frame (`5440:1317`): `wr = (wr+1)`, 100 → 0; copy pl+04 (12 bytes) → `trail_pos[wr]`, pl+10h (6 bytes) → `trail_ang[wr]`; then `want = wr − lag`; `rd' = rd − 100 if rd > wr else rd`; if `want > rd'`: `rd = min(rd' + 2, want)`, if `rd < 0` `rd += 100` (the read index advances ≤ 2 per frame and never goes back) |
| `1c30:00d0` | `trail_set_lag` | `void far ()` | `lag = min(362b:0146(18h), 62h)` (frames per 24 nominal steps at the current dt) |
| `1c30:00ee` | `orbit_min_dist` | `int far (Object *o)` | `r = 271b:0539(o+02)` (shape radius, render3d); `d = r + (r >> 1)` (sar); return max(d, 400) |
| `1c30:0117` | `orbit_pan_begin` | `near ()` | `view_frame_fn = 1c30:01fc`, `view_force = 1`, `orbit_pitch = cam.pitch`, `cam.roll = 0`, `orbit_heading = cam.heading − target+14h` |
| `1c30:0143` | `orbit_pan` | `near (ViewRec *r)` | flags bit 0: `orbit_dist += 362b:0106(r.pan_y << 5)`, clamp to [orbit_min_dist(target), 10000]; else `orbit_heading += clamp(362b:0106(r.pan_x << 8), −4000, 4000)`, `orbit_pitch += clamp(362b:0106(r.pan_y << 8), −4000, 4000)`, `orbit_pitch = clamp(orbit_pitch, −16000, 16000)` (`35ff:0009`) |
| `1c30:01fc` | `orbit_pan_frame` | `void far ()` | per-frame fn in orbit-pan mode (no servos): if `view_attached()`: `orbit_pitch = orbit_ground_clamp(orbit_pitch, orbit_dist)`, `cam.pos = player+04`, `cam.pitch = orbit_pitch`, `cam.roll = 0`, `cam.heading = player+14h + orbit_heading`, `cam.pos += dir(cam angles)·(−orbit_dist)` (`3611:0007`); else the same around `view_target`, then `orbit_store()` |
| `1c30:02ad` | `view_save_slot` | `void far (int n)` | if `view >= 6`: `DS:1AB8[n] = {orbit_pitch, orbit_heading, orbit_dist}` (nothing in the cockpit, but the message is shown anyway) |
| `1c30:02d9` | `view_preset` | `near (int v)` | see below |
| `1c30:0425` | `servo_snap` | `near (Servo *s)` | `s.value = s.goal; s.vel = 0; s.acc = 0` |
| `1c30:0441` | `servos_snap` | `near ()` | `servo_snap` on pitch, roll, heading, dist servos |
| `1c30:0466` | `orbit_servo_place` | `near ()` | `cam.pos = target+04`; `cam.pitch = servo_step(pitch)`, `cam.roll = servo_step(roll)`, `cam.heading = servo_step(heading)`, `d = servo_step(dist)`; `cam.pos += dir(cam angles)·(−d)` |
| `1c30:04c2` | `view_attached` | `near int ()` | `view == 18h || view == 17h || view_inside` |
| `1c30:04df` | `orbit_store` | `near ()` | unless `view_attached()` or `wcam_active`: target+22h record = {orbit_pitch, orbit_heading, orbit_dist} (the camera remembers the orbit per object) |
| `1c30:050a` | `cam_min_alt` | `near (i32 pos[3])` | `if pos[2] < 100: pos[2] = 100` |
| `1c30:0525` | `orbit_ground_clamp` | `near int (int pitch, int dist)` | below |
| `1c30:05c1` | `orbit_frame_rel` | `void far ()` | views 6, 7: servo goals: dist = orbit_dist; pitch = `orbit_ground_clamp(target+10h + orbit_pitch, orbit_dist)`; roll 0; heading = target+14h + orbit_heading; `orbit_servo_place()`; `orbit_store()` |
| `1c30:05fc` | `orbit_frame_abs` | `void far ()` | views 8..16h, 19h: as `05c1` but pitch goal = `orbit_ground_clamp(orbit_pitch, orbit_dist)` (absolute pitch), and `cam_min_alt(cam.pos)` after placing |
| `1c30:0638` | `cam_attach_target` | `void far ()` | cockpit views 1–5: `cam.pos = target+04`, `cam.pitch/roll/heading = target+10h/12h/14h` |
| `1c30:0668` | `trail_frame` | `void far ()` | view 17h: `cam.pos = trail_pos[rd]`, `cam angles = trail_ang[rd]` (far copies `0000:1c7a`) |
| `1c30:06a3` | `freecam_frame` | `void far ()` | view 18h: `cam.roll = 0`; `cam.pos += freecam_vel` (`277a:5004`, i32 add); `cam_min_alt(cam.pos)` |
| `1c30:06c3` | — | `int far ()` | returns 0 (no callers) |
| `1c30:06ca` | `freecam_pan` | `near (ViewRec *r)` | `freecam_vel = *(vec*)DS:3714`; if !(flags & 1): `cam.pitch += 362b:0106(pan_y << 7)`, `cam.heading −= 362b:0106(pan_x << 7)`; else `a = −362b:0106(pan_y << 6)`, `b = −362b:0106(pan_x << 6)`, `freecam_vel += dir(cam angles)·a`, `freecam_vel += dir(0, 0, cam.heading + 4000h)·b` (strafe) |
| `1c30:0780` | `view_get` | `int far ()` | returns `view` (18 callers: draw, cockpit, gauges, VCR, LSO, radio …) |
| `1c30:0788` | `view_set` | `near int (int v, RRec *rr, Object *tgt)` | below |
| `1c30:0986` | `view_restore_rrec` | `void far ()` | `view_frame_fn = 0`; `saved_rrec->eye = saved_rrec_eye` |
| `1c30:099e` | `view_request_reset` | `void far ()` | `view_reset_req = 1` (no direct callers; pointer use *likely*) |
| `1c30:09a9` | `view_outside_target` | `Object *far ()` | 0 when `view_inside`, else `view_target` (callers: culling 0802, crash 088a, death 10bf, VCR) |
| `1c30:09bc` | `view_new_frame` | `near int ()` | `5d3c:0064()` (frame counter `DS:0887`, or `DS:4E3B` in VCR playback) != `view_frame` |
| `1c30:09d9` | `view_input_pending` | `int far (ViewRec *r)` | below |
| `1c30:0a73` | `view_set_head` | `void far (RRec *rr)` | `rr+06 = 0`; if `view_class` is 1 or 2: `rr+04 = head[view].pitch`, `rr+08 = head[view].heading` (`DS:1B2C + 4·view`); else both 0 |
| `1c30:0ab4` | `view_override_set` | `void far (int on)` | `view_override = on`; if !on `view_forced_cmd = −1` |
| `1c30:0aca` | `view_force_cmd` | `void far (int cmd)` | `view_forced_cmd = cmd` |
| `1c30:0ad5` | `view_update` | `int far (ViewRec *r)` | below |
| `1c30:0f68` | `views_init` | `near ()` (called far from `sim_init 4e0d:03e9`) | below |
| `1c30:1021` | `wcam_is_active` | `u8 far ()` | returns `wcam_active` (caller `05d6:0002`) |

**`view_preset(v)`** (`1c30:02d9`):
```
if (v < 0Ch || v == 19h) {
    p = (v == 19h) ? (deathcam_first ? DS:1A88 : DS:1AA0) : DS:1968 + 18h*v;
    servo_pitch.vmax = p[0]; servo_roll.vmax = p[1]; servo_heading.vmax = p[2]; servo_dist.vmax = p[3];
    servo_pitch.shift = (u8)p[4]; servo_roll.shift = (u8)p[5]; servo_heading.shift = (u8)p[6]; servo_dist.shift = (u8)p[7];
    orbit_pitch = p[8]; orbit_roll = p[9]; orbit_heading = p[10];
    if (v != 19h) p[11] = orbit_min_dist(view_target);      // writes into the table
    orbit_dist = p[11];
} else {
    m = orbit_min_dist(view_target);
    all four servo vmax = 5000; all shifts = 2;
    if (v == 16h) { r = view_target->orbit (obj+22h); orbit_pitch = r[0]; orbit_roll = 0; orbit_heading = r[1]; orbit_dist = r[2]; }
    else { s = DS:1A70 + 6*v; orbit_pitch = s[0]; orbit_roll = 0; orbit_heading = s[1];
           orbit_dist = s[2] = max(s[2], m); }          // `cmp [si+4],cx; jle` → uses m when s[2] <= m
}
servo_init(&servo_pitch); servo_init(&servo_roll); servo_init(&servo_heading); servo_init(&servo_dist);
```

**`orbit_ground_clamp(pitch, dist)`** (`1c30:0525`), keeps the orbit camera above the ground:
```
h = 100;
t = view_target;
if (t->kind (+18h) == 0) { g = t->+0B8h + t->model(+66h)->+98h; if ((i32)g >= t->alt(+0Ch)) h += g; }
above = t->alt − h;                                  // i32
if ((i32)dist <= above) return pitch;
if ((i32)(−dist) >= above) return −16000 (C180h);
a = asin16(satdiv(above << 14, dist));               // 277a:3dc1, 277a:6b28
return min(a, pitch);                                // `cmp a,pitch; jge → pitch`
```

**`view_set(v, rr, tgt)`** (`1c30:0788`) returns 1 when something was (re)set:
```
if (v == view && !view_force && tgt == view_target && v != 18h && v != 19h) return 0;
view_force = 0; view = v; view_target = tgt;
if (view_frame_fn == 0) { saved_rrec_eye = rr->eye (+02); saved_rrec = rr;
    memset(&servo_heading,0,12h); memset(&servo_pitch,0,12h); memset(&servo_roll,0,12h); }  // not servo_dist
switch (v) {
 case 0:   view_class = 0; if (view_frame_fn) view_restore_rrec(); view_inside = 1; return 1;  // rr->eye NOT changed
 case 1:   view_class = 2; view_frame_fn = cam_attach_target; cam_attach_target(); view_inside = 1; break;
 case 2..5:view_class = 1; view_frame_fn = cam_attach_target; cam_attach_target(); view_inside = 1; break;
 case 6,7: view_class = 3; view_preset(v); orbit_frame_rel(); servos_snap(); view_frame_fn = orbit_frame_rel; view_inside = 0; break;
 case 19h: view_class = 3; view_preset(v); view_frame_fn = orbit_frame_abs; orbit_frame_abs();
           view_inside = 0; deathcam_first = 0; break;                       // no snap: swoops in
 case 8..16h: view_class = 3; view_preset(v); view_frame_fn = orbit_frame_abs; orbit_frame_abs(); servos_snap(); view_inside = 0; break;
 case 17h: view_class = 3; view_inside = 0; view_frame_fn = trail_frame; trail_frame(); break;
 case 18h: view_class = 3; view_inside = 0; freecam_vel = *(vec*)DS:3714; view_frame_fn = freecam_frame; break;
 default (> 19h): break;
}
rr->eye = &cam (DS:5E4F); return 1;
```
(For 6/7 the order is preset → one servo step (which also places the camera) → snap; the camera is
re-placed at the end of `view_update` by the per-frame function.)

**`view_input_pending(r)`** (`1c30:09d9`) — whether `view_update` must run this frame:
```
p = (view_forced_cmd >= 0);
if (r->flags & 2) { if (!pan_held) p = 1;
                    else if ((r->pan_x || r->pan_y) && (view < 17h || view == 18h)) p = 1; }
else if (!pan_moved || pan_held) p = 1;
if (r->cmd) p = 1;
if (wcam_impact) p = 1;
if (deathcam_req) { p = 1; r->cmd = 24h; deathcam_req = 0; }
if (view_new_frame() && view != 0 && view != 18h) p = 1;     // moving cameras update every frame
return p;
```

**`view_update(r)`** (`1c30:0ad5`) → bit 0 = the view/target changed (full redraw), bit 2 = the
camera moved:
```
rec = *r; save cam.pos (12 bytes) and cam angles (6 bytes); res = 0; obj = player (DS:3B09);
if (view_override) { rec = {0}; if (view_forced_cmd >= 0) rec.cmd = view_forced_cmd; }
if (rec.flags & 2) {                                   // pan button down
    if (!pan_held) { pan_held = 1; pan_moved = 0; }
    else if (rec.pan_x || rec.pan_y) {
        pan_moved = 1;
        if (view < 6 && !(rec.flags & 1)) {            // cockpit: pick a view from the pan grid
            i = 4 + (pan_x > 4) − (pan_x < −4) + 3*((pan_y > 4) − (pan_y < −4));
            view_req = (i8)DS:1B0E[view_set*9 + i]; }
        else if (6 <= view < 17h && !orbit_pan) { orbit_pan_begin(); orbit_pan = 1; }
    }
} else {                                               // pan button up
    if (pan_held && orbit_pan) orbit_pan = 0;
    pan_held = 0;
    if (!pan_moved) {                                  // click without moving: cockpit <-> outside
        view_req = (view < 6) ? 7 : 0; view_set = !view_set; pan_moved = 1; }
}
dispatch rec.cmd (table §2.3; 27h/29h/2Ah may change obj);
if (view_reset_req) { view_req = 0; view_reset_req = 0; view_set = 0; }
else if (wcam_active) {
    if (view_req >= 0 && rec.cmd != 2Ah) wcam_active = 0;            // any other view ends it
    else if (wcam_impact) { view_req = 19h; view_set = 1; obj = &wcam_proxy;
                            wcam_proxy.alt (DS:3C7A, i32) = 100; wcam_impact = 0; }
    else if (view_req == −2 || (view_req == −1 && (view_target->+42h & 4))) {
        05d6:03fc();  obj = wcam_saved_target;
        view_req = (wcam_saved_view == −1) ? 16h : wcam_saved_view; wcam_active = 0; }
} else if (!view_attached() && (view_target->+42h & 4)) {           // target gone: back to own plane
    obj = player; view_req = (player->orbit->dist > 0) ? 16h : 7; }
if (view_req != −1) { orbit_pan = 0; if (view_set(view_req, rrec, obj)) res = 1; }
if (orbit_pan) orbit_pan(&rec); else if (view == 18h) freecam_pan(&rec);
if (view_frame_fn) view_frame_fn();
view_req = −1; view_frame = 5d3c:0064();
if (cam.pos or cam angles differ from the saved copy) res |= 4;
view_set_head(rrec); view_forced_cmd = −1;
return res;
```
Weapon camera command 2Ah: if `wcam_active` → `view_req = −2`; else `w = wcam_object()`
(`05d6:0381`); if w: `wcam_saved_target = view_target`; `wcam_saved_view = view_attached() ? view : −1`
(when −1, `orbit_store()` first); obj = w; `view_req = 7`; `wcam_active = 1`.

**`views_init`** (`1c30:0f68`): `deathcam_first = 1`; fill ring slot 0 with the player's position
and angles; `trail_wr = trail_rd = 0`; `trail_set_lag()`; `DS:5EB7 = 0`, `view = 0`,
`DS:5EB9 = 1`, `view_frame_fn = 0`, `view_set = 0`, `pan_moved = 1`, `pan_held = 0`,
`orbit_pan = 0`, `view_class = 0`, `view_inside = 1`, `view_frame = −1`, `DS:19F4 = 0`,
`view_override = 0`, `view_forced_cmd = −1`, `view_target = 0`, `wcam_active = 0`.

### 2.5 Weapon camera and next object (split functions)

| Address | Name | Behaviour |
|---|---|---|
| `05d6:036c` | `wcam_note_weapon(far Object *w)` | `last_weapon = w`; `last_weapon_time = DS:4086` (mission clock). Callers: bombs `0688:009d`, rockets `1a32:00a7`, torpedoes `1baa:00ba` |
| `05d6:0381` | `wcam_object()` → `Object *` | 0 if `last_weapon == 0`, or `DS:4086 − last_weapon_time > 0C80h` (unsigned), or `w->+18h & 8000h` (already followed). Else `w->+18h |= 8000h`; copy 24 bytes of `*w` to `wcam_proxy` (`DS:3C6E`); `DS:3C6A = w`; `DS:3CD2 = 0`; proxy+22h (`DS:3C90`) = `DS:3CCC` (its orbit record); `DS:3CB0 &= DS:3CB4`; `DS:3CB4 = 0`; return `DS:3C6E` |
| `05d6:03fc` | `wcam_release()` | `DS:3C6A->+18h &= 7FFFh`; `DS:3C6A = 0`; `DS:3CD2 = 0` |
| `637f:00af` | `next_view_object()` → `Object *` | list `DS:475D` (ptr to an array of `DS:4778` object pointers), cursor `DS:3B01`. `i = start = (cursor + 1) % n`; loop: `o = list[i]`; accept when `alive(o)` (`637f:002b`) and !(`o->flight(+34h)->+3Bh & 2`) and (`o->+18h == 1 ? o->+19h != 0 : o->+0BBh == 2Ch`); else if ++tries ≥ n: `i = start`; if that object's flight is hidden, `i = 36d8:000a(DS:475B, player, DS:4776)` (index of the player in the list `DS:475B`; −1 if absent, *not guarded*); accept; else `i = (i+1) % n`. `cursor = i`; return `list[i]` |

`637f:002b` alive(o): `o->+18h == 1 → o->+19h != 0`; `o->+18h == 0 → !(o->+1Ah & 1) && !(o->+1Bh & 1)`; else 0 (sim_world).

### 2.6 Servo helpers (`0590`)

Servo struct (12h bytes):

| Off | Type | Field |
|---|---|---|
| +00 | i16 | `acc_step` = max(vmax >> shift, 1) |
| +02 | i16 | `acc_step2` = max(acc_step >> shift, 1) |
| +04 | u16 | `brake` = vmax << shift |
| +06 | i16 | `value` (output) |
| +08 | i16 | `goal` |
| +0A | i16 | `vel` |
| +0C | i16 | `acc` |
| +0E | i16 | `vmax` |
| +10 | u8 | `shift` |

| Address | Name | Behaviour |
|---|---|---|
| `0590:0002` | `approach(int *v, int target, int step)` → int | if `*v > target`: `*v −= step`; if `*v <= target` {`*v = target`; return 0}; return `*v − target`. If `*v < target`: `*v += step`; if `*v >= target` {`*v = target`; return 0}; return `target − *v`. Equal: 0 |
| `0590:004b` | `approach_dt(v, target, step)` | `approach(v, target, 362b:00be(step))` (step·dt >> 8, saturated) |
| `0590:0069` | `servo_step(Servo *s)` → int | below |
| `0590:015b` | `servo_init(Servo *s)` | `acc_step = vmax >> shift` (logical), 0 → 1; `acc_step2 = acc_step >> shift`, 0 → 1; `brake = vmax << shift` |

```
int servo_step(Servo *s) {
    e = s->goal − s->value;
    if (e <= 0 && s->vel <= 0) {
        if ((u16)(−e) < s->brake) { s->vel = e >> s->shift; s->acc = 0; }        // sar; close: proportional
        else { approach(&s->acc, s->acc_step, s->acc_step2); approach(&s->vel, −s->vmax, s->acc); }
    } else if (e >= 0 && s->vel >= 0) {
        if ((u16)e < s->brake) { s->vel = e >> s->shift; s->acc = 0; }
        else { approach(&s->acc, s->acc_step, s->acc_step2); approach(&s->vel, s->vmax, s->acc); }
    } else {                                                                      // moving the wrong way
        approach(&s->acc, s->acc_step, s->acc_step2);
        if (e > 0) { s->vel += s->acc; if (s->vel > e) s->vel = e; }
        else       { s->vel −= s->acc; if (s->vel < e) s->vel = e; }
    }
    s->value += 362b:00be(s->vel);
    return s->value;
}
```
Users: views (`1c30`), gauges (`678a`), the blackout ramp `0fd4` (sim_world).

