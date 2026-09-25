# render3d — part 5: sky, horizon, sun/moon/stars, palette effects, ground and flash effects

Part of the `render3d` spec (index: `render3d.md`). AP addresses (`work/AP_flat.exe`, DGROUP `3EA4`).
Conventions and `277a` names: `render3d_math.md`. Segments: `4d6e`, `0a88`, `1abf` (horizon fill),
`55e8` sky.c, `59eb` stars.c, `6964` sun/moon/time of day, `4b91` moon phase, `1a9a` stars and
celestial directions, `1a8b` shadows, `675d` ground speed dots, `655d:038a` gun/exhaust flashes,
`1792`/`17ce`/`51b4`/`51a8` palette effects. Confidence **Verified** for control flow and constants
read in the code; formulas marked **Likely** where only the decompile was read.

-----------------------------------------------------------------------------------------------

## 1. Sky and horizon (`4d6e`)

### 1.1 Globals

| DS: | Meaning |
|---|---|
| `5BDB` | sky base palette index (70h clear, 61h under an overcast); sky colours are `base .. base+15` |
| `5BDD` | ground/sea colour index (80h; 70h = cloud tops when above the overcast) |
| `5BDA` | 1 = eye below the overcast (no sun/moon callback) |
| `0320` | haze bands enabled (off under an overcast) |
| `031A/031C/031E` | band width factor / band count / colour step, set by `4d6e:0000(detail)`: detail < 55h → no bands; < AAh → 7 bands, step 2, width 4; else 15 bands, step 1, width 2 |
| `0322` | far buffer 780h bytes (span list), `4d6e:004b` |
| `4000..4006` | horizon line end points (x, y) |
| `4008/400A` | horizon normal (sign swapped when upside down) |
| `400C/400E` | ground colour / sky base of this frame |
| `3FFA` | "celestial callback pending" flag; `3FFC` far callback |

### 1.2 `4d6e:0076` `draw_sky(u16 sky_base, u16 ground, u16 pitch, u16 roll, far void (*celestial)())`

Called by `5440:03aa` with `DS:5BDB`, `DS:5BDD`, `cam_ang` pitch/roll (`CS:0A1F/0A21`, the
effective view angles), and `celestial = 3e1d:002a` (stub → `6964:01a2`) when `DS:5BDA == 0`, else 0.

```
r = horizon_line(−pitch, −roll);                    /* 4d6e:015c */
if (r == 0) { (|400A| < |4008|) ? horizon_fill_rows() : horizon_fill_cols();   /* 03be / 0724 */
              DS:3FFA = 1; return; }
if (r == 1) { colour = sky_base + 15; DS:3FFA = 1; }      /* looking steeply up: all sky */
else /* −1, looking steeply down: all ground */ {
    if (DS:3FFA && celestial) celestial(); DS:3FFA = 0; colour = ground; }
DS:26CE = DS:26CD = colour; DS:26CC = 1; 1d32:6ab0(window)             /* filled rectangle */
if (r == 1 && celestial) celestial(); DS:3FFA = 1;
```

### 1.3 `4d6e:015c` `horizon_line(p, r)` → −1 / 0 / 1

`inv = |p| > 4000h`; `s = sin16(p)`, `c = cos16(p)`; `s >= 15000` → −1, `s <= −15000` → 1 (±66°).
`dx = cos16(r) >> 6`, `dy = sin16(r) >> 6` (±256); `h = ldiv_sat((i32)s << S, c)` (= f·tan p,
pixels); `ox = (h·dy) >> 8`, `oy = (h·dx) >> 8`;
`x0 = cx − dx + ox`, `x1 = cx + dx + ox`, `y0 = cy − (dy + oy)`, `y1 = cy − (−dy + oy)`
(`DS:4006, 4002, 4004, 4000`); normal `(4008, 400A) = inv ? (dxfull, −dyfull) : (−dxfull, dyfull)`
with the unshifted cos/sin. Returns 0.

### 1.4 Fill (`4d6e:03be`, `4d6e:0724`, `4d6e:029e`, helpers `0a88`, `1abf`)

