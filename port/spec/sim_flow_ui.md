# sim_flow part: ui — sliders, end-of-mission prompts, realism, in-flight map, preferences, dialog library (AP.EXE)

Part of `sim_flow` (lead file `sim_flow.md`). Target `work/AP_flat.exe`, DGROUP `3EA4`. Written
2026-09-26 by the finisher from the disassembly (verified unless tagged *likely* / *guess*).
Symbols: `sim_flow_ui_symbols.csv`.

Segments: `5613` slider.c, `4b9f` (lead §4.3), `5da1` + `6210` + `5a01` stdalert.c (end-of-mission
and generic alerts), `522c` + `6e9b` + `6e9f` realism, `6cdc` fltmap.c, `6b4d` control.c
(preferences), dialog library `46de 472f 47a8 48a2 5119 5247 53a6 53ec 6396 6c5f 0de8`, `565f` IFF
screenshot, `48af` boxlist.c (`.BXL`), `6b3d`/`6de0` cockpit exit, `4bcd:01df`.

## Index

1. Sliders (`5613`) — the TIME SCALE slider and the **real-time scale of the simulation**
2. End-of-mission prompts (`5da1`), mission summary text (`6210`), alert builder (`5a01`)
3. Realism settings and the score multiplier (`522c`, `6e9b`, `6e9f`)
4. In-flight map (`6cdc` fltmap.c) and the map target
5. Preferences dialog (`6b4d` control.c)
6. Dialog library
7. Screenshot writer (`565f`), `.BXL` box lists (`48af`), cockpit exit (`6b3d`, `6de0`), `4bcd:01df`
8. Port notes · 9. Hand-offs · 10. Open questions

---

## 1. Sliders (`5613` slider.c)

Four slider records at `DS:073C + 20h·i` (i = 0 TIME SCALE, 1 WORLD, 2 AIRCRAFT, 3 the VCR tape
position):

| Off | Type | Meaning | i = 0 / 1 / 2 / 3 |
|---|---|---|---|
| +00 | u16 | dialog item id | 5 / 6 / 8 / 15h |
| +02 | s16 | label, STR group 0 id (−1 none) | 12h "TIME SCALE" / 13h "WORLD" / 14h "AIRCRAFT" / −1 |
| +04, +06, +08 | u16 | frames (in the slider bitmap set `DS:44F6`) of the left end, right end, knob | 1, 2, 0 / … / 3, 4, 6 |
| +0A | s8 | label y offset | −7 |
| +0B/+0C, +0D/+0E | s8 | left end (x, y), right end (x, y) | (0, 1), (−1, 14) |
| +0F, +10, +11 | s8 | knob y, knob x origin, right margin | 0, 3, 0 |
| +12 (`DS:074E`) | s16 | value at position 0 (`lo`) | 80 / 0 / 0 / set by the VCR |
| +14 (`DS:0750`) | s16 | value at the last position (`hi`) | 20 / 255 / 255 / frames |
| +16 (`DS:0752`) | s16 | last position (`max`) | 72 (48h) for all |
| +18 (`DS:0754`) | s16 | position | |
| +1A (`DS:0756`) | s16 | drawn position | |
| +1C (`DS:0758`) | far ptr | save-under buffer of the knob | |

| Address | Name | Behaviour |
|---|---|---|
| `5613:0068` | `sliders_load(name)` | `DS:44F6 = 7229:01aa(name)` (bitmap set `sliders`, fatal `slider.c` 63h); `slider_alloc(i)` for i = 0..3; **`lo(0) = 80`, `hi(0) = 20`** |
| `5613:0000` | `slider_alloc(i)` | far buffer of the knob bitmap size (`1d32:5a2a(w, h)`), fatal `slider.c` 5Bh |
| `5613:00bc` | `slider_map(v, a0, a1, b0, b1)` | if `|b1 − b0| < |a1 − a0|` (value range narrower than the position range): `d = |a1 − a0| − 1`, negated when `b1 < b0`; return `satdiv((v − a0)·(b1 − b0) + d, a1 − a0) + b0` (rounds away from `b0`); else `277a:41c4(v, a0, a1, b0, b1)` (linear map) |
| `5613:0161` | `slider_value(i)` | `slider_map(pos, 0, max, lo, hi)` |
| `5613:0196` | `slider_drawn_value(i)` | same with the drawn position (no callers) |
| `5613:01cb` / `01da` | `slider_lo(i)` / `slider_hi(i)` | |
| `5613:01e9` | `slider_set(i, v)` → changed | `pos = slider_map(v, lo, hi, 0, max)` |
| `5613:0247` | `slider_settled(i)` | `pos == drawn` |
| `5613:026a` | `slider_range(i, lo, hi)` | (VCR tape slider) |
| `5613:0155` | `slider_bitmaps()` | `DS:44F6->+0Eh` |
| `5613:0489` | `slider_draw(i)` | dialog callback: if the item is being (re)drawn (`DS:3BCB & 40h`): `slider_frame 028a` (label with `53ec:01e6`, both ends); then `slider_knob 034a` |
| `5613:034a` | `slider_knob(rec)` → dragged | while the item is pressed (`DS:3BCB & 10h`) the knob follows the mouse (`DS:3BBF − w/2`, keys 1Ch..), clamped between the ends; restores the old knob background, saves the new one, draws the knob; stores the position into the item value (`+0Eh`) and `+1A` |

