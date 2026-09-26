# video — VGA driver, pages, graphics library, pictures, palettes, TTM

Phase 3 spec of the **video** module (see `port/spec/README.md`): the VGA320 driver loaded from
`VMCODE.OVL`/`VMCODE2.OVL` (all 50 jump-table entries), the driver/library shared variable block,
pages and flipping, the graphics library of the Dynamix system library (INTRO `05da`, PS `16e3`,
AP `1d32`), fonts and text, and — in part files — palettes, picture loaders, the TTM player and the
PS `ts_*` shape library. Conventions as `port/RE_GUIDE.md` (`SSSS:OOOO` file segments, `DS:xxxx`
DGROUP offsets; AP = `work/AP_flat.exe`). Confidence: **verified** = read instruction by
instruction; **likely**; **guess**. Unless marked, everything here is verified.

## Index

| File | Contents |
|---|---|
| `video.md` (this file) | §1 overview and the port model · §2 driver loading, `gfx_init`, the shared block · §3 the 50 driver entries · §4 pages: who draws where, flipping, vsync · §5 `-ph` "hivga" · §6 port notes · §7 hand-offs · §8 open questions |
| `video_library.md` | the graphics library on top of the driver: clipping, pixels, lines, rectangles, circles, polygons (clip + edge walk + span fill), flood fill, rectangle copies, sprites (plain / flipped / opaque / cached / scaled / SCN), fonts and text |
| `video_palette.md` | palette load/slots, DAC, fades, colour cycling, the INTRO VGA-register effect `103d`, AP DAC code |
| `video_pictures.md` | BMP / SCR loaders and decoders (BIN+VGA nibble planes, VQT, SCN, RLE, MTX, IFF ILBM) |
| `video_ttm.md` | the TTM animation player (INTRO `1125`/`11d2`, PS `3b02`/`3baf`, AP `24fc`/`2595`) |
| `video_ts.md` | the `ts_*` 3Space shape library as used by the shell (PS `4708`–`4960`), AP matches |
| `video_rotate.md` | the rotated-sprite renderer `gfx_sprite_rotated` (INTRO `05da:3d01`) |
| `video_symbols.csv` | names (all three programs) |

-----------------------------------------------------------------------------------------------

## 1. Overview

### 1.1 Layers

```
game code (TTM player, shell screens, sim)                 C, far calls
  │  writes the shared variables directly (colours, clip, read/write page)
  ▼
graphics library  INTRO 05da / PS 16e3 / AP 1d32             C + asm (medium model)
  │  lcall [DS:tab + 4n]   (n = 0..49)
  ▼
VGA driver  (OVL:VGA:, 9424 bytes, loaded at run time)       asm, own DS = caller DGROUP + base/16
  ▼
VGA hardware: unchained 256-colour 320×200, 3 pages + a bitmap cache in video memory
```

The driver is data-driven by a **shared variable block** that lives in the caller's DGROUP
(§2.3): the library and the game write colours, clip rectangle and the read/write page segments
straight into it; the driver reads them.

### 1.2 Video memory layout (verified, driver init `0000`, entries 8/30/31)

Unchained mode ("mode X" layout at 200 lines): each planar byte address holds 4 horizontally
adjacent pixels, one per plane; pixel `(x, y)` of a page at segment `S` = plane `x & 3`, offset
`y*80 + (x >> 2)` from `S:0`.

| Segment | Size | Role (initial) | Driver var |
|---|---|---|---|
| `A000` | 16 000 bytes used of 16 K | page 0, **front** (displayed) | `drv[14]` |
| `A400` | 16 K | page 1, **back** | `drv[12]` |
| `A800` | 16 K | page 2, **background** ("third page") | `drv[10]` |
| `AC00` | 16 K = 64 000 pixels | **bitmap cache** for entries 30/31 (pre-planarised sprites copied with latches) | cs:`1FCA` = next free offset |

`drv[16]` = **read page** segment (source of get-pixel, get-rect, rectangle copies, flood-fill
reads), `drv[18]` = **write page** segment (target of every drawing entry). The game selects them by
copying one of `drv[10]/[12]/[14]` into them. Page flip (entry 8) swaps `drv[12]` and `drv[14]` and
points the CRTC at the new front page.

### 1.3 Port model (decision, see §6)

Four linear 320×200 byte buffers (pages A000/A400/A800 + the AC00 cache as a linear pixel
store) addressed by the page *segment value* so that `drv[10..18]` keep their original values in
`mem[]`; every driver entry is reimplemented in C on these buffers with the exact pixel results
of §3, including the plane-dependent effects (latch copies move whole 4-pixel columns; the
cache stores bitmaps per plane). The host presents the page whose segment is in `drv[14]` (via the
emulated CRTC start address) with the current DAC palette.

-----------------------------------------------------------------------------------------------

## 2. Driver loading and initialisation

### 2.1 Adapter codes and the OVL chunk (verified)

`gfx_load_driver(code, name)` (INTRO `05da:4933`, PS `16e3:4c57`, AP `70ff:0000`) maps the
adapter code to a chunk tag through the table at INTRO `DS:187D` (PS `DS:30E1`) and reads chunk
`"OVL:" + tag` of the file `name` (`vmcode.ovl` in INTRO/PS, `vmcode2.ovl` in AP) through the
volume/chunk helpers (platform), unpacks it into a DOS block (previous block at `DS:1876` freed,
new far pointer stored at `DS:1876/1878`) and returns its far address (0 on failure).

