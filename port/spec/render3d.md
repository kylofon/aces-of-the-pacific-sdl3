# render3d — AP 3Space renderer (index)

Spec of the 3D view of AP.EXE (`work/AP_flat.exe`, DGROUP `3EA4`). Ownership follows the map in
`sim_flow.md` §0 (render3d rows), plus by content `5440:03aa`/`0269`/`0375` (3D scene build and
per-object draw, segment otherwise sim_flow) and the splits `1560:055b/06e9`, `465c:0589`,
`655d:038a`. Symbols: `render3d_symbols.csv`.

| Part | File | Contents |
|---|---|---|
| 1 | `render3d_math.md` | **projection maths** (§1), camera record, `277a` CS state block, sin/cos/atan/asin tables, matrices, transform, vector library, model/world scale answer |
| 2 | `render3d_poly.md` | polygon pipeline in `277a`: draw modes 0–3, vertex cache, culling, VGA/EGA colours, SHADES shading, near-plane and window clipping, fill |
| 3 | `render3d_shapes.md` | ts2 shape library: `ts_draw` (visibility, LOD, draw mode, BSP part sort, variants), discs, sprites, shadows, `.BMD` effects (payload decoded, all 31 files), ts_util/utilo/file |
| 4 | `render3d_world.md` | scene assembly (`5440:03aa`), object lists and depth order, pools, world/area loading (obwload, macros, wdata, .FLT, GID) |
| 5 | `render3d_sky.md` | horizon/sea/sky, sun/moon/stars, palette effects (paltrick, `1792`, `17ce`), shadows/tracer/ground-dot effects |

## Frame order (summary)

`5440:018c` (sim_flow) → `5440:03aa`: `277a:004b` camera (view `DS:437E`, shift 7 = focal 128),
optional `cy` override + force-clip, `277a:0152` sun light, window `DS:26C4..26CA`, sky/horizon
`4d6e:0076`, object lists (`33d1`), culling (`0802`, `583c:04a9`), sorted draw (`34bf`) calling
`5440:0269` per object → `ts_draw` `2f0e:08e9` → `277a` part routines → `1d32:09ce` fill.

## Settled questions

* Model/world scale and `CS:09AC` (math §6); `CS:21EC` is a pointer; polygon flag 40h unused (poly §1.1).
* Shape header byte 2 = ground-layer priority (world §2.3); `GID:` layout (world §4.3); `.FLT` fields
  (world §4.2); `.BMD` payload (shapes §4.1).
* The "DEMO" label of `277a`: Ghidra misreads `CS:0A13` (`cam_pos`) as the DGROUP string
  "TAPES\DEMO_.VCR" (world §3). `277a` is the 3Space core, not demo code.
* `DS:26DF`: set by the video driver's info call; VGA → the +1/+2 colour bytes (poly §1.2).
* Colour remap `CS:21EE`: never set in the sim; night/fog/haze are palette channels (sky §3).
* Self-modifying code: none in the render code.

## Hand-offs

* **platform**: INT 0 handler `1d32:69cc` is load-bearing for projection overflow (halves the
  dividend and retries; infinite loop on /0) — render3d_math.md §1.4.
* **video**: fill `1d32:09ce` (uses `DS:26CC/26CD/26CE`, `DS:276C/2794`), ellipse `1d32:6bbc`,
  scaled bitmap `1d32:5e5b`, rotated bitmap `1d32:2258`; `DS:26DF` set by the driver info call
  `1d32:0070` (block `DS:26C0`); `DS:26C3` meaning. AP driver jump table is `DS:351A`.
* **sim_world**: `0916:0273`, `05d6:01d3` (object draws that just call `ts_draw`), `04c4:0b53` flak,
  `490a:03fb/043e/0509/017f` clouds and line of sight, `583c:04a9`, `6ac7:0120` (used by the depth
  comparator `465c:0589`), `1641:0142` wreck shapes, `0fd4` blackout level `DS:5798`, target semantics.
* **video**: span fill `1d32:09a8` (entry 27, `DS:3586`), rectangle `1d32:6ab0`, pixel `1d32:6a29/6a5b`,
  bitmap `1d32:3de5`; DAC queue `5440:07bd`/`0000:189b`.
* **sim_world**: `07fe:000a` (ces.c) is a 4-point bitmap draw primitive (only reached by polygon
  flag 10h, unused); world unit in metres unresolved (F4U 388 units vs map scale, math §6);
  `.BMD` effect ids loaded by `0916:002e`, `4b3a`.
* **sim_flow**: `1c0f:0053` (VCR hook) is called from the per-object draw callback on every
  other object — the call order matters; `4899:0000/0027`, `644a:089f`, `1c30:0780`, `4b9f` (detail
  slider → `333b:0158`, `4d6e:0000`, `1a8b:001e`), `4e0d:03e9` → `sky_init`, `5440:1317` → `6964:0076`.
* **sim_flow**: `519d:008a` loads SHADES1 into `DS:4092` (camera `+12h`); eye record `DS:4368`
  and window `DS:06AD..06B3` are written by the view/cockpit code; `5440:03aa/0269/0375` specced here.

## Open questions

* Exact metric size of a world unit; `CS:09B1` use; `DS:26C3` semantics; `2e33:0333` matrix
  element choice (Likely); shadow colour `DS:2402` producer (`2ecb:013c` has no caller).
* `62d2` area loader details (decompile broken), object type numbering, `DS:36D0` callback target.
* Horizon band geometry (`4d6e:03be/0724`), star projection scaling, `DS:51CF/51CD` meaning.
