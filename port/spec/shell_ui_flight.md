# shell_ui part — flight map, flight deck, squadron info, big map, single-mission set-up

Target `Game/PS.EXE` (DGROUP `4D08`). Segments `06c7` fltmap.c, `0787` fltdeck.c, `07ba` squadinf.c,
`0d16` bigmap.c, `100e` flymiss2.c. Toolkit names: `shell_ui_toolkit.md`; career globals
(`DS:4754..47CD` = current pilot record) `shell_data.md` §4. Confidence **V** (read in the
disassembly) / **L** / **G**. Far data tables: segment as stored in the file (the Ghidra decompile
shows them +1000h, e.g. `59db` = `49db`).

World units in the shell: 1 unit = 1/4 foot (altitude/4 = feet; 21128 units = 1 "mile" of 5282 ft).

## 1. Flight map (`fltmap.c`, `06c7`, screen 27 `FLTMAP`, table `49db:000f`, 5 items) — V

Shows the mission area picture `W<area>.BMP`, the flights / convoys / places (icons from
`FLTMAP.BMP`), and on FLIGHT PLAN animates the route waypoint by waypoint with a popup per
waypoint. Data comes from `fmap_prepare` (`12c4:0377`, `shell_ui_mission.md` §5): flights =
16-byte records {u8 class, u8 heading, long x, long z, long alt, u16 id}, waypoints = 16-byte
records {long x, long z, long alt, far char *text}.

| # | Rect | Callback | Mask/fl | Label (`FLTMAP.SCD`) |
|---|---|---|---|---|
| 0 | 0,0,320,200 | — | 00 | |
| 1 | 0,177,320,23 | `draw_popup_box` | 40 | |
| 2 | 8,183,172,10 | `fm_draw_area_name` `00c5` | 40 | |
| 3 | 188,182,75,13 | `fm_btn_cb` `00fd` | 74 / 82 | str 0 "FLIGHT PLAN" (links 4) |
| 4 | 270,182,41,13 | `fm_btn_cb` | 74 / 82 | str 1 "EXIT" (links 3) |

Other strings: 2 "Altitude", 3 "Distance", 4 "Bearing" (pointers `DS:4277`, `DS:427B`, `DS:4279`).
State: `DS:4272` FLTMAP.BMP handle (frame table: word pointers from offset 0), `DS:4274` u8 area
(world) number, `DS:4275` near pointer to the area name, `DS:4270` waypoint array, `DS:05B6` u8
"route is drawn" toggle, `DS:05B7` u8 abort (Esc) flag, `DS:05B8:05BA` far save buffer of the popup,
`DS:05BC` its size (u16).

