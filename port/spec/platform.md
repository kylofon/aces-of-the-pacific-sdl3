# Platform: system library, start-up, configuration, resources (INTRO / PS / AP)

**Status: partial (phase 3, first delivery).** Written: §1.2 library map, §2 program chain /
start-up / main / fatal / config files, §7 picture, palette and font loaders, §9 port notes.
Pending (helper research still running when this was written): §3 input (keyboard ISR, INT 1Ch,
joystick, mouse, divide-by-zero, Windows), §4 timer, §5 DOS memory / EMS / `mem.c` /
`emm_pool.c`, §6 volume.c, chunk access and the RLE/LZW decompressor.

Conventions: `port/RE_GUIDE.md`. DGROUPs INTRO 17E0, PS 4D08, AP 3EA4 (AP = `work/AP_flat.exe`).
Confidence: **verified** = read in the disassembly; **likely**; **guess**.

## Index
1.2 Library map and ownership · 2 Chain, start-up, main, fatal, configuration files ·
3 Input (pending) · 4 Timer (pending) · 5 Memory/EMS (pending) · 6 Volumes and decompression
(pending) · 7 Loaders · 9 Port notes · 10 Hand-offs · 11 Open questions

## Key findings
* **`RESOURCE.CFG` is never read** by INTRO/PS/AP (the reader/writer code is dead; only
  `INST.EXE` uses it). The real configuration is `CONTROL.PRF` (37 bytes: video/sound driver ids,
  module mask, option toggles, calibration of two joysticks), read and rewritten by all three.
* GCD sets `0000:0510` = 29Ah **once**; afterwards PS/AP maintain it (AP always leaves 3E7h).
  `0000:0512` is only used by the INTRO (≥ 609 200 bytes) and PS (≥ 590 000) memory checks.
* Programs exit **without resetting the video mode**: the next program starts over the last picture.
* AP gives the EMS pages it does not need to the Borland overlay manager (`_OvrInitEms`), picks
  an "EMS tier" (`DS:0539` = 3 with 19–32 free pages, 4 with ≥ 33); the "112K" message is
  printed for < 19 pages (304 KB).
* `05da:5f97` (named `dos_setblock` by the matcher) is an **SCN encoder** (`bmp_to_scn`) that
  re-encodes pre-decoded VQT frames when a `BMP:RLE:` chunk is present.
* The `FNT:` u16 after `count` is the **unpacked** size (correction to resources.md §6).
* All `-p…` options of PS and most of INTRO are compiled out; AP debug switches need the first
  argument `nlkle`.

## 1.2 Map of the system library (INTRO `05da` / PS `16e3` / AP `1d32`) and who owns what

Same code in the three programs (AP moved a few modules into overlays: `7115` fonts, `715b`
screen planes, `7187` chunk access, `71db` SCN encoder, `7229` bitmap planes). PS/AP addresses are
given where the match is known (`port/shared_matches.csv`, checked); DS offsets differ per
program. "platform §n" = specified in this document.

| INTRO 05da | What | Owner |
|---|---|---|
| 0014–03f4 | keyboard install/restore/ISR, INT 1Ch ramps, key queue read, key-held test | platform §3 |
| 0408, 046e, 05a1, 0638 | circle / ellipse drawing (edge buffer `DS:2652`) | video |
| 06e5, 06e9, 0b6b, 0b7e, 24eb, 24ef, 2fb0, 2fb5, 2fbd, 35d8, 35dc, 3cfd, 492f | one-instruction thunks `jmp far [drv entry]` (`DS:19AC`, `19BC`, `19A4`, `1994`, `197C`, `1980`, `1948`, …, `182C`, `1954`) | video |
| 06f1 | VGA write-mode reset (3CEh/3C4h) when adapter `DS:0AA1` = 10h | video |
| 070b, 0980 | `pal_load`, `pal_free` | platform §7.6 |
| 090e, 09da, 0a00, 0a7b, 0b46 | palette set, set range, colour-cycling ranges (`DS:265C/2670/2684`) and step, far byte copy | video |
| 0b91, 0fbd–1245, 2b2f | polygon fill (edge table `DS:0B2C`) | video |
| 1e1d, 1e21, 1e25, 1e38, 1e3c | SCN bitmap drawing (resources.md §4c) | video |
| 2307, 2351, 2374, 23e1, 241a | timer callbacks, PIT install/restore, INT 8 ISR | platform §4 |
| 24f3, 25a6, 2827 | scaled bitmap blit (`"videoDrv"`) | video |
| 2893, 2aba, 2add | flood fill (6000-byte `dos_alloc` stack) | video |
| 2b08 | machine test: `E000:FFFE == FFFFh && E000:C000 == '!'` → `DS:0A9C` = 1 (keyboard remap machine) | platform §3 |
| 2fc1, 3098, 30c8, 30f8, 3122, 3133, 3193, 33f7, 340e, 3573 | font select, metrics, string width, text drawing | video (30f8 `font_valid` used by §7.7) |
| 35e0, 3657 | `dos_alloc`, `dos_free` | platform §5 |
| 3667–3927 | joystick | platform §3 |
| 3957 | clipped line | video |
| 3a40–3c61 | mouse | platform §3 |
| 3c84, 3d01 | rotated/scaled bitmap drawing | video |
| 45d3 | read clip rectangle | video |
| 4611–4836 | huge-pointer helpers (normalise, add, memmove, memcpy, memset, compare) | platform §5 |
| 4844, 486e, 48a7 | divide-by-zero handler | platform §3 |
| 48cb, 48fd | clipped get/put pixel | video |
| 4933, 5c93, 5dc9, 5de1, 5f2e, 5f48, 5f6b, 5f83 | driver load, `gfx_init`, text mode, adapter detection, CRTC probe, BIOS mode/equipment | video |
| 4a8f, 4e01 | `font_load`, `font_free` | platform §7.7 |
| 4ee4, 5001, 539d, 53c1, 53ef, 540f, 54ae | bitmap/screen plane loaders | platform §7 |
| 5764–5c7a | resource file / chunk access | platform §6 |
| 5c92 | empty function | – |
| 5db4 | `sys_shutdown` = kbd_restore, mouse_shutdown, timer_restore, divzero_restore | platform §3 |
| 5f97, 607c, 6116, 6196, 62b4 | `bmp_to_scn` SCN encoder | platform §7.3 |
| 645b | clipped rectangle fill | video |
| 6567–7c51 | packed streams: RLE / LZW decompression | platform §6 |

Outside the library: INTRO `0dc5`/`0e2c` (PS `383a`/`38a1`, AP `6f1c`/`2651`) = VQT decoder
(draws, or writes to memory for §7.2) → video; `0ead`, `0ef8`, `0f2c:0010`, `0f35`, `0f48:000c`
→ platform §7; `0f2c:0032`, `0f48` drawing, `0f88`, `0f9e`, `0fb0`, `1739` → video.

## 2. Program chain, start-up and `main`

### 2.1 `GCD.COM` (965 bytes, origin 100h) — verified

Run by `AOTPCD.BAT` as `gcd -nC:\DYNAMIX\AOTP` after `cd \DYNAMIX\AOTP`.

```
0100  INT 21h AH=4Ah, ES=PSP, BX=004Ch      ; shrink to 4Ch paragraphs (1216 bytes)
0108  tail[0x80]++ ; tail[0x80+old_len+1] = '\\' ; copy "btest.bin\0" after it
      ; the command tail MUST be " -n<dir>": the file name used is PSP:0084 (= <dir>\btest.bin),
      ; i.e. it assumes one leading blank and the two characters "-n".
0125  INT 21h AH=3Ch create PSP:0084 (attr 0); AH=40h write 5 bytes (from DS:0084, i.e. the
      first 5 characters of the path); AH=3Eh close.
      any CF -> print "The temporary file area specified does not exist or is not
      writeable.\r\nPlease run WIN SETUP to set up the temporary file area. \r\n" and exit(0)
0141  tail[0x81+new_len] = 0Dh   ; the child's tail is the original tail + '\' : " -nC:\DYNAMIX\AOTP\"
015E  INT 21h AH=48h BX=FFFFh (fails) -> BX = largest free block (paragraphs)
      word [0000:0512] = BX ; word [0000:0510] = 029Ah        (set ONCE, before the first EXEC)
017C  SP = 03EDh ; EXEC block at 02DDh: env = PSP:[2Ch], tail = CS:025D (copy of the new tail),
      FCB pointers 0 ; call 0240 (save BIOS equipment video bits 40:10 & 30h >> 4 in [0211])
01A6  EXEC (4B00h) "INTRO.EXE"
loop: restore DS=ES=SS=CS, SP=3EDh ; CF -> error
      INT 21h AH=4Dh -> AL = child exit code ; AL-1 < 0 (code 0, or >= 81h) -> exit(0)
      name = table[AL-1] at CS:040F = {03EF "INTRO.EXE", 03FA "PS.EXE", 0404 "AP.EXE"}
      (no bound check: code >= 4 reads garbage from 0415 "btest.bin" and the EXEC fails)
      EXEC name ; CF -> error ; else loop
error: call 0212 (a bare RET: the video-mode restore routine at 0213 is unreferenced dead code)
      copy 12 bytes of the name into the message; print "Unable to chain: <name>\r\n"; exit(0)
```