| code | tag | notes |
|---|---|---|
| 1 | `CGA:` | also used for 4 = Hercules: code 4 → 1 with `DS:116A` (screen width) = 640 |
| 2 | `EGA:` | |
| 3 | `TAN:` | |
| 4 | `HER:` | → `CGA:` (above) |
| 5 | `MCG:` | |
| 7 | `EVA:` | |
| **8** | **`VGA:`** | the only path the port needs |
| 9 | `EVG:` | |
| 10 | `HVG:` | "hivga" — **no `HVG:` chunk is shipped** (§5) |
| 11 | `HEG:` | also 12 → 11 with height 350, 13 → 11 with height 480 (`DS:116C`) |
| 12 | `NEW:` | |

`VMCODE.OVL` (SHELL1) holds `VGA EGA MCG CGA TAN HEG EVG EVA`; `VMCODE2.OVL` (SIM2, loaded by AP)
holds only `VGA:`. **The two `OVL:VGA:` chunks are byte-identical** (9424 bytes; compared
`work/ovl/VMCODE_OVL_VGA.bin` with `VMCODE2_OVL_VGA.bin`: 0 differences).

### 2.2 `gfx_init(code, unused, name)` — INTRO `05da:5c93`, PS `16e3:59ed`, AP `1d32:000a`

Called once per program: INTRO `sys_init 038e:080d` with `(DS:24B1, 0FFh, "vmcode.ovl")`, PS
`048e:0009` with `(DS:43B0, 0FFh, DS:00AB)`, AP `init 4e0d:0000` with `(DS:43B1, 80h, name)`. The
first argument is the adapter code saved in the preferences (`CONTROL.PRF` word 0, PS reads it into
`DS:43B0`; shipped value 8 = VGA; 0 = detect). If `gfx_init` returns 0 the callers retry with code
0 (auto-detect); if that fails INTRO prints an error and exits, PS calls its fatal handler.

1. `DS:1A51 = code`; `drv[6E8]` (INTRO `DS:1168`, "y shift", 0 = full 200 lines) = 0; `drv[1F]` = 0;
   `drv[6EA]` = 320 (screen width), `drv[6EC]` = 200 (height). Free the palette buffer
   `drv[19E]:drv[1A0]` if allocated.
2. `DS:1A50 = 05da:5f6b()` (current BIOS video mode, for `gfx_restore_text`).
3. `code = gfx_detect_adapter()` (`05da:5de1`): if `drv[AB4]` (INTRO `DS:1534`, "hardware present",
   initial 1) is 0, returns `DS:1A51` unchanged. Otherwise INT 10h/1A00h (display combination),
   INT 10h/12h and a CRTC probe; a VGA (combination code 7 or 8) returns 8 unless a code was
   requested (then that code). The port: always 8.
4. `drv[1D] = code`; driver = `gfx_load_driver(code, name)`; if null → `drv[1D] = 0` → return 0.
5. **Call the driver entry** (offset 0) as `far drv_init(base, far callbacks)` with `base` =
   INTRO `0A80` / PS `2300` / AP `26C0` and `callbacks` = `DS:1A04` / `DS:3240` / `DS:35E6`
   (19 far pointers: `dos_alloc`, `dos_free` and 17 RTL file wrappers; the VGA driver never uses
   them). The driver returns `DX:SI` = its jump table (`cs:00DA`).
6. Copy 50 (AP: 40) far pointers from the driver table to `DS:tab` (INTRO `1938`, PS `3174`, AP
   `351A`) and overwrite every segment word with the driver's segment (the stored segments are
   0). Entry 0 thus points at the driver's own init.
7. `0000:04F0` (BIOS inter-application area) = DGROUP (unused by the game; **guess**: debugging aid).
8. **Read page = front, write page = back**: `drv[16] = drv[14]`, `drv[18] = drv[12]`.
9. If the driver loaded: allocate the **span buffer** `dos_alloc(0x340 << drv[6E8])` paragraphs
   (13 312 bytes) and store its segment **+1** in `drv[AB2]` (INTRO `DS:1532`; the polygon filler
   writes its span header just before it, §lib 4); get the BIOS 8×8 font pointer (INT 10h/1130h,
   BH=3) into font slots 0 and 1 (`DS:2ED4`, `2ED8`), and set their widths/heights to 8
   (`drv[34..35]`, `drv[48..49]`), first char 0 (`drv[5C..5D]`), count 255 (`drv[70..71]`).
10. Return the adapter code (0 = failure).

`gfx_restore_text` (INTRO `05da:5dc9`, PS `5b23`, AP `013f`): if `DS:1A50 ≠ FFh`, INT 10h to set
that BIOS mode (`05da:5f48`), `DS:1A50 = FFh`. `05da:5db4` = shutdown helper (kbd, mouse, timer,
div-zero restore; platform).

### 2.3 Driver entry `0000` = `drv_init(base, far callbacks)` (verified)

```
copy 38 words from callbacks to cs:01A2        (callback table, unused by VGA)
cs:00D8 = base; cs:00D6 = DS_caller + base/16  (the driver's DS from now on)
drv[21] = FFh; drv[1F] += 1
if drv[AB4] != 0:                               ("hardware present": set the mode)
    INT 10h AX=0013h
    SC[04] = (SC[04] & ~08h) | 04h              (chain-4 off, odd/even off)
    GC[06] &= ~02h                              (chain odd/even off)
    SC[02] = 0Fh; clear A000:0000..FFFF (all 4 planes: 256 KB of pixels = 0)
    CRTC[14h] &= ~40h                           (dword mode off)
    CRTC[17h] |= 40h                            (byte mode)
    GC[05] = 40h (write mode 0, 256-colour shift); GC[01] = 0; GC[08] = FFh
drv[14] = A000; drv[12] = A400; drv[10] = A800
for y in 0..199: drv[6F2 + 2y] = y*80           (row table, planar byte offsets)
drv[1D] = 8
return DX:SI = cs:00DA (jump table)
```

