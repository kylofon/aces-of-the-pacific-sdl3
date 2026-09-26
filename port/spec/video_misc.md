# video — AP `368f` page/wipe/wait helpers and `4c9b` font set

Extra part of `video.md`. Segment `368f` (no source tag; 24 functions) is a small AP utility module:
page selection, the line-blind screen wipe, clip reset and the countdown waits are video; the
string/filename helpers are platform per the ownership map in `sim_flow.md` (`368f` row) and are
rowed with owner `platform` in `platform_misc_symbols.csv` (spec below, §3). Verified against
x86dis.

Driver block (AP DGROUP, base `DS:26C0`, `video.md` §2): `26C3` clip flag `drv[03]`, `26C4/26C6`
clip x0/x1, `26C8/26CA` clip y0/y1 (inclusive), `26CC` fill flag `drv[0C]`, `26CD/26CE` colours
`drv[0D]/[0E]`, `26D0` background page `drv[10]` (A800), `26D2` back page `drv[12]`, `26D4` front
page `drv[14]`, `26D6` read page `drv[16]`, `26D8` write page `drv[18]`, `26DC` is_tandy, `26DF`
DAC flag `drv[1F]`. Screen size `DS:2DAA` (w) / `DS:2DAC` (h). Timer (platform): `DS:31E4`
timer_installed, `DS:31E5` timer_countdown (s16, −1 per 236.69 Hz tick, saturating at 0).

## 1. Page selection (all far, no arguments)

| AP | Name | Effect |
|---|---|---|
| 368f:03b6 | `write_back` | `DS:26D8 = DS:26D2` |
| 368f:03c1 | `read_back` | `DS:26D6 = DS:26D2` |
| 368f:03cc | `write_bg` | `DS:26D8 = DS:26D0` (no callers) |
| 368f:03d7 | `read_bg` | `DS:26D6 = DS:26D0` |
| 368f:03e2 | `write_front` | `DS:26D8 = DS:26D4` |
| 368f:03ed | `read_front` | `DS:26D6 = DS:26D4` |
| 368f:01cf | `clip_full` | `DS:26C3 = 1` (clip on), `DS:26CC = 1` (filled); `DS:26C4 = DS:26C8 = 0`; `DS:26C6 = DS:2DAA − 1`; `DS:26CA = DS:2DAC − 1` |
| 368f:01f2 | `copy_screen` | `gfx_copy_rect(0, 0, DS:2DAA, DS:2DAC)` (`1d32:53fe`, read page → write page) |

## 2. Countdown waits and the wipe

| AP | Name | Behaviour |
|---|---|---|
| 368f:00b7 | `countdown_get()` → int | `DS:31E4 ? DS:31E5 : 0` |
| 368f:00ca | `countdown_wait()` → int | `while (countdown_get() && !key_or_click()) ;` (`606e:0208`) → return `countdown_get()` (0 = expired, else interrupted by input) |
| 368f:00e6 | `delay18(int n)` | `DS:31E5 = 13·n` (≈ n BIOS ticks: 13/236.69 s = 54.9 ms); `wait_key_release()` (`606e:0243`); `countdown_wait()` |
| 368f:009f | `dec_floor(int *p)` → int | `if (--*p > 0) return 1; *p = 0; return 0` (signed) |
| 368f:008d | `floppy_off()` | `if (!DS:26DC) 0000:18d6()` — RTL-segment helper that writes 1 to BIOS `0040:0040` (motor-off count) and spins (≤ F000h loops) until `0040:003F & 3` is 0 (the floppy motors stop). `/* PORT: */` no-op |

`368f:00ff wipe(int x, int y, int w, int h, int ticks, int copy)` (far) — the "line blind" screen
transition (not a column dissolve):

```
last = y + h - 1
DS:31E5 = 0
for k = 0..9:
    while (countdown_get()) ;              // wait for the previous pass's time slot (no input check)
    DS:31E5 = ticks
    for (r = y + k; r <= last; r += 10)
        if (w) copy ? gfx_copy_rect(x, r, w, 1)      // 1d32:53fe, read page -> write page
                    : gfx_rect(x, r, w, 1)           // 1d32:6ab0, filled with drv[0D] when drv[0C]
```