**TIME SCALE** = slider 0: value 80 (position 0, left) … 20 (position 72, right); it is the
divisor `DS:7118` of the time base (lead §4.3: `dt = clamp(ticks·256 / value, 40h, 1C2h)`).
Values are `80 − 60·pos/72` rounded away from 80: pos 0 → 80, 36 → 50, 72 → 20.
Defaults: SIMPREFS.PRF (lead §3.2); the installed file holds 50 (= 32h, the fast-machine
benchmark choice); films store it in their header (+04, all four demos: 50).

### 1.1 How fast the simulation runs (settled from the mission clock)

The mission clock `4ca7` (lead §4.3) is **game seconds**: the VCR panel shows it as HH:MM:SS
(`5ea5:00ca hms`, vcr part §10). It advances by `200·dt/256` 1024ths per frame, so

* **1 game second = 1310.72 dt units = 5.12 nominal steps**; one nominal step (dt = 100h) =
  0.1953 s of game time. (Consistent with the physics: gravity `DS:3F24 = 66` with the
  `v·70/1024` position scale and ¼-ft position units (§4) gives ≈ 29.6 ft/s² for this step.)
* dt per real second = `236.69·256 / value` = `60593 / value` (while unclamped), so the world runs
  at **`46.23 / value` × real time**: value 46.2 ≈ real time, **50 → 0.92×**, 20 → 2.31×,
  80 → 0.58×.
* The clamp changes this at short frames: with the minimum frame of 8 PIT ticks (29.6 fps) dt =
  2048/value < 64 for every value > 32, so dt is clamped to 40h = 64 → **1.445× real time for any
  TIME SCALE ≥ 32** (values 20..31 give 2.31×..1.49×). At 12 ticks (19.7 fps) value 50 still
  clamps (61 → 64: 0.96×); from 16 ticks per frame (≤ 14.8 fps) the slider acts as intended.
  The demo films were recorded at 5–24 × 4 ticks per frame (2.5–12 fps), where value 50 gives
  0.92× real time (DEMOAG: 841 frames, clock 113 s).
* So the original, on hardware fast enough to hit the 8-tick frame cap, runs the world about 45 %
  faster than real time and ignores the slider above 32. **Port decision** (lead §9): keep the
  exact `ticks → dt` mapping (films and determinism need it); a "true speed" option would have to
  lengthen the frame to ≥ 16 ticks or change the clamp — both change the simulation.

---

## 2. End-of-mission prompts, summary text and alerts

### 2.1 `5da1` (end requests and the end prompt)

`DS:4E74` end request (0 none, 1 end now, 2 landed on the carrier, 3 landed at the base, 4 bailed
out / timed end); set once by `5da1:0000 end_request(u8 code)` (first request wins; callers: the
crash code `088a:0007`, death `10bf:00d2`, landing/bail-out in the command handler `5440:0aee`,
`655d:159d`); cleared by `5da1:02da end_reset()` at mission start. The flight loop's
`flight_keys` (lead §4.5) reacts to it.

