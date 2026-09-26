# shell_ui part — main menu, single-mission menu, options, records, briefing

Target `Game/PS.EXE` (DGROUP `4D08`). Segments `04df` (main menu), `0b16` (fly single mission
menu), `09a9` best.c (best missions / top aces records screens), `0a41` campset.c, `0a71`
once.c, `0a8d` (realism), `0b48` (preferences / controls), `0c1d` (mission briefing). Toolkit
names: `shell_ui_toolkit.md`. Confidence **V**/**L**/**G** as in `shell_ui.md`.

Common screen skeleton (used by every screen below, V):

```
screen_show(id, scd_arg, 1)          // background + palette (deferred), loads <scd>.SCD strings
hs_set_table(table, n); hs_focus(sel); hs_draw_all()
r = menu_run(frame)                  // frame = [extra work;] hs_dispatch(601A,6018,2033,0); hs_present(); [Esc handling]
ui_busy()                            // busy cursor, present
dispatch on the variable the button callbacks set
```

Button callbacks are all of the form `if (btn_cb()) { var = 5FDE (item index); menu_set_result(1); }`.

## 1. Main menu (`04df`, screen 11 `MAINMENU`, table `4987:0000`) — V

| # | Rect | Callback | Mask/fl | Label (`MAINMENU.SCD`) |
|---|---|---|---|---|
| 0 | 164,7,143,144 | `mm_draw_window` `04df:0117` | 40 / 80 | 0 "MAIN MENU" |
| 1 | 10,22,123,18 | `mm_btn_cb` `04df:004e` | 74 / 82 | 1 "FLY SINGLE MISSION" |
| 2 | 10,42,123,18 | `mm_btn_cb` | 74 / 82 | 2 "CAREER MENU" |
| 3 | 10,62,123,18 | `mm_btn_cb` | 74 / 82 | 3 "VIEW VEHICLES" |
| 4 | 10,82,123,18 | `mm_other_cb` `04df:007c` | 74 / 82 | 4 "OTHER OPTIONS" |
| 5 | 10,102,123,18 | `mm_btn_cb` | 74 / 82 | 5 "MISSION RECORDER" |
| 6 | 10,122,123,18 | `mm_btn_cb` | 74 / 82 | 6 "EXIT TO DOS" (`QUIT` in the loose `Game/MAINMENU.SCD`, which is the file actually read: `shell_ui.md` §8) |

Buttons are relative to item 0 (so on screen at x = 174, y = 29 + 20k). Links: default ring.

| Address | Name | Behaviour |
|---|---|---|
| `04df:0002` | `mm_credits()` | `21f4:0245(res_name("intace6", −1, "ttm"), −1, 0, 0, 1CDh, far 21f4:0018)` — the PS copy of the INTRO `intro_play` (same argument list: whole script, skip callback `21f4:0018`, end frame 1CCh; module `21f4`, not owned here) plays the credits script `INTACE6.TTM`; then `screen_open(11, 0, 0, 0, 1)` (re-open the main menu screen without drawing, deferred palette) |
| `04df:004e` | `mm_btn_cb` | `if btn_cb(): DS:4224 = 5FDE; menu_set_result(1)` |
| `04df:006c` | `mm_other_pick(k)` | `DS:4225 = k; cursor_hide()` (callback of the CHOOSE list) |
| `04df:007c` | `mm_other_cb` | if `btn_cb()`: `strtab_load(res_name("sftbtns", 0, "dat"))` (`SFTBTNS0.DAT`); current item `+10` (count) = 3; `DS:4225 = FFh`; `choose_run(mm_other_pick, 0, 97)` → entries 97–99 of the table = "PREFERENCES", "WATCH DEMO", "CREDITS" (+ CANCEL); `cursor_show()`; `hs_restart()`; `DS:4224 = 4`; `menu_set_result(1)`; `strtab_free()` |
| `04df:00e8` | `mm_btn7_cb` | item label (`+0E`) = `str_get(7)` ("MISSION RECORDER"); if `btn_cb()`: `DS:4224 = 5`, result 1. Not referenced by the table (L: dead) |
| `04df:0117` | `mm_draw_window` | `draw_titled_panel()`; 18 rivets at (x+3, y+18) and at (x+w−6, y+18) |
| `04df:0159` | `mm_frame` | `hs_dispatch(601A, 6018, 2033, 0); hs_present()`; if result == 2 (Esc) → `menu_set_result(0)` (Esc does nothing here) |
| `04df:018d` | `main_menu()` | below |
| `04df:02be` | `mm_init()` | `hs_default_links(4987:0000, 7)` |

```
main_menu():
  DS:4224 = 1
  loop:
    screen_show(11, 87h, 1); hs_set_table(4987:0000, 7); hs_focus(DS:4224); hs_draw_all()
    menu_run(mm_frame); ui_busy(); cursor_show()
    switch DS:4224:
      1 FLY SINGLE MISSION: flymenu_run() (0b16:01a7)
      2 CAREER MENU:       career_menu() (0607:011d, shell_ui_debrief.md)
      3 VIEW VEHICLES:     c = 05fa:007f() (VWHICH chooser)
                           c == 0: v = 1612:0388(2); if v != FFh: view_vehicle(-1, v, 0) (0ddd:0cde)
                           c == 1: v = 1612:0388(3); if v != FFh: view_ship(v) (0ddd:0d2f)
      4 OTHER OPTIONS:     DS:4225: 0 → prefs_screen() (0b48:0cf0); 1 → DS:626B = 4; shell_fly(0) (WATCH DEMO);
                           2 → mm_credits(); snd_play(3EAh) (title music again)
      5 MISSION RECORDER:  DS:626B = 3; shell_fly(0)          // AP runs the VCR (film) screen
      6 EXIT TO DOS:       return   → main() calls shell_exit(0)
```

(`DS:626B` = mission kind of the header, shell_data: 0 single/generated, 1 career, 2 historic,
3 mission recorder, 4 demo.) There is no confirmation for EXIT TO
DOS from the main menu (only for the Alt-X/Q hotkeys).

## 2. Fly single mission menu (`0b16`, screen 49 `FLYMISS`, table `4ac1:0000`, 15 items) — V