Note: the mode is set (and **video memory cleared**) only when `drv[AB4] ≠ 0`. INTRO and PS keep
the initial 1. **AP clears it** (`4e0d:0021`) unless `argv[1]` is the debug word `"nlkle"`
(`50c8:0008` sets `DS:053F`), so normally AP **keeps the mode, the video memory and the CRTC start
address left by PS**; only the driver variables are reset (front = A000 etc.). PS `shell_exit`
(`227c:0072`) makes `drv[12] = A000` before leaving (see §4.2).

### 2.4 The shared variable block (verified unless marked)

`drv[X]` = INTRO `DS:0A80+X`, PS `DS:2300+X`, AP `DS:26C0+X` — this holds for the whole block
`0000..0B48` (INTRO `0A80..15C8`) with the exception of the polygon scratch `drv[B20..B39]`, which
is at AP `DS:1CF8..1D11` (INTRO `15A0..15B9`, PS `2E20..2E39`). Initial values are the
DGROUP image values.

| drv | INTRO DS | size | name | meaning / users |
|---|---|---|---|---|
| 00 | 0A80 | b | `text_fg` | text colour (entry 1 fg; slow text path pixel colour) |
| 01 | 0A81 | b | `text_bg` | text background colour (entry 1 when `text_flags == 0`; slow path background line) |
| 02 | 0A82 | b | `text_flags` | bit 0 transparent background, 1 bold (+1 px), 2 italic (shear), 3 underline (row `font_uline`), 4 halftone (every other pixel); entry 1 treats any non-zero as transparent |
| 03 | 0A83 | b | `clip_on` | 0 = no clipping in the library/driver (initial 0) |
| 04 | 0A84 | w | `clip_x1` | inclusive, initial 0 |
| 06 | 0A86 | w | `clip_x2` | inclusive, initial 319 |
| 08 | 0A88 | w | `clip_y1` | inclusive, initial 0 |
| 0A | 0A8A | w | `clip_y2` | inclusive, initial 199 |
| 0C | 0A8C | b | `fill_on` | rectangles, circles, polygons are filled (initial 1) |
| 0D | 0A8D | b | `fill_col` | fill colour |
| 0E | 0A8E | b | `draw_col` | line/outline/pixel colour; outline of a filled shape is drawn only if `draw_col ≠ fill_col` |
| 0F | 0A8F | b | `fill_col2` | second fill colour: ≠ 0 → checkerboard dither of `fill_col`/`fill_col2` (poly spans, flood fill) |
| 10 | 0A90 | w | `page_bg` | A800 |
| 12 | 0A92 | w | `page_back` | A400 |
| 14 | 0A94 | w | `page_front` | A000, displayed |
| 16 | 0A96 | w | `page_read` | read page segment |
| 18 | 0A98 | w | `page_write` | write page segment |
| 1C | 0A9C | b | | set to 1 by `05da:2b08` (platform, 101-key check) — not video |
| 1D | 0A9D | b | `adapter` | 8 = VGA; indexes `DS:164A` (pixel shift per adapter, 0 for VGA) |
| 1F | 0A9F | b | `drv_inits` | incremented by drv_init |
| 21 | 0AA1 | b | `ega_mode` | FFh for VGA; `10h` would make the library program EGA write mode 2 (`05da:06f1`, a no-op on VGA) |
| 34+i | 0AB4+i | b[20] | `font_w[i]` | font slot i width (slot 0 = current font) |
| 48+i | 0AC8+i | b[20] | `font_h[i]` | height |
| 5C+i | 0ADC+i | b[20] | `font_first[i]` | first character |
| 70+i | 0AF0+i | b[20] | `font_count[i]` | number of characters |
| AC | 0B2C | w[20] | `poly_x` | polygon vertices (input, then clipped) |
| D4 | 0B54 | w[20] | `poly_y` | |
| FC | 0B7C | w[20] | `poly_x2` | polygon work array |
| 124 | 0BA4 | w[20] | `poly_y2` | |
| 14C | 0BCC | w[20] | `poly_ox` | copy of the unclipped polygon for the outline |
| 174 | 0BF4 | w[20] | `poly_oy` | |
| 19C | 0C1C | w | `poly_n` | vertex count |
| 19E | 0C1E | far | `pal_buf` | 1536-byte palette buffer (+0 current, +300h target); driver assumes offset 0 |
| 6BC | 113C | w | `xlat_tab` | colour translation table offset (SS) for entry 19 |
| 6C2 | 1142 | w | (driver) | line colour latch (entry 2) |
| 6E2 | 1162 | w | `use_entry28` | ≠ 0 → call entry 28 (no-op on VGA) with the write page before sprite draws |
| 6E8 | 1168 | b | `yshift` | 1 = "half height" mode for polygons (y halved); 0 on VGA |
| 6EA | 116A | w | `scr_w` | 320 |
| 6EC | 116C | w | `scr_h` | 200 (rotated sprite clips rows against it) |
| 6F2 | 1172 | w[200] | `row_ofs` | y*80 |
| AB2 | 1532 | w | `span_seg` | span buffer segment (+1, see §2.2) |
| AB4 | 1534 | b | `hw_present` | initial 1; 0 = don't set the mode (AP) |
| AB8 | 1538 | w | | initial 3Fh (**guess**: max DAC value; palette part) |
| B20..B39 | 15A0..15B9 | | polygon scratch | §lib 4 (AP `1CF8..1D11`) |
| B3A | 15BA | far | `scn_draw_fn` | target of `05da:1e38` (the SCN sprite routine, = `05da:1e3c`) |
| DAC | 165E | b[8] | `aa_map` | 8-bpp font colour remap for values 1..4 (identity 0,1,2,3,4) |

