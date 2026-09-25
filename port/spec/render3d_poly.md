# render3d — part 2: the polygon pipeline (AP `277a`)

Part of the `render3d` spec (index: `render3d.md`). Conventions, the `277a` data block (`CS:xxxx`)
and the math routines are in `render3d_math.md` (§2.3 lists every `CS:` variable used here). Code is
hand-written asm; interfaces are registers/stack as stated. Confidence **Verified** unless marked.

The shape walker (`ts_draw` `2f0e`, `render3d_shapes.md`) calls one of four "part" routines for each
variant of type 0 (a polygon list), selected by the object's draw mode `CS:09B0`:

| Mode | Routine | Arithmetic | Near plane | 2D clip (if `CS:09B3`) |
|---|---|---|---|---|
| 0, `DS:2403` = 0 | `277a:05c6` `part_draw16` | 16-bit, no vertex shift | S-H clip `2adf` | `25ec` |
| 0, `DS:2403` ≠ 0 | `277a:03bb` `part_draw_shadow` | 16-bit, flattened to z = 0 | `2adf` | `25ec` |
| 3 | `277a:07ae` `part_draw16s` | 16-bit, vertices `>> −vtx_shift` | none (object known to be in front) | `25ec` |
| 1 | `277a:361d` `part_draw32` | 32-bit | `2f4e` (16-bit interpolation) | `2caa` |
| 2 | `277a:361d` | 32-bit | `3530` (32-bit interpolation) | `3242` |

All four share: the vertex cache (`CS:0A79` state per vertex, reset when the vertex array far pointer
`CS:09A4:09A2` differs from `ES:CS:09A6`), the polygon index list (`CS:0A51`, count `CS:0A4F`),
the output lists `CS:0C77`/`CS:0C9F` (+ high words `CS:170D`/`CS:1735` in 32-bit modes), the colour
routine `01ba`, and the fill routine `029f`.

-----------------------------------------------------------------------------------------------

## 1. Data

### 1.1 Variant type 0 and polygon records (shapes.md §5, §7)

Argument of the part routines: far pointer to the variant entry `+2` (`u16 npolys, u16 poly_ofs`).
Polygon record (8 bytes): `+0 flags`, `+1 VGA edge`, `+2 VGA fill`, `+3 EGA edge`, `+4 EGA fill`,
`+5 normal vertex index`, `+6 u16 offset of the index list` (bytes, `FFh`-terminated). Flags
`& 3`: 0 two-sided, 1 back-face culled, 2 never drawn, 3 (none in the data) = treated like 1.
`10h` = 4-point bitmap fill, `20h` = shaded, `40h` = **not read by any render routine** (settles
shapes.md: it has no effect on drawing), `80h` = filled.

### 1.2 Globals written for the fill (DGROUP, read by the system-library fill `1d32:09ce`)

| DS: | Type | Meaning |
|---|---|---|
| `26CC` | u8 | 1 = filled polygon, 0 = outline only (flag 80h) |
| `26CD` | u8 | fill colour |
| `26CE` | u8 | edge colour |
| `26C3` | u8 | cleared by `2f0e:071f` before a polygon variant, set to 1 by the bitmap/disc paths and by `5440:03aa`; read by the library fill/blit code (video spec) — **Unknown** meaning (clip-to-window flag, Likely) |
| `26C4/26C6/26C8/26CA` | i16 | clip window x0, x1, y0, y1 (inclusive), set from the camera by `277a:004b` |
| `26DF` | u8 | 0 = EGA colours (bytes +3/+4), non-zero = VGA (bytes +1/+2). Cleared by `1d32:000a` (graphics init), filled in by the driver's info call `1d32:0070` (block `DS:26C0`, byte `+1Fh`) — video spec. The VGA320 driver sets it non-zero |
| `2402` | u8 | shadow colour (set by `2ecb:013c`) |
| `2403` | u16 | shadow mode: `2ecb:00ba` sets 1 around a `ts_draw` call |
| `2405` | u16 | shadow LOD cap (`2f0e:08e9` uses LOD index `DS:2405` when the shape has more) |
| `276C/2794` | i16[21] | x/y copies passed to `1d32:09ce` (it copies them again) |
| `285C` | u16 | vertex count for the fill |

### 1.3 Shading tables

* `CS:21EC` → **DS pointer** to the 256-byte SHADES table (`DS:4092`, loaded from `SHADES1` by
  `519d:008a`, 256 bytes; identical to `COMMON1:SHADES.DAT`). Value `n` = number of shades on each
  side of palette index `c` (0 = not shadable; values used: 2, 4, 6, 8; `FFh` at index 255).
  (shapes.md called `CS:21EC` the table itself; it is a pointer.)
