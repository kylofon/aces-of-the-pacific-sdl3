# Porting rules — Aces of the Pacific → SDL3

Faithful reimplementation of the three programs of the CD version 1.2, **INTRO.EXE**, **PS.EXE** (the
shell) and **AP.EXE** (the simulator), in one executable (`aotp`), VGA with AdLib sound (PLAN.md
decisions 1, 2, 7). Behaviour, integer arithmetic and visible quirks must match the original; the only
intended change of feel is the sim frame pacing default (PLAN.md decision 4). The executables and all
data are read from the game folder at run time: the port never ships game data.

Specs: `../port/spec/*.md` (read `../port/RE_GUIDE.md` first; `platform.md` §9 is the design basis of
this skeleton). Formats: `../FORMATS.md`, `../port/formats/*.md`. Symbols: `../port/symbols.csv` →
generated `src/symbols_{intro,ps,ap}.h` and `src/symbols_layout.{h,c}` (`python tools/gen_symbols.py`
from the repository root, after `python tools/merge_symbols.py`). Ground truth when a spec is unclear:
`python tools/x86dis.py Game/PS.EXE dis SSSS:OOOO LEN` (AP: `work/AP_flat.exe`). Reference decoders:
`tools/dyn*.py` (volumes, chunks, images, shapes, worlds, TTM), `tools/aotpsnd.py` (SCI player + AdLib
driver, DRO regression renders in `work/sound/`).

## Architecture

```
main.c            GCD.COM's chain loop, command line                                   (coordinator)
prog.h/.c         the three programs: EXEC (load, PSP, environment, MCBs), Borland c0 (DGROUP,
                  BSS, stack, argv), exit() = atexit chain + longjmp back to the loop       (coordinator)
mem.h/.c          real-mode address space mem[], accessors, loader (MZ + VROOMM flattening),
                  DOS memory arena (INT 21h 48h/49h/4Ah), division helpers, DGROUP stack   (coordinator)
ems.h/.c          INT 67h model: handles, 64 KB page frame at E000 in mem[]                  (coordinator)
codeptr.h/.c      code pointers stored in data -> C functions                               (coordinator)
host.h/.c         SDL3: window/present, 236.69 Hz tick, XT key bytes, mouse, gamepad, OPL2 +
                  sound service on the audio thread, files, headless developer aids         (coordinator)
symbols_*.h/.c    generated                                                                 (tools)
platform/vga.*    VGA model: 256 KB planar memory as linear pages, CRTC start/offset, pel
                  panning, DAC, 70 Hz retrace                                               (coordinator)
platform/*        platform.md: timer (INT 8), keyboard (INT 9 + BIOS), INT 33h model, game port,
                  later: the rest of the system library, volumes, chunks, loaders, RTL       (platform)
game/placeholder.c  PHASE 4 ONLY: stand-in mains (test pattern, Esc chains to the next program)
```

Only `host.c`, `mem.c`, `ems.c` and `main.c` include SDL. Everything else talks to the host through
`host.h`.

### Module layout for phase 5

One directory per spec module; each module declares its API in its own header (`<dir>/<dir>.h`):

| Directory | Spec | Program(s) |
|---|---|---|
| `src/platform/` | `platform.md`, `platform_resources.md` | shared library (all three) + Borland RTL (`rtl_*.c`) + INTRO/PS/AP `main` start-up parts |
| `src/video/` | `video*.md` | shared library graphics, the VGA driver entries in C, palettes, TTM player, PS `ts_*` |
| `src/sound/` | `sound.md` | SCI player + AdLib driver model (shared), per-program sound API, AP `sx_sim` |
| `src/shell_ui/` | `shell_ui*.md` | INTRO flow, PS screens, dialogs/menus |
| `src/shell_data/` | `shell_data*.md` | PS `emd\*`, `sys\*`, `miss\*`, `file.c` |
| `src/sim_flow/` | `sim_flow*.md` | AP main/init, flight loop, cockpit/HUD, map, VCR, results |
| `src/sim_world/` | `sim_world*.md` | AP flight model, AI, weapons, damage |
| `src/render3d/` | `render3d*.md` | AP 3Space renderer (PS copies of `277a` live in video/`ts`) |

`game/placeholder.c` is deleted when the ported mains exist; `prog.c`'s table then points at them.

## The three programs in one process (`prog.c`)

* `main` = GCD.COM: `0000:0512` = 9C00h (free paragraphs, passes the INTRO/PS memory checks),
  `0000:0510` = 29Ah **once**, then `code = prog_run(code)` while `code` is 1 (INTRO), 2 (PS) or 3 (AP).
