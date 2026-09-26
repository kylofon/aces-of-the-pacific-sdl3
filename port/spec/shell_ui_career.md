# shell_ui part — career screens: dog-fight ace chooser, vehicle viewer, calibration chooser, new pilot, awards, pilot roster, campaign selection, pilot record

Target `Game/PS.EXE` (DGROUP `4D08`). Segments `0c8a` dogace.c, `0ddd` view.c, `0eb4` (joystick
calibration device chooser), `0ed9` / `0f67` / `13be` pilot.c (new pilot, roster records, roster
screen), `0f35` (award ceremonies), `0fa1` campsel.c, `135d` (pilot record). Toolkit names:
`shell_ui_toolkit.md`; the current pilot record `DS:4754..47CD` and the roster (far array
`4b4c:000e + 122·i`, count `DS:4A18`, event-letter blob `DS:47CE`) are described in
`shell_data.md` §4. Far data tables are given with their file segment. Confidence **V** unless
marked.

**Side group** (`0f67:02ed`, used everywhere): service 0–2 (USN, USMC, USAAF) → 1 (USA); 3–4 (IJN,
JAAF) → 0 (Japan); 5–7 → 2 (Britain); 8 → 3 (China); 9 → 4 (USSR); 10 → 5 (Netherlands); other → FFh.
It indexes the nation strings (`SFTBTNS0.DAT` row 0, 144 + n) and the insignia frames
(`DS:5FE4[side + 16]`, flags `[side + 8]`).

## 1. Dog-fight a famous ace (`dogace.c`, `0c8a`, screen 14 `DOGACE`, table `4b01:000f`, 11 items)

"DOGFIGHT A FAMOUS ACE": a list of the enemy aces (insignia, name, victories), the selected ace's
portrait and biography; the sentence "Aces from the %a." has an inline button for the enemy
service. Returns the ace id or −1.

| # | Rect | Callback | Label (`DOGACE.SCD`) |
|---|---|---|---|
| 0 | 6,30,309,144 | `draw_side_riveted_panel` | |
| 1 | 20,6,224,6 | `dg_draw_prompt` `02c2` | str 3 "Aces from the %a." |
| 2 | (inline) | `dg_service_cb` `0266` | service name |
| 3 | 15,14,167,65 | `lbox_draw` (mask 5Ch) | |
| 4 | 189,14,25,65 | `dg_draw_scroll` `0295` | |
| 5 | 222,13,73,63 | `dg_draw_face` `0321` | |
| 6 | 14,86,282,49 | `dg_draw_bio` `042a` | |
| 7, 8 | 192,17 / 192,56, 20×19 | `lbox_arrow_cb` | arrows |
| 9, 10 | 72 / 164, 149, 77,17 | `dg_btn_cb` `0248` | str 1 "CANCEL", str 2 "SELECT" |

State: `DS:43F8` enemy service, `DS:43F7` chosen ace, `DS:43F9` pressed button (10 initially),
`DS:0928` "change service" request, `DS:43EE` number of listed aces, `ACEFACE.DAT` table slot
`DS:43F2` (8-byte records {u16 service, u16 bitmap number, u16 first ace, u16 last ace}, count
`DS:43F4`), `DS:43F0` near array of loaded `ACE<n>.BMP` handles (one per record), `DS:43F6` loaded.

| Address | Name | Behaviour |
|---|---|---|
| `0c8a:0009` | `dg_load_faces()` | first call: `DS:43F2 = table_load("aceface", "dat", 8, 0, 11h, 1, …)` (fatal 66h), `DS:43F4 = table_count`, handles array zeroed, `DS:43F6 = 1`; then per record: service ≠ `DS:43F8` → free its bitmap if loaded; else `bmp_load_planes(res_name("ace", rec.bitmap, "bmp"))` (fatal 7Ah with the name if missing) |
| `0c8a:018d` | `dg_free_faces()` | if loaded: `table_free`, free all bitmaps and the array, `DS:43F6 = 0` |
| `0c8a:01e4` | `dg_change_service()` | `s = fly_for_choose(5)` ("WHO WILL YOU FLY AGAINST?"); `s != −1` → `DS:43F8 = s`; `dg_load_faces()` |
| `0c8a:0205` | `dg_subst(c, item far *it)` → 0 | `c == 'a'`: `it.label` = copy of `strtab_get(0, DS:43F8 + 133)` in `DS:411A`; returns 0 (inline button) |
| `0c8a:0248` | `dg_btn_cb` | `if btn_cb()`: `DS:43F9 = 5FDE`; result 1 |
| `0c8a:0266` | `dg_service_cb` | `dg_subst(5FDE, item)`; mask 74h; `if choose_entry_cb()`: `DS:0928 = 1` |
| `0c8a:0295` | `dg_draw_scroll` | `draw_bevel_box()`; colour C0h rect (x+4, y+25, 18, 15) |
| `0c8a:02c2` | `dg_draw_prompt` | FONT3; `flow_text_buttons(4b01:000f, 2, dg_subst, {str_get(3), 0}, x, y, x+w)`; mask 40h |
| `0c8a:0321` | `dg_draw_face` | `acelist_select(0)`; `DS:43F7 = acelist_id(lbox_selected())`; record r with `first ≤ id ≤ last` (fatal 12Ah if none); `draw_inset_box2()`; bitmap not loaded → fatal 12Eh; `draw_bitmap(ACE[r] frame id − first, x+2, y+2)`; mask 40h |
| `0c8a:042a` | `dg_draw_bio` | FONT3, `2302 = 1`; `rect_grow(4); draw_popup_box(); rect_shrink(4)`; `flow_setup(−3, 8, 1)`; `flow_text(acetxt_bio(DS:43F7), 1, 0)`; mask 40h |
| `0c8a:04a0` | `dg_draw_row(i, y)` | `acelist_select(0)`; `a = acelist_id(i)`; insignia `DS:5FE4[side(ace_service(a)) + 16]` at (x+5, y); `ace_name(a)` at (x+15, y); `itoa(ace_kills(a))` at (x+w−15, y); masks of items 5 and 6 := 3 (face and bio follow the list) |
| `0c8a:0571` | `dg_draw_bg` | `screen_clear_panel()`; `draw_title_bar_for(DS:43F8, 0, str_get(0))` |
| `0c8a:0594` | `dg_frame` | dispatch + present; if `DS:0928`: `dg_change_service()`, `DS:43F9 = 2`, `DS:0928 = 0` (the service chooser's own result ends this `menu_run`: L); else result 2 (Esc) → `DS:43F9 = 9` |
| `0c8a:05db` | `dogace_choose()` → s8 | below |

```
dogace_choose():                                    // caller flymenu_run 0b16:01a7
  acetxt_open(); strtab_load(res_name("sftbtns", 0, "dat"))
  DS:43F8 = fly_for_choose(5); if -1: DS:43F7 = -1
  else:
    DS:43F9 = 10; dg_load_faces()
    do:
      acelist_build(DS:43F8, 0, 0, 1); acelist_select(0); DS:43EE = acelist_enabled_count()
      lbox_setup(…, DS:43EE, 10, draw dg_draw_row); lbox_bind(4b01:000f, 3, 7)
      screen_open(14, dg_draw_bg, 44h, 1); hs_set_table(4b01:000f, 11); hs_focus(DS:43F9); hs_draw_all()
      menu_run(dg_frame); ui_busy()
      if DS:43F9 == 9 (CANCEL/Esc): DS:43F7 = -1; break
    while DS:43F9 != 10 (SELECT)
    for d in 0..8: if (d-1)·15 + 29 <= DS:43F7 < d·15 + 29: 1f85:0833(d)   // select the ace's data set
  dg_free_faces(); strtab_free(); acetxt_close(); return DS:43F7
```

## 2. Vehicle viewer (`view.c`, `0ddd`, screen 25 `SIM`/`VIEW`, table `4b1e:000d`, 11 items)

A 3D view of one aircraft (on a carrier deck or an airfield) or one ship, rotated and zoomed with
four diamond buttons, with its description; PREVIOUS / NEXT browse all types (main menu VIEW
VEHICLES), or only CONTINUE for one type (flight deck VIEW AIRCRAFT, career "NEW AIRPLANE"
event). The 3D part is shell_data's viewer module `217d` (`view3d_*`, `DS:52A0` view, `DS:52A2`
camera, `DS:52A4` model) on top of the 3Space library (`3d50`, `48ea`).