Exit codes: **0 = quit to DOS, 1 = INTRO, 2 = PS, 3 = AP**. `BTEST.BIN` stays in the game folder
(5 bytes). GCD never rewrites `0000:0510`/`0512` after the first EXEC: the programs themselves
maintain the marker.

### 2.2 The `0000:0510` marker and `0000:0512` — verified (all accesses in the three EXEs)

| Where | Access | Meaning |
|---|---|---|
| GCD `015E` | `[0512]` = largest free block (paragraphs) after GCD shrank itself; `[0510]` = 29Ah | "started by GCD" |
| INTRO `038e:092a` (mem_check) | reads `[0512]` | `(u32)[0512] << 4 < 0x94BB0` (609 200 bytes) → memory message, `exit(0)` |
| INTRO | never reads/writes `[0510]` | |
| PS `048e:020f` (mem_check) | reads `[0512]` | `(u32)[0512] << 4 < 0x900B0` (590 000 bytes) → message, `exit(0)` |
| PS `048e:04a1/04b5` (main) | reads `[0510]` | 29Ah → `returned_from_sim` `DS:00C3` = 0; 3E7h → `DS:00C3` = 1; anything else → `fatal_error("You can run Aces of the Pacific by typing 'AOTPCD' from the command line, or by clicking …")` (skipped when started with the `nlkle` argument) |
| PS `048e:04d3` | `[0510]` = 0 | consumed |
| PS `227c:00da` (shell_exit, to sim) | `[0510]` = `DS:00C3` ? 3E7h : 29Ah | then `exit(3)` |
| AP `50c8:0226/0231` (main) | reads `[0510]` | must be 29Ah or 3E7h, else `exit(1)` (→ GCD runs INTRO) — skipped in debug mode (`nlkle`) |
| AP `50c8:0263` | `[0510]` = 0 | consumed |
| AP `50c8:04ee` (end of main), `4e0d:0c15` (sim_exit) | `[0510]` = 3E7h | "returning from the simulator" |

Note the asymmetry: PS writes 3E7h before `exit(3)` only if PS itself was entered from AP; the value
only matters to AP as "not garbage". AP always writes 3E7h, so PS (next run) takes the debrief path
(`0542:01c4`, reads `SIM.OUT`).

No program reads `0000:0512` except for the memory check. `0000:0510` is the only state (besides
files) that crosses program boundaries.

### 2.3 Borland start-up `_c0_startup` (`0000:0000`, all three) — verified

Standard Borland C++ 3.0 `c0m` (medium model), the same code in the three EXEs:
DOS version → `DS:0092`; PSP → `DS:0090`; environment segment → `DS:008C`; top of memory →
`DS:00A8`; `_SaveVectors` (INT 0, 4, 5, 6); environment size scan; DGROUP stack/heap placement:
`SS = DS = DGROUP`, `SP = _stklen + end_of_bss + _heaplen` (heap length 0 ⇒ the whole 64 KB
DGROUP), `INT 21h/4Ah` shrinks the program to that; BSS zeroed; if DOS ≥ 3.30 and `_nfile > 20`
the handle table is enlarged with `INT 21h/67h`; `INT 1Ah` midnight flag → `40:70`; `_StartTable`
(#pragma startup), `main(argc, argv, envp)`, `exit(ax)`.

| | INTRO | PS | AP |
|---|---|---|---|
| DGROUP | 17E0 | 4D08 | 3EA4 |
| `_stklen` (DS) | `DS:2316` = 1000h | `DS:3FB4` = 1000h | `DS:05B2` = 0E74h |
| `_heaplen` (DS) | `DS:222A` = 0 | `DS:3F4C` = 0 | `DS:39AA` = 0 |
| BSS (cleared) | `DS:242C`–`348B` | `DS:40CA`–`782D` | `DS:3AF4`–`71F7` |
| static DGROUP size | 348Ch | 782Eh | 71F8h |
| `_nfile` | `DS:21FC` = 14h | `DS:3F1E` | `DS:397C` |
| MZ SS:SP (initial) | 1B29:0080 | 548B:0080 | 45C4:0080 |

So each program's DGROUP is a full 64 KB segment: static data + BSS, then the stack (grows down
from `end_of_bss + _stklen`), then the near heap (`malloc`) up to 64 KB. Far memory beyond the
program image is managed by the Dynamix `dos_alloc` (INT 21h/48h, memory section) and Borland
`farmalloc` (AP `mem.c`).

AP 2494:019b (`stack_left`) compares `&local + _stklen` against 0FFFFh (stack check helper).

### 2.4 INTRO `main` (`038e:0ac1`) — verified

Globals (INTRO DS): `work_dir` `DS:2461` char[?] (≥ 80), `prf_loaded` `DS:2460` u8, `skip_intro`
`DS:00C0` u8, `mem_override` `DS:00C1` u8, `intro_module` `DS:00C2` u16, `control_prf` `DS:24B1`
(37 bytes, §2.8), `no_chdir` `DS:00C5` u8 (never set: 0).

```
main(argc, argv):
  work_dir[0] = 0; DS:264B = DS:264A = 0
  for i in 1..argc-1: if argv[i][0]=='-' && argv[i][1]=='n': strcpy(work_dir, argv[i]+2)   // last wins
  if work_dir[strlen-1] != '\\': strcat(work_dir, "\\")
      // quirk: with no -n, strlen = 0 and the byte before work_dir (DS:2460, 0 at that time) is
      // tested, so work_dir becomes "\" = root of the current drive.
  if work_dir ends with "\\\\": drop the last '\'
  vol_init(0, 0x4000, 1)                               // volume scan, see §6
  prf_loaded = control_load()                          // 038e:0181
  modules_detect()                                     // 038e:0704
  for i in 1..argc-1:
      if argv[i][0]=='-':
          switch tolower(argv[i][1]) (table CS:0CF1 = '?','h','p','s'):
            '?','h': print help (10 lines, DS:063E…0767), exit(0)
            'p':     if tolower(argv[i][2])=='i': skip_intro = 1        // -pi only
            's':     control_prf.sound_drv (DS:24B3) = atol(argv[i]+2)
            other:   ignored (also -n here)
      else if stricmp(argv[i], "override")==0: mem_override = 1
  mem_check()                                          // 038e:091b
  if !skip_intro: sys_init(); intro_play()             // 038e:080d, 038e:0973 (shell_ui)
  snd_term()                                           // 1686:0004 (sound)
  sys_shutdown()                                       // 05da:5db4
  if DS:0A94 != A000h: DS:0A92 = A000h; DS:0A96 = DS:0A94; DS:0A98 = A000h; 05da:2fbd(0)
      // video: make the displayed page the visible one before exit — the video mode is NOT reset,
      // the last intro picture stays on screen while GCD loads PS (video hand-off)
  control_save()                                       // 038e:0687
  exit(2)                                              // -> PS
```

The help text lists `-s<num>`, `-pr`, `-pq<num>`, `-pd`, `-pi`, `-ps`, `override`, but INTRO
implements only `-n`, `-s`, `-pi`, `override`, `-h`/`-?`.

`mem_check` (`038e:091b`): skipped if `mem_override`. Else: `(u32)[0000:0512] << 4 < 0x94BB0` →
`mem_fail`; `ems_detect()` (17bd:0000) == 0 → `mem_fail`; `ems_free_pages()` (17bd:002a) < 21
(21 × 16 KB = 344 064) → `mem_fail`. `mem_fail` (`038e:08e7`) prints the NULL-terminated line
table `DS:0148` ("Your computer does not have enough available memory…", 7 lines) with
`printf("%s\n")` and `exit(0)`. (Text says 610 000 bytes; the test is 609 200.)

