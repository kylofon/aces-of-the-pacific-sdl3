# Platform: system library, start-up, configuration, resources (INTRO / PS / AP)

**Status: complete (phase 3; §3–§6 added by the finisher).** Parts: this file (§1.2, §2–§5,
§7, §9–§11) and `platform_resources.md` (§6). Symbols: `platform_symbols.csv` (start-up, loaders),
`platform_sys_symbols.csv` (§3–§5), `platform_res_symbols.csv` (§6).

Conventions: `port/RE_GUIDE.md`. DGROUPs INTRO 17E0, PS 4D08, AP 3EA4 (AP = `work/AP_flat.exe`).
Confidence: **verified** = read in the disassembly; **likely**; **guess**.

## Index
1.2 Library map and ownership · 2 Chain, start-up, main, fatal, configuration files ·
3 Input: keyboard, joystick, mouse, INT 0 divide handler, Windows, `sys_shutdown` ·
4 Timer (PIT, INT 8, callbacks, tick counters) · 5 DOS memory, huge pointers, EMS, `emm_pool.c`,
`mem.c`, near arena · 6 Volumes, chunk API, RLE/LZW decoder (`platform_resources.md`) ·
7 Loaders · 9 Port notes · 10 Hand-offs · 11 Open questions

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
* **Time base**: every program runs PIT channel 0 at 1193182 / 5041 = **236.69 Hz**
  (`timer_install(13)`); callbacks with rate 4 run at 59.17 Hz; the saturating
  `timer_countdown` (INTRO `DS:15BF`, PS `DS:2E3F`, AP `DS:31E5`) paces game waits (§4).
* **Divide handler**: INT 0 retries an overflowing `DIV/IDIV` with the dividend halved until the
  quotient fits (AP 1d32:69cc); render3d depends on it; a true /0 hangs (§3.6).
