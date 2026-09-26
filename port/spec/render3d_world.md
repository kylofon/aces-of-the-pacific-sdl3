# render3d — part 4 (D): scene assembly, object lists, depth order, world loading

Part of the `render3d` spec (index: `render3d.md`). AP.EXE addresses in `work/AP_flat.exe`
(`SSSS:OOOO`, DGROUP `3EA4`, `DS:xxxx`). Formats this part builds on: `port/formats/world.md` (WD3,
MBL, FLT, TARGET), `port/formats/shapes.md` (header, GID). Math, camera record `DS:437E`, the `277a`
CS block and routine names (`ldist3 3b3c`, `ldist2 3bfc`, `log_key 3c90`, `lnear 5434`, `lbox 5510`,
...): `render3d_math.md`. `ts_draw 2f0e:08e9` and `shadow_draw 2ecb:00ba`: `render3d_shapes.md`.
Sky, horizon `4d6e`, sun `6964`, ground dots `675d`: `render3d_sky.md`.

Scope: `5440:03aa/0269/0375` (segment `5440` is sim_flow's; these three are the 3D scene by
content), `33d1` (10), `33b4` (3), `34bf` (4), `465c:0589`, `0802` (3), `1560:055b/06e9`, `05a9` (8),
`2466` (2), `59f9` (4), `35a4:000f`, `35d1:000e`, `35d6` (9), `3368` (6), `333b` (6), `33a1` (3),
`3546` pool.c (15), `3591` init.c (2), `35ad` obwload.c (3), `34f1` macros.c (12), `62d2` (9),
`628f` wdata.c (9), `62ca` (2), `51ca` (6).

Confidence: **Verified** (read in the disassembly) unless marked **Likely** / **Unknown**.
Calling convention: far cdecl (`retf`, arguments on the stack, caller pops) unless noted; "AX=" marks
register arguments. `SCOPY@` (`0000:1c7a`, CX bytes, far src/dst) is the RTL struct copy.
Library helpers referenced (platform/RTL, not specced here): `24b2:013d` `fnew(u32 size, flag)`
(far alloc), `24b2:01c0` `ffree(far)`, `24b2:0074` `nnew(size, …)` / `24b2:00ca` `nfree(p, …)`
(near, with assert file/line args), `24d3:0059` `mark_alloc(size)` (near stack heap `DS:1FDA`+`1FDE`,
size rounded up to even, zero-filled), `24d3:0092` `mark_release(p)`, `2494:0127` fatal error,
`2494:0009` source-file tag for the allocators, `0000:0555` `vol_fopen(name, mode)`, `0000:08cc`
`vol_fclose`, `0000:0945` `vol_fread(buf, size, n, fp)` (returns n read), `0000:0ae8`
`vol_fseek(fp, i32, whence)`, `0000:0bba` `vol_filelength(fp)` (i32), `0000:0c58` `vol_getc(fp)`,
`0000:0d8d` `vol_putc(c, fp)`, `0000:1fff` `labs`, `0000:4b03` `_fmemset(far p, c, n)`,
`1d32:67fb` far memmove (u32 count), `1d32:690e` far memset (u32 count), `7187:013c` resource-file
open, `7187:01d4` find chunk (returns i32 offset, −1 = none), `7187:04cc` chunk size (i32),
`7187:04f7` close.

-----------------------------------------------------------------------------------------------

## 1. Data structures

### 1.1 The object flags word (`+00` of every drawable object)

