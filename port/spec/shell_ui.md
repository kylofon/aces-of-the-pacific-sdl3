# shell_ui — intro sequence, PS shell start-up/exit, UI toolkit, shell screens

Owner module `shell_ui` (see `README.md`). Targets `Game/INTRO.EXE` (DGROUP `17E0`) and
`Game/PS.EXE` (DGROUP `4D08`). Game-data logic (campaign, scoring, mission generation, records)
is `shell_data`'s; this spec calls it by address.

Confidence tags: **V** verified instruction by instruction, **L** likely, **G** guess.

## Index

| File | Content |
|---|---|
| `shell_ui.md` (this file) | §1 overview; §2 INTRO intro sequence; §3 PS start-up (`main` `048e:0259`, `sys_init`), fly path, `shell_exit` (`227c`), fatal errors; §4 Windows focus / sound toggles (`166d`, `315c`); §5 copy protection; §6 screen flow graph; §7 port notes; §8 hand-offs; §9 open questions |
| `shell_ui_toolkit.md` | the UI toolkit ("alert" library): hot-spot manager `2b4f`, drawing `2c11`, text flow `2dd0`, event loop / input `2e25`, screen table & palettes `2e8a` (**screen id table**), dialogs `2ed6`, `2f47`, `2f7f`, `2fa5`, `3038`, `307d` |
| `shell_ui_debrief.md` | return from the sim, debrief, flight history, career events: `050c`, `0542`, `0583`, `05fa`, `0607`, `0637`, `0874` |
| `shell_ui_flight.md` | flight map, flight deck, squadron info, big map, single-mission set-up: `06c7`, `0787`, `07ba`, `0d16`, `100e`, `1155` |
| `shell_ui_options.md` | main menu `04df`, hall of fame `09a9`, campaign set-up `0a41`, one-time init `0a71`, realism `0a8d`, `0b16`, options/controls `0b48`, briefing `0c1d` |
| `shell_ui_career.md` | dog-fight ace `0c8a`, view vehicles `0ddd`, `0eb4`, pilot roster `0ed9`/`0f67`/`13be`, awards `0f35`, campaign select `0fa1`, medals `135d` |
| `shell_ui_mission.md` | `simshell` `125a`, `12a7`, `12c4`, `1305`, decision `144e`, custom mission `147e`, `1513`, `1612`, `1656` |
| `shell_ui_symbols.csv` | all names of this module |

## 1. Overview

```
GCD.COM ──exit code 1──> INTRO.EXE ──exit(2)──> PS.EXE ──exit(3) + SIM.IN──> AP.EXE ──exit(2) + SIM.OUT──> PS.EXE …
                                                   └─exit(0)──> DOS
```

* INTRO: start-up (platform), the intro TTM sequence (§2), `exit(2)`.
* PS: `main` → checks the `0000:0510` marker and the free memory left by GCD, `sys_init`, then the
  **main menu loop** (`04df:018d`, never returns except through `shell_exit`). When coming back
  from the simulator (marker 3E7h) the **sim-end/debrief chain** `0542:01c4` runs first.
* Every "fly" path ends in `048e:01a0` (`shell_fly`): generate the mission (`3164:23e3`), write
  `SIM.IN`, `shell_exit(1)` → marker + `exit(3)`.
* Quitting (main-menu EXIT TO DOS, Alt-X/Alt-Q/Ctrl-Q + "Exit to DOS? (Y/N)") → `shell_exit(0)` →
  text mode, `exit(0)`.

The UI is a software toolkit on top of the VGA driver (three 16 KB pages: work `DS:2312`, front
`DS:2314`, spare `DS:2310`): every screen = a background (`screen_show(id…)`, table in
`shell_ui_toolkit.md` §5.1) + a hot-spot table (22-byte items with callbacks) run by
`menu_run(frame)`; results 1 = OK, 2 = Esc/cancel.

## 2. INTRO.EXE: the intro sequence — V

### 2.1 Where it sits in `main` (`038e:0ac1`, platform spec for the rest)