Other library globals outside the block (INTRO / PS / AP): circle state `264C..265A` / `6930..693E`
/ `70EA..70F8`; scaled-sprite column table `2698` / `697C` / `6646` (w[≤640]) and row table `2B98`
/ `6E7C` / `6B46` (w[≤400]); flood-fill stack pointers `2EB8..2EBE` / `719C..71A2` / `6E66..6E6C`;
font arrays `2EC0` kind[20], `2ED4` glyphs far[20], `2F24` offsets far[20], `2F74` widths far[20],
`2FC4` underline row[20] / PS `71A4, 71B8, 7208, 7258, 72A8` / AP `6E6E, 6E82, 6ED2, 6F22, 6F72`;
rotated-sprite state `182C..1868` / `3090..30CC` / `3436..3472`; driver far pointer `1A52`,
requested code `1A51`, saved BIOS mode `1A50` (PS `328C..3290`, AP `1B44..`).

-----------------------------------------------------------------------------------------------

## 3. The 50 driver entries (VGA)

Offsets are driver offsets (origin 0, `rawdis.py work/ovl/VMCODE_OVL_VGA.bin`). "C" = far cdecl
with stack arguments (words), called from DS = DGROUP; "R" = register interface. All drawing goes
to the **write page** `drv[18]`; all reading from the **read page** `drv[16]`, unless stated.
Pixel results are given for a linear page model `P[seg][y*320+x]`.

| n | off | name | caller(s) in the library (INTRO / PS / AP) |
|---|---|---|---|
| 0 | 0000 | `drv_init` | `gfx_init` |
| 1 | 0E72 | `drv_glyph1` (R) | `gfx_text` 340e / 3a22 / 585c |
| 2 | 0753 | `drv_line` (R) | `gfx_line` 3957 / 3c7b / 5ab5 |
| 3 | 0E58 | `drv_sprite` (C) | AP thunk `1d32:3de1` only |
| 4 | 1103 | `drv_copy_rect` (C) | thunk 2fb0 / 35c4 / 53fe |
| 5 | 0F67 | `drv_get_rect` (C) | thunk 35d8 / 3bec / 5a26 |
| 6 | 0FCA | `drv_rect_size` (C) | thunk 35dc / 3bf0 / 5a2a |
| 7 | 0FD6 | `drv_put_rect` (C) | thunk 492f / 4c53 / 6a8d |
| 8 | 10AD | `drv_flip` (C) | thunk 2fbd / 35d1 / 540b |
| 9 | 01EE | no-op | — |
| 10 | 02B1 | `drv_hspan` (R) | SCN sprite, flood fill, VQT-to-screen |
| 11 | 0205 | `drv_hspan_dither` (R) | (via 10) |
| 12 | 064D | no-op (`retf`) | — |
| 13 | 0CD6 | `drv_bm_size` (C) | BMP loaders |
| 14 | 0D09 | `drv_bm_layout` (C) | BMP loaders |
| 15 | 0E04 | `drv_bm_merge_hi` (C) | BMP loaders |
| 16 | 064C | no-op (`retf`) | — |
| 17 | 126D | `drv_nib_put` (C) | SCR loader via thunk 24eb / 2aff / 4939 |
| 18 | 131C | `drv_nib_or_hi` (C) | SCR loader via thunk 24ef / 2b03 / 493d |
| 19 | 050E | `drv_cols_xlat` (R) | none found |
| 20 | 0C16 | `drv_set_palette` (C) | 090e / 0f22 / 400e (palette part) |
| 21 | 103F | `drv_get_pixel` (C) | 48cb / 4bef / 6a29, flood fill |
| 22 | 1075 | `drv_put_pixel` (C) | 48fd / 4c21 / 6a5b, circle outline, text |
| 23 | 1173 | `drv_span_copy` (R) | thunk 0b7e / 1192 / 09bb |
| 24 | 1252 | `drv_span_copy_ofs` (C) | none found in the library (**likely** game code) |
| 25, 26, 28 | 01EE | no-op | 25 via thunk 2fb5 / 35c9; 28 by the sprite/text code when `drv[6E2]` |
| 27 | 0932 | `drv_poly_spans` (R) | 0b6b / 117f / 09a8, polygon, rectangle |
| 29 | 1412 | `drv_sprite_flip` (C) | thunk 06e5 / 0637 / 3de5 |
| 30 | 1FCC | `drv_cache_blit` (C) | thunk 1e1d / 2431 / 426b |
| 31 | 2067 | `drv_cache_upload` (C) | thunk 1e21 / 2435 / 426f |
| 32 | 2113 | `drv_cache_reset` (C) | 1e25 / 2439 / 4273 |
| 33 | 2128 | `drv_sprite_opaque` (C) | thunk 06e9 / 063b / 3de9 |
| 34 | 0C58 | `drv_fade_step` (C) | 09da, 0a7b / 0fee, 108f / 40da, 417b |
| 35 | 0BC2 | `drv_dac_upload` (C) | entries 20 and 34 |
| 36 | 0334 | `drv_span_tex` (R) | rotated sprite 3d01 / 4025 / 5e5f; PS `16e3:065d` |
| 37 | 0438 | `drv_span_cols` (R) | scaled sprite 25a6 / 2bba / 49f4 |
| 38 | 064E | `drv_row_copy` (R) | SCN sprite 1e3c / 2450 / 428a |
| 39–48 | 01EE / 24CF | no-op | — |
| 49 | 0000 | = `drv_init` (segment patched) | — |

AP copies only entries 0–39.

### 3.1 Entry 0 — `drv_init` — see §2.3.

### 3.2 Entry 1 — `drv_glyph1` (R, `0E72`)

In: `BP` = y, `DX` = x, `CX` = rows, `ES:SI` = glyph bitmap (1 byte per row, bit 7 = leftmost
pixel, exactly 8 columns). `BX` is ignored. Preserves DI, BP, DS, ES.

```
if drv[02] == 0:                       for r in 0..CX-1, c in 0..7: P[y+r][x+c] = drv[01]
for r in 0..CX-1: b = glyph[r]; for c in 0..7: if b & (80h >> c): P[y+r][x+c] = drv[00]
```

