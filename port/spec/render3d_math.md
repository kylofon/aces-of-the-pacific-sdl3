# render3d — part 1: 3Space math, camera, transform and projection (AP `277a` + helpers)

Part of the `render3d` spec (index: `render3d.md`). AP.EXE addresses in `work/AP_flat.exe`
(`SSSS:OOOO`, DGROUP `3EA4`, `DS:xxxx`). Segment **`277a`** is the hand-written 386 assembly core of
the Dynamix 3Space library ("ts2"; 27.5 KB = code + data). Its routines keep all their state **in the
code segment** (`CS:xxxx`, written with `cs:` overrides or with `DS = CS`); the port keeps those bytes
in the emulated image like any other data. This part covers the math library, the object state block,
the camera, the transform and the projection. The polygon routines of the same segment are in
`render3d_poly.md`.

Confidence: **Verified** (read in the disassembly, arithmetic traced) unless marked **Likely** /
**Unknown**. Register interfaces are given for the asm routines; "far cdecl" = `retf`, arguments on
the stack (`[sp+4]` = first), caller pops.

-----------------------------------------------------------------------------------------------

## 1. Projection maths (summary for the port and for the Enhanced renderer)

### 1.1 Units and axes

* **Angles**: `u16`, `10000h` = 360°, so `4000h` = 90°. Table resolution is 1/4096 turn (`angle >> 4`).
* **Fixed point**: rotation matrices and unit vectors are **2.14** (`4000h` = 1.0), products are
  `(a*b) >> 14` taken as the **high word of `(a*b) << 2`** (arithmetic floor, never rounded).
* **World**: `i32` x east, y north, z up (world.md). **Object** axes: x right, y forward (nose),
  z up (shapes.md). **Eye** axes: x right, **y = depth (forward)**, z up. The screen maps eye x to
  the right and eye z upwards.
* **Rotation convention**: row vectors. A matrix `M` (3×3 `i16`, row-major) maps object → parent as
  `v_parent[j] = Σ_i v_obj[i] · M[i][j] >> 14` (`277a:4a0c`); the rows of `M` are the object axes
  expressed in the parent frame. World → eye uses the **transposed** camera matrix.

### 1.2 Matrix from angles (`277a:457a`, angles `a[0]`=pitch p, `a[1]`=roll r, `a[2]`=heading h)

With `S(x) = sin`, `C(x) = cos` from the 4096-step table (§3.1), each product formed through
sum/difference identities (see §4.3 for the exact integer evaluation):

```
row0 (right) = ( Cr·Ch − Sp·Sr·Sh ,  Sp·Sr·Ch + Sh·Cr ,  −Sr·Cp )
row1 (fwd)   = ( −Sh·Cp           ,  Cp·Ch            ,   Sp    )
row2 (up)    = ( Sp·Sh·Cr + Ch·Sr ,  Sr·Sh − Sp·Cr·Ch ,  Cp·Cr  )
```

i.e. `M = Ry(r) · Rx(p) · Rz(h)` in row-vector order (roll first, then pitch, then heading).
Heading is counter-clockwise seen from above (h = 4000h turns the nose from north to west), pitch
positive = nose up, roll positive = right wing down. Type byte: 0 all angles 0 (identity), 1 only
heading (2×2 block), 3 general (pitch ≠ 0), 2 roll ≠ 0 but pitch = 0 (evaluated with the general
formula).

### 1.3 Camera and object transform (per frame / per object)

```
/* per frame: 277a:004b */
Mcam  = matrix(cam.angles) [· extra look rotation]      CS:09B6, then transposed (world→eye)
/* per object: 277a:22f8 + 277a:237d */
D     = obj.pos − cam.pos                    (i32 ×3, CS:09EF)
E     = D · Mcam^T  (i32 dot, >>14, floor)   eye position of the origin, CS:09FB/09FF/0A03
Moe   = Mobj · Mcam^T                        object→eye matrix, CS:09C9
O     = (D >> k) · Mobj^T                    eye→object vector in object axes, CS:0A07 (for culling/sort)
L     = light · Mobj^T                       light in object axes, CS:0A3B (for shading)
```

`k` (`CS:09AE`) is chosen per object so that `(max(|Ex|,|Ey|,|Ez|) + R) >> k < 3FACh` (16300); the
object is then drawn in 16-bit arithmetic with every length divided by `2^k`. Vertices are
`i16` object coordinates scaled by `2^s` (`s` = shape header byte 3); the net vertex shift is
`s − k` (`CS:09AC`, always ≤ 0: **a right shift**, never a model/world scale — see §6).

### 1.4 Perspective projection

`S` = camera shift (`camera+0`, `CS:0A49`, **7** for the sim view), focal length `f = 2^S = 128`
pixels (`CS:0A47`), screen centre `(cx, cy)` = `(x0 + w/2, y0 + h/2)` of the view window
(`CS:0A4B/0A4D`; `cy` can be overridden per cockpit view, `5440:03aa`).

```
vertex in eye space (x, y, z), y = depth, visible if y >= near
sx = cx + trunc((x << S) / y)          /* i32 dividend, i16 divisor: idiv, toward zero */
sy = cy − trunc((z << S) / y)
```

* Near plane: `near` = `CS:000E` = `2^n`. World objects are drawn with `n = S − 3` (**16**, f/8,
  `5440:0269` calls `277a:0012(S−3)`); default (`277a:0037`) is `n = S` (128). `CS:0010` = `S − n`.
* A point clipped exactly onto the near plane projects without a division: `sx = cx + (x << (S−n))`.
* Horizontal field of view with the full 320-pixel window: `2·atan(160/128)` = 102.7°; vertical
  (200 rows) `2·atan(100/128)` = 76°. Pixels are treated as square (no 320×200 aspect correction):
  on a 4:3 display the picture is stretched vertically by 1.2. The Enhanced renderer must keep
  `f = 128` at 320 pixels (scale `f` with the width) and decide whether to correct the aspect.
* 32-bit path (draw modes 1/2, objects crossing the near plane, `277a:3f6e`): `x·f/y` is computed
  as `x · (f/y as a 0.32 fraction)`; **when `y <= f` the point is not divided at all**
  (projected `= (x, z)` unscaled) — a quirk the port must keep (§4.8).