| # | Rect | Label (`FLYMISS.SCD`) | Links (up,down,left,right) |
|---|---|---|---|
| 0 | 2,9,315,171 (window, `0b16:000e`) | 0 "FLY SINGLE MISSION" | |
| 1–6 | 10, 22+20k, 144,18 | 1 "FLY A HISTORIC MISSION", 2 "DOGFIGHT A FAMOUS ACE", 3 "DOGFIGHT A SQUADRON", 4 "COMBAT AIR PATROL", 5 "FIGHTER SWEEP", 6 "SCRAMBLE" | from the file table (e.g. item 1 = 0E,07,0E,02) |
| 7–11 | 159, 22+20k, 144,18 | 7 "TRAINING MISSION", 8 "ESCORT BOMBERS", 9 "INTERCEPT BOMBERS", 10 "ANTI-SHIPPING STRIKE", 11 "GROUND ATTACK" | |
| 12 | 159,(122),144,18 | 12 "CUSTOM MISSIONS" (callback patched in) | |
| 13 | 159,(122/148),144,18 | 13 "BEST MISSIONS" | |
| 14 | (84/10),148,144,18 | 14 "RETURN TO MAIN" | |

All buttons use `fm_btn_cb` (`0b16:0050`): `DS:4368 = 5FDE`, result 1. Window `0b16:000e`:
`draw_titled_panel()`, 21 rivets at (x+3, y+18) and (x+w−6, y+18).

| Address | Name | Behaviour |
|---|---|---|
| `0b16:000e` | `fm_draw_window` | above |
| `0b16:0050` | `fm_btn_cb` | above |
| `0b16:006e` | `fm_set_links(custom)` | for the 5 items listed at `DS:082C` = {6, 7, 11, 13, 14}: copies 4 link bytes from `DS:0831 + 4k` (custom present) or `DS:0845 + 4k` into the item |
| `0b16:00ca` | `fm_layout()` | `DS:081E = custmiss_exist()` (`147e:0935`: `findfirst(DS:0EF8 pattern)`, shell_ui_mission); none → item 12 mask/flags = 0 (hidden, not focusable), item 13 y = 122, item 14 x = 84, `fm_set_links(0)`; else item 12 y = 122, callback = `fm_btn_cb`, item 13 y = 148, item 14 x = 10, `fm_set_links(1)` |
| `0b16:013a` | `fm_frame` | `24b7:000c()` (steps the shell random generator every frame: shell_data); dispatch + present; on a result: 2 (Esc) → `DS:4368 = 14`; else if `DS:4368 == 13` (BEST MISSIONS) and `DS:433F == 0` (no best-mission records): `req_ok(0, 0, 9, 8)` (REQUEST string 9, button 8) and `menu_set_result(0)` (stay) |
| `0b16:01a7` | `flymenu_run()` | below |

```
flymenu_run():
  DS:4F22 = 1; fm_layout(); DS:4368 = 1
  do:
    screen_show(49, 396h, 1); hs_set_table(4ac1:0000, 15); hs_focus(DS:4368); hs_draw_all()
    menu_run(fm_frame); ui_busy()
    k = DS:4368
    if k == 13: best_missions_run() (09a9:05ac)                // then back to this menu
    else if k == 12: custom_missions() (147e:07e5)
    else if 1 <= k <= 11:
      t = DS:0820[k]                                            // FF,00,01,…,09 for k = 1..11
      if t == FFh: historic_run() (0583:03c2)
      else:
        world reset: 2ab3:013b, 2a85:0006, 2550:0679, 2624:0902, 2777:0000   (shell_data)
        if t == 0 (dogfight a famous ace): ace = 0c8a:05db()  (ace chooser, shell_ui_career)
             if ace != FFh && flymiss2_setup(0, ace) (100e:12c9): 2624:09c4; DS:4B89 = ace; shell_fly(0)
        else: v = 1612:0388(0) (side/aircraft chooser, shell_ui_mission)
             if v != FFh && flymiss2_setup(t, v): 2624:09c4; shell_fly(0)
        (set-up cancelled after a choice) 3164:0005 (mission data free); (chooser cancelled) nothing
        world save: 2777:04df, 2624:09c4, 2550:073f, 2a85:0216, 2ab3:057f
  while k == 13
```

So only BEST MISSIONS loops back here; every other choice (including a cancelled set-up)
returns to the main menu.

## 3. Realism panel (`0a8d`, screen 51 `REALISM`, table `4a95:0000`, 32 items) — V

Settings: 16 bytes at `DS:4357` (the in-memory `MREAL.PRF`/`CREAL.PRF`; indices 0–9 on/off flags
in the order of `REALISM.SCD` 0–9: sun blind spot, realistic weather, gun jams, engine burnout,
blackouts, limited ammunition, limited fuel, aircraft may be damaged, midair collisions, no
in-flight info; 10 = combat level 0–2 (`DS:4361`), 11 = flight model 0–2 (`DS:4362`), 12–15 unused).
`DS:4346` = copy taken on entry (RESTORE). `DS:4356` = "career" flag (the caller sets it).

| # | Rect | Callback | Label | user |
|---|---|---|---|---|
| 0 | 5,30,309,149 | `draw_side_riveted_panel` | | |
| 1 | 9,26,292,117 | `real_draw_frame` `0a8d:040f` | | |
| 2–4 | 14/108/202, 5, 90,18 | `real_preset_cb` `01ca` | 12 NOVICE, 13 INTERMEDIATE, 14 EXPERT | 0,1,2 |
| 5–9 | 28, 31+16k, 126,14 | `real_toggle_cb` `01ee` | 0–4 | 0–4 |
| 10–14 | 156, 31+16k, 126,14 | `real_toggle_cb` | 5–9 | 5–9 |
| 15, 16 | 98, 111/126, 82,14 | `real_toggle_cb` | 10 COMBAT LEVEL, 11 FLIGHT MODEL | 10, 11 |
| 17–21, 22–26 | 13 / 284, 32+16k, 12,10 | `real_draw_check` `0339` | (check boxes of 5–14) | state |
| 27, 28 | 24, 112/127, 71,10 | `real_draw_value` `02d6` | combat level / flight model value | |
| 29 | 185,112,100,26 | `real_draw_percent` `0377` | "OVERALL DIFFICULTY" + % | |
| 30 | 53,151,90,18 | `real_restore_cb` `02b0` | 20 RESTORE | |
| 31 | 167,151,90,18 | `real_accept_cb` `0298` | 21 ACCEPT | |

