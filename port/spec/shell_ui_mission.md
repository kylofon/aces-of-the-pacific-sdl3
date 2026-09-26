# shell_ui part — mission set-up helpers: choosers, preflight, text boxes, custom missions, career decision

Target `Game/PS.EXE` (DGROUP `4D08`). Segments `125a` simshell.c (file-name helpers), `0cfe`
(career text substitutions — **not in the function index**, see §3), `12a7` (campaign chooser),
`12c4` (flight-map data), `1305` (text boxes), `144e` decision.c, `147e` custmiss.c, `1513`
(preflight), `1612` (service/nation chooser), `1656` (career notifications). Toolkit names:
`shell_ui_toolkit.md`; mission globals (`DS:626B` kind, `626C` type, `626D` area, `6277` date,
`62C5` flights…) are shell_data's (`shell_data.md`). Confidence **V**/**L**/**G**.

## 1. File-name helpers (`simshell.c`, `125a`) — V

| Address | Name | Behaviour |
|---|---|---|
| `125a:000f` | `res_add_ext(char *name, char *ext)` → path | `strcat(strcat(name, "."), ext)`; when no volume is open (`DS:0DFF` `volumes_present` == 0, a development set-up): returns `DS:4B94` = ext + "\" + name (files sorted in one directory per extension); else returns name. (Tail of `res_name` `1193:0115`) |
| `125a:0060` | `dev_chdir(dir)` → ok | only without volumes: `chdir(dir)`, fatal (simshell.c line 3Eh) on failure; returns 1 otherwise |
| `125a:00ab` | `dev_chdir_up()` | `dev_chdir("..")` |
| `125a:00bb` | `namelist_split(char far *p, char far **out)` → n | counts NUL-terminated words (each copied with `24d5:0005`) until one starting with LF; stores far pointers when `out`; a NUL word before the LF is fatal (5Ch) |
| `125a:0139` | `fread_far(char far *dst, long n, FILE *f)` → count | byte loop with `fgetc` (`0000:0cee`) until n bytes or EOF |
| `125a:01a4` | `res_size(name)` → long | `res_fopen(name, "rb")`, `filelength`, close; 0 if missing |
| `125a:01ea` | `namelist_suffix(char *s, n)` | n == 1 → append "_" (the `…1_` name files of the add-on) |
| `125a:0203` | `namelist_load(char *base, mask, total, per_set)` → table | for set n = 0..8 (set 0 always, set n ≥ 1 when `mask & (1 << (n−1))`): file = base + itoa(n) (+ "_" for n = 1), ≤ 8 chars (fatal BEh), `.TXT`; sums the sizes (missing file fatal C3h); one far block for all texts (fatal CAh); a near table of `total` far pointers (xmalloc, fatal AEh); set 0 fills `total − 8·per_set` slots, the others `per_set` each (overflow fatal DFh). Used by the view-vehicles screens (`0ddd:089a`, `08d7`) for the pilot name lists `PFNAME`/`SFNAME` (formats/data.md §3.3) |
| `125a:04bb` | `namelist_free(table)` | frees the text block and the table |

## 2. Text boxes (`1305`, screen 56 `PARTS`/`TEXTBOX`, table `4bef:0000`, 2 items) — V

