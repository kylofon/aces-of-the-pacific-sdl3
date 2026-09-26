# video — part `ts`: the PS copy of the 3Space core and the `ts2` shape library

Scope: the 3D code linked into **PS** for the shell's model viewer (`view3d_*` `217d`, shell_data;
aircraft/ship in the hangar, recognition and briefing screens): the asm math/transform/polygon core
PS `3d50` (= AP `277a`), the `ts2` shape library PS `4708` (`ts_draw.c`), `47c8` (`ts_util.c`),
`4818` (`ts_bm.c`), `48ac` (shadow), `48c0` (`ts_file.c`), `48ea` (`ts_utilo.c`), `4915`
(disc/curve), `46d0` (sprites/bitmaps in shapes), `4960` (fatal error / stack check), and the PS
4-point bitmap mapper `16e3:065d` it uses. AP's versions are specified by render3d
(`render3d_math.md`, `render3d_poly.md`, `render3d_shapes.md`; AP `ts_draw` `2f0e`, `ts_bm` `2e33`):
**this part gives the PS↔AP correspondence and specifies only what differs**. INTRO has no 3D code
(only the cos table + `sin16`/`cos16` copy `1739`, see `video_library.md` §9.1).

Confidence: correspondences are **verified** by instruction-by-instruction comparison of the PS and
AP code (normalised for register allocation, stack cleanup and data offsets; scratch
`finish/fdiff.py`); the PS variants below are verified from the PS disassembly unless marked.

## Index

1. Summary for the port
2. PS `3d50` ↔ AP `277a`: function table, data offsets
3. PS-only arithmetic in `3d50` (asin/acos table, `proj32`-based projection and clipping)
4. The `ts2` library: function table and differences from AP
5. `ts_bm` bitmap shapes in PS (`4818`)
6. Curves (`4915:0173/02fb`, also AP `70b4`) and the fatal-error module `4960`
7. PS globals
8. Port notes, hand-offs, open questions

---

## 1. Summary for the port

* The PS 3D pipeline is the AP pipeline **without the 386 instructions**: every AP routine that
  uses 32-bit registers (`imul edx`/`idiv ebx`, `movsx`, `shld`) has an 8086 replacement in PS that
  computes the quotient through `proj32` (`3d50:032a`, render3d_math.md §4.8), which is an
  approximation of `a·f/y` (fraction of the normalised high words, truncated) and **returns `a`
  unchanged when `|y| ≲ |f|`**. So PS clipping points and apparent sizes can differ by a few
  units from AP's for the same inputs — keep both variants if bit-exact shell images matter.
* PS never calls `set_near` (`3d50:2342` has no caller), so near_z = focal and the vertex shift is 0
  (as set by `cam_begin_frame`); the PS 32-bit near clippers hard-wire exactly that (they use focal
  and no shift).
* Draw-mode selection in PS `ts_draw` uses the thresholds `0x7D00` / `0x3FAC` **unshifted** (AP
  shifts them right by the near shift, which is 0 in PS anyway) — §4.
* No EMS / memory handles in PS: shape tables and bitmaps are plain DOS memory; the "fast shape
  cache" of `ts_util` exists but is never built (`DS:39E6` stays 0).
* The PS bitmap-shape drawer (`4818`) always uses the rotated path (`DS:3B0C = 1`, never
  written) and draws with `gfx_sprite_rotated` (`16e3:4021`).
* Polygon flag 10h (4-point bitmap) really draws in PS (`46d0:02fa` → `16e3:065d`, a texture
  mapper), while AP's `2ec2:000d` only calls an assert helper. The flag is unused by the shipped
  shapes (render3d_poly.md §2.3), so this is dead in practice.

## 2. PS `3d50` ↔ AP `277a`

### 2.1 Function table

"identical" = same instruction sequence up to register allocation and data offsets; the spec is
the render3d one for the AP address. `3d50` keeps its data in its own code segment exactly like
`277a` (routines set `DS = CS`), see §2.2 for the offsets.