No clipping; always an 8-pixel cell (the background box is 8 wide whatever the font width). Any
non-zero `drv[02]` counts as transparent.

### 3.3 Entry 2 — `drv_line` (R, `0753`)

In: `BX` = x1, `CX` = y1, `DX` = x2, `SI` = y2 with **x1 ≤ x2** (the library orders the ends);
colour `drv[0E]`. No clipping. Pixels:

```
if x1 == x2:
    if y1 == y2: plot(x1, y1)
    else: for y in min(y1,y2)..max(y1,y2): plot(x1, y)
elif y1 == y2: hspan(y1, x1..x2)                         (entry 10 logic, solid)
else:
    dx = x2-x1; dy = |y2-y1|; ys = (y2 > y1) ? +1 : -1
    if dy == dx: for i in 0..dx: plot(x1+i, y1+ys*i)
    elif dy < dx:                                        (x-major, from (x1,y1))
        e = 2dy - dx; x = x1; y = y1; plot(x, y)
        repeat dx times: x += 1; if e < 0: e += 2dy else: y += ys; e += 2dy - 2dx; plot(x, y)
    else:                                                (y-major)
        if ys > 0: start (x1,y1), xs = +1   else: start (x2,y2), xs = -1   (always walks downwards)
        e = 2dx - dy; plot(start)
        repeat dy times: y += 1; if e < 0: e += 2dx else: x += xs; e += 2dx - 2dy; plot(x, y)
```

Note the y-major case with the line rising: it is drawn **from the right end downwards**, which
changes which pixels the Bresenham decisions pick; the port must walk in the same direction.

### 3.4 Entry 29 — `drv_sprite_flip(frame*, x, y, flags)` (C, `1412`) and entry 3 (`0E58`)

`frame` = near pointer to a frame record `{+0 seg, +2 off, +4 ?, +6 w, +8 h}`; pixels at
`seg:off`, one byte each, rows of stride **W4 = w & ~3**. Entry 3 = entry 29 with `flags = 0`.
Colour 0 is transparent. `flags` bit 0 = vertical flip, bit 1 = horizontal flip.

Only **W4 columns** are drawn per row (a frame whose width is not a multiple of 4 loses `w & 3`
columns). Source index of destination pixel (i, j), 0 ≤ i < W4, 0 ≤ j < h, unclipped:
`src = S0 + j*D + i*step`, with

| flags | S0 | step | D (row start to next row start) |
|---|---|---|---|
| 0 | 0 | +1 | +W4 |
| 2 (mirror) | w − 1 | −1 | 2w − W4 |
| 1 (upside down) | W4·h − w | +1 | W4 − 2w |
| 3 | W4·h − 1 | −1 | −W4 |

For w a multiple of 4 these are the exact mirror images; otherwise the code's mixed use of w and W4
skews the image (reproduce literally). When rows are clipped at the top, the start moves by
`k*W4` (negated when upside down); when columns are clipped at the left, it moves by `+k` (`−k`
when mirrored).

Clipping only if `drv[03] ≠ 0`, against the inclusive rectangle `drv[04..0A]`, in this order:
right (columns with x+i > x2 dropped), bottom (rows with y+j > y2 dropped), top (rows above y1
dropped; the source start moves by k rows, negated when vertically flipped), left (columns left
of x1 dropped). The routine returns without drawing if the visible width becomes ≤ 0 by the
right or left test alone, or the height ≤ 0. If both left and right clipping apply and the
remaining width is ≤ 0 the planar loops run with a negative count (undefined; not reached by
the game — **likely**). Result: every visible pixel with a non-zero source value is written.

### 3.5 Entry 33 — `drv_sprite_opaque(frame*, x, y)` (C, `2128`)

As entry 29 with flags 0 but **opaque** (zeros written too) and with one difference in top
clipping: when k > 0 rows are clipped at the top, the source starts at row **k−1** (`dec ax`
before the multiply at `21CF`): the first visible row shows the source row above the one it
should. Reproduce.

### 3.6 Entry 4 — `drv_copy_rect(x, y, w, h)` (C, `1103`)

Latch copy (write mode 1) from the read page to the write page, same position, **whole 4-pixel
columns**: planar bytes `x>>2 .. (x>>2) + ((x&3)+w+3)/4 − 1` of rows `y .. y+h−1`, i.e. pixels
`x & ~3` up to the end of the 4-group that contains `x+w−1`. No clipping. Restores GC mode 40h.

### 3.7 Entries 5, 6, 7 — rectangle get / size / put

* 5 `drv_get_rect(far dst, x, y, w, h)` (`0F67`): `dst[j*w+i] = Pread[y+j][x+i]` for i < w, j < h.
* 6 `drv_rect_size(w, h)` (`0FCA`): returns `DX:AX = w*h` (unsigned 16×16).
* 7 `drv_put_rect(far src, x, y, w, h)` (`0FD6`): `Pwrite[y+j][x+i] = src[j*w+i]`, opaque.
No clipping.

### 3.8 Entry 8 — `drv_flip(wait)` (C, `10AD`)

```
old_back = drv[12]; drv[12] = drv[14]; drv[14] = old_back
CRTC (port from 0040:0063) reg 0Ch = ((old_back >> 4) & FFh)... precisely:
    start = (old_back << 4) & FFFFh  (A000→0000, A400→4000h, A800→8000h)
    out CRTC 0Ch = start >> 8; out CRTC 0Dh = start & FFh
if wait: while (in 3DAh & 8): ;  while !(in 3DAh & 8): ;     (end of current retrace, then start of next)
```

The read/write page variables are **not** changed by the flip; callers reassign them. The new
front page becomes visible at the next vertical retrace (CRTC start latching); with `wait ≠ 0`
the call returns just after that retrace began.

