# video — the graphics library (part of `video.md`)

The drawing functions of the Dynamix system library layered on the driver (`video.md` §3). Same
code in the three programs; addresses given as INTRO / PS / AP (AP resident segment `1d32` unless
an overlay address is given). Globals: `drv[X]` = shared block (`video.md` §2.4: INTRO `DS:0A80+X`,
PS `2300+X`, AP `26C0+X`); other DS offsets as INTRO / PS / AP. All functions are far cdecl
(medium model) unless marked near. Clipping in the library = against `drv[04..0A]` (inclusive) and
only when `drv[03] ≠ 0`, unless stated. Confidence: verified unless marked.

## Index

1. Thunks and small wrappers
2. Pixels, lines
3. Rectangles
4. Polygons (clip, edge walk, span fill)
5. Circles
6. Flood fill
7. Sprites: plain/flipped/opaque, cached, scaled, SCN (the rotated sprite: `video_rotate.md`)
8. Fonts and text

-----------------------------------------------------------------------------------------------

## 1. Thunks (`ljmp [DS:tab+4n]`) and small wrappers

| INTRO | PS | AP | name | = |
|---|---|---|---|---|
| 06e5 | 0637 | 3de5 | `gfx_sprite_flip(frame*, x, y, flags)` | entry 29 |
| 06e9 | 063b | 3de9 | `gfx_sprite_opaque(frame*, x, y)` | entry 33 |
| — | — | 3de1 | `gfx_sprite(frame*, x, y)` | entry 3 |
| 1e1d | 2431 | 426b | `gfx_cache_blit(frame*, x, y)` | entry 30 |
| 1e21 | 2435 | 426f | `gfx_cache_upload(frame* list[])` | entry 31 |
| 1e25 | 2439 | 4273 | `gfx_cache_reset(list)` | entry 32, then `05da:539d(list)` (pictures part: marks the list uncached) |
| 1e38 | 244c | 4286 | `gfx_sprite_scn(frame*, x, y, flags)` | `ljmp [DS:15BA]` (= `05da:1e3c`, §7.4) |
| 24eb | 2aff | 4939 | `gfx_nib_put(...)` | entry 17 |
| 24ef | 2b03 | 493d | `gfx_nib_or_hi(...)` | entry 18 |
| 2fb0 | 35c4 | 53fe | `gfx_copy_rect(x, y, w, h)` | entry 4 |
| 2fb5 | 35c9 | — | (entry 25, no-op) | |
| 2fbd | 35d1 | 540b | `gfx_flip(wait)` | entry 8 |
| 35d8 | 3bec | 5a26 | `gfx_get_rect(far dst, x, y, w, h)` | entry 5 |
| 35dc | 3bf0 | 5a2a | `gfx_rect_size(w, h)` | entry 6 |
| 492f | 4c53 | 6a8d | `gfx_put_rect(far src, x, y, w, h)` | entry 7 |
| 3cfd | 4021 | 5e5b | `gfx_sprite_rotated(...)` | `ljmp [DS:182C]` (= `05da:3d01`) |
| 0b6b | 117f | 09a8 | `gfx_poly_spans(far list)` | `ES:SI = list`, entry 27 |
| 0b7e | 1192 | 09bb | `gfx_span_copy(far list)` | `ES:SI = list`, entry 23 |
| 06f1 | 0643 | 3df1 | `gfx_ega_restore()` | if `drv[21] == 10h`: GC5=2, GC8=FFh, SC2=0Fh; no-op on VGA |

`gfx_get_pixel(x, y)` (48cb / 4bef / 6a29): if clipping is on and (x, y) outside → return −1 (FFFFh),
else entry 21. `gfx_put_pixel(x, y, c)` (48fd / 4c21 / 6a5b): if clipping is on and outside →
return, else entry 22.

## 2. Lines — `gfx_line(x1, y1, x2, y2)` (3957 / 3c7b / 5ab5)

Colour `drv[0E]`, write page. If clipping is on, clip in this order (each step may swap the two
endpoints so that the one being moved is "point 1"; all divisions are 16-bit signed `idiv` of the
32-bit product, truncating toward zero):