| PS `3d50:` | AP `277a:` | name | note |
|---|---|---|---|
| `0012` | `3968` | `mul_shr8` | identical |
| `0022` | `3978` | `mul_shr10` | identical |
| `003a` | `3990` | `bit_index8` | identical |
| `004c` | `39a2` | `isqrt16` | identical |
| `0102` | `3a58` | `isqrt32` | identical |
| `01e6` | `3bfc` | `ldist2` | identical; the same routine contains `ldist2v` at `3d50:0220` (= AP `3c36`) |
| `0254` | `3c6a` | `dist2_16` | identical |
| `027a` | `3cfc` | `mul32` | identical |
| `0292` | `3d14` | `lmul` | identical |
| `02d0` | `3d52` | `lsar` | identical |
| `032a` | `3f6e` | `proj32` | identical |
| `04ca` | `41e0` | `mat_mul` | identical |
| `0840` | `4556` | `mat_transpose` | identical |
| `0864` | `457a` | `mat_from_angles` | identical |
| `0c8e` | `49a4` | `mat_to_angles` | identical |
| `0cf6` | `4a0c` | `vec_rotate_n` | identical |
| `0dcf` | `4ae5` | `vec_rotate` | far wrapper of `vec_rotate_n` `0cf6` |
| `0de4` | `4afa` | `dot48` | identical |
| `0f11` | `4c27` | `lvec_rotate_n` | identical |
| `0f9d` | `4cb3` | `lvec_rotate` | far wrapper of `lvec_rotate_n` `0f11`; no caller in PS |
| `0fb2` | `4cc8` | `vtx_rotate_shift` | identical |
| `1562` | — | `asin16` | **PS variant**, §3.1 |
| `1589` | — | `acos16` | **PS variant**, §3.1 |
| `15b4` | `4e76` | `mul_cos` | identical |
| `15f4` | `4eb6` | `mul_sin` | identical |
| `1636` | `4ef8` | `vdot_n` | identical |
| `1656` | `4f18` | `vdot` | identical |
| `1664` | `4f26` | `vneg` | identical |
| `1676` | `4f58` | `vadd_far` | identical |
| `169a` | `4fb2` | `vsar` | identical |
| `16b0` | `53e2` | `lmid` | identical (midpoint `(a+b)>>1` per component into the static `DS:3889`, returns it) |
| `1702` | `5510` | `lbox` | identical (all `|a_i − b_i| <= r`) |
| `1f7c` | `5e66` | `sin16` | identical |
| `1f87` | `5e71` | `cos16` | identical |
| `21ba` | `6228` | `atan2_16` | identical |
| `225a` | `62c8` | `atan2_32` | identical |
| `2342` | `0012` | `set_near` | identical; no caller in PS |
| `237b` | `004b` | `cam_begin_frame` | identical |
| `2482` | `0152` | `set_light` | identical |
| `24ea` | `22f8` | `obj_set_position` | identical |
| `256f` | `237d` | `obj_set_orientation` | identical |
| `26e1` | `24ef` | `obj_near_depth` | identical |
| `27de` | `01ba` | `poly_colours` | identical |
| `28c3` | `029f` | `poly_fill` | identical |
| `2908` | `02e4` | `poly_fill_bitmap4` | identical; its callee `46d0:02fa` draws in PS (§4) |
| `296d` | `361d` | `part_draw32` | identical (calls the PS clippers below) |
| `2b92` | `07ae` | `part_draw16s` | identical |
| `2d86` | `2fee` | `pt_add_centre` | 8086 version, same result: `p[0] += (i32)cx; p[1] = (i32)cy − p[1]`; returns `p` |
| `2daa` | `3010` | `pt_project` | **PS variant** via `proj32`, §3.2 |
| `2de4` | `304c` | `apparent_size` | **PS variant** via `proj32`, §3.2 |
| `2e0c` | `25ec` | `clip2d16` | identical (register allocation only) |
| `32ad` | `2a8d` | `near_isect16` | identical semantics (anchor in BX instead of BP) |
| `32f6` | `2adf` | `near_clip16` | identical semantics |
| `3399` | `2b5d` | `poly_add_centre16` | identical |
| `33c4` | `2b88` | `clip32a_x_edge` | identical |
| `3455` | `2c19` | `clip32a_y_edge` | identical |
| `34e6` | `2caa` | `clip2d32a` | identical (calls `33c4`/`3455`) |
| `3713` | `2ed7` | `near_isect32a` | **PS variant** §3.3 |
| `376e` | `2f4e` | `near_clip32a` | same S-H walk (render3d_poly.md §4.1), calls `3713` |
| `385a` | `3070` | `clip32b_x_edge` | **PS variant** via `proj32` §3.3 |
| `392f` | `3159` | `clip32b_y_edge` | **PS variant** via `proj32` §3.3 |
| `3a04` | `3242` | `clip2d32b` | the code of `clip2d32a` (identical instructions) calling `385a`/`392f` |
| `3c31` | `346b` | `near_isect32b` | **PS variant** via `proj32` §3.3 |
| `3cb4` | `3530` | `near_clip32b` | same S-H walk, calls `3c31` |
| `3d9f` | `35d0` | `poly_add_centre32` | identical |
| `3e0f` | `09b6` | `m_cam_block` | **data** (matrices), indexed as a function by mistake |
| `3e4d` | `0a07` | `eye_in_obj` | **data**: i16[3] |
| `3e53` | `0a13` | `cs_state_block` | **data**: the object state block |
| `573e` | `0346` | `poly_facing` | identical |
| `57b3` | `03bb` | `part_draw_shadow` | identical |
| `59be` | `05c6` | `part_draw16` | identical |

