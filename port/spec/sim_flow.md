# sim_flow — AP.EXE game flow: main, init, flight loop and time base, input and controls, commands (+ parts)

Target: `work/AP_flat.exe` (DGROUP `3EA4`), addresses as in `port/RE_GUIDE.md`. Phase 3 spec,
2026-09-26. Symbols: `port/spec/sim_flow_symbols.csv`.

Index:
* §0 AP segment ownership map (for all AP spec writers)
* §1 Overview (session structure, part files) · §2 `main` · §3 init, preferences, mission set-up,
  shutdown, `sim_exit` · §4 **flight loop and time base** (frame pacing) · §5 input polling,
  input record, control mapping, key bindings, view input · §6 frame step and draw order ·
  §7 command handler (gear, flaps, brakes, bail-out, …) · §8 small helpers · §9 Port notes ·
  §10 Hand-offs · §11 Open questions
* Parts: `sim_flow_vcr.md` (VCR films), `sim_flow_cockpit.md` (views, cockpit, gauges, HUD,
  messages), `sim_flow_ui.md` (map, dialogs, sliders, preferences, realism),
  `sim_flow_results.md` (scoring, SIM.OUT, skip-ahead, RNG).

## 0. AP segment ownership map

Rule: one Borland code segment = one source module; a segment is owned whole unless a split is
listed in its row (then the named functions go to the other module). Confidence: **H** (strings /
read), **M** (call graph + skim of the decompile), **L** (guess). Function counts are from
`port/ap_functions.json` (VROOMM stub segments `3c59`–`3ea0` excluded). Classification pass
2026-09-25 (sim_flow), for sim_world / render3d to use; objections go in their Hand-offs.

Notes for the other owners:
* **Flight model** = `0b01` (sim_world), driven per aircraft from `4bf9:0257`; the player's control
  inputs arrive at `player+0ACh` (written by `5440:0aee`, sim_flow).
* **Time base** = `362b` (sim_flow, §2): every dt-scaled quantity in the world code uses
  `362b:00be` (x·dt>>8) or the timer helpers `362b:0165..02e3`; `DS:711E` = dt (1/256 of the nominal
  step). The mission clock is `DS:4086` (u32, += dt each frame, `5440:12e3`).
* `277a` is shared: 3D math (`3b3c`/`3bfc` distances, `3dc1` saturating 32/16 divide, `3e84`
  bit length, `41c4` range map, `5e66`/`5e71` sin/cos, matrices `41e0`/`4556`/`457a`/`49a4`/`4ae5`)
  and render primitives; owned by render3d, other modules only reference it.
* Ghidra shows segment immediates +1000h (`0x4923` in `ap_ds.c` = far data segment `3923`).