* `CS:21EE` → DS pointer to a 256-byte colour remap, 0 = none (camera `+14h`).
* `CS:21F8` `shade_ofs[8][32]` (i8), row `n−1`, column `level + 16`:

```
n=1: -1 ×16, 0 ×16
n=2: -2 ×10, -1 ×6, 0 ×6, 1 ×10
n=3: -3 ×8, -2 ×4, -1 ×4, 0 ×4, 1 ×4, 2 ×8
n=4: -4 ×6, -3 ×4, -2 ×4, -1 ×2, 0 ×2, 1 ×4, 2 ×4, 3 ×6
n=5: -5 ×6, -4 ×2, -3 ×2, -2 ×2, -1 ×4, 0 ×2, 1 ×2, 2 ×2, 3 ×4, 4 ×6
n=6: -6 ×6, -5 ×2, -4 ×2, -3 ×2, -2 ×2, -1 ×2, 0 ×2, 1 ×2, 2 ×2, 3 ×2, 4 ×2, 5 ×6
n=7: -7 ×5, -6 ×2, -5, -4 ×2, -3 ×2, -2 ×2, -1 ×2, 0 ×2, 1 ×2, 2 ×2, 3 ×2, 4, 5 ×2, 6 ×5
n=8: -8 ×5, -7 ×2, -6, -5 ×2, -4, -3 ×2, -2, -1 ×2, 0 ×2, 1, 2 ×2, 3, 4 ×2, 5, 6 ×2, 7 ×5
```

(exact bytes: `277a:21F8`, 256 bytes; the port copies them from the image.)

-----------------------------------------------------------------------------------------------

## 2. Per-polygon routines

### 2.1 `277a:01ba` `poly_colours` (near; ES:DI = polygon record, BP = vertex array offset, DS = CS)

```
if (DS:26DF) { edge = rec[1]; fill = rec[2]; } else { edge = rec[3]; fill = rec[4]; }
DS:26CC = (rec[0] & 0x80) != 0;
if (DS:26CC && (rec[0] & 0x20) && DS:26DF && CS:21EC != 0) {
    n = SHADES[fill];                       /* byte at DS:(CS:21EC + fill) */
    if (n >= 1 && n <= 8) {                 /* signed compare: FFh = -1 is excluded */
        N = vtx[rec[5]];                    /* 3 words at BP + 6*idx, copied to CS:21BC */
        if (CS:09B5) N = -N;                /* back side of a two-sided polygon */
        level = (N · light_obj) >> 16;      /* high word of the 32-bit dot, CS:0A3B */
        if (level == 16) level = 15;        /* no lower clamp: level is -16..15 for |N|=2048 */
        s = fill + shade_ofs[n-1][level + 16];   /* 8-bit add */
        if (edge == fill) edge = s;
        fill = s;
    }
}
if (CS:21EE) { edge = REMAP[edge]; fill = REMAP[fill]; }
DS:26CE = edge; DS:26CD = fill;
```

Normals longer than 2048 (used only as sort normals, shapes.md §6) would give levels outside
−16..15 and index outside the row; only normals of shaded polygons matter, and in the shipped data
they are 2048 long (**Likely**, not checked over all files). Outline-only polygons are never shaded.
EGA (`DS:26DF` = 0): no shading.

### 2.2 `277a:029f` `poly_fill` (near)

If `CS:0A4F` ≠ 0: `DS:285C = n`; copy `CS:0C77[n]` → `DS:276C`, `CS:0C9F[n]` → `DS:2794`; call
`1d32:09ce(n, DS:276C, DS:2794)` (system library fill: n ≤ 2 → line/point, `DS:26CC` = 0 →
closed polyline in the edge colour, else fill with `DS:26CD` and outline with `DS:26CE` when they
differ — video spec). No return value.

### 2.3 `277a:02e4` `poly_fill_bitmap4` (near)

Only for flag `10h` (unused in the data). If `CS:0A4F == 4`: copies the four points as `029f` and
calls `2ec2:000d(colours, xs, ys)` with `DL/DH` = the edge/fill colour pair of the record (VGA or
EGA by `26DF`) interpreted as a **bitmap index**; `2ec2:000d` resolves it in the shape table's sprite
set (`DS:647C[CS:0A25].+0Ah`, or globally through `2edf:0007` when that is FFFFh) and draws it with
`07fe:000a` (a 4-point bitmap mapper in segment `07fe`, "ces.c", owned by sim_world in the map —
hand-off: it is a draw primitive), with `DS:26C3 = 1` around the call.

### 2.4 `277a:2b5d` `poly_add_centre16` (near)

For the n points: `px[i] += CS:0A4B; py[i] = CS:0A4D − py[i]` (16-bit).
`277a:35d0` `poly_add_centre32`: same on 32-bit values (`px`/`170D`, `py`/`1735`).

