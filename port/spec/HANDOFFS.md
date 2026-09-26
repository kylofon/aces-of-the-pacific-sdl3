# Phase 3 hand-off reconciliation

Every "Hand-offs" / "Open questions" item of `port/spec/*.md` (as of the phase-3 wrap-up), checked
against the receiving spec(s) by searching for the addresses/globals named in the hand-off and
reading the hits. Statuses: **done** = the receiving spec now covers it (file named); **open** =
nobody covers it yet; **conflict** = two specs disagree — every conflict is listed again in §2 with
the resolution taken from the disassembly (x86dis). Other specs were not edited; format corrections
were folded into `port/formats/*.md` and `FORMATS.md` (§3).

Totals: **168 items — 121 done (S1/Z8 partly), 36 open (22 of them are the sources' own internal
open questions), 11 conflict.** §2 lists 16 cross-spec conflicts (C1–C16, all resolved) plus the
naming-only conflicts of `symbol_conflicts.txt`.

## 1. Hand-offs and open questions by source

### platform.md, platform_resources.md

| ID | → | Hand-off | Status | Where / note |
|---|---|---|---|---|
| P1 | sim_flow | AP joystick calibration `DS:4F60/4F6C`, `60a9:097d`, throttle step from `DS:4F5E` | done | sim_flow.md §3 (CONTROL.PRF table), §5 |
| P2 | video | `gfx_init` args/driver entries, shell_exit hand-over `DS:0A92..`, `vqt_predecode 0ef8:000e` | done | video.md §2–4, video_pictures.md |
| P3 | sound | sound-id mapping 4/7→2, 88h MT-32 no-reset, CONTROL.PRF +08/+09, `ttd.sx` | done | sound.md §7, §15 |
| P4 | sim_flow | `prefs_load/save`, far copies `3974:…`, `-s -t -W`, `sim_exit` callers, `DS:0539` EMS tier | done | sim_flow.md §2–3 |
| P5 | shell_ui | `intro_play 038e:0973`, `fly_mission 048e:01a0` | done | shell_ui.md |
| P6 | render3d/sim_world/sim_flow | 16-bit divide overflow = INT 0 halve-and-retry (`1d32:69cc`) | done | render3d_math.md §1.4; a port-wide rule (sim specs do not repeat it) |
| P7 | render3d/sim_flow | EMS pool users: is `pool_free` LIFO (needed by `pool_trim`)? | **open** | not checked by any owner; irrelevant if the port drops EMS (`/* PORT: */`) |
| P8 | video | AP-only 1d32 hooks `1cac–1e9d`, `1eca`, `6d55`, `244d:*`, PS `16e3:065d…`, `05da:5f2e–5f83`, `45d3` | done | video_library.md; `05da:3b32` mouse VGA save stays in platform.md §3.5 |
| P9 | sim_flow/sound | CONTROL.PRF +06/+07/+0A..+0C meaning | done | sim_flow.md §3 table (joystick, mouse, sound, devices); **conflict C12** on +04 |
| P10 | sound | can `5a75:0c81` install the timer a second time? | done | no: sound.md §12.2 — `sx_init` (sound on) and `4e0d:0168` (sound off) are exclusive paths |
| P11 | — | Windows task-switch flags only written with 0 | done | sound.md §12.1: `win_task_switch 2466:0118` has no caller (dead) |
| P12 | — | AP limit of 3 open `my_fopen` files not cross-checked | **open** | |
| R1 | sound | `pk_seek` never ends on a truncated stream: decode whole chunks | **open** | port note only; sound.md does not mention it |
| R2 | video | TTM loader `1125:002f` / AP `24fc` | done | video_ttm.md |

### render3d.md, render3d_sky.md, render3d_world.md

