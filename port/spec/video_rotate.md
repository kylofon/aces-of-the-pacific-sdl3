# video — the rotated sprite (part of `video.md`)

`gfx_sprite_rotated(frame* f, int x, int y, u16 angle, int w, int h, int px, int py)` —
INTRO `05da:3d01`, PS `16e3:4025`, AP `1d32:5e5f` (identical code); called through the pointer
`rot_fn` (INTRO `DS:182C`, PS `3090`, AP `3436`) by the thunk `05da:3cfd` / `16e3:4021` /
`1d32:5e5b`. Used by the TTM opcode `A5A7` (`video_ttm.md`). Hand-written, table-driven; this is a
literal transcription (verified instruction by instruction; the purpose of some intermediate
quantities is not obvious, keep the arithmetic exactly). Transparent colour 0, write page,
driver entry 36 per row.

Globals (INTRO / PS / AP): corner x `1830[4]` / `3094` / `343A`, corner y `1838[4]` / `309C` / `3442`,
corner byte-indices `T 1840`, `B 1842`, `L 1844`, `R 1846` / `30A4..30AA` / `344A..3450`, mode
pointers `1848, 1852, 185C, 1866` chosen from the tables `184A[4], 1854[4], 185E[4], 1868[4]`
(4 code addresses each), the left-x list `2B98` (= the scaled sprite's row table, reused) and the
texture-offset table `2698` (= the scaled sprite's column table, reused). Stack locals: `rowtab[200]`
(`bp−6A0`), `A[320]` (`bp−504`), `Bt[320]` (`bp−284`).

## Helpers

* `cos(a)` = `1739:080d` (PS/AP matches in the same library), `sin(a)` = `1739:0802` = `cos(a − 4000h)`:
  `v = (i16)a >> 4` (arithmetic), `v = |v|`; if `v ≥ 400h`: `−T[800h − v]` else `T[v]`, with the
  1025-entry table `T[i] = trunc(16384·cos(i·π/2048))` (at `1739:0000` in INTRO; values checked:
  T[0] = 16384, T[512] = 11585, T[1024] = 0). Angle 0..FFFFh = 0..360°, Q14 result.
* `mul14(a, b)` = high word of `((i32)a*b) << 2` = `((i32)a*b) >> 14` (arithmetic).
* `dda_init` = `gfx_dda_init` (`video_library.md` §7.3): `{frac, int, step}`; stepping
  `frac += step_lo; int += step_hi + carry`; reading `int` *before* the step.
* `edge_x(out, x0, y0, x1, y1)` (`05da:3c84`, near): `n = y1 − y0 + 1`; DDA from x0 to x1 over **n**
  (`dda_init` with divisor n); for k in 0..n−1: `v = int`, step; `row = y0 + k`; if `0 ≤ row < drv[6EC]`
  (200): `*out++ = min(v, drv[06])` (x clamped to the clip x2 even when clipping is off; rows outside
  0..199 produce no entry).

## Algorithm

```
if w == 0 or h == 0: goto done;  w = |w|; h = |h|
c = cos(angle); s = sin(angle)
x0 = x; y0 = y
if py: t = py*h / f.h (idiv); y0 -= mul14(t, c); x0 += mul14(t, s)
if px: t = px*w / f.w;        x0 -= mul14(t, c); y0 -= mul14(t, s)
hc = mul14(h, c); hs = mul14(h, s); wc = mul14(w, c); ws = mul14(w, s)
X = {x0, x0+wc, x0+wc-hs, x0-hs}              (X3 computed as X2 - wc)
Y = {y0, y0+ws, y0+ws+hc, y0+hc}              (Y3 = Y2 - ws)
rowtab[k] = k*f.w (k < 200); fsize = rowtab[f.h]            (f.h < 200 assumed)
T = 2*index of the first minimum of Y[0..3]
if T == 0 and angle >= 4000h: T = 6
if angle < 8000h and Y[2] == Y[3]: T += 2                  (T may become 8: then "corner 4" reads
                                                            X = Y[0] and Y = the variable T itself; reproduce)
L = (T+2)&6; B = (T+4)&6; R = (T+6)&6                        (byte offsets into X/Y)
q = ((8 - T) & 6) >> 1
mode1 = tab184A[q]; mode2 = tab1854[q]; mode3 = tab185E[q]; mode4 = tab1868[q]
ystart = max(Y[T], 0); list[0] = ystart                      (list = DS:2B98, words)
edge_x(&list[1], X[T], Y[T], X[R], Y[R])
k = max(Y[R] - ystart, 0); edge_x(&list[k+1], X[R], Y[R], X[B], Y[B])
fh1 = f.h - 1; fw1 = f.w - 1
if q & 1: swap(fh1, fw1); swap(c, s); swap(w, h)
nA = nB = 0
if Y[R] < Y[L]:                                              ── branch 1
    n = (Y[L]-Y[T] != 0 ? (Y[R]-Y[T])*(X[L]-X[T]) / (Y[L]-Y[T]) : (Y[R]-Y[T])*(X[L]-X[T]) low word)
        + X[T] - X[R]                                        (16-bit)
    if n == 0: goto done
    k = s ? |h*c / s| : 0;  p = (u32)k * fw1 (16x16 signed product); if p >> 16: p = FFFFh
    m = min((u16)p / (u16)w, 320)
    U = dda(0 → fh1, n); V = dda(0 → m, n); offs = mode1
else:                                                        ── branch 2
    n = (Y[L]-Y[B] != 0 ? (Y[R]-Y[B])*(X[L]-X[B]) / (Y[L]-Y[B]) : low word) + X[B] - X[R]
    if n == 0: goto done
    k = c ? |w*s / c| : 0;  p = k * fh1, saturated to FFFFh; m = min(p / h, 320)
    U = dda(0 → m, n); V = dda(0 → fw1, n); offs = mode2
for i in 0..n-1:
    a = U.int; step U; b = V.int; step V
    cnt = a - nA + 1; if cnt > 0: A[nA .. a] = i; nA += cnt
    cnt = b - nB + 1; if cnt >= 0: Bt[nB .. b] = i; nB += cnt
    tex[i] = offs(a, b)                                      (tex = DS:2698)
fill A[nA .. fh1] = n (if fh1+1-nA >= 0); fill Bt[nB .. fw1] = n (if fw1+1-nB >= 0)

offs forms (mode1 = tab184A, mode2 = tab1854; same four forms, same order):
    q0: b - rowtab[a]      q1: -a - rowtab[b]      q2: rowtab[a] - b      q3: a + rowtab[b]

── upper part: rows Y[T] .. Y[R]-1
U = dda(0 → fh1, Y[R] - Y[T]); p = &list[1]
for yy in Y[T] .. Y[R]-1:
    a = U.int; step U
    if yy < ystart: continue                                  (no list advance)
    if clip_y1 <= yy <= clip_y2:                              (always, whatever drv[03])
        x = *p
        cnt = (yy <= Y[L] + 1) ? A[a] : Bt[fw1]
        base = mode3(a):  q0: rowtab[a]   q1: fsize - f.w + a   q2: fsize - rowtab[a] - 1   q3: f.w - a - 1
        draw_row(yy, x, cnt, base)
    p += 1
── lower part: rows Y[R] .. Y[B]-1
U = dda(0 → fw1, Y[B] - Y[R])
for yy in Y[R] .. Y[B]-1:
    a = U.int; step U
    if yy < ystart: continue
    if clip_y1 <= yy <= clip_y2:
        x = *p
        cnt = (yy <= Y[L] - 1) ? A[fh1] : Bt[fw1 - a]
        base = mode4(a):  q0: fsize - f.w + a   q1: fsize - rowtab[a] - 1   q2: f.w - a - 1   q3: rowtab[a]
        draw_row(yy, x, cnt, base)
    p += 1
done: gfx_ega_restore()

draw_row(yy, x, cnt, base):
    if x + cnt > clip_x2: cnt = clip_x2 - x + 1
    skip = 0; if x < clip_x1: skip = clip_x1 - x; x += skip; cnt -= skip
    if cnt <= 0: return
    entry 36: ES = write page (entry 28 first if drv[6E2]), DI = row_ofs[yy], DX = x, CX = cnt,
              source = f.seg : (f.off + base), table = &tex[skip]
              → pixel (x+k, yy) = src[base + tex[skip+k]] if non-zero
```

`tab184A = tab1854 = {q0, q1, q2, q3}` as listed (INTRO `DS:184A = 40DD 40ED 40FF 4111`, `DS:1854 =
4257 4267 4279 428B`, `DS:185E = 43DE 43EE 43FE 4413`, `DS:1868 = 452F 453F 4554 4561`); the port
implements them as `switch (q)`.

Notes for the port: the "rows" use `drv[08]/[0A]` and x uses `drv[04]/[06]` regardless of `drv[03]`;
`edge_x` drops rows outside 0..199 (not the clip rows) while the list pointer advances per drawn
row, so a sprite that starts above row 0 stays aligned (ystart = 0). For EGA adapters (`drv[1D]` = 2,
12, 13) GC registers are set (no-op for VGA).