| # | Rect | Callback | Label (`VIEW.SCD`) |
|---|---|---|---|
| 0 | 0,0,320,200 | `vw_draw_view` `00b5` | 3D view + title bar |
| 1 | 0,130,319,69 | `vw_draw_panel` `010c` | bottom panel (its y = 130 is the view's lower edge everywhere) |
| 2 | 23,137,45,37 | `draw_popup_box` | |
| 3–6 | (38,140) (46,148) (38,156) (30,148), 15×15, round (flag 8) | `vw_diamond_cb` `0120` | glyphs 86h..89h: zoom in, rotate +, zoom out, rotate − |
| 7 | 76,137,220,37 | `vw_draw_text` `0286` | description |
| 8, 9, 10 | 23 / 123 / 223, 180, 73,18 | `vw_btn_cb` `02d4` | 0 "PREVIOUS", 1 "NEXT", 2 "CONTINUE" |

State: `DS:4470` aircraft (1) / ships (0), `DS:446E` selected type, `DS:446F` loaded type, `DS:445A`
number of types, `DS:446D` service (title bar insignia), `DS:446C` side group, `DS:4460` name
buffer (80 bytes on the caller's stack), `DS:4462` title date (career date or 0), `DS:445C:445E`
far description text, `DS:4458` name table (`namelist_load`), `DS:4456` `PITCH_.DAT` slot
(aircraft: 6-byte records {+0 pitch, +2 model variant, +4 viewable}), camera: `DS:4464` default
distance, `DS:4468` distance, `DS:4466` height, `DS:446A` yaw; limits `DS:09AC` min distance,
`DS:09AE` max, `DS:09B0` zoom step, `DS:09B2` = 512 yaw step, `DS:09A8` height base, `DS:09AA` start
yaw, `DS:09A2` model altitude, `DS:09A4` model heading, `DS:09A6` model pitch, `DS:09A0` ground colour.

| Address | Name | Behaviour |
|---|---|---|
| `0ddd:0006` / `0060` / `0039` | `vw_pitch(t)` / `vw_variant(t)` / `vw_viewable(t)` | `PITCH_` record fields +0 / +2 / +4 (the first two return 0 for ships) |
| `0ddd:0094` | `vw_model_name(t)` | `strpool_copy(DS:4458[t])` (base name of the 3D model: used by `view3d_load_model`) |
| `0ddd:00b5` | `vw_draw_view` | `vw_render(0)`; `draw_title_bar_for(DS:446D, DS:4462, DS:4460)`; mask 40h; `hs_load(table, 1)` (rect of item 1), `draw_bottom_bar()`, `hs_load(table, 0)` |
| `0ddd:010c` | `vw_draw_panel` | `tile_fill_rect(); draw_frame(); draw_bottom_bar()` |
| `0ddd:0120` | `vw_diamond_cb` | not pressed: `draw_diamond_up()`. Pressed (`5FDC & 4`): pages work→spare, `vw_save_strips()`; pages front→work; `draw_diamond_down()`; `cursor_draw(601A, 6018)`; pages work→front; `vw_save_strips()`; save `view.+0C`; **while the button is held** (`DS:2033`) and the mouse is over an item (`hs_hit`): item 3: `DS:4468 −= DS:09B0`, clamp ≥ `DS:09AC`; item 5: `+= DS:09B0`, clamp ≤ `DS:09AE`; after either `DS:4466 = DS:09A8 + (DS:4468 >> 3)`; item 4: `DS:446A += DS:09B2`; item 6: `−= DS:09B2` (switch `0ddd:027e`); `vw_camera(0, 0)`; pages front→work; `vw_render(28)`; `draw_bottom_bar()` at item 1's y; `page_flip(1)`; `menu_poll()`. After release: restore `view.+0C`; pages spare→work; `copy_rect(25, 140, 50, 40)`; `2316 = 2312`; item 0 mask := 3 |
| `0ddd:0286` | `vw_draw_text` | `draw_inset_box(); rect_shrink(3)`; FONT3; `2300 = CCh`; `flow_setup(0, 6, 1)`; `flow_text(DS:445C, 1, 0)` |
| `0ddd:02d4` | `vw_btn_cb` | `if btn_cb()`: PREVIOUS → `DS:446E−−`, NEXT → `DS:446E++` (item 0 mask := 3), result 1; CONTINUE → result 2 |
| `0ddd:0323` | `vw_select(force)` | if `DS:446E != DS:446F`: step in the direction of the change until a valid type or back at `DS:446F`: forward `i = i % n`, backward `i = (i + n) % n`, then while invalid: `i = (i + 1) % n` / `i = i ? i − 1 : n − 1`. Valid = aircraft: `2777:0077(i) && 2777:012f(i, DS:446D) && vw_viewable(i)`; ship: `shiptxt_is_nation(i, DS:446C)`. If the type changed or `force`: `DS:446F = i`; `view3d_unload_model(); view3d_load_model(i, vw_variant(i))`; name → `DS:4460` (`2777:00a1(i)` / `shiptxt_name(i)`), uppercased; text = `pltxt_text(i)` / `shiptxt_text(i)` |
| `0ddd:04de` | `vw_save_strips()` | `copy_rect(0, 0, 320, 28)`; `copy_rect(0, y1, 320, 200 − y1)` (y1 = item 1's y) |
| `0ddd:051e` | `vw_set_center(y0)` | 3Space projection centre (`3d50:3E91/3E93`) = (view.+0A + view.+0E/2, view.+0C − y0 + view.+10/2) |
| `0ddd:0552` | `vw_draw_sky(y0)` | quad xs = (0, 319, 319, 0), ys = (85, 85, 83, 83); y0 = max(arg, 14); colour c = 7Fh; for i < 15 while ys[0] > y0: `fill_poly(4, xs, ys)` colour c; ys[0] = ys[1] = ys[2]; ys[3] −= 2 (≥ y0); ys[2] = ys[3]; c−−; a last band down to y0 if needed; then the ground quad ys = (85, 85, y1−1, y1−1) in `DS:09A0` |
| `0ddd:064b` | `vw_camera(recompute, full)` | recompute: d = `view3d_distance()`; aircraft: `09AC = max(DS:4464, d)`, `09AE = min(d·3, 850)` (`(d·C00h) >> 10`, long); ships: `09AC = d`, `09AE = d·3`; `09AC = min(09AC, 09AE)`; `DS:4468 = 09AC`; `09B0 = (d·50) >> 10`; `09A6 = vw_pitch(t)` → model.+0E; `DS:4466 = 09A8 + (DS:4468 >> 3)`. Always: camera.+0A (long) = `DS:4466`; camera position = `2b1f:0121(model pos, DS:446A, (long)DS:4468)`; full: camera.+0E = `2b1f:0069(camera, model)` (pitch towards the model); camera.+12 = `2b1f:00b4(camera, model)` (heading); full: `view3d_sort_scene()` |
| `0ddd:07c1` | `vw_render(y0)` | `3d50:237b(view)`; view.+0C = y0; `vw_set_center(y0)`; clip (0, y0)–(319, y1−1), off while `vw_draw_sky(y0)`, on for `view3d_draw_scene()` (`3d50:3DF8 = 1`), off after |
| `0ddd:0824` / `0884` | `vw_pitch_load()` / `vw_pitch_free()` | aircraft only: `DS:4456 = table_load("pitch_", "dat", 6, 0Fh, 9, 1, …)` (fatal 2D5h) / `table_free` |
| `0ddd:089a` | `vw_names_aircraft(t)` | t == −1 → `2777:0000` (aircraft data); `pltxt_open()`; `DS:445A = 2777:0097()`; `DS:4458 = namelist_load("pfname", DS:43B4, 159, 15)`; `vw_pitch_load()` |
| `0ddd:08d7` | `vw_names_ships()` | `shiptxt_open()`; `DS:445A = shiptxt_count()`; `DS:4458 = namelist_load("sfname", DS:43B4, 115, 10)` |
| `0ddd:0905` | `vw_links(browse)` | item 5 link 3 = browse ? 8 : 10; item 10 links 0, 2 = browse ? 9 : 5 |
| `0ddd:094c` | `vw_nav(t)` | t ≥ 0 (one type): item 10 x = 123, items 8, 9 hidden (mask/flags 0), `DS:446F = DS:446E = t`, `vw_links(0)`; else item 10 x = 223, items 8, 9 = 74h/82h, `DS:446E = 0`, `DS:446F = FFh`, `vw_links(1)` |
| `0ddd:09cf` | `vw_limits(navy, side)` | aircraft: `09AE = 850`; land service: `09AC = DS:4464 = 350`, `09A2 = 0`, `09A4 = 4000h`, `09A8 = 2`, `09AA = 0`; navy (service 0 or 3): `09AC = DS:4464 = 375`, `09A2 = 09A8 = side == 1 ? 337 : 499` (deck height), `09A4 = 8000h`, `09AA = 4000h`. Ships: `09A2 = 0, 09A4 = 4000h, 09A8 = 0, 09AA = 0, 09AC = 4000, 09AE = 8000` |
| `0ddd:0a6c` | `vw_open(t, aircraft)` | `DS:4470 = aircraft`; aircraft: `vw_names_aircraft(t)`, `vw_nav(t)`, `09A0 = navy ? 84h : 6Bh`, `DS:4462 = t ≥ 0 ? DS:477F : 0`; ships: `vw_names_ships()`, `DS:446E = 0`, `DS:446F = FFh`, `09A0 = 84h`, `DS:4462 = 0`; `vw_limits(navy, DS:446C)`; `DS:4468 = 09AC`; `DS:446A = 09AA`; `48ea:0009(2, 1)`; `3d50:2482(4000h, 4000h)`; `view3d_init(DS:446C, aircraft)`; model.+12 = `09A4`, model.+0A = (long)`09A2`; rect := item 0, `5FD4 = y1 − 3`; `view3d_set_window()`; `vw_select(1)`; `view3d_load_scene(aircraft ? (navy ? 1 : 0) : 2)` (carrier / airfield / sea) |
| `0ddd:0b99` | `vw_close(t)` | aircraft: t == −1 → `2777:04df`; `pltxt_close()`; ships: `shiptxt_close()`; `namelist_free(DS:4458)`; `view3d_done(); view3d_unload_model(); 48ea:0133()`; aircraft → `view3d_unload_scene()`; `vw_pitch_free()` |
| `0ddd:0be5` | `vw_frame` | dispatch + present (Esc = result 2 ends the viewer) |
| `0ddd:0c06` | `vw_run(message)` | `first = 1`; until `menu_run` returns 2: `vw_select(0)`; `vw_camera(first, 1)`; `first = 0`; item 0 mask := 3; `hs_draw_all(); hs_push()`; if `message`: `copy_work_to_spare()`, `tbox_titled3(strtab_get(1, 0))` (VIEW.SCD 3 "NEW AIRPLANE" + `MISC.DAT` row 1 text), `copy_spare_to_work(); copy_work_to_front()`; `hs_pop()`; `menu_run(vw_frame); ui_busy()` (the message is shown again after every PREVIOUS/NEXT: harmless, `message` is only set for single-type calls) |
| `0ddd:0c95` | `vw_screen(browse)` | `screen_open(25, screen_clear_black, 30h, 1)`; `hs_set_table(4b1e:000d, 11)`; focus browse ? 9 : 10 |
| `0ddd:0cde` | `view_vehicle(t, service, message)` | `DS:4460` = stack buffer; `DS:446D = service`; `DS:446C = side(service)`; `vw_open(t, 1)`; `vw_screen(t == −1)`; `vw_run(message)`; `vw_close(t)`. Callers: main menu (−1, service, 0), flight deck (`DS:478A`, `DS:4776`, 0), career new-aircraft event `0874:0cd6` (…, 1) |
| `0ddd:0d2f` | `view_ship(nation)` | `DS:446C = DS:4775 = nation` (**overwrites the career side group**: harmless outside a career, L); `DS:446D = nation == 1 ? 0 : 3`; `vw_open(0, 0)`; `vw_screen(1)`; `vw_run(0)`; `vw_close(0)` |

## 3. Calibration device chooser (`0eb4`, table `4b2e:0000`, 8 items) — V

From the preferences screen (CALIBRATE, `0b48:0c22`) with `CALBRATE.DAT` loaded as the string
table (row 0: 0 "JOYSTICK 1", 1 "THRUSTMASTER FCS", 2 "THRUSTMASTER HAT", 3 "YOKE", 4 "RUDDER
PEDALS", 5 "SLIDER", 6 "JOYSTICK 2"). Items: 0 (84,55,151,94) side-riveted panel; 1 (25,10) title
`0eb4:000c` (FONT4 `text_engrave(label, C1h, B1h, C0h, x, y)`; labels are strings 0–2 of the
current string table); 2 list; 3 bevel; 4, 5 arrows; 6, 7 (16/84, 70, 55,13) `cal_btn_cb` `004a`
(`DS:4477 = (5FDE == 7)`, result 1).

| Address | Name | Behaviour |
|---|---|---|
| `0eb4:0076` | `cal_draw_row(i, y)` | `draw_text(strtab_get(0, DS:4473[i]), x+5, y)` |
| `0eb4:00b9` | `cal_build()` → u8 | `DS:4473..4476 = FFh`, n = `DS:4472` = 0; control device `DS:43BA`: 1 → {0}; 3 → {1, 2}; 2 → {3}; rudder `DS:43BB`: 1 → 6, 2 → 4; throttle `DS:43BC`: 1 → 6 unless the rudder already added it, 2 → 5; n == 0 → 0; n ≥ 2: `req_open(61, 70)`, `lbox_setup(…, n, 5, cal_draw_row)`, `lbox_bind(4b2e:0000, 2, 4)`, `DS:4477 = 0`; returns 1 |
| `0eb4:01e4` | `cal_frame` | dispatch + present |
| `0eb4:0205` | `cal_choose()` → device + 1 / 0 | `cal_build()` == 0 → 0; n == 1 → `DS:4473[0] + 1`; else `dlg_run(4b2e:0000, 8, cal_frame)`; not ACCEPTed → 0; else `DS:4473[lbox_selected()] + 1` |

## 4. New pilot (`0ed9`, screen 28 `START0`/`SIGNIN`, table `4b39:0000`, 9 items)

"START A CAREER": a sentence from `STRINGS_.DAT` row 0 entry 11 "In %a, %b with the rank of %c,
enlisted in the %d." with inline buttons: `%a` enlistment date, `%b` pilot name, `%c` rank, `%d`
service; CANCEL / START. Uses `SFTBTNS<cset>.DAT` row 0 as the string table during the screen.

Items: 0 (0,121,320,79) `nw_draw_panel` `0008` (`tile_fill_rect; draw_frame`); 1 (1,−131,312,40)
`nw_draw_title` `0017`; 2 (1,2,312,42) `nw_draw_text` `0272`; 3–6 inline buttons `nw_slot_cb`
`023f` (kind = item index); 7 (48,54,71,18) str 0 "CANCEL", 8 (202,54,71,18) str 2 "START"
(`nw_btn_cb` `0040`).

State: `DS:4478[33·3]` = `DATE<cset>.DAT` (3 enlistment dates × 11 services, 3 bytes each),
`DS:45B6` date choice, `DS:45AF` first rank of the service, `DS:45B1` rank choice, `DS:45B0`
pressed button, `DS:44DB[53]` far copies of `STRINGS_.DAT` row 0, `DS:45B2` string list (the
sentence in a 300-byte stack buffer, 0).

| Address | Name | Behaviour |
|---|---|---|
| `0ed9:0017` | `nw_draw_title` | `draw_title_bar_for(DS:4776, DS:477B, str_get(3) "START A CAREER")`; mask 40h |
| `0ed9:0040` | `nw_btn_cb` | `if btn_cb()`: `DS:45B0 = 5FDE`; result `5FDE == 8 ? 1 : 2` |
| `0ed9:006a` | `nw_on_ok(sel)` | item 3: `DS:45B6 = sel`, `DS:477B = date_to_days(DS:4478 + 9·DS:4776 + 3·sel)` (`284f:0007`); item 5: `DS:4777 = DS:45AF + sel`, `DS:45B1 = sel`, `DS:47BD = rank_points(DS:4777)`; item 6: `DS:4776 = sel`, `DS:4775 = side(sel)`, `DS:45B6 = 0`; masks of items 1, 2 := 3 (for item 6 only those; not reached: the service button does not use a chooser) |
| `0ed9:010b` | `nw_edit()` | switch on `5FDE` (table `0ed9:0197`): 3 → item.user = 3, `choose_run(nw_on_ok, DS:45B6, 100 + 3·DS:4776)` ("February of 1942"…); 4 → `text_entry(0, DS:4754, 15, 1)`; 5 → item.user = `DS:1DB4[DS:4776]` (ranks per service: 3, 3, 3, 4, 5, 0…), `choose_run(nw_on_ok, DS:45B1, 51 + DS:45AF)`; 6 → `DS:45B0 = 6`, `menu_set_result(1)` |
| `0ed9:019f` | `nw_slot_label(kind, item far *it)` → 0 | 3 → row0[100 + 3·service + `DS:45B6`] copied to `DS:411A`; 4 → `DS:4754` (the name itself); 5 → row0[`DS:4777` + 51]; 6 → row0[`DS:4776` + 133] |
| `0ed9:0223` | `nw_subst(c, it)` | `nw_slot_label(c − 5Eh, it)` (`%a` → item 3 …) |
| `0ed9:023f` | `nw_slot_cb` | refresh the label; mask 74h; `if choose_entry_cb()`: `nw_edit(); hs_restart()` |
| `0ed9:0272` | `nw_draw_text` | `tile_fill_rect()`; FONT3, `2302 = 1`; `flow_text_buttons(4b39:0000, 3, nw_subst, DS:45B2, x+20, y+8, x+w−20)`; `draw_bottom_bar()`; mask 40h |
| `0ed9:02d2` | `nw_frame` | `rng_next()` (`24b7:000c`: the RNG is stirred every frame while the player types); dispatch + present; Esc → `DS:45B0 = 7` |
| `0ed9:0307` | `pilot_add()` | `DS:47CB` = Σ of the roster pilots' list lengths (+79h) (the new pilot's event list starts at the end of the blob); `DS:47CD = 0`; `DS:4A18++`; `pilot_store()` |
| `0ed9:0347` | `pilot_new()` → u8 | below |
| `0ed9:05b3` | `nw_init()` | `hs_default_links(4b39:0000, 9)` |

```
pilot_new():                                        // CAREER MENU → START A CAREER (0607)
  first = 1; loaded = 0
  if DS:4A18 > 12: roster_manage(0) (13be:07c3: the roster is full, delete one)
  if DS:4A18 >= 13: return 0
  memset(DS:4754, 0, 122); DS:4774 = DS:4A18
  DS:4776 = fly_for_choose(0); if -1: return 0
  cset_scan(DS:4776, 0, FFh) (0a41:028d); DS:4779 = cset_choose(1) (0a41:01c1); if -1: return 0
  file_read_n(DS:4478, 3, 33, res_name("date", DS:4779, "dat"))
  strtab_load("strings_.dat"); strings_dup_far(DS:44DB, 53, 0); copy row0[11] into buf; DS:45B2 = {buf, 0}; strtab_free()
  DS:45B6 = 0; DS:45B1 = 0; ranks_load(); DS:478E = FFFFh; prf_read16("creal.prf", DS:47A9)   // career realism defaults
  loop:
    DS:4775 = side(DS:4776); DS:477B = date_to_days(DS:4478 + 9·DS:4776 + 3·DS:45B6)
    DS:45AF = DS:4777 = rank_first(DS:4776); DS:47BD = rank_points(DS:4777)
    if !loaded: strtab_load(res_name("sftbtns", DS:4779, "dat")); loaded = 1
    screen_show(28, 43h, 1); hs_set_table(4b39:0000, 9); hs_focus(8); hs_draw_all()
    if first: text_entry(0, DS:4754, 15, 1); first = 0          // name typed straight away
    r = menu_run(nw_frame); ui_busy()
    if DS:45B0 == 8 (START): strtab_free(); loaded = 0
                             if campsel_run(1) (0fa1:02f9): pilot_add(); break     // else back into the loop
    else if DS:45B0 == 7 (CANCEL/Esc): break
    else if DS:45B0 == 6: s = fly_for_choose(1); if s != -1: DS:4776 = s     // new service resets date/rank
  if loaded: strtab_free(); ranks_free(); return r == 1
```

(The rank and the date are recomputed from their defaults at the top of every loop pass: after
START is cancelled in the campaign screen, a changed rank or date reverts to the first one. L —
matches the code.)

## 5. Pilot roster records (`pilot.c`, `0f67`)

| Address | Name | Behaviour |
|---|---|---|
| `0f67:0001` | `pilot_store()` | roster[`DS:4774`] = `DS:4754` (122 bytes) |
| `0f67:0024` | `pilot_delete(i)` | `off = roster[i].+77h`, `len = roster[i].+79h`; for j = i+1 … n−1: `acc += roster[j].+79h`; `roster[j].+77h = roster[j−1].+77h`; `roster[j−1] = roster[j]`; `roster[j−1].+20h−−`; if len: `memmove(blob+off, blob+off+len, acc)`; `DS:4A18−−`. **Quirk:** from the second moved pilot on, `+77h` gets the value already overwritten in the previous step (= `off`), so after deleting a pilot followed by ≥ 2 others their event lists point at the wrong place (only affects which career event letters count as "already shown"); keep |
| `0f67:00f9` | `pilot_backup(char *name)` | BACKUP CAREER: if `DS:4A18 < 13`: `s = DS:47CB + Σ_{j = DS:4774}^{n−1} roster[j].+79h`; `s + DS:47CD > 512` → fatal 62h; `memmove(blob+s, blob+DS:47CB, DS:47CD)` (copy the list to the end); `old = DS:4774`; `DS:4774 = n`; `DS:47CB = s`; `strcpy(DS:4764, name)` (second text = backup label); `pilot_store()` (the copy); `DS:4754 = roster[old]` (back to the original); `DS:4A18++`; every roster[i].+20h must equal i (fatal 79h); `roster_write()` |
| `0f67:021a` | `pilot_event_seen(c)` → u8 | c occurs in `DS:47CE[DS:47CB .. DS:47CB + DS:47CD)` |
| `0f67:0252` | `pilot_event_add(c)` | for j = `DS:4774` … n−1: `acc += roster[j].+79h`, `roster[j].+77h += 1`; `DS:47CB + acc > 1FFh` → fatal 9Ah; `memmove(blob+DS:47CB+1, blob+DS:47CB, acc)`; `blob[DS:47CB] = c`; `DS:47CD++`; `pilot_store()` (restores the current pilot's own offset) |
| `0f67:02ed` | `service_side(s)` → s8 | table above |
| `0f67:033b` | `service_available(s)` | s is in `DS:49CE[11]` (s16 list of the services of the installed data sets, filled by shell_data) |
| `0f67:036b` | `nation_available(n)` | some `DS:49CE[i]` (until −1, i ≤ 10) has `service_side == n` |

## 6. Award ceremonies (`0f35`, screen 53 `PARTS`/`RESULTS`, table `4b46:0000`, 4 items)

`award_ceremony(side, kind, far text)` (`0f35:01d8`, from `note_show` `1656:0095`): kind 0
CAPTURED, 1 INJURED, 2 AWARDED A MEDAL, 3 PROMOTED (`RESULTS.SCD`). A panel with the career text
on the right and a TTM animation on the left (e.g. the medal pinned on).

`TTMS<n>.DAT` (all installed data sets, `open_module_files`): records of 69 bytes {u8 side, 4 ×
17-byte entries {char[9] TTM name, s16 last, s16 nrand, s16 span, s16 end_frame}} → `DS:45BC +
68·side + 17·kind` (`0f35:012d aw_load_ttms`, called by `dialogs_init`).

Items: 0 (9,28,302,143) `aw_draw_window` `000c` (`draw_titled_panel`; 17 rivets at x+3 and x+w−6,
y+20); 1 (11,22,280,111) popup box; 2 (15,26,163,104) inset box (the TTM area); 3 (181,26,106,104)
`aw_draw_text` `004e` (popup box; FONT3; `2302 = 1`; `rect_shrink(3)`; `flow_setup(3, 7, 1)`; `2316 =
2312`; `flow_text(DS:45B8, 1, display_subst 0cfe:0057)`; `rect_grow(3)`).

```
award_ceremony(side, kind, text):
  title[50] = copy of DS:0A18; e = DS:45BC + 68·side + 17·kind; DS:45B8 = text; item 0 label = title
  screen_show(53, 36h, 0); copy_front_to_work(); hs_set_table(4b46:0000, 4)
  title = kind == 2 ? strupr(medabbr_text(DS:0500)) : str_get(kind)
  aw_draw(1):  pages front→work; call the draw callback of items 0..3 directly (hs_load each)
               copy_work_to_spare(); 3a73:000d(5); 3a73:0085(item0 x, y, w, h + 5, 1, DS:2310, DS:2314, 0, 0, 0)   // TTM background region (video)
  menu_flush(); while menu_busy() ;
  ttm_play_file(res_name(e.name, -1, "ttm"), e.last, e.nrand, e.span, e.end_frame, ttm_skip_check 21f4:0018)
  while menu_busy() ;
  if kind == 2: ttm_play_file("awrdmed.ttm", -1, 0, 0, 25, ttm_skip_check)
```

(`0f35:00af aw_draw(tm)`: the four callbacks, then the spare copy and the TTM region when `tm`.)

## 7. Pilot roster screen (`13be`, screen 50 `PARTS`/`FULL`, table `4c18:0000`, 13 items)

Two uses: `roster_manage(keep)` (`07c3`) — "THE ROSTER IS FULL / SELECT A PILOT TO DELETE OR
CANCEL." with CANCEL / DELETE / VIEW; `roster_pick()` (`086e`) — "CONTINUE A CAREER... / SELECT AN
ACTIVE PILOT OR CANCEL." with CANCEL / DELETE / VIEW / ACCEPT. List rows: insignia, "<rank abbr>
<name>", date, status.

| # | Rect | Callback | Label (`FULL.SCD`) |
|---|---|---|---|
| 0 | 7,61,306,104 | `ro_draw_window` `0027` (`tile_fill_rect; draw_bevel_box`; 14 rivets at x+4 and x+w−6, y+4) | |
| 1 | 0,−30,302,26 | `ro_draw_title` `009b` | two lines `str_get(DS:4EEE[k])` |
| 2–4 | 37 / 135 / 200, 5 | `ro_draw_header` `011c` (FONT3 engraved `str_get(DS:0E57[user])`) | 8 "PILOT NAME", 9 "DATE", 10 "DESCRIPTION" |
| 5 | 10,12,255,83 | `lbox_draw` | |
| 6 | 271,11,25,85 | `ro_draw_scroll` `006e` (bevel box, C0h rect (x+4, y+25, 18, 35)) | |
| 7, 8 | 274,14 / 274,72, 20×20 | `lbox_arrow_cb` | |
| 9–12 | x set per mode, 112, 61,18 | `ro_btn_cb` `0009` (`DS:4EF0 = 5FDE`, result 1) | 4 "CANCEL", 6 "DELETE", 7 "VIEW", 5 "ACCEPT" |

| Address | Name | Behaviour |
|---|---|---|
| `13be:0161` | `ro_draw_row(i, y)` | `r = roster[i]`: insignia `DS:5FE4[r.+21h + 16]` at (x+5, y); `strtab_get(3, r.+23h)` (rank abbreviation, `STRINGS_.DAT` row 3) + " " + name at x+15; date text `284f:026b(r.+2Bh)` at x+120; status `r.+24h == 0` → the second text (+10h: backup label) at x+175, else `strtab_get(1, status)` ("Retired" / "Discharged" / "Deceased") at x+200 |
| `13be:02c5` | `ro_subst()` → char * | "<rank abbr> <name>" of the selected pilot in `DS:419A` (request-box substitution) |
| `13be:0339` | `ro_frame` | below |
| `13be:04e0` | `ro_draw_bg` | `screen_clear_panel()`; `draw_title_bar_for(sel.+22h service, sel.+2Bh date, str_get(11) "CAREER ROSTER")` |
| `13be:052a` | `roster_run(delete_once)` → u8 | below |
| `13be:075a` | `ro_links_manage()` | copies the link bytes of items 7, 8, 9, 11, 10 from the tables `DS:0E5D/0E65/0E6D/0E75/0E7D` (low bytes of 4 words each) |
| `13be:07c3` | `roster_manage(keep)` → u8 | `strtab_load("strings_.dat")`; `DS:4EF1 = keep ? DS:4774 : −1` (the current pilot); title ids `DS:4EEE = &{0, 1}`; x of items 9, 10, 11 = 16, 228, 122; item 12 hidden (mask/flags 0); `DS:4EF0 = 10`; `ro_links_manage()`; `r = roster_run(1)`; keep → `DS:4754 = roster[DS:4EF1]` (reload the current pilot, whose index may have moved); `strtab_free()`; returns r |
| `13be:086e` | `roster_pick()` → u8 | `squad_open()`; `strtab_load("strings_.dat")`; `DS:4EF1 = FFh`; titles `&{2, 3}`; x of items 9, 10, 11 = 7, 85, 162; item 12 = 74h/82h; `DS:4EF0 = 12`; `hs_default_links(4c18:0000, 13)`; `r = roster_run(0)`; `strtab_free(); squad_close()` |

```
roster_run(delete_once):
  open:   lbox_setup(…, DS:4A18, 15, ro_draw_row); lbox_bind(4c18:0000, 5, 7); screen_open(50, ro_draw_bg, 396h, 1)
  loop:   hs_set_table(4c18:0000, 13); hs_focus(DS:4EF0); hs_draw_all(); menu_run(ro_frame); ui_busy()
          switch DS:4EF0 (table 13be:0752):
          9  CANCEL: if DS:0E56: re-open (lbox + screen), DS:0E56 = 0, loop; else return 0
          10 DELETE: pilot_delete(sel); if DS:4EF1 != FFh && DS:4EF1 > sel: DS:4EF1--
                     if DS:4A18 == 0: return 0
                     lbox re-setup/bind; item 5 mask := 3; pages spare→work; copy_rect(item10.x, 173, item10.w, 27)
                     if delete_once: return 1
          11 VIEW:   DS:4754 = roster[sel]; if DS:4774 >= 0: strtab_free(); pilot_record() (135d:04ec); strtab_load("strings_.dat"); re-open
          12 ACCEPT: module_set_active(DS:4779) (2008:0003); pilot_store(); return 1

ro_frame():
  dispatch + present
  if result 1: switch DS:4EF0 (table 13be:04d8):
     10 DELETE: sel == DS:4EF1 (the pilot in use) → req_ok(ro_subst, 14, -1); result 0
                else if !req_yes_no(ro_subst, 15, 3, 4): result 0                       // "delete <pilot>?"
     12 ACCEPT: DS:4754 = roster[sel]
                status DS:4778 == 1 (retired): if cset_scan(DS:4776, DS:477F, FFh) (another campaign set is open):
                                                  if req_yes_no_wide(ro_subst, 11, 0, 1):
                                                     c = cset_choose(0); c != FFh → DS:4778 = 0, DS:4779 = c, DS:4790 = FFFFh, best_career_remove() (09a9:088e)
                                                     else DS:0E56 = 1                    // (the accept still goes through)
                                                  else result 0
                                               else req_ok(ro_subst, 12, 8); result 0
                status 2, 3 (discharged / deceased): req_ok(ro_subst, 13, 8); result 0
  if result 2 (Esc): DS:4EF0 = 9
```

(Request strings 11–15 are those of the request screen table, `REQUEST.SCD`: toolkit §6.5.)

## 8. Campaign selection (`campsel.c`, `0fa1`, screen 15 `CAMPSEL` / 16 `CAMPSELJ`, table `4bb0:0010`, 9 items)

`campsel_run(new_career)` → u8: choose the campaign (of the chosen campaign set) to join, then the
squadron (`squadinf(0)`); `campsel_show_text(text)`: the same screen as "CAMPAIGN REVIEW" with a
text and CONTINUE (end of a campaign). Background 15 for side ≠ 0 (US), 16 (`CAMPSELJ`) for Japan.

| # | Rect | Callback | Label (`CAMPSEL.SCD`) |
|---|---|---|---|
| 0 | 0,166,320,34 | `cs_draw_prompt` `0002` (popup box; FONT3; centred engraved label if any) | 0 "SELECT THE CAMPAIGN YOU WANT TO JOIN OR CANCEL..." / 1 "CAMPAIGN REVIEW" |
| 1–4 | 10/87/164/241, 16, 70,13 (relative to item 0) | `cs_btn_cb` `0039` | 2 "PREVIOUS", 3 "NEXT", 4 "CANCEL" (7 "QUIT FOR NOW" when called with 0, 6 "CONTINUE" in review), 5 "SELECT" |
| 5 / 7 | 64,−97,201,25 / 54,−109,191,25 | `cs_draw_header` `005b` | |
| 6 / 8 | 69,−68,192,86 / 56,−79,191,96 | `cs_draw_text` `0112` | |

Items 5, 6 are the US layout, 7, 8 the Japanese one (`cs_side_items` `0147`: side 0 → 5, 6 hidden,
7, 8 shown; else the reverse; `hs_default_links(4bb0:0010, 9)`). State: `DS:0A66` list of campaign
indices (count `DS:0A64` allocated, `DS:4A26` used), cursor = item 0's user word (`4bb0:0020`),
`DS:4A24` campaign shown, `DS:4A22` its start (or end) date, `DS:4A1E:4A20` far text, fonts
`DS:4A1A` `SIMQ_HDL`, `DS:4A1C` `SIMQ_SML`.

| Address | Name | Behaviour |
|---|---|---|
| `0fa1:005b` | `cs_draw_header` | name `287b:026e(DS:4A24)`; date text `284f:026b(DS:4A22)`; colours C3h; `SIMQ_HDL`: name centred at y+4, underline (x, y+14)–(x+width, y+14); `SIMQ_SML`: date centred at y+17 |
| `0fa1:0112` | `cs_draw_text` | `2300 = C3h`; `flow_setup(0, 8, 1)`; `flow_text(DS:4A1E, 1, 0)` |
| `0fa1:0192` | `cs_cmp(a, b)` | `287b:0389(*a) − 287b:0389(*b)` (by start date, for `qsort`) |
| `0fa1:01c8` | `cs_build_list()` | `DS:0A64 = 287b:0256()`; `DS:0A66 = xmalloc`; for k from `287b:053f()` (first campaign of the set) over `DS:0A64`: `287b:051f(k) && 287b:0389(k) >= DS:477B && 287b:0325(k, DS:4776)` → append; `DS:4A26 = n` (fatal 10Eh if 0); n > 1 → `qsort(list, n, 1, cs_cmp)`; the rest FFh |
| `0fa1:02c8` | `cs_frame` | dispatch + present; Esc → `DS:5FD2 = 3` |
| `0fa1:02f9` | `campsel_run(new_career)` → u8 | below |
| `0fa1:055a` / `05ad` | `cs_review_layout()` / `cs_normal_layout()` | review: items 1, 2, 4 hidden, item 0 label 1, item 3 label 6 at x 125; normal: 74h/82h, labels 0 / 4, x 164 |
| `0fa1:0600` | `campsel_show_text(far text)` | `DS:4A24 = DS:4790`; review layout; side items; fonts; `screen_show(side ? 15 : 16, 88h, 1)`; table; `DS:4A22 = 287b:03e1(DS:4790)` (end date); text; `hs_draw_all(); menu_run(cs_frame); ui_busy()`; normal layout; **`xfree(DS:0A66)`** (frees the list pointer left from the last `campsel_run`, which already freed it: a double free in the original — PORT: skip); fonts freed |

```
campsel_run(new_career):                            // callers: pilot_new (1), career menu 0607:011d, career_next_campaign 0874:11ff (0)
  loop = 1; first = 1; if !new_career: item 3 label = 7 "QUIT FOR NOW"
  287b:0104(DS:4779); 287b:056a(); cs_build_list(); DS:4A24 = list[0]; cursor = 0
  cs_side_items(); fonts
  while loop:
    DS:4A22 = 287b:0389(list[cursor]) (start date); DS:4A1E = 287b:05ec(list[cursor]) (campaign text)
    screen_show(DS:4775 ? 15 : 16, 88h, 1); hs_set_table(4bb0:0010, 9)
    hs_focus(first ? 4 : DS:5FD2); first = 0; hs_draw_all(); menu_run(cs_frame); ui_busy()
    switch DS:5FD2:
      1 PREVIOUS: cursor = cursor ? cursor - 1 : n - 1; DS:4A24 = list[cursor]
      2 NEXT:     cursor = (cursor + 1) % n;             DS:4A24 = list[cursor]
      3 CANCEL:   result = 0; loop = 0
      4 SELECT:   DS:4790 = list[cursor]; squad_open(); 2777:0000; ace_open(); 2a85:0006
                  result = squadinf(0); 2a85:0216; ace_close(); 2777:04df; squad_close()
                  loop = !result; first = 1                 // squadron choice cancelled → back to the campaigns
  287b:0556(); 287b:0686(); xfree(DS:0A66); fonts freed; item 3 label = 4
  if result: pilot_store(); return result
```

## 9. Pilot record (`135d`, screen 12 `PRECORD`, table `4bf2:0000`, 27 items)

"PILOT RECORD": name plate with rank, insignia of the service twice, score / missions / date /
service / squadron / campaigns completed / successful missions / air victories / successful strikes
/ ships sunk, and the medals awarded, CONTINUE.

Labels (items 1, 3, 5, … 19, 22: `pr_draw_label` `012c`, FONT3 engraved C7h/B1h/C0h at (x, y+1)):
`PRECORD.SCD` 0–10 ("SCORE:", "MISSIONS FLOWN:", "DATE:", "SERVICE:", "SQUADRON:", "CAMPAIGNS
COMPLETED:", "SUCCESSFUL MISSIONS:", "AIR VICTORIES:", "SUCCESSFUL STRIKES:", "SHIPS SUNK:",
"MEDALS AWARDED"). Values (items 2, 4, … 20: `pr_draw_value` `01bb`, switch `135d:02e9`), always
uppercased into `DS:419A`, drawn by `pr_draw_field` `0170` (`draw_inset_box2`; FONT3 CCh text at
(x+5, y+3)):

| Item (rect) | Value |
|---|---|
| 2 (57,4,37,10) | `ltoa(DS:47B9)` score |
| 4 (173,4,21,10) | `min(DS:4784, 999)` missions flown |
| 6 (231,4,69,10) | date text `284f:026b(DS:477F)` |
| 8 (57,17,204,10) | service name `DS:4D54 + 30·DS:4776` |
| 10 (57,30,204,10) | `squad_name(DS:478E)` |
| 12 (114,43,21,10) | `min(DS:4788, 999)` campaigns completed |
| 14 (240,43,21,10) | `min(DS:4786, 999)` successful missions |
| 16 (78,56,21,10) | `min(DS:47BF, 999)` air victories |
| 18 (199,56,21,10) | `min(DS:47C1 + DS:47C3, 999)` successful strikes (ships + ground targets) |
| 20 (279,57,21,10) | `itoa(DS:47C1)` ships sunk (no cap) |

| Address | Name | Behaviour |
|---|---|---|
| `135d:0009` | `pr_btn_cb` | item 23 (106,132,107,18) str 12 "CONTINUE": `if btn_cb()`: result 1 |
| `135d:0021` | `pr_draw_insignia` | items 24, 25 (9 / 257, −47, 45,37): `tile_fill_rect(); draw_header_panel()`; `INSIGNIA.BMP[DS:4776]` centred (+3 x) |
| `135d:0093` | `pr_draw_nameplate` | item 26 (56,−19,199,18): `sprintf(DS:419A, "%Fs %s", rank title far DS:57A2[DS:4777], DS:4754)`, uppercased → label; `draw_header_panel()`; symbols `DS:5FE4[side + 8]` at (x+9, y+1) and (x+w−22, y+1) |
| `135d:030f` | `pr_draw_medals` | item 21 (10,71,292,56): `draw_popup_box()`; rules C7h (35,123)–(117,123), (52,125)–(117,125), (196,123)–(281,123), (196,125)–(264,125) and B1h one row lower; 1-rivet groups in the four corners; x = item x + 8; for m < 20: if `DS:4795[m]`: `draw_bitmap(MEDALS[m], x, MEDLOCS[m].y)`, `x += MEDLOCS[m].w + 2` |
| `135d:04a6` | `pr_draw_bg` | `screen_clear_panel()`; `draw_title_bar_for(DS:62C5, DS:6277, str_get(13) "PILOT RECORD")` (sic: the mission header's service and date, not the pilot's) |
| `135d:04cb` | `pr_frame` | dispatch + present |
| `135d:04ec` | `pilot_record()` | `DS:4D52 = bmp_load_planes("medals.bmp")`; `DS:4D50 = bmp_load_planes("insignia.bmp")`; `file_read_n(DS:4E9E, 4, 20, "medlocs.dat")` (20 × {s16 y, s16 w}); `strtab_load(SFTBTNS0.DAT)`: the 11 service names row0[133 + k] → `DS:4D54 + 30k`; `strtab_free()`; `screen_open(12, pr_draw_bg, DAh, 1)`; `hs_set_table(4bf2:0000, 27)`; `hs_draw_all(); menu_run(pr_frame); ui_busy()`; free both bitmaps. Callers: flight deck, roster VIEW, best-careers screen |
| `135d:0600` | `pr_init()` | `hs_default_links(4bf2:0000, 27)` |
