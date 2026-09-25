# render3d — part 4: scene assembly, object lists, depth order, world loading

Part of the `render3d` spec (index: `render3d.md`). AP addresses (`work/AP_flat.exe`, DGROUP `3EA4`).
Formats: `port/formats/world.md` (WD3, MBL, FLT, TARGET), `shapes.md` (GID). Math/projection:
`render3d_math.md`; shape drawing: `render3d_shapes.md`. Confidence **Verified** unless marked.
Segments: `5440:03aa/0269/0375` (claimed by content from sim_flow's `5440`), `33d1`, `33b4`,
`34bf`, `465c:0589`, `0802`, `05a9`, `1560:055b/06e9`, `2466`, `59f9`, `35a4`, `35d1`, `35d6`, `3368`,
`333b`, `33a1`, `3546` pool.c, `3591` init.c, `35ad` obwload.c, `34f1` macros.c, `62d2`, `628f`
wdata.c, `62ca`, `51ca`.

-----------------------------------------------------------------------------------------------

## 1. The 3D frame

### 1.1 `5440:03aa` `render_scene()` (called from `5440:018c`, sim_flow's frame driver, in the
default view branch; the sky, cockpit and HUD are drawn around it by sim_flow)

```
4899:005c(view);                                  /* sim_flow: cockpit panel line */
cy_override = 644a:089f(&view->window);           /* sim_flow: window per view, returns cy */
cam_begin_frame(view = DS:437E);                  /* 277a:004b */
if (DS:19F2) { CS:09B2 = 1; CS:0A4D = cy_override; }   /* view centre moved -> always clip */
set_light(DS:51D9, DS:51DB);                      /* 277a:0152, sun direction (render3d_sky.md) */
DS:26C3 = 1; window DS:26C4..26CA recomputed from the view (same as 004b)
4899:0027();                                      /* sim_flow */
CS:09B2 += (4899:0000() == 0);                   /* sim_flow full-screen flag: force clipping in the cockpit view */
4d6e:0076(DS:5BDB, cam_ang.heading?, CS:0A1F, CS:0A21, DS:5BDA ? 0 : 2Ah);   /* sky/horizon, render3d_sky.md */
if (!(DS:3B09[+0Dh] & 1)) player obj flag 2000h = (DS:19F2 != 0);      /* hide own aircraft in cockpit */
DS:36CC:36CE = 3D32:0070 (stub → 5440:0269); DS:36D0:36D2 = 3E07:0020 (stub, post-ground callback)
scene_begin(view);                                /* 33d1:0004 */
if (DS:4380 countdown) ...
if (!overcast_split())                            /* 0802:0026 */
     { if (DS:4380) { scene_force_rebuild(); DS:4380 = 0; } scene_gather_static(0); }   /* 33d1:04dc, 04e7 */
else { DS:36D8 = DS:36DC = DS:36DA = 0; DS:4380 = 1; }   /* eye inside/above the layer: no static world */
eye = 5440:008d();                                /* eye position pointer (DS:4368+2) */
0802:0173();                                      /* cloud / range culling of moving objects */
490a:0509();                                      /* sim_world: cloud bookkeeping ('grsmstr') */
1560:055b();                                      /* fire/smoke effects on destroyed ground objects */
583c:0471();                                      /* sim_world: spotting helper */
for (i = 0; i < DS:00BE; i++) {                   /* moving objects DS:00BC[] */
    o = DS:00BC[i];
    if ((o->model[+3Bh] & 2) && o[+18h].b != 1) continue;
    d = ldist3(o->pos, eye);
    if (o[+18h].b == 0 && !(o->flags & 0x100)) {  /* aircraft */
        R = shape_radius_cached(o->shape);        /* 35d6:018a */
        if (d < R*256 && (!DS:42C8 || !583c:04a9(o->pos, eye, d))) {
            if (d < R*128) list_add(o, d);        /* 33d1:00f2 */
            else { p = DS:5EDE + 18·k++;          /* distant aircraft → dot proxy */
                   p = { 8012h, o[+2], o->pos (12 bytes), colour = DS:55D2[DS:54BC[o[+19h]]].+81h };
                   list_add(p, d); }
        }
    } else if (o[+18h].b == 1) { if (d < 250000) list_add(o, d); }
    else list_add(o, d);
}
v = 1c30:0780();  own_hidden = (v == 2 || v == 3);   /* sim_flow view mode */
for (e in pool DS:00E6):  e.type == DS:54B5 ? 04c4:0b53(e)          /* sim_world: flak bursts */
                          : (!own_hidden || e[+16h] != DS:3B09) && scene_add_dynamic(e);   /* 33d1:0140 */
for (e in pool DS:55F1 (effects, §3)): scene_add_dynamic(e);
scene_draw();                                     /* 34bf:0006 */
CS:09B2 -= (4899:0000() == 0);
```

