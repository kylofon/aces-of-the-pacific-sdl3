# render3d — part 3: the shape library ("ts2": `ts_draw`, `ts_bm`, `ts_util`, `ts_utilo`, `ts_file`)

Part of the `render3d` spec (index: `render3d.md`). Formats: `port/formats/shapes.md` (TBL, shape
header, LOD, part, variant, polygon) and `port/formats/world.md` §7 (`.BMD`). CS variables of `277a`:
`render3d_math.md` §2.3. Confidence **Verified** unless marked.

Segments: `2f0e` ts_draw.c, `2e33` ts_bm.c (bitmap shapes / BMD effects), `2edf` sprite/disc
helpers, `70e8` disc variant, `2ec2` 4-point bitmap, `2ecb` shadows, `271b` ts_util.c, `7074`
ts_utilo.c, `7039` ts_file.c, `7017` shape pointer cache, `7032` counts, `241c` BMD loader, `243d`
sprite sets. C code (Borland), far cdecl.

-----------------------------------------------------------------------------------------------

## 1. Data

### 1.1 Shape tables `DS:647C` (count `DS:6480`), 12-byte records — `7074:0000`

| Off | Type | Field |
|---|---|---|
| 00 | far ptr | the loaded `DAT:` pointer list (relocated far pointers, one per shape, zero-terminated); if the segment word `+02` is 0, `+00` is a **memory handle** (EMS/XMS, platform `1d32:22f4` alloc, `1d32:2525`/`2571` lock → pointer, `25a5` unlock, `24b6` free) |
| 04 | u16 | number of shapes |
| 06 | u16 | LOD scale (8.8, 100h = 1.0; `FFFFh` = use `+08` as a fixed LOD size) |
| 08 | u16 | LOD size limit (100h) |
| 0A | u16 | sprite set used by type-2 variants and BMD shapes, `FFFFh` = global numbering |

Global shape id = cumulative index over the tables in order. `DS:647E` = total count (set by
`7017:004f`). Fast path: `DS:2294` (far) = array of far pointers per id, `DS:2298` (far) = table
index per id (u8) — built by `7017:004f`, freed by `7017:0000`.

### 1.2 Sprite sets `DS:6498` (count `DS:649A`), 4-byte records

`u16 handle` (bitmap resource handle: `+06` width, `+08` height used here), `u16 count`. Filled by
`243d:0009/004c` (load a `BMP` by name through `7229:01aa` / `1d32:214e`), freed by
`243d:008f/00cd`. A "bitmap index" is either global (running over all sets, `2edf:0007`) or local to
the table's set `+0A`.

### 1.3 Draw record ("instance") passed to `ts_draw`

| Off | Type | Field |
|---|---|---|
| 00 | u16 | global shape id |
| 02 | i32[3] | position (world units) |
| 0E | u16[3] | pitch, roll, heading |
| 14 | u16 | DS pointer to the state bytes (one per state slot), 0 = all slots 0 |

(The records are built by the scene code, `render3d_world.md`: `33b4:010e`, `5440:0269`.)

-----------------------------------------------------------------------------------------------

## 2. `ts_draw` (`2f0e`)

### 2.1 `2f0e:08e9` `ts_draw(instance *o)`

```
if (bm_is_bitmap(o->id)) { bm_draw(o); return; }          /* 2e33:08b8 / 2e33:07f4 */
hdr = shape_ptr(o->id);            /* 271b:0007; also sets CS:0A25 */  CS:0A27 = hdr; assert(hdr)
CS:0A2B = o->state;  obj_shift CS:09AA = hdr[3];
radius CS:0A2D = (i32)hdr.radius(+0C) << hdr[3];
obj_set_position(o);               /* 277a:22f8 */
if (ts_visible_lod()) return;      /* 2f0e:0008: 1 = culled */
obj_set_orientation();             /* 277a:237d */
/* draw mode (render3d_math.md §1.5) */
if (obj_shift == 0 && radius <= 0x3FAC && (0x7D00 >> near_shift) >= e_dist + radius)  /* unsigned 32 */
    mode = 0;                      /* keeps the 32-bit e_pos, low words used */
else {
    obj_near_depth();              /* 277a:24ef */
    if ((e_near >> obj_down) > near_z) {            /* signed 32 vs u16 */
        obj_shift = vtx_shift; e_depth = sext(CS:0A45); e_pos = sext(e_pos16);
        mode = obj_shift ? 3 : 0;
    } else mode = ((0x3FAC >> near_shift) > radius) ? 1 : 2;
}
CS:09B0 = mode;
/* LOD (shapes.md §3) */
lods = hdr + hdr.lod_ofs(+0A); n = hdr.nlod(+08);
if (DS:2403 && n > DS:2405) lod = lods[DS:2405];           /* shadow: fixed LOD */
else { for (i = 0; i < n && app_size > lods[i].size; i++); if (i == n) i = n-1; lod = lods[i]; }
CS:09A2 = CS:09A4 = CS:09A6 = 0;                            /* invalidate vertex cache */
cnt = part_list(0, lod.nparts, lod.parts_ofs, list);        /* 2f0e:06eb, list = 54 words on stack */
part_walk(0, cnt, list);                                    /* 2f0e:071f */
```

