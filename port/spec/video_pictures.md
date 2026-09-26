# video — part `pictures`: bitmap kinds, the VQT decoders, bitmap drawing, the PS snapshot writer

Scope: how the loaded pictures are **decoded and drawn**: the three VQT quadtree decoders (sprite
drawer with flips, full-screen decoder, "to memory" pre-decoder), the per-kind bitmap draw
dispatcher, the nibble-plane pixel order (settled from the code), and the PS `SNAPSHOT.LBM`
(IFF ILBM) writer. The **loaders** (`bmp_load` `0ead`/`3922`/`6f97`, `bmp_info_*`, `vqt_predecode`
`0ef8`/`396d`/`6fe3`, `bmp_to_scn` (the RLE→SCN re-encoder), `bmp_load_planes` `05da:5001`,
`scr_load` `0f35`/`39aa`/`6f83`, `scr_load_planes` `05da:54ae`, `amiga_to_nibbles` `05da:540f`,
`bmp_free`/`bmp_free_table`/`bmp_count` `05da:53c1`/`539d`/`53ef`) and the chunk / packed-stream
layer are specified in `platform.md` §7 and `platform_resources.md` §6 and are **not repeated**
here. Driver entries are in `video.md` §3, the SCN sprite drawer and the plain/opaque sprite thunks
in `video_library.md` §1 and §7, the tile-map (MTX) drawing in `video_ttm.md` §12.1.

