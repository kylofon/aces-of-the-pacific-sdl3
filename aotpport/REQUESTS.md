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
- [ ] `ldist3` takes two near pointers: `(u16 a_ds, u16 b_ds)`, not 6 words (used by `sound/sx_sim.c`).

## sim_flow
- [ ] `timeout_start` takes a 32-bit tick count (`s32`), not `u16` (used by `sound/sx_sim.c`).

## all modules
- [x] MinGW: a stub file whose weak functions are the only globals fails to link ("multiple definition
      of .weak.f."). Give every `stubs_tmp.c` one plain global anchor, e.g. `int <module>_stubs_anchor;`.
      (`video/stubs_tmp.c` needs it.)

## lead (from platform, 2026-09-26)
- [ ] Delete `game/placeholder.c` once the real mains link (platform's mains are weak until then). Not yet: PS's real main needs shell_ui/shell_data, and the headless chain test relies on the placeholders.
- [x] symbols.csv lacks the RTL globals (private table `rtl_layouts` in `platform/rtl_dos.c`), AP `mtx_*`
      globals and PS SCN-encoder state (hard-coded fallbacks in `loaders.c`, `scn_encode.c`); INTRO
      `pal_slots`/`font_ptr` are not in the layout table under `pal_slot`/`font_glyphs`. (`platform_extra2_symbols.csv` / `video_extra2_symbols.csv`; `rtl_layouts`, the loaders/scn fallbacks and video's INTRO special cases removed.)

## sim_flow (from platform)
- [x] AP loaders call `ap_fread_far_4bb7`, which must behave like `my_hread`. (implemented by platform in `platform/loaders.c`; sim_flow must not define it again.)

## video (from platform)
- [ ] Driver entry 14 receives 5 arguments and entry 15 a 16-bit count; the current function types
      are narrower (works for the loaders).

## render3d / video (from platform's link of shell_data)
- [ ] shell_data needs `mul32`, `lmid`, `atan2_32`, `ldist2` (PS 3d50 math library, owned by render3d).

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
- [ ] `vqt.c`'s constructor now also registers `F_gfx_sprite_scn` (AP's `scn_draw_fn` reached it unregistered: fatal in AP pictures). Please keep it.
- [ ] AOTP_TEST=pictures under AP: 154 BMP / 864 frames load and draw; against work/img 123 PNGs are identical or identical up to the palette, 34 differ in their colour indices (mostly `nib` bitmaps, some `vqt`: ALERTS, MOON*, SMOKE, BACK4, RGUN*, ...; the shapes are right) — check AP's drawing/palette path; SCR strips (322x202) cannot be compared with dynimg's 320x200.

## shell_data / shell_ui / render3d (from platform, integration round)
- [ ] `platform/stubs_tmp.c` carries weak link stubs for your functions the shared build references (math library, `service_side`, `fltplan_*`, `fm_bearing`, and a generated block at the end of the file). Delete a stub's line (or leave it: the weak stub loses to your definition) — tell platform if one collides.