The `0x7D00 >> near_shift` test: near objects of unscaled shapes (aircraft, `s = 0`) inside
`32000 >> 3 = 4000` units are drawn in mode 0 directly on the low words of the 32-bit eye position
(no near-plane box test: vertices behind the near plane are clipped by `2adf`).

### 2.2 `2f0e:0008` `ts_visible_lod()` → 1 culled / 0 visible

```
R = radius; E = e_pos (i32);
if (E.y + R < near_z) return 1;                                         /* signed 32 */
d = E.y − R; if (d < focal) d = focal;          /* CS:0A47 sign-extended */
A = apparent_size({R, d});                      /* 277a:304c: focal·R/d */
if (A > 256) app_size = 256; else { app_size = A; if (A == 0) return 1; }
c = { |E.x| − R, E.y + R, |E.z| − R };  p = pt_add_centre(pt_project(c));
if (p.x > DS:26C6 || p.y < DS:26C8) return 1;   /* signed 32 compares */
need_clip CS:09B3 = 0;
if (CS:09B2 || E.y − R < near_z) CS:09B3 = 1;
else { c = { |E.x| + R, E.y − R, |E.z| + R }; p = ...;
       if (p.x > DS:26C6 || p.y < DS:26C8) CS:09B3 = 1; }
t = &DS:647C[CS:0A25]; scale = t[+6]; lim = t[+8];
if (scale == 0x100) ; else if (scale == 0xFFFF) app_size = lim;
else app_size = clamp(mul_shr8(app_size, scale), 0, lim);        /* 277a:3968 */
return 0;
```

The corner tests only look right/up (absolute values): they assume a window symmetric about
`(cx, cy)`; `5440:03aa` sets `CS:09B2` (always clip) when it moves `cy` (render3d_world.md).

### 2.3 `2f0e:06eb` `part_list(self, n, parts_ofs, u16 *out)` → count

`out[i] = parts_ofs + 14·i` for i < n; if `self` ≠ 0 append `self`; returns n (+1).

### 2.4 `2f0e:033d` `part_sort(self, n, u16 *list)` → count (list compacted in place)

`hidden(p)` = `CS:0A2B != 0 && p.slot != FFh && state[p.slot] == FFh`.
* n < 2: n = 0 → 0; n = 1 → `hidden ? 0 : 1`.
* shape flags `& 40h` = 0: drop hidden parts, keep order.
* else: for each non-hidden part compute `key` (i32):
  `key = 0` if `p == self` or `p.normal == FFh`; else
  `P = (p.point == FFh) ? eye_in_obj : (vtx[p.point] >> −vtx_shift) + eye_in_obj` (16-bit per
  component; `vtx` = the part's own vertex array at `p.vtx_ofs`), `N = vtx[p.normal]`,
  `key = N·P` (`277a:4f18`, 32-bit). Then selection sort, **descending**, on the compacted list:
  for `i = 0..cnt−2`: find `j > i` with the largest key, strictly greater than the running maximum
  (so the first of equal keys wins); swap entries `i` and `j` (keys and parts) if `j ≠ i`.
  Keys are kept in a local array of 57 entries (no bound check).

Meaning: `N·P > 0` ⇔ the eye is behind the part's plane (seen from the side the normal points
away from); such parts are drawn first. Parts with key 0 (no plane) sit between.

### 2.5 `2f0e:071f` `part_walk(self, n, u16 *list)` (recursive)