`sys_init` (`038e:080d`):
```
  v = gfx_init(control.video_drv, 0xFF, "vmcode.ovl")          // 05da:5c93 (video)
  if v == 0: v = gfx_init(0, 0xFF, "vmcode.ovl")               // autodetect
  control.video_drv = v; if v == 0: printf("Cannot initialize graphics card!\nPlease run INSTALL to configure…"), exit(0)
  if control.sound_drv == 4 (SBL) or 7 (PRO): control.sound_drv = 2 (ADL)
  if !snd_init(control.sound_drv, "sxcode.ovl"): printf("Cannot initialize sound & music driver!…"), exit(0)   // 1593:0004
  divzero_install()        // 05da:4844
  kbd_install(0)           // 05da:0014
  mouse_glue_init()        // 0491:000c
  chdir_unless(no_chdir, "TTD"); snd_load_resource("ttd.sx", 0) /*1659:000b*/; chdir_unless(no_chdir, "..")
      // leftover developer layout: the chdir fails harmlessly in the shipped game
  if control.toggle3 == 0: 164d:0006(-2)      // sound option (sound spec)
  if control.toggle4 == 0: 164d:0006(-1)
```
The timer is installed by `snd_init` (sound hand-off). `038e:0097` `chdir_unless(path)`: returns
`true` if `no_chdir`, else `chdir(path)==0`; `038e:00bc` = `chdir_unless("..")`.

`modules_detect` (`038e:0704`): `control.modules` (DS:24B5) = 0; for n = 1..7: if
`my_fopen("CSET<n>.dat","rb")` succeeds (a volume or loose file): `modules |= 1 << (n-1)`,
`control.latest` (DS:24B6) = n, close; then if `my_fopen("INTRO<n>.DAT","rb")` exists and its first
byte ≠ 0: `intro_module` (DS:00C2) = n. After the loop body, if `intro_module` ≠ 0: write one 0 byte
to `INTRO<intro_module>.DAT` opened with `"wb"` (through `my_fopen`, i.e. a loose file in the
current directory; volume.c section says how a write open is served). Data: M1SHL.DYN holds
`CSET0.DAT` ("ACES OF THE PACIFIC"), `CSET1.DAT` ("1946!") and `INTRO1.DAT` = 01; the installed game
has a loose `INTRO1.DAT` = 00 written by the first run. So the "1946" add-on intro plays once after
installation. `038e:0121` builds `"<base><n>.<ext>"` (n omitted when < 0) in `DS:244A` (through
`038e:00cc`, which also builds a path in `DS:242C` unless `no_chdir`); `038e:0004` = integer power
`pow(a, b)` (loop). `038e:0021` = random pick of a module bit (time-seeded `srand/rand`) used by
`intro_play` (shell_ui).

### 2.5 PS `main` (`048e:0259`) — verified

PS globals: `work_dir` `DS:40CA`, `nlkle` `DS:00C2` u8, `returned_from_sim` `DS:00C3` u8,
`mem_override` `DS:00AA` u8, `rand_seed_opt` `DS:00C5` u16, `control_prf` `DS:43B0` (37 bytes).

```
main(argc, argv):
  work_dir = "" ; DS:4F6D = DS:4F6C = 0
  -n<dir> pass and trailing-'\' normalisation exactly as INTRO (same quirk)
  vol_init(0, 0x4000, 0x0FFF)                          // PS 0000:10d1
  shell_files_load()                                   // 1193:0881: 1193:0084, control_load, roster, topace, topmiss, strings, 3555:0133
  for i in 1..argc-1:
      if argv[i][0]=='-': switch tolower(argv[i][1]) (table CS:04FE = '?','h','p','r','s'):
            '?','h': print 16 help lines (DS:027E…0439), shell_exit(0)
            'p':     tolower(argv[i][2]) evaluated and discarded — all -p debug options are compiled out
            'r':     rand_seed_opt (DS:00C5) = atol(argv[i]+2)
            's':     control.sound_drv (DS:43B2) = atol(argv[i]+2)
      else if stricmp(argv[i], "nlkle")==0: nlkle = 1
      else if stricmp(argv[i], "override")==0: mem_override = 1
  mem_check()                                          // 048e:0200 (threshold 590 000 bytes; message table DS:00C7)
  if !nlkle: marker check as §2.2 (else returned_from_sim stays 0 and the marker is left alone)
  [0000:0510] = 0                                      // (inside the !nlkle branch)
  ps_sys_init()                                        // 048e:0009
  if returned_from_sim: 0542:01c4 (debrief, reads SIM.OUT — shell_ui/shell_data)
  04df:018d (shell main loop — shell_ui)
  shell_exit(0)
```
(The help lists `-f<num>`, `-pr/-pq/-pd/-pi/-ps/-ph/-pm/-pv`: none is effective in this build.)

`ps_sys_init` (`048e:0009`): `gfx_init(control.video_drv, 0xFF, "vmcode.ovl")`, retry with 0,
failure → `fatal_error("Cannot initialize graphics card!\nPlease run SETUP to configure")`;
`sound_drv` 4 → 2 (note: 7/PRO is **not** remapped in PS, unlike INTRO); if sound_drv == 3 (MT-32)
and !nlkle → `snd_init(0x88, "sxcode.ovl")` else `snd_init(sound_drv, "sxcode.ovl")` (bit 7 =
"don't reset the already initialised MT-32", sound hand-off); failure → fatal; `timer_add(229e:0013,
1)` (`16e3:291b(0x13, 0x229e, 1)`, input section); `divzero_install`; `kbd_install(0)`;
`2316:000f` (mouse glue); `2e8a:0164`, `0a71:0001`, `0a71:00eb`, `2e8a:0124`, `0b48:0b6e` (shell
UI set-up); `snd_load_resource(make_name("shell", -1, "sx"), 0)`; if !returned_from_sim:
`464d:0002(1002)` (start shell music, sound); `DS:00C4` = 1; `2c11:0001`; `0a71:015c`
(loads mreal.prf); `DS:051E` = 0.

`048e:01a0` `fly_mission(kind)` (called by the shell screens): "Please Wait…" box (`048e:0112`),
`3164:23e3(kind)` writes `SCRIPT.DAT`, `sim_in_build_write` (1193:093e), `realism_save_current`
(1193:0856), unless header kind 2/3: saves campaign/state (2777:04df, 2550:073f, 2a85:0216,
2ab3:057f), `2c11:002e`; `shell_exit(1)`.

`shell_exit(to_sim)` (`227c:0072`): call the exit hook `DS:1BE6` (far ptr, set by `227c:0007`,
cleared by `227c:0019`) if non-null; `ps_shutdown` (`227c:004d`: if `DS:051E`: `DS:4778` = 1,
`09a9:07ee`, `0f67:0001`; `vol_close_all` (0000:11d7); `sys_shutdown` (16e3:5b0e));
`shell_files_save` (1193:08a4: control_save, roster, topace, topmiss); if to_sim: `snd_term`
(461d:0005); if nlkle `gfx_restore_text` else make the shown page visible (as INTRO end);
marker (§2.2); `exit(3)`. Else `snd_term`, `gfx_restore_text` (16e3:5b23), `exit(0)`.
`227c:002a` sets `DS:00C1` = 1; `227c:0034(x)`: if x: `shell_exit(0)`.

### 2.6 AP `main` (`50c8:0008`) up to `sim_init` — verified

AP globals: `work_dir` `DS:4032`, `debug` `DS:053F` u16 (read by `is_debug` `50c8:0000`), `sim_mode`
`DS:43DC` u16, `ems_tier` `DS:0539` u8, `ems_spare_pages` `DS:4030` u16, `sim_in` `DS:439A`
(13 bytes), `extract_name` `DS:0534`, `DS:052E/0532/0536/053A/053C/0884` debug option values.

