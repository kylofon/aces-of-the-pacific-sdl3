# render3d — part 5: sky, horizon and sea, sun/moon/stars, palette effects, shadows and small effects

Part of the `render3d` spec (index: `render3d.md`). AP.EXE addresses in `work/AP_flat.exe`
(`SSSS:OOOO`, DGROUP `3EA4`, `DS:xxxx`); 277a state is `CS:xxxx` (render3d_math.md §2.3). All
routines here are compiled C (far cdecl, `retf`, caller pops) except the span/DDA helpers `0a88`
and `1abf:011d`, which are small hand-written asm routines with a stack interface. No
self-modifying code, no port I/O and no use of the VGA/EGA flag `DS:26DF` in this part (checked
for every function listed below). All arithmetic is integer; "i16", "i32" = signed, "u16" =
unsigned; `/` on signed values is `idiv` (truncation toward zero), `>>` on signed values is
arithmetic.

Scope: `4d6e` (horizon/sea/sky fill, 8), `0a88` (span-list helpers, 10), `1abf` (DDA, 4), `55e8`
sky.c (6), `59eb` stars.c (2), `6964` sun/moon/time of day (11), `4b91` moon phase (2), `1a9a`
stars draw + angle vector (2), `1a8b` aircraft shadows (3), `675d:0000` ground speed dots,
`655d:038a` muzzle flash / gun smoke effects, `1792` palette effect channels (9), `17ce`
per-frame palette update (2), `51b4` paltrick.c (2), `51a8` (2). 63 functions (`1792:038a/038b`
count as one routine, see §5.8).

Confidence: **Verified** (read in the disassembly) unless marked **Likely** / **Unknown**.

Video library calls are named as in `video_library.md` (`gfx_*`, AP addresses in `1d32`); the 2D
drawing context `drv[X]` = `DS:26C0+X` (video.md §2.4): `DS:26C3` clip on, `DS:26C4/26C6/26C8/26CA`
clip x0/x1/y0/y1 (inclusive), `DS:26CC` fill on, `DS:26CD` draw colour, `DS:26CE` fill colour,
`DS:26D2`/`26D4` page segments, `DS:26D6` read page, `DS:26D8` draw page.

-----------------------------------------------------------------------------------------------

## 1. Overview (one frame)

```
sim step (5440:1317, sim_flow):  sky_update()                     6964:0076  (clock, stars flag, light)
frame draw (5440:018c):
    shadows_queue()   1a8b:004c   → effect records (05a9 pool)
    gun_flash_queue() 655d:038a   → effect records
    render_scene()    5440:03aa   (render3d_world.md §1.1):
        set_light(DS:51D9, DS:51DD)                           277a:0152
        horizon_draw(DS:5BDB, DS:5BDD, CS:0A1F, CS:0A21, DS:5BDA ? NULL : 3E1D:002A)
            sky side (gradient bands + flat top colour)
            → callback sky_draw_callback() 6964:01a2: stars, sun disc, moon bitmap
            sea side (flat colour)
        scene_draw(): ground layer, then DS:36D0 = ground_dots_draw() 675d:0000, then the rest
    palfx_frame()     17ce:0013   (palette channels → working palette → DAC request)
    5440:07e1         (sim_flow: vsync flip + DAC upload of the queued palette)
```

Palette layout used by this part (from the constants in the code and `PAL_MAPS.DAT`):