AP routines with no PS counterpart: `get_near_n`, `reset_near`, `near_clip32b`'s 386 helpers,
`ldist3`/`ldist3v`, `log_key`, `lnorm`, the `l*` vector helpers `4f38–563a`, `dir_from_*`,
`asin16`/`acos16` (AP versions, different table), `lswap_order`, `lbox_order`, `lbox_overlap`,
`linbox`, `lnear`, `pt_add_centre`/`pt_project`/`apparent_size` 386 versions.

### 2.2 Data offsets (PS `3d50` code-segment data vs AP `277a`)

Derived from the operand pairs of all identical routine pairs (scratch `finish/opmap.txt`,
83 pairs agree):

| AP | PS | rule / meaning |
|---|---|---|
| `CS:09A2..21FF` (object state, vertex arrays, polygon lists, `m_*` blocks, render3d_math.md §2.3) | `CS:3DE8..3645+…` | **PS = AP + 3446h** (e.g. `need_clip 09B3` → `3DF9`, `force_clip 09B2` → `3DF8`, `obj_shift 09AA` → `3DF0`, `focal 0A47` → `3E8D`, `S 0A49` → `3E8F`, `cx 0A4B` → `3E91`, `cy 0A4D` → `3E93`, poly count `0A4F` → `3E95`, `CS:0A25` table index → `3E6B`, `hdr 0A27/0A29` → `3E6D/3E6F`, `radius 0A2D` → `3E73`, `app_size 0A39` → `3E7F`) |
| `CS:000A/000C/000E/0010` (near_z `000E`, near shift `0010`) | `CS:233A/233C/233E/2340` | +2330h |
| `CS:03B7/03B9/03BA` (part_draw16 counters) | `CS:57AF/57B1/57B2` | +53F8h |
| `CS:361A/361C` (part_draw32 counter / behind flag) | `CS:296A/296C` | |
| `CS:3A28/3A38` (`4^i` tables of isqrt32) | `CS:00D2/00E2` | |
| `CS:5664` `cos_tab` (1025 i16) | `CS:177A` | same values (sin16/cos16 identical) |
| `CS:6028` `atan_corr` (512 i8) | `CS:1FBA` | |
| — | `CS:1160` | PS asin table (§3.1) |
| DGROUP `DS:26C4..26CE`, `26DF` (driver clip/colours, `drv[04..0E]`, `drv[1F]`) | `DS:2304..230E`, `231F` | driver block base 26C0 → 2300 |
| DGROUP `DS:276C/2794/285C` (`drv[AC]`, `drv[D4]`, `drv[19C]` polygon arrays/count) | `DS:23AC/23D4/249C` | same |
| DGROUP `DS:2402/2403/2405` (shadow colour / mode / LOD cap) | `DS:3B52/3B53/3B55` | |
| DGROUP `DS:25F5..2600` (`lmid` result), `260E..261D` (`proj32` scratch) | `DS:3889..3894`, `38A2..38B1` | +1294h |

## 3. PS-only arithmetic in `3d50`

### 3.1 `asin16` `3d50:1562` / `acos16` `3d50:1589` (far cdecl, arg `i16 v` in 2.14)

