# Aces of the Pacific — SDL3 port plan

Same approach as the Test Drive ports (TestDrive1987, TestDrive2, TestDrive3): first a **faithful C
port** here (reverse-engineer → document → port function by function against the original data,
read at runtime), then a separate **Aces of the Pacific Enhanced** repo built on it.

Aces of the Pacific (Dynamix, 1992; this copy: CD release, "ver. 1.2", 1994 readme) is a 3Space
flight sim: filled-polygon 3D world, cockpits, career mode, mission builder, film (VCR) playback. It is
far larger than any Test Drive: ~900 KB of x86 code over three programs, against 166 KB for TD3.

## What we have (recon, 2026-09-25)

`Game/` is a junction to `AcesotP/DYNAMIX/AOTP` (the installed game, eXoDOS layout; `AcesotP/CD`
holds the CD image, a single data track: no CD audio).

| File | Size | Notes |
|---|---|---|
| `GCD.COM` | 965 | Chain loader: runs `INTRO.EXE`, then loops `PS.EXE` ⇄ `AP.EXE` on the child's exit code; checks the temp area with `btest.bin` |
| `INTRO.EXE` | 117 008 | Intro sequence. Borland C++ 3.0 (1991) real mode, 957 relocs. Source path `d:\aces1946\code\shell\intro\`. Mentions `vmcode.ovl`, `sxcode.ovl`, `ttd.sx`; requires 610 000 bytes of EMS |
| `PS.EXE` | 377 136 | The shell ("Aces Of The Pacific ver. 1.2"): menus, career, mission set-up, briefings, records. Borland C++, 7177 relocs, no overlays. Writes `SIM.IN`, reads `SIM.OUT` |
| `AP.EXE` | 494 032 | The simulator. Borland C++, 3433 relocs, **VROOMM overlays**: `FBOV` block of 192 256 bytes, 525-entry segment table. "At least 112K EMS memory required" |
| `*.DYN` | 5.5 MB | **Dynamix Volume File** archives: `COMMON1`, `SHELL1`, `SIM1`, `SIM2`, `M1CMN`, `M1SHL`, `M1SIM` (M1 = add-on/mission-set 1?). Entries are named files (`FONT1.FNT`, `ACES.PAL`, `P80.TBL`, `MIDWAY.TBL`, …) holding DGDS-style tagged chunks (`PAL:VGA:`, `SCR:VGA:`, `BMP:VGA:`, `FNT:`, `MAP:`, `DAT:`, `GID:`, `APP:`, `INF:`) |
| `ADL.DRV`, `MT32.DRV`, `STD.DRV`, `IBMPS1.DRV` | 2–9 K | **Sierra SCI sound drivers** (`87654321h` signature): AdLib, MT-32/MPU-401, PC speaker, PS/1 audio. Selected in `RESOURCE.CFG` (`soundDrv`) |
| `RESOURCE.CFG` | 248 | Text config: sound/joystick/mouse/memory drivers, toggles, `minCPU 386`, `minEMS 336` |
| `*.PRF` | | Preferences: `CONTROL.PRF`, `SIMPREFS.PRF`, `MREAL.PRF`/`CREAL.PRF` (realism) |
| `SIM.IN`/`SIM.OUT` | | Shell → sim mission hand-off and result |
| `ROSTER.DAT`, `TOPACE.DAT`, `TOPMISS.DAT` | | Pilot roster, hall of fame |
| `SCRIPT.DAT`, `MAINMENU.SCD` | | Shell script / menu data |
| `TAPES/*.VCR` | | Recorded flights (demo films) |
| `CPVW.BUF` | 192 008 | Zero-filled scratch file (cockpit view buffer?) |
| `INST.EXE`, `BOOTDISK.EXE`, `RC2CP.EXE`, `README.MVB` | | Installer, boot-disk maker, config converter, Windows help: out of scope |

Graphics: `VGA320` (MCGA/VGA 320×200×256) is the only video driver name found; EGA palettes exist in
the resource code paths (`PAL:EGA:`) but no EGA driver is shipped.

## Phases

### 0. Repository — done (2026-09-25)
- `C:\Coding\AcesOverPacific`, git `master`, no remote (GitHub later, on request).
- `Game/` → junction to the installed game (git-ignored, with `AcesotP/`).
- `_tools` → junction to `TestDrive1987/_tools` (Ghidra 12.1.3, JDK 21).
- Tools carried over from TD3: `x86dis.py`, `merge_symbols.py`, `gen_symbols.py`, `assign_modules.py`,
  `snapsheet.py`, the Ghidra scripts, and `td3index.py` as the base for the new indexer.

### 1. Executable map — first pass done (2026-09-25, see `port/RE_GUIDE.md`)
Found: Borland C++ 3.0 medium model, no x87/emulator (AP is 386 integer code); DGROUPs 17E0/4D08/3EA4;
GCD exit codes 0 DOS / 1 INTRO / 2 PS / 3 AP with the `0000:0510` marker; timer 236.7 Hz (PIT 65535/13);
video and sound drivers are loaded from the volumes (`VMCODE.OVL`: unchained 320×200, 3 pages;
`SXCODE.OVL`/`SX.OVL`: SCI0-style drivers).
- **De-overlay AP.EXE** (`tools/unovl.py`): load every VROOMM overlay segment after the resident
  image, apply its relocations and turn the `INT 3Fh` stubs into direct far jumps, so Ghidra and the
  indexer see one flat program.
- Index the three programs (`tools/apindex.py`, from `td3index.py`, Borland C++ 3.0 flavoured):
  segments, far/near functions, DGROUP, strings, INT 67h (EMS), I/O ports.
- Identify the Borland C++ 3.0 RTL and the Dynamix library shared by INTRO/PS/AP (resource volumes,
  memory/EMS, graphics, sound driver interface, input) by matching functions across the three exes.
- Ghidra projects in `_ghidra/`, decompiles in `port/decomp/` (ignored).
- Output: `port/RE_GUIDE.md`, `port/symbols.csv`.

### 2. File formats
Decoders in `tools/` that dump to `work/` with contact sheets:
1. Dynamix Volume File directory + tagged chunks + their compression (DGDS: RLE / LZW).
2. Palettes, fonts, bitmaps and screens → PNG.
3. 3D shapes (aircraft, ships, ground objects), terrain / map tables (`*.TBL`), cockpits.
4. Sound: SCI-format music and effects, the SCI driver interface; render AdLib to `.dro`.
5. `.PRF`, `RESOURCE.CFG`, `SIM.IN`/`SIM.OUT`, roster/records, `SCRIPT.DAT`/`.SCD`, `.VCR` films.

### 3. Specs
Split by subsystem (names to be settled in phase 1): platform (startup, EMS, timer, input, files),
video (VGA 320 driver, palettes, blitters), resources (volumes, chunks, decompression), shell UI
(PS: menus, career, briefings, mission builder), intro, sim game flow (AP: mission run, debrief,
VCR), flight model, AI / weapons / damage, render3d (3Space: transform, polygons, terrain, sky,
cockpits), sound (SCI driver interface + AdLib device).

### 4. `aotpport/` skeleton
CMake + SDL3, adapted from `td3port`: loaders for the three exes (AP flattened), `mem.h` memory
model, EMS model (page frame in `mem[]`), host (timer, keyboard, mouse, joystick, OPL), VGA model,
generated `symbols.h`, `PORTING.md`. INTRO/PS/AP run in one process; the `GCD.COM` chain becomes
a loop in `main`.

### 5. Port, subsystem by subsystem
Order: platform/video/resources → intro → shell screens (visible milestone) → sim start-up +
3D renderer (static camera, then a VCR film playing back) → flight model and controls → AI and
weapons → full mission loop shell ⇄ sim → sound. Verified against DOSBox captures of the original
and headless snapshots (`SDL_VIDEO_DRIVER=dummy`, `SDL_AUDIO_DRIVER=dummy`).

### 6. Release, then Aces Enhanced
Release the faithful port (v0.1.0 zip, launcher like TD3). Then a new `AcesOverPacificEnhanced`
repo: the world and aircraft are polygons, so the 3D view can be re-rendered at native resolution /
widescreen / 60 fps from the same geometry, with longer view distance and higher detail later.

## Decisions

1. **Sound** (2026-09-25): AdLib through a bundled OPL emulator (Nuked-OPL3, as TD3), behaving like the
   SCI `ADL.DRV`. MT-32, PC speaker and PS/1 audio → TODO.
2. **Packaging** (2026-09-25): one executable. INTRO, PS and AP run in one process; the `GCD.COM` chain
   becomes a loop in `main`; `SIM.IN` / `SIM.OUT` are still written to the game folder as the original does.
3. **Milestone** (2026-09-25): the full chain (intro + shell + sim) is ported before the v0.1.0 release.

Still open (settled when the phases reach them): EMS model, frame pacing, copy protection, graphics
(VGA only, expected).

## TODO (parked)

- [ ] MT-32 / LAPC-1 music (Munt; user supplies ROMs)
- [ ] PC speaker and PS/1 audio drivers
