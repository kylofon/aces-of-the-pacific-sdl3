# shell_ui part S1 — return from the sim, debrief, career events, historic missions, career menu

Target `Game/PS.EXE` (DGROUP `4D08`), Borland C++ 3.0 medium model (far cdecl, first argument at
`[bp+6]`). Main file: `shell_ui.md` (index, flow graph); toolkit: `shell_ui_toolkit.md` (names used
here without re-definition: `hs_*`, `menu_*`, `btn_cb`, `text_engrave`, `screen_show/open`, `req_ok`,
`lbox_*`, `draw_*`, `str_get`, `strtab_*`, `res_name`…). Symbols: `shell_ui_debrief_symbols.csv`
(scratchpad, merged by the owner).

Segments owned (modules):

| Seg | File (far-data assert name / evidence) | Contents |
|---|---|---|
| `050c` | none (uses `DISPLAYS.DAT`; data `DS:0500–0510`) | post-mission message queue: KIA / POW / hospital / friendly fire / medal / promotion |
| `0542` | `shell\simend.c` (far data `4991`) | **`sim_end`**: the return-from-simulator chain; career counters |
| `0583` | `shell\flyhist.c` (far data `4992`) | **FLY HISTORIC MISSION** screen |
| `05fa` | none (far data `49ab`) | **VIEW WHICH?** chooser (airplanes / ships) |
| `0607` | none (far data `49b1`, `CAREER.SCD`) | **CAREER MENU** |
| `0637` | `shell\missdebr.c` (far data `49b8`) | **MISSION DEBRIEFING** screen |
| `0874` | none (`events.evt`, `misc.dat`) — "events.c" | career events (newspapers, rumours, war end), squadron moves, campaign end / next campaign |
| `0cfe` | none — **not in the function index** (code reached only through far pointers) | `display_subst`: the `%a…%x` substitution of the DISPLAYS / DEBRIEF / TEXTBOX texts (§8). Not assigned to any part; specced here because the debrief uses it |

Confidence: **V** verified instruction by instruction in the disassembly, **L** likely (decompile
read, call sequence checked), **G** guess. Unmarked statements inside a V section are V.

Resources: `DISPLAYS.DAT`, `DEBRIEF.DAT`, `OPTIONAL.DAT`, `MISC.DAT`, `SFTBTNS0.DAT` (text tables,
`scripts.md` §2), `EVENTS0.EVT`/`EVENTS<n>.EVT` (§7.1), `OFFICERS.BMP`, `DEBRIEF.BMP`,
`MT_HIST.BMP`, `INSIGNIA.BMP`, fonts `NP_TXT.FNT`, `NP_HDLN.FNT`, `SIMQ_SML.FNT`, `SIMQ_HDL.FNT`,
TTM scripts named by the events (`USPAPER`, `JNPAPER`, `RUMUSA`, `RUMJAP`, `WARENDA/J`, `WARE46A/J`),
screen table ids 22 `MISSDEBR`, 23 `FLYHIST`, 45 `CAREER`, 55 `VWHICH` (toolkit §5.1),
`HIST_*.DAT`, `HISTNM_*.DAT`, `HISTSN_*.DAT` (historic missions, shell_data `1f85`), `MISS<n>.DAT`.

External calls are named by address with a working name; the game-data ones belong to shell_data
(`shell_data.md`), the other screens to the other parts. Sound ids (`snd_play`): **1002** (3EAh,
shell/title music), **1010** (3F2h, career music: flight deck, squadron news), **1004** (3ECh, KIA),
**1015** (3F7h, board of inquiry).

---------------------------------------------------------------------------------------------------

## 0. Globals and structures

### 0.1 Hand-off data read here (layouts: `data.md` §1, `shell_data.md` §3)

| DS | Field | Use here |
|---|---|---|
| `4B86` | SIM.IN +00 roster index | career pilot to reload |
| `4B87` | SIM.IN +01 mode | 0 single/historic, **1 career**, 2/3 mission recorder |
| `4B88` | SIM.IN +02 mission type | debrief group, success table |
| `4B89` | SIM.IN +03 | training sub-type (4 = carrier landing); **enemy ace index** for `%j` (§8) |
| `4B8C` | SIM.IN +06 area | event condition `+17` |
| `4B8E` | SIM.IN +08 player's service | officer portrait, title bar symbol |
| `4B8F` | SIM.IN +09 enemy service | "AIRCRAFT" row flag icon |
| `4227` | SIM.OUT +00 result code (1-based) | debrief sentence, success |
| `4229` | SIM.OUT +02 fate flags | 1 killed, 2 captured, 4 wounded, 10/20/40 friendly fire |
| `422B` | +04 aircraft lost | |
| `422D` | +06 u16[4] | **event ids triggered in the sim** (type-3 events, §7.2) |
| `4235` | +0E | ==1: date jump; also compared with type-4 events |
| `4237`,`4239`,`423B`,`423D` | +10 ground, +12 ships hit, +14 ships sunk, +16 aircraft | player |
| `423F`,`4241`,`4243`,`4245` | +18..+1E same four | player's flight |
| `4247` | +20 merit points | |
| `4249` | +22 mission score | |

Current career pilot copy `DS:4754..47CD` (122-byte record, `shell_data.md` §4): `4775` side group,
`4776` service, `4777` rank, `4778` status (0 active, **1 retired** (captured pilots and pilots who
retire, §7.8), 2 cook, 3 KIA), `4779` campaign, `477B` next-mission date, `477F` current date,
`4784` missions, `4786` successful missions, `4788` counter, `478A` aircraft type, `478C` station,
`478E` squadron (FFFF none), `4790` campaign-part index (FFFF none), `4792` victories, `4794`
friendly-fire incidents, `4795[20]` medals awarded, `47B9` s32 score, `47BD` merit, `47BF` air
kills, `47C1` ships sunk, `47C3` ground, `47C5/47C7/47C9` flight air / ships / ground.
Roster: far `4b4c:000e + 0x7A·i` (count `DS:4A18`); TOPACE count `DS:4341`.

### 0.2 Globals owned by this part