-----------------------------------------------------------------------------------------------

## 3. Part routines

### 3.1 `277a:05c6` `part_draw16(far variant*)` (far cdecl) — mode 0

```
DS = CS; ES:DI = variant; BP = vtx_ofs (CS:09A6);
if (ES != CS:09A4 || BP != CS:09A2) { CS:09A4 = ES; CS:09A2 = BP; zero CS:0A79[vtx_count] (words); }
count = variant.npolys (CS:03B7); DI = variant.poly_ofs;
while (count-- > 0) {                          /* dec, jge: npolys = 0 draws nothing */
    f = rec.flags; m = f & 3;
    if (m == 2) goto next;
    SI = rec.index_ofs; CS:09B5 = 0;
    if (m == 0) {
        if (f & 0x20) { if (poly_facing(rec.normal, first index) >= 0) CS:09B5 = 1; }
    } else if (poly_facing(rec.normal, first index) >= 0) goto next;   /* 277a:0346 */
    poly_colours();                            /* 01ba */
    behind = 0 (CS:03B9); n = 0;
    for (each index i until FFh) {
        st = vtx_state[i];
        if (st == 0) {
            vtx_state[i] = 1;
            e = vec_rotate(vtx[i], m_obj_eye) + e_pos (low words, 16-bit);   /* 4a0c */
            ex[i], ey[i], ez[i] = e;
            if (ey[i] < near_z) { vtx_state[i] = 3; behind = 1; }
            else { vtx_state[i] = 2;
                   vx[i] = ((i32)ex[i] << S) / ey[i];  vy[i] = ((i32)ez[i] << S) / ey[i]; }
        } else if (st != 2) behind = 1;        /* state 3 (or 1) */
        poly_idx[n++] = i*2;
    }
    if (behind) near_clip16();                 /* 2adf: builds px/py directly */
    else { if (n == 0) goto next; copy vx/vy of poly_idx → px/py; }
    poly_add_centre16();                       /* 2b5d */
    if (f & 0x10) poly_fill_bitmap4();         /* 02e4 */
    else { if (CS:09B3) clip2d16(); poly_fill(); }   /* 25ec, 029f */
next: DI += 8;
}
```

Notes: `ey < near_z` is a signed 16-bit compare; the projection `idiv` may overflow (INT 0,
render3d_math.md §1.4). A vertex found in state 1 (impossible in practice) is treated as behind.

### 3.2 `277a:07ae` `part_draw16s` — mode 3

As `05c6` except: the rotated vector's components are shifted by `obj_shift` (`CS:09AA`, which the
caller has set to `vtx_shift ≤ 0`: `sar` by `−obj_shift`; `shl` if positive) **before** adding
`e_pos` (which holds `e_pos16`, sign-extended); there is no near-plane test (every vertex gets state
2 and is projected); no `behind` flag.

### 3.3 `277a:03bb` `part_draw_shadow` — mode 0 with `DS:2403` ≠ 0

As `05c6` except:
* no culling and no shading: only `m == 2` polygons are skipped; `poly_colours` is not called:
  `DS:26CE = DS:26CD = DS:2402` (the adds are `0 + [2402]`), `DS:26CC = 1`;
* transform of a new vertex: `transpose(m_obj)` (back to object→world), `w = vec_rotate(v, m_obj)`,
  `w.z = 0` (flatten), `e = vec_rotate(w, m_cam) + e_pos` (low words), `transpose(m_obj)` again;
  then the same near test/projection. The shadow is the object squashed onto the horizontal plane
  through its (moved) origin; `2ecb:00ba` moves the origin to the ground point (render3d_shapes.md).
  Uses `CS:03BA` as its behind flag.

### 3.4 `277a:361d` `part_draw32` — modes 1 and 2

Same loop (counter `CS:361A`, behind flag `CS:361C`), culling/shading as `05c6`. New vertex:

```
r = vtx_rotate_shift(v, m_obj_eye, obj_shift);          /* 4cc8, i32[3] at CS:21E0, returns CF */
e.x = r.x + e_pos.x + CF;  e.y = r.y + e_pos.y + carry(e.x); e.z = r.z + e_pos.z + carry(e.y);
    /* the three 32-bit additions are adc chains (original bug, render3d_math.md §4.8) */
ex/17AD, ey/19AB, ez/1BA9 = e (low/high words)
if (e.y < near_z  /* signed 32 */) { state 3; behind = 1; }
else { state 2; (vx|1DA7, vy|1FA5) = proj32(e.x, e.z, e.y, focal); }   /* 3f6e */
```