### 3.9 Entries 10 / 11 — horizontal spans (R, `02B1` / `0205`)

In: `ES` = page segment, `DI` = planar offset of the row start (y*80), `BX` = x, `CX` = count,
`AL` = colour A, `AH` = colour B, `DX` = parity. Entry 10 returns at once if `CX ≤ 0`; if `AH = 0`
it fills `x .. x+CX−1` with `AL`; if `AH ≠ 0` it continues as entry 11. Entry 11:

```
if DX & 1: swap(AL, AH)
for x' in x .. x+CX-1: P[x'] = (x' even) ? AH : AL
```

(Entry 11 itself has no `CX ≤ 0` guard and dithers even with AH = 0.) Callers pass `DX = y`, so
the pixel colour is `A` where `(x'+y)` is odd and `B` where it is even.

### 3.10 Entry 27 — `drv_poly_spans` (R, `0932`)

In: `ES:SI` = span list `{u16 y0, u16 n, n × (i16 xl, i16 xr)}`; colours `drv[0D]` (A) and
`drv[0F]` (B). The row table is read at `SS:(0x6F2+base)` (i.e. DGROUP), whatever `ES` is. Row k
(y = y0+k) spans `xl..xr` inclusive; rows with `xr < xl` are skipped (the row counter still
advances). No clipping (callers clip).

* `B == 0`: solid fill with A.
* `B ≠ 0`: checkerboard: pixel (x, y) gets **A if `(x + y + xl0)` is even, else B**, where `xl0`
  is the `xl` of the **first** span of the list (the phase of the pattern follows the first span).

### 3.11 Entries 13, 14, 15 — bitmap preparation (C)

Used by the BMP loaders (details of the data flow in `video_pictures.md`).

* 13 `drv_bm_size(frame* list[], int *out)` (`0CD6`): sums `w*h` (`+6`×`+8`, 16×16→32-bit) over
  the zero-terminated list of near frame pointers; returns the sum in `DX:AX`; writes 0 to `*out`.
* 14 `drv_bm_layout(frame* list[], far buf, u32 n)` (`0D09`): (1) assigns consecutive normalised
  far pointers inside `buf` to the frames (`+0 = seg + off/16`, `+2 = off & 15`; the next frame
  starts `w*h` bytes later — only the low 16 bits of `w*h` are used, a carry adds 1000h to the
  segment); (2) **expands `n` packed bytes in place, from the end backwards**: packed byte k at
  `buf + k` becomes `buf[2k] = byte >> 4`, `buf[2k+1] = byte & 0Fh` (huge-pointer arithmetic, safe
  across 64 KB). `n` is passed as a 32-bit value (low word, then a word whose low byte is used).
* 15 `drv_bm_merge_hi(far src, far dst, u32 n)` (`0E04`): for k < n (low word of n only):
  `dst[2k] |= src[k] & F0h`, `dst[2k+1] |= (src[k] & 0Fh) << 4` (huge pointers).

So after 14 + 15 the first pixel of each pair holds the **high** nibbles of the `BIN:` and `VGA:`
bytes and the second pixel the low nibbles. `resources.md` §4a states "first pixel in the low
nibble" (checked visually); `video_pictures.md` reconciles the two (the loader may reorder).

### 3.12 Entries 17, 18 — nibble screen writers (C, `126D`, `131C`)

Args (after the entry's 5 pushes): `off, seg` (far source, normalised inside), `xb` (planar byte
column = x/4), `y`, `w` (pixels, multiple of 4), `rows`. For each row r (y+r) and each source
byte pair covering 4 pixels: byte `b0` → pixels 0 (high nibble) and 1 (low nibble), `b1` →
pixels 2, 3.

* 17: `P = nibble` (0..15).
* 18: `P |= nibble << 4` (reads the pixel through read-map select, i.e. from the **write page**
  segment, and ORs): combines a low-nibble plane written by 17 with a high-nibble plane.

### 3.13 Entries 20, 34, 35 — palette (summary; full data flow in `video_palette.md`)

* 35 `drv_dac_upload(near src, first, count)` (`0BC2`): wait until vertical retrace is active
  (`in 3DAh & 8`), if `(in 3C7h & 3) ≠ 3` write that value to 3C9h (resets a half-done DAC write
  sequence), `out 3C8h, first`, then `count*3` bytes from `DS:src` to 3C9h with interrupts off.
* 20 `drv_set_palette(far pal)` (`0C16`): if `seg(pal) ≠ 0`: `dac_upload(pal, 0, 256)`; copy the
  768 bytes to `pal_buf+0` and again to `pal_buf+300h`.
* 34 `drv_fade_step(first, count, c, l)` (`0C58`): for i in first..first+count−1 and each
  component k: `cur[i][k] = tgt[i][k]*l/63 + tgt[c][k]*(63−l)/63` (each product 8-bit×8-bit,
  each quotient truncated separately), `cur` = `pal_buf+0`, `tgt` = `pal_buf+300h`, then
  `dac_upload(cur+3*first, first, count)`. `l` = 0..63 (63 = target palette, 0 = all colour c).

### 3.14 Entries 21, 22 — pixels (C)

* 21 `drv_get_pixel(x, y)` (`103F`) → `AX = Pread[y][x]` (AH = 0).
* 22 `drv_put_pixel(x, y, c)` (`1075`): `Pwrite[y][x] = c`. No clipping (the library wrappers
  `gfx_get_pixel`/`gfx_put_pixel` clip).

### 3.15 Entries 23, 24 — span copy between pages