* Divide overflow: in the 16-bit paths `(x << S) / y` can exceed 16 bits for points near the near
  plane and far to the side; the `idiv` then raises INT 0. The platform's handler (`1d32:69cc`,
  installed by `divzero_install` `1d32:69a2`; platform spec) re-executes the division with the
  dividend **halved** (`sar dx,1; rcr ax,1` for a word divide, `sar ax,1` for a byte divide) until it
  fits: the projected coordinate becomes `q / 2^j` for the smallest `j` that fits in 16 bits
  (a folded, still on-screen-side value, later clipped). On a 386 the saved IP points at the `F6/F7`
  opcode; otherwise the handler backs IP up by 2 (wrong for 32-bit `66h`-prefixed divides — those do
  not overflow in the renderer). Division by zero loops forever (the dividend halves to 0 or −1).
  **Port**: implement `idiv16` as "halve the dividend until the quotient fits" to match.

### 1.5 Visibility, LOD and draw mode (per object, `2f0e:0008` + `2f0e:08e9`, spec in `render3d_poly.md`)

With `E` the eye position of the origin and `R` = radius << s (`CS:0A2D`):
* culled if `Ey + R < near`;
* apparent size `A = min(256, (f·R) / max(Ey − R, f))` (`277a:304c`), culled if 0; then scaled by
  the shape-table LOD factor (`277a:3968`); the first LOD with `size >= A` is drawn;
* culled if the projected nearest corner `(|Ex|−R, Ey+R, |Ez|−R)` is right of `x1` or above `y0`;
* clipping needed (`CS:09B3`) unless the farthest corner `(|Ex|+R, Ey−R, |Ez|+R)` projects inside;
* draw mode: 0 = 16-bit, no near clipping; 3 = 16-bit with vertex shift; 1/2 = 32-bit with near-plane
  clipping (2 = large objects, 32-bit interpolation).

-----------------------------------------------------------------------------------------------

## 2. Data

### 2.1 The camera ("view") record — 16h bytes, `271b:0251`

Created by `271b:0251(eye)` (malloc 16h; `271b:02a6` frees it). The sim's view is `DS:437E`
(= `DS:43D8`), made by `5440:009c` with `eye = DS:4368`.

| Off | Type | Field | Init | Read by |
|---|---|---|---|---|
| 00 | u16 | `S`, projection shift (focal = `1<<S`) | 7 | `277a:004b` → `CS:0A49`; also sim code (`FUN_… << (*DS_437E & 31)`) |
| 02 | u16 | pointer to the eye record (below) | arg | `277a:004b` |
| 04 | i16[3] | extra look rotation (pitch, roll, heading), e.g. view direction | 0 | `277a:004b` → `CS:21B6` |
| 0A | i16 | window x0 | 0 | `277a:004b` → `DS:26C4`; `5440:03aa` |
| 0C | i16 | window y0 | 0 | → `DS:26C8` |
| 0E | i16 | window width | 140h | → `DS:26C6 = x0+w−1`, `cx = x0 + w/2` |
| 10 | i16 | window height | C8h | → `DS:26CA = y0+h−1`, `cy = y0 + h/2` |
| 12 | u16 | DS pointer to the 256-byte shades table | 0 (`DS:4092` in the sim) | → `CS:21EC` |
| 14 | u16 | DS pointer to a 256-byte colour remap table, 0 = none | 0 | → `CS:21EE` |