Weights `DS:07C2[16]` = 10, 5, 10, 10, 10, 30, 10, 0, 10, 5, 25, 25, 0, 0, 0, 0 (sum 150).
Presets `DS:07D2 + 16 p` (p = 0 NOVICE, 1 INTERMEDIATE, 2 EXPERT):
`0 0 0 0 0 1 0 1 0 0 0 0 …`, `0 1 0 0 1 1 1 1 0 1 1 1 …`, `1 1 1 1 1 1 1 1 0 1 2 2 …` (midair
collisions stay off even in EXPERT).

| Address | Name | Behaviour |
|---|---|---|
| `0a8d:0005` | `real_weight_sum()` | Σ `(s8)DS:07C2[i]`, i < 16 (= 150) |
| `0a8d:0023` | `realism_percent(u8 *s)` → int | `lo, hi = s[7] ? (20, 100) : (0, 20)`; `sum = Σ over i<16 with s[i] != 0 of (i == 10 \|\| i == 11 ? w[i]·s[i]/2 : w[i])` (signed C division); if `DS:626B == 0` (mission kind 0 = single mission): `sum += w[6]` (limited fuel is always credited in single missions, where it cannot be switched); returns `lo + (hi − lo)·sum / 150` (int division) |
| `0a8d:00ba` | `realism_current()` | `realism_percent(DS:4357)` |
| `0a8d:00ca` | `real_show_model()` | item 28 label = `str_get(12 + DS:4362)` (NOVICE/INTERMEDIATE/EXPERT), mask 3 |
| `0a8d:00f1` | `real_show_combat()` | item 27 label = `str_get(15 + DS:4361)` (EASY/STANDARD/HARD), mask 3 |
| `0a8d:0118` | `real_sync_check(i)` | item `i+12`.user = `(DS:4357[item i.user] != 0)`, mask 3 |
| `0a8d:015e` | `real_refresh()` | `real_sync_check(5..14)`; item 29 mask = 3; `real_show_model()`; `real_sync_check(13)`; `real_show_combat()` |
| `0a8d:0192` | `real_apply_preset(u8 *dst, p)` | copies preset p; entry 6 forced 0 when `DS:626B == 0` (single mission) |
| `0a8d:01ca` | `real_preset_cb` | `btn_cb()` → `real_apply_preset(DS:4357, item.user)`; `real_refresh()` |
| `0a8d:01ee` | `real_toggle_cb` | `btn_small_cb(0)` →: user 10: `DS:4361 = (DS:4361 + 1) % 3`, `real_show_combat`; user 11: `DS:4362` likewise, `real_show_model`; user 6 when `DS:626B == 0`: `DS:435D = 0` (cannot be switched in single missions); else flag = `!flag`, item (this+12).user = flag, mask 3; always item 29 mask = 3 |
| `0a8d:0298` | `real_accept_cb` | `btn_cb()` → result 1 |
| `0a8d:02b0` | `real_restore_cb` | `btn_cb()` → `memcpy(DS:4357, DS:4346, 16)`; `real_refresh()` |
| `0a8d:02d6` | `real_draw_value` | `draw_inset_box2()`; label (if any) FONT3, colour CCh, transparent, centred at y+3; mask := 40h |
| `0a8d:0339` | `real_draw_check` | `draw_inset_box2()`; if `user`: `draw_bitmap(PARTS[8], x+2, y+2, 0)` (the tick); mask := 40h |
| `0a8d:0377` | `real_draw_percent` | `draw_popup_box()`; FONT3; `text_engrave(str_get(18), C1h, B1h, C0h, centred, y+3)`; label = `itoa(realism_current(), DS:411A, 10)` (`22ce:032d`); `real_draw_value` on the fixed rect (222, 154, 22, 10) |
| `0a8d:040f` | `real_draw_frame` | two B8h boxes: (x+2, y+2, w−3, h−33) and (x+15, y+h−30, w−28, 31) (coordinates after the +2/+2 offset, see code); then the tab-shaped outline: C2h top (x,y)-(x+w,y); B5h (x+1,y+1)-(x+w−1,y+1); C0h sides (x, y+1)-(x, y+h−31) and (x+w, …); C0h (x+11, y+h−30)-(x+11, y+h) and (x+w−11, …); BFh inner verticals at x+1, x+w−1 (to y+h−31) and x+12, x+w−12 (y+h−30..y+h); C4h (x+11, y+h)-(x+w−11, y+h), (x, y+h−29)-(x+10, …), (x+w, y+h−29)-(x+w−10, …); C1h (x+11, y+h−1)-(x+w−11, …), (x, y+h−30)-(x+11, …), (x+w, y+h−30)-(x+w−11, …); C0h (x+11, y+h−2)-(x+w−11, …), (x+2, y+h−31)-(x+12, …), (x+w−2, y+h−31)-(x+w−12, …) |
| `0a8d:0785` | `real_frame` | dispatch + present |
| `0a8d:07a6` | `real_draw_bg` | `screen_clear_panel()`; `draw_title_bar_for(DS:62C5, DS:6277, str_get(19) "REALISM PANEL")` (pilot service and current date: shell_data) |
| `0a8d:07cb` | `realism_run()` | below |

```
realism_run():
  if !DS:4356: load "mreal.prf" → DS:4357 (1193:0818) else memcpy(DS:4357, DS:47A9, 16)   // career pilot record
  memcpy(DS:4346, DS:4357, 16)
  screen_open(51, real_draw_bg, 156h, 1); real_refresh()
  hs_set_table(4a95:0000, 32); hs_focus(31 ACCEPT); hs_draw_all()
  menu_run(real_frame); ui_busy()                     // Esc keeps the changes too
  if !DS:4356: save "mreal.prf" (1193:0840)
  else: memcpy(DS:47A9, DS:4357, 16); 0f67:0001 (roster save); save "creal.prf"
```

## 4. Preferences / controls (`0b48`, screen 46 `CONTROL`, table `4ad6:0000`, 19 items) — V