```
n = part_sort(self, n, list);
for (i = 0; i < n; i++) {
    p = list[i];
    if (p != self && p.nchildren > 0) {                     /* +0A */
        sub = list + n;                                     /* appended after this level */
        m = part_list(p, p.nchildren, p.children_ofs, sub); /* children + p itself */
        part_walk(p, m, sub);
        continue;
    }
    CS:09A6 = p.vtx_ofs; CS:09A8 = p.nverts;
    v = 0;
    if (CS:0A2B && p.slot != FFh) { v = state[p.slot]; while (v >= p.nvariants) v -= p.nvariants; }
    var = p.variants_ofs + 8·v;                             /* in the shape segment */
    switch (var.type) {
    case 0: DS:26C3 = 0;
            mode 0: DS:2403 ? part_draw_shadow : part_draw16;   /* 277a:03bb / 05c6 */
            mode 3: part_draw16s (07ae);  modes 1, 2: part_draw32 (361d);  (arg = &var+2)
    case 1: disc_draw(&var+2);                              /* 70e8:0000 */
    default: sprite_draw(&var+2);                           /* 2edf:0119 */
    }
}
```

A part with children is drawn as a sub-list: its children and itself, sorted together (itself with
key 0). The same stack buffer (54 words in `08e9`) holds all levels.

-----------------------------------------------------------------------------------------------

## 3. Non-polygon variants and helpers

### 3.1 `2edf:005e` `vtx_eye16(u8 idx, i16 out[3])`