`list_add` keys are distances (`ldist3`, u32). The proxy array `DS:5EDE` (18-byte records) is
allocated by `2466:000a` for `DS:4776` entries.

### 1.2 `5440:0269` `draw_object(far obj *o)` — the `DS:36CC` callback (via stub `3d32:0070`)

```
t = o->flags & 1Fh;
if (!(DS:06B7++ & 1)) 1c0f:0053();                /* sim_flow VCR hook, every other object */
if (t == 0Fh) 0916:0273(o);                       /* sim_world: parachute/debris (then continues!) */
if (t == 0Eh) { effect_draw(o); return; }         /* 1560:06e9 */
if (t == 12h) { far_dot_draw(o); return; }        /* 2466:0023 */
if (o->flags & 2000h) return;                     /* hidden */
if (t == 5) { 05d6:01d3(o); return; }             /* sim_world: ordnance */
r = draw_record(o);                               /* 33b4:010e → DS:3666 */
if (!(o->flags & 1000h)) { r.state = o[+16h]; if (r.state < 40h) { tmp = (u8)r.state; r.state = &tmp; } }
else if (o[+1Dh] == 0Ch) { if (t == 11h) return; tmp = (t != 10h); r.state = &tmp; }
set_near(get_near_n() − 3);                       /* near = focal/8 */
if (t == 0Bh) shadow_draw(r, DS:5CE0); else ts_draw(r);   /* 2ecb:00ba / 2f0e:08e9 */
reset_near();
```

(`t == 0Bh` objects are drawn as their shadow only — `2ecb:00ba` draws the shadow version.)
State field: `o[+16h]` is either a DS pointer to state bytes (≥ 40h) or a small constant stored in a
stack byte.

### 1.3 `5440:0375` `dist_limit(i16 v)` → `max((v + 40) << 8, 100000)` (low word returned; used by
`583c:0ef0`/`18bf`, sim_world).

-----------------------------------------------------------------------------------------------

## 2. Object lists and depth order

### 2.1 Globals

| DS: | Type | Meaning |
|---|---|---|
| `3682` | u16 | current view record (set by `33d1:0004`) |
| `36D4` | far | draw list: entries of 8 bytes `{far obj*, i32 key}`, capacity `DS:367C` |
| `367E` | u16 | reserve kept free for moving objects during the static gather |
| `36D8` | u16 | entries in the list |
| `36DA` | u16 | **ground layer** entries at the front (key = layer byte), drawn first |
| `36DC` | u16 | static distance entries, filled from the end downwards during the gather, moved behind the ground layer afterwards (`1d32:67fb` memmove) |
| `3694`/`3698` | far | fill pointers (front / back) during the gather |
| `3688` | lvec | eye position at the last static gather |
| `36C4` | i16 | re-gather distance (the gather is redone when the eye moved farther) |
| `3680` | u8 | force re-gather (`33d1:04dc`) |
| `369C` | far | object being tested |
| `36A0` | i32 | minimum range for big objects (`R >= 5 000 000`) |
| `36A8` | far | temporary object arena (macro members), 2-ended: 30-byte records from the bottom (`DS:710C`), 40-byte from the top (`DS:710A`), size `DS:710E` |
| `36AE` | far | macro table, 18-byte entries (`u16 count, i32 box[3], far members`), count `DS:36B2`, capacity `DS:36AC` |
| `36E0` | ptr | per-class detail table, 85-byte records (`DS:36DE` of them), from `.FLT` (§4.4) |
| `36E2` | ptr | per-class current draw range (i32) |
| `36CC/36CE` | far | draw callback (5440:0269) |
| `36D0/36D2` | far | callback called after the ground layer is drawn (stub `3e07:0020`) |
| `06F3` | far | array of far pointers to the static objects, partitioned by the cumulative counts `DS:5134 ≤ 5132 ≤ 5130 ≤ 512E ≤ 43D6` |