```
main(argc, argv):
  skip_mem = 0; mode = 0 (local [bp-4]); work_dir = ""; DS:5EE1 = DS:5EE0 = 0
  -n<dir> pass and '\' normalisation (inline string code, same result as INTRO)
  if strcmp(argv[1], "nlkle")==0: debug = 1                       // argv[1] only, must exist
  for each arg starting with '-' or '/': if arg[1]=='m' && debug:
        printf("%ld\n", mem_far_avail()) /*24b2:013d(-1L,0)*/, exit(1)
  DS:1EBC = "SH" (DS:0583)
  vol_init_ap(0, 0, 0)                                  // 0000:1057 (volume section)
  if ems_detect() /*24e1:0000*/:
      atexit(24e5:00b6)                                 // free all EMS handles at exit
      p = ems_free_pages() /*24e1:0031*/ ; ems_spare_pages = p
      if p < 19: assert_fail("…", 0xBD, "At least 112K EMS memory required to run.")   // exits
      if p < 33: ems_tier = 3, ems_spare_pages -= 21  else: ems_tier = 4, ems_spare_pages -= 33
  else: assert_fail(…, 0xDB, "At least 112K EMS memory required to run.")
  int24_install()                                       // 0000:1a70
  if !debug:
      if [0000:0510] != 29Ah && != 3E7h: exit(1)        // not started through the chain -> INTRO
      read_file("sim.in", 13, 1, DS:439A)               // 519d:0000
      mode = sim_in[1]                                  // DS:439B
      [0000:0510] = 0
  for each arg starting with '-' or '/':  switch arg[1]:
      's': if debug: if arg[2]: DS:0532 = 0, DS:052E = atol(arg+2) else DS:0532 = 1
      'S','x': (name = arg+2, non-empty) if debug: extract_name = name;
            if !find_file(name) /*4bcd:01df*/: assert_fail(…, 0x106, "Could not find %s")
            else copy the file byte by byte: in = my_fopen(name, "rb"), out = my_fopen(name, "wb")
            (fgetc/fputc until EOF) — extracts a volume entry to a loose file (debug)
      't': if debug: DS:053C = atol(arg+2); DS:053A = 1; DS:0884 = 1
      'o': skip_mem = 1                                  // no debug needed
      'W': if debug: DS:0536 = atol(arg+2)
      'w': if debug: mode = 2
      'd': if debug: mode = 3
  if !skip_mem and mem_far_avail() - 140000 < 0: assert_fail(…, 0x1B8, "MEMORY TOO LOW")
  if ems_spare_pages: _OvrInitEms(0, 0, ems_spare_pages)   // 36f6:08ed: rest of EMS to the overlay manager
  4b9e:0000()
  sim_mode = mode
  sim_init()                    // 4e0d:0000 (sim_flow)
  5c9b:0000(mode)               // the sim run (sim_flow)
  4e0d:035c()                   // sim shutdown (sim_flow)
  [0000:0510] = 3E7h
  sim_exit(2, 0)                // 4e0d:0bb0 -> exit(2) = back to PS
```
Sim modes: 0 single mission, 1 career, 2/3 mission-recorder paths (data.md §1.1). `-w/-d` need
debug mode. The meaning of the `-s/-t/-W` values belongs to sim_flow (hand-off).

`sim_exit(code, text_mode)` (`4e0d:0bb0`): `5a75:0d39(0)` (sound stop); if `DS:4010` (prefs
loaded): `prefs_save` (4e0d:06fd), `simprefs_save` (4e0d:0b3e); `0000:122b` (volume close all);
`368f:03ed/03b6/01f2` (sim_flow); if `DS:4012` ≠ `DS:26D4`: `1d32:540b(1)`; `int24_restore`
(0000:1ab0); `sys_shutdown` (1d32:012a); if `debug` or `text_mode`: `gfx_restore_text`
(1d32:013f); `[0000:0510]` = 3E7h; `exit(code)`. Callers: AP main (2 → PS), `5440:115b`
(1 → INTRO), `60a9:0a28` / `60a9:0a6c` (VCR/demo paths, 0 → DOS).

`int24_install` (AP `0000:1a70`, AP only): once (`DS:3726` flag): save INT 24h vector in
`CS:1A6C`, install `CS:1AA4`: `if AL bit 7 (non-disk error) jmp old; else AL = 1 (Retry); iret`.
So disk critical errors are retried silently. `int24_restore` `0000:1ab0` puts the old vector
back. Port: nothing to do.

`1d32:6a91` `sys_exit(code)` (AP only; no caller found, dead): `sys_shutdown`,
`gfx_restore_text`, `code == 1` → `INT 19h` (reboot), else `INT 21h/4C00h`.

### 2.7 Fatal errors and asserts — verified