* 24 `drv_span_copy_ofs(x, y)` (`1252`): `cs:116D = y*80 + (x >> 2)` (signed shift).
* 23 `drv_span_copy` (R, `1173`): `ES:SI` = span list as entry 27. For each row and span
  `xl..xr`, copies whole 4-pixel columns by latches from the **read page** at planar offset
  `+cs:116D` to the **write page**, with the edge bytes masked to the pixels `xl..xr` (plane mask
  `0Fh << (xl&3)` on the left, `{0F,01,03,07}[(xr+1)&3]` on the right; single-byte spans use both).
  In pixels: `Pwrite[y][x] = Pread[y + dy][x + 4*dxb]` for x in xl..xr, where `cs:116D = dy*80 + dxb`
  — the horizontal displacement is a multiple of 4 pixels and the plane is preserved.

### 3.16 Entries 30, 31, 32 — video-memory bitmap cache

* 32 `drv_cache_reset()` (`2113`): `cs:1FCA = 0`.
* 31 `drv_cache_upload(frame* list[])` (`2067`): for each frame of the zero-terminated list:
  `n = w*h/4`; copy the frame's pixels to AC00 at offset `cs:1FCA`, plane p receiving pixels
  `p, p+4, p+8…` of the frame (in row-major order); set the frame's `+0 = AC00`, `+2 = offset`;
  `cs:1FCA += n`. Then **frees the DOS block** whose segment was the first frame's original `+0`
  (INT 21h/49h, ES = that segment) — the caller's bitmap memory is released. Returns the list
  pointer in AX.
* 30 `drv_cache_blit(frame*, x, y)` (`1FCC`): latch copy (write mode 1) of `h` rows × `w/4` planar
  bytes from `AC00:off` to the write page at `y*80 + (x >> 2)`: **opaque, no clipping, x rounded
  down to a multiple of 4**. In pixels: `Pwrite[y+j][(x&~3) + 4b + p] = frame pixel (4b+p, j)` with
  the pixel index taken over a *row-major* frame whose rows are w pixels (so the frame width must be
  a multiple of 4).

Capacity 16 K planar bytes = 64 000 pixels; no overflow check.

### 3.17 Entries 36, 37, 19 — per-pixel source spans (R)

Common: `ES` = page, `DI` = row planar offset (y*80), `DX` = x, `CX` = count; transparent 0;
only the pixel loop is planar.

* 37 `drv_span_cols` (`0438`): `DS:SI` = source row base, `SS:BP` = word table T (per destination
  pixel k, the source column). `for k < CX: v = DS:[SI + T[k]]; if v: P[x+k] = v`.
* 19 `drv_cols_xlat` (`050E`): as 37, but `v = SS:xlat[ DS:[SI+T[k]] ]` with the table at
  `SS:drv[6BC]`, and the zero test is on the untranslated value.
* 36 `drv_span_tex` (`0334`): C-like frame `[bp+6]` = pointer to a `{seg, off}` pair (source base),
  `[bp+8]` = extra offset added to the base, `[bp+0Ah]` = pointer to a word table T; register DX =
  x (may be negative: then the first `−x` pixels are skipped, T advanced, x = 0; nothing drawn if
  the count becomes ≤ 0), CX = count. `v = src[base + T[k]]`, transparent 0. Used by the rotated
  sprite (`video_rotate.md`). Restores DS = SS.

### 3.18 Entry 38 — `drv_row_copy` (R, `064E`)

`ES` = page, `DI` = row planar offset, `BX` = x, `CX` = count, `DS:SI` = source bytes, carry
flag = direction. CF = 0: `P[x+k] = src[k]`; CF = 1: `P[x−k] = src[k]` (right to left), k < CX.
Opaque. Used by the SCN sprite for literal runs.

### 3.19 No-op entries

9, 12, 16, 25, 26, 28, 39–48 are `retf` (EGA/other adapters use them: 28 = "prepare page", 25 =
?, 12/16 = unknown). Entry 49 and 0 point at `drv_init`.

-----------------------------------------------------------------------------------------------

## 4. Pages: who draws where, flipping, vsync

### 4.1 Mechanisms

* **Selection**: the game assigns `drv[16]`/`drv[18]` from `drv[10]/[12]/[14]`; all drawing goes to
  `drv[18]`. Copies between pages use `drv_copy_rect` (entry 4, read → write page, 4-pixel
  columns) — most often the whole screen `(0, 0, 320, 200)`.
* **Flip** (entry 8): swap back/front, CRTC start, optional vsync wait. The library thunk is INTRO
  `05da:2fbd`, PS `16e3:35d1`, AP `1d32:540b`.
* **Vertical retrace waits** happen only in `drv_flip(wait≠0)` and in `drv_dac_upload` (every
  palette upload waits for retrace to be active). There is no other frame pacing in the driver;
  frame timing is the game's (timer ticks, 236.7 Hz; see platform / TTM / sim specs).

### 4.2 Per program (verified from the writers of `drv[10..18]`; screen-level detail belongs to
the TTM, shell_ui and sim_flow specs)

* **INTRO**: at the end of `main` (`038e:0cba`), before `exit(2)` to PS, the same hand-over as PS
  `shell_exit`: if the front page is not A000 → `drv[12] = A000`, read = front, write = A000,
  `gfx_flip(0)`. PS then sets the mode again (clearing video memory). The TTM player (`11d2:053f`) and its
  helpers switch pages explicitly (background page A800 = TTM "background buffer" for
  SAVE_BG/STORE_AREA; details in `video_ttm.md`); the VGA effect module `103d` and the wipes
  (`0f88`, `1111`, `11d2:1688`) draw to the front page directly. `0460:0174` flips once.