### 2.2 `33d1:0004` `scene_begin(view)`

`DS:3682 = view`; `alt = min(eye.z >> 2, 7FFFh)`; for each class record `c` with `c[0]` (valid) and
`c[3] == 0` (range mode): `range[c] = (c.r0 + ((c.r1 − c.r0) · alt >> 15)) · 1000` (`c.r0` = `+7`,
`c.r1` = `+9`) → `DS:36E2[c]`. Then `34f1:0144` resets the temporary arena.

### 2.3 `33d1:02ea` `static_test_add()` (near; object `DS:369C`) — visibility by class

```
d = ldist3(eye, obj.pos); c = &DS:36E0[class(obj.shape)];   /* 35d6:020c */
if (c[0] == 0) vis = 1;
else if (c[4]) return 0;                          /* class disabled at this detail */
else {
  if (c.density(+0Dh) < 3FFh) {                   /* pseudo-random thinning */
      h = 14b8:0057(obj.pos, 12) + 13;  DS:5822 = h;
      if ((WORD[3A0D:(h & FF)*2] & 3FFh) > c.density) return 0;
  }
  if (c[3]) vis = log_key(Rw) + S·256 − log_key(d) > c.ratio(+5);     /* Rw = radius<<shift */
  else { lim = range[c]; if (Rw >= 5 000 000 && lim < DS:36A0) lim = DS:36A0;
         vis = d − Rw < lim; }
}
if (vis) { l = layer(obj.shape);                  /* shape header byte 2, 35d6:01e2 */
  if (l) { front[DS:36DA++] = {obj, l}; } else { back[--] = {obj, d}; DS:36DC++; } DS:36D8++; }
return vis;
```

`log_key(Rw) + S·256 > log_key(d) + ratio` ≈ `Rw·2^S / d > 2^(ratio/256)`: an object is kept while its
projected size is above a per-class threshold. **Shape header byte 2 (shapes.md "sub-class") is the
ground-layer priority**: non-zero for flat ground objects (islands, reefs, runways, roads), which
bypass the distance sort.

### 2.4 `33d1:04e7` `scene_gather_static(force)`

If not forced, not `DS:3680`, and `33d1:00a8` (eye moved less than `DS:36C4` since the last gather,
else it stores the new eye in `DS:3688`) → only refresh the keys of the `DS:36DC` distance entries
(`ldist3` to the eye), `DS:36D8 = 36DA + 36DC`, return. Otherwise rebuild from `DS:06F3`:

| Range of the array | Test before `static_test_add` |
|---|---|
| `[0, 5134)` | `lnear(eye, pos, 2 000 000)` |
| `[5134, 5132)` | `lnear(eye, pos, Rw + 4 000 000)` |
| `[5132, 5130)` | `lnear(eye, pos, 2 000 000)` |
| `[5130, 512E)` macro instances | `d < 1 300 000` and `log_key(macro radius 34f1:0259) + S·256 > log_key(d)`: expand the members (`34f1:0155`) into temporary 30/40-byte objects (layer 0 → top 40-byte, else bottom 30-byte), flags `(obj.flags & FFh) | 1800h`, parent link at `+16h/+1Ah`, member index, state `FFh`; wreck substitution for destroyed members (`1641:0142`); each member tested with `lnear(…, 1 300 000)` and added (else its arena slot is released) |
| `[512E, 43D6)` tiled macros | `d < 2 000 000` and the same size test: the macro's members are repeated on a grid over the instance's rectangle (`+10h` extents) with pitch = macro box x/y; only tiles whose approximate distance key is within `S·256` of the macro size are expanded; members inside the rectangle are added |