```
top    (ymin = drv[08], signed):  both y < ymin → reject.  one y < ymin → move it:
        x += (xo - x) * (ymin - y) / (yo - y);  y = ymin          (xo,yo = the other end)
left   (xmin = drv[04], signed):  both x < xmin → reject; one → y += (yo-y)*(xmin-x)/(xo-x); x = xmin
bottom (ymax = drv[0A], UNSIGNED compares): both > → reject; one → x += (xo-x)*(ymax-y)/(yo-y); y = ymax
right  (xmax = drv[06], UNSIGNED):  both > → reject; one → y += (yo-y)*(xmax-x)/(xo-x); x = xmax
```

(Only one endpoint is moved per edge; if both lie beyond the same edge the line is rejected.
Unsigned compares at bottom/right mean negative coordinates count as "beyond" — they can only
survive to that point if clipping produced them, which the top/left steps prevent.)
Then order the endpoints so that x1 ≤ x2 (swap both coordinates) and call entry 2
(`video.md` §3.3). Without clipping the ordering and entry 2 are the same.

## 3. Rectangles

### `gfx_rect(x, y, w, h)` (645b / 61b5 / 6ab0)

```
x2 = x+w-1; y2 = y+h-1                        (from the unclipped values)
if drv[0C] (fill_on):
    cx=x, cy=y, cw=w, ch=h
    if clip_on: d = cx - drv[04]; if d < 0: cx -= d, cw += d
                d = cy - drv[08]; if d < 0: cy -= d, ch += d
                d = drv[06] - x2;  if d < 0: cw += d
                d = drv[0A] - y2;  if d < 0: ch += d
    if cw > 0 and ch > 0:
        span list at span_seg:0000 = {cy, ch, ch × (cx, cx+cw-1)}; entry 27 (fill_col/fill_col2 dither)
if !fill_on or drv[0E] != drv[0D]:
    gfx_line(x2, y, x2, y2); gfx_line(x, y2, x2, y2); gfx_line(x, y, x, y2); gfx_line(x, y, x2, y)
```

The dither phase of a filled rectangle is `(x + y + cx)` even → `fill_col` (entry 27 rule).

### Copies, get/put — see thunks (§1) and `video.md` §3.6–3.7.

-----------------------------------------------------------------------------------------------

## 4. Polygons — `gfx_polygon(n, int *xs, int *ys)` (0b91 / 11a5 / 09ce)

Near arrays in DGROUP, at most 20 vertices (the work arrays are 20 words; no check). Used by TTM
`AF1F/AF2F`, PS `0ddd`, `2c11`, `3d50` (ts core), AP `2595`, `277a`, `6396`. Returns `span_seg` if
a fill was made, else 0 (AX). Globals (INTRO; PS +1880h; AP +1C40h except scratch at AP 1CF8+):
`poly_x 0B2C`, `poly_y 0B54`, `poly_x2 0B7C`, `poly_y2 0BA4`, `poly_ox 0BCC`, `poly_oy 0BF4`,
`poly_n 0C1C`, scratch `15A0` top index, `15A2` bottom index, `15A4` chain-1 length, `15A6` chain-2
length, `15A8` edge counter, `15AA` edge offset, `15AC` span slot (2 = right x, 0 = left x), `15AE/15B0`
last kept x/y, `15B2` return value, `15B4` outline vertex count, `15B6` saved length, `15B8` row
stride − 2 for the unrolled writer, `15B9` "ambiguous orientation" flag.

```
poly_ret = 0; ambiguous = 0
if n >= 0: poly_n = n; copy xs → poly_x, ys → poly_y        (n < 0: nothing is drawn)
if n == 2: outline_lines(poly_x, poly_y, 1); return
if n < 2: return
if !fill_on: close (poly_x[n] = poly_x[0], same y); outline_lines(poly_x, poly_y, n); return
if draw_col != fill_col: poly_ox/oy = closed copy (n+1 points); poly_outline_n = n
if clip_on: gfx_poly_clip()                                   (§4.1; may change poly_n)
if poly_n == 2: outline_lines(1 segment); return;  if poly_n < 2: return
```