Each pass draws every 10th row starting at row `y+k`; ten passes cover the rectangle; each pass
starts `ticks` PIT ticks after the previous one (the last pass is not followed by a wait). With the
timer not installed `countdown_get()` is 0 and the wipe runs without delay.

| AP | Name | Behaviour |
|---|---|---|
| 368f:017f | `wipe_in(int ticks)` | `read_back(); write_front(); wipe(0, 0, 320, 200, ticks, 1)` — reveal the back page onto the displayed page (callers use 2 or 4 ticks: 10 × 4/236.69 s ≈ 0.17 s) |
| 368f:01a3 | `wipe_black()` | `write_front(); DS:26CC = 1; DS:26CD = DS:26CE = 0; wipe(0, 0, DS:2DAA, DS:2DAC, 4, 0)` — blind the displayed page to colour 0 |

Port: the wipe draws on the **front** (displayed) page, so the host must present after every pass
(or at least at the 236.69 Hz time slots) for the effect to be visible; `/* PORT: */` present the
front page once per pass.

## 3. String helpers (owner platform)

| AP | Name | Behaviour |
|---|---|---|
| 368f:000e | `memswap(u8 *a, u8 *b, int n)` (near data) | swap `n` bytes (`n <= 0`: nothing); no callers |
| 368f:002f | `memswap_huge(u8 huge *a, u8 huge *b, int n)` | same with huge-pointer increments (`0000:1e58` PADA); no callers |
| 368f:020a | `str_subst(char *s, char c, char r)` → s | the first `c` among the `strlen(s)+1` bytes of s (the NUL included) is replaced by `r`; none → unchanged |
| 368f:0243 | `strip_ext_all(char **v, int n)` | for each of `v[0..n)`: `str_subst(v[i], '.', 0)`; no callers |
| 368f:0268 | `strlist_remove(char **v, char *s, int n)` → n | first i with `strcmp(v[i], s) == 0`: `n−1` is returned and `v[i+1..n)` moved down one (`memmove`, `0000:3e34`); not found → n. No callers |
| 368f:02e6 | `make_filename(char *name, char *ext)` → `DS:712C` | `strcpy(DS:712C, name)`; `str_subst(DS:712C, '.', 0)` (drop any extension); append `DS:3723` = `"."`; `strcat(DS:712C, ext)`. Static buffer: the result is overwritten by the next call |
| 368f:035c | `make_filename_dev(char *name, char *ext)` → `DS:712C` | if `DS:26DF == 0` (no DAC-capable display): `strcpy(DS:3719, name)`, `DS:3720 = 0` (keep 7 chars), name = `DS:3718` — the byte before is `'E'`, so the name becomes `"E" + name[0..7)` (EGA variant files); then `make_filename(name, ext)`. Caller `4e0d:0c29` |
| 368f:03a1 | `itoa_static(int v)` → `DS:714A` | `itoa(v, DS:714A, 10)` (`0000:3d02`); caller `6e9f:02ab` |

Buffers: `DS:712C` (30 bytes up to `DS:714A`), `DS:714A` (itoa text), `DS:3718` `"E2345678--"`
template, `DS:3723` `"."`.

## 4. `4c9b:0000 fonts_load()` → int (far)

For the five names `"font1"`, `"font2"`, `"font3"`, `"font4"`, `"talk"` (`DS:02EA/02F0/02F6/02FC/
0302`): `font_load(res_name(name, "FNT"))` (`55a4:0000` with `DS:02E6` = `"FNT"`, then
`7115:0000` = the shared `gfx_font_load`, `video_library.md` §8.2) into, in this order, `DS:3F32`
(font1), `DS:3F30` (font2), `DS:3F2E` (font3), `DS:3F2C` (font4), `DS:3F2A` (talk). All five are
loaded even if one fails; returns 1 if all five slots are non-zero, else 0 (`sim_init` `4e0d:0000`
then aborts with a fatal error). `DS:3F2E`/`DS:3F30` are the radio-menu fonts
(`sim_flow_cockpit.md` §7).

## Hand-offs

* video_palette.md §10 calls `368f:00ff` a "column dissolve": it is a 10-pass horizontal-line
  blind (rows `y+k+10j`, `gfx_copy_rect(x, r, w, 1)`), see §2 here.
* platform: rows for §3 are in `platform_misc_symbols.csv`; `0000:18d6` (floppy motor wait) lives in
  the RTL segment that `spec_coverage.py` skips.
