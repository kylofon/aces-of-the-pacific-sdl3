# sim_flow part: cockpit — views, cameras, cockpit, gauges, HUD overlays, messages (AP.EXE)

**Status: complete (2026-09-26; §3–§12 added by the finisher).** Part of `port/spec/sim_flow.md` (lead). Target
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


-----------------------------------------------------------------------------------------------

## 3. Cockpit build and panel drawing (`644a` cockpit.c, `4899`, `4963`, `465c:04ee`)

The cockpit of every aircraft is a **TTM script** `<code>.TTM` (video module's TTM player,
`24fc`): the panel, stick, rudder bar, overlays and damage are TTM *tags* played with
`24fc:0610(tag)` (the tag runs its drawing commands on the current page). Views 0–3 (front, rear,
left, right) have pre-rendered backgrounds; view 4/5 (down/up) share the front panel. The panel
background of the front view is also tiled from `.GAU` bitmaps (§5).

Globals (`DS:`): `3ECC` char[] aircraft code (the model's 4-letter code, e.g. `P39`, `J7W`, `F4U?`
— the `.TTM`/`.EDG`/`.GAU` stem), `3ED6` cockpit view shown (0..3, −1 none), `3ED8` 1 = the model
has a second rear view (`D<code>.EDG` exists: the rear gunner's position), `3ED9` pending full rebuilds (2 = both pages), `3EDB`
rebuild forced, `3EDC` last `DS:3EF5`, `3EDE..3EE7` engine-puff state (§3.3), `3EE9` damage-crack
stage 0..7, `3EEB` 1 = view backgrounds cached in EMS (`DS:3EEC/3EEE/3EF0` EMS handles, 64000 bytes
each), `3EF2` model is `P39`, `3EF3` `J7W`, `3EF4` `P80` (special cases), `3EF5` gunner/rear
variant (from sim_world), `3EF7` gauges frozen (player down), `3EF8` oil on the side windscreens,
`3EF9` panel damage stage 1..3, `3EFB` engine state for the puffs (0..3). `3EF5`–`3EFB` are
written by sim_world (`655d:0bd9/159d`); sim_flow reads them.

| Address | Name | Behaviour |
|---|---|---|
| `644a:0000` | `cockpit_load(char *code)` | from the scenario loader (`56ac:0236`): `DS:3EF2/3EF3/3EF4 = strcmp(code, "P39"/"J7W"/"P80") == 0`; `DS:3ED8 = 0`; copy code to `DS:3ECC`; `24fc:0016()`; `h = 24fc:0028(55a4:0000(code, "TTM"))` (load the TTM; −1 → fatal `cockpit.c` A8h); `24fc:03c5(0)`; in the resource dir (`55a4:007f(DS:05F2)` … `55a4:00a2`) play tag 1 (setup). `s` = max over the sizes (`0962:0396`) of `F<code>.EDG`, `B…`, `L…`, `R…`, and `D…` — if the D file exists (size ≠ 0) `DS:3ED8 = 1`; `0962:0009(s + 340h)` (edge arena, §4). `4cad:00ab(code)` (`.GAU`, §5). EMS class `DS:0539 ≥ 4`: allocate three 64000-byte EMS blocks (`24e5:0000(FA00h)`) → `DS:3EEC/3EEE/3EF0`, `DS:3EEB = 1` (any failure frees the earlier ones and sets 0); else `DS:3EEB = 0`. Then `cockpit_prebuild 644a:09b0` |
| `644a:09b0` | `cockpit_prebuild()` near | `368f:01cf()`; draw page = `DS:26D0 + 400h` (the spare page); `cockpit_render_view(0)`; if `DS:3EEB`: `cache_to_ems 644a:0d95` else `cache_to_file 644a:0f2b(DS:3ECC)` |
| `644a:0a35` | `cockpit_render_view(int v)` near | `368f:01cf()`; v 0: `678a:0005()` (tile the panel background), tag 4 (front panel), `678a:0088()` (gauge faces); v 1: tag 0Ah; v 2: tag 2Dh; v 3: tag 21h (tags played inside the resource dir) |
| `644a:0d95` | `cache_to_ems()` near | render views 1, 2, 3 into page `DS:26D0` and copy the 320×200 page into EMS handles `3EEC/3EEE/3EF0` (`24e5:00d7` map, `1d32:5a26` read screen block, `24e5:0139` unmap) |
| `644a:0f2b` | `cache_to_file(char *code)` near | `CPVW.BUF` (`DS:0F38`): read its first 8 bytes; if they equal `code` (the cache is for this aircraft) → done; else rewrite: `fopen("cpvw.buf","wb")`, 8-byte code header (zero padded), then views 1, 2, 3 rendered and each written as 200 rows × 320 bytes (`644a:1096`: `1d32:5a26` one row → `fwrite`). File = 8 + 3·64000 = 192008 bytes (matches the installed file) |
| `644a:09db` | `cockpit_view_background(int v)` near | v 0: copy the whole screen (`1d32:53fe(0,0,DS:2DAA,DS:2DAC)`) from page `DS:26D0+400h` (the pre-rendered front panel); v 1..3: `DS:3EEB` ? `644a:0e5f(v)` (EMS → screen, `1d32:6a8d`) : `644a:1020(v)` (`CPVW.BUF` at offset 8 + (v−1)·64000 → screen row by row, `644a:10e2`) |
| `644a:0271` | `cockpit_frame_bg(int redraw)` | called by `draw_frame` before the world: if `DS:3EF5 != DS:3EDC` and view 1 shown: remember it, `DS:3ED9 = 2`, `DS:3EDB = 1`. `r = DS:3ED9 ? DS:3ED9-- : redraw` (and `DS:3EDB = 0` when not forced). r == 2: if `view_get()` differs from `DS:3ED6` or forced: first *leave* the old view — old 0: `0962:038d` (edge arena reset), tag 7; old 1: `038d`, tag 15h, and if `DS:3ED8` and not forced `644a:0912` (palette back to ACES, below); old 2: `038d`, tag 36h; old 3: `038d`, tag 2Ah — then `DS:3ED6 = view`, draw page `DS:26D0`, `368f:01cf`, and *enter* the new view: 0 → background 0, tag 5, edges `F<code>`; 1 → if `DS:3ED8` (a gunner position) and not forced `644a:0961` (GUNNER palette); `DS:3EF5 == 1` → background 1, tags 14h, 0Bh, edges `D<code>`; else background 1, tags 13h, 0Bh, edges `B<code>`; without `DS:3ED8`: background 1, tag 0Bh, edges `B<code>`; 2 → background 2, tag 2Eh, `L<code>`; 3 → background 3, tag 22h, `R<code>` (edges: `0962:00f1(sprintf(fmt, code))`). r == 1 (or after the above): copy the cockpit window rectangle (`4899:0027` clip) from page `DS:26D0` to the draw page `DS:26D2` (`1d32:53fe`) — for views 0..3 only |
| `644a:0584` | `cockpit_frame_fg(int redraw)` | after the world: `368f:01cf`, `4899:0027`, source page `DS:26D0`, dest `DS:26D2`; `CB = P + ACh`. View 0: `0962:0bf1` (mask on), `engine_puffs 644a:0b0b`; `J7W` only: stick tag by `CB+02` (pitch) < 0 → 57h, > 0 → 55h, else 56h; `0962:0c7f` (mask off); `0962:0655` (glass overlay); panel damage `DS:3EF9` 3 → tags 1Ah, 19h, 18h; 2 → 19h, 18h; 1 → 18h; then tag 6. View 1: mask on; rudder `CB+04` < 0 → tag 0Fh, > 0 → 0Dh, else 0Eh; stick pitch `CB+02` < 0 → 12h, > 0 → 10h, else 11h; tag 0Ch; mask off, glass; damage 3 → 1Dh, 1Ch, 1Bh … (1Bh..1Dh). View 2: mask on, puffs, roll `CB+00` < 0 → 30h, > 0 → 32h, else 31h; flaps `CB+0E & 3` ? 34h : 33h; unless (`P80` and no drop tank `P+1A & 4`) tag 2Fh; mask off, glass; `DS:3EF8` → 42h; damage → 3Eh/3Dh/3Ch. View 3: the same with 26h/24h/25h, 28h/27h, 23h, 41h, 3Bh/3Ah/39h. Then `gauges_draw 678a:034f(redraw)`; if `DS:3EF7`: `678a:0345()` (freeze gauges) and `damage_cracks 644a:0ad9` |
| `644a:0ad9` | `damage_cracks()` near | front view only: tags `4Dh + i` for `i < DS:3EE9`; `DS:3EE9` += 1 up to 7 (one more crack each frame after the player is hit fatally) |
| `644a:088f` | `cockpit_force_rebuild()` | `DS:3ED9 = 2; DS:3EDB = 1` (after the map, `6cdc:0e0b`) |
| `644a:089f` | `cockpit_view_window(int r[4])` → int | `r = {0, 0, 320, …}`: view 0..3: `r[3] = DAT(P)+28h[view]` (window height), return `DAT(P)+30h[view]` (horizon/eye row); other views: `r[3] = 200`, return 100. Used by the renderer (`5440:03aa`, `2466:0023`, `675d:0000`, `6964:01a2`) |
| `644a:0912` | `palette_aces()` near (`inc bp` form; body `0913`) | load `ACES.PAL` (`1d32:3e0b`), copy 300h bytes over `DS:408A` (the sim palette), `1d32:4080` free, `1792:00c0(1)` (re-apply palette effects) |
| `644a:0961` | `palette_gunner()` near (body `0962`) | the same with `GUNNER.PAL` (rear gunner position) |

`4899` (panel top line):

| Address | Name | Behaviour |
|---|---|---|
| `4899:0000` | `fullscreen_view()` | `(s8)DS:00F8` |
| `4899:0009` | `set_panel_top(int y)` | `DS:3CD8 = y`; `DS:00F8 = (y >= DS:2DAC − 1)` (the 3D view uses the whole screen) |
| `4899:0027` | `clip_to_view()` → bottom | if `!DS:00F8` and no clip set (`DS:26C3 == 0`): clip = `(0, 0)–(DS:2DAA−1, DS:3CD8)`, `DS:26C3 = 1`; returns `DS:26CA` |
| `4899:005c` | `limit_window(cam)` | `cam+10h` (window height) clipped so that `cam+0Ch + cam+10h − 1 <= DS:3CD8` |

`4963` (gauge/cockpit state): `4963:0000` → `678a:0000` (empty). `4963:000a cockpit_reset()` (from
`56ac:089e` object creation): `4cad:0000()` (gauge servos, §5.3), `DS:3ED6 = −1`, and zero
`3ED9 3EDB 3EDC 3EDF 3EE1 3EE3 3EE5 3EE7 3EE9 3EF5 3EF7 3EF8 3EF9 3EFB`, `DS:3EDE = 1`.

`465c:04ee screenshot_name()` → char* (used by the Alt+T screenshot, lead §5.2): `DS:3AF4` = first
4 characters of the aircraft name (`DAT(P)+0Ah`, zero padded) + `"__"` (`DS:00CD`); then
`itoa(DS:00CB++, DS:3AF8, 10)` overwrites from the 5th character; append `".LBM"` (`DS:00D0`).
E.g. `F4U_0.LBM`, `F4U_1.LBM` … (counter `DS:00CB` from 0 per run).

### 3.3 Engine start puffs (`644a:0b0b engine_puffs`, near; body `0b0c`)

Exhaust smoke sprites drawn on the cowling in views 0 (single-engine models, `model.90h <= 1`,
`!(DAT.53h & 1)`, not `P39`) and 2/3 (`!(DAT.53h & 2)`, not `P39`). Sprites from the set
`DS:519C->+7Ah` (`1d32:21b6(set, x, y, flags)`).
```
if DS:3EDF != DS:3EFB or DS:3EDE:                       // engine state changed
    DS:3EDF = DS:3EFB; DS:3EDE = 0
    switch DS:3EFB: 0 → d1 = −1, d2 = 0
                    1 → d1 = (rand() & 15) + 1; d2 = (rand() & 3) + 1
                    2 → d1 = (rand() & 3) + 1;  d2 = (rand() & 15) + 1
                    3 → d1 = 0, d2 = −1                   // d1 = DS:3EE5, d2 = DS:3EE7
T = view 0 ? DS:0F18 : DS:0F28;  e = T + 4·phase (DS:3EE1)   // {frames, list}
if e.frames <= frame (DS:3EE3):
    frame = 0
    phase 0: d1 == −1 → stay; d1 → d1−−; else phase 1, e += 4
    phase 1: phase 2, e += 4
    phase 2: d2 == −1 → stay; d2 → d2−−; else phase 3, e += 4
    phase 3: phase 0, e = DS:0F18 (sic, the front table), DS:3EDE = 1
if e.list: f = e.list + 4·frame = {n, spr}; for each of the n 6-byte entries {x, y, flags}:
    view 0: draw at (x, y+7, flags) and mirrored at (319 − x − width, y+7, flags ^ 2)
    view 2: (x, y, flags); view 3: mirrored only
    frame++
```
Tables (verified dump): front `DS:0F18` phases 0..3 = 0/2/4/2 frames, side `DS:0F28` = 0/2/4/2
(entries listed in `puff.py` output: e.g. front phase 1 frame 1 = (110,90,1) (85,91,1) (53,94,1)
(25,95,0)). `rand()` is Borland's LCG (results part §2).

-----------------------------------------------------------------------------------------------

## 4. Cockpit window masks (`0962`, `0a7b`, `.EDG`)

The 3D world is drawn *through* the cockpit windows: while the mask is on, the video driver's span
fill vectors are replaced by `0962` routines that intersect every horizontal span with the window
region of the current view.

### 4.1 `.EDG` file (`<V><code>.EDG`, V = F front, B back, L left, R right, D rear view from the gunner's position — used instead of B when `DS:3EF5 == 1`) — verified

```
u16 nA;  nA × {s16 y0, s16 y1}                 // rows fully open (y0..y1 inclusive)
u16 nB;  nB × { s16 y, u16 n; n × {s16 x0, s16 x1} }   // window polygons: row y+i open from x0..x1
u16 nC;  nC × { s16 y, u16 n; n × {s16 x0, s16 x1} }   // overlay polygons drawn after the panel
```
Loaded by `0962:00f1(name)` into the arena: `DS:5674`→A (count `DS:5678`), `DS:566E`→B pointers
(count `DS:5672`) with per-polygon x bounds `DS:566A[i] = {min x0, max x1}`, `DS:5664`→C pointers
(count `DS:5668`). All 149 shipped files parse exactly (helper's `edgstat.py`).

### 4.2 Functions

| Address | Name | Behaviour |
|---|---|---|
| `0962:0009` | `edge_arena_init(int size)` | far alloc `size` → `DS:142E`, capacity `DS:1432`, cursor `DS:1434`, used `DS:1438 = 0`; allocate the 340h-byte span buffer `DS:567A`; `DS:5680 = DS:3172`, `DS:567E = 0` |
| `0962:005a` | `edge_arena_free()` | free and zero (from `6b3d:00ac`, mission exit) |
| `0962:0095` | `edge_alloc(int n)` → far ptr | bump allocation; 0 when it would exceed the capacity |
| `0962:00cb` / `00de` | `edge_mark()` / `edge_release()` | save / restore cursor and used (per view: `00f1` marks, `038d` releases) |
| `0962:00f1` | `edge_load(char *name)` | `edge_mark()`; open `55a4:0000(name,"EDG")`; read A, B, C as above (`55a4:0108` far reads) |
| `0962:038d` | `edge_unload()` | `edge_release()` |
| `0962:0396` | `file_size(char *name)` → int | `fopen` + `0000:0ae8` (filelength), close; 0 if missing |
| `0962:0bf1` | `mask_on()` | save six video vectors (`DS:31E0`, `3436`, `3522`, `3572`, `3586`, `358E` — span/rect fill entry points of the loaded driver) into `DS:564C..5660` and install the masked versions (`0962:08de`, `0cc6`, `0e47`, `1023` …); `DS:1440 = 1` |
| `0962:0c7f` | `mask_off()` | restore the vectors, `DS:1440 = 0` |
| `0962:0520` | `span_in_rows(span)` | a span record `{x0? , y, …}` against the A ranges: rows fully inside a range are passed to the saved routine unchanged (return 1) |
| `0962:079a` | `span_through_windows(span)` | if not in an A range: for each B polygon intersect the span list with the polygon (`0a7b:000c`) and call the saved routine for the result |
| `0962:0819` | `pixel_rows(...)` | the single-row variant for the other vector (`DS:565C`) |
| `0962:08de`, `0cc6`, `0e47`, `1023` | masked driver entry points | wrap span fills / rectangle fills / sprite draws / line draws (`1d32:1e17/1e9d/1e7a/1eca/49f4/5e5b/3de5`) so that only pixels inside the window region are written; the clip rectangle `DS:26C3..26CA` is honoured |
| `0962:0655` | `glass_overlay()` | after the panel: for each C polygon clipped to the clip rows `DS:26C8..26CA` draw it with `1d32:09bb` (span-list draw, platform) — *likely* the canopy frame/glass edges |
| `0a7b:000c` | `span_intersect(far a, b, far out)` | asm: two span lists `{u16 y0, u16 n; n × {x0, x1}}` → the row-wise intersection written to `out` (rows where both exist; per row `max(x0)`, `min(x1)`, rows with an empty result end the list) |

**Port:** build a per-view 320×200 byte mask from A ∪ B (rows of A fully set, B spans set) at
load time and clip the world rasteriser to it; draw C after the panel. Faithful pixel results
only require the same set of pixels.

-----------------------------------------------------------------------------------------------

## 5. Gauges (`4cad` `.GAU`, `678a`)

### 5.1 `.GAU` file (`<code>.GAU`, loaded by `4cad:00ab gau_load(code)`) — verified

`char[14]` panel tile bitmap (→ `DS:3F3A`), `u16` first tile row (→ `DS:3F48`), `char[14]`
common gauge bitmap set (loaded with `6f97:0000` → `DS:3F4A`), `u16 n` (→ `DS:3F4C`), then n
records of 28 bytes, expanded to 44-byte `Gauge` records (far array `DS:3F4E`):

| Mem off | File off | Type | Meaning |
|---|---|---|---|
| +00 | +00 | u16 | kind 0..19 (below); also sets bit `kind` in `DS:3FCF` (kinds present) |
| +02 | +02 | char[14] | face bitmap (drawn once, frame 0, at (x, y)) |
| +10 | — | 4 × s16 | dirty rectangle for page parity 0 (x0, y0, x1, y1) |
| +18 | — | 4 × s16 | dirty rectangle for parity 1 |
| +20 | +10 | u16 | frame index in the common set (needle/lamp/digit art) |
| +22, +24 | +12, +14 | s16 | face x, y |
| +26, +28 | +16, +18 | s16 | centre offset cx, cy (pivot = x+cx, y+cy) |
| +2A | +1A | s16 | needle length |

### 5.2 Values (`678a:010b gauges_update`, every sim step) — verified

```
DS:3FD2 (s32) = FM(P).0Ah − model.98h            // altitude above the gear point (P.64 FmState)
DS:3FD6 = P.94h (airspeed); DS:3FDA = P.12h (roll); DS:3FDC = P.14h (heading); DS:3FEC = P.B0h
DS:3FEE bit4 = ((P.AAh >> 1) | P.AAh) & 1
DS:3FEF bit0 = P.BAh bit2 (dive brakes), bits1–2 = P.BAh & 3 (flaps), bit3 = !(P.BAh bit4) (gear up)
m = 0b01:1a95(&P.64)                              // max RPM reference (sim_world)
w = 277a:41c4(P.94h, 0, m, 0, 1000h)              // windmilling RPM from the airspeed
for engine e in {1: P.A4h / servo DS:3F96 / DS:3FDE,  2 (only if kind 6 present): P.A6h / DS:3FA8 / DS:3FE0}:
    t = ((P.B2h << 4) · health_e) >> 10           // throttle × engine condition
    goal = t > w ? w + (3·(t − w) >> 2) : t + (5·(w − t) >> 4)
    do v = servo_step(servo) while (DS:3FCC and |goal − servo.value| > 20)   // first frame: settle
    out = clamp(v >> 2, 0, 400h)                  // 35ff:0009
servo DS:3FBA.goal = P.9Ch; do v = servo_step while (first and |…| > 20); DS:3FD8 = v   // VSI
DS:3FCC = 0
```
Servos (`4cad:0000 gauges_reset`): `DS:3F96` vmax 200h shift 2, `DS:3FA8` vmax 200h shift 2,
`DS:3FBA` vmax 100h shift 2 (`servo_init`); `DS:3F94 = 0`, `DS:3FCC = 1`, `DS:3FCD = DS:3FCE = 0`,
`DS:3FEE` bits 0–3, 5–7 cleared. Other inputs written by sim_world: `DS:3FE2`/`3FE4` gun ammo
(`0769`, `4cda`), `DS:3FE6` rockets (`1a32`), `DS:3FE8`/`3FEA` fuel (`655d:159d`), `DS:3FEE`
lamp bits.

### 5.3 Drawing

`678a:034f gauges_draw(int redraw)` (front view only): `r = DS:3FCE ? 1 : redraw` (`DS:3FCE`
cleared); for each record call the kind's routine `DS:10B6[kind](rec, r)` (far pointers through the
stub table `3E0A:005C + 5·kind`); then `DS:3F94 ^= 1` (page parity). Every routine: value `v` =
the live value, or when `DS:3FCD` (frozen) the parity-0 cached value; unless `r`, skip when
`v == cache[parity]` (caches `DS:3F52 + 21h·parity + k`); store; erase the old needle rectangle
(`678a:04db`: copy rect ±1 from the background page, clipped to `DS:26C4..26CA`); draw; store the
new bounding rectangle (`678a:041d` union for two needles). Needles: `678a:047e needle(x, y, len,
angle, rect)` = line `(x, y)`–`(x + mul_sin(len, angle), y + mul_cos(len, angle))` in colour `DS:26CE`
(= FAh), angle 10000h = 360°. Pivot `(px, py) = (x + cx, y + cy)`.

| Kind | Routine | Value | Drawing |
|---|---|---|---|
| 0 altimeter | `0563` | `DS:3FD2` (s32) | long needle `angle = (80h − satdiv(((alt % 400) << 6), 100)) << 8`, length len; short needle `(80h − satdiv(alt << 6, 1000)) << 8`, length len/2; digits `sprintf("%02hd", satdiv(alt<<6,1000) >> 8)` at (px − 4, py + 4), font `DS:3F2E`, colour FAh. So 400 units per turn of the long needle, 4000 per turn of the short one and per digit step (with ¼-ft units: 100 ft / 1000 ft) |
| 1 airspeed | `0704` | `max(DS:3FD6, 0)` | `a = 41c4(v, 0, 7200, 0, 100h)`; angle `(80h − a) << 8` |
| 2 VSI | `07e6` | `DS:3FD8` (s16; 8000h → 7FFFh) | piecewise on `|v|`: < 118h → `41c4(|v|, 0, 118h, 0, 1Eh)`; < 230h → `41c4(…, 118h, 230h, 1Eh, 40h)`; < 690h → `(230h, 690h, 40h, 80h)`; else 80h; negated for v < 0; angle `(C0h − a) << 8` |
| 3 artificial horizon / bank | `090c` | `DS:3FDA` (roll) | bar through (px+7, py+2) at angle roll + 4000h, half-length len (both directions), plus the common frame `rec.20` at (px, py) |
| 4 compass | `0a37` | `DS:3FDC` (heading) | strip bitmap `rec.20` drawn at x = px + `41c4((FFFFh − h) >> 8, 0, FFh, 0, −203)` − 3, clipped to (px−1, py−2)–(px + 2·len − 1, py + 6) |
| 5 / 6 tachometer 1 / 2 | `0b98` / `0c59` | `DS:3FDE` / `DS:3FE0` | `a = 41c4(v, 0, 400h, 0, E8h)`; needle |
| 7 / 8 ammo counters | `0d1a` / `0e6d` | `DS:3FE2` / `DS:3FE4` + lamp `DS:3FEE` bit5 / (bit of 3FEE) | background frame `rec.20` (+1 when the lamp is on), `sprintf("%04hd")` at (px + 12, py) |
| 9 rockets | `0fc0` | `DS:3FE6` | `"%02hd"` |
| 10 fuel | `109b` | `DS:3FE8`, `DS:3FEA` (each clamped to 3FFh) + lamp `DS:3FEE` bit7 | two needles: `41c4(v1, 0, 3FFh, 1Ah, 5Ch)` and `41c4(v2, 0, 3FFh, E6h, A2h)` (opposite arcs) |
| 11 | `1258` | `DS:3FEC` (`P.B0h`) | clamped `35ff:0009(v, 1, FFh)` → frame of `rec.20` (8000h special) |
| 12–16 lamps | `1365`, `1419`, `14d5`, `1595`, `1655` | `DS:3FEE` bits 0–4 (bit 4 = `P.AAh` warning) | frame `rec.20` (+1 when on) |
| 17 dive-brake lamp | `1715` | `DS:3FEF` bit0 | on/off frame |
| 18 flaps indicator | `17c9` | `DS:3FEF` bits 1–2 (0..2) | frame `rec.20 + state` |
| 19 gear lamp | `18bc` | `DS:3FEF` bit3 | on/off frame |

Helpers: `678a:0005 panel_tiles()` — load `DS:3F3A`, tile the screen from row `DS:3F48` down
with frame `rand() & 3` of the tile set (consumes Borland `rand()`), free; `678a:0088
gauge_faces()` — load each record's face bitmap and draw frame 0 at (x, y); `678a:033b
gauges_dirty()` → `DS:3FCE = 1` (a message box was erased over the panel; the arguments are
ignored); `678a:0345 gauges_freeze()` → `DS:3FCD = 1`; `678a:03ad set_rect(a, b, c, d, far r)`;
`678a:03d0 rect_from_line(x0, y0, x1, y1, far r)` (sorted); `678a:041d rect_union(a, b, far r)`;
`678a:0000` empty.

-----------------------------------------------------------------------------------------------

## 6. Messages and text

### 6.1 STR_POOL (`4bb7`, `0ab0` english.c)

`STR_POOL.DAT` (SIM1): `u16 size`, then `size` bytes: a word table — word `g` = index (in words)
of group g's id table; `word[word[g] + id]` = byte offset of the string (from the start of the
data). Loaded once by `4bb7:007f str_pool_load()` (`55a4:0000("str_pool","dat")`, fatal
`english.c` 5Ch/65h) into a movable memory handle `DS:3F20` (`1d32:22f4`), read in 20-byte
chunks by `4bb7:0000 fread_far(far dst, u32 size, u32 count, FILE*)` (also used by `6f83`,
`6f97`, `6fe3` bitmap loaders).

| Address | Name | Behaviour |
|---|---|---|
| `0ab0:000b` | `str(int group, int id)` → char far* (DS) | lock `DS:3F20`; offset as above; `2494:0009` copies the string to a static near buffer; unlock; returns `DS:ax` |
| `0ab0:0066` | `str0(int id)` | `str(0, id)` |
| `0ab0:0080` | `word_wrap(char *s, int width)` → lines (near) | in place: `'\n'` → NUL (new line); at each space, if the text since the last break is wider than `width` (`1d32:5570` string width in the current font) break at the previous space; a single word wider than `width` is fatal (`english.c` DBh); returns the number of lines |

### 6.2 Message lines (`1614` message.c, `6939`)

Two slots at `DS:5B1A` (21 bytes each; slot 0 = priorities ≤ 3, drawn at the top; slot 1 =
priorities > 3, at the bottom):

| Off | Type | Meaning |
|---|---|---|
| +00 | far char* | text (a copy in far `3A31:(15h + 96h·k)`, k = `DS:18D0` = 0..3 rotating) |
| +04 | far char* | speaker label or 0 |
| +08 | s16 | life (dt units), from `DS:18CC` = 186Ah (6250 ≈ 24 nominal steps) |
| +0A | s16 | priority; 0 empty, −1 expired (erase pending) |
| +0C | u8 | draw state: 1 new, 2 replaced (erase the old box first), 0 steady |
| +0D..+13 | 4 × s16 | box x, y, w, h (last drawn) |

| Address | Name | Behaviour |
|---|---|---|
| `1614:000e` | `msg_init()` | zero both slots |
| `1614:024e` | `msg_show(far char *s, int prio, far char *speaker)` | `s == 0` → nothing; slot = prio > 3; if `slot.prio > prio` → nothing (a more important message shows); `slot.text = _fstrcpy(next rotating buffer, s)`; `slot.life = DS:18CC`; `slot.speaker = speaker`; `slot.state = slot.prio ? 2 : 1`; `slot.prio = prio` |
| `1614:0023` | `msg_tick()` (sim step) | each non-empty slot: `timer16_dec(&life)`; `life <= 0` → `prio = −1` |
| `1614:005b` | `msg_draw(int redraw)` (draw_frame) | each live slot (`prio ∉ {0, −1}`): if `state` or `redraw == 2`: draw page `DS:26D2`, `msg_box 6939:0000(slot)`; state 2 → box = component-wise max of old and new (`DS:3BC3..3BC9`), else the new box; `state = 0`. Steady slots: copy the box from the displayed page `DS:26D4` to `DS:26D2` |
| `1614:019a` | `msg_erase()` (draw_frame, before the world) | a pending extra box `DS:18CE` → `DS:18CE = 6939:020f(0)`; the first expired slot: `DS:18CE = 6939:020f(slot)`, `prio = 0`, return; replaced slots (state 2), unless the VCR panel covers them (`DS:08D5` and y ≥ 100): restore the old box from `DS:26D0` to `DS:26D2` and, in cockpit views, `gauges_dirty()` |
| `1614:02c3` | `msg_clear_top()` | slot 0 `prio = −1` |
| `1614:02ce` | `msg_clear_all()` | both `prio = −1` (from `655d:159d`) |
| `6939:0000` | `msg_box(slot)` | font `DS:3F2E`; `lines = word_wrap(near copy of text, 316)` (+1 with a speaker); `h = lines·fh + 2`; slot 0: text colour `DS:26C0` = (prio == 3 ? CFh : FFh), y = 0; slot 1: FEh, y = 200 − h; x = 0, w = 320 → `DS:3BC9/3BC7/3BC5/3BC3`; `47a8:0077` (save draw state); frame lines top C6h, bottom C9h, left and right C7h (`1d32:5ab5`); `47a8:005d(1)`; fill C8h (`1d32:6ab0`); `DS:26C2 = 1` (transparent text); y + 1; with a speaker y += fh, lines−−; draw the lines at x + 4 (`1d32:5845`); with a speaker draw `name + ':'` at x + 4 on the next row (**as coded the speaker comes out below the text and the first row stays empty**; no caller seen passing a speaker); `47a8:0094` (restore) |
| `6939:020f` | `msg_unbox(slot)` → 1/0 | dest `DS:26D2`, source `DS:26D0`. slot ≠ 0: outside the cockpit (`!DS:19F2`) return 0 without copying (outside views redraw the whole screen); else remember `DS:51AA/51AC/51AE/51B0` = (x, y − h if y ≠ 0 else 0, w, 2·h), result 1. slot == 0: reuse the remembered box, result 0. Then copy the remembered box unless the VCR panel covers it (`DS:08D5` and y ≥ 100) and, in cockpit views, `gauges_dirty()` |

Callers show messages with priority 1 (normal), 2 (LSO, aileron lock), 3 (warnings), 5 (radio).

### 6.3 Radio messages (`1815`)

Templates are STR_POOL strings with escapes. Escape char `DS:5C8C` = first char of STR(5, 0)
(`'%'`), quote char `DS:5C8A` = first char of STR(5, 1Eh) (`'|'`, printed as `"`), loaded by
`1815:070e radio_init()`.

Radio context `RadioCtx` (24 bytes, from the AI callers): `+00 s16` relative bearing, `+02 s32`
altitude difference, `+06 s32` value for `%a`, `+0A u16` aircraft type, `+0C s8` count, `+0E far
char*` name, `+12 s32` distance, `+16 Object*` who.

`1815:00dc radio_expand(char *buf, RadioCtx *c)` → 1 if escapes remain (one pass):

| Code | Output |
|---|---|
| `%e` | `c.02 > 4000` → " " + STR(5, 1Ah) "high"; `< −4000` → " " + STR(5, 19h) "low"; else nothing |
| `%n` | clock position `n = (u16)(−c.00 − 0AABh) / 1556h + 1` (1..12) as a word (≤ 12: STR(4, n) "one".."twelve", else digits) |
| `%#` | `c.0C` as a word; remembers that a number was printed |
| `%p` | aircraft name `DAT(type c.0A).0Ah`; plural when `%#` was printed and `c.0C > 1` (`1815:002f`: ends in 's' → append `'`, else append `s`) |
| `%a` | `5b91:0000(c.06)` as a number (≤ 12 words) |
| `%B` | `c.02 < 0` ? STR(7, 21h) : STR(7, 22h) |
| `%b` | `c.00 > 0` ? STR(7, 21h) "Break left!" : STR(7, 22h) "Break right!" |
| `%E` | `side(P) == 0` ? STR(7, 1) "Bandits" : STR(7, 0) "Enemies" |
| `%d` | itoa(`c.12`) + `" UNITS"` (`DS:1924`) |
| `%o` | STR(5, 1Ch) = `"%n o'clock%e"` (expanded in the next pass) |
| `%r` / `%R` | rank `STR(7, 4Bh + DS:1912[56ac:022e()])` (the player's rank; `%R` capitalised with `toupper`) |
| `%t` | the far string `c.0E` |
| `%w` | speaker: `c.16` = P → STR(7, 27h) "Gunner"; = the player's leader (`P.DDh` or P) → 24h "Section leader"; its leader is the player's leader → 23h "Wingman"; else by serial numbers (`+C9h`) of the two leaders: less → 25h "Flight leader", else 26h "Other section"; then `":  "` (`DS:192B`) |
| `%` + other | nothing (the code char is consumed) |

`1815:0546 radio_show(group, id, RadioCtx *c)`: `buf = STR(group, id)`; `while (radio_expand(buf,
c)) ;`; `msg_show(buf, 5, 0)` (bottom slot).
Delayed queue: two slots at `DS:5C26` (50 bytes: +00 24-byte ctx copy, +18 id, +1A timer, +1C
group, +1D has ctx, +1E name copy):
`1815:05e0 radio_queue(group, id, RadioCtx *c, int delay)`: `delay == 0` → `radio_show` now. Else
use the first slot with timer 0; if none, evict the one with the smallest timer (< 7D1h) after
showing it at once (quirk: with the **new** group number); store id, timer = 2000 (7D0h dt
units), group, `has = c != 0`, the ctx (24 bytes) and a copy of `c.0E` into +1E (the stored ctx's
name pointer is re-pointed at it).
`1815:0593 radio_tick()` (sim step): each slot with a timer: `timer16_dec`; reaching 0 →
`radio_show(slot.group, slot.id, slot.has ? slot : 0)`.
`1815:06d0 radio_queue5(id, c, delay)` = `radio_queue(5, …)`; `1815:06e7 radio_queue7(id, c,
delay)`: only while the player is alive (`!1142:0000(P)`) → `radio_queue(7, …)`.
Small helpers: `1815:0004 clock(int a)`, `1815:0019 itoa10(char*, s32)` (`0000:3d44`),
`1815:0068 number_word(char*, s32 n, int max)` (STR(4, n) when 0 ≤ n ≤ 12 and ≤ max, else
digits), `1815:00ad units(char*, s32)`.

### 6.4 Advisories (`10e5`) and repeating warnings (`1ba4`)

`1ba4:0003 warn_init(W *w, group, id, prio)`: `w = {u32 next = DS:4086, group, id, prio}`.
`1ba4:0026 warn_tick(W *w)`: if `w.next <= DS:4086` (mission time): `w.next = DS:4086 + 6400h`
(100 nominal steps) and `msg_show(str(w.group, w.id), w.prio, 0)`.

`10e5:0005 advice_init()` (mission start): zero `DS:57C6..57DB`, `DS:57DD..57E9`; `DS:57DB =
DS:57E8 = −1`; if the player starts in state `P.4Ah` ∈ {3F4h, 408h} (on the deck/ground):
`DS:57D3 = 1900h` (when to say "Give it full throttle"), and if the model has no retractable
gear (`!(DS:3FD1 & 8)`) `DS:57CD = 1`; else (airborne start) `DS:57CF = 1` (no take-off advice).
Warnings: `DS:57B2` = (1, 8 "external fuel tank is empty. Drop it.", prio 3), `DS:57BC` = (1, 11h
"engine is overheating", 3), `DS:57A8` = (1, 0Fh "compressibility", 3), `DS:579E` = (1, 10h
"aileron lock", 2).

`10e5:00ac advice_step()` (sim step, unless messages are off or the player is down; lead §6.1).
The one-shot event flags `DS:57DD..57E7` are set by sim_world during the step and **cleared at the
end of every call**; only the first matching line fires (return after a message):
```
57E7 → msg(1, 45h "The bomb blast has damaged your aircraft!", 3)
57DD → warn_tick(57A8); 57DE → warn_tick(57BC)
57E0 and !57D2 → msg(1, 7 "Warning! You are low on fuel.", 3), 57D2 = 1
57E1 → warn_tick(57B2)
fm = P.64 (FmState): if 57C8: 57C8 = (fm.46h >> 1) & 1
spin (fm.46h & 4): !57C9 → 57C9 = 1, msg(1, 0Dh "entered a spin!", 3), return   (else continue)
                   not spinning → 57C9 = 0
stalled (fm.46h & 1): !57C7 → 57C7 = 1, msg(1, 0Ch "has stalled!", 3), return
not stalled and 57C7 → 1614:02c3, msg(1, 0Eh "Stall recovered.", 1), 57C7 = 0, 57C8 = 1, return
fm.46h & 2 (stall warning) and !57C8: !57C6 → 57C6 = 1, msg(1, 0Bh "about to stall", 3), return
                                  else 57C6 = 0
57E8 != 57DB: 57DB = 57E8; if 57E8 >= 0: msg(1, 3Ch + 57E8, 2) (LSO call, below), return
57E2 → warn_tick(579E)
57DF and !57D1 → msg(1, 0Ah "You are out of fuel...", 1), 57D1 = 1
57E5 → msg(1, 3Bh "torpedo didn't arm", 1);  57E6 → msg(1, 44h "torpedo failed on entry", 1)
57E4 → msg(1, 1 "Selected guns are out of ammo.", 1);  57E3 → msg(1, 0 "All guns are out of ammo.", 1)
if !57CF (take-off advice):
    57CB = fm.08h > 0
    !57CB and DS:4086 > 57D3 → msg(1, 16h "Give it full throttle.", 1)
    elif !57CC and fm.08h > 80: on the ground (CB.0C + model(fm.02).98h == P.0C) →
             msg(1, 17h "Pull back on the stick.", 1); else (just airborne) 57CC = 1,
             57D3 = DS:4086 + 3200h, 57D7 = DS:4086 + 4B00h
    elif 57CC and !57CD and DS:4086 > 57D3: gear down (CB.0E & 10h) → msg(1, 18h "Raise your
             landing gear.", 1); else 57CD = 1
    elif 57CC and !57CE and DS:4086 > 57D7: flaps (CB.0E & 3) → msg(1, 1Ah "Raise your flaps.", 1);
             else 57CE = 57CF = 1
clear DS:57DD..57E7
```
LSO calls (`DS:57E8`, written by `6dfc:0000`): 0 "No good. Abort landing.", 1 "Too fast. Slow
down.", 2 "Too slow. Speed up.", 3 "Too low. Climb slightly.", 4 "Move to the left slightly.",
5 "Everything's O.K.", 6 "Cut engine and land.", 7 "Move to the right slightly.".
`1133:0001` (at `10e5:04e1` in the flat image; sim_world's segment) sets `DS:57CF = 1` after an
autopilot jump.

-----------------------------------------------------------------------------------------------

## 7. Radio command menu (`6e5a`, `1660` menu subset)

Player → wingmen orders and reports. Opened with command 9 (key S, lead §7 step 4), keys F1–F7
pick a line (commands 18h–1Eh), Esc cancels.

State: `DS:1206` menu open, `DS:1207` selected line (−2 none, −1 the Esc line), `DS:1209` drawn,
`DS:5240` lines, `DS:5242..5248` box h, w, y, x, `DS:524A` 62-byte line buffers, `DS:523E`
rebuild request; order state `DS:5BD0` page (−2 top, 0..2 recipient chosen: wingman / other
section / whole flight, 2 also = spotting reports), `DS:5BCE` sub-menu flag, `DS:5BD2` step,
`DS:5BCC` "nothing seen" repeat count (0..2).

| Address | Name | Behaviour |
|---|---|---|
| `1660:0f6e` | `orders_reset()` | `DS:5BD0 = −2; DS:5BCE = DS:5BD2 = 0` (menu opened) |
| `1660:110f` | `orders_items(u16 *items, int max)` → n (near-called far) | `k = 1142:0f5f(P.flight, list)` (members of the player's group); members ≠ P within 80000 (d2) are counted, with the flight leader (`+DDh == 0`) and those led by P noted; `h = 1660:0706(P, 2, 0)`. None near → only the LSO item. `DS:5BD2 == 2` (choose a recipient): 2Eh "Your wingman" if P leads someone, 2Fh "The other section" if a leader is near, 30h "The entire flight" if more than one. Else if `!DS:5BCE` and (`h ? P.flight.3B & 1 : 583c:0b51(buf, P, 0)`) is false: items 45h–48h (enemies ahead/behind/left/right), `DS:5BD0 = 2`, and if P leads (`583c:1a7c`) append the order items `1660:0c12(items, n, 0706(P, DS:5BD0, 0))`, `DS:5BD2 = 1`; otherwise (or `DS:5BCE`) the order list `1660:0c47(items, max, list, k)`. Finally, unless `DS:5BCE`, if a carrier landing can be requested (`6dfc:0413()`) append 49h "Request landing" and `DS:5BD0 = max(DS:5BD0, −1)` |
| `1660:0f5f` | `orders_title()` | `DS:1900[DS:5BD0]`: −1 → 28h "Send message to:", 0 → 29h, 1 → 2Bh, 2 → 2Ch (STR group 7); the −2 entry reads `DS:18FC` (6, unused) |
| `1660:0685` | `order_text(code, index, char *dst)` | the item's STR(7, code) expanded against the order target (`1815:00dc`; `1660:0009` builds aircraft names with plural `s`) |
| `1660:0f85` | `order_send(code, index)` → 1 sent / 0 menu continues | 2Eh–30h: `DS:5BD0 = code − 2Eh`, `6e5a:0396` (rebuild), if step 2 → `DS:5BCE = 1`, step 0; return 0. 45h–48h (spotting report in direction `DS:187C[code]` = 0, 8000h, 4000h, C000h): `r = 583c:132f(dir, &b, &ctx)`; bit 0 → `radio_queue5(5 + s, ctx, 1)` ("Roger, I see 'em"; s = side(P) == 1); bit 1 → `radio_queue5(7 + s, …)` ("aren't bandits"); else `radio_queue5(DS:5BCC + (P leads ? 0 : 3) + 6·s + 9, ctx, 1)` (escalating "I see nothing … stay off the radio") and `DS:5BCC = min(DS:5BCC + 1, 2)`; return 1. 31h/32h ("Attack the.."/"Strike the.."): step 0 → `DS:5BCE = 1`, else step 2; rebuild; return 0. 49h: `6dfc:0400()` (LSO: cleared to land); return 1. Others: `1660:01bc(code, DS:5BD0, code 40h–42h ? &DS:5B6C[12·index] : 0)` (the order is executed by the wingman AI, sim_world); return 1 |
| `6e5a:0000` | `radio_menu_build(int n, u16 *items)` | font `DS:3F2E`; line 0 = `order_text(orders_title())`; lines 1..n = `"F<i> "` (`DS:120A`, digit `'1'+i`) + `order_text(items[i], i)`; the last line = `order_text(2Dh)` "   ESC to Cancel"; `DS:5240 = n + 2`; width = max(text widths + 2, width("SEND RADIO MESSAGE:" `DS:11F2`, font `DS:3F30`) + 24) + 12; x = (320 − w)/2, y = 25, h = fh(3F30) + fh(3F2E)·lines + 16; opens the menu (`DS:1206 = 1`, `DS:1207 = −2`) if closed; `DS:1209 = 0` |
| `6e5a:01a0` | `radio_menu_draw(int redraw)` | not yet drawn or `redraw == 2`: dialog frame `47a8:0ae1`, title with `53ec:01e6` (shadow colours C1h/B1h/C0h), inner panel `47a8:0477`, lines in colour C1h; `DS:1209 = 1`. Else copy the box from the displayed page. A selection (`DS:1207 > −2`) is highlighted (fill B9h/BEh behind the line, text redrawn) and `DS:1209 = 0` |
| `6e5a:03a1` | `radio_menu_key(int cmd)` → selection | rebuild requested (`DS:523E`) → clear it, `DS:1207 = −2`; a selection made last frame → close (`DS:1206 = 0`, `DS:4090 = 2`, `5b93:01e2`, `5cde:0000`), `DS:1207 = −2`; `cmd == 1Fh` (Esc) → −1; `18h <= cmd <= 1Eh` and `cmd − 18h < DS:5240 − 2` → `cmd − 18h`. Returns `DS:1207` |
| `6e5a:038b` / `0396` | `DS:523E = 0` / `1` | |

The order handler `1660:01bc` and the target/threat evaluation `1660:07bb/0bae/0c12/0c47` are AI
code (sim_world's rows exist); sim_flow only builds the menu.

-----------------------------------------------------------------------------------------------

## 8. LSO signal overlay (`6dfc:0497/04ce`, `50c0`)

`50c0:0000 lso_load()`: sprite set `sig_j.BMP` (Japanese player, `side(P) == 1`) or `sig_a.BMP`
(`1d32:214e`) → `DS:11F0`; `4b9e:0000()`. `50c0:004a lso_free()`: `bmp_free_ems(DS:11F0)` (`1d32:2170`) if non-zero, then `DS:11F0 = 0`. `50c0:0068 lso_reset()`:
`DS:5238 = 0`, `DS:523B = −1` (no signal), `DS:5236 = DS:5239 = 0`. `50c0:0080` = `debug_mode()`
(lead).

`6dfc:04ce lso_draw()` (after the messages): if `DS:523B >= 0` (signal from `6dfc:0000`,
sim_world) and not (inside the cockpit in a view other than 0): sprite 0 (the LSO) at (230, 10);
the paddles at (266 − w/2, 66 − h): signal 4 → sprite 5, flags 0; 7 → sprite 5 mirrored (flags
2); 1 → sprite `s+1` mirrored; other s → sprite `s+1`; `DS:5238 = 2`.
`6dfc:0497 lso_erase()`: when there is no signal and `DS:5238`: copy (230, 10, 80, 62) from
`DS:26D0` to `DS:26D2`, `DS:5238−−`.

-----------------------------------------------------------------------------------------------

## 9. File formats (summary)

* `<code>.TTM` — cockpit TTM script (video format); tags used: 1 setup, 4 front panel render, 5
  front view enter, 6 front overlay, 7/15h/36h/2Ah view leave (0..3), 0Ah/2Dh/21h pre-render of
  views 1..3, 0Bh–14h rear view, 18h–1Ah / 1Bh–1Dh / 3Ch–3Eh / 39h–3Bh panel damage per view,
  0Ch–12h rear stick/rudder, 22h–28h / 2Eh–34h side views, 2Fh/23h drop tank, 41h/42h oil,
  4Dh–53h damage cracks, 55h–57h J7W stick.
* `<V><code>.EDG` — §4.1. `<code>.GAU` — §5.1. `CPVW.BUF` — §3 (8-byte code + 3 × 64000).
* `STR_POOL.DAT` — §6.1. `SIMPREFS.PRF` +0Ah — the 10 saved views (§2.2).

## 10. Port notes

* The cockpit is TTM-driven: the port needs the video module's TTM interpreter with the same tag
  semantics; `CPVW.BUF`/EMS caching can be replaced by in-memory copies (`/* PORT: */`).
* Window masks: render the world into a buffer and composite through a per-view mask (§4) — the
  driver-vector patching is an implementation detail.
* `rand()` consumption by `678a:0005` (panel tiles) and `644a:0b0c` (puffs) must be kept if the
  bail-out fate (results part) is to match the original run for run.
* Gauges redraw only on change per page parity; a port that redraws the full panel every frame
  gives identical pixels as long as the values are the same.

## 11. Hand-offs

* **video**: TTM tags above are played with `24fc:0610`; sprite sets `1d32:214e/2170/21b6`;
  `26d2:0001/0031` bitmap free/draw; `6f97:0000` bitmap load; `1d32:09bb` span-list draw.
* **sim_world**: inputs to the cockpit/gauges — `DS:3EF5`, `3EF7`, `3EF8`, `3EF9`, `3EFB`,
  `DS:3FE2..3FEA`, `DS:3FEE` bits, `DS:57DD..57E8` advisory flags, `DS:523B` LSO signal;
  `1660:01bc/07bb/0bae/0c12/0c47` belong to the order execution (already rowed by sim_world).
* **render3d**: `644a:089f` gives the cockpit window height/eye row per view from `DAT+28h/+30h`.

## 12. Open questions

* Exact effect of the six patched driver vectors (which primitive each is) — the port only needs
  the mask semantics.
* `P.94h` airspeed and altitude units (the gauge scales: 7200 per airspeed-dial turn, 400/4000
  altitude units per needle turn); combined with the flight model's `v·70/1024` this would fix the
  real-time length of a nominal step (lead §4.1).
* Who passes a speaker to `msg_show` (none found; the speaker line position looks like a bug).