After the index list: if `behind`: mode 1 → `near_clip32a` (`2f4e`), else `near_clip32b` (`3530`);
else copy the 32-bit projected points to `px/170D`, `py/1735` (n = 0 → next polygon). Then
`poly_add_centre32` (`35d0`); if `CS:09B3`: mode 1 → `clip2d32a` (`2caa`), else `clip2d32b`
(`3242`). Then `poly_fill` (low words only are passed to the fill). **Flag `10h` is ignored in the
32-bit modes** (no `02e4` call).

-----------------------------------------------------------------------------------------------

## 4. Clipping

All clippers are Sutherland–Hodgman over the closed polygon, walking `i = 0..n−1` with `prev`
starting at the last vertex, emitting into a temporary list and copying back. An intersection is
always computed **anchored at the outside vertex O towards the inside vertex I**:
`t = edge − O.a;  b = O.b + trunc(t · (I.b − O.b) / (I.a − O.a))` (a = clipped coordinate,
b = the other one; `trunc` = `idiv`, toward zero). No bound on the output count (≤ 20 assumed).

### 4.1 Near plane (eye space, `y = near_z`), results are already projected

* `277a:2adf` `near_clip16` (+ helper `2a8d`): n = `CS:0A4F`; for each edge `(prev, cur)`:
  cur behind & prev front → emit `X(cur)`; cur front & prev behind → emit `X(prev)` then cur;
  both front → emit cur; both behind → nothing. `X(b)` for the behind vertex b and front vertex a:
  `x = ex[b] + trunc((ex[a] − ex[b]) · (near − ey[b]) / (ey[a] − ey[b]))` (16×16→32 `imul`,
  32/16 `idiv`), same for z; the point is projected by `x << CS:0010`, `z << CS:0010` (16-bit
  `shl`, wraps) and stored **into the behind vertex's `vx/vy` slot** (harmless: behind vertices are
  never used unprojected), then copied to the output. Output count → `CS:0A4F`.
* `277a:2f4e` `near_clip32a` (+ `2ed7`): the same with 32-bit eye coordinates but the deltas and
  interpolation on the **low words** (`imul`/`idiv` 16-bit), the result sign-extended and added to
  the anchor's 32-bit value (`cdq; add; adc`), then shifted left `CS:0010` times as 32 bits
  (`shl/rcl` pairs).
* `277a:3530` `near_clip32b` (+ `346b`): full 32-bit: `(e_a − e_b) · (near − ey_b)` as 64-bit
  (`imul ecx`), `/ (ey_a − ey_b)` (`idiv ebx`), `+ e_b`, `shl eax, CS:0010`.

### 4.2 Screen window (after the centre is added)

Outcodes: bit 1 `x < DS:26C4`, bit 2 `x > DS:26C6` (x pass); bit 8 `y < DS:26C8`, bit 4
`y > DS:26CA` (y pass). The x pass (left and right together, one outcode per vertex) runs first into
`CS:0CC7/0CEF`, then the y pass back into `CS:0C77/0C9F`. For an edge with both ends outside on
different sides (`cl & ch == 0`, both non-zero) two points are emitted: first against prev's edge,
then against cur's. When the x pass leaves fewer than 2 points the y pass is skipped and the x-pass
list (0 or 1 points) is used.

* `277a:25ec` `clip2d16`: 16-bit values and interpolation.
* `277a:2caa` `clip2d32a` (+ `2b88` x edge, `2c19` y edge): 32-bit outcode compares (high word
  signed, then low word unsigned), interpolation on the low words (16-bit), result `cdq`-extended and
  added to the anchor's 32-bit coordinate; the edge value itself is stored sign-extended.
* `277a:3242` `clip2d32b` (+ `3070`, `3159`): full 32-bit interpolation (`imul edx`/`idiv ebx`).

After 2D clipping every point is inside the window, so only the low words matter for the fill.

-----------------------------------------------------------------------------------------------

## 5. Self-modifying code, hardware access

None: the routines write only data in `CS:` (listed in render3d_math.md §2.3) and DGROUP. No port
I/O; all output goes through `1d32:09ce` (system library → driver).

## 6. Port notes

* `/* PORT: */` The four part routines can be one C function with a mode switch; keep the three
  arithmetic variants of the clippers distinct (their rounding differs) and keep the `adc` carry
  chain in mode 1/2.
* The vertex cache is keyed on the vertex-array far pointer only; parts that share an array share
  the cached projection even across LOD/variant boundaries within one object (the key is reset by
  `2f0e:08e9` for every object: `CS:09A2 = CS:09A4 = 0`). A segment value of 0 never occurs for a
  loaded shape, so the reset forces a clear.
* Enhanced renderer: replace the 20-point lists and the 16-bit paths by float/64-bit geometry at
  native resolution; the colour logic (§2.1) and the part ordering (render3d_shapes.md) define the
  look and should be kept.