| INTRO | PS | AP | Name | Behaviour |
|---|---|---|---|---|
| 05bb:0000 | – | – | `iret_stub` | a lone `IRET` (unused) |
| 05bb:0001 | – | – | `nop_far` | empty, no callers |
| 05bb:0006 | ? | ? | `kbd_break_hook` | empty far function called by the keyboard ISR on Ctrl+Esc (input section) |
| 05bb:000b | 227c:004d | (inline in callers) | `shutdown_all` | `vol_close_all` (049d:0d50), `sys_shutdown` (05da:5db4). PS adds its shell clean-up |
| 05bb:001a | – | – | `quit(code)` | dead: shutdown_all; snd_term unless sound_drv==3; text mode; `exit(code ? 3 : 0)` |
| 05bb:0052 | 227c:00f8 | 2494:0057 (line list) | `fatal_error(fmt, …)` | shutdown_all; `snd_term`; `gfx_restore_text`; if fmt: `vprintf(fmt, …)`, `printf("\n")`; wait for `kbhit()`; `exit(0)`. AP form: `fatal_lines(char **lines, int n)` prints n+1 lines with `"%s\n"`; `2494:00a9` = fatal_lines(DS:1D7E "The mission recorder has run out of disk space…", 4) |
| 05bb:009f | 227c:0143 | 2494:0127 | `assert_fail(char far *file, int line, char *msg)` | shutdown_all; sound off (INTRO 1672:000b(0), PS 4609:000c(0), AP 5a75:0d39(1)); text mode; print "A SHELL system error has occured.…contact ChrisR x170 or DayneF x142" (INTRO) / "…contact Sierra Customer Support:" (PS, AP); `printf("%s:%d (%s)\n", file, line, msg ? msg : " ")` (AP prints only the upper-case base name of `file`, `2494:00ba`); PS then prints `RSEED MODE MTYPE DATE WORLD PLYR SINDEX ENEMY SERVICE` from the mission header (`DS:6275 626B 626C 6277 626D 62DB 6355`); AP restores INT 24h and calls sys_shutdown; wait for a key; `exit(0)`. Returns 0 (never reached) |
| – | – | 2494:01ca | `assert_fail0(file, line)` | = assert_fail(file, line, NULL) |
| – | – | 2494:0009 | `far_to_near_str(char far *s)` | returns s if its segment is DS, else copies it into a 512-byte ring `DS:5EE2` (index `DS:1D7C`, wraps to 0 when the string does not fit) |
| – | – | 2494:00ba | `basename_upper(char far *path)` | near copy, strip up to the last `\`, cut at the first `.`, `strupr` |
| – | – | 2494:019b | `stack_left()` | stack-space helper (see §2.3) |
| – | – | 2494:01df | empty | |

Callers use the pattern `cond || assert_fail(__FILE__, __LINE__, msg)`. Every fatal path ends
with `exit(0)`: GCD then quits to DOS.

### 2.8 Configuration files

**`RESOURCE.CFG` is not read by any of the three programs.** INTRO contains a reader
(`config_read` `038e:0284`, via the line reader `05cb:0027/00a6/00dc`) and a writer
(`config_write` `038e:04d6`), PS a writer (`1193:0ad2`), but no code or pointer references them
(checked by call and relocation scan): dead code left from the installer's library. The file is
written and used by `INST.EXE` only. (For completeness, the dead reader would map `videoDrv`
through the table `DS:00C7` {"VGA320"→8} and `soundDrv` by `strstr` through `DS:00CF`
{"ADL"→2, "IBMPS1"→5, "MT32"→3, "PROAUDIO"→7, "SNDBLAST"→4, "STD"→0, "TANDY3V"→1}, `modules`,
`latest`, `toggle3..7` with `"%*s %*s %hd"`/`"%d"` into the CONTROL.PRF fields below.)

**`CONTROL.PRF`** (37 bytes) is the real configuration, written by the installer and rewritten by
each program:

| Off | Type | INTRO DS | PS DS | AP DS | Field |
|---|---|---|---|---|---|
| 00 | u16 | 24B1 | 43B0 | 43B1 | video driver id (8 = VGA; 0 = autodetect); replaced by the id `gfx_init` returns |
| 02 | u16 | 24B3 | 43B2 | 43B3 | sound driver id: 0 STD, 1 TAN, 2 ADL, 3 M32, 4 SBL, 5 PS1, 6 TAN, 7 PRO, 8 NLD (`-s<n>` overrides) |
| 04 | u8 | 24B5 | 43B4 | 43B5 | modules: bit n-1 set when `CSET<n>.DAT` exists (INTRO rewrites it every start) |
| 05 | u8 | 24B6 | 43B5 | 43B6 | latest module n |
| 06 | u8 | 24B7 | 43B6 | 43B7 | option (default 1) — AP → far `3974:012D` and `5f2c:004d` |
| 07 | u8 | 24B8 | 43B7 | 43B8 | option (default 1) — AP → `3974:0159`, `5f2c:0074` |
| 08 | u8 | 24B9 | 43B8 | 43B9 | toggle3 (default 1): INTRO `== 0` → `164d:0006(-2)`; AP → `3974:0185` |
| 09 | u8 | 24BA | 43B9 | 43BA | toggle4 (default 1): INTRO `== 0` → `164d:0006(-1)` |
| 0A | u8 | 24BB | 43BA | 43BB | toggle5; AP → `3974:007D` |
| 0B | u8 | 24BC | 43BB | 43BC | toggle6; AP → `3974:00A9` |
| 0C | u8 | 24BD | 43BC | 43BD | toggle7; AP → `3974:00D5` |
| 0D | s16[6] | 24BE | 43BD | 43BE | joystick 0 calibration: X min, X centre, X max, Y min, Y centre, Y max (default −127, 0, 127, −127, 0, 127) |
| 19 | s16[6] | 24CA | 43C9 | 43CA | joystick 1 calibration, same layout (the installed file has zeros here) |

(`Game/CONTROL.PRF` = video 8, sound 3, modules 1, latest 1, options 0 1 1 1 0 0 0, joystick 0
−127/0/127 twice, joystick 1 all zero.) The meaning of the option bytes belongs to sound (INTRO
toggles) and sim_flow (AP far copies) — hand-off.

| Program | Read | Write |
|---|---|---|
| INTRO | `control_load` `038e:0181`: `memset(DS:24B1, 0, 37)`; `fopen(work_dir+"control.prf","rb")`, else `fopen("control.prf","rb")` (RTL fopen, loose files only); none → return 0 (all fields 0); `fread(…, 1, 37)`; short read: if 0 bytes read, video = sound = 0; bytes +06..+0C = 1; both joystick-0 axes = −127/0/127; return 1 | `control_save` `038e:0687` at the end of main: `fopen(work_dir+"control.prf","wb")` (assert on failure, `main.c` line 0x266), `fwrite(DS:24B1, 37, 1)` |
| PS | `control_load` `1193:027a` in `shell_files_load`: `file_read("control.prf", DS:43B0, 37)`; ≠ 37 → assert("size of control", `file.c` 0x109) (fatal); then if X min == X max or Y min == Y max of joystick 0 → reset joystick 0 to −127/0/127 | `control_save` `1193:0306` in `shell_exit`: `file_write("control.prf", DS:43B0, 37)` |
| AP | `prefs_load` `4e0d:05f5` (sim_flow's init.c/control.c): `realism` file (below) into `DS:42C8` (16 bytes); `my_fopen("control.prf","rb")` → `my_fread(DS:43B1, 37, 1)`; missing → copy defaults `DS:06C4` (37 bytes: 0,0,0,0, 01 01 01 01, 0 0 0, −127/0/127 ×4); distribute bytes +06..+0C to far globals (table above), copy the two 12-byte calibration blocks to `60a9:096d(0)` / `60a9:096d(1)` (input section), call `5f2c:004d(+06)`, `5f2c:0074(+07)`, `6b4d:0751()` | `prefs_save` `4e0d:06fd` from `sim_exit`, **not in modes 2/3**: realism file "wb" (assert 0x26F), gather the far copies back, `my_fopen("control.prf","wb")` (assert 0x280), write 37 bytes |

PS file helpers (`file.c`, shell_data owns the other users): `1193:01b7` `file_read(name, buf,
size)` = `my_fopen(name,"rb")`, `my_fread(buf, 1, size)`, close, return bytes (0 if missing) —
the name is **not** prefixed with `work_dir` (current directory or a volume); `1193:01ff`
`file_write(name, buf, size)` = RTL `fopen(work_dir+name, "wb")` (assert `file.c` 0xF5), write,
close; `1193:0115` `make_name(base, n, ext)` → `DS:4B72` = base + itoa(n) (if n > −1) +
extension (125a:000f).

**`MREAL.PRF` / `CREAL.PRF`** (16 bytes, realism): PS `realism_load(name, buf)` `1193:0818`
(`file_read(name, buf, 16)`, missing → `0a8d:0192(buf, 0)` defaults), `realism_save(name, buf)`
`1193:0840`; `1193:0856` saves the current one before flying: SIM.IN mode (`DS:4B87`) == 1 →
`creal.prf` from `DS:47A9`, else `mreal.prf` from `DS:4357`. PS loads `mreal.prf` in
`0a71:015c` and both in `0a8d:07cb`, `0ed9:0347` (shell_data). AP: `realism_name()` `4e0d:05e0`
patches the first letter of `DS:032E` "?real.prf" to 'c' if `sim_mode` == 1 else 'm'; loaded to
`DS:42C8` by `prefs_load`, written by `prefs_save`. Field meanings: shell_data / sim_flow.

**`SIMPREFS.PRF`** (70 bytes): AP only, `4e0d:09d0` (read) / `4e0d:0b3e` (write), layout in
data.md §3.1; sim_flow owns the fields.

## 3. Input (keyboard, INT 1Ch, joystick, mouse, divide-by-zero, Windows) — PENDING
## 4. Timer — PENDING
Known: `timer_install(13)` INTRO 05da:2374 / PS 16e3:2988 / AP 1d32:47c2: PIT divisor 5041 →
236.69 Hz; callbacks via `timer_add` 05da:2307 (PS 16e3:291b; PS registers 229e:0013 with 1),
`timer_remove` 05da:2351; mask `DS:15C7` (INTRO). Details to follow.
## 5. DOS memory, EMS, mem.c, emm_pool.c — PENDING
Known: `dos_alloc` 05da:35e0 / 16e3:3bf4 / 1d32:5a2e, `dos_free` 05da:3657 / 16e3:3c6b / 1d32:5aa5;
huge helpers 05da:4611–4836 (§7 preamble); INTRO EMS 17bd, AP 24e1/24e5, AP `mem.c` 24b2 (debug
`mem.log`), `24d3` malloc wrappers, pool code in 1d32:1cac–25a5.
## 6. Volumes, chunk access, decompression — PENDING
Known: format verified in `port/formats/resources.md` (RLE method 1, LZW method 2).
## 7. Picture, palette and font loaders

These build on the resource API of §6 (open-by-name `res_open` 05da:589e, `res_is_open` 5c7a,
`res_close` 5c4b, `chunk_find(f, "XXX:YYY:", 0)` 5934 → size or −1, `chunk_size` 5c21,
`res_state_save/restore` 581a/5856, `my_fread` 049d:0411, huge read 049d:04f4, packed stream
`pk_open` 6b6c / `pk_read` 6f3d / `pk_size` 702d / `pk_close` 6db5). Every loader takes either an
open resource handle or a file name (`res_is_open(x)` decides) and closes what it opened.
Drawing, the driver's own pixel formats and the palette/driver entry points belong to the video
spec; this section gives what is read, how it is stored and which driver entry is called with
what. `drv[n]` = the n-th far pointer of the video driver jump table at INTRO `DS:1938`
(`DS:1938 + 4n`).

Memory helpers used (system library, all three exes; §5): `dos_alloc(u32 size, u32 flags)`
05da:35e0 / 16e3:3bf4 / 1d32:5a2e → far pointer (0 on failure), `dos_free(far)` 05da:3657 /
16e3:3c6b / 1d32:5aa5, near `malloc`/`free`/`calloc` wrappers INTRO `0000:03b4`/`03c3`/`040b`,
huge-pointer helpers `huge_norm` 05da:4611 (DX:AX → `seg + off>>4 : off & 0Fh`), `huge_add`
4640, `far_memmove` 469d (overlap-safe), `huge_memcpy` 4776, `huge_memset` 47b0 (in 32000-byte
pieces), `huge_cmp` 480a, `huge_norm_far` 4836; PS 16e3:4935…4b5a, AP 1d32:676f…6994 (same
order).

### 7.1 Bitmap object

A loaded bitmap is a **near** pointer `bmp` to a zero-terminated array of near pointers to frame
records (`calloc((n+1)*2)`); the records are one `calloc(n, 10)` block and `bmp[0]` points to its
start. Frame record (10 bytes):

| Off | Type | Meaning |
|---|---|---|
| 00 | u16 | pixel data offset — far pointer, normalised (offset < 16) for the SCN/VQT kinds; for the nibble-plane kind the driver fills +00..+05 |
| 02 | u16 | pixel data segment |
| 04 | i16 | kind: −1 VQT bit stream (decoded when drawn), −2 SCN, −3 SCN with `BMP:SCL:`, −4 raw 8-bit pixels (pre-decoded VQT), other = driver format (nibble planes converted by `drv[14]`/`drv[15]`) |
| 06 | u16 | width |
| 08 | u16 | height |

`bmp_count(bmp)` INTRO 05da:53ef = 0f2c:0010 (PS 39a1:0010, AP 26d2:000f / 7229:0598) counts
the entries. `bmp_draw(frame, …)` 0f2c:0032 (PS 39a1:0032, AP 26d2:0031) dispatches on +04:
−3 → 05da:06e9 (`drv` thunk), −2 → 05da:1e38 (SCN drawer), −1 → 0dc5:0049 (VQT drawer),
else 05da:06e5 (`drv` thunk) — video. `bmp_free(bmp)` 05da:53c1 (= 0ef8:0342; AP 7229:056a):
`dos_free(frame0.ptr)` (the one pixel block all frames share), then `bmp_free_table` 05da:539d
(AP 7229:0546): `free(bmp[0]); free(bmp)`.

### 7.2 `bmp_load(x)` — INTRO 0ead:0002, PS 3922:0002, AP 6f97:0000 (verified)

```
f = open if needed; save state S0 (581a)
if chunk_find(f,"BMP:SCN:"):                                   // cockpit wings/tails/sights
    save state S1 (at SCN:); restore S0; bmp_info_list(f,&n,&bmp)  // 0ead:0387
    set_kind(-2, bmp) /*0ead:036c: every frame +04 = kind*/; restore S1; first = 0; goto READ_OFFSETS
