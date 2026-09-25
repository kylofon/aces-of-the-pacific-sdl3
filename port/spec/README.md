# Phase 3 specs

One spec per subsystem, written against the three programs (read `../RE_GUIDE.md` first). Each spec
owner also writes `<module>_symbols.csv` with the columns of `../symbols.csv`
(`exe,kind,address,name,type,owner,other_names,notes`, `owner` = the module name); `tools/merge_symbols.py`
merges them into `../symbols.csv` afterwards.

| Module | Spec | Scope |
|---|---|---|
| platform | `platform.md` | Shared system library (INTRO `05da` / PS `16e3` / AP `1d32`): timer, keyboard, mouse, joystick, DOS memory, EMS (+ AP `emm_pool.c`, `mem.c`), Windows checks; `volume.c`; resource loaders and decompression; fatal/assert; start-up and `main` option parsing of all three; the GCD chain and the `0000:0510` marker; `RESOURCE.CFG`, `*.PRF`; the Borland RTL functions actually used (list, behaviour notes only) |
| video | `video.md` | The VGA320 driver loaded from `VMCODE.OVL`/`VMCODE2.OVL` (all 50 jump-table entries), pages and flipping, palettes and fades (`103d`, DAC code), bitmap / screen / font drawing, the TTM player (INTRO `1125`, PS `3b02`, AP `24fc`) and the `ts_*` library |
| sound | `sound.md` | The SCI player (INTRO `1373`, PS `430a`, AP `3060`), sound API modules, the embedded AdLib driver, `sx_sim` and every game call site's intent |
| shell_ui | `shell_ui.md` | INTRO's flow; PS `main`, `alert\*` (dialogs, menus, list boxes), all `shell\*.c` screens, `simshell`, `shell_exit`, screen flow graph of the shell |
| shell_data | `shell_data.md` | PS `emd\*` (world data, campaign, squadrons, aces, medals, dates, aircraft, ships, convoys, stations, ordnance), `sys\*` (scenario, historic, ranks, text…), `miss\script.c` + mission types `s_*.c`, `file.c` (SIM.IN / SIM.OUT, roster, records) |
| sim_flow | `sim_flow.md` | AP `main`, `init`, sim main loop and time base, mission set-up from `SCRIPT.DAT`, views/camera selection, cockpit and HUD (`cockpit.c`, gauges), messages, map (`fltmap`), in-sim dialogs/sliders/`stdalert`, controls, results (`SIM.OUT`), VCR film record/playback, `sim_exit` |
| sim_world | `sim_world.md` | AP flight model, AI (`g_attack`, `ces`), formations, weapons (guns, bombs, rockets, torpedoes, flak), damage, collisions, ships and ground targets, the sim-side scenario (`snario`), `acedata` |
| render3d | `render3d.md` | AP 3Space renderer: world/shape loading (`obwload`, macros, pool), camera, transform/projection (386 fixed point), LOD, part sorting, polygon fill and shading (`SHADES.DAT`), terrain/islands, sky, clouds, stars, horizon, effects (`.BMD`), `paltrick`, `ts_draw` |

Address convention and tools: `../RE_GUIDE.md`. File formats: `../../FORMATS.md`, `../formats/*.md`.