The sim sets `+0A..+10` from `DS:06AD..06B3` (0, 0, 320, 200 at start; the cockpit code changes
them: sim_flow). `SHADES1` is read into `DS:4092` by `519d:008a` (sim_flow's `ovl.c`, 256 bytes).

**Eye record** (`DS:4368` for the sim; any object record with the same head works): `+02` i32 x,
`+06` i32 y, `+0A` i32 z (world), `+0E` u16 pitch, `+10` roll, `+12` heading. Written by the view
code (sim_flow `1c30`).

### 2.2 Matrix record (19 bytes)

`i16 m[3][3]` row-major (`+0,+2,+4 / +6,+8,+A / +C,+E,+10`), `u8 type` at `+12h` (0 identity, 1
heading only, 2/3 general, §1.2). Every matrix routine honours the type (skips zero terms), so the
type must be kept exact.

### 2.3 `277a` code-segment data (the object state block and scratch)

All zero in the file unless noted. "Per frame" = set by `277a:004b`; "per object" = set by
`2f0e:08e9` and `277a:22f8/237d/24ef`.

| CS: | Type | Name | Meaning |
|---|---|---|---|
| 0008 | i16[3] | `light_world` | light vector (length 200h) from `277a:0152`; copied to `DS:6492..6497` |
| 000E | u16 | `near_z` | near-plane depth `2^n` |
| 0010 | u16 | `near_shift` | `S − n` |
| 03B7 | u16 | | polygon counter of `277a:03bb` and `05c6` |
| 03B9/03BA | u8 | | "a vertex is behind the near plane" flag of `05c6` / `03bb` |
| 09A2 | u16:u16 | `vtx_cache_key` | offset/segment of the last vertex array transformed (cache key) |
| 09A6 | u16 | `vtx_ofs` | vertex array offset of the current part (in the shape segment) |
| 09A8 | u16 | `vtx_count` | number of vertices of the current part |
| 09AA | i16 | `obj_shift` | shape header byte 3 (`s`); replaced by `09AC` in the scaled path |
| 09AC | i16 | `vtx_shift` | `s − k` (≤ 0): vertices are shifted right by `−09AC` |
| 09AE | i16 | `obj_down` | `k`, down-shift that makes the object fit 16 bits |
| 09B0 | u8 | `draw_mode` | 0..3 (§1.5) |
| 09B1 | u8 | | cleared per frame, no other use found (**Unknown**) |
| 09B2 | u8 | `force_clip` | set by `5440:03aa` when the view centre is moved (`DS:19F2`); forces `09B3` |
| 09B3 | u8 | `need_clip` | current object needs 2D clipping |
| 09B5 | u8 | `backlit` | two-sided polygon seen from behind: light with the negated normal |
| 09B6 | mat | `m_cam` | camera matrix, transposed (world→eye) |
| 09C9 | mat | `m_obj_eye` | object→eye |
| 09DC | mat | `m_obj` | object matrix (kept transposed between objects) |
| 09EF | i32[3] | `d_world` | object position − eye position |
| 09FB | i32[3] | `e_pos` | object origin in eye space (x `09FB`, y `09FF`, z `0A03`); low words used by the 16-bit modes |
| 0A07 | i16[3] | `eye_in_obj` | object origin − eye, in object axes, `>> k` |
| 0A0D | i16[3] | `e_pos16` | `e_pos >> k` |
| 0A13 | i32[3] | `cam_pos` | eye position |
| 0A1F | u16[3] | `cam_ang` | eye angles (rewritten from the combined matrix when a look rotation is set) |
| 0A25 | u16 | `shape_tbl` | shape-table index (set by `271b:0007`) |
| 0A27 | far | `shape_ptr` | shape header |
| 0A2B | u16 | `state_ptr` | pointer to the instance state bytes (instance `+14h`) |
| 0A2D | i32 | `radius` | radius `<< s` |
| 0A31 | i32 | `e_dist` | `max(|Ex|,|Ey|,|Ez|)` |
| 0A35 | i32 | `e_near` | nearest depth of the box (or `Ey − R`) |
| 0A39 | u16 | `app_size` | apparent size 0..256 (LOD key) |
| 0A3B | i16[3] | `light_obj` | light in object axes |
| 0A41 | i32 | `e_depth` | `max(Ey, near_z)`; `0A45` = `e_depth >> k` (i16) |
| 0A47 | u16 | `focal` | `1 << S` |
| 0A49 | u16 | `proj_shift` | `S` |
| 0A4B/0A4D | i16 | `cx`, `cy` | screen centre |
| 0A4F | u16 | `poly_n` | vertices in the polygon being built |
| 0A51 | u16[20] | `poly_idx` | vertex index×2 of each polygon vertex |
| 0A79 | u16[255] | `vtx_state` | per vertex: 0 not done, 1 transforming, 2 projected, 3 behind near |
| 0C77/0C9F | i16[20] | `px`, `py` | polygon screen x / y (low words) |
| 0CC7/0CEF | i16[20] | | clipper temporaries (low words) |
| 0D17/0F15/1113 | i16[255] | `ex`, `ey`, `ez` | eye coordinates per vertex (low words) |
| 1311/150F | i16[255] | `vx`, `vy` | projected coordinates per vertex, **without** the centre |
| 170D/1735/175D/1785 | i16[20] | | high words of `px`, `py` and the clipper temporaries (modes 1/2) |
| 17AD/19AB/1BA9 | i16[255] | | high words of `ex`, `ey`, `ez` (modes 1/2) |
| 1DA7/1FA5 | i16[255] | | high words of `vx`, `vy` (modes 1/2) |
| 21A3 | mat | `m_look` | extra look rotation |
| 21B6..21EB | | scratch | `21B6` vec/angles, `21BC` normal, `21C2` result, `21E0` i32[3] result of `4cc8` |
| 21EC | u16 | `shades` | DS pointer to SHADES (camera `+12h`) |
| 21EE | u16 | `remap` | DS pointer to the colour remap table or 0 (camera `+14h`) |
| 21F8 | i8[8][32] | `shade_ofs` | shading offsets (initialised, dumped in `render3d_poly.md`) |
| 3840..384D | | | scratch of `4afa`/`4cc8` (matrix column, 48-bit accumulator, shift) |
| 361A/361C | | | polygon counter / behind flag of `361d` |
| 3A28/3A38 | u16[8] | | `1,4,16,…,16384` (low/high words of `4^i`) for `isqrt32` |
| 3E1A | u16 | | exponent of the last `277a:3e1c` |
| 5664 | i16[1025] | `cos_tab` | §3.1 |
| 6028 | i8[512] | `atan_corr` | §3.2 |
| 63A6 | i16[961] | `asin_tab` | §3.3 |

Limits that follow from the layout: 255 vertices per vertex array (byte index, FFh = end), **20
vertices per polygon after clipping** (no bounds check: a polygon clipped to more than 20 points
overwrites the next array — cannot happen with the shipped data, whose polygons have ≤ 10 points,
**Likely**).

-----------------------------------------------------------------------------------------------

## 3. Tables

### 3.1 `cos_tab` `CS:5664`, 1025 `i16`

`cos_tab[i] = trunc(16384 · cos(i·π/2048))`, i = 0..1024 (`[0]` = 4000h, `[512]` = 11585,
`[1024]` = 0); verified identical to that formula for all entries. Lookup (inlined everywhere,
also as `277a:5e71`):

```c
int16 cos16(uint16 a) {            /* 277a:5e71 */
    int16 i = (int16)a >> 4;       /* arithmetic: -2048..2047 */
    if (i < 0) i = -i;             /* note: -1>>4 = -1, so cos(-1) uses [1] but cos(1) uses [0] */
    return i < 0x400 ? cos_tab[i] : -cos_tab[0x800 - i];
}
int16 sin16(uint16 a) { return cos16(a + 0xC000); }   /* 277a:5e66 = cos(a − 90°) */
```

### 3.2 `atan_corr` `CS:6028`, 512 `i8`

`q + atan_corr[q] = trunc(atan(q/512) · 4096/2π)` for q = 0..511 (verified for all). Used by the
`atan2` routines (§4.4).

### 3.3 `asin_tab` `CS:63A6`, 961 `i16`

`u = |v| >> 2` (v in 2.14); index `i = u >> 3` for `u <= 0DFFh` (entries 0..1BFh, step 1/512),
else `i = u − 0C40h` (entries 1C0h..3C0h, step 1/4096 near ±1). Value = `asin` in 16-bit angle
units, within ±1 of `round(asin(x)·65536/2π)` (482 of 961 equal the rounded value; the rest differ
by 1). **Port: copy the three tables from the executable image** (they are not reproducible by a
single formula for `asin_tab`).

-----------------------------------------------------------------------------------------------

## 4. Functions — matrices, camera, transform

### 4.1 `277a:0012` `set_near(n)` / `277a:002d` `get_near_n()` / `277a:0037` `reset_near()` / `277a:0046`

* `0012` (far cdecl, `n`): `CS:000E = 1 << n; CS:0010 = CS:0A49 − n`.
* `002d`: returns `CS:0A49 − CS:0010` (= current `n`).
* `0037`: `CS:000E = CS:0A47; CS:0010 = 0` (near = focal).
* `0046` (not in the index, no callers found): returns `CS:0010`.

Used by `5440:0269`: `set_near(get_near_n() − 3)` before every world object, `reset_near()` after.
(Because `004b` resets `n = S` each frame, world objects always get `n = S − 3`.)

### 4.2 `277a:004b` `cam_begin_frame(camera *c)` (far cdecl)

1. `ES = CS`. `CS:0A13..0A1E` ← 6 words from `eye+02` (position), `CS:0A1F..0A24` ← 3 words from
   `eye+0E` (angles), where `eye = c->[+02]`.
2. `S = c[+0]`: `CS:0A49 = S`; `CS:0A47 = CS:000E = 1 << S`; `CS:0010 = 0`.
3. `CS:21EC = c[+12h]`, `CS:21EE = c[+14h]`.
4. View window: `DS:26C4 = x0`, `DS:26C6 = x0 + w − 1`, `DS:26C8 = y0`, `DS:26CA = y0 + h − 1`,
   `CS:0A4B = x0 + (w >> 1)` (logical shift), `CS:0A4D = y0 + (h >> 1)`.
5. `CS:09B2 = CS:09B1 = 0`.
6. `CS:21B6..21BB` ← `c[+04..+09]`; `mat_from_angles(CS:21B6 → m_look CS:21A3)`.
7. If `m_look.type == 0`: `mat_from_angles(cam_ang → m_cam)`.
   Else: `mat_from_angles(cam_ang → CS:09C9)`; `mat_mul(m_look, CS:09C9 → m_cam)` (i.e.
   `m_cam = m_look · m_eye`: the look rotation is applied in the eye's own frame);
   `mat_to_angles(m_cam → cam_ang)` (so `cam_ang` = the effective view angles, used by the sky code).
8. `mat_transpose(m_cam)` in place.

Callers: `5440:03aa` (3D view), `277a:004b` is also used by other views through the same record
(see `render3d_world.md`).

### 4.3 `277a:457a` `mat_from_angles(u16 ang[3], mat *m)` (far cdecl, returns `m`)

`type = 3 if ang[0]; else 2 if ang[1]; else 1 if ang[2]; else 0` → `m[12h]`.
* type 0: identity (4000h on the diagonal).
* type 1 (`h = ang[2]`): `m = [[C h, S h, 0], [−S h, C h, 0], [0, 0, 4000h]]`.
* types 2, 3 (general), with `c(x) = cos16(x)`, `s(x) = sin16(x)`, `/2` = `sar 1`, and
  `mul(a,b) = (a*b) >> 14` taken as the high word of `(a*b) << 2`, in this order:
  exact sequence (`p = ang[0]`, `r = ang[1]`, `h = ang[2]`):
  ```
  m[1][2] = sp = s(p)
  A = c(r−h)/2 + c(r+h)/2;  B = c(r−h)/2 − c(r+h)/2
  m[0][0] = A − mul(sp, B);         m[2][1] = B − mul(sp, A)      /* stored at +0Eh */
  A = s(h+r)/2 + s(h−r)/2;  B = s(h+r)/2 − s(h−r)/2              /* A = Sh·Cr, B = Ch·Sr */
  m[0][1] = mul(sp, B) + A;         m[2][0] = mul(sp, A) + B      /* +02h, +0Ch */
  m[1][1] = c(p+h)/2 + c(p−h)/2                                   /* +08h */
  m[2][2] = c(p+r)/2 + c(p−r)/2                                   /* +10h */
  m[0][2] = −( s(r−p)/2 + s(r+p)/2 )                               /* +04h, = −Sr·Cp */
  m[1][0] = −( s(h−p)/2 + s(h+p)/2 )                               /* +06h, = −Sh·Cp */
  ```
  Each `/2` truncates the table value (`sar`), each sum is 16-bit.
  The rows are orthonormal (checked algebraically: row1·row2 = row0·row2 = 0), matching §1.2.

### 4.4 Angle extraction

* `277a:6228` `atan2_16(int16 x, int16 y)` (far cdecl) → `u16` angle of the vector (x, y) measured
  from +x towards +y. Signs saved, `|x|`, `|y|`. `x == 0`: `y == 0` → 0, else 400h. `y == 0` → 0.
  `x == y` → 200h. `x > y`: `q = (y·512)/x` (unsigned 24/16 divide), `a = q + atan_corr[q]`;
  `x < y`: `q = (x·512)/y`, `a = 400h − (q + atan_corr[q])`. Then `x < 0` → `a = 800h − a`;
  `y < 0` → `a = 1000h − a`. Return `a << 4` (16-bit wrap: `1000h << 4 = 0`).
* `277a:62c8` `atan2_32(i32 x, i32 y)`: same on 32-bit values; both are normalised to 9 fraction
  bits by shifting the larger right / the smaller left (loop of 9 steps, `bp` counter), then
  `q = LDIV(numerator, denominator)` (Borland `0000:1d69`), same table and quadrant fix-up.
* `277a:6b28` `asin16(int16 v)` (v 2.14) and `277a:6b5d` `acos16(v) = 4000h − asin16(v)`
  (sign handled so that `acos(−v) = 8000h − acos(v)`), both via `asin_tab` (§3.3).
* `277a:49a4` `mat_to_angles(mat *m, u16 ang[3])` (far cdecl): `ang[0] = asin16(m[+0Ah])`
  (pitch = asin of `m[1][2]`). If `|ang[0]| == 4000h`: `ang[1] = 0`, `ang[2] = atan2_16(m[+0],
  m[+2])`. Else `ang[1] = atan2_16(m[+10h], −m[+04h])`, `ang[2] = atan2_16(m[+08h], −m[+06h])`.

### 4.5 Matrix products

* `277a:41e0` `mat_mul(mat *a, mat *b, mat *c)` (far cdecl, returns `c`): `c = a × b`
  (`c[i][j] = Σ_k a[i][k]·b[k][j]`, each product 32-bit signed, the three summed in 32 bits,
  result = high word of `sum << 2`). Type rules: `a.type == 0` → `c = b` (copy, with b's type);
  `b.type == 0` → `c = a`; both 1 → 2×2 product, `c.type = 1` (row/col 2 = 0/4000h); `a` type 1
  and `b` general → rows 0..1 from the 2×2·3×3 product, row 2 copied from `b`, `c.type = 3`; `a`
  general and `b` type 1 → column 2 copied from `a`, the rest from the 3×2 product, `c.type = 3`;
  otherwise full product, `c.type = 3`. `c` may not alias `a`/`b` (row-by-row writes).
* `277a:4556` `mat_transpose(mat *m)` (far, `[sp+4]`): swaps `+2↔+6`, `+4↔+0Ch`, `+0Ah↔+0Eh`.
* `277a:4a0c` `vec_rotate` (near, **AX** = `i16 v[3]`, **BX** = mat, **CX** = out `i16[3]`):
  type 0 → copy; type 1 → `out.x = (m00·x + m10·y)`, `out.y = (m01·x + m11·y)`, `out.z = z`;
  else `out[j] = Σ_i v[i]·m[i][j]`. Each sum 32-bit, result high word of `sum << 2`
  (**no overflow check**: a sum ≥ 2^29 wraps).
* `277a:4ae5` `vec_rotate(v, m, out)` far cdecl wrapper of `4a0c`, returns `out`.
* `277a:4afa` (near, **BX** = `i32 v[3]`, AX/CX/DX = matrix column `c0,c1,c2`): 48-bit
  `Σ v[i]·c[i]` (sign-magnitude 32×16 products; the third term is skipped when `c2 == 0`), result in
  `DX:AX:CX`. Stores its arguments/accumulator in `CS:3840..384B`.
* `277a:4c27` `lvec_rotate` (near, **AX** = `i32 v[3]`, **BX** = mat, **CX** = out `i32[3]`):
  type 0 → copy; type 1 → `out.z = v.z`; else `out.z` via `4afa` with column 2; `out.x`, `out.y` via
  `4afa` with columns 0 and 1; each result = bits 14..45 of the 48-bit sum (`(sum << 2) >> 16`,
  floor). `277a:4cb3` = far cdecl wrapper (returns `out`).
* `277a:4cc8` `vtx_rotate_shift` (near, **AX** = `i16 v[3]`, **BX** = mat, **CX** = out `i32[3]`,
  **DX** = shift `s` (→ `CS:384C`)): type 0 → `out[i] = sext(v[i]) << s`; type 1 → `out.x/y` =
  `sext32(m00·x + m10·y)` as a 48-bit value `<< (2 + s)`, high 32 bits (i.e. `sum >> (14 − s)`,
  floor), `out.z = sext(z) << s`; else the same for all three columns. **The carry flag on return
  is used by the caller** (`361d`, §4.7): it is the last bit shifted out of the top of the `z`
  result (type 2/3: the sign of the 32-bit `z` sum; type 1 or 0 with `s >= 1`: the sign of `v.z`;
  type 0 with `s == 0`: 0; type 1 with `s == 0`: the sign of the 32-bit `y` sum).

### 4.6 `277a:0152` `set_light(u16 a0, u16 a2)` (far cdecl)

`CS:21B6 = (a0, 0, a2)`; `mat_from_angles(CS:21B6 → CS:21A3)` (**overwrites `m_look`**; harmless
because `004b` rebuilds it next frame and `0152` is called after `004b`); then
`vec_rotate((0, 200h, 0), CS:21A3 → CS:0008)`, copies `CS:0008..000D` to `DS:6492..6497` and
returns `CS:0008` in AX. So the light vector is the forward axis of the orientation (pitch `a0`,
heading `a2`), length 512. Callers: `5440:03aa` with `DS:51D9/51DB` (sun direction, sky part),
`7074:0000` (`ts_init`).

### 4.7 Per-object set-up (called from `ts_draw` `2f0e:08e9`)

* `277a:22f8` `obj_set_position(instance *o)` (far cdecl): `CS:21B6 = o[+0Eh..+13h]` (angles);
  `d_world = o[+02h..+0Dh] − cam_pos` (i32); `lvec_rotate(d_world, m_cam → e_pos)`;
  `e_depth = e_pos.y < near_z ? near_z : e_pos.y` (signed 32-bit compare with the u16 `near_z`).
* `277a:237d` `obj_set_orientation()` (far, no args): `mat_from_angles(CS:21B6 → m_obj)`;
  `mat_mul(m_obj, m_cam → m_obj_eye)`; `mat_transpose(m_obj)`;
  `e_dist = max(|e.x|, |e.y|, |e.z|)` (i32); `t = (e_dist + radius) >> obj_shift` (arithmetic);
  `k = obj_shift; while (t >= 3FACh as unsigned 32) { t >>= 1 (logical); k++ }`;
  `obj_down = k`; `vtx_shift = obj_shift − k`;
  `CS:0A45 = (i16)(e_depth >> k)`; `e_pos16 = (i16)(e_pos >> k)` (each `sar`, low word);
  `CS:21B6 = (i16)(d_world >> k)`; `vec_rotate(CS:21B6, m_obj(transposed) → eye_in_obj)`;
  `vec_rotate(light_world CS:0008, m_obj → light_obj)`. (**Note**: the shifts use the full
  `obj_down`, not `k − s`; `d_world >> k` is in world units / 2^k while the vertices are in
  `2^s`-scaled units, consistent with `vtx_shift = s − k`.)
* `277a:24ef` `obj_near_depth()` (far): if shape flags & 20h (no box): `e_near = e.y − radius`.
  Else, with `mo = m_obj_eye` column 1 (`+02, +08, +0Eh`) and the box `min = hdr+0Eh.., max =
  hdr+14h..` (shapes.md §2): `e_near = Σ_axis (m ≠ 0 ? min(mul(box_min,m), mul(box_max,m)) : 0)`
  (each `mul` = high word of `(a·m) << 2`), then `e_near = (e_near << obj_shift) + e.y` (32-bit).

### 4.8 Vertex transform and projection routines

* `277a:0346` `poly_facing` (near; **AL** = normal vertex index, **AH** = first vertex index,
  **BP** = vertex array offset, **ES** = shape segment): `n = vtx[AL]` → `CS:21BC`;
  `p = (vtx[AH] >> −vtx_shift) + eye_in_obj` (each component `sar` then 16-bit add) → `CS:21C2`;
  returns `DX:AX = n·p` (32-bit, `277a:4ef8`). `< 0` = front facing. (With `vtx_shift` from the
  per-object set-up: in the 32-bit modes `vtx_shift` is still `s − k` and `eye_in_obj` scaled by
  `2^−k`, so the test is done at 16-bit precision in every mode.)
* **16-bit vertex transform** (inline in `05c6`/`07ae`/`03bb`, see `render3d_poly.md`):
  `e = vec_rotate(v, m_obj_eye)`; mode 3: each component `sar −vtx_shift` (or `shl` if > 0,
  never happens); `e += e_pos` (low words, 16-bit wrap); state 3 if `e.y < near_z` (signed 16-bit
  compare), else project: `vx = ((i32)e.x << S) / e.y`, `vy = ((i32)e.z << S) / e.y` (`idiv`,
  shift done as `<< 8` by byte moves when `S >= 8`, then single shifts).
* **32-bit vertex transform** (inline in `361d`): `r = vtx_rotate_shift(v, m_obj_eye, obj_shift)`
  (i32 ×3, `CS:21E0`); `e.x = r.x + e_pos.x + CF` (CF from `4cc8`), `e.y = r.y + e_pos.y + CF`,
  `e.z = r.z + e_pos.z + CF` (**all three additions are `adc` chains**: each receives the unsigned
  carry out of the previous 32-bit addition — an original bug, ±1 unit; keep it). State 3 if
  `e.y < near_z` (signed 32-bit), else `(vx, vy) = proj32(e.x, e.z, e.y, focal)`.
* `277a:3f6e` `proj32` (near, stack: `i32 x @+4, i32 z @+8, i32 y @+0Ch, i32 f @+10h`, results
  replace x and z on the stack; caller pops them): saves `y`/`f` to `DS:2612..261D`, `x` to
  `DS:260E`, `z` to `DS:2616` (scratch, no other reader found). `sgn = sign(y) ^ sign(f)`;
  `|y|`, `|f|`. If `|y| == |f|`: return `(x, z)` negated if `sgn` (**note**: the negation applies to
  the stack copies at `+4/+6` and `+8/+0Ah`). Normalise: shift `|y|` and `|f|` left together (by 16
  if `|y| < 10000h`, by 8 if `< 1000000h`, then 1 at a time) until bit 31 of `|y|` is set. Let
  `Yh`/`Fh` be the high words. If `Yh <= Fh` → **return (x, z) unchanged** (no projection when
  `|y| <= |f|` roughly). Else `R = ((Fh:Fl) / Yh)` as a 32-bit fraction (`q1 = (Fh:Fl)/Yh`,
  `q2 = (rem:0)/Yh`), and for each of x, z (skipped when 0): `|v|·R >> 32` computed from the
  16×16 partial products (the lowest product dropped: truncation), sign = `sign(v) ^ sgn`.
* `277a:2fee` `pt_add_centre(i32 p[2])` (far, 386): `p[0] += cx; p[1] = cy − p[1]`.
* `277a:3010` `pt_project(i32 in[3], i32 out[2])` (far, 386): `out[0] = (focal·in[0]) / in[1]`,
  `out[1] = (focal·in[2]) / in[1]` (64/32 `idiv`, truncation; `focal` zero-extended).
* `277a:304c` `apparent_size(i32 v[2])` (far, 386): `(focal·v[0]) / v[1]` as i32 in DX:AX.

-----------------------------------------------------------------------------------------------

## 5. Functions — vector and scalar library (`277a`, shared with the simulation)

`vec` = `i16[3]`, `lvec` = `i32[3]` (x, y, z at +0/+4/+8). All far cdecl unless noted; "ret"
= value in AX (DX:AX for 32-bit).

### 5.1 Scalars

| Address | Name | Behaviour |
|---|---|---|
| `3968` | `mul_shr8(a, b)` | `(i16)((a·b) >> 8)` (bits 8..23 of the 32-bit product) |
| `3978` | `mul_shr10(a, b)` | `(i16)((a·b) >> 10)` |
| `3990` | (near) | CX = u16 → BX = index of its top set bit (0 if CX < 2) — helper of the square roots |
| `39a2` | `isqrt16(u16 n)` | `n <= 200`: count odd numbers subtracted → `floor(sqrt(n))`; else bit-by-bit root with the `(r+b)^2` trial update (`es`/`si`/`dx` registers), result `floor(sqrt(n))` (**Likely** exact floor) |
| `3a58` | `isqrt32(u32 n)` | high word 0 → `isqrt16`; else digit-by-digit root using `CS:3A28/3A38` (`4^i`) and a computed jump into an unrolled shift chain; `floor(sqrt(n))`, `7FFFh` if the top two bits are set (**Likely**) |
| `3b3c` | `ldist3(lvec *a, lvec *b)` | `|d|` per axis (32-bit), sorted `mx >= md >= mn`; `mx + (md>>2) + (md>>4) + (md>>5) + (mn>>2)` where each shift applies to the running value (`md>>2`, then that `>>2`, then `>>1`) — ≈ `mx + 11/32·md + 1/4·mn`, u32 |
| `3b8b` | `ldist3v(u32 a, u32 b, u32 c)` | same on three given (non-negative) values |
| `3bfc` | `ldist2(lvec *a, lvec *b)` | 2D (x, y): `mx + (mn>>2) + (mn>>3)` (running shifts) |
| `3c36` | `ldist2v(u32 a, u32 b)` | same on two values |
| `3c6a` | `dist2_16(i16 a, i16 b)` | `|a|`,`|b|` (16-bit), `mx + (mn>>2) + (mn>>3)` |
| `3c90` | `log_key(u32 v)` | monotonic 16-bit key: `v == 0` → 0; else `hi byte = index of the top set bit`, `lo byte` = the 8 bits following the top bit (`1` → 0000h, `2` → 0100h, `3` → 0180h, `10000h` → 1000h). Used as a depth-sort key (`33d1`) |
| `3cfc` | `mul32(i16 a, i16 b)` | `(i32)a·b` |
| `3d05` | `muls(i16 a, i16 b, n)` | `((i32)a·b) >> (n & 31)` (arithmetic, via `3d5d`) |
| `3d14` | `lmul(i32 a, i16 b)` | low 32 bits of `a·b` (signed; `|a|·|b|` then sign) |
| `3d52` | `lsar(i32 v, n)` | `v >> (n & 31)` arithmetic |
| `3dac` | (near) | overflow test for `3dc1`: CF = `|num| > 32767·|den|` (DX:AX = |num|, BX = |den|) |
| `3dc1` | `ldiv_sat(i32 num, i16 den)` | `num/den` (`idiv`, toward zero); if `|num| > 32767·|den|` returns `7FFFh` or `8000h` by the sign (DX = 0). `den == 0` and `num == 0` → `idiv` by zero (INT 0) |
| `3e1c` | `lnorm(i32 v, int *exp)` | `m`, `e` with `v ≈ m << e`, `|m| <= 7FFFh`: shift `|v|` right until the high word is 0 and bit 15 clear, `e` = shifts; stores `e` at `CS:3E1A` and `*exp` (if non-null); returns signed `m` |
| `3e66` | `lnorm_undo(i16 m)` | `(i32)m << CS:3E1A` |
| `3e6f` | `lshl(i16 m, n)` | `(i32)m << n` |
| `3e84` | `lbitlen(u32 v)` | index of the top set bit, −1 for 0 |
| `3ec8` | `bitlen16(u16 v)` | same for 16 bits |
| `3ed4` | `sum_i8(i8 *p, n)` | Σ signed bytes → i16 |
| `3eed` | `sum_i16(i16 *p, n)` | Σ → i32 |
| `3f0e` | `in_open_range(a, b)` | `−b < a < b` → 1 else 0 |
| `3f27` | `clamp_sym(a, b)` | clamp `a` to `[−b, b]` |
| `3f3c`/`3f55` | `imin`/`imax` | signed |
| `410d`/`4123` | `normalize_to_sum(i16 *p, n, total)` | `p[i] = LDIV(p[i]·total, Σp)`, then add 1 to each non-zero entry in order (repeating) until `Σ == total` (loops forever if Σ > total — cannot happen with positive inputs). Used by the cloud set-up (`490a:0000`) |
| `41c4` | `lerp_map(x, x0, x1, y0, y1)` | `y0 + (x − x0)·(y1 − y0)/(x1 − x0)` (16×16→32, `idiv`) |
| `4e76` | `mul_cos(i16 r, u16 a)` | `(r·cos16(a)) >> 14` as i32 (arithmetic) |
| `4eb6` | `mul_sin(i16 r, u16 a)` | `(r·sin16(a)) >> 14` |
| `5e66`/`5e71` | `sin16`/`cos16` | §3.1 |

### 5.2 Vectors

| Address | Name | Behaviour |
|---|---|---|
| `4ef8` | `vdot` (near, AX = a, BX = b) | `Σ a[i]·b[i]` i32 (no shift) |
| `4f18` | `vdot(a, b)` | far wrapper |
| `4f26` | `vneg(v)` | in place |
| `4f38` | `vadd(a, b)` | `a += b` |
| `4f58` | `vadd_far(a, b far)` | `a += *b` |
| `4f7c` | `vsub(a, b)` | `a −= b` |
| `4f9c` | `vshl(v, n)` / `4fb2` `vsar(v, n)` | per component |
| `4fd3` | `vlen(v)` | `isqrt32(x²+y²+z²)` (32-bit sum, wraps) |
| `5004` | `ladd(a, b)` | lvec `a += b` |
| `5038` | `ladd_far(a far, b)` | `*a += b` |
| `5074` | `ladd3(a, b, c)` | `c = a + b` |
| `50c0` | `lsub(a, b)` | `a −= b` |
| `50f4` | `lsub_far(a, b far)` | `a −= *b` |
| `512e` | `lsub3(a, b, c)` | `c = a − b` |
| `517a`/`51ce` | `lmin`/`lmax(a, b)` | `a = min/max(a, b)` per component (signed) |
| `5224`/`526a` | `lshl`/`lsar(a, n)` | per component, through `LXLSH@`/`LXRSH@` (`0000:1e17`/`1e38`) |
| `52b0` | `ladd_scalar(a, i32 s, out)` | `out = a + s` per component |
| `52c6` | `ladd_scalar16(a, i16 s, out)` | same, `s` sign-extended |
| `530c`/`533a` | `ladd_v`/`lsub_v(a, vec b)` | `a ±= sext(b)` |
| `5368` | `ladd3_v(a, vec b, out)` | `out = a + sext(b)` |
| `53ae` | `ldiff16(a, b, vec out)` | `out = (i16)(a − b)` (low words) |
| `53e2` | `lmid(a, b)` | midpoint `(a + b) >> 1` per component into the static `DS:25F5..2600`, returns `DS:25F5` |
| `5434` | `lnear(a, b, u32 r)` | 0 if any `|a_i − b_i| > r`, else `ldist3` of the difference `<= r` |
| `5510` | `lbox(a, b, u32 r)` | all `|a_i − b_i| <= r` |
| `5588` | `linbox(a, u32 r)` | all `|a_i| <= r` |
| `55f0` | `l2v(vec out, lvec in)` | low words |
| `5612` | `v2l(lvec out, vec in)` | sign extend |
| `563a` | `lmove(lvec p, i16 r, u16 h)` | `p.x −= mul_sin(r, h); p.y += mul_cos(r, h)` (move `r` along heading `h`) |
| `5ea4` | `dir_from_angles(vec out, u16 ang[3])` | forward unit vector: `ang[0] == 0` → `(−sin h, cos h, 0)`; else `z = sin p`, `x = mul_sin(−cos p, h)`, `y = mul_cos(cos p, h)` (= row 1 of the matrix) |
| `5fae` | `dir_from_heading(vec out, u16 h)` | `(−sin h, cos h, 0)` |
| `384e` | `lswap_order(i32 *a, i32 *b)` | swap if `*a > *b` |
| `3892` | `lbox_order(lvec mn, lvec mx)` | per component `384e` |
| `38d0` | `lbox_overlap(amin, amax, bmin, bmax)` | 1 if `amin <= bmax && amax >= bmin` on all axes (no callers found) |

### 5.3 Small C helpers around the core (compiled modules, owned by render3d per the sim_flow map)

| Address | Name | Behaviour |
|---|---|---|
| `35ff:0009` | `clamp(v, lo, hi)` | signed |
| `35ff:0029` | `in_range(v, lo, hi)` | 1 if `lo <= v <= hi` |
| `35ff:0041` | `bearing32(i32 dx, i32 dy)` | `atan2_32(dx, dy) + C000h` (= heading of the vector in the game's convention: 0 = north, CCW) |
| `3604:0009` | `vscale(vec v, i16 s)` | `v[i] = (v[i]·s) >> 14` (386, arithmetic) |
| `3609:0001` | `vrot_z(vec v, u16 a)` | `x' = (x·c − y·s) >> 14; y' = (x·s + y·c) >> 14` |
| `3611:0007` | `dir_scaled(out, ang, s)` | `vscale(dir_from_angles(ang), s)` → copied to `out` |
| `3614:0009` | `angles_to(out, lvec from, lvec to)` | `out = (pitch, 0, heading)`: heading `= bearing32(to.x − from.x, to.y − from.y)` (stored at `+4`), horizontal distance `ldist2v(|dx|, |dy|)`, pitch `= bearing32(to.z − from.z, dist)`... stored at `+0` (**Likely**: argument order of the pitch call is `(dist, dz)` — see `3614:006c..0084`) |
| `361d:000b` | `lmove_dir(lvec p, ang, i32 dist)` | adds `dir_from_angles(ang)` 4000h at a time while `dist > 4000h`, then the scaled remainder |
| `3624:0000` | `lmove_heading(lvec p, u16 h, i16 r)` | `p.x −= (r·sin h) >> 14; p.y += (r·cos h) >> 14` (386) |
| `3629:0004` | `bearing_between(a, b)` | `bearing32(a.x − b.x, a.y − b.y)` |
| `365a:000c` | `obj_matrix(obj in BX)` | if `!(obj[26h] & 1)`: `mat_from_angles(obj[+28h] → obj+13h)`, set bit 0; returns `obj+13h` (the matrix cache of an object record) |
| `365a:0032` | `obj_matrix_t(obj in BX)` | if `!(obj[26h] & 2)`: copy `obj_matrix` result onto itself (`SCOPY@`, 13h bytes) and transpose, set bit 1 (**note**: after this the cache holds the transposed matrix and bit 0 stays set) |
| `365a:0074` | `obj_set_angles(obj BX, ptr AX)` | `obj[26h] = 0; obj[28h] = AX` |
| `3662:0002` | | empty (`retf`) |
| `3662:000d` | `lscale(lvec v, i16 s)` | `v[i] *= s` (32-bit) |
| `3666:0009` | `l2v_sar(vec out, lvec in, n)` | `out[i] = in[i] >> n` |
| `3666:003b` | `v2l_shl(lvec out, vec in, n)` | `out[i] = (i32)in[i] << n` |
| `3666:0073` | `lrotate(lvec v, mat m, lvec out)` | `e = bitlen(ldist3(v,0)·3/2) − 15`; `e < 1`: `out = v2l(vec_rotate(l2v(v), m))`; else `out = v2l_shl(vec_rotate(l2v_sar(v, e), m), e)` (precision-reduced rotation of a long vector) |
| `3678:0004` | `obj_to_world(out, obj, vec v)` | `out = obj.pos + vec_rotate(v, obj_matrix(obj))` |
| `367b:0006` | `lrot_z(lvec v, u16 a)` | `x' = (x·c − y·s) >> 14; y' = (x·s + y·c) >> 14` (32-bit products, wrap) — rotates macro members (`34f1:0155`) |
| `3684:000c` | `vdist(vec a, vec b)` | `ldist3` of the sign-extended vectors |
| `3684:0042` | `vec_outside_mask(v, lo, hi)` | bit i set when component i is inside `[lo_i, hi_i]` (`in_range` per axis, bits 1/2/4) |
| `3684:00a1` | `lbits(u32 v)` | `v == 0 ? 0 : lbitlen(v) + 1` |
| `4edb:0000` | `lneg(out, in)` | `out = −in`; `4edb:0030` empty |
| `5137:0000` | `vec_map_362b(in, out)` | `out[i] = 362b:0146(in[i])` (sim_flow time-base helper) |
| `5137:0034` | `ratio10(a, b)` | `ldiv_sat((i32)a << 10, b)` |
| `5137:004f` | `vratio10(v, b, out)` | per component |
| `5137:0084`/`00b3` | `v2l` / `ladd_v` | C versions |
| `5137:00e2` | `dir_from_angles_far(out, far ang)` | copy the angles, `dir_from_angles` |
| `5137:0128` | `vec_dt(v)` | `v[i] = 362b:00be(v[i])` (x·dt>>8, sim_flow) |
| `5137:015c` | `lrot_z2(lvec v, a)` | as `367b:0006` |
| `5b91:0000` | `per4000(i32 v)` | `ldiv_sat(v, 4000)`; `5b91:0014` empty |

-----------------------------------------------------------------------------------------------

## 6. The model/world scale question (shapes.md open question) — settled

* `CS:09AC` is **not** a model scale. It is `s − k`: `s` = the shape's own scale shift (header byte
  3), `k` = a per-object precision shift chosen each frame so that distance + radius fits in 14 bits
  (`277a:237d`). Everything that enters the 16-bit paths (vertices after `>> (k−s)`, the eye
  position `>> k`, the eye→object vector `>> k`) is divided by the same `2^k`, so the projection
  (a ratio) is unchanged; lighting and culling are sign/ratio tests and are unaffected too.
* Therefore **model units = world units × 2^−s**: a vertex `(x, y, z)` of a shape with shift `s` lies
  at `obj.pos + ((x,y,z) << s)·M` in world units. The world placement code (macros, WD3 objects)
  adds positions in the same units without any further scale. Aircraft have `s = 0` (F4U: 388 units
  wide) and the world spans ±13 M units; if Oahu–Hilo (≈ 350 km) is 5.6 M units, one unit is
  ≈ 6 cm and the F4U would be ≈ 23 m wide — about twice its real 12.5 m span. Either the world is
  compressed ~2× or the unit estimate from the map is off; the renderer itself has one unit system
  (**Verified** for the code; the metric value of a unit stays **open**, a question for sim_world:
  speeds in `.FMD` would settle it).

-----------------------------------------------------------------------------------------------

## 7. Self-modifying code

None in `277a`: every `cs:` store targets data areas (`0008..0011`, `03B7..03BA`, `09A2..21FF`,
`361A..361C`, `3840..384D`, `3E1A`), never instruction bytes. Several routines are entered in the
middle of another's body (`277a:3d05` jumps into `3d5d`, `4e76`/`4eb6` tail-jump to `3d5d` with
`CL = 14`, `3a58` falls into `39a5`), and `3a58` computes a jump into an unrolled shift chain
(`jmp ax` at `3ade`, target `3B24h − 4·(bp+2)`). The port writes these as ordinary functions.

## 8. Port notes

* `/* PORT: */` Keep the `277a` data block (`CS:0000..22FF`, tables `CS:3A28..3A47`,
  `5664..6B27`) as bytes of the emulated image: other code (`2f0e`, `5440`, the sky code) reads and
  writes it through segment `277a`.
* The 32-bit multiply/divide sequences are exact integer operations; C `int64_t` reproduces them.
  Take care to reproduce: floor (not round) of every `>> 14`, 16-bit wrap of the 16-bit sums, the
  `adc` carry chain of `361d`, the `y <= f` no-projection case of `proj32`, the divide-by-`idiv`
  truncation toward zero.
* INT 0 on `idiv` overflow must be modelled as in §1.4 (halve the dividend and retry).