`idx == FFh` → `out = e_pos16` (`CS:0A0D`); else `out = vec_rotate(vtx[idx] >> −vtx_shift,
m_obj_eye) + e_pos16` (vertex array = current part's, `CS:0A27` segment : `CS:09A6`).

### 3.2 `70e8:0000` `disc_draw(var+2)` — variant type 1 (`+0 u16 size, +2 u8 vertex, +3 u8 VGA
colour, +4 u8 EGA colour`)

```
p = vtx_eye16(vertex); if (p.y < near_z) return;
x = cx + LDIV((i32)p.x << S, p.y);  y = cy − LDIV((i32)p.z << S, p.y);
r = LDIV((i32)(size >> −vtx_shift) << S, p.y);  if (r > 255) r = 256;
w = r + (r >> 2);
if (r && x <= DS:26C6 && DS:26C4 < x + w && y <= DS:26CA && DS:26C8 < y + r) {
    DS:26C3 = 1; DS:26CC = 1;
    c = DS:26DF ? var[+3] : var[+4];   if (CS:21EE) c = REMAP[c];
    DS:26CD = DS:26CE = c;
    1d32:6bbc(r, x, y);                 /* filled ellipse, video spec */
}
```

`LDIV` = Borland `0000:1d69` (signed 32-bit divide, toward zero).

### 3.3 `2edf:0119` `sprite_draw(var+2)` — variant type ≥ 2 (`+0 i16 bitmap, +2 u8 lo, +3 u8 hi,
+4 u8 scale, +5 u8 vertex`)

```
set = DS:647C[CS:0A25].+0A;
bm = (set == FFFF) ? bitmap_global(id) : (0 <= id < sets[set].count ? sets[set].list[id] : 0);
if (!bm) return;
p = vtx_eye16(vertex); if (p.y < near_z) return;
s = scale ? mul_shr8(app_size, scale) : app_size;
m = max(bm.w, bm.h) >> 1;  if (!s || !m) return;
f = LDIV((i32)s << 10, m);  w = mul_shr10(bm.w, f);  h = mul_shr10(bm.h, f);
x = cx + LDIV((i32)p.x << S, p.y);  y = cy − LDIV((i32)p.z << S, p.y);
DS:26C3 = 1;
1d32:5e5b(bm, x, y, 0, w, h, hi, lo);   /* scaled bitmap draw (video spec); lo/hi = the flag bytes */
```

(`2edf:0007` `bitmap_global(i)`: walks the sets subtracting counts; 0 if out of range.) No shipped
shape uses type 2.

### 3.4 Shadows `2ecb`

* `2ecb:0007` `shadow_pos(i32 pos[3], i32 out[3])` → 1 if cast: needs the world light
  `DS:6492/6494/6496` (copy of `CS:0008`, render3d_math.md §4.6) with `z >= 1`:
  `t = LDIV(−(pos.z << 12), light.z)`; `out.x = pos.x + lsar(t · light.x, 12)`;
  `out.y = pos.y + lsar(t · light.y, 12)`; `out.z = 0` (`LXMUL@` 32-bit product, `277a:3d52`).
* `2ecb:00ba` `shadow_draw(instance *o, lod)`: if `shadow_pos(o->pos)`: save `o->pos`, put the
  ground point in, `DS:2403 = 1`, `DS:2405 = lod`, `CS:0A2B = o->state`, `ts_draw(o)` (mode-0 objects
  go through `part_draw_shadow`), `DS:2403 = 0`, restore. Caller: `5440:0269` for type 0Bh with
  `DS:5CE0` as the LOD cap.
* `2ecb:013c` `set_shadow_colour(u8 c)`: `DS:2402 = c` (no caller found in the index; the colour is
  set elsewhere or stays 0 — **Unknown**, see render3d_sky.md for `1a8b`).

### 3.5 `2ec2:000d` 4-point bitmap (render3d_poly.md §2.3); `2ec2:0002` empty.

-----------------------------------------------------------------------------------------------

## 4. Bitmap shapes and `.BMD` effects (`2e33` ts_bm.c, `241c`)

### 4.1 `.BMD` file (all 31 files parse with this layout, `tools`-style decoder in the scratch of
this spec; **Verified**)

Chunks `VER:` ("40", first byte must be `'4'`), `EXT:` (36 bytes; words 0, 1 used: `ext0`,
`ext1`), `PRF:` (ignored by the loader), `BMD:` = `char name[8]` + data `D`:

| D+ | Type | Field |
|---|---|---|
| 00 | u16 | radius (becomes shape `+0C`) |
| 02 | u8 | number of animation frames (the shape's state-slot variant count: header `+06` points here) |
| 03..11 | | other header words (not read by the draw code) |
| 12 | u16 | `nhot` = number of bitmaps described |
| 14 | i8[nhot][2] | hot-spot (x, y) per bitmap index |
| 14+2·nhot | | elevation table: `u16 n` (7), `n × {i16 elevation, u16 offset}` (elevations 0, 2730, 5461, 8192, 10923, 13653, 16384 = 0°..90° step 15°) |
| offset | | azimuth table: `u16 n` (12), `n × {i16 azimuth, u16 offset}` |
| offset | | frame list: `u16 nframes`, then per frame `u16 nitems` + `nitems × item` |

Item (9 bytes): `u8 bitmap` (index relative to the shape's sprite base), `i8 dx`, `i8 dy`,
`u16 sx`, `u16 sy` (scale, 1024 = 1.0; 0 = unscaled), `u16 rot` (angle). Offsets are relative to `D`.
All files: 7 elevations × 12 azimuths; frame counts 1–21; `EXT` pairs `(1,30)`, `(1,50)`, `(1,40)`,
`(1,20)` or `(0,100)`.

### 4.2 `241c:0005` `bmd_load(shape_id, sprite_set, name)` → pointer to `D` or 0

Opens `name` (`7039:0187`, chunk lookup `7187:01d4`); `VER:` (2 bytes, first `'4'`); `tmpl =
shape_ptr(shape_id)` (an existing placeholder shape of the table); `EXT:` → `DS:648A = ext0`,
`DS:6488 = ext1` (`DS:648A = 0` if absent); `BMD:` (size N): allocate a memory handle of `N + 16h`
bytes (`1d32:22f4`), lock, zero it, read the 8-byte name, then build a shape header in place:
`[0] = 30h` (no box + bitmap), `[1] = tmpl[1]` (class), `[04] = 1` (one state slot), `[06] =`
offset of `D+2`, `[0A] = sprite_set`, `[0C] = D.radius`, `[1A] = ext0`, `[1C] = ext1`, `D` read at
`+1Eh`; register it under `shape_id` (`271b:011d`, replacing the table's far pointer), unlock.
`241c:01f6` frees it (`dos_free` of `shape_ptr(id)` — note: a handle-allocated shape is freed with
`dos_free`, **Likely** a latent bug, only matters at exit).
Callers: `0916:002e` (parachutes `para_*`), `4b3a:0000`/`025c` (damage.c: `flak1–4` etc.; sim_world
chooses which effect loads into which id).

### 4.3 `2e33:07f4` `bm_draw(instance *o)` / `2e33:08b8` `bm_is_bitmap(id)`

`bm_is_bitmap`: shape exists and `flags & 10h`. `bm_draw` (asserts the same):
`obj_shift = 0; radius = sext(hdr[0C]); CS:0A27 = hdr; obj_set_position(o);`
if `bm_visible()` (`2e33:0208`, returns 0 when visible): `obj_set_orientation(); bm_view_angles();
DS:648C = hdr[0A]` (sprite base); `frame = o->state ? *o->state : 0`;
`bm_draw_frame(hdr + 1Ah, frame)`.

`2e33:0208` `bm_visible`: requires `E.y >= near_z`; `app_size = apparent_size(R, E.y)` (≠ 0);
nearest-corner test as in `2f0e:0008` (right/top only). No LOD scale, no `CS:09B3`.

### 4.4 `2e33:0333` `bm_view_angles()` — eye direction seen from the object (object axes)

`v = −eye_in_obj` (vector object → eye). `elev = 4000h − atan2_16(v.z, dist2_16(v.x, v.y))` → `DS:6482`;
if `|elev| < 3FD1h`: `DS:6486 = atan2_16(v.x, v.y) − 4000h` (azimuth), else `elev = ±4000h`,
azimuth 0 (looking straight down/up). The same for `e_pos16` (the object origin in eye space) gives
the view-ray angles `(elev2, az2)`; a matrix `m_obj_eye · R(az: −az2) · R(pitch: −elev2)` is built
with `mat_from_angles`/`mat_mul`, and the on-screen rotation of the object's "up" is
`DS:6484 = 4000h − atan2_16(M[2][0], M[2][1])` (taking row 1 instead when the first clamp applied)
(**Likely** in the exact matrix element choice: `2e33:03f8..0505`).

### 4.5 `2e33:0508` `bm_draw_frame(u16 *p /* hdr+1A */, frame)`

```
DS:648A = p[0]; DS:6488 = p[1]; D = p + 4 bytes; DS:648E = &D[14h] (hot-spots, far);
E = elevation table: pick the entry with the smallest |elevation − DS:6482| (first on ties);
A = azimuth table at D + E.offset: smallest |azimuth − DS:6486|;
F = frame list at D + A.offset: nf = *F; if nf == 0 return;
while (frame >= nf) frame -= nf;   skip `frame` frames → (nitems, items);
s  = LDIV((i32)app_size << 8, 127);         /* size scale, 256 ≈ app_size 127 */
sy = s;
if (DS:648A) {                               /* ext0 = 1: squash with elevation */
    a = acos16(LDIV((i32)DS:6488 << 14, 100));        /* acos(ext1/100) */
    c = cos16(LDIV((i32)DS:6482 · a, 0x4000)) >> 6;   /* 0..256 */
    sy = mul_shr8(s, c);
}
x = cx + LDIV((i32)e_pos16.x << S, e_pos16.y);  y = cy − LDIV((i32)e_pos16.z << S, e_pos16.y);
for each item: bm_draw_item(item, s, sy, x, y, s, c);   /* c undefined when ext0 = 0 (not used) */
```

### 4.6 `2e33:001c` `bm_draw_item(item, a, b, x, y, k, c)`

```
bm = bitmap_global(DS:648C + item.bitmap); assert(bm);
if (item.sx) a = mul_shr10(a, item.sx);  if (item.sy) b = mul_shr10(b, item.sy);
a = min(a, DS:23BC); b = min(b, DS:23BC);            /* DS:23BC = 200h default (2e33:0011) */
w = mul_shr8(bm.w, a); h = mul_shr8(bm.h, b); if (!w || !h) return;
dx = item.dx; dy = item.dy; if (DS:648A) dy = mul_shr8(dy, c);
rx = mul_cos(dx, DS:6484) − mul_sin(dy, DS:6484);   ry = mul_sin(dx, DS:6484) + mul_cos(dy, DS:6484);
rx = mul_shr8(rx, k); ry = mul_shr8(ry, k);
DS:26C3 = 1;
1d32:2258(bm, x + rx, y + ry, item.rot + DS:6484, w·DS:23BE, h·DS:23BE,
          hot[bm_idx].x / DS:23BE, hot[bm_idx].y / DS:23BE);   /* rotated scaled blit, video */
```

(`y + ry`: screen y grows downwards while `dy` is a picture offset — kept as in the code.)
`2e33:0006`/`0011` set/reset `DS:23BC` (size cap; `0006` is called by `655d:0322` with the
`shipsiz` setting — sim_world); `2e33:08e7`/`08f2` set/reset `DS:23BE` (integer size multiplier,
default 1; no caller found).

-----------------------------------------------------------------------------------------------

## 5. `ts_util.c` `271b`, `ts_utilo.c` `7074`, `ts_file.c` `7039`, `7017`, `7032`, `243d`

| Address | Name | Behaviour |
|---|---|---|
| `271b:0007` | `shape_ptr(id)` → far | fast path if `DS:2294` set and `id < DS:647E`: `CS:0A25 = DS:2298[id]`, lock the table's handle if it is one, return `DS:2294[id]`; else walk the tables (`id −= count`), `CS:0A25 = table`, return `ptrlist[id]` (through `1d32:2525` when the table is a handle). 0 if out of range |
| `271b:011d` | `shape_set_ptr(id, far p)` | same walk, stores `p` into the pointer list (and the fast cache) |
| `271b:0251` / `02a6` | `view_new(eye)` / `view_free(v)` | camera record (render3d_math.md §2.1) |
| `271b:02b5` | `shape_flags(id)` | header byte 0 (asserts non-null) |
| `271b:02f5` / `0336` | `shape_class(id)` / `shape_set_class(id, c)` | byte 1 |
| `271b:037a` | `shape_subclass(id)` | byte 2 |
| `271b:03bb` | `shape_shift(id)` | byte 3 |
| `271b:03fc` | `shape_nslots(id)` | word 4 |
| `271b:043d` | `shape_nvariants(id, slot)` | `hdr[hdr[6] + slot]`, asserts `0 <= slot < nslots` |
| `271b:04b4` / `04f5` | `shape_radius(id)` / `shape_set_radius(id, r)` | word 0Ch |
| `271b:0539` | `shape_radius_world(id)` | `(i32)radius << shift` |
| `271b:0584` | `shape_box(id, i16 min[3], i16 max[3])` | copies `+0E`/`+14h` when the pointers are non-null (no check of flag 20h) |
| `7074:0000` | `ts_init(ntables, nsets)` | `malloc` the table arrays (min 1 each), init records (`0, 0, 100h, 100h, FFFFh`) and sets; first call only (`DS:24B4`): `set_light(2000h, A000h)` |
| `7074:012d` | `ts_done()` | counts to 0, free both arrays |
| `7074:0154` | `ts_load_table(t, name)` | `7039:020a(name, "DAT:")` into DOS memory; relocate every far pointer (32-bit add of the load address) and count them |
| `7074:02d8` | `ts_load_table_h(t, name, flag)` | same through `7039:02a4` (memory handle when `DS:1FEC` and `1d32:22f4` succeeds; locked for relocation, then unlocked) |
| `7074:022b` | `ts_free_table(t)` | free handle or DOS block, reset the record |
| `7039:0000` | `ts_read(far dst, u32 n, file)` | read in chunks through a malloc'd buffer (16 KB, halving/−256 down to a 256-byte stack buffer), `fread` + far copy (`0000:3dc9`), advances a huge pointer (`PADA@`) |
| `7039:0187` / `0144` | `ts_open(name, tag)` / `ts_close(f)` | volume file open (`7187:0527` if already open, else `7187:013c`), seek to chunk `tag` (`7187:01d4`); `DS:2408` = opened-here flag |
| `7039:020a` | `ts_load_chunk(name, tag)` → far | `dos_alloc(size)`, `ts_read` |
| `7039:02a4` | `ts_load_chunk_h(name, tag, flag)` | handle variant (asserts size < 64 KB... `> 1:0000` check) |
| `7017:004f` / `0000` | `shape_cache_build` / `shape_cache_free` | `DS:2294`/`DS:2298` (1.1) |
| `7032:0000` | `shape_count()` | `DS:647E` if the cache exists else Σ counts |
| `7032:0039` | `sprite_count()` | Σ set counts |
| `243d:0009` / `004c` | `sprite_set_load(set, name)` | `7229:01aa` / `1d32:214e` load, count `7229:0598` |
| `243d:008f` / `00cd` | `sprite_set_free(set)` | `1d32:2170` / `7229:056a` |

Callers of the table loaders: the area loader `62d2:049e`, `56ac:0236`/`010b` (snario, loads the
model tables), `1641:000c` (misctbl `APP:`), `3368:0001` (`GID:`), render3d_world.md.

## 6. Differences between `tools/dynshape.py` and the game

* The tool picks the most detailed LOD and ignores `app_size`/LOD scale; the game uses §2.1.
* The tool uses a fixed light; the game's light is `CS:0A3B` = the world light (`5440:03aa` sets it
  from the sun direction `DS:51D9`) rotated into object axes.
* Shading/sorting/culling match. `CS:21EC` is a pointer to SHADES in DGROUP.

## 7. Port notes

* `/* PORT: */` Memory handles (EMS) for shape tables become plain allocations; `shape_ptr` returns
  a pointer into the emulated memory.
* `.BMD` shapes are rebuilt in memory with a synthetic 1Eh-byte header; keep that layout because
  `ts_util` accessors read it (`shape_nvariants` → frame count).