| DS | Type | Name | Meaning |
|---|---|---|---|
| `0500` | s8 (init FF) | `medal_awarded` | medal index awarded this mission, −1 none (`medal_check`) |
| `0501` | s8 (init FF) | `promotion_rank` | new rank this mission, −1 none (`promotion_check`) |
| `0502` | u16 (init 0) | `msg_queue` | near pointer to the message queue, 0 = not built |
| `0512` | u8[12] | `mission_success_bits` | `28 2C E0 16 1F 00 0B 0F 8A 4A 3C 0F` |
| `051E` | u8 | `career_dirty` | 1 while a career result is being processed (see `shell_cleanup`, `shell_ui.md` §3.4) |
| `053A` | u8 | `flyhist_no_missions` | set when the chosen service has no historic mission |
| `053B` | u8 | `flyhist_notice_delay` | one-frame delay before the notice |
| `053C` | char[1] | | `""` (campaign label when there is no campaign) |
| `0550`, `0552` | char[2] | | arrow glyph labels `"\x80"`, `"\x81"` |
| `0582` | u16 | `debrief_text` | near pointer to the debrief sentence (a buffer on `debrief_run`'s stack) |
| `0674` | u8 (init 0) | `evt_squads_loaded` | this module loaded the squadron table (`2624:0902`) |
| `0675` | u8 | `evt_campaign_loaded` | copy of `287b:024c()` / campaign table flag during events |
| `0676` | s8 (init FF) | `evt_text_file` | EVENTS file whose text block is cached |
| `0677` | u16 | `evt_text_cap` | size of the cached text buffer |
| `0679:067B` | far | `evt_text1` | text of box 1 of the current event |
| `067D:067F` | far | `evt_text2` | text of box 2 |
| `0681:0683` | far | `evt_current` | event being played (for the TTM hook) |
| `0685`,`0687`,`0689`,`068B` | u16 | fonts | `NP_HDLN`, `NP_TXT`, `SIMQ_SML`, `SIMQ_HDL` handles (lazy) |
| `068D` | u8 | `evt_line_h` | line height of the last selected event font |
| `068F`,`0691` | u16 | `evt_font1/2` | fonts of box 1 / box 2 |
| `0693` | u8 | `evt_ttm_drew_text` | the TTM tag hook already drew the texts |
| `0956` | char[1] | | `""` (substitution default) |
| `4226` | u8 | `music_changed` | 1 = the shell music was stopped/replaced (restart 1002 later) |
| `424C` | u16 | `insignia_bmp` | frame table of `INSIGNIA.BMP` |
| `424E` | u16 | `mt_hist_bmp` | frame table of `MT_HIST.BMP` |
| `4250` | u16[11] | `flyhist_service_names` | near pointers to 11 × 30-byte copies (on `flyhist_run`'s stack) |
| `4266` | s8 | `flyhist_campaign` | historic campaign record index (−1 none) |
| `4267` | s8 | `flyhist_service` | service chosen (0..10) |
| `4268` | s8 | `flyhist_action` | item to focus / item activated |
| `426A`,`426C` | u16 | | `OFFICERS.BMP`, `DEBRIEF.BMP` frame tables |
| `426E` | u16 | `debrief_values` | near pointer to 12 s32 (on `debrief_run`'s stack) |
| `42C1` | u16 | `career_seed` | `rng_count()` after `rng_seed_time()` (used by `0787:0181`) |
| `42E4` | u16[9] | `evt_fonts` | font table for ids 0..8 (`events_init_fonts`) |
| `42F6` | u16 | `evt_capacity` | capacity (records) of the growing event buffer |
| `42F8` | u16 | `evt_count` | events collected |
| `42FA` | u16 | `evt_station_name` | near pointer to the current station name (**a local of `career_continue`**) |
| `42FC:42FE` | far | `evt_text_buf` | cached text block of an EVENTS file |
| `4300`,`4302` | u16 | `evt_date_to`, `evt_date_from` | event date window |
| `4304` | u16 | `career_day` | day cursor of the event / squadron processing |
| `43FA` | char[] | `subst_buf` | scratch for `display_subst` (dates, ace and station names) |

### 0.3 Message record (`msg`, 5 bytes, xmalloc; built by `1656:0008`, S5)

`+00 u8 kind` (1..6), `+01 char far *text` (farmalloc'ed copy of `strtab_get(0, id)` of the table
loaded at build time). `1656:0008 msg_new(kind, id)`; `1656:0095 msg_show(m)` shows and frees it
(`1656:006f`). Kinds (from `1656:0095`, S5 owns it): 1 = `snd_play(1004)`, text box "KILLED IN
ACTION" (`1305:044e`), `snd_stop(1004)`; 2 = ceremony `0f35:01d8(DS:4775, 0, text)` (prisoner,
`PRISJAP/PRISUSA`); 3 = ceremony type 1 (`MEDJAP/MEDUSA`: hospital); 4 = `snd_play(1015)`, text box
"BOARD OF INQUIRY" (`1305:0487`), `snd_stop(1015)`; 5 = medal ceremony type 2 (medal tables
`1f7f`/`27f0` opened around it); 6 = promotion ceremony type 3 (ranks `225d` opened around it). After
kinds 2, 3, 5, 6 `snd_stop(−1)`.

### 0.4 Queue (`sys\queue.c`, `2242`, shell_data) — as used

`2242:0005 queue_new()`, `2242:0081 queue_put(q, item)` (fatal if item is 0), `2242:018b
queue_rewind(q)`, `2242:019a queue_at_end(q)`, `2242:0067 queue_next(q)` → item,
`2242:011e queue_free(q)` (frees the nodes, not the items).

---------------------------------------------------------------------------------------------------

## 1. Return from the simulator — `sim_end` (`0542:01c4`, simend.c) — V

Called once by PS `main` (`048e:0259`) when the GCD marker was 3E7h, before the main menu.
When it returns, PS continues into the main menu (`04df:018d`).

```
sim_end():
    DS:4778 = 0                                  // status of the (not yet loaded) pilot copy
    if 4B87 == 1: 051E = 1
    ext_select(DS:4779)                          // 2008:0003: DS:5288 = arg (value still from the image / previous state)
    sim_in_read()                                // 1193:08f6 → DS:4B86 (13 bytes)
    if 4B87 == 2 or 4B87 == 3:                   // mission-recorder modes: no debrief
        snd_play(1002); return
    sim_out_read()                               // 1193:09fe → DS:4227 (36 bytes)
    if DS:4227 == −1: fatal_line(simend.c, 140h)
    if 4B87 == 1:                                // career
        copy 122 bytes far 4b4c:(0x7A·(s8)4B86 + 0Eh) → DS:4754     (SCOPY@)
        DS:4304 = DS:477F + 1
        campaign_load(DS:4779)                   // 287b:0104
        r = career_update(campaign_end_date(DS:4790))     // 287b:03e1; §1.1
        campaign_free()                          // 287b:0556
    m = msg_next()                               // §2 (builds the queue on the first call)
    rng_seed_time(); DS:42C1 = rng_count()       // 24b7:01d1, 24b7:00be
    if m and m.kind == 1:                        // KIA text first, before the debrief
        strtab_load(res_name("optional", −1, "dat"))
        while m and m.kind == 1: msg_show(m); m = msg_next()
        strtab_free()
    snd_play(1002); DS:4226 = 0
    debrief_run(1)                               // §5
    if m:
        snd_stop(1002); DS:4226 = 1
        strtab_load("OPTIONAL.DAT")
        while m: msg_show(m); m = msg_next()
        strtab_free()
    if 4B87 != 1: return
    if DS:4778 != 0:                             // career over (KIA / retired-POW / cook)
        if DS:4226: snd_play(1002)
        09a9:07ee()                              // best.c: top aces / records update (S3)
        career_menu_run()                        // §4
        return                                   // NB: DS:051E is NOT cleared on this path
    if career_after_mission(r):                  // §7.9 → 1: fly the next mission
        DS:051E = 0
        ext_select(DS:4779)
        snd_stop(−1); snd_play(1010)
        2a85:0006; 2ab3:013b; 2624:0902; 2550:0679; 2777:0000   // load stations, ordnance, squadrons, aces, aircraft
        fltdeck_run()                            // 0787:0181 (S2): sets DS:43D6 when FLY was chosen
        if DS:43D6 == 0:
            2777:04df; 2550:073f; 2624:09c4; 2ab3:057f; 2a85:0216   // free them
        else:
            2624:09c4; shell_fly(1)              // 048e:01a0, does not return
    else:
        DS:051E = 0
        if DS:4226: snd_stop(−1); snd_play(1002)
        career_menu_run()
    DS:051E = 0
```

The `ax = 1/0` computed after the fatal call (0542:0229) is the dead tail of the assert macro.

### 1.1 Career counters (V)

| Address | Name | Behaviour |
|---|---|---|
| `0542:0180` | `career_update(end)` → r | `r = 1`; `squad_load()` (`2624:0902`); `career_count_incident()`; `career_status_update()`; if `DS:4778 == 0`: `r = career_date_update(end)`; `career_add_kills()`; `career_add_score()`; `squad_free()` (`2624:09c4`); `pilot_save()` (`0f67:0001`, copies `DS:4754` back to the roster and saves, S4); returns r (byte) |
| `0542:0154` | `career_count_incident()` | if `DS:4229 & 70h`: `DS:4794 += 1` (byte) |
| `0542:000a` | `career_status_update()` | if `4229 & 1`: `4778 = 3`; else if `4229 & 2`: `4778 = 1`, `477F = 477B = enddate_get(DS:4779, 1)` (`1193:0006`); else if `DS:4794 == 3`: `4778 = 2` |
| `0542:004b` | `mission_success(char mtype, int result)` → u8 | `t = mtype`, `r = result`; if `t == 8`: if `r > 8` (signed): `t = 9`, `r −= 8`; else if `t > 8` (signed): `t += 1`; returns `DS:0512[(s8)t] & (u8)(1 << (u8)(r − 1))` (8-bit shift: 0 when r − 1 ≥ 8) |
| `0542:0086` | `career_date_update(u16 end)` → u8 | below |
| `0542:011a` | `career_add_kills()` | u16 adds: `47BF += 423D`; `47C1 += 423B`; `47C3 += 4237`; `4792 += 423D + 423B`; `47C5 += 4245`; `47C7 += 4243`; `47C9 += 423F` |
| `0542:0168` | `career_add_score()` | `(s32)47B9 += (s32)(s16)4249` (cwd, add/adc); `47BD += 4247` |

```
career_date_update(end):
    p = &DS:477B
    if 4229 & 4:  squad_advance(DS:478E, p, DS:477F + 90)      // 2624:043a: hospital, 90 days
    r = (squad_next_mission(DS:478E, p) == 0)                   // 2624:05a6 (byte result; r = 1 when it returns 0)
    if r: DS:477B = DS:477F
    if !(4229 & 4) and DS:477F > end (unsigned): DS:477F = DS:477B = end
    if DS:4235 == 1 and DS:477F < end (unsigned): DS:477F = DS:477B = end
    DS:4784 += 1
    if mission_success(DS:4B88, DS:4227): DS:4786 += 1
    return r
```

`r = 1` means "the squadron has no further mission": it becomes the `squad_done` argument of
`career_after_mission` (§7.9).

---------------------------------------------------------------------------------------------------

## 2. Post-mission messages (`050c`) — V

### 2.1 `msg_next()` (`050c:01ba`) → msg * or 0

```
if DS:0502 == 0:                                      // build the queue once
    strtab_load(res_name("displays", −1, "dat"))      // DISPLAYS.DAT
    q = DS:0502 = queue_new()
    if 4229 & 1:                                      // killed
        k = (4B87 == 1) ? {0:1, 1:2, 2:3}[msg_fame_level()] : 0
        queue_put(q, msg_new(1, k)); goto built
    if 4B87 == 1:
        if 4229 & 2:                                  // captured
            k = {0:4, 1:5, 2:6}[msg_fame_level()]
            queue_put(q, msg_new(2, k)); goto built
        if 4229 & 4: queue_put(q, msg_new(3, 7))      // hospital
    if 4229 & 70h:                                    // friendly fire
        queue_put(q, msg_new(4, 8 + (4B87 == 1 ? (s8)DS:4794 : 0)))
        if DS:4794 == 3: goto built                   // tested in every mode (stale value outside careers)
    if 4B87 == 1:
        m = medal_check();     if m ≥ 0: queue_put(q, msg_new(5, m + 12))
        r = promotion_check(); if r ≥ 0: queue_put(q, msg_new(6, 32))
built:
    strtab_free(); queue_rewind(q)
if queue_at_end(DS:0502): queue_free(DS:0502); DS:0502 = 0; return 0
return queue_next(DS:0502)
```

(The `{…}` maps are switch statements; a fame level outside 0..2 cannot occur.) `DISPLAYS.DAT`
strings: 0 "You were killed in action. R.I.P.", 1–3 KIA by fame, 4–6 POW by fame, 7 hospital
("You're taken to a%e hospital…"), 8–11 "You attacked %f." + 0/1/2/3 incident warnings (11 = "…must
spend the remainder of the war as a cook"), 12–31 the 20 medal citations (medal m → 12 + m), 32 "You
are promoted to %i.".

### 2.2 Helpers

| Address | Name | Behaviour |
|---|---|---|
| `050c:0007` | `msg_fame_level()` → u8 | `v = DS:47BF + (DS:47C1 + DS:47C3) / 2` (signed, `cwd; sub ax,dx; sar` = truncation toward 0); `v < 5` → 0, `v < 30` → 1, else 2 (signed compares) |
| `050c:0035` | `medal_check()` → s8 | below |
| `050c:0147` | `promotion_check()` → s8 | below |

```
medal_check():
    v = DS:4792; DS:0500 = −1
    medals_open()                                   // 27f0:0004
    for m = 0..19:
        medal_req(m, &req)                          // 27f0:0155: req = {victories, air, ground, ships} (s16 ×4)
        if DS:4795[m] == 0 and medal_for_service(m, DS:4776):      // 27f0:010d
            if req.victories != −1 and req.victories <= v: DS:0500 = m; break
            if req.victories == −1 and (4229 & 4) and medal_is_wound(m): DS:0500 = m; break   // 27f0:013c
    if DS:0500 == −1:
        for m = 0..19:
            medal_req(m, &req)
            if DS:4795[m] == 0 and req.victories != −1
               and (DS:423D >= req.air or DS:4237 >= req.ground or DS:423B >= req.ships)
               and medal_for_service(m, DS:4776): DS:0500 = m; break
    if DS:0500 != −1: DS:4795[DS:0500] = 1
    medals_close()                                  // 27f0:0191
    return DS:0500
```

(All compares signed. At most one medal per mission; pass 1 uses the career victories, pass 2 the
mission's own counters.)

```
promotion_check():
    DS:0501 = −1
    ranks_open()                                    // 225d:0006
    top = ranks_last(DS:4776)                       // 225d:018d (byte)
    for (s8) r = DS:4777 + 1; r <= top; r++:        // signed char compare
        if rank_service(r) == DS:4776 and rank_merit(r) <= DS:47BD (signed): DS:0501 = r   // 225d:010f, 225d:0128
    ranks_close()                                   // 225d:01de
    if DS:0501 > −1: DS:4777 = DS:0501
    return DS:0501
```

(Several ranks can be skipped at once: the last qualifying rank wins.)

---------------------------------------------------------------------------------------------------

## 3. VIEW WHICH? (`05fa`) — V

Entry `vwhich_run()` (`05fa:007f`), called by the main menu (`04df:018d`, VIEW VEHICLES).

`screen_show(55, 2Fh, 1)` (background `CLOUDS`, labels `VWHICH.SCD`: 0 "VIEW WHICH?", 1 "AIRPLANES",
2 "SHIPS", 3 "CANCEL"); `hs_set_table(49ab:0000, 4)`; `hs_draw_all()`; `r = menu_run(vwhich_frame)`;
`ui_busy()`; returns `r == 2 ? FFh : (u8)DS:5FD2` (0 airplanes, 1 ships).

| # | Rect | Callback | Mask/flags | Label | Links (u,d,l,r) |
|---|---|---|---|---|---|
| 0 | 85,60,143,90 | `vwhich_draw_window` | 40 / 80 | str 0 | — |
| 1 | 11,20,123,18 | `vwhich_btn_cb` | 74 / 82 | str 1 | 1,1,3,2 |
| 2 | 11,42,123,18 | `vwhich_btn_cb` | 74 / 82 | str 2 | 2,2,1,3 |
| 3 | 11,64,123,18 | `vwhich_btn_cb` | 74 / 82 | str 3 | 3,3,2,1 |

| Address | Name | Behaviour |
|---|---|---|
| `05fa:0003` | `vwhich_draw_window` | `draw_side_riveted_panel(); font_select(FONT4); text_engrave_center(label, C1h, B1h, C0h)` |
| `05fa:0033` | `vwhich_btn_cb` | `if btn_cb()`: item 3 → `menu_set_result(2)`; else `DS:5FD2 = DS:5FDE − 1`, `menu_set_result(1)` |
| `05fa:005e` | `vwhich_frame` | `hs_dispatch(601A, 6018, 2033, 0); hs_present()` |

(No initialiser: the static links are used.)

---------------------------------------------------------------------------------------------------

## 4. CAREER MENU (`0607`) — V

Entry `career_menu_run()` (`0607:011d`); callers: main menu `04df:018d` (CAREER MENU), `sim_end`.

Screen 45: background `MAINMENU` (cached main menu picture), labels `CAREER.SCD` (0 "CAREER MENU",
1 "START A CAREER", 2 "CONTINUE A CAREER", 3 "VIEW BEST CAREERS", 4 "RETURN TO MAIN").
Table `49b1:0000`, 5 items (links made by `career_init` = `hs_default_links(49b1:0000, 5)`, called
from `dialogs_init` `0a71:0191`):

| # | Rect | Callback | Mask/flags | Label |
|---|---|---|---|---|
| 0 | 135,7,172,117 | `career_draw_window` | 40 / 80 | str 0 |
| 1–4 | 13, 22+23k, 146, 18 (rel.) | `career_btn_cb` | 74 / 82 | str 1–4 |

| Address | Name | Behaviour |
|---|---|---|
| `0607:000d` | `career_draw_window` | `draw_titled_panel()`; `draw_rivets(x+3, y+18, 14)`; `draw_rivets(x+w−6, y+18, 14)` |
| `0607:004f` | `career_btn_cb` | `if btn_cb()`: `DS:5FD2 = DS:5FDE`, `menu_set_result(1)` |
| `0607:006d` | `career_frame` | below |
| `0607:02f5` | `career_init` | `hs_default_links(49b1:0000, 5)` |

```
career_frame():
    hs_dispatch(601A, 6018, 2033, 0); hs_present()
    if menu_get_result() == 0: return
    if DS:5FD2 == 2:                                   // CONTINUE
        n = number of roster records i < DS:4A18 with far byte 4b4c:(0x7A·i + 32h) == 0   (status +24h == active)
        if (n != 0 or ext_flag() (2008:0018 = DS:43B5)) and DS:4A18 != 0: return
        req_ok(0, 0, 6 "There are no active pilots. Please start a career.", 8 "OK")
    else if DS:5FD2 == 3 and DS:4341 == 0:             // VIEW BEST CAREERS, empty TOPACE
        req_ok(0, 0, 7 "The top ace list is empty. Please finish a career.", 8)
    else return
    menu_set_result(0); DS:5FD2 = 4                     // keep the menu running
```

(The strings are `REQUEST.SCD` ids, `req_ok` loads it. `DS:43B5` is an extension flag of
`sys\extens.c`: with it, retired pilots may be continued — `REQUEST.SCD` 0/1 "REMAIN RETIRED /
COME OUT OF RETIREMENT"; L.)

```
career_menu_run():
    again = 1
    do:
        screen_show(45, 396h, 1); hs_set_table(49b1:0000, 5); DS:5FD2 = 4; hs_draw_all()
        menu_run(career_frame); ui_busy()
        switch DS:5FD2:
        case 1:                                        // START A CAREER
            if !pilot_new():  break                    // 0ed9:0347 (S4: name entry, service, campaign…)
            2a85:0006; bigmap_show (0d16:0b33, S2); 2ab3:013b; 2550:0679; 2777:0000; 2624:0902
            rng_seed_time(); DS:42C1 = rng_count()
            snd_stop(1002); snd_play(1010)
            fltdeck_run()                              // 0787:0181
            if DS:43D6 == 0: snd_stop(1010); snd_play(1002); 2624:09c4; 2777:04df; 2550:073f; 2ab3:057f; 2a85:0216
            else: 2624:09c4; shell_fly(1)
            again = 0
        case 2:                                        // CONTINUE A CAREER
            if !roster_pick():  goto check_fly         // 13be:086e (S4)
            if (s16)DS:4790 <= −1 and !campsel_run(0): goto check_fly     // 0fa1:02f9 (S4)
            rng_seed_time(); DS:42C1 = rng_count()
            snd_stop(1002); snd_play(1010)
            2a85:0006; 2ab3:013b; 2624:0902; 2550:0679; 2777:0000
            fltdeck_run()
            if DS:43D6 == 0: snd_stop(1010); snd_play(1002); 2777:04df; 2550:073f; 2624:09c4; 2ab3:057f; 2a85:0216
            else: 2624:09c4
            again = 0
          check_fly:
            if DS:43D6: shell_fly(1)                   // also reached when the pick was cancelled (uses the old flag value)
        case 3: best_careers_view()                    // 09a9:058f (S3)
        case 4: again = 0
        default (Esc: DS:5FD2 stays 4): again = 0 — (switch index = 5FD2−1 > 3 → no case; 4 is the preset)
    while again
```

(Switch table `0607:02ed` = {0181, 0220, 02d6, 02dd}; values outside 1..4 fall to the loop test with
`again` unchanged, but `DS:5FD2` is always 1..4 here.)

---------------------------------------------------------------------------------------------------

## 5. MISSION DEBRIEFING (`0637`, missdebr.c) — V

Entry `debrief_run(char check_best)` (`0637:082a`); callers: `sim_end` (1), `09a9:0572` (0: view a
recorded best mission, S3, which restores SIM.IN/SIM.OUT globals from a TOPMISS record first).

### 5.1 What it shows

Palette `MISSDEBR.PAL` (screen 22); the picture `MISSDEBR.SCR` is **not** drawn (a draw function is
given). Labels `MISSDEBR.SCD`: 0 " MISSION DEBRIEFING ", 1 "CONFIRMED VICTORIES", 2 "PERSONAL",
3 "FLIGHT", 4 "MISSION SCORE", 5 "AIRCRAFT LOST", 6 "AIRCRAFT", 7 "SHIPS HIT", 8 "SHIPS SUNK",
9 "GROUND STRIKES", 10 "TOTAL STRIKES", 11 "CONTINUE".

* Background: `screen_clear_panel()` (B8h); title bar `draw_title_bar_for(DS:4B8E, career ? DS:477B :
  0, str 0)`.
* Riveted window 7,29,305×151; officer portrait `OFFICERS.BMP[SIM.IN+08]` in an inset box at
  (24,37); the debrief sentence (FONT3, flowed, `%` substitutions) in 97,35,200×45.
* Left box (score) and right box (confirmed victories) joined into one panel; values right-aligned
  in inset boxes; row labels with `DEBRIEF.BMP` icons.
* One button CONTINUE (136,181,66×18).

### 5.2 Hot-spot table `49b8:0011` (24 items; origin = item 0 = (7,29))

| # | Rect (items ≥1 relative) | Abs. x,y | Callback | Mask/fl | Content |
|---|---|---|---|---|---|
| 0 | 7,29,305,151 | 7,29 | `draw_side_riveted_panel` | 40 | window |
| 1 | 90,6,200,45 | 97,35 | `debrief_draw_text` | 40 | sentence |
| 2 | 15,6,68,55 | 22,35 | `debrief_draw_officer` | 40 | portrait |
| 3 | 15,65,79,83 | 22,94 | `debrief_draw_left_box` | 40 | left box |
| 4 | 93,54,198,94 | 100,83 | `debrief_draw_victories_box` | 40 | right box + labels |
| 5 | 21,73,78,61 | 28,102 | `debrief_draw_score_box` | 40 | score panel + labels |
| 6 | 28,85,63,11 | 35,114 | `debrief_draw_value_box` | 40 | value 0 = mission score |
| 7 | 49,116,21,11 | 56,145 | `debrief_draw_value_box` | 40 | value 1 = aircraft lost |
| 8–12 | 108, 76+14k, 22, 13 | 115,105.. | `debrief_draw_row_label` | 40 / 80 | str 6–10 |
| 13–17 | 215, 76+14k, 21, 11 | 222,105.. | `debrief_draw_value_box` | 40 | values 2–6 (personal) |
| 18–22 | 258, 76+14k, 21, 11 | 265,105.. | `debrief_draw_value_box` | 40 | values 7–11 (flight) |
| 23 | 129,152,66,18 | 136,181 | `debrief_continue_cb` | 74 / 82 | str 11 CONTINUE |

All links are 0 (a single focusable item).

### 5.3 Values (`debrief_build_values`, `0637:060e`)

`DS:426E` points at 12 s32 (each = sign-extended s16):

| k | Value | k | Value |
|---|---|---|---|
| 0 | `4249` mission score | 6 | `[3] + [5]` personal total strikes (ships hit + ground) |
| 1 | `422B` aircraft lost | 7 | `4245` flight aircraft |
| 2 | `423D` personal aircraft | 8 | `4241` flight ships hit |
| 3 | `4239` personal ships hit | 9 | `4243` flight ships sunk |
| 4 | `423B` personal ships sunk | 10 | `423F` flight ground |
| 5 | `4237` personal ground | 11 | `[8] + [10]` flight total strikes |

Item → value: item < 8 → `k = item − 6`; else `k = item − 11`.

### 5.4 Sentence (`debrief_build_text(char *buf)`, `0637:069e`)

```
strtab_load(res_name("debrief", −1, "dat"))            // DEBRIEF.DAT (2-D table: group, index)
g = switch DS:4B88: 0→0, 1→1, 2→2, 3→3, 4→4, 5→(DS:4B89 == 4 ? 10 : 11), 6→5, 7→6, 8→8, 9→9, 10→7;
    other → fatal_line(missdebr.c, 228h)
DS:0582 = buf
if DS:4B88 == 5 and DS:4B89 != 4:                      // training (not carrier landing)
    fstrcpy_n(buf, strtab_get(g, 0)); strtab_free()    // "This has been a%x training mission."
    strtab_load(res_name("optional", −1, "dat"))       // stays loaded for %x while drawing
else:
    fstrcpy_n(buf, strtab_get(g, DS:4227 − 1)); strtab_free()
```

Groups: 0 ace duel (`%j`), 1 squadron dogfight, 2 CAP, 3 sweep, 4 scramble, 5 escort, 6 intercept,
7 kamikaze defence, 8 anti-ship, 9 ground attack, 10 carrier landing, 11 training.

### 5.5 Functions

| Address | Name | Behaviour |
|---|---|---|
| `0637:082a` | `debrief_run(check_best)` | stack: 12 s32 + 300-byte text buffer; `DS:426E = &values`; `DS:426A = bmp_load(res_name("officers",−1,"bmp"))`, `DS:426C = bmp_load("DEBRIEF.BMP")` (`168a:011c`); `debrief_build_values()`; `debrief_build_text(buf)`; `screen_open(22, debrief_draw_bg, B5h, 1)`; `hs_set_table(49b8:0011, 24)`; `hs_draw_all()`; if check_best: `09a9:072e()` (best.c: records the mission in TOPMISS, may show "Congratulations, you ranked number %r…", S3); `menu_run(debrief_frame)`; `ui_busy()`; `bmp_free(426A)`, `bmp_free(426C)` (`168a:04b1`); if `4B88 == 5 && 4B89 != 4`: `strtab_free()` |
| `0637:07d2` | `debrief_draw_bg` | `screen_clear_panel(); draw_title_bar_for(DS:4B8E, 4B87 == 1 ? DS:477B : 0, str_get(0))` |
| `0637:0809` | `debrief_frame` | `hs_dispatch(601A, 6018, 2033, 0); hs_present()` |
| `0637:05f6` | `debrief_continue_cb` | `if btn_cb(): menu_set_result(1)` (Esc also ends `menu_run`) |
| `0637:000e` | `debrief_draw_text` | `font_select(FONT3)`; `2302 = 1`; `flow_setup(3, 8, 1)`; `flow_text(DS:DS:0582, 1, display_subst)` (`0cfe:0057`, §8) in the item rect |
| `0637:004d` | `debrief_draw_officer` | `draw_inset_box2()`; `draw_bitmap(OFFICERS[(s8)DS:4B8E], x+2, y+2, 0)` |
| `0637:017c` | `debrief_draw_open_box(open)` | box B8h filled x,y,w,h; `rect_save`; R = x+w, B = y+h; if open ≠ 0: lines C2h (x+1,y)-(R,y), C3h (x+1,y+1)-(R,y+1); if open ≠ 1: C0h (R,y+1)-(R,B−1), C3h (R−1,y+1)-(R−1,B−1); if open ≠ 3: C0h (x,y+1)-(x,B−1), C3h (x+1,y+1)-(x+1,B−1); if open ≠ 2: C1h (x,B)-(R,B), C3h (x,B−1)-(R,B−1); `rect_restore` (open: 0 top, 1 right, 2 bottom, 3 left) |
| `0637:02cf` | `debrief_draw_left_box` | `open_box(1)`; B8h lines (x+w, y)-(x+w, y+h) and (x+w−1, y+1)-(x+w−1, y+h−1) |
| `0637:032c` | `debrief_draw_victories_box` | `open_box(3)`; B8h line (x,y)-(x, y+h−2); `yj = item0.y + item3.y` (= 94); C3h (x+1, yj−1)-(x+1, y+1); C0h (x, y+1)-(x, yj−1) (left edge only above the left box); `debrief_draw_victory_labels()`; C1h (x+13, y+19)-(x+193, y+19); B1h (x+13, y+20)-(x+193, y+20) |
| `0637:0089` | `debrief_draw_victory_labels` | FONT4: str 1 engraved (C1h, B1h, C0h) at `text_center_x(s, x, w)`, y+3 (item 4 rect); FONT3: `ly = item0.y + item13.y − 10` (= 95): str 2 at `item0.x + item13.x − 8` (214), str 3 at `item0.x + item18.x − 4` (261) |
| `0637:04d8` | `debrief_draw_score_box` | `draw_popup_box(); debrief_draw_score_labels()` |
| `0637:040d` | `debrief_draw_score_labels` | FONT3; `lx = item0.x + item5.x` (28), width `item5.w` (78): str 4 centred at y `item0.y + item6.y − 7` (107), str 5 centred at y `item0.y + item7.y − 7` (138); engraved C1h, B1h, C0h |
| `0637:0567` | `debrief_draw_value_box` | `draw_inset_box2(); debrief_draw_value()` |
| `0637:04e6` | `debrief_draw_value` | k from the item (§5.3); FONT3; `2300 = CCh`; `ltoa(values[k], s, 10)`; `draw_text(s, x + w − text_width(s) − 3, y + 3)` (flags `2302` as left by the previous drawing: transparent) |
| `0637:0575` | `debrief_draw_row_label` | icon `i = (item == 8) ? side_group(DS:4B8F) + 4 : item − 9` (`0f67:02ed`: 0 Japan, 1 US → frames 4/5 = the enemy nation's flag; 0 ships hit, 1 ships sunk, 2 ground, 3 total); `draw_inset_box2()`; `draw_bitmap(DEBRIEF[(s8)i], x, y, 0)`; FONT3 `text_engrave(label, C1h, B1h, C0h, x+28, y+3)` |
| `0637:060e` | `debrief_build_values` | §5.3 |
| `0637:069e` | `debrief_build_text(buf)` | §5.4 |

Transitions: CONTINUE / Enter / Esc → returns to the caller.

---------------------------------------------------------------------------------------------------

## 6. FLY HISTORIC MISSION (`0583`, flyhist.c) — V

Entry `flyhist_run()` (`0583:03c2`), called by the single-mission menu `0b16` (`0b16:025a`, S3).
Historic data (shell_data `sys\historic.c`, `1f85`): `hist_open` `1f85:00b7` (`HIST_<n>.DAT`
records: word +0 campaign id; list of 8-byte entries {+0 name id, +2 `MISS<n>` number, +4
`MT_HIST.BMP` frame, +6 service}), `histnm_open` `1f85:043b`, `histsn_open` `1f85:067b`, closes
`04bd`/`06fd`/`0139`; `hist_count` `014d`, `hist_campaign_id(c)` `0157`, `hist_has_service(c, s)`
`0359`, `hist_count_service(c, s)` `039f`, `hist_nth_of_service(c, s, i)` `03e9` → entry index,
`hist_entry_name(c, e)` `01f2`, `hist_entry_miss(c, e)` `024b`, `hist_entry_pic(c, e)` `02a5`,
`histnm_text(id)` `073b` and `histsn_text(id)` `07f5` → far strings.

### 6.1 What it shows

Palette `FLYHIST.PAL` (screen 23, labels `FLYHIST.SCD`: 0 "CAMPAIGN:", 1 "SERVICE:", 2 "SELECT
MISSION:", 3 "RETURN TO MAIN", 4 "REALISM PANEL", 5 "BEGIN MISSION", 6 " HISTORIC MISSIONS ");
the draw function paints `screen_clear_panel()` and the title bar `draw_title_bar_for(1, 0, str 6)`.
A riveted window with the service insignia at both ends of the title bar, the campaign button, the
service button, a 5-row mission list with scroll arrows, the mission picture, the synopsis box, and
three buttons at the bottom.

### 6.2 Hot-spot table `4992:0010` (17 items; origin (16,37))

| # | Rect | Abs. | Callback | Mask/fl | Label | User | Links u,d,l,r |
|---|---|---|---|---|---|---|---|
| 0 | 16,37,289,97 | 16,37 | `draw_side_riveted_panel` | 40 | — | | |
| 1 | −4,−36,45,35 | 12,1 | `flyhist_draw_insignia` | 40 | | | |
| 2 | 245,−36,45,35 | 261,1 | `flyhist_draw_insignia` | 40 | | | |
| 3 | 15,10,36,6 | 31,47 | `flyhist_draw_label` | 40 | "CAMPAIGN:" (DS:053D) | | |
| 4 | 63,4,211,18 | 79,41 | `flyhist_btn_cb` | 74 / 02 | campaign name | 1 | 4,4,14,6 |
| 5 | 16,31,41,6 | 32,68 | `flyhist_draw_label` | 40 | "SERVICE:" (DS:0547) | | |
| 6 | 63,27,131,14 | 79,64 | `flyhist_service_btn_cb` | 74 / 02 | service name | 0 | 6,6,4,10 |
| 7 | 23,46,117,6 | 39,83 | `flyhist_draw_label` | 40 / **00** | **0002** | | |
| 8 | 15,53,147,36 | 31,90 | `lbox_draw` | 5C | list body | | |
| 9 | 169,45,25,45 | 185,82 | `flyhist_draw_scroll_frame` | 40 | | | |
| 10 | 172,49,19,18 | 188,86 | `lbox_arrow_cb` | 7C / 02 | `"\x80"` (DS:0550) | | 10,10,6,11 |
| 11 | 172,68,19,18 | 188,105 | `lbox_arrow_cb` | 7C / 02 | `"\x81"` (DS:0552) | | 11,11,10,16 |
| 12 | 201,26,73,63 | 217,63 | `flyhist_draw_picture` | 40 | | | |
| 13 | 4,103,282,35 | 20,140 | `flyhist_draw_synopsis` | 40 | | | |
| 14 | −12,144,102,17 | 4,181 | `flyhist_btn_cb` | 74 / 82 | str 3 RETURN TO MAIN | 3 | 14,14,15,4 |
| 15 | 93,144,102,17 | 109,181 | `flyhist_btn_cb` | 74 / 82 | str 4 REALISM PANEL | 3 | 15,15,16,14 |
| 16 | 198,144,102,17 | 214,181 | `flyhist_btn_cb` | 74 / 82 | str 5 BEGIN MISSION | 3 | 16,16,11,15 |

Item 7's label is the near pointer 2 without flag 80h: it points at DGROUP bytes `00 00` (empty
string), so **"SELECT MISSION:" is never drawn** (it was meant to be string id 2). Up/Down do not
move the focus; Tab/Shift-Tab (and Left/Right) cycle 4 → 6 → 10 → 11 → 16 → 15 → 14 → 4. The
initialiser `flyhist_init` (`0583:075a`, `hs_default_links(4992:0010, 17)`) is **never called**
(no reference; `dialogs_init` does not list it): the static links above apply.

### 6.3 Flow

```
flyhist_run():
    DS:424E = bmp_load(res_name("mt_hist", −1, "bmp")); DS:424C = bmp_load("INSIGNIA.BMP")
    if either is 0: fatal_line(flyhist.c, 191h)
    strtab_load(res_name("sftbtns", 0, "dat"))                 // SFTBTNS0.DAT
    for i = 0..10: DS:4250[i] = &local[30·i]; fstrcpy_n(DS:4250[i], strtab_get(0, 85h + i))
    strtab_free()
    campaign_load(FFh)                                         // 287b:0104: all campaigns
    hist_open(); histnm_open(); histsn_open()
    DS:4268 = 10h (BEGIN); DS:4267 = 0; flyhist_find_campaign()
loop:
    n = (DS:4266 > −1) ? hist_count_service(DS:4266, DS:4267) : 0
    screen_open(23, flyhist_draw_bg, 396h, 1)
    lbox_setup(0, 0, n, 5, fmt = NULL, draw = flyhist_draw_row)
    lbox_bind(4992:0010, 8, 10)
    hs_set_table(4992:0010, 17); hs_focus(DS:4268); hs_draw_all()
    menu_run(flyhist_frame); ui_busy()
    switch DS:4268:
    6:  (service) svc = DS:4267; camp = DS:4266
        s = choose_service(0)                                  // 1612:0388 (S5)
        if s > −1 (signed): DS:4267 = s; flyhist_find_campaign()
             DS:053A = (DS:4266 == −1); if DS:053A: DS:4267 = svc; DS:4266 = camp
        else DS:053A = 0
    4:  (campaign) c = choose_campaign(DS:4267)                 // 12a7:010d (S5)
        if c > −1: DS:4266 = c
    0Eh: goto quit                                             // RETURN TO MAIN (or Esc)
    0Fh: DS:626B = 0; DS:62C5 = DS:4267; realism_run()         // 0a8d:07cb (S3), MREAL.PRF
    10h: if DS:4266 <= −1: break
        m = hist_entry_miss(DS:4266, lbox_selected())
        snario_load(res_name("MISS", m, "DAT"), 1)             // 1f06:015c; then 1f06:0269, 1f06:0782 (file → memory)
        DS:626B = 2 (historic mission kind); DS:62C5 = DS:4267 (player service)
        ext_select(m > 58 ? 1 : 0)                             // MISS59+ come from the 1946 add-on
        histnm_close; histsn_close; hist_close; campaign_free; bmp_free(424C); bmp_free(424E)
        2624:0902; 2550:0679; 2ab3:013b; 2777:0000
        hist_brief_run(m)                                      // 0c1d:03c6 (S3: briefing / pre-flight)
        2777:04df; 2ab3:057f; 2550:073f; 2624:09c4
        if DS:43D6: shell_fly(0)                               // does not return
        farfree(DS:5272:5274) if set, = 0; farfree(DS:5276:5278) if set, = 0
        3164:3602()                                            // shell_data: free mission data
        return
    goto loop
quit:
    histnm_close; histsn_close; hist_close; campaign_free; bmp_free(424C); bmp_free(424E)
```

### 6.4 Functions

| Address | Name | Behaviour |
|---|---|---|
| `0583:0237` | `flyhist_find_campaign()` | `DS:4266 = −1`; for c = 0 .. `hist_count()`−1: if `hist_has_service(c, DS:4267)`: `DS:4266 = c`, stop |
| `0583:0345` | `flyhist_frame()` | `hs_dispatch(601A, 6018, 2033, 0); hs_present(); edit_poll()` (harmless: the list box's hidden text field); if `DS:053A`: if `DS:053B`: `req_ok(0, 0, 23 "There are no historic missions in the modules on disk for the service you selected.", 8)`, `DS:4268 = 6`, `menu_set_result(1)`, `DS:053B = 0` (→ the service chooser opens again); else `DS:053B = 1` (first frame: let the screen appear). Else: `DS:053B = 0`; if `menu_get_result() == 2` (Esc): `DS:4268 = 0Eh` |
| `0583:0009` | `flyhist_btn_cb()` | if item `user == 1` (campaign button): label = `DS:4266 > −1 ? campaign_name(hist_campaign_id(DS:4266))` (`287b:026e`, near string) `: ""` (DS:053C); `if btn_cb()`: `DS:4268 = DS:5FDE`, `menu_set_result(1)` |
| `0583:005f` | `flyhist_service_btn_cb()` | label = `DS:4250[DS:4267]`; `if btn_small_cb(0)`: `DS:4268 = DS:5FDE`, result 1 |
| `0583:009f` | `flyhist_draw_label()` | FONT3; `text_engrave(label, C7h, B1h, C0h, x, y)` |
| `0583:0095` | `flyhist_draw_scroll_frame()` | `draw_bevel_box()` |
| `0583:00dd` | `flyhist_draw_insignia()` | `tile_fill_rect(); draw_header_panel()`; f = `INSIGNIA[DS:4267]`; `draw_bitmap(f, x + (w>>1) − ((f.w − 4)>>1), y + (h>>1) − (f.h>>1), 0)` (arithmetic shifts) |
| `0583:014f` | `flyhist_draw_picture()` | `draw_inset_box2()`; if `DS:4266 > −1`: `draw_bitmap(MT_HIST[hist_entry_pic(DS:4266, lbox_selected())], x+2, y+2, 0)`; item mask := 40h |
| `0583:01a9` | `flyhist_draw_synopsis()` | `rect_grow(4); draw_popup_box(); rect_shrink(4)`; if `DS:4266 > −1`: FONT3, `2302 = 1`, `flow_setup(−3, 8, 1)` (engraved), `flow_text(histsn_text(hist_entry_name(DS:4266, lbox_selected())), 1, NULL)`; item mask := 40h |
| `0583:027c` | `flyhist_draw_row(i, y)` | `e = hist_nth_of_service(DS:4266, DS:4267, i)`; `id = hist_entry_name(DS:4266, e)`; fatal (flyhist.c 148h) if id < 0; `draw_text(fstrcpy_n(DS:419A, histnm_text(id)), x + 4, y)` (x of the body item; colour set by `lbox_draw`); items 12 and 13 masks := 3 (picture and synopsis repaint on the next dispatch) |
| `0583:0322` | `flyhist_draw_bg()` | `screen_clear_panel(); draw_title_bar_for(1, 0, str_get(6))` |
| `0583:075a` | `flyhist_init()` | `hs_default_links(4992:0010, 17)` — unreferenced |

Quirk (V): the list rows map row i → the i-th entry *of the chosen service*
(`hist_nth_of_service`), but the picture, the synopsis and the mission flown use
`lbox_selected()` directly as the entry index. It only works because each `HIST_` campaign record
holds entries of one service (the shipped data: e.g. Midway has a US record and a Japanese record);
keep it as is.

---------------------------------------------------------------------------------------------------

## 7. Career events and campaign progress (`0874`, "events.c") — V

### 7.1 Event files `EVENTS<n>.EVT` (verified against `EVENTS0.EVT` 41 records and `EVENTS1.EVT` 22)

`u16 n; n × 66-byte records; u16 text_len; text_len bytes` (NUL-terminated strings, offsets
relative to the text start). File n = 0 (base game) and one per installed extension module
(`sys\extens.c`: `2008:00a8(fh[9], "events", "evt")` opens `EVENTS0.EVT` (or `EVENTS.EVT`) and
`EVENTS<m>.EVT` for each module m; `2008:0022/002e/0064` iterate; `2008:01d3` closes).

| Off | Type | Field |
|---|---|---|
| 00 | u8 | trigger type 1..5 (all shipped events: 5) |
| 01 | u16 | type 5: side-group mask (bit `DS:4775`; 1 = Japan, 2 = US; 0 = any); types 1–4: the id to match |
| 03 | u16 | service mask (bit `DS:4776`; 0 = any) |
| 05 | u16 | squadron mask (bit `2624:00cf(DS:478E)`; 0 = any) |
| 07 | u16 | first date (day number); also the sort key |
| 09 | u16 | last date (0 = open) |
| 0B,0D | s16 | missions min / max (−1 = no limit) vs `DS:4784` |
| 0F,11 | s16 | air kills min / max vs `DS:47BF` (e.g. rumour 8 "our newest Ace!": min 5) |
| 13,15 | s16 | ground strikes min / max vs `DS:47C3` |
| 17 | s16 | area (−1 any) vs SIM.IN +06 `DS:4B8C` |
| 19 | u8 | event id: bits 0–5 index, **bits 6–7 = file number n** (EVENTS1 ids are 40h+); the "already seen" key (`0f67:021a`) |
| 1A | char[9] | TTM script name |
| 23 | u16 | last frame of the script (abort jumps to frame last−1) |
| 25,27,29,2B | s16 | box 1 x, y, w, h |
| 2D | u8 | 1 = draw a tiled frame panel behind box 1 (rumours) |
| 2E | u16 | text 1 offset (FFFF none) |
| 30 | u16 | font id of text 1 (§7.4) |
| 32 | u8 | colour of text 1 (FFh in the data) |
| 33 | u8 | unused (FFh) |
| 34,36,38,3A | s16 | box 2 x, y, w, h (h unused) |
| 3C | u16 | text 2 offset (FFFF none) |
| 3E | u16 | font id of text 2 |
| 40 | u8 | colour of text 2 |
| 41 | u8 | unused |

Newspapers: box 1 = article (font 7 `NP_TXT`), box 2 = headline (font 8 `NP_HDLN`); rumours: box 1
only, font 9 (→ FONT3 engraved), frame panel; war end: no text (TTM only).

### 7.2 Selection

| Address | Name | Behaviour |
|---|---|---|
| `0874:0291` | `event_matches(evt far *e)` → u8 | `switch e.type − 1` (table `0874:032d`): 1 → `(s16)(s8)DS:0501 == e.+01` (promotion this mission); 2 → `(s16)(s8)DS:0500 == e.+01` (medal); 3 → for k = 0..3 while `DS:422D[k] != −1`: `DS:422D[k] == e.+01` → 1 (SIM.OUT +06 list); 4 → `e.+01 == DS:4235`; 5 → `event_conditions(e)`; other → 0 |
| `0874:011d` | `event_conditions(evt far *e)` → u8 | id = `e.+19`; reject if `event_seen(id)` (`0f67:021a`); if `e.+01` and not `(e.+01 >> DS:4775) & 1` reject; same `e.+03` with `DS:4776`; reject unless `e.+07 <= DS:4300` (unsigned) and (`e.+09 == 0` or `e.+09 >= DS:4302`); each s16 pair: `+0B != −1 && +0B > DS:4784`, `+0D != −1 && +0D < DS:4784`, `+0F`/`+11` vs `DS:47BF`, `+13`/`+15` vs `DS:47C3` (signed) → reject; `+17 != −1 && +17 != (u8)DS:4B8C` → reject; if `e.+05 != 0`: (squadrons loaded if `DS:0674 == 0` → `2624:0902`, `0674 = 1`) reject unless bit `2624:00cf(DS:478E)` of `e.+05`; accept: `event_mark_seen(id)` (`0f67:0252`) — **an event is marked seen when collected**, before it is played |
| `0874:0337` | `evt_read_u16(FILE *f)` | `fread(&w, 2, 1, f)` (`0000:08a0`) → w |
| `0874:035d` | `evt_read_matching(buf far, f, at, u16 n)` → kept | for i < n (unsigned): `fread(rec, 66, 1, f)`; if read and `event_matches(rec)`: copy to `buf[at + kept]`, kept++ |
| `0874:03cc` | `evt_load_file(buf far, f, have)` → buf' | if `f == 0`: return buf. `n = evt_read_u16(f)`; if buf is NULL: `DS:42F6 = 0`; `need = have + n`; if `need > DS:42F6` (unsigned): `DS:42F6 = (need + 10) − (need + 10) % 10`; `nb = farmalloc(DS:42F6 · 66)`; copy `have` records; `farfree(buf)` if not NULL; else `nb = buf`. `DS:42F8 += evt_read_matching(nb, f, have, n)`; return nb |
| `0874:04b0` | `events_collect()` → far | `DS:42F8 = 0`; `2008:00a8(fh, "events", "evt")`; `i = 0` (`2008:0022`); while `2008:0064() >= i` (signed): `buf = evt_load_file(buf, fh[i], DS:42F8)`; `i = 2008:002e()`. `2008:01d3(fh)`. If `DS:42F8`: exact copy into `farmalloc(42F8 · 66)`, `farfree(buf)`, return it; else return NULL (**the growth buffer leaks when files had records but none matched**) |
| `0874:05aa` | `event_compare(evt *a, evt *b)` → int | `a.type != b.type` → `a.type − b.type`; type 5: `a.+07 != b.+07` → `a.+07 − b.+07` else `a.+09 − b.+09`; other types: `a.+01 − b.+01` (16-bit subtractions) |
| `0874:05fb` | `events_sort(list far)` | near copy (`xmalloc(42F8·66)`), `qsort(copy, 42F8, 66, event_compare)` (`0000:3c66`), copy back, `xfree` |
| `0874:0691` | `events_collect_sorted()` → far | `l = events_collect()`; if `DS:42F8`: `events_sort(l)`; return l |

### 7.3 `events_run(u16 from, u16 to, char advance)` (`0874:0ec5`)

```
DS:4302 = from; DS:4300 = to; d = from
l = events_collect_sorted()
i = 0
while i < DS:42F8 and l[i].type != 5: event_play(&l[i]); i++           // triggered events first
while i < DS:42F8:                                                     // dated events, by date
    if advance: while l[i].+07 > d (unsigned): career_squadron_day(); d++
    event_play(&l[i]); i++
if advance: while DS:4304 <= DS:477F (unsigned): career_squadron_day(); DS:4304++
events_free(l)
```

(`career_squadron_day` looks at `DS:4304`, not at d: inside the second loop it is called repeatedly
for the same day; faithful behaviour.)

### 7.4 Playing one event

| Address | Name | Behaviour |
|---|---|---|
| `0874:0b57` | `event_play(evt far *e)` | below |
| `0874:06bc` | `event_load_texts(e)` | `n = (e.+19 >> 6) & 3`; if `n != DS:0676`: `DS:0676 = n`; `f = vol_fopen(res_name("events", n, "evt"), "rb")`; `c = evt_read_u16(f)`; `fseek(f, (u16)(c·66), SEEK_CUR)`; `len = evt_read_u16(f)`; if `DS:0677 < len`: `farfree(42FC:42FE)` if `0677 != 0`, `42FC:42FE = farmalloc(len)`, `0677 = len`; `fread_far(42FC:42FE, 1, len, f)` (`1193:0a46`); `fclose(f)`. Then `DS:0679:067B = text + e.+2E`, `DS:067D:067F = text + e.+3C` (offsets added even when FFFF) |
| `0874:079f` | `event_font(int id)` → handle | 5 → `SIMQ_SML.FNT`, 6 → `SIMQ_HDL.FNT`, 7 → `NP_TXT.FNT`, 8 → `NP_HDLN.FNT` (each `font_load(res_name(name, −1, "fnt"))` once, kept in `DS:0689/068B/0687/0685`); else `DS:42E4[id % 9]` (signed `idiv`) |
| `0874:0e0f` | `events_init_fonts()` | `42E4..42EC = FONT3 (421E), FONT2 (4220), FONT1 (4222), FONT4 (421C), TALK (421A)`; `42EE..42F4 = 0` (called by `dialogs_init` `0a71:01a5`) |
| `0874:0886` | `event_select_fonts(e)` | if `e.+2E != −1`: `DS:068F = event_font(e.+30)`; if `e.+3C != −1`: `DS:0691 = event_font(e.+3E)` |
| `0874:08c8` | `event_set_box1(e, char frame)` | rect = (`e.+25, +27, +29, +2B`); `pages_2314_2312`; if frame: `tile_fill_rect(); draw_frame()` |
| `0874:0901` | `event_draw_box1(e, char present)` | `2302 = 1`; `2300 = e.+32`; `font_select(068F)`; `068D = font_height(068F)` (`16e3:36dc`); `flow_setup(e.+30 >= 9 (signed), 068D, 1)` (ids ≥ 9: engraved style); rect x += 7, y += 4, w −= 14, h −= 8; `2316 = 2318 = 2312`; `flow_text(DS:0679 text1, 1, NULL)`; rect restored; if present: `pages_2312_2314`, `copy_rect(x, y, w, h)` |
| `0874:09b7` | `event_draw_box2(e, char present)` | saves the current rect (box 1); `2302 = 1`; `2300 = e.+40`; `font_select(0691)`; `068D = font_height(0691)`; `flow_setup(e.+30 >= 9, 068D, 1)` (**tests the box-1 font id**, quirk); rect = (`e.+34, +36, +38, +3A`); `2316 = 2318 = 2312`; `hh = (s8)flow_text(text2, 1, NULL)`; if present: `pages_2312_2314`; `copy_rect(e.+34, e.+36, e.+38, hh)`; if `e.+2E != −1`: `copy_rect(saved box-1 rect)` |
| `0874:0aa5` | `event_ttm_text_hook()` | TTM tag callback (slot called via `2221:0107`, sys TTM glue): `e = DS:0681`; `event_set_box1(e, e.+2D)`; box 1 text → `event_draw_box1(e, 0)`; box 2 text → `event_draw_box2(e, 0)`; `2318 = 2310, 2316 = 2312`; `copy_rect(e.+25, e.+27, e.+29, e.+2B + 1)` (work → spare); `3a73:0085(x1, y1, w1, h1, 1, DS:2310, DS:2312, 0, 0, 0)` (video: dissolve the box from the spare page into the work page); `2318 = 2312`; `DS:0693 = 1` |
| `0874:0e40` | `events_free(list far)` | if `DS:42F8`: `farfree(list)`; if `DS:0676 != FFh`: `farfree(42FC:42FE)`; `0677 = 0`, `0676 = FFh`, `0679:067B = 0`; if `0674`: `squad_free()`, `0674 = 0`; `font_free` + clear `0685` and `0687` (the SIMQ fonts `0689/068B` stay loaded) |

```
event_play(e):
    if e.+2E != −1 or e.+3C != −1: event_load_texts(e); event_select_fonts(e)
    pages_2314_2312; screen_clear_black(); pages_2312_2314
    wipe(0, 0, 320, 200)                       // 22ce:0137: copy work→front in 10 passes of every 10th row, 5 timer ticks each
    DS:0681 = e; snd_stop(−1); DS:4226 = 1
    name = copy of e.+1A (9 chars)
    ttm_play(res_name(name, −1, "ttm"), −1, 0, 0, e.+23, ttm_abort_cb (21f4:0018))    // 21f4:0245 (sys)
    if DS:0693: DS:0693 = 0                   // the hook drew the texts during the animation
    else:
        event_set_box1(e, e.+2D)
        if e.+2E != −1: event_draw_box1(e, e.+3C == −1)
        if e.+3C != −1: event_draw_box2(e, 1)
    if e.+2E != −1 or e.+3C != −1: wait_input(10000)    // 2171:000a
```

`ttm_play` (`21f4:0245`, sys part): plays the script from frame 0 until it ends; the abort callback
(`21f4:0018`) stops it when Enter/Esc/Space, a joystick or mouse button is pressed (Alt/Ctrl hot keys
are handled); on abort the player jumps to frame `last − 1` (so the final picture is shown).
`wait_input(t)` (`2171:000a`): `DS:2E3F = t` and loops until the countdown reaches 0 or Enter (1Ch),
Esc (01h), Space (39h), a joystick or mouse button (keys read with `kbd_getkey`, `menu_hotkey`
honoured). 10000 PIT ticks at 236.7 Hz = **42.2 s**.

### 7.5 Squadron news (`career_squadron_day`, `0874:0cd6`)

```
if !DS:0674: squad_load(); DS:0674 = 1
if squad_inactive(DS:478E, DS:4304) (2624:011d, byte != 0): return
st = squad_station(DS:478E, DS:4304)                  // 2624:0256
if st != DS:478C:
    DS:478C = st
    stations_open (2a85:0231); name = str_near(station_name(st))    // 2a85:027c, 24d5:0005
    if strcmp(name, DS:[42FA]) != 0:
        snd_stop(−1); snd_play(1010); DS:4226 = 1
        textbox_movement(misc_relocated_text(buf))   // 1305:0546 "SQUADRON MOVEMENT": MISC.DAT 3 "Your squadron, %p, is being relocated."
        strcpy(DS:[42FA], name)
        stations_close (2a85:02c1); 2a85:0006; bigmap_show (0d16:0b33, S2); 2a85:0216
    else stations_close
ac = squad_aircraft(DS:478E, DS:4304)                 // 2624:0219
if ac != DS:478A:
    DS:478A = ac; snd_stop(−1); snd_play(1010); DS:4226 = 1
    strtab_load("MISC.DAT"); 2777:0000; view_new_aircraft(DS:478A, DS:4776, 1) (0ddd:0cde, S4); 2777:04df; strtab_free()
```

`misc_relocated_text(buf)` (`0874:0c8d`) and `misc_tour_text(buf)` (`0874:00d7`): load `MISC.DAT`,
`fstrcpy_n(buf, strtab_get(0, 3 / 0))`, free, return `DS:buf`.

### 7.6 Squadron choice (`career_pick_squadron(u16 end)`, `0874:0003`)

```
if !DS:0674: squad_load(); DS:0674 = 1
cur = best = DS:478E
for (s8) k = 0; k < squad_count() (2624:002d); k++:
    if campaign_has_squad(DS:4790, k) (287b:0439):
        d = squad_next_active(k, DS:477B + 1, end)      // 2624:0163: first active day in [date, end], 0 none
        if d and (best == cur or rng_below(2) != 0): best = k; bestd = d     // RNG only after a first pick
if best == cur: return −1
squad_advance(best, &DS:477B, bestd)                     // 2624:043a
DS:478A = squad_aircraft(best, DS:477B); DS:478C = squad_station(best, DS:477B)
return best
```

### 7.7 After-mission flow (`career_after_mission(char squad_done)`, `0874:12be`) and helpers

```
career_after_mission(squad_done):
    shell_set_exit_hook(career_exit_hook)               // 227c:0007
    campaign_load(DS:4779); DS:0675 = 1
    end = campaign_end_date(DS:4790)
    cont = DS:477B < end (unsigned); sq = −1
    if squad_done and cont: sq = career_pick_squadron(end); cont = sq > −1
    if cont: career_continue(sq)
    else:    cont = career_campaign_end(end)
    pilot_save(); shell_clear_exit_hook()               // 0f67:0001, 227c:0019
    return cont                                         // 1 → sim_end goes to the flight deck
```

| Address | Name | Behaviour |
|---|---|---|
| `0874:1039` | `career_continue(int sq)` | `wounded = 4229 & 4`; `stations_open`; `fstrcpy_n(buf[80] (local), station_name(DS:478C))`; `DS:42FA = buf`; `stations_close`; `campaign_free()`; `DS:0675 = 0`. If `sq > −1` (transfer): `DS:478E = −1`; if !wounded: `events_run(DS:4304, DS:477F, 0)`; `DS:478E = sq`; squadrons loaded (`0674`); `2777:0000; 2550:0679; 2a85:0006`; `squadinf_run(2)` (`07ba:08c2`, S2: new squadron); `bigmap_show()` (`0d16:0b33`); `2a85:0216; 2550:073f; 2777:04df`. Else if !wounded: `events_run(DS:4304, DS:477F, 1)` (with day advance). Finally if `0674`: `squad_free()`, `0674 = 0` |
| `0874:1270` | `career_campaign_end(u16 end)` → u8 | if `0674`: `squad_free()`, `0674 = 0`; `career_tour_end(end)`; `w = career_war_over()`; `cmptext_close()` (`287b:0686`); `campaign_free()`; `r = career_next_campaign(w)`; if `r == 0`: `DS:4790 = −1`; return r |
| `0874:1113` | `career_tour_end(u16 end)` | `jump = DS:4235 == 1`; `wounded = 4229 & 4`; `saved = DS:478E`; `DS:4788 += 1`; if `DS:477B < end`: `DS:477F = DS:477B = end`; `DS:478E = −1`; if !wounded and !jump: `events_run(DS:4304, DS:477B, 0)`; `DS:478E = saved`; `textbox_campaign_end(misc_tour_text(buf))` (`1305:03f2`: text box titled with the campaign end date: MISC.DAT 0 "You have successfully completed your tour of duty with %p in %q campaign."); `cmptext_open()` (`287b:056a`); `campsel_show_text(cmptext(DS:4790))` (`287b:062a` → `0fa1:0600`, S4) |
| `0874:11a9` | `career_war_over()` → u8 | `w = !campaign_left(DS:477B, DS:4776)` (`287b:04b5`: some campaign starting at or after the date has the service); if w: `e = enddate_get(DS:4779, 1)`; `events_run(min(DS:477B, e), e, 0)` (remaining events up to the war end, e.g. `WARENDA`); return w |
| `0874:11ff` | `career_next_campaign(char w)` → u8 | `c = campset_available(DS:4776, DS:477B, DS:4779)` (`0a41:028d`, S3); `d = decision_run(w, c)` (`144e:029c`, S5); if `d == 1`: `DS:4779 = campset_choose(0)` (`0a41:01c1`); `d = DS:4779 != FFh ? 2 : 0`; if `d == 0`: **`DS:4778 = 1` (retired)**, `09a9:07ee()`, return 0; else `r = campsel_run(0)` (`0fa1:02f9`, S4: squadron assignment), `DS:0675 = 0`, return r |
| `0874:0f7d` | `career_exit_hook()` | run by `shell_exit` if the player quits (Alt-X…) during the events: if `(s16)DS:4790 > −1`: `DS:0675 = campaign_loaded()` (`287b:024c`); if not loaded: `campaign_load(DS:4779)`; if `!0674`: `squad_load()` (flag not set); `end = campaign_end_date(DS:4790)`; if `end <= DS:477B`: `DS:4790 = −1`; else: if `DS:478E == −1` or `squad_inactive(DS:478E, DS:477B)`: `DS:478E = career_pick_squadron(end)`; if −1: `DS:4790 = −1`, skip; else `squad_advance(DS:478E, &DS:477B, DS:477B)`; then `DS:478A = squad_aircraft(478E, 477B)`, `DS:478C = squad_station(478E, 477B)`. Always `pilot_save()` |

`DS:42FA` points into `career_continue`'s stack frame; it is only dereferenced inside that call
(`events_run(…, 1)` → `career_squadron_day`), so the dangling value is harmless.

---------------------------------------------------------------------------------------------------

## 8. Text substitution `display_subst` (unindexed module `0cfe`) — V

`flow_text` substitution callback used by `debrief_draw_text` (`0637:0033`), the award ceremony
(`0f35:0088`) and the text boxes (`1305:0161`, `1305:0208`). Returns a far string (`DS:` pointers
unless noted); the strings from `OPTIONAL.DAT` require that table to be loaded (callers do).

| Address | Name | Behaviour |
|---|---|---|
| `0cfe:0057` | `display_subst(char c)` → far char * | switch `c − 'a'` (0..23, table `0cfe:015f`), other → `""` (DS:0956) |
| `0cfe:000a` | `subst_ace_name()` → char * | `aces_load` (`2550:0679`); `s = ace_name((s8)DS:4B89)` (`2550:0043`, far); `n = (u8)_fstrlen(s)`; `farcopy(DS:43FA, s, n)` (`22ce:026e`, **no NUL copied**: a shorter name keeps the tail of an earlier longer text); `aces_free` (`2550:073f`); returns `DS:43FA` |

| Code | Text |
|---|---|
| `%a` | pilot name `DS:4754` |
| `%b` | `date_text(DS:477F, DS:43FA)` (`284f:021c`) |
| `%e` | `strtab_get(0, (s8)DS:4775)`: " Japanese" / "n American" / … (article glue "a%e hospital") |
| `%f` | `strtab_get(0, 4229 & 10h ? 6 : 4229 & 20h ? 7 : 8)`: "and shot down one of our aircraft" / "one of our ships" / "one of our installations" |
| `%g` | `strtab_get(0, DS:4776 + 9)`: service name ("United States Navy" …) |
| `%h` | `medal_name(DS:0500)` (`27f0:00f5`) |
| `%i` | `rank_name(DS:0501)` (`225d:00f7`) |
| `%j` | `subst_ace_name()` (enemy ace of an ace-duel mission) |
| `%p` | `squad_name(DS:478E)` (`2624:0042`, far) |
| `%q` | `campaign_name(DS:4790)` (`287b:026e`) |
| `%u` | `aircraft_name(DS:478A)` (`2777:00a1`, far) |
| `%v` | `strtab_get(0, (s8)DS:4775 + 20)`: "Japan" / "America" … |
| `%w` | station name: `stations_open`; `fstrcpy_n(DS:43FA, station_name(DS:478C))`; `stations_close`; `DS:43FA` |
| `%x` | `strtab_get(0, (s8)DS:4B89 + 26)`: "n aerial gunnery", " dive bombing", " torpedo bombing", " ground attack" |
| `%c %d %k–%o %r–%t` | `""` |

---------------------------------------------------------------------------------------------------

## 9. Screen flow

Entry points into this part (call sites):

| Caller | → | Function |
|---|---|---|
| PS main `048e:0259` (marker 3E7h) | | `sim_end` `0542:01c4` |
| main menu `04df:0205` (CAREER MENU) | | `career_menu_run` `0607:011d` |
| main menu `04df:020c` (VIEW VEHICLES) | | `vwhich_run` `05fa:007f` |
| single-mission menu `0b16:025a` (historic) | | `flyhist_run` `0583:03c2` |
| best missions `09a9:0572` | | `debrief_run(0)` `0637:082a` |
| `dialogs_init` `0a71:0191`, `0a71:01a5` | | `career_init`, `events_init_fonts` |
| TTM tag glue `2221:010a` | | `event_ttm_text_hook` `0874:0aa5` |
| `shell_exit` (hook) | | `career_exit_hook` `0874:0f7d` |

Edges:

```
PS main --(marker 3E7h, 048e)--> sim_end
sim_end --(mode 2/3)--> [return] --> main menu
sim_end --(KIA message, 0542:02bd)--> msg_show kind 1 (KILLED IN ACTION text box, S5 1305:044e)
sim_end --(0542:02ea)--> MISSION DEBRIEFING (22) --(09a9:072e: best-mission notice)--> …
MISSION DEBRIEFING --(CONTINUE/Enter/Esc)--> sim_end
sim_end --(0542:0321)--> msg_show kinds 2..6 (ceremonies 0f35:01d8, BOARD OF INQUIRY 1305:0487)
sim_end --(single/historic, 0542:0337)--> [return] --> main menu
sim_end --(career over: KIA/POW/cook, 0542:035e)--> 09a9:07ee --> CAREER MENU
sim_end --(career active, 0542:036a)--> career_after_mission
    career_after_mission --> career_continue --> events (TTM newspapers/rumours, text boxes)
                                             --> SQUADRON MOVEMENT text box (1305:0546) + big map (0d16:0b33)
                                             --> new aircraft (0ddd:0cde) ; transfer: squadron info (07ba:08c2) + big map
    career_after_mission --> career_campaign_end --> END OF CAMPAIGN text box (1305:03f2) --> campaign text (0fa1:0600)
                         --> [war over: WAREND events] --> DECISION (144e:029c) --> campaign choice (0a41:01c1)
                         --> squadron assignment (0fa1:02f9)
sim_end --(continue = 1, 0542:03b0)--> FLIGHT DECK (0787:0181) --(FLY: DS:43D6)--> shell_fly(1) → AP
                                                              --(back)--> [return] --> main menu
sim_end --(continue = 0, 0542:040a)--> CAREER MENU
CAREER MENU --(START A CAREER, 0607:0181)--> new pilot (0ed9:0347) --> big map --> FLIGHT DECK --> shell_fly(1) | main menu
CAREER MENU --(CONTINUE, 0607:0220)--> roster (13be:086e) --> [no campaign] campaign selection (0fa1:02f9) --> FLIGHT DECK --> shell_fly(1) | main menu
CAREER MENU --(VIEW BEST CAREERS, 0607:02d6)--> best careers (09a9:058f) --> CAREER MENU
CAREER MENU --(RETURN TO MAIN / Esc)--> caller (main menu, or sim_end's caller → main menu)
VIEW WHICH? --(AIRPLANES 0 / SHIPS 1 / CANCEL FFh)--> main menu (which opens the viewer, S4 view.c)
FLY HISTORIC --(SERVICE)--> service chooser (1612:0388) ; --(CAMPAIGN)--> campaign chooser (12a7:010d)
             --(REALISM PANEL)--> realism (0a8d:07cb) ; --(BEGIN)--> briefing (0c1d:03c6) --> shell_fly(0) → AP | [return]
             --(RETURN TO MAIN / Esc)--> single-mission menu (0b16)
```

---------------------------------------------------------------------------------------------------

## 10. Port notes

* **sim_end trigger**: the GCD marker (3E7h) becomes a flag passed by the in-process chain; SIM.IN /
  SIM.OUT stay files (or in-memory buffers with the same layout).
* **Timed waits**: `wait_input(10000)` (`2171:000a`, 42.2 s) and the wipe (`22ce:0137`, 10 × 5
  ticks) busy-wait on the countdown `DS:2E3F` decremented by the 236.7 Hz timer; the port must drive
  that counter from real time and yield/present inside the loops. `ttm_play` polls input through its
  abort callback every frame.
* The event/TTM screens draw straight on the pages (2312 work, 2314 front, 2310 spare); keep the page
  model of the toolkit (`shell_ui_toolkit.md` §0.2, §8).
* Keep the quirks: one medal per mission; events marked seen when collected; `event_draw_box2` uses the
  box-1 font id for the style; the SIMQ fonts are never freed; item 7 "SELECT MISSION:" not drawn;
  `display_subst('%j')` copies without the NUL; the growth buffer leak of `events_collect` (a no-op for
  a port with a GC-free allocator: simply free it).
* `rng_below(2)` in `career_pick_squadron` and `rng_seed_time` in `sim_end` / the career menu: keep the
  call order (shell_data §1.1).
* `flyhist_init` is dead code; the static links of `4992:0010` must be used.

## 11. Hand-offs

* **shell_data**: SIM.OUT **+06 u16[4] is read** by PS (`0874:0291`, event type 3: ids of events
  triggered in the sim, list ends at FFFF) and **+0E** is also compared with the event id of type-4
  events (in addition to the `== 1` date jump). `shell_data.md` §3.2 says +06 is not read.
* **shell_data**: the TOPMISS temp record at `DS:4308` is built by `09a9` (best.c, `09a9:0629…06f2`),
  not by `0874` (the "case 2" in the `0874:0291` decompile is Ghidra merging code from elsewhere).
* **shell_data**: pilot status `DS:4778 = 1` is "retired", set for captured pilots (`0542:000a`), when
  the player retires at the end of a campaign (`0874:11ff`), and by `shell_cleanup` (`227c:004d`).
* **shell_data**: `EVENTS<n>.EVT` layout decoded (§7.1; `data.md` §3.4 can be replaced): 66-byte record,
  id byte bits 6–7 = file number, text block after the records.
* **shell_data**: `HIST_*` records hold entries of a single service; `1f85:03e9` maps list rows but the
  UI uses raw indices for picture / synopsis / mission (§6.4 quirk).
* **owner (shell_ui.md)**: module **`0cfe` is not in the function index** (two functions `0cfe:000a`,
  `0cfe:0057` + switch table, image `0xCFEA–0xD16E`, reached only through far pointers from `0637`,
  `0f35`, `1305`); specced in §8. `sim_end` leaves `DS:051E = 1` on the career-over path
  (`0542:0363` jumps past the clear), so a later `shell_cleanup` sets `DS:4778 = 1` and saves again.
  `sim_end` returns to `main` for non-career missions, which then enters the main menu.
* **S2**: `fltdeck_run` `0787:0181` is called from `sim_end` and the career menu; its result is
  `DS:43D6` (1 = FLY). `squadinf_run(2)` `07ba:08c2` (transfer), `bigmap_show` `0d16:0b33`.
* **S3**: `09a9:07ee` (career over / retire: top aces + save), `09a9:072e` (best-mission check after the
  debrief), `09a9:058f` (best careers), `0a41:028d` / `0a41:01c1` (campaign availability / choice),
  `0a8d:07cb` (realism), `0c1d:03c6(miss)` (historic briefing, may set `DS:43D6`).
* **S4**: `0f67:0001` pilot_save, `0f67:021a/0252` event seen / mark (key = event id byte),
  `0f67:02ed` side group, `0f35:01d8(side, kind 0..3, far text)` ceremonies, `0ed9:0347` new pilot,
  `13be:086e` roster pick, `0fa1:02f9(0)` campaign / squadron selection, `0fa1:0600(far text)`
  campaign summary, `0ddd:0cde(aircraft, service, 1)` new-aircraft presentation.
* **S5**: `1656:0008/0095` message records (§0.3) and the `1305` text boxes (`03f2` campaign end,
  `044e` KIA, `0487` board of inquiry, `0546` squadron movement); `144e:029c(war_over, n)` decision;
  `1612:0388(0)` service chooser; `12a7:010d(service)` campaign chooser.
* **video**: `3a73:0085(x, y, w, h, 1, src_page, dst_page, 0, 0, 0)` region dissolve used by the TTM
  text hook; `16e3:36dc(font)` = font height (`DS:2348[slot]`).
* **sound**: shell ids 1002 / 1004 / 1010 / 1015 (`SHELL.SX` / music); `snd_stop(−1)` = stop all.

## 12. Open questions

* `DS:4779` passed to `ext_select` at the very start of `sim_end` before the pilot copy is loaded: its
  value comes from the DGROUP image / earlier start-up code (probably 0); the effective selection is
  redone before the flight deck.
* Exact meaning of `2624:05a6` (the squadron's next mission date: returns 0 when the squadron has no
  more missions — L) and `2624:011d` (non-zero = squadron not active at that date — L): shell_data.
* `DS:43B5` (`2008:0018`) semantics (allows CONTINUE without an active pilot): extension flag — L.
* Whether any shipped add-on uses event types 1–4 (none in `EVENTS0/1.EVT`).
