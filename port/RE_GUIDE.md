# Reverse-engineering guide for the SDL3 port

Shared conventions for everyone writing port specs. Targets: the three programs of the CD version 1.2
(`Game/INTRO.EXE`, `Game/PS.EXE`, `Game/AP.EXE`), VGA path only. This is the phase 1 map (first pass,
2026-09-25): names and subsystem boundaries are to be refined by the phase 3 specs.

All three programs are **Borland C++ 3.0 (1991), medium model** (far code, near data: every C
function is `retf`, `char *` is a DS offset; far data only where declared `far`). INTRO and PS are
16-bit 8086/286 code; AP is compiled for the **386** (6 500 instructions with 66h/67h prefixes:
32-bit registers for fixed-point math). **No x87 and no FPU emulator** in any of the three (no
`INT 34h–3Dh`, no ESC opcodes): the port needs no floating point emulation, all math is integer.

## Files

| Path | What |
|---|---|
| `work/AP_flat.exe` | AP.EXE with its VROOMM overlays flattened (`tools/unovl.py`): a plain MZ that Ghidra and the indexer read as one program |
| `port/ap_overlays.csv`, `port/ap_overlay_entries.csv` | Overlay segment map (segment-table index, stub segment → flat code segment, size, entries, relocs) and every stub entry `stub:off` → `code:off` |
| `port/{intro,ps,ap}_functions.json` / `.csv` | Capstone index (`tools/apindex.py`): extent, near/far, callers/callees, DS reads/writes, strings (DS and far), INT numbers with AH (`21.3d`, `67.44`), I/O ports (with the `mov dx,imm` value), far data segments used and the source file named there (`source`), jump tables |
| `port/shared_matches.csv` | Functions matched across the three programs (`tools/apmatch.py`; masked-immediate instruction hash or 6-gram share), with the carried-over name and a hint |
| `port/symbols.csv` | Names: `exe,kind,address,name,type,owner,other_names,notes` (TD3 columns plus `exe` = `intro`/`ps`/`ap`). `owner` = `seed` (hand) or `match:<exe>` (carried over by `apmatch.py`, exact or score ≥ 0.9, mutual best match) |
| `port/decomp/{intro,ps,ap}_ds.c` | Ghidra decompilation of every indexed function with the names of `symbols.csv`; DGROUP globals renamed to DS offsets (`*_DSxxxx`, `DS_xxxx`); `*_globals_xref.txt` = users of each DS global (git-ignored) |
| `work/ovl/*.bin` | Run-time loaded code (`tools/ovlcode.py`): video drivers from `VMCODE.OVL`/`VMCODE2.OVL`, SCI sound drivers + patch banks from `SXCODE.OVL`/`SX.OVL`/`SX1.OVL` |
| `tools/x86dis.py EXE dis SSSS:OOOO LEN` | Ground-truth disassembly (use `work/AP_flat.exe` for AP) |
| `_ghidra/AOTP.gpr` | Ghidra project with `INTRO.EXE`, `PS.EXE`, `AP_flat.exe` |

## Addresses

* Code addresses are **`SSSS:OOOO` with the segment as stored in the file** (load segment 0),
  image offset = SSSS×16 + OOOO. Ghidra loads every image at segment **1000**, so `05da:2374` is
  `FUN_15da_2374` in Ghidra; the `*_ds.c` files have names rewritten back to `FUN_05da_2374`.
* AP addresses are **`AP_flat.exe` addresses**. The resident part is identical to AP.EXE; overlay
  code lives in segments `45CC`–`728E` (placed by `unovl.py` after the resident image). A call that
  the original makes through a stub (`call far 3c59:0020`) is shown as the direct call
  (`call far 45cc:059e`); `port/ap_overlay_entries.csv` gives both, and stub entries are `JMP FAR`
  thunks in the flat image, so pointers kept in data still work.
* Borland medium model links **one code segment per module**: the relocated segment values are the
  module boundaries (hundreds of small segments; the RTL modules of Borland's `_TEXT` are all in
  segment `0000`).
* **DGROUP** (from the c0 startup `mov dx,DGROUP`): INTRO **`17E0`**, PS **`4D08`**, AP **`3EA4`**.
  `DS:xxxx` = image DGROUP×16 + xxxx. C code always runs with DS = DGROUP; ISRs and the loaded
  drivers set DS themselves (`sets_ds` in the index).
* Far data segments (between the code and DGROUP) hold per-module data, notably the `__FILE__`
  strings of asserts (`c:\a\d\s\c\cockpit.c`, `shell\file.c`): the index uses them to tag functions
  with their source file (`source`).