| Bits | Meaning (as used by this part) |
|---|---|
| `001Fh` | object type. Values seen here: 1 static world object / long macro group, 0/2/10h/11h short macro group (state from the target file, §6.3), 3 aircraft, 4 ship, 5 ordnance, 0Bh shadow-only object, 0Ch/0Dh (sort comparator), 0Eh effect, 0Fh debris/parachute, 12h far-aircraft dot proxy. Names of the sim types belong to sim_world |
| `0040h` | macro member shown as its wreck (destroyed) / fire phase 2 (`1560:055b`) |
| `0080h` | fire phase 1 (`1560:055b`) |
| `0100h` | "skip this frame": set by the culling code (`0802`, `05a9:01d1`); cleared (and the object not drawn) by the list insertion `33d1:00f2`/`0140` and by `33b4:002a` |
| `0E00h` | placement kind: where the draw record takes z and the angles (§1.2) |
| `1000h` | static world object (WD3 group, macro member): never added by `33d1:0140`; state handling in `5440:0269` |
| `2000h` | hidden (not drawn; set on the player's own aircraft in cockpit views, on wrecks without a wreck shape) |
| `4000h` | WD3 instance without rotation (set by the loader; not read by this part) |

### 1.2 Draw record (22 bytes) — built by `33b4:010e` into `DS:3666` (confirmed)

| Off | Type | Field | Source (`o` = object, `k = o.flags & 0E00h`) |
|---|---|---|---|
| 00 | u16 | global shape id | `o[+02] & 1FFFh` |
| 02 | i32[3] | position x, y, z (world units) | `o[+04..+0F]`; **z = 0** when `k` is 400h, 600h or C00h |
| 0E | u16[3] | pitch, roll, heading | `k = 200h`: (0, 0, `o[+10h]`); `600h`: (0, 0, `o[+0Ch]`); `800h`: `o[+10h..+15h]`; `C00h`: `o[+0Ch..+11h]`; other `k`: 0 |
| 14 | u16 | DS pointer to the state bytes, 0 = none | 0 (set by `5440:0269`) |

So an object's world position reaches `ts_draw` unchanged (i32 world units, no offset or scale);
`2f0e:08e9` → `277a:22f8` subtracts the eye position (render3d_math.md §1.3). Objects of kinds
400h/600h/C00h stand on z = 0 and reuse their z slot (`+0Ch`) for angles. **WD3/macro angle order
settled**: `+10h` pitch, `+12h` roll, `+14h` heading (the 22-byte member / 24-byte instance
layout feeds the record in `mat_from_angles` order).

### 1.3 World object records

**WD3 static instance, 24 bytes** (`62d2:0133`, array `DS:5138` far, count `DS:5136`):
`+00 u16 flags` = `0801h`, `| 4000h` when `rec[+10h] | rec[+14h] == 0` (roll ignored); `+02 u16`
shape (the table index as stored); `+04 i32[3]` position; `+10/+12/+14 u16` pitch, roll, heading;
`+16 u16` 0.

**MBL group record, 42 bytes** (`62d2:001d`, array `DS:512A` far, count `DS:5128`):
* short form (`type & C000h == 8000h`): `+00 u16 flags = state | 1200h` (state from the target file,
  §6.3; type bits = 0, 2, 10h or 11h; 200h = heading only); `+02 u16 type` (8000h + macro);
  `+04 i32[3]` position; `+10 u16` heading; `+12..+29` 24 bytes zero = **per-member damage bytes**
  (`FFh` = member destroyed; indexed by member number, see §3.3; cleared again at mission start by
  `62d2:044a`).
* long form (`C000h`, the 40-byte MBL record, one in AW3): `+00 = 1001h`, `+02` type, `+04` position,
  `+10 i32` x phase, `+14 i32` y phase, `+18` 4 bytes, `+1C i32[3]` extent (40 bytes copied). The
  macro is **tiled** over the rectangle `[pos, pos + extent]` (x/y) with pitch = macro box x/y
  (§3.3). This settles world.md's "40-byte MBL record".

**Macro member, 22 bytes** (`AW<n>.MBL`, world.md §3): `+00 flags` (4800h/0800h), `+02 shape`,
`+04 i32[3]` relative position, `+10/+12/+14` pitch, roll, heading.

**Temporary member objects** (per frame, arena `DS:36A8`, §5.4): *A records* (30 bytes, from the
bottom) for 3D members: the 22 member bytes, then `+16 far` group record, `+1A u16` member index,
`+1C u8` = FFh (fire animation counter), `+1D u8` object kind (`1641:0157(shape)`, APP kind);
*B records* (40 bytes, from the top) for flat members: 22 member bytes, rest 0.
Flags of both: `1800h | (group.flags & 0FFh)` (so 800h placement and the group's type bits).

**Far-aircraft proxy, 18 bytes** (`DS:5EDE`, allocated by `2466:000a` with `mark_alloc(DS:4776·18)`):
`+00 = 8012h` (type 12h), `+02` shape of the aircraft, `+04 i32[3]` its position,
`+10 u16` colour = `WORD[ WORD[DS:55D2 + 2·BYTE[DS:54BC + ac[+19h]]] + 81h ]` (side colour of the
aircraft type, sim data). Index restarts at 0 every frame.

**Effect record, 48 bytes** (pool `DS:55F1`, §4.1): `+00` flags (fires: `080Eh`), `+02` shape,
`+04 i32[3]` position (z < 0 → deleted), `+10` angles, `+16 u16` state/animation frame (low byte
drawn), `+18 far` update callback (0 = none), `+1C u16` cull radius in units of 1024, `+1E u8`,
`+1F u8` bit 0 = updated since the last draw, `+2A u16` radius used when drawing. Other fields are
the spawner's (sim_world).

### 1.4 Draw list and sort tree

Draw list `DS:36D4` (far, `fnew(2000)` = **250 entries** of 8 bytes: `{far object*, i32 key}`),
capacity `DS:367C = 250`, reserve for moving objects `DS:367E = 100` (so the static gather stops at
150). Layout after a gather: `[0, DS:36DA)` ground-layer entries (already ordered), `[36DA,
36DA+36DC)` static distance entries, then moving objects appended by `33d1:00f2` up to `DS:36D8`.

Sort tree node (8 bytes): `+00 far` pointer to the list entry (in `33d1:04e7` replaced by the object
pointer before flattening), `+04 u8` parent, `+05 u8` nearer child ("left"), `+06 u8` farther child
("right"), `+07 u8` flags: 1 has parent, 2 has nearer, 4 has farther, 8 visited.

### 1.5 Globals of the scene code

| DS: | Type | Name | Meaning |
|---|---|---|---|
| `3666` | rec | `draw_rec` | draw record built by `33b4:010e` (22 bytes, `3668` pos, `3670` z, `3674..3679` angles) |
| `367C` | u16 | `list_cap` | 250 (set by the area loader) |
| `367E` | u16 | `list_reserve` | 100 |
| `3680` | u16 | `gather_force` | 1 = rebuild the static list at the next gather (`33d1:04dc`) |
| `3682` | u16 | `scene_view` | camera record of the frame (set by `33d1:0004`) |
| `3688` | i32[3] | `gather_eye` | eye position of the last static rebuild |
| `3694` | far | `list_front` | front fill pointer during a rebuild |
| `3698` | far | `list_back` | back fill pointer (starts at `36D4 + 8·367C`, moves down) |
| `369C` | far | `gather_obj` | object being tested by `33d1:02eb` |
| `36A0` | i32 | `big_range_min` | 250 000 (initialised data): minimum range of objects with radius ≥ 5 000 000 |
| `36A4` | far | `flatten_ptr` | output pointer of `33d1:0e6a` |
| `36A8` | far | `tmp_arena` | per-frame arena for expanded members (11 000 bytes) |
| `36AC` | u16 | `macro_cap` | 31 |
| `36AE` | far | `macro_tab` | macro table, 18-byte entries `{u16 n, i32 box[3], far members}` |
| `36B2` | u16 | `macro_count` | macros loaded |
| `36B4` | i32[3] | | zero vector (origin for `34f1:0259`) |
| `36C4` | i16 | `regather_dist` | 7500 (set by the loader) |
| `36C6` | far | `gid_base` | loaded `GID:` chunk; `36CA` = entry count |
| `36CC` | far | `draw_cb` | per-object draw callback, `3d32:0070` = `5440:0269` |
| `36D0` | far | `after_ground_cb` | called after the ground layer, `3e07:0020` = `675d:0000` (ground speed dots, render3d_sky.md) |
| `36D4` | far | `draw_list` | §1.4 |
| `36D8` | u16 | `list_n` | entries used |
| `36DA` | u16 | `list_ground_n` | ground-layer entries |
| `36DC` | u16 | `list_static_n` | static distance entries |
| `36DE` | u16 | `flt_n` | 20 (class records) |
| `36E0` | u16 | `flt_tab` | near pointer to 20 × 85-byte class records (§6.4) |
| `36E2` | u16 | `flt_range` | near pointer to i32[20]: current range ×1000 per class |
| `3700/3704/3708` | far | | shape attribute cache: class, layer, shift bytes (§6.6) |
| `370C` | far | | radius words; `3710` u8 cache valid |
| `5822` | u16 | | shared random-table cursor (also `14b8:0072`, sim_flow) |
| `5EDE` | u16 | `proxy_buf` | far-aircraft proxies (§1.3) |
| `06F3` | far | `world_objs` | far pointers to all static objects (§6.1) |
| `43D6` | u16 | `world_n` | entries of `06F3` |
| `5134 ≤ 5132 ≤ 5130 ≤ 512E ≤ 43D6` | u16 | | partition of `06F3` (§6.1) |
| `710A/710C/710E` | u16 | | arena top / bottom / size+1 |
| `7110` | far | `wd3_handler` | `3de9:0034` = `62d2:0199` |
| `7114` | u16 | `whd_tab` | near pointer to the 512-byte `WHD:` count table while loading |

-----------------------------------------------------------------------------------------------

## 2. The 3D frame (`5440`)

### 2.1 `5440:018c` frame driver (sim_flow) — only the renderer calls

`if (DS:06A5 (i32) < 0) return 0;` video page calls `368f:03c1/03b6`; wait for the tick timeout
`4b31:0000(148h)`; `effects_update_view(eye_pos())` (`05a9:00ad`); `if (!overcast()) 1a8b:004c()`
(aircraft shadows); `655d:038a` (muzzle flashes); cockpit/message/LSO calls; then by view mode
`1c30:0780()` (`DS:5EBB`): 0–3 → `0962:0bf1(); render_scene(); 0962:0c7f();` (cockpit window
masks around the 3D view), other → `render_scene()` only; cockpit/HUD overlays; `if
(!DS:069F) 17ce:0013()` (palette); `5440:07e1`. `5440:009c` (sim init) creates the camera
`271b:0251(DS:4368)` → `DS:437E = DS:43D8`, shades `DS:4092`, window from `DS:06AD..06B3`, then
`scene_begin`, `scene_force_rebuild`, `scene_gather_static(0)` (the initial list).

### 2.2 `5440:03aa` `render_scene()` (Verified)

```
4899:005c(DS:437E);                 /* sim_flow: clip window bottom to the panel top DS:3CD8 */
cy = 644a:089f(DS:437E + 0Ah);      /* sim_flow: per-view window; returns the centre y */
cam_begin_frame(DS:437E);           /* 277a:004b */
if (DS:19F2) { CS:0A4D = cy; CS:09B2 = 1; }        /* moved view centre: force clipping */
set_light(DS:51D9, DS:51DD);        /* 277a:0152 (sun pitch, heading; render3d_sky.md) */
DS:26C3 = 1; DS:26C4 = cam.x0; DS:26C8 = cam.y0; DS:26CA = y0+h-1; DS:26C6 = x0+w-1;
4899:0027();                        /* sim_flow: panel clip of DS:26CA */
CS:09B2 += (DS:00F8 == 0);          /* 4899:0000 = full-screen flag: panel visible -> force clip */
4d6e:0076(far DS:5BDB, CS:0A1F /*pitch*/, CS:0A21 /*roll*/,
          DS:5BDA ? NULL : 3e1d:002a /*= 6964:01a2 sun/moon*/);   /* horizon, render3d_sky.md */
pl = DS:3B09;                        /* player object */
if (!(pl[+1Ah] & 1)) { if (DS:19F2) pl.flags |= 2000h; else pl.flags &= ~2000h; }
DS:36CC = 3d32:0070;  DS:36D0 = 3e07:0020;          /* callbacks (stubs) */
scene_begin(DS:437E);               /* 33d1:0004 */
if (DS:18C0) DS:18C0--;             /* only ever zeroed elsewhere (14e0:0044): always 0 */
if (!overcast_split()) {            /* 0802:0026 */
    if (DS:4380) { scene_force_rebuild(); DS:4380 = 0; }
    scene_gather_static((u8)DS:18C0);
} else { DS:36D8 = DS:36DC = DS:36DA = 0; DS:4380 = 1; }   /* eye above the overcast */
eye = eye_pos();                    /* 5440:008d */
visibility_cull();                  /* 0802:0173 */
490a:0509(eye);                     /* sim_world: cloud effects */
spawn_ground_fires();               /* 1560:055b */
spot = 583c:0471();                 /* sim_world */
k = 0;
for (i = 0; i < DS:00BE; i++) {     /* moving objects: aircraft and ships, DS:00BC[] (near ptrs) */
    o = DS:00BC[i];
    if ((BYTE[o[+34h] + 3Bh] & 2) && o[+18h] != 1) continue;
    d = ldist3(eye, o+4);           /* u32 */
    if (o[+18h] == 0 && !(o.flags & 100h)) {           /* aircraft */
        R = shape_radius(o[+2]) << 7;                  /* 35d6:018a, i32 */
        if (2·R <= d) continue;                        /* unsigned: not drawn at all */
        if (DS:42C8 && 583c:04a9(o+4, eye, d, spot, DS:3B09)) continue;   /* not spotted */
        if (d < R) list_add(o, d);
        else { p = DS:5EDE + 18·k++; p = {8012h, o[+2], o.pos, colour}; list_add(p, d); }
    } else if (o[+18h] == 1) { if (d < 250000) list_add(o, d); }       /* ship */
    else list_add(o, d);            /* aircraft with 100h: list_add clears the flag, skips */
}
own = (1c30:0780() == 2 || 1c30:0780() == 3);
for (e = pool_next(DS:00E6, 0); e; e = pool_next(DS:00E6, e))          /* ordnance pool */
    if ((e[+18h] & 0Fh) == DS:54B5) 04c4:0b53(e, eye);                /* flak burst (sim_world) */
    else if (!own || e[+16h] != DS:3B09) scene_add_dynamic(e);        /* 33d1:0140 */
for (e = pool_next(DS:55F1, 0); e; ...) scene_add_dynamic(e);        /* effects */
scene_draw();                       /* 34bf:0006 */
CS:09B2 -= (DS:00F8 == 0);
```

Keys of moving objects are plain `ldist3` distances. Aircraft closer than `128·R` are drawn as
shapes, between `128·R` and `256·R` as one-pixel dots (§4.3), farther not at all (`R` = the shape's
unshifted header radius). `list_add` = `33d1:00f2`.

### 2.3 `5440:0269` `draw_object(far obj *o)` — the `DS:36CC` callback (Verified)

```
t = o.flags & 1Fh;
if (!(DS:06B7++ & 1)) 1c0f:0053();          /* sim_flow VCR hook, on every other object drawn */
if (t == 0Fh) 0916:0273(o);                 /* sim_world draw, then CONTINUES below */
if (t == 0Eh) { effect_draw(o); return; }   /* 1560:06e9 */
if (t == 12h) { far_dot_draw(o); return; }  /* 2466:0023 */
if (o.flags & 2000h) return;
if (t == 5) { 05d6:01d3(o); return; }       /* sim_world: ordnance */
r = build_draw_rec(o);                      /* 33b4:010e -> DS:3666 */
if (o.flags & 1000h) {
    if (o[+1Dh] == 0Ch) {                   /* APP kind 0Ch (flags on bases) */
        if (t == 11h) return;
        tmp = (t == 10h) ? 0 : 1;  r.state = &tmp;
    }                                       /* else r.state stays 0 */
} else {
    r.state = o[+16h];
    if (r.state < 40h) { tmp = (u8)r.state; r.state = &tmp; }   /* small value = the state itself */
}
set_near(get_near_n() - 3);                 /* 277a:002d/0012: near = focal/8 */
if (t == 0Bh) shadow_draw(r, DS:5CE0); else ts_draw(r);        /* 2ecb:00ba / 2f0e:08e9 */
reset_near();                               /* 277a:0037 */
```

`tmp` is a stack byte of this function. `DS:06B7` = draw counter (u16).

### 2.4 `5440:0375` `range_from_size(i16 v)` → i32 (Verified; callers `583c:0ef0/18bf`, sim_world AI
spotting — not renderer code)

`r = (i32)(i16)(v + 40) << 8; if (r < 100000) r = 100000; return r;` (DX:AX).

### 2.5 `5440:008d` `eye_pos()` → `WORD[DS:437E][+2] + 2` (pointer to the eye position). Used by
`490a:017f`, `4bf9:0017`, `5440:018c`, `03aa`.

-----------------------------------------------------------------------------------------------

## 3. Object lists and depth order (`33d1`, `34bf`, `33b4`, `465c:0589`)

### 3.1 `33d1:0004` `scene_begin(camera *v)`

```
DS:3682 = v;
a = eye.z >> 2 (i32 sar);  alt = (a >= 7FFFh) ? 7FFFh : (i16)a;     /* no lower clamp */
for (c = 0; c < DS:36DE; c++) {
    e = DS:36E0 + 85·c;
    if (e[0] && e[3] == 0)                                              /* range mode */
        DS:36E2[c] = (i32)(i16)(e.r0 + (i16)(((i32)(i16)(e.r1 - e.r0) · alt) >> 15)) · 1000;
}                                                   /* r0 = WORD e+7, r1 = WORD e+9; 16-bit adds */
arena_reset();                                      /* 34f1:0144 */
```

### 3.2 `33d1:00a8` `eye_moved(camera *v)` → u8 and `33d1:04dc` `scene_force_rebuild()`

`00a8`: `d = ldist3(eye, DS:3688)`; if `d > (u32)(i32)DS:36C4` (unsigned compare with the
sign-extended word): `DS:3688 = eye`, return 1; else 0. `04dc`: `DS:3680 = 1` (callers `5440:009c`,
`03aa`, detail slider `4b9f:00d0`).

### 3.3 `33d1:04e7` `scene_gather_static(u8 keep)` (Verified)

Local `E` = copy of the eye position (`WORD[v+2] + 2`).

**Refresh path** — taken when `DS:3680 == 0` and (`keep != 0` or `!eye_moved(v)`):
`DS:3698 = DS:36D4 + 8·DS:36DA`; for each of the `DS:36DC` entries there: `key = ldist3(E, obj+4)`;
`DS:36D8 = DS:36DA + DS:36DC`; return. (Moving objects appended last frame are dropped.)

**Rebuild path**:
```
DS:3680 = 0; S = WORD[v+0] (projection shift, 7);
DS:36D8 = 0; DS:3694 = DS:36D4; DS:36DA = 0; DS:3698 = DS:36D4 + 8·DS:367C; DS:36DC = 0;
lim = DS:367C - DS:367E;  i = 0;  P = DS:06F3;
while (i < DS:5134) { o = P[i++]; if (lnear(E, o+4, 2000000)) gather_test(o); if (DS:36D8 >= lim) goto done; }
while (i < DS:5132) { o = P[i++]; if (lnear(E, o+4, radius_w(o[+2] & 1FFFh) + 4000000)) gather_test(o); ...same stop }
while (i < DS:5130) { o = P[i++]; if (lnear(E, o+4, 2000000)) gather_test(o); ... }
while (i < DS:512E) {                               /* short macro groups */
    g = P[i++]; d = ldist3(E, g+4);
    if (d > 1300000) continue;
    if (!(log_key(macro_radius(g)) + (S << 8) > log_key(d))) continue;   /* 34f1:0259, i16 compare */
    n = macro_expand(g);                            /* 34f1:0155 -> buffer 3B05:0000 */
    for (m = 0; m < n; m++) {
        src = 3B05:0000 + 22·m;
        if (layer(src.shape) == 0) {                /* 35d6:01e2: 3D member -> A record */
            a = arena_alloc_a(); if (!a) goto done; /* 34f1:04a3 */
            copy 22 bytes; a.flags = 1800h | (g.flags & 0FFh);
            a[+1Dh] = 1641:0157(a.shape);           /* APP kind */
            if (BYTE[g + 12h + m] == 0FFh) {        /* destroyed member */
                a.flags |= 40h; a.shape = 1641:0142(a.shape);          /* wreck shape */
                if (a.shape == 0FFFFh) { arena_free_a(); continue; }   /* 34f1:053a */
            }
            a[+16h] = g (far); a[+1Ah] = m; a[+1Ch] = 0FFh;
        } else {                                    /* flat member -> B record */
            a = arena_alloc_b(); if (!a) goto done; /* 34f1:04f0 */
            copy 22 bytes; a.flags = 1800h | (g.flags & 0FFh);
        }
        DS:369C = a;
        if (lnear(E, a+4, 1300000) && gather_test(a)) { if (DS:36D8 >= lim) goto done; }
        else if (layer == 0) arena_free_a(); else arena_free_b();     /* 053a / 0548 */
    }
}
while (i < DS:43D6) {                               /* long (tiled) groups */
    g = P[i++]; d = ldist3(E, g+4);
    if (d > 2000000) continue;
    if (!(log_key(macro_radius(g)) + (S << 8) > log_key(d))) continue;
    M = &macro_tab[g.type & 3FFFh]; B = g+4 (pos); X = g+1Ch (extent);
    bx = M.box.x, by = M.box.y;
    t = (by > bx) ? (bx>>2) + (bx>>3) + by : (by>>2) + (by>>3) + bx;   /* i32 sar */
    ks = (i32)(i16)(log_key(t) << 1);
    for (ty = B.y - g[+14h](i32); ty < B.y + X.y; ty += by)
      for (tx = B.x - g[+10h](i32); tx < B.x + X.x; tx += bx) {
        ax = labs(E.x - tx); ay = labs(E.y - ty);
        h = (ay > ax) ? (ax>>2) + (ax>>3) + ay : (ay>>2) + (ay>>3) + ax;
        w = (E.z > h) ? (h>>2) + (h>>3) + E.z : (E.z>>2) + (E.z>>3) + h;
        if ((i32)S < (i32)(i16)log_key(w) - ks) continue;     /* see note */
        for (m = 0; m < M.n; m++) {
            q = M.members[m].pos + (tx, ty, 0);
            if (q.x < B.x || B.x + X.x < q.x || q.y < B.y || B.y + X.y < q.y) continue;
            a = arena_alloc_b(); if (!a) goto done;
            copy 22 bytes; a.flags = 1800h | (g.flags & 0FFh); a.pos = q;
            DS:369C = a;
            if (lnear(E, q, 2000000) && gather_test(a)) { if (DS:36D8 >= lim) goto done; }
            else arena_free_b();
        }
      }
}
done:
if (DS:36DA) {                                      /* order the ground layer once */
    tree_build(DS:36DA, DS:36D4, T);                /* 34bf:0084, T = 0x6A2-byte stack local */
    for (j < DS:36DA) T[j].ptr = *(far*)T[j].ptr;   /* entry -> object pointer */
    DS:36A4 = DS:36D4; tree_flatten(T);             /* 33d1:0e6a */
}
if (DS:36DC) memmove(DS:3694, DS:3698, 8·DS:36DC);  /* 1d32:67fb: statics behind the ground layer */
```

`radius_w(id)` = `271b:0539` (radius << shift, i32). Note on the tile test: `S` is compared raw
(7), not `S << 8` as in the other size tests, so a tile is skipped only when `log_key(w) −
2·log_key(t) > 7` — never for the shipped macro sizes (box ≈ 10^5–10^6: every tile passes).
Keep literally. Member z is not offset in tiles; members are not rotated there.

### 3.4 `33d1:02eb` `gather_test()` (near, object `DS:369C`; `33d1:02ea` = `inc bp` entry) → u8

```
d = ldist3(E, obj+4);  c = class(obj.shape & 1FFFh);          /* 35d6:020c */
e = DS:36E0 + 85·c;                                            /* no bound check on c */
if (e[0] == 0) vis = 1;
else {
    if (e[4]) return 0;                                        /* class disabled at this detail */
    if ((i16)WORD[e+0Dh] < 3FFh) {                             /* density thinning */
        DS:5822 = xor8(obj+4, 12 bytes) + 13;                  /* 14b8:0057 */
        if ((WORD[3A0D:(DS:5822 & 0FFh)·2] & 3FFh) > WORD[e+0Dh]) return 0;
    }
    if (e[3])                                                  /* size mode */
        vis = (i16)(log_key(radius_w) + (S << 8) - log_key(d)) > (i16)WORD[e+5];
    else {                                                     /* range mode */
        Rw = radius_w; lim = DS:36E2[c];
        if (Rw >= 5000000 && lim < DS:36A0) lim = DS:36A0;     /* 250 000 */
        vis = (i32)(d - Rw) < lim;
    }
}
if (vis) {
    l = layer(obj.shape & 1FFFh);                              /* 35d6:01e2 = header byte 2 */
    if (l) { DS:36DA++; *DS:3694 = {obj, (i32)l}; DS:3694 += 8; }
    else   { DS:36DC++; DS:3698 -= 8; *DS:3698 = {obj, d}; }
    DS:36D8++;
}
return vis;
```

`log_key(Rw) + S·256 − log_key(d)` is `log2(Rw·2^S/d)` in 8.8 format: the size test keeps an
object while its projected radius in pixels exceeds `2^(thr/256)`. The table `3A0D:0000` (256
words) is filled at run time by `14b8:000d` (sim_flow RNG) — deterministic per position.
**Shape header byte 2 (shapes.md "sub-class") is the ground-layer priority**: non-zero for flat
ground objects (islands, reefs, pads, runways, roads, rivers), which are drawn first in descending
byte order, before and without the distance sort.

### 3.5 `33d1:00f2` `list_add(far obj *o, i32 key)` → int and `33d1:0140` `scene_add_dynamic(far obj *o)` → u8

`00f2`: `if (DS:36D8 >= DS:367C) return 0; if (o.flags & 100h) { o.flags &= ~100h; return 0; }
DS:36D4[DS:36D8++] = {o, key}; return 1;`

`0140`: `if (o.flags & 100h) { clear; return 0; } if (o.flags & 1000h) return 0;` then the class test
of §3.4 with `d = ldist3(eye(DS:3682), o+4)` and `c = class(o[+2] & 1FFFh)` (same order: `e[0]==0` →
visible; `e[4]` → 0; density; size or range test); if visible:
`l = layer(o[+2] & 1FFFh); return list_add(o, l ? l : d);` (callers `5440:03aa`, `04c4:0b53`).

### 3.6 `34bf:0006` `scene_draw()` (Verified)

```
for (i = 0; i < DS:36DA; i++) draw_entry(DS:36D4[i].obj);       /* 33b4:0004, list order */
if (DS:36D0) DS:36D0();                                          /* 675d:0000 ground dots */
n = DS:36D8 - DS:36DA;
if (n) { tree_build(n, &DS:36D4[DS:36DA], T); tree_draw(T); }   /* T = 0x644 bytes on stack */
```

`T` holds **200** nodes (1604 bytes) but `tree_build` accepts up to 256: with fewer than 50
ground-layer entries and a full list (250) the nodes overwrite the caller's frame. `/* PORT: */`
size the node array 256.

### 3.7 `34bf:0084` `tree_build(int n, far entry *list, node *T)` (Verified)

```
if (n <= 0) return; if (n > 256) n = 256;
T[0] = {&list[0], 0, 0, 0, 0};
for (i = 1; i < n; i++) {
    T[i] = {&list[i], 0, 0, 0, 0};  key = list[i].key;  cur = 0;
    do {
        nd = &T[cur];  diff = key - nd.ptr->key;               /* i32 */
        tn = list[i].obj.flags & 1Fh;  tc = nd.ptr->obj.flags & 1Fh;
        if (tn == tc) nearer = diff < 0;
        else if (labs(diff) >= 10000) nearer = diff < 0;
        else if ((i32)shape_radius(new.obj[+2]) + shape_radius(cur.obj[+2]) < labs(diff))
             nearer = diff < 0;                                /* 35d6:018a, unshifted radii */
        else nearer = sort_compare(&{tn, tc, diff, new.obj, cur.obj});   /* 465c:0589 */
        if (nearer) { if (nd.flags & 2) cur = nd.nearer;
                      else { nd.nearer = i; nd.flags |= 2; T[i].parent = cur; T[i].flags |= 1; cur = -1; } }
        else        { if (nd.flags & 4) cur = nd.farther;
                      else { nd.farther = i; nd.flags |= 4; T[i].parent = cur; T[i].flags |= 1; cur = -1; } }
    } while (cur >= 0);
}
```

Ties (`diff == 0`, same type) go to the farther side: of two equal keys the later-inserted entry is
drawn first. Types are compared on the objects' `flags & 1Fh`.

### 3.8 `34bf:02a4` `tree_draw(node *T)` (near; `34bf:02a3` = `inc bp` entry) and `33d1:0e6a` `tree_flatten(node *T)`

Iterative in-order walk from node 0:
```
cur = 0;
while (cur >= 0) {
    nd = &T[cur]; f = nd.flags;
    if (f & 4)      { cur = nd.farther; nd.flags &= ~4; }      /* consumes the tree */
    else if (f & 8) cur = (f & 1) ? nd.parent : -1;
    else { VISIT(nd); nd.flags |= 8;
           cur = (f & 2) ? nd.nearer : (f & 1) ? nd.parent : -1; }
}
```
`34bf:02a4`: `VISIT` = `draw_entry(nd.ptr->obj)` (`33b4:0004`). `33d1:0e6a` (`33d1:0e69` = `inc
bp`): `VISIT` = `*(far u32*)DS:36A4 = nd.ptr; DS:36A4 += 8` (writes only the object pointers; the
key dwords of the ground entries keep stale values, unused). Result: **farther subtree, node,
nearer subtree** = descending key = far to near (painter's order); ground layer by descending
priority byte.

### 3.9 `465c:0589` `sort_compare(cmp *c)` → int (1 = new is nearer) (Verified)

`c`: `+0 u16 tn, +2 u16 tc, +4 i32 diff, +8 far new, +0C far cur`. `P(o)` = copy of `o+4`; `eye` =
`WORD[DS:437E][+2] + 2`; `seg_hits(a, b, box, p, o2)` = `6ac7:0120(a, eye, box = o[+20h], p, o[+24h])`
(sim_world: segment a→eye against the object's hit box). `code = tn << 5 | tc`:

| Case | Result |
|---|---|
| `code == 6Ch or 6Eh` (new 3, cur 0Ch/0Eh) | `cur.z == 0` → 1; `cur.z == 1` → 0; else `6ac7:0120(P(cur), eye, new[+20h], P(new), new[+24h])` (returned as is) |
| `code == 183h or 1C3h` (new 0Ch/0Eh, cur 3) | `new.z == 0` → 0; `new.z == 1` → 1; else `!6ac7:0120(P(new), eye, cur[+20h], P(cur), cur[+24h])` |
| `tn` 4 or 0Dh | eye z > 1000 → 0; else `!6ac7:0120(P(cur), eye, new[+20h], P(new), new[+24h])` |
| `tn` 0Bh | 0 |
| `tn` 0Ch or 0Eh (cur not 3) | 1 |
| else, `tc` 4 or 0Dh | eye z > 1000 → 1; else `!6ac7:0120(P(new), eye, cur[+20h], P(cur), cur[+24h])` |
| else, `tc` 0Bh, 0Ch or 0Eh | 0 |
| otherwise | `diff < 0` |

(`z` = the i32 at `+0Ch`. Jump tables `465c:0802`/`07ec`, 11 entries for types 4..0Eh.) So low
objects on the sea (ships, type 4/0Dh) are ordered by line of sight when the eye is below 1000
units, shadows (0Bh) always behind, 0Ch/0Eh (effects, **Likely** also wakes) in front of all but
aircraft.

### 3.10 `33b4:0004` `draw_entry(far obj)`, `33b4:002a` `draw_default(far obj)`, `33b4:010e` `build_draw_rec(far obj)` → `DS:3666`

`0004`: `if (DS:36CC) DS:36CC(o); else draw_default(o);`. `010e`: zero `DS:3666` (11 words), fill as
in §1.2, return `3666h`. `002a`: `if (o.flags & 100h) { clear; return; }` then the same record on the
stack and `ts_draw(&rec)` (state pointer 0; not used in AP because `DS:36CC` is always set).

-----------------------------------------------------------------------------------------------

## 4. Visibility culling, effects and special draws

### 4.1 `05a9` effect pool (`DS:55F1` = pool of 100 × 48 bytes, §5.3)

| Function | Behaviour |
|---|---|
| `0005` `effects_init()` | `DS:55F1 = pool_new_far(100, 48)`; `DS:55E5..55F0` (view position) = `22222222h` ×3, copied to `DS:55D9..55E4`; `DS:55D8 = 0` |
| `0043` `effects_free()` | `pool_destroy_far(DS:55F1)`; `DS:55F1 = 0` |
| `025f` `effect_in_range(far e)` → 1/0 | `r = (u32)e[+1Ch] << 10`; 1 if `ldist2(e+4, DS:55E5) < r` and `ldist3(e+4, DS:55E5) < r` (unsigned) |
| `005a` `effect_spawn(near tmpl)` → far | if `effect_in_range(tmpl)` and `pool_alloc(DS:55F1)`: copy 48 bytes, `+1Fh = 0`, return it; else 0 (12 callers: sim_world weapon/impact code, `1560:055b`, `1a8b:004c`, `490a:0509`, `655d`) |
| `00ad` `effects_update_view(i32 *eye)` | `DS:55E5 = *eye`; if `ldist3(DS:55E5, DS:55D9) > 3000` → `effects_recull()` (**`DS:55D9` is never updated**, so this runs every frame); if `DS:55D8 == 0`: free every record with `(+1Fh & 1) == 0` (collect up to 100 far pointers on the stack, then `effects_free_list`); `DS:55D8 = 0` |
| `014c` `effects_step()` (sim step `5440:1317`) | for each record: if `+18h` (far callback) ≠ 0 and `z (+0Ch) >= 0` and `callback(e) != 0` → `+1Fh |= 1`; else collect it; free the collected; `DS:55D8 = 1` |
| `01d1` `effects_recull()` | for each: `flags &= ~2000h`; if `!effect_in_range(e)`: `flags = 100h` (**the whole word**, type lost). Frees nothing (count 0) |
| `0233` `effects_free_list(far *list, n)` | `pool_free(DS:55F1, list[i])` |

Effects are drawn through the list (`5440:03aa` → `scene_add_dynamic`), type 0Eh → `effect_draw`.

### 4.2 `1560:055b` `spawn_ground_fires()` and `1560:06e9` `effect_draw(far e)`

```
T = 48-byte template, zero; T.flags = 080Eh; T[+1Ch] = 80h; T[+1Eh] = 0;
for (i = DS:36DA; i < DS:36D8; i++) {          /* the non-ground part of this frame's list */
    o = DS:36D4[i].obj;
    if (!(o.flags & 1000h)) continue;           /* only expanded 3D members (A records) */
    g = o[+16h]; if (BYTE[g + o[+1Ah] + 12h] != 0FFh) continue;   /* member not destroyed */
    if (o[+1Dh] >= 13h) continue;
    if (!(o.flags & 0C0h)) {
        o.flags |= 80h; w = 1641:0142(o.shape);
        if (w == 0FFFFh) { o.flags |= 2000h; continue; }
        o.shape = w;
    }
    f = DS:5A82 + 8·o[+1Dh];                     /* GDAMAGE.DAT, 19 × 8 bytes (655d:0322) */
    if (WORD[f] == 0) continue;
    T.shape = DS:474D + (BYTE[f+4] ? 1Fh : 1Dh) + ((o.flags & 80h) ? 1 : 0);
    T.pos = o.pos;
    e = effect_spawn(&T); if (!e) continue;
    e[+2Ah] = WORD[f];                           /* fire radius: 1200, 2200, 5000 */
    o[+1Ch]++;                                   /* u8, starts at FFh */
    if (o[+1Ch] > shape_nvariants(e.shape, 0) - 1) {        /* 271b:043d, signed compare */
        o[+1Ch] = 0;
        if (o.flags & 80h) { o.flags ^= 0C0h; e.shape--; }  /* fire -> smoke */
    }
    e[+16h] = o[+1Ch];
}
```
The spawned records have no callback: they live one frame (freed by the next `effects_step`).
`DS:474D` = first id of the common effect shapes (sim_world).

`06e9` (Verified): `st = (u8)e[+16h]; R0 = shape_radius(e[+2]) (35d6:018a); 271b:04f5(e[+2], e[+2Ah])`
(sets the header radius directly, **the `35d6` cache is not updated**); `rec = 22 bytes from e+2`
(shape, pos, angles); `rec.state = &st; ts_draw(&rec); 271b:04f5(e[+2], R0)`.

### 4.3 `2466` far-aircraft dots

* `2466:000a` `proxies_alloc()` (from `4e0d:038e`): `DS:5EDE = mark_alloc(DS:4776 · 18)`.
  `5440:03aa` indexes it by the number of dot aircraft in `DS:00BC` (no bound check against
  `DS:4776`).
* `2466:0023` `far_dot_draw(far p)` (near-called via far frame): `P = p+4`; `C = CS:0A13` (eye);
  `M = CS:09B6` (19 bytes); `644a:089f(&rc)` → `rc = {x, y, w, h}` (sim_flow cockpit window);
  `D = lsub(P, C)`; `e = lvec_rotate(D, M)` (`277a:4cb3`); if `focal (CS:0A47) > e.y` return;
  `pt_project(e, s)` (`277a:3010`), `pt_add_centre(s)` (`2fee`); if `rc.x < s.x < rc.x + rc.w` and
  `rc.y < s.y < rc.y + rc.h` (strict, i32): `DS:26C3 = 1; 1d32:6a5b(s.x, s.y, p[+10h])` (pixel,
  video).

### 4.4 `0802` cloud-layer and range culling

* `0802:000c` `overcast()` → `DS:4512 != 0 && DS:42C9 != 0` (callers `04c4:07a2`, `17ce:0013`,
  `5440:018c`, and below).
* `0802:0026` `overcast_split()` → u8 (Verified): `z = eye.z`; `own = 1c30:09a9()` (object carrying
  the camera, sim_flow); `s = sgn(z − 16000)`; `if (!overcast()) return 0;` for each `o` in
  `DS:475D[0..DS:4778)` (near pointers) except `own`, each in pool `DS:00E6` and in pool `DS:55F1`:
  `if (sgn(o.z − 16000) != s) o.flags |= 100h`; return `z > 16000`. (`sgn` ∈ {−1, 0, 1}: an object
  exactly at 16000 is hidden unless the eye is too.) The overcast deck is at **z = 16000**; above it
  `5440:03aa` empties the static lists.
* `0802:0173` `visibility_cull()` (Verified): `E = eye`; `if (overcast()) return;`
  `c = 490a:03fb(E)` (cloud containing the eye, sim_world). If `c`: `DS:5BE5 = 1; DS:5600 = c[+4]
  (i32); DS:55FC = c[+8]`; for each `o` in `DS:475D[0..DS:4778)` without `100h`: if
  `ldist3(E, o+4) > 3000` → `o.flags |= 100h`. Else `DS:5BE5 = 0`; for each `o` in
  `DS:475B[0..DS:4776)` without `100h`: `d = ldist3(o+4, E)`; `if (d > 200000 || 490a:043e(o+4, E))
  o.flags |= 100h` (line of sight through clouds).

### 4.5 `59f9` class registry (Verified; used by sim code only, **Likely** better owned by sim_world)

`59f9:0000` (BX = class record): `rec[+6] |= 8000h; DS:47F6[DS:47F2++] = BX; DS:47F4 = max(DS:47F4,
rec[+4])` (signed). `59f9:0026` (AX = n, BX = array of record pointers): `0000` for each.
`59f9:004e` (BX = object): `obj[+0Ah] = mark_alloc(DS:47F4)` (called by `465c:005a` for every sim
object). `59f9:0068`: `DS:488C = 0`. The records (20 bytes, e.g. `DS:16B5..`, registered by
`14b8:0000` ×23, `10bf:0005`, `655d:0322`) are AI/behaviour descriptors (`+4` = per-object data
size).

-----------------------------------------------------------------------------------------------

## 5. Memory helpers

### 5.1 `34f1` macros.c — macro table and per-frame member arena

| Function | Behaviour |
|---|---|
| `000b` `macros_alloc(n, m)` (`62d2:0a0d`: 31, 500) | `DS:36AE = fnew(18n)` (fatal on 0, macros.c line 64h); `DS:36AC = n`; `DS:36A8 = fnew(22m)` (fatal, line 68h); `DS:710E = 22m + 1` |
| `00a8` `macros_free_all()` | `ffree` `36AE`, `36A8`, zero them |
| `00e9` `macros_unload()` | `ffree` every entry's members; `DS:36B2 = 0`; `_fmemset(36AE, 0, 18·36AC)` |
| `0310` `macros_load(name)` | see §6.2 |
| `0144` `arena_reset()` | `DS:710C = 0; DS:710A = DS:710E` |
| `04a3` `arena_alloc_a()` → far | `t = 710C + 30; if (t > 710A) return 0` (unsigned); `p = 36A8 + 710C; 710C = t; _fmemset(p, 0, 30)` |
| `04f0` `arena_alloc_b()` → far | `t = 710A − 40; if (t < 710C) return 0`; `710A = t; p = 36A8 + t; _fmemset(p, 0, 40)` — the first B record ends at offset `22m + 1`, **one byte past** the 22m-byte block |
| `053a` / `0548` | `710C −= 30` / `710A += 40` (release the last A / B record) |
| `02f5` `macro_entry(i)` → far | `36AE + 18·(i & 1FFFh)` (no callers) |
| `0155` `macro_expand(far g)` → n | `M = 36AE + 18·(g.type & 3FFFh)`; copies the `M.n` members to the static buffer `3B05:0000` (704 bytes = **32 members max**, no check); if `g[+10h]` (heading) ≠ 0: each copy `lrot_z(&copy.pos, heading)` (`367b:0006`), `copy[+14h] = heading` (replaced, not added); then `copy.x += g.x; copy.y += g.y` (z not added); returns `M.n` |
| `0259` `macro_radius(far g)` → u32 | `v` = `g+1Ch` (extent) if `(type & C000h) == C000h`, `M.box` if `== 8000h`, else return 0; `ldist3(DS:36B4 (0), v)` — the length of the full box/extent vector |

### 5.2 `3591` init.c — FLT class arrays

`3591:0001(unused, n)` (`62d2:0a0d`: n = 20): `DS:36E0 = nnew(85n)` zeroed, `DS:36E2 = nnew(4n)`
zeroed (fatal on failure, lines 22h/27h), `DS:36DE = n`. `3591:00dc` frees both.

### 5.3 `3546` pool.c — fixed-size record pools (Verified)

Header (14 bytes, near `nnew(0Eh)`): `+00 u16 nfree, +02 u16 nused, +04 u16 size, +06 u16 segment,
+08 u16 base offset, +0A u16 free head, +0C u16 used head` (offsets of nodes, −1 = none). Node =
`{u16 next, u16 prev}` + record; element pointer = node + 4; nodes at `base + i·(size+4)`.

| Function | Behaviour |
|---|---|
| `0006` `pool_new_far(count, size)` → hdr | `size += size & 1`; hdr = `nnew(14)`; block = `fnew((u16)(count·(size+4)))`; either 0 → 0; `pool_init(hdr, block, count, size)` |
| `007e` `pool_new_near(count, size)` | same with a near block (`nnew`), segment = DS; frees hdr if the block fails |
| `0118` `pool_init(hdr, off, seg, count, size)` | `nfree = count, nused = 0, size, seg, base = free = off, used = −1`; links nodes in order (`prev` of the first = −1, `next` of the last = −1) |
| `019d` / `01d4` | destroy far (`ffree(seg:base)`, free hdr) / near |
| `021a` `pool_alloc(hdr)` → far | 0 if `nfree == 0`; take the free head, `nfree--, nused++`; new free head's `prev = −1`; push the node at the head of the used list; return `seg:node+4` |
| `02bb` | wrapper of `021a` (no callers) |
| `02ca` `pool_alloc_zero(hdr)` | `021a` + `1d32:690e(p, 0, (i32)size)` |
| `0304` `pool_alloc_zero_near(hdr)` | `021a` + zero `size` bytes at DS:offset |
| `0333` `pool_free(hdr, off, seg)` | `nused--, nfree++`; if `seg ≠ hdr.seg`: `off += (seg − hdr.seg)·16`; unlink from the used list, push on the free head |
| `03f2` `pool_free_near(hdr, p)` | `0333(hdr, p, hdr.seg)` |
| `040a` `pool_next(hdr, far p)` → far | `p == 0` → first used element or 0; else the next used element (`seg` = hdr.seg) or 0 |
| `045f` | the same, near |
| `0498` / `04a4` | `nfree` / `nused` |

Iteration order is most-recently-allocated first. Pools: effects `DS:55F1`, ordnance `DS:00E6`,
aircraft `DS:3B05` (`0x107` bytes), ships `DS:3B03` (`0x88`), `488e`, `5a75`.

-----------------------------------------------------------------------------------------------

## 6. World loading

### 6.1 `62d2:049e` `area_load(char *name, i32 (*tpos)[3], u16 *tcount, int n)` → far (Verified)

Called by `56ac:0236` (snario, sim_world) with the area name (`"AW1"` …), a list of `n` target
positions and an output count array. Sequence:

```
tn = "target.XX" (copy of DS:0C58); zero tcount[0..n);
wd3 = 55a4:0000(name, "wd3");                         /* name + extension */
W = whd_load(wd3);                                    /* 35ad:000c, u16[256] */
total = (u16)sum_i16(W, 256);                         /* 277a:3eed */
groups = W[FEh] + W[FFh];  statics = total - groups;
DS:5130 = statics;  DS:512E = statics + W[FEh];
tn[7] = name[2]; tn[8] = (name[3] == '.') ? 0 : name[3];   /* "target.1" / "target.11" */
targets_load(tn);                                     /* 628f:0144 */
dead = mbl_count_dead(wd3);                           /* 62d2:0a2e */
groups -= dead; total -= dead; DS:512E -= dead;
DS:5138 = fnew(24·statics); DS:512A = fnew(42·groups); DS:06F3 = fnew(4·total);
DS:36D4 = fnew(2000);                                 /* draw list, 250 entries */
DS:36D8 = DS:43D6 = DS:5136 = 0;  DS:5132 = DS:5134 = −1;
DS:0C34..0C3F = 7FFFFFFFh ×3 (min);  DS:0C40..0C4B = 80000000h ×3 (max);
DS:7110 = 3de9:0034 (= wd3_record 62d2:0199);
DS:5126 = L (10 × 6-byte stack table {far group, u16 count}, zeroed); DS:5124 = tpos; DS:5122 = n;
DS:5140 = 0;
wd3_load(wd3);                                        /* 35ad:00f8 */
for (i = DS:5130; i < DS:512E; i++)                   /* short groups without a target state */
    if ((P[i].flags & 1Fh) == 0) {                    /* inherit the nearest stated group's type */
        best = 7FFFFFFFh; t = 0;
        for (j = DS:5130; j < DS:512E; j++) if (P[j].flags & 1Fh) {
            d = ldist2(P[i]+4, P[j]+4); if (d < best) { best = d; t = P[j].flags & 1Fh; } }
        P[i].flags |= t;
    }
targets_free();                                       /* 628f:010e */
if (DS:5132 == −1) DS:5132 = DS:5130;
s = 0; for (k < n) { tcount[k] = L[k].count; s += L[k].count; }
DS:5146 = DS:5142 = DS:513C = 0;  DS:5140 = s;
if (s) { DS:5146 = fnew(22s); DS:513C = fnew(4s); DS:5142 = fnew(6s);
    for (k < n) if (L[k].count) {                     /* member copies for mission targets */
        m = macro_expand(L[k].group);
        for (j = 0; j < m && layer(buf[j].shape) == 0; j++) {
            513C[p] = &5146[p]; copy buf[j] (22 bytes) to 5146[p]; 5142[p] = {L[k].group, j}; p++; } } }
DS:367C = 250; DS:367E = 100;
whd_free();                                           /* 35ad:00ce */
v = max − min (lsub); m = max(v.x, v.y);
DS:0C2E = floor_log2_or_0(m / 62) + 1;                /* 62d2:0000 */
DS:0C30 = 1 << (DS:0C2E − 1); DS:0C4C..0C57 = min; t = 1 << DS:0C2E; DS:0C4C −= t; DS:0C50 −= t;
flt_load(55a4:0000(name, "flt")); flt_set_level(80h);  /* 333b:000a, 333b:0158 */
DS:36C4 = 7500;
return DS:5146;
```

`DS:06F3` partition after loading: `[0, 5134)` statics before the first class-1 (island) object;
`[5134, 5132)` from the first island up to the first object with layer byte 0; `[5132, 5130)` the
remaining statics; `[5130, 512E)` short macro groups; `[512E, 43D6)` long groups. (The OB0 records
are thus expected ordered: flat non-island objects, islands and other flat objects, then 3D
objects; each range gets its own pre-test radius in §3.3.) `DS:0C2E..0C57` is a spatial grid used
by sim_world (`14e0`); `DS:5140..5148` (member copies of mission targets) are sim_world data.
Note the `m/62` division (`idiv` by 3Eh) and that `62d2:0000` loops forever for a negative value
(cannot happen).

* `62d2:0000` `floor_log2_or_0(i32 v)`: `n = 0; while ((v >>= 1) != 0) n++; return n;` (sar).
* `62d2:0199` `wd3_record(rec *r)` → int (the `DS:7110` handler): see §6.3.
* `62d2:0133` `make_instance(far dst, rec *r)` → dst: §1.3.
* `62d2:001d` `make_group(far dst, rec *r)` → dst or 0: §1.3 / §6.3.
* `62d2:0a2e` `mbl_count_dead(name)`: opens the volume entry, `WD2:MBL:` → `u16 n`; per record reads
  **16 + 6 bytes regardless of the form** (the AW3 40-byte record desynchronises the rest of the
  count) and counts records with `target_state(rec.pos, DS:4787) == 10`; closes; returns the count.
* `62d2:044a` `groups_reset()` (sim init `4e0d:03e9`): `_fmemset(P[i] + 12h, 0, 24)` for `i` in
  `[5130, 512E)` — clears the per-member damage bytes.
* `62d2:0969` `area_free()` (`56ac:07b4`): `ffree` 5138, 512A, 06F3, 36D4, 5142, 5146, 513C; zero
  the pointers and `36D8, 43D6, 5128, 5136`.
* `62d2:0a0d` `world_tables_init()` (`4e0d:0000`): `3591:0001(2BCh, 20)`; `macros_alloc(31, 500)`.

### 6.2 `35ad` obwload.c, `34f1:0310` macro file

* `35ad:000c` `whd_load(name)` → near: if `DS:7114` already set, return it. Else `buf = nnew(200h)`;
  open (fatal, obwload.c line 2Eh); find `"WD2:WHD:"`; read `u8 k`; `vol_fseek(fp, 2k, SEEK_CUR)`;
  read 256 words into `buf`; close; `DS:7114 = buf`.
* `35ad:00ce` `whd_free()`: `nfree(DS:7114)`, `DS:7114 = 0`.
* `35ad:00f8` `wd3_load(name)`: open (fatal, line 5Bh); for `d = '0'..'5'`: chunk `"WD2:OBd:"`
  (`DS:36ED`, byte 6 patched): `n = chunk_size / 26` (signed); read 26-byte records while `n--` and
  `vol_fread` returns non-zero, calling `DS:7110(&rec)`; then `"WD2:MBL:"`: `u16 n`; per record read
  16 bytes, then 24 bytes if `(type & C000h) == C000h` else 6, call `DS:7110(&rec)`; close.
* `34f1:0310` `macros_load(name)`: `fp = vol_fopen(name, "rb")` (fatal, line 1A8h); read `u8`, `u16
  count`; `e = DS:36AE`; `while (count-- && DS:36B2++ < DS:36AC)`: read `name[8]`, `u16 n`, `i32
  box[3]`; `e.n = n; e.box = box; e.members = fnew(22n)` (fatal, line 1C3h); read `n` 22-byte
  members, keeping those with `shape != FFFFh` (else `e.n--`); `e += 18`. Close. (world.md §3.)

### 6.3 `62d2:0199` `wd3_record(rec *r)` → 1 = kept, 0 = dropped (Verified)

```
if (r.type & 8000h) {                                  /* MBL group */
    g = make_group(DS:512A + 42·DS:5128++, r);
    if (!g) { DS:5128--; return 0; }
    if ((r.type & C000h) == 8000h) {
        link = 0;
        for (si = 0; si < DS:5122; si++)
            if (ldist3(r+4, DS:5124 + 12·si) < 10) { link = 1; ti = si; DS:5126[si].group = g; break; }
        n = macro_expand(g);
        for (m = 0; m < n; m++) {
            if (link && layer(buf[m].shape) && class(buf[m].shape)) { DS:5126[ti].count = m; link = 0; }
            R = (i16)radius_w(buf[m].shape);          /* truncated to 16 bits */
            lmin(DS:0C34, buf[m].pos + (−R));  lmax(DS:0C40, buf[m].pos + R);   /* 277a:52c6/517a/51ce */
        }
        if (link && m == n) DS:5126[ti].count = n;
    }
} else {                                               /* OBx static object */
    g = make_instance(DS:5138 + 24·DS:5136++, r);
    if (DS:5134 == −1 && class(r.shape) == 1) DS:5134 = DS:43D6;
    if (DS:5132 == −1 && layer(r.shape) == 0) DS:5132 = DS:43D6;
    R = (i16)radius_w(g.shape);  lmin/lmax of r.pos ± R;
}
DS:06F3[DS:43D6++] = g;  return 1;
```

`make_group` for the short form: `k = target_state(r+4, DS:4787)` (`628f:031f`, date `DS:4787`);
state by `k` (jump table `62d2:011b`): −1 → 0; 0 → 10h; 1–5 → 2; 6–9 → 11h; **10 → group not
created** (returns 0); other → 11h. Record as §1.3.

### 6.4 `.FLT` detail table (`333b`, `33a1`) — settles world.md §4

`333b:000a` `flt_load(name)`: `fp = vol_fopen(name, "rb")` (no error: missing file → nothing);
`n = ldiv_sat(vol_filelength(fp), 24)`; read `n` records of 24 bytes (`r`, words `r0..r11` at
`+0..+16h`), `flt_record(&r)`; close; then `dda_init(DS:70FA, 0, 0, 80h, 100h)` (a global
interpolator 0→0 … 128→256 used by `4b9f` control.c, sim_flow).

`333b:0098` `flt_record(r)`: `e = DS:36E0 + 85·r0` (no bound check; r0 ≤ 12h in the data):
`e[0] = 1; WORD[e+1] = r1; e[3] = BYTE[r+4];` if `e[3]`: `dda_init(e+0Fh, 0, r3, 0FFh, r4)`; else
`dda_init(e+1Dh, 0, r5, 0FFh, r6)`, `dda_init(e+2Bh, 0, r7, 0FFh, r8)`, `dda_init(e+39h, 0, r9, 0FFh,
r10)`; always `dda_init(e+47h, 0, r11, 0FFh, 3FFh)`.

`333b:0158` `flt_set_level(u16 lv)` (at load with 80h; the detail slider `4b9f:00d0`): `a =
clamp(lv, 0, 255)`; `b = clamp((i16)((lv − 128) << 1), 0, 255)` (`35ff:0009`); for each class with
`e[0]`: `e[4] = ((i16)WORD[e+1] > a)`; if `e[3]`: `WORD[e+5] = dda_eval(e+0Fh, a)`; else `WORD[e+7]
= dda_eval(e+1Dh, a)`, `WORD[e+9] = dda_eval(e+2Bh, a)`, `WORD[e+0Bh] = dda_eval(e+39h, a)`; always
`WORD[e+0Dh] = dda_eval(e+47h, b)`. `333b:0143(c)` → `e[0]`. `333b:024c`/`0290` = `dda_init`/`dda_eval`
on a 14-byte copy (copied in and out).

**85-byte class record** `DS:36E0 + 85·class`:

| Off | Type | Meaning |
|---|---|---|
| 00 | u8 | present |
| 01 | u16 | detail threshold (FLT `+02`): class off while threshold > level (`0`, `55h`; `100h` = never shown) |
| 03 | u8 | mode (FLT `+04`): 1 = size test, 0 = range test |
| 04 | u8 | disabled at the current level |
| 05 | i16 | size threshold, 8.8 log2 pixels (FLT `+06` at level 0 → `+08` at 255) |
| 07 | i16 | range at z = 0, thousands of units (FLT `+0A` → `+0C`) |
| 09 | i16 | range at z ≥ 131 068 (FLT `+0E` → `+10`) |
| 0B | i16 | third range (FLT `+12` → `+14`; 0 in all files, unused) |
| 0D | i16 | density 0..3FFh (FLT `+16` at levels ≤ 128 → 3FFh at 255) |
| 0F/1D/2B/39/47 | dda | interpolators of `+05`, `+07`, `+09`, `+0B`, `+0D` |

AW1 examples: class 1 (islands) range mode `20→220` / `20→1620` (at level 128: 120 000 at sea
level, 823 000 high up); class 0 size mode `710→570` (≈ 2^2.5 = 5.7 px at level 128), density 0Ah
(1 %); classes 7/8 threshold 100h (never drawn); 9/0Ah (rivers, roads) and 11h/12h from level 55h.
The class is the shape header byte 1 (`35d6:020c`). Objects of the classes never listed in the file
(`e[0] == 0`) are always visible.

**`33a1` interpolator** (14 bytes: `+0 i16 x0, +2 i16 x1, +4 i16 x, +6 i32 y` (16.16, integer
part `+8`), `+0A i32 step`):
* `33a1:0055` `dda_init(s, xa, ya, xb, yb)`: swap the points if `xa > xb`; `x0 = x = xa, x1 = xb,
  y = ya << 16, step = yb << 16`; `33a1:00b3(&s.y, xb − xa)`; `dda_eval(s, xa)` (result dropped).
* `33a1:00b3` `dda_slope(i32 *y, i16 dx)` → 1/0: if `dx <= 0`: `step = 0`, `LOWORD(y) = 0`,
  return 0. Else `step = (step − y) / dx` (32-bit `idiv`, toward zero); `LOWORD(y) = (|step| &
  FFFF8000h) ? LOWORD(|step|) : 8000h`; return 1.
* `33a1:0008` `dda_eval(s, x)` → i16: clamp `x` to `[x0, x1]` (`x1 < x` → x1, else `x0 > x` → x0);
  step `s.x` toward `x` adding/subtracting `step` to `y`; return the integer part of `y`. Since
  each step is exact, `result = hi16((ya << 16 | frac0) + step·(x − xa))`.

### 6.5 `628f` wdata.c (`TARGET.n` in memory), `62ca`, `51ca` (Verified)

Target node (14 bytes, `mark_alloc`): `+00 next, +02 u16 id, +04 u16 head[5]` (one sorted list per
world.md list 0..4). Dated entry (8 bytes): `+00 next, +02 u16 date, +04` payload: list 0 → near
pointer to `P·12` bytes of points (`mark_alloc`), list 1 → two words, lists 2–4 → one word.
Globals: `DS:5120` first target, `DS:0C1E` current target, `DS:0C20` current entry, `DS:511E`
current list, `DS:0C1C` P, `DS:0C22` heap mark.

| Function | Behaviour |
|---|---|
| `0144` `targets_load(name)` | `DS:0C22 = mark_alloc(0)`; open (fatal, wdata.c line 153h); chunk `"INF:"` (result ignored) → `DS:0C1C = read_u16`; chunk `"DAT:"` (missing → return **without closing**); `u16 count`; per target `target_new(read_u16)`; for list `l` 0..4: `list_select(l)`; `u16 m`; per entry `entry_new(read_u16 date)` and its payload (`l == 0`: P × (x, y, z) `read_i32`, `point_set(i, &v)`; `l == 1`: two `read_u16` → `entry_set_long`; else `entry_set_word(read_u16)`); close; `0C1E = 0C20 = 0`. `TAG:` is not read |
| `00bb` `target_new(id)` | 14-byte node, heads 0, `DS:5120 = list_append(DS:5120, node)` (`62ca:004f`), current = node, `0C20 = 511E = 0` |
| `00aa` `list_select(l)` | `DS:511E = l; DS:0C20 = 0` |
| `0048` `entry_new(date)` | 8-byte node `{0, date}`; list 0: payload = `mark_alloc(12·P)`; `head[511E] = sorted_insert(head[511E], node)` (`62ca:0000`); `0C20 = node` |
| `0000` `point_set(i, v)` / `0024` / `0039` | copy 12 bytes to `payload + 12i` / `+4 = dword` / `+4 = word` |
| `010e` `targets_free()` | `mark_release(DS:0C22)`; zero `0C1E, 5120, 0C20, 0C1C` |
| `031f` `target_state(i32 pos[3], u16 date)` → i16 | for each target: `e = head[0]` (the **earliest** position only); if `lbox(e.points, pos, 10)` (all axes within 10): walk `head[3]` and return the value of the entry with `e.date <= date` and (`next == 0` or `next.date > date`); if none found continue with the next target; −1 if no target matches. (Settles world.md: **list 3 = state by date**; kinds: see §6.3) |

`62ca:0000` `sorted_insert(head, node)` → head: ascending `u16` at `+2`, after equal keys (stable);
`62ca:004f` `list_append(head, node)` → head (sets `node.next = 0` only for an empty list; relies on
zeroed allocations).

`51ca` file helpers (on the volume `FILE*`): `0000` `read_u16` = `getc | getc << 8` (no EOF check);
`0027` `read_i32` (4 × `getc`, little endian); `008d` `read_str` into the static `DS:4192` (256
bytes, no length check; returns `DS:4192`, or 0 at EOF / empty); `00ce` `write_u16`, `010c`
`write_u32`, `0180` `write_str` (+ NUL) → 1 ok / 0 on EOF error. `008d` is used by the VCR loader
`5b71:0118` (sim_flow); the writers have no callers.

### 6.6 Shape attributes `35d6` and ground data `GID:` (`3368`, `35a4`, `35d1`)

`35d6` (per global shape id, `n = DS:647E` shapes):

| Function | Behaviour |
|---|---|
| `00b8` `shape_cache_build()` (snario `56ac:0236`) | `fnew(n)` ×3 → `DS:3700` class, `3704` layer, `3708` shift; `fnew(2n)` → `370C` radius; `000c` |
| `000c` `shape_cache_fill()` → changed | for each id: header byte 1 / byte 2 / byte 3 / word `+0Ch` via `271b:02f5/037a/03bb/04b4`; returns 1 if any cached value differed; `DS:3710 = 1` |
| `0128` `shape_cache_free()` | `ffree` ×4, zero, `DS:3710 = 0` |
| `018a` / `01b8` / `01e2` / `020c` | AX = id → radius (word) / shift / layer / class; from `271b` when `DS:3710 == 0` |
| `0236` / `0267` | AX = id, DL / DX = value: set class / radius in the header (`271b:0336/04f5`) and the cache |

**`GID:` layout (settles shapes.md)** — `3368:0001` `gid_load(table)` (snario): chunk `"GID:"`
(`7039:020a`) → `DS:36C6` (far), then each non-zero dword of the pointer list gets the chunk's far
pointer added (32-bit add, normalised pointers like `DAT:`), `DS:36CA` = count. `3368:0057` frees
it. Entry (per shape, same order as `DAT:`):

| Off | Type | Field |
|---|---|---|
| 0 | i16 | half extent x (object units) |
| 2 | i16 | half extent y |
| 4 | u8 | flags: 1 = no region test (the first region covers the box: roofs), 2 = regions are 10-byte sloped records |
| 5 | u8 | number of regions (0 = no ground data) |
| 6 | u16 | offset of the regions (in the entry's segment) |

Region, 6 bytes: `+0 u16` edge list offset, `+2 i8` edge count, `+3 u8` slope scale, `+4 i16`
height; 10 bytes: the same plus `+6 u16` plane offset, `+8` 2 bytes (not read). Edge and plane:
`i8 nx, i8 ny, i16 px, i16 py` (outward normals, e.g. `is_1` polygons tile the island's box).

* `35d1:000e` `point_in_region(far region, i16 x, i16 y)` → 1/0: for each edge
  `(i8)nx·(i16)(x − px) + (i8)ny·(i16)(y − py)` (32-bit) `> 0` → 0; all ≤ 0 → 1 (0 edges → 0).
* `3368:02f4` `region_height(far region, x, y)` → i16: `v = gx·(x − px) + gy·(y − py)` (plane at
  `+6`; each term only when the i8 factor ≠ 0); `h = WORD[+4] + (v ? (i16)((v · BYTE[+3]) >> 12) : 0)`.
* `35a4:000f` `obj_angles(far o, i16 out[3])`: by `o.flags & 0E00h`: 800h and C00h → `o[+10h..+15h]`;
  200h → (0, 0, `o[+10h]`); 600h → (0, 0, `o[+0Ch]`); other kinds: **out not written** (differs from
  §1.2 for C00h).
* `3368:0169` `gid_probe(out, i32 p[3], far gid, far o)` → 1/0: `dx = (p.x − o.x) >> DS:7109`
  (i32 sar), `|dx| > half_x` → 0; same for y; `obj_angles(o, a)`; if `a[2]`: `vrot_z(&(dx,dy),
  −a[2])` (`3609:0001`); region: flags & 1 → the first, else the first with `point_in_region`
  (none → 0); `out+8 = far region, out+0 = o`; `out+4 (i32) = DS:7108 ? 0 : ((i32)h << DS:7109) +
  o.z` with `h` = flags & 2 ? `region_height` : region `+4`; return 1. (`DS:7109` = shift, `DS:7108` =
  layer byte of the shape; the uninitialised `a` of other placement kinds makes the rotation
  random there.)
* `3368:0069` `gid_ground(out[12], far i32 p[3], far objs[], n)` → 1/0: `out` zeroed; if no GID → 0;
  for each object with `gid[shape & 1FFFh].nregions ≠ 0`: set `DS:7109/7108`, `gid_probe` → return 1
  on the first hit. Callers: sim_world `14e0:06c0/07aa` (terrain/building height under a point).
* `3368:0128` region pointer by index (no callers).

The GID data are therefore **collision/ground-height volumes**: flat islands (height 0 regions =
land), sloped mountain faces, building roofs (flag 1). Terrain for the renderer is only the shapes.

-----------------------------------------------------------------------------------------------

## 7. Answers to world.md / shapes.md open questions

* WD3 angle order at `+10h/+12h/+14h`: pitch, roll, heading (§1.2).
* 40-byte `MBL:` record: tiled macro (position, i32 x/y phase at `+10h/+14h`, extent at `+1Ch`), §1.3,
  §3.3. `WHD:` `[FEh]` = short groups, `[FFh]` = long groups (the loader uses both).
* `.FLT` fields: §6.4 (threshold, mode, size threshold, ranges vs altitude, density).
* TARGET list 3 = state by date, looked up at each group position (±10 units, earliest position) to
  give the group's type bits / suppress destroyed groups (state 10). Lists 2 and 4: not read here.
* `GID:` layout and use: §6.6. Shape header byte 2: ground-layer draw priority (§3.4).

-----------------------------------------------------------------------------------------------

## Port notes

* `/* PORT: */` Keep the list capacities (250 / 150 static), the tree sort and its tie rule, the
  ground-layer order, the density hash and the 1/2-frame VCR hook call in `5440:0269`: all are
  visible (draw order, which objects appear) or affect determinism.
* `/* PORT: */` Size the sort node array for 256 entries (`34bf:0006` has room for 200; overflow is
  a stack smash in the original).
* `/* PORT: */` Bound the macro expansion buffer (`3B05:0000`, 32 members) and the FLT class index
  (20 records; class 1Fh stubs index past the table) — the data never exceed them, but a port
  should assert.
* The overlay far pointers `3d32:0070`, `3e07:0020`, `3e1d:002a`, `3de9:0034` (stubs) become plain
  function pointers to `5440:0269`, `675d:0000`, `6964:01a2`, `62d2:0199`.
* `62d2:0a2e` miscounts after a 40-byte MBL record (AW3): keep for the allocation sizes, or allocate
  generously (the counts only size arrays).

## Hand-offs

* **sim_flow**: `5440:018c`/`009c` (frame driver and view init, summarised §2.1); `4899:005c/0027`,
  `DS:00F8` (panel clip); `644a:089f` (per-view window, returns cy); `1c30:0780` (view mode
  `DS:5EBB`), `1c30:09a9` (object carrying the camera); `1c0f:0053` VCR hook called from the draw
  callback on every other object; `14b8:000d` fills the density table `3A0D:0000`; `4b9f:00d0`
  detail slider → `333b:0158` + `33d1:04dc`; `DS:70FA` interpolator; `51ca:008d` VCR string reader.
* **sim_world**: object types (`flags & 1Fh`), `+18h` kind byte (0 aircraft, 1 ship), `+16h`
  owner, `+1Ah` flags, `+20h/+24h` hit-box data read by the sort comparator through `6ac7:0120`;
  draws `0916:0273`, `05d6:01d3`, `04c4:0b53`; clouds/LOS `490a:03fb/043e/0509`; spotting
  `583c:0471/04a9` (and `5440:0375`, specced §2.4 but AI code); `1641:0142/0157` (wreck shape,
  APP kind); `GDAMAGE.DAT` fields beyond `+0/+4`; `DS:474D` effect shape base; `DS:5140..5148`,
  `DS:0C2E..0C57` built by the area loader for collisions (`14e0`); `59f9` class registry (§4.5,
  AI data); `62d2:044a` group damage reset; target lists 2 and 4.
* **video**: `1d32:6a5b(x, y, colour)` pixel (far dots); `DS:26C3/26C4..26CA` window.

## Cross-part notes

* render3d_shapes.md §1.3: draw record confirmed and completed (§1.2 here: z = 0 kinds, angle
  sources, state pointer rules of `5440:0269`); `ts_draw` is also called directly by
  `1560:06e9` (effects, with a temporary header radius) and `33b4:002a`.
* render3d_math.md §4.6: `5440:03aa` passes `DS:51D9` (pitch) and `DS:51DD` (heading) to
  `set_light` (not `51DB`). §1.4: `CS:0A4D` override from `644a:089f`.
* render3d_sky.md: `DS:36D0` = `675d:0000` (after the ground layer, before the sorted objects);
  horizon callback `6964:01a2` only when `DS:5BDA == 0`.

## Open questions

* `DS:18C0` (gather "keep" count) is only ever zeroed (`14e0:0044`): dead feature?
* `DS:55D9` (effects re-cull reference) is never updated after init: re-cull every frame, and the
  flags word of culled effects is overwritten with `100h` (type lost) — intended? (**Verified**
  behaviour, intent Unknown.)
* Tile size test in `33d1:04e7` compares `S` without `<< 8` (§3.3): bug or intent (Unknown).
* Meaning of object types 0Ch/0Dh and of the `z == 0 / 1` special cases of `465c:0589` (sim_world).
* `.FLT` third range (`+0Bh`) and GID 10-byte region bytes `+8/+9`: never read in AP.