| Address | Name | Behaviour |
|---|---|---|
| `5da1:00cb` | `plane_in_trouble(Plane *p)` → 0/1 | only with realism "damage" (`DS:42CF`): `p.AAh & 10h`, oil leak (`DS:0FE8/0FE9`), player down (`0FEC`), pilot wounded (`0FEB`), fuel leak (`0FEA`), `p.1Ah & 40h`, or engine condition < 50 (`model.90h > 1` ? `(p.A4h + p.A6h) >> 1` : the **player's** `A4h` — quirk: reads P, not p) |
| `5da1:0165` | `object_lost(o)` | aircraft: `1142:0000(o)`; ship: `o.1Bh & 2` (no callers) |
| `5da1:0196` | `in_contact(p)` | `p.1Fh & 1` (results part: enemy within 25000) |
| `5da1:01a8` | `low_and_diving(p)` | `p.0Ch < 4000 && (s16)p.10h < −1820` |
| `5da1:01cb` | `end_danger(p)` → text list / 0 | `DS:4E74 == 2` → 0; `plane_in_trouble` → `DS:0A42`; `in_contact` → `DS:0A48`; `low_and_diving` → `DS:0A4E`; realism fuel (`DS:42CE`) and `!can_reach_home(p)` (`69d0:0285`) → `DS:0A54`; else 0 |
| `5da1:0092` | `str_list(far char **out, u16 *ids)` | `out[i] = str(0, ids[i])` until −1, then 0 |
| `5da1:0012` | `end_alert(texts, buttons, codes)` → 5 / 6 / 7 / 8 | `n = alert_build 5a01:00e9(texts, buttons, codes)`; `53a6:02cf(16h, 38BF:…, n)`; `606e:000d`; loop `r = dlg_poll 606e:007a()`: 9 (Esc) → 6, 0Ah → 5, 0Ch → 7, 10h → 8 (each after `5cde:0000` full redraw); other results keep polling |
| `5da1:022e` | `end_prompt()` → code | below |

`end_prompt()` (verified): buttons default {B9h "CONTINUE FLYING", BBh "END MISSION ANYWAY"}
with result codes `DS:0A74` = {9, 10h}.
* `DS:4E74` 2 or 3 (landed): texts `DS:0A6C` {BDh "YOU HAVE LANDED."}, buttons {BAh "END
  MISSION"}, codes `DS:0A78` {0Ah}.
* training (`DS:477C == 5`): texts `DS:0A68` {BCh "WOULD YOU LIKE TO:"}, buttons {B9h, BAh}
  (codes {9, 10h} — note: END MISSION returns 10h here, i.e. "abandoned").
* else `t = end_danger(P)`: a danger → texts `t` (B2h "YOUR PLANE IS SERIOUSLY DAMAGED." / B3h
  "ENEMY THREATS ARE NEARBY." / B4h "YOU'RE DANGEROUSLY LOW." / B5h+B6h "YOU HAVE INSUFFICIENT FUEL
  TO MAKE IT BACK."; each followed by B0h "ENDING THE MISSION NOW IS DANGEROUS!"), buttons {B9h,
  BBh}; no danger and not `DS:5CC9` (mission over) and not landed: `DS:0A5C` {B7h "YOUR MISSION IS
  NOT COMPLETE.", B0h}, buttons {B9h, BBh}; mission over: `DS:0A62` {B8h "YOUR MISSION IS
  COMPLETE.", B1h "DO YOU WISH TO:"}, buttons {B9h, BAh}, codes `DS:0A70` {9, 0Ah}.
Then `end_alert(str_list(texts), str_list(buttons), codes)`. `flight_keys` maps the result with
`key_to_code` (lead §4.5): 5 → 3 (end, normal), 8 → 2 (end, abandoned), others → 4 (continue).
So "END MISSION ANYWAY" ends the flight as *abandoned* (flight loop returns 0).

`5da1:02e4` (`end_init`, from `sim_init`) is empty.

### 2.2 Mission summary text (`6210`)

`6210:05e0 results_text(u16 *ids, char *buf)` (from the VCR session driver after the flight):
`fate = fate_record()` (results part §7.2); `summary_text 6210:0000(buf, &fate)`; `n =
word_wrap(buf, 200)`; `ids[i] = i + 1` and `DS:50CA[i + 1]` (far ptr) = line i; then `ids[n] =
5Dh` ("DO YOU WISH TO:" in group 9) and `ids[n+1] = 0`.

`6210:0000 summary_text(char *buf, u16 fate[5])` (STR group 8, `%s` filled with `sprintf`):

| Fate low nibble | Text |
|---|---|
| 1 shot down | "You've been shot down!"; with 10h: newline + "%s has added you to his long list of victories." (the ace's name) |
| 2 crashed | "Your %s has crashed." (aircraft name) + 20h "The crash is fatal." / 40h "You've been captured by the enemy." / 50h "You survive, but your injuries require hospitalization." / 60h "Fortunately, you emerge unharmed." |
| 3 bailed out | "Throwing open your canopy, you bail out of your plane!" + 20h "…in your wounded condition you fail to survive the descent." / 30h "…struck by the tail section…" / 40h "…land behind enemy lines and have been captured." / 50h "You land in friendly territory." + "…your injuries require hospitalization." / 60h "You land in friendly territory." + "With only a few bumps and bruises, you return to duty immediately." |
| 4 returned | 40h "Your %s has touched down in enemy territory. You've been captured." / 50h "…friendly territory. Your injuries are severe…" / 60h "Your %s has touched down in friendly territory." / 70h "You've safely returned to your airfield." / 80h "You've safely returned to your carrier." |

`6210:0675 alert_ids(far u16 *texts, far u16 *buttons, …)`: builds far-pointer lists (ids 1..20 →
`DS:50CA[id]`, others → `str(9, id)`) and runs the alert like `end_alert`. `6210:07a8
alert_modal(…)`: `modal_enter`, `606e:000d`, `alert_ids`, screen refresh, `368f:017f(2)`,
`modal_leave` (vcr part §11.1); used by all VCR/tape questions.

### 2.3 Alert builder `5a01` (stdalert.c)

`5a01:00e9 alert_build(far char **texts, far char **buttons, u16 *codes)` → item count: fills the
far item table `38BF` (22-byte dialog items): width = max(button text widths) + 12 (at least 5
average character widths) and max(text widths) + 12 (at least 7); height = lines·fh + 16 + buttons
·18 + 9; centred on the 320×200 screen; up to 6 buttons, each with its result code. Text widths
via `0de8:0020 text_width(far s)` (`2494:0009` copy + `1d32:5570`); `0de8:0000` draws a far string.
`5a01:0395 quit_box(…)` → handle: the modal "Exit to DOS? (Y/N)" box (STR0 5Eh) — saves the
background (`1d32:5a26`, far buffer), draws with `5a01:005d`; `5a01:05d5 quit_box_close(h)`
restores and frees. `5a01:0000/0027/0037`: button callback helpers (`47a8:0cb0` press handling).
Used by the lead's `quit_prompt 60a9:0a04` and the preferences calibration.

---

## 3. Realism and the score multiplier (`522c`, `6e9b`, `6e9f`)

`DS:42C8` = the 16 realism bytes (`?REAL.PRF`, lead §3.2). Item order (STR0 50h..5Bh):

| i | DS | Item | Values | Weight `DS:0636[i]` | Used by |
|---|---|---|---|---|---|
| 0 | 42C8 | sun blind spot | 0/1 | 10 | render3d culling (`5440:03aa`) |
| 1 | 42C9 | realistic weather | 0/1 | 5 | wind (`56ac:009d`) |
| 2 | 42CA | gun jams allowed | 0/1 | 10 | guns |
| 3 | 42CB | engine burn out | 0/1 | 10 | engine |
| 4 | 42CC | blackouts allowed | 0/1 | 10 | `0fd4` |
| 5 | 42CD | limited ammunition | 0/1 | 30 | guns |
| 6 | 42CE | limited fuel | 0/1 | 10 | fuel burn, autopilot, end prompt |
| 7 | 42CF | aircraft may be damaged | 0/1 | 0 (selects the range) | damage, `5da1:00cb`, `P.AB` |
| 8 | 42D0 | midair collisions | 0/1 | 10 | `085b` |
| 9 | 42D1 | no in-flight info | 0/1 | 5 | suppresses cockpit messages |
| 10 | 42D2 | combat level | 0 novice / 1 intermediate / 2 expert | 25 × v/2 | AI |
| 11 | 42D3 | flight model | 0 easy / 1 standard / 2 hard | 25 × v/2 | FM |
| 12–15 | | unused | | 0 | |

Presets (`DS:120E`, the OVERALL DIFFICULTY buttons, 16 bytes each): EASY `00 00 00 00 00 01 00
01 00 00 00 00`, STANDARD `00 01 00 00 01 01 01 01 00 01 01 01`, HARD `01 01 01 01 01 01 01 01 00
01 02 02`.

| Address | Name | Behaviour |
|---|---|---|
| `522c:011c` | `realism_init()` (mission start) | grace timer `DS:4294 = 9858h` (39000 dt units ≈ 29.8 game s); zero `DS:42B8` (16 "not changeable" flags) and `DS:42A8` (16 "credited" flags); `DS:576B = (s8)DS:42CF`; mission kind 0 (single/quick, `DS:477B == 0`): `DS:42CE = 0` (fuel off), `DS:42BE = DS:42AE = 1` (item 6 fixed) |
| `6e9b:0000` | `realism_timer()` (sim step) | while `DS:4294 != 0`: `timer32_expired(&DS:4294)` → baseline `DS:4298 = DS:42C8` (16 bytes), `DS:42A8[0..15] = 1` |
| `522c:0162` | `realism_changed()` | after the grace time: `DS:4298[i] = min(DS:4298[i], DS:42C8[i])` (lowering a setting lowers the credit for the rest of the flight; raising it again gives nothing); `DS:576B = (s8)DS:42CF` |
| `522c:0038` | `realism_percent()` → % | grace time running: `pct(DS:42C8)`; else `pct(min(DS:4298, DS:42C8))` |
| `522c:006f` | `pct(u8 r[16])` | `(hi, lo) = r[7] ? (100, 20) : (20, 0)`; `s = Σ over r[i] != 0 of (i == 10 or 11 ? (w[i]·r[i]) >> 1 : w[i])`; if `DS:477B == 0` add `w[6]` (fuel counts as on in single missions); return `lo + (hi − lo)·s / Σw` (Σw = 150, `522c:0100`; 16-bit `imul`/`idiv`) |
| `522c:0000` | `min16(out, a, b)` | byte-wise signed minimum of 16 bytes |
| `522c:0186` | `realism_uncredited(i)` | grace time running → 0; else `DS:4298[i] == 0` |

So the flight's score (results part §7.3) is multiplied by 20..100 % with damage on (0..20 % with
damage off); the first ≈ 30 game seconds of a flight are a free-change window.

Realism dialog (`simreal.BOX`, 36 items at far `39A4`, loaded by `6e9f:0000`; opened in flight with
Alt+R through `606e:0137`, vcr part §10): `6e9f:0232 realism_bind(u8 *r)` (`DS:5488 = r`, from
`mission_start` with `DS:42C8`); `6e9f:02d5 realism_open()` — keeps a copy in `DS:5478` and marks
items whose credit is lost (`realism_uncredited`) with item flag 2000h; toggles `6e9f:0141` flip
`r[i]` unless `DS:42B8[i]` (not changeable) — item 0 (sun) requests a cockpit redraw (dialog
result 0Eh); `6e9f:01c6` / `01f2` cycle flight model / combat level `(v + 1) % 3`; `6e9f:00ba`
applies a preset to the changeable items; `6e9f:023d` RESTORE (back to the copy); `6e9f:021e`
ACCEPT (result 9); `6e9f:02ab` title with `realism_percent()` (`368f:03a1` number → text,
`5247:0000`); `6e9f:0024`/`0065` refresh the labels (frames 49h + r[11], 4Ch + r[10]); the rest
(`026f`, `033c`, `0394/03c0/03ec`, `0418`, `078a`) are draw callbacks (frame `472f:0782`, panel,
percentage bar). The copy is compared by `606e:0137` to decide whether a film data block is
written.

---

## 4. In-flight map (`6cdc` fltmap.c)

Opened with M (lead §4.5), not in dogfight missions for the target function. The map target is
the autopilot destination (results part §8) and is recorded in films (data blocks 2/3).

Target: `DS:521C` = {s32 x, s32 y, s32 altitude}, `DS:5228` = set.
* `6cdc:0db1 map_target()` → `&DS:521C` or 0; when set, `DS:5224 = max(P.0Ch, 2500)` (the target
  is always at the player's current altitude, at least 2500).
* `6cdc:0de1 map_set_target(p)`: copy 12 bytes and set, or clear when `p == 0`.
* `6cdc:0da7 map_reset()`: clear (mission start).

Coordinates (verified): world units are ¼ ft (`6cdc:0761 feet(z) = z / 4`), the map unit is 21128
units (≈ 1 mile; `6cdc:072f miles(a, b) = ldist2 / 21128`, unsigned). World → screen
(`6cdc:006a`): `mx = (x / 21128)·147 / 1200 + 99`, `my = −((y / 21128)·147 / 1200) + 89` (signed
32-bit divisions); screen → world (`6cdc:00db`): `x = ((sx − 99)·1200 / 147)·21128`, `y = (−(sy −
89)·1200 / 147)·21128`. Clicks are accepted for 26 < sx < 173, 16 < sy < 163.
`6cdc:06cb bearing_deg(a, b)` = `((10000h − (atan2_32(b.x − a.x, b.y − a.y) − 4000h))·360 >> 16) %
360`. `6cdc:014c dir8(u8 h)` = `(u8)(h + 16) >> 5`.

`6cdc:0e0b fltmap()`: block the quit prompt (`60a9:0aa7`), dissolve, load `fltmap.PAL` and set it,
background `6cdc:0ce7` (`fltmap.SCR` via `715b:0000`, the pilot figure `PILOT` and the wind/weather
bitmap `W<n>`), icon sprites `fltmap.BMP` → `DS:521A`; `n = map_icons 6cdc:0161(buf)`, draw them
(`6cdc:0408`: sprite frame by icon kind and `dir8(heading)` at the projected position); activate
the dialog (far `399A`, 6 items, `53a6:02cf`); loop on `dlg_poll 606e:007a`: result 9 → leave;
C8h → redraw and show the route; last event `DS:3BBB`: 0Eh or 53h (Backspace, Delete) → clear
the target; 20h (click) → unless a dogfight mission (`496a:0ded`): inside the map area → target =
screen → world at the click (altitude 0; replaced on read), else clear; then redraw. Leaving: free
the sprites, restore `DS:408A` palette, `DS:4090 = 2`, full redraw, cockpit rebuild
(`644a:088f`), palette effects (`17ce:0008/0013`, `1792:00c0(1)`), unblock the quit prompt,
`DS:0B80 = 0`.
`6cdc:0161 map_icons(Icon *out)` → n (16-byte icons {u8 kind, u8 heading, 3 × s32 position}):
dogfight/scramble types (`DS:477C` 0, 1, 4): only the player (kind 3..6 by side and carrier) and
his base; otherwise every other flight (aircraft flights with role 2 or 3 as friendly/enemy kinds
1/2, ship groups, places) — *likely* (decompile read).
`6cdc:0c11 map_route()` → 1 if interrupted: the player's route points (`6cdc:04fd`: waypoints
`17fe:00a1/00c9`, `69d0:00c4`, and the map target), drawn segment by segment (`6cdc:07da`, animated,
waits on `DS:31E5 = 58Ch`) with an info box per point (`6cdc:098e`: "Bearing: %03d°",
"Distance: %d mile%s", "Altitude: …%03d feet", laid out with `6c5f`); `6cdc:077a input_abort()` → 2
Esc, 1 any key / button, 0. `6cdc:0000`, `003e`: dialog callbacks.

---

## 5. Preferences dialog (`6b4d` control.c)

F10 in flight (lead §4.5) → `6b4d:0f95 prefs_dialog()` → changed flag (the flight loop records a
film data block with the TIME SCALE value). Items: `prefsim.BOX` (21 items at far `3974`, loaded
by `6b4d:0308 prefs_init()`, which also sets the toggle labels and the device labels).
* Sliders TIME SCALE / WORLD / AIRCRAFT (`6b4d:0295/02a4/02b3` → `slider_draw`); on accept
  `4b9f:0000/0018/00d0` apply them (lead §4.3).
* Toggles (`6b4d:03b1 toggle(a, b, base)`: flip item a's value `+25h`, item b's frame `+23h = base
  + value`, dirty): `6b4d:0408` JOYSTICK (only with a joystick, `DS:1B4A`; `5f2c:0058`), `0443`
  MOUSE (only with a mouse; `5f2c:007f`), `0480` SOUNDS (`5a75:09f0` on / `09d5` off), `04c0`
  GROUND DETAIL OFF/ON IN COMBAT (`3974:0209`, lead §4.3). The same toggles run for Alt+J/D/S
  outside the dialog (lead §5.2).
* Device selection (`6b4d:0c74`, `089b`, `05c1`): flight control 0 keyboard, 1 joystick 1, 2 yoke,
  3 Thrustmaster FCS, 4 mouse (`3974:007D`); rudder 0 keyboard, 1 joystick 2, 2 rudder pedals
  (`3974:00A9`); throttle 0 keyboard, 1 joystick 2, 2 slider, 3 Thrustmaster WCS (`3974:00D5`) —
  CONTROL.PRF +0A/+0B/+0C. `6b4d:0751 controls_apply()`: stick axis on for flight 1–3
  (`5f2c:0137(0, …)`), rudder axis for rudder 1–2, throttle axis for throttle 1–2, hat views for
  FCS (`5f2c:0153`), absolute throttle for the slider (`5f2c:0166`), mouse flight for 4
  (`5f2c:0148`). Incompatible combinations get an alert (STR0 26h–2Bh).
* Calibration (`6b4d:0a41`, `0000`, `00a0`, `0158`, `0546`): "Center the joystick and press any
  button" / corners / slider ends / Thrustmaster hat, reading `1d32:04e5/063f` and storing through
  `60a9:08e3` (lead §5.1).
* Callbacks `6b4d:0174/01e2/0257/02c2/02d6/04e2/04fb/0514/052d` draw labels and buttons.

---

## 6. Dialog library

A variant of the PS toolkit (`shell_ui_toolkit.md` §1–§3): items are 22-byte records in far tables
(`+00..+06` x, y, w, h from the `.BOX` file, `+0Ch` dirty byte (43h = redraw), `+0Dh` flags (bit 1
hot, bit 6 disabled …), `+0Eh` value, `+10h` user word, `+12h` 4 bytes from the companion `.bl`
file, `+21h`/`+23h`/`+25h` used by some tables); callbacks are reached through the far stub tables
`3C6D`, `3D1D`, `3E39`, `3E49`, `3E62`. Current item `DS:3BCF` (far), index `DS:3BCD`, state flags
`DS:3BCB`, mouse `DS:3BBF/3BBD`, result `DS:3BC1`, key `DS:3BBB`; item rectangle `DS:3BC9/3BC7/
3BC5/3BC3` (x, y, w, h).

| Address | PS equivalent | Behaviour |
|---|---|---|
| `6396:0000` | — | `box_load(far Item *items, char *name, int n)`: n × {x, y, w, h} from `name`, then n × 4 bytes into `+12h` from the same name with extension `bl` (`DS:0C74`); fatal `alrtlib2.c` 2Ch |
| `53a6:02cf` | `2b4f` activate | `dlg_activate(far items, n)`: `DS:00D6 = items`, `DS:00DC = n`, clears the per-item pressed bytes `DS:3B90`, builds the hot list `DS:42E0[DS:42DE]` (flag +0Dh bit 1), focus `DS:42DC = −1`, focus init |
| `53a6:0016` | — | allocate the pointer save buffer (`1d32:5a2a/5aa5`) |
| `53a6:0255`, `0360`, `0393`, `044d`, `0078`, `00c1`, `0108`, `0203`, `0000/000b/038b` | `2b4f` | keyboard focus movement, click at (x, y) (`606e:0018`), select item i, full redraw (`5b93:084e`), key filter, item count |
| `46de:00ee` | `hs_dispatch 2b4f:0426` | hit test and callback dispatch for the mouse at (x, y, button), state bits in `DS:3BCB` (1 inside, 2 outside, 4/8 pressed, 10h released inside, 20h left, 40h redraw) |
| `46de:02f3`, `0000`, `0057`, `00cd`, `04a4/04bc/04de` | `2b4f` | redraw dirty items (page copy), item iterator, point-in-item, show/hide the mouse over the VCR panel |
| `47a8:0000/0031` | — | allocate / free the 10×10 save buffer |
| `47a8:0043`, `005d`, `0077`, `0094`, `00b1` | `2c11:0042`, `005c`, `006c`, `0089`, `00a6` | rect grow/shrink, rect save/restore, rect copy |
| `47a8:00ce` | `2c11:042c` | bevel box ("forms") |
| `47a8:026c`, `0335`, `0477` | `2c11:05cf`, `069a`, `07de` | groove, inset box |
| `47a8:0480` | `2c11:07e7` | `text_center_x` |
| `47a8:04c7`, `0549`, `0565`, `0593`, `05bd` | `2c11` | tile fill, fills (`0593` = `2c11:091c` C1h fill) |
| `47a8:05eb`, `06ca` | `2c11:0b65`, `0c46` | frame lines |
| `47a8:0712/076e/0912/0971/0bf2/0c51/0dc7`, `07ca` | `2c11:142b` | buttons in the various styles (engraved label with `53ec:01e6`), pressed/released art |
| `47a8:09d0` | `2c11:1633` | framed panel |
| `47a8:0ae1`, `0ba3` | — | dialog window frame with title (`53ec:0174`), item draw dispatcher |
| `47a8:0cb0` | — | button press handling (click sound `5a75:0eea(10h)`) |
| `47a8:0d92` | — | toggle button press → 1 when released inside |
| `47a8:0232` | — | draw frame `+0Eh` of a bitmap set at the item |
| `53ec:01e6`, `013f`, `0174`, `0000` | `2c11:03d4`, `027c`, `0362` | engraved/shadowed text (the standard label style), edge pass |
| `48a2:0000` | `2c11:00c3` | embossed text |
| `5247:0000`, `0070` | `2c11:0980`-like | dialog title text (the realism % title; VCR panel title) |
| `5119:0000`, `0037`, `01ad` | — | a dialog box with frame, inset and embossed text (callbacks) |
| `472f:0782` (+`0000`, `00cb`, `0165`, `01c4`, `0302`) | `2c11:136a`, `0c8e`, `0d96` | the large dialog frame used by the preferences and realism panels |
| `6396:00ff`, `0109`, `0127`, `0140`, `0159`, `016c`, `0261`, `02cb`, `0335`, `036a`, `03a1`, `03d7`, `045e`, `04fa`, `0521`, `0548` | `2c11:1a40`, `1a76`, `0583:0095` | small drawing helpers and button variants of `alrtlib2.c` (C1h fill, lines, `DS:26C3 = 0`, arrow buttons for the list box, radio buttons) |
| `6c5f:0000..0443` | `2dd0` drawtext.c | text layout into a box (word wrap, alignment, `%d` substitution via `0000:4bfb`); used by the map info boxes |
| `0de8:0000`, `0020` | — | far text draw / width |

The event pump is `606e:007a dlg_poll` (vcr part §10): returns the hit item's code, 9 for Esc.

Names of the small helpers in `472f`, `6396`, `6c5f`, `5119` and of the item draw callbacks
(`6b4d:0174..052d`, `6e9f:0394..078a`, `5a01:0000..0037`) in the symbols file are *guess* level
(role from call sites and the PS equivalents); the port redraws these panels with its own dialog
code and needs only the behaviour stated above.

---

## 7. Other

### 7.1 Screenshot writer (`565f`, Alt+T / Ctrl+Alt+F10)

`565f:008a iff_write(char *name)`: file = work dir `DS:4032` + `screenshot_name()` (cockpit part §3);
IFF `FORM` … `ILBM`: `BMHD` (320 × 200, 8 planes, compression 1), `CMAP` (`565f:022a`: the DAC read
with `0000:185e`, 256 × RGB scaled from 6 to 8 bits by `<< 2`), `BODY` (`565f:0377`: each row read
from the screen (`1d32:5a26`), split into 8 bit planes, each plane row compressed with ByteRun1
(`565f:030d`)); `565f:0000` writes big-endian values / chunk lengths (recursive helper).
`/* PORT: */` may write PNG instead.

### 7.2 `.BXL` box lists (`48af` boxlist.c)

`48af:0000 bxl_table(n)` (`DS:1160` = table of n pointers, from `56ac:0236`); `48af:0017
bxl_load_slot(slot, name)`: `u8 count`, `u8 flags`, 4 bytes, then count × 12-byte boxes → pointer in
the table; `48af:00a8 bxl_load(name)` → record (the same, allocated with `24b2:0074`; fatal
`boxlist.c`); `48af:015a bxl_get(slot, &out)`. Used by `acedata` (`45cc`), hit boxes (`490a`),
object creation (`465c`) — the box semantics belong to sim_world.

### 7.3 Cockpit exit (`6b3d`, `6de0`)

`6b3d:0000 cockpit_leave()` (from `56ac:18e5`): leave the current cockpit view as in
`cockpit_frame_bg` (edges released; TTM tags 7 / 15h (+ ACES palette back when a gunner view was
used) / 36h / 2Ah), `6de0:0000` (empty). `6b3d:00ac cockpit_unload()` (from `scenario_unload
56ac:07b4`): free the three EMS view caches, `6de0:0005 gauges_free()` (common bitmap `DS:3F4A`,
gauge array `DS:3F4E`), `edge_arena_free()`, TTM tag 54h, `24fc:0989` (unload the TTM).
(The §0 map entry "mission music + ACES.PAL" for `6b3d` is corrected by this.)

### 7.4 `4bcd:01df file_exists(char *path)`

`fopen(path, "rb")` succeeds → close, 1; else 0 (lead §8, vcr part §11.4).

---

## 8. Port notes

* Frame pacing and the TIME SCALE: §1.1 (numbers for the lead's decision).
* The dialog library can be implemented once for PS and AP (same look; AP adds the VCR panel and
  the slider/realism/preferences panels). Item tables are loaded from `.BOX`/`.bl` files in SIM2.
* Screenshots: PNG instead of IFF is acceptable (`/* PORT: */`).

## 9. Hand-offs

* **sim_world**: realism bytes and their users (§3 table); `DS:4E74` end requests from `088a:0007`,
  `10bf:00d2`, `655d:159d`; `.BXL` box semantics (§7.2).
* **video**: `715b:0000` SCR, `7229:01aa` slider bitmaps, `6f97:0000` BMP, sprite draws.
* **shell_ui**: the AP dialog library mirrors `2b4f`/`2c11`/`2dd0` (§6 equivalence column).

## 10. Open questions

* Exact list of map icon kinds and which flights/places are shown in non-dogfight missions
  (`6cdc:0161` read from the decompile only).
* The meaning of dialog event code 20h in `fltmap` (treated as "mouse click").