**Vertex pass** (`0C3D`): walk i = poly_n−1 down to 0 with `last = (poly_x[0], poly_y[0])`; a vertex
equal to `last` is dropped, else it is appended to `poly_x2/poly_y2` (so the kept list is in
reverse order) and becomes `last`. While appending track **top** = minimum y (ties: larger x wins)
and **bottom** = maximum y (ties: x ≤ current wins, i.e. the leftmost, last one on equal x).

* If min y == max y: `gfx_line(x_bottom, ymax, x_top, ymin)` (a horizontal line from the left-most
  to the right-most tracked point) and return. Same if the kept count m == 2. m < 2: return.
* **Orientation** (`0D08`): t = top; next = t+1 (mod m), prev = t−1 (mod m) in the kept list.
  `dxn = x[next]-x[t], dyn = y[next]-y[t]`; if `dyn == 0`: `dyn = 1`, `dxn = dxn < 0 ? −7FFFh : 7FFFh`.
  `dxp, dyp` likewise for prev, with `dxp = dxp < 0 ? −7FFFh : 7FFFh` when `dyp == 0`.
  - `dxp ≥ 0` and `dxn ≤ 0` → **reverse**; `dxp < 0` and `dxn ≥ 0` → **forward**;
  - both > 0: compare slopes `dxn/dyn` vs `dxp/dyp` as unsigned 16.16 fractions (integer quotient
    first, then `(rem << 16)/divisor`): next greater → forward, smaller → reverse;
  - both < 0: compare `|dxp|/dyp` against `|dxn|/dyn`: `|dxp|/dyp` greater → forward, smaller → reverse;
  - equal (quotient and fraction): **ambiguous**: set the flag, save `poly_x2/y2` (m entries) into
    `poly_ox/oy` (overwriting the outline copy), continue **forward**; after the fill (and outline),
    restore and run everything again **reversed**.
  - forward: `poly_x/y = poly_x2/y2` in order; reverse: in reverse order, with top/bottom indices
    mirrored (`2m−2−idx` in bytes).
* **Chains** (`0E1A`): chain 1 = from top forward until the first vertex with y ≥ y_bottom
  (inclusive), copied to `poly_x2/y2[0..c1−1]`; chain 2 = from bottom forward until y ≤ y_top
  (inclusive), appended. After orientation chain 1 is the **right** side, chain 2 the **left**.
* **Edge walk** (`0E8E`): the span buffer is addressed by absolute row: record for row y at
  `span_seg:(4y)`, `+0` = left x, `+2` = right x. Chain 1 edges write slot +2 (`15AC = 2`), then chain 2
  edges write slot +0. For each edge (x0,y0)→(x1,y1) of a chain (consecutive entries):
  - `x0 == x1` → **vertical** (`1009`): rows min(y)..max(y) get x0.
  - `y0 == y1` → **horizontal**: row y0 gets min(x0,x1) (left slot) or max (right slot).
  - `|dx| < |dy|` → **steep** (`1025`): start from the endpoint with the smaller x (swap if
    x0 ≥ x1); `dx = x1−x0 > 0`, `dy = |y1−y0|`, row step +1 if the start is above the end else −1;
    `e = 2dx − dy`; write x at the start row; then `dy` times: `if e ≥ 0: x += 1; e += 2dx−2dy else
    e += 2dx`; next row; write x. (Total dy+1 rows.)
  - `|dx| == |dy|` → **diagonal** (`1163`): start at the endpoint with the smaller y (swap if
    y0 ≥ y1 — sic: when equal ys cannot occur here); x steps −1 per row if x_start ≥ x_end else +1;
    rows start..end.
  - `|dx| > |dy|`, left slot → `1245`; right slot → `118a`:
    ```
    left:  start = endpoint with smaller x (swap if x0 >= x1); dx = xe - xs; dy = |ye-ys|; ystep = ±1
           e = 2dy - dx; x = xs; row = ys
           out[row] = x; row += ystep; x += 1
           while e < 0: x += 1; e += 2dy
           loop: out[row] = x; row += ystep; x += 1; if --dy_left == 0: break      (dy_left starts = dy)
                 e += 2dy - 2dx; while e < 0: x += 1; e += 2dy
    right: identical with start = endpoint with the LARGER x (swap if x0 <= x1) and x -= 1 instead of +=.
    ```
    (writes the first x of each row's run for the left edge, the last x for the right edge;
    dy+1 rows.)
  Each edge rewrites its end rows; the later edge wins at shared vertices (chain order).