* Capstone prints `cbw`/`cwd` as `cwde`/`cdq` in 16-bit mode; read them as the 16-bit forms.

## AP.EXE overlays (Borland VROOMM), verified against the bytes

* MZ load image ends at file 0x49AC0 (header 0x3E00, 3433 relocations). There follows
  `FBOV` + u32 size (0x2EF00 bytes of overlay data after this 16-byte header) + u32 **file offset**
  of the segment table (0x3F310, i.e. image 0x3B510, inside the resident data) + u32 count (525).
* Segment table, 8 bytes per entry: `u16 seg, u16 maxoff, u16 flags, u16 minoff`. Flags: 1 =
  resident code (entries 0–226, 384), 3 = overlay (129 entries, `seg` = its stub), 0 = data (far data
  `381C`–`3B37`, DGROUP `3EA4`, stack `45C4`), 4 = the segments `3B48`… and `4250`–`45C3` (overlay
  manager data).
* Stub segment (resident, paragraph aligned, `3C59`–`3EA0`): `+00 CD 3F` (INT 3Fh), `+02 u16
  memswap` (0), `+04 u32` offset of the overlay code relative to the byte after the FBOV header,
  `+08 u16` code size, `+0A u16` relocation bytes, `+0C u16` entry count, `+0E u16 prevstub` (0),
  `+10..1F` work area (0). Entries from `+20`, 5 bytes each: `CD 3F <u16 offset in the overlay> 00`
  (confirmed for all 890 entries). `unovl.py` rewrites each into `EA <off> <seg>` (JMP FAR, same size).
* Overlay relocations (u16 code offsets after the code) hold **segment-table index × 8** in the
  relocated word; the loader substitutes the segment of that entry (an overlay entry resolves to its
  stub, so calls between overlays go through stubs). 4285 relocations: 2602 to resident code, 1464 to
  stubs, 219 to data. `unovl.py` retargets 1859 `call far stub:entry` to the overlay code directly.
* The overlay manager itself (INT 3Fh handler, EMS/XMS swap: INT 67h/40h–48h, INT 15h/87h–88h,
  INT 2Fh/43h) is Borland RTL code in segment `36F6`; the port does not need it.

## Run-time loaded code (not in the EXEs)

* **Video drivers**: `VMCODE.OVL` (SHELL1.DYN) = `OVL:{VGA: EGA: MCG: CGA: TAN: HEG: EVG: EVA:}`,
  `VMCODE2.OVL` (SIM2.DYN) = the same VGA driver for AP. `gfx_init` (INTRO `05da:5c93`) detects the
  adapter (`05da:5de1`: INT 10h/1Ah, 12h, CRTC probe), loads the chunk (`gfx_load_driver`
  `05da:4933`), calls its entry (offset 0) with a pointer to shared variables, and copies the returned
  **50-entry jump table** (driver `cs:00DA`) to `DS:1938` as far pointers. All drawing goes through
  that table. `work/ovl/VMCODE_OVL_VGA.bin` = 9424 bytes of real-mode code.
* **VGA320 = unchained 320×200×256 ("mode Y")**: the VGA driver sets mode 13h, then clears Chain-4
  (SC 04h), odd/even (GC 06h), CRTC 14h dword mode and sets CRTC 17h byte mode; clears the 64 KB;
  row table of 200 × 80 bytes; **three pages at A000h, A400h, A800h** (16 KB each). The EXEs only
  program the VGA directly for fades/effects (INTRO `103d:0933`, `09f8`: 3C0h/3D4h/3DAh) and the DAC
  (AP `0000`: 3C7h–3C9h). The port can render linear 320×200 and ignore planes, as long as page
  flipping and plane-dependent effects are modelled at the driver interface (50 entries).
* **Sound drivers**: `SXCODE.OVL` (SHELL1), `SX.OVL` (SIM2), `SX1.OVL` (M1SIM) = `SSM:{M32: NLD: ADL:
  TAN: PS1: STD:}` = Sierra **SCI0-style drivers** (`E9 xx xx`, 87654321h, "dude"/"stddrv"/"audjoy"),
  plus `001:`/`003:`/`101:` patch banks (MT-32 "ACES OF THE PACIFIC" SysEx, AdLib, …). The driver
  number maps to a tag through `DS:1EFA` (INTRO): 0 STD, 1 TAN, 2 ADL, 3 M32, 4 SBL, 5 PS1, 6 TAN,
  7 PRO, 8 NLD; `sys_init` maps 4 (SBL) and 7 (PRO) to 2 = AdLib. The loose `ADL.DRV`, `MT32.DRV`,
  `STD.DRV`, `IBMPS1.DRV` differ from the embedded ones; no code path of INTRO/PS/AP was found that
  opens them (`.DRV` only appears in `config_write` `038e:04d6`, which writes `soundDrv = <name>.DRV`
  to `resource.cfg`); probably for the installer's sound test. To confirm in the sound spec.