elif chunk_find(f,"BMP:OFF:"):
    my_fread(&first, 2, 1, f)          // low word of the first u32 offset, or FFFFh = frames follow each other
    restore S0; bmp_info_list(f,&n,&bmp); set_kind(-1, bmp)
    if !chunk_find(f,"BMP:VQT:"): fail
    if first == 0: goto READ_OFFSETS                           // explicit offset list
    // sequential VQT frames: decode now into raw pixels
    size = drv[13](bmp, &tmp)          // DS:196C: bytes the pixel block needs
    buf = dos_alloc(size); set_kind(-4, bmp)
    frame[i].ptr = buf + Σ previous (w*h) (huge add)             // consecutive
    vqt_predecode(f, bmp)              // 0ef8:000e, below
    goto FINISH
else:
    return bmp_load_planes(f)          // 05da:5001 (§7.4)
READ_OFFSETS:
    size = chunk_size(f); buf = dos_alloc(size); huge_read(buf, size, f)   // whole SCN:/VQT: payload
    chunk_find(f,"BMP:OFF:"); for i in 0..n-1: my_fread(&off32, 4, 1, f) (fail → free, fail)
        frame[i].ptr = buf + off32 (huge add)
FINISH:
    for each frame: ptr = huge_norm(ptr)
    if chunk_find(f,"BMP:RLE:"): bmp_to_scn(bmp, 16)           // 05da:5f97: re-encode as SCN, kind -2
    if chunk_find(f,"BMP:SCL:"): set_kind(-3, bmp)
    close if opened; return bmp          (fail: bmp_free(bmp), return 0)
```

`bmp_info_list(f, &n, &bmp)` 0ead:0387 (PS 3922:0387, AP 6f97:0385): `chunk_find("BMP:INF:")`,
read u16 n, allocate the table and records, read `n` widths then `n` heights (one `malloc(4n)`
temporary), fill +06/+08, terminate the table with 0. Returns 1/0.
`bmp_info_planes(f, &n, &bmp)` 05da:4ee4 (PS 168a:0000, AP 7229:0000): the same with two
`my_fread` per value (widths, then heights).

`vqt_predecode(f, bmp)` 0ef8:000e (PS 396d:000e, AP 6fe3:0000): computes the largest per-frame
need (`05da:35dc` = `drv` thunk `DS:1950` with w, h), tries `dos_alloc` of the whole remaining
chunk (probe with `dos_alloc(0xFFFFFFFF)` to learn the largest block); if that is impossible
falls back to the 0x3AB4-byte scratch `DS:1A58/1A5A` (§7.4) when the biggest frame fits, else
gives up silently. Reads the VQT data in pieces (huge read), and for every frame sets up the VQT
decoder context (`DS:328E` → local context: bit position, source pointer, four plane
destination pointers at `ptr + k*(w*h/4)`, row offsets `y*w`) and calls `0e2c:004e(0, 0, w, h)`
(the VQT quadtree decoder in "to memory" mode — video owns the decoder, resources.md §4b the
bit-stream format), then moves the unread tail of the buffer down and refills.

### 7.3 `bmp_to_scn(bmp, colours)` — INTRO 05da:5f97 (misnamed `dos_setblock` in symbols.csv), PS 16e3:5cf1, AP 71db:0000 (verified)

Re-encodes raw 8-bit frames (kind −4) **in place** into the SCN run/skip format of
resources.md §4c and shrinks the DOS block. INTRO globals: `mask` `DS:313A` (u8 = colours − 1 =
0Fh), `tmp` `DS:3138` (near `malloc(2000)`), `src` `DS:3130/3132`, `dst` `DS:3134/3136`
(far, starts at frame 0's data), `block` `DS:312A/312C`, `pending_nl` `DS:3128`, `size_par`
`DS:312E`; `run_min` `DS:1A56` (minimum run length that is coded as a run). AP: mask `DS:70E8`,
tmp `DS:70E6`, block `DS:70D8/70DA`, dst `DS:70E2/70E4`.

```
bmp_to_scn(bmp, colours):
  mask = colours - 1; tmp = malloc(2000); dst = block = frame0.ptr
  for each frame f:
      dst = huge_norm(dst); scn_encode(f); f.ptr = dst_at_frame_start; f.kind = -2
  size_par = paragraphs(dst - block) (rounded up); INT 21h AH=4Ah ES=block.seg BX=size_par
  free(tmp); return bytes

scn_encode(f):                                    // 05da:62b4
  base = 1; if mask == 0Fh and VGA (DS:0A9F): base = min non-zero pixel of the frame
  out(placeholder); pending_nl = 0; lit_n = 0; skip = 0
  for y in 0..h-1:
      row = next w source bytes (huge_memcpy into a 256-byte stack buffer)
      for p in row:
          if p == 0: if lit_n: lit_flush(tmp, lit_n), lit_n = 0; skip++
          else:
              tmp[lit_n++] = (p - base) & mask
              if skip == 0: emit pending_nl zero bytes; pending_nl = 0
              else: emit_skip(skip), skip = 0
      if lit_n: lit_flush; lit_n = 0
      skip -= w; pending_nl++                     // negative skip = x back-step for the next line
  if lit_n: lit_flush
  emit_skip(0)                                   // ends with 40h = end of frame
  placeholder = base

emit_skip(n):                                     // 05da:607c
  if pending_nl:
      if n < 0: out((-n) & 3Fh); m = ((-n) & 1C0h) >> 6; if m: out(m)   // newline, x -= n
                out(0) × (pending_nl - 1); pending_nl = 0; return
      out(0) × pending_nl; pending_nl = 0
  while n > 63: out(7Fh); n -= 63
  out(40h | n)

lit_flush(buf, n):                                // 05da:6196
  scan buf: a value repeated k >= run_min times → flush pending literals (lit_out),
      then out(BFh, v) while k > 63 (k -= 63), then out(80h | k, v)
  else append to a literal list; a list of 63 is flushed with lit_out
lit_out(k, list):                                 // 05da:6116
  out(C0h | k); if k odd: list[k] = 0, k++
  if mask == 0Fh: out((list[i] << 4) | list[i+1]) for i += 2    // two pixels per byte, high nibble first
  else: out(list[i]) for each
