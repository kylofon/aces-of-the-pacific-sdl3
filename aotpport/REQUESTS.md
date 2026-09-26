# Cross-module requests (phase 5)

Implementers: read the section for your module before you start, and tick items off (`[x]`) in your
report. The lead appends new requests from each report.

## coordinator (main.c, prog.c, host)
- [ ] `AOTP_TEST` dispatch in `main.c` calling the module test entry points (`snd_test_dro()`; the
      sound test currently runs from a constructor before `main`).
- [ ] Call `snd_host_detach()` at every program end (a fatal exit can skip shutdown and leave the
      sound service running).

## platform
- [ ] PS `0000:03c1` (named `lib_realloc`) is the one-argument malloc wrapper.
- [ ] `pk_seek` must stop at the end of a truncated stream (HANDOFFS R1); the sound loader relies on it.
- [ ] Missing sound globals for AP/PS in symbols (patch_block, timer_owned/handle, error, disabled,
      iterator, play id 7Eh, string buffers): `sound/snd_api.c` has a per-program table marked
      `TODO(symbols)` until rows exist (platform/lead: add rows to `port/spec/sound_extra_symbols.csv`).

## render3d
- [ ] `ldist3` takes two near pointers: `(u16 a_ds, u16 b_ds)`, not 6 words (used by `sound/sx_sim.c`).

## sim_flow
- [ ] `timeout_start` takes a 32-bit tick count (`s32`), not `u16` (used by `sound/sx_sim.c`).

## all modules
- [ ] MinGW: a stub file whose weak functions are the only globals fails to link ("multiple definition
      of .weak.f."). Give every `stubs_tmp.c` one plain global anchor, e.g. `int <module>_stubs_anchor;`.
      (`video/stubs_tmp.c` needs it.)