## Program flow (first pass)

`AOTPCD.BAT` runs `gcd -nC:\DYNAMIX\AOTP` (work directory for `btest.bin`, `SIM.IN`, `SIM.OUT`).

**GCD.COM** (965 bytes): shrinks itself, checks the work directory is writeable (creates
`<dir>\btest.bin`, 5 bytes), stores the largest free DOS block at `0000:0512` and the marker
**29Ah at `0000:0510`**, then EXECs `INTRO.EXE` with the same command tail and loops on the child's
exit code: **0 = quit to DOS, 1 = `INTRO.EXE`, 2 = `PS.EXE`, 3 = `AP.EXE`** ("Unable to chain" on EXEC
failure). The port replaces this with a loop in `main` (PLAN.md).

The word at **`0000:0510`** is the hand-off marker between programs: 29Ah = started by GCD (or
restarted), 3E7h (999) = returning from the simulator; PS and AP clear it after reading.

| Program | main | Flow |
|---|---|---|
| INTRO | `038e:0ac1` | options (`-n<dir>`, `override` skips the memory check, `-s<n>` sound driver…), memory check (610 000 bytes conventional + 344 064 EMS), `resource.cfg` / `control.prf`, `sys_init` `038e:080d` (video, sound `ttd.sx`, keyboard, mouse), the intro TTM scripts `intace1`–`4` (`1125` TTM player), `exit(2)` → PS |
| PS | `048e:0259` | `-n<dir>` work dir; `-p?` debug options (`-pi` skip intro, `-ps` as if back from the sim, `-ph` "hivga" driver…); marker 29Ah/3E7h (3E7h → debrief path, reads `SIM.OUT` 36 bytes, `1193:09fe`); shell menus; `shell_exit` `227c:0072`: to fly, writes **`SIM.IN` (13 bytes, `DS:4B86`)**, sets the marker and **`exit(3)`** → AP; quit = `exit(0)` |
| AP | `50c8:0008` | `-n<dir>`; CPU check (`24e1`), "At least 112K EMS memory required"; exits 1 unless the marker is 29Ah or 3E7h, clears it; debug switches `-s -S -x -t -W -o -w -d`; reads `sim.in`; `sim_init` `4e0d:0000`; mission; results → `SIM.OUT` (`5254:0859`, `results.c`); **`sim_exit(code)` `4e0d:0bb0`** sets 3E7h and exits: **2 = back to PS** (normal), 1 = INTRO (from `5440:0aee`), 0 = DOS (VCR/demo path `60a9:0a04`). `1d32:6a91` reboots with INT 19h when called with 1 |

## Platform (shared library)

The Dynamix system library is linked into all three (INTRO `05da` / PS `16e3` / AP `1d32`, 24–32 KB,
~170 functions, same code; see `shared_matches.csv`):

* **Timer**: `timer_install(13)` (`05da:2374`): PIT channel 0 divisor 65535/13 = 5041 →
  **236.7 Hz (13 × 18.2)**; INT 8 handler `05da:241a` runs up to N far callbacks (bit mask `DS:15C7`,
  per-callback countdown/reload) and chains the BIOS INT 8 every 13th tick. All three programs call it
  with 13 (the sound driver service is one callback). `timer_restore` `05da:23e1`.
* **Keyboard**: own INT 9 handler `05da:0117` (port 60h/61h, key state table), INT 1Ch hook
  `05da:02fd` (18.2 Hz: held keys / joystick-axis ramps), 101-key check via INT 15h;
  `kbd_install` `05da:0014`, `kbd_restore` `05da:00d9`.
* **Mouse** INT 33h (`05da:3a40`… functions 0, 4, 7, 8, 0Ch); **joystick** port 201h timing loop
  (`05da:3667`, buttons `05da:390d`).