```
s = sign(v); a = |v|                 // neg: v = -8000h stays negative (quirk, garbage index)
T = asin_ps[a >> 5]                  // CS:1160, i16, index = a >> 5 (arithmetic)
asin16(v) = s > 0 ? T : -T           // s from "v >= 0" → T, else −T
acos16(v) = (v >= 0 ? -T : T) + 4000h
```

`asin_ps[i] = floor(asin(i / 512) · 65536 / 2π)` for i = 0..512 (verified: all 513 entries equal
this formula; `asin_ps[512] = 16384`). Inputs with `|v| > 4000h` (> 1.0) index past entry 512 into
unrelated code-segment data (not guarded; callers pass values ≤ 1.0: `mat_to_angles` `0c8e` via
`1562`, `ts_bm` `4818:028a` via `1589`). AP uses a different, finer table (render3d_math.md §3.3):
the results differ.

### 3.2 `pt_project` `3d50:2daa`, `apparent_size` `3d50:2de4`

* `pt_project(i32 in[3], i32 out[2])` (far): `(out[0], out[1]) = proj32(x = in[0], z = in[2],
  y = in[1], f = (u32)focal)` (`focal` = `CS:3E8D`, zero-extended); returns `out`. (AP: exact
  `focal·in/in[1]` with `idiv`.)
* `apparent_size(i32 v[2])` (far): `proj32(x = v[0], z = 0, y = v[1], f = (u32)focal).x` in DX:AX.

`proj32` semantics (render3d_math.md §4.8): result ≈ `trunc(x·f/y)`, sign-corrected, and **x
unchanged when after normalisation the high word of |y| is ≤ that of |f|** (roughly |y| ≤ |f|).
Used by `ts_visible_lod` (`4708:0003`) exactly where AP uses the 386 versions.

### 3.3 PS clip interpolation

Notation as render3d_poly.md §4 (O = outside/anchor vertex, I = inside vertex).

* `near_isect32a` `3d50:3713` (near; BP = behind vertex b, SI = front vertex a): with
  `t = focal − ey16[b]` (**`CS:3E8D` focal, not near_z**), `d = ey16[a] − ey16[b]` (low words):
  `vx[b] = ex[b] + (i32)(i16)((ex16[a] − ex16[b]) · t / d)` (16×16 `imul`, 32/16 `idiv`, `cdq`,
  32-bit add to the anchor's 32-bit value), same for z → `vz[b]`; **no left shift** afterwards (AP
  shifts by `CS:0010`; in PS the shift would be 0 and near_z = focal, so both agree in practice).
  Output slots PS `CS:4757/51ED` (x lo/hi) and `4955/53EB` (z lo/hi).
* `near_isect32b` `3d50:3c31` (near): `(dx', dz') = proj32(x = ex[a] − ex[b], z = ez[a] − ez[b],
  y = ey[a] − ey[b], f = focal − ey[b])` (all 32-bit), `vx[b] = ex[b] + dx'`, `vz[b] = ez[b] +
  dz'`. (AP: exact 64-bit `imul`/`idiv` and a shift by `CS:0010`.)
* `clip32b_x_edge` `3d50:385a` (near; CL = outcode of the outside vertex O at BP, SI = inside
  vertex I, DI = output index): bit 1 → edge = `drv[04]` (`DS:2304`), else bit 2 → edge =
  `drv[06]` (`DS:2306`), else nothing. `out.x = (i32)edge`, `out.y = O.y + proj32(x = I.y − O.y,
  z = 0, y = I.x − O.x, f = edge − O.x).x`; `DI += 2`. (x list `CS:40BD/4B53` → out
  `CS:410D/4BA3`, y list `CS:40E5/4B7B` → out `CS:4135/4BCB`, lo/hi words.)
* `clip32b_y_edge` `3d50:392f`: the same for y: bit 8 → edge = `drv[08]` (`DS:2308`), else bit 4
  → `drv[0A]` (`DS:230A`); `out.y = (i32)edge`, `out.x = O.x + proj32(x = I.x − O.x, z = 0,
  y = I.y − O.y, f = edge − O.y).x`; it reads the x-pass output lists (`CS:410D/4BA3`,
  `4135/4BCB`) and writes back into `CS:40BD/4B53`, `40E5/4B7B`.

Compared with AP `clip2d32b` (exact `imul edx`/`idiv ebx`), the PS points differ by the `proj32`
truncation and by the "unchanged" rule when `|edge − O| ≈ |I − O|`.