```
Only `bmp_load` calls it (`BMP:RLE:` present, colours = 16).

### 7.4 `bmp_load_planes(x)` — INTRO 05da:5001, PS 168a:011c, AP 7229:01aa (verified)

The nibble-plane bitmaps (`BMP:BIN:` low nibbles, `BMP:VGA:` high nibbles; `BMP:AMG:` = Amiga
bit planes, not used by any shipped file).

```
bmp_info_planes(f, &n, &bmp) or fail
size = drv[13](bmp, &tmp_size)                    // DS:196C: u32 pixel bytes + a temp size
pix = dos_alloc(size); if tmp_size: tmp = dos_alloc(tmp_size)
if scratch (DS:1A58/1A5A) == 0:                   // decompression scratch, freed again at the end
    if p = malloc(0x3CC4): free(p); p = malloc(0x3AC4)   // insist on 200h spare bytes
    scratch = huge_norm((DS:p + 16) & ~0Fh)       // paragraph aligned, 0x3AB4 usable
if !chunk_find(f,"BMP:BIN:"): fail
h = pk_open(0, f, "r", chunk_size(f))
while pk_read(h, pix_cursor, 0x7FFF) == 0x7FFF: pix_cursor += 0x7FFF (huge)
drv[14](bmp, pix, pk_size(h, tmp, …), …)          // DS:1970: store the low-nibble plane in driver format
pk_close(h); ok = 1
if VGA (DS:0A9F):
    kind = chunk_find("BMP:VGA:") ? 5 : chunk_find("BMP:AMG:") ? 6 : none
    if kind: h = pk_open(…); buf = dos_alloc(0x7FFF, halving until it succeeds)
        while (k = pk_read(h, buf, len)) > 0:
            if kind == 6: amiga_to_nibbles(buf, buf, k) /*05da:540f*/; k *= 4
            drv[15](buf, pix_cursor, k)           // DS:1974: merge the high nibbles
            pix_cursor += len (huge)
        pk_close(h)
cleanup: free buf/tmp; free the scratch if allocated here (DS:1A58/5A = 0);
on failure free pix, pk_close, bmp_free_table; close if opened; return bmp (0 on failure)
```
`amiga_to_nibbles(src, dst, n)` 05da:540f (AP 7229:05b8): for each source byte, its 8 bits are
written as 4 output bytes: bits 0,2,4,6 → value 0/1 in a new byte, bits 1,3,5,7 → OR 10h into
the same byte (processed in place, high addresses first). Dead with the shipped data.

### 7.5 Screens — `scr_load(page, x)` INTRO 0f35:000a, PS 39aa:000a, AP 6f83:0000 (verified)

```
f = open if needed (fail → return −1); save state
if !chunk_find(f,"SCR:VQT:"): restore state; return scr_load_planes(f)          // 05da:54ae
buf = dos_alloc(chunk_size); huge_read(buf, size, f)
ctx = vqt_begin(buf) /*0dc5:000a, DS:328E*/; if ctx: vqt_quad(0, 0, 320, 200) /*0e2c:0461*/; vqt_end() /*0dc5:003e*/
   // decodes straight to the current drawing page (video)
free buf; close if opened; return 0 (or −1)
```
`scr_load_planes(x)` INTRO 05da:54ae, PS 16e3:5208, AP 715b:0000: `06f1` (VGA write-mode reset,
video); width/height default 320×200, overridden by `SCR:DIM:` (two u16); `SCR:BIN:` packed →
read in bands of `rows = bufsize / (w/2)` lines into a near buffer (`malloc((w/2) << 7)`,
halved until it succeeds, minimum one line) and `drv[17]` (`05da:24eb` → `DS:197C`) (buf, x 0,
y, w/2*2, rows) for each band; if VGA and `SCR:VGA:` (5) or `SCR:AMG:` (6, via 540f, quarter
reads): the same with `drv[18]` (`05da:24ef` → `DS:1980`). Returns 0 / 1 / 5 / 6. The screen
goes directly into the current page; there is no screen object.

### 7.6 Palettes — `pal_load(x)` INTRO 05da:070b, PS 16e3:0d1f, AP 1d32:3e0b (verified)

Palette slots `DS:0C1E` (INTRO) = 10 far pointers; slot 0 is the working palette owned by
`pal_set` (05da:090e, video); `pal_load` takes the first free slot 1..9 (none → returns 0 without
loading).
```
size = DS:153C = pal_size[adapter]      // table DS:153E[DS:0A9D]: 300h VGA, 11h EGA, 102h CGA, 0 none
tag = pal_tag[adapter]                  // table DS:1576: "PAL:VGA:", "PAL:EGA:", "PAL:CGA:" or ""
open if needed
if chunk_find(f, tag): p = dos_alloc(size); my_fread(stack768, 1, size, f); far_memmove(p, stack768, size)
elif VGA (DS:0A9F) and chunk_find(f,"PAL:AMG:") and my_fread(amg, 1, 64, f):
    p = dos_alloc(size); for i in 0..31: c = amg[2i] | amg[2i+1] << 8     // Amiga 0RGB, 4 bits each
        *p++ = ((c >> 8) & 0Fh) << 2; *p++ = ((c >> 4) & 0Fh) << 2; *p++ = (c & 0Fh) << 2
    then 0x2A0 zero bytes (colours 32..255)
close if opened; slot = p; return p (far, 6-bit RGB triplets for VGA)
```
`pal_free(p)` 05da:0980 (PS 16e3:0f94, AP 1d32:4080) clears every slot holding `p` and frees it.
Everything that uploads, fades or cycles palettes (05da:090e, 09da, 0a00, 0a7b, 0b6b, 0b7e,
`103d`) is video.

### 7.7 Fonts — `font_load(x)` INTRO 05da:4a8f, PS 16e3:4db3, AP 7115:0000; `font_free(slot)` 05da:4e01, PS 16e3:5125, AP 7115:0372 (verified)

Font slots 2..19 (slot 0 = current font, a copy; slot 1 is the built-in one or unused). INTRO
arrays indexed by slot: `font_ptr` `DS:2ED4` (far[20]), `font_ofs` `DS:2F24` (far[20]),
`font_wid` `DS:2F74` (far[20]), `font_kind` `DS:2EC0` (u8[20]), `font_w` `DS:0AB4`, `font_h`
`DS:0AC8`, `font_base` `DS:2FC4`, `font_first` `DS:0ADC`, `font_count` `DS:0AF0` (u8[20] each).

```
i = first slot 2..19 with font_ptr[i] == 0 (none → return 0)
open if needed; if !chunk_find(f, "FNT:") → return 0
b = byte
if b == FFh or FDh (proportional):
    font_kind[i] = -b (1 = 1 bpp, 3 = 8 bpp)
    font_w[i] = byte (max width), font_h[i] = byte, font_base[i] = byte, font_first[i] = byte,
    font_count[i] = byte, u16 size
    h = pk_open(-1, f, "r", chunk_size); require pk_size(h) == size   // the u16 is the UNPACKED size
    blk = dos_alloc(size); require pk_read(h, blk, size) == size; pk_close(h)
    font_ofs[i] = blk                     // u16 offset[count]
    font_wid[i] = blk + 2*count           // u8 width[count]
    font_ptr[i] = blk + 3*count           // glyph bits
else (fixed):
    if b == FEh: font_kind[i] = 2, font_w[i] = byte, bpr = font_w   // 8 bpp fixed
    else:        font_kind[i] = 0, font_w[i] = b,    bpr = (b + 7) >> 3
    font_h[i] = byte, font_first[i] = byte, font_count[i] = byte
    n = bpr * font_h * font_count; p = malloc(n) (near); my_fread(p, n, 1, f)
    font_ptr[i] = DS:p; font_ofs[i] = font_wid[i] = 0