After option parsing (`-pi` → `DS:00C0 = 1`; `override` → `DS:00C1`; `-s<n>` → sound driver
`DS:24B3`; `-h`/`-?` → usage, `exit(0)`), config/`control.prf` reading and the add-on scan
`038e:0704` (below), `038e:091b` (EMS check):

```
if (!DS:00C0) { sys_init (038e:080d); intro_sequence (038e:0973); }
snd_shutdown (1686:0004); 05da:5db4 (keyboard restore)
if front page DS:0A94 != A000h: DS:0A92 = A000h; src = front, dst = A000h; 05da:2fbd(0)  // copy + flip so A000h shows the last frame
038e:0687 (write control.prf); exit(2)
```

So `-pi` skips `sys_init` as well (no graphics mode change at all).

### 2.2 Add-on scan `intro_scan_sets()` (`038e:0704`)

```
DS:24B5 = 0
for n = 1 .. 7:
    f = vol_fopen(res_name("CSET", n, "dat"), "rb"); if !f continue
    DS:24B5 |= pow(2, n-1)  (038e:0004: integer power, pow(b, e<=0) = 1); DS:24B6 = n; close
    f = vol_fopen("INTRO<n>.DAT", "rb"); if f: read 1 byte b; if b: DS:00C2 = n; close
if DS:00C2: f = vol_fopen("INTRO<DS:00C2>.DAT", "wb"); write byte 0; close
```

`CSET<n>.DAT` marks an installed data set (`M1SHL` has `CSET0` "ACES OF THE PACIFIC" and `CSET1`
"1946!"; n starts at 1, so `CSET0` is never looked at). `INTRO<n>.DAT` is a one-shot flag
"show the add-on intro next time": M1SHL ships `INTRO1.DAT` = 01; the first run rewrites it on disk
as 00 (the game folder has `INTRO1.DAT` = 00). **`vol_fopen` tries the disk first** (the work
directory `DS:2461`, then the current directory) and the volumes only when the file is not on
disk (V, `049d:00bb`) — so once the disk copy exists the volume copy is never read again.

### 2.3 `intro_sequence()` (`038e:0973`)

```
v = DS:00C2 ? DS:00C2 : intro_pick_set(DS:24B5)          // 038e:0021
for (name, num) in [("intace1", -1), ("intace2", -1), ("intace3", v), ("intace4", v), ("intace5", v)]:
    if DS:00C4 (skipped) break                              // tested before each script
    if name is intace3..5 and v == 0: num = -1
    intro_play(res_name(name, num, "ttm"), -1, 0, 0, 1CDh, intro_skip_check)   // 0460:028c
```

`intro_pick_set(mask)` (`038e:0021`): builds a list of i in 0..7 with `mask & pow(2, i−1)` (note
`pow(2,−1)` = `pow(2,0)` = 1, so i = 0 and i = 1 both test bit 0); `srand(time(0))`;
`k = (rand() · count) / 8000h` (long arithmetic); returns `list[k]` (byte).
With the shipped data (`CSET1` only, mask = 1): list = {0, 1} → **50 %**: `INTACE3/4/5`
(1942 ending) or `INTACE31/41/51` (the 1946 variants), unless `INTRO1.DAT` forced 1 (first run
after installing the add-on). `INTACE1` (Dynamix logo, clouds) and `INTACE2` always play.

### 2.4 TTM playback (`0460`, "intro.c" in `d:\aces1946\code\shell\intro\`)