A message box that sizes itself to its text. Item 0 (58,41,204,62) `tbox_draw` `0154`, item 1
(1,1,203,17) `tbox_draw_title` `0222`. `DS:0E1C` text, `DS:0E1A` title (xmalloc'ed copies), `DS:4D4C`
text font, `DS:4D4E` title font, `DS:4D44..4D4A` the final rectangle, `DS:0E18` a sound/"voice"
handle passed to `2171:000a` after drawing (shell_data/sound: Likely the event's speech/music).

| Address | Name | Behaviour |
|---|---|---|
| `1305:0008` | `tbox_fit(far text, int *x, int *y, int *w, int *h, pad_w, pad_h, line_h, far subst)` | usable `w0 = *w − pad_w`, `h0 = *h − pad_h`; `aspect = (w0 << 16) / h0` (long); rect = (x, y, w0, h0); `flow_setup(0, line_h, 0)` (measure); loop: `m = flow_text(text, 1, subst)`; while `m > h`: `h = isqrt(m · h)` (`3d50:0102`, long square root), `w = (aspect · h) >> 16`, `h += 5`, `w += 8`, measure again. Then `*w = w + pad_w`, `*h = h + pad_h`; centre: `x −= (w − w0) >> 1`, `y −= (h − h0) >> 1`; clamp x, y ≥ 0; `x + *w ≤ 318`, `y + *h ≤ 198` (by moving x/y) |
| `1305:0154` | `tbox_draw` | `font_select(DS:4D4C)`; `tbox_fit(DS:0E1C, &5FDA, &5FD8, &5FD6, &5FD4, 22, title_h + 8, 7, subst 0cfe:0057)` where `title_h` = `4bef:001C` (item 1 h = 17); remember the rect in `DS:4D44..4D4A`; `tile_fill_rect(); draw_frame()`; text rect = (x+11, y+title_h+4, w−22, h−(title_h+8)); `2302 = 1`; `2316 = 2312`; `flow_setup(3, 7, 1)` (engraved); `flow_text(DS:0E1C, 1, subst 0cfe:0057)` |
| `1305:0222` | `tbox_draw_title` | rect x, y, w = the box (`DS:4D46/4D44/4D4A`); `draw_bevel_box()`; rivets every 7 px at x+4 and x+w−7 from y+5 to y+`DS:4D48`−6; `font_select(DS:4D4E)`; `text_emboss(title, centred, y+4, C1h, C0h, B1h)` |
| `1305:02bd` | `tbox_show()` | pages (2314 → 2312) (`22ce:0074`, no copy); calls both item callbacks directly (items 0, 1); `hs_restart()`; `cursor_hide(); hs_present(); cursor_show()`; `2171:000a(DS:0E18)` |
| `1305:0323` | `tbox_set(far title, far text, title_font, text_font)` | copies the non-null strings |
| `1305:0392` | `tbox_clear()` | frees them |
| `1305:03b7` | `tbox_message(far title, far text, title_font, text_font)` | item 0 x = 58, y = 41; `tbox_set`, `tbox_show`, `tbox_clear` |
| `1305:03f2` | `tbox_end_of_campaign(text)` | `screen_show(56, CAh, 1)`; title = date text of `287b:03e1(DS:4790)` (campaign end date, `284f:021c`); `2624:0902` … `tbox_message(date, text, FONT4, FONT3)` … `2624:09c4` |
| `1305:044e` | `tbox_kia(far text)` | `screen_show(56, CAh, 1)`; `tbox_message(str_get(1) "KILLED IN ACTION", text, FONT4, FONT3)` |
| `1305:0487` | `tbox_inquiry(far text)` | same with str 2 "BOARD OF INQUIRY" |
| `1305:04c0` | `tbox_titled3(far text)` | no screen change; title = `str_get(3)` of the **current** screen's `.SCD` (caller `0ddd:0c06` on the view screen → `VIEW.SCD` 3 "NEW AIRPLANE"; text = `MISC.DAT` row 1 entry 0). (Corrected: was "SQUADRON MOVEMENT") |
| `1305:04e6` | `tbox_over_screen(far text)` | keeps the current screen: `clip_full()`; `hs_dispatch(…, 0, 1)` (redraw); `copy_work_to_spare()`; `hs_push()`; message with str 12 of the current table; `copy_spare_to_work()`; `hs_pop()`; `hs_focus(5FDE)` (from `07ba:08c2`) |
| `1305:0546` | `tbox_squadron_move(far text)` | `screen_show(56, CAh, 1)`; `2a85:0006` (stations load); str 3 "SQUADRON MOVEMENT"; `2a85:0216` |

## 3. Career text substitutions (segment `0cfe`, not indexed) — V

Canonical entry: `shell_ui_debrief.md` §8 (names `subst_ace_name`, `display_subst`, symbols there); summary kept here.

Segment `0cfe` (between `dogace.c` `0c8a` and `bigmap.c` `0d16`; the indexer took it for far data)
holds two functions:

| Address | Name | Behaviour |
|---|---|---|
| `0cfe:000a` | `subst_ace_name()` → far char * | `2550:0679` (aces load); name = `2550:0043(DS:4B89)`; copies `_fstrlen` bytes into `DS:43FA` (`22ce:026e`); `2550:073f`; returns `DS:43FA` |
| `0cfe:0057` | `display_subst(char c)` → far char * | `%a` pilot name `DS:4754`; `%b` date text of `DS:477F` into `DS:43FA`; `%e` `strtab_get(0, DS:4775)`; `%f` `strtab_get(0, (DS:4229 & 10h) ? 6 : (DS:4229 & 20h) ? 7 : 8)`; `%g` `strtab_get(0, DS:4776 + 9)`; `%h` medal name `27f0:00f5(DS:0500)`; `%i` rank name `225d:00f7(DS:0501)`; `%j` `subst_ace_name()`; `%p` squadron name `2624:0042(DS:478E)`; `%q` campaign name `287b:026e(DS:4790)`; `%u` aircraft name `2777:00a1(DS:478A)`; `%v` `strtab_get(0, DS:4775 + 20)`; `%w` station name (`2a85:0231`, `2a85:027c(DS:478C)` copied into `DS:43FA`, `2a85:02c1`); `%x` `strtab_get(0, DS:4B89 + 26)`; any other letter a–x and anything else → `DS:0956` (empty string). Switch table `0cfe:015F` (24 words) |

(`0cfe:0000`–`0009` is the tail of a function of the preceding module.)

## 4. Campaign chooser (`12a7`, screen 43 `CLOUDS`/`CAMPBOX`, table `4be4:0000`, 8 items) — V

Items: 0 (44,75,236,75) `draw_side_riveted_panel`; 1 (17,5) `12a7:0008` title str 0 "CHOOSE A
CAMPAIGN" (FONT4, `2302 = 3`, `text_engrave(C1h, B1h, C0h)` at x, y); 2 (16,15,176,35) `lbox_draw`;
3 (198,15,25,44) `draw_bevel_box`; 4, 5 arrows; 6 (33,55,55,13) str 1 CANCEL; 7 (122,55,55,13)
str 2 ACCEPT (`12a7:004b`: `btn_small_cb(0)`, result `5FDE == 7 ? 1 : 2`).

| Address | Name | Behaviour |
|---|---|---|
| `12a7:0008` | `camp_draw_title` | above |
| `12a7:004b` | `camp_btn_cb` | above |
| `12a7:0073` | `camp_draw_row(i, y)` | `draw_text(DS:4C7C[i], x+5, y)` |
| `12a7:0093` | `camp_list(service)` | for each campaign k < `1f85:014d()`: if `1f85:0359(k, service)`: `DS:4C7C[n] = 287b:026e(1f85:0157(k))` (name), `DS:4BB4[n] = k`, n++; `DS:4BB2 = n` |
| `12a7:00ec` | `camp_frame` | dispatch + present |
| `12a7:010d` | `camp_choose(service)` → k / FFh | `camp_list`; `lbox_setup(…, DS:4BB2, 5, draw camp_draw_row)`; `lbox_bind(4be4:0000, 2, 4)`; `screen_show(43, 2Ah, 1)`; focus 7; `menu_run`; Esc/CANCEL (2) → `DS:0E09 = FFh`, else `DS:4BB4[lbox_selected()]`; `ui_busy()`; returns `DS:0E09` (called by the historic-mission screen `0583:03c2`) |
| `12a7:01c0` | `camp_init()` | `hs_default_links(4be4:0000, 8)` |

## 5. Flight-map data (`12c4`) — V

Builds the two arrays `fltmap_show` (`06c7:0b14`, shell_ui_flight) draws: **flights** (16-byte
records: u8 symbol/colour class, u8 flags, 12 bytes position (copied waypoint), u16 id) and
**waypoints** (16 bytes: 12-byte waypoint + far pointer to its message text). The returned block
`DS:0E10` = {flights ptr `0E10`, count `0E12`, waypoints ptr `0E14`, count `0E16`}.

| Address | Name | Behaviour |
|---|---|---|
| `12c4:0009` | `fmap_count_flights()` | `DS:6261` (flights) + `DS:6269` (convoys) + (`DS:6265` ? 1) + places `DS:64B4[18k]` flagged among `DS:6267` |
| `12c4:0044` | `fmap_rec(dst, cls, flags, far src12, id)` | stores the record |
| `12c4:0072` | `fmap_fill_flights(dst)` | classes by side (player's service `0f67:02ed(DS:62C5)`: own side gets the even set {2,4,6} or odd {1,3,5} depending on the side, other side the other set): own flight 0 = (0, DS:62CA, DS:62E7 waypoint, DS:62DD); convoys `DS:6475 + 20k` (class own/enemy convoy, flags `DS:6479`, position `DS:6487`); places with `DS:64B4` set (class own/enemy place, position `DS:64B7`, id `DS:64B2`); other flights 1… of `DS:62C5 + 36h·k` (class of flights); escorted/extra flight at `DS:63E5` when `DS:6265` |
| `12c4:023c` | `fmap_wp_text(i)` → far char * | `wp_message(i)` (shell_data `fltplan`); if the message tables `DS:5272/5276` exist: the text between the first and second '\|' of the entry (terminated at the second) |
| `12c4:02d4` | `fmap_fill_waypoints(dst, from_file)` | not from a file: `2a85:0231`, `fltplan_sim_off`, `fltplan_build`, `2a85:02c1`, `msgs = fltplan_messages()`; count = `DS:62E1` (−1 for CAP, type 1); each: 12-byte waypoint `DS:62E7 + 12i`, text = msgs[i] or `fmap_wp_text(i)` |
| `12c4:0377` | `fmap_prepare(from_file)` → `DS:0E10` | allocates and fills both arrays |
| `12c4:03cc` | `fmap_release(from_file)` | frees; `fltplan_free()` unless from a file |

## 6. Career decision (`decision.c`, `144e`, screen 47 `CLOUDS`/`DECISION`, table `4c2a:0011`) — V

"You've reached the end of <campaign set> Campaign Set — You may: …". `DS:4EF2` = variant =
`(end_of_set ? 2 : 0) + (other_sets ? 1 : 0)`.

Items: 0 (55,52,210,h) `draw_riveted_panel`, label str 8 "CAREER DECISION"; 1 (15,19,180,32)
`dec_draw_text`; 2, 3 (15, y, 180, 13) option buttons; 4 (15,87,180,13) str 9 "RETIRE". Buttons
`dec_btn_cb`.

Per-variant tables: window h `DS:0EBC[v]` = 65, 80, 66, 89; button y `DS:0EC4[3v + i]` (i = 0..2 for
items 2, 3, 4; 0 = hidden) = (30,0,45) (30,45,60) (48,0,0) (57,0,72); labels of items 2, 3
`DS:0ED0[2v + i]` = (0, −1) (0, 3) (2, −1) (1, −1) → "CONTINUE WITH CURRENT CAMPAIGN SET",
"TRANSFER TO ANOTHER CAMPAIGN SET", "CONTINUE", "CONTINUE IN ANOTHER CAMPAIGN SET"; results of
item 2 `DS:0EE0[v]` = 2, 2, 0, 1; text line ids `DS:0EE4..0EEA` = 4, 5, 6, 7.

| Address | Name | Behaviour |
|---|---|---|
| `144e:0004` | `dec_draw_text` | FONT3; up to 4 far lines `DS:4EF3[k]`, each `text_engrave(C1h, B1h, C0h)` centred, 9 px apart |
| `144e:0082` | `dec_btn_cb` | `btn_small_cb(0)` → `DS:5FD2` = 0 for RETIRE (item 4), 1 for item 3, `DS:0EE0[v]` for item 2; result 1 |
| `144e:00ca` | `dec_layout()` | window h; for i < 3: y = table; 0 → item mask/flags 0 (hidden) else mask 74h, flags 82h, and label for i < 2; lines: v < 2: {"You may:"}; else {"You've reached the end of", name of `CSET<DS:4779>.DAT` (first 80 bytes, farmalloc copy; fatal F4h if missing), "Campaign Set", + "You may:" when v == 3}; `hs_default_links(4c2a:0011, 5)` |
| `144e:027b` | `dec_frame` | dispatch + present |
| `144e:029c` | `career_decision(end_of_set, other_sets)` → choice | `DS:4EF2 = …`; `screen_show(47, E5h, 1)`; `dec_layout()`; table (5); `hs_draw_all()`; `menu_run`; `ui_busy()`; returns `DS:5FD2` (0 retire, 1 transfer, 2 continue) — Esc leaves `DS:5FD2` unchanged (L: whatever the caller preset). Caller `0874:11ff` |

## 7. Custom missions (`custmiss.c`, `147e`, screen 60 `PARTS`/`CUSTMISS`, table `4c32:0011`) — V

Lists `CMS\*.CMD` files (a mission-builder format; **none are shipped**, so the fly-menu button
is hidden: `custmiss_exist` `147e:0935`). For each mission `<name>.CMT` (in `CMS\`, work dir first)
holds a 27-byte header (u16 aircraft, char[25] title) and up to 500 bytes of description.

Items: 0 (7,31,306,75) `cm_draw_window` (label 0 "FLY CUSTOM MISSION"); 1 (11,4) str 1 "SELECT
CUSTOM MISSION TO FLY:", 2 (192,4) str 2 "PLANE TYPE" (`cm_draw_label`); 3 (10,12,255,55) `lbox_draw`;
4 (271,11,25,56) `cm_draw_scroll`; 5, 6 arrows; 7 (1,79,304,68) `cm_draw_desc`; 8–10 (−3/102/207,
150, 102,17) str 3 RETURN TO MAIN, 4 REALISM PANEL, 5 BEGIN MISSION (`cm_btn_cb`).

State: `DS:4F15` count, `DS:4F0D` near array of names (9 bytes each at `DS:4F0F`), `DS:4F13`
first entry of the 16-entry header cache (`DS:4F19` aircraft words, `DS:4F1D` 25-byte titles),
`DS:4F11` first entry of the 5-entry description cache (`DS:4F1F`, 500 bytes each), `DS:4F17`
button, `DS:4F1B` "No description." (str 6), `DS:4F04` chosen name.

| Address | Name | Behaviour |
|---|---|---|
| `147e:000c` | `cm_load_headers()` | for i < 16 from `DS:4F13`: `"cms\" + name + ".cmt"`, opened in the work dir `DS:40CA` or as is; missing → aircraft = FFFFh; else reads 27 bytes: aircraft word, title (24 chars + NUL) |
| `147e:011f` | `cm_load_descs()` | for i < 5 from `DS:4F11` (inner code at `147e:0143`, not split by the indexer): same file, reads 527 bytes, takes the text after the header (`strchr`), `strncpy(…, 500)`, NUL at 499 (L) |
| `147e:0225` / `027f` | `cm_page_headers(i)` / `cm_page_descs(i)` | fatal (FFh / 111h) if i is out of range; reload the 16-block (`i/16·16`) / 5-block (`i/5·5`) when i is outside the cached page |
| `147e:02da` | `cm_has_header(i)` | aircraft word < 8000h (fatal 124h if not cached) |
| `147e:0333` / `0382` / `03d3` | `cm_aircraft(i)` / `cm_title(i)` / `cm_desc(i)` | cached values (fatal 132h/140h/14Eh when not cached) |
| `147e:0424` | `cm_draw_window` | `draw_side_riveted_panel()`; `draw_title_bar_for(…, label)` (arguments are two constants: L — the pilot/date words are not meaningful here) |
| `147e:0450` | `cm_draw_label` | FONT3 `text_engrave(label, C1h, B1h, C0h, x, y)` |
| `147e:048e` | `cm_draw_scroll` | `draw_bevel_box()`; C0h outline rect (x+3, y+23, 19, 11) |
| `147e:04bb` | `cm_draw_row(i, y)` | `cm_page_headers(i)`; header present: title (uppercase) at x+3, aircraft name (`2777:00a1`, uppercase) at x+150; else the file name at x+3; item 7 mask := 3 (description redraw) |
| `147e:0560` | `cm_draw_desc` | `cm_page_descs(sel)`; text = header present ? `cm_desc(sel)` : "No description."; box B8h over the item; FONT3; `flow_setup(3, 7, 1)`; `flow_text(text, 1, 0)`; mask := 40h |
| `147e:05f6` | `cm_btn_cb` | `btn_cb()` → `DS:4F17 = 5FDE`; result 2 for RETURN (8) else 1 |
| `147e:061e` | `base_name(dst, src)` | copies up to the first '.' |
| `147e:0648` | `name_cmp(a, b)` | `strcmp(*a, *b)` for `qsort` (`0000:3c66`); note: the result is not returned (AX happens to hold strcmp's value: works by accident) |
| `147e:0664` | `cm_scan(desc_buf, title_buf, aircraft_buf)` | buffers from the caller's stack; `findfirst/findnext("cms\*.cmd")` twice (count, then names); `qsort` by name; caches page 0 |
| `147e:07a1` | `cm_free()` | frees the name arrays |
| `147e:07ba` | `cm_draw_bg` | `screen_clear_panel()` |
| `147e:07c4` | `cm_frame` | dispatch + present |
| `147e:07e5` | `custom_missions()` → name / 0 | `2777:0000` (aircraft load); `DS:4F17 = 10`; `cm_scan` (fatal 27Dh if no file); loop: `lbox_setup(…, count, 8, draw cm_draw_row)`, `lbox_bind(4c32:0011, 3, 5)`, `screen_open(60, cm_draw_bg, 89h, 1)`, `DS:4F1B = str_get(6)`, table (11), focus `DS:4F17`, `r = menu_run(cm_frame)`, `ui_busy()`; REALISM (9) → `realism_run()` and loop; BEGIN (10) → `strcpy(DS:4F04, name)`; RETURN → exit; `cm_free(); 2777:04df`; returns `DS:4F04` for BEGIN else 0 |
| `147e:0935` | `custmiss_exist()` | `findfirst("cms\*.cmd") == 0` |

**Note:** the only caller (`flymenu_run` `0b16:021c`) tests the returned name but both branches
continue the same way: **BEGIN MISSION of a custom mission does nothing** in v1.2 (the
mission-builder hand-off was not finished). Faithful port: keep it; the screen is unreachable with
the shipped data anyway.

## 8. Preflight (`1513`, screen 26 `PREFLITE`, table `4c43:0000`, 32 items) — V (L for the shell_data calls)

Shows the player's aircraft configuration, armament, ordnance loadout (changeable), drop tank,
range, flight roster and formation (changeable), with buttons DECLINE MISSION, REALISM PANEL,
FLIGHT MAP, MISSION BRIEFING, BEGIN MISSION. Strings: `PREFLITE.SCD` (labels) and row 4 of
`MISC.DAT` (loaded as the string table: weapon types, yes/no, units, loadout names 21–31,
roster codes 16…).

| # | Rect | Callback | Label / role |
|---|---|---|---|
| 0 | 4,30,309,130 | `pf_draw_window` `0009` | panel + mission-type tab (str 18 + type) |
| 1 | 11,7,288,119 | `draw_popup_box` | |
| 2, 4, 6, 7, 9, 12, 13, 15, 17, 19, 21, 24 | | `pf_draw_label` `0a0c` | 1 CONFIGURATION, 2 PLANE TYPE:, 3 ARMAMENT, 4 RNDS/GUN, 5 ORDNANCE:, 6 DROP, 7 TANK, 8 RANGE, 9 FLIGHT ROSTER, 10 POSITION, 11 PILOT, 12 FORM.: |
| 3, 18, 20, 22 | | `pf_draw_rule` `0a4a` | underlines: C7h at y, B1h at y+1 |
| 5 | 69,22,96,11 | `pf_draw_plane` `01d0` | aircraft name |
| 8 | 15,49,150,24 | `pf_draw_guns` `0208` | armament list |
| 10 | 72,76,93,14 | `pf_loadout_cb` `0348` | ordnance loadout button |
| 11 | 14,91,151,17 | `pf_draw_ordnance` `0432` | loadout contents |
| 14 | 61,112,21,11 | `pf_draw_tank` `054c` | drop tank yes/no |
| 16 | 113,112,52,11 | `pf_draw_range` `05ba` | range |
| 23 | 175,26,120,37 | `pf_draw_roster` `068c` | flight roster |
| 25 | 205,62,87,14 | `pf_formation_cb` `07c4` | formation button |
| 26 | 175,77,117,46 | `pf_draw_formation` `084f` | formation diagram |
| 27–31 | (−2/104/210, 131), (46/156, 151), 103/107 × 18 | `pf_btn_cb` `09ee` | 13 DECLINE MISSION, 14 REALISM PANEL, 15 FLIGHT MAP, 16 MISSION BRIEFING, 17 BEGIN MISSION |

State: `DS:4F2A` aircraft type, `DS:62C8` loadout (1..10), `DS:62C6` formation, `DS:4F2C`/`DS:4F2D[]`
formation cursor/list (`DS:0F5D` entries), `DS:4F39` drop tank present, `DS:4F3A` initial tank
state, `DS:4F38` player leads the flight (`DS:62CF == 4`), `DS:4F23` = came with a fixed mission
variant (no changes allowed), `DS:4F22` first entry (set by the fly menu), `DS:0F51` plane name,
`DS:0F53:0F55`/`0F57:0F59` range without/with tank (long), `DS:0F4F[11]` loadout names, `DS:0F4D[]`
formation names, `DS:4F28` "n/a" range text, `DS:4F26` `FORMPLNS.BMP`, `DS:0F4B`/`DS:0F4D`/`DS:4F37`
pending messages.

| Address | Name | Behaviour |
|---|---|---|
| `1513:0009` | `pf_draw_window` | `draw_side_riveted_panel()`; the tab rectangle `DS:0F44..0F4A` (x, y, w, h): the background block at (x, y+2) is saved and restored at (x, `DS:0F46`), then lines C2h top, B4h (x+1 … w−1) on the same row, C0h sides, BFh inner sides; `text_engrave(str_get(18 + DS:626C), C1h, B1h, C0h, centred, y+2)` (FONT4) |
| `1513:01d0` | `pf_draw_plane` | `draw_inset_box2()`; FONT3 CCh `DS:0F51` at (x+4, y+3) |
| `1513:0208` | `pf_draw_guns` | `draw_inset_box2()`; n = `2ab3:01c7(DS:4F2A, 0)`; `2ab3:021d(DS:4F2A, 0, types[], ids[])`; `2ab3:02d1(DS:4F2A, rounds[])`; FONT3 CCh; for each i with ids[i] ≥ 0: `"%Fs %Fs"` of `strtab_get(4, types[i] + 2)` and (types[i] == 1 ? `2ab3:061c(id)` : `2ab3:065a(id)`) at (x+4, y+3+7i); `"%d"` rounds right-aligned at x+w−4 |
| `1513:0348` | `pf_loadout_cb` | not activated → mask := 74h; fixed mission (`DS:4F23`) → `DS:0F4D = 1` (message); not leader → `DS:0F4B = 1, DS:4F37 = 0` (message); else: k = `DS:62C8`; repeat k = (k+1) % 11, 0 → 1, until the loadout's ordnance is valid (`2ab3:021d`, first id ≠ −1) and (`DS:4F3A == 0` or `2ab3:0504(aircraft, k)`); `DS:62C8 = k`; label = `DS:0F4F[k−1]`; redraw items 10, 11, 14, 16 |
| `1513:0432` | `pf_draw_ordnance` | `draw_inset_box2()`; loadout `DS:62C8` contents like `pf_draw_guns` (no rounds); an id of 0 = drop tank → `DS:4F39 = 1`; mask := 40h |
| `1513:054c` | `pf_draw_tank` | `strtab_get(4, DS:4F39 == 0)` (yes/no text) at (x+4, y+3); mask := 40h |
| `1513:05ba` | `pf_draw_range` | FONT3 CCh; not a career (`DS:4356 == 0`) → `DS:4F28` text; else `ltoa(DS:4F39 ? range_tank : range)` at x+4 and the unit `strtab_get(4, 13)` right-aligned (width cached in `DS:0F61`) |
| `1513:068c` | `pf_draw_roster` | for each member k of flight 0 (`DS:62C5` record, count at +1Ah): `"%d."` (k+1) at x; member 0 also `strtab_get(4, 15)` at x+10; name at x+52: rec[+0Ah + k] == −1 → pilot name `2550:00a3(rec[+0Eh + 2k])` uppercase, else `strtab_get(4, rec[+0Ah + k] + 16)`; all `text_engrave(C7h, B1h, C0h)`, 7 px rows |
| `1513:07c4` | `pf_formation_cb` | like the loadout button: `DS:4F2C = (DS:4F2C + 1) % DS:0F5D`; `DS:62C6 = DS:4F2D[DS:4F2C]`; label = formation name; redraw item 26 |
| `1513:084f` | `pf_draw_formation` | `draw_inset_box2()`; p = first slot of flight 0 whose code (`DS:62CF[k]`) is 4 (the player), else −1; `2300 = DCh`; lead plane `FORMPLNS[p == 0 ? 0 : 1]` at (x+55, y+4), its number `FORMPLNS[2]` at (x+50, y+3); for member i = 2..n (`DS:62DF`): `2a56:01fa(DS:62C6, i, steps[], &m)` (form.c, the path of moves from the leader); start (x+55, y+4); each step d moves by: 0 (0,−11), 1 (0,+11), 2 (−16,0), 3 (+16,0), 4 (+16,−11), 5 (+16,+11), 6 (−16,−11), 7 (−16,+11) (switch table `1513:09DE`); `FORMPLNS[p == i−1 ? 0 : 1]` there and the number `FORMPLNS[i+1]` at (−5, −1); mask := 40h |
| `1513:09ee` | `pf_btn_cb` | `btn_cb()` → `DS:5FD2 = 5FDE`, result 1 |
| `1513:0a0c` | `pf_draw_label` | FONT3 `text_engrave(label, C7h, B1h, C0h, x, y)` |
| `1513:0a4a` | `pf_draw_rule` | lines C7h (x,y)-(x+w,y), B1h (x,y+1)-(x+w,y+1) |
| `1513:0a99` | `pf_plane_init()` | first entry: `DS:4F2A = DS:62DD`; `DS:0F51` = uppercase copy of the aircraft name; first entry: ranges `2777:03e2(type)` and + `2777:0434(type)` (long) |
| `1513:0b21` | `pf_names_init()` | formation names (`2a56:0185` count → `DS:0F5B`, `2a56:019a(k)`) → `DS:0F4D[]`; item 25 label = name of `DS:62C6`; 11 loadout names `strtab_get(4, 21 + k)` → `DS:0F4F[]`, item 10 label = name of `DS:62C8`; `DS:4F28` = copy of `strtab_get(4, 14)` |
| `1513:0c71` | `pf_formations_init()` | first entry and not fixed: `280a:00af`, `DS:0F5D = 280a:032c(DS:62C5, DS:62C7, DS:6277, DS:4F2D)` (formations allowed for the service/date), `DS:4F2C = 0`, `DS:62C6 = DS:4F2D[0]`, `280a:0431`; fixed: the single current formation |
| `1513:0cd3` | `pf_names_free()` | |
| `1513:0d44` | `pf_draw_bg` | `screen_clear_panel()`; `draw_title_bar_for(DS:62C5, DS:6277, str_get(0) "PREFLIGHT")` |
| `1513:0d68` | `pf_msg_subst()` | returns `str_get(DS:4F37 ? 19 : 20)` of the request table (formation / loadout) |
| `1513:0d8e` | `pf_frame` | dispatch + present; `DS:0F4B` → `req_ok(pf_msg_subst, 18, 8)` (only the flight leader may change it); `DS:0F4D` → `req_ok(0, 22, 8)` (cannot change in this mission); Esc → `DS:5FD2 = 1Bh` |
| `1513:0e05` | `preflight(variant)` | below |
| `1513:0fdc` | `pf_init()` | `hs_default_links(4c43:0000, 32)` |

```
preflight(variant):
  DS:4F23 = (variant >= 0); pf_plane_init(); 2ab3:059a; 2a56:0114      // ordnance / formation data
  strtab_load("misc.dat"); pf_formations_init(); pf_names_init()
  DS:4F26 = bmp_load("formplns.bmp"); DS:4F38 = (DS:62CF == 4)
  if DS:4F22 (first entry): DS:4F39 = DS:4F3A = 2ab3:0504(DS:4F2A, DS:62C8); DS:4F22 = 0
  loop:
    screen_open(26, pf_draw_bg, 396h, 1); hs_set_table(4c43:0000, 32); hs_draw_all(); menu_run(pf_frame); ui_busy()
    1Ch REALISM: strtab_free; realism_run(); reload misc.dat; continue
    1Dh FLIGHT MAP: strtab_free; p = fmap_prepare(variant >= 0 || DS:626B == 2); fltmap_show(p…, DS:626D); fmap_release; reload; continue
    else break
  pf_names_free(); 2ab3:06b7; 2a56:02db; strtab_free(); bmp_free(DS:4F26)
  1Eh MISSION BRIEFING → briefing(variant) (0c1d:03c6: loops back into preflight through its own PREFLIGHT button)
  1Fh BEGIN → DS:43D6 = 1 ; 1Bh DECLINE/Esc → DS:43D6 = 0
```

## 9. Service / nation chooser (`1612`, screen 48 `CLOUDS`/`FLYFOR`, table `4c6f:0000`, 9 items) — V

Mode `DS:4F6A`: 0 or 1 "WHO WILL / YOU FLY FOR?" (services), 2 "VIEW AIRPLANES / FOR WHICH
SERVICE?", 3 "VIEW SHIPS / FOR WHICH NATION?" (nations), 4 "SELECT THE CAMPAIGN SET / TO FLY
FROM" (data sets), 5 "WHO WILL YOU / FLY AGAINST?". Items: 0 (80,55,159,94) side-riveted panel;
1 title `1612:0170`; 2 (24,28) subtitle `1612:02dd` ("SELECT A NATION:" in mode 3, "SELECT A
SERVICE:" otherwise); 3 (16,35,99,37) list; 4 bevel; 5, 6 arrows; 7 CANCEL, 8 ACCEPT (`1612:031f`,
result `5FDE == 8 ? 1 : 2`).

| Address | Name | Behaviour |
|---|---|---|
| `1612:0005` | `ff_build(char *buf)` | 11 row pointers `DS:4F54[k] = buf + 30k`; modes other than 1, 4, 5 load `SFTBTNS0.DAT` themselves; mode 4: data sets from `2008:0022` to `2008:0064` (step `2008:002e`), names `DS:0FA3[set]` ("ACES OF THE PACIFIC", …); else k = 0..11: mode 3 → nations with `0f67:036b(k)`, text `strtab_get(0, 144 + k)`; others → services with `0f67:033b(k)`, text `strtab_get(0, 133 + k)`; empty texts skipped; `DS:4F3E[n] = k`, `DS:4F3C = n` |
| `1612:0170` | `ff_draw_title` | FONT4, `2302 = 3`, two centred engraved lines (strings above) at y+4 and y+14; rivet groups (3 at ±24, 2 at ±16) unless mode 2/3 |
| `1612:02dd` | `ff_draw_subtitle` | FONT3 engraved at x, y |
| `1612:031f` | `ff_btn_cb` | above |
| `1612:0347` | `ff_draw_row(i, y)` | `draw_text(DS:4F54[i], x+5, y)` |
| `1612:0367` | `ff_frame` | dispatch + present |
| `1612:0388` | `fly_for_choose(mode)` → k / FFh | `ff_build(stack buffer 330 bytes)`; `lbox_setup(…, DS:4F3C, 5, draw ff_draw_row)`; `lbox_bind(4c6f:0000, 3, 5)`; `screen_show(48, E4h, 1)`; focus 8; cancel → `DS:0FA2 = FFh` else `DS:4F3E[lbox_selected()]`; `ui_busy()`; returns `DS:0FA2` |

Callers: main menu (modes 2, 3), fly menu (mode 0), and the career parts.

## 10. Career notifications (`1656`) — V

A notification = 5-byte xmalloc'ed record {u8 kind, far char *text}; `050c:01ba` (career events,
shell_ui_debrief) queues them (`queue.c` `2242`); `0542:01c4` shows them after a mission.

| Address | Name | Behaviour |
|---|---|---|
| `1656:0008` | `note_new(kind, str_id)` → rec | text = farmalloc'ed copy of `strtab_get(0, str_id)` |
| `1656:006f` | `note_free(rec)` | |
| `1656:0095` | `note_show(rec)` | switch on kind (table `1656:016D`): 1 → `snd_play(3ECh)`, `tbox_kia(text)`, `snd_stop(3ECh)`; 2 → `award_ceremony(DS:4775, 0, text)` (`0f35:01d8`, shell_ui_career); 3 → same with 1; 4 → `snd_play(3F7h)`, `tbox_inquiry(text)`, `snd_stop(3F7h)`; 5 → `1f7f:0001`, `27f0:0004` (medals), `award_ceremony(DS:4775, 2, text)`, `1f7f:0021`, `27f0:0191`; 6 → `225d:0006` (ranks), `award_ceremony(DS:4775, 3, text)`, `225d:01de`; kinds 2, 3, 5, 6 end with `snd_stop(−1)`; other kinds: nothing; always `note_free(rec)` |

## 11. Hand-offs

* **indexer / all**: code segment `0cfe` (functions `0cfe:000a`, `0cfe:0057`) is missing from
  `ps_functions.json` (classified as far data); `147e:0143` is a separate code block inside
  `147e:011f`.
* **shell_data**: `3d50:0102` is a long integer square root (used by `tbox_fit`); `2a56:01fa` gives
  a formation slot as a list of 8-direction steps from the leader; `2ab3:0504(aircraft, loadout)` =
  drop tank in the loadout; `0f67:033b/036b/02ed` (career part) = service valid / nation valid /
  service → insignia; the custom-mission `.CMT` header layout (u16 aircraft, char[25] title,
  description).
* **sound**: shell ids 3ECh (killed in action) and 3F7h (board of inquiry); `snd_stop(−1)` after
  award ceremonies.

## 12. Open questions

* `147e:0424` passes two unrelated constants as service/date to `draw_title_bar_for` (the
  decompiler shows string addresses): check what insignia appears on the custom-mission screen.
* `2171:000a(DS:0E18)` after a text box — sound/speech of career events (shell_data/sound).