* **PS**: the shell uses the helper module `sys\helper.c` (`22ce`) to select page pairs
  (read ← write): `22ce:0063` bg→back, `0074` front→back, `0085` back→front, `0096` back→bg; the same
  followed by a full-screen `copy_rect` (`22ce:004a`): `00a7` bg→back, `00bc` back→bg, `00d1`
  bg→front, `00e6` back→front, `00fb` front→back. Typical screen update: draw on the back page,
  then `22ce:00e6`/flip. Flips via `16e3:35d1` from `0d16`, `0ddd`, `21f4`, `227c`, `2b4f`, `2e8a`.
  `shell_exit(fly)` (`227c:0072`): if the front page is not A000, it sets `drv[12] = A000`, read =
  front, write = A000 and calls `gfx_flip(0)` — so **A000 is the displayed page when AP starts**
  (AP's `drv_init` resets its variables to front = A000 without touching the CRTC, §2.3). Quitting to
  DOS restores the text mode (`gfx_restore_text`).
* **AP** does **not** flip per frame (`gfx_flip` only at `4e0d:0beb` and `5440:07fe`). The screen
  update `46de:02f3` (sim_flow) draws the mouse pointer into the back page (area saved with
  `gfx_get_rect`, pointer with `gfx_sprite`, AP entry 3), then sets read = back, write = front and
  copies back → front with `gfx_copy_rect` — the whole screen `(0, 0, drv[6EA], drv[6EC])` or a list of
  dirty rectangles — then removes the pointer from the back page. So in the sim **A000 stays
  displayed**, A400 is the drawing page and A800 holds saved backgrounds (cockpit build `24fc`/`2595`,
  dialogs/map `644a`, `6cdc`, `368f`, `5a01`… write it; owned by sim_flow/render3d).

-----------------------------------------------------------------------------------------------

## 5. PS `-ph` "hivga" (settled)

The PS usage text lists `-ph  hivga driver`, but in this build **all `-p?` options are parsed and
ignored**: `main` (`048e:0259`) dispatches on the letter after `-` (`? h p r s` via the table at
`048e:04fe`); `-p` (`048e:0397`) reads `tolower(argv[i][2])` and discards it. `-r<n>` sets the
random seed (`DS:00C5`), `-s<n>` the sound driver (`DS:43B2`). The video adapter actually comes
from `CONTROL.PRF` word 0 (`1193:027a` reads 37 bytes into `DS:43B0`; 8 = VGA), with auto-detect as
fallback. "hivga" corresponds to adapter code 10 = chunk `HVG:` in `gfx_load_driver`'s tag table,
which is **not present** in `VMCODE.OVL`; had it been selected, `gfx_init` would fail and PS would
fall back to auto-detection (VGA). Nothing to port.

-----------------------------------------------------------------------------------------------

## 6. Port notes

* **Driver**: not loaded. `gfx_init` becomes a C function that performs §2.2/§2.3 on `mem[]`
  (same variable values at the same DS offsets, jump table filled with host thunks) and returns 8.
  The OVL chunk is not needed. `/* PORT: */` INT 10h / VGA register writes replaced by the page
  model; `drv[AB4] = 0` in AP means "don't clear the pages".
* **Pages**: one 64 000-byte linear buffer per page segment A000/A400/A800 (+ a 64 000-pixel
  planar-ordered store for the AC00 cache, or a linear store with the cache offsets kept in
  4-pixel units — the cache is only read by entry 30). Map a segment value to a buffer by
  `(seg − A000) >> 10`. Keep the page segments in `drv[10..18]` as numbers.
* **Planar effects to reproduce**: entry 4 / 23 / 30 whole-column rounding; the cache layout;
  entries 29/33 drawing only `w & ~3` columns and their flip/top-clip quirks; the dither phase
  rules of 10/11/27. Everything else is a plain per-pixel operation.
* **Presentation**: keep an emulated CRTC start (`page_shown`), set by `drv_flip` (and initially
  A000). The host presents `page_shown` with the current DAC palette at its own vsync (70 Hz VGA
  refresh; the original is 320×200 double-scanned at 70 Hz). `drv_flip(wait)` must block until the
  next emulated vertical retrace (≈ 14.3 ms period) when `wait ≠ 0`; `drv_dac_upload` waits for a
  retrace to be *active* — model as: if not inside the emulated retrace window, block until the next
  one. Palette changes take effect for the next presented frame. Direct CRTC/attribute effects of
  INTRO `103d` are described in `video_palette.md` (they need the host to support at least what that
  module does, e.g. start-address changes mid-sequence).
* **Timing**: the driver has no timing of its own besides the retrace waits above.
* **Memory**: the span buffer (13 KB DOS block), fonts, palette buffer are ordinary allocations in
  the port's DOS-memory model (platform).

## 7. Hand-offs

* **platform**: `05da:5de1` adapter detection is only needed to return 8; `05da:5f6b`/`5f48`
  BIOS mode save/restore; `0000:04F0` written with DGROUP by `gfx_init`; `DS:1A04` callback table
  (19 far pointers to `dos_alloc`, `dos_free`, RTL file wrappers `0000:02f1…03f8`) passed to the
  video driver and unused by VGA. AP `4e0d:0021`: `argv[1] == "nlkle"` (`50c8:0008` → `DS:053F`)
  enables setting the video mode in AP (debug start without PS).
* **shell_ui / shell_data**: PS `sys\helper.c` page helpers `22ce:004a..00fb` (§4.2) are the
  shell's page protocol; names proposed in `video_symbols.csv` (owner left to them). `CONTROL.PRF`
  +0 = video adapter code (8), +2 = sound driver (3 = MT-32 in the shipped file). The `-p?` options
  of PS are dead (§5).
* **sim_flow**: AP keeps PS's video mode and memory (§2.3); which AP code selects which page is
  listed in §4.2.
* **render3d**: the library polygon filler (`gfx_polygon`, `video_library.md`) is also used by AP
  `277a` and `6396`; its pixel rules are specified there.

## 8. Open questions

* Entries 12, 16, 25, 26, 28 purpose (no-ops on VGA; only matter for other adapters).
* Entry 13's second argument (always zeroed).
* Entry 24 callers (none in the library; search game code) and entry 19 callers (none found).
* `drv[AB8] = 3Fh` meaning.