## 4. The `ts2` library (PS) — function table

| PS | AP | name | PS difference (else: identical semantics, see render3d_shapes.md) |
|---|---|---|---|
| `46d0:0000` | `2edf:0007` | `bitmap_global(i)` | tables `DS:76CE`/`76D0` (AP `6498`/`649A`) |
| `46d0:005b` | `2edf:005e` | `vtx_eye16(idx, out[3])` | — |
| `46d0:0117` | `2edf:0119` | `sprite_draw(var)` | variant pointer is a far argument (`les`), AP near + ES |
| `46d0:02fa` | `2ec2:000d` | `bitmap4_draw(colours, xs, ys)` | draws the frame onto the quad with `gfx_bitmap_quad` `16e3:065d` (`video_library.md` §9.4), `drv[03] = 1` before and **`drv[03] = 0` after**; AP calls the assert helper `07fe:000a` instead (nothing drawn) and leaves `drv[03] = 1` |
| `4708:0003` | `2f0e:0008` | `ts_visible_lod()` | projections through the PS `pt_project`/`apparent_size` (§3.2) |
| `4708:034c` | `2f0e:033d` | `part_sort(self, n, list)` | first calls `stack_check("ts_draw.c", 125)` (`4960:0184`, §6.2) |
| `4708:0715` | `2f0e:06eb` | `part_list(...)` | — |
| `4708:074b` | `2f0e:071f` | `part_walk(...)` | — |
| `4708:0925` | `2f0e:08e9` | `ts_draw(instance *o)` | draw mode, below |
| `47c8:0000` | `271b:0007` | `shape_ptr(id)` | walk of the 12-byte tables `DS:76D2`, count `DS:76D6`; sets `CS:3E6B` = table index; fast cache `DS:39E6`/`76D4` never built; no handles |
| `47c8:008f` | `271b:011d` | `shape_set_ptr(id, far p)` | same; no caller |
| `47c8:0132` / `0188` | `271b:0251` / `02a6` | `view_new(eye)` / `view_free(v)` | — (16h-byte record: `+0 = 7`, `+2 = eye`, window `0,0,320,200`) |
| `47c8:0196` … `03f6` | `271b:02b5` … `04f5` | `shape_flags`, `shape_class`, `shape_set_class`, `shape_subclass`, `shape_shift`, `shape_nslots`, `shape_nvariants`, `shape_radius`, `shape_set_radius` (in that order: `0196 01da 021f 0267 02ac 02f1 0336 03b1 03f6`) | — |
| `47c8:043e` | `271b:0539` | `shape_radius_world(id)` | — |
| `47c8:0490` | `271b:0584` | `shape_box(id, min, max)` | — |
| `4818:0006` / `0011` | `2e33:0006` / `0011` | `bm_set_cap(n)` / `bm_reset_cap()` | `DS:3B0A`, reset value **100h** (AP 200h), initial 109h; no callers in PS |
| `4818:001c` | — | `bm_draw_item_flat(item)` | dead (§5) |
| `4818:0152` | `2e33:001c` (+ part of `0508`) | `bm_draw_item(item)` | §5 |
| `4818:0468` | `2e33:0333` | `bm_view_angles()` | outputs `DS:76D8` elev, `76DA` rot, `76DC` az (AP `6482/6484/6486`) |
| `4818:063d` | `2e33:0508` | `bm_draw_frame(far p, frame)` | §5 |
| `4818:0833` | `2e33:07f4` | `bm_draw(instance *o)` | — |
| `4818:08fc` | `2e33:08b8` | `bm_is_bitmap(id)` | — |
| `4818:092f` | `2e33:08e7` | `bm_set_mult(n)` | `DS:3B0E` (initial 1); no caller |
| `4818:093a` | `2ecb:013c` | (2-instruction stub) | fragment, no caller |
| `48ac:0005` | `2ecb:0007` | `shadow_pos(...)` | globals `DS:76E8..76EC` (AP `6492..6496`) |
| `48ac:00ba` | `2ecb:00ba` | `shadow_draw(o)` | `DS:3B53`/`3B55` |
| `48ac:013a` | `2ecb:013c` | `shadow_set_colour(c)` | `DS:3B52 = c` |
| `48c0:0005` | `7039:0000` | `ts_read(far dst, u32 n, f)` | — |
| `48c0:0149` / `018b` | `7039:0144` / `0187` | `ts_close(f)` / `ts_open(name, tag)` | errors → `ts_fatal` (§6.2) instead of AP's assert |
| `48c0:020d` | `7039:020a` | `ts_load_chunk(name, tag)` → far | — |
| `48ea:0009` | `7074:0000` | `ts_init(ntables, nsets)` | first-call flag `DS:3BBC`; malloc failure → `ts_fatal(…, "ts_init : my_malloc")` |
| `48ea:0133` | `7074:012d` | `ts_done()` | — |
| `48ea:0158` | `7074:0154` | `ts_load_table(t, name)` | `"DAT:"` chunk |
| `48ea:0236` | `7074:022b` | `ts_free_table(t)` | DOS block only (no handle branch) |
| `4915:0007` | `70e8:0000` | `disc_draw(var)` | — (uses `gfx_circle` `16e3:035a`) |
| `4915:0173` / `02fb` | `70b4:0000` / `0188` | `curve4_draw` / `bezier2_draw` | §6.1 |
| `4960:0001` … `0213` | — | error / stack-check module | §6.2 |