* `prog_run` does what DOS EXEC + Borland c0 do: clears the program area, loads the image at
  `LOAD_SEG` (0200h; PSP at 01F0h, environment before it), applies the relocations, builds the MCB
  chain, PSP (tail `" -nC:\DYNAMIX\AOTP\"` = GCD's child tail), environment, and the c0 state at the
  same DS offsets as the original (`_version` DS:0092, `_psp` 0090, `_envseg` 008C, top 00A8/00A0/00A4,
  BSS zeroed, `_stklen` ≥ 200h, SP at the top of the 64 KB DGROUP, argv strings on that stack,
  `argc/argv` at DS:0084/0086), then calls the program's `main`.
* **The DOS work directory is the DOS path `C:\DYNAMIX\AOTP`** (`DOS_WORK_DIR`): the programs build
  `"<work_dir>SIM.IN"` etc. into ~80-byte DGROUP buffers; the file layer (phase 5, platform) maps that
  prefix and relative names to the game folder (`host_game_path`, case-insensitive).
* `exit(n)` inside a program = `prog_exit(n)`: runs the `atexit` functions (reverse order), then
  `longjmp`s to `prog_run`, which returns `n`. PORT: vectors left hooked are unhooked by the loop.
* What survives a switch, as in the original: low memory (the marker), EMS allocations, the VGA
  state (mode, video memory, CRTC start, DAC: the next program starts on the last picture) and the
  files in the game folder. Everything else is reloaded.
* `--start`, `--intro-args/--ps-args/--ap-args` (e.g. `--ap-args nlkle` = AP debug mode) for testing.

## Memory model (`mem.h`)

* The original's data stays **in `mem[]` at its original address**. File address `SSSS:OOOO` is
  segment `SEG(0xSSSS)` (= `LOAD_SEG + SSSS`); the current program's DGROUP is `cur_dgroup`. Program
  code uses its own symbols with the DGROUP accessors: `DSW(PS_DS_quit_flag) = 1`. For an offset
  without a name write the raw offset with a comment: `DSW(0x00C1) /* quit_flag */`. Never shadow
  game state in C variables that outlive a function (host-side caches are fine).
* **Pointers follow the Borland medium model**: near data pointer = DGROUP offset (`u16 name_ds`); far
  pointer = `FarPtr {off, seg}` by value; huge arithmetic on `far_lin()` / `far_norm()` (platform.md
  §5.2). Code pointers: see below.
* **Locals whose address the original passes on** (sprintf buffers, structs given to library calls)
  go on the emulated DGROUP stack: `u16 m = stk_mark(); u16 buf = stk_alloc(80); … stk_release(m);`.
  The near heap (`malloc`, AP `safe_malloc`, `arena_*`) lives between the end of BSS and the stack;
  TODO(phase 5, platform/RTL): port Borland's near-heap allocator so block addresses match.
* **Far memory**: `dos_alloc` = `dos_mem_alloc` (INT 21h 48h/49h/4Ah on a real MCB chain, DOS 5
  first fit, blocks never move, offset 0). The arena starts above the program's 64 KB DGROUP.
* **AP**: code addresses are `work/AP_flat.exe` addresses (the loader flattens the VROOMM overlays
  exactly like `tools/unovl.py`; `aotp --check ../work/AP_flat.exe` compares byte for byte). The
  overlay code segments (45CC–728E) overlap AP's own 64 KB DGROUP (3EA4–4EA3), so they are kept in a
  read-only store: read code bytes (switch tables, CS data, thunks) with `code_rd8/16`. Overlay code is
  never written (VROOMM discards and reloads it). The overlay manager is not ported.
* **EMS** (`ems.h`): INT 67h functions as C calls returning AH; page frame E000:0000 in `mem[]`;
  copy-in/copy-out mapping; 256 pages (AP tier 4).
* **Video memory is not in `mem[]`**: `platform/vga.h` (below). A far pointer to A000–AFFF in game data
  must go through `vga_page()`.
* Fixed-width arithmetic: `u8/s8/u16/s16/u32/s32` exactly as the original register widths; cast at every
  step where the original truncates. Signed right shift = `(s16)x >> n`. Emulate `adc/sbb/rcl/rcr`
  carries explicitly. Borland long helpers (`LXMUL@`, `LDIV@`, `LUDIV@`, `LMOD@`) are C operators on
  `s32/u32` (truncating toward zero). AP's 386 code (66h prefixes): 32-bit C arithmetic.
* **Division** (platform.md §3.6): every 16- or 8-bit `DIV`/`IDIV` that can overflow uses
  `idiv16_retry` / `div16_retry` / `idiv8_retry` / `div8_retry` (the INT 0 handler's halve-and-retry
  semantics; render3d depends on it). 386 divisions use `idiv32_386` / `div32_386` (must not overflow).
  A true division by zero hung the original: `div_unreachable` (fatal in Debug, 0 in Release).
* Keep the original's bugs and quirks the specs mark as faithful (the INTRO/PS "one key pending" drop,
  `divzero_restore` not restoring, `emm_pool`'s bump allocator …), but never read or write outside
  `mem[]` (or the VGA/EMS buffers).

## Shared library: `prog_layout` (platform.md §9.1, **option 1**)

The Dynamix system library and the Borland RTL are the same code in the three programs, with the
globals at different DS offsets. **Choice: option 1** — library code is written once and addresses
its globals through the current program's layout table; the globals themselves stay in `mem[]` at each
program's own DS offsets:

```c
LW(G_timer_countdown) = 13 * n;              /* = DSW(prog_layout->ds[G_timer_countdown]) */
u8 *ks = LP(G_key_state);                    /* pointer into the current DGROUP */
codeptr_far_shared(F_timer_isr);             /* the current program's address of a function */
```

`symbols_layout.h` (generated) has an id `G_<name>` for every DGROUP global whose name appears in at
least two programs of `symbols.csv` (277) and `F_<name>` for every shared function name (679);
`layout_intro/ps/ap` hold the offsets/addresses (`LAYOUT_ABSENT_*` where a program lacks one; using it
is fatal). `prog_run` sets `prog_layout`.

Why not option 2 (library state in a C struct, mirroring selected globals into `mem[]`): game code in
all three programs reads and writes library globals directly (the driver's shared block `drv[]` —
colours, clip, page segments —, `timer_countdown`, key state, `control_prf`, font and palette slots),
and data structures hold near/far pointers into them. A mirror would need an exhaustive list of those
accesses and a synchronisation point for each; with option 1 there is one copy, at the original
address, and the byte layout (e.g. `drv[]` offsets, `timer_cnt` records) is exact by construction.
Rule: **library code uses `G_`/`F_` only; program code uses its own `<EXE>_DS_`/`<EXE>_FN_`**. A global
that exists in one program only is used with that program's symbol even inside library files (e.g. AP's
key queue `AP_DS_kbq_*` in `platform/kbd.c`). If a shared name is missing in `symbols.csv` for one
program, add the row and regenerate rather than hard-coding the offset.