| Address | Name | Behaviour |
|---|---|---|
| `06c7:0000` | `fm_poll_skip()` → u8 | `k = kbd_getkey()`; `DS:6017 = k & FFh`, `DS:6016 = k >> 8` (scan); `if menu_hotkey(scan)` → returns an **uninitialised** local (PORT: return 0); else `skip = scan ∈ {1Ch, 01h, 39h}`; scan 01h (Esc) also sets `DS:05B7 = 1`; if joystick enabled (`DS:43B6`): `skip \|= joy_button(0) \|\| joy_button(1)`; if mouse enabled (`DS:43B7`): `skip \|= mouse_button(0) \|\| mouse_button(1)`; returns skip |
| `06c7:00c5` | `fm_draw_area_name` | `draw_inset_box2()`; FONT3 (`DS:421E`); `2302 = 1`; `2300 = CCh`; `draw_text(DS:4275, x+3, y+3)` |
| `06c7:00fd` | `fm_btn_cb` | `if btn_small_cb(0)`: `menu_set_result(5FDE == 3 ? 1 : 2)` |
| `06c7:0125` | `fm_bearing(wp *a, wp *b)` → deg | `ang = 3d50:225a(b.x − a.x, b.z − a.z)` (32-bit differences; `3d50:225a` = atan2 returning a 16-bit binary angle, 4000h = +z axis — shell_data math); `t = 1 − ((long)(s16)ang − 4000h)` (32-bit); returns `(u16)((t · 360) >> 16) % 360` (LXMUL, then the high word as an unsigned long, LUMOD) |
| `06c7:019e` | `fm_miles(wp *a, wp *b)` → int | `3d50:01e6(a, b)` (32-bit distance between the two points, shell_data math) `/ 21128` (LUDIV, unsigned) |
| `06c7:01d2` | `fm_feet(long alt)` → long | `alt / 4` (signed LDIV) |
| `06c7:01eb` | `fm_to_screen(int *sx, int *sy, long x, long z)` | `sx = (s16)((x · 147) / 25344000) + 26 + 73`; `sy = −(s16)((z · 147) / 25344000) + 16 + 73` (LXMUL + signed LDIV each; 25344000 = 182B800h; the map picture is drawn at (26,16), its centre at +73) |
| `06c7:0251` | `fm_heading_frame(u8 heading)` → 0..7 | `(u8)(heading + 16) >> 5` |
| `06c7:026b` | `fm_frame` | `hs_dispatch(601A, 6018, 2033, 0); hs_present()` |
| `06c7:028c` | `fm_draw_flight(rec *f)` | `fm_to_screen(&x, &y, f.x, f.z)`; class c = `(s8)f[0]`: 0 ≤ c ≤ 2: frame `c·8 + fm_heading_frame(f[1])`, offset (−4, −4); c ≥ 5: frame `c + 21`, offset (−4, −2); else (3, 4, negative): frame `c + 21`, offset (−8, −3); `draw_bitmap(FLTMAP[frame], x, y, 0)` |
| `06c7:033a` | `fm_draw_flights(rec *f, n)` | `DS:4272 = bmp_load_planes(res_name("fltmap", −1, "bmp"))`; `do { n--; fm_draw_flight(&f[n]); } while (n)` (last to first; n = 0 would loop 65536 times — never happens: the player's flight is always there) |
| `06c7:037b` | `fm_popup_measure(far text, int *h, has_nav, has_alt)` | `flow_setup(0, 7, 0)` (measure only); `5FD6 −= 10`; `h = text ? flow_text(text, 1, 0) : 0`; `if (!has_nav && !has_alt) h += 10; else { if (has_nav) h += 23; if (has_alt) h += 9; }`; `5FD6 += 10` |
| `06c7:03ec` | `fm_popup(far text, bearing, miles, long feet)` | below |
| `06c7:068f` | `fm_draw_leg(x0, y0, x1, y1)` | if the points differ: wait until `fm_poll_skip()` returns 0 (key release); DDA along the major axis (`dx = x1−x0`, `dy = y1−y0`; \|dx\| > \|dy\|: for i = 0 → dx step ±1: `y = y0 + dy·i/dx` (int division); else the same with x/y swapped); per pixel: `DS:2E3F = 15` (15 PIT ticks ≈ 63 ms); `put_pixel` colour A4h on the work page and on the front page (page pairs `22ce:0074`/`22ce:0085`); `skip = skip ? 1 : fm_poll_skip()`; if not skipped: busy-wait `DS:2E3F == 0`. After the line: wait for release again |
| `06c7:0854` | `fm_route(wp *w, n)` | `hs_push()`; FONT3; `fm_to_screen(&x0, &y0, w[0])`; `DS:05B7 = 0`; `fm_popup(w[0].text, 0, 0, 0)` (start point: text only); for i = 1; i < n && !`DS:05B7`: `fm_to_screen(&x1, &y1, w[i])`; `fm_draw_leg(x0, y0, x1, y1)`; if not aborted: `fm_popup(w[i].text, fm_bearing(&w[i−1], &w[i]), fm_miles(&w[i−1], &w[i]), fm_feet(w[i].alt))`; `x0, y0 = x1, y1`. Then frees the popup buffer (`DS:05BC = 0`); `hs_pop()`; aborted → `menu_set_result(2)` (Esc during the route leaves the map) |
| `06c7:099b` | `fm_clear_route()` | `copy_spare_to_work(); copy_work_to_front()` (the clean map was cached in the spare page) |
| `06c7:09aa` | `fm_draw_map(flights, n, area)` | pages front→work; `bmp = bmp_load_planes(res_name(sprintf("w%d", area), −1, "bmp"))`; `draw_bitmap(frame 0, 26, 16, 0)`; `bmp_free`; `fm_draw_flights(flights, n)` |
| `06c7:0a25` | `fm_area_name(char *buf)` | `DS:427B = str_get(3)`, `DS:4279 = str_get(4)`, `DS:4277 = str_get(2)`; `s = table_load("wldnms", "dat", 2, 3, 12h, 5, …)` (fatal 36Eh if 0); `rec = table_rec(s, DS:4274)` (fatal 371h if NULL); `DS:4275 = buf`; `fstrcpy_n(buf, table_text(s, DS:4274, *(u16 far*)rec))`; `table_free(s)` |
| `06c7:0b14` | `fltmap_show(rec *flights, n_flights, wp *wps, n_wps, area)` | below |

```
fm_popup(text, bearing, miles, feet):          // 06c7:03ec
  y_line = 5; 5FDA = 180; 5FD8 = 98; 5FD6 = 120
  fm_popup_measure(text, &5FD4, miles > 0, feet > 0)
  if 5FD8 + 5FD4 > 197: 5FD8 = 197 - 5FD4
  size = save_size(5FD6+1, 5FD4+1); grow the far buffer DS:05B8 if size > DS:05BC (farfree old, farmalloc)
  2316 = 2318 = 2312; save_rect(buf, 5FDA, 5FD8, 5FD6+1, 5FD4+1)
  draw_popup_box()
  if text: rect inset by 5 (x+5, y+5, w-10); 2300 = C5h; flow_setup(1, 7, 1); y_line = flow_text(text, 1, 0) + 5; rect restored
  if miles != 0:
     x = 5FDA + 5; y = 5FD8 + y_line
     if feet != 0: th = feet / 1000; th ? sprintf(t, "%d,", th) : t = ""
                   sprintf(s, "%s: %s%03d feet", "Altitude", t, feet % 1000)   // 500 → "Altitude: 500 feet", 50 → "050 feet"
                   text_engrave(s, C7h, B3h, C0h, x, y); y += 7
     sprintf(s, "%s: %03d`", "Bearing", bearing)     // '`' is the degree glyph of the font
     text_engrave(s, …, x, y)
     sprintf(s, "%s: %d mile%s", "Distance", miles, miles == 1 ? "" : "s"); text_engrave(s, …, x, y + 7)
  copy_work_to_front()
  DS:2E3F = 58Ch (1420 ticks = 6.0 s); while DS:2E3F && !fm_poll_skip() ;    // shown up to 6 s
  while fm_poll_skip() ;                                                        // wait for release
  pages front→work; restore_rect(buf, …); copy_work_to_front()
```

(The measure step always adds the nav block when `miles > 0`, but the drawing tests `miles != 0`;
the first point passes 0, 0.)

```
fltmap_show(flights, n_flights, wps, n_wps, area):   // 06c7:0b14
  first = 1; r = 0; DS:4274 = area; DS:4270 = wps
  screen_show(27, 39h, 1); fm_draw_map(flights, n_flights, area); fm_area_name(stack buf[51])
  hs_set_table(49db:000f, 5)
  while r != 2:
     hs_draw_all()
     if first: copy_work_to_spare(); first = 0          // cache the clean map
     r = menu_run(fm_frame)
     if r == 1 && !DS:05B6: cursor_hide()
     ui_busy()
     if r == 1:                                         // FLIGHT PLAN
        cursor_show()
        if n_wps < 2: DS:05B6 = 0
        DS:05B6 ? fm_clear_route() : fm_route(wps, n_wps)
        r = menu_get_result()                           // 2 if the route was aborted with Esc
        DS:05B6 = !DS:05B6                              // the button toggles route / clean map
  DS:05B6 = 0; bmp_free(DS:4272)
```

Callers: preflight (`1513:0e05`, FLIGHT MAP), briefing (`0c1d`), via `fmap_prepare`.

## 2. Flight deck (`fltdeck.c`, `0787`, screens 38–41 `FLTDK0`–`FLTDK3`, table `49e3:0010`, 8 items) — V

The career hub between missions. `FLTDECK<m>.DAT` (m = `module_active()` `2008:000e`, the data
set): u16 n (5), n × 6 bytes {s16 x, s16 y, u16 screen id} per service `DS:4776` → the panel
position and the background (shipped: (8,6,38), (12,10,39), (12,10,39), (165,4,40), (165,6,41));
loaded into `DS:427E` (fatal 54h no file, 56h service ≥ n) unless `DS:0614` (never set: reloaded
every time); item 0 x, y (`49e3:0010/0012`) := the record's x, y.

| # | Rect | Callback | Label (`FLTDECK.SCD`) |
|---|---|---|---|
| 0 | (x,y),151,168 | `fd_draw_window` `00e7` (mask 40, fl 80, user 5) | 0 "FLIGHT DECK" |
| 1–7 | 15, 22+20k, 123,18 (relative to item 0) | `fd_btn_cb` `0129` (74/82) | 1 "FLY NEXT MISSION", 2 "SQUADRON INFO", 3 "VIEW THE WAR MAP", 4 "VIEW PILOT RECORD", 5 "VIEW AIRCRAFT", 6 "BACKUP CAREER", 7 "RETURN TO MAIN" |

| Address | Name | Behaviour |
|---|---|---|
| `0787:0006` | `fd_load_layout()` | above |
| `0787:00e7` | `fd_draw_window` | `draw_titled_panel()`; `draw_rivets(x+3, y+18, 21)`; `draw_rivets(x+w−6, y+18, 21)` |
| `0787:0129` | `fd_btn_cb` | `if btn_cb()`: `snd_play(18h)`; `DS:42C0 = 5FDE`; `menu_set_result(1)` |
| `0787:0151` | `fd_frame` | dispatch + present; result 2 (Esc) → `DS:42C0 = 7` |
| `0787:0181` | `flight_deck()` | below |
| `0787:031b` | `fd_init()` | `hs_default_links(49e3:0010, 8)` — **not called** (no caller; `dialogs_init` does not list it: the table keeps its file links) |

```
flight_deck():                        // callers: sim_end 0542:01c4 (back from a career mission), career_menu 0607:011d
  redraw = 1; DS:4F22 = 1 (preflight first entry); DS:4356 = 1 (in a career)
  fd_load_layout(); DS:42C0 = 1
  loop:
    if redraw: screen_show(DS:427E[6·DS:4776 + 4], 8Dh, 1) else redraw = 1
    hs_set_table(49e3:0010, 8); hs_focus(DS:42C0); hs_draw_all(); menu_run(fd_frame); ui_busy()
    switch DS:42C0:
    1 FLY NEXT MISSION: rng_seed(DS:42C1) (24b7:0070); m = career_pick_mission() (3164:0944)
                        if DS:626B == 2: briefing((s8)m)                  // historic mission of the campaign
                        else: mission_build(m, DS:4776, 1) (3164:0a27); briefing(-1)
                        if DS:43D6 (BEGIN chosen in the preflight): return   // the caller flies
                        mission_free() (3164:0005)
    2 SQUADRON INFO:    squadinf(1)                       (07ba:08c2)
    3 VIEW THE WAR MAP: bigmap_show()                     (0d16:0b33)
    4 VIEW PILOT RECORD: pilot_record()                   (135d:04ec, shell_ui_career.md)
    5 VIEW AIRCRAFT:    view_vehicle(DS:478A, DS:4776, 0) (0ddd:0cde)
    6 BACKUP CAREER:    name[16] = ""; cursor_flush(601A, 6018); if text_entry(1, name, 15, 0) (2f7f:0143):
                           if roster_count DS:4A18 >= 13: if roster_full_replace(1) (13be:07c3): pilot_backup(name) (0f67:00f9)
                           else: redraw = 0; pilot_backup(name)
    7 RETURN TO MAIN / Esc: snd_play(3EAh) (title music); DS:4356 = 0; return
```

## 3. Squadron info / squadron choice (`squadinf.c`, `07ba`, screen 19 `SQD_A` / 20 `SQD_J`, table `49ef:0011`, 16 items) — V

`squadinf(mode)` → u8: mode 0 = **choose a squadron to join** (list of the service's squadrons
active in the campaign, PREVIOUS / NEXT / CANCEL / SELECT); mode 1 = show the player's squadron
(CONTINUE only); mode 2 = as 1 but first shows the "transfer" text box (string row 2, entry 0 of
`MISC.DAT`). Two copies of the info panel exist, one per side group `DS:4775` (0 → items 11–15
and screen 20 `SQD_J`; ≠ 0 → items 6–10 and screen 19 `SQD_A`).

| # | Rect | Callback | Mask/fl | Label (`SQUADINF.SCD`) |
|---|---|---|---|---|
| 0 | 0,167,320,33 | `si_draw_prompt` `0004` | 40 / 80 | 0 "SELECT THE SQUADRON YOU WANT TO JOIN OR CANCEL..." |
| 1–4 | 10/87/164/241, 16, 70,13 (relative to item 0) | `si_btn_cb` `0034` | 74 / 82 | 7 "PREVIOUS", 8 "NEXT", 9 "CANCEL", 10 "SELECT" |
| 5 | 125,16,70,13 | `si_btn_cb` | 74 / 82 | 11 "CONTINUE" |
| 6 / 11 | 14,−125,286,53 / 18,−121,278,53 | `si_draw_header` `0056` | 40 | |
| 7–9 / 12–14 | 32, −73/−63/−53 (−69/−59/−49), 249,10 | `si_draw_field` `0230` | 40 / 80 | 3 "Plane Type:", 4 "Station:", 5 "Pilot Quality:" |
| 10 / 15 | 32,−43 (−39),249,34 | `si_draw_aces` `02ad` | 40 / 80 | 6 "Aces in Squad:" |

(String 12 "TRANSFER" is unused.) Text buffers (on `squadinf`'s stack, pointers in DS):
`DS:42DC` squadron name, `DS:42DE` second name line, `DS:42E0` "A %s SQUADRON", `DS:42E2` "FOR
THE %s" (50 bytes each); `DS:42CE[3]` aircraft / station / pilot quality, `DS:42D4[4]` ace
names (40 bytes each). `DS:42C4` `FLAGS.BMP`, `DS:42C6` `SIMQ_HDL.FNT`, `DS:42C8` `SIMQ_SML.FNT`.
List: far array `DS:0624` of {u16 squadron, u16 date} (count `DS:0628` allocated = all
squadrons, `DS:062A` used), cursor `49ef:0021` (word inside the table segment), `DS:062C` u8
squadron currently loaded into the buffers (FFh = none), `DS:42CA`/`DS:42CC` campaign first/last
date (mode 0).

| Address | Name | Behaviour |
|---|---|---|
| `07ba:0004` | `si_draw_prompt` | `draw_popup_box()`; FONT3; `text_engrave_center(label, C1h, B1h, C0h)` |
| `07ba:0034` | `si_btn_cb` | `if btn_small_cb(0)`: `DS:5FD2 = 5FDE`; result 1 |
| `07ba:0056` | `si_draw_header` | `2300 = 18h`, `230E = C3h`; font `DS:42C6`: `DS:42DC` centred at y+4, `DS:42DE` centred at y+16; font `DS:42C8`: `DS:42E0` centred at y+32, `DS:42E2` centred at y+32+`gfx_font_width(FONT3)` (`16e3:36dc`; used as a line step, so probably the font height: video); `draw_line(x+6, y+27, x+6+L, y+27)` with L = `DS:4775 ? 271 : 263`; flag `FLAGS[DS:4775]` at (x+6, y+5) and at (x + (`DS:4775` ? 238 : 230), y+5) |
| `07ba:01b4` | `si_draw_cell` | colour C3h: rectangle outline (x, y, x+w, y+h) and a divider at x+72 |
| `07ba:0230` | `si_draw_field` | `si_draw_cell()`; font `DS:42C8`; label right-aligned at x+69−width, y+2, colour C3h; value colour 18h at (x+76, y+2): `DS:42CE[5FDE − (DS:4775 ? 7 : 12)]` |
| `07ba:02ad` | `si_draw_aces` | as `si_draw_field` for the label; names `DS:42D4[k]` (k < 4, stop at the first empty) at (x+75, y+3 + k·`gfx_font_width(FONT3)`) |
| `07ba:0351` / `037a` / `03a3` | `si_str_row4/5/7(buf, idx)` | `fstrcpy_n(buf, strtab_get(4 / 5 / 7, idx))` (`STRINGS_.DAT` rows: 4 squadron roles, 5 services, 7 pilot qualities); return buf |
| `07ba:03cc` | `si_format(str_id, arg, dst)` | `sprintf(dst, str_get(str_id), arg); strupr(dst)` |
| `07ba:03fb` | `si_load(first)` | below |
| `07ba:0618` | `si_layout(mode)` | mode 0: items 1–4 mask 74h / flags 82h, item 5 mask 0 / flags 80h, item 0 mask 40h; mode ≠ 0: items 1–4 hidden (0 / 80h), item 5 74h / 82h, item 0 mask 0 (no prompt); `hs_default_links(49ef:0011, 16)` |
| `07ba:06bd` | `si_side_items()` | items 6–10 mask = `DS:4775 ? 40h : 0`, items 11–15 mask = `DS:4775 ? 0 : 40h` |
| `07ba:0729` | `si_build_list(mode)` | `DS:0628 = squad_count()` (`2624`); `DS:0624 = farmalloc(4·count)`; mode 0: for sq < count: `squad_valid(sq) && 287b:0439(DS:4790, sq)` (squadron in the campaign) `&& squad_service(sq) == DS:4776 && (d = squad_next_mission_date(sq, DS:42CA, DS:42CC)) != 0` → append {sq, d}; mode ≠ 0: one entry {`DS:478E`, `DS:477F`}; `DS:062A = n`; n == 0 → fatal (squadinf.c 289h); the unused entries get squadron FFFFh |
| `07ba:0822` | `si_set_buffers(char *a, char *b)` | `42DC = a, 42DE = a+50, 42E0 = a+100, 42E2 = a+150`; `42CE[i] = b + 40i` (i < 3), `42D4[i] = b + 120 + 40i` (i < 4) |
| `07ba:0891` | `si_frame` | dispatch + present; result 2 (Esc) → `DS:5FD2 = 3` (CANCEL) |
| `07ba:08c2` | `squadinf(mode)` → u8 | below |

```
si_load(first):                                    // 07ba:03fb
  e = list[cursor]; if (s8)DS:062C == e.sq: return
  DS:062C = e.sq; date = e.date
  DS:42DC = strupr(copy squad_name(sq)); DS:42DE = strupr(copy squad_name2(sq))
  si_format(1, si_str_row4(tmp, squad_role(sq)), DS:42E0)                 // "A FIGHTER SQUADRON"
  if first: si_format(2, si_str_row5(tmp, DS:4776), DS:42E2)             // "FOR THE <service>"
  DS:42CE[0] = strupr(copy aircraft_name(squad_aircraft(sq, date)))      // 2777:00a1
  2a85:0231; DS:42CE[1] = strupr(copy station_name(squad_station(sq, date))) (2a85:027c); 2a85:02c1
  si_str_row7(DS:42CE[2], squad_quality(sq))
  n = 0
  for a in 0 .. ace_count()-1:
     if ace_valid(a) && ace_status(a, date) == 0 && ace_squadron(a, date) == (s8)DS:062C && !ace_has_successor(a):
        fstrcpy_n(DS:42D4[n], ace_name(a)); n++; strupr(DS:42D4[n])   // sic: uppercases the NEXT slot, the name keeps its case
  while n < 4: DS:42D4[n][0] = 0; n++
```

Quirks to keep: the name just copied is not uppercased (the following buffer is); more than 4
matching aces would write past `DS:42D4[3]` into `DS:42DC`… (the data never has more than 4 living
aces per squadron: L).

```
squadinf(mode):                                    // 07ba:08c2
  loop = 1; first = 1; result = (garbage until set); DS:062C = FFh
  si_set_buffers(stack 200 bytes, stack 320 bytes)
  if mode == 0: DS:42CC = 287b:03e1(DS:4790); DS:42CA = 287b:0389(DS:4790)
  strtab_load(res_name("strings_", -1, "dat")); si_build_list(mode); cursor = 0
  DS:42C4 = bmp_load_planes("flags.bmp"); si_layout(mode); si_side_items()
  DS:42C8 = font_load("simq_sml.fnt"); DS:42C6 = font_load("simq_hdl.fnt")
  hs_set_table(49ef:0011, 16); hs_focus(mode ? 5 : 4)
  while loop:
     screen_show(DS:4775 ? 19 : 20, CAh, 1); si_load(first)
     if mode == 2 && first: strtab_free; strtab_load("misc.dat"); tbox_over_screen(strtab_get(2, 0)); strtab_free; strtab_load("strings_.dat")
     first = 0; hs_draw_all(); menu_run(si_frame); ui_busy()
     switch DS:5FD2:
       1 PREVIOUS: cursor = cursor ? cursor - 1 : DS:062A - 1
       2 NEXT:     cursor = (cursor + 1 == DS:062A) ? 0 : cursor + 1
       3 CANCEL:   result = 0; loop = 0
       4 SELECT:   loop = 0; result = 1; DS:478E = e.sq; DS:477B = e.date; DS:477D = FFFFh
                   squad_sched_init(DS:478E, &DS:477B, DS:477B) (2624:043a)
                   DS:478A = squad_aircraft(DS:478E, DS:477B); DS:478C = squad_station(DS:478E, DS:477B)
       5 CONTINUE: loop = 0; result = 1
  strtab_free; bmp_free(DS:42C4); farfree(DS:0624); font_free(DS:42C8); font_free(DS:42C6)
  return result
```

Callers: flight deck (mode 1), career events `0874:1039` (squadron move / transfer), new-career
set-up `0fa1:02f9` (mode 0).

## 4. The war map (`bigmap.c`, `0d16`, screen 13 `BIGMAP`, table `4b12:000f`, 8 items) — V

"THE PACIFIC THEATER": a map wider than the window made of two bitmaps (`BIGMAP.BMP` frames 0
and 1 side by side) that scrolls left/right with the `<` / `>` buttons, the player's station
marked with the side's insignia and a speech-bubble box "YOU ARE STATIONED AT / ABOARD THE
<station>.", and place names that light up under the mouse (`BIGMAP.DAT`).

| # | Rect | Callback | Mask/fl | Label (`BIGMAP.SCD`) |
|---|---|---|---|---|
| 0 | 0,0,320,200 | `draw_side_riveted_panel` | 40 | |
| 1 | 15,18,292,173 | `draw_inset_box2` | 40 | |
| 2 | 16,3,153,13 | `bm_draw_title` `0467` | 40 | str 0 "THE   PACIFIC   THEATER" |
| 3 | 17,20,288,169 | `bm_draw_map` `01d7` | 40 | |
| 4 | 229,3,16,13 | `bm_btn_cb` `0445` | 74 / 02 | "<" |
| 5 | 244,3,16,13 | `bm_btn_cb` | 74 / 02 | ">" |
| 6 | 265,3,41,13 | `bm_btn_cb` | 74 / 82 | str 4 "EXIT" |
| 7 | 0,0,165,23 | `bm_draw_station` `04ab` | 40 | (rect set at draw time) |

Map window (clip) = x 17..305, y 20..189. State: `DS:0958` / `DS:095A` x of frame 0 / frame 1
(y always 20), `DS:4431` u8 view (2 = left part, 4 = right part), `DS:4432` u8 scroll request
(1 initial, 2 left, 4 right, 0 none), `DS:095C` u8 station box dismissed, `DS:095D` u8 view at the
last label pass, `DS:441A` BIGMAP.BMP handle (frames 0, 1 map halves, 4 / 5 bubble arrows),
`DS:441C..4422` station position (long x, long z), `DS:442A`/`DS:4428` centre of the station's
area on the big map (from `WLDLOCS.DAT`), `DS:442C` area number, `DS:4430` station is a carrier,
`DS:4433` station name, `DS:419A` text buffer, labels `DS:4418` (count `DS:442E`, text blob
`DS:4451`, shown flags `DS:4453`).

`BIGMAP.DAT`: u16 n (25), n × 18-byte records {s16 x0, y0, x1, y1 (mouse rectangle, map
coordinates), u16 text offset (→ near pointer after loading), s16 text x, text y, far save buffer
(filled at run time)}, u16 len, len bytes of NUL-terminated names.

| Address | Name | Behaviour |
|---|---|---|
| `0d16:000f` | `bm_to_screen(cx, cy, w, h, long x, long z, int *sx, int *sy)` | `sx = cx + (w>>1) + (s16)((long)(w>>1) · x / 12672000) + DS:0958`; `sy = cy + (h>>1) − (s16)((long)(h>>1) · z / 12672000) + 20` (`sar` for >>1; LXMUL, signed LDIV by C15C00h = 2400 × 5280). Always called with (`DS:442A`, `DS:4428`, 64, 53) |
| `0d16:009c` | `bm_load_labels(name)` | `res_fopen(name, "rb")` (fatal BAh); read n → `DS:442E`; `DS:4418 = xmalloc(18n)`, read; u16 len; `DS:4451 = xmalloc(len)`, read; FONT3; per record: text += `DS:4451`; save buffer = `farmalloc(save_size(text_width(text), 10))` |
| `0d16:01d7` | `bm_draw_map` | below |
| `0d16:0445` | `bm_btn_cb` | `if btn_small_cb(0)`: `DS:5FD2 = 5FDE`; result 1 |
| `0d16:0467` | `bm_draw_title` | font `DS:4220` (FONT4); `2302 = 1`; `text_emboss(str_get(0), x, y, C1h, C0h, B1h)` |
| `0d16:04ab` | `bm_draw_station` | below |
| `0d16:06c1` | `bm_hover_labels()` | below |
| `0d16:0901` | `bm_frame` | `hs_dispatch(601A, 6018, 2033, 0)`; mouse inside the map window (17 < x < 305, 20 < y < 189): first time (`DS:095C == 0`) → `DS:095C = 1`, masks of items 3 and 7 (`4b12:005d`, `4b12:00b5`) := 3 (redraw the map without the box); later → both masks := 40h and `bm_hover_labels()`; `hs_present()`; result 1: item 4 → `DS:4432 = 2`, item 5 → `DS:4432 = 4`; result 2 (Esc) → `DS:5FD2 = 6` |
| `0d16:09d8` | `bm_station()` | `2a85:00f1(DS:478C, &area_of_world, &DS:442C)`; `DS:4430 = 2a85:0180(DS:478C)`; file = `res_name(DS:4430 ? "CARRIER" : "TARGET", −1, itoa(DS:442C))` → **`CARRIER.<n>` / `TARGET.<n>`** (the area number is the extension); `wd_load_database(file)`; `wd_position(area_of_world, DS:477B, &DS:441C, 1)`; `wd_close()` (`2322`, shell_data); station name → `DS:4433` (`2a85:0231/027c/02c1`); `s = table_load("wldlocs", "dat", 4, 3, 11h, 1, …)`; `rec = table_rec(s, DS:442C)` (fatal 2BAh); `DS:442A = rec[0]`, `DS:4428 = rec[1]`; `table_free(s)` |
| `0d16:0b03` | `bm_free_label_buffers()` | farfree each save buffer |
| `0d16:0b33` | `bigmap_show()` | below |
| `0d16:0c5d` | `bm_init()` | `hs_default_links(4b12:000f, 8)` |

```
bm_draw_map():                                     // item 3
  clip on: 17, 20, 305, 189
  W = BIGMAP[1].width (+6 of the frame)
  if DS:4432 == 4 && DS:4431 == 2:                 // scroll to the right part
     for (i = 0; i <= W + 30; i += 10):
        pages front→work; copy_full_screen()
        gfx_sprite_opaque(BIGMAP[0], DS:0958 - i, 20); gfx_sprite_opaque(BIGMAP[1], DS:095A - i, 20); page_flip(1)
     DS:0958 -= i - 10; DS:095A -= i - 10; DS:4432 = 0; DS:4431 = 4
     bm_to_screen(…, &sx, &sy); if !DS:095C && sx < 17: DS:095C = 1     // station scrolled out: box gone
     hs_draw_all()
  else if DS:4432 == 2 && DS:4431 == 4:            // scroll back left
     same loop with + i; DS:0958 += i - 10; DS:095A += i - 10; DS:4432 = 0; DS:4431 = 2
     bm_to_screen(…); if !DS:095C && sx > 305: DS:095C = 1
     hs_draw_all()
  else if DS:4432 == 1:                            // first draw: open on the half that holds the station
     bm_to_screen(…); if sx < 306: DS:4431 = 2
     else: s = W + 30; s -= s % 10; DS:4431 = 4; DS:0958 -= s; DS:095A -= s
     DS:4432 = 0
  gfx_sprite_opaque(BIGMAP[0], DS:0958, 20); gfx_sprite_opaque(BIGMAP[1], DS:095A, 20); clip_full()
```

(The nested `hs_draw_all()` redraws every item, including this one, after a scroll: the second
pass finds no request and just draws the frames.)

```
bm_draw_station():                                 // item 7
  bm_to_screen(DS:442A, DS:4428, 64, 53, DS:441C, DS:4420, &5FDA, &5FD8); FONT3
  if !(17 < x < 305 && 20 < y < 189): return
  draw_bitmap(insignia DS:5FE4[DS:4775 + 16], x, y, 0)
  if x < 162: bx = x - 10; ax = x + 1;  mirror = 0
  else:       bx = x - w + 10; ax = bx + w - 15; mirror = 1
  if y < 105: by = y + 22; ay = y + 7; arrow = 4
  else:       by = y - h - 18; ay = by + h - 1; arrow = 5; mirror = !mirror
  if bx < 18: bx = 17;  if bx + w > 305: bx = 305 - w
  5FDA = bx; 5FD8 = by
  if !DS:095C:
     tile_fill_rect(); draw_frame(); draw_bitmap(BIGMAP[arrow], ax, ay, mirror ? 2 : 0)
     sprintf(DS:419A, "%s%s", str_get(1), str_get(DS:4430 ? 2 : 3)); text_engrave(DS:419A, C1h, B1h, C0h, bx+7, by+3)
     sprintf(DS:419A, "%s.", DS:4433); strupr; text_engrave(…, bx+7, by+13)

bm_hover_labels():
  S = BIGMAP[1].width + 25; FONT3
  for each label i: tw = text_width(text)
     (x0, y0, x1, y1, tx) = record, minus S on x0, x1, tx when DS:4431 == 4; ty = record
     sx = tx + 17, sy = ty + 20
     if DS:095D != DS:4431 && 17 < sx < 305 && 20 < sy < 189: 2316 = 2312; save_rect(buf_i, sx, sy, tw, 10)
     if x0+17 < mx < x1+17 && y0+20 < my < y1+20 (mx, my = 601A, 6018):
        if DS:4453[i] != 1: draw_text(text, sx, sy) colour A4h on the front page and on the work page; DS:4453[i] = 1
     else if DS:4453[i] == 1: restore_rect(buf_i, sx, sy, tw, 10) on the front and the work page; DS:4453[i] = FFh
  DS:095D = DS:4431
```

```
bigmap_show():                                     // flight deck VIEW THE WAR MAP
  bm_load_labels(res_name("bigmap", -1, "dat")); DS:441A = bmp_load_planes("bigmap.bmp") (fatal 2DAh)
  DS:4453 = xmalloc(DS:442E); DS:0958 = 17; DS:095A = BIGMAP[0].width + 17
  DS:4432 = 1; DS:4431 = 2; DS:095C = 0; DS:095D = 0
  bm_station()
  screen_open(13, screen_clear_black (2c11:0902), 4Eh, 1)
  DS:5FD2 = 6
  do { hs_set_table(4b12:000f, 8); hs_focus(DS:5FD2); hs_draw_all(); menu_run(bm_frame) } while DS:5FD2 != 6
  xfree(DS:4418); xfree(DS:4453); xfree(DS:4451); bm_free_label_buffers(); bmp_free(DS:441A)
```

(The label flags `DS:4453` are xmalloc'ed uninitialised: a label is restored only after it was
drawn, so garbage ≠ 1 is harmless except that a stray 1 would skip its first highlight: L.)

## 5. Single-mission set-up (`flymiss2.c`, `100e`, screens 0–9 `MT_*`, table `4bbe:0011`, 13 items) — V (L where marked)

After the fly menu has picked a mission type (and a service, or an ace for "dogfight an ace"), the
mission is generated at once (`mission_build`) and shown as a **paragraph with inline buttons**:
the type's sentence from `STRINGS_.DAT` row 0 ("Your %a will fly %b. Most of the %t in the area
are %c, flying %j. The sky is %e.") is laid out by `flow_text_buttons` (toolkit §3); every `%a`..`%j`
becomes a button showing the current value, clicking it opens a chooser; CANCEL / START below.
Screen = mission type (`screen_show(type, 11Ah, 1)`: backgrounds `MT_DACE`…`MT_GRND`, labels
`FLYMISS2.SCD`), title bar `draw_title_bar_for(DS:4B30, DS:6277, str_get(type + 2))` ("DOGFIGHT
AN ACE" … "GROUND ATTACK", 12 "STOP KAMIKAZES!" for the generated type 10).

Items: 0 (0,121,320,79) `fm2_draw_text` `0648` (mask 40h); 1–10 (74×9 placeholders) `fm2_slot_cb`
`08d4` (74h / 02h) = the inline buttons, positioned by `flow_text_buttons`; 11 (48,60,75,18) str 16
"CANCEL", 12 (202,60,75,18) str 17 "START" (`fm2_btn_cb` `007e`, 74h / 82h). A pristine copy of
items 1–10 is kept after the table (`4bbe:012f + 22i`).

**Parameter kinds** (`%a` = kind 1 … `%j` = kind 10; value `DS:4A30[kind]` (s16), labels from
`SFTBTNS0.DAT` row 0 = the string table loaded during the screen, or `str_get` of `FLYMISS2.SCD`):

| Kind | Value (init from the built mission) | Button label | Chooser on click (`fm2_edit`) |
|---|---|---|---|
| 1 `%a` own flight | `DS:4A32 = DS:62DF − 1` | str 15 "flight" | flight roster dialog (own) |
| 2 `%b` own aircraft | `DS:4A34` = index of `DS:62DD` in aircraft list 0 | aircraft name (`2777:06fd(0, type != 0)`, `2777:0741(v)`) | `pick_aircraft(str 14 "SELECT AIRCRAFT:", fm2_on_ok, DS:4B22, 0, type != 0, v)` |
| 3 `%c` enemy skill | `DS:4A36` = Σ enemy pilot codes < 4 / `DS:636F` | row0[v + 173] "novice pilots"… | CHOOSE 4 entries from 173 |
| 4 `%d` altitude | `DS:4A38 = DS:62CC` | row0[v + 4] "at very low altitude"… | CHOOSE 5 from 4 (`DS:4B3C` = old value) |
| 5 `%e` sky | `DS:4A3A = DS:626F` | row0[v + 9] "clear"… | CHOOSE 4 from 9 |
| 6 `%f` training | `DS:4A3C = 0` | row0[v + b], b = 39 when `DS:4B30` ∈ {2, 4} (USAAF, JAAF: "aerial gunnery", "ground attack") else 34 (5 kinds) | CHOOSE 2 or 5 from b |
| 7 `%g` surprise | `DS:4A3E = DS:6270` | row0[v + (type ? 31 : 28)] ("No one / You / He" or "No one / Your flight / The enemy flight") | CHOOSE 3 |
| 8 `%h` escorted / intercepted aircraft | `DS:4A40` = index of `DS:63FD` in list 2 | aircraft name (list 2) | `pick_aircraft(…, DS:4B1E, 2, …)` |
| 9 `%i` enemy flight | `DS:4A42 = DS:636F − 1` | str 15 "flight" | flight roster dialog (enemy) |
| 10 `%j` enemy aircraft | `DS:4A44` = index of `DS:636D` in list 1 | aircraft name (list 1) | `pick_aircraft(…, DS:4B20, 1, …)` |

Other substitutions (`fm2_subst`): `%r` row0[`DS:4B24` + 13] (ship target class), `%s` row0[`DS:4B24`
+ 16] (ground target), `%t` row0[side ? `DS:0A9D` : `DS:0A9F`] ("Japanese" / "Americans", side =
`0f67:02ed(DS:4B30)`), returned as text. `DS:4B24` = target class: type 8 → `DS:6477[20·DS:62E5]`,
type 9 → `DS:64B2[18·DS:62E5]`.

State: `DS:4B2F` mission type (after the build: `DS:626C`, except training 5), `DS:4B30` service (1
for dogfight-an-ace), `DS:4B31[1..10]` kind of inline button i (FFh unused), `DS:4B3E` number of
inline buttons, `DS:4B3F` pressed CANCEL/START index, `DS:4B29[4]` / `DS:4B25[4]` own / enemy pilot
codes (0–3 skill, ≥ 4 = ace id + 4), `DS:4B2D` roster slot being edited (FFh = none), `DS:4B2E` side
of that slot, `DS:4B1D` re-link pending, `DS:0B25` something changed, `DS:4B1A` enemy skill changed,
`DS:4B1B` altitude accepted, `DS:4B3D` training slot, `DS:4A46[53]` far copies of `STRINGS_.DAT`
row 0, `DS:4A28[4]` the string list given to `flow_text_buttons`, `DS:4B22`/`4B20`/`4B1E` aircraft
list counts.

| Address | Name | Behaviour |
|---|---|---|
| `100e:0007` | `fm2_training_slot(k)` → i | table `DS:0AA1` (rows of 22 bytes = s16 per service): i = first row with `[i][DS:4B30] != −1`; then k times: advance to the next such row; i > 6 → fatal (flymiss2.c C8h) |
| `100e:007e` | `fm2_btn_cb` | `if btn_cb()`: `DS:4B3F = 5FDE`; `menu_set_result(5FDE == 12 ? 1 : 2)` |
| `100e:00a8` | `fm2_on_ok(sel)` | chooser callback: roster slot (`DS:4B2D ≥ 0`): side 0 → `acelist_select(0)`, `DS:4B29[DS:4B2D] = acelist_code(sel)`; side 1 → `acelist_select(1)`, `DS:4B25[DS:4B2D] = …`; else `DS:4A30[DS:4B31[5FDE]] = sel`; `DS:0B25 = 1` |
| `100e:0120` | `fm2_roster_cb(slot)` | roster-dialog callback: slot < 0 (its "%a" size button): `DS:4B2D = FFh`; item.user = 4; `choose_run(fm2_on_ok, DS:4A30[DS:4B3F], 93)` ("one".."four") — see the note; else `DS:4B2D = slot`; `pick_list2(str 13 "SELECT PILOT:", fm2_on_ok, acelist_enabled_count())` |
| `100e:017f` | `fm2_prepare_acelist(side)` → sum | service = side ? `DS:6355` : `DS:4B30`; codes = side ? `DS:4B25` : `DS:4B29`; `acelist_build(service, side, 1, side == 0)`; n = side ? `DS:636F` : `DS:62DF − 1`; for i < n: code < 4 → sum += code, else `acelist_disable(code, side)` (aces already in the flight); returns sum |
| `100e:0225` | `fm2_edit(kind)` | `DS:4B2D = FFh`; kind 1 / 9: `DS:4B2E = 0 / 1`; `acelist_select`; repeat { item.user = `DS:4A30[kind] + 1`; `DS:4B1C = flt_roster(fm2_roster_cb, side ? DS:4B25 : DS:4B29, side)`; `fm2_prepare_acelist(side)` } while `DS:4B1C`; kinds 2, 8, 10: `pick_aircraft` as in the table; kinds 3–7: item.user = count, `DS:4B3C = v` for kind 4, `choose_run(fm2_on_ok, v, first)` (switch table `100e:0401`) |
| `100e:0415` | `fm2_slot_label(kind, item far *it, reg)` → 0 | sets `it.label` (switch `100e:05b2`): 1, 9 → `str_get(15)`; 2 / 8 / 10 → `2777:06fd(0 / 2 / 1, type != 0)`, `2777:0741(v)`; 3 → copy of row0[v + 173] into `DS:411A`, `DS:4B1A = 1`; 4 → `c = 2777:02f8(2777:0724(DS:4A36))` (sic: the kind-3 value used as an aircraft-list index; L: meant `DS:4A34`), if `c < v`: `v = DS:4B3C` (reject) else `DS:4B1B = 1`; label row0[v + 4]; 5, 6, 7 → row0 as in the table (copied into `DS:411A`); `reg` → `DS:4B31[++DS:4B3E] = kind`. Returns 0 (→ inline button) |
| `100e:05c6` | `fm2_subst(c, item far *it)` | `%r`, `%s`, `%t` above (returns a `strpool_copy`); other letters → `fm2_slot_label(c − 60h, it, 1)` |
| `100e:0648` | `fm2_draw_text` | item 0: `tile_fill_rect(); draw_frame()`; FONT3, `2302 = 1`; y_off = 8; type 0: rect += (20, 6, −35 w) (saved/restored), `flow_setup(−3, 7, 1)`, `flow_text(acetxt_duel_text(DS:6363), 1, 0)` (the ace's own blurb), y_off = 23; `DS:4B3E = 0`; `DS:4B1D = 1`; strings = {row0[type], 0}; training (type 5): `DS:4B3D = fm2_training_slot(DS:4A3C)`, `DS:4B89 = DS:4B3D == 5 ? 4 : DS:4B3D`, strings = {row0[5], row0[`DS:0AA1[DS:4B3D][DS:4B30]`] ("You will be flying a …"), row0[`DS:4B3D` + 12] ("Try to shoot down the drone …"), 0}; `flow_text_buttons(4bbe:0011, 1, fm2_subst, strings, x+20, y+y_off, x+w−20)`; `draw_bottom_bar()` |
| `100e:07c0` | `fm2_relink()` | re-orders the inline buttons into text order: spare[i] := item `DS:4B31[i]` for i = 1..`DS:4B3E`; items 1–10 := spare[1..10]; links: item i up/left = i − 1, item i−1 down/right = i; item 1 up/left = 12; item `DS:4B3E` down/right = 11; item 12 up/left = `DS:4B3E` |
| `100e:08d4` | `fm2_slot_cb` | if `DS:4B31[5FDE] < 80h`: first time after a layout (`DS:4B1D`): `fm2_relink()`, current rect := item rect + (0, item 0's y), `DS:4B1D = 0`; `fm2_slot_label(kind, item, 0)` (refresh); mask = 74h; `if choose_entry_cb()`: `fm2_edit(kind)`; `hs_restart()` |
| `100e:0967` | `fm2_frame` | dispatch + present; result 2 → `DS:4B3F = 11` |
| `100e:0997` | `fm2_codes(flight *f, u8 *dst)` | for i < f.+1Ah: `dst[i] = f[+0Ah + i] == −1 ? f[+0Eh + 2i] + 4 : f[+0Ah + i]` |
| `100e:09d0` | `fm2_codes_all()` | `fm2_codes(DS:62C5, DS:4B29)`; `fm2_codes(DS:6355, DS:4B25)` |
| `100e:09f1` | `fm2_init(arg)` | below |
| `100e:0bff` | `fm2_apply()` | below |
| `100e:12c9` | `flymiss2_setup(type, arg)` → u8 | below |
| `100e:1459` | `fm2_links_init()` | `hs_default_links(4bbe:0011, 13)` |

```
fm2_init(arg):                           // arg = service, or the ace for type 0
  strtab_load("strings_.dat"); strings_dup_far(DS:4A46, 53, row 0); strtab_free()
  strtab_load(res_name("sftbtns", 0, "dat"))                     // stays loaded until fm2_apply
  for i in 1..10: DS:4A30[i] = -1; DS:4B31[i] = FFh; spare[i] = item i
  mission_build(DS:4B2F, arg, 0) (3164:0a27); if DS:4B2F != 5: DS:4B2F = DS:626C
  DS:4A32 = DS:62DF - 1; DS:4A3A = DS:626F; DS:4A38 = DS:62CC; DS:4A3E = DS:6270; DS:4A42 = DS:636F - 1; DS:4A3C = 0
  DS:4B1D = 1; DS:4B1C = 0; DS:4B1A = 0; DS:4B30 = (DS:4B2F == 0) ? 1 : arg
  for (list, count, id, value) in [(0, DS:4B22, DS:62DD, DS:4A34), (1, DS:4B20, DS:636D, DS:4A44), (2, DS:4B1E, DS:63FD, DS:4A40)]:
     2777:06fd(list, 0); count = 2777:070e(); value = first i with 2777:0724(i) == id (unchanged if none)
  fm2_codes_all(); fm2_prepare_acelist(0)
  s = fm2_prepare_acelist(1); DS:4A36 = DS:636F ? s / DS:636F : 0
  DS:4B24 = type 8 ? DS:6477[20·DS:62E5] : type 9 ? DS:64B2[18·DS:62E5] : unchanged

flymiss2_setup(type, arg):              // 100e:12c9, caller flymenu_run 0b16:01a7
  ok = 0; if type == 0: acetxt_open() (2550:0780)
  DS:4B2F = type; fm2_init(arg)
  loop:
    screen_show(type, 11Ah, 1); draw_title_bar_for(DS:4B30, DS:6277, str_get(DS:4B2F + 2))
    hs_set_table(4bbe:0011, 13); hs_focus(12); hs_draw_all(); menu_run(fm2_frame); ui_busy()
    if DS:4B3F == 11 (CANCEL / Esc): fm2_apply(); return 0
    if DS:4B3F == 12 (START):
       type 0: fm2_apply(); return 1
       type 5: n = DS:4B3D·5 + DS:4B30; fm2_apply()
               mission_load(res_name("TRN", n, "DAT"), 1) (1f06:015c); mission_write_script (1f06:0269); mission_free (1f06:0782)
               DS:626C = 5; DS:626B = 0; DS:62C5 = DS:4B30; farfree the message tables DS:5272, DS:5276 (and zero them); load_free (3164:3602)
               return 1
       else:   fm2_apply(); briefing(-1) (0c1d:03c6); return DS:43D6 ? 1 : 0     // declined → back to the fly menu
```

```
fm2_apply():                             // 100e:0bff — writes the chosen values into the mission
  if DS:0B25:                            // something was changed
    f = &DS:62C5 (own flight, 90h bytes); 280a:00af()
    DS:626F = kind5; DS:6270 = kind7; f.+1Ah (count) = kind1 + 1
    if type 0 or 1 (dogfights):
       m = 3d50:16b0(DS:62E7, DS:6377)    // midpoint of the two first waypoints (12-byte x,z,alt)
       own wp0 = m; enemy wp0 = m
       if DS:4B1B: f.+7 = kind4 + 1 (altitude class); a = DS:6526[8·class] (long: DS:652E band minimum of class−1)
                   own wp0.alt = own wp1.alt = a; DS:635C = class; enemy wp0.alt = enemy wp1.alt = a
       switch DS:6270:
         0 (no one): own wp0.x += 19000; enemy wp0.x -= 19000 (long)
                     own wp1 = enemy wp0; enemy wp1 = own wp0            // fly at each other
                     DS:62CA = heading(own wp0 → own wp1) >> 8; DS:635A = heading(enemy wp0 → enemy wp1) >> 8   (2b1f:00b4)
         1 (you):    own wp0.x += 5000; enemy wp0.x -= 5000; own wp0.alt += 3000
                     h = heading(own wp0 → enemy wp0); DS:62CA = h >> 8; DS:635A = DS:62CA   // enemy flies away
                     own wp1 = 2b1f:0121(own wp0, h, 4000000) ; enemy wp1 = 2b1f:0121(enemy wp0, h, 4000000)   // project 4,000,000 units
         2 (he):     same shifts; enemy wp0.alt += 3000; h = heading(enemy wp0 → own wp0); DS:635A = DS:62CA = h >> 8; wp1 projections as in 1
    DS:636F = kind9 + 1
    if kind2 >= 0: 2777:06fd(0, 0); f.+18h (DS:62DD) = id = 2777:0724(kind2); f.+2 = cls = 2777:0204(id)
                   f.+1 = 280a:021b(DS:62C5, DS:62C7, DS:6277); f.+3 = 2ab3:03a7(DS:4B2F, 2777:0252(id), DS:0A9C, 0)
                   if DS:626C not 0/1: every waypoint k < f.+1Ch with alt > 10000: alt = DS:651E[cls] (long)
                                         (types 8, 9 with DS:6265 > 0: the same for the list DS:6407)
    if kind10 >= 0: 2777:06fd(1, 0); DS:636D = 2777:0724(kind10); DS:6357 = 2777:0204(DS:636D)
                    DS:6356 = 280a:021b(DS:6355, DS:6357, DS:6277); DS:6358 = 2ab3:03a7(DS:626C, DS:636D, 0, 1)
                    if DS:626C == 4 (scramble): enemy wp0.alt = wp1.alt = (DS:6357 == 3) ? 20000 : DS:651E[DS:6357]
    if kind8 >= 0 and DS:626C in {6, 7}: 2777:06fd(2, 0); DS:63E6 = 280a:021b(DS:63E5, DS:63E7, DS:6277)
                    DS:63FD = 2777:0724(kind8); DS:63E8 = 2ab3:03a7(DS:626C, DS:63FD, 0, 2)
    280a:0431()
  DS:62CF = 4                                        // slot 0 = the player
  if type != 5:
    for s in 1..3: c = DS:4B28[s] (= DS:4B29[s-1]); c >= 4 ? (DS:62D3[s] = c - 4, DS:62CF[s] = FFh) : DS:62CF[s] = c
    for s in 0..3: c = DS:4B25[s];                   c >= 4 ? (DS:6363[s] = c - 4, DS:635F[s] = FFh) : DS:635F[s] = c
  if DS:4B1A: for each enemy flight i < DS:6263: for j < DS:636F[24h·i] (word): DS:635F[24h·i + j] = kind3
  strings_free_far(DS:4A46, 53); strtab_free(); if type == 0: acetxt_close()
  // data sets needed by the mission → SIM.IN flags
  need[9] = 0; bits = DS:0B26[8] (copied; need[8] reads past it: stack garbage)
  for fl in 0..2 (flights DS:62C5 + 90h·fl):
     for d in 0..8: a = aircraft(fl) + 1; if (d-1)·15 + 39 < a < d·15 + 39: need[d] = 1
                    for k in 0..3: p = DS:62D3[48h·fl + k]; if (d-1)·15 + 29 <= p < d·15 + 29: need[d] = 1
  for d in 0..8: for g in 0..2: for k < DS:6483[20·g] (word): t = DS:6479[20·g + k] + 1; if (d-1)·10 + 35 < t < d·10 + 35: need[d] = 1
  need[module_active()] = 1
  for d in 0..8: if need[d]: DS:6271 |= bits[d]; DS:4B8D |= bits[d]
```

Notes (L, faithful port keeps them): `fm2_apply` copies the own codes from `DS:4B29[0..2]` into
slots 1–3, while `fm2_codes` stores slot 0 (the player, code 4) at `DS:4B29[0]` — so an untouched
roster puts code 4 (= ace 0) into slot 1 unless the roster dialog rewrote the array; the roster
size button reads `DS:4A30[DS:4B3F]` and writes `DS:4A30[DS:4B31[5FDE]]` with `5FDE` = the index
inside the roster dialog. Verify against the running game before "fixing".