**`ts_draw` draw mode (PS `4708:0925`, differs from render3d_shapes.md §2.1):**

```
if (obj_shift == 0 && radius <= 0x3FAC [32-bit signed compare] &&
    e_dist + radius <= 0x7D00 [32-bit signed])            mode = 0
else {
    obj_near_depth();
    if ((e_near >> obj_down) > near_z) { obj_shift = vtx_shift; e_depth = sext(...);
                                         e_pos = sext(e_pos16); mode = obj_shift ? 3 : 0; }
    else mode = (radius < 0x3FAC [signed 32]) ? 1 : 2;
}
```
i.e. AP's `0x7D00 >> near_shift` and `0x3FAC >> near_shift` without the shift (PS near shift is 0).

## 5. `ts_bm` bitmap shapes in PS (`4818`)

`bm_draw_frame(far p /* hdr+1A */, frame)` `4818:063d`:
```
DS:76E0 = p[0] (ext0); DS:76DE = p[1] (ext1); D = p + 4 bytes
nhot = D[12h]; DS:76E4 = &D[14h] (far; hot-spot table, 2 bytes per bitmap: i8 x, i8 y)
E = elevation list at D + 14h + 2·nhot: {u16 n; n × (i16 value, u16 offset)}:
    pick the entry with the smallest |value − DS:76D8| (|−8000h| taken as 7FFFh; first on ties)
A = azimuth list at D + E.offset, same with DS:76DC
F = frame list at D + A.offset: nf = *F; if nf == 0 return
while (frame >= nf) frame -= nf
skip `frame` frames: each frame = {u16 nitems; nitems × 9-byte items}
for each item of the chosen frame: DS:3B0C ? bm_draw_item(item) : bm_draw_item_flat(item)
```