Stops when `DS:36D8` reaches `DS:367C − DS:367E`. Then the ground layer is ordered once with the tree
sort (§2.6) and flattened into order (`33d1:0e69`), and the distance entries are moved behind it.

### 2.5 `33d1:0140` `scene_add_dynamic(obj)` / `33d1:00f2` `list_add(obj, key)`

`list_add`: fails if the list is full; an object with flag `100h` ("skip this frame") has the flag
cleared and is not added. `scene_add_dynamic`: flag `100h` → clear, skip; flag `1000h` → skip; else
the class test of §2.3 with `d = ldist3(eye, pos)` (layer objects: key = the layer byte) and
`list_add`.

### 2.6 `34bf:0006` `scene_draw()` and the depth sort `34bf:0084`

```
for (i = 0; i < DS:36DA; i++) draw_entry(list[i].obj);        /* ground layer, list order */
if (DS:36D0) DS:36D0();
n = DS:36D8 − DS:36DA;
if (n) { tree_build(n, &list[DS:36DA], nodes /* 200 × 8 bytes on stack */); tree_draw(nodes); }
```

`draw_entry` (`33b4:0004`) calls `DS:36CC` if set, else `33b4:002a` (default: build a draw record and
`ts_draw`).

`34bf:0084` `tree_build(n ≤ 256, entries, nodes)`: node = `{far entry*, u8 parent, u8 nearer,
u8 farther, u8 flags (1 has parent, 2 nearer set, 4 farther set, 8 drawn)}`. Entry 0 is the root;
each next entry descends from the root: `diff = new.key − node.key`;
`closer = (same type (flags & 1Fh)) ? diff < 0 :
         (|diff| >= 10000 || |diff| > R(new) + R(node)) ? diff < 0 : 465c:0589(new, node)`;