* **Fill** (`0F39`): span header `{y_top, y_bottom − y_top + 1}` written at `(span_seg−1):(4*y_top+0Ch)`
  = 4 bytes before row y_top's record; entry 27 on that list (fill_col / fill_col2 dither with the
  phase from the first row's left x). `poly_ret = span_seg`.
* **Outline**: if `draw_col ≠ fill_col`: `outline_lines(poly_ox, poly_oy, poly_outline_n)` —
  the **unclipped** polygon, each line clipped by `gfx_line`. In the ambiguous case the outline
  arrays hold the kept vertex list and the count is still the original n: lines between whatever is
  there (quirk; reproduce).
* `outline_lines(xs, ys, k)` (`0fbd`, near): `gfx_line(xs[i], ys[i], xs[i+1], ys[i+1])` for i < k.
  With `yshift` (`drv[6E8]`) ≠ 0 the clip y1/y2 are halved and the y coordinates `sar 1` for the
  line calls (not used on VGA).

Rows are never checked against the buffer: without clipping, a negative y writes before the span
buffer (the header uses `span_seg−1`; `span_seg` is its DOS block +1 paragraph, §2.2).

### 4.1 `gfx_poly_clip()` (2b2f / 3143 / 4f7d, near-called far)

Sutherland–Hodgman in two passes over `poly_n` vertices; outcodes per vertex: x pass bit 1 = x <
x1, bit 2 = x > x2; y pass bit 8 = y < y1, bit 4 = y > y2. For each edge P (previous, starting with
the last vertex) → C (current):

```
both inside: emit C
both outside and (cP & cC): nothing
P inside, C outside: emit I(C side), computed from C:        (x pass, side = x1 if cC&1 else x2)
        I = (edge, C.y + (P.y - C.y)*(edge - C.x)/(P.x - C.x))
P outside, C inside: emit I(P side) computed from P: (edge, P.y + (C.y-P.y)*(edge-P.x)/(C.x-P.x)); emit C
both outside, different sides: emit I(P side) from P, then I(C side) from C
```

(y pass: same with x/y exchanged, side y1 checked before y2.) Products are `imul` 16×16→32, the
quotient `idiv` truncated. Output of the x pass → `poly_x2/y2`, of the y pass → `poly_x/y`; `poly_n`
= output count. If the x pass leaves ≤ 1 vertex the arrays are copied back and it returns.

-----------------------------------------------------------------------------------------------

## 5. Circles — `gfx_circle(r, xc, yc)` (0408 / 035a / 6bbc)

Midpoint circle with **horizontal aspect 9/8** (offsets `a + a/8`, arithmetic shift). Globals
(INTRO/PS/AP): `264C/6930/70EA` xc, `264E/6932/70EC` top row, `2650/6934/70EE` yc − top,
`2652/6936/70F0` far span write pointer, `2656/693A/70F4` y1 − top, `265A/693E/70F8` y2 − top,
`2658/693C/70F6` plotter.