| ID | → | Hand-off | Status | Where / note |
|---|---|---|---|---|
| D1 | platform | INT 0 handler load-bearing | done | platform.md §3.6 |
| D2 | video | fill `09ce`, ellipse `6bbc`, sprites `5e5b/2258`, `DS:26DF`, `DS:26C3`, table `DS:351A` | done | video_library.md, video.md; `1d32:2258` = `bmp_draw_ems_rotated` (platform row) |
| D3 | sim_world | object draws `0916:0273`, `05d6:01d3`, flak, clouds/LOS `490a`, `583c:04a9`, `6ac7:0120`, wrecks, `DS:5798` | done | sim_world_dmg/wpn/ai.md |
| D4 | video | span fill `09a8`, rect, pixel, bitmap, DAC queue | done | video_library.md, video_palette.md §8.3 |
| D5 | sim_world | `07fe:000a` (ces.c) "is a 4-point bitmap draw primitive" | **conflict** | §2 C9: it is the `ces_check` assert, no drawing |
| D6 | sim_world | world unit in metres; `.BMD` effect ids `0916:002e`, `4b3a` | open (unit) / done (ids) | unit still a guess (¼ ft, sim_world_fm.md) |
| D7 | sim_flow | VCR hook `1c0f:0053` order, `4899`, `644a:089f`, `1c30:0780`, detail slider, `sky_init`, `6964:0076` | done | sim_flow.md §4, §6 |
| D8 | sim_flow | `519d:008a` SHADES1 → `DS:4092`, eye `DS:4368`, window `DS:06AD..06B3` | done | sim_flow.md §6 |
| D9 | — | `CS:09B1` use, `2e33:0333` matrix element, shadow colour `DS:2402` producer, `62d2` loader details, `DS:36D0`, horizon geometry | open | render3d-internal questions |
| S1 | sim_flow | time-of-day clock `6964:*`; **`DS:1132[tod]` labels (clock runs backwards?)**; `sky_init` inputs; `DS:42C8/42C9` options; `5440:083a` | done except labels | labels: **open** (no spec maps `DS:1132` to the shell's time names) |
| S2 | sim_world | `490a:017f`, `0802:0173`, channels 11/12, `490a:0509`, `583c:0471`, `655d:038a`, `655d:1bb7` | done | sim_world_dmg/ai.md; `0802:0173` is render3d's own (`range_cull`) |
| S3 | platform | DAC write `0000:189b`, allocators, RTL | done | video_palette.md §8 (DAC), platform.md §5 |
| S4 | video | gfx calls; BMP load/free `7229:01aa/056a` | done | video_library.md; `7229` rows are platform's (`bmp_load_planes`) |
| S5 | render3d/sim_world | who sets bit 80h of moon/star records (`DS:1128`)? | **open** | never set in AP as far as searched |
| S6 | — | sun-glare day test always true; one-month date offset quirk | done | render3d_sky.md keeps both (faithful) |
| W1 | sim_flow | `5440:018c/009c`, `4899:005c/0027`, `DS:00F8`, `1c30:09a9`, `14b8:000d`, `4b9f:00d0`, `DS:70FA`, **`51ca:008d` "VCR string reader"** | done / **conflict** | §2 C11: `51ca:008d`'s only caller is the dead `5b71:0118` (sim_flow_extra.md), not the VCR |
| W2 | sim_world | object type/flags, spotting, wrecks, `GDAMAGE.DAT`, `DS:474D`, area lists, `59f9`, target lists 2 and 4 | done | sim_world_dmg/ai.md; lists 2–4 in world.md §5 (§3 below) |
| W3 | video | pixel `6a5b`, window `DS:26C3..26CA` | done | video.md, video_misc.md |
| W4 | sim_world | object types 0Ch/0Dh; `z == 0/1` cases of `465c:0589` | **open** | |
| W5 | — | `DS:18C0` only zeroed; `DS:55D9` never updated; `33d1:04e7` tile test without `<< 8`; `.FLT +0Bh`, GID bytes +8/+9 | open (intent) | behaviour verified, faithful port keeps it |

### shell_data*.md

| ID | → | Hand-off | Status | Where / note |
|---|---|---|---|---|
| SD1 | sim_flow/sim_world | SIM.OUT meanings from the PS side | done | agrees with the AP writer (sim_flow_results.md §7.4) except +06/+0E: **conflict C5** |
| SD2 | shell_ui | `125a:000f`, RNG seed `DS:42C1`, reseed `0787:0181`, fltplan shared with `12c4:02d4` | done | shell_ui_mission/flight/debrief.md |
| SD3 | platform | `1193:0ad2` = INTRO `038e:04d6`, `DS:0DFF`, `16e3:49c1` | done | platform.md, platform_resources.md |
| SD4 | video/render3d | PS `3d50` math library has no owner | done | video_ts.md §2.1 maps every `3d50` routine to AP `277a` (render3d_math.md) |
| SD5 | platform | `DS:00C5` debug seed writer | done | platform.md §2: `-r<n>` → `rand_seed_opt DS:00C5` |
| SD6 | — | header +03/+05/+0E, group +01..+04/+1E, aircraft +04..+06 `80 00 80`; pilot +26h, +2Dh..+2Fh | **open** | see M1 |
| E1 | platform | `qsort 0000:3c66`, `_fstricmp 0000:4858`, chunk API `16e3:55f8/568e/59a5/59d4` | done | platform_resources.md §6 |
| E2 | shell_data | extens.c `2008` id mapping, date.c `284f` | done | shell_data_sys.md, shell_data_emd2.md |
| E3 | formats | `.SCD` layout; world.md §5 lists 2/3/4 | done | scripts.md, world.md (§3) |
| E4 | platform | `16e3:568e` flag 0 vs FFFFh | done | platform_resources.md: `n >= 1` n-th, `0` next, `−1` again |
| E5 | — | ACETAB `+02/+05`, unused first tables; squad `+03` role, ace career types 2..5 | open | inferred from data only |
| F1 | video | `3d50` atan2/sin/cos/dist/mul/midpoint exact approximations | done | video_ts.md §2.1 → render3d_math.md |
| F2 | sim_world | `FORM.DAT` position codes, `ORDTXT` codes = SCRIPT group +01 / ordnance slots | **open** | no sim_world spec names FORM.DAT/ORDTXT; the AP side of the formation id is in `fly_formation_slot` (sim_world_ai.md) without the link |
| F3 | — | AIR `+0A/+0B`, WLDFGEN `+15`, CMP `+02`, MISSINF L5 class order | open | |
| M1 | sim_world | flight +04 (1..6) / +09 (0..2) → SCRIPT group +03 / +1E = AI behaviour codes | **open** | sim_world_dmg.md "open questions" still lists the 58→56h record mapping (`56ac:0b78/0c6a`) |
| M2 | shell_data | `2777:04fa` second argument | done | shell_data_emd2.md |
| Y1 | shell_data | `mission_load` callbacks `3164:34ad…371d`, `3164:3efe` | done | shell_data.md |
| Y2 | shell_ui | `21f4:0245`, `2171:000a`, `22a0`, `230d`, `2316`, `22ce`, `2221` hook, `0ddd:0094` | done | shell_ui*.md (naming conflict X2) |
| Y3 | video | threed.c ts calls `48ea/47c8/4708/48ac`, `DS:3B53/3B55/2303` | done | video_ts.md |
| Y4 | video | TTM `3baf:0540` → hook `2221:0111`; `22a0` timers | done | video_ttm.md, video_palette.md §6 |
| Y5 | shell_ui | which TTM scripts call hooks 1/2 (`0874:0aa5`) | **open** | shell_ui_debrief.md names the hook, not the scripts (video_ttm says: 3 award scripts use `2012`) |
| Y6 | — | hist entry `e0/e4/e6`, `RANKS.DAT +5`, `MEDLOCS.DAT` first word, threed object axis | open | |

### shell_ui*.md

| ID | → | Hand-off | Status | Where / note |
|---|---|---|---|---|
| U1 | platform/formats | `vol_fopen` opens loose files first; resources.md §1 / scripts.md §2 wrong; `0000:0512`; `227c:0034`; `16e3:291b` | done | platform_resources.md; formats corrected (§3) |
| U2 | video | shell page roles, flip/copy/save thunks, `31E8` mirror flag, INTRO `DS:33C8` units | done | video.md §4.2, video_library.md, video_ttm.md |
| U3 | sound | shell ids 18h/19h/1Ah/3EAh; `315c` toggles | done | sound.md §11 |
| U4 | sim_flow | PS marker 29Ah / 3E7h | done | sim_flow.md §2 |
| U5 | shell_data | names of the `fatal_line` globals; `3164:23e3`; `0a71:015c` | done | shell_data.md; `0a71:015c` = shell_ui `dialogs_init` |
| U6 | shell_data | pilot +34h campaigns completed, +10h backup label, `DS:49CE`, `pilot_delete` offset bug, `DS:651E/6526`, `DS:0B26` | done | shell_data.md §4, shell_data_emd2.md |
| U7 | formats | layouts of `WLDNMS/WLDLOCS/BIGMAP/ACEFACE/PITCH_/TTMS<n>/MEDLOCS/FLTDECK<n>/DATE<n>` for data.md | **open** | layouts are in shell_ui_flight/career.md; not copied into data.md (a pointer is enough) |
| U8 | video | `draw_bitmap` flag 2 = mirror; `3d50:3E91/3E93/3DF8` | done | video_library.md, video_ts.md |
| U9 | — | `fm2_apply` off-by-one, `fm2_slot_label` kind 4, `dg_frame` result | open | original bugs to confirm in DOSBox |
| B1 | shell_data | SIM.OUT +06 u16[4] **is read** (type-3 events); +0E compared with type-4 ids | **conflict** | §2 C5 |
| B2 | shell_data | TOPMISS temp record `DS:4308` built by `09a9`, not `0874` | **conflict** | §2 C6 |
| B3 | shell_data | pilot status 1 = "retired" | **conflict** | §2 C7 |
| B4 | formats | `EVENTS<n>.EVT` decoded | done | data.md §3.4 now points to shell_ui_debrief.md §7.1 |
| B5 | shell_data | `HIST_*` single service, `1f85:03e9` row mapping | done | shell_data_sys.md |
| B6 | shell_ui | code segment `0cfe` not in the index | done | specced in shell_ui_debrief.md §8 (index gap: N1) |
| B7 | shell_ui | cross-part calls (fltdeck, squadinf, bigmap, best, campaign, realism, career, mission parts) | done | shell_ui*.md |
| B8 | video | `3a73:0085` region dissolve; `16e3:36dc` font height | done | video_ttm.md, video_library.md |
| B9 | sound | shell ids 1002/1004/1010/1015; `snd_stop(−1)` | done | sound.md §11 |
| B10 | — | `DS:4779` at `sim_end` start, `2624:05a6/011d`, `DS:43B5`, add-on event types 1–4 | open | |
| N1 | (tools) | code segment `0cfe` missing from `ps_functions.json`; `147e:0143` inside `147e:011f` | **open** | `spec_coverage.py` cannot see them — re-run `apindex.py` with `0cfe` as code |
| N2 | shell_data | `3d50:0102` isqrt, `2a56:01fa`, `2ab3:0504`, `0f67:*`, `.CMT` header | done | video_ts.md (`isqrt32`), shell_data_emd2.md, shell_ui_career.md; `.CMT` in shell_ui_mission.md |
| N3 | sound | shell ids 3ECh (KIA), 3F7h (inquiry) | done | ids documented in shell_ui_debrief/mission.md (they are plain `snd_play` ids) |
| N4 | — | `147e:0424` insignia constants; `2171:000a(DS:0E18)` | open | |
| O1 | shell_data | `24b7` RNG, best-mission record, `1f85:0833`, `22ce:032d` | done | shell_data.md, shell_data_sys.md |
| O2 | platform | joystick reads `16e3:01e3/0339`, detection `16e3:00ac` | done | platform.md §3.4 |
| O3 | — | `0b48:0006` remap tables, `DS:4F22` reader | open | |

### sim_flow*.md

| ID | → | Hand-off | Status | Where / note |
|---|---|---|---|---|
| L1 | render3d | `world_draw 5440:03aa`, `5440:0269`, camera globals, `277a:3dc1`, `3684:00a1`, `05a9:00ad`, detail tables `DS:0222/0234` → `DS:647C` | done | render3d*.md (naming conflict N-a); the LOD tables are only in sim_flow.md §4.3 |
| L2 | sim_world | control block `P+AC..BA`, `P+AB`, firing entries, `362b` timers, `5440:0375` | done | sim_world_fm/wpn/ai.md |
| L3 | platform | `DS:31E5` saturating, `0000:02db` tick, key ring, restores, INT 24h, log close | done | platform.md §3–4 |
| L4 | video | `368f` page selection / wipes / blit, `715b:0000` SCR, `244d` context | done | **video_misc.md** (new), platform (`715b`), video_library.md |
| L5 | sound | `sx_*` call sites | done | sound.md §12 |
| L6 | sim_flow | `60a9:017c` "mis-seeded fragment?" | done | resolved here: a real far function `button_latch_clear(n)`: `n` 0..3 → `DS:4F7B/4F7A/4F79/4F78 = 0` via the 4-word table at `60a9:01aa` (n > 3: nothing). The CSV row name `input_frag_017c` should be renamed |
| L7 | — | benchmark divisor 50; `5f2c:08fd`; CONTROL.PRF +04/+09; SIMPREFS +08 | open | lead decisions / unread |
| C1 | video | TTM `24fc:0610`, sprite sets `1d32:214e/2170/21b6`, `26d2`, `6f97:0000`, `1d32:09bb` | done | video_ttm.md, video_pictures.md; `1d32:214e..` are platform rows (EMS sprite sets) |
| C2 | sim_world | cockpit inputs `DS:3EF5..`, `3FE2..`, `57DD..`, `523B` | done | sim_world_dmg/wpn.md |
| C3 | sim_world | "`1660:07bb/0bae/0c12/0c47` already rowed by sim_world" | **conflict** | §2 C1 |
| C4 | render3d | `644a:089f` window/eye row | done | render3d*.md |
| C5 | sim_flow/sim_world | who passes a speaker to `msg_show`? | done | nobody: every caller found passes 0 (incl. `kill_credit`, sim_world_extra.md) |
| C6 | — | six patched driver vectors; `P.94h` units | open | |
| RA1 | sim_world | `DS:18EC` is a word table | done | resolved in sim_flow_radio.md (x86dis `mov ax,[bx+18ECh]` after `shl bx,1`) |
| T1 | sim_world | `goal_update` status bits, `kill_credit`/`target_credit` contract, ship `+78h/+7Ah`, `DS:5C97` writers | done | sim_world_dmg.md §5 (naming conflict N-b) |
| T2 | shell_data/formats | SIM.OUT +0E, +20 | done | data.md §1.2 rewritten (§3) |
| T3 | sim_world | `P.AB` values 1..3, `DS:0FEB == 2`, `obj.1B & 80h/40h/20h` | done | sim_world_dmg.md (`P+AB` landing damage/status), sim_world_ai.md §16 (`1B` bits) |
| I1 | sim_world | realism users; `DS:4E74` writers `088a:0007`, `10bf:00d2`, `655d:159d`; `.BXL` | done | sim_world_dmg/ai.md |
| I2 | video | `715b:0000`, `7229:01aa`, `6f97:0000` | done | platform rows / video_ttm.md |
| I3 | shell_ui | AP dialog library mirrors PS `2b4f/2c11/2dd0` | done | shell_ui_toolkit.md (equivalence in sim_flow_ui.md §6) |
| I4 | — | map icon kinds (`6cdc:0161`), dialog event 20h | open | |
| V1 | sim_flow | `5cde:0405` recording contract, `DS:5060/5064` | done | sim_flow.md §6 |
| V2 | sim_flow | `5cde:0080` data blocks, `5f2c:05d1` alphabet ranges, `5440:1317` unrecorded fields | done | sim_flow.md §5–6 |
| V3 | sim_flow | `60a9:02c4` consults `5b93:0153` | done | sim_flow.md §5 |
| V4 | sim_flow | `618d:04e4` results discarded | done | sim_flow.md, sim_flow_results.md |
| V5 | render3d | the draw path must not use the sim RNGs `DS:4454` / `DS:43DE` | done | resolved here: the draw path uses **`DS:43DE`** (`655d:038a` gun smoke/flash, called from `draw_frame`; render3d_sky.md §4.3) but no sim logic reads `DS:43DE` (decompile: only `655d:038a` calls `1889:005f(43DE)`), and `DS:4454` is never used by draw code → playback stays deterministic; `DS:43DE` is the "visual" RNG (the cockpit puffs use `rand()`) |
| V6 | sim_world | `4edf:068a` frame counter via `5d3c:0064`; add-on flag readers | done | sim_world_ai.md |
| V7 | sim_flow | dialog library item layout for `VCR.BOX` / `tapes.BOX` / `lbox.BOX` | **open** | only sim_flow_vcr.md; the "dirty" item bytes (43h) are not mapped to the dialog item structure |
| V8 | formats | data.md §5 superseded | done | data.md §5 now points to sim_flow_vcr.md §2 |
| V9 | sim_flow/video | purpose of the one-time fade `5d56:0000` / `50c8:0000` | **conflict** | §2 C2 (`50c8:0000` = debug flag) |
| V10 | — | control +0E/+10 bits, view +00/+02, slider 0, `DS:19F2` | open | `DS:19F2` = inside-cockpit view per sound.md §15 |

### sim_world*.md

| ID | → | Hand-off | Status | Where / note |
|---|---|---|---|---|
| A1 | sim_flow | order codes via `1660:01bc`, radio ids, `DS:57E8`, `5d3c:0064` | done | sim_flow_cockpit.md §7, sim_flow_radio.md |
| A2 | sim_flow | `1660:07bb/0bae/0c12/0c47` neither rowed nor specced | **conflict** | §2 C1 — now **sim_flow_radio.md** |
| A3 | sim_flow | writer of `player+44` bit 0 (tested by `1284:01a3`) | done | sim_flow.md §7: fire2 → `0769:009a` success → `P+44h |= 1; P+48h |= 1` |
| A4 | render3d | `277a:5fae`, `277a:512e/4cb3`, `5137:*`, `277a:4eb6` | done | render3d_math.md / sky.md rows |
| A5 | ? | builder of the hostile plane lists `DS:5CCC..5CD8` | done | sim_flow_results.md §3 `results_init 5254:0000` (`DS:5CD2/5CD6` counters) |
| A6 | sim_world | `Plane+42` bit 0 never set → state 0444h unreachable | **open** | confirm with a film |
| A7 | — | `1142:05ce` role-2 branches from the decompile; `0deb:0896` low == 1 never releases | open | verify with x86dis before porting |
| G1 | sim_flow | flags `DS:0FEB..`, `42BD..`, `57DD..`, `3EF5..`; `1899:*` contract; `5da1:0000(1)`; `10bf:013a/01d6` | done | sim_flow_results/ui/cockpit.md |
| G2 | render3d | effect object `05a9:005a`; GID query `3368:0069`; `490a:0509` | done | render3d_sky/world.md |
| G3 | formats | PFNAME/SFNAME, `.MEC` sizes, `.DAT+0`, `.WND` | done | data.md corrected (§3) |
| G4 | — | `56ac:0b78/0c6a` Ghidra-garbled; `.DMG` fields; PLT ratings | open | |
| H1 | render3d | `277a` math semantics; helper segments `35ff…3684` ownership | done | render3d_math.md (ownership: sim_world rows stay, merge priority settles names) |
| H2 | sim_flow | `ts_frame 362b:008f`, `DS:7118`, `DS:3712`, control input, `DS:576B` writers | done | sim_flow.md §4, sim_flow_ui.md |
| H3 | sound | `plane_engine_sound` call sites, `DS:02D4/02DA`, gear latch | done | sound.md §12.5, §15 (the two specs agree after sim_world_fm's fix) |
| H4 | — | world/speed unit; FMD `+92..+B4`; `Controls[4]` | open | |
| K1 | sim_flow | firing entries, weapon camera `05d6:*`, flags, gauges | done | sim_flow.md §7, sim_flow_cockpit.md |
| K2 | render3d | class draw callbacks, effects, `1560` | done | callbacks are sim_world rows (sim_world_wpn.md); `1560:06e9` in render3d_sky/world.md |
| K3 | sound | sx ids, gun sounds `DS:1362` | done | sound.md §12.5 |
| K4 | — | BULLETS/BOMBS/ROCKETS/TORPS unexplained fields; burst flag 4000h; `6ac7` box clip | open | |

### sound.md, video*.md

| ID | → | Hand-off | Status | Where / note |
|---|---|---|---|---|
| Q1 | video/formats | TTM C000 dispatch; `C0E3` = fade (rename) | done | video_ttm.md; scripts.md corrected; `tools/dynttm.py` still says `SND_C0E3` (tool, open) |
| Q2 | platform | CONTROL.PRF sound fields, `soundDrv`, `-s<n>`, timer in `snd_init`, pk stream fns | done | platform.md §2–4 |
| Q3 | shell_ui | PS sound call sites | done | shell_ui*.md use the same ids |
| Q4 | sim_flow/sim_world | AP sx call sites; gates at `5440:0aee` "still to name" | done | sim_flow.md / sim_flow_results.md / sim_flow_ui.md describe `5440:0aee` |
| Q5 | sim_flow/render3d | token lists `3546`, timer objects `4b31`, `277a:3b3c` | done | sim_flow.md, render3d_world.md |
| Q6 | — | DRO vs DOSBox listening, MT-32 path, device tracks 06h/09h/16h, never-called player functions | open | |
| X1 | platform | `05da:5de1` detection, BIOS mode save/restore, `0000:04F0`, `DS:1A04` table, AP `nlkle` | done | video.md itself (`gfx_detect_adapter` row) |
| X2 | shell_ui/shell_data | PS `22ce` page helper names | done | naming conflict N-c |
| X3 | sim_flow | AP page protocol (video.md §4.2) | **conflict** | §2 C3 |
| X4 | render3d | `gfx_polygon` used by `277a`/`6396` | done | video_library.md is the single spec |
| X5 | — | entries 12/16/25/26/28, entry 13 arg, entries 19/24 callers, `drv[AB8]` | open | no-ops on VGA |
| VM1 | video | video_palette.md §10 "column dissolve" | **conflict** | §2 C4 |
| Z1 | video | `pal_slot[0]`, `drv[1F]`, `drv[1D]`, fade = present, `pal_load` quirk | done | video.md / video_library.md |
| Z2 | formats | scripts.md opcode corrections; resources.md §3 COCPAL | done | formats corrected (§3) |
| Z3 | sim_world/render3d | `17ce:0013` 13 effect targets; damage effects `655d:15f7..164f`; `490a:0554`; `362b:00be` | done | render3d_sky.md §5.9 specs `17ce:0013` completely (channel meanings: night, clouds, blackout 11, red flash 12…); damage calls are in video_palette.md only (sim_world does not describe them — minor) |
| Z4 | sim_flow | `644a:0271` view palette switch, `6b3d:0000`, `606e:029d` dim | done | sim_flow_cockpit/ui/vcr.md |
| Z5 | render3d | paltrick `51b4:0000/0088` | done | render3d_sky.md §5.4 |
| Z6 | shell_ui | PS palette switching / cache | done | shell_ui_toolkit.md |
| Z7 | — | `50c8:0000` condition in `sim_init` | done | §2 C2: it is the debug flag; ACES.PAL is set immediately in debug mode or without a DAC |
| Z8 | — | fade pacing (70 Hz), adapter id 4, `30b5` vs `103d`, meaning of the 13 `pal_fx` entries | done (entries) / open (rest) | entries: render3d_sky.md §5.9 |
| J1 | formats | resources.md §4a nibble order, §4b sprite `ncol` | done | resources.md (§3) |
| J2 | platform | `vqt_scr_node`/`vqt_mem_node` naming; kind −3 opaque | done | platform.md §7.5 names `0e2c:004e`; naming only |
| J3 | shell_ui | `SNAPSHOT.LBM` | done | shell_ui_toolkit.md |
| J4 | sim_flow/render3d | `bmp_draw 26d2:0031` per kind | done | video_pictures.md §6 is the spec (video row) |
| J5 | — | VQT ≥ 8192 px palette leaf; encoder empty-quadrant bits | open | not measured |
| TS1 | render3d | `3d50` = copy of `277a`; AP polygon flag 10h draws nothing; `70b4:0000/0188` | done | render3d_poly/shapes.md, video rows for `70b4` |
| TS2 | sim_world/render3d | "AP `39e5:0000` = PS `m_cam_block` data" | **conflict** | §2 C8 |
| TS3 | shell_data | `view3d_*` library entry points | done | shell_data_sys.md, shell_ui_career.md |
| TS4 | — | `DS:3FB4` = `_stklen` | open | likely |
| TT1 | shell_ui | TTM frame-loop contract (flip + `upd_flush(0)`, sticky delay, return codes) | done | the contract is fully in video_ttm.md §14; shell_ui specs call the player without restating it |
| TT2 | shell_ui/shell_data | hook `2221:0111` → `DS:1B80` table | done | shell_data_sys.md |
| TT3 | video | `pal_set` return, `pal_cycle(-1,0,0)`, `DS:33CA/33CC` read nowhere | done | video_palette.md §4.6/§5.8: cycling is registered but never stepped |
| TT4 | sim_flow | cockpit selects pages before `ttm_run` | done | sim_flow_cockpit.md |
| TT5 | video | `drv[0C]`, `drv[1F]`, `drv[1D]`, MTX entries, update list | done | video_library.md, video_palette.md |
| TT6 | platform | timer callbacks (period 4 / 1) | done | platform.md §4.7 |
| TT7 | — | `A5A7` a4/a5, polygon layout, `05da:0a00(-1,0,0)` | open | |

## 2. Conflicts between specs and their resolution

Substantive conflicts (behaviour or ownership), resolved from x86dis unless stated:

| # | Specs | Conflict | Resolution |
|---|---|---|---|
| C1 | sim_flow_cockpit.md §7/§11 vs sim_world_ai.md §15/§21 | each says the other owns/rowed `1660:07bb/0bae/0c12/0c47` (radio-menu item builders); neither had them | specced and rowed in **`sim_flow_radio.md`** (owner sim_flow per the ownership map): `targets_list`, `targets_exist`, `add_attack_item`, `orders_list`, target table `DS:5B6C` |
| C2 | sim_flow.md §2 (line ~347: "`50c8:0000` is an empty far function used as a no-op callback", row `sim_nop`) vs platform/sound (`is_debug`) | `50c8:0000` is image `50c80` = the same bytes as `50c0:0080`: `mov ax,[DS:053F]; retf` → returns the **debug flag** (set when `argv[1] == "nlkle"`). sim_flow.md is wrong. Consequences: `sim_init` sets ACES.PAL immediately when in debug mode or without a DAC (answers video_palette open Q); `demo_fade_once 5d56:0000` fades only when **not** in debug mode (answers sim_flow_vcr open Q); the NLD-driver error at `4e0d:01db` is skipped in debug mode |
| C3 | video.md §4.2 ("AP does **not** flip per frame … A000 stays displayed") vs sim_flow.md §6.2 / video_palette.md §8.3 | the flight frame `draw_frame 5440:018c` selects the back page (`368f:03c1/03b6`) and ends with `page_flip 5440:07e1(flip)`, which calls driver entry 8 (`1d32:540b` = `jmp [DS:353A]`) **every frame** when `flip ≠ 0`, then uploads the pending DAC palette. So in flight A000/A400 are double-buffered by CRTC flips; the back→front copy path (`46de:02f3`) belongs to the dialog/menu screens. Also sim_flow.md says `5d3c:0000` "returns the page number" — it returns **1 when the VCR panel is shown** (it draws the panel/pointer into the back page), 0 otherwise, and that value is the flip's `wait` argument: **the flight loop waits for vertical retrace only while the VCR panel is visible**; otherwise pacing is the 3-tick `timeout(DS:0148)` minimum. `frame_present` (video_palette) and `page_flip` (sim_flow) name the same function |
| C4 | video_palette.md §10 ("`368f:00ff` column dissolve") vs video_misc.md §2 | `wipe(x, y, w, h, ticks, copy)` draws 1-pixel-high rows `y+k+10j` in 10 passes (`gfx_copy_rect(x, r, w, 1)` / `gfx_rect(x, r, w, 1)`), `ticks` PIT ticks apart — a horizontal line blind, not columns |
| C5 | shell_data.md §3.2 ("SIM.OUT +06 u16[4] not read by PS"; +0E only date jump) vs shell_ui_debrief.md §11 | the debrief is right: PS `0874:0291` reads +06 as a FFFF-terminated list of event ids (type-3 career events) and compares +0E with type-4 event ids. AP 1.2 always writes FFFFh ×4 at +06 (`results_write`), so those events can never fire from this sim; +0E is "home carrier sunk" (sim_flow_results.md §7.4). data.md §1.2 rewritten accordingly |
| C6 | shell_data.md §4 ("TOPMISS record built at `DS:4308` by `0874` case 2") vs shell_ui_debrief.md §11 (built by `09a9` best.c, `09a9:0629…06f2`; the `0874` "case 2" is Ghidra merging code) | debrief's reading taken (it cites the x86dis range); the record layout itself is not in dispute |
| C7 | shell_data.md §3.2/§4 (status 1 = POW) vs shell_ui_debrief.md (status 1 = "retired") | value 1 is set for captured pilots (`0542:000a`), for a pilot retiring at the end of a campaign (`0874:11ff`) and by `shell_cleanup` (`227c:004d`); the roster shows it as "retired" — name it **retired** (POW is one way to get there) |
| C8 | video_ts.md §8 ("AP `39e5:0000` matches PS `3d50:3e0f` = `m_cam_block` data") vs sim_flow.md §1 ("256 zero bytes, no code") | `39e5:0000` is a 256-byte far `char` buffer (zero in the file) whose only user is `kill_credit 088a:054f`: `_fstrcpy/_fstrcat` "You just shot down " + ace name + "!" → `msg_show`. Not `m_cam_block`. Rowed in `sim_world_extra_symbols.csv`, spec `sim_world_extra.md` |
| C9 | render3d.md hand-offs ("`07fe:000a` is a 4-point bitmap draw primitive") vs sim_world_ai.md §15 / video_ts.md (assert helper `ces_check`) | x86dis `07fe:000a`: tests its three arguments and on every path calls the assert/error routine `2494:0127(far "ces.c", 41h)`; no drawing. AP polygon flag 10h (`2ec2:000d` → `07fe:000a`) therefore draws nothing |
| C10 | sim_flow_cockpit.md §11 (`1660:*` "already rowed by sim_world") | same as C1 (listed separately in the cockpit spec) |
| C11 | render3d_world.md §6.5 ("`51ca:008d` is used by the VCR loader `5b71:0118`") vs sim_flow.md §1 (`5b71` "named-resource lookup, no callers") | `5b71:0118` has no caller: it is a dead named-id list loader (`sim_flow_extra.md`); `51ca:008d`'s only user is dead code — nothing in the VCR path uses it |
| C12 | sim_flow.md §3 (CONTROL.PRF +04 "u16, not used by AP") vs platform.md §3 (+04 u8 modules, +05 u8 latest) | platform's byte layout is right (RESOURCE.CFG `modules`/`latest`); AP simply does not read them |
| C13 | sim_world_ai.md §15 (`DS:18EC[(i8)class]`) | element size missing: a **word** table {1, 0, 7, 2, 3, 4, 8, 5, 6}, used both as `ship_priority[class]` and as the class listing order of the radio target menu (sim_flow_radio.md) |
| C14 | sim_flow_symbols.csv `60a9:017c` "mis-seeded fragment?" | a real function (L6 above) |
| C15 | sim_flow_vcr.md §16 vs render3d_sky.md §4.3 (draw path RNG) | no real conflict: the draw path uses `DS:43DE` only, never `DS:4454` (V5) |
| C16 | sim_world_ai.md §15 `07fe:000a` "assert … line 41" | the pushed line number is 41**h** (65) |

Naming-only conflicts from `port/symbol_conflicts.txt` (same address, different names — behaviour
agrees after reading both specs; `merge_symbols.py` keeps the higher-priority owner):

* **N-a** `5440:03aa` `render_scene` (render3d) / `world_draw` (sim_flow); `5440:0269` `draw_object` /
  `object_draw_cb`; `5440:0375` `dist_limit` / `range_helper`: same code, render3d's specs are the
  detailed ones.
* **pal_fx vs palfx** (`1792:*`, `51a8:*`, `DS:5BD8`): video_palette.md §8.4 and render3d_sky.md §5
  specify the same routines with identical arithmetic (checked `1792:00c0/0286/038a`, incl. the
  `(c−1)·k >> 6` step table quirk). One implementation; video_palette names win (priority).
* **`7115:0000/0372`, INTRO `05da:4a8f/4e01`, PS `16e3:4db3/5125`** `font_load/free` (platform
  §7.7) / `gfx_font_load/free` (video_library.md §8.2): the two pseudo-codes agree (header byte 3 =
  "baseline" in one, "underline row" in the other — same field). Only one should be ported.
* **N-b** `kill_credit` is used for two different functions: `088a:054f` (sim_world_dmg: messages and
  bookkeeping when something is destroyed) and `1899:0cf0` (sim_flow_results: the credit counters it
  calls). Suggest renaming `088a:054f` → `object_destroyed_notify` (gen_symbols.py disambiguates
  meanwhile). Same-name pairs for different functions also: `nearest_enemy` (`1284:0184`,
  `496a:070e`), `view_free` (`271b:02a6`, `5440:012c`), `sun_glare` (`583c:04a9`, `6964:0458`),
  `pool_alloc/free` (`1d32:22f4/24b6` EMS vs `3546:021a/0333` token pools), PS `scr_load`,
  `strings_load`, `mission_free`, `fm_btn_cb`, `fm_frame`, `fread_far` — distinct routines, rename in
  the port.
* **N-c** PS `22ce:004a..00fb` page helpers: video (`bg/back/front`) vs shell_data_sys
  (`spare/work/front`) — the same page roles under two vocabularies (video.md §4.2 maps them).
* Driver-block globals `DS:26C4..26CE`, `DS:26DF`, `DS:285E`; `DS:31E5`; `DS:4032`; `DS:42C8`;
  `DS:437E`; `DS:4454`; `DS:4E74`; `DS:711E`; `DS:0887`; `DS:069C/069F`; `DS:0B80`; `DS:02D4/02DA`;
  `DS:052E/0532/0539/053F`: consistent meanings, names differ only.
* `50c8:0000` `is_debug` / `sim_nop` is **not** naming-only — C2.

## 3. Format corrections folded into `port/formats/` and `FORMATS.md`

* **data.md** §1.1 SIM.IN +03 (training sub-type / enemy ace index), +04 (merit value), +07 (OR of
  the extension bit); §1.2 SIM.OUT rewritten from the AP writer and PS readers (result code, fate bits,
  +04 aircraft lost, +06 event ids (always FFFF from AP), +0E home carrier sunk, +20 merit, +22 score
  formula); §3.1 CONTROL.PRF field list; §3.2 pilot/TOPMISS pointers; §3.3 PFNAME/SFNAME are model
  file-name lists; §3.4 EVENTS superseded; §4 `.DAT+0` empty weight, `.MEC` record sizes, `.WND`
  loaded twice; §5 VCR superseded by sim_flow_vcr.md §2; `CPVW.BUF` = 8-byte code + 3 × 64000; open
  questions pruned.
* **resources.md** §1 `my_fopen` opens loose files first; §3 COCPAL/COCKPIT/GUNPAL are never
  generated (load returns NULL); §4b sprite decoder `ncol`; §6 FNT u16 = unpacked size, `FE` kind.
* **scripts.md** SEL_PAL (no VGA upload), PAL_CYCLE (never animates), `3103` SCROLL, FADE_PART
  duration in ticks, `C0E3` SND_FADE; `.SCD`: the loose `Game/MAINMENU.SCD` is the one used; PS's
  `u16 n, off[n], size` reading is byte-identical to variant A.
* **world.md** §5 target lists 2/3/4 (kind, owner/state with 0Ah destroyed, service set).
* **FORMATS.md** summary lines for COCPAL, SIM.OUT, PFNAME/SFNAME and the open-question pointer.

## 4. Most important open items for the port

1. **World/speed units and the real-time length of a nominal step** (D6, H4, C6/cockpit `P.94h`):
   still a ¼-ft guess; needed to calibrate time scale, gauges and the benchmark divisor (L7).
2. **Frame pacing** (C3): flight frames flip every frame without vsync except while the VCR panel
   is shown; minimum 3 ticks (236.69 Hz) between flips. The port must reproduce this timing
   rather than a fixed 60/70 Hz loop.
3. **SCRIPT.DAT group/flight fields → AI behaviour** (M1, F2, SD6, G4): the 58-byte group → 56h
   flight mapping (`56ac:0b78/0c6a`) is still read from a broken decompile; formation ids / FORM.DAT
   codes are not linked to the sim side.
4. **Unreachable/undriven states** (A6 state 0444h, S5 moon/star bit 80h, W4 types 0Ch/0Dh):
   faithful port keeps them; confirm with a film if possible.
5. **Clock direction labels `DS:1132`** (S1) — cosmetic but visible in the shell/sky.
6. **Index gap** (N1): PS code segment `0cfe` is not in `ps_functions.json`, so coverage there is
   unmeasured (the spec exists in shell_ui_debrief.md §8).
7. EMS pool free order (P7) and the 3-file `my_fopen` limit (P12) only matter if the port emulates
   EMS/file handles instead of replacing them.