* **Memory**: DOS blocks (INT 21h/48h/49h/4Ah, `05da:35e0`/`3657`); **EMS** INT 67h (INTRO `17bd`,
  AP `24e1`/`24e5` + `emm_pool.c` pool; PS uses none): functions 41h page frame, 42h free pages,
  43h alloc, 44h map, 45h free, 47h/48h save/restore map, 4Ch, 50h, 51h realloc. AP needs ≥ 112 KB,
  INTRO checks 344 064 bytes. Port: model the page frame as memory and the handles as arrays.
* **Windows** detection INT 2Fh/1600h, critical sections 1681h/1682h (`0db2`).
* **Volumes** (`volume.c`: `049d` in INTRO, in `0000` for PS/AP): `vol_init` scans `*.DYN`,
  `vol_fopen` (`my_fopen`) serves a name from a volume or from disk ("[not in volume]").
* Resource loaders: `PAL:`, `BMP:{INF,BIN,VGA,VQT,RLE,MTX…}`, `SCR:{DIM,BIN,VGA}` (`05da:070b`,
  `4ee4`, `5001`, `54ae`, `0ead`, `0f35`, `0f48`), decompression candidates `0e2c`, `0dc5`.
* **Sound** (SCI-style player, INTRO `1373` / PS `430a` / AP `3060`, plus the small modules
  `1593`–`172c`): `snd_init` `1593:0004` loads the driver chunk (`16ac:000b`), calls it with
  **BP = function number** (`1373:0398`: BP=0 → info, returns CL/CH/AH), installs the timer, registers
  the service. Music/effects resources: `SND:INF:`/`DAT:` (`1659:000b`), `*.SX`, `SIMSNDS1.SNG`.