```
if fill_on: plotter = span_plot; if (list = circle_walk(r, xc, yc)): gfx_poly_spans(list)
if draw_col != fill_col or !fill_on: plotter = outline_plot; circle_walk(r, xc, yc)

circle_walk (046e, near):
    buffer = span_seg:0000
    top = max(yc - r, drv[08]);  buffer[0] = top                (y clipped even if clip_on == 0)
    cnt = min(yc - top + r + 1, drv[0A] - top + 1); buffer[1] = cnt
    if top > drv[0A] or top + cnt < drv[08]: return 0
    x = 0; y = r; d = 3 - 2r
    while x <= y:
        plot(x, -y); plot(x, y); plot(y, -x); plot(y, x)
        if d < 0: d += 4x + 6  else: d += 4(x - y) + 10; y -= 1
        x += 1
    return far pointer to buffer

span_plot(a, b) (05a1):  xl = xc - a - (a>>3); xr = xc + a + (a>>3); row = b + (yc - top)
    if clip_on: if row < drv[08]-top or row > drv[0A]-top: return
                xl = max(xl, drv[04]); xr = min(xr, drv[06])
    record[row] = (xl, xr)                                   (at buffer + 4 + 4*row; last write wins)
outline_plot(a, b) (0638): xl, xr as above; row = b + (yc - top)
    if clip_on: if row outside [drv[08]-top, drv[0A]-top]: return
                y = row + top; if drv[04] <= xl <= drv[06]: gfx put (entry 22)(xl, y, draw_col)
                               if drv[04] <= xr <= drv[06]: put(xr, y, draw_col)
    else: put(xl, row + top), put(xr, row + top)
```

The TTM opcode `A404/A424` computes `r = h/2`, centre `(x+r, y+r)` (TTM part).

-----------------------------------------------------------------------------------------------

## 6. Flood fill — `gfx_flood(x, y, c)` (2893 / 2ea7 / 4ce1)

Scan-line seed fill on the **write page** (read page temporarily = write page, restored at the end).
Stack: `dos_alloc(6000 bytes)` (1500 seeds, no overflow check), pointers at `2EB8..2EBE` (INTRO).

```
old = gfx_get_pixel(x, y); if old == c: return            (−1 outside the clip)
push(x, y)
while stack not empty:
    (x, y) = pop(); up = down = 0; flagU = flagD = 0
    L = R = x
    xi = x                                                   (scan left, including x)
    while drv_get_pixel(xi, y) == old and xi >= drv[04]:
        L = xi
        if drv_get_pixel(xi, y-1) == old: if !flagU and y > drv[08]: flagU = 1; push(xi, y-1)
        else flagU = 0
        if drv_get_pixel(xi, y+1) == old: if !flagD and y < drv[0A]: flagD = 1; push(xi, y+1)
        else flagD = 0
        xi -= 1
    xi = x                                                   (scan right, including x again)
    while drv_get_pixel(xi, y) == old and xi < drv[06]:      (strict: column drv[06] is never scanned)
        R = xi + 1
        (same up/down seed logic, with their own flags continuing from the left scan)
        xi += 1
    hspan (entry 10) on row y from L to R inclusive: AL = c, AH = drv[0F], DX = y
dos_free(stack); restore read page
```

Quirks to keep: the span is filled **to R = last matching pixel + 1** (one pixel beyond the run on
the right, over the boundary); `drv[06]` is exclusive on the right; the clip bounds are used even
when `drv[03] = 0`; the fill is dithered with `drv[0F]` when that is non-zero (pixel colour `c`
where `(x+y)` is odd, `drv[0F]` where even — entry 10/11 rule). Seed flags: four locals zeroed at
each pop — left scan uses U=`bp-2`, D=`bp-4`, right scan U2=`bp-6`, D2=`bp-8`. A push in the left
scan sets both its own flag and the right-scan flag (U and U2, or D and D2); a non-matching pixel in
the left scan clears only U (or D); in the right scan a push sets U2/D2, a non-match clears U2/D2.
So the right scan does not push a seed above/below x if the left scan pushed one in that direction
and no non-match reset it.

-----------------------------------------------------------------------------------------------

## 7. Sprites

Frame record (`video.md` §3.4): `{+0 seg, +2 off, +4 ?, +6 w, +8 h}`.

### 7.1 Flipped/plain/opaque — entries 29/3/33 (`video.md` §3.4, §3.5)

### 7.2 Cached — entries 30/31/32 (`video.md` §3.16)

### 7.3 `gfx_sprite_scaled(frame*, x, y, flags, w, h)` (25a6 / 2bba / 49f4)

Draws the frame scaled to `w × h` (transparent 0) on the write page. Tables (INTRO/PS/AP):
columns `2698/697C/6646`, rows `2B98/6E7C/6B46`.