The window is split along the horizon line into a sky part and a ground part, each filled as a
list of horizontal spans (`0a88:00cf`: clips the rows to `DS:26C8..26CA`, writes `{y0, n, (xl, xr)×n}`
into `DS:0322` and calls `1d32:09a8` = span fill through driver entry 27 (`DS:3586`), video spec).
Edges are stepped with the 16.16 DDA `1abf:0008/00c6/00de/011d` (setup / step / fill an edge array /
constant edge). `03be` is used when the line is flatter than 45°, `0724` when steeper (column-wise
set-up through `lerp_map` `277a:41c4`).

Colours, from the horizon outwards into the sky: if `DS:0320`, `DS:031C` bands, band `i` in colour
`sky_base + i·DS:031E + DS:031E/2`, each band's thickness from a DDA over `(031C+1)·031A·4000h /
normal` (so bands get thinner as the horizon tilts), then the rest of the sky in `sky_base + 15`;
the celestial callback runs between the sky and the ground fill; the ground/sea part in `ground`.
`4d6e:029e` fills the part of the window above/below the span block with rectangles
(`1d32:6ab0`). (**Likely** for the exact band edge arithmetic; the colour sequence is Verified.)
There is no terrain drawing here: land is made of island/ground-layer shapes drawn on top of this
flat sea (render3d_world.md §2.3).

`4d6e:0040` sets `DS:3FFA = 1` (after a view change).

-----------------------------------------------------------------------------------------------

## 2. Time of day, sun, moon, stars

### 2.1 `55e8:00c4` `sky_init(u16 date, int hour_slot, u16 lat?, u16 ?)` (sky.c, from `4e0d:03e9`)

Converts the mission date (days since 1900, `55e8:0028`: day/month/year tables `DS:0711..`) to a
day-of-year (`55e8:028f`) and a sun declination (`55e8:02a3`: `doy·0B3h`, then `mul_sin`
products with `0EF46h`/`1304h`). Sets the sun hour angle `DS:1120` from the start-time table
`DS:1132[hour_slot]`, the moon angle `DS:112A = 4b91:0000(date) + …`, twilight limits
`DS:51D1/51D3`, sunrise/sunset window `DS:1140/1142/113A`, `DS:114C` (night flag), loads the moon
phase bitmap `moonN` (N = phase 1..9 from the sun–moon angle, `7229:01aa`; size `DS:51D7/51D5`),
stores `DS:51CF/51CD` (latitude/tilt of the sky, **Likely**), resets the stars (`59eb:0097`) and runs
`6964:0076`. `55e8:000a` frees the moon bitmap; `55e8:0000` → `59eb:0000`.

`4b91:0000` moon phase: days since a reference epoch (`−24D9B9h`), `4b91:008d`:
`((days << 14) mod 6ECCCh) >> 14` (synodic month 29.53 days in 14-bit fraction) `· 93Fh` → angle.

### 2.2 `6964` per frame (`6964:0076` from the sim step `5440:1317` and `sky_init`)

Every `1900h` units of `DS:711E` (dt) the sun, moon and star angles advance by 4 (`DS:51C5`
countdown; `6964:0000(n)` = skip-ahead by n·256). Then: `DS:114C = |sun| <= DS:51D3` (sky dark
enough for stars/moon); sun and moon directions `DS:51E5..51E9`, `DS:51DF..51E3`; `6964:05d2`
chooses the light direction `DS:51D9..51DD`: the sun when it is up (`6964:05a3(1000h)`), else the
moon when it is above the horizon (4000h < angle < C000h), else a fixed night light
`DS:1144..1148`. `DS:51BE..51C2` = the sun vector rotated by the sky tilt `DS:51CF`
(`6964:005b` returns it while the sun is up, `6964:0633` returns the sun angles).
`6964:064d(a, b)`: `a` when the sun is higher than `DS:51D3`, `b` below `DS:51D1`, linear in between
(`ldiv_sat(|sun − 51D3|·(b − a), 640h)`) — used for the darkness level and glare.
`6964:059b` returns the sun angle.

### 2.3 `6964:01a2` `draw_celestial()` (the sky callback, via stub `3e1d:002a`)

Sets the clip window to the cockpit window (`644a:089f` → `DS:51B6..51BC`, centre
`DS:51B2/51B4`), `DS:26C3 = 1`; if night (`DS:51C4`) `1a9a:000a` stars; `6964:0298(1)` sun,
`6964:0298(0)` moon: direction (`1a9a:01da`), sky tilt, `vec_rotate` by `m_cam`; if in front
(`y > focal`): `x = cx + ldiv_sat(x << S, y)`, `y = cy − …`, kept if within the window ± 7 → flag
40h and position in the record (`DS:111E` sun, `DS:1128` moon). Sun: filled disc radius 7 colour
8Ch (`1d32:6bbc`). Moon (night, flag set, not behind 80h): bitmap `DS:114A` at its position,
rotated by `−roll` when rolled (`1d32:5e5b`), else `1d32:3de5`.

`6964:0458` `sun_glare()` → 0..4000h: 0 if the sun is not on screen or is inside the sunrise window;
else from the distance of the sun to the window centre and the number of the 9 sample pixels around
it that are still colour 8Ch (not covered): `clamp(((3000h − d·3000h/50h)·dark >> 14) − n·1000h/9,
0, 4000h)` (**Likely**); drives palette channel 8.

### 2.4 Stars (`59eb`, `1a9a`)

`59eb:0000` loads the star table (DAT file named through `55a4`, 6-byte records `{u16 flags,
i16 az, i16 alt}`, count `DS:5CE6`, far `DS:5CE8`); `59eb:0097(t)` sets the rotation
`DS:5CE2 = DS:5CE4 = t + DS:51C9·0B3h` and clears flag 80h. `1a9a:000a` (night only): for each star
without flag 80h: direction `1a9a:01da(alt, az + DS:5CE4)` tilted by `DS:51CF`, rotated to the
eye; if `y > focal`: screen y = `atan2_16(...)/75 + cy`, x = `atan2_16(...)/64 + cx` (angular, not
perspective, **Likely**), plotted with `1d32:6a5b` inside the window. `1a9a:01da(out, ang)`:
`ang[0] == 0` → `(−sin a1, 0, −cos a1)`; else `(mul_sin(−cos a0, a1), sin a0, mul_cos(−cos a0, a1))`.

-----------------------------------------------------------------------------------------------

## 3. Palette effects (`51b4` paltrick.c, `51a8`, `1792`, `17ce`)

### 3.1 Block `DS:5BD8` (allocated by `51a8:0000(n = 13, base palette DS:408A)`, 13·25h + 3ACh bytes)

`+0` channels (13), `+2` loaded, `+4` far base palette, `+8` working palette (300h bytes),
`+347h` 64-entry delta table (built by `1792:038a` for the current level), `+387h` channel records
(25h bytes each, read from `pal_maps` by `51b4:0000` via `51a8:004e`): up to 6 `{u16 first, u16 last}`
palette ranges, `+18h` u8 use-own-colour flag, `+19h` target (3 bytes RGB or a palette index),
`+1Ch` target level, `+1Eh` rise speed, `+20h` fall speed, `+22h` u8 active, `+23h` u16 current
level (8.8).

### 3.2 Functions

* `1792:0032(ch, active, level)`: set a channel (level FFFFh = keep; level 0 → inactive).
* `1792:00c0(force)` per frame: each level moves towards its target (`+1Eh`/`+20h` scaled by dt,
  `362b:00be`), or decays when inactive; if any level's high byte changed (or `force`): copy the base
  palette, then for every active channel and range blend each colour component towards the target by
  `level >> 8` (`1792:0286`, per component `c += delta_table[target − c]`, clamped 0..3Fh) and queue
  the DAC upload of 256 colours (`5440:07bd` → `5440:07e1` → `0000:189b`, platform/video).
* `1792:0066`: copy the base palette and queue it unchanged; `1792:009b` reset all levels;
  `1792:0000(ch)` current level; `1792:0021(far p)` set the base palette pointer.
* `51b4:0088` `palette_effects_init()`: channel 0 off, 9 = 4000h, 10 = 3800h, 5/8/11 off, 6/7/12 keep;
  `DS:5BDB = 70h`, `DS:5BDD = 80h`, `DS:0320 = 1`, other sky flags reset, `DS:5798 = 0`.
* `17ce:0013` per frame (from `5440:018c`): channel 11 = `DS:5798` (blackout/redout from `0fd4`,
  sim_world); on overcast change resets the sky colours; darkness `d = 6964:064d(0, 2280h)`:
  channel 0 = d, 4 = d/2, 9/10 = sunlight `4000h − d·4000h/2280h`, 1 (clear) or 2/3 (overcast) =
  dusk tint; under an overcast: altitude bands around z 16000 (`< 34BCh`, `< 4845h`, above) set
  channel 5 (cloud-layer fog, level `(9C4h − |16000 − z|)·8` capped 3D00h), `DS:5BDA`, sky base 61h
  below / ground 70h above, `DS:0320`; channel 6 = inside a cloud (`DS:5BE5`); channel 7 = 1000h
  while `490a:017f` reports a cloud flag; channel 8 = sun glare (`6964:0458`) unless in cloud/fog;
  then `1792:00c0(0)`. `17ce:0008` forces a recompute (`DS:5BE6 = FFFFh`).

The polygon colour remap (`camera+14h` / `CS:21EE`) is **never set** by this code: all night, haze and
fog effects are palette changes, not remaps (the remap pointer stays 0 in the sim).

-----------------------------------------------------------------------------------------------

## 4. Effects drawn from the sky/scene code

* `1a8b` shadows: `1a8b:0004` defaults (`DS:5CE0` LOD cap 2, `DS:5CDE` 10, range `DS:5CDA` 3000);
  `1a8b:001e(v)`: range `v·300`, cap 3 if `v > 13` else 0 (off) — from the detail slider;
  `1a8b:004c` per frame: for each live aircraft (`637f:002b`) below the range altitude with a
  ground point (`2ecb:0007`) spawn a type `80Bh` effect record into the `05a9` pool (drawn by
  `5440:0269` as `shadow_draw`). The shadow colour `DS:2402` is not set anywhere (stays 0 = black).
* `675d:0000` ground speed dots (view below altitude 4000): 9×9 grid of points on the ground at
  1024-unit spacing aligned to the eye position, rotated to the eye, projected
  (`ldiv_sat(x << S, y)`), and plotted inside the cockpit window only over pixels whose colour is
  < 88h, in the darker colour `DS:102E[pixel]` (`1d32:6a29` read, `1d32:6a5b` write).
* `655d:038a` gun/engine flashes: per live aircraft and gun group, spawns type `80Eh` effect
  records (shapes `DS:474D + 15h..17h`) at the gun positions (gun data sim_world).

## Port notes

* `/* PORT: */` The DAC upload becomes a palette update of the SDL surface; keep the per-frame channel
  arithmetic, since fog, night and flashes are only palette changes.
* Enhanced renderer: the horizon is a flat plane with coloured bands; at higher resolutions keep the
  same colour indices and band counts (or interpolate) for the look.

## Hand-offs

* **video**: `1d32:09a8` span fill (entry 27), `1d32:6ab0` rectangle, `1d32:6bbc` disc, `1d32:5e5b`
  rotated bitmap, `1d32:3de5` bitmap, `1d32:6a29`/`6a5b` pixel read/write.
* **platform/video**: DAC queue `5440:07bd` / `0000:189b`.
* **sim_flow**: `4e0d:03e9` calls `sky_init`; `644a:089f` window; `4b9f` slider → `4d6e:0000`,
  `1a8b:001e`; `5440:1317` calls `6964:0076`.
* **sim_world**: `490a:017f` cloud flag, `0fd4` blackout level `DS:5798`, `655d` gun data.

## Open questions

* Exact band geometry of `4d6e:03be/0724` (decompile only); meaning of `DS:51CF/51CD` (latitude?).
* Star projection formula (`/75`, `/64` angular scaling) needs a disassembly check.