go to the `nearer` child if closer else `farther`, inserting at the first empty slot. (The 256 cap
exceeds the 200-node stack buffer of `34bf:0006`; the list capacity keeps n below that in practice,
**Likely**.) `34bf:02a4` `tree_draw`: iterative in-order walk: farther subtree, node (`draw_entry`),
nearer subtree — **far to near** (painter's order).

`465c:0589` `sort_compare(new, node)`: only for the type pairs `(3,0Ch)`, `(3,0Eh)`, `(0Ch,3)`,
`(0Eh,3)` (aircraft-class 3 vs large objects 0Ch/0Eh, **Likely** ships/effects): uses the ship's
hit box through `6ac7:0120` (segment vs box, sim_world) with the eye as segment start to decide
which one is in front; other pairs return 0 (farther). **Likely** in the meaning of the types.

### 2.7 Draw record builder `33b4:010e` / `33b4:002a` and object angles `35a4:000f`

Record (`DS:3666`, or a stack copy in `002a`): `+00 id = obj[+2] & 1FFFh`, `+02` 12 bytes = `obj+4`
(position), `+0E` pitch, roll, heading, `+14` state pointer (0). Angles by object kind
`obj.flags & E00h`: `200h` heading = `obj[+10h]`; `400h` z = 0; `600h` z = 0, heading = `obj[+0Ch]`;
`800h` angles = `obj[+10h..]`; `C00h` z = 0, angles = `obj[+0Ch..]`. (z = 0 means objects standing
on the ground/sea.) `35a4:000f(obj, out)` returns the same angles (0 for other kinds).
`33b4:002a` also clears flag `100h` and skips.

### 2.8 Cloud-layer and range culling `0802`

* `0802:000c` `overcast()` = `DS:4512 && DS:42C9`.
* `0802:0026` `overcast_split()`: if overcast: every object in `DS:475D[DS:4778]` and the pools
  `DS:00E6`, `DS:55F1` whose altitude is on the other side of **z = 16000** than the eye gets flag
  `100h` (hidden this frame); returns `eye.z > 16000`. (5440:03aa then skips the static world when
  the eye is above the overcast.)
* `0802:0173` `range_cull()`: if not overcast: `c = 490a:03fb(eye)` (the cloud containing the eye,
  sim_world); inside a cloud (`DS:5BE5 = 1`, `DS:5600/55FC` = its data): hide objects of
  `DS:475D[DS:4778]` farther than 3000; else hide objects of `DS:475B[DS:4776]` farther than
  200 000 or occluded by a cloud (`490a:043e(pos, eye)`).

-----------------------------------------------------------------------------------------------

## 3. Effects pool and special draws

* `05a9` effect pool `DS:55F1` (pool.c pool of 48-byte records, created by `05a9:0005` with the
  reference position `DS:55D9/55E5` = `22222222h`): `05a9:005a(tmpl)` allocates a record if
  `05a9:025f` (within `rec[+1Ch] << 10` of the reference point, `ldist2` then `ldist3`) and copies 48
  bytes, `+1Fh = 0`; `05a9:00ad(eye)` sets the reference to the eye, re-culls when it moved > 3000
  (`05a9:01d1`: out-of-range records are marked `100h`) and releases records with `+1Fh & 1`;
  `05a9:014c` runs each record's update callback `+18h` (far) when `+0Ch >= 0`, marking finished
  ones; `05a9:0233` releases a list; `05a9:0043` frees the pool.
* `1560:055b` `spawn_ground_fires()`: for the distance entries of the list whose object has flag
  `1000h` (macro member), state `FFh` in the parent (destroyed) and class < 13h: switch to the wreck
  shape (`1641:0142`, once, flag `80h`; none → flag `2000h`), then spawn an effect record (type
  `80Eh`, shape `DS:474D + 1Dh/1Fh (+1)`, radius from `DS:5A82[class·8]`) with an animation frame
  counter kept in the member (`+1Ch`), cycling through the effect shape's frames
  (`shape_nvariants`), toggling flags `C0h` at the end (fire → smoke).
* `1560:06e9` `effect_draw(o)`: temporarily sets the shape radius to `o[+2Ah]`, draws
  `{o+2.., state = &o[+16h]}` with `ts_draw`, restores the radius.
* `2466:0023` `far_dot_draw(p)`: `e = lvec_rotate(p.pos − cam_pos, m_cam)`; if `e.y >= focal`:
  project, and if strictly inside the cockpit window rectangle (`644a:089f`), `DS:26C3 = 1`,
  `1d32:6a5b(x, y, p[+10h])` (pixel).
  (Ghidra shows a "TAPES\DEMO_.VCR" string here: it is `CS:0A13` (`cam_pos`) misread as a DGROUP
  address — the origin of the "DEMO" label attached to `277a` in the task list.)
* `59f9` class registry: `59f9:0000` (BX = class record) sets `+06 |= 8000h`, appends to
  `DS:47F6[DS:47F2++]`, `DS:47F4 = max(size +04)`; `0026` registers AX records; `004e` allocates
  `DS:47F4` bytes into `+0Ah` (`24d3:0059`); `0068` clears `DS:488C`.

-----------------------------------------------------------------------------------------------

## 4. World loading

### 4.1 Sequence (`62d2:049e`, from `56ac:0236` snario, sim_world)

Builds `AW<n>.wd3`, `.flt`, `target.XX` names (`55a4:0000`), then: `35ad:000c` (open `WD2:WHD:`,
count table into `DS:7114`), `35ad:00f8` (`WD2:OBx:` records → handler `DS:7110` =
`62d2:0199`; `WD2:MBL:` instances), `62d2:0a2e` (`WD2:MBL:` again: group records with target
lookup `628f:031f`), `628f:0144` (`TARGET.n`), `333b:000a` (`.FLT`), `333b:0158(80h)`, `34f1:0155`
for macro instances, `35ad:00ce` (close). Formats and records: world.md §2–5. The decompile of
`62d2` is unusable (overlapping code); the order above is from the call list (**Likely**).

* `62d2:0199` object record handler: builds the 24-byte instance (`62d2:0133`: flags
  `0801h | 4000h`, shape, position, angles; 4000h recomputed "no rotation" when both extra angles
  are 0), looks up class/layer (`35d6:01e2/020c`), expands macros (`34f1:0155`), group records
  (`62d2:001d`, 42 bytes, target sample `628f:031f`). `62d2:0000` = bit length of a long.
  `62d2:044a`/`0969`/`0a0d` = free/alloc helpers (`0a0d` calls `34f1:000b` and `3591:0001` at init).
* `35ad:000c/00ce/00f8` obwload.c: open/close the WD3 volume entry, read `WHD:` (512-byte count
  table → far `DS:7114`), iterate `OB0..OB5` (digit patched) in 26-byte records and `MBL:` (22/40-byte
  records by `(type & C000h) == C000h`), calling `DS:7110`.
* `34f1` macros.c: `000b` allocate the macro table (`DS:36AE`) and arena; `0310` load `AW<n>.MBL`
  (world.md §3; members with shape FFFFh dropped); `0155` expand a macro instance (members' x/y
  rotated by the instance heading with `367b:0006`, added to the instance x/y, z not added, heading
  replaced); `0259` distance from the eye (`DS:36B4`) to a macro instance's centre; `02f5` entry
  pointer; `00a8`/`00e9` free; `0144` reset the arena; `04a3`/`04f0` allocate a 30/40-byte temp
  object (zeroed), `053a`/`0548` release the last one.
* `3546` pool.c: pool header 14 bytes `{count free, count used, record size, segment, first free,
  (ptr), first used}`, records with a 4-byte link header `{next, prev}`; `0006`/`007e` create (size
  rounded up to even), `0118` init the free list, `019d`/`01d4` destroy, `021a` alloc (moves a
  record to the head of the used list), `02ca`/`0304` alloc + zero, `0333`/`03f2` free, `040a`/`045f`
  iterate used records (`NULL` → first), `0498` get field 0.
* `3591:0001`/`00dc` init.c: allocate/free the object arrays.
* `628f` wdata.c: `TARGET.n` reader (world.md §5): `0144` loads `INF:`/`DAT:` lists through the
  `51ca` file helpers (`51ca:0000/0027` read word/long, others strings), sorted by date
  (`62ca:0000/004f` sorted insert); `031f` finds the entry valid at the mission date (uses
  `277a:5510` box test). Target semantics → sim_world.

### 4.2 `.FLT` detail table `333b` / `33a1` (settles world.md §4)

`333b:000a` reads 24-byte records (word fields `w[0..11]`) into 85-byte class records `DS:36E0 +
class·55h`:

| Rec | From | Meaning |
|---|---|---|
| +0 | 1 | valid |
| +1 | `w1` | detail threshold: class hidden (`+4 = 1`) while the detail level < `w1` |
| +3 | `w2` | mode: 1 = size-ratio visibility, 0 = range visibility |
| +5 | lerp(`w3`→`w4`) | ratio threshold (mode 1), in `log_key` units |
| +7/+9/+0B | lerp(`w5`→`w6`), (`w7`→`w8`), (`w9`→`w10`) | range at sea level, at altitude 131 072, third (unused by `33d1`) — thousands of units |
| +0D | lerp(`w11`→3FFh) over `(level − 80h)·2` | density 0..3FFh (thinning, §2.3) |
| +0F.., +1D.., +2B.., +39.., +47.. | | the 14-byte interpolators |

`lerp(a→b)` = `33a1` stepper over the detail level 0..255: `33a1:0055(s, x0, y0, x1, y1)` sets up
a 16.16 accumulator stepping `(y1−y0)/(x1−x0)` per unit (`33a1:00b3`), `33a1:0008(s, x)` clamps x
to `[x0, x1]` and steps to it, returning the integer part. `333b:0158(level)` re-evaluates all
classes (called at load with 80h and by the detail slider `4b9f`, sim_flow). `333b:0143(c)` =
record valid byte.

### 4.3 Ground data `GID:` (`3368`) — settles shapes.md "GID: layout"

`3368:0001` loads `GID:` of a table (`7039:020a`), relocating its offset list (`DS:36C6`, count
`DS:36CA`). Entry per shape:

| Off | Type | Field |
|---|---|---|
| 0 | i16 | half extent x |
| 2 | i16 | half extent y |
| 4 | u8 | flags: 1 = the whole box is solid (no polygon test), 2 = regions carry a slope plane (10-byte regions) |
| 5 | u8 | number of regions |
| 6 | u16 | offset of the regions |

Region (6 or 10 bytes): `+0 u16` offset of the edge list, `+2 i8` edge count, `+3 u8` slope scale,
`+4 i16` height, `+6 u16` offset of the plane (10-byte form). Edge / plane: `i8 nx, i8 ny, i16 px,
i16 py`; a point is inside a region when `nx·(x − px) + ny·(y − py) <= 0` for every edge
(`35d1:000e`). `3368:0169(out, pos, gid, obj)`: `local = (pos − obj.pos) >> shift`, outside if
`|x| > half_x` or `|y| > half_y`; rotated by `−heading` (`3609:0001`); first matching region; height
= region height (+ `(nx·(px − x) + ny·(py − y)) · scale >> 12` when sloped, `3368:02f4`); world
`z = (h << shift) + obj.z`, or 0 for ground-layer shapes. `3368:0069(out, pos, objs, n)` tests a list
of nearby objects (sim_world `14e0`, collisions/terrain height); `3368:0128` region pointer by
index; `3368:0057` free.

### 4.4 Shape attribute cache `35d6`

Per shape id arrays: class `DS:3700`, layer `DS:3704`, shift `DS:3708` (bytes), radius `DS:370C`
(words), valid flag `DS:3710`. `35d6:00b8` allocate + fill (`000c` refresh, returns 1 if anything
changed), `0128` free; getters `018a` radius, `01b8` shift, `01e2` layer, `020c` class (AX = id,
fall back to `ts_util` when not built); setters `0236` class, `0267` radius.

## 5. Port notes

* `/* PORT: */` Keep the list capacities and the tree sort exactly: draw order is visible (ships vs
  aircraft, overlapping ground layers).
* The pseudo-random thinning uses the table at `3A0D:0000` (far data) and `14b8:0057` (sim_flow
  RNG helper): position-hashed, deterministic.

## Hand-offs

* **sim_flow**: `5440:03aa`, `0269`, `0375` are specced here (3D scene build); `4899:*`, `644a:089f`
  (per-view window/centre), `1c30:0780` (view mode), `1c0f:0053` (VCR hook called from the draw
  callback on every other object — keep the call order), `14b8:0057` hash, `4b9f` detail slider.
* **sim_world**: `0916:0273`, `05d6:01d3` (object draws that only call `ts_draw`), `04c4:0b53`
  (flak bursts), `490a:03fb/043e/0509` (clouds, line of sight), `583c:04a9/0471`, `6ac7:0120` used by
  the sort comparator, `1641:0142` wreck shapes, `628f` target semantics.

## Open questions

* Object type numbers (`flags & 1Fh`) and `+18h` kind byte: names belong to sim_world.
* `62d2` details (decompile broken): instance/group record fields beyond world.md.
* `DS:36D0` callback target (stub `3e07:0020`) not traced.