close if opened; return i
```
(Correction to resources.md §6: the u16 after `count` is the unpacked size, compared with the
packed header; FEh = fixed 8 bpp exists in the code, not in the data.)
`font_free(i)`: if `font_valid(i)` (05da:30f8: 1 ≤ i ≤ 19 and ptr ≠ 0): if slot 0 is the same
font, clear slot 0; free (`free` for a near fixed font, `dos_free(font_ofs)` for a packed one);
zero all fields. Selection, metrics and text drawing (05da:2fc1, 3098, 30c8, 3122, 3133, 3193,
33f7, 340e, 3573) are video.

### 7.8 `bmp_mtx_load` — INTRO 0f48:000c, PS 39bd:000c, AP 26db:0009 (likely)

Loads a bitmap through `bmp_load` and a `BMP:MTX:` tile matrix (u16 per cell) into `DS:1B2A`
(near `malloc(n*2)`), sets the tile size/area globals (`DS:1B32/1B34` = frame 0 w/h,
`DS:32A8` = 320 − w, `DS:32AA` = 200 − h …) for the TTM "matrix" background drawing; calls
`drv` entry `DS:19B8` first on adapters 2/8. The Ghidra output is unusable here; the rest of
segment 0f48 (023d, 026a, 0282, 02d3, 03d1) draws tiles. Hand-off to video (TTM); only the file
side is platform.

## 9. Port notes (`/* PORT: */` decisions; the faithful behaviour stays the reference)

### 9.1 Three programs in one process

The shared library is the same C code in the three programs, but its globals sit at different DS
offsets (e.g. `key_state` INTRO `DS:09EA`, PS …, AP …; `control_prf` INTRO `DS:24B1`, PS `DS:43B0`,
AP `DS:43B1`). Proposal:

1. **One emulated memory image per program, loaded on demand.** `mem[]` is a 1 MB+ real-mode
   address space (plus EMS, §9.4). Each "EXEC" of INTRO/PS/AP loads that EXE's image (AP: the
   de-overlaid `AP_flat.exe`, or just its DGROUP and far data segments) at a fixed load segment,
   applies relocations, and re-initialises DGROUP from the file exactly like DOS + `c0` do
   (initialised data from the image, BSS `DS:end_of_data…end_of_bss` zeroed, stack and near heap
   above it). Only one program is resident at a time, as in the original: nothing in the three
   programs survives in memory except `0000:0510` (and the video state, §9.3).
2. **Library code written once, parameterised by a per-program layout table.** Each shared global
   gets a symbolic id; a `struct prog_layout { u16 ds_ofs[N_GLOBALS]; u32 drv_table; … }` holds
   its DS offset per program (generated from `platform_symbols.csv`, which lists every global per
   exe). Accessors `G16(id)`, `G8(id)` resolve `DGROUP_base + layout->ds_ofs[id]`. The current
   program's layout is a global pointer switched by the chain loop. Game-side code (shell, sim)
   is program specific anyway and uses its own DS constants directly.
   Alternative (simpler, also acceptable): keep the library state in a C struct and **mirror** only
   the globals that program code reads/writes directly (key state table, tick counters, joystick
   values, control_prf, font/palette slots) into `mem[]` at the program's DS offsets. The
   per-program table of those offsets is the same `prog_layout`.
3. **The GCD chain becomes a loop in `main`:**
   ```
   marker16(0x510) = 0x29A; marker16(0x512) = free_paragraphs_constant;   // e.g. 0x9FFF-ish, > 0x9500 for INTRO's 609 200-byte test
   code = 1;
   while (code >= 1 && code <= 3) code = run_program(code);   // 1 INTRO, 2 PS, 3 AP; exit(n) unwinds with longjmp
   ```
   `exit()` inside a program is a `longjmp` back to the loop after running the RTL exit chain
   (atexit handlers: AP registers `ems_free_all` 24e5:00b6) and the library shutdown; any other
   code (0, ≥ 4) ends the port. The first run always starts INTRO, as GCD does.
4. **Command line**: the port passes GCD's tail (`-n<gamedir>\`) to every program: `-n` sets the
   work directory used for `CONTROL.PRF` writes and `SIM.IN`/`SIM.OUT`. Debug switches (`-pi`,
   `-s<n>`, `override`, AP `nlkle`, `-w/-d/-o`) can be forwarded from the port's own command line.
5. **State that must survive switches**: `0000:0510` (in `mem[]`, low memory is shared), the game
   folder files (`CONTROL.PRF`, `SIM.IN`, `SIM.OUT`, `SCRIPT.DAT`, `ROSTER.DAT`, `*.PRF`,
   `INTRO1.DAT`), the screen contents and palette (programs exit without resetting the video mode:
   the next program starts on top of the last picture), the sound driver state (PS passes 0x88 for
   an already initialised MT-32 — sound spec). Everything else is re-initialised.

### 9.2 Hardware and DOS replacements

| Original | Port |
|---|---|
| PIT reprogramming, INT 8 ISR and callbacks (§4) | a host timer thread or per-frame catch-up that runs the callback table at 236.69 Hz (13 × 18.2065); callbacks run in the program's context with the same order and countdowns |
| INT 9 ISR, BIOS key buffer, 40:17 flags (§3) | SDL key events translated to set-1 scan codes and fed through the same ISR logic (so the state table, remaps and BIOS-buffer words are exact) |
| INT 1Ch ramps | run from the timer at 18.2 Hz (every 13th tick), as the BIOS does |
| Port 201h joystick timing loop | SDL joystick axes mapped to the raw count range the calibration expects |
| INT 33h mouse | SDL mouse mapped to the driver's coordinate space |
| INT 21h/48h/49h/4Ah (`dos_alloc`) | an allocator over the conventional-memory part of `mem[]` (addresses matter only as segment:offset values stored in data; keep real-mode segment arithmetic) |
| INT 67h EMS | page frame at `E000:0000` (or the frame the original reports) inside `mem[]`, handles/pages as arrays, map = memcpy or pointer switching (§5) |
| INT 2Fh Windows checks | report "no Windows" |
| INT 24h handler (AP) | not needed |
| INT 0 divide handler | C division guarded where the original can divide by zero (§3) |
| `INT 19h` reboot (dead code) | not ported |
| `GCD.COM`'s `btest.bin` write test | dropped (or a writability check of the game folder) |

### 9.3 Memory checks

`[0000:0512]` must be set so INTRO (≥ 609 200 bytes) and PS (≥ 590 000) pass; AP's checks use
its own far-heap size (`mem_far_avail` ≥ 140 000) and EMS pages (≥ 19; 33 selects the tier 4
layout). The port reports ≥ 33 free EMS pages so AP runs in the tier-4 (higher detail) mode, and
enough far heap. `override`/`-o` keep working.

### 9.4 Files

Keep the lookup order of `my_fopen` (§6) and the loose-file behaviour: `CONTROL.PRF` etc. are read
from the current directory (PS/AP without the work-dir prefix), written with the prefix. The port
runs with the game folder as current directory, so both are the same folder.

## 10. Hand-offs
* **video**: `gfx_init` 05da:5c93 is called with (driver id, 0xFF, "vmcode.ovl"); returns the id
  (0 = failed). Driver entries used by the loaders: `drv[13]` DS:196C (bitmap byte size),
  `drv[14]` DS:1970 / `drv[15]` DS:1974 (store low / merge high nibble planes), `drv[17]` DS:197C /
  `drv[18]` DS:1980 (screen bands), DS:19B8, DS:1950. End of INTRO (`038e:0cba`) and PS
  `shell_exit` (`227c:00a4`) set `DS:0A92/0A96/0A98` (PS `2312/2316/2318`) and call
  05da:2fbd / 16e3:35d1(0) to make the displayed page visible instead of restoring text mode.
  VQT decoder 0dc5/0e2c is also used "to memory" by `vqt_predecode` 0ef8:000e (§7.2).
* **sound**: INTRO maps sound ids 4 and 7 → 2, PS only 4 → 2 and passes 0x88 for MT-32 when
  entered from the chain (don't reset). INTRO toggles CONTROL.PRF +08/+09 == 0 → `164d:0006(-2/-1)`.
  INTRO loads `ttd.sx` after a (failing) `chdir("TTD")`.
* **sim_flow**: AP `prefs_load` 4e0d:05f5 / `prefs_save` 4e0d:06fd copy CONTROL.PRF +06..+0C to
  far `3974:012D/0159/0185/007D/00A9/00D5` and call `5f2c:004d/0074`, `6b4d:0751`; debug options
  `-s -t -W` (DS:052E/0532/0536/053A/053C/0884); `sim_exit` 4e0d:0bb0 callers 5440:115b (code 1),
  60a9:0a28/0a6c (code 0); `DS:0539` EMS tier read by 5ea5, 6163, 62d2, 644a, 655d, 6b4d.
* **shell_ui / shell_data**: INTRO `intro_play` 038e:0973, `038e:0021` module pick; PS
  `fly_mission` 048e:01a0; `file.c` helpers 1193:01b7/01ff/0115 described in §2.8.
* **symbols.csv**: `ap 71db:0000 dos_setblock` (and INTRO 05da:5f97) should be `bmp_to_scn`.

## 11. Open questions
* §3–§6 pending (see status). Meaning of CONTROL.PRF option bytes +06/+07/+0A..+0C.
* AP `DS:1EBC` = "SH", `4b9e:0000`: purpose not traced.
* `bmp_mtx_load` (0f48) only outlined.