```
if w < 0: w = -w; flags |= 2 (mirror)      if h < 0: h = -h; flags |= 1 (upside down)
W = min(w, 640); H = min(h, 400)
col DDA: start = (flags&2) ? fw-1 : 0, end = (flags&2) ? 0 : fw-1, n = w-1   (dda_init, below)
for i in 0..W-1: col[i] = int(cur); cur += step
col[W] += 1                                (increments a stale entry; harmless, reproduce if exact)
row DDA: start 0, end fh-1, n = h-1
rowbytes = fw >> DS:164A[drv[1D]]          (0 on VGA → rowbytes = fw)
r = 0; off = 0
for j in 0..H-1: v = int(cur); cur += step
                 while v > r: r += 1; off += rowbytes
                 if flags&1: rows[H-1-j] = off  else rows[j] = off
x2 = x + W; y2 = y + H; top = y; left = x; skip = 0          (x2, y2 exclusive)
if clip_on: if x2 > drv[06]: x2 = drv[06]+1
            if y2 > drv[0A]: y2 = drv[0A]+1
            if top < drv[08]: top = drv[08]
            if left < drv[04]: skip = drv[04] - left; left = drv[04]
if y2 - top <= 0 or x2 - left <= 1: return                     (sic: a 1-column result is not drawn)
if drv[6E2]: entry 28(write page)
for r in top..y2-1: entry 37 with DI = row_ofs[r], DS:SI = frame pixels + rows[r - y],
                    DX = left, CX = x2 - left, T = &col[skip]
```