* Keys: INTRO/PS use their own INT 9 ISR feeding the BIOS buffer (with a "drop when exactly one
  key is pending" bug); AP keeps a private 1-entry queue of `scan<<8 | shift flags` (§3.3). The
  INT 1Ch ramp handler is never installed.
* **EMS** (AP): 64 KB page frame, max 4 pages mapped; holds sprite-set bitmaps (frame records
  with a segment word < 50h carry an EMS handle), render3d shapes and terrain tables and the
  recorder's Huffman tables in `emm_pool` pools, the recorder bit-stream cache, and the Borland
  overlay cache (§5.3–§5.4).
* Loose files override volume entries; lookup is by base name with a keyed hash (§6.1).
* Bitmap frame records store the **segment at +00 and the offset at +02** (correction to the
  first delivery of §7.1).

## 1.2 Map of the system library (INTRO `05da` / PS `16e3` / AP `1d32`) and who owns what

Same code in the three programs (AP moved a few modules into overlays: `7115` fonts, `715b`
screen planes, `7187` chunk access, `71db` SCN encoder, `7229` bitmap planes). PS/AP addresses are
given where the match is known (`port/shared_matches.csv`, checked); DS offsets differ per
program. "platform §n" = specified in this document.

| INTRO 05da | What | Owner |
|---|---|---|
| 0014–03f4 | keyboard install/restore/ISR, INT 1Ch ramps, key queue read, key-held test | platform §3.3 |
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
| 2b08 | `is_tandy`: byte `F000:FFFE == FFh && F000:C000 == 21h` → `DS:0A9C` = 1 (Tandy 1000 keyboard remap) | platform §4.6 |
| 2fc1, 3098, 30c8, 30f8, 3122, 3133, 3193, 33f7, 340e, 3573 | font select, metrics, string width, text drawing | video (30f8 `font_valid` used by §7.7) |
| 35e0, 3657 | `dos_alloc`, `dos_free` | platform §5.1 |
| 3667–3927 | joystick | platform §3.4 |
| 3957 | clipped line | video |
| 3a40–3c61 | mouse | platform §3.5 |
| 3c84, 3d01 | rotated/scaled bitmap drawing | video |
| 45d3 | read clip rectangle | video |
| 4611–4836 | huge-pointer helpers (normalise, add, memmove, memcpy, memset, compare) | platform §5.2 |
| 4844, 486e, 48a7 | divide-by-zero handler | platform §3.6 |
| 48cb, 48fd | clipped get/put pixel | video |
| 4933, 5c93, 5dc9, 5de1, 5f2e, 5f48, 5f6b, 5f83 | driver load, `gfx_init`, text mode, adapter detection, CRTC probe, BIOS mode/equipment | video |
| 4a8f, 4e01 | `font_load`, `font_free` | platform §7.7 |
| 4ee4, 5001, 539d, 53c1, 53ef, 540f, 54ae | bitmap/screen plane loaders | platform §7 |
| 5764–5c7a | chunk access | platform §6.3 |
| 5c92 | empty function | – |
| 5db4 | `sys_shutdown` = kbd_restore, mouse_shutdown, timer_restore, divzero_restore | platform §3.7 |
| 5f97, 607c, 6116, 6196, 62b4 | `bmp_to_scn` SCN encoder | platform §7.3 |
| 645b | clipped rectangle fill | video |
| 6567–7c51 | packed streams: RLE / LZW decompression (writer dead) | platform §6.4 |

Other platform segments: INTRO `049d` / PS, AP `0000` volume.c (§6.1), INTRO `05bb` fatal
errors (§2.7), `05cb` RESOURCE.CFG line table (dead, §6.2), `0491` / PS `2316` mouse glue (§3.5),
`0db2` / PS `1671` / AP `247d` Windows (§3.8), `17bd` / AP `24e1`, `24e5` EMS (§5.3), AP `2494`
asserts (§2.7), `24b2` mem.c and `24d3` arena (§5.5), AP `1d32:2050–25a5` EMS bitmaps and
`emm_pool` (§5.4). AP-only video code inside 1d32 (clip-span hooks `1cac–1e9d`, rotated-quad setup
`1eca`, `6d55` ellipse helper) and AP `244d` (graphics-state save/restore and driver-hook swaps)
belong to video. INTRO `1739:0802/080d` (called by the rotated-bitmap drawer 05da:3d01) → video.

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
program image is managed by the Dynamix `dos_alloc` (INT 21h/48h, §5.1; AP `mem.c` wraps it, §5.5 —
Borland `farmalloc` is not used), plus EMS in AP (§5.3).

AP 2494:019b (`stack_left`) compares `&local + _stklen` against 0FFFFh (stack check helper).

### 2.4 INTRO `main` (`038e:0ac1`) — verified

Globals (INTRO DS): `work_dir` `DS:2461` char[?] (≥ 80), `prf_loaded` `DS:2460` u8, `skip_intro`
`DS:00C0` u8, `mem_override` `DS:00C1` u8, `intro_module` `DS:00C2` u16, `control_prf` `DS:24B1`
(37 bytes, §2.8), `vol_active` `DS:00C5` u16 (set to 1 by `vol_init` when a volume was opened,
§6.1; the first delivery called it `no_chdir`, "never set" — wrong).

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
  chdir_unless("TTD"); snd_load_resource("ttd.sx", 0) /*1659:000b*/; chdir_up()
      // leftover developer layout: with volumes active (always, in the shipped game) no chdir is
      // done; ttd.sx comes from a volume
  if control.toggle3 == 0: 164d:0006(-2)      // sound option (sound spec)
  if control.toggle4 == 0: 164d:0006(-1)
```
The timer is installed by `snd_init` (sound hand-off, §4.7). `038e:0097` `chdir_unless(path)`:
returns 1 if `vol_active`, else `chdir(path) == 0`; `038e:00bc` `chdir_up()` = `chdir_unless("..")`.

`modules_detect` (`038e:0704`): `control.modules` (DS:24B5) = 0; for n = 1..7: if
`my_fopen("CSET<n>.dat","rb")` succeeds (a volume or loose file): `modules |= 1 << (n-1)`,
`control.latest` (DS:24B6) = n, close; then if `my_fopen("INTRO<n>.DAT","rb")` exists and its first
byte ≠ 0: `intro_module` (DS:00C2) = n. After the loop body, if `intro_module` ≠ 0: write one 0 byte
to `INTRO<intro_module>.DAT` opened with `"wb"` (through `my_fopen`, i.e. a loose file in the
current directory; volume.c section says how a write open is served). Data: M1SHL.DYN holds
`CSET0.DAT` ("ACES OF THE PACIFIC"), `CSET1.DAT` ("1946!") and `INTRO1.DAT` = 01; the installed game
has a loose `INTRO1.DAT` = 00 written by the first run. So the "1946" add-on intro plays once after
installation. `038e:0121` `make_name_n(base, n, ext)`: `strcpy(DS:244A, base)`; if n > −1
append `itoa(n, 10)`; then `make_path(DS:244A, ext)` and copy its result back to `DS:244A`; returns
`DS:244A` = `"<base><n>.<ext>"`. `038e:00cc` `make_path(s, ext)`: `r = strcat(strcat(s, "."),
ext)`; if `!vol_active` it also builds `DS:242C` = `ext + "\\" + r` (the `<ext>\` developer
sub-directory) but still returns r — the second string is unused. `038e:0004` `ipow(a, b)`: `r =
1; repeat b times r *= a` (16-bit, 1 for b ≤ 0). `038e:0021` `module_pick(u8 mask)`: collects `i`
in 0..7 with `mask & ipow(2, i−1)` (so bit 0 admits both 0 and 1) into a list of n entries,
`srand(time(0))`, returns `list[(s32)rand() * n / 32768]` (used by `intro_play`, shell_ui).
`038e:0247` `cfg_lookup(struct {char *key; int val;} *tab, char *line)`: first i with
`strstr(line, tab[i].key)` (table ends with an empty key) or −1; only used by the dead
`config_read`.

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
`227c:002a` `set_quit_flag()` sets `DS:00C1` = 1; `227c:0034(x)` `ctrl_esc_hook` (called with 0
by the keyboard ISR on Ctrl+Esc, §3.3.4): if x: `shell_exit(0)`; then `DS:00C1` = 1.

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

## 3. Input and system services (keyboard, joystick, mouse, INT 0, Windows)

Scope: keyboard (INT 9), the INT 1Ch "key ramp" handler, joystick (port 201h), mouse (INT 33h), the divide-overflow handler (INT 0), system shutdown,
and the Windows helpers (INT 2Fh); the timer is §4. All three programs link the same library code (INTRO seg `05da`,
PS `16e3`, AP `1d32`); only DS offsets differ, plus the AP keyboard ISR, which is a different version.
Addresses: `SSSS:OOOO` per exe; "–" = absent. Confidence: **verified** = read instruction by
instruction in all listed exes (PS/AP compared against INTRO with an aligned diff); **likely**;
**guess**.

### 3.0 Findings that matter for the port

* **Time base.** Every program programs PIT channel 0 through `timer_install(13)`:
  divisor = `0xFFFF / 13` = **5041** (0x13B1), so **IRQ0 runs at 1193182 / 5041 = 236.69 Hz**. The
  original BIOS INT 8 is chained every 13th tick (18.207 Hz, so the DOS clock stays right). Callbacks
  are registered with a divider `rate`: rate 1 = 236.69 Hz, **rate 4 = 59.17 Hz** (sound drivers,
  delay helpers, INTRO/PS 32-bit tick counters). A saturating down-counter `timer_countdown` is
  decremented on every tick (236.69 Hz). Game code uses it to pace frames and waits (PS
  `06c7/2171/22ce/2e25`, AP `368f/4e0d/5a75/5cde/5d56/6cdc`). The port needs an accurate 236.69 Hz
  virtual tick source that drives these counters and the callbacks in the original order.
* **INT 1Ch ramp handler is never installed.** All three exes call `kbd_install(0)` (INTRO
  `038e:089b`, PS `048e:00a7`, AP `60a9:0b3a`). So `tick_isr_1c` and its X/Y ramp values
  (`DS:0A43..`) are dead code. It is documented only so that nobody reimplements it. The per-set
  "current direction" bytes that the keyboard ISR keeps up to date *are* used (by `kbd_dir_bits`).
* **Key delivery.** INTRO and PS put keys into the BIOS type-ahead buffer (40:1E..3D) from their own
  INT 9 handler and read them back with `key_read`. AP keeps its own 1-entry queue whose entries are
  `scancode<<8 | BIOS shift flags`, not ASCII (see 3.3.5). A key-state table (bit 0 = key held) is
  kept for every scancode 00..58h. The scancode tables are byte-identical in all three exes.
* **Tandy code paths** (Tandy 1000 BIOS detection) are irrelevant on a PC; they are documented
  briefly.
* **Joystick.** The library auto-centres from one reading at `joy_calibrate` time and scales
  deflection to −127..127 with a dead zone of ±7. AP then applies the CONTROL.PRF min/centre/max
  calibration in game code (`60a9:097d`). INTRO never calibrates, so INTRO only reads buttons.
* **Mouse.** Coordinates are kept ×4 (the INT 33h range is set to 4×pixels) and are updated only by
  the INT 33h event handler. No exe installs a user callback.
* **Divide handler** retries a faulting DIV/IDIV with the dividend halved until it no longer
  overflows (it hangs on a true divide by zero; render3d relies on the retry, §3.6).
  `divzero_restore` is buggy and never puts the vector back.
* **Windows helpers**: detection by INT 2Fh 1600h/4680h. The "switch to Windows" path (clipboard
  text `"*~"`/`"*~doco"` + INT 2Fh 168Bh) is reachable only through a request flag that no code ever
  sets, so it is dead in all three exes (**likely**).

### 3.1 Function table (timer rows: details in §4)

| INTRO | PS | AP | name | signature | purpose | conf. |
|---|---|---|---|---|---|---|
| 05da:0014 | 16e3:62c9 | 1d32:0668 | kbd_install | `far int kbd_install(int hook_1c)` | hook INT 9 (and INT 1Ch if arg≠0), Tandy/enhanced detection, BIOS LED flags | verified |
| 05da:00d9 | 16e3:638d | 1d32:072d | kbd_restore | `far int kbd_restore(void)` | flush BIOS buffer, restore INT 9 / INT 1Ch | verified |
| 05da:0117 | 16e3:63cb | 1d32:075e | kbd_isr | `interrupt` | INT 9 handler (AP version differs, 3.3.5) | verified |
| 05da:02fd | 16e3:65aa | 1d32:0938 | tick_isr_1c | `interrupt` | INT 1Ch key-ramp integrator; **AP: bare `iret`**; never installed | verified |
| 05da:03ab | 16e3:6658 | – | key_read | `far u16 key_read(void)` | pop one word from BIOS type-ahead buffer, 0 if empty | verified |
| – | – | 1d32:0939 | key_queue_read | `far u16 key_queue_read(void)` | AP: pop one word from the private queue, 0 if empty | verified |
| 05da:03da | 16e3:6687 | 1d32:095e | kbd_dir_bits | `far int kbd_dir_bits(int set)` | direction bits (up 1, down 2, left 4, right 8) of the key currently held in key set 0/1 | verified |
| 05da:03f4 | 16e3:66a1 | 1d32:0978 | key_held | `far int key_held(int scancode)` | `key_state[sc] & 1` | verified |
| – | – | 1d32:098c | key_name_char | `far u8 key_name_char(int scancode)` | AP: printable char for a scancode (digit row → normal table, others → shifted table) | verified |
| – | – | 1d32:0001 | (not syslib) | `far u8 f(void)` | AP: returns byte `DS:5E3C` (a flag set/cleared by AP module `1c30`); no direct callers; belongs to the preceding module | verified (code), purpose unknown |
| 05da:2b08 | 16e3:311c | 1d32:4f56 | is_tandy | `far int is_tandy(void)` | F000:FFFE==FFh && F000:C000==21h → `is_tandy=1`; returns flag | verified |
| 05da:2307 | 16e3:291b | 1d32:4755 | timer_add | `far int timer_add(void far (*fn)(void), int rate)` | register callback every `rate` ticks; returns handle 1..16 or 0 | verified |
| 05da:2351 | 16e3:2965 | 1d32:479f | timer_remove | `far int timer_remove(int handle)` | clear mask bit; returns 1 (0 if handle out of range) | verified |
| 05da:2374 | 16e3:2988 | 1d32:47c2 | timer_install | `far int timer_install(int mult)` | PIT ch0 = 65535/mult, hook INT 8 | verified |
| 05da:23e1 | 16e3:29f5 | 1d32:482f | timer_restore | `far int timer_restore(void)` | PIT back to 65536, restore INT 8 | verified |
| 05da:241a | 16e3:2a2e | 1d32:4868 | timer_isr | `interrupt` | INT 8: countdown, callbacks, BIOS chaining | verified |
| 05da:3667 | 16e3:000e | 1d32:030d | joy_read_axes | near, in BL=axis mask, out SI,DI | raw one-shot counts from port 201h | verified |
| 05da:36ce | 16e3:0075 | 1d32:0374 | joy_scale | near, in AX=raw BX=centre CX=scale, out AX | raw → −127..127, dead zone | verified |
| 05da:3705 | 16e3:00ac | 1d32:03ac | joy_calibrate | `far int joy_calibrate(void)` | loop-speed calibration, presence, centre, scale; returns present mask | verified |
| 05da:383c | 16e3:01e3 | 1d32:04e5 | joy_read | `far void joy_read(int stick, int *x, int *y)` | scaled X/Y of stick 0/1 | verified |
| – | 16e3:025b | 1d32:055e | joy_read_raw | `far void joy_read_raw(int stick, int *x, int *y)` | raw counts X/Y | verified |
| 05da:38b4 | 16e3:0296 | 1d32:059a | joy_dir_bits | `far int joy_dir_bits(int stick)` | ±30 threshold → bits up1 down2 left4 right8 | verified |
| 05da:390d | 16e3:02ef | 1d32:05f5 | joy_button | `far int joy_button(int n)` | button n (0..3), 1 = pressed (existing name `joy_read_buttons` is misleading: it reads ONE button) | verified |
| 05da:3927 | 16e3:0309 | 1d32:060f | joy_axis | `far int joy_axis(int axis)` | one scaled axis 0..3 | verified |
| – | 16e3:0339 | 1d32:063f | joy_axis_raw | `far int joy_axis_raw(int axis)` | one raw axis 0..3 | verified |
| 05da:3a40 | 16e3:3d64 | 1d32:5b9e | mouse_init | `far int mouse_init(void)` | INT 33h reset, range, event handler | verified |
| 05da:3ab0 | 16e3:3dd4 | 1d32:5c0e | mouse_set_range | `far void mouse_set_range(int x,int y,int w,int h)` | INT 33h fn 7/8 (×4 coordinates) | verified |
| 05da:3ae1 | 16e3:3e05 | 1d32:5c3f | mouse_set_callback | `far void mouse_set_callback(void far (*fn)(void))` | user callback for the event handler (never called by any exe) | verified |
| 05da:3af2 | 16e3:3e16 | 1d32:5c50 | mouse_event_handler | far, INT 33h fn 0Ch handler | stores buttons/x/y; calls callback | verified |
| 05da:3b32 | 16e3:3e56 | 1d32:5c90 | mouse_vga_save | far | save VGA GC/SEQ state around the callback (hand-off video) | verified (INTRO/AP), likely (PS addr) |
| 05da:3b97 | 16e3:3ebb | 1d32:5cf5 | mouse_vga_restore | far | restore it | verified (INTRO/AP), likely (PS addr) |
| 05da:3bf0 | 16e3:3f14 | 1d32:5d4e | mouse_shutdown | `far int mouse_shutdown(void)` | INT 33h reset, remove handler | verified |
| 05da:3c0c | 16e3:3f30 | 1d32:5d6a | mouse_get_pos | `far void mouse_get_pos(int *x, int *y)` | last event position /4 | verified |
| 05da:3c36 | 16e3:3f5a | 1d32:5d94 | mouse_set_pos | `far int mouse_set_pos(int x, int y)` | INT 33h fn 4 | verified |
| 05da:3c61 | 16e3:3f85 | 1d32:5dbf | mouse_button | `far int mouse_button(int right)` | 0 = left, ≠0 = right, from last event | verified |
| 0491:000c | 2316:000f | – | mouse_init_dos3 | `far int (void)` | glue: mouse_init only if DOS major ≥ 3 (`_osmajor` DS:0092) else 0 | verified |
| 0491:0025 | 2316:0028 | – | mouse_shutdown_dos3 | `far int (void)` | glue | verified |
| 0491:003e | 2316:0041 | – | mouse_get_pos_dos3 | `far void (int*,int*)` | glue | verified |
| 0491:005f | 2316:0062 | – | mouse_button_dos3 | `far int (int)` | glue | verified |
| 0491:007c | 2316:007f | – | mouse_move_to | `far int (int x,int y)` | glue: get pos; if ≠ (x,y) → mouse_set_pos, else return 1 | verified (INTRO), likely (PS) |
| 05da:4844 | 16e3:4b68 | 1d32:69a2 | divzero_install | `far void (void)` | hook INT 0 | verified |
| 05da:486e | 16e3:4b92 | 1d32:69cc | divzero_isr | `interrupt` | halve dividend and retry | verified |
| 05da:48a7 | 16e3:4bcb | 1d32:6a05 | divzero_restore | `far void (void)` | **bug: reads instead of writes the vector** | verified |
| 05da:5db4 | 16e3:5b0e | 1d32:012a | sys_shutdown | `far void (void)` | kbd_restore, mouse_shutdown, timer_restore, divzero_restore | verified |
| 0db2:0002 | 1671:0007 | 247d:0005 | win_detect | `far int win_detect(void)` | 1 if running under Windows | verified |
| 0db2:0035 | 1671:003a | 247d:0034 | win_critical_section | `far void (int leave)` | 0 → INT 2Fh 1681h (begin critical section), ≠0 → 1682h (end). Existing param name `enter` is inverted. | verified |
| 0db2:004c | 1671:0051 | 247d:004b | win_switch_out | `far void (const char *tag)` (INTRO: no arg) | put `"*~"+tag` (80 bytes) on Windows clipboard, then INT 2Fh 168Bh BX=1 (focus system VM) | verified |
| – | 1671:00fd | 247d:00ee | win_clip_put | `far void (const char *tag)` | same without the 168Bh focus switch; never called | likely |
| 0dc0:000d | 166d:0009 | 2466:0118 | win_task_switch | `far void (void)` | caller-side wrapper: suspend sound, win_switch_out, resume (hand-off) | likely |

### 3.2 Globals

| name | INTRO DS | PS DS | AP DS | type | meaning |
|---|---|---|---|---|---|
| kbd_installed | 08EA | 3294 | 1B67 | u8 | 1 after kbd_install |
| kbd_caps_forced | 08EB | 3295 | 1B68 | u8 | init 0 in all exes, never written: ≠0 would force CapsLock on and ignore the Caps key |
| kbd_last_key | 08EC | 3296 | 1B69 | u16 | `scan<<8|ascii` of the last make code, 0 on any break code. **Written only, never read** |
| kbd_dir[2] | 08EE | 3298 | 1B6B | u8[2] | direction code 1..9 (0 = none) of the last pressed direction key, per key set (0 = keypad/arrows, 1 = QWE/ASD/ZXC) |
| kbq_ascii_mode | – | – | 1B66 | u8 | AP only, init 0, never written: 0 → queue low byte = BIOS shift flags (40:17) instead of ASCII |
| kbq_limit | – | – | 1B6D | s16 | AP only, init **1**, never written: max queued keys |
| kbq_count | – | – | 1B6F | s16 | AP queue fill count |
| kbq_buf[32] | – | – | 1B71 | u16[32] | AP ring buffer (64 bytes) |
| kbq_tail | – | – | 1BB1 | u16 | AP write byte index (0..3E, `&0x3F`) |
| kbq_head | – | – | 1BB3 | u16 | AP read byte index |
| kbd_ascii[0x59] | 0938 | 32E2 | 1BB5 | u8[] | scancode → ASCII / modifier flag (table 3.1) |
| kbd_shifted[0x59] | 0991 | 333B | 1C0E | u8[] | scancode → shifted ASCII |
| key_state[0x59] | 09EA | 3394 | 1C67 | u8[] | per-scancode attributes + bit0 = held (table 3.1) |
| ramp_x[2] | 0A43 | 33ED | 1CC0 | s16[2] | INT 1Ch integrator X per key set (dead) |
| ramp_y[2] | 0A47 | 33F1 | 1CC4 | s16[2] | integrator Y (dead) |
| ramp_autocentre[2] | 0A4B | 33F5 | 1CC8 | s16[2] | init {1,1}: snap to 0 when no direction key held (dead) |
| ramp_step | 0A4F | 33F9 | 1CCC | s16 | init 3: step per INT 1Ch tick (dead) |
| dir_axis_tab[8] | 0A51 | 33FB | 1CCE | u8[8] | dir 1..8 → axis flags for the ramp: `80 A0 40 E0 C0 F0 60 B0` |
| dir_bits_tab[10] | 0A59 | 3403 | 1CD6 | u8[10] | dir 0..9 → bits: `00 08 0A 02 06 04 05 01 09 00` (up1 down2 left4 right8) |
| tandy_remap_from[11] | 0A63 | 340D | 1CE0 | u8[11] | `59 5A 55 54 29 58 2B 4A 4E 56 57` |
| tandy_remap_to[11] | 0A6E | 3418 | 1CEB | u8[11] | `57 58 52 46 48 47 4B 50 4D 53 1C` |
| kbd_enhanced | 0A79 | 3423 | 1CF6 | u8 | 1 = Tandy with enhanced (101-key) keyboard |
| is_tandy | 0A9C | 231C | 26DC | u8 | set by is_tandy() |
| timer_installed | 15BE | 2E3E | 31E4 | u8 | |
| timer_countdown | 15BF | 2E3F | 31E5 | s16 | saturating down-counter, −1 per IRQ0 tick (236.69 Hz); read and written by game code |
| timer_divisor | 15C1 | 2E41 | 31E7 | u16 | PIT reload value (5041); also restored by joy_calibrate |
| timer_bios_reload | 15C3 | 2E43 | 31E9 | u16 | = mult (13) |
| timer_bios_count | 15C5 | 2E45 | 31EB | u16 | ticks left until the BIOS INT 8 is chained |
| timer_mask | 15C7 | 2E47 | 31ED | u16 | bit i = slot i in use |
| timer_fn[16] | 15C9 | 2E49 | 31EF | far ptr[16] | callback per slot (offset, segment) |
| timer_cnt[16] | 1609 | 2E89 | 322F | {u16 count; u16 reload}[16] | per-slot divider |
| joy_present[2] | 1664 | 0FF8 | 1B4A | u8[2] | stick 0/1 detected |
| joy_axis_ok | 1666 | 0FFA | 1B4C | u8 | after calibrate: bit0 A.X, bit1 A.Y, bit2 B.X, bit3 B.Y had raw < 400 |
| joy_centre[4] | 1667 | 0FFB | 1B4D | u16[4] | raw count at calibrate (A.X, A.Y, B.X, B.Y) |
| joy_scale[4] | 166F | 1003 | 1B55 | u16[4] | `0x7F00 / centre` |
| joy_tmp_x | 1677 | 100B | 1B5D | s16 | scratch |
| joy_delay | 1679 | 100D | 1B5F | u16 | inner delay loop count per sample |
| joy_dir_xy[2] | 167B | 100F | 1B61 | s16[2] | scratch X,Y for joy_dir_bits |
| mouse_x4 | 1680 | 2EE4 | 328A | u16 | last event X (mouse units = 4 × pixel) |
| mouse_y4 | 1682 | 2EE6 | 328C | u16 | last event Y |
| mouse_callback | 1684 | 2EE8 | 328E | far ptr | user callback (always NULL) |
| mouse_stack_top | 1818 | 307C | 3422 | – | private stack used inside the event handler |
| mouse_present | 182A | 308E | 3434 | u8 | |
| mouse_buttons | 182B | 308F | 3435 | u8 | BL of last event (bit0 left, bit1 right) |
| divz_installed | 1870 | 30D4 | 347A | u8 | |
| divz_old_seg | 1871 | 30D5 | 347B | u16 | |
| divz_old_off | 1873 | 30D7 | 347D | u16 | |

Code-segment variables: saved INT 9 vector at INTRO `05da:000C` (PS `16e3:62C1`, AP `1d32:0660`),
saved INT 1Ch at `05da:0010` (PS `16e3:62C5`, AP `1d32:0664`), saved INT 8 at `05da:2370`
(PS `16e3:2984`, AP `1d32:47BE`), and the two patchable immediates `05da:019D`/`01AA`
(PS `16e3:6450`/`645C`, AP `1d32:07E4`/`07F1`).

### 3.3 Keyboard

#### 3.3.1 Tables (identical bytes in INTRO, PS and AP, verified by comparing the images)

`kbd_ascii` values ≥ 80h with bits 4..6 clear are modifier flags (bit = BIOS 40:17 bit):
81h RShift, 82h LShift, 84h Ctrl, 88h Alt; C0h = CapsLock toggle (40h).
`key_state` bits: bit0 = held (runtime); bit1 set for letters and `[ ] \` (no code reads it);
bit2 = letter (Caps/Ctrl apply); bits 3..7 = direction key: bit3 = key set (0 keypad/arrows,
1 letter cluster), bits 4..7 = direction code in numeric-keypad layout
(1 right, 2 down-right, 3 down, 4 down-left, 5 left, 6 up-left, 7 up, 8 up-right, 9 centre).

```c
static const uint8_t kbd_ascii[0x59] = {
    0x00, 0x1B, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x30, 0x2D, 0x3D, 0x08, 0x09,  /* 00 */
    0x71, 0x77, 0x65, 0x72, 0x74, 0x79, 0x75, 0x69, 0x6F, 0x70, 0x5B, 0x5D, 0x0D, 0x84, 0x61, 0x73,  /* 10 */
    0x64, 0x66, 0x67, 0x68, 0x6A, 0x6B, 0x6C, 0x3B, 0x27, 0x60, 0x82, 0x5C, 0x7A, 0x78, 0x63, 0x76,  /* 20 */
    0x62, 0x6E, 0x6D, 0x2C, 0x2E, 0x2F, 0x81, 0x2A, 0x88, 0x20, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00,  /* 30 */
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  /* 40 */
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,                                            /* 50 */
};
static const uint8_t kbd_shifted[0x59] = {
    0x00, 0x1B, 0x21, 0x40, 0x23, 0x24, 0x25, 0x5E, 0x26, 0x2A, 0x28, 0x29, 0x5F, 0x2B, 0x08, 0x00,  /* 00 */
    0x51, 0x57, 0x45, 0x52, 0x54, 0x59, 0x55, 0x49, 0x4F, 0x50, 0x7B, 0x7D, 0x0D, 0x84, 0x41, 0x53,  /* 10 */
    0x44, 0x46, 0x47, 0x48, 0x4A, 0x4B, 0x4C, 0x3A, 0x22, 0x7E, 0x82, 0x7C, 0x5A, 0x58, 0x43, 0x56,  /* 20 */
    0x42, 0x4E, 0x4D, 0x3C, 0x3E, 0x3F, 0x81, 0x00, 0x88, 0x20, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00,  /* 30 */
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x37, 0x38, 0x39, 0x2D, 0x34, 0x35, 0x36, 0x2B, 0x31,  /* 40 */
    0x32, 0x33, 0x30, 0x2E, 0x00, 0x00, 0x00, 0x00, 0x00,                                            /* 50 */
};
static const uint8_t key_state_init[0x59] = {   /* bit0 always 0 in the image */
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  /* 00 */
    0x6E, 0x7E, 0x8E, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x02, 0x02, 0x00, 0x00, 0x5E, 0x9E,  /* 10 */
    0x1E, 0x06, 0x06, 0x06, 0x06, 0x06, 0x06, 0x00, 0x00, 0x00, 0x00, 0x02, 0x4E, 0x3E, 0x2E, 0x06,  /* 20 */
    0x06, 0x06, 0x06, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,  /* 30 */
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x60, 0x70, 0x80, 0x00, 0x50, 0x90, 0x10, 0x00, 0x40,  /* 40 */
    0x30, 0x20, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,                                            /* 50 */
};
```

Direction keys: set 0 = keypad 7 8 9 / 4 5 6 / 1 2 3 (scancodes 47 48 49 / 4B 4C 4D / 4F 50 51,
codes 6 7 8 / 5 9 1 / 4 3 2); set 1 = Q W E / A S D / Z X C (10 11 12 / 1E 1F 20 / 2C 2D 2E, the
same codes). Scancodes ≥ 59h (including the E0h/E1h prefixes) are ignored, so extended keys arrive
as their non-E0 twin (grey arrows = keypad arrows, right Ctrl = Ctrl, keypad Enter = Enter,
keypad `/` = `/`).

#### 3.3.2 kbd_install (INTRO 05da:0014, PS 16e3:62c9, AP 1d32:0668) — verified

```c
int kbd_install(int hook_1c) {
    if (!kbd_installed) {
        save INT 9 and INT 1Ch vectors (INT 21h AH=35h) into CS vars;
        set INT 9 -> kbd_isr;                          /* INT 21h AX=2509h */
        if (hook_1c) set INT 1Ch -> tick_isr_1c;       /* never: every caller passes 0 */
        kbd_enhanced = 0;
        if (is_tandy()) {                              /* PC: skipped */
            INT 15h with AX = 0xFFFF;
            if (CF set && byte[0040:0096] == 0x10) kbd_enhanced = 1;
            else if (INTRO or PS) {                    /* AP: unreachable - both the CF-clear and the
                                                          "not 0x10" branches jump straight to the end */
                patch the CS immediates at 019D and 01AA from 0xFF to 0xFE;
                key_state[0x29] = key_state[0x48]; key_state[0x2B] = key_state[0x4B];
                key_state[0x4E] = key_state[0x4D]; key_state[0x4A] = key_state[0x50];
            }
        }
        kbd_installed = 1;
    }
    byte[0040:0017] &= ~0x20;                          /* NumLock off (on every call) */
    if (kbd_caps_forced) byte[0040:0017] |= 0x40;      /* CapsLock on */
    return kbd_installed;                              /* AL */
}
```
Callers: INTRO `038e:089b` (sys_init, arg 0), PS `048e:00a7` (sys_init, arg 0), AP `60a9:0b3a`
(arg 0). The patched immediates belong to code that only runs when `kbd_enhanced == 1`, so the
patch never has any effect.

#### 3.3.3 kbd_restore (INTRO 05da:00d9, PS 16e3:638d, AP 1d32:072d) — verified

If installed: `kbd_installed = 0`; `word[40:1A] = word[40:1C]` (flush the BIOS buffer); restore
INT 9 and INT 1Ch from the CS vars (INT 1Ch is written back even if it was never hooked, which is
harmless). Returns 1, or 0 if it was not installed.

#### 3.3.4 kbd_isr, INTRO/PS version (INTRO 05da:0117, PS 16e3:63cb) — verified

PS differs from INTRO only by 7 alignment NOPs and the hook target (below).

```c
void interrupt kbd_isr(void) {
    uint8_t raw = inp(0x60);
    uint8_t p = inp(0x61); outp(0x61, p | 0x80); outp(0x61, p);     /* XT-style keyboard ack */
    uint8_t al = raw;
    if (is_tandy == 1) {                                              /* PC: skipped */
        if (kbd_enhanced != 1) {
            for (i = 0; i < 11; i++) if (al == tandy_remap_from[i]) { al = tandy_remap_to[i]; break; }
            /* compared including the break bit -> only make codes are remapped */
        } else {
            if (al == 0x29) al = 0x48;
            if (al == 0x2B) al = 0x4B;
        }
    }
    uint8_t sc = al & 0x7F, brk = al >> 7;
    if (sc >= 0x59) goto eoi;
    uint8_t old = key_state[sc];
    key_state[sc] = (old & (0xFE | brk)) ^ 1;   /* make: bit0 = 1; break: bit0 ^= 1 (a break of a
                                                   key that is not held SETS bit0 - quirk) */
    if (kbd_enhanced == 1 && (sc == 0x3A || sc == 0x45)) { al = sc; old &= 0xFF; }
        /* Tandy-enhanced only: Caps/NumLock breaks are treated as makes; 0xFF = patched byte */
    if (al & 0x80) {                                                  /* ---- break ---- */
        if (old & 0xF8) { int set = (old >> 3) & 1;
                          if (kbd_dir[set] == (old >> 4)) kbd_dir[set] = 0; }
        kbd_last_key = 0;
        uint8_t v = kbd_ascii[sc];
        if ((v & 0x80) && !(v & 0x70)) byte[40:17] &= (v ^ 0x7F);     /* release Shift/Ctrl/Alt */
        goto eoi;
    }
    /* ---- make ---- */
    if (old & 0xF8) kbd_dir[(old >> 3) & 1] = old >> 4;
    uint8_t v = kbd_ascii[sc];
    if (v & 0x80) {
        v &= 0x7F;
        if (!(v & 0x70)) { byte[40:17] |= v; goto eoi; }             /* Shift/Ctrl/Alt pressed */
        if ((v & 0x40) && kbd_caps_forced) goto eoi;
        if (old & 1) goto eoi;                                       /* typematic repeat: no toggle */
        byte[40:17] ^= v;                                            /* CapsLock toggle */
        goto eoi;
    }
    if (byte[40:17] & 0x04) {                   /* Ctrl */
        v |= 0x80; if (old & 4) v -= 0x20;      /* Ctrl+letter = uppercase|0x80: Ctrl+A = 0xC1 */
    } else if ((byte[40:17] & 0x40) && (old & 4)) {
        v -= 0x20;                              /* CapsLock + letter (Shift ignored) */
    } else if (byte[40:17] & 0x03) {
        v = kbd_shifted[sc];
    }
    uint16_t key = (sc << 8) | v;
    kbd_last_key = key;
    /* BIOS type-ahead insert, hard-coded ring 0x1E..0x3C (ignores 40:80/40:82) */
    uint16_t head = word[40:1A], tail = word[40:1C];
    bool skip = (head == 0x3C) ? (tail == 0x1E) : (head + 2 == tail);
    /* BUG: this tests "exactly one key pending", not "buffer full" (full is tail+2 == head).
       With one unread key the new key is dropped; a really full buffer still takes the key and
       then looks empty */
    if (!skip) { word[40:tail] = key; tail = (tail == 0x3C) ? 0x1E : tail + 2; word[40:1C] = tail; }
    if ((key >> 8) == 0x20 && (byte[40:17] & 4)) outp(0x20, 0x20);   /* Ctrl+D: early EOI, and
                                                                       the EOI below = 2 EOIs */
    if ((key >> 8) == 0x0F) goto eoi;                                 /* Tab: nothing special */
    if (key == 0x019B && (byte[40:17] & 4)) {                         /* Ctrl+Esc */
        t = tail - 2; if (t == 0x1C) t = 0x3C; word[40:t] = 0;        /* zero the slot just written */
        word[40:1A] = word[40:1C];                                    /* flush buffer */
        outp(0x20, 0x20);
        ctrl_esc_hook(0);   /* INTRO 05bb:0006 = empty retf; PS 227c:0034: with arg 0 it only sets
                               DS:00C1 = 1 (quit-request flag, hand-off) */
        return;             /* iret without a second EOI */
    }
eoi:
    outp(0x20, 0x20);
}
```
The ISR never chains to the BIOS INT 9, so Ctrl+Alt+Del, Pause, PrtSc and SysRq do nothing, and
40:18, 40:96 and the keyboard LEDs are never updated.

#### 3.3.5 kbd_isr, AP version (1d32:075e) — verified

Identical to 3.3.4 up to and including `kbd_last_key = key;` (same tables, same Tandy code, same
key_state/kbd_dir handling). The rest is different:

```c
    kbd_last_key = key;
    if (kbq_count < kbq_limit) {                 /* kbq_limit = 1 (static): the queue holds 1 key */
        uint16_t e = key;
        if (kbq_ascii_mode == 0) e = (e & 0xFF00) | byte[40:17];   /* always: scan<<8 | shift flags */
        kbq_buf[kbq_tail/2] = e; kbq_tail = (kbq_tail + 2) & 0x3F; kbq_count++;
    }
    if ((key >> 8) == 0x20 && (byte[40:17] & 4)) { outp(0x20,0x20); return; }   /* Ctrl+D: 1 EOI */
    if (byte[40:17] & 4) {                                             /* Ctrl held */
        if (key == 0x019B)                                ap_quit_request = 1;  /* Ctrl+Esc, DS:0B80 */
        else if ((byte[40:17] & 8) && (key >> 8) == 0x53) ap_quit_request = 2;  /* Ctrl+Alt+Del */
    }
    outp(0x20, 0x20);
    /* dead code at 1d32:091f: "if Ctrl && scan == 0x19 -> INT 5" (Ctrl+P print screen) */
```
Break codes and the modifier/Caps paths exit through the same EOI. There is no Tab case, no
Ctrl+Esc buffer flush and no hook call. `DS:0B80` is read by AP `60a9:09ed/09fa/0a1b` and
`6b4d:0092/00ef`, set to 1 by `60a9:0649/0680/06ee`, cleared by `60a9:0a8e` and `6cdc:1034`
(hand-off to sim_flow).

#### 3.3.6 Readers

* `key_read` (INTRO 05da:03ab, PS 16e3:6658): `pushf; cli`; if `word[40:1A] != word[40:1C]`:
  `ax = word[40:head]; head += 2; if (head == word[40:82]) head = word[40:80]; word[40:1A] = head`;
  else `ax = 0`; `popf`; return ax. Key word = `scan<<8 | ascii` as built above (ASCII 0 for
  F-keys, cursor keys, NumLock, ScrollLock; keypad keys give digits only with Shift).
* `key_queue_read` (AP 1d32:0939): `pushf; cli`; if `kbq_count == 0` return 0; else
  `e = kbq_buf[kbq_head/2]; kbq_head = (kbq_head+2) & 0x3F; kbq_count--`; `popf`; return
  `scan<<8 | shiftflags`.
* `kbd_dir_bits(set)` (INTRO 05da:03da, PS 16e3:6687, AP 1d32:095e): `return
  dir_bits_tab[kbd_dir[set != 0]]` (AH = 0). The arg is read at `[sp+4]` in a frame without BP.
* `key_held(sc)` (INTRO 05da:03f4, PS 16e3:66a1, AP 1d32:0978): `cli; r = key_state[sc] & 1;
  sti; return r` (no range check).
* `key_name_char(sc)` (AP 1d32:098c): `return (unsigned)(sc-2) <= 9 ? kbd_ascii[sc] :
  kbd_shifted[sc]` (AH = 0). Used by AP `60a9:072d` (key-binding display, hand-off).

Call sites (the meaning of each key belongs to the calling module):
* INTRO: key_read `0460:0054`; key_held `0460:0024/0032/0040` (scancodes 1Ch Enter, 01h Esc,
  39h Space: the "skip" test of the INTRO input module `0460:001a`); kbd_dir_bits: none.
* PS: key_read `06c7:0006`, `2171:0019`, `21f4:005b`, `2e25:0053`, `2e25:0626`; kbd_dir_bits
  `2e25:0095`; key_held `0b48:0604`, `21f4:002c/003a/0048`, `2e25:0075/0083/00b4/00c3/00d1/0427/047e`.
* AP: key_queue_read `60a9:059e`; kbd_dir_bits `60a9:05ee`; key_held `60a9:0078/0085/0092/009f`,
  `60a9:0544/0556/0568/057a/058e`; key_name_char `60a9:072d`.
* No code outside the library reads `key_state`, `kbd_dir`, `kbd_last_key` or the ramp values
  directly (checked by scanning every listing for those DS offsets).

#### 3.3.7 tick_isr_1c (INTRO 05da:02fd, PS 16e3:65aa; AP 1d32:0938 = `iret`) — verified, dead

It is never installed (3.3.2). For completeness: for set s = 1, then 0: `d = kbd_dir[s]`; if d == 0 and
`ramp_autocentre[s]` → `ramp_x[s] = ramp_y[s] = 0`; if d == 9 → both 0; else `f = dir_axis_tab[d-1]`:
if f bit7 → `ramp_x[s] = clamp(ramp_x[s] + (f bit6 ? −1 : +1) * ramp_step, −127, 127)`, then the
next two bits (bit5 = Y active and bit4 = Y negative when bit7 was set; bit6/bit5 when it was not)
do the same for `ramp_y` (+ = down). The clamp is on the magnitude relative to the current sign,
which is the same as a symmetric clamp. At 18.2 Hz with step 3 it reaches full deflection in about
2.3 s.

#### 3.3.8 Port notes (keyboard)

* Replace INT 9 with SDL key events translated to PC set-1 make codes (SDL_Scancode → XT code;
  extended keys map to their non-E0 twin as above). Run the make/break logic of 3.3.4/3.3.5 on them,
  with a private `shift_flags` byte in place of 40:17 (bits 0/1 Shift, 2 Ctrl, 3 Alt, 6 Caps;
  NumLock forced off). Start with CapsLock off, or seed it from the host.
* INTRO/PS: model the BIOS buffer as a 16-slot ring and keep the "drop the key when exactly one is
  pending" quirk (flag it as optional). AP: a 1-entry queue that holds `scan<<8 | shift_flags`.
* Keep the `key_state` bit0 semantics. "A break without a make sets bit0" cannot happen with SDL.
* Ctrl+Esc → PS sets the quit flag DS:00C1 (through the PS hook); AP sets the quit request to 1;
  Ctrl+Alt+Del in AP sets it to 2 (the OS will normally swallow Ctrl+Alt+Del).
* Drop the Tandy paths, the INT 1Ch ramp, the port 61h ack and the EOIs.

### 3.4 Joystick (game port 201h)

The code is identical in all three exes except for DS offsets; PS/AP add `joy_read_raw` and
`joy_axis_raw` (**verified**, aligned diff).

#### 3.4.1 joy_read_axes (INTRO 05da:3667, PS 16e3:000e, AP 1d32:030d) — near, verified

In: BL = mask of the port bits to time (3 = stick A X|Y, 0Ch = stick B X|Y, or a single bit).
Out: SI = count for the first bit (X), DI = count for the second bit (Y).
```c
pushf; cli;
for (n = 400; n && (inp(0x201) & bl); n--) delay(joy_delay);  /* wait until the one-shots are idle */
outp(0x201, 0);                                                 /* fire the one-shots */
si = di = 0;
for (n = 400; n; n--) {
    delay(joy_delay);                        /* inner `loop $` of joy_delay iterations */
    v = inp(0x201) & bl; if (!v) break;
    if (bl & 3) { si += v & 1; di += (v >> 1) & 1; }
    else        { si += (v >> 2) & 1; di += (v >> 3) & 1; }
}
popf;                                        /* restores IF */
```
The counts are 0..400 samples; one sample takes about `joy_delay` loop iterations.

#### 3.4.2 joy_calibrate (INTRO 05da:3705, PS 16e3:00ac, AP 1d32:03ac) — verified

```c
int joy_calibrate(void) {
    cli;
    outp(0x43,0x36); outp(0x40,0); outp(0x40,0);   /* PIT ch0 = 65536, mode 3 */
    outp(0x43,0x00); t0 = inp(0x40) | inp(0x40)<<8; /* latch + read */
    for (n = 1000; n; n--) { 6 filler instructions; inp(0x201); }
    outp(0x43,0x06); t1 = inp(0x40) | inp(0x40)<<8; /* latch (RW=00) + read */
    outp(0x43,0x36); outp(0x40, timer_divisor lo); outp(0x40, timer_divisor hi);  /* 0 = 65536 if no timer */
    sti;
    elapsed = t0 - t1;                              /* mode 3 counts down by 2 per PIT clock */
    joy_delay = 0x6FCC / elapsed; if (joy_delay == 0) joy_delay = 1;   /* div by 0 if elapsed==0 */
    joy_read_axes(3);  joy_centre[0] = si; joy_centre[1] = di;
    ok = (si < 400) , (di < 400) shifted into joy_axis_ok from the top (rcr);
    joy_present[0] = (both < 400);
    if (si) joy_scale[0] = 0x7F00 / si;  if (di) joy_scale[1] = 0x7F00 / di;
    joy_read_axes(0x0C); the same for [2],[3] -> joy_present[1];
    outp(0x201, 0); delay 20 `loop`s; v = inp(0x201);
    if (!(v & 3))   joy_present[0] = 0;             /* one-shots not running -> no stick */
    if (!(v & 0xC)) joy_present[1] = 0;
    joy_axis_ok >>= 4;                              /* bit0 A.X, bit1 A.Y, bit2 B.X, bit3 B.Y */
    return joy_present[1] << 1 | joy_present[0];
}
```
The stick must be centred during calibration: the centre is taken from this single reading.
0x6FCC = 28620 makes the sample loop roughly machine-independent (the time of 1000 port reads
divided into a constant).

Callers: INTRO none (the joystick is never calibrated, so `joy_present` stays 0 and only
`joy_button` works). PS `0b48:07cb/0828/0ba3`, `230d:0073`. AP `60a9:0ad8`.

#### 3.4.3 joy_scale (INTRO 05da:36ce, PS 16e3:0075, AP 1d32:0374) — near, verified

```c
int joy_scale(uint16_t raw, uint16_t centre, uint16_t scale) {
    int neg = (int16_t)(raw - centre) < 0;
    uint16_t a = abs((int16_t)(raw - centre));
    if (scale) a = (uint16_t)(((uint32_t)a * scale) >> 8);   /* bits 8..23 of the product */
    if (a > 127) a = 127;
    if ((a & 0xFF) < 8) a = 0;                  /* dead zone |v| < 8 */
    return neg ? -a : a;
}
```
With `scale = 0x7F00/centre`, a raw count of 2 × centre gives +127 and 0 gives −127.

#### 3.4.4 Readers — verified

* `joy_read(stick, int *x, int *y)` (INTRO 05da:383c, PS 16e3:01e3, AP 1d32:04e5): if
  `!joy_present[stick != 0]` return 0 **without writing *x, *y**. Otherwise joy_read_axes(3 or 0Ch),
  `*x = joy_scale(si, centre[2s], scale[2s])`, `*y = joy_scale(di, centre[2s+1], scale[2s+1])`
  (stick ≠ 0 → s = 1). Callers: PS `0b48:0886`; AP `60a9:0337` (stick 0), `6b4d:0ad8`.
* `joy_read_raw(stick, int *x, int *y)` (PS 16e3:025b, AP 1d32:055e): same presence test, writes
  the raw SI/DI. AP `60a9:039e` (stick 1).
* `joy_dir_bits(stick)` (INTRO 05da:38b4, PS 16e3:0296, AP 1d32:059a): if not present return 0;
  `joy_read(stick, &joy_dir_xy[0], &joy_dir_xy[1])`; bits: x < −30 → 4, else x ≥ 30 → 8;
  y < −30 → 1, else y ≥ 30 → 2 (same encoding as `kbd_dir_bits`). PS `2e25:012b`.
* `joy_button(n)` (INTRO 05da:390d, PS 16e3:02ef, AP 1d32:05f5): `return ((inp(0x201) >> ((n&3)+4))
  & 1) ^ 1;` 0 = A button 1, 1 = A button 2, 2 = B button 1, 3 = B button 2. Needs no calibration.
  INTRO `0460:0069/0077`; PS `06c7:0068/0076`, `0b48:05aa..05f0` (6 calls), `2171:0069/0077`,
  `21f4:006e/007c`, `2e25:00f9/0107`; AP `60a9:001a/0027/0034/0041` (buttons 0..3).
* `joy_axis(i)` (INTRO 05da:3927, PS 16e3:0309, AP 1d32:060f): `joy_read_axes(1<<i)`; value = SI
  (even i) or DI (odd i); `return joy_scale(value, centre[i], scale[i])`; `sti`. No presence test.
  Not called by any exe.
* `joy_axis_raw(i)` (PS 16e3:0339, AP 1d32:063f): the raw count of axis i. PS `0b48:083e/085a`;
  AP `60a9:0451` (axis 2), `60a9:048f` (axis 3), `60a9:0afc`, `6b4d:0aeb/0aff`.

#### 3.4.5 AP calibration with CONTROL.PRF (game side, for reference; hand-off to sim_flow)

AP keeps 2 × 12-byte records at `DS:4F60` (stick 0) and `DS:4F6C` (stick 1):
`{s16 x_min, x_centre, x_max, y_min, y_centre, y_max}`. They are loaded from CONTROL.PRF +0Dh / +19h
(defaults −127/0/127). `60a9:096d(n)` returns `&rec[n]` (`0x4F60 + 12*n`). AP input `60a9:02f0..`
maps every value through `60a9:097d(v, min, centre, max)` (**verified**):
```c
int joy_cal_map(int v, int mn, int c, int mx) {
    if (v <= mn) return -127;
    if (v <  c)  return lerp(v, mn, c, -127, 0);   /* 277a:41c4(v,x0,x1,y0,y1) = (int16)((int32)(v-x0)*(y1-y0)
                                                      / (x1-x0)) + y0, 16-bit imul/idiv, truncating (verified) */
    if (v == c)  return 0;
    if (v <  mx) return lerp(v, c, mx, 0, 127);
    return 127;
}
```
Stick 0 is read *scaled* (joy_read, −127..127) and then mapped; stick 1 and axes 2/3 are read
*raw* (joy_read_raw / joy_axis_raw) and mapped with record 1. AP 60a9:03ff/04cb derives a throttle
step from `(DS:4F5E − raw)` (hand-off).

#### 3.4.6 Port notes (joystick)

* Use SDL gamepad/joystick. Reproduce the library contract: `joy_calibrate` returns the present mask
  and stores the current position as the centre; `joy_read` returns −127..127 with a dead zone of
  ±7 and 0 at the centre; the raw functions return counts on a synthetic 0..~2×centre scale. The
  simplest choice: raw = 200 + axis * 200/32767 (range 0..400, centre 200), scale = 0x7F00/centre,
  and let the unchanged scale/calibration math run.
* Buttons: SDL buttons 0..3 → n 0..3 (A1, A2, B1, B2).
* Drop the PIT reprogramming and the loop-speed calibration (`joy_delay`).

### 3.5 Mouse (INT 33h)

Identical in the three exes (DS offsets aside) except `mouse_set_range`: INTRO/PS use
`max = (x+w−1)*4`, AP uses `max = (x+w)*4` (no `dec dx`). **verified**

#### 3.5.1 mouse_init (INTRO 05da:3a40, PS 16e3:3d64, AP 1d32:5b9e) — verified

```c
int mouse_init(void) {
    if (mouse_present) return 0;
    AX=0000h INT 33h;  mouse_present = (AX == 0xFFFF) ? 1 : (uint8_t)-AX;   /* neg ax -> al */
    if (AX_before_neg == 0) return 0;
    INT 33h AX=4 CX=DX=7FFFh;       /* move to the far corner */
    INT 33h AX=1; INT 33h AX=2;      /* show, hide (the cursor stays hidden) */
    INT 33h AX=0Fh CX=DX=8;          /* mickeys per 8 pixels = driver default */
    INT 33h AX=4 CX=DX=0;            /* position 0,0 */
    mouse_set_range(0, 0, screen_w, screen_h);   /* INTRO DS:116A/116C, PS 29EA/29EC, AP 2DAA/2DAC (video globals) */
    INT 33h AX=0Ch CX=1Fh ES:DX = mouse_event_handler;   /* move + L/R press/release */
    if (video_type == 8) { vga_byte_1826 = vga_byte_1827; vga_byte_1828 = vga_byte_1829; }
        /* INTRO DS:0A9D / PS 231D / AP 26DD; bytes INTRO 1826..1829, PS 308A..308D, AP 3430..3433 (hand-off video) */
    return 1;
}
```

#### 3.5.2 Others — verified

* `mouse_set_range(x,y,w,h)` (05da:3ab0 / 16e3:3dd4 / 1d32:5c0e): INT 33h AX=7 CX=x*4
  DX=(x+w−1)*4 (AP: (x+w)*4); AX=8 CX=y*4 DX=(y+h−1)*4 (AP: (y+h)*4). No other callers.
* `mouse_set_callback(fn)` (05da:3ae1 / 16e3:3e05 / 1d32:5c3f): `mouse_callback = fn`. Never called.
* `mouse_event_handler` (05da:3af2 / 16e3:3e16 / 1d32:5c50), called far by the mouse driver:
  switches to a private stack at DGROUP:`mouse_stack_top`, `mouse_buttons = BL`, `mouse_x4 = CX`,
  `mouse_y4 = DX`; if `mouse_callback` is set: `mouse_vga_save(); callback(); mouse_vga_restore();`
  (no arguments). The event mask (AX) is ignored.
* `mouse_vga_save/restore` (05da:3b32/3b97, 16e3:3e56/3ebb, 1d32:5c90/5cf5): save/restore
  GC regs 0,1,3,4,5,8 and SEQ reg 2 plus the latches (dummy write/read at A000:FFFF). Hand-off video;
  not needed in the port (there is no callback).
* `mouse_shutdown` (05da:3bf0 / 16e3:3f14 / 1d32:5d4e): if present: `mouse_present = 0`; INT 33h
  AX=0 (reset); AX=0Ch CX=0 ES:DX=0000:0000 (remove the handler); return 1. Else 0.
* `mouse_get_pos(int *x, int *y)` (05da:3c0c / 16e3:3f30 / 1d32:5d6a): if not present return
  (nothing written); `*x = mouse_x4 >> 2; *y = mouse_y4 >> 2` (unsigned). The values come only from
  the last event, there is no polling.
* `mouse_set_pos(x,y)` (05da:3c36 / 16e3:3f5a / 1d32:5d94): if present: `mouse_x4 = x*4;
  mouse_y4 = y*4;` INT 33h AX=4 CX,DX; return 1. Else return AL = 0.
* `mouse_button(right)` (05da:3c61 / 16e3:3f85 / 1d32:5dbf): if not present 0; else
  `(mouse_buttons >> (right ? 1 : 0)) & 1`.
* Glue (INTRO `0491`, PS `2316`): each wrapper runs only if `byte DS:0092 >= 3`. DS:0092 is the
  Borland RTL `_version` word stored by c0 startup (`0000:0016`), low byte = DOS major. Otherwise it
  returns 0. `mouse_move_to(x,y)` (0491:007c / 2316:007f) reads the position and calls mouse_set_pos
  only if it differs (returns its result), else returns 1.

Call sites: INTRO `0491:000c` ← one site, `0491:005f` ← 2 sites; PS `2316:000f` ×1, `2316:0041` ×1,
`2316:0062` ×10, `2316:007f` ×6; AP (no glue) mouse_init `60a9:083c`, mouse_shutdown
`60a9:0852`, get_pos `60a9:086e`, set_pos `60a9:08d1`, button `60a9:088a`; all three exes:
mouse_shutdown from sys_shutdown.

#### 3.5.3 Port notes (mouse)

Track the SDL mouse position in game pixels (after the letterbox/scale transform), stored ×4 and
clamped to the range set by `mouse_set_range` (the INT 33h driver clamps; INTRO/PS max = (w−1)*4,
AP max = w*4). Update `mouse_buttons` from SDL button state (bit0 left, bit1 right). `mouse_set_pos`
warps the host cursor (or only the virtual position when the pointer is relative/hidden). The game
draws its own cursor, so hide the OS cursor over the window. Always report "present" (DOS ≥ 3).

### 3.6 Divide-overflow handler (INT 0)

* `divzero_install` (05da:4844 / 16e3:4b68 / 1d32:69a2): `divz_installed = 1`; save `0000:0000`
  → `divz_old_off`, `0000:0002` → `divz_old_seg`; cli; set the vector to `divzero_isr`; sti.
  Called from INTRO sys_init `038e:0893`, PS sys_init `048e:009f`, AP `4e0d:0146`. **verified**
* `divzero_isr` (05da:486e / 16e3:4b92 / 1d32:69cc, `interrupt`, DS not reloaded and not used):
  faulting IP/CS at `[bp+2]/[bp+4]`. `w = word[CS:IP]`; if `(w & 0x00FE) != 0x00F6` (the opcode byte
  is not F6h/F7h — the 8086 pushes the address *after* the instruction): `IP -= 2` (assumes a
  2-byte `DIV/IDIV reg`) and store it back. On a 286 or later the pushed IP is the faulting
  instruction itself, so the test passes for every `F6/F7` form (register or memory operand) and
  IP is not changed. Then the opcode byte at the (possibly adjusted) IP: bit 0 set (`F7`, word
  form) → `DX:AX = (DX:AX) >> 1` (`sar dx,1; rcr ax,1`); clear (`F6`, byte form) → `AX = AX >> 1`
  (`sar`). `iret` re-executes the division with the halved dividend. Net effect: **a DIV/IDIV whose
  quotient overflows is retried with the dividend halved until the quotient fits**, giving the
  largest-magnitude representable result (roughly `dividend / 2^k / divisor`) instead of a crash.
  Cases that never terminate: a true divide by zero (the dividend converges to 0 or −1 and keeps
  faulting); an unsigned `DIV` whose dividend has the top bit set (`sar` keeps it set). A prefixed
  division (`66h` operand size, segment override) fails the opcode test, IP is moved back 2 bytes
  and execution resumes at a wrong address (**verified** code; behaviour inferred). render3d's
  16-bit fixed-point divides depend on the halving retry (hand-off: render3d/sim must implement a
  `div_retry()` helper with exactly these semantics where a quotient can overflow).
* `divzero_restore` (05da:48a7 / 16e3:4bcb / 1d32:6a05): if installed: clear the flag, then
  `mov ax,[divz_old_off]; mov ax,es:[0]; mov ax,[divz_old_seg]; mov ax,es:[2]`. **Bug: loads
  instead of stores, so the INT 0 vector is never restored** (it is left pointing at freed code
  after exit). **verified**
* Port notes: C code must not rely on hardware traps. Provide
  `s16 idiv16_retry(s32 num, s16 den)` / `u16 div16_retry(u32 num, u16 den)` (and 8-bit forms):
  `while (quotient does not fit) num >>= 1 (arithmetic);` then divide; the math/render modules
  call them at every 16-bit `idiv`/`div` that can overflow. Division by zero hung the original:
  treat it as unreachable (assert in debug builds, return 0 in release).

### 3.7 sys_shutdown (INTRO 05da:5db4, PS 16e3:5b0e, AP 1d32:012a) — verified

`kbd_restore(); mouse_shutdown(); timer_restore(); divzero_restore();` (near calls with a pushed CS).
Callers: INTRO `038e:0cb5` (exit path, after snd shutdown `1686:0004`) and `05bb:0013` (fatal error
path, after `049d:0d50`); PS `227c:006b` (exit), `4960:00e1`, `4960:0170`; AP `2494:008d`,
`2494:017e`, `4e0d:0bf8`.

### 3.8 Windows helpers (INT 2Fh)

* `win_detect` (0db2:0002 / 1671:0007 / 247d:0005) **verified**: `AX=1600h INT 2Fh`; if AL ∉ {00h,
  80h} → return 1 (Enhanced-mode Windows, or Windows/386 2.x for 01h/FFh). Else `AX=4680h INT 2Fh`;
  AX == 0 → 1 (Windows 3.x real/standard mode), else 0.
* `win_critical_section(leave)` (0db2:0035 / 1671:003a / 247d:0034) **verified**: `leave == 0` →
  `AX=1681h` (begin critical section), else `AX=1682h` (end critical section). Not called by any exe.
* `win_switch_out(tag)` (0db2:004c / 1671:0051 / 247d:004b) **verified**: build a text at
  `bufseg:0000` (INTRO seg `17DB`, AP `3AE9`; PS not checked): `"*~"`, then (PS/AP) far-strcat of
  `tag` (`0000:4b22`). Using the RTL int86x on INT 2Fh: `AX=1701h` (open clipboard); if AX ≠ 0:
  `AX=1703h DX=1 (CF_TEXT) ES:BX=bufseg:0 SI:CX=0:0050h` (set clipboard data, 80 bytes);
  `AX=1708h` (close clipboard); then `AX=168Bh BX=1` (set focus to the system VM = switch to the
  Windows desktop). Tags: PS `DS:0FCA` = `"doco"`, AP `DS:1D76` = `"doco"`, INTRO: none. Presumably a
  message to a Windows-side Dynamix front end (**guess**).
* `win_clip_put(tag)` (1671:00fd / 247d:00ee): the same without the 168Bh call; never called
  (**likely**).
* Wrappers (hand-off): INTRO `0dc0:000d`: `DS:264A = 1`; if win_detect: `164d:0006(−1)`,
  `164d:0006(−2)` (sound suspend, likely), win_switch_out, `16de:0002(−1/−2)` (resume). Called from
  INTRO `0460:01ab` only when `win_detect() && DS:264B != 0 && DS:264A == 0`. PS `166d:0009`
  (`DS:4F6C = 1`; `315c:004f/000e` around the call; tag "doco"), called from `2e25:054f` when
  `win_detect() && DS:4F6D && !DS:4F6C`. AP `2466:0118` (`DS:5EE0 = 1`; `3280:0009(−2/−1)`,
  switch("doco"), `32de:0008(−2/−1)`; `DS:5EE1 = 0`), with no direct caller found.
  **The request flags INTRO `DS:264B`, PS `DS:4F6D` and AP `DS:5EE1` are only ever written with 0**
  (INTRO `038e:0ad1`, `0460:01b2`; PS `048e:0269`, `166d:003b`, `2e25:0556`; AP `2466:012a/0169`,
  `50c8:0020`), so the switch never happens (**likely** dead: no code found that sets them, though
  a write through a pointer cannot be excluded).
* `win_detect` call sites: INTRO `0460:0193`, `0dc0:0015`; PS `166d:0011`, `2e25:0537`; AP
  `2466:0120`.
* Port notes: drop all of it (`win_detect` → 0).

### 3.9 AP-only functions at the start of 1d32

* `1d32:0001`: `return byte DS:5E3C` (no BP use). `DS:5E3C` is written by AP module `1c30`
  (`1c30:0dc7` = 1; `0dfc/0e60/1018` = 0; read at `1c30:04e7/0d85/0de8`). No direct caller was found.
  It is the tail of module `1c30`, not part of the system library (**likely**).
* `1d32:6aaf` (listed as a function by the index) is the final `retf` of `sys_exit` 1d32:6a91
  (§2.6), not a function.
* `1d32:072d` = kbd_restore; `1d32:0938` = tick_isr_1c (bare `iret`); `1d32:0939` =
  key_queue_read; `1d32:098c` = key_name_char (see 3.3). **verified**

## 4. Timer (PIT channel 0, INT 8)

Function table and globals: §3.1 / §3.2 (rows `timer_*`, `is_tandy`). Timer globals per exe: `timer_installed` INTRO `DS:15BE` / PS `DS:2E3E` / AP `DS:31E4`; `timer_countdown` `DS:15BF` / `DS:2E3F` / `DS:31E5`; `timer_mask` `DS:15C7` / `DS:2E47` / `DS:31ED`; `timer_fn[16]` `DS:15C9` / `DS:2E49` / `DS:31EF`; `timer_cnt[16]` `DS:1609` / `DS:2E89` / `DS:322F`.

### 4.1 timer_install(mult) (INTRO 05da:2374, PS 16e3:2988, AP 1d32:47c2) — verified

```c
int timer_install(int mult) {
    if (timer_installed) return 0;
    timer_mask = 0;
    is_tandy();                                 /* result unused here; sets is_tandy */
    save INT 8 vector (INT 21h AX=3508h) into the CS var;
    if (mult > 255 || mult == 0) return 0;      /* signed compare; the vector was saved anyway */
    timer_bios_reload = timer_bios_count = mult;
    timer_divisor = 0xFFFFu / mult;             /* DX:AX = 0000:FFFF div mult */
    cli;
    outp(0x43, 0x36);                           /* ch0, lo/hi, mode 3, binary */
    outp(0x40, timer_divisor & 0xFF); outp(0x40, timer_divisor >> 8);
    outp(0x21, inp(0x21) & 0xFC);               /* unmask IRQ0 and IRQ1 */
    set INT 8 -> timer_isr;                     /* INT 21h AX=2508h */
    sti;
    timer_installed = 1; return 1;
}
```
Every caller passes 13: divisor 5041, **236.69 Hz**; the BIOS handler still runs at
236.69 / 13 = 18.207 Hz.

### 4.2 timer_restore (INTRO 05da:23e1, PS 16e3:29f5, AP 1d32:482f) — verified

If installed: cli; `outp(0x43,0x36); outp(0x40,0); outp(0x40,0)` (65536 = 18.2 Hz); unmask
IRQ0/IRQ1; restore INT 8; `timer_installed = 0`; sti; return 1. Otherwise return 0. The callback
mask is not cleared.

### 4.3 timer_add(fn, rate) (INTRO 05da:2307, PS 16e3:291b, AP 1d32:4755) — verified

Stack args: `[bp+6]` = fn offset, `[bp+8]` = fn segment, `[bp+0A]` = rate.
```c
int timer_add(void far *fn, int rate) {
    if (!timer_installed) return 0;
    if (timer_mask == 0xFFFF) return 0;
    for (i = 0; timer_mask & (1 << i); i++) ;   /* lowest free slot */
    timer_cnt[i].reload = timer_cnt[i].count = rate;
    timer_fn[i] = fn;
    cli; timer_mask |= 1 << i; sti;
    return i + 1;                               /* handle */
}
```
Note: registration fails silently (returns 0) when the timer is not installed yet.

### 4.4 timer_remove(handle) (INTRO 05da:2351, PS 16e3:2965, AP 1d32:479f) — verified

`i = handle - 1; if (i & 0xF0) return 0;` (only the low byte of the handle is tested)
`cli; timer_mask &= ~(1 << i); sti; return 1;`. Removing handle 0 (the value of a failed add)
gives i = 0xFFFF, whose low byte FFh fails the test, so it is a no-op returning 0.

### 4.5 timer_isr (INTRO 05da:241a, PS 16e3:2a2e, AP 1d32:4868) — verified

```c
void interrupt timer_isr(void) {               /* DS = DGROUP, IF stays 0 throughout */
    int16_t c = timer_countdown - 1;
    timer_countdown = (c < 0) ? ~c : c;         /* 0 stays 0; a negative value v becomes -v (quirk) */
    for (i = 0, m = timer_mask; m; i++, m >>= 1)          /* slots in ascending order */
        if (m & 1) {
            if (--timer_cnt[i].count == 0) {
                timer_fn[i]();                  /* far call, IF=0, before the EOI */
                timer_cnt[i].count = timer_cnt[i].reload;
            }
        }
    if (--timer_bios_count != 0) { outp(0x20, 0x20); return; }
    timer_bios_count = timer_bios_reload;
    jmp far old_int8;                           /* BIOS clock + BIOS EOI */
}
```
The mask is re-read at the start of every tick. A callback that removes itself takes effect on the
next tick. A callback registered with rate 0 fires only after 65536 ticks (the count wraps).

### 4.6 is_tandy (INTRO 05da:2b08, PS 16e3:311c, AP 1d32:4f56) — verified

`if (byte[F000:FFFE] == 0xFF && byte[F000:C000] == 0x21) is_tandy = 1; return (int)(int8_t)is_tandy;`
(Tandy 1000 BIOS signature). The flag is never cleared. Port: always 0.

### 4.7 Who installs the timer and registers what

| exe | where | call | effect |
|---|---|---|---|
| INTRO | snd_init `1593:0045` | `timer_install(13)` | only if the device arg ≠ −1, the driver loaded (`16ac:000b`) and the timer is not installed yet |
| INTRO | snd_init `1593:0063` | `timer_add(17de:1373, 4)` → handle `DS:1F4F` | sound driver service, 59.17 Hz (hand-off sound) |
| INTRO | `0460:0104` (input init `0460:00d3`) | `timer_add(0460:000b, 4)` → handle `DS:24D6` | 32-bit counter `DS:24D8/24DA` += 1 at 59.17 Hz (reset to 0 here); read by `0460:01bd/0232`, `10fc:0020/0070/011b/013c`; removed at `0460:0137`, `0460:016c` |
| INTRO | `16d5:006c` (in `16d5:0054`) | `timer_add(16d5:008d, 4)`, busy-wait, remove | delay: `DS:33D4 = 5`, callback decrements it, wait while > 0 → 5 × 4 ticks = 84.5 ms |
| INTRO | `1686:0021/0036` (snd shutdown) | timer_remove(sound), timer_restore | |
| PS | snd_init `452a:0046` / `452a:0064` | `timer_install(13)` (same conditions as INTRO, installed flag `DS:3971`); `timer_add(17df:430a, 4)` → `DS:3973` | sound service 59.17 Hz |
| PS | sys_init `048e:0097` (after snd_init `048e:0076`) | `timer_add(229e:0013, 1)` | 32-bit counter `DS:1CC8/1CCA` += 1 at **236.69 Hz**; read by `229e:001f` (cli; DX:AX; sti) → used by `22a0:0009` (timeout_expired), `22a0:0050` (timeout_start), `22a0:006a` (timeout_expire_now) |
| PS | `21f4:00e1` (in `21f4:00cd`) | `timer_add(21f4:0009, 4)` → `DS:52A8` | 32-bit counter `DS:52AA/52AC` at 59.17 Hz (reset to 0); used by `22a0:0089`, `22a0:00d2`, `22a0:018e`, `22a0:01aa` (the same timeout helpers on the 59 Hz clock); removed at `21f4:0114/0149` (= INTRO module `0460`) |
| PS | `466c:006d` (in `466c:0055`) | delay callback `466c:008e`, rate 4, counter `DS:76B0 = 5` | 84.5 ms delay |
| PS | snd shutdown `461d:0022/0037` | timer_remove(`DS:3973`), timer_restore if `DS:3971` | |
| AP | `4e0d:0168/0178` (init, if `DS:0532 ≠ 0` and `DS:0530 == 0`) | `timer_install(13)`; `timer_add(0000:02db, 1)` | 32-bit counter `DS:18D2/18D4` at 236.69 Hz, read by `0000:02e7`; used by `4b31:0000` timeout_expired, `4b31:0041` timeout_start, `4b31:0062` timeout_expire_now. If `DS:0530 ≠ 0`, `4e0d:0183` calls `0000:02db` once directly instead |
| AP | `5a75:0c81/0c91/0ca1` | `timer_install(13)`; `timer_add(3060:17e2, 4)` (sound service); `timer_add(0000:02db, 1)` | `5a75:0d5f` calls timer_restore at the end. If this runs while the 4e0d timer is still installed, install fails but both adds succeed, so the 236 Hz counter would count twice per tick (open question 3) |
| AP | `32d5:0072` (in `32d5:0060`) | delay callback `32d5:0093` (`dec DS:65EC`), rate 4, `DS:65EC = 5` | 84.5 ms delay |
| AP | sys_shutdown `1d32:012a` | timer_restore | |

Timeout helper struct (PS `22a0`, AP `4b31`): `{u32 start; u16 duration}`.
`timeout_start(t, d)`: `t->start = now(); t->duration = d`. `timeout_expired(t)`: if the timer is not
installed → 1; else `(now() - t->start) > t->duration` (unsigned 32-bit). `timeout_expire_now(t)`:
`t->duration = 0; t->start = now() - 1`. (**verified** for AP 4b31:0000/0041/0062 and PS
22a0:0009/0050/006a/018e/01aa; PS `22a0:00d2` is an interpolation variant, not analysed.)

Users of `timer_countdown` (the 236.69 Hz saturating counter) outside the library:
PS `06c7:063b..0808` (values 0x58C and 0x0F), `2171:0013/00b9`, `22ce:0010/014d` (5), `2e25:064a`;
AP `368f:00c1` (`368f:00b7` returns it, or 0 if the timer is not installed), `368f:00e6`
(`delay18(n)`: `countdown = 13*n`, wait until 0 or input), `368f:0116..0131`, `4e0d:083e/09c8`
(speed benchmark: countdown = 10000, run 32 iterations, return `10000 − countdown`), `5a75:0d2b`
(10), `5cde:0400/047b`, `5d56:0179` (0x1D8), `6cdc:0875..0bc1` (0x0F, 0x58C). All hand-off (callers'
modules); the port just has to provide the counter.

### 4.8 Port notes (timer)

* Run a virtual 236.69 Hz tick (period 5041/1193182 s = 4.2249 ms) from an accumulator on the
  host's high-resolution clock, on the main thread (e.g. `pump_ticks()` called from every busy-wait,
  input poll and frame loop), or on an SDL timer thread with a mutex, because callbacks touch game
  state. Each tick: saturating `timer_countdown` decrement, then the slot callbacks in ascending
  order with their dividers. The BIOS chain is not needed. If the DOS date/time is read anywhere, use
  the host clock.
* Callbacks ran with interrupts disabled. Everything that reads multi-word counters did `cli` around
  the read. With a main-thread pump this is automatic.
* Frame pacing: games wait on `timer_countdown` or on the 59.17 Hz / 236.69 Hz counters. There is no
  vsync-based pacing in this library. The AP speed benchmark (`4e0d:0835`) measures elapsed ticks
  of a work loop and must see realistic values. On a fast host it will measure near 0 (hand-off to
  sim_flow: pick a fixed value).
* Keep timer_add's "fails if not installed" behaviour, or make the port install the virtual timer
  unconditionally. Note that INTRO/PS only install it when sound is enabled (open question 2).

## 5. DOS memory, huge pointers, EMS, `mem.c`, `emm_pool.c`

Confidence: everything in this section was read instruction by instruction (**verified**) unless
marked. Memory model: Borland medium; near data = the 64 KB DGROUP (static data, stack, near heap,
§2.3); far data = DOS blocks from `dos_alloc`, Borland `farmalloc` is not used by the library.

### 5.1 `dos_alloc` / `dos_free` — INTRO 05da:35e0 / 05da:3657, PS 16e3:3bf4 / 16e3:3c6b, AP 1d32:5a2e / 1d32:5aa5

Byte-identical in the three programs.

```c
void far *dos_alloc(u32 size, u16 unused, u16 flags) {   /* [bp+6] size, [bp+0A] ignored, [bp+0C] flags */
    if (size == 0xFFFFFFFF) {                         /* query: both words FFFFh */
        INT 21h AH=48h BX=FFFFh;                      /* always fails */
        return (void far *)((u32)BX << 4);            /* DX:AX = largest free block in BYTES (not a pointer) */
    }
    u16 par = (u16)(size >> 4) + ((size & 0xF) != 0); /* 16-bit: sizes >= 1 MB wrap */
    INT 21h AH=48h BX=par; if (CF) return 0L;
    if (flags & 1) huge_memset(MK_FP(AX, 0), 0, size);   /* zero-fill */
    return MK_FP(AX, 0);                              /* offset always 0 */
}
void dos_free(void far *p) { INT 21h AH=49h ES=FP_SEG(p); }   /* offset ignored, error ignored */
```
Callers pass the flags as the high word of a `long` (`dos_alloc(n, 0, 1)` = zeroed, `(n, 0, 0)` or
`(n, 0L)` = not zeroed). `dos_alloc(-1L, 0)` is the "free far memory" query: AP
`mem_far_avail()` = `mem_far_new(-1L, 0)` (§5.5), used by AP main (`- 140000 < 0` → "MEMORY TOO
LOW"). DOS blocks are paragraph aligned and the returned offset is 0, which the SCN encoder
(`INT 21h/4Ah` on the block, §7.3), the bitmap loaders and the EMS bitmap code rely on.

Near heap: INTRO `0000:03b4` / `03c3` / `040b` are thin `malloc` / `free` / `calloc` wrappers.
AP `0000:035c` `safe_malloc(n)`: `n == 0xFFFF` → 0; `p = malloc(n)`; if `(u16)(p + n) > 0xFFFF −
_stklen` (`DS:05B2` = 0E74h) → `free(p)`, return 0 (keeps the top 0E74h bytes of DGROUP free);
`0000:03ac` = `free`.

### 5.2 Huge-pointer helpers — INTRO 05da:4611–4843, PS 16e3:4935–4b67, AP 1d32:676f–69a1 (same order)

All far pointers are `seg:off`; "normalised" = offset < 16.

| INTRO | PS | AP | Name | Contract |
|---|---|---|---|---|
| 05da:4611 | 16e3:4935 | 1d32:676f | `huge_norm` (near, regs) | DX:AX → `DX += AX >> 4; AX &= 0Fh` |
| 05da:4623 | 16e3:4947 | 1d32:6781 | `huge_norm_top` (near) | normalise; if `DH & F0h` (seg ≥ 1000h): `AX += FFF0h, DX -= 0FFFh` (largest offset); else `AX += DX << 4, DX = 0`. Used for backward copies |
| 05da:4640 | 16e3:4964 | 1d32:679e | `huge_add` (near) | DX:AX += CX:BX bytes: `AX += BX` (carry → `DX += 1000h`), `DX += rcr17(CX, 5)` = `CX << 12` for CX < 32 (not normalised) |
| 05da:4654 | 16e3:4978 | 1d32:67b2 | `huge_sub` (near) | DX:AX −= CX:BX, then normalise |
| 05da:466f / 4686 | | | copy primitives (near) | backward / forward `rep movsw` + odd byte |
| 05da:469d | 16e3:49c1 | 1d32:67fb | `far_memmove(void far *dst, void far *src, u32 n)` | overlap-safe (compares the normalised addresses; backward copy from `+n−1` when dst > src), in pieces of ≤ 32000 (7D00h) bytes, renormalising both pointers per piece; returns the original `dst` |
| 05da:4776 | 16e3:4a9a | 1d32:68d4 | `huge_memcpy(void far *dst, void far *src, u16 n)` | normalises both, one forward copy of n bytes (n ≤ 65535, no overlap handling) |
| 05da:47b0 | 16e3:4ad4 | 1d32:690e | `huge_memset(void far *dst, u8 v, u32 n)` | pieces of ≤ 32000 bytes, renormalising per piece |
| 05da:480a | 16e3:4b2e | 1d32:6968 | `huge_cmp(void far *a, void far *b)` | compares the normalised (seg, off): −1 / 0 / 1 |
| 05da:4836 | 16e3:4b5a | 1d32:6994 | `huge_norm_far(void far *p)` | far wrapper of `huge_norm` |

PS/AP addresses checked in the disassembly (the group is at INTRO + 324h in PS, + 215Eh in AP); the port implements all of
them on 32-bit linear addresses (`lin = seg*16 + off`), keeping the "normalised" form wherever a
pointer is stored back into data (bitmap frame records, §7.1).

### 5.3 EMS (LIM 4.0, INT 67h)

Two copies of the same small EMS module: INTRO `17bd` (16-bit code, no callers except detection)
and AP `24e1`/`24e5` (386 build, extended). PS has none. Handles are kept in a 32-entry table.

| INTRO | AP | Name | Contract |
|---|---|---|---|
| 17bd:0000 | 24e1:0000 | `ems_detect()` | `INT 21h/3567h`; compare 8 bytes at `ES:000A` with `"EMMXXXX0"` (INTRO `DS:1F62`, AP `DS:1FE4`); `ems_present` = 1/0 and returned. AP also stores the page-frame segment (`INT 67h/41h` BX) in `ems_frame` `DS:1FE2` |
| 17bd:002a | 24e1:0031 | `ems_free_pages()` | `INT 67h/42h` → BX (unallocated pages) |
| 17bd:003a | 24e5:0000 | `ems_alloc(u32 bytes)` | pages = `(bytes + 3FFFh) >> 14`; find the first zero handle slot (`loopne` over 32; a hit in the **last** slot is treated as "table full" — quirk); `INT 67h/43h`; success: slot = DX (AP also stores pages in `ems_pages[slot]`), return handle; failure: `ems_error` = AH, return 0. Table full: returns AX unchanged (garbage, in practice nonzero) |
| 17bd:0080 | 24e5:004b | `ems_realloc(u16 h, u32 bytes)` | `INT 67h/51h` (reallocate) with the new page count; AP first writes the page count into the slot of h (the last slot if h is not found); success → h, failure → `ems_error`, 0 |
| 17bd:00b2 | 24e5:008d | `ems_free(u16 h)` | h == 0: nothing. Else clear h's slot (not found → the last examined slot is cleared, quirk) and `INT 67h/45h` |
| 17bd:00d9 | 24e5:00b6 | `ems_free_all()` | `ems_free` every slot and zero it. AP registers it with `atexit` in main |
| 17bd:00fa | 24e5:00d7 | `ems_map(u16 h, u16 first)` | `INT 67h/47h` (save the page map for h; error → `ems_error`, return 0L); map logical pages `first..` to physical pages 0.. : INTRO `INT 67h/4Ch` (pages of h) → n = min(pages, 4) pages mapped one by one (`INT 67h/44h`, AL = physical, BX = first + physical), then `INT 67h/41h`; AP n = min(`ems_pages[slot]`, 4) → one `INT 67h/5000h` with the `{logical, physical}` array `DS:206E`; returns `frame:0000` (far) |
| 17bd:013b | 24e5:0139 | `ems_restore_map(u16 h)` | `INT 67h/48h` |
| 17bd:014b | 24e5:0149 | `ems_map_nosave(u16 h)` | like `ems_map(h, 0)` without the save (INTRO/AP: `INT 67h/4Ch`, up to 4 pages with `44h`, `41h`); returns `frame:0000` |

Globals: INTRO `ems_present` `DS:1F6A` u8, `ems_error` `DS:1F6B` u8, `ems_handles` `DS:1F6C`
u16[32]. AP `ems_frame` `DS:1FE2` u16, `ems_present` `DS:1FEC` u8, `ems_error` `DS:1FED` u8,
`ems_pages` `DS:1FEE` u16[32] (indexed like the handles), `ems_handles` `DS:202E` u16[32],
`ems_map_array` `DS:206E` {u16 logical, u16 physical}[4].

At most four 16 KB pages (the whole 64 KB page frame) are visible at a time; every user maps its
object at the start of the frame.

**Use in INTRO**: only `mem_check` (§2.4): EMS must exist and have ≥ 21 free pages, although INTRO
never allocates EMS. **PS**: no EMS at all. **AP** (§2.6): ≥ 19 free pages or assert; tier
`DS:0539` = 3 (19–32 pages; 21 kept for the game) or 4 (≥ 33; 33 kept); the rest
(`ems_spare_pages` `DS:4030`) goes to the Borland overlay manager (`_OvrInitEms(0, 0, n)`,
`36f6:08ed`) as overlay cache.

### 5.4 What AP keeps in EMS

Direct `ems_alloc` users and the pool/bitmap layers below:

| Object | Code | Mechanism |
|---|---|---|
| Sprite-set bitmaps (`BMP:` files loaded by render3d `sprite_set_load2` 243d:004c, and `50c0:0000`) | `bmp_load_ems` 1d32:214e, `bmp_to_ems` 1d32:2050, `bmp_free_ems` 1d32:2170, draw wrappers 1d32:21b6/2204/2258 | one EMS handle per bitmap (§5.4.1) |
| 3D shape data (render3d `bmd_load` 241c:0005 / `shape_ptr` 271b:0007, `shape_set_ptr` 271b:011d), terrain/tile tables (render3d `ts_load_chunk_h` 7039:02a4, `ts_load_table_h`/`ts_free_table` 7074), Huffman tables of the mission recorder (sim_flow `huff_*` 4d15, 6922, 6de4), `4bb7:007f`, `0ab0:000b` | `emm_pool` 1d32:22b2–25a5 (§5.4.2) | sub-allocations in up to 4 pools, one EMS handle per pool |
| Mission-recorder bit-stream cache (sim_flow `bs_open` 48c7:0190, `bs_close`/`bs_abort`, `bs_fill_cache`, `bs_cache_put/get` 63ed) | direct `ems_alloc` / `ems_map` / `ems_restore_map` / `ems_free` | sim_flow |
| `644a:0000` (tier-dependent graphics data, video/cockpit), `6b3d:00ac` (free) | direct calls | owner modules |
| Overlay cache | Borland `_OvrInitEms` | not modelled (the port has no overlays) |

#### 5.4.1 EMS bitmaps (AP only)

A bitmap frame record (§7.1) whose **segment word (+00) is < 50h** holds an EMS handle instead of a
segment (a real DOS segment is never that low); its offset word (+02) is then the byte offset of
the frame inside the handle's memory (not normalised).

```c
bmp_t *bmp_to_ems(bmp_t *bmp) {                          /* 1d32:2050 */
    u32 size = drv_bitmap_size(bmp, &tmp);                /* far call [DS:354E]: bytes of the pixel block */
    if (!ems_present || !(h = ems_alloc(size))) return bmp;   /* stays in DOS memory */
    void far *f = ems_map(h, 0);
    old = MK_FP(bmp[0]->seg, bmp[0]->off);
    huge_memcpy(f, old, (u16)size);                       /* 16-bit count: the block must be < 64 KB */
    base = ((s32)(s16)bmp[0]->seg << 4) | bmp[0]->off;
    for (i = bmp_count(bmp) - 1; i >= 0; i--) {           /* 7229:0598 */
        lin = ((s32)(s16)bmp[i]->seg << 4) | bmp[i]->off;
        bmp[i]->seg = h; bmp[i]->off = (u16)(lin - base);
    }
    ems_restore_map(h); dos_free(old); return bmp;
}
bmp_t *bmp_load_ems(x)  { b = bmp_load_planes(x) /*7229:01aa*/; if (b) bmp_to_ems(b); return b; }  /* 1d32:214e */
void   bmp_free_ems(bmp_t *b) {                          /* 1d32:2170 */
    if (b[0]->seg < 0x50) { ems_free(b[0]->seg); b[0]->seg = FP_SEG(dos_alloc(16, 0L)); }  /* dummy block for bmp_free */
    bmp_free(b);                                          /* 7229:056a */
}
```
Draw wrappers `bmp_draw_ems_*(frame, args…)` 1d32:21b6 → `gfx_sprite_flip` 1d32:3de5 (3 args),
1d32:2204 → `gfx_sprite_scaled` 1d32:49f4 (5 args, no caller), 1d32:2258 →
`gfx_sprite_rotated_ind` 1d32:5e5b (7 args): `h = frame->seg; if (h < 0x50) frame->seg =
FP_SEG(ems_map(h, 0));` call the drawer with the same arguments; `frame->seg = h; if (h < 0x50)
ems_restore_map(h)`.

#### 5.4.2 `emm_pool.c` (AP 1d32:22b2–25a5)

Four pools `emm_pools` `DS:615C` (4 × 8Eh bytes); `emm_cur_pool` `DS:207E` (pool mapped by
`pool_map`, −1 = none); `emm_cur_frame` `DS:6158` (far, frame of that mapping). A block id is
`pool << 8 | slot` (slot 1..32).

| Off | Type | Pool field |
|---|---|---|
| 00 | u16 | EMS handle (0 = none yet) |
| 02 | s32 | capacity in bytes (multiple of 16 KB) |
| 06 | s32 | used bytes (bump pointer) |
| 0A | u32 | slot mask (bit k−1 = slot k in use) |
| 0C + 2k | u16 | slot k: paragraph offset inside the handle (k = 1..32 → +0E..+4C) |
| 4C + 2k | u16 | slot k: size in bytes, rounded up to 16 (+4E..+8C) |

```c
void emm_pools_clear(void)      { memset(emm_pools, 0, 4*0x8E); }           /* 1d32:22b2, no callers */
int  emm_first_free(u32 mask)   { if (mask == 0xFFFFFFFF) return 0;           /* 1d32:22c7 */
                                  for (n = 1; mask & 1; mask >>= 1) n++; return n; }
u16 pool_alloc(int p, u16 size) {                                            /* 1d32:22f4 */
    P = &emm_pools[p]; if (p == emm_cur_pool) emm_cur_pool = -1;
    if (size & 0xF) size = (size + 15) & 0xFFF0;
    s32 need = P->used + size;
    k = emm_first_free(P->mask); if (!k) return 0;
    if (P->capacity < need) {                                                 /* signed */
        if (!P->handle) { if (!(P->handle = ems_alloc(need))) return 0; }
        else if (!ems_realloc(P->handle, need)) return 0;
        P->capacity = ((need + 0x3FFF) / 0x4000) << 14;
    }
    P->off[k] = (u16)(P->used >> 4); P->size[k] = size;
    P->mask |= 1UL << (k-1); P->used += size;
    return p << 8 | k;
}
void pool_free(u16 id) {                                                     /* 1d32:24b6 */
    p = (s16)id >> 8; k = id & 0xFF; P = &emm_pools[p];
    if (p == emm_cur_pool) emm_cur_pool = -1;
    P->mask &= ~(1UL << (k-1));
    if (emm_first_free(P->mask) == k) pool_trim(P);
}
void pool_trim(POOL *P) {                                                    /* 1d32:23f4 */
    i = emm_first_free(P->mask) - 1; bit = 1UL << i;
    do { P->used -= P->size[i+1]; P->size[i+1] = 0; P->off[i+1] = 0; bit >>= 1;
         if (i-- == 0) break; } while (!(P->mask & bit));
    if (P->used == 0) { ems_free(P->handle); P->capacity = 0; P->handle = 0; return; }
    cap = ((P->used + 0x3FFF) / 0x4000) << 14;
    if (P->capacity != cap) { ems_realloc(P->handle, P->used); P->capacity = cap; }
}
void far *pool_map(u16 id) {                     /* 1d32:2525: cached, no map save */
    p = (s16)id >> 8;
    if (p != emm_cur_pool) { emm_cur_pool = p; emm_cur_frame = ems_map_nosave(emm_pools[p].handle); }
    return MK_FP(FP_SEG(emm_cur_frame) + emm_pools[p].off[id & 0xFF], 0);
}
void far *pool_map_save(u16 id) {                /* 1d32:2571: saves the map; pair with pool_unmap */
    f = ems_map(emm_pools[(s16)id >> 8].handle, 0);
    return MK_FP(FP_SEG(f) + emm_pools[(s16)id >> 8].off[id & 0xFF], 0);
}
void pool_unmap(u16 id) { ems_restore_map(emm_pools[(s16)id >> 8].handle); } /* 1d32:25a5 */
```
Quirks (faithful): the pool is a bump allocator —
`pool_trim` only lowers `used` by the freed slot (the lowest free slot) and the free slots directly
below it, so freeing a block that is not the most recent one while later blocks are alive would let
the next allocation overlap them (not checked here whether any caller frees out of order — hand-off,
§10); only the
first 64 KB of a pool are ever mapped (`ems_map` maps ≤ 4 pages), so each pool is effectively
≤ 64 KB; `pool_map` does not save the map and `pool_map_save` does not update `emm_cur_pool`.

### 5.5 AP `mem.c` (24b2) and the near arena (24d3)

`mem.c` wraps allocations with an optional log (`mem_log_on` `DS:1F44`, u16, 0 in the shipped
game; nothing sets it). `4b9e:0000` (called around every allocation) is an empty function
(a disabled heap-check hook).

| AP | Name | Contract |
|---|---|---|
| 24b2:0004 | `mem_calloc(u16 n)` | `n == 0` → 1; `p = safe_malloc(n)`; zero it; return p (near) |
| 24b2:004a | `mem_free_raw(void *p)` | `free(p)` |
| 24b2:0064 | `mem_log_reset()` | `0000:2240("mem.log")` (RTL, remove the log); no callers |
| 24b2:0074 | `mem_new(u16 n, char *tag, char *what, int line)` | `p = mem_calloc(n)`; if `mem_log_on`: `f = my_fopen("mem.log", DS:1F56)`, `fprintf(f, "%10p %6u   new   %4d %15s   %s\n", p, n, line, tag, what)`, `fclose`; return p |
| 24b2:00ca | `mem_delete(void *p, char *tag, char *what, int line)` | `p == 0` → `assert_fail("…\\mem.c", 0x68, what)`; free; optional log line "free" |
| 24b2:013d | `mem_far_new(u32 n, s16 flags)` | `p = dos_alloc(n, (s32)flags)`; if `p && n != 0xFFFFFFFF`: `huge_memset(p, 0, n)` (always zeroed); optional log "fnew"; returns p (or the free-byte count for `n = −1`) |
| 24b2:01c0 | `mem_far_delete(void far *p)` | `if (p) dos_free(p)`; optional log "ffree" |
| 24b2:0000, 24d3:0000 | – | tails (`pop bp; retf`) of the preceding function, not functions |

Near arena (24d3, globals `arena_base` `DS:1FDA`, `arena_size` `DS:1FDC`, `arena_lo` `DS:1FDE`,
`arena_hi` `DS:1FE0`, all u16): a mark/release allocator in one `malloc` block, used by AP
modules for per-mission near data.

| AP | Name | Contract |
|---|---|---|
| 24d3:0002 | `arena_init(u16 n)` | n rounded up to even; `base = malloc(n)` (unchecked); `lo = 0; size = hi = n`. Called once by `sim_init` 4e0d:000b with 2F44h (12 100 bytes) |
| 24d3:002d | `arena_done()` | `if (base) free(base), base = 0; lo = size = 0; hi = FFFFh` (4e0d:035c) |
| 24d3:0059 | `arena_alloc(u16 n)` | n rounded up to even; `p = base + lo; lo += n;` zero n bytes; return p. **No overflow check** against `hi` (45 call sites) |
| 24d3:0092 | `arena_release(void *mark)` | `lo = mark − base` (14e0:0286, 4e0d:03b4, 4e0d:058e, 628f:010e) |
| 24d3:00a1 | `arena_alloc_top(u16 n)` | n even; `hi -= n; return base + hi` (not zeroed); no callers |
| 24d3:00bb | `arena_release_top(void *mark)` | `hi = mark − base`; no callers |
| 24d3:00ca | `arena_reset()` | `lo = 0`; no callers |
| 24d3:00d5 | `arena_reset_top()` | `hi = size`; no callers |

### 5.6 Port notes (memory)

* `mem[]` must be a real-mode address space: code stores `seg:off` values in data (bitmap frame
  records, palette/font slots, pool offsets) and does segment arithmetic on them. Implement
  `dos_alloc` as a paragraph allocator over the conventional region of `mem[]` (e.g. from the end
  of the loaded program image up to 9FFFh:000Fh), returning `seg:0000`, with first-fit and
  merging on free like DOS; `dos_alloc(-1)` returns the largest free block. Offsets returned by
  `dos_alloc` must stay 0; blocks must not move (AP keeps far pointers).
* Report ≥ 33 free EMS pages and a page frame at `E000:0000` (a 64 KB window in `mem[]`).
  Simplest faithful model: EMS handles own host buffers of `pages × 16 KB`; `ems_map` saves the
  current window owner and copies/aliases up to 4 pages into the window, `ems_restore_map`
  restores the previous owner (write back the window first if it was modified). Because every
  user maps its object at the frame start and writes through the window only between map and
  restore (bitmap blits read-only, pools written after `pool_map`), a copy-in/copy-out model is
  correct as long as a write-back happens when another handle is mapped (`pool_map` does not
  restore: keep a "currently mapped handle" and write back on every switch).
* Alternative (simpler, not byte-faithful): give up the EMS window and make `bmp_to_ems` a no-op
  (bitmaps stay in DOS memory; the `< 50h` test then never triggers) and back `emm_pool` with
  plain `mem[]` blocks. This changes which DOS memory is free, which is only observable through
  AP's `mem_far_avail` check. Recommended only if the far heap is large enough (it is: the port
  can make conventional memory as large as 640 KB minus the image).
* The overlay manager (`_OvrInitEms`, `36f6`) is dropped: the port runs `AP_flat.exe`'s code as C.
* `arena_alloc` has no bounds check: keep the 12 100-byte arena and treat overflow as a fatal
  assertion in debug builds.

## 6. Volumes, chunk access, decompression

See `platform_resources.md` (volume.c, the dead RESOURCE.CFG line table, the chunk API, the
RLE/LZW packed-stream decoder, their port notes).

## 7. Picture, palette and font loaders

These build on the resource API of §6 (`platform_resources.md` §6.3–§6.5): `chunk_open(name)`
05da:589e, `chunk_is_open(h)` 5c7a, `chunk_close(h)` 5c4b, `chunk_find(h, "XXX:YYY:", n)` 5934 →
payload file offset or −1, `chunk_size(h)` 5c21, `chunk_save/chunk_restore` 581a/5856 (the "save
state" below), `my_fread` 049d:0411, `my_hread` (huge read) 049d:04f4, packed stream `pk_open`
6b6c / `pk_read` 6f3d / `pk_size` 702d / `pk_close` 6db5. Every loader takes either an open chunk
handle or a file name (`chunk_is_open(x)` decides) and closes what it opened.
Drawing, the driver's own pixel formats and the palette/driver entry points belong to the video
spec; this section gives what is read, how it is stored and which driver entry is called with
what. `drv[n]` = the n-th far pointer of the video driver jump table at INTRO `DS:1938`
(`DS:1938 + 4n`).

Memory helpers used (system library, all three exes; §5.1–§5.2): `dos_alloc(u32 size, u16, u16
flags)` 05da:35e0 / 16e3:3bf4 / 1d32:5a2e → `seg:0000` (0 on failure; flags bit 0 = zero-fill), `dos_free(far)` 05da:3657 /
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
| 00 | u16 | pixel data **segment** (AP: < 50h = EMS handle, §5.4.1) |
| 02 | u16 | pixel data **offset** — the pair is normalised (offset < 16) for the SCN/VQT kinds (`seg += off >> 4; off &= 0Fh`, 0ead:02d7); for the nibble-plane kind the driver fills +00..+05. (Corrected: the first delivery had offset at +00; the code — `bmp_load` 0ead:020e, `bmp_to_scn` 05da:5fbd, `INT 21h/4Ah` with `ES = [+00]` — stores the segment first, i.e. the record is not a Borland far pointer) |
| 04 | i16 | kind: −1 VQT bit stream (decoded when drawn), −2 SCN, −3 SCN with `BMP:SCL:`, −4 raw 8-bit pixels (pre-decoded VQT), other = driver format (nibble planes converted by `drv[14]`/`drv[15]`) |
| 06 | u16 | width |
| 08 | u16 | height |

`bmp_count(bmp)` INTRO 05da:53ef = 0f2c:0010 (PS 168a:04dc / 39a1:0010, AP 7229:0598 /
26d2:000f) counts the entries. PS copies of the plane-loader helpers: `bmp_free_table` 168a:048f,
`bmp_free` 168a:04b1, `amiga_to_nibbles` 168a:04fe. `bmp_draw(frame, …)` 0f2c:0032 (PS 39a1:0032, AP 26d2:0031) dispatches on +04:
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
| INT 9 ISR, BIOS key buffer, 40:17 flags (§3.3) | SDL key events translated to set-1 scan codes and fed through the same ISR logic (so the state table, remaps and BIOS-buffer words are exact) |
| INT 1Ch ramps | run from the timer at 18.2 Hz (every 13th tick), as the BIOS does |
| Port 201h joystick timing loop | SDL joystick axes mapped to the raw count range the calibration expects |
| INT 33h mouse | SDL mouse mapped to the driver's coordinate space |
| INT 21h/48h/49h/4Ah (`dos_alloc`) | an allocator over the conventional-memory part of `mem[]` (addresses matter only as segment:offset values stored in data; keep real-mode segment arithmetic) |
| INT 67h EMS | page frame at `E000:0000` (or the frame the original reports) inside `mem[]`, handles/pages as arrays, map = memcpy or pointer switching (§5.6) |
| INT 2Fh Windows checks | report "no Windows" |
| INT 24h handler (AP) | not needed |
| INT 0 divide handler | `idiv16_retry`/`div16_retry` helpers with the halve-and-retry semantics at every divide that can overflow (§3.6) |
| `INT 19h` reboot (dead code) | not ported |
| `GCD.COM`'s `btest.bin` write test | dropped (or a writability check of the game folder) |

### 9.3 Memory checks

`[0000:0512]` must be set so INTRO (≥ 609 200 bytes) and PS (≥ 590 000) pass; AP's checks use
its own far-heap size (`mem_far_avail` ≥ 140 000) and EMS pages (≥ 19; 33 selects the tier 4
layout). The port reports ≥ 33 free EMS pages so AP runs in the tier-4 (higher detail) mode, and
enough far heap. `override`/`-o` keep working.

### 9.4 Files

Keep the lookup order of `my_fopen` (§6.1) and the loose-file behaviour: `CONTROL.PRF` etc. are read
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
  INTRO loads `ttd.sx` (a `chdir("TTD")` is skipped while volumes are active). Timer users and
  callbacks: §4.7 (INTRO/PS install the timer only inside `snd_init`).
* **sim_flow**: AP `prefs_load` 4e0d:05f5 / `prefs_save` 4e0d:06fd copy CONTROL.PRF +06..+0C to
  far `3974:012D/0159/0185/007D/00A9/00D5` and call `5f2c:004d/0074`, `6b4d:0751`; debug options
  `-s -t -W` (DS:052E/0532/0536/053A/053C/0884); `sim_exit` 4e0d:0bb0 callers 5440:115b (code 1),
  60a9:0a28/0a6c (code 0); `DS:0539` EMS tier read by 5ea5, 6163, 62d2, 644a, 655d, 6b4d.
* **shell_ui / shell_data**: INTRO `intro_play` 038e:0973, `038e:0021` module pick; PS
  `fly_mission` 048e:01a0; `file.c` helpers 1193:01b7/01ff/0115 described in §2.8.
* **symbols.csv**: the `dos_setblock` rows (INTRO 05da:5f97, PS 16e3:5cf1, AP 71db:0000) were
  renamed to `bmp_to_scn` by the platform finisher (the SCN encoder proper, `scn_encode`, is
  05da:62b4 / 16e3:600e / 71db:0322).
* **render3d / sim_world / sim_flow**: every 16-bit `idiv`/`div` that can overflow must use the
  INT 0 halve-and-retry semantics (§3.6, AP 1d32:69cc); 32-bit (`66h`-prefixed) divides must never
  overflow (the handler would corrupt IP). EMS users (§5.4): render3d `bmd_load` 241c:0005,
  `shape_ptr`/`shape_set_ptr` 271b:0007/011d, `ts_*` 7039/7074, sprite sets 243d:004c; sim_flow
  `huff_*` 4d15/6922/6de4 and `bs_*` 48c7/63ed; unnamed `4bb7:007f`, `0ab0:000b`, `644a:0000`,
  `6b3d:00ac`. Whether their `pool_free` order is LIFO (required by `pool_trim`, §5.4.2) is for the
  owners to confirm. AP `DS:0B80` quit request (Ctrl+Esc = 1, Ctrl+Alt+Del = 2) set by the keyboard
  ISR (§3.3.5), read by 60a9/6b4d. AP input `60a9` uses the joystick/keyboard API of §3.
* **video**: AP-only code in 1d32 not specified here: clip-span hooks 1d32:1cac–1e9d (swap driver
  entries `DS:35AA/35AE/35B2/3542` through `DS:1D44–1D50`), rotated-quad corner setup 1d32:1eca
  (caller 0962:0e47), ellipse helper 1d32:6d55; AP `244d:000b/0087` (save/restore the graphics
  state `DS:26C0–26E0` + font) and `244d:0101/0126/0170` (swap driver hooks `DS:3522/3542/3572/
  3586`); INTRO `1739:0802/080d` (callees of 05da:3d01); PS `16e3:065d/0b5e/0c58` (VGA, port
  3CEh); the text-mode/BIOS helpers 05da:5f2e–5f83 and clip rectangle 05da:45d3. Mouse event
  handler VGA save/restore 05da:3b32/3b97 (§3.5). EMS bitmap draw wrappers call
  `gfx_sprite_flip/scaled/rotated_ind` 1d32:3de5/49f4/5e5b with a patched segment (§5.4.1).

## 11. Open questions
* Meaning of CONTROL.PRF option bytes +06/+07/+0A..+0C (owners: sound, sim_flow).
* AP: can `5a75:0c81` install the timer while `4e0d:0168` already did (the 236.69 Hz counter
  `DS:18D2` would then count twice per tick)? (§4.7)
* INTRO/PS install the timer only when a sound driver is initialised; with sound id −1 every
  `timer_add` fails silently and `timer_countdown` never runs (§4.8: the port installs the virtual
  timer unconditionally).
* Windows task switch (§3.8): the request flags are only written with 0 — dead unless a pointer
  write sets them.
* `emm_pool` free order (§5.4.2) and AP's limit of 3 simultaneously open `my_fopen` files
  (§6.1.7) not cross-checked against all callers.
* AP `4b9e:0000` is an empty hook (§5.5); `DS:1EBC` = `vol_exclude` (§6.1.2).
* `bmp_mtx_load` (0f48) only outlined.