| Segment | Owner | Conf. | Fns | Bytes | What |
|---|---|---|---|---|---|
| `0000` | platform | H | 254 | 18761 | Borland RTL, volume.c, DAC; also the sim tick counter callback 0000:02db/02e7 (DS:18D2, used by sim_flow timeouts 4b31) |
| `04c4` | sim_world | M | 13 | 3253 | flak / AA fire: target choice by altitude/range, burst objects 2805h, update 0910, draw 0bf0 |
| `0590` | **sim_flow** | M | 4 | 397 | rate-limited servo helpers (value approaches a goal with accel/decel): views 1c30, gauges 678a, blackout 0fd4 |
| `05a9` | render3d | M | 8 | 715 | pool of transient effect objects culled around the camera; update callbacks from the sim step, drawn from 5440:018c |
| `05d6` | sim_world | H | 7 | 1070 | ordnance/projectile pool + deferred delete; split: 036c/0381/03fc (remember / follow the last dropped weapon for the weapon camera) -> sim_flow (views) |
| `0619` | sim_world | H | 10 | 1761 | AI air-combat tactic states |
| `0688` | sim_world | H | 6 | 3596 | bombs.c |
| `0769` | sim_world | H | 9 | 2382 | guns: firing, bullet objects 0805h, hit test, tracers, ammo messages |
| `07fe` | sim_world | H | 1 | 53 | ces.c |
| `0802` | render3d | M | 3 | 625 | visibility culling before drawing (cloud layer, range, line of sight) |
| `082a` | **sim_flow** | L | 2 | 777 | segment/sphere closest-point geometry used only by the skip-ahead code 496a |
| `085b` | sim_world | H | 6 | 745 | aircraft proximity: collision avoidance flags, mid-air collisions |
| `088a` | sim_world | H | 6 | 2218 | ground/ship impact, crash handling, kill messages |
| `0916` | sim_world | M | 7 | 1202 | parachutes (para_*.BMD) and debris pieces |
| `0962` | **sim_flow** | M | 19 | 4311 | cockpit window outlines .EDG (per view) and the cockpit edge masks |
| `0a7b` | **sim_flow** | M | 1 | 195 | asm span-list intersection for the 0962 cockpit edge masks |
| `0a88` | render3d | M | 10 | 438 | asm span/edge-list helpers for the horizon fill 4d6e |
| `0ab0` | **sim_flow** | M | 3 | 276 | english.c string lookup (group,id) in STR_POOL + word wrap: used by every message |
| `0ac2` | sim_world | H | 1 | 991 | AI gunnery aiming / lead |
| `0b01` | sim_world | H | 26 | 11878 | **flight model core**: 0134 and 1d33 physics variants, 1860 dispatcher (from 4bf9:0257), 1a28 max speed at altitude |
| `0de8` | **sim_flow** | L | 2 | 48 | two tiny text wrappers (format + measure/draw), only for stdalert 5a01 |
| `0deb` | sim_world | H | 40 | 7780 | g_attack.c |
| `0fd4` | sim_world | M | 2 | 505 | player G load and blackout/redout ramp (DS:579B, DS:5798, DS:579A) |
| `0ff4` | sim_world | M | 5 | 813 | weapon stations: select/cycle bomb and rocket stations (0001 is called by the key/command handler) |
| `1027` | sim_world | H | 17 | 2422 | AI tactic states |
| `10bf` | sim_world | M | 6 | 602 | aircraft death states, wreck timer; 013a/01d6 save/restore the player position relative to the carrier (called by 5440:0aee) |
| `10e5` | **sim_flow** | M | 2 | 1243 | player advisory messages per frame (engine, take-off, brakes/flaps/gear) |
| `1133` | sim_world | M | 8 | 239 | small AI state handlers |
| `1142` | sim_world | H | 36 | 5152 | AI targeting and threat scoring; 1142:0000 = object dead/out test |
| `1284` | sim_world | H | 12 | 1935 | AI combat decisions |
| `12fd` | sim_world | H | 49 | 7088 | AI air-combat manoeuvre state machine |
| `14b8` | **sim_flow** | M | 3 | 163 | random table seeding from the 1889 RNG, XOR checksum (with 1889) |
| `14c3` | sim_world | M | 8 | 435 | per-plane AI alert level and radio cooldown timers |
| `14e0` | sim_world | H | 9 | 2046 | collision support: near-ground-object list, ground hit tests, world bounds |
| `1560` | sim_world | M | 12 | 2868 | weapon impacts and explosions; split: 06e9 (effect draw, from 5440:0269) and 055b (fire/smoke spawn from the draw pass) -> render3d |
| `1614` | **sim_flow** | H | 7 | 705 | message.c: on-screen message lines |
| `1641` | sim_world | M | 6 | 484 | misctbl.c: object-type tables (APP:/TBL/DAT) |
| `1660` | **sim_flow** | M | 18 | 4795 | split: radio-command menu to wingmen (0f6e/0f85/110f/0685/07bb/0bae/0c12/0c47) -> sim_flow; AI responses (0065/0110/0130/01bc/0706) -> sim_world |
| `1792` | render3d | M | 9 | 922 | palette effect channels (fades/tints) + upload (paltrick family) |
| `17ce` | render3d | M | 2 | 759 | per-frame palette update (time of day, channels) |
| `17fe` | sim_world | M | 8 | 346 | waypoint list cursor/accessors |
| `1815` | **sim_flow** | H | 12 | 1832 | radio message text builder (templates, callsigns) + 2-slot delayed message queue; feeds 1614 |
| `1889` | **sim_flow** | H | 5 | 253 | lagged-Fibonacci RNG (state DS:4454), rand%N, chance test (core infra; VCR determinism) |
| `1899` | **sim_flow** | H | 9 | 6501 | scoring and mission goals: per-frame goal flags, kill credit 0cf0, ground-target credit 102f, score DS:5CA1 |
| `1a32` | sim_world | H | 4 | 1413 | rockets.c |
| `1a8b` | render3d | H | 3 | 236 | aircraft shadows |
| `1a9a` | render3d | M | 2 | 580 | sun/moon direction and sprite |
| `1abf` | render3d | M | 4 | 296 | DDA / fill helpers for the horizon fill |
| `1ad2` | sim_world | H | 37 | 3133 | AI aerobatic manoeuvre library |
| `1ba4` | **sim_flow** | M | 2 | 92 | repeating timed warning message |
| `1baa` | sim_world | H | 5 | 1609 | torps.c |
| `1c0f` | **sim_flow** | H | 6 | 516 | VCR per-frame hook (record/playback of the frame inputs) |
| `1c30` | **sim_flow** | H | 43 | 4055 | view/camera modes, view keys, saved views ("Current view saved") |
| `1d32` | platform | H | 170 | 24095 | system library |
| `241c` | render3d | H | 2 | 522 | .BMD effect loader |
| `243d` | render3d | M | 4 | 244 | sprite-set slots DS:6498 |
| `244d` | video | M | 5 | 389 | save/restore the 2D graphics context |
| `2466` | render3d | M | 2 | 258 | far-object dot/sprite inside the cockpit view window |
| `2494` | platform | H | 8 | 471 | fatal error / assert |
| `247d` | platform | H | 4 | 362 | Windows clipboard INT 2Fh (no callers) |
| `24b2` | platform | H | 7 | 524 | mem.c |
| `24d3` | platform | H | 8 | 222 | memory marks |
| `24e1` | platform | H | 2 | 64 | EMS detect |
| `24e5` | platform | H | 7 | 367 | EMS map |
| `24fc` | video | H | 13 | 2407 | TTM player (AP copy) |
| `2595` | video | H | 6 | 2814 | TTM interpreter (AP copy) |
| `2651` | video | H | 6 | 2058 | bitmap helpers |
| `26d2` | video | H | 3 | 143 | bitmap helpers |
| `26db` | video | H | 6 | 998 | BMP:MTX loader |
| `271b` | render3d | H | 15 | 1510 | ts_util.c |
| `277a` | render3d | H | 122 | 22481 | 386 asm core: 3D math (vectors, matrices, sin/cos, muldiv, distance) + render primitives |
| `2e33` | render3d | H | 9 | 2282 | ts_bm.c |
| `2ec2` | render3d | M | 2 | 138 | sub-shape/sprite draw dispatch |
| `2ecb` | render3d | H | 3 | 312 | shadow projection |
| `2edf` | render3d | H | 3 | 744 | ts draw helpers |
| `2f0e` | render3d | H | 5 | 2999 | ts_draw.c |
| `2fca-3342` | sound | H | 103 | 13951 | SCI sound module and API (3060 player) |
| `333b` | render3d | H | 6 | 710 | detail-level tables |
| `3368` | render3d | H | 6 | 911 | terrain GID |
| `33a1` | render3d | L | 3 | 296 | DDA/interpolation stepper (detail tables DS:3F10; also used by control.c 4b9f) |
| `33b4` | render3d | M | 3 | 458 | object draw dispatch by type |
| `33d1` | render3d | H | 10 | 3804 | world/camera setup |
| `34bf` | render3d | M | 4 | 685 | draw-list sort |
| `34f1` | render3d | H | 12 | 1347 | macros.c |
| `3546` | render3d | H | 15 | 1194 | pool.c |
| `3591` | render3d | H | 2 | 301 | init.c (ob) |
| `35a4` | render3d | M | 1 | 128 | object extents by type |
| `35ad` | render3d | H | 3 | 564 | obwload.c |
| `35d1` | render3d | M | 1 | 66 | point in convex polygon |
| `35d6` | render3d | M | 9 | 644 | per-tile attributes cache |
| `35ff-3684` | render3d | H | 44 | 2174 | 3D math helpers (clamp, angles, rotate, bearings, vector length, bit length) |
| `362b` | **sim_flow** | H | 21 | 734 | **time base**: per-frame dt (DS:711E) and dt-scaled timers |
| `365a` | render3d | M | 3 | 116 | object rotation matrix cache |
| `368f` | video | M | 24 | 994 | pages, dissolve wipe, clip reset, countdown wait (DS:31E5); split: 000e/002f/020a/0243/0268/02e6/035c/03a1 string/filename helpers -> platform |
| `36ce-36ea` | sim_world | M | 12 | 427 | AP utilities used by snario/AI: buffer stream reader 36ce, int array fill/find/bitset helpers |
| `36ee` | **sim_flow** | H | 1 | 125 | free disk space (getdfree), used by the VCR before recording |
| `36f6` | platform | H | 40 | 3978 | Borland overlay manager (not ported) |
| `39e5` | - | M | 1 | 256 | 256 zero bytes, no code |
| `45cc` | sim_world | H | 17 | 2301 | acedata.c |
| `465c` | sim_world | M | 18 | 2078 | object creation from mission records, object lists; split: 04ee (cockpit .LBM name) -> sim_flow, 0589 (draw sort comparator) -> render3d |
| `46de` | **sim_flow** | M | 8 | 1287 | hot regions / button bars (mouse hit test, background save) |
| `472f` | **sim_flow** | H | 6 | 1935 | dialog window frames |
| `47a8` | **sim_flow** | H | 33 | 3676 | "forms" widget library |
| `488e` | sim_world | H | 3 | 176 | weapon class registry |
| `4899` | **sim_flow** | M | 4 | 131 | cockpit panel top line DS:3CD8, full-screen flag DS:00F8 |
| `48a2` | **sim_flow** | H | 1 | 197 | embossed text for forms |
| `48af` | **sim_flow** | H | 4 | 371 | boxlist.c |
| `48c7` | **sim_flow** | H | 7 | 890 | bstream.c (VCR bit stream file I/O) |
| `48ff` | sim_world | H | 2 | 165 | bulletso.c |
| `490a` | sim_world | H | 14 | 1417 | hit boxes (.BXL), line of sight |
| `4963` | **sim_flow** | M | 2 | 112 | gauge/cockpit state reset |
| `496a` | **sim_flow** | M | 43 | 7267 | skip-ahead ("A" key): reason codes, moving the flights along their routes |
| `4b31` | **sim_flow** | H | 3 | 132 | tick timeouts on the DS:18D2 counter |
| `4b3a` | sim_world | H | 8 | 1380 | damage.c |
| `4b91` | render3d | M | 2 | 203 | date -> moon phase (sky) |
| `4b9e` | **sim_flow** | M | 2 | 10 | two empty debug stubs |
| `4b9f` | **sim_flow** | H | 5 | 370 | control.c: slider effects (time scale, detail, sky) |
| `4bb7` | **sim_flow** | H | 2 | 340 | english.c: STR_POOL loader |
| `4bcd` | **sim_flow** | M | 6 | 696 | findfile.c (file exists / find first) |
| `4bf9` | sim_world | H | 17 | 2577 | AI/player flight-control primitives, per-aircraft control apply 0257 |
| `4c9b` | video | H | 1 | 177 | font loading |
| `4ca7` | **sim_flow** | H | 3 | 83 | mission clock DS:3F36 |
| `4cad` | **sim_flow** | M | 2 | 706 | .GAU gauge file load |
| `4cda` | sim_world | H | 5 | 936 | gunlist.c |
| `4d15` | **sim_flow** | M | 7 | 1414 | Huffman codec setup for VCR streams |
| `4d6e` | render3d | H | 8 | 2532 | horizon / sky-ground fill |
| `4e0d` | **sim_flow** | H | 16 | 3287 | init.c / control.c: sim_init, mission start/end, prefs, sim_exit |
| `4edb` | render3d | H | 2 | 53 | vector negate |
| `4edf` | sim_world | H | 48 | 5976 | flight-level AI states (carrier, landing, formation, patrol, attack) |
| `5058` | sim_world | H | 13 | 1652 | per-frame flight-group update |
| `50c0` | **sim_flow** | M | 3 | 128 | LSO signal bitmaps (sig_a/sig_j) for the HUD overlay; 0080 = debug flag getter (DS:053F) |
| `50c8` | **sim_flow** | H | 2 | 1284 | main.c |
| `5119` | **sim_flow** | M | 3 | 468 | dialog library box |
| `5137` | render3d | M | 8 | 478 | vec3 helpers |
| `5155` | **sim_flow** | M | 7 | 1152 | modules.c (add-on volume M#SHL.DYN, VCR files) |
| `519d` | **sim_flow** | M | 2 | 174 | ovl.c (load DAT tables by name) |
| `51a8` | render3d | M | 2 | 185 | paltrick helper |
| `51b4` | render3d | H | 2 | 341 | paltrick.c |
| `51ca` | render3d | M | 6 | 452 | file word/long/string I/O helpers (world loader 628f) |
| `51e7` | **sim_flow** | M | 8 | 305 | ring-buffer queue (VCR) |
| `51fb` | sim_world | M | 4 | 779 | AI spawn/intercept positions |
| `522c` | **sim_flow** | H | 7 | 423 | realism flags and score multiplier |
| `5247` | **sim_flow** | H | 2 | 194 | dialog title text |
| `5254` | **sim_flow** | H | 13 | 5376 | results.c -> SIM.OUT |
| `53a6` | **sim_flow** | H | 16 | 1118 | dialog item list / focus |
| `53ec` | **sim_flow** | M | 4 | 574 | dialog shadowed text |
| `5410` | sim_world | M | 9 | 765 | ship movement |
| `5440` | **sim_flow** | H | 27 | 5649 | sim frame step 1317, draw 018c, commands 0aee; split: `03aa` (world draw) and `0269` (object draw callback) -> render3d (sim_flow §6.2 gives their call order) |
| `55a4` | **sim_flow** | M | 11 | 1069 | simshell.c: resource name helpers (M#SHL.DYN) |
| `55e8` | render3d | H | 6 | 688 | sky.c |
| `5613` | **sim_flow** | H | 14 | 1211 | slider.c |
| `565f` | **sim_flow** | M | 5 | 1229 | IFF ILBM screenshot writer (key in 60a9) |
| `56ac` | sim_world | H | 26 | 6361 | snario.c (+acedata) |
| `583c` | sim_world | H | 44 | 6887 | AI spotting, leader/wingman pairing, threat evaluation |
| `59eb` | render3d | H | 2 | 216 | stars.c |
| `59f9` | render3d | M | 4 | 115 | object class registry |
| `5a01` | **sim_flow** | H | 7 | 1848 | stdalert.c |
| `5a75` | sound | H | 59 | 4012 | sx_sim.c |
| `5b71` | - | L | 3 | 502 | named-resource lookup, no direct callers (dead?) |
| `5b91` | render3d | L | 2 | 25 | math helper |
| `5b93` | **sim_flow** | H | 33 | 3143 | VCR (vcr_gfx) |
| `5c5f` | **sim_flow** | H | 11 | 956 | vcr2.c |
| `5c9b` | **sim_flow** | H | 1 | 1052 | vcr3.c: the session driver (record/play/fly) |
| `5cde` | **sim_flow** | H | 7 | 1493 | flight loop |
| `5d3c` | **sim_flow** | H | 5 | 155 | VCR glue |
| `5d46` | **sim_flow** | H | 5 | 246 | VCR |
| `5d56` | **sim_flow** | H | 4 | 1197 | vcr_demo.c |
| `5da1` | **sim_flow** | H | 11 | 727 | stdalert.c (end-of-mission alerts) |
| `5dd0` | **sim_flow** | H | 6 | 853 | VCR seek/fast forward |
| `5e06` | **sim_flow** | H | 16 | 2536 | vcr_file.c |
| `5ea5` | **sim_flow** | H | 26 | 2092 | vcr_gfx.c |
| `5f2c` | **sim_flow** | H | 30 | 3112 | control mapping: input -> control frame, key bindings |
| `5fef` | **sim_flow** | H | 20 | 2031 | vcr_list.c |
| `606e` | **sim_flow** | H | 14 | 933 | rlsmgfx.c |
| `60a9` | **sim_flow** | H | 24 | 2958 | input polling (keyboard, joystick, mouse) |
| `6163` | **sim_flow** | H | 4 | 632 | VCR |
| `618d` | **sim_flow** | H | 26 | 2085 | vcr_tape.c |
| `6210` | **sim_flow** | H | 4 | 2021 | stdalert.c |
| `628f` | render3d | H | 9 | 933 | wdata.c |
| `62ca` | render3d | M | 2 | 123 | sorted list helpers |
| `62d2` | render3d | H | 9 | 2740 | area loader |
| `637f` | sim_world | M | 7 | 357 | object alive tests; split: 00af (cycle to next object for the view) -> sim_flow |
| `6396` | **sim_flow** | H | 17 | 1389 | alrtlib2.c |
| `63ed` | **sim_flow** | H | 8 | 1483 | bstream.c |
| `644a` | **sim_flow** | H | 29 | 4309 | cockpit.c |
| `655d` | sim_world | H | 21 | 8152 | guns/bullets/hits and fuel burn (0bd9 per frame); split: 038a (muzzle flash, tracers) -> render3d |
| `675d` | render3d | M | 1 | 710 | ground speed dots |
| `678a` | **sim_flow** | H | 32 | 6524 | gauges |
| `6922` | **sim_flow** | M | 4 | 364 | VCR object id tables |
| `6939` | **sim_flow** | H | 2 | 677 | message box helpers |
| `6964` | render3d | H | 11 | 1715 | sun/moon, time of day |
| `69d0` | sim_world | M | 12 | 735 | flight/waypoint helpers |
| `69fe` | sim_world | H | 8 | 1603 | AI state machine executor |
| `6a63` | **sim_flow** | H | 21 | 1589 | VCR frame encoder/decoder |
| `6ac7` | sim_world | H | 5 | 1879 | segment vs hit-box collision |
| `6b3d` | **sim_flow** | M | 2 | 242 | mission music + ACES.PAL |
| `6b4d` | **sim_flow** | H | 34 | 4328 | control/sim preferences dialog (prefsim.box), CONTROL.PRF |
| `6c5f` | **sim_flow** | H | 8 | 1569 | dialog text layout |
| `6cc2` | sim_world | H | 2 | 405 | drop tank jettison |
| `6cdc` | **sim_flow** | H | 20 | 4155 | fltmap.c |
| `6de0` | **sim_flow** | M | 2 | 50 | mission-exit resource cleanup |
| `6de4` | **sim_flow** | L | 1 | 122 | sorted table lookup (VCR) |
| `6dec` | sim_world | M | 2 | 249 | midpoints for tactics |
| `6dfc` | sim_world | H | 6 | 1494 | carrier landing/LSO; split: 0497/04ce (LSO paddle overlay drawing) -> sim_flow |
| `6e5a` | **sim_flow** | H | 5 | 1040 | radio message menu |
| `6e9b` | **sim_flow** | M | 1 | 58 | realism timer |
| `6e9f` | **sim_flow** | H | 24 | 1992 | rlsmgfx.c realism dialog (simreal.box) |
| `6f1c-6fe3` | video | H | 15 | 3985 | bitmap/screen loaders |
| `7017` | render3d | M | 2 | 420 | shape index cache |
| `7032` | render3d | M | 2 | 98 | shape bank counts |
| `7039` | render3d | H | 5 | 940 | ts_file.c |
| `7074` | render3d | H | 5 | 1019 | ts_utilo.c |
| `70b4` | video | L | 2 | 830 | ellipse (no callers) |
| `70e8` | render3d | H | 1 | 355 | draw helper |
| `70ff` | video | M | 1 | 348 | video driver load |
| `7115` | video | H | 2 | 1109 | font/text |
| `715b` | video | H | 1 | 694 | SCR loader |
| `7187` | video | H | 11 | 1344 | resource file library |
| `71db` | video | H | 5 | 1233 | BMP helpers |
| `7229` | video | H | 6 | 1623 | BMP loader |

Totals (functions / bytes of the index, stubs excluded): - 4 / 758, platform 500 / 48844, render3d 421 / 63800, sim_flow 902 / 130237, sim_world 659 / 116770, sound 162 / 17963, video 107 / 21146

## 1. Overview

AP.EXE is started by GCD (or the port's chain loop) after PS has written `SCRIPT.DAT` and `SIM.IN`.
One run of AP = one **session**: `main` → `sim_init` (everything that lives for the whole run) →
`vcr_session` `5c9b:0000` (the VCR session driver, `sim_flow_vcr.md`: it loads the mission,
flies/records/plays it with the **flight loop** `5cde:0405`, writes `SIM.OUT`, offers the VCR
panel) → `sim_shutdown` `4e0d:035c` → `sim_exit(2)` (back to PS).

```
main 50c8:0008 ............................................................ §2
 ├ options, EMS check, marker 0000:0510, SIM.IN -> DS:439A (13 bytes), memory check
 ├ sim_init 4e0d:0000 ...................................................... §3.1
 ├ vcr_session 5c9b:0000(&DS:5E0D?, mode) ........................ sim_flow_vcr.md
 │   ├ mission_load 4e0d:038e (SCRIPT.DAT or the film's script) -> snario 56ac:0236
 │   ├ mission_start 4e0d:03e9 ................................................ §3.3
 │   ├ flight_loop 5cde:0405 ................................................... §4
 │   │    per frame: input_poll 60a9:02c4 -> flight_keys 5cde:0080 -> controls_map 5f2c:05d1
 │   │               -> view_input 5f2c:08fd -> sim_step 5440:1317 -> view keys 1c30:09d9/0ad5
 │   │               -> VCR record 6a63:04d0 -> draw_frame 5440:018c -> wait >= 8 ticks
 │   │               -> timebase_set 362b:008f
 │   ├ results_write 5254:04f1 (SIM.OUT) ................................ sim_flow_results.md
 │   ├ mission_end 4e0d:058e, mission_unload 4e0d:03b4 ......................... §3.3
 │   └ (VCR panel, replay, save film …)
 ├ sim_shutdown 4e0d:035c ................................................... §3.4
 └ sim_exit 4e0d:0bb0(2, 0) -> marker 3E7h, exit(2) ......................... §3.5
```

Parts of this spec:

| File | Contents |
|---|---|
| `sim_flow.md` (this file) | §0 ownership map; main, init, mission set-up/tear-down, preferences, exit; flight loop and **time base**; frame step and draw order; input polling, control mapping, key bindings; command handler |
| `sim_flow_vcr.md` | VCR: session driver `5c9b`, recording/playback, film format, Huffman streams, demos, VCR panel |
| `sim_flow_cockpit.md` | views and cameras, cockpit build (`<plane>.TTM`, `.EDG`, `CPVW.BUF`), gauges (`.GAU`), HUD overlays, messages, radio menus, STR_POOL strings |
| `sim_flow_ui.md` | in-flight map (`fltmap`), dialog library, stdalert (end-of-mission questions), sliders, preferences / control calibration dialogs, realism |
| `sim_flow_results.md` | scoring and mission goals (`1899`), results → `SIM.OUT` (`5254`), skip-ahead (`496a`), the RNG (`1889`) |

Notation: `DS:xxxx` = DGROUP `3EA4` offsets; `P` = the player's aircraft object (`DS:3B09`, near
pointer); `P+ACh` = the player's control block (`CB`). Tick = one PIT interrupt at 236.69 Hz
(divisor 5041, `timer_install(13)`, platform spec). Confidence: **verified** (read in the
disassembly), **likely**, **guess**.

## 2. `main` (`50c8:0008`) — verified

`void main(int argc, char **argv)`. DS globals: `DS:4032` work directory (char[], `-n`),
`DS:4030` spare EMS pages for the overlay manager, `DS:0539` EMS class, `DS:053F` debug flag,
`DS:43DC` sim mode, flags written by the debug switches below.

1. `DS:4032[0] = 0; DS:5EE0 = DS:5EE1 = 0`. For each argv `-n<dir>`: copy `<dir>` to `DS:4032`.
   If the string does not end in `\`, append `"\\"` (`DS:0576`); if it ends in `\\` (two
   backslashes) drop the last one. (The work directory is used for `SIM.IN`/`SIM.OUT`? — no: the
   code opens `sim.in`, `sim.out`, `*.prf` by bare name; `DS:4032` is only passed to the sound
   loader (`5a75`) and film paths. **likely**.)
2. If `argv[1]` equals `"nlkle"` (`DS:0578`, `strcmp`): `DS:053F = 1` (**debug mode**; `50c0:0080`
   returns it and gates every debug switch below).
3. For each argv `-m`/`/m` while in debug mode: `printf("%ld\n", farcoreleft-like 24b2:013d(-1,-1,0))`
   and `exit(1)`.
4. `DS:1EBC = 0583h` (`"SH"`, platform assert tag); `0000:1057(0,0,0)` (RTL, platform).
5. EMS: `ems_detect()`; none → fatal `2494:0127(0, 487Bh, 0DBh, "At least 112K EMS memory
   required to run.")`. Else `atexit(34E5:00B6)` (EMS release) and `DS:4030 = ems_free_pages()`;
   `< 13h` pages → the same fatal; `< 21h` → `DS:0539 = 3`, `DS:4030 -= 15h`; else
   `DS:0539 = 4`, `DS:4030 -= 21h` (pages left for the overlay cache, 16 KB each).
6. `0000:1a70()` installs the INT 24h critical-error handler.
7. Not debug: the hand-off marker `word 0000:0510` must be 29Ah or 3E7h, else `exit(1)`;
   read `sim.in` (`519d:0000(DS:439A, 13, 1, "sim.in")`, 13 bytes; `data.md` §1.1) and
   `mode = SIM.IN[1]` (`DS:439B`). Always: `word 0000:0510 = 0`.
8. Switches (`-` or `/`), all but `-o` only in debug mode:

   | Switch | Effect |
   |---|---|
   | `-s` | `DS:0532 = 1`: no sound (sim_init installs only the tick counter) |
   | `-s<n>` | `DS:0532 = 0`, `DS:052E = atol(n)`: sound driver number (overrides CONTROL.PRF `+02`) |
   | `-S<file>`, `-x<file>` | debug: `DS:0534 = file` (script file name instead of `SCRIPT.DAT` `DS:056B`), fatal "Could not find %s" if missing. Non-debug: if `<file>` exists, copy it byte by byte to `DS:0534` (= `SCRIPT.DAT`) |
   | `-W<n>` | `DS:0536 = atol(n)`: world area override (snario) |
   | `-t<n>` | `DS:053C = atol(n)`, `DS:053A = 1`, `DS:0884 = 1`: timed run, exits after n units (§8) |
   | `-w` | mode 2 (recorder) |
   | `-d` | mode 3 (demo films `TAPES\DEMO*.VCR`) |
   | `-o` | skip the memory check (any build) |

9. Unless `-o`: free memory `24b2:013d(-1,-1,0)` − 140 000 < 0 → fatal "MEMORY TOO LOW".
10. `DS:4030 != 0` → `36f6:08ed(0, 0, DS:4030)` (overlay manager: use EMS for the overlay cache;
    port: nothing). `4b91:00d0()` (empty stub).
11. `DS:43DC = mode`; `sim_init()`; `vcr_session(DS:5E0D?, mode)` (`5c9b:0000`; the first argument
    is not used by it — the callee reads `mode` only); `sim_shutdown()`; `word 0000:0510 = 3E7h`;
    `sim_exit(2, 0)`.

`50c8:0000` (8 bytes) is an empty far function used as a no-op callback.

## 3. Initialisation, mission set-up and tear-down, preferences (`4e0d`)

### 3.1 `sim_init` `4e0d:0000` — verified

Runs once per AP run. In order:

1. `24d3:0002(DS:2F44)` (memory mark). `prefs_load` `4e0d:05f5` (§3.2).
2. Not debug → `DS:3174 = 0`.
3. Video: `1d32:000a(DS:43B1 video mode, 80h, name 55a4:0000("vmcode2", "OVL"))` loads the video
   driver; `DS:4012 = DS:26D4` (the page current at start, compared by `sim_exit`). Failure → fatal.
4. `DS:3586 = 0AA4:0024` (far pointer, a text vector for the video driver); `4c9b:0000()` loads the
   fonts font1–4 and "talk" (video); failure → fatal.
5. Palettes: `DS:408A = 1d32:3e0b("ACES.PAL")`, `DS:06B9 = 1d32:3e0b("clouds.PAL")` (far
   pointers); `DS:408A == 0` → fatal. If debug or `DS:26DF == 0`: `1d32:400e(DS:408A)` (set the
   palette); else (`DS:26DF` = a fade-capable display): `368f:03ed; 368f:03b6; 368f:01f2`.
6. `DS:408E = 1`, `DS:4090 = 2` (number of display pages to refresh after a full redraw, §4.1).
7. `divzero_install()`.
8. Sound: if `DS:052E != -1` → `DS:43B3 = DS:052E`. If `DS:0532` (no sound): `DS:0530 == 0` →
   `timer_install(13)` and `1d32:4755(0000:02DB, period 1)` (the tick counter callback, `DS:18D2`,
   +1 per tick); else call `0000:02db` once. Otherwise `sx_sim_init 5a75:0afa(55a4:0000("sx1",
   "DAT"), work dir buffer, "simsnds1.sng", DS:43B3, DS:0530)` (sound spec: it installs the timer,
   the tick counter callback and the sound service); `DS:43B3 == 88h` and not debug → fatal.
9. `368f:008d()`; `input_init 60a9:0b35()` (keyboard handler, mouse, joysticks; §5.1);
   `55a4:03d9()`; `5a75:0d66(DS:43B9)` (sound on/off from CONTROL.PRF); `47a8:0000()` (forms);
   `ui_load 4e0d:0c29()` (loads the `alerts` and `sliders` bitmaps `.BMP`, sliders `5613:0068`,
   `53a6:0016`); `simprefs_load 4e0d:09d0()` (§3.2); `6b4d:0308()`, `6e9f:0000()` (preference and
   realism dialogs, ui part).
10. World/object subsystems, one init each, in this order (verified from the disassembly — the
    Ghidra list is off in places; owners in §0): `56ac:010b 4b3a:025c 0916:002e 59eb:0000 51b4:0000
    4bb7:007f 4963:0000 1899:000d 4b9f:0159 48ff:0000("bullets") 0688:0004("bombs")
    1baa:001e("torps") 1a32:000b("rockets") 1a8b:0004 04c4:0057 655d:0322 10bf:0005 519d:008a
    1ad2:0c39 62d2:0a0d 085b:0006 45cc:0822 5410:02ed 4edf:1774 14b8:000d 4bf9:0a18 1133:00e0
    1142:1421 1284:078b 12fd:1bad 0ac2:03fa 583c:1ae2 5058:0641 1815:070e 465c:0818 490a:0137
    1027:0975 69fe:0000 496a:0000 0619:06e4 5b91:0014 1660:1302 0deb:1e83 51fb:0306 5da1:02e4
    17fe:016b 4d6e:004b 60a9:07d2(ax)`.

### 3.2 Preference files — verified

`prf_name` `4e0d:05e0` (near): patches `DS:032E "?real.prf"` to `mreal.prf`, or `creal.prf`
when `DS:43DC == 1` (career); returns `DS:032E`.

`prefs_load` `4e0d:05f5`:
1. `f = fopen(prf_name(), "rb")`; if open: `fread(DS:42C8, 16, 1, f)` (realism flags, ui part
   §realism) and close.
2. `f = fopen("control.prf", "rb")`: missing → copy the 37-byte default `DS:06C4` to `DS:43B1`;
   else `fread(DS:43B1, 37, 1, f)`.
3. Copies CONTROL.PRF bytes into the preference dialog's item values in far segment `3974`
   (`3974:0185 = +08`, `:012D = +06`, `:0159 = +07`, `:007D = +0A`, `:00A9 = +0B`, `:00D5 = +0C`),
   the joystick calibrations `+0D` (12 bytes) → `60a9:096d(0)` = `DS:4F60`, `+19` (12 bytes) →
   `DS:4F6C`; `5f2c:004d(+06)` (joystick flight control flag `DS:0B20`), `5f2c:0074(+07)` (mouse
   flag `DS:0B1E`); `6b4d:0751()` applies the device selections (ui part).

CONTROL.PRF (`DS:43B1`, 37 bytes; `data.md` §3.1 refined) — **likely** from the uses:

| Off | DS | Use |
|---|---|---|
| 00 | 43B1 | u16 video driver/mode for `1d32:000a` |
| 02 | 43B3 | u16 sound driver number (`-s<n>` overrides; 88h is refused outside debug) |
| 04 | 43B5 | u16 (not used by AP code seen) |
| 06 | 43B7 | u8 joystick flight control on (`DS:0B20`) |
| 07 | 43B8 | u8 mouse on (`DS:0B1E`) |
| 08 | 43B9 | u8 sound on (`5a75:0d66`) |
| 09 | 43BA | u8 — |
| 0A–0C | 43BB–43BD | u8 ×3: prefsim dialog items (flight / rudder / throttle device choices, ui part) |
| 0D | 43BE | joystick 1 calibration: s16 X min, centre, max, Y min, centre, max → `DS:4F60` |
| 19 | 43CA | joystick 2 (rudder / throttle axes) calibration, same layout → `DS:4F6C` |

`prefs_save` `4e0d:06fd` (from `sim_exit` when `DS:4010`): unless mode 2/3, `fwrite(DS:42C8,
16, 1)` to `?real.prf` (fatal on open failure); copies the far `3974` items and both calibrations
back into `DS:43B1…` and writes `control.prf` (37 bytes, "wb"); returns 1 on success.

`simprefs_load` `4e0d:09d0` (misnamed `sim_write_results` in `symbols.csv`):
1. `f = fopen("simprefs.prf", "rb")`: open → `fread(DS:43A7, 10, 1, f)`, `view_prefs_read
   1c30:0007(f)` (the saved views, cockpit part; the file is 70 bytes), close. Missing → copy
   the default 5 words `DS:06E9` = `{28h, 28h, 50h, 0, 1}` to `DS:43A7`.
2. If `sim.out` does **not** exist (`4bcd:01df("sim.out")` = file exists) — i.e. the first flight
   after installation — run the CPU benchmark `t = 4e0d:0835()` and choose the slider defaults
   from it (`lo(i)`, `hi(i)` = slider i value range `5613:01cb/01da`; `mid(i) = lo + (hi−lo)>>1`):

   | t (ticks) | `DS:43A9` (slider 1) | `DS:43AB` (slider 2) | `DS:43A7` (slider 0) |
   |---|---|---|---|
   | > 237 (slow) | lo(1) | lo(2) | hi(0) |
   | 176..237 | lo(1) | mid(2) | mid(0) |
   | 113..175 | mid(1) | hi(2) | mid(0) |
   | ≤ 112 (fast) | hi(1) | hi(2) | mid(0) |

   (hi(0) = 14h, lo(0) = 50h: slider 0 values run backwards, §4.3.)
3. `5613:01e9(0, DS:43A7)`, `(1, DS:43A9)`, `(2, DS:43AB)` set the slider positions from the
   values; `3974:0209 = DS:43AD` (the "OFF/ON IN COMBAT" ground-detail flag); `5e06:02d9(1)`
   (VCR, vcr part).

SIMPREFS.PRF = `u16 slider0 value (time scale divisor), u16 slider1 (world detail), u16 slider2
(aircraft detail), u16 ground detail in combat (DS:43AD), u16 DS:43AF`, then the 60 bytes of
`1c30:0007` (saved views, cockpit part). **verified** (sizes), meanings **likely**.

`simprefs_save` `4e0d:0b3e` (from `sim_exit` when `DS:4010`): `DS:43A9 = slider_value(1)`,
`DS:43AB = slider_value(2)`, `DS:43A7 = slider_value(0)`, `DS:43AD = 3974:0209`; write the 10
bytes and `1c30:0020(f)` to `simprefs.prf` ("wb").

`cpu_benchmark` `4e0d:0835` → int ticks: `DS:31E5 = 10000` (the PIT down-counter, §4.2); seeds a
local RNG state (`1889:0002`), fills 64 random 3-vectors (`1889:005f` ×3 each) and turns each into a
19-byte matrix (`277a:457a`); then 32 × 64 rounds of matrix products/inverses (`277a:4ae5`,
`457a`, `41e0`, `49a4`, `4556`); returns `10000 − DS:31E5`. **Port:** this measures the host; on
any modern machine it returns ≤ 112 (fast branch). `/* PORT: */` return a constant (e.g. 100) so
the result does not depend on emulation speed.

### 3.3 Mission set-up and tear-down (called by the VCR session driver)

`mission_load` `4e0d:038e(far char *script, u16 len)` — verified: `DS:0326 = 24d3:0059(0)`
(memory mark); `snario_load 56ac:0236(script, len)` (sim_world); `cockpit_alloc 2466:000a()`.

`mission_start` `4e0d:03e9()` — verified from the disassembly (the Ghidra call list is wrong
here). Builds the world for a flight (also run again when a film is replayed), in order:
`618d:04e4(0)` (VCR tape reset); RNG states: `1889:0002(DS:4454)`, far hook `DS:44C6 = 3CD3:0061`
(stub of the empty `4e0d:03e4`), `1889:0002(DS:43DE)`, hook `DS:4450 = 3CD3:0061` (results part,
RNG); `DS:0328 = 24d3:0059(0)` (memory mark); mission clock `DS:4082 = DS:4086 = 0` (u32);
`55e8:00c4(DS:4787, DS:4789 (byte, sign-extended), DS:478D, DS:478B)` (sky/sun from the mission
date and time); `59f9:0068()`; `56ac:089e()` (create the mission objects); `5b93:0000()` (VCR
frame state); `5254:0000()` (results init); `6cdc:0da7()` (map); `14e0:0002()`; if `DS:032C`:
`DS:032C = 0`, `368f:01a3()` (dissolve); `timebase_reset 362b:002d()`; `60a9:0b51()` (input state
reset, §5.1); `6e9f:0232(DS:42C8)` (realism); `1c30:0f68()` (views); `sliders_apply 4b9f:012c()`
(§4.3); `522c:011c()`; `05a9:0005()`; `5058:0646()`; `5a75:0d66(−1)`; `5c5f:0083()`;
`view_setup 5440:009c()` (§6.3); `frame_reset 5440:013d()`; `490a:0000()`; `51b4:0088()`;
`0fd4:0007()`; `488e:0000(28h)`; `1614:000e()`; clear both pages (`DS:26D8 = DS:26D4`,
`DS:26CD = DS:26CE = 0`, `1d32:6ab0(0, 0, 320, 200)`; then `DS:26D8 = DS:26D2` and clear again);
`1d32:400e(DS:408A)` (ACES palette); `mission_clock_reset 4ca7:0000()`; `465c:0000()`;
`59f9:0068()`; `4bf9:0000()`; `583c:1a9b()`; `4b3a:02aa()`; `48ff:009a()`; `17fe:0137()`;
`50c0:0068()`; `10e5:0005()`; `4d6e:0040()`; `5da1:02da()`; `62d2:044a()`; `0deb:1718()`;
`1142:0e4e()`; `085b:02c3()`; `6e5a:038b()`; `04c4:0073()`; finally `DS:44C5 |= 80h` (§4.4).

`mission_end` `4e0d:058e()` — verified: `24d3:0092(DS:0328)` (release to the mark), `5254:065e
56ac:18e5 05a9:0043 488e:004b 583c:1ad0 465c:000b 5440:012c (free the camera object) 55e8:000a
4cda:0000 14e0:006d 5440:017e (DS:06A5 = −1: stops drawing) 17fe:0142 4b91:00d0`.

`mission_unload` `4e0d:03b4()` — verified: `24d3:0092(DS:0326)`, `4b3a:02a5 34f1:00e9 3368:0057
56ac:07b4`.

`4e0d:03d9` sets `DS:032C = 1` (request the dissolve at the next `mission_start`; from
`5d56:004b`, demo). `4e0d:03e4` is empty.

### 3.4 `sim_shutdown` `4e0d:035c` — verified

`5440:083a()` (end screen: full-screen clip `DS:26C4..26CA = 0,0,320,200`, clear both pages,
`55a4:0000(DS:06BD, DS:0606)` + `715b:0000` loads and shows an `.SCR` picture (`clouds`),
waits for the page timeout `DS:0148`, sets the `clouds` palette `DS:06B9`, `368f:017f` dissolve,
`1792:0066`); `24d3:002d()`; `47a8:0031()`; `243d:008f(0)`, `(1)`; `34f1:00a8()`; `3591:00dc()`.

### 3.5 `sim_exit` `4e0d:0bb0(u16 code, int text)` — verified

1. `5a75:0d39(0)` (sound off).
2. If `DS:4010` (set by the VCR driver once a flight has been flown in this run): `prefs_save`,
   `simprefs_save`.
3. `0000:122b()` (close the debug log `DS:1EBA`); `368f:03ed; 368f:03b6; 368f:01f2`; if
   `DS:4012 != DS:26D4` → `1d32:540b(1)` (show page 1); `0000:1ab0()` (restore INT 24h);
   `1d32:012a()` (keyboard, mouse, timer, divide-error restore).
4. If debug or `text != 0` → `gfx_restore_text()`.
5. `word 0000:0510 = 3E7h`; `exit(code)`.

Callers: `main` (2 = back to PS), the command handler's `-t` timeout (`5440:0aee`, 1 = INTRO:
the timed-run debug path, §8), `60a9:0a04` (quit key while a quit alert is up / demo: exit code
from `DS:0B80`, §5.4). The port replaces `exit` with a return to the chain loop.

## 4. Flight loop and time base — the port's frame pacing

### 4.1 Summary (what the port must reproduce)

* The simulation runs **once per rendered frame**, synchronously: input → sim step → draw → wait.
  There is no fixed-rate simulation and no timer-driven simulation code (the PIT interrupt only
  counts ticks and runs the sound driver).
* A frame lasts **at least 8 ticks** (8/236.69 s = 33.8 ms → at most **29.6 fps**); the loop busy-
  waits on the PIT down-counter `DS:31E5`. Slower frames just take longer.
* The measured frame length, rounded **down to a multiple of 4 ticks** (`ticks = elapsed & ~3`,
  elapsed ≥ 8), becomes the **next** frame's time step: `dt = clamp((ticks << 8) / div, 40h,
  1C2h)` in `DS:711E`, where `div` = the time-scale slider value (14h..50h, default from
  SIMPREFS/benchmark). With `div = 20`, 20 ticks (84.5 ms, 11.8 fps) = `dt 100h` = one nominal
  step. dt saturates at 1C2h (1.76 steps): below ~6.7 fps (div 20) the simulation slows down;
  it never takes more than one step per frame. `DS:711A` is the same computation with the fixed
  divisor `DS:3712 = 20` (real-time dt, used for UI countdowns).
* Every world quantity that changes over time is scaled by dt: `x·dt >> 8` (`362b:00be`) or the
  timer helpers `362b:0165..02e3`. The whole world state is therefore a deterministic function of
  (mission, RNG seeds, per-frame control records, per-frame tick counts) — which is exactly what
  the VCR records (control record incl. the tick count, `sim_flow_vcr.md`).
* **Port:** keep the loop structure; replace the busy-wait with "wait until 8 ticks of a 236.69 Hz
  virtual PIT have elapsed since the frame start" (SDL high-resolution counter), and feed
  `362b:008f` the same `elapsed & ~3` in *virtual ticks*. Because the original clamps dt and the
  tick count comes from the host clock, a faster host just runs at the 29.6 fps cap with dt =
  8·256/div. A later "Enhanced" 60 fps mode would need `ticks = 4` (dt 51 at div 20 → clamped to
  40h at div > 32 — i.e. the clamp would slow the sim; the minimum of 8 ticks is part of the
  tuning). For deterministic film playback the tick count must be taken from the film, not the
  clock (vcr part).

### 4.2 Timer globals used by sim_flow (platform owns the ISR) — verified

| Global | Type | Meaning |
|---|---|---|
| `DS:31E5` | s16 | PIT down-counter: `timer_isr` (`1d32:4868`) does `x = x−1; if (x < 0) x = 0` (saturating) every tick. Set by `flight_loop` (1FFh per frame), `cpu_benchmark` (10000), wait helpers `368f:00b7…` (n·13 = n BIOS ticks), `5d56`, `6cdc` |
| `DS:31E4` | u8 | 1 = timer installed |
| `DS:18D2` | u32 | tick counter, +1 per tick by the callback `0000:02db` (installed with period 1); read with interrupts off by `0000:02e7` |

Timeouts `4b31` (struct `{u32 start; u16 duration}`, 6 bytes):
* `timeout_expired` `4b31:0000(t)` → 1 if the timer is not installed (`DS:31E4 == 0`) or
  `(u32)(now − t.start) > t.duration` (unsigned compare of `duration` (zero-extended) against the
  elapsed ticks: expired when `duration < elapsed`); else 0. `now` = `DS:18D2`.
* `timeout_start` `4b31:0041(t, u16 n)`: `t.start = now; t.duration = n`.
* `timeout_expire` `4b31:0062(t)`: `t.duration = 0; t.start = now − 1` (expired at once).

Timeouts in sim_flow: `DS:0148` page-flip spacing (3 ticks, §6.2), `DS:0B85` input (11 ticks,
joystick polling `60a9:02c4`), `DS:014E` (5f2c), `DS:4334` (`-t` run, §7.4).

### 4.3 Time base `362b` — verified

Globals: `DS:711E` dt (s16, 1/256 of a nominal step), `DS:711C` = bitlen(dt) − 7, `DS:711A`
real-time dt, `DS:7118` time divisor (time-scale slider value), `DS:7116` ticks of the last frame,
`DS:3712` = 20 (initialised data).

| Address | Name | Behaviour |
|---|---|---|
| `362b:000d` | `dt_set(int dt)` | `DS:711E = dt; DS:711C = bitlen(dt) − 7` where `bitlen(x) = 3684:00a1(x)` = `x ? floor(log2 x) + 1 : 0` (so 100h → 2) |
| `362b:002d` | `timebase_reset()` | `dt_set(100h); DS:711A = 100h; DS:7118 = 1` |
| `362b:0048` | `timebase_set_div(int div)` | `DS:7118 = div` (from `4b9f:0000` = slider 0 value) |
| `362b:0053` | `timebase_ticks()` | returns `DS:7116` |
| `362b:005b` | `dt_from_ticks(int div, int ticks)` near | `clamp(sdiv32_16_sat((long)ticks << 8, div), 40h, 1C2h)` — `277a:3dc1(long a, int b)` = signed `a / b` truncated, saturating to 7FFFh/8000h on overflow |
| `362b:008f` | `timebase_frame(int ticks)` | `dt_set(dt_from_ticks(DS:7118, ticks)); DS:711A = dt_from_ticks(DS:3712, ticks); DS:7116 = ticks` |
| `362b:00be` | `dt_scale(int x)` | `clamp(((long)x · DS:711E) >> 8, −7FFFh, 7FFFh)` |
| `362b:0106` | `dt_scale_real(int x)` | same with `DS:711A`; clamps to 8001h/7FFFh |
| `362b:0146` | — | empty |
| `362b:0165` | `timer16_dec(int *t)` | `*t −= DS:711E`; on signed overflow `*t = 0`; returns `*t` (callers treat ≤ 0 as expired). NB: a negative result without overflow is kept |
| `362b:017c` | `timer32_dec(long *t)` | same on a long, overflow → 0; returns the low word |
| `362b:01a0` | `timer16_dec2(int *t)` | identical to `0165` |
| `362b:01bb`, `01e7` | `timer16_inc(int *t)` | `*t += DS:711E`, returns it |
| `362b:01cc`, `023b` | `timer32_inc(long *t)` | `*t += (long)DS:711E`, returns the low word |
| `362b:01f8` | `timer32_expired(long *t)` | `*t −= dt`; if the result is 0 or overflowed → `*t = 0`, return 1; else 0 (note: a negative non-overflowed result returns 0 — the decompile's test is `result != 0 && no overflow → 0`) |
| `362b:021c` | `timer16_expired(int *t)` | 16-bit version of `01f8` |
| `362b:0256` | `dt_scale_frac(int *x, int *frac)` | `p = (long)*x · dt`; `*frac = 3FFh`; `q = p >> 8`; if `q ≥ 8000h` → `q = 7FFFh`; else if `q < −7FFFh` → `q = −7FFFh`; else `*frac = (|p| & FFh) << 2`; if `q < 0` → `*frac = −*frac`; `*x = q` |
| `362b:02e3` | `dt_mul(int x)` | `x · DS:711E` (16-bit, wraps) |

Mission clock (`4ca7`, verified): `DS:3F36` (u32) and fraction `DS:3F34` (s16).
`clock_reset 4ca7:0000`: both 0. `clock_tick 4ca7:0014` (from the frame step): `DS:3F34 +=
dt_scale(200)`; if `DS:3F34 ≥ 400h`: `DS:3F36 += DS:3F34 >> 10; DS:3F34 &= 3FFh`.
`clock_get 4ca7:0045` → `DS:3F36` (DX:AX). Unit: 1 = 1024/200 nominal steps (5.12 steps,
102.4 ticks at div 20 ≈ 0.43 s real time; **what it counts is unclear**, maybe a "game second"
of accelerated time — guess). It is written to the film trailer (`DS:5064`).

Frame counter `DS:0887` (u32, +1 per frame, `DS:5060` copy at the end); mission time `DS:4086`
(u32, `+= dt` per frame by `5440:12e3` = `timer32_inc(DS:4086)`; `DS:4082` = its companion,
zeroed at mission start; used by the world code for "time since …").

The slider effects (`4b9f`, control.c) — verified:

| Address | Name | Behaviour |
|---|---|---|
| `4b9f:0000` | `time_scale_apply()` | `timebase_set_div(slider_value(0))` — slider 0 "TIME SCALE": position 0..72 → value 80..20 (`5613:0161`, ui part); dt = ticks·256/value, so 20 = real time (dt equals `DS:711A`), 80 = quarter speed |
| `4b9f:0018` | `aircraft_detail_apply(int v)` | slider 2 "AIRCRAFT" (0..255): `w = v + 1`; for shape-bank entries `DS:3F0E..DS:3F0C` (12-byte records in `DS:647C`): `+6 = (w >> 2) + BFh`, `+8 = word DS:0222[(w >> 5)]`; for `DS:3F0A..DS:3F08`: `+6 = (w >> 1) + 7Fh`, `+8 = DS:0234[w >> 5]` (LOD thresholds, render3d); `1a8b:001e(33a1:0008(DS:3F10, v))` (shadow detail: `DS:5CDE = n`, `DS:5CDA = n·300` altitude limit, `DS:5CE0 = n > 13 ? 3 : 0`); `DS:515A = 2000` |
| `4b9f:00d0` | `world_detail_apply(int v)` | slider 1 "WORLD" (0..255): `333b:0158(DS:5C93 && !3974:0209 ? 0 : v)` — `DS:5C93` = combat in progress, `3974:0209` = "ON IN COMBAT" (ground detail kept in combat); `33d1:04dc()`; `4d6e:0000(v)` (horizon bands); `04c4:000b(v)` (flak range); `DS:51C4 = v ≥ 55h` |
| `4b9f:012c` | `sliders_apply()` | `aircraft_detail_apply(slider_value(2)); world_detail_apply(slider_value(1)); time_scale_apply()` |
| `4b9f:0159` | `detail_table_init()` | `33a1:0055(DS:3F10, 0, 0, 14h, FFh)` (the 0..255 → 0..20 interpolator used for shadows) |

### 4.4 `flight_loop` `5cde:0405` → int — verified

Locals: `in` = input record (0x25 bytes, §5.2) at `bp−34h`; `ctl` = control record (0x14 bytes,
§5.3) at `bp−48h`; `vw` = view record (8 bytes) at `bp−8`; `ended` (di); `tail = FA0h` at
`bp−0Ch`.

```
DS:4E20 = 0                                   // VCR playback state: 0 = live flight
loop:
  input_poll(&in)                             // 60a9:02c4
  r = flight_keys(&in)                        // 5cde:0080, §4.5
  if r == 3 or r == 2:
      if DS:0886: vcr_put(4, 0)               // 6a63:04d0: end-of-film marker
      DS:5060 = DS:0887; DS:5064 = clock_get()
      return r == 3                           // 1 = normal end, 0 = abandoned (vcr part)
  DS:31E5 = 1FFh; t0 = 1FFh
  controls_map(&ctl, &in)                     // 5f2c:05d1, §5.3
  if !ended: view_input(&vw, &in, 1)          // 5f2c:08fd, §5.4
  else:      vw = DS:0940..0947 (4 words: 24h, 3, 2, 0 — a fixed "watch the end" view command)
  ended = sim_step(&ctl) & 2                  // 5440:1317, §6.1
  DS:0887++                                   // u32 frame counter
  vchg = view_keys(&vw)                       // 1c30:09d9 (cockpit part)
  if vchg and (view_apply(&vw) /*1c30:0ad5*/ & 1): DS:4E71 = DS:4090   // full redraw on 2 pages
  5d3c:003a(1)                                // VCR glue (vcr part)
  draw_frame(DS:4E71, 1)                      // 5440:018c, §6.2
  if --DS:4E71 < 0: DS:4E71 = 0
  if DS:0530: ticks4 = 19h >> 2               // debug fixed step (DS:0530 is never set: 0)
  else: do elapsed = t0 − DS:31E5 while elapsed < 8;  ticks4 = elapsed >> 2
  ctl[+12h] = ticks4                          // frame length in 4-tick units, recorded
  ticks = ticks4 << 2
  if DS:0886:                                 // recording
      vcr_put(0, &ctl); if vchg: vcr_put(1, &vw)
      if ended and tail == 0: vcr_put(4, 0)
  timebase_frame(ticks)                       // 362b:008f: dt for the NEXT frame
  if !ended: goto loop
  if tail != 0: timer16_dec(&tail); goto loop  // keep flying ~FA0h dt units after the end
  DS:5060 = DS:0887; DS:5064 = clock_get(); return 1
```

Notes: the first frame after `mission_start` runs with dt = 100h (`timebase_reset`). The view
passed to `draw_frame` is `DS:4E71` = number of pages that still need a full cockpit redraw
(set to `DS:4090` = 2 by `5cde:0000` and by view changes). After the step reports the end
(`P+1Ah` bit 0, dead/landed/bailed), the loop keeps running `tail` = 4000 dt units (15.6 nominal
steps) before returning 1. `5cde:03fd` returns `DS:31E5`; `5cde:0000` sets `DS:4E71 = DS:4090`;
`5cde:0076` sets `DS:4E6E = 0`.

### 4.5 `flight_keys` `5cde:0080(in)` → 2/3/4 — verified

Handles the end-of-mission prompt and the keys that leave the frame (map, pause, quit, dialogs).
Globals: `DS:4E74` end-alert state (set by `5da1`, ui part: 1 = end now, 2/3 = mission complete /
landed, 4 = timed end), `DS:4E6E` prompt already shown, `DS:4E6F` post-end timer, `DS:4E1C` (s32)
prompt delay, `DS:088C` delay started, `DS:5CC9` mission over (results part), `DS:1206` radio
menu open (cockpit part), `DS:0886` recording.

1. `s1 = DS:4E74 == 1`, `s4 = DS:4E74 == 4`. `s1` → return 3.
2. `s4`: `DS:4E6F += dt_scale_real(100h)`; `> 500h` → return 3; else go to 5.
3. `DS:4E6E` set → go to 5. `s23 = DS:4E74 ∈ {2,3}`; if `!DS:5CC9 && !s23` → go to 5.
4. `any = in.23h bit5|bit6|bit7 || in.24h bit0 || in.1Bh (key)`. If `DS:088C == 0`: `DS:088C = 1`,
   `DS:4E1C = s23 ? 2800h : 9600h`. `DS:4E1C −= dt_scale_real(100h)` (sign-extended); if still
   > 0 → go to 5. If `any` → `DS:4E1C = 0`, go to 5 (a key postpones the prompt by one frame).
   Else `DS:4E6E = 1`; if `5da1:01cb(P) == 0` (the "mission complete — end?" check, ui part):
   `5a75:0e96()` (silence), `return key_to_code(5da1:022e())`.
5. Keys (`k = in.1Bh`, `alt = in.22h bit0`, `ctrl = in.21h bit7`); nothing if `k == 0`:
   * neither alt nor ctrl: `19h` P → `pause 5cde:000b()`; `01h` Esc / `10h` Q → ignored while the
     radio menu is open or `s1`/`s4`; else `5a75:0e96()`, `return key_to_code(5da1:022e())` (the
     quit dialog); `32h` M → `t = 6cdc:0db1()` (current map target, 12 bytes saved),
     `5a75:0e96()`, `5f2c:0036()`, `fltmap 6cdc:0e0b()`, `5f2c:0043()`; if recording: target
     changed → `vcr_put_event(2, 0Ch, new target)` (`6a63:0515`), target cleared → `(3, 0, 0)`;
     `44h` F10 → `5a75:0e96()`, `if (6b4d:0f95() && DS:0886) { v = slider_value(0);
     vcr_put_event(1, 2, &v); }` (prefs dialog changed the time scale); return 4.
   * alt without ctrl: `13h` R → `5a75:0e96()`; `if (606e:0137()) { if (DS:0886)
     vcr_put_event(0, 10h, DS:42C8); 17ce:0013(); }` (realism dialog); return 4. `1Fh` S →
     `606e:01e6(str[DS:094C + 2·5a75:0a01()])` (sound on/off message; the toggle itself happened
     in `input_poll`); `24h` J → `606e:01e6(str[DS:0948 + 2·5f2c:006c()])` (joystick);
     `20h` D → `606e:01e6(str[DS:0950 + 2·5f2c:00ae()])` (mouse); `19h` P → pause.
   * return 4.

`key_to_code` `5cde:0057(int r)`: 5 → 3, 8 → 2, else 4.

`pause` `5cde:000b()`: `5a75:0e96()`; show message STR(1, 6) (`0ab0:000b(1, 6)`) via `1614:024e(s, 2, 0, 0)`; `draw_frame(DS:4090, 1)`; `606e:0243()`; `while (!606e:0208()) ;` (wait for a key);
`5cde:0000()`; `1614:02c3()` (remove the message).

## 5. Input polling and control mapping

### 5.1 Input state (`60a9`) — verified

Device flags: `DS:4F5B` joystick 1 present (`DS:1B4A`), `DS:4F5C` joystick 2 X = rudder
(`DS:1B4C & 4`), `DS:4F5D` joystick 2 Y = throttle (`DS:1B4C & 8`); `DS:3434` mouse enabled,
`DS:0092 > 2` = mouse driver present. Calibration (s16 min, centre, max per axis):
`DS:4F60/62/64` J1 X, `DS:4F66/68/6A` J1 Y, `DS:4F6C..` J2 X, `DS:4F72..` J2 Y; `DS:4F5E` =
throttle axis raw max, `DS:4F76` (= `DS:4F74+2`) throttle range (≥ 14h).

| Address | Name | Behaviour |
|---|---|---|
| `60a9:0b35` | `input_init()` | `kbd_install(0)`; `368f:008d()`; `mouse_init()` if `DS:0092 > 2`; `joy_detect 60a9:0ad5()` |
| `60a9:0ad5` | `joy_detect()` | `1d32:03ac()` (platform detection); `DS:4F5B = DS:1B4A; DS:4F5C = DS:1B4C & 4; DS:4F5D = DS:1B4C & 8`; if throttle: `DS:4F5E = 1d32:063f(3)`, `DS:0B81 = DS:4F5E·11/8`, `DS:0B83 = max(DS:4F5E/4, 10)` (… < 11 → 10) |
| `60a9:0b51` | `input_reset()` | `timeout_start(DS:0B85, 0)`; zero `DS:4F8C..4FA7` (14 words); `DS:4F90 = 160, DS:4F92 = 100` (mouse centre); if mouse: `mouse_warp(160, 100, 1)` |
| `60a9:0000` | `buttons_poll()` near-called | joystick buttons `DS:4F87..4F84 = joy_read_buttons(0..3)` (0 when no joystick); mouse `DS:4F83/4F82 = mouse_button(0/1)`; held keys `DS:4F8B` Space (39h), `DS:4F8A` Enter (1Ch), `DS:4F89` Backspace (0Eh), `DS:4F88` G (22h) (`key_down 1d32:0978`); **fire buttons** `DS:4F7F = J1b0 | Space | mouse L`, `DS:4F7E = J1b1 | Enter | mouse R`, `DS:4F7D = J2b0 | BkSp | DS:4F81`, `DS:4F7C = J2b1 | G | DS:4F80`; press edges: for button i (bit i of `DS:4FA7` = was down): newly down → set bit, `DS:4F7B−i = 1` (`4F7B`, `4F7A`, `4F79`, `4F78` for 7F..7C); up → clear bit |
| `60a9:01b2` | `buttons_to_record(in)` | copies the held states into `in.22h` bits 1–7 (J1b0 J1b1 J2b0 J2b1 Space Enter BkSp), `in.23h` bits 0–7 (G, mouse L, mouse R, `4F81`, `4F80`, fire1 `4F7F`, fire2 `4F7E`, fire3 `4F7D`), `in.24h` bit 0 (fire4 `4F7C`) |
| `60a9:097d` | `axis_scale(v, min, ctr, max)` | `v ≤ min` → −127; `min < v < ctr` → `277a:41c4(v, min, ctr, −127, 0)`; `v == ctr` → 0; `ctr < v < max` → `41c4(v, ctr, max, 0, 127)`; `≥ max` → 127 (`41c4` = linear map, render3d/math) |
| `60a9:0804/0817` | `mouse_present()` / `mouse_active()` | `DS:0092 > 2`; and `DS:3434` |
| `60a9:0832/0847` | mouse init / shutdown wrappers | |
| `60a9:085d` | `mouse_pos(&x, &y)` | `1d32:5d6a` if active |
| `60a9:087c` | `mouse_button(i)` | `1d32:5dbf(i)` if active, else 0 |
| `60a9:0898` | `mouse_warp(x, y, force)` | `DS:4F9C = x, DS:4F9E = y`; if active and (force or position differs from `DS:4F8C/4F8E`): store and `mouse_set_pos(x, y)` |
| `60a9:07d2` | `mouse_enable_set(v)` | if `DS:3434`: `DS:4F5A = v > 0` |
| `60a9:07ee` | `mouse_enable_toggle()` | if `DS:3434`: `DS:4F5A ^= 1`; returns `DS:3434` |
| `60a9:08e3` | `calib_set(axis, flags, int v[3])` | axis ≥ 2 (throttle): `DS:4F76 = max(v[2] − v[0], 20)`, `DS:4F5E = v[2]`; else `flags & 1` → X calibration of joystick `axis` (`DS:4F60 + 12·axis`), else Y |
| `60a9:096d` | `calib_ptr(j)` | `&DS:4F60 + 12·j` |
| `60a9:017c` | — | jump-table fragment (Ghidra garbage; no direct callers except `6b4d:0000`) — **to check**, probably mis-seeded |
| `60a9:09d8` | `quit_pending()` | if `DS:0BB7 == 0 && DS:0BB9 == 0 && DS:0B80`: `DS:0BB7 = 1`, return `DS:0B80`; else 0 |
| `60a9:0a04` | `quit_prompt()` | `244d:000b()` (save 2D context); `6163:003c()`; `DS:0B80 == 2` → `sim_exit(0, 1)`; wait for timeout `DS:0B85`; `a = 5a01:0395()` (show "quit?" alert, ui part); if shown: poll `input_poll` until `in.1Bh` is `31h` (N) or `01h` (Esc); `15h` (Y) → `sim_exit(0, 1)` (quit to DOS); then `5a01:05d5(a)`; `DS:0B80 = 0`; `244d:0087()`; `DS:0BB7 = 0` |
| `60a9:0aa7/0ab2` | block / unblock the quit prompt | `DS:0BB9 = 1 / 0` |
| `60a9:0abd` | `quit_check()` | if not blocked and `quit_pending()` → `quit_prompt()` (called at the start of `draw_frame`) |

### 5.2 `input_poll` `60a9:02c4(in)` and the input record — verified

Zero the 0x25-byte record; `buttons_poll()`; `buttons_to_record(in)`. If any joystick axis is
present: if the input timeout `DS:0B85` has not expired, reuse the last values (`DS:4F94..4FA6`);
else restart it (11 ticks) and read: J1 → `1d32:04e5(0, &x, &y)`, `in.00 = axis_scale(x, J1X)`,
`in.04 = axis_scale(y, J1Y)`, `in.14 = 1`; rudder+throttle both → `1d32:055e(1, &x, &y)`; only
one → `1d32:063f()`: `in.02 = axis_scale(rudder)`, `in.15 = 1`; `in.06 = axis_scale(throttle)`,
`in.16 = 1`, and unless a film is playing (`5b93:0153()`): `notch = 5 − ((DS:4F5E − raw)·3 +
range/2) / range` (range = max(`DS:4F76`, 20)) → `DS:4FA0`, `in.1Dh = notch` (throttle position
0..5 for hat/view use), else 0.
Then keys: held `33h` `,` → `in.21 |= 8`, `34h` `.` → `|= 4`, `35h` `/` → `|= 10h`; `1Ah` `[` →
`in.1Ah = 7Fh`, else `1Bh` `]` → `in.1Ah = 81h`; `k = key_get 1d32:0939()` (ring buffer at
`DS:1B71`, 32 entries: `scancode << 8 | shift bits`): `in.1Bh = k >> 8`; shift bits 1/2/4 →
`in.21h |= 20h / 40h / 80h`, bit 8 → `in.22h |= 1`. (Borland BIOS-like flags: **likely** 1 = right
shift, 2 = left shift, 4 = Ctrl, 8 = Alt; below "ctrl" = `in.21h` bit 7, "alt" = `in.22h` bit 0.)
If `|in.00| < 8 && |in.04| < 8` (stick centred): `d = 1d32:095e(0) & 0Fh` (keypad direction);
`d < 11` → `in.08 = DS:0B8B[d]`, `in.0C = DS:0BA1[d]`, `in.21 |= 2` (keypad stick; tables
`0B8B = {0,0,0,0,−127,−127,−127,0,127,127,127}`, `0BA1 = {0,−127,127,0,0,−127,127,0,0,−127,127}`).
Global keys (handled here, whatever else runs):

| Keys | Action |
|---|---|
| Ctrl/Alt + Q (`10h`) | `in.1Bh = 0`, `DS:0B80 = 1` (quit prompt at the next draw) |
| Ctrl/Alt + J (`24h`) | `6b4d:0408()` (joystick on/off) |
| Ctrl + Esc | `in.1Bh = 0`, `DS:0B80 = 1` |
| Alt + D (`20h`) | `6b4d:0443()` (mouse on/off) |
| Alt + T (`14h`) | screenshot: `465c:04ee()` (file name) + `565f:008a()` (IFF writer) |
| Alt + S (`1Fh`) | `6b4d:0480()` (sound on/off); in demo mode (`DS:43DC == 3`) the key is then cleared |
| Alt + X (`2Dh`) | `in.1Bh = 0`, `DS:0B80 = 1` |
| Ctrl + Alt + F10 (`44h`) | screenshot |

`in.1Ch = 1d32:098c(in.1Bh)` (ASCII of the key). Mouse: active → `in.21 |= 1`,
`mouse_pos(&in.10, &in.12)`; else `in.10/12 = DS:4F9C/4F9E`. If no key: a new button press edge
`DS:4F7B/7A/79/78` (cleared when used) → `in.24h |= 2 / 4 / 8 / 10h`; else if `in.1Dh != DS:4FA2`
→ `in.1Eh = in.1Dh`, `DS:4FA2 = in.1Dh` (throttle notch changed).

Input record (0x25 bytes, local of the flight loop; the VCR does not store it):

| Off | Type | Meaning |
|---|---|---|
| 00 | s16 | joystick 1 X (−127..127) |
| 02 | s16 | rudder axis |
| 04 | s16 | joystick 1 Y |
| 06 | s16 | throttle axis |
| 08, 0C | s16 | keypad stick X, Y (±127) |
| 10, 12 | s16 | mouse x, y (screen) |
| 14, 15, 16 | u8 | J1 / rudder / throttle axis valid |
| 1A | s8 | `[` / `]` held: 7Fh / 81h |
| 1B | u8 | key scancode (0 = none) |
| 1C | u8 | key ASCII |
| 1D | u8 | throttle notch 0..5 |
| 1E | u8 | throttle notch changed (new value) |
| 21 | u8 | bit0 mouse, 1 keypad stick, 2 `.`, 3 `,`, 4 `/`, 5/6 shift, 7 ctrl |
| 22 | u8 | bit0 alt, bits1–7 held J1b0 J1b1 J2b0 J2b1 Space Enter BkSp |
| 23 | u8 | bits0–7 held G, mouse L, mouse R, 4F81, 4F80, fire1, fire2, fire3 |
| 24 | u8 | bit0 fire4; bits1–4 press edges of fire1..4 |

### 5.3 `controls_map` `5f2c:05d1(ctl, in)` and the control record — verified

Control record (0x14 bytes; recorded by the VCR every frame; consumed by `sim_step`):

| Off | Type | Meaning |
|---|---|---|
| 00, 02 | s16 | stick X (roll), Y (pitch) |
| 04 | s16 | rudder |
| 06 | — | 0 |
| 08 | s8 | absolute throttle 0..40h (FFh = no change) |
| 09 | s8 | throttle change (±8 per key press, or axis) |
| 0E | u16 | bit0 fire1 held (guns), bit1 fire2 held |
| 10 | u16 | command code (0 = none), §7 |
| 12 | u16 | frame length in 4-tick units (written by the flight loop after the step) |

Algorithm: clear 10 words; `ctl.08 = FFh`, `ctl.09 = 0`, `ctl.10 = 0`. `ctl.0E = (in.23 bit5) |
(in.23 bit6) << 1`. Keyboard rudder `DS:4EEC` (s16): `.` held → `min(DS:4EEC + dt_scale(40), 127)`;
else `,` → `max(… − dt_scale(40), −127)`; else 0. Edge commands: `in.24 bit3` (fire3 press) →
`ctl.10 = 0Bh`; `bit4` (fire4) → `0Ah`.
Mouse flight (`in.21 bit0` and `DS:0B2C`): `x = 277a:3f27((in.10 − 160)·8, 127)`, `y = …(in.12 −
100)·8` (clamp ±127); if either ≠ 0: `mouse_warp(…)` (recentre), `ctl.00 = shape(x, 6)`,
`ctl.02 = shape(y, 6)`, `used = 1`.
Joystick (not `used`, not keypad, `in.14`, `DS:0B26`): `ctl.00 = shape(in.00, 6)`, `ctl.02 =
shape(in.04, 6)`. Rudder axis (`in.15`, `DS:0B28`): `DS:4EEC = shape16(in.02, 8)`. Throttle axis
(`in.16`, `DS:0B2A`): if `DS:0B2E` (absolute throttle) → `ctl.08 = 277a:41c4(in.06, −127, 127,
40h, 0)` (**likely** order: full forward = 40h), else `ctl.09 = −shape(in.06, 4)`.
Keypad (not `used`, `in.21 bit1`): `ctl.00/02 = shape(in.08/0C, 6)`.
Key bindings: `flags = (ctrl ? 4 : 0) | (alt ? 8 : 0)`; search the table at far `3923:0000`
(10-byte entries `{u16 flags, u16 scancode, u16 value, far fn}`, end at scancode 0) for
`(flags, in.1B)`: found → `fn ? fn(value, ctl) : (ctl.10 = value)`. Not found and `3Bh ≤ in.1B ≤
42h` (F1–F8) → `ctl.10 = in.1B − 23h` (18h..1Fh). If `view_class 1c30:0780() > 5` (outside
views) and both fire buttons held and the stick is off centre → `ctl.00 = ctl.02 = 1` (the stick
pans the camera instead). Throttle de-duplication: `ctl.08 == FFh` → `DS:4EEE = −1`; equal to
`DS:4EEE` → `ctl.08 = FFh`; else `DS:4EEE = ctl.08`, `ctl.09 = 0`. Finally `ctl.04 =
shape(DS:4EEC, 5)`.

`shape(v, k)` `5f2c:0ba3` (near): dead zone ±8 with a slight gain: `v > 8 → v + (v >> 4) − 8`,
`v < −8 → v + (v >> 4) + 8`, else 0; result `>> (8 − k)` (arithmetic). `shape16` `5f2c:0bda`: dead
zone ±16 (`± 10h`) the same way.

Key binding table `3923:0000` (verified dump; `fn 3DB3:0089` = `5f2c:055b` sets `ctl.08 = value`,
`3DB3:008E` = `5f2c:056b` sets `ctl.09 = value`):

| Key | Command / effect |
|---|---|
| B (30h) | cmd 6 (dive brakes? — `P` flag bit 2, needs `DS:3FD1 & 2`) |
| W (11h) | cmd 7 (wheel brakes, bit 3) |
| D (20h) | cmd 8 (drop tanks) |
| F (21h) | cmd 5 (flaps) |
| L (26h) | cmd 4 (landing gear) |
| S (1Fh) | cmd 9 (radio message menu) |
| U (16h) | cmd 2 (unjam guns) |
| R (13h) | cmd 0Ch (release bombs/torpedo) |
| A (1Eh) | cmd 3 (skip ahead) |
| Esc (01h) | cmd 1Fh |
| 1–9 (02h–0Ah) | absolute throttle 0, 7, 0Fh, 17h, 1Eh, 25h, 2Dh, 35h, 3Ch |
| keypad `*` (37h) | absolute throttle 40h (full) |
| `-` (0Ch), keypad `-` (4Ah) | throttle −8 |
| `=` (0Dh), keypad `+` (4Eh) | throttle +8 |
| Ctrl+B | cmd 0Dh (bail out) |

(Command meanings from `5440:0aee`, §7; names of 6/7 from the messages `STR 1:1Ch–1Fh`, cockpit
part.) The small setters: `5f2c:0000` (`DS:0B16..0B1C = 0, 136h, 0, BEh` — mouse cursor box),
`0036/0043` (`DS:4EEB/4EEA` map mode flags), `004d/0058/006c` (`DS:0B20` joystick flag set /
toggle (if `DS:1B4A`) / get), `0074/007f/00ae` (`DS:0B1E` mouse flag set / toggle + warp / get),
`00b6(x, y)` (store `DS:0B22/0B24`, warp if mouse), `00dc(in, &x, &y, &b)` (pointer position: mouse
or stored; `b` = either mouse button), `0137(i, v)` (`DS:0B26 + 2i` = device enables: 0 stick,
1 rudder, 2 throttle, 3 mouse flight `DS:0B2C`), `0148` (`DS:0B2C`), `0153/015e` (`DS:0B30`,
hat/throttle-notch views), `0166/0171` (`DS:0B2E` absolute throttle), `0179(&x, &y)` (clamp to the
box `DS:0B16..0B1C`, returns changed), `0c11()` (`timeout_start(DS:014E, 0); DS:4EEE = −1;
DS:4EEC = 0`).

`5f2c:01d8(ptr, in)` → 8-byte pointer record `{x, y, buttons, cmd}`: the dialog/map cursor driven
by mouse, stick or keys (arrow scancodes table `DS:0B32 = 4Bh 4Dh 48h 50h` → cmd 1..4; `0Fh` Tab →
cmd 3/4 with shift; in map mode `DS:4EEB` the stick/keypad moves the cursor with acceleration:
speed `277a:41c4(min(count, 200), 1, 200, 38h?, …)` — **likely**; used by the map and VCR panel
(ui/vcr parts). `5f2c:0179` clamps it.

### 5.4 `view_input` `5f2c:08fd(vw, in, allow_mouse)` — verified (partly)

View record (8 bytes, recorded when it changes): `+0 view command`, `+2 flags` (bit0 pan active,
bit1 pan record), `+4 pan x`, `+6 pan y`.
* If `view_class() ≥ 6` (outside view), no ctrl/alt, and `in.1Ah` (`[`/`]`) ≠ 0: `flags = 2`; if
  already zooming (`DS:4ED6`) → `flags |= 1`, `+6 = shape(in.1A, 4)`; `DS:4ED6 = 1`; return.
* Else `DS:4ED6 = 0`. Unless the radio menu is open: F1–F10 (`3Bh..44h`, `n = k − 3Bh`): exactly
  one of ctrl/alt → ctrl ? `n + 1` (1..10) : `n + 0Bh` (0Bh..14h); neither → F1–F7 `n + 15h`
  (15h..1Bh), F8 → 2Ah.
* Otherwise, if hat views are enabled (`DS:0B30`): in cockpit views (`< 6`) a throttle-notch
  change `in.1E` selects `DS:0B34[in.1E]` (`19h, 18h, 16h, 17h, 15h` for notches 1..5); in outside
  views the notch drives a small state machine (decompile broken — **to check** in the cockpit
  part).
* Pan: if fire2 held (`in.23 bit6`) and no pan yet: source = keypad (`in.08/0C`) or stick
  (`DS:0B26`) or 0; `flags |= 2`, `+4/+6 = shape(…, 4)`; fire1 also held → `flags |= 1`.
* Mouse pan (allow_mouse, `DS:0B2C`, no pan yet, mouse active): offset from (160, 100)·8 clamped
  ±127 → recentre, `+4/+6 = shape(…, 4)`.

The view commands are interpreted by `1c30:09d9`/`0ad5` (cockpit part).

## 6. Frame step and draw (`5440`)

### 6.1 `sim_step` `5440:1317(ctl)` → 0 / 2 — verified

The one simulation step per frame; returns 2 when the player's aircraft has ended (`P+1Ah` bit
0: crashed, shot down, landed and stopped, bailed out). Globals: skip-ahead state `DS:069C`
(0 off, 1 running, 2 jump), `DS:069D`, `DS:069E`, `DS:06A9` (frames to wait), `DS:4382`,
`DS:4346` (map target pointer) — details in `sim_flow_results.md` (skip-ahead); `DS:44C5` bit 7 =
"step finished" (cleared while stepping, read by the VCR); `DS:06A5` (s32) = steps done
(−1 = mission not running).

```
1c0f:0053()                              // VCR per-frame hook (vcr part), called 4 times
mission_time_tick 5440:12e3()            // timer32_inc(DS:4086)
DS:44C5 &= 7Fh
if DS:069C (skip-ahead active) and the map target changed (6cdc:0db1() vs DS:4346, or the
   12-byte target differs, 5440:12f3): skip_cancel 5440:12b9(); message STR(1, 34h) with the
   target; DS:069D = 2
if DS:069C == 2: 496a:170e() (perform the jump); skip_cancel()
else:
   if DS:06A9: DS:06A9--
   5a75:0a0a()                           // sound update
   if DS:069C == 0:
      if DS:069D and --DS:069D == 0: 1c30:0ab4()
      if ctl.10 == 3 (skip ahead key A) and DS:06A9 == 0: start the skip-ahead (results part):
         r = 496a:0e07(); r == 8 but the next waypoint is > 50000 away → r = 0;
         r == 0 → 1c30:0ab4(); 1c30:0aca(); DS:069C = 1; 496a:0f65(); DS:069D = 1; DS:069E = 2;
                  DS:4382 = 3000; 085b:02e5(); DS:4346 = 6cdc:0db1(), copy its 12 bytes to DS:433A
         else     496a:0f9b(r, 0)  (message why not)
   else (DS:069C == 1):
      r = 496a:0e07(); r == 0: if DS:069E: 1c30:0aca(), DS:069E--; if timer16_dec(DS:4382) == 0:
      DS:069C = 2 — else DS:069C = 0, 1c30:0aca(), 496a:0f9b(r, 1)
   05a9:014c()                            // effects update
   throttle_apply 5440:0904(ctl)
   commands 5440:0aee(ctl)                // §7 (its return value is ignored except as the result, always 0)
   678a:010b()                            // gauges update (cockpit part)
   5058:0630()                            // flight groups / AI
   1c0f:0053(); camera_follow 5440:0000(P); 490a:017a(); 6964:0076(); realism_timer 6e9b:0000()
   if DS:42CF == 0: P+ABh = 0
   1614:0023()                            // message timers
   if DS:477C != 5 (not training) and DS:4791 != 2Fh: flak 04c4:0098()
   583c:1992(); 0fd4:0033(); 1c0f:0053()
   if 14e0:008c(): 14e0:0286()
   if !(P+1Ah & 1): guns_and_ordnance 5440:0969(ctl)
   05d6:0002(); 085b:0085(); 088a:01d3(); 1c0f:0053()
   scoring 1899:0012(); 655d:0bd9(); 6dfc:02e5(); clock_tick 4ca7:0014(); 1815:0593()
   if !DS:0FEC and !DS:42D1 and !(P+1Ah & 1): advisories 10e5:00ac()
   085b:02ce()
   result = (P+1Ah & 1) ? 2 : 0
   1c30:0039()
DS:44C5 |= 80h; DS:06A5++
return result
```

`skip_cancel` `5440:12b9`: `1c30:0aca(1Ch)`; `DS:069C = 0`; `5cde:0000()` (full redraw);
`camera_follow(P)`; `DS:06A9 = 3`.
`5440:12f3` (near register helper): compares the two longs at `[BX]` and `[AX]`.

`throttle_apply` `5440:0904(ctl)` — verified: `ctl.08 != FFh` → `P+B2h = ctl.08 << 2`
(absolute, 0..100h); else if `ctl.09 != 0` → `throttle_add 5440:08d1(dt_scale(ctl.09 · DS:06AB))`
(`DS:06AB = 5`): `CB+06 += v`, clamped to 0..FFh. (**Note** the absolute path writes `P+B2h` and
the relative path `CB+06` = `P+B2h` too: `CB = P+ACh`, `+06` = `P+B2h`; throttle 0..FFh.)

`guns_and_ordnance` `5440:0969(ctl)` (near, `inc bp` frame) — verified: fire1 held and not
fire2 (`ctl.0E & 3 == 1`) → `if (0769:009a(0, P, P+10h, {P, 0Fh, 1})) { P+44h |= 1; P+48h |= 1; }`
(fire the guns; sim_world). `ctl.10 == 0Ch` (R): if `0deb:1500(P)` (has bombs/torpedoes):
sound `5a75:0eea(15h, P+4, P+70h, 1)` and release twice (`0deb:0221(P)` ×2); else unless
`DS:42D1` message STR(1, 15h). `ctl.10 == 0Bh` (fire3): if `0deb:1490(P)` → `0deb:000a(P, 0)`
(rockets); else unless `DS:42D1` STR(1, 14h). `DS:42D1` = messages suppressed (training
narration?; **guess**).

`guns_jammed` `5440:0a8d()` (called by the gun code `0769`): message STR(1, 2); `DS:4362 = 4000;
DS:4360 = 0`.

`camera_follow` `5440:0000(obj)` — verified: copies `obj+4..+0Fh` (position, 3 × s32) to
`DS:436A`, `obj+10h/12h/14h` (angles) to `DS:4376/4378/437A`; unless the view class
(`1c30:0780`) is 0: offset by the eye point of the aircraft model (`model = word
DS:55D2[DS:54BC[obj+19h]]`; `277a:4ae5(model+77h, rot = 365a:000c(tmp))`, `277a:530c(DS:436A,
tmp)`). The camera object is `DS:437E` (created by `view_setup`). **Hand-off render3d** (the
camera object layout).

`view_setup` `5440:009c` — verified: `DS:437E = DS:43D8 = 271b:0251(DS:4368)` (allocate the
camera object); `+12h = 4092h` (? a DS pointer), `+0Ah/0C/0E/10 = DS:06AD..06B3` (view window
0, 0, 140h, C8h); `camera_follow(P)`; `33d1:0004(DS:437E)`; `33d1:04dc()`; `33d1:04e7(0)`; copy
the 12-byte camera position `DS:436A` to `DS:582C`; zero `DS:4360..4366`, `DS:435C/435E`,
`DS:06B5`. `5440:012c` frees the camera (`271b:02a6(DS:437E)`).
`frame_reset` `5440:013d`: zero `DS:06A5` (s32), `DS:069C`, `DS:4382`, `DS:069D`, `DS:4380`,
`DS:1206`, `DS:069F/06A1/06A3` (pending palette), `DS:06A9`.
`5440:017e`: `DS:06A5 = −1`. `5440:008d`: `word [DS:437E+2] + 2`. `5440:0375(int x)`:
`max(100000, (long)(x + 40) << 8)` (range helper for `583c`, sim_world). `5440:0944`:
`P+1Ah & 1`; `5440:0955`: `byte [P+34h]+3Bh & 1` (flight flag). `5440:07bd(p, a, b)`: if no
palette upload is pending (`DS:069F == 0`): store `DS:069F/06A1/06A3 = p, a, b`, return 1;
else 0 (queue a DAC upload for the next flip; callers `1792`).

### 6.2 `draw_frame` `5440:018c(int redraw, int flip)` → 0/1 — verified

```
quit_check()                                     // 60a9:0abd (quit prompt, §5.1)
if DS:06A5 < 0: return 0                         // no mission running
368f:03c1(); 368f:03b6()                        // select the back page (video)
while !timeout_expired(DS:0148): ;               // >= 3 ticks since the last flip
05a9:00ad(5440:008d())                           // effects: prepare
if !0802:000c(): 1a8b:004c()                     // shadows unless culled
655d:038a()                                      // tracers, muzzle flashes
644a:0271(redraw)                                // cockpit panel background when redraw
1614:019a(); 6dfc:0497()                         // messages erase, LSO
switch view_class 1c30:0780():
   0..3 (cockpit views): 0962:0bf1(); world_draw 5440:03aa(); 0962:0c7f()   // with window mask
   else:                 world_draw 5440:03aa()
644a:0584(redraw)                                // cockpit panel / gauges
1614:005b(redraw); 6dfc:04ce()                   // messages, LSO paddles
if DS:1206: 6e5a:01a0(redraw)                    // radio menu
if DS:069F == 0: 17ce:0013()                     // palette effects of the frame
page_flip 5440:07e1(flip)
return 1
```

`page_flip` `5440:07e1(flip)`: if `flip`: `timeout_start(DS:0148, 3)`; `1d32:540b(5d3c:0000())`
(show the drawn page; `5d3c:0000` returns the page number, VCR glue); if `DS:069F`: upload the
queued palette `0000:189b(DS:069F, DS:06A1, DS:06A3)` (DAC, platform) and clear the three words;
`5d3c:0023()`. Flips are at least 3 ticks apart (the loop's 8-tick minimum dominates).

`world_draw` `5440:03aa` — the 3D scene of one frame. It lives in segment `5440` but is render3d
work; summary for the hand-off (verified call order): `4899:005c()` (cockpit clip), `w =
644a:089f()`, `277a:004b()` (frame start); if `DS:19F2`: `277a:09B2 = 1`, `277a:0A4D = w`;
`277a:0152(DS:51D9)`; draw window `DS:26C3 = 1`, `DS:26C4 = cam+0Ah`, `DS:26C8 = cam+0Ch`,
`DS:26CA = …+cam+10h−1`, `DS:26C6 = …+cam+0Eh−1`; `4899:0027()`; `277a:09B2 += (488e:00b0() == 0)`;
horizon `4d6e:0076(DS:5BDB, 277a:0A1F, 277a:0A21, DS:5BDA ? 0 : 2Ah)`; player visibility bit
`P.flags` 2000h set when `DS:19F2` and the player is not hidden (`P+1Ah bit? [P+0Dh] & 1`);
draw hooks `DS:36CC:36CE = 4D32:0070`, `DS:36D0:36D2 = 4E07:0020` (the object callbacks
`5440:0269`-style, render3d); `33d1:0004()`; decrement a counter `4EA4:18BF` (far data, **to
check**); if `0802:0026()` (inside cloud?) zero `DS:36D8/36DA/36DC` and `DS:4380 = 1`, else
(`DS:4380` → `33d1:04dc()`, clear) `33d1:04e7()`; `0802:0173()`, `490a:0509()`, `1560:055b()`,
`583c:0471()`; then every object of the draw list `DS:00BC[0..DS:00BE)` (see `render3d`):
distance `d = 277a:3b3c(cam, obj)`; aircraft-class filters (`obj+34h+3Bh & 2`, `obj+18h` kind 0/1),
LOD distance `35d6:018a() << 8` and `<< 7` (far aircraft become 0x12-byte dot records `8012h` in
`DS:5EDE`), sighting test `583c:04a9` when `DS:42C8` (realism "sun blind spot"?), kind 1 within
250000; `33d1:00f2(obj, d)` queues it; then the pooled effect objects (`3546:040a` iteration):
flak bursts (`+18h & 0Fh == DS:54B5`) → `04c4:0b53`, others → `33d1:0140` (the player's own
effects are skipped in view classes 2 and 3); `34bf:0006()` sorts and draws;
`277a:09B2 −= (488e:00b0() == 0)`. The object draw callback `5440:0269` (`fn_54669`) dispatches
by object kind (`*obj & 1Fh`): 0Fh → `0916:0273` (parachute), 0Eh → `1560:06e9` (explosion),
12h → `2466:0023` (far dot), 05h (not hidden) → `05d6:01d3`, else `33b4:010e` + `277a:002d/0012`,
0Bh → `2ecb:00ba` (shadow), else `2f0e:08e9` (shape), `277a:0037`; every second call
`1c0f:0053()`. **Hand-off render3d:** spec `5440:03aa` and `5440:0269` in `render3d.md`
(sim_flow lists them as owned by render3d in its symbols with a note).

## 7. Command handler `5440:0aee(ctl)` — verified

Called once per step (§6.1). `CB = P + ACh` (player control block: `+00 roll, +02 pitch,
+04 rudder, +06 throttle 0..FFh, +0C`, `+0E` flags: bits 0–1 flaps 0..2, bit 2 dive brakes,
bit 3 wheel brakes, bit 4 gear down; `+0C` ground height under the aircraft). Returns 0.

1. **Stick**: if blacked out (`DS:579A`) → `CB+00/02/04 = 0`, skip to step 4. Else if `ctl.0E & 2`
   (fire2 held — the stick pans the view) → `CB+00 = CB+02 = 0`; else `CB+00 =
   stick_curve(ctl.00 << 3)`, `CB+02 = stick_curve(ctl.02 << 3)`; always `CB+04 = ctl.04 << 4`.
   `stick_curve` `5440:0abb(int v)`: `r = sdiv32_16_sat((long)v·v, 240)`; `v < 0 → −r` (a square
   law: input ±127 → ±1016 → ±4301).
2. **Stopped on the ground/deck** (`P+70h/72h/74h` velocity all 0 and `P+4Ah == 458h`): if
   `CB+0C + model(P+66h)+98h ≥ P+0Ch` (at or below ground level + gear height, sign-extended
   compare), `P+12h == 0`, `P+1Ah & 1 == 0`:
   * home airfield (`byte [P+34h (flight)]+3` == 0): if the distance (`277a:3b3c`) from `P+4` to
     the flight's base object (`[flight+4]+4`) ≤ 4268h (17000): `DS:5C98 = 1`, `5da1:0000(3)`
     ("landed at base" end alert, ui part);
   * else if `CB+0C > 0` and on a ship (`P+EFh`): `DS:5C97 = (P+1Ch & 8 && !(P+1Ch & 10h)) ? 2 :
     1`, `10bf:013a()`, `5da1:0000(2)` ("landed on the carrier").
3. **Radio menu** (`DS:1206` open): if `DS:4348 == 0`: `n = 1660:110f(buf, 8)` (current
   recipients list); if `n != DS:434A` or the list differs from `DS:434C`: store it, `6e5a:0000(n,
   buf)` (redraw the menu), `DS:4090 = 2`, `5b93:01e2()`, `5cde:0000()`, `DS:434A = n`. Then `r =
   6e5a:03a1(ctl.10)` (menu key); `r > −1` → `ctl.10 = r + 18h`.
4. **Menu open request**: `ctl.10 == 9` and the menu is closed: `1660:0f6e()`; `DS:434A =
   1660:110f(DS:434C, 8)`; if non-zero: `6e5a:0000(DS:434A, DS:434C)`, `DS:4348 = 0`.
5. `DS:4362` (unjam timer) ≠ 0 → `timer16_dec(DS:4362)`.
6. **Gear forced down on the ground**: unless (`DS:42D3 && DS:42CF`), if alive, gear up (`CB+0E`
   bit 4 = 0), `DS:0FEC == 0` and on the ground (`CB+0C + model+98h ≥ P+0Ch`, s32 compare;
   `CB+0C` = ground/deck height under the aircraft, `model+98h` = gear height, `P+0Ch` =
   altitude): `CB+0E |= 10h`; gear shape state `[P+16h]+1 = 271b:043d(P+2, 1) − 1` (last state
   = fully down); message STR(1, 20h).
7. **Commands** `ctl.10`, jump table `5440:12a1` for 2..0Dh:

   | Cmd | Key | Action |
   |---|---|---|
   | 2 | U | unjam: only if a jam is set (`DS:4364` or `DS:4366`) and `DS:4362 == 0`: `r = 1889:005f(DS:4454) & 1023h`; `r < DS:4360` → cleared: `DS:4364 = DS:4366 = 0`, STR(1, 3) (duration 5); else `DS:4360 += 25`, `DS:4362 = 4000`, STR(1, 4) |
   | 4 | L | landing gear (bit 4 = down): ignored while `DS:06B5` ≠ 0 (moving) or the model has fixed gear (`model+76h`). Down → if on the ground nothing, else `CB+0E &= ~10h`, `DS:06B5 = −1` (retract); up → `DS:06B5 = 1`, `CB+0E |= 10h` (extend). Step 9 animates |
   | 5 | F | flaps: `CB+0E` bits 0–1 = (flaps == 2 ? 0 : flaps + 1); unless `DS:42D1`: STR(1, 22h + flaps); `DS:435C = 4` (flap motor sound frames) |
   | 6 | B | dive brakes, only if `DS:3FD1 & 2` (the aircraft has them): toggle bit 2, STR(1, 1Ch + bit), `DS:435E = 4` |
   | 7 | W | wheel brakes: toggle bit 3, STR(1, 1Eh + bit) |
   | 8 | D | drop tanks, if `P+1Ah & 4`: STR(2, 9), `6cc2:0000(P)` |
   | 0Ah | fire4 | `0ff4:0001(P+5Eh)` (select weapon station) |
   | 0Dh | Ctrl+B | bail out: altitude `P+0Ch < 6000` → STR(1, 3Ah) (too low); else if not blacked out (`DS:5798 < 3000h`): G `DS:579B ≥ 280h` → STR(1, 47h) (too many G); else `DS:5C8F = 1`, `5da1:0000(4)` (bail-out end alert) |
   | 3, 9, 0Bh, 0Ch | | nothing here (handled in `sim_step` / step 4 / `5440:0969`) |
   | 18h–1Eh | radio menu | if the menu is open and `ctl.10 − 18h < DS:434A`: `if (1660:0f85(DS:434C[i], i)) DS:4348 = 1` (send the radio command; cockpit part) |

8. **Timed run** (`-t`, `DS:053A`): when `timeout_expired(DS:4334)`: `n = DS:053C > 100 ? 100 :
   DS:053C`; `n ≤ 0` → `sim_exit(1, 0)` (exit code 1 = INTRO: the attract-mode / benchmark loop);
   `DS:053C −= n`; `timeout_start(DS:4334, n · 236)` (n seconds).
9. **Gear animation** (`DS:06B5 != 0`): `s = [P+16h]+1 += DS:06B5`; if `s > 0` and `s < states − 1`
   (`271b:043d(P+2, 1)`) keep going (sound `5a75:0eea(0Dh, P+4, P+70h, 1)` if `DS:19F2`); else
   STR(1, DS:06B5 == 1 ? 20h : 21h) unless `DS:42D1`, sound 0Eh, `DS:06B5 = 0`.
10. Flap / brake motor sounds: `DS:435E`, `DS:435C` frames → sound 0Dh each frame, decremented.

`DS:19F2` = outside-sound audible flag (sound part). Sound calls `5a75:0eea(id, pos, vel, 1)`.

## 8. Other sim_flow helpers in the resident part

| Address | Name | Behaviour |
|---|---|---|
| `50c0:0080` | `debug_mode()` | returns `DS:053F` |
| `4b9e:0000`, `4b9e:0005` | — | empty debug hooks (`retf`) |
| `36ee:0003` | `disk_free(drive)` | free disk bytes (vcr part) |
| `4bcd:*`, `5155:*` | findfile.c, modules.c | file exists / directory listing `_files_.out`, add-on modules of films — documented in `sim_flow_vcr.md` (`4bcd:01df(name)` = `fopen(name,"rb")` succeeds → 1, used here for `sim.out` and `-S`) |
| `519d:0000` | `file_load(buf, size, count, name)` | `fopen(name, "rb")` (fatal `2494:0127` if missing), `fread(buf, 1, size·count)` (fatal if short), close — used for `sim.in` |
| `519d:008a` | — | empty |
| `55a4:0000` | `res_name(name, ext)` → char* | `n = 368f:02e6(name, ext)` (name + extension); if `DS:06F8` (resources from volumes) return `n`; else build `DS:44CA` = (current dir string) + `"\"` + `n` and return it |
| `55a4:007f` | `res_chdir(dir)` | unless `DS:06F8`: `chdir(dir) == 0` |
| `55a4:00a2` | — | `res_chdir("..")` |
| `55a4:00b1(far p, long *list)` | | counts/links a chain of loaded blocks (**likely**, used by `01f0`) |
| `55a4:0108(far dst, long n, f)` | `fread_far` | byte-wise `fgetc` into a huge pointer (`PADA@` increments) |
| `55a4:0167(name)` | `res_exists` | `fopen(name,"rb")`, close |
| `55a4:01b5(char *s, int n)` | | patches the add-on digit of a name when module bit `n−1` of `DS:44E8` is set (**likely**: `M1` names) |
| `55a4:01f0(…)` | `res_load_set` | loads the numbered name lists (`pfname<n>`/`sfname<n>.TXT`, mask `header+06`) into one buffer and builds the pointer tables (snario caller `56ac`); **likely** |
| `55a4:03a7(far **p)` | | `24b2:01c0(*p)` (far free) |
| `55a4:03d9` | `modules_detect()` | `DS:44E8 = 0`; for `i = 0..`: patch `M#SHL.DYN` (`DS:06FA`) with digit `'1'+i`, `fopen(…, "rb")` → set bit i (add-on volumes present) |
| `55a4:0429` | `modules_mask()` | `DS:44E8` |
| `55a4:0440` | — | `59eb:0000()` (stars init thunk) |

## 9. Port notes

1. **Frame pacing** (§4.1): virtual PIT at 236.69 Hz; minimum 8 ticks per frame; dt from the
   measured ticks rounded down to 4; the port measures host time in virtual ticks. The busy-wait
   becomes a sleep. `DS:31E5`, `DS:18D2` are updated from the host clock (or the timer thread
   of the platform layer) — the platform spec's timer model must keep the saturating decrement.
2. **CPU benchmark** (`4e0d:0835`): return a fixed value (fast branch) so defaults do not depend
   on emulation speed.
3. **EMS / overlays**: `36f6:08ed` and the EMS page count are irrelevant; keep `DS:0539`/`DS:4030`
   values for code that reads them (`0539` is read by the cockpit and VCR code: EMS class 3/4).
4. **Keyboard**: the scancode ring buffer and held-key table of the platform layer must produce
   the same scancodes (set 1) and BIOS-style shift bits; screenshots (Alt+T, Ctrl+Alt+F10) can
   write PNG instead of IFF (`/* PORT: */`).
5. **Exit codes**: `sim_exit` returns to the chain loop with the code (2 PS, 1 INTRO, 0 quit) and
   sets the marker; text mode restoration is a no-op.
6. **Debug switches** (`nlkle` + `-s -S -x -t -W -w -d -m`) can be kept as port command-line
   options; `-d` (demo films) and `-w` (recorder) are useful for testing.

## 10. Hand-offs

* **render3d**: `world_draw 5440:03aa` and the object draw callback `5440:0269` are 3D drawing
  (§6.2 gives the call order); camera object `DS:437E` (created by `271b:0251(DS:4368)`, window at
  `+0Ah..+10h`), camera position `DS:436A` (3 × s32) / angles `DS:4376..437A` set by
  `camera_follow 5440:0000` with the model eye point `model+77h`; `277a:3dc1` = saturating 32/16
  signed divide, `3684:00a1` = bit length; the per-frame effect hooks `05a9:00ad/014c`; the
  slider-driven detail entry points `4b9f:0018/00d0` (§4.3) call `333b:0158`, `4d6e:0000`,
  `1a8b:001e`, `33a1:0008` and write LOD thresholds into the shape-bank records `DS:647C`
  (`+6`, `+8`) from the tables `DS:0222` / `DS:0234` (8 words each).
* **sim_world**: the player's control block `P+ACh` (§7: stick/rudder after `stick_curve`,
  throttle `P+B2h` 0..FFh, flags `P+BAh` = flaps/dive brakes/wheel brakes/gear) and `P+ABh`
  (cleared each step when `DS:42CF == 0`); gun firing entry `0769:009a(0, P, P+10h, {P,0Fh,1})`,
  ordnance `0deb:1500/0221/1490/000a`, weapon station `0ff4:0001(P+5Eh)`, drop tank `6cc2:0000`,
  carrier bookkeeping `10bf:013a`; world per-frame calls and their order in `sim_step` (§6.1);
  every world timer uses `362b` (§4.3): dt `DS:711E` is 100h per nominal step of 20 ticks at
  time scale 20. `5440:0375` (range helper) is called only by `583c`.