Addresses `SSSS:OOOO` (AP = `work/AP_flat.exe`), DS offsets per exe. Confidence: everything below
is **verified** (read instruction by instruction in the INTRO copy; the PS and AP copies were
compared instruction by instruction with the INTRO one — they differ only in DS offsets and
relocated segments) unless tagged **likely**/**guess**.

## Index

1. Bitmap kinds and how each is drawn
2. Nibble planes: pixel order (settled)
3. The VQT bit reader and decoder context
4. Sprite decoder (kind −1 at draw time, with flips) — INTRO `0dc5`, PS `383a`, AP `6f1c`
5. Screen decoder (`SCR:VQT:`) and memory decoder (`vqt_predecode`) — INTRO `0e2c`, PS `38a1`, AP `2651`
6. `bmp_draw` / `bmp_free` wrappers — INTRO `0f2c`, PS `39a1`, AP `26d2`
7. PS screenshot `SNAPSHOT.LBM` — PS `3a13`, `0000:032c`, `0000:167b`, `0000:1692`
8. Globals (DS offsets per exe)
9. Port notes
10. Hand-offs
11. Open questions / corrections

---

## 1. Bitmap kinds and how each is drawn

Frame record (10 bytes; `platform.md` §7.1): `+0` pixel segment, `+2` pixel offset, `+4` kind,
`+6` width, `+8` height. A bitmap is a near, zero-terminated array of near frame pointers.

| `+4` kind | Produced by | Pixel data | Drawn by `bmp_draw` (§6) |
|---|---|---|---|
| −1 (FFFF) | `bmp_load`, `BMP:OFF:` with an explicit offset list | VQT bit stream, decoded **every time it is drawn** | `vqt_draw(fr, x, y, flip)` §4 (transparent 0, flips, clipped) |
| −2 (FFFE) | `BMP:SCN:`, or `BMP:RLE:` re-encoded by `bmp_to_scn` | SCN run/skip lines (resources.md §4c) | `gfx_sprite_scn(fr, x, y, flip)` INTRO `05da:1e38` / PS `16e3:244c` / AP `1d32:4286` (`video_library.md` §7.4) |
| −3 (FFFD) | any bitmap with a `BMP:SCL:` chunk | raw 8-bit (whatever the earlier steps produced) | `gfx_sprite_opaque(fr, x, y)` = driver entry 33 (`05da:06e9` / `16e3:063b` / `1d32:3de9`): **opaque, flip ignored** |
| −4 (FFFC) | `BMP:OFF:` = `FFFF` (sequential VQT) → `vqt_predecode` (§5.3) | raw 8-bit, row-major, `w·h` bytes | `gfx_sprite_flip(fr, x, y, flip)` = driver entry 29 (`05da:06e5` / `16e3:0637` / `1d32:3de5`): transparent 0 |
| 0 | nibble planes `BIN:`(+`VGA:`) via driver entries 13/14/15 (`platform.md` §7.4; entry 14 writes `+0/+2` only, `+4` stays 0 from `calloc`) | raw 8-bit, row-major | entry 29 as above |

Screens (`SCR:`) have no object: `scr_load` decodes straight into the **current write page**
`drv[18]` (VQT: §5.2 with driver entry 22; nibble planes: driver entries 17/18 per band, entry 18
ORs the high nibbles into the write page). This answers the TTM hand-off: `F01F` LOAD_SCR draws
into the write page, which the TTM interpreter has set to the back page (`video_ttm.md` §5).

## 2. Nibble planes: pixel order (settled)

Conflict: `video.md` §3.11 (driver entries 14/15) said "first pixel = high nibble", `resources.md`
§4a says "first pixel in the **low** nibble" for `BIN:`/`VGA:`.

**Settled: the first (left) pixel of each byte is in the high nibble**, for bitmaps and for
screens:

* Driver entry 14 (`OVL:VGA:` `0D09`, unpack loop `0DBB–0DFD`): `al = b >> 4`, `ah = b & 0Fh`,
  `mov es:[di], ax` → `buf[2k] = b >> 4`, `buf[2k+1] = b & 0Fh`. Entry 15 (`0E04`) merges
  `dst[2k] |= src[k] & F0h`, `dst[2k+1] |= (src[k] & 0Fh) << 4`. So `pixel[2k] = (bin[k] >> 4) | (vga[k] & F0h)`,
  `pixel[2k+1] = (bin[k] & 0Fh) | ((vga[k] & 0Fh) << 4)`.
* Driver entries 17/18 (screens, `video.md` §3.12): byte b0 → pixels 0 (high nibble) and 1 (low
  nibble).
* Data check (scratch `pictures/nibcheck.py`, horizontal-smoothness test over all 77 `BIN:`
  bitmaps/screens of the shipped volumes): high-nibble-first gives the smoother image in **77 of
  77** files (e.g. `DEMO.SCR` 20 646 vs 26 378 horizontal colour changes).

`resources.md` §4a is wrong on this point (hand-off to the formats owner, §10).

## 3. The VQT bit reader and decoder context

The stream format is `resources.md` §4b. All three decoders share one bit-reader convention.

**Context** (pointer in `vqt_ctx` INTRO `DS:328E` / PS `7572` / AP `6462`):

| Off | Type | Meaning |
|---|---|---|
| +00 | u32 | bit position (from the start of the stream) |
| +04 | far (off, seg) | stream start (normalised, offset < 16) |
| +08 + 4k | far (off, seg), k = 0..3 | destination pointers (memory decoder only; **only k = 0 is used** by the decoder: the frame's 8-bit pixel block) |
| +18 | u16[h] | row offsets `rowtab[y] = y·w` (memory decoder only) |

The sprite/screen decoders use the static context `vqt_ctx0` INTRO `DS:3290` / PS `7574` / AP
`6464` (8 bytes used), created by `vqt_begin`; the memory decoder uses a 1CAh-byte context on
`vqt_predecode`'s stack (room for 217 row offsets).

**`bits(n)`** — INTRO `0e2c:0007` / PS `38a1:0007` / AP `2651:0006` (far, arg n; also inlined in
the screen/memory decoders with the same arithmetic):

```
mask = ((0xFF00 rol n) & 0x00FF)            // (1<<n)-1 for n = 0..8; n = 0 → 0
p    = ctx.bitpos; ctx.bitpos += n           // 32-bit
w    = *(u16 far *)(ctx.src.seg : (u16)(ctx.src.off + (u16)(p >> 3)))   // offset wraps at 64 KB
return (w >> (p & 7)) & mask
```

Quirk: the byte offset `p >> 3` is truncated to 16 bits and added to the offset only (no segment
carry), so a stream is limited to 64 KB − 16 (all shipped VQT frames/screens are smaller; the
largest `SCR:VQT:` is < 64 000 bytes — **likely**, not measured). The inline copies read 8-bit
values without masking (`shr ax, cl` then use `al`).

**`vqt_begin(far p)`** — INTRO `0dc5:000a` / PS `383a:000a` / AP `6f1c:0000`: if `vqt_busy`
(`DS:32A4` / `7588` / `6478`) ≠ 0 → return 0; `vqt_busy = 1`; `vqt_ctx0.src = p`,
`vqt_ctx0.bitpos = 0`; return `&vqt_ctx0` (the callers store it in `vqt_ctx`).
**`vqt_end()`** — `0dc5:003e` / `383a:003e` / `6f1c:0034`: `vqt_busy = 0`.

## 4. Sprite decoder (kind −1, drawn at run time)

### 4.1 INTRO `0dc5:0049` / PS `383a:0049` / AP `6f1c:003f` — `vqt_draw(frame *fr, int x, int y, int flip)`

1. Save `drv[0E]`, `drv[0D]`, `drv[03]` (bytes).
2. `p = (fr.seg + (fr.off >> 4)) : (fr.off & 0Fh)`; `vqt_ctx = vqt_begin(p)`; 0 → go to 7.
3. `w = fr+6`, `h = fr+8`. If `x >= drv[04]` and `y >= drv[08]` and `x + w <= drv[06]` and
   `y + h <= drv[0A]` (signed; note `<=` against the inclusive x2/y2, i.e. one pixel stricter than
   necessary): `vqt_putpix` = the driver's `put_pixel` (the far pointer of entry 22, INTRO
   `[DS:1990]`, PS `[31CC]`, AP `[3572]`: unclipped). Else `vqt_putpix = gfx_pixel` (INTRO
   `05da:48fd`, PS `16e3:4c21`, AP `1d32:6a5b`: clipped when `drv[03]`) and **`drv[03] = 1`**.
   (The clip rectangle `drv[04..0A]` is used as is, even if clipping was off.)
4. `vqt_draw_zero = 0` (zero pixels are transparent); `vqt_flip = flip`.
5. `vqt_root(x, y, w, h)` (§4.2).
6. `vqt_end()`.
7. Restore `drv[03]`, `drv[0E]`, `drv[0D]`.

### 4.2 INTRO `0dc5:0149` / PS `383a:0149` / AP `6f1c:013f` — `vqt_root(x, y, w, h)`

`vqt_hflip = (vqt_flip & 2) != 0`; `vqt_vflip = (vqt_flip & 1) != 0`. Select the flipped leaf
filler `vqt_fill_fn` (far pointer, `DS:328A/328C`):

| hflip | vflip | `vqt_fill_fn` |
|---|---|---|
| 1 | 1 | `vqt_fill_hv` `0dc5:03f6` |
| 1 | 0 | `vqt_fill_h` `0dc5:035e` |
| 0 | 1 | `vqt_fill_v` `0dc5:03aa` |
| 0 | 0 | null |

Save `drv[0C]`; `drv[0C] = 1` (filled rectangles); `vqt_node(x, y, w, h)`; restore `drv[0C]`.
(Flip bit meanings as for every sprite routine: 1 = vertical (bottom-up), 2 = horizontal.)

### 4.3 INTRO `0dc5:01ef` / PS `383a:01ef` / AP `6f1c:01e5` — `vqt_node(x, y, w, h)` (recursive)

```
if w == 0 or h == 0: return                  // NB: the screen/memory decoders only return if BOTH are 0 (§5)
wl = w >> 1; wr = (w + 1) >> 1; ht = h >> 1; hb = (h + 1) >> 1      // sar (signed)
offL = 0;  offR = wl;  offT = 0;  offB = ht
if vqt_hflip: offL = wr; offR = 0
if vqt_vflip: offT = hb; offB = 0
m = vqt_bits(4)                              // through the far pointer vqt_bits_fn
(m & 8 ? vqt_node : vqt_leaf)(x + offL, y + offT, wl, ht)      // stream quadrant TL
(m & 4 ? vqt_node : vqt_leaf)(x + offR, y + offT, wr, ht)      // TR
(m & 2 ? vqt_node : vqt_leaf)(x + offL, y + offB, wl, hb)      // BL
(m & 1 ? vqt_node : vqt_leaf)(x + offR, y + offB, wr, hb)      // BR
```

The quadrants keep their stream order and sizes; with a flip, the left/right (top/bottom)
quadrants swap screen positions, and each leaf mirrors its own pixel order (§4.5), which
together mirror the whole frame.

`vqt_bits_fn` (INTRO `DS:1ADA`, PS `34A6`, AP `2244`; far, initialised to `bits` §3, never
changed) is how this decoder reads bits, except where noted below.

### 4.4 INTRO `0dc5:0445` / PS `383a:0445` / AP `6f1c:043b` — `vqt_leaf(x, y, w, h)` (near)

```
if w == 0 or h == 0: return
if w == 1 and h == 1:
    v = vqt_bits_fn(8)
    if v or vqt_draw_zero: vqt_putpix(x, y, v)
    return
size = w * h                                 // u16 × u16 → u32
b1 = size >= 256 ? 8 : (size == 1 ? 0 : bitlen((u8)(size - 1)))
k  = vqt_bits_fn(b1) & 0xFF
vqt_nbits = bitlen(k)                        // 0 for k = 0            (DS:3288)
ncol = k + 1                                 // 16-bit: 1..256
if size*8 <= size*vqt_nbits + ncol*8:        // 32-bit unsigned compare → RAW
    if vqt_fill_fn:                          // flipped
        vqt_nbits = 8; vqt_src_fn = vqt_bits_fn
        vqt_fill_fn(x, y, x + w, y + h)
    else:
        for i in x .. x+w-1:                 // column-major: x outer, y inner
            for j in y .. y+h-1:
                v = bits(8)                  // direct call of 0e2c:0007, not the pointer
                if v: gfx_pixel(i, j, v)     // direct call of 05da:48fd (always the clipped one)
elif ncol == 1:                              // FILL
    v = vqt_bits_fn(8); drv[0D] = drv[0E] = v
    if v or vqt_draw_zero: vqt_rect_fn(x, y, w, h)   // DS:1AD2 = gfx_rect 05da:645b (filled: drv[0C] = 1)
else:                                        // TABLE
    for n in 0..ncol-1: tab[n] = vqt_bits_fn(8)     // 256-byte table on the stack; vqt_tab (DS:32A6) = &tab
    if vqt_fill_fn:
        vqt_src_fn = vqt_tab_read (0dc5:0130)
        vqt_fill_fn(x, y, x + w, y + h)
    else:
        for i in x .. x+w-1: for j in y .. y+h-1:
            v = tab[bits(vqt_nbits)]         // direct call of 0e2c:0007
            if v: gfx_pixel(i, j, v)
```

Notes: in the un-flipped RAW/TABLE paths the pixel writer is always the clipped `gfx_pixel`
(`vqt_putpix` from §4.1 is only used by 1×1 leaves and the flipped fillers); the result is the
same because `gfx_pixel` = `put_pixel` inside the clip window. A FILL leaf draws with `gfx_rect`
(colour `drv[0D]`, filled), which clips when `drv[03]` is on and is opaque except that colour 0
is skipped by the `v != 0` test. A pixel value 0 is never drawn (`vqt_draw_zero` is always 0).
`gfx_rect` for FILL leaves leaves `drv[0D]/[0E]` changed until §4.1 step 7 restores them.

### 4.5 Flipped leaf fillers — `(x0, y0, x1, y1)`, ends exclusive

Each pixel: `v = vqt_src_fn(vqt_nbits)`; if `v || vqt_draw_zero`: `vqt_putpix(col, row, v)`.
The loops read the stream in its normal (column-major) order but place the pixels mirrored:

| Function (INTRO / PS / AP) | outer (columns) | inner (rows) |
|---|---|---|
| `vqt_fill_h` `0dc5:035e` / `383a:035e` / `6f1c:0354` | `col = x1−1` down to `x0` | `row = y0` up to `y1−1` |
| `vqt_fill_v` `0dc5:03aa` / `383a:03aa` / `6f1c:03a0` | `col = x0` up to `x1−1` | `row = y1−1` down to `y0` |
| `vqt_fill_hv` `0dc5:03f6` / `383a:03f6` / `6f1c:03ec` | `col = x1−1` down to `x0` | `row = y1−1` down to `y0` |

`vqt_tab_read(n)` INTRO `0dc5:0130` / PS `383a:0130` / AP `6f1c:0126`: `return
vqt_tab[vqt_bits_fn(n) & 0xFF]`.

## 5. Screen decoder and memory decoder

Two more copies of the quadtree decoder, same recursion, bit reader inlined. They differ from
§4 in these points (all verified):

* **Node** returns only if `w == 0 && h == 0` (`or si, di`), so a node child of width 0 and
  height ≥ 1 still reads its 4 mask bits and recurses. Shifts are unsigned (`shr`). Quadrants:
  TL `(x, y, w>>1, h>>1)`, TR `(x + (w>>1), y, (w+1)>>1, h>>1)`, BL `(x, y + (h>>1), w>>1,
  (h+1)>>1)`, BR `(x + (w>>1), y + (h>>1), (w+1)>>1, (h+1)>>1)`, mask bits 8/4/2/1. No flips.
* **Leaf** returns if `h == 0` or `w == 0`; 1×1 → one `bits(8)` pixel.
* `size = (u8)w * (u8)h` (**8×8-bit multiply**, 16-bit result); `b1 = 8` if `size >= 256`, else
  `bitlen((u8)(size−1))` with a minimum of 1.
* `k = bits(b1)`, `nb = bitlen(k)`, **`ncol = (u8)(k + 1)`** (k = 255 → ncol byte 0).
* RAW iff `!(size*8 > size*nb + ncol*8)` with **16-bit** arithmetic (products truncated; for
  leaves of ≥ 8192 pixels this differs from the 32-bit test of §4.4 — faithful ports must use the
  16-bit form here and the 32-bit form in §4).
* FILL iff `ncol == 1` (byte compare); TABLE reads `ncol` entries with a byte counter (`ncol` byte
  0 → 256 entries).
* Pixels, column-major (x outer, y inner), **opaque (0 is written too)**.

For the shipped data the two forms agree (the decoders produce the same images — **likely**; the
data never needs the corner cases: widths/heights ≤ 320×200, the encoder does not emit node bits
for empty quadrants — **guess**).

### 5.1 Node functions

`vqt_mem_node(x, y, w, h)` INTRO `0e2c:004e` / PS `38a1:004e` / AP `2651:004d` and
`vqt_scr_node(x, y, w, h)` INTRO `0e2c:0461` / PS `38a1:0461` / AP `2651:0460` — identical code
(only the callees differ): children are `vqt_mem_node`/`vqt_mem_leaf` resp.
`vqt_scr_node`/`vqt_scr_leaf`.

### 5.2 INTRO `0e2c:056b` / PS `38a1:056b` / AP `2651:056a` — `vqt_scr_leaf(x, y, w, h)`

Writes to the **write page** `drv[18]`:
* pixel: driver entry 22 `put_pixel(x, y, v)` through `[DS:1990]` (PS `31CC`, AP `3572`) —
  **unclipped**;
* FILL: for each of the h rows: `ES = drv[18]`, `DI = rowtab_drv[y] + …` (driver row table
  `drv[6F2]`: INTRO `DS:1172`, PS `29F2`, AP `2DB2`), `BX = x`, `CX = w`, `AL = AH = v`, call driver
  entry 10 (`hspan`, `[DS:1960]` / PS `[319C]` / AP `[3542]`); `DI += 80` per row. Opaque.

Called from `scr_load` (`platform.md` §7.5) as `vqt_scr_node(0, 0, 320, 200)` after `vqt_begin`.

### 5.3 INTRO `0e2c:0155` / PS `38a1:0155` / AP `2651:0154` — `vqt_mem_leaf(x, y, w, h)`

Writes `ctx.dst0[ctx.rowtab[y] + x] = v` (far pointer +08 of the context, offset add without
carry — the frame block is normalised so this stays inside 64 KB for frames ≤ 65 520 pixels).
FILL writes the rectangle row by row. Used by `vqt_predecode` (INTRO `0ef8:000e`, `platform.md`
§7.2), which sets up the context per frame (dst0 = frame pixels, `rowtab[y] = y·w`) and calls
`vqt_mem_node(0, 0, w, h)`; the result is a kind −4 raw frame.

`far_copy(dst, src, n)` INTRO `0e2c:0446` / PS `38a1:0446` / AP `2651:0445`: `rep movsw` of
`n>>1` words + 1 byte if n odd (not overlap-safe); used by `vqt_predecode` to move the unread
tail of its input buffer down.

## 6. `bmp_draw` / `bmp_free` wrappers

* INTRO `0f2c:0032` / PS `39a1:0032` / AP `26d2:0031` — `bmp_draw(frame *fr, int x, int y, int
  flip)`: switch on `fr+4`: −3 → `gfx_sprite_opaque(fr, x, y)`; −2 → `gfx_sprite_scn(fr, x, y,
  flip)`; −1 → `vqt_draw(fr, x, y, flip)`; anything else → `gfx_sprite_flip(fr, x, y, flip)`
  (§1 table). Callers: TTM draw dispatch and scroller (`video_ttm.md` §7.1, §12.2); AP also the
  cockpit/map code `678a:*` (sim_flow/render3d).
* INTRO `0f2c:0002` / PS `39a1:0002` / AP `26d2:0001` — `bmp_free_w(bmp)`: calls `bmp_free`
  (INTRO `05da:53c1`, PS `168a:04b1`, AP `7229:056a`; `platform.md` §7.1).
* INTRO `0f2c:0010` / PS `39a1:0010` / AP `26d2:000f` — `bmp_count` (platform-owned row).

## 7. PS screenshot — `SNAPSHOT.LBM`

Hot key Alt+T / Ctrl+T in the PS menus (`2e25:0419`, shell_ui_toolkit).

* PS `0000:032c` — `snapshot()`: saves `drv[16]` (`DS:2316`), sets the read page `drv[16] =
  drv[14]` (front page, `DS:2314`), `snap_save("SNAPSHOT.LBM")` (`DS:2188`), restores `drv[16]`.
* PS `3a13:031e` — `snap_save(name)`: saves `drv[18]` (`DS:2318`) and `drv[03]` (`DS:2303`);
  `drv[03] = 0`; `drv[18] = drv[16]`; `ilbm_write(name)`; restores both.
* PS `3a13:01af` — `ilbm_write(name)`: `f = fopen(name, "wb")` (`DS:35A5`), fail → return. Writes
  (all multi-byte values big-endian through `put_be`):
  `"FORM"`, u32 `0000FD30h` (64 816), `"ILBM"`, `"BMHD"`, u32 20, u16 320, u16 200, u32 0
  (x, y), u32 `08000000h` (nPlanes 8, masking 0, compression 0, pad 0), u32 `00000101h`
  (transparent colour 0, xAspect 1, yAspect 1), u16 320, u16 200 (page size); then
  `ilbm_cmap(f)`, `ilbm_body(f)`; `fclose(f)`. Strings at `DS:358C` `"FORM"`, `3591 "ILBM"`,
  `3596 "BMHD"`, `359B "CMAP"`, `35A0 "BODY"`.
* PS `3a13:0078` — `ilbm_cmap(f)`: `"CMAP"`, u32 768; `dac_read_block(buf, 0, 256)`
  (`0000:167b`: INT 10h AX=1017h, ES:DX = buf, BX = first, CX = count — reads the **hardware DAC**);
  every byte `<<= 2` (6 → 8 bit); `fwrite(buf, 768, 1, f)`.
* PS `3a13:00fa` — `ilbm_body(f)`: `"BODY"`, u32 64 000; `row = malloc(640)`; for y = 0..199:
  `row[x] = gfx_get_pixel(x, y)` (`16e3:4bef`, reads the read page = front, unclipped since
  `drv[03] = 0`) for x = 0..319; `c2p_row(row, row + 320)`; `fwrite(row + 320, 320, 1, f)`;
  `free(row)`. Uncompressed, 8 interleaved bit-planes per line.
* PS `0000:1692` — `c2p_row(src, dst)` (asm): for each of 40 groups g of 8 pixels, plane p
  (0..7) byte `dst[p·40 + g]` = bit p of pixels `8g … 8g+7`, first pixel in bit 7.
* PS `3a13:0000` — `put_be(ptr, n, size, f)`: n items; size 4 → `put_be(ptr+2, 1, 2, f)`,
  `put_be(ptr, 1, 2, f)`; size 2 → `fwrite(ptr+1, 1, 1)`, `fwrite(ptr, 1, 1)`; size 1 →
  `fwrite(ptr, 1, 1)`; `ptr += size`.

`/* PORT: */` INT 10h/1017h reads the DAC; the port returns its emulated DAC (the current
palette as uploaded), which is what the original captures. INTRO and AP have no snapshot (AP's
`565f:022a` screenshot palette is in `video_palette.md` §8.6 — the AP writer itself is sim_flow's).

## 8. Globals (DS offsets per exe)

| INTRO | PS | AP | Name | Meaning |
|---|---|---|---|---|
| `3286` b | `756A` | `645A` | vqt_draw_zero | 0 = pixel value 0 transparent (always 0) |
| `3288` | `756C` | `645C` | vqt_nbits | bits per pixel index of the current leaf |
| `328A` far | `756E` | `645E` | vqt_fill_fn | flipped leaf filler or null |
| `328E` | `7572` | `6462` | vqt_ctx | near pointer to the decoder context |
| `3290` 8 B | `7574` | `6464` | vqt_ctx0 | static context (bitpos u32, src far) |
| `329A` | `757E` | `646E` | vqt_hflip | |
| `329C` | `7580` | `6470` | vqt_vflip | |
| `329E` far | `7582` | `6472` | vqt_src_fn | value source of the flipped fillers |
| `32A2` | `7586` | `6476` | vqt_flip | flip argument |
| `32A4` | `7588` | `6478` | vqt_busy | set by `vqt_begin` |
| `32A6` | `758A` | `647A` | vqt_tab | near pointer to the leaf colour table |
| `1AD2` far = `05da:645b` | `349E` = `16e3:61b5` | `223C` = `1d32:6ab0` | vqt_rect_fn | `gfx_rect` |
| `1AD6` far = `05da:48fd` | `34A2` = `16e3:4c21` | `2240` = `1d32:6a5b` | vqt_putpix | `gfx_pixel` or entry 22 |
| `1ADA` far = `0e2c:0007` | `34A6` = `38a1:0007` | `2244` = `2651:0006` | vqt_bits_fn | `bits` |

PS snapshot: `DS:2188` `"SNAPSHOT.LBM"`, `DS:358C–35A7` IFF tags and `"wb"`.

## 9. Port notes

* Decode VQT exactly as specified, including the two different leaf tests (§4.4 32-bit / §5
  16-bit), the "return if either dimension is 0" rule of the sprite node vs "both" in the others,
  the `(u8)w * (u8)h` product and the byte `ncol` of §5. The shipped data may never hit the
  differences, but they are cheap to keep.
* `vqt_draw` draws per pixel through `gfx_pixel`/`put_pixel`/`gfx_rect`; the port may render
  a decoded frame with a transparent blit only if it reproduces: clipping to `drv[04..0A]`, value
  0 transparent, FILL leaves drawn by `gfx_rect` (same pixels), flips per §4.3/§4.5.
* Kind −1 frames are decoded at every draw in the original (CPU cost only); a port may cache the
  decoded pixels (the stream is immutable) — `/* PORT: */` optional.
* The 64 KB offset wrap of the bit reader (§3) need not be emulated if streams stay < 64 KB
  (assert it at load time).

## 10. Hand-offs

* **formats / platform (resources.md §4a)**: nibble planes are **high nibble first** (§2) — the
  `resources.md` statement "first pixel in the low nibble" is wrong; 77/77 files confirm the code.
  Also `resources.md` §4b: `ncol = (k+1) & FF` holds for the screen/memory decoders only; the
  sprite decoder uses `k + 1` (up to 256) and a 32-bit RAW test (§4.4, §5).
* **platform**: `platform.md` §7.5 "`vqt_quad(0,0,320,200)` 0e2c:0461" = `vqt_scr_node` here;
  `0e2c:004e` = `vqt_mem_node`; kind −3 frames are drawn **opaque by driver entry 33** (so a
  `BMP:SCL:` bitmap must hold raw pixels).
* **shell_ui**: PS Alt/Ctrl+T writes `SNAPSHOT.LBM` of the front page and the hardware DAC (§7).
* **sim_flow / render3d (AP `678a:*`)**: `bmp_draw` 26d2:0031 semantics per kind (§6).

## 11. Open questions / corrections

* Corrected: `video.md` §3.11's pending reconciliation — settled high-nibble-first (§2).
* Whether any shipped VQT leaf reaches ≥ 8192 pixels with a palette (where the 16- and 32-bit
  RAW tests could disagree) — not measured.
* Whether the encoder ever emits a node bit for an empty quadrant (would desynchronise the
  sprite decoder vs the others) — not measured (**guess**: no).