| Colours | Use |
|---|---|
| `70h..7Fh` | sky ramp: `70h` = haze at the horizon … `7Fh` = top of the sky (`DS:5BDB` = base 70h); `70h` also the cloud-deck / overcast colour |
| `80h` (`80h..87h`) | sea (`DS:5BDD` = 80h) |
| `8Ch` | sun disc |
| `8Dh`, `8Eh` | stars (by the star's flag bit 0) |
| `0..87h` | colours the ground dots recolour through `DS:102E` |
| `D0h..FDh` | cockpit (dimmed at night by channel 4) |

-----------------------------------------------------------------------------------------------

## 2. Horizon, sky and sea (`4d6e`, helpers `0a88`, `1abf`)

The 3D view has no sky or sea polygons: `horizon_draw` fills the whole view window with a
2-colour split along the projected horizon line (sky above, sea below, roll and pitch applied),
plus optional haze bands of the sky ramp parallel to the horizon on the sky side. Land and every
object are drawn over it afterwards. The horizon is the projection of the plane's
horizontal direction at infinity only (no curvature, no altitude dependence).

### 2.1 Data

| DS: | Type | Name | Meaning |
|---|---|---|---|
| `031A` | i16 | `haze_spacing` | band spacing in pixels (perpendicular to the horizon); file value 2 |
| `031C` | i16 | `haze_bands` | number of bands; file value 0Fh |
| `031E` | i16 | `haze_step` | colour step between bands; file value 1 |
| `0320` | i16 | `haze_on` | bands drawn when ≠ 0; file value 1 (set by `17ce`, `51b4:0088`) |
| `0322` | far | `hz_buf` | 780h-byte buffer (960 i16), `4d6e:004b`: x-edge array for the flat case, span list for the steep case |
| `3FFA` | u16 | `hz_cb_pending` | see §2.3 |
| `3FFC` | far code | `hz_cb` | the callback of the current call (drawn between sky and sea) |
| `4000`,`4002` | i16 | `hz_y1`, `hz_x1` | right end of the horizon segment (screen) |
| `4004`,`4006` | i16 | `hz_y0`, `hz_x0` | left end |
| `4008`,`400A` | i16 | `hz_nx`, `hz_ny` | 2.14 vector (`∓cos r`, `±sin r`) selecting the sky side and the band direction |
| `400C` | u16 | `hz_sea_col` | sea colour of this call (low byte used) |
| `400E` | u16 | `hz_sky_base` | sky ramp base colour (low byte used) |
| `3172` | u16 | (video) | segment of the library span scratch buffer (`span_seg`, offset 0) |

Span list (the `gfx_poly_spans` format, video_library.md): `{u16 y0; u16 n; n × {i16 xl; i16 xr}}`,
one span per row from `y0` down. `DDA` (8 bytes, `1abf`): `{u16 frac; i16 val; i32 step}` — `val:frac`
is a 16.16 value.

### 2.2 `4d6e:0076` `horizon_draw(u8 sky_base, u8 sea_col, u16 pitch, u16 roll, void far (*cb)())`

Called once per frame by `render_scene` (`5440:03aa`) with `(word DS:5BDB, word DS:5BDD, CS:0A1F,
CS:0A21, DS:5BDA ? 0 : 3E1D:002Ah)`; `3E1D:002A` is the stub of `6964:01a2` (§3.6). The world part's
call line (`render3d_world.md` §1.1: "cam_ang.heading?") should read: arguments = the two colours
(pushed as one dword `DS:5BDB`), camera pitch, camera roll, callback. Heading is not used.

```
DS:400E = sky_base; DS:400C = sea_col; DS:3FFC = cb; DS:26D8 = DS:26D2;
r = horizon_compute(-pitch, -roll);                  /* 4d6e:015c, §2.4 */
if (r == 1) { DS:400C = sky_base + 0Fh; DS:3FFA = 1; }        /* looking steeply up: all sky */
if (r == -1 && DS:3FFA) { if (cb) cb(); DS:3FFA = 0; }        /* steeply down: all sea */
if (r == -1 || r == 1) {
    DS:26CE = DS:26CD = (u8)DS:400C; DS:26CC = 1;
    gfx_rect(DS:26C4, DS:26C8, DS:26C6-DS:26C4+1, DS:26CA-DS:26C8+1);   /* 1d32:6ab0 */
    if (r == 1) { if (cb) cb(); DS:3FFA = 1; }
    return;
}
/* r == 0: the horizon crosses the view */
if (|DS:4008| > |DS:400A|) horizon_draw_flat();      /* 4d6e:03be: |cos r| > |sin r| */
else                        horizon_draw_steep();     /* 4d6e:0724 */
DS:3FFA = 1;
```
(`|v|` is the 16-bit `cwd/xor/sub` abs.) Quirk kept: in the all-sea case the callback is called
only on the first such frame (`DS:3FFA`) and its drawing is then covered by the fill; its side
effects (sun/moon screen flags `DS:111E/1128 & 40h`, §3.6) are what matters. The `r == 0` path does
not set `DS:26CC` itself (it relies on it being 1 from the library state; the span fills do not
use it).

### 2.3 `4d6e:0040` `horizon_reset()` / `4d6e:004b` `horizon_alloc()` / `4d6e:0000` `horizon_set_haze(v)`

* `0040` (from `4e0d:03e9`, mission start): `DS:3FFA = 1`.
* `004b` (from `sim_init 4e0d:0000`): `DS:0322 = 24b2:013d(780h, 0)` (far alloc, platform);
  returns 1 if non-NULL else 0.
* `0000(v)` (from the detail slider `4b9f:00d0`, sim_flow; `v` 0..FFh): `v < 55h` →
  `DS:031C = 0` (no bands; `031A/031E` unchanged); `v < AAh` → `031E = 2, 031A = 4, 031C = 7`; else
  `031E = 1, 031A = 2, 031C = 0Fh`.

### 2.4 `4d6e:015c` `horizon_compute(u16 p, u16 r)` → −1 / 0 / 1

`p = −pitch`, `r = −roll` (16-bit angles, render3d_math.md §1.1).
```
inverted = ((i16)p > 4000h || (i16)p < -4000h);        /* signed compares */
sp = sin16(p); cp = cos16(p);                            /* 277a:5e66 / 5e71 */
if (sp >= 3A98h)  return -1;                             /* 15000/16384: ~66.3° nose down */
if (sp <= -3A98h) return 1;                              /* ~66.3° nose up */
sr = sin16(r); cr = cos16(r);
DS:4002 = cr >> 6; DS:4006 = -(cr >> 6);
DS:4004 = sr >> 6; DS:4000 = -(sr >> 6);                 /* half-length 256 px (4000h>>6) */
d  = ldiv_sat((i32)sp << S, cp);                         /* 277a:3dc1; S = CS:0A49 (7) */
bx = (i16)(((i32)d * (i16)DS:4004) >> 8);
dx = (i16)(((i32)d * (i16)DS:4002) >> 8);
DS:4006 += bx; DS:4002 += bx; DS:4004 += dx; DS:4000 += dx;
DS:4006 += CS:0A4B; DS:4002 += CS:0A4B;                  /* cx */
DS:4004 = CS:0A4D - DS:4004; DS:4000 = CS:0A4D - DS:4000;   /* cy − … */
if (inverted) { DS:400A = -sr; DS:4008 =  cr; }
else          { DS:400A =  sr; DS:4008 = -cr; }
return 0;
```
So the segment is `(x0, y0) = (cx − c + d·s', cy − (s + d·c'))`, `(x1, y1) = (cx + c + d·s',
cy + s − d·c')` with `c = cr>>6`, `s = sr>>6` and `d = f·tan(−pitch)` (`d·s'`, `d·c'` the two `>>8`
products): the horizon passes `f·tan(pitch)` pixels below the screen centre along the roll-rotated
vertical, direction `(cos r, sin r)` on screen (y down). All adds are 16-bit.
The sky is on the side where `DS:4008 < 0` (upright: `cos r > 0`).

### 2.5 `4d6e:03be` `horizon_draw_flat()` — horizon closer to horizontal

Local: `L` = `DS:0322` as `i16[]`, `D` = the destination span buffer `DS:3172:0000`.
```
dx0 = DS:4002 - DS:4006; dyl = DS:4000 - DS:4004;               /* i32 */
yl = DS:4004 + (i16)(((i32)(DS:26C4 - DS:4006) * dyl) / dx0);   /* y at x = clip x0 */
yr = DS:4004 + (i16)(((i32)(DS:26C6 - DS:4006) * dyl) / dx0);   /* y at x = clip x1 */
dy = yr - yl;  m = max(|dy|, 16);  c = m + |dy|;
ymin = min(yl, yr), ymax = max(...)   (si = yl, di = yr if dy > 0 else si = yr, di = yl)
if (dy > 0) {   A = L;       B = L + m;   C = L + c;   E = L + m + c;        /* word offsets */
    fill_words(A, DS:26C4, m);                       /* 1abf:011d */
    dda_fill(C - dy, DS:26C4, DS:26C6, dy);          /* 1abf:00de: x from x0 to x1 over dy rows */
    fill_words(B + dy, DS:26C6, m);
} else {        B = L;       E = L + c;   A = L + m;   C = L + m + c;
    fill_words(B, DS:26C6, m);
    dda_fill(A, DS:26C6, DS:26C4, -dy);
    fill_words(A - dy, DS:26C4, m);
}
```
`L` now holds `X[k]`, the x where the horizon crosses row `ymin − m + k`, clamped to the window at
both ends, over `2m + |dy|` rows (at most 960 = the buffer size, since `|dy| ≤` window width 320).
`A/B/C/E` are the four views of it used as left/right edge arrays, shifted by rows.
```
y0 = si; y1 = di;                                    /* kept for the sea */
if (DS:0320) {
    dda_init(&t, ((i32)DS:031A << 14) / DS:4008,
                 ((i32)(DS:031C + 1) * DS:031A << 14) / DS:4008, DS:031C);   /* i32 idiv, low words */
    prev = 0;
    for (i = 0; i < DS:031C; i++) {
        cur = dda_step(&t); dl = cur - prev; prev = cur;     /* rows between bands (signed) */
        n = |dl| + |dy|;
        if (DS:4008 < 0) { si += dl; di += dl; }             /* sky above: move up first */
        DS:26CD = sky_base + i*DS:031E + (DS:031E >> 1);     /* 8-bit add */
        if (dy > 0) span_build_draw(si, seg(L), C - n, B, n, D);   /* 0a88:00cf (y, seg, left, right, n, dst) */
        else        span_build_draw(si, seg(L), A, E - n, n, D);
        if (DS:4008 > 0) { si += dl; di += dl; }             /* sky below: move after */
    }
}
DS:26CE = DS:26CD = sky_base + 0Fh;
horizon_fill_side(DS:4008 < 0, si, di, A, B, C, E, D);       /* 4d6e:029e: the rest of the sky */
if (DS:3FFC) DS:3FFC();                                      /* sun, moon, stars */
DS:26CE = DS:26CD = DS:400C;
horizon_fill_side(DS:4008 > 0, y0, y1, A, B, C, E, D);       /* the sea */
```
The band offsets are `k·spacing/|cos r|` rows (`dda` 16.16, first step `a`, see §2.8 for its
rounding). Band `i` covers the rows between the horizon shifted by `prev` and by `cur`, coloured
`base + i·step + step/2` (bands 0..14 → colours 70h..7Eh with the default 15 bands, 71h..7Dh odd
with 7 bands); the top of the sky is `base + 15`. With `DS:0320 = 0` the whole sky side is flat
`base + 15`.

### 2.6 `4d6e:029e` `horizon_fill_side(flag, ya, yb, far A, far B, far C, far E, far D)`

Fills one side of the (possibly band-shifted) line whose rows run `ya..yb`: `flag ≠ 0` = the side
above (smaller y), `flag = 0` = the side below. Colour = the current `DS:26CD/26CE`.
```
if (flag) {
    if (yb < DS:26C8) return;
    if (ya > DS:26CA) { gfx_rect(window); return; }
    if (ya >= DS:26C8) gfx_rect(DS:26C4, DS:26C8, w, ya - DS:26C8 + 1);   /* rows y0..ya */
    y = max(ya, DS:26C8); n = yb - y;
    span_build_draw(y, seg(A), C - n, E - n, n, D);        /* left = C[-n..], right = E[-n..] */
} else {
    if (ya > DS:26CA) return;
    if (yb < DS:26C8) { gfx_rect(window); return; }
    if (yb <= DS:26CA) gfx_rect(DS:26C4, yb, w, DS:26CA - yb + 1);        /* rows yb..y1 */
    n = yb - ya;
    span_build_draw(ya, seg(A), A, B, n, D);
}
```
(`w` = `DS:26C6 − DS:26C4 + 1`; row `ya` is drawn twice in the `flag` case — rect and first span —
harmless.) The span helper clips the rows to `DS:26C8..26CA`; x values come from the clamped
array, so no x clipping is needed.

### 2.7 `4d6e:0724` `horizon_draw_steep()` — horizon closer to vertical

Works directly on a span list in `L = DS:0322` covering every row of the window, moving one
edge at a time.
```
L.y0 = DS:26C8; L.n = H = DS:26CA - DS:26C8 + 1;
xa = lerp_map(DS:26C8, DS:4004, DS:4000, DS:4006, DS:4002);   /* 277a:41c4: x of the line at row y0 */
xb = lerp_map(DS:26CA, DS:4004, DS:4000, DS:4006, DS:4002);   /* at row y1 */
d = xb - xa; if (d <= 0) xa = xb;                             /* xa = min */
if (d > 0) dda_init(&t, 0, d, H); else dda_init(&t, -d, 0, H);
if (DS:400A < 0) { span_xl_from_dda(L, &t); span_add_xl(L, xa); }    /* 0a88:009a, 0030 */
else             { span_xr_from_dda(L, &t); span_add_xr(L, xa); }    /* 0a88:009f, 0035 */
acc = 0;
if (DS:0320) {
    dda_init(&t, ((i32)DS:031A << 14) / DS:400A,
                 ((i32)(DS:031C + 1) * DS:031A << 14) / DS:400A, DS:031C);
    prev = 0;
    for (i = 0; i < DS:031C; i++) {
        DS:26CD = sky_base + i*DS:031E + (DS:031E >> 1);
        cur = dda_step(&t); dl = cur - prev; prev = cur; acc -= dl;
        if (DS:400A < 0) { span_xr_from_xl(L); span_add_xl(L, dl); }  /* 0059, 0030 */
        else             { span_xl_from_xr(L); span_add_xr(L, dl); }  /* 007c, 0035 */
        span_clip_draw(L, D);                                         /* 0a88:0145 */
    }
}
DS:26CD = sky_base + 0Fh;
if (DS:400A < 0) { span_xr_from_xl(L); span_set_xl(L, DS:26C4); }    /* 0059, 000a */
else             { span_xl_from_xr(L); span_set_xr(L, DS:26C6); }    /* 007c, 000f */
span_clip_draw(L, D);                                                 /* rest of the sky */
if (DS:3FFC) DS:3FFC();
DS:26CD = DS:400C;
if (DS:400A < 0) { span_xl_from_xr(L); span_add_xl(L, acc); span_set_xr(L, DS:26C6); }
else             { span_xr_from_xl(L); span_add_xr(L, acc); span_set_xl(L, DS:26C4); }
span_clip_draw(L, D);                                                 /* the sea */
```
Band widths here are `spacing/|sin r|` pixels horizontally. The sea edge is recovered by adding
`acc = −Σdl` back to the last band edge (exact, integer). Only `DS:26CD` is set (spans only).

### 2.8 `1abf` DDA helpers (compiled C except `011d`)

* `1abf:0008` `dda_init(DDA *d, i16 a, i16 b, i16 n)`:
  ```
  d->val = a;
  if (n <= 0) { d->step = 0; d->frac = 0; return; }
  d->frac = 0;
  d->step = ((i32)b << 16) - ((i32)a << 16);          /* 16-bit sub/sbb on the high word */
  d->step = LDIV(d->step, (i32)n);                     /* Borland 0000:1d69, truncation */
  neg = d->step < 0; if (neg) d->step = -d->step;
  d->frac = ((d->step & 0xFFFF8000) == 0) ? 0x8000 : (u16)d->step;   /* quirk: kept */
  if (neg) d->step = -d->step;
  ```
  (For `|step| < 0.5` the start is rounded by +0.5; otherwise the start fraction is the low word of
  `|step|` — probably meant as a rounding bias; keep exactly.)
* `1abf:00c6` `dda_step(DDA *d)` → `old = d->val; (u32)(val:frac) += step; return old;`
* `1abf:00de` `dda_fill(i16 far *dst, a, b, u16 n)`: `if (n == 0) return; dda_init(&t, a, b, n);
  repeat n times { *dst++ = t.val; t += t.step; }` (`n` used unsigned by `loop`; callers pass n ≥ 0).
* `1abf:011d` `fill_words(i16 far *dst, i16 v, u16 n)` (asm, `[sp+4]` far dst, `[sp+8]` v, `[sp+0Ah]`
  n): `rep stosw` (preserves DI).

### 2.9 `0a88` span-list helpers (hand-written asm, far, stack arguments, caller pops)

`L` is a far pointer to a span list `{y0, n, n×{xl, xr}}`; each routine iterates `n = L[+2]`
entries (none if 0).

| Address | Name | Arguments | Effect per entry |
|---|---|---|---|
| `000a` | `span_set_xl` | `(L, v)` | `xl = v` |
| `000f` | `span_set_xr` | `(L, v)` | `xr = v` |
| `0030` | `span_add_xl` | `(L, v)` | `xl += v` |
| `0035` | `span_add_xr` | `(L, v)` | `xr += v` |
| `0059` | `span_xr_from_xl` | `(L)` | `xr = xl` |
| `007c` | `span_xl_from_xr` | `(L)` | `xl = xr` |
| `009a` | `span_xl_from_dda` | `(L, DDA near *d)` | `xl = d->val; d += step` (32-bit add/adc) |
| `009f` | `span_xr_from_dda` | `(L, DDA near *d)` | `xr = d->val; d += step` |

* `0a88:00cf` `span_build_draw(i16 y, u16 seg, u16 left_ofs, u16 right_ofs, i16 n, far D)` (C
  frame): clip rows: `if (y + n − 1 > DS:26CA) n −= y + n − 1 − DS:26CA`; `skip = (y < DS:26C8) ?
  DS:26C8 − y : 0`, `y = max(y, DS:26C8)`; `D.y0 = y` (written even if nothing follows);
  `n −= skip; if (n <= 0) return;` `D.n = n`; entry `k` = `{seg:left_ofs[skip+k],
  seg:right_ofs[skip+k]}` (i16 arrays); `gfx_poly_spans(D)` (`1d32:09a8`, driver entry 27 via
  `DS:3586` = `DS:351A + 4·27`).
* `0a88:0145` `span_clip_draw(far L, far D)`: x-clip against `DS:26C4..26C6`: rows entirely
  outside (`xl > x1 || xr < x0`) before the first inside row are skipped (`y0++`); the first outside
  row after an inside one ends the list; kept rows get `xl = max(xl, x0)`, `xr = min(xr, x1)`. If any
  row is kept: `D = {y0 & FFh, count (8-bit), rows}` and `gfx_poly_spans(D)`. (Both header words
  are written from 8-bit registers — `y0 < 256` and `count < 256` are assumed; true for 200 rows.)
  Rows with `xl > xr` are passed unchanged (the driver draws nothing for them, video spec).

-----------------------------------------------------------------------------------------------

## 3. Sun, moon, stars and time of day (`55e8` sky.c, `59eb` stars.c, `6964`, `4b91`, `1a9a`)

### 3.1 Data

| DS: | Type | Name | Meaning |
|---|---|---|---|
| `111E` | body | `sun` | `+0 u16 flags` (40h = on screen this frame), `+2 u16 time` (hour angle, **`DS:1120`**), `+4 i16 decl` (`DS:1122`), `+6 i16 sx`, `+8 i16 sy` (`DS:1124/1126`) |
| `1128` | body | `moon` | same layout: flags `1128` (40h on screen; 80h tested, never set in AP — **Unknown**), time `112A`, decl `112C`, `sx/sy` `112E/1130` |
| `1132` | i16[8] | `tod_times` | time of day per mission setting 0..7: `A000h, 7FFFh, 6AA8h, 6000h`, then **aliases** `113A` (sunrise, recomputed), `113C` = 2000h, `113E` = 0, `1140` (dusk, recomputed) |
| `113A` | u16 | `sunrise` | `4000h + t − 100h` (§3.3) |
| `1140` | u16 | `dusk` | `C000h − t + 1E38h` |
| `1142` | u16 | `sunset` | `C000h − t + 200h` |
| `1144` | i16[3] | `night_light` | light angles when neither body is up: `(4000h, 0, 0)` |
| `114A` | u16 | `moon_bmp` | handle of the loaded `moonN` BMP (0 = none) |
| `114C` | u8 | `night_sky` | stars/moon allowed (recomputed each sim step) |
| `114D` | i8[9][2] | `glare_taps` | sample offsets `(0,0) (7,0) (−7,0) (0,7) (0,−7) (4,4) (4,−4) (−4,−4) (−4,4)` |
| `51B2` | i16 | `sky_cy` | view centre y (from `644a:089f`) |
| `51B4` | i16 | `sky_cx` | `DS:51BA >> 1` (half the width; **not** + x0 — the rectangle from `644a:089f` always has x0 = 0) |
| `51B6` | i16[4] | `sky_rect` | view rectangle `x0, y0, w, h` (filled by `644a:089f`, sim_flow) |
| `51BE` | i16[3] | `sun_vec` | sun direction in the local world frame, 2.14 (x east, y north, z up) |
| `51C4` | u8 | `sky_detail` | stars and moon drawn (`4b9f:00d0`: detail slider ≥ 55h) |
| `51C5` | i32 | `sky_tick` | countdown for the clock (`1900h` per 4 angle units) |
| `51C9` | i16 | `day_rel` | days since the September equinox (with the month quirk, §3.2) |
| `51CD` | u16 | | 4th argument of `sky_init`; no reader (**dead**) |
| `51CF` | u16 | `latitude` | 16-bit angle |
| `51D1`,`51D3` | u16 | `dawn_lo`, `dawn_hi` | twilight ramp limits (distance from midnight) |
| `51D5`,`51D7` | i16 | `moon_h`, `moon_w` | size of the moon bitmap |
| `51D9` | i16[3] | `light_ang` | angles for `set_light` (`277a:0152(DS:51D9, DS:51DD)`, `51DB` always 0) |
| `51DF` | i16[3] | `moon_light_ang` | `(−(moon.time + 4000h), 0, moon.decl + C000h)` |
| `51E5` | i16[3] | `sun_light_ang` | `(−(sun.time + 4000h), 0, sun.decl + C000h)` |
| `5CE2`,`5CE4` | u16 | `star_rot0`, `star_rot` | sidereal rotation of the star field |
| `5CE6` | u16 | `star_n` | star count (267 in `STARS.DAT`) |
| `5CE8` | far | `stars` | star table, 6 bytes each |
| `44EC..44F4` | u16 | | copies `44EC` moon time, `44EE` moon decl, `44F2` sun time, `44F4` sun decl (written once by `sky_init`; readers: sim_flow/shell, not render) |
| `070E` | u32 | `epoch` | `0024D9B9h` = 2 415 033 (Julian day offset of the mission day count) |
| `0712` | i8[12] | `mdays` | 31, (Feb: 28/29 patched at `0713`), 31, 30, … (Jan at index 0) |
| `071E` | char[6] | | `"moon "` template (5th char replaced by the phase digit) |
| `0724` | i16[12] | `cumdays` | 0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334 (read as `W[0722 + 2m]`, see quirk) |
| `0214` | i8[13] | `mdays1` | month lengths with Jan at index 1 (`0216` = Feb patched) |

**STARS.DAT** (`SIM1`, 1602 bytes = 267 records): `{u16 flags; u16 ra; i16 dec}`; flags bit 0 selects
colour 8Eh (else 8Dh), bit 80h = "skip" (cleared by `stars_set_time`, never set — **Unknown** who
would set it), `ra`/`dec` 16-bit angles (dec mostly negative: southern-sky stars).

### 3.2 `55e8:00c4` `sky_init(u16 day, i16 tod, u16 lat, u16 unused)` (sky.c, once per mission)

Called by `4e0d:03e9` (sim_flow) with `(DS:4787, (i8)DS:4789, DS:478D, DS:478B)` — the mission
date, time-of-day setting, latitude and one unused word (sim_flow owns their source).
```
date = sky_day_to_date(day);                     /* 55e8:0028 → {month0, day, year8} */
DS:114C = (tod > 3);
DS:51C9 = sky_day_of_year(date.month, date.day); /* 55e8:028f */
a = sky_day_to_angle(DS:51C9);                   /* 55e8:02a3: ×179 (65536/366), 16-bit */
DS:1122 = DS:44F4 = mul_sin(-4282, a);           /* 277a:4eb6: declination, ±23.5° */
t = mul_sin(mul_sin(4868, a), lat);              /* day-length term (±26.7° × sin lat) */
DS:1142 = C000h - t;  DS:1140 = DS:1142 + 1E38h;
DS:113A = t + 4000h;  DS:51D3 = DS:113A + 190h;  DS:51D1 = DS:51D3 - 640h;
DS:1142 += 200h;      DS:113A -= 100h;
DS:1120 = DS:44F2 = DS:1132[tod];                /* tod 4..7 alias 113A/113C/113E/1140 */
DS:112C = DS:44EE = DS:1122;                     /* moon declination = sun's */
DS:112A = moon_phase_from_date(&date) + DS:1132[tod];   /* 4b91:0000 */
DS:44EC = DS:112A;
ph = DS:112A - DS:1120;
k  = (|ph| < 1555h) ? 0 : ph / 1999h;  if (k < 0) k += 10;       /* 16-bit signed */
if (k) {                                         /* moon shown only away from new moon */
    name = "moon" + ('0' + k);                   /* "moon1".."moon9" */
    DS:114A = 7229:01aa(55a4:0000(name, "BMP"));  /* BMP loader (video) */
    if (!DS:114A) fatal(sky.c, line FBh, name);   /* 2494:0127 */
    DS:51D7 = (*DS:114A)[+6]; DS:51D5 = (*DS:114A)[+8];   /* width, height */
}
DS:51CF = lat; DS:51CD = unused;
stars_set_time(DS:1120);                         /* 59eb:0097 */
sky_update();                                    /* 6964:0076 */
```
Units: time angles `10000h` = 24 h, `0` = midnight, `8000h` = noon (from `sky_is_day`: day between
`113A` and `1142`); `tod_times` 0..3 are therefore 15:00, 12:00, 10:00, 09:00 (**Likely** — the
clock runs backwards, see §3.4, so the labels are for sim_flow to confirm), 4 = dawn, 5 = 03:00,
6 = midnight, 7 = dusk.

* `55e8:0028` `sky_day_to_date(u16 day, u8 far *out)` → `out`:
  `X = (i32)day + DS:070E; q = (i16)((X << 2) / 1461); d = (i16)X − (i16)(q·365) − (q − 1)/4; if (X <=
  365) d++; DS:0713 = (q % 4 == 0) ? 29 : 28; m = 0; while (d > 0) d −= mdays[m++]; m−−;`
  `out[0] = m` (0-based month), `out[1] = d + mdays[m]`, `out[2] = (u8)q + 2Ch` (year byte, 0 in
  1900: `q` counts years since 4712 BC).
* `55e8:028f` `sky_day_of_year(m, d)` = `W[DS:0722 + 2m] + d − 108h`. **Quirk (keep):** `m` is
  0-based but the table has January at `0724`, so January reads the string bytes `" \0"` (32) and
  every other month uses the previous month's offset: the equinox reference is shifted by one month.
* `55e8:02a3` `sky_day_to_angle(v)` = `(i16)(v · B3h)`.
* `55e8:000a` `sky_free_moon()` (from `4e0d:058e`, mission end): `if (DS:114A) 7229:056a(DS:114A)`;
  `DS:114A = 0`.
* `55e8:0000` `sky_load_stars()` = `stars_load()` (no callers).

### 3.3 `4b91` moon phase

* `4b91:0000` `moon_phase_from_date(u8 *date)`: `Y = (i8)date[2] + 1268h; DS:0216 = (Y % 4 == 0) ?
  29 : 28; D = (i8)date[1]; for (i = 1; i < (i8)date[0]; i++) D += mdays1[i];` (**same one-month
  quirk**: 0-based month against a 1-based table) `J = (i32)Y·365 + D + (Y − 1)/4; if (Y == 0) J−−;`
  return `moon_phase_angle(J − 2415033)`.
* `4b91:008d` `moon_phase_angle(i32 x)`: `r = (i32)(x << 14) % 6ECCCh` (32-bit wrap of the shift,
  `idiv` remainder, sign of the dividend); `days = r >> 14`; return `(i16)(days · 93Fh)`.
  (Period 6ECCCh/4000h ≈ 27.7 days, 93Fh ≈ 65536/27.7; with the year formula `x` is large and
  negative and the shift wraps — the result is still deterministic; the port must use exact i32
  wraparound.)

### 3.4 `6964:0076` `sky_update()` (per sim step, `5440:1317`; also from `sky_init`)

```
DS:51C5 -= DS:711E;                                    /* dt (sim_flow time base) */
if (DS:51C5 <= 0) { DS:1120 -= 4; DS:112A -= 4; DS:5CE4 -= 4; DS:51C5 += 1900h; }
DS:114C = (|DS:1120| > DS:51D3) ? 0 : 1;               /* signed abs, 8000h stays negative → 1 */
DS:51E5 = -(DS:1120 + 4000h); DS:51E7 = 0; DS:51E9 = DS:1122 + C000h;
DS:51DF = -(DS:112A + 4000h); DS:51E1 = 0; DS:51E3 = DS:112C + C000h;
sky_select_light();                                    /* 6964:05d2 */
v = sky_angles_to_vec({DS:1122, DS:1120});             /* 1a9a:01da */
DS:51BE = v.x;
DS:51C0 = (cos16(-lat)·v.y + sin16(-lat)·v.z) >> 14;   /* i32, lat = DS:51CF */
DS:51C2 = (cos16(-lat)·v.z - sin16(-lat)·v.y) >> 14;
```
The clock advances by −4 every 1900h dt units (the time value decreases). The clock belongs to
the simulation (hand-off) but lives here.

* `6964:0000` `sky_advance_time(i16 n)` (skip-ahead, `496a:170e`): `v = (i32)n << 8; if (v <
  DS:51C5) { DS:51C5 −= (i16)v; return; }` (the low word sign-extended) else `k = ldiv_sat(v −
  DS:51C5, 1900h); d = 4k + 4; DS:1120 −= d; DS:112A −= d; DS:5CE4 −= d; DS:51C5 = 1900h` (the
  remainder is dropped — quirk).
* `6964:05a3` `sky_is_day(u16 m)`: `DS:113A − m < DS:1120 <= DS:1142 + m` (unsigned) → 1.
* `6964:05d2` `sky_select_light()`: `sky_is_day(1000h)` → `DS:51D9..51DD = sun_light_ang`; else if
  `4000h < DS:112A < C000h` (unsigned) → `moon_light_ang`; else `DS:1144..1148`.
* `6964:005b` → `&DS:51BE` if `sky_is_day(800h)` else 0 (caller `583c:0471`, sim_world spotting).
* `6964:0633` → `&DS:51E5` if `sky_is_day(800h)` else 0 (caller `490a:017f`, sim_world).
* `6964:059b` → `DS:1120` (no callers).
* `6964:064d` `sky_daylight_lerp(i16 day_v, i16 night_v)`: `t = |DS:1120|` (8000h → 7FFFh);
  `t > DS:51D3` → `day_v`; `t < DS:51D1` → `night_v`; else `day_v + ldiv_sat((i32)|t − DS:51D3| ·
  (night_v − day_v), 640h)`.

### 3.5 `1a9a:01da` `sky_angles_to_vec(i16 out[3], u16 ang[2])` → `out`

`ang[0]` = declination, `ang[1]` = time. `ang[0] ≠ 0`: `c = cos16(ang[0]); out = (mul_sin(−c,
ang[1]), sin16(ang[0]), mul_cos(−c, ang[1]))`; else `out = (−sin16(ang[1]), 0, −cos16(ang[1]))`
(same values). The result is in the equatorial frame (y = celestial pole); callers rotate it by
the latitude about x as in §3.4.

### 3.6 `6964:01a2` `sky_draw_callback()` — the horizon callback (via stub `3E1D:002A`)

```
DS:51B2 = 644a:089f(&DS:51B6);                   /* sim_flow: view rectangle, returns cy */
DS:51B4 = DS:51BA >> 1;
DS:26C3 = 1; DS:26C4 = x0; DS:26C6 = x0 + w - 1; DS:26C8 = y0; DS:26CA = y0 + h - 1;
4899:0027();                                     /* sim_flow: clip bottom to the panel line */
DS:26D8 = DS:26D2;
if (DS:51C4) stars_draw();                       /* 1a9a:000a */
sky_project_body(1);  sky_project_body(0);       /* 6964:0298: sun, then moon */
if (DS:111E & 40h) { DS:26CD = DS:26CE = 8Ch; gfx_circle(7, DS:1124, DS:1126); }   /* 1d32:6bbc, filled */
if (DS:114C && DS:51C4 && DS:114A && (DS:1128 & 40h) && !(DS:1128 & 80h)) {
    if (CS:0A21)  gfx_sprite_rotated(*DS:114A, DS:112E, DS:1130, -CS:0A21, DS:51D7, DS:51D5, 0L);  /* 1d32:5e5b */
    else          gfx_sprite_flip(*DS:114A, DS:112E, DS:1130, 0);                                /* 1d32:3de5 */
}
```
The moon bitmap is placed with its top-left at the projected point (library convention) and
rotated by the camera roll. (`gfx_circle` draws with the aspect 9/8 of the library.)

### 3.7 `6964:0298` `sky_project_body(u8 sun)`

```
b = sun ? &DS:111E : &DS:1128;  b->flags &= ~40h;
M = copy of CS:09B6 (camera matrix, world→eye, 19 bytes);
v = sky_angles_to_vec({b->decl, b->time}); rotate v by −lat about x (as §3.4);
e = vec_rotate(v, M);                            /* 277a:4ae5 */
if ((1 << S) >= e.y) return;                     /* S = CS:0A49 */
sx = ldiv_sat((i32)e.x << S,  e.y) + DS:51B4;    /* i32 compares below */
sy = ldiv_sat((i32)e.z << S, -e.y) + DS:51B2;
if (DS:51B6 - 7 < sx < DS:51B6 + DS:51BA && DS:51B8 - 7 < sy < DS:51B8 + DS:51BC)
    { b->sx = sx; b->sy = sy; b->flags |= 40h; }
```
(Perspective projection of a unit vector, same as objects; −7 margin on the left/top only.)

### 3.8 `1a9a:000a` `stars_draw()`

```
if (!DS:114C) return;
f = 1 << S; M = copy of CS:09B6;
for (i = 0; i < DS:5CE6; i++) {  s = &stars[i];
    if (s->flags & 80h) continue;
    v = sky_angles_to_vec({s->dec, s->ra + DS:5CE4}); rotate by −lat about x;
    e = vec_rotate(v, M);
    if (e.y <= f) continue;
    sy = (i16)atan2_16(e.y, -e.z) / 75 + DS:51B2;       /* 277a:6228, signed idiv */
    if (!(DS:51B8 < sy < DS:51B8 + DS:51BC)) continue;
    sx = (i16)atan2_16(e.y,  e.x) / 64 + DS:51B4;
    if (!(DS:51B6 < sx < DS:51B6 + DS:51BA)) continue;
    gfx_put_pixel(sx, sy, 8Dh + (s->flags & 1));        /* 1d32:6a5b */
}
```
Stars use an **angular** projection (1024 px per turn horizontally, 873.8 px per turn vertically),
not the perspective one used for the sun/moon — their positions do not match the sun's scale
off-centre; keep.

### 3.9 `59eb` stars.c

* `59eb:0000` `stars_load()` (from `sim_init`): `fp = fopen(55a4:0000("STARS", "DAT"), "rb")`,
  fatal (stars.c line 49h) if NULL; `DS:5CE6 = filelength(fp) / 6` (`0000:0bba`, unsigned);
  `DS:5CE8 = 24b2:013d(n·6, 0)`; `55a4:0108(DS:5CE8, n·6, fp)` (read); `fclose`.
* `59eb:0097` `stars_set_time(u16 t)`: `DS:5CE4 = DS:5CE2 = t + DS:51C9·B3h`; clear bit 80h of
  every star.

### 3.10 `6964:0458` `sky_sun_glare()` → 0..4000h (called by `palfx_frame`)

```
if (!(DS:111E & 40h)) return 0;
if (DS:1120 > DS:1142 && DS:1120 < DS:113A) return 0;    /* unsigned; see note */
cx = DS:51B6 + DS:51BA/2; cy = DS:51B8 + DS:51BC/2;       /* /2 truncating toward 0 */
ax = |DS:1124 - cx|; ay = |DS:1126 - cy|;
dist = max + (min >> 2) + (min >> 3);                     /* octagonal distance */
g = 3000h - ldiv_sat((i32)dist * 3000h, 50h);             /* full at the centre, 0 at 80 px */
w = sky_daylight_lerp(4000h, E000h); if (w <= 0) w = 0;
g = (i16)(((i32)g * w) >> 14);
DS:26D6 = DS:26D2; hidden = 9;
for (k = 0; k < 9; k++)
    if (gfx_get_pixel(DS:1124 + glare_taps[k].x, DS:1126 + glare_taps[k].y) == 8Ch) hidden--;
g -= ldiv_sat((i32)hidden << 12, 9);
return clamp(g, 0, 4000h);                                /* 35ff:0009 */
```
Note on the night test (**Verified**: `cmp dx,[1142]; jbe go; cmp dx,[113A]; jae go; return 0`):
with the normal `DS:113A < DS:1142` the condition can never hold, so the test never returns 0;
at night the glare is removed by the `sky_daylight_lerp(4000h, E000h)` weight instead (≤ 0 →
0). The pixel test reads the page being drawn (the sun disc is 8Ch): terrain, sea or aircraft
covering the disc reduce the glare.

-----------------------------------------------------------------------------------------------

## 4. Shadows, ground dots, gun flashes (effect-record producers)

Records go to the effect pool `05a9:005a(tmpl)` (48-byte template, `render3d_world.md` §3): fields
written here: `+00 u16 type` (80Bh shadow, 80Ch smoke/flash with callback, 80Eh flash), `+02 u16
shape`, `+04 i32[3] pos`, `+10 i16[3] angles`, `+16 u16 state/frame`, `+18 far update callback`,
`+1C u16 range (<<10)`, `+1E u8`, `+20 u16 owner`, `+22 i16[3] velocity`, `+28 u16`, `+2A u16 radius`
(`1560:06e9` uses `+2A` as the draw radius).

### 4.1 `1a8b` aircraft shadows

| DS: | Name | Init (`1a8b:0004`, sim_init) | Set by `1a8b:001e(v)` (detail slider `4b9f`, sim_flow) |
|---|---|---|---|
| `5CE0` | `shadow_mode` (0 = off; also the LOD cap for type 0Bh in `5440:0269`) | 2 | `v > 13 ? 3 : 0` |
| `5CDE` | `shadow_range` (record `+1C`) | 10 | `v` |
| `5CDA` | `shadow_max_alt` (i32) | 3000 | `v · 300` |

`1a8b:004c` `shadows_queue()` (frame, `5440:018c`): if `DS:5CE0 == 0` return; template zeroed,
`type = 80Bh`, `+1C = DS:5CDE`, `+1E = C8h`; for each `o` in `DS:475B[0..DS:4776)` (aircraft list):
if `637f:002b(o)` (alive, sim_world) and `o->z (+0Ch, i32) < DS:5CDA` and `shadow_pos(&o->pos,
&tmpl.pos)` (`2ecb:0007`, render3d_shapes.md §3.4): `+02 = o[+2]` (the aircraft's own shape),
`+10..+17 = o[+10..+17]` (angles + 1 word), `05a9:005a(&tmpl)`. The shadow colour: see shapes part
(`DS:2402`, open there).

### 4.2 `675d:0000` `ground_dots_draw()` — ground-speed dots (the `DS:36D0` callback)

Installed by `render_scene` as `DS:36D0 = 3E07:0020` (stub → `675d:0000`) and called by
`scene_draw` after the ground layer, before the sorted objects.
```
f = 1 << S (camera+0); eye = camera->eye;
if (eye.z (i32) > 4000) return;
cy = 644a:089f(&r); cx = r.w >> 1; (xmin, xmax, ymin, ymax) = (r.x0, r.x0 + r.w, r.y0, r.y0 + r.h);
DS:26D6 = DS:26D8 = DS:26D2;
P = (-(eye.x_lo & 3FFh), -(eye.y_lo & 3FFh), -eye.z_lo);         /* i16, 1024-unit grid */
U = P + (400h, 0, 0); V = P + (0, 400h, 0);
P = vec_rotate(P, M); U = vec_rotate(U, M) - P; V = vec_rotate(V, M) - P;   /* M = CS:09B6 copy */
if (U.y > 0) U = -U;  if (V.y > 0) V = -V;                          /* step toward the viewer */
P -= (U + V) << 2;                                                  /* per component, i16 */
for (i = 0; i < 9; i++, P = row + U) { row = P;
    for (j = 0; j < 9; j++, P += V) {
        if (P.y <= f) continue;
        sx = cx + ldiv_sat((i32)P.x << S, P.y); if (!(xmin < sx < xmax)) continue;
        sy = cy - ldiv_sat((i32)P.z << S, P.y); if (!(ymin < sy < ymax)) continue;
        c = gfx_get_pixel(sx, sy); if (c > 87h) continue;          /* signed compare */
        gfx_put_pixel(sx, sy, (i8)DS:102E[c]);
    }
}
```
A 9×9 grid of world points (z = 0, 1024 units apart, locked to world multiples of 1024) around
the eye, drawn as recoloured pixels. `DS:102E` (136 bytes, `0..87h` → dot colour): `0Ah×8, 06h×8,
48h×12, 3Ah×12, 1Fh×24, 10h×12, 1Bh×8, 3Fh×5, 2Bh×7, 39h×4, 5Bh×4, 3Dh×4, 27h×4, 4Bh×16, 50h×8`
(the sea 80h..87h → 50h). Copy from the image.

### 4.3 `655d:038a` `gun_flash_queue()` — muzzle flashes and gun smoke

Frame routine (`5440:018c`). Template zeroed, `type = 80Eh`, `+1C = 80h`, `+1E = 0`. For each
object `a = DS:00BC[n]`, `n < DS:00BE`, with `637f:002b(a)`: `G = a[+2Ah]` (gun state), `K =
a[+28h]` (gun set description), `ai = (a[+18h].b == 0)`; per gun `i` while `(K[0] & 0Fh) > i`, with
walking pointers `p22 = K + 10h + 10i`, `p1e = p22 + 8`, `p24 = K + 4 + 8i`, `p26 = G[+4] + 2i`
(i16), `p28 = G[+6] + i` (u8 frame counter), `T = &DS:5178[((K[0] >> 8) & 3) · 8]` (4 words):
```
shape = 0; ang = *(i16[3] *)DS:3716; tmpl.+18 = 0;
if (!ai) {                                           /* a[+18h] != 0 */
    if (G[0] == 400h) {                              /* one class of gun set */
        if (!(K[0] & 8000h)) {
            if (((K[0] & 0Fh) >> 1) == i) { shape = DS:474D+16h; tmpl.+2A = T[3]; }
            else                          { shape = DS:474D+17h; tmpl.+2A = T[2]; }
        }
    } else if (*p26 >= 500) {
        shape = DS:474D + ((p24[+6] & 40h) ? 16h : 15h); type = 80Eh; tmpl.+2A = T[0];
    }
    ofs = p24[0..2];
} else {                                             /* a[+18h] == 0 */
    big = 0; near = 0;
    if (DS:3B09 == a) {                               /* the player */
        if (i == 0)       { big = a[+A4h] < 20Ch; near = a[+A4h] < 7Ch; }
        else if (i == 1 && ((K[0] & F00h) >> 8) == 2) { big = a[+A6h] < 20Ch; near = a[+A6h] < 7Ch; }
    }
    if (*p26 < 500 && !big) goto emit;
    if (!362b:0165(p22 + 6)) {                        /* timer expired (sim_flow time base) */
        shape = DS:474D+1Bh; tmpl.+18 = 3DFF:0061 (→ 655d:1bb7, smoke update, sim_world);
        tmpl.+22.. = ((i32)a[+70h..74h] << 7) >> 8;  /* half the velocity */
        tmpl.+28 = DS:515A;
        p22[+6] = (1889:005f(DS:43DE) & 3Fh) + C8h;  /* next puff delay (RNG, sim_flow) */
        type = 80Ch; ofs = p22[0..2]; ofs.y += K[+0Eh];
    }
    if (*p26 < 900 && !near) goto emit;
    if (shape) {                                      /* emit the smoke puff now */
        ofs.y -= 100h;
        tmpl.pos = a->pos + vec_rotate(ofs, obj_matrix(a[+20h]));   /* 365a:000c, 277a:530c */
        if (!(p1e[0] & 10h)) { *p28 = 0; p1e[0] |= 10h; }
        e = 05a9:005a(&tmpl); if (e) { e[+20h] = a; e[+16h] = *p28 & 3; }
        tmpl.+18 = 0;
    }
    shape = DS:474D + ((p1e[0] & 80h) ? 1Ah : 19h); type = 80Ch;
    ang = a[+10h..14h]; ang[0] -= 4000h;
    ofs = p22[0..2]; ofs.y += K[+0Eh];
}
emit:
if (!shape) continue;
if (ai && a == DS:3B09) { v = 1c30:0780(); if (v <= 5 && v != 1) continue; }  /* own flashes hidden in cockpit views */
tmpl.pos = a->pos + vec_rotate(ofs, obj_matrix(a[+20h]));
c = ++*p28;
if (c >= 271b:043d(shape, 0) - 1) {                  /* frame count of the effect shape */
    *p28 = 0;
    if (shape == DS:474D+19h) { p1e[0] |= 80h; shape++; }
    else if (shape == DS:474D+15h) { p24[+6] |= 40h; shape++; }
}
e = 05a9:005a(&tmpl); if (e) { e[+20h] = a; e[+12h] = 0; e[+16h] = *p28; }
```
(`ang` goes to `+10`, `shape` to `+02`, `type` to `+00`.) The field meanings of the gun records
(`a[+28h]`, `a[+2Ah]`, `a[+A4h]`, `DS:5178`, the `400h` class) are sim_world's (guns, `655d`);
the effect shapes `DS:474D + 15h..1Bh` are `.BMD` sets (render3d_shapes.md §4). **Likely** in the
meaning of each branch (gun fire vs overheating smoke); the arithmetic above is **Verified**.

-----------------------------------------------------------------------------------------------

## 5. Palette effect channels (`1792`, `17ce`, paltrick.c `51b4`, `51a8`)

### 5.1 What it is

The sim does not remap colours per polygon for lighting: day/night, cloud shadow, whiteout in
clouds, sun glare, blackout/redout and flashes are done by **blending palette ranges toward a
target colour**, recomputing the 256-colour palette from the base palette whenever a channel level
changes, and queuing a DAC upload. The channels come from `PAL_MAPS.DAT` ("pal_maps" `DAT`, 13
records × 37 bytes, `SIM1`). There are no colour **remap tables** in this part: nothing in AP writes
the camera's remap pointer `camera+14h` (`271b:0251` initialises it to 0; `5440:009c` sets only
`+12h` and the window) — so `CS:21EE` stays 0 (**Likely**: no store found in the decompile or the
xref; the polygon code's remap path is dead in AP).

### 5.2 Data

`DS:5BD8` = near pointer to the channel block (allocated by `51a8:0000`, `n·25h + 3ACh` bytes):

| Off | Type | Meaning |
|---|---|---|
| `+000` | i16 | `n` capacity (13) |
| `+002` | i16 | `used` = highest loaded index + 1 |
| `+004` | far | source palette (`DS:408A`, the mission base palette, 768 bytes of 6-bit RGB; sim_flow) |
| `+008` | u8[768] | working palette (uploaded to the DAC) |
| `+308..+386` | i8[127] | step table `T[−63..63]` at `+347` (§5.8) |
| `+387 + 25h·i` | chan | channel `i` (37 bytes, the file record) |

Channel record (`PAL_MAPS.DAT` layout, **Verified** against the reader `1792:00c0`):

| Off | Type | Meaning |
|---|---|---|
| `00` | u16[6][2] | colour ranges `{first, last}` (inclusive); the list ends at the first `last == 0` |
| `18` | u8 | target kind: ≠0 = literal RGB at `19..1B`; 0 = palette index (u16 at `19`) in the **working** palette |
| `19` | u8[3] / u16 | target |
| `1C` | i16 | goal level (8.8; the integer part 0..64 is the blend weight /64) |
| `1E` | u16 | rise rate (per nominal step, dt-scaled; 0 = jump) |
| `20` | u16 | fall rate |
| `22` | u8 | active |
| `23` | i16 | current level (8.8) |

The 13 channels (file values; goals/actives set at run time by `17ce`, `51b4:0088`, sim code):

| # | Ranges | Target | Rates up/down | Use (set by) |
|---|---|---|---|---|
| 0 | 0–6Fh, 80–87h | black | 0/0 | night darkening of the world (`17ce`: goal = night level 0..2280h) |
| 1 | 70–7Fh | RGB(6,20,24) | 0/0 | night sky, no clouds (`17ce`) |
| 2 | 71–7Fh | RGB(6,20,24) | 0/0 | night sky, clouds on (`17ce`) |
| 3 | 70h | black | 0/0 | overcast colour at night, clouds on (`17ce`) |
| 4 | D0–FDh | black | 0/0 | cockpit at night (half the night level) |
| 5 | 1–8Eh, A2–AFh | colour 15 | 0/0 | whiteout inside the cloud layer (`17ce`) |
| 6 | 1–8Eh, A2–AFh | colour 15 | 0C1Ch/08FCh, goal 3F00h | cloud flash when `DS:5BE5` changes, clouds off path (`17ce`) |
| 7 | 0–8Eh, 90–AFh, D0–FDh | black | 0320h/0320h | cloud shadow when the sun is hidden (`17ce`, goal 1000h) |
| 8 | 0–8Eh, 90–AFh, D0–FDh | RGB(63,63,0) | 0/0 | sun glare (`17ce`, goal = `sky_sun_glare()`) |
| 9 | 8D–8Eh | colour 127 | 0/0 | stars fade into the day sky (goal = day fraction) |
| 10 | 88–8Bh | colour 127 | 0/0 | same for 88h–8Bh (goal = day fraction) |
| 11 | 0–8Eh, 90–AFh, D0–FDh | black | 0/0 | blackout (goal = `DS:5798`, `0fd4` G load, sim_world) |
| 12 | 1–8Eh, 90–AFh, D0–FDh | RGB(60,0,0) | 04B0h/044Ch | red flash (`655d:159d`, sim_world: goal 4000h/keep/off) |

Other globals: `DS:1910` last `k` of the step table; `DS:5BDA` `sky_no_sun` (1 = no horizon
callback); `DS:5BDB` sky base colour; `DS:5BDD` sea colour; `DS:5BDF` previous sun-hidden flag;
`DS:5BE0` previous `DS:5BE5`; `DS:5BE1` `cloud_zone` (0 below, 1 inside, 2 above the layer; read by
sim_flow/VCR); `DS:5BE3` cloud-shadow goal; `DS:5BE5` in-cloud flag (written by `0802:0173`,
render3d_world.md §2.8); `DS:5BE6` previous night level (FFFFh = force); `DS:5BE8` previous
clouds flag.

### 5.3 `51b4:0000` `paltrick_load()` (paltrick.c, from `sim_init`)

`palfx_alloc(13, DS:408A)`; `fp = fopen(55a4:0000("pal_maps", "DAT"), "rb")`, fatal (paltrick.c
line 55h) if NULL; 13 × { `fread(rec, 25h, 1, fp)`; `palfx_load_channel(rec, i)` }; `fclose`.

* `51a8:0000` `palfx_alloc(i16 n, far src)`: `DS:5BD8 = 24d3:0059(n·25h + 3ACh)` (near alloc,
  platform), zero it, `[+0] = n`, `[+4] = src`.
* `51a8:004e` `palfx_load_channel(rec *r, i16 i)` → 0 if `i >= n`; else `used = max(used, i + 1)`,
  copy 37 bytes to channel `i`, `active = 0`, `level = 0`; → 1.

### 5.4 `51b4:0088` `paltrick_reset()` (from `4e0d:03e9`, mission start)

`palfx_set_channel` calls in order `(0,0,0) (9,1,4000h) (10,1,3800h) (5,0,0) (6,0,keep) (7,0,keep)
(8,0,0) (11,0,0) (12,0,keep)`; `palfx_reset_levels()`; `DS:5BDA = 0; DS:5BDD = 80h; DS:5BDB = 70h;
DS:0320 = 1; DS:5BE3 = 0; DS:5BE1 = 2; DS:5BE0 = 0; DS:5BDF = 0; DS:5BE5 = 0; DS:5BE8 = FFh;
DS:5BE6 = FFFFh; DS:5798 = 0` (the last one is sim_world's blackout level).

### 5.5 `1792` small functions

* `0000` `palfx_get_level(i)` → `chan[i].level` (caller `490a:0509`, sim_world).
* `0021` `palfx_set_source(far p)` → `[+4] = p` (no callers).
* `0032` `palfx_set_channel(i, u8 active, i16 goal)`: `if (goal != −1) { chan[i].goal = goal; if
  (goal == 0) active = 0; }` `chan[i].active = active`.
* `0066` `palfx_upload_base()` (from `5440:083a`, the "clouds" loading screen, sim_flow): copy the
  768-byte source to the working palette, `5440:07bd(&work, 0, 100h)`.
* `009b` `palfx_reset_levels()`: `level = 0` for channels `0..used−1`.

### 5.6 `1792:00c0` `palfx_update(u8 force)` (from `17ce:0013`, cockpit `644a:0913/0962`, map `6cdc:0e0b`)

```
_fmemcpy(work, src, 768);                                       /* 0000:4abb */
changed = 0;
for (i = 0; i < used; i++) { c = &chan[i]; old = c->level >> 8;
    if (c->active) {
        if (c->level < c->goal) {
            if (!c->rise) c->level = c->goal;
            else { c->level += dtscale(c->rise); if (c->level > c->goal) c->level = c->goal; }
        } else if (c->level > c->goal) {
            if (!c->fall) c->level = c->goal;
            else { c->level -= dtscale(c->fall); if (c->level < c->goal) c->level = c->goal; }
        }
    } else if (c->level != 0) {
        if (!c->fall) c->level = 0;
        else { c->level -= dtscale(c->fall); if (c->level < 0) c->level = 0; }   /* jge on the sub flags */
    }
    if ((c->level >> 8) != old) changed = 1;
}
if (!changed && !force) return;
for (i = 0; i < used; i++) { c = &chan[i];
    tgt = c->kind ? &c->rgb : &work[3 * c->index];
    for (j = 0; j < 6 && c->range[j].last != 0; j++)
        palfx_blend_range(work, tgt, c->range[j].first, c->range[j].last, c->level >> 8);   /* 1792:0286 */
}
5440:07bd(work, 0, 100h);                                       /* queue DAC upload, sim_flow */
```
`dtscale(x)` = `362b:00be(x)` = `x·dt >> 8` (sim_flow time base). All comparisons signed 16-bit.
Channels are applied in index order onto the same working palette (later channels blend the
already-blended colours; a palette-index target reads the working palette at that moment).
Note that the upload is requested every call when anything moved, even by less than one step.
When a request is already pending `5440:07bd` returns 0 and the new palette is **not** queued
(the next change will be).

### 5.7 `1792:0286` `palfx_blend_range(u8 *pal, u8 *rgb, i16 first, i16 last, i16 k)`

```
if (k == 0) return;
if (DS:1910 != k) { DS:1910 = k; palfx_build_step_table(k); }
for (i = first; i <= last; i++) for (ch = 0; ch < 3; ch++) {
    p = &pal[3*i + ch];
    *p += T[rgb[ch] - (i8)*p];               /* u8 target, signed byte current; 8-bit add */
    *p = clamp((i8)*p, 0, 3Fh);
}
```

### 5.8 `1792:038a` `palfx_build_step_table(k)` (near; `inc bp` frame marker, `ret`)

`for (c = 1, s = 0; c < 64; c++, s += k) { T[c] = (i8)(s >> 6); T[−c] = −T[c]; }` — i.e. `T[c] =
((c − 1)·k) >> 6`; `T[0]` stays 0 (zeroed at allocation). **Quirk (keep):** the `c − 1` makes a
full-strength channel (k = 64) stop one step short of the target. The index lists `038a` (1 byte,
the `inc bp`) and `038b` separately; they are this one routine.

### 5.9 `17ce:0013` `palfx_frame()` (frame, `5440:018c`; also `5cde:0080`, `6cdc:0e0b`)

```
alt = camera->eye.z (i32); fog = 0; in_cloud = 0;
palfx_set_channel(11, 1, DS:5798);                          /* blackout */
if (DS:5BE8 != DS:42C9) {                                   /* clouds option changed */
    DS:5BE8 = DS:42C9;
    if (!DS:42C9) { DS:5BDA = 0; DS:5BDD = 80h; DS:5BDB = 70h; DS:0320 = 1; palfx_set_channel(5,0,0); }
    DS:5BE6 = FFFFh;
}
n = sky_daylight_lerp(0, 2280h);                            /* night level */
if (n != DS:5BE6) {
    q = ldiv_sat((i32)n << 14, 2280h);                      /* night fraction 0..4000h */
    day = 4000h - q; if (day < 0) day = 0;
    palfx_set_channel(0, 1, n); palfx_set_channel(4, 1, n >> 1);
    palfx_set_channel(9, 1, day); palfx_set_channel(10, 1, day);
    if (clouds_on()) { palfx_set_channel(2,1,q); palfx_set_channel(3,1,n); palfx_set_channel(1,0,0); }
    else             { palfx_set_channel(1,1,q); palfx_set_channel(2,0,0); palfx_set_channel(3,0,0); }
    DS:5BE6 = n;
}
if (clouds_on()) {                                          /* 0802:000c: DS:4512 && DS:42C9 */
    if (alt < 34BCh) DS:5BE1 = 0;                           /* 13500 */
    else if (alt > 4844h) DS:5BE1 = 2;                      /* 18500 */
    else { DS:5BE1 = 1; fog = (9C4h - (i16)labs(3E80h - alt)) << 3; if (fog > 3D00h) fog = 3D00h; }
    DS:5BDA = (alt < 3E80h);                                /* below the layer centre: no sun/moon/stars */
    DS:5BDD = 80h; DS:5BDB = 70h; DS:0320 = 1;
    if (DS:42C9) {                                          /* always true here */
        if (alt < 3E80h) { DS:5BDB = 61h; DS:0320 = 0; }    /* under the overcast: flat 70h sky */
        else DS:5BDD = 70h;                                  /* above it: cloud deck instead of sea */
    }
    in_cloud = (DS:5BE1 == 1);
    palfx_set_channel(5, in_cloud, fog);                    /* whiteout */
} else if (DS:5BE5 != DS:5BE0) {
    palfx_set_channel(6, DS:5BE5, -1); DS:5BE0 = DS:5BE5;
}
hidden = 490a:017f(14A20h);                                 /* sim_world: sun blocked by a cloud */
g = sky_sun_glare();                                        /* 6964:0458 */
if (clouds_on() && alt < 34BCh) g = 0;
if (!in_cloud && hidden != DS:5BDF) {
    DS:5BE3 = hidden ? 1000h : 0; palfx_set_channel(7, hidden, DS:5BE3); DS:5BDF = hidden;
}
palfx_set_channel(8, 1, (DS:42C8 && !in_cloud && !hidden) ? g : 0);
palfx_update(0);
```
Altitudes are world z units (same as `eye.z`); the cloud layer is centred at 16000 with ±2500 of
fog. `DS:42C9` / `DS:42C8` are bytes 1 and 0 of the realism/option flag block at `DS:42C8`
(`522c`, sim_flow): **Likely** "clouds" and "sun glare" options.

* `17ce:0008` `palfx_force_tod()` (from `6cdc:0e0b`, map): `DS:5BE6 = FFFFh`.

### 5.10 DAC path (hand-off)

`5440:07bd(pal, first, count)` (sim_flow) stores the request in `DS:069F/06A1/06A3` only if none is
pending (returns 1 / 0); `5440:07e1` (end of the frame) flips with `gfx_flip` (`1d32:540b`) and then
writes the DAC with `0000:189b(pal, first, count)` (platform: ports 3C8h/3C9h, 6-bit values).
render3d produces only the 768-byte working palette at `DS:5BD8+8`.

-----------------------------------------------------------------------------------------------

## 6. Clouds

No cloud drawing exists in this part's segments. What the player sees of the clouds is:
the horizon colour swap above/below the layer and the flat overcast sky (`17ce`, §5.9), the
whiteout/flash/shadow palette channels 5, 6, 7, and the removal of the world when the eye is in or
above the layer (`0802:0026`, render3d_world.md §2.8). `490a` (sim_world) loads the `CLOUD?` hit-box
lists (`.BXL`) and does the line-of-sight tests (`490a:017f`, `03fb`, `043e`); `5440:083a` is the
full-screen "clouds" `SCR` loading picture (sim_flow), not a 3D effect. Whether cloud objects
(shapes) are also placed in the world is for the objects part (`33d1`/`0802`); none are drawn here.

-----------------------------------------------------------------------------------------------

## Port notes

* `/* PORT: */` The horizon span buffer (`DS:0322`, 960 words) and the span scratch
  (`DS:3172:0000`) can be ordinary arrays; keep the exact span arithmetic (including the 8-bit
  header words of `0a88:0145`) so band edges match pixel for pixel.
* `/* PORT: */` For an Enhanced (high-resolution) renderer the horizon can be rendered analytically
  from §2.4 (`f`, roll, pitch) and the band offsets `k·spacing/|cos r|` scaled with the resolution;
  the faithful 320×200 path must keep the DDA quirk of §2.8.
* `/* PORT: */` The palette channel system stays as is (it defines the look of night, clouds and
  glare); in a true-colour renderer apply the resulting 256-entry palette at presentation time.
* Wraparound: `moon_phase_angle` and `sky_day_to_date` rely on i32 wrap / i16 truncation; use
  fixed-width types.

## Hand-offs

* **sim_flow**: (1) the clock: `6964:0076` lines 1–3 and `6964:0000` advance the time of day (`DS:1120`,
  `DS:112A`, `DS:5CE4`, countdown `DS:51C5` by `DS:711E`); the rest of both functions is render. The
  clock value **decreases** with time — please confirm the labels of `DS:1132[0..7]` (tod setting
  `DS:4789`) against the shell's time names. (2) `sky_init` inputs `DS:4787/4789/478B/478D` (date
  as days since JD 2 415 033, tod, unused word → `DS:51CD`, latitude). (3) `5440:07bd` / `07e1`
  DAC queue (§5.10). (4) `DS:42C8`/`42C9` option bytes used here as sun glare / clouds (**Likely**).
  (5) `644a:089f` fills a view rect and returns cy (used by §3.6, §4.2). (6) `5440:083a` "clouds"
  loading screen calls `palfx_upload_base`.
* **sim_world**: `490a:017f` (sun behind a cloud, 84512-unit ray along `sky_sun_angles_if_day`),
  `0802:0173` sets `DS:5BE5`; `DS:5798` blackout level (`0fd4`) feeds channel 11; `655d:159d` drives
  channel 12 (red flash); `490a:0509` reads channel levels; `583c:0471` uses `6964:005b` (sun vector);
  the gun-record fields read by `655d:038a` (§4.3) and the smoke update callback `655d:1bb7`.
* **platform**: `0000:189b` DAC write; `24b2:013d` / `24d3:0059` allocators; Borland `LDIV`
  `0000:1d69`, `labs` `0000:1fff`, `_fmemcpy` `0000:4abb`, `fopen/fread/fclose/filelength`
  (`0555/0945/08cc/0bba`).
* **video**: library calls `gfx_rect 6ab0`, `gfx_poly_spans 09a8` (entry 27), `gfx_get_pixel
  6a29`, `gfx_put_pixel 6a5b`, `gfx_circle 6bbc`, `gfx_sprite_flip 3de5`, `gfx_sprite_rotated
  5e5b`; BMP load/free `7229:01aa/056a`.

## Cross-part notes

* `render3d_world.md` §1.1: the `4d6e:0076` call is `(sky_base = DS:5BDB, sea = DS:5BDD, pitch =
  CS:0A1F, roll = CS:0A21, cb = DS:5BDA ? NULL : 3E1D:002A)` (no heading), and `set_light` is called
  with `(DS:51D9, DS:51DD)` (the first and third words; `51DB` is 0), not `(51D9, 51DB)`.
* `render3d_shapes.md` §3.4: the shadow records carry the aircraft's own shape (`o[+2]`), range
  `DS:5CDE`, `+1E = C8h`; `DS:5CE0` values are 0/2/3 (off / init / detail > 13). The shadow colour
  `DS:2402` is not set in this part either.
* `render3d_math.md`: `CS:21EE` (remap) is never non-zero in AP (§5.1).
* The effect-record field list of §4 extends `render3d_world.md` §3.

## Open questions

* Who sets bit 80h of the moon record (`DS:1128`) and of star records (both tested, never set in
  AP)?
* `DS:1132[tod]` hour labels (clock direction) — sim_flow.
* `sky_sun_glare` day test (§3.10) is effectively always true with `sunrise < sunset`; confirm no
  other writer makes `113A > 1142`.
* The one-month offset in `sky_day_of_year` / `moon_phase_from_date` is a data/code mismatch in the
  original; faithful port keeps it (affects the declination, day length and moon phase).