Settings bytes `DS:43B6..43BC`: 0 joystick on, 1 mouse on, 2 sound effects on, 3 music on,
4 flight control device (0 keyboard, 1 joystick 1, 2 yoke, 3 Thrustmaster FCS, 4 mouse),
5 rudder device (0 keyboard, 1 joystick 2, 2 rudder pedals), 6 throttle device (0 keyboard,
1 joystick 2, 2 slider on joystick 1, 3 Thrustmaster WCS). Saved in `CONTROL.PRF` (shell_data).
Label arrays (xmalloc'ed copies of `CONTROL.SCD` strings, `0b48:099d`): `DS:43AC` JOYSTICK
OFF/ON (10,11), `43A8` MOUSE OFF/ON (12,13), `43A4` MUSIC OFF/ON (14,15), `43A0` SOUND OFF/ON
(16,17), `4396` flight (18–22), `438E` rudder (23–25), `437C` throttle (26–29), `4372` (30,31),
`4386` (30), `4394` (32), `436A` flight/rudder/throttle lower-case (7–9); `4378`/`437A` and
`438A`/`438C` are 2-entry aliases used when the flight device is the Thrustmaster FCS.
Per-setting label table `DS:085D` = {43AC, 43A8, 43A0, 43A4, 4396, 438E, 437C};
toggle functions `DS:087F` = {`230d:008b` joystick, `230d:0018` mouse, `315c:004f` effects,
`315c:000e` music}; choice counts `DS:086B` = {5, 3, 4}; `SFTBTNS0.DAT` rows `DS:0871` = {152,
158, 165}; after-choice checks `DS:088F` = {`0b48:0133`, `0201`, `0261`}; label item of each toggle
`DS:089B` = {7, 8, 9, 10}.

| # | Rect | Callback | Label / user |
|---|---|---|---|
| 0 | 57,6,213,182 | `pref_draw_window` `02c1` (`draw_titled_panel`, 22 rivets at x+4 and x+w−6 from y+20) | 0 PREFERENCES |
| 1 | 10,22,194,48 | `pref_draw_group` `0307` | 1 MENU CONTROLS |
| 2 | 10,72,194,63 | `pref_draw_group` | 2 FLIGHT CONTROLS |
| 3–6 | (15,32) (110,32) (20,138) (114,138), 19×17 | `pref_toggle_cb` `044e` | user 7–10 |
| 7–10 | (37,35,67) (132,35,67) (45,140,56) (139,140,55), h 12 | `pref_draw_label` `0510` | user 0–3: JOYSTICK / MOUSE / SOUND / MUSIC state |
| 11–13 | 23, 84/99/114, 56,13 | `pref_device_cb` `0472` | 4 FLIGHT, 5 RUDDER, 6 THROTTLE; user 0–2 |
| 14–16 | 85, 84/99/114, 105,12 | `pref_draw_label` | user 4–6: device names |
| 17 | 68,52,79,13 | `pref_calibrate_cb` `0902` | 3 CALIBRATE |
| 18 | 62,159,90,17 | `pref_accept_cb` `0920` | 33 ACCEPT |

| Address | Name | Behaviour |
|---|---|---|
| `0b48:0006` | `pref_remap(setting, v)` | for settings 5/6 when the flight device is 3 (FCS): v = `DS:089F[v]` (rudder) / `DS:08A3[v]` (throttle) |
| `0b48:0043` | `pref_msg_subst(c)` → far char * | text substitution for the conflict messages: 'k' → `DS:436E` (if `DS:0879 == 6`) else `DS:436C`; 'l' → `DS:436A[DS:087D]`; 's' → `((DS:0879 == 6) ? DS:4370 : DS:4384)[DS:43B6[DS:0879]]`; 't' → `DS:087D ? DS:4370[DS:087D] : DS:4394`; others → null (switch on c − 'k', 11 cases, table `0b48:00CF`) |
| `0b48:00e5` | `pref_set_device(item)` | `k = item.user` (4..6); `DS:43B6[k] = pref_remap(k, DS:0874 choice)`; item.label = `DS:085D[k][choice]`; mask 3 |
| `0b48:0133` | `pref_flight_chosen()` | choice 3 (FCS): set item 14 (`4ad6:0134`); rudder/throttle label items y/labels switched to the 2-entry FCS arrays (`DS:0867 = 438A`, …, counts 2/2, rows A2h/AAh); if throttle device is 1 or 2 → queue message for setting 6 (`DS:0879 = 6`, `DS:085A` pending); if rudder is 1 → queue setting 5; `DS:087D = 0`. Otherwise restores the normal arrays (rows 9Eh/A5h, counts 3/4) and sets the label. Returns 1 |
| `0b48:0201` | `pref_rudder_chosen()` | if the new rudder = 1 (joystick 2) and throttle = 2 → conflict: `DS:43BB = 1`, queue setting 5 with message variant `DS:087D = 2`; else `pref_set_device(item 15)` |
| `0b48:0261` | `pref_throttle_chosen()` | if the new throttle = 2 (slider) and rudder = 1 → conflict: `DS:43BC = 2`, queue setting 6, `DS:087D = 1`; else `pref_set_device(item 16)` |
| `0b48:02c1` | `pref_draw_window` | above |
| `0b48:0307` | `pref_draw_group` | `draw_bevel_box()`; rivets in the 4 corners (x+2,y+2), (x+2,B−6), (R−5,y+2), (R−5,B−6); FONT3 `text_engrave_center(label, C1h, B1h, C0h)` |
| `0b48:03c7` | `pref_toggle(k)` | (also the Alt-J/D/S/M hotkeys, k = 0..3) calls `DS:087F[k]()` (which toggles `DS:43B6[k]` and applies it: joystick detect / mouse init / sound mute); when the preferences screen is open (`DS:085A`) the label item `DS:089B[k]` gets `DS:085D[k][DS:43B6[k]]`, mask 3 |
| `0b48:044e` | `pref_toggle_cb` | `btn_cb()` → `pref_toggle(5FDE − 3)` |
| `0b48:0467` | `pref_choice(v)` | `DS:0874 = v` (CHOOSE callback) |
| `0b48:0472` | `pref_device_cb` | `btn_small_cb(0)` →: `k = item.user`; `strtab_load(SFTBTNS0.DAT)`; item.user = `DS:086B[k]` (count); `DS:0874 = −1`; `choose_run(pref_choice, DS:43BA[k], DS:0871[k])`; `hs_restart()`; if a choice was made: `DS:088F[k]()`; item.user = k; `strtab_free()` |
| `0b48:0510` | `pref_draw_label` | `draw_inset_box2()`; FONT3 CCh transparent, centred, y+4; mask := 40h |
| `0b48:0574` | `cal_wait_button()` → bool | `menu_flush()`; waits until mouse buttons are up (when mouse on) and joystick buttons are up (when joystick on); then waits for a joystick button (returns 1 after it is released) or Esc (returns 0) |
| `0b48:0616` | `cal_prompt(i, row)` → bool | on the work page: `draw_popup_box()`, `rect_shrink(6)`, `flow_text(strtab_get(row, i), 1, 0)`, `rect_grow(6)`; copy (80, 50, 160, 30) to the front page; `cal_wait_button()` |
| `0b48:0680` | `cal_erase()` | copy (80,50,160,30) spare → work and work → front |
| `0b48:06bf` | `cal_sort(int v[3], n, throttle)` | n == 2: v[2] = v[1], v[1] = (v[0] + v[2]) / 2; sorts v[0..2] ascending (3 compare-swaps); throttle: `d = max(v[2] − v[0], 20)`; `v[1] = old v[2]`, `v[2] = d` |
| `0b48:0740` | `cal_params(dev, &n, &axes, &raw, &xs, &ys)` → row | n = `DS:08B5[dev]`, axes = `DS:08C3[dev]` (bit0 X, bit1 Y), raw = `DS:08D1[dev]`; buffers `DS:43C9/43CF` (raw) or `DS:43BD/43C3`; returns row `DS:08A7[dev]` of `CALBRATE.DAT` |
| `0b48:079c` | `calibrate(dev)` | save the screen (`22ce:00bc`); joystick detect (`16e3:00ac`); rect (80,50,160,30); FONT3; `flow_setup(3, 8, 1)`; for i < n while not cancelled: `cal_prompt(i, row)`; if accepted: (i == 0 → re-detect) raw mode → `16e3:01e3(0, &xs[i], &ys[i])` (read stick 0) else `xs[i] = 16e3:0339(2)`, `ys[i] = 16e3:0339(3)` per axis bit; `cal_erase()`. If raw and n > 1: one more `cal_prompt(0)`. If completed: `cal_sort(xs, n, 0)`, `cal_sort(ys, n, dev == 2)` |
| `0b48:0902` | `pref_calibrate_cb` | `btn_small_cb(0)` and joystick on → `DS:085C = 1` |
| `0b48:0920` | `pref_accept_cb` | `btn_cb()` → result 1 |
| `0b48:0938` | `pref_dup_strings(first, n, char **dst)` | dst[k] = xmalloc'ed copy of `str_get(first + k)` |
| `0b48:099d` / `0acf` | `pref_labels_load()` / `_free()` | the arrays listed above |
| `0b48:0a99` | `pref_free_strings(char **a, n)` | |
| `0b48:0b6e` | `pref_apply_all()` | (from `sys_init`) for k = 0..3: `DS:43B6[k] ^= 1; DS:087F[k]()` (re-applies each setting through its toggle); if flight device = 1 (joystick): detect, and if absent → device 0 (keyboard) |
| `0b48:0bb9` | `pref_labels_init()` | label of items 7–10 (k < 4) and 14–16 (k ≥ 4) = `DS:085D[k][DS:43B6[k]]`; if the flight device is 3: `DS:0874 = 3; pref_flight_chosen()` |
| `0b48:0c22` | `pref_frame` | dispatch + present; if `DS:085A` pending messages: while `DS:0879 ≥ 0`: `req_ok(far pref_msg_subst, 17, 8)` (CONTROL-conflict text REQUEST 17h?/string 17, button 8), then `pref_set_device(item for 0879)`, `DS:0879 = DS:087B`, `DS:087B = −1`; clear. If `DS:085C` (calibrate): `strtab_load(CALBRATE.DAT)`; `d = 0eb4:0205()` (device chooser, shell_ui_career); if d: `calibrate(d − 1)`; `strtab_free()` |
| `0b48:0cf0` | `prefs_screen()` | `DS:085A = 1`, pending = 0; `screen_show(46, 396h, 1)`; `pref_labels_load(); pref_labels_init()`; `hs_set_table(4ad6:0000, 19)`; `hs_draw_all()`; `menu_run(pref_frame)`; `ui_busy()`; `pref_labels_free()`; `DS:085A = 0` |

(The exact meaning of the conflict messages lives in `REQUEST.SCD`/`CALBRATE.DAT`; the queue
`DS:0879`/`DS:087B` holds up to two pending setting indices.)

## 5. Best missions / best careers (`best.c`, `09a9`, screen 42 `PARTS`/`BEST`, table `4a08:000d`) — V

Records in far data segment `4a08`: **best missions** `4a08:0115` = 10 × 55-byte records (count
`DS:433F`, file `TOPMISS.DAT`), **best careers** `4a08:033B` = 10 × 122-byte pilot records (count
`DS:4341`, file `TOPACE.DAT`); loading/saving is shell_data (`1193:050D/05B8/065C/0727`). Mode
`DS:4307`: 0 = missions, 1 = careers.

55-byte best-mission record (written by `best_store` from the globals of the finished mission):

| Off | Size | From (single mission / career) | Off | Size | From |
|---|---|---|---|---|---|
| +00 | char[16] | pilot name (entered, or `DS:4754` career pilot name) | +2E | u8 | career `DS:4775`, else `0f67:02ed(DS:4B8E)` (insignia index) |
| +10 | u16 | career `DS:478A`, else `DS:4B90` (aircraft) | +2F | u8 | `DS:4B8E` (service) |
| +12 | s32 | score = `DS:4249` sign-extended | +30 | u8 | career `DS:4777`, else rank from `225d:018d(DS:4B8E)` |
| +16 | u16 | `DS:4247` | +31 | u8 | `DS:4B8F` |
| +18 | u16 | `DS:4249` | +32 | u8 | `DS:4B87` (mission mode) |
| +1A | u16 | `DS:422B` | +33 | u8 | `DS:4B88` |
| +1C | u16[4] | `DS:4237` | +34 | u8 | `DS:4B89` |
| +24 | u16[4] | `DS:423F` | +35 | u16 | career `DS:477B`, else 0 |
| +2C | u16 | `DS:4227` | | | |

(The meanings of these mission-result globals are shell_data's; they are the `SIM.OUT` summary.)

| # | Rect | Callback | Label |
|---|---|---|---|
| 0 | 7,32,306,133 | `09a9:0002` (`draw_side_riveted_panel`) | |
| 1 | 45,6,218,37 | `draw_header_panel` | |
| 2 | 45,6,218,20 | `best_draw_header` `00c4` | |
| 3–5 | (38,49,50) (130,49,24) (219,49,25), h 6 | `best_draw_colhead` `0057` | user 0–2 |
| 6 | 11,56,255,65 | `lbox_draw` | rows (10 visible) |
| 7 | 272,55,25,66 | `best_draw_scroll` `000c` | |
| 8, 9 | 275, 58/98, 20,19 | `lbox_arrow_cb` | arrows |
| 10 | 41,141,56,18 | `best_btn_cb` `0039` | 6 VIEW |
| 11 | 209,141,56,18 | `best_btn_cb` | 7 EXIT |

| Address | Name | Behaviour |
|---|---|---|
| `09a9:0002` | `best_draw_window` | `draw_side_riveted_panel()` |
| `09a9:000c` | `best_draw_scroll` | `draw_bevel_box()`; outline C0h rect (x+4, y+25, 18, 16) between the arrows |
| `09a9:0039` | `best_btn_cb` | `btn_cb()` → `DS:5FD2 = 5FDE` (10 VIEW / 11 EXIT), result 1 |
| `09a9:0057` | `best_draw_colhead` | FONT3, transparent; label id = `user == 0 ? 0 : DS:06FC[user + (DS:4307 != 1 ? 2 : 0)]` → careers: PILOT NAME, SERVICE, SCORE; missions: PILOT NAME, PLANE, SCORE; `text_engrave(str, C7h, B1h, C0h, x, y)` |
| `09a9:00c4` | `best_draw_header` | record 0 of the current list: `sprintf(DS:419A, "%Fs       %ld", name, score)` (7 spaces); item label = `str_get(DS:4307 ? 5 : 4)` ("ALL TIME BEST CAREER"/"…MISSION"); `draw_header_panel()`; font TALK (`DS:421A`); the line centred at y+h+3 in `text_engrave(C7h, B1h, C0h)`; `SYMBOLS[sym + 8]` at (x+9, y+2) and (x+w−22, y+2), sym = record 0 insignia (+2E, or +21 for careers) |
| `09a9:0201` | `best_draw_row(i, y)` | (`lbox` custom row) careers (122-byte record, `4a08:033B + 122 i`): `sprintf("%Fs %Fs", strtab_get(3, rec[+23h]) rank, name)` at x+15; `strtab_get(6, rec[+22h])` (service) at x+120; `ltoa(rec[+65h] s32)` at x+208; `SYMBOLS[rec[+21h] + 16]` at x+5. Missions: rank `strtab_get(3, rec[+30h])` + name; aircraft name `2777:00a1(rec[+10h])` at x+120; score (+12h) at x+208; `SYMBOLS[rec[+2Eh] + 16]` |
| `09a9:0381` | `best_draw_bg` | `screen_clear_panel()`; `draw_title_bar_for(0FFh, 0, str_get(DS:4307 ? 9 : 8))` ("BEST CAREERS"/"BEST MISSIONS") |
| `09a9:03b0` | `best_frame` | dispatch + present + `edit_poll()`; Esc → `DS:5FD2 = 11` |
| `09a9:03e6` | `best_load_mission(i)` | copies record i back into the mission globals (`DS:477B, 4B8E, 4B8F, 4B88, 4B87, 4B89, 4247, 4249, 422B, 4237[4], 423F[4], 4227`) for replaying its debrief |
| `09a9:0481` | `best_run(n)` | below |
| `09a9:058f` | `best_careers()` | `DS:4307 = 1`; `2624:0902`; `best_run(DS:4341)`; `2624:09c4` |
| `09a9:05ac` | `best_missions()` | `DS:4307 = 0`; `2777:0000`; `best_run(DS:433F)`; `2777:04df` |
| `09a9:05c9` | `best_rank_subst(c)` | `%r` only (else fatal line 19Eh): `itoa(DS:4306, DS:419A)` |
| `09a9:060a` | `best_store(i)` | career mission (`DS:4B87 == 1`): name = `DS:4754` etc.; else `text_entry(0, buf = "" (DS:0706, 20 bytes), 15, anon = 1)` asks for the name; fills the staging record `DS:4308` (table above) and copies it to slot i |
| `09a9:072e` | `best_mission_insert()` | after a mission: first slot i whose score (+12h, long) is below `DS:4249` (sign-extended); if i < 10: shift slots i..8 down, count+1 (max 10), `DS:4306 = i + 1`, `req_ok(best_rank_subst, 10, 8)` (REQUEST string 10: "…ranks %r…"), `best_store(i)` |
| `09a9:07ee` | `best_career_insert()` | current pilot record `DS:4754` (122 bytes) inserted by its score `DS:47B9:47BB` (long) into the top-10 careers (called from `shell_cleanup`) |
| `09a9:088e` | `best_career_remove()` | removes the entry that matches the current pilot (score, service `DS:4776`, rank `DS:4777`, `DS:4784`, `DS:477B`), count−1 (≥ 0) |
| `09a9:096a` | `best_init()` | `hs_default_links(4a08:000d, 12)` |

```
best_run(n):
  loop:
    strtab_load("strings_.dat" res_name("strings_", -1, "dat"))
    lbox_setup(0, 0, n, 10 visible, fmt 0, draw best_draw_row); lbox_bind(4a08:000d, 6, 8)
    screen_open(42, best_draw_bg, 396h, 1); hs_set_table(4a08:000d, 12); DS:5FD2 = -1
    hs_draw_all(); menu_run(best_frame); ui_busy()
    if DS:5FD2 == 10 (VIEW):
        careers: copy record lbox_selected() to DS:4754 (122 bytes); strtab_free(); pilot_record_screen() (135d:04ec)
        missions: best_load_mission(lbox_selected()); strtab_free(); debrief_screen(0) (0637:082a)
        continue
    break if DS:5FD2 == 11                                    // EXIT or Esc
  strtab_free()
```

(VIEW with an empty list: `lbox_selected()` = 0 → shows slot 0; the fly menu prevents entering
with no records: `fm_frame`.)

## 6. Campaign-set selection (`campset.c`, `0a41`, screen 44 `CLOUDS`/`CAMPSET`, table `4a88:0010`) — V

| # | Rect | Callback | Label |
|---|---|---|---|
| 0 | 77,45,175,104 | `draw_side_riveted_panel` | |
| 1 | 34,5,105,30 | `cset_draw_prompt` `0003` | |
| 2 | 14,30,123,51 | `lbox_draw` | set names (5 visible) |
| 3 | 139,30,24,51 | `draw_bevel_box` | |
| 4, 5 | 142, 32/61, 19,18/17 | `lbox_arrow_cb` | |
| 6 | 14,86,55,13 | `cset_btn_cb` `00e7` | 5 CANCEL |
| 7 | 108,86,55,13 | `cset_btn_cb` | 6 ACCEPT |

| Address | Name | Behaviour |
|---|---|---|
| `0a41:0003` | `cset_draw_prompt` | FONT3; mode 0 (`DS:4344 == 0`): `sprintf(buf, "%Fs %s %s", rank_title[DS:4777] (far `DS:57A2`), DS:4754 name, str_get(0) "is now on")` then str 1 "active duty. Select which", str 2 "Campaign Set to fly in:"; mode 1: str 3 "Select the Campaign Set", str 4 "to fly from:"; three lines `text_engrave(C1h, B1h, C0h)` at (x−20, y), (x−20, y+8), (x−20, y+16) (the first line only in mode 0) |
| `0a41:00e7` | `cset_btn_cb` | `btn_small_cb(0)` → result `5FDE == 7 ? 1 : 2` |
| `0a41:010f` | `cset_draw_row(i, y)` | reads the first 80 bytes of `CSET<DS:0742[i]>.DAT` (fatal campset.c line 89h if missing) and draws them at (x+5, y) ("ACES OF THE PACIFIC", "1946!") |
| `0a41:01a0` | `cset_frame` | dispatch + present |
| `0a41:01c1` | `cset_choose(mode)` → set / FFh | if the list `DS:0742[DS:0754]` is empty → FFh; `DS:4344 = mode`; `lbox_setup(…, DS:0754, 5, draw cset_draw_row)`; `lbox_bind(4a88:0010, 2, 4)`; `screen_show(44, 81h, 1)`; table (8 items), focus 7 (ACCEPT); `r = menu_run(cset_frame)`; r == 2 → FFFFh else `DS:0742[lbox_selected()]`; `ui_busy()`; `1f85:0833(set)` (shell_data: select the data set); returns the low byte |
| `0a41:028d` | `cset_scan(a, b, cur)` → bool | walks the installed data sets (`2008:0022` first, `2008:002e` next, `2008:0064` last; shell_data): for each, `287b:0104(set)` (load campaign info), `287b:04b5(b, a)` (campaign valid for the pilot?) → append to `DS:0742[DS:0754++]`; returns 1 if some valid set differs from `cur`; `287b:0556` after each |

Callers: `0874:11ff` (career events: new campaign), `0ed9:0347` (pilot roster), `13be:0339`.

## 7. Mission briefing (`0c1d`, screen 21 `BRIEF`/`MISSBRF`, table `4af1:0000`, 11 items) — V

| # | Rect | Callback | Mask | Label |
|---|---|---|---|---|
| 0 | 8,30,304,129 | `brief_draw_text` `0031` | 40 | briefing text |
| 1 | 17,5,68,55 | `brief_draw_officer` `0106` | 40 | |
| 2 | 97,5,191,26 | `brief_draw_title` `016a` | 40 | |
| 3 | 17,113,271,12 | `brief_draw_weather` `026d` | 40/0 | |
| 4 | −5,131,103,17 | `brief_btn_cb` `031f` | 74 | 2 DECLINE MISSION |
| 5 | 101,131,103,17 | `brief_btn_cb` | 74 | 3 REALISM PANEL |
| 6 | 207,131,102,17 | `brief_btn_cb` | 74 | 4 FLIGHT MAP |
| 7 | 30,151,120,17 | `brief_btn_cb` | 74 | 5 PREFLIGHT OPTIONS |
| 8 | 153,151,120,17 | `brief_btn_cb` | 74 | 6 BEGIN MISSION |
| 9 | 101,72,110,14 | `brief_draw_label` `02ef` | 0/40 | 19 HISTORIC OVERVIEW |
| 10 | 16,88,276,44 | `brief_draw_overview` `00c7` | 0/40 | historic overview text |

Globals: `DS:08F8` briefing variant (−1 = pick), `DS:43EB` player insignia/service index for the
`%a`/`%e` substitutions, `DS:43EC` chosen button, `DS:43D6` = 1 when BEGIN MISSION was chosen,
`DS:43D7[4]` far strings = weather names (entries 9–12 of `SFTBTNS0.DAT`: clear, partly cloudy,
mostly cloudy, overcast), `DS:43E9` officers bitmap. `DS:626B` mode (2 = historic mission),
`DS:626C` mission type, `DS:626F` weather, `DS:6277` date, `DS:62C5` player service (shell_data).

| Address | Name | Behaviour |
|---|---|---|
| `0c1d:0000` | `brief_subst(c)` | `%a` → `strtab_get(11, DS:43EB + 2)`, `%e` → `strtab_get(11, DS:43EB)` (allied / enemy names), else 0 |
| `0c1d:0031` | `brief_draw_text` | `draw_side_riveted_panel()`; FONT3; text = historic ? `1f85:0779(DS:08F8)` : `strtab_get(DS:626C, DS:08F8)` (`BRIEF.DAT`); rect (100, 64, 204, 90); `flow_setup(−3, 8, 1)` (engraved); `flow_text(text, 1, brief_subst)` |
| `0c1d:00c7` | `brief_draw_overview` | FONT3; `flow_setup(−3, 8, 1)`; `flow_text(1f85:07b7(DS:08F8, 1, 0, 0), 0)` (historic overview) |
| `0c1d:0106` | `brief_draw_officer` | `draw_inset_box2()`; `DS:43E9 = bmp_load("officers.bmp")`; `draw_bitmap(frame DS:62C5, x+2, y+2, 0)`; `bmp_free` (`168a:04b1`) |
| `0c1d:016a` | `brief_draw_title` | `draw_popup_box()`; FONT4; name = historic ? `1f85:073b(DS:08F8)` : `str_get(8 + DS:626C)`; `text_emboss(name, centred, y+3, C1h, C0h, B1h)`; FONT3; "DATE: " + `284f:021c(DS:6277)` (date text) `text_engrave(C1h, B1h, C0h)` centred at y+15 |
| `0c1d:026d` | `brief_draw_weather` | `draw_popup_box()`; FONT3; "WEATHER: " + `DS:43D7[DS:626F]` engraved at (x+5, y+3) |
| `0c1d:02ef` | `brief_draw_label` | `draw_popup_box()`; FONT3; `text_engrave_center(label, C1h, B1h, C0h)` |
| `0c1d:031f` | `brief_btn_cb` | `DS:43EC = 5FDE`, result 1 |
| `0c1d:033d` | `brief_draw_bg` | `screen_clear_panel()`; `draw_title_bar_for(DS:62C5, DS:6277, str_get(7) "MISSION BRIEFING")` |
| `0c1d:0362` | `brief_set_historic(h)` | item 3 mask = h ? 0 : 40h (weather hidden in historic missions); items 9, 10 mask = h ? 40h : 0 |
| `0c1d:0396` | `brief_frame` | dispatch + present; Esc → `DS:43EC = 4` (decline) |
| `0c1d:03c6` | `briefing(variant)` | below |
| `0c1d:06c0` | `brief_init()` | `hs_default_links(4af1:0000, 11)` |

```
briefing(variant):
  copy weather names 9..12 of SFTBTNS0.DAT into DS:43D7[k] (farmalloc 15 bytes each, 48b8 = _fstrncpy)
  historic = (DS:626B == 2)
  if historic: 1f85:04fb, 05bb, 043b (load historic texts); DS:08F8 = variant >= 0 ? variant : 2624:03fb(DS:478E, 477B, 477D)
  else: strtab_load("brief.dat"); type = DS:626C
        type 8 (anti-shipping): DS:08F8 = DS:6477; type 9 (ground attack): DS:08F8 = DS:64B2[DS:62E5 * 18]
        other: if DS:08F8 == -1: DS:08F8 = rand(3) (24b7:00c8)
  brief_set_historic(historic); DS:43EC = 8 (focus BEGIN MISSION)
  DS:43EB = 0f67:02ed(service): type 8 → DS:6475[62E5*20]; type 9 → DS:64B3[62E5*18]; else DS:62C5[(DS:6263 ? 1 : 2) * 90h]
  loop:
    screen_open(21, brief_draw_bg, 161h, 1); hs_set_table(4af1:0000, 11); hs_focus(DS:43EC); hs_draw_all()
    menu_run(brief_frame); ui_busy()
    5 REALISM PANEL: realism_run() (historic missions: DS:626B = 0 around the call, i.e. treated like single missions); continue
    6 FLIGHT MAP: strtab_free (not historic); p = 12c4:0377(historic || variant >= 0);
                  fltmap_show(p[0], p[1], p[2], p[3], DS:626D) (06c7:0b14, shell_ui_flight); 12c4:03cc(...);
                  reload brief.dat; continue
    else break
  free the texts (historic: 1f85:057d, 063d, 04bd) and the weather strings
  7 PREFLIGHT OPTIONS: preflight(variant) (1513:0e05, shell_ui_mission)
  8 BEGIN MISSION: DS:43D6 = 1
  4 DECLINE / Esc: DS:08F8 = -1; DS:43D6 = 0
```

Callers: `0583:03c2` (historic), `0787:0181` (flight deck), `100e:12c9` (single mission set-up),
`1513:0e05` (back from preflight). They fly when `DS:43D6 == 1`.

## 8. One-time initialisation (`once.c`, `0a71`) — V

| Address | Name | Behaviour |
|---|---|---|
| `0a71:0001` | `fonts_load()` | `font_load` of `FONT1.FNT` → `DS:4222`, `FONT2` → `4220`, `FONT3` → `421E`, `FONT4` → `421C`, `TALK.FNT` → `421A`; any missing → fatal (once.c line 2Fh); `font_select(FONT1)` |
| `0a71:00eb` | `parts_load()` → ok | `DS:5FE6 = bmp_load("parts.bmp")`, `DS:5FE4 = bmp_load("symbols.bmp")` (`168a:011c`); failure → fatal line 40h |
| `0a71:015c` | `dialogs_init()` | see `shell_ui.md` §3.2 |

## 9. Screen flow of this part

```
main_menu (04df:018d) ─1─> flymenu_run (0b16:01a7) ─historic─> 0583:03c2 ; ─ace─> 0c8a:05db → 100e:12c9 → shell_fly
      │                         ├─types 3..11─> 1612:0388 → 100e:12c9 (set-up → briefing 0c1d:03c6) → shell_fly(0)
      │                         ├─CUSTOM─> 147e:07e5 ; ─BEST─> best_missions (09a9:05ac) → back ; RETURN/Esc → main menu
      ├─2─> career menu 0607:011d        ├─3─> 05fa:007f → 1612:0388 → 0ddd:0cde / 0ddd:0d2f
      ├─4─> CHOOSE: PREFERENCES → prefs_screen (0b48:0cf0) ; WATCH DEMO → shell_fly (626B=4) ; CREDITS → INTACE6.TTM
      ├─5─> shell_fly (626B=3, mission recorder)          └─6─> return → shell_exit(0)
briefing (0c1d:03c6) ─REALISM─> realism_run (0a8d:07cb) ; ─FLIGHT MAP─> 06c7:0b14 ; ─PREFLIGHT─> 1513:0e05 ; BEGIN → DS:43D6 = 1
best_run ─VIEW─> 135d:04ec (career record) / 0637:082a (mission debrief)
prefs_screen ─CALIBRATE─> 0eb4:0205 → calibrate (0b48:079c)
```

## 10. Hand-offs

* **shell_data**: `24b7:000c` is stepped once per frame by the fly menu (additive lagged-Fibonacci
  generator, 56 words at `DS:551E`, indices `DS:5590/5591`, counter `DS:558E` mod 400h);
  `24b7:00c8(n)` random 0..n−1; the best-mission record layout (§5) and the globals copied into it;
  `1f85:0833` selects a data set; `22ce:032d` = `itoa(v, buf, 10)`.
* **platform**: joystick calibration reads `16e3:01e3(stick, &x, &y)` and `16e3:0339(axis)`;
  `16e3:00ac` = joystick detection (sets `DS:0FF8`).

## 11. Open questions

* `0b48:0006` remap tables `DS:089F`/`DS:08A3` and the conflict message strings (REQUEST string
  17 with `pref_msg_subst`) were not rendered; the logic is complete.
* `0b16`'s `DS:4F22 = 1` (set on entering the fly menu) — read elsewhere (Likely by the set-up
  screens to know they come from the single-mission menu).