| Address | Name | Behaviour |
|---|---|---|
| `0460:000b` | `intro_tick()` | timer callback: `DS:24D8:24DA` (u32) += 1 |
| `0460:001a` | `intro_skip_check()` → continue | `skip = key_down(1Ch Enter) \|\| key_down(01h Esc) \|\| key_down(39h Space)`; reads one key from the BIOS buffer (`05da:03ab`, discarded); if joystick enabled (`DS:24B7`) and not skip: either joystick button; if mouse enabled (`DS:24B8`) and not skip: mouse button 0 or 1 (`0491:005f`); `DS:00C4 = skip`; returns `!skip` |
| `0460:00d3` | `intro_ttm_open(name)` → ok | TTM view rect: `0A8C = 1, 0A83 = 1, 0A84 = 0, 0A88 = 0, 0A86 = 319, 0A8A = 199`; `DS:24D6 = timer_add(0460:000b, reload 4)` (`05da:2307`: every 4 PIT ticks = **59.17 Hz**); counter = 0; `ttm_init` (`1125:0013`); `ttm_load(name)` (`1125:002f`) == −1 → `ttm_free` (`1125:095c`), `timer_remove(24D6)` (`05da:2351`), return 0; returns `1125:03a7(0) ≥ 1` |
| `0460:0157` | `intro_ttm_close()` | `1125:06c5(0)`, `ttm_free`, `timer_remove(24D6)` |
| `0460:0174` | `intro_ttm_play(first, last, far cb)` → r | below |
| `0460:028c` | `intro_play(name, last, extra, first, end_frame, far cb)` | below |

```
intro_ttm_play(first, last, cb):
    cont = 1; running = 1; delay = 0 (persists across frames)
    for (f = first; cont && running && (last == -1 || f < last); f++):
        if win_detect() && DS:264B && !DS:264A: 0dc0:000d (Windows: release/reacquire sound) else DS:264B = 0
        DS:33C8 = -1                                    // the script sets its frame delay here
        t0 = counter
        running = ttm_run_frame(f)   (1125:05ee)
        if running: 05da:2fbd(1) (video: show the page); 0fca:03cc(0) (palette/fade step)
        if DS:33C8 != -1: delay = DS:33C8 (sign-extended to 32 bits)
        if delay: while (t0 + delay > counter): if cb: cont = cb(); if !cont break
        else if cb: cont = cb()
    return !cont ? -1 : !running ? -2 : f

intro_play(name, last, extra, first, end_frame, cb):
    if !intro_ttm_open(name) return
    chdir("TTD") (038e:0097: skipped when DS:00C5 != 0 — the release sets it: development leftover)
    r = intro_ttm_play(first, last, cb)
    if r == -1: ttm_run_frame(end_frame - 1)             // skipped: jump to the script's end frame 1CCh
    else if r != -2: r += extra; r2 = intro_ttm_play(r, r + extra, cb); if r2 != -2: ttm_run_frame(end_frame - 1)
    chdir("..") (038e:00bc); intro_ttm_close()
```

