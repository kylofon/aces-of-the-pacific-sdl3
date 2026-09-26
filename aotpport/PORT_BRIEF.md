# Brief for phase 5 module implementers

You implement one module (or one part of a module) of the faithful C/SDL3 port of DOS **Aces of the
Pacific**. Repo `C:\Coding\AcesOverPacific`, port in `aotpport/`.

Read first: `aotpport/PORTING.md` (rules, memory model, module interfaces, file split),
`PLAN.md` (decisions), `port/spec/README.md`, your module's specs in `port/spec/`, `port/spec/HANDOFFS.md`
(entries concerning your module), `port/modules.csv` (the functions you own: column `module`, file:
`c_file`), and your module header `aotpport/src/<module>/<module>.h`.

Rules:
- **No sub-agents.** Work alone. Save often; build often.
- Implement every function your part owns in the `c_file` given by `port/modules.csv`. Behaviour,
  integer arithmetic, order of operations, RNG draws and quirks must match the spec; where the spec
  is unclear, the disassembly is the ground truth (`python tools/x86dis.py <exe> dis SSSS:OOOO LEN`,
  AP = `work/AP_flat.exe`). Mark deliberate deviations `/* PORT: ... */`.
- Globals stay in `mem[]` at their DS offsets (program symbols `INTRO_DS_x`/`PS_DS_x`/`AP_DS_x`, shared
  library globals via the layout ids). Never shadow game state in C statics.
- You may fix your own module header (signatures) — note the change at the top of your report. If
  another module's header is wrong for you, don't edit it: write the needed change in your report.
- Until the other modules exist, calls into them need stubs: put them in
  `aotpport/src/<your module>/stubs_tmp.c`, **every stub marked `__attribute__((weak))`** so that
  several implementers' stubs and the real implementation can coexist in one build. MinGW needs
  one plain global in each stub file (`int <module>_stubs_anchor;`), or the link fails.
- Read `aotpport/REQUESTS.md` (requests from other modules to yours) and handle your section.
- Several implementers work at the same time: **build in your own directory**
  `aotpport/build_<module>` (not `build/`), and edit only your module's files.
- Keep the build clean (`-Wall`, no warnings) and the headless chain running:
  `PATH=/c/msys64/mingw64/bin:$PATH`, build in `aotpport/build`, run with
  `SDL_VIDEO_DRIVER=dummy SDL_AUDIO_DRIVER=dummy` (always mute), `--game-dir ../Game` (see
  PORTING.md). Don't run the game with sound.
- Write test harnesses as developer aids inside the port (env vars like `AOTP_TEST=...`) rather than
  separate programs; compare against the Python reference tools in `tools/` where they exist
  (`dynimg.py` pictures, `dynchunk.py` decompression, `aotpsnd.py` DRO renders, `dynshape.py`).
- Don't commit; the lead reviews and commits.

Report (under 40 lines): files written, functions implemented vs owned, verification done (and
against what), header changes, requests to other modules, known gaps.