Item (9 bytes): `+0 i8` bitmap index (relative to `DS:76E2` = the shape's bitmap base), `+1 i8 dx`,
`+2 i8 dy`, `+3 u16 sx` (0 = 400h), `+5 u16 sy` (0 = 400h), `+7 u16 rot`.

`bm_draw_item(far item)` `4818:0152` (the only path used, `DS:3B0C = 1`):
```
bm = bitmap_global(DS:76E2 + item.idx); assert (ts_bm.c, 148)
e = e_pos16 (CS:3E53: x, y = depth, z)
if (focal CS:3E8D > e.y) return                        // too close
a = min(app_size CS:3E7F, DS:3B0A)
s = LDIV((i32)a << 10, 127)
sx = item.sx ? (i32)s·item.sx >> 10 : s;  sy = item.sy ? (i32)s·item.sy >> 10 : s
if (DS:76E0) {                                          // squash with elevation
    k = acos16(LDIV((i32)DS:76DE << 14, 100))           // PS acos16, §3.1
    c = cos16(LDIV((i32)(2·DS:76D8) · k, -32768)) >> 4  // sar; 0..1024
    sy = mul_shr10(sy, c)
}
w = mul_shr10(bm.w, sx); h = mul_shr10(bm.h, sy); if (!w || !h) return
x = cx + LDIV((i32)e.x << S, e.y);  y = cy − LDIV((i32)e.z << S, e.y)      // S = CS:3E8F
dx = item.dx; dy = item.dy; if (DS:76E0) dy = mul_shr10(c, dy)
rx = mul_cos(dx, DS:76DA) − mul_sin(dy, DS:76DA);  ry = mul_sin(dx, DS:76DA) + mul_cos(dy, DS:76DA)
x += mul_shr10(rx, s); y += mul_shr10(ry, s)
drv[03] = 1
gfx_sprite_rotated(bm, x, y, item.rot + DS:76DA, w·M, h·M, hot[idx].x / M, hot[idx].y / M)   // 16e3:4021, M = DS:3B0E (1)
```
(`mul_shr10(a, b)` = `3d50:0022`; `LDIV` = Borland signed 32-bit division; `hot[idx]` bytes are
sign-extended and divided with `idiv`.) Differences from AP: the scale base is `<< 10`/`>> 10` (AP
`<< 8`), the size cap `DS:3B0A` applies to `app_size` before scaling (AP caps the scaled factors at
`DS:23BC`), the position is computed per item, `drv[03]` (not `26C3`) is the clip flag.

`bm_draw_item_flat(far item)` `4818:001c` (dead): `w = mul_shr10(bm.w, sx)`, `h =
mul_shr10(bm.h, sy)` with the item's sx/sy only (no distance scaling); position `(cx + dx, cy +
dy)`; same `gfx_sprite_rotated` call with `item.rot` (no view rotation).

## 6. Curves and the fatal-error module

### 6.1 `curve4_draw(int xs[4], int ys[4])` PS `4915:0173` / AP `70b4:0000` (no callers in PS or AP)

Splits the 4 control points into midpoints `m01 = p0 + (p1−p0)>>1`, `m03 = p0 + (p3−p0)>>1`,
`m12 = p1 + (p2−p1)>>1`, `m32 = p3 + (p2−p3)>>1` (sar) and draws four quadratic Béziers with
`bezier2_draw(3, …)`: `(m03, p0, m01)`, `(m01, p1, m12)`, `(m12, p2, m32)`, `(m32, p3, m03)`
(x and y as i32; argument order `(k, x0, x1, x2, y0, y1, y2)` with x0 = first point). A closed
rounded outline through the edge midpoints (**likely** purpose: a smooth "blob").

`bezier2_draw(k, i32 x0, x1, x2, y0, y1, y2)` PS `4915:02fb` / AP `70b4:0188` (near): forward
differences with `n = 1 << k` steps in fixed point `2k` bits:
```
Ax = x0 + x2 − 2·x1;  Bx = (x1 − x0) << (k+1);  Px = x0 << 2k    (same for y)
prev = (Px >> 2k, Py >> 2k)
for i = 0 .. n (inclusive):
    cur = (Px >> 2k, Py >> 2k)                 // arithmetic 32-bit shifts
    if cur != prev: gfx_line(prev, cur) (16e3:3c7b / AP 1d32:5ab5); prev = cur
    Px += Bx + (2i+1)·Ax;  Py += By + (2i+1)·Ay