* **TTM** animation script player (`PAG:`/`TT3:`): INTRO `1125`, PS `3b02`, AP `24fc`; `ts_*.c`
  (`c:\work\ts2\s\`) graphics helpers.

## Segment map (first pass)

**INTRO** (71 code segments, 638 functions, 90 % of code bytes covered): `0000` Borland RTL + c0
(193 functions); `038e` main.c (main, config, sys_init); `0460`/`0491` intro sequence/mouse glue;
`049d` volume.c; `05bb` fatal_error/assert; `05cb` resource-file text; **`05da` system library**;
`0db2` Windows; `0dc5`–`0f9e` decompression and bitmap/screen loaders; `0fca`–`11d2` palette, fades
(`103d` VGA registers), TTM player; **`1373` sound player**; `157f`–`172c` sound API modules;
`1739` misc; **`17bd` EMS**.

**PS** (184 code segments, 1974 functions, 96 %): `0000` RTL + volume.c; `048e` main; `0542`–`147e`
`shell\*.c` (simend, flyhist, missdebr, fltmap, fltdeck, squadinf, best, campset, once, dogace, bigmap,
view, pilot, campsel, flymiss2, **file.c `1193`** (SIM.IN/SIM.OUT), simshell `125a`, decision,
custmiss); **`16e3` system library**; `1ed0`–`22ce` `sys\*.c` (farquick, snario, historic, extens,
shiptext, planetxt, threed, queue, ranks, helper); `227c` shell_exit; `2322`–`2ab3` `emd\*.c` (wdata,
wdutil, strp, ace, squad, text, emd, list, aircraft, medals, flight, date, campaign, missinfo,
wldfgen, convoy, ship, form, station, ordnance); `2b4f`–`307d` `alert\*.c` (dialogs, menus,
listbox); `3164` `miss\script.c` (15 KB) + tables + mission types `s_*.c`; `383a`–`3baf` bitmap/TTM
(as INTRO); **`430a` sound**; `4516`–`46c3` sound API; `4708`–`4960` `ts_*.c`.

**AP** (400 code segments incl. 129 overlays and 129 stub segments, 2827 functions, 96 %): resident `0000` RTL + volume.c
+ DAC; `0688`–`1c30` sim code (bombs, ces, g_attack `0deb`, message, misctbl, rockets, torps, big
unnamed modules `0b01` 12 KB, `12fd`, `1899`, `1c30` views); **`1d32` system library**; `2466`–`24e5`
mem.c / EMS; `24fc` TTM; `277a` (22 KB, "DEMO"); `2f0e` ts_draw; **`3060` sound**; `3368`–`36e8`
macros, pool, init, obwload, …; `36f6` Borland overlay manager; `3c59`–`3ea0` VROOMM stubs (thunks).
Overlays `45cc`–`728e` (see `ap_overlays.csv`): acedata, boxlist, bstream, damage, control,
findfile, gunlist, init `4e0d`, **main `50c8`**, modules, ovl, paltrick, results `5254`, simshell,
sky, slider, snario `56ac`, stars, stdalert, sx_sim `5a75`, the VCR (film) code `5b93`–`618d`
(vcr*.c), wdata, alrtlib2, cockpit `644a`, fltmap `6cdc`, rlsmgfx…

Source directories named in the binaries: `d:\aces1946\code\shell\intro\`, `…\sim\s\c\` and
`c:\a\d\s\c\` (sim), `shell\`, `sys\`, `emd\`, `alert\`, `miss\` (PS), `c:\work\ts2\s\` (TTM/"ts"
library), `mm\emm_pool.c`.

## Code reached only through pointers

`apindex.py` seeds far code pointers built from a relocated segment (`mov/push` pairs, `mov
[m],off/[m+2],seg`, far pointer tables in data), prologues (`push bp; mov bp,sp` / `enter`), ISRs
that load DGROUP, stub thunks and Borland switch tables (index form after `cmp bx,N`, and the value
search form `mov cx,N / mov bx,tbl / … jmp cs:[bx+2N]`). Runs of relocations 8 bytes apart (the
VROOMM segment table) are not taken as pointers. Remaining gaps are mostly RTL printf/scanf internals
and data in code segments (`apindex.py EXE out gaps` lists them). Ghidra keeps some near helpers
inside their caller: the decompiles have 634/638 (INTRO), 1971/1974 (PS) and 2700/2827 (AP) of the
indexed functions as separate blocks; use `x86dis.py` for the others.

## Regenerating

```
python tools/unovl.py Game/AP.EXE work/AP_flat.exe
python tools/apindex.py Game/INTRO.EXE port/intro
python tools/apindex.py Game/PS.EXE port/ps
python tools/apindex.py work/AP_flat.exe port/ap
python tools/apmatch.py            # port/shared_matches.csv, carries names into port/symbols.csv
python tools/ovlcode.py            # work/ovl/*.bin
python tools/ghidra_syms.py        # work/<exe>_symbols_ghidra.txt
analyzeHeadless _ghidra AOTP -import Game/INTRO.EXE -overwrite -scriptPath tools/ghidra \
    -preScript SetDS.java 17E0 -postScript FixNearFlows.java 17E0
analyzeHeadless _ghidra AOTP -import Game/PS.EXE ... SetDS.java 4D08 ... FixNearFlows.java 4D08
analyzeHeadless _ghidra AOTP -import work/AP_flat.exe ... SetDS.java 3EA4 45CC ... FixNearFlows.java 3EA4 45CC
analyzeHeadless _ghidra AOTP -process AP_flat.exe -noanalysis -scriptPath tools/ghidra \
    -postScript ApplySymbols.java work/ap_symbols_ghidra.txt 3EA4 \
    -postScript DecompileAll.java work/ap_starts.txt port/decomp/ap.c 3EA4 120 only 45CC
python tools/ghidra/postprocess.py port/decomp/ap.c 3EA4 45CC
```

(same for INTRO/PS without the overlay segment argument; `tools/ghidra/aotp_import.sh` and
`tools/ghidra/aotp_decompile.sh` run all of it from Git Bash). The extra overlay segment argument of
`SetDS`/`FixNearFlows`/`DecompileAll`/`postprocess.py` makes the code above DGROUP run with DS =
DGROUP and keeps it from being renamed as DGROUP data. `JAVA_HOME` = `_tools/jdk-21.0.12.1+1`,
`analyzeHeadless` in `_tools/ghidra_12.1.3_PUBLIC/support/`.

## Open questions

* The 50 entries of the video driver table (names, arguments) and how page flipping / the three
  pages are used by the shell and the 3D view; what `-ph` "hivga" selects (HEG:/EVG:?).
* The sound driver function numbers beyond 0 and the timer callback that services the driver;
  whether the loose `*.DRV` files are ever used; tags `NLD`, `SBL`, `PRO`.
* Content of `SIM.IN` (13 bytes) and `SIM.OUT` (36 bytes) field by field (PS `1193:093e`,
  `1193:09fe`; AP `5c5f:0000`, `5254:0859`).
* Which AP segments are the 3D renderer and the flight model (large unnamed modules `0b01`, `12fd`,
  `1899`, `277a`, `3060` vs sound, `655d`, `583c`); the AP exit code 1 path (`5440:0aee`).
* The in-code LZW/RLE decompressor (candidates INTRO `0e2c`, `0dc5`).
* `0000:0512` (free memory stored by GCD): who reads it.