`dda_init(s, n)` (24f3 / 2b07 / 4941), s = {+0 frac, +2 int (= start), +4 step lo, +6 step hi(=end)}:
```
if n <= 0: step = 0; frac = 0; return 0
frac = 0; step32 = ((end - start) << 16) / n        (signed 32-bit division, truncated)
a = |step32|; frac = (a >> 16 == 0 and (a & FFFFh) < 8000h) ? 8000h : (a & FFFFh)
return 1
```
Stepping (`cur` = int.frac as 16.16): `frac += step_lo; int += step_hi + carry`. The initial
fraction bias (½, or the step's own fraction when |step| ≥ ½) decides the rounding; reproduce.

`gfx_sprite_scaled_centered(frame*, xc, yc, flags, scale)` (2827 / 2e3b / 4c75): `w = fw*scale >> 10`,
`h = fh*scale >> 10` (32-bit products, arithmetic shift); calls `gfx_sprite_scaled(frame, xc − w/2,
yc − h/2, flags, w, h)` (`/2` = `sar 1`). (No caller found in INTRO.)

### 7.4 SCN sprites — `gfx_sprite_scn(frame*, x, y, flags)` (1e3c / 2450 / 428a)

Run-length "SCN" frames (`resources.md` §4c): the frame's far pointer addresses `u8 base` then ops.
The caller (TTM `A5f5`) may overwrite `base` first (tinting). Write page; `flags` 1 = bottom-up, 2 =
right-to-left.

```
clip = clip_on; if the box x..x+w (sic, not w-1), y..y+h lies inside [x1..x2]×[y1..y2]: clip = 0
dy = +1; if flags&1: dy = -1; y += h-1
if flags&2: x += w-1
row_vis = !clip or (y1 <= y <= y2); if row_vis: rowofs = row_ofs[y]
loop over ops b:
  11nnnnnn (n > 0 literal pixels, n/2 rounded up bytes, HIGH nibble first; value = base + nibble,
            8-bit add): expand into tmp[n]; draw(tmp, n); x = new x
  10nnnnnn v: run of n pixels of colour base+v: draw_run(n)
  01000000: end
  01nnnnnn: skip n: x -= n (RTL) / x += n
  00nnnnnn: newline: y += dy; row_vis/rowofs recomputed; x += n (RTL) / x -= n;
            peek next byte b2: if (b2 & C0h) == 0 and (b2 & 3Fh) != 0: consume, x ±= 64*(b2 & 3Fh) (same sign)
```

Literal draw (entry 38; `tmp` pixels are opaque, including value `base+0`):
* left-to-right: `nx = x + n`. If !clip → draw at x. Else if !row_vis → skip. Else if `x ≥ x1` and
  `nx ≤ x2` → draw all. Else if `x < x1`: `k = x1 − x`; if k > 63 skip; `n −= k`; if n ≤ 0 skip;
  draw `tmp+k` at x1. Else (`nx > x2`): `k = nx − x2 − 1`; if k > 63 skip; `n −= k`; if n > 0 draw
  at x. Then `x = nx`.
* right-to-left: `nx = x − n`; pixels x, x−1, … If !clip → draw. Else if !row_vis skip. Else if
  `nx ≥ x1` and **`x < x2`** (strict) → draw all. Else if `nx < x1`: `k = x1 − nx`; if k > 63 skip; `n −= k`;
  if n ≤ 0 skip; draw n from x. Else (`x ≥ x2`): `k = x − x2`; if k > 63 skip; `n −= k`; if n ≤ 0 skip;
  draw `tmp+k` from x2. Then `x = nx`.

Run draw (entry 10, `AL = base+v`, `AH = 0`, `DX = y`):
* LTR: `nx = x + n`; same tests as literals; the left case sets `x = x1` after `n −= k`; draws from x.
* RTL: `nx = x − n`; draws the span `x−n+1 .. x`; clip cases: `nx < x1` → `n −= x1 − nx` and draws
  from `x − n + 1`; `x ≥ x2` (with the strict test above) → `k = x − x2`, `n −= k`, `x = x2`, draws from
  `x2 − n + 1`. Then `x = nx`.

-----------------------------------------------------------------------------------------------

## 8. Fonts and text

### 8.1 Font slots

20 slots; slot 0 is the **current** font (a copy), slot 1 the BIOS 8×8 ROM font (set by `gfx_init`),
slots 2..19 loaded fonts. Per slot (INTRO / PS / AP DS offsets):

| field | INTRO | PS | AP | |
|---|---|---|---|---|
| `font_w` | `0AB4+i` | `2334+i` | `26F4+i` | width (fixed) / max width (prop.) |
| `font_h` | `0AC8+i` | `2348+i` | `2708+i` | height |
| `font_first` | `0ADC+i` | `235C+i` | `271C+i` | first char |
| `font_count` | `0AF0+i` | `2370+i` | `2730+i` | number of chars |
| `font_kind` | `2EC0+i` | `71A4+i` | `6E6E+i` | 0 fixed 1 bpp, 1 proportional 1 bpp (`FF`), 2 fixed 8 bpp (`FE`), 3 proportional 8 bpp (`FD`) |
| `font_uline` | `2FC4+i` | `72A8+i` | `6F72+i` | underline row (header byte 3 of `FF`/`FD` fonts) |
| `font_glyphs` | `2ED4+4i` | `71B8+4i` | `6E82+4i` | far pointer to glyph bits |
| `font_ofs` | `2F24+4i` | `7208+4i` | `6ED2+4i` | far u16 offset table (proportional; 0 = fixed) |
| `font_wid` | `2F74+4i` | `7258+4i` | `6F22+4i` | far u8 width table (proportional) |

### 8.2 `gfx_font_load(name)` (4a8f / 4db3 / AP overlay `7115:0000`)

Finds the first free slot 2..19 (glyph pointer null), else returns 0. Opens `name` (volume), finds
chunk `FNT:`, reads byte 0 into `font_w[i]`:
* `FFh` / `FDh`: `kind = −byte` (1 / 3); then bytes: max width → `font_w`, height → `font_h`, underline
  row → `font_uline`, first, count, `u16 size`; unpacks the packed data (5-byte header,
  `resources.md` §2) into a `dos_alloc(size)` block which must yield exactly `size` bytes; layout:
  `font_ofs = block`, `font_wid = block + 2*count`, `font_glyphs = block + 3*count`.
* `FEh`: kind 2; next byte = width; else kind 0 with width = byte 0. Then height, first, count; glyph
  size = (kind 2 ? w : (w+7)/8) * h * count bytes read raw into a near `malloc` block (DGROUP);
  `font_ofs = font_wid = 0`.
Returns the slot, 0 on failure. `gfx_font_free(i)` (4e01 / 5125 / 7115:0372): if the slot is valid:
if it is also the current font, clear slot 0; free (`dos_free` for proportional, `free` otherwise);
clear the slot.

### 8.3 Selection and metrics

* `gfx_font_valid(i)` (30f8 / 370c / 5546): 0 < i < 20 and glyph pointer ≠ 0.
* `gfx_font_select(i)` (2fc1 / 35d5 / 540f): i == 0 → return the index of the slot (1..19) whose glyph
  pointer equals the current font's, or 0; else if valid: copy slot i to slot 0 (all nine fields),
  return i; invalid → 0.
* `gfx_font_width(i)` (3098 / 36dc / —) → `font_w[i]` if valid or i == 0, else 0; `gfx_font_height(i)`
  (30c8 / — / —) likewise with `font_h`.
* `gfx_char_metrics(c, int *w, int *h)` (3573 / 3b87 / 59c1): current font; returns 0 if c outside
  [first, first+count); else `*w` = width (table or fixed), `*h` = height (each pointer may be null),
  returns 1.
* `gfx_text_width(near str)` (3122 / 3736 / 5570) → `gfx_text_width_far(str)` (3133 / 3747 / 5581):
  sum of the widths of the characters inside the font (others count 0). Bold and italic are not
  counted.

### 8.4 Drawing — `gfx_text(near str, x, y)` (33f7 / 3a0b / 5845) → `gfx_text_far(far str, x, y)` (340e / 3a22 / 585c)

Current font; colours `drv[00]` (fg), `drv[01]` (bg); style `drv[02]`.

**Fast path** when `drv[02] ≤ 1` and `drv[03] == 0` (clipping off) and `font_kind ≤ 1`: for each
character: if `wprev > 8` → `char_slow(c, x, y)`, `x += result` (`wprev` starts as `font_w` and is
updated only by fast-path characters, so a font with `font_w > 8` is drawn entirely by the slow
path). Else glyph pointer
(proportional: `glyphs + ofs[c−first]`, width from the table; fixed: `glyphs + (c−first) *
((w+7)/8 * h)`) and **driver entry 1** (8-pixel cell: background box 8 wide when `drv[02] == 0`),
`x += width`. Characters outside the font are *not* filtered on this path (the index is used
unchecked — garbage glyph; **verified**, not reached by the game **likely**).

**Slow path** otherwise: for each character `w = char_slow(c, x, y); x += w; if drv[02] & 2: x += 1`.

`char_slow(c, x, y)` (3193 / 37a7 / 55e1, near), returns the advance (0 if c not in the font):
```
save = drv[00]
w, h, glyph as above (8 bpp fixed: glyph = glyphs + i*w*h)
put = (x >= x1 and y >= y1 and x + w <= x2 and y + h <= y2 (unsigned)) ? driver entry 22 : gfx_put_pixel
       (the clip rectangle is consulted even when clip_on == 0; gfx_put_pixel then does not clip)
if drv[02] & 4 (italic): x += h/2
for r in 0..h-1:
    if !(drv[02] & 1): drv[0E] = drv[01]; gfx_line(x, y, x + w, y)     (w+1 pixels; leaves drv[0E] = bg!)
    for c in 0..w-1:
        1 bpp: bit = glyph byte & mask (mask 80h, 40h … ; next byte every 8 columns); pix = bit
        8 bpp: v = glyph byte; if v: drv[00] = (v < 5) ? aa_map[v] : v; pix = v
        X = x + c
        if pix:
            if drv[02] & 10h (halftone): if (X + y) odd: put(X, y, drv[00])
                                          else if drv[02] & 2: put(X+1, y, drv[00])
            else: put(X, y, drv[00]); if drv[02] & 2: put(X+1, y, drv[00])
        elif drv[02] & 8 and r == font_uline: put(X, y, save)
    next glyph row (1 bpp: rows are (w+7)/8 bytes; 8 bpp: w bytes)
    if (drv[02] & 4) and (r & 1): x -= 1
    y += 1
drv[00] = save; return w
```

Differences between the paths that the port must keep: the fast path paints an 8-wide background
cell, the slow path a (w+1)-wide background line and leaves `drv[0E]` = background colour.