```

### 6.2 `4960` — `ts2` fatal error and stack check (PS only)

* `4960:0001` `str_rotbuf(far s)`: copies `s` into one of two 80-byte buffers `DS:76EE +
  50h·t` (`t = DS:3BF2 ^= 1`), returns it.
* `4960:003c` `src_name(far path)`: `str_rotbuf`, then keeps the file base name: `strrev`
  (`0000:400a`), cut at the first `\` (i.e. the last one), `strrev`, cut at `.`, `strupr`.
* `4960:0094` `ts_fatal(far file, line, char *msg)`: `gfx_restore_text()` (`16e3:5b23`),
  prints "A system error has occured.  Please write down the" / "following data and contact
  Sierra Customer Support:" / `"%s:%d (%s)\n"` with `src_name(file)`, line, `msg` (or `" "`),
  `stack_report()`, `sys_shutdown()` (`16e3:5b0e`), `exit(0)`.
* `4960:0184` `stack_check(far file, line)`: `sp = (u32)(u16)&file` (the argument address);
  limit = `(0FFFFh − DS:3FB4) + 12Ch` (32-bit; `DS:3FB4` = Borland `_stklen`, **likely**); if
  `sp < DS:3BF4:3BF6` (lowest seen): record it with `file` (`DS:3BF8/3BFA`) and `line`
  (`DS:3BFC`); if `sp < limit`: releases 1000 bytes of stack (`add sp, 3E8h`) and calls
  `stack_overflow(file, line)`.
* `4960:0133` `stack_overflow(file, line)`: text mode, "Bad Human!", "FILE = %s", "LINE = %d",
  `stack_report()`, `sys_shutdown()`, `exit(0)`.
* `4960:0213` `stack_report()`: "Stack usage:", "FILE:   %s", "LINE:   %d", "DEPTH:  %ld" with
  `0FFFFh − lowest`.
* `4960:00f6` (no caller): `t = (u32)(u16)&local + DS:3FB4`; returns `t − 0FFFFh` if `t > 0FFFFh`,
  else 0.

`/* PORT: */` the stack check is meaningless in the port; keep `ts_fatal` as a fatal error.

## 7. PS globals (DGROUP 4D08)

| PS | AP | Name |
|---|---|---|
| `76CE` far / `76D0` | `6498` / `649A` | sprite sets / count |
| `76D2` / `76D4` / `76D6` | `647C` / `647E` / `6480` | shape tables (12-byte records) / fast-cache count / number of tables |
| `39E6` far | `2294` | fast shape cache (never built in PS) |
| `3BBC` | `24B4` | `ts_init` first-call flag |
| `76D8` / `76DA` / `76DC` | `6482` / `6484` / `6486` | bm elevation / rotation / azimuth |
| `76DE` / `76E0` | `6488` / `648A` | bm ext1 / ext0 |
| `76E2` / `76E4` far | `648C` / `648E` | bm bitmap base / hot-spot table |
| `3B0A` / `3B0C` / `3B0E` | `23BC` / — / `23BE` | bm size cap (init 109h, reset 100h) / rotated-path flag (1) / size multiplier (1) |
| `3B52` / `3B53` / `3B55` | `2402` / `2403` / `2405` | shadow colour / mode / LOD cap |
| `76E8..76EC` | `6492..6496` | shadow position |
| `3BF2`, `76EE` 2×80 | — | `str_rotbuf` toggle / buffers |
| `3BF4` u32, `3BF8` far, `3BFC` | — | lowest stack pointer, its file, line |
| `3889..3894`, `38A2..38B1` | `25F5..2600`, `260E..261D` | `lmid` result, `proj32` scratch |

## 8. Port notes, hand-offs, open questions

**Port notes.** One implementation of the 3Space core can serve both programs if it is
parameterised by: the data block (PS `3d50` CS data vs AP `277a`), the PS-only routines of §3
(`asin16`/`acos16` table, `proj32`-based `pt_project`/`apparent_size`/near and 2D clippers), the
PS `ts_draw` draw-mode test, the PS `ts_bm` item drawer, and the absent EMS paths. The polygon
fill (`gfx_polygon` via `poly_fill`) and sprites are the shared video library.

**Hand-offs.**
* **render3d**: PS `3d50` is a byte-identical copy of most of `277a` (table §2.1); `3d50:1562/1589`
  use a 513-entry `floor(asin)` table, not the AP `asin_tab`. AP `2ec2:000d` → `07fe:000a` is only
  an assert (`ces_check`), so AP draws nothing for polygon flag 10h, whereas PS draws a textured
  quad. AP `70b4:0000/0188` (uncovered in AP) are `curve4_draw`/`bezier2_draw` (§6.1), no callers.
  AP `39e5:0000` (still uncovered, 256 bytes) matches PS `3d50:3e0f` = the `m_cam_block` data, i.e.
  a data block indexed as a function, not code.
* **shell_data** (`view3d_*` `217d`): the library entry points used are `ts_init` `48ea:0009`
  (from `0ddd:0b0c`), `ts_done` `48ea:0133` (`0ddd:0bce`), `ts_load_table` `48ea:0158`,
  `ts_free_table` `48ea:0236`, `ts_draw` `4708:0925`, `view_new` `47c8:0132`, `view_free`
  `47c8:0188`, `shape_*` accessors, `shadow_set_colour` `48ac:013a`, `shadow_pos` `48ac:0005`.

**Open questions.**
* `DS:3FB4` = `_stklen` (**likely**, not traced into the RTL).