Where the library code itself differs between programs (AP's keyboard ISR tail, `mouse_set_range`'s
`max`), branch on `prog_current_id()` inside the one function and cite both addresses.

## Symbols and naming

* `#include "symbols_ps.h"` etc. in files of that program; library files include only
  `symbols_layout.h` (via `mem.h`) plus the per-program headers they need for program-only globals.
* One C function per original function, named as in `symbols.csv`, with a leading comment giving the
  address(es) and the spec section: `/* 16e3:2a2e timer_isr — platform.md §4.5 */`; shared library
  functions list INTRO / PS / AP. Where the same name has different code per program (not one shared
  function), prefix: `ps_intro_play`, `ap_…`.
* Assembly routines with register arguments become C functions with explicit parameters/returns named
  after the registers they model (`joy_read_axes(u8 bl, u16 *si, u16 *di)`).

## Code pointers (`codeptr.h`)

Far code pointers in data (timer callbacks `timer_fn[16]`, TTM opcode/dialog tables, exit hooks, the
driver jump table DS:1938/3174/351A) keep their stored relocated values in `mem[]`; `codeptr_lookup`
maps them to C. Register program functions with `codeptr_register(PROG_PS, PS_FN_x, fn)`, shared ones
with `codeptr_register_shared(F_x, fn)`. AP pointers to VROOMM stub entries are followed through the
`JMP FAR` thunk automatically. Run-time code (the video driver, which the port's `gfx_init` "loads" into
a DOS block it allocates like the original) is registered with `codeptr_register_abs`. Functions with
other signatures are cast to `CodeFn` and back.

## Timing (`host.h`)

* The host runs the PIT tick at exactly 236.69 Hz (1193182 / 5041) from `host_pump()`. While a
  program's `timer_install(13)` is in effect, each tick runs the ported `timer_isr` (saturating
  `timer_countdown`, the callback table in slot order with the original count/reload semantics, BIOS
  tick every 13th); otherwise only the BIOS tick (40:6C) at 18.2 Hz. PORT: the timer is only installed
  by the programs (INTRO/PS: inside `snd_init`), as in the original.
* **Every busy-wait loop of the original must call `host_pump()` once per iteration** (tick waits, key
  polls). Port 3DAh polls become `vga_wait_vretrace_start/active/end()`.
* **Sound**: the SCI player service (a `timer_add(service, 4)` client in the original) runs on the
  audio thread every 20164 PIT clocks of produced audio (59.17 Hz, sound.md §13):
  `host_set_sound_service(player_service)`. The ported `snd_init` still calls `timer_add` with the
  service's far pointer (so slots and handles match); its codeptr registration is a no-op
  `/* PORT: runs on the audio thread */`. Game-side sound API calls take `host_audio_lock()` where the
  original did `cli`.
