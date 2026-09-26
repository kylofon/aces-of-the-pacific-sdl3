# Cross-module requests (phase 5)

Implementers: read the section for your module before you start, and tick items off (`[x]`) in your
report. The lead appends new requests from each report.

## coordinator (main.c, prog.c, host)
- [x] `AOTP_TEST` dispatch in `main.c` calling the module test entry points (`snd_test_dro()`; the
      sound test currently runs from a constructor before `main`). (platform, integration round: main.c runs `dro`; in-program tests (volumes/chunks/loaders/pictures/ttm) via `platform_dev_test`; sound's constructor removed.)
- [x] Call `snd_host_detach()` at every program end (a fatal exit can skip shutdown and leave the
      sound service running). (`platform_prog_end`; `host_fatal` detaches the service too.)

## platform
- [x] PS `0000:03c1` (named `lib_realloc`) is the one-argument malloc wrapper.
- [x] `pk_seek` must stop at the end of a truncated stream (HANDOFFS R1); the sound loader relies on it.
- [x] Missing sound globals for AP/PS in symbols (patch_block, timer_owned/handle, error, disabled,
      iterator, play id 7Eh, string buffers): `sound/snd_api.c` has a per-program table marked
      `TODO(symbols)` until rows exist (platform/lead: add rows to `port/spec/sound_extra_symbols.csv`). (`port/spec/sound_extra2_symbols.csv`; `snd_api.c` uses `G_snd_*` via `SD()`.)

## render3d
- [x] `ldist3` takes two near pointers: `(u16 a_ds, u16 b_ds)`, not 6 words (used by `sound/sx_sim.c`).
      (render3d: semantics done — a0/a1 are the two near pointers, the 4 extra words are ignored. The header keeps
      the 6-word form until sound drops its 6-word weak stub in `sound/stubs_tmp.c`; then switch header + the one
      call in `sx_sim.c` together.)

## sim_flow
- [x] `timeout_start` takes a 32-bit tick count (`s32`), not `u16` (used by `sound/sx_sim.c`).

## all modules
- [x] MinGW: a stub file whose weak functions are the only globals fails to link ("multiple definition
      of .weak.f."). Give every `stubs_tmp.c` one plain global anchor, e.g. `int <module>_stubs_anchor;`.
      (`video/stubs_tmp.c` needs it.)

## lead (from platform, 2026-09-26)
- [x] Delete `game/placeholder.c` once the real mains link (platform's mains are weak until then). Not yet: PS's real main needs shell_ui/shell_data, and the headless chain test relies on the placeholders.
- [x] symbols.csv lacks the RTL globals (private table `rtl_layouts` in `platform/rtl_dos.c`), AP `mtx_*`
      globals and PS SCN-encoder state (hard-coded fallbacks in `loaders.c`, `scn_encode.c`); INTRO
      `pal_slots`/`font_ptr` are not in the layout table under `pal_slot`/`font_glyphs`. (`platform_extra2_symbols.csv` / `video_extra2_symbols.csv`; `rtl_layouts`, the loaders/scn fallbacks and video's INTRO special cases removed.)

## sim_flow (from platform)
- [x] AP loaders call `ap_fread_far_4bb7`, which must behave like `my_hread`. (implemented by platform in `platform/loaders.c`; sim_flow must not define it again.)

## video (from platform)
- [x] Driver entry 14 receives 5 arguments and entry 15 a 16-bit count; the current function types
      are narrower (works for the loaders). (video: entry 14 already takes 5 words (list, far buf, u32 n);
      `DrvBmMergeFn`/`drv_bm_merge_hi` now take a `u16` count, as `0E04` reads CX = [bp+0Eh].)

## render3d / video (from platform's link of shell_data)
- [x] shell_data needs `mul32`, `lmid`, `atan2_32`, `ldist2` (PS 3d50 math library, owned by render3d). (render3d/r3d_math.c, PS and AP.)

## platform (from video, 2026-09-26)
- [x] `emm_pool.c:105` passes 9 arguments to `gfx_sprite_rotated_ind`; drop the trailing 0 (breaks the build).
- [x] `scr_load`'s first word is the name, not `page`: rename the parameter.
- [x] Implement `ap_fread_far_4bb7` (AP loaders; without it AP pictures read garbage and VQT recursion overflows).
- [x] Call `video_dev_test()` from `platform_dev_test` (or main.c's AOTP_TEST dispatch).
- [x] `bmp_mtx_load` is platform's (video removed its duplicate; ttm.c calls it).
- [x] `intro_main.c` uses `host_fatal` without including its header.

## lead / symbols (from video)
- [x] INTRO `pal_slots` → `pal_slot`, `font_ptr` → `font_glyphs` in the layout table; AP driver block 0x3480;
      AP font slots DS:3F2A..3F32 and name strings DS:02E6..0302.

## video (from platform, integration round)
- [x] `vqt.c`'s constructor now also registers `F_gfx_sprite_scn` (AP's `scn_draw_fn` reached it unregistered: fatal in AP pictures). Please keep it.
- [x] AOTP_TEST=pictures under AP: 154 BMP / 864 frames load and draw; against work/img 123 PNGs are identical or identical up to the palette, 34 differ in their colour indices (mostly `nib` bitmaps, some `vqt`: ALERTS, MOON*, SMOKE, BACK4, RGUN*, ...; the shapes are right) — check AP's drawing/palette path; SCR strips (322x202) cannot be compared with dynimg's 320x200.
      (video: not a port bug. Index-level comparison against the current dynimg decoders: AP 157/157 BMPs
      identical incl. SIM1/SIM2/M1SIM, INTRO/PS 106/107 (DEMO.SCR not openable). The RGB differences come from
      SIM.PAL existing only in SHELL1 (not openable from AP, so the test falls back to grey) and from
      work/img PNGs older than dynimg's nibble fix (stored vs fresh differ for the nib BMPs).)

## shell_data / shell_ui / render3d (from platform, integration round)
- [x] `platform/stubs_tmp.c` carries weak link stubs for your functions the shared build references (math library, `service_side`, `fltplan_*`, `fm_bearing`, and a generated block at the end of the file). Delete a stub's line (or leave it: the weak stub loses to your definition) — tell platform if one collides.

## from render3d (2026-09-26)
- [x] platform: call `render3d_dev_test()` from `platform_dev_test` (AOTP_TEST=shapes, run with --start 3).
- [x] video: `video.h` uses `CodeFn` without including `codeptr.h`; its static `pal_fx_build_delta`
      duplicates `palfx_delta_table_body` (1792:038b) — harmless, dedupe later.
- [x] shell_data: use `ts_load_table_far` (far table in DX:AX) and the new `mul_cos`/`mul_sin` signatures.
- [x] sim_world: register 655d:1bb7 (gun-smoke callback, via stub 3DFF:0061) with codeptr.
- [x] sound + render3d: switch `ldist3` to `(u16 a_ds, u16 b_ds)` together (semantics already match).

## from sim_world A (2026-09-26)
- [x] platform: call `sim_world_a_dev_test()` (AOTP_TEST=fm / ballistics) from `platform_dev_test` so build_sim_world_a's `--wrap` flags can go.
- [x] sim_flow: implement `misc.c` (`res_name`, `file_load`, `res_load_set`, `res_free`, `ap_fread_far_55a4`) — only no-op stubs exist; snario.c/acedata.c need them to run.
- [x] sim_world B (AI): fix the `ai_*.c` compile errors (conflicting prototypes, missing `PROG_AP`/`stdarg.h`); they break the shared build. (sim_world B: fixed; all 11 AI files build warning-free with part A.)
- [x] 655d:1bb7 gun-smoke callback registered (damage.c).

## integration round (2026-09-26)
- [x] All `*/stubs_tmp*.c` deleted; the only link gap was `fd_init` (shell_ui/fltdeck.c had made it static; once-init 0a71:01be calls it).
- [x] `gfx_sprite_rotated` registered in `video/vqt.c` (removed from `sim_flow/vcr_runtime.c`); `gfx_sprite_rotated`, `drv_set_unselect`, `pal_fx_build_delta` declared in `video.h` (which now includes `codeptr.h`); render3d's `palfx_delta_table_body` calls video's `pal_fx_build_delta`.
- [x] `ldist3(a, b)` everywhere (render3d, sim_flow, sim_world, sound).
- [x] shell_data threed.c: `ts_load_table_far` for both tables (the chunk offset is 0: the AX-only test made view3d_load_scene assert 0xE7 = line 231).