With the arguments used (last = −1, extra = 0) every script plays to its end unless skipped; a
skip jumps to frame 1CCh (the script's exit frame: black/fade) and the following scripts are not
started (`DS:00C4`). Frame timing comes entirely from the scripts' delay opcode (59.17 Hz units);
sound effects come from `TTD.SX` (loaded by `sys_init`, sound spec).

`0491:000c/0025/003e/005f/007c` are the INTRO mouse wrappers (init, shutdown, get position, button,
move-to), all no-ops when DOS < 3 (`DS:0092`): platform.

## 3. PS.EXE start-up, fly and exit

### 3.1 `main` (`048e:0259`) — V

```
DS:40CA = ""; DS:4F6D = DS:4F6C = 0
for each argv "-n<dir>": strcpy(DS:40CA, dir)          // work directory (SIM.IN/OUT, records)
append '\' if missing; if it ends in "\\" drop one
0000:10d1(0, 4000h, 0FFFh)                             // RTL heap set-up (platform)
1193:0881                                               // shell_data: file-set detection
for each argv:
   "-?"/"-h" → usage (DS:027E…0439, 13 lines) and shell_exit(0)
   "-r<n>"   → DS:00C5 = atol(n)       (force random seed)
   "-s<n>"   → DS:43B2 = atol(n)       (sound driver)
   "-p<c>"   → tolower(c) computed, nothing else (the -pr/-pq/-pd/-pi/-ps/-ph/-pm/-pv debug
               switches listed in the usage text are compiled out)
   "-n…"     → already handled; "-f<n>" is listed in the usage but not handled
   "nlkle"   → DS:00C2 = 1 (developer bypass: no GCD marker needed, no return to AP)
   "override"→ DS:00AA = 1 (skip the memory check)
mem_check (048e:0200)
if !DS:00C2:
   marker = word 0000:0510: 29Ah → DS:00C3 = 0 (fresh start); 3E7h → DS:00C3 = 1 (back from AP);
   else fatal_msg("You can run Aces of the Pacific by typing 'AOTPCD' from the command line, …")
word 0000:0510 = 0
sys_init (048e:0009)
if DS:00C3: sim_end (0542:01c4)          // debrief chain (shell_ui_debrief.md)
main_menu (04df:018d)                    // does not return normally
shell_exit(0)
```

`mem_check` (`048e:0200`): unless `DS:00AA`: `free = word 0000:0512 << 4` (paragraphs stored by
GCD → bytes, long); if `free < 900B0h` (**590 000 bytes**): prints the NULL-terminated message
table `DS:00C7` ("There is not enough memory for 'Aces of the Pacific' …", 5 lines) and `exit(0)`.
(This answers RE_GUIDE's open question: PS reads `0000:0512`.)

### 3.2 `sys_init` (`048e:0009`) — V

```
DS:43B0 = gfx_init(DS:43B0 adapter, 0FFh, 0ABh); if 0: DS:43B0 = gfx_init(0, 0FFh, 0ABh);
    if 0: fatal_msg("Cannot initialize graphics card!\nPlease run SETUP to configure")
if DS:43B2 == 4: DS:43B2 = 2                          // SoundBlaster → AdLib driver
drv = DS:43B2; if drv == 3 (MT-32) && !DS:00C2: drv = 88h
if !snd_init(drv, "sxcode.ovl" DS:00B6): fatal_msg("Cannot initialize sound & music driver!…")
timer_add(229e:0013, reload 1)            // DS:1CC8 tick counter, 236.7 Hz (16e3:291b)
divzero_install; kbd_install(0); mouse_init (2316:000f)
screens_load (2e8a:0164); fonts_load (0a71:0001); parts_load (0a71:00eb); scr_init (2e8a:0124)
0b48:0b6e (options: apply control settings, shell_ui_options.md)
snd_load_resource(res_name("shell", -1, "sx"))       // SHELL.SX effects
if !DS:00C3: snd_play(3EAh)                            // title music, not when back from the sim
DS:00C4 = 1
plate_buf_alloc (2c11:0001); dialogs_init (0a71:015c); DS:051E = 0
```

`dialogs_init` (`0a71:015c`): loads `MREAL.PRF` into `DS:4357` (`1193:0818`, shell_data) and
calls every screen's table initialiser (`choose_init`, `2f7f:026a`, `lbox_init`, `pick_init`,
`12a7:01c0`, `0f35:012d`, `04df:02be`, `0607:02f5`, `0ed9:05b3`, `135d:0600`, `09a9:096a`,
`0874:0e0f`, `100e:1459`, `0c1d:06c0`, `0d16:0c5d`, `1513:0fdc`, `0787:031b`), mostly
`hs_default_links` on their tables.

### 3.3 Fly: `shell_fly(mode)` (`048e:01a0`) and the "Please Wait" box (`048e:0112`) — V

```
shell_fly(mode):
    screen_show(37 CLOUDS, 0, 0)
    please_wait()
    3164:23e3(mode)                    // shell_data: build the mission (script.c)
    sim_in_build_write (1193:093e)      // SIM.IN (13 bytes, DS:4B86)
    1193:0856                           // shell_data: save prefs/state files
    if DS:626B (mission mode) not 2 and not 3:
        2777:04df, 2550:073f, 2a85:0216, 2ab3:057f   // shell_data: write the career world files
    plate_buf_free
    shell_exit(1)

please_wait():
    DS:2303 = 0; font_select(DS:421E FONT3); DS:2302 = 1
    y = 80, h = 20, w = text_width("Please Wait...") + 10, x = 160 - (w >> 1)
    22ce:0085 (src work, dst front); draw_popup_box(); DS:2300 = C5h
    text_engrave("Please Wait...", C7h, B3h, C0h, text_center_x(s, x, w), y + 7)   // drawn on the front page
    22ce:00fb (front → work)
```

Callers of `shell_fly`: main menu (`04df:018d`, modes 3 and 4 via `DS:626B`), `0542:01c4`,
`0583:03c2`, `0607:011d`, `0b16:01a7` (see the part files).

### 3.4 Exit and fatal errors (`227c`) — V

| Address | Name | Behaviour |
|---|---|---|
| `227c:0007` | `shell_set_exit_hook(off, seg)` | `DS:1BE6:1BE8` (used by `0874:12be`) |
| `227c:0019` | `shell_clear_exit_hook()` | clears it |
| `227c:002a` | `shell_request_quit()` | `DS:00C1 = 1` (the next `menu_run` iteration asks "Exit to DOS? (Y/N)") |
| `227c:0034` | `shell_break(now)` | from the keyboard handler `16e3:63cb` (Ctrl-Break/Ctrl-C, platform): now → `shell_exit(0)`, else quit request |
| `227c:004d` | `shell_cleanup()` | if `DS:051E` (career data dirty): `DS:4778 = 1`, `09a9:07ee`, `0f67:0001` (save records/roster); `0000:11d7`, `16e3:5b0e` (RTL / platform shutdown: Likely restores vectors, frees EMS-less memory) |
| `227c:0072` | `shell_exit(to_sim)` | exit hook if set; `shell_cleanup()`; `1193:08a4` (shell_data); **to_sim = 0**: `snd_shutdown` (`461d:0005`), `gfx_restore_text`, `exit(0)`. **to_sim ≠ 0**: `snd_shutdown`; if not `DS:00C2` (nlkle): if front page ≠ A000h: `DS:2312 = A000h`, copy front → A000h, `page_flip(0)` (so the picture stays on screen while AP loads); else `gfx_restore_text`; `word 0000:0510 = DS:00C3 ? 3E7h : 29Ah`; `exit(3)` |
| `227c:00f8` | `fatal_msg(fmt, …)` | `shell_cleanup`, `snd_shutdown`, text mode, `vprintf(fmt, …)` + `"\n"` (`DS:1C57`), waits for a key (`kbhit` loop), `exit(0)` |
| `227c:0143` | `fatal_line(file_off, file_seg, line, expr)` | the shell's `assert`: cleanup, sound unload, text mode; prints "A SHELL system error has occured.\nPlease write down the following data and contact Sierra Customer Support:\n", `"%s:%d (%s)"` (file name copied from the far data segment, `expr` default `DS:1C65`), then `RSEED = %d` (`DS:6275`), `MODE = %d` (`DS:626B`), `MTYPE = %d` (`DS:626C`), `DATE = %d` (`DS:6277`), `WORLD = %d` (`DS:626D`), `PLYR SINDEX = %d` (`DS:62DB`), `ENEMY SERVICE = %d` (`DS:6355`); waits for a key; `exit(0)`. The file segments name the modules (e.g. `5CAB` alert.c, `5CAE` menu.c): the line numbers quoted in the toolkit spec are these |

The marker written by `shell_exit(1)` is **29Ah on a fresh session, 3E7h if PS itself was entered
from AP** (`DS:00C3` is not reset in between): AP accepts both (sim_flow).

## 4. Windows focus and sound toggles — V

| Address | Name | Behaviour |
|---|---|---|
| `166d:0009` | `shell_win_focus()` | called by `menu_run` when `win_detect()` and `DS:4F6D` (set by the Windows callback, platform `1671`) and not `DS:4F6C`: `DS:4F6C = 1`; if under Windows: `snd_fx_toggle`, `snd_music_toggle` (mute), `1671:0051("doco")` (Windows switch/"doco" request, platform), toggle both back; `DS:4F6D = 0`. (The `4F6C` guard is never cleared here: Likely cleared by the platform callback) |
| `315c:0003` | `snd_music_on()` | returns `DS:43B9` |
| `315c:000e` | `snd_music_toggle()` → on | `DS:43B9 ^= 1`; now on → `4675:0003(-1)` (resume music), else `DS:43B9 = !45e4:0007(-1)` (pause; stays on if pausing failed); returns `DS:43B9` |
| `315c:0044` | `snd_fx_on()` | returns `DS:43B8` |
| `315c:004f` | `snd_fx_toggle()` → on | same with `DS:43B8` and channel −2 |

## 5. Copy protection

None in this CD version 1.2: no manual/code-wheel/aircraft-identification check exists in INTRO,
PS or AP (no such strings, no screen or data file for it; the screen table has no quiz screen).
The only gate is the GCD marker (`0000:0510` = 29Ah/3E7h) and the free-memory check, both in §3.1.
**PORT:** the marker check becomes the in-process chain (`main` passes "fresh"/"back from sim"
directly); `mem_check` is skipped (free memory is not a DOS quantity any more).

## 6. Screen flow graph

(Filled from the part files; call sites in brackets.)

See §6.1 below (completed after all parts are written).

## 7. Port notes

* **INTRO**: keep `intro_pick_set` (50 % 1946 intro). The one-shot `INTRO1.DAT` rewrite is written
  to the game folder like the original. `chdir("TTD")`/`chdir("..")` are no-ops (`DS:00C5`).
* **PS main**: the GCD marker (`0000:0510`) and `0000:0512` become fields of the port's chain loop;
  `nlkle` can be kept as a developer switch. `-r<n>` / `-s<n>` map to port options.
* `shell_exit(1)`'s "copy to A000h + flip" keeps the last shell image visible while AP starts: the
  port can simply not clear the screen between the programs.
* Fatal screens (`fatal_line`, `fatal_msg`) are text-mode printouts waiting for a key: show them in a
  message box / stderr.
* Timing: nothing in the shell is frame-locked; waits use `DS:2E3F` (PIT countdown), the 236.7 Hz
  counter `DS:1CC8`, the INTRO 59.17 Hz counter and TTM script delays. Drive these from real time.

## 8. Hand-offs

* **platform**: `vol_fopen` (`049d:00bb`, PS `0000` copy) opens **disk first** (work dir `DS:2461`
  prefix, then as given), volumes only when not found — `port/formats/resources.md` §1 ("tries the
  current volume…") and `scripts.md` §2 (loose `MAINMENU.SCD` "presumably unused") are wrong: the loose
  `Game/MAINMENU.SCD` (QUIT instead of EXIT TO DOS) **is** the one used. PS `main` reads `0000:0512`
  (GCD free-memory word, paragraphs) in `048e:0200` (≥ 590 000 bytes). The keyboard handler
  `16e3:63cb` calls `227c:0034` (break). `16e3:291b(off, seg, reload)` = timer callback add.
* **video**: shell page roles (work `2312`, front `2314`, spare `2310`, main-menu cache page `AC00h`
  when `DS:231D` is 2 or 8 — hivga?); `16e3:35d1` = page flip, `35c4` = page copy (`2316`→`2318`),
  `3188/318C/3190` save/size/restore, `31E8` bitmap draw with flag 2 = mirror (Likely). INTRO TTM
  frame delay variable `DS:33C8` is in 59.17 Hz ticks of the INTRO timer callback.
* **sound**: shell ids 18h (press), 19h (focus move), 1Ah (click on nothing), 3EAh (title music, not
  played when back from the sim); `315c` toggles use `4675:0003` / `45e4:0007` with −1 music, −2 effects.
* **sim_flow**: PS writes marker 29Ah on the first flight of a session and 3E7h afterwards.
* **shell_data**: `3164:23e3(mode)` mission build; `1193:0856`, `1193:08a4`, `1193:0881`,
  `0a71:015c` loads `MREAL.PRF` into `DS:4357`; `fatal_line` prints `DS:6275/626B/626C/6277/626D/62DB/6355`
  (RSEED, MODE, MTYPE, DATE, WORLD, PLYR SINDEX, ENEMY SERVICE) — names for those globals.

## 9. Open questions

* `16e3:5b0e` and `0000:11d7` in `shell_cleanup` (platform shutdown details).
* The Windows "doco" call (`1671:0051`) — platform.