* **Sim frame pacing (PLAN.md decision 4, sim_flow.md §4.1)**: the flight loop's minimum of 8 ticks
  becomes `host_frame_ticks()` (default 16, `--frame-ticks`); `ticks = elapsed & ~3` and the dt clamp
  stay as in the original. Film playback takes the tick count from the film, never from the clock.

## Video (`platform/vga.h`)

* 256 KB planar memory stored as `vram[addr * 4 + plane]`, which makes every 16 KB page a linear
  320×200 buffer: `vga_page(0xA400)[y * 320 + x]` (video.md §1.3). Latch copies = `vga_latch_copy`.
* The screen is composed like the hardware: CRTC start (0Ch/0Dh), offset (13h), attribute pel panning
  (13h), DAC; so `drv_flip` is "swap `drv[12]/drv[14]`, write the start address" and the TTM 3103 scroll
  canvas works unchanged. Presented at the host's vsync; `AOTP_SNAPSHOT_DIR` saves frames.
* INT 10h: `vga_set_mode(0x13)` + `vga_set_unchained()` (driver init); AP keeps PS's mode/memory
  (`drv[AB4] = 0`), programs do not reset the mode on exit.

## Input

* Keyboard: SDL events → XT set-1 bytes (E0/E1 prefixes included) → one IRQ1 each → the ported
  `kbd_isr` (INTRO/PS: BIOS buffer 40:1E..3D with 40:17 flags in `mem[]`; AP: its private queue) while
  hooked, else a minimal BIOS INT 9. Ctrl+Esc calls INTRO `05bb:0006` / PS `227c:0034` through codeptr.
* Mouse: `platform/int33.c` (INT 33h fn 0/1/2/3/4/7/8/0Ch/0Fh); host pixels × 4 clamped to the ranges;
  the event handler (fn 0Ch) is called through codeptr as `Int33Handler(ax, bx, cx, dx)`.
* Joystick: `platform/gameport.c`, first gamepad: left stick = A, right stick = B, synthetic counts
  (centre 200, 0..399; 400 = absent), buttons south/east/west/north = A1/A2/B1/B2.

## Dropped / replaced (mark with `/* PORT: ... */`)

* PIT/PIC/port 61h programming, interrupt vectors (kept as hook flags), Tandy paths, INT 1Ch ramps,
  Windows helpers (`win_detect` → 0), INT 24h handler, `INT 19h`, the VROOMM overlay manager
  (`_OvrInitEms` is a no-op), the joystick loop-speed calibration, GCD's `btest.bin` test.
* Sound devices other than AdLib (MT-32, PC speaker, PS/1): the AdLib driver model runs whatever the
  configuration says (sound.md §13, PLAN.md TODO).
* Text mode is not displayed: messages the originals print on exit/fatal paths go to stderr.

## Porting a function

1. Follow the spec pseudocode; confirm against the disassembly wherever the spec says *likely*/*guess*,
   or where signedness, carries or evaluation order matter.
2. Mark deliberate deviations with `/* PORT: ... */`, unresolved doubts with `/* TODO(verify): ... */`
   and list them in your report.
3. No `static` game state: state lives in `mem[]` (a `static` is fine for pure host-side caches).
4. Don't restructure files owned by another module. If you need a declaration that isn't in a shared
   header, add it to **your own** header.
5. Your files must compile without warnings.

## Build and checks

From `aotpport/` in Git Bash with MinGW first on PATH (`export PATH=/c/msys64/mingw64/bin:$PATH`; the
compiler fails silently otherwise):

```
cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=gcc -DCMAKE_BUILD_TYPE=Debug
cmake --build build
./build/aotp.exe --game-dir ../Game --check ../work/AP_flat.exe
```

Headless end-to-end run (always muted; INTRO → PS → AP → PS → quit with the phase 4 placeholders):

```
SDL_VIDEO_DRIVER=dummy SDL_AUDIO_DRIVER=dummy AOTP_TRACE=1 AOTP_SNAPSHOT_DIR=../work/snap \
AOTP_KEYS="3:01,6:01,9:01,12:01" ./build/aotp.exe --game-dir ../Game
```

Developer aids (`host.h`): `AOTP_SNAPSHOT_DIR` (+ `AOTP_SNAPSHOT_MS`, default 1000) saves presented
frames as PNG, `AOTP_KEYS` scripts XT key presses (`"<s>:<xt>[+<xt>][p|r],…"`, grey keys `e048`),
`AOTP_TRACE=1` logs program switches. Throwaway verification programs go in your scratch area. Do not
create HTML pages. Always run with `SDL_AUDIO_DRIVER=dummy`.