* **platform**: `timer_isr` must keep `DS:31E5` saturating at 0 (the flight loop depends on it);
  `0000:02db` tick callback `DS:18D2`; key ring buffer `1d32:0939`, key-down table `1d32:0978`,
  keypad direction `1d32:095e`, scancode→ASCII `1d32:098c`, joystick reads `1d32:04e5/055e/063f`,
  mouse `1d32:5d6a/5dbf`; `1d32:012a` = keyboard + mouse + timer + divide-error restore;
  `0000:1a70/1ab0` INT 24h handler install/restore; `0000:122b` closes the log file `DS:1EBA`.
* **video**: `368f:03b6/03c1/03cc/03d7/03e2/03ed` page selection, `368f:017f/01a3` dissolve,
  `368f:01f2` full blit, `1d32:540b` show page, `715b:0000` SCR display (end picture `clouds`),
  `244d:000b/0087` 2D context save/restore.
* **sound**: `5a75:0afa` (init with `sx1`, `simsnds1.sng`, driver `DS:43B3`, no-sound flag),
  `5a75:0a0a` (per-step update), `5a75:0e96` (silence before dialogs), `5a75:0d39(0)` (off at
  exit), `5a75:0d66(v)` (sound on/off), `5a75:0a01` (toggle, returns the new state),
  `5a75:0eea(id, pos, vel, 1)` (positional effect: 0Dh flap/gear motor, 0Eh gear locked, 15h bomb
  release).

## 11. Open questions

* Unit of the mission clock `DS:3F36` (1 = 5.12 nominal steps) and why the benchmark picks a
  slower time scale (divisor 50) on faster machines (§3.2) — is div 20 really "real time", or is
  the nominal step shorter than 20 ticks in the flight-model tuning? (sim_world may settle it
  from the physics constants.)
* `5f2c:08fd`: the outside-view throttle-notch state machine (decompile broken, cockpit part).
* CONTROL.PRF `+04`, `+09`; SIMPREFS `+08` (`DS:43AF`).
* `60a9:017c` looks like a mis-seeded code fragment (jump table) — confirm it is not a function.
* `DS:42D1` (suppresses the cockpit messages) and `DS:42CF`/`DS:42D3` — realism bytes of
  `DS:42C8` (`?REAL.PRF`, ui part).

