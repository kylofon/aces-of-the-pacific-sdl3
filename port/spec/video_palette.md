# video — part "palette": palettes, DAC, fades, colour cycling, VGA register effects

Part of the **video** module spec (merged by the video lead into `video.md`). Scope: the library
palette API shared by INTRO/PS/AP (loader, slots, current palette, driver palette buffer, fades,
colour-cycle blocks), how the three programs use driver entries 20/34/35, the TTM palette opcodes'
library side (FADE_OUT/FADE_IN/FADE_PART, PAL_BLOCK/PAL_CYCLE, SEL_PAL, PAL_RESET), the INTRO/PS
hardware **scroll** effect (TTM `3103`, direct CRTC/attribute programming), the AP DAC routines in
segment `0000`, AP's run-time palette effect system (`1792`/`51a8`, driven by the sim every frame),
the VCR message dimmer and every other palette call site. Out of scope: the TTM interpreter itself
(only its palette opcode handlers are described, as far as needed), picture loaders, render3d's
`paltrick.c` (`51b4`, cited only) and shading tables.

Confidence tags: **verified** (read instruction by instruction), **likely**, **guess**.

## Index

1. [Summary for the port](#1-summary-for-the-port)
2. [Data: palette slots, current palette, driver palette buffer](#2-data)
3. [Driver entries 20 / 34 / 35 as used by the library](#3-driver-entries-20-34-35)
4. [Library functions](#4-library-functions) — `pal_load`, `pal_set`, `pal_free`, `pal_fade`,
   `pal_cycle_block`, `pal_cycle_step`, `far_copy_n`, `far_memmove`
5. [TTM palette opcodes (library side, fade arithmetic and timing)](#5-ttm-palette-opcodes)
6. [Timed interpolator used by FADE_PART](#6-timed-interpolator-ttm_timer)
7. [INTRO `103d` / PS `30b5`: TTM `3103` hardware scroll](#7-ttm-3103-hardware-scroll-intro-103d--ps-30b5)
8. [AP: DAC routines, pending-upload, palette effects (`pal_fx`), other palette users](#8-ap)
9. [PS: palette call sites outside the TTM](#9-ps-palette-call-sites)
10. [Segments that are *not* palette code (INTRO `0fca`, `10f5`, `05da:45d3`)](#10-not-palette-code)
11. [Port notes](#11-port-notes)
12. [Hand-offs](#12-hand-offs)
13. [Open questions](#13-open-questions)

## 1. Summary for the port

* **Values are 6-bit** (0–63) everywhere: files, buffers, DAC. No code converts to 8 bits except
  the AP screenshot writer (`v << 2`, §8.6).
* **Data flow** (all three programs, VGA): `.PAL` chunk `PAL:VGA:` (768 bytes) → `pal_load` →
  far block in one of 9 **palette slots** (`slot[1..9]`) → returned far pointer is kept by the caller
  (TTM script record `+24`, the shell screen cache, AP globals) → `pal_set(p)` = driver entry 20:
  DAC upload of all 256 colours **and** copy of the 768 bytes to both halves of the driver palette
  buffer `slot[0]` (= `drv[19E]:drv[1A0]`, 1536 bytes: `+0` "current", `+300h` "target") →
  fades (`pal_fade` = entry 34) compute `current[i] = target[i]*l/63 + target[c]*(63-l)/63` into
  `+0` and upload that range. Colour cycling rotates the `+300h` target copy (dead code, §4.6).
* **Every DAC upload waits for vertical retrace** (`3DAh` bit 3 set, "in retrace", not "start of
  retrace"). Fades have no other time base: **one fade step per display frame (70 Hz)**, likely.
  FADE_PART alone is time-based (59.17 Hz tick counter, §6).
* FADE_OUT / FADE_IN also **present the back page**: they copy the whole back page to the front
  page (and for FADE_OUT optionally to the third page) while the palette is at the dark end.
* Palette colour cycling (TTM `2302/2312/2322/2402`, library `pal_cycle_block`/`pal_cycle_step`)
  is **never executed**: no shipped script uses those opcodes, and the step routine has no caller
  in any of the three programs (the TTM's period/active flags are write-only). Spec'd for
  completeness; the port can omit the stepping.
* TTM `3103` (hardware scroll, INTRO `103d`, PS `30b5`) is used by **no shipped script** (0 of 63).
* **AP** never uses the library fades. Its palette changes during flight go through a
  *pending DAC upload* (`5440:07bd` request, applied right after the page flip in `5440:07e1`)
  fed by the **palette effect system** `pal_fx` (`1792`, `51a8`; 13 entries loaded by `paltrick.c`
  from `pal_maps`), recomputed every frame by `17ce:0013`. The only AP "fade" is the VCR message
  dimmer (`606e:029d`, 18 steps to black).
* `COCPAL.PAL`, `COCKPIT.PAL`, `GUNPAL.PAL` named by the cockpit TTM scripts exist nowhere (no
  volume, no disk file, no code that writes them): `pal_load` returns NULL, the script's palette
  slot stays NULL and the cockpit art is shown with the sim palette `ACES.PAL` (+ effects).
  They are *not* built at run time (likely; §8.5).

## 2. Data

### 2.1 Library globals (DS offsets per exe)

| Name | INTRO | PS | AP | Type | Meaning |
|---|---|---|---|---|---|
| `pal_slot[10]` | `0C1E` | `249E` | `285E` | far ptr ×10 | slot 0 = driver palette buffer (= `drv[19E]:drv[1A0]`), slots 1–9 = loaded palettes |
| `pal_size` | `153C` | `2DBC` | `317C` | u16 | bytes of a palette for the adapter (`pal_size_tab[adapter]`), 300h on VGA |
| `pal_size_tab[14]` | `153E` | `2DBE` | `317E` | u16 ×14 | by adapter id: `0,102h,11h,11h,102h,300h,0,300h,300h,300h,300h,30h,30h,30h` |
| `pal_tag_tab[14]` | `1576` | `2DF6` | `31B6` | near ptr ×14 | chunk path by adapter: 1,4 → `"PAL:CGA:"`; 2,3,11 → `"PAL:EGA:"`; 5,7,8,9,10,12,13 → `"PAL:VGA:"`; 0,6 → `""` |
| `pal_tag_amg` | `1596` | `2E16` | `31D6` | char[9] | `"PAL:AMG:"` (fallback chunk) |
| `pal_current` | `1592` | `2E12` | `31D2` | far ptr | last pointer passed to `pal_set` (returned by `pal_set(NULL)`) |
| `cyc_count` | `1536` | `2DB6` | `3176` | s16 | number of colour-cycle blocks (0–9) |
| `fade_level` | `1538` | `2DB8` | `3178` | s16 | `l` of the last `pal_fade` call |
| `fade_colour` | `153A` | `2DBA` | `317A` | s16 | `c` of the last `pal_fade` call |
| `cyc_step3[10]` | `265C` | `6940` | `660A` | s16 ×10 | block step ×3 (bytes) |
| `cyc_start3[10]` | `2670` | `6954` | `661E` | s16 ×10 | block first colour ×3 |
| `cyc_end3[10]` | `2684` | `6968` | `6632` | s16 ×10 | (first+count) ×3 |
| `drv[1D]` adapter id | `0A9D` | `231D` | `26DD` | u8 | **8 = VGA** (set by the VGA driver init, `VMCODE_OVL_VGA.bin:00CF`) |
| `drv[1F]` DAC flag | `0A9F` | `231F` | `26DF` | u8 | 0 before init (`gfx_init` clears it), the VGA driver init increments it: non-zero = "has a DAC palette"; gates all fade/cycle code |
| jump-table entry 20 | `1988` | `31C4` | `356A` | far ptr | `set_palette` |
| jump-table entry 34 | `19C0` | `31FC` | `35A2` | far ptr | `fade_step` |

`gfx_init` (INTRO `05da:5c93`, PS `16e3:59ed`, AP `1d32:000a`) clears `drv[1F]`, and if
`pal_slot[0]` is non-NULL frees it (`dos_free`) and sets it to NULL (verified INTRO). The buffer is
re-allocated by the first `pal_set` (§4.2).

The adapter-id tables are listed for completeness: the port only needs id 8 (VGA; size 300h, tag
`PAL:VGA:`). Two code paths test other ids: TTM SEL_PAL uploads immediately only when the id is
**4** (not VGA, §5.3), and the scroll effect accepts ids 2 and 8 (§7).

### 2.2 Palette block

A palette is a far block of `pal_size` bytes (768 on VGA) = 256 × (R, G, B), each 0–63, allocated
with `dos_alloc` (INTRO `05da:35e0`; paragraph-aligned, offset 0). The pointer is the handle; the
slot table only exists so `pal_free` can find it and so the loader can refuse a 10th palette.

### 2.3 Driver palette buffer (`pal_slot[0]`, `drv[19E]:drv[1A0]`)

1536 bytes (2 × `pal_size`), allocated by `pal_set` on first use:

| Offset | Content | Written by | Read by |
|---|---|---|---|
| `+000h` | **current** (what the DAC holds after the last fade step) | entry 20 (copy), entry 34 (fade result), `pal_cycle_step` (scratch copy) | entry 34 upload |
| `+300h` | **target** (the palette as set, possibly rotated by cycling) | entry 20 (copy), `pal_cycle_step` | entry 34 (both terms) |

The driver's entry 34 addresses the buffer with offsets `first*3` / `300h + …` in segment
`drv[1A0]`, i.e. it assumes `drv[19E]` = 0, which `dos_alloc` guarantees.

### 2.4 TTM globals touched by the palette opcodes (owned by the TTM part; listed for reference)

| Meaning | INTRO | PS | AP |
|---|---|---|---|
| current script palette (`ttm_pal`) far ptr | `332E` | `760A` | `639A` |
| "don't draw / skip" flag (ctx `+0E` copy) | `33BE` | `769A` | `6408` |
| run context pointer (`+12` = palette slot) | `1CFA` | `36E2` | `209C` |
| script record far ptr (`+24 + 4*slot` = palette of slot) | `1CF4` | `36DC` | `2096` |
| fade speed table `[7]` | `1E80` | `3868` | — |
| scratch: fade speed / (INTRO: also the current opcode word) | `33C0` | `769C` | — |
| cycle block first `[3]`, last `[3]` | `33B2`, `33B8` | `768E`, `7694` | — |
| cycle period, cycle active (write-only) | `33CA`, `33CC` | `76A6`, `76A8` | — |
| pages mode (≥ 3: FADE_OUT also refreshes the third page) | `1CFD` | `36E5` | — |
| screen width, height (320, 200) | `116A`, `116C` | `29EA`, `29EC` | — |
| 59.17 Hz tick counter (u32) / timer-installed flag | `24D8` / `15BE` | `52AA` / `2E3E` | — |

Speed table (INTRO `DS:1E80`, PS `DS:3868`, verified values): index 0–6 = `0, 80, 20, 10, 5, 2, 1`
(the word after it is `0072h` in INTRO, `0000` in PS; the index is not range-checked).

## 3. Driver entries 20, 34, 35

Established by the lead (`VMCODE_OVL_VGA.bin`); restated here with what the library relies on
(verified against the driver bytes).

* **Entry 35 `dac_upload(near src, first, count)`** (`0BC2`): busy-wait until `in(3DAh) & 8`;
  `a = in(3C7h) & 3`; if `a != 3` then `out(3C9h, a)` (a dummy data write when the DAC state is not
  "write mode"; the port ignores it); `out(3C8h, first)`; `cli`; `count*3` × `out(3C9h, *src++)`;
  `sti`. `src` is read through the caller's **DS** — the library never calls entry 35 directly;
  entries 20 and 34 call it with DS set to the palette segment.
* **Entry 20 `set_palette(far pal)`** (`0C16`): if `seg(pal) == 0` do nothing. Else
  `dac_upload(pal, 0, 256)`, then copy the 768 bytes to `buf+0` and again to `buf+300h`
  (`buf = drv[19E]:drv[1A0]`). The DAC is written *before* the buffer.
* **Entry 34 `fade_step(first, count, c, l)`** (`0C58`): for every byte `k` of colours
  `first … first+count−1` (component `j` = k mod 3):
  `buf[k] = (u8)((buf[300h+k] * l) / 63) + (u8)((buf[300h + 3c + j] * (63 − l)) / 63)`
  — 8-bit `mul`/`div`, each term truncated separately, `l` and `63−l` as bytes (a caller passing
  `l > 63` would make `63−l` wrap; no caller does), sum stored as a byte. Then
  `dac_upload(buf + 3*first, first, count)` with DS = buffer segment.
* An unlisted helper at driver `0BFF` (`dac_upload` of one colour from the stack) is not in the
  jump table (dead code).

## 4. Library functions

Addresses: INTRO `05da` / PS `16e3` / AP `1d32` (from `port/shared_matches.csv`; PS/AP bodies are
the same code, byte-identical except relocated calls and DS offsets; `pal_load` matches at 0.81
only because its helper calls go to different segments — same length 515 bytes).

### 4.1 INTRO `05da:070b` / PS `16e3:0d1f` / AP `1d32:3e0b` — `pal_load`

`void far *pal_load(const char *name_or_fh)` — far cdecl. **Verified** (INTRO).

1. `pal_size = pal_size_tab[drv[1D]]`.
2. Find the first free slot `i` in `1..9` (`pal_slot[i] == NULL`). If none (`i == 10`): **quirk** —
   jumps straight to the epilogue, which stores the (NULL) result into `pal_slot[10]`, i.e. writes
   4 zero bytes at `DS:0C46` (INTRO) / `24C6` (PS) / `2886` (AP) = `drv[1C6..1C9]`; returns NULL.
3. The argument is either an already open resource file (checked by `05da:5c7a` → `5764`) or a
   file name: in the latter case the file is opened (`05da:589e`, via `vol_fopen`, mode `DS:1934`)
   and closed at the end (`05da:5c4b`). (Resource-file layer: see the resources/platform specs.)
4. `off = chunk_seek(fh, pal_tag_tab[drv[1D]], 0)` (`05da:5934`; returns −1 if `fh` is NULL or
   the chunk is absent).
   * Found: `p = dos_alloc(pal_size)`; if NULL → result NULL. Else `fread(stackbuf, 1, pal_size,
     fh)` (`049d:0411`; 768-byte stack buffer; result not checked) and
     `far_memmove(p, stackbuf, pal_size)` (§4.8).
   * Not found and `drv[1F] != 0`: try chunk `"PAL:AMG:"`; if found, `fread(words, 1, 40h, fh)`
     (32 little-endian words; result must be non-zero), `p = dos_alloc(pal_size)`, and for each
     word `w` of the 32: `R = ((w >> 8) & 15) << 2`, `G = ((w >> 4) & 15) << 2`, `B = (w & 15) << 2`
     (Amiga 12-bit colours → 6-bit, 0–60); then 2A0h (672) zero bytes → 768 bytes total. No
     shipped palette has an `AMG:` chunk (resources.md §3); the port can drop this path.
   * Otherwise result NULL.
5. `pal_slot[i] = result`; return result (DX:AX).

A missing file therefore yields NULL without consuming a slot. `EGA:`/`CGA:` chunks are read only
for other adapters and are ignored on VGA.

### 4.2 INTRO `05da:090e` / PS `16e3:0f22` / AP `1d32:400e` — `pal_set`

`void far *pal_set(void far *pal)` — **verified**.

1. `pal_size = pal_size_tab[drv[1D]]`.
2. If `pal_slot[0] == NULL` and `pal_size != 0`: `pal_slot[0] = dos_alloc(2 * pal_size)` (the driver
   palette buffer; no failure check).
3. If `pal == NULL`: return `pal_current` (a getter; nothing uploaded).
4. Else `pal_current = pal`; call driver entry 20 (`set_palette(pal)`); return `pal`.

Note: `pal_set` does **not** reset `fade_level`/`fade_colour` or the cycle blocks.

### 4.3 INTRO `05da:0980` / PS `16e3:0f94` / AP `1d32:4080` — `pal_free`

`void pal_free(void far *pal)` — **verified**. If `pal == NULL` return. For `i = 1..9`: if
`pal_slot[i] == pal` then `dos_free(pal_slot[i])` and `pal_slot[i] = NULL` (the loop continues; a
pointer not in the table is not freed). Does not touch `pal_current` (callers clear their own
copies, e.g. TTM FREE_PAL).

### 4.4 INTRO `05da:09da` / PS `16e3:0fee` / AP `1d32:40da` — `pal_fade`

`void pal_fade(int first, int count, int c, int l)` — **verified**. `fade_level = l`;
`fade_colour = c`; call driver entry 34 `fade_step(first, count, c, l)`. Meaning: colours
`first…first+count−1` are shown at level `l` (63 = the target palette, 0 = all equal to target
colour `c`), linearly mixed per component. AP: no caller.

### 4.5 INTRO `05da:0a00` / PS `16e3:1014` / AP `1d32:4100` — `pal_cycle_block`

`int pal_cycle_block(int first, int count, int step)` — **verified**.

```
if (first < 0) { count = 0; cyc_count = 0; }          /* reset */
if (drv[1F] == 0 || cyc_count >= 9 || count <= 1) return 0;
cyc_start3[cyc_count] = first*3;
cyc_end3[cyc_count]   = (first+count)*3;
if (step < 0) step += count;                          /* only once: step < -count stays negative */
cyc_step3[cyc_count]  = step*3;
return ++cyc_count;
```

Callers: TTM PAL_RESET/PAL_CYCLE (reset with `(-1,0,0)`) and `11d2:1630` / PS `3baf:1631`
(§5.6). AP: no caller.

### 4.6 INTRO `05da:0a7b` / PS `16e3:108f` / AP `1d32:417b` — `pal_cycle_step`

`void pal_cycle_step(void)` — **verified**; **no caller in any program** (not called directly,
not referenced as a far pointer; searched the images for the `off:seg` pair and immediates).

```
if (drv[1F] == 0) return;
cur = pal_slot[0]; tgt = cur + 300h;
far_copy_n(tgt → cur, 300h);                              /* cur := tgt (scratch) */
for (i = 0; i < cyc_count; i++) {
    s = cyc_start3[i]; e = cyc_end3[i]; st = cyc_step3[i];
    far_copy_n(cur+s      → tgt+s+st, e-s-st);            /* shift up by st bytes   */
    far_copy_n(cur+e-st   → tgt+s,    st);                /* wrap the top st bytes  */
}
driver entry 34: fade_step(0, 256, fade_colour, fade_level);   /* re-apply the last fade level */
```

Effect: in every block, colour `i` takes the old value of colour `i − step` (colours move towards
higher indices by `step`, wrapping inside the block), in the **target** half, then the whole
palette is recomputed at the last fade level and uploaded.

### 4.7 INTRO `05da:0b46` / PS `16e3:115a` / AP `1d32:4246` — `far_copy_n`

Near cdecl helper of `pal_cycle_step`: `(far src, far dst, u16 n)`, byte loop `*dst++ = *src++`
(offsets only incremented; no overlap handling). **Verified.**

### 4.8 INTRO `05da:469d` / PS `16e3:49c1` / AP `1d32:67fb` — `far_memmove`

`void far *far_memmove(void far *dst, void far *src, u32 n)` — **verified**. Normalises both
pointers (`05da:4611`: seg += off>>4, off &= 15). If dst ≤ src (normalised linear compare) copies
forwards, else backwards (pointers moved to the last byte via `05da:4640`, `std`); in chunks of at
most 7D00h bytes, re-normalising between chunks. Returns the original `dst`. Implementation detail:
it patches its own near call targets (`cs:4699`, `cs:469B`) to select forward/backward helpers —
self-modifying code; the port uses `memmove`. Used by `pal_load` and other library code.

## 5. TTM palette opcodes

Handler addresses: INTRO `11d2:xxxx` (table `CS:147A`, 47 entries) / PS `3baf:xxxx+1` (table
`CS:147B`). Arguments `a0…a5` are the opcode's words. "skip" = the TTM skip flag (§2.4) is set;
"DAC" = `drv[1F] != 0`. `copy_rect(x,y,w,h)` = INTRO `05da:2fb0` / PS `16e3:35c4` (copy from the
**read page** `drv[16]` to the **write page** `drv[18]`; lead's spec). Page variables: `drv[10]`
third, `drv[12]` back, `drv[14]` front (INTRO `0A90/0A92/0A94`, read `0A96`, write `0A98`; PS
`2310/2312/2314/2316/2318`). All **verified** in INTRO; the PS handlers were compared call by call
(same structure and callees).

### 5.1 `0070` FREE_PAL (INTRO `0b2d`)

If not skip: `s = ctx.pal_slot`; `p = script.pal[s]`; if `p`: if `p == ttm_pal` then `ttm_pal =
NULL`; `pal_free(p)`. Then `script.pal[s] = NULL` (also when skip).

### 5.2 `0400` PAL_RESET (INTRO `0f19`)

If not skip and DAC: `pal_cycle_block(-1, 0, 0)`; `ttm_pal = pal_set(ttm_pal)`; cycle active = 0.
(`pal_set(NULL)` just returns `pal_current`.) Unused by the scripts.

### 5.3 `1061` SEL_PAL slot (INTRO `0a7b`)

`ctx.pal_slot = a0`. If not skip: `ttm_pal = script.pal[a0]`, and **only if `drv[1D] == 4`**
`pal_set(ttm_pal)`. On VGA (id 8) SEL_PAL does **not** change the DAC: the palette becomes visible
at the next FADE_IN / FADE_OUT / PAL_RESET or when the player applies it (INTRO `1125:065c` /
PS `3b02:065d` / AP `24fc:067d`: `if (ttm_pal) { pal_set(ttm_pal); ttm_pal = NULL; }`, TTM part).
(Corrects scripts.md "becomes current (VGA)".)

### 5.4 `F05F` LOAD_PAL name (INTRO `0ac1`)

If not skip: `s = ctx.pal_slot`; if `script.pal[s]` → `pal_free` it; `p = pal_load(name)`;
`script.pal[s] = p`; `ttm_pal = p` (NULL if the file does not exist).

### 5.5 `4114` FADE_OUT first n col speed (INTRO `0bd5`)

```
if (skip) return;
if (DAC) {
    spd = speed_tab[a3];
    if (spd == 0) pal_fade(a0, a1, a2, 0);
    else for (v = 640; v != 0; v -= spd) pal_fade(a0, a1, a2, clamp(v/10, 0, 63));
}
read = back; write = front;  copy_rect(0, 0, 320, 200);          /* present the back page */
if (pages_mode >= 3) { write = third; copy_rect(0, 0, 320, 200); } /* back → third as well */
write = back;
ttm_pal = pal_set(ttm_pal);           /* full-intensity palette immediately */
```

(read page is left = back.) Levels for spd = 80/20/10/5/2/1: v = 640, 640−spd, …, spd →
`v/10` with 64 clamped to 63. **Quirk:** the loop stops at v = 0 without a level-0 step, so the
last level is `spd/10` (8 for speed 1, 2 for speed 2, 1 for speed 3, 0 for speeds 4–6); the fade
then ends with the copy and `pal_set` (full palette of `ttm_pal`). Steps: 8 / 32 / 64 / 128 /
320 / 640 for speed 1–6. Division is signed 16-bit (`idiv`); all spd divide 640 so v hits 0.

### 5.6 `4124` FADE_IN first n col speed (INTRO `0cd9`)

```
if (skip) return;
ttm_pal = pal_set(ttm_pal);                       /* uploads the FULL palette first */
if (DAC) pal_fade(a0, a1, a2, 0);                 /* then the range to colour a2 */
write = front; read = back; copy_rect(0, 0, 320, 200); write = back;
if (DAC) {
    spd = speed_tab[a3];
    if (spd == 0) pal_fade(a0, a1, a2, 63);
    else for (v = 0; v <= 640; v += spd) pal_fade(a0, a1, a2, clamp(v/10, 0, 63));
}
```

Steps: 9 / 33 / 65 / 129 / 321 / 641 (last level 63). Quirk: between `pal_set` and the level-0
upload the DAC briefly holds the full new palette while the old front page is displayed (at most
until the next retrace, since both uploads wait for retrace; usually invisible because the screen
is dark after a FADE_OUT). Colours outside `first…first+n−1` stay at full intensity throughout.

Used values in the 63 scripts: speeds 1–3; ranges `0 256`, `0 255`, `1 255`, `0 128`, `0 176`,
`1 175`; colour 0 always.

### 5.7 `4136` FADE_PART first n col from% to% time (INTRO `0dce`)

No skip test. If DAC:

```
from = ((a3 << 6) / 101) & 63;   to = ((a4 << 6) / 101) & 63;    /* % → level: 100 → 63, 60 → 38 */
ttm_timer_start(&t, (long)a5);                                    /* a5 in 59.17 Hz ticks */
while (!ttm_timer_done(&t)) pal_fade(a0, a1, a2, ttm_timer_value(&t, from, to));
pal_fade(a0, a1, a2, to);
```

No page copy. Each iteration waits one retrace (DAC upload), so the fade advances once per frame
with a level interpolated from elapsed time (§6). If the timer is not installed, only the final
`pal_fade(to)` happens. Used: `0 192 0 100 60 60` (63 → 38 over 60 ticks ≈ 1.01 s) and
`0 256 0 60 0 45` (38 → 0 over 45 ticks ≈ 0.76 s).

### 5.8 `2302/2312/2322` PAL_BLOCK first last, `2402` PAL_CYCLE mask period

PAL_BLOCK (INTRO `0e54`, no skip test): if DAC: `i = (op − 2302h) >> 4`; `blk_first[i] = a0`;
`blk_last[i] = a1`.

PAL_CYCLE (INTRO `0e83`): if not skip and DAC: if `a1 == 0` → `a1 = 1`;
`step = a1 / |a1|` (±1); `cyc_period = |a1|`; `cyc_active = 1`; `pal_cycle_block(-1,0,0)`; for
`i` in 0,1,2 with bit `i` of `a0` set: `ttm_cycle_add(i, step)` = INTRO `11d2:1630` / PS
`3baf:1631`: `pal_cycle_block(blk_first[i], blk_last[i] − blk_first[i] + 1, step)`.

Nothing reads `cyc_period`/`cyc_active` and `pal_cycle_step` is never called (§4.6), so these
opcodes only register blocks. None of the 63 scripts uses them.

### 5.9 AP TTM (`2595:038b`)

Knows `0070`, `1061`, `F05F` with the same handlers (AP globals §2.4; SEL_PAL uploads only for
adapter 4, i.e. never on VGA). No fade opcodes.

### 5.10 Timing summary

| Operation | Step pacing | Duration at 70 Hz (VGA mode 13h-derived timing; likely) |
|---|---|---|
| FADE_OUT speed 1 / 2 / 3 | 1 retrace per step | 8 / 32 / 64 frames ≈ 0.11 / 0.46 / 0.91 s |
| FADE_IN speed 1 / 2 / 3 | 1 retrace per step | 9 / 33 / 65 frames |
| FADE_PART | 1 retrace per step, level from 59.17 Hz ticks | `a5` ticks |
| `pal_set` | 1 retrace | — |

The wait tests "retrace active", so two uploads can fall into the same retrace interval on a fast
machine when little work happens between them; the port should model **one upload per vblank**.

## 6. Timed interpolator (`ttm_timer`)

INTRO `10fc` / PS `22a0` (not in AP). Record `t`: `+0 u32 start`, `+4 u16 duration`. Tick counter
`ticks` (u32) = INTRO `DS:24D8` / PS `DS:52AA`, incremented by the far callback INTRO `0460:000b` /
PS `21f4:0009`, registered with `timer_add(cb, 4)` (INTRO `0460:00d3` → `05da:2307`, PS
`21f4:00cd` → `16e3:291b`): every 4th tick of the 236.7 Hz timer = **59.17 Hz** (reload semantics:
platform spec; likely). `timer_on` = INTRO `DS:15BE` / PS `DS:2E3E`. **Verified.**

* `ttm_timer_start(t, long dur)` (INTRO `10fc:0114`, PS `22a0:018e`): `t.start = ticks`;
  `t.duration = (u16)dur`.
* `ttm_timer_done(t)` (INTRO `10fc:000f`, PS `22a0:0089`): if `!timer_on` return 1; `e = ticks −
  t.start` (u32); return `e >= t.duration`.
* `ttm_timer_value(t, a, b)` (INTRO `10fc:0058`, PS `22a0:00d2`): if `!timer_on` return `a`.
  `e = ticks − t.start`; if `e >= duration` or `duration == 0` return `b`. If `a > b`: swap so
  `lo = b, hi = a` and `e = duration − e`; else `lo = a, hi = b`. `r = lo + (u32)((s32)(hi − lo) *
  (s32)e) / (u32)duration` (Borland `LXMUL@`, then `LUDIV@` unsigned); clamp `r` to `[lo, hi]`;
  return `r` (16-bit).
* INTRO `10fc:0130` / PS `22a0:01aa` (no caller): `t.duration = 0; t.start = ticks − 1`.

Also used by INTRO `1111:0001` (not palette).

## 7. TTM `3103` hardware scroll (INTRO `103d`, PS `30b5`)

Opcode `3103 dir steps dist` → INTRO handler `11d2:1030`: if not skip:
`scroll(a0, a1, a2)` (`103d:0000`), then `ttm_update_rect(0, 0, W, H)` (`1125:096a`). PS: handler
`3baf:1031` → `30b5:000f` (1012 bytes; its own variant that also programs SC/GC; not compared
instruction by instruction — **likely** the same effect). **Used by no shipped script**, AP has no
equivalent. The effect scrolls from the currently displayed picture (front page) to the new
picture (back page) by moving the CRTC start address over an off-screen canvas.

### 7.1 `103d:0000` scroll(dir, steps, dist) — two-screen scroll (dist ≤ 320). Likely (decompile + x86 check of 0933/09f8)

If `dist > 320` → `scroll3(dir, steps, dist)` (§7.3). Invalid if `dir ∉ 0..3`, `steps < 1`,
`dist < 0` or `drv[1D] ∉ {2, 8}`: then **fallback**: write = front, read = back,
`copy_rect(0,0,320,200)`; write = back; read = front (instant cut). Otherwise (VGA):

1. `out(3C4h, 0F02h)` (all planes), `out(3CEh, 4105h)` (GC mode: write mode 1 = latch copy, 256-colour
   bit) — whole-byte (4-pixel) copies inside video memory.
2. Build a **canvas** in video memory at linear VGA address 8050h (segment A800 + 50h; it overwrites
   the third page and 16 KB of unused memory above it), 80 bytes per plane-row (= 320 pixels):
   * dir 0 (new image enters from below): rows 0–199 = front (old), rows 200–399 = back (new);
     start position y = 0, moving +y. `dist` clamped to 200.
   * dir 1 (from above): rows 0–199 = back (new), 200–399 = front (old); start y = 200, moving −y.
   * dir 2 (from the right): 200 rows of 640 pixels: x 0–319 = front, 320–639 = back; start x = 0,
     moving +x. `dist` clamped to 320.
   * dir 3 (from the left): x 0–319 = back, 320–639 = front; start x = 320, moving −x.
   While building, the **third page is saved into the back page** (it is about to be overwritten by
   the canvas); the back page's own content was copied into the canvas first.
3. `base = 8050h`, `screens = 2`. `if (dist < steps) steps = dist;` `d = dist / steps` (quirk:
   `dist == 0` → `steps = 0` → division by zero, INT 0). `dx, dy = ±d` along the direction.
   GC mode back to 4005h (write mode 0). `s = |dx + dy|`.
4. Loop: `for (rem = dist; rem != 0; rem -= s) { show(x, y, first_call && dir >= 2);
   if (rem < s) { clamp dx/dy magnitude to rem; s = rem; } x += dx; y += dy; }` then `show(x, y, 0)`
   and `finish(dir, x, y)`. Positions shown: start, start ± d, …, start ± dist (one per frame).
5. `show(x, y, set_offset)` = `103d:0933` (**verified**): `start = x/4 + y*80 + base`; `pel =
   (x & 3) * 2`. Wait while `in(3DAh) & 8` (retrace over), write CRTC 0Ch/0Dh = start high/low;
   wait until `in(3DAh) & 8` (retrace), `in(3DAh)` (reset the attribute flip-flop), `out(3C0h, 13h)`,
   `out(3C0h, pel)`, `out(3C0h, 20h)` (horizontal pel panning, re-enable display). If `set_offset`:
   `outport(3D4h, ((80*screens/2) << 8) | 13h)` → CRTC offset 80 (160-byte rows) for the horizontal
   canvas. Result on screen: the 320×200 window of the canvas at pixel (x, y).
6. `finish` = `103d:09f8` (**verified**): latch-copy the visible window (canvas at `base + x/4 +
   y*80`, 80 bytes per row, 200 rows, skipping `(screens−1)*80` bytes per row for dir ≥ 2) to the
   **front** page; GC mode 4005h; wait for end of retrace, CRTC start = `(drv[14] − A000h) * 16`
   (the front page), wait for retrace, pel panning 0; for dir ≥ 2 restore CRTC offset 40
   (`outport(3D4h, 2813h)`). Then: read = (`screens > 2` ? front : back), write = third,
   `copy_rect(0,0,320,200)` (restores the saved third page); read = front, write = back, copy
   (back := the final image). Leaves read = front, write = back.

**What the port must emulate** (pixel level; no CRTC model needed): for each position shown,
present one frame composed of the old front image and the new back image offset by (x, y) as
above (pel-exact: `x & 3` panning makes it pixel-exact); pace one position per 70 Hz frame; at
the end front = back = the last shown window (normally the new picture when the full distance is
travelled), third page unchanged, read = front, write = back.

### 7.2 Canvas copy details (for bit-exactness of the "third page saved in back" order)

Copies run backwards (from the last byte) in latch mode, so the order matters only for the
overlapping third-page region; the result is as described (verified from the decompile only;
likely).

### 7.3 `103d:0459` scroll3(dir, steps, dist) — three-screen scroll (dist > 320). Likely

Same structure with `screens = 3`, `base = −48000 = 4480h` (canvas at linear 4480h–FFFFh, i.e.
over all three pages, which are first stacked in the order below via latch copies), `dist` clamped
to 400 (vertical) / 640 (horizontal). Canvas order, top→bottom (dir 0/1) or left→right (dir 2/3):
dir 0 and 2: front, back, third (start 0, moving +); dir 1 and 3: third, back, front (start at the
end: y = 400 / x = 640, moving −). For dir 2/3 the stacked 600 rows are permuted in place into 200
rows of 240 bytes (cycle-following loop with `LXMUL@`/`LUMOD@`; not read in detail). Fallback when
invalid: write = front, read = third, copy; write = back, read = front, copy (instant cut to the
third page). `finish` with `screens = 3` copies the final window to front, then front → third and
front → back. So the effect scrolls through the old picture, the back page and the third page and
ends on the third page.

## 8. AP

### 8.1 AP `0000:189b` — `dac_write(near src, first, count)`

**Verified.** Byte-for-byte the driver's entry 35 (wait `3DAh` bit 3; `3C7h & 3 != 3` → dummy
`out 3C9h`; `out 3C8h, first`; `cli`; `count*3` × `outsb`-style writes from DS:src; `sti`).
AP calls this copy instead of the driver entry. Callers: `5440:07e1` (pending upload), `606e:029d`
(VCR dimmer).

### 8.2 AP `0000:185e` — `dac_read(near dst, first, count)`

**Verified.** Wait until `3DAh` bit 3; `a = in(3C7h) & 3`; if `a != 0` a dummy `in(3C9h)`;
`out(3C7h, first)` (read index); `cli`; `count*3` × `*dst++ = in(3C9h)` (ES = DS); `sti`.
Port: return the shadow DAC. Callers: `565f:022a` (screenshot), `606e:029d`.

### 8.3 AP `5440:07bd` / `5440:07e1` — pending DAC upload (verified)

Globals: `pend_src DS:069F` (near ptr), `pend_first DS:06A1`, `pend_count DS:06A3`.

* `bool pal_request_upload(near src, first, count)` (`5440:07bd`): if `pend_src != 0` return 0;
  else store the three values, return 1. Callers: `1792:0066`, `1792:00c0`.
* `frame_present(bool doit)` (`5440:07e1`, called at the end of the flight frame `5440:018c`):
  if `doit`: `4b31:0041(148h, 3)` (frame timer; sim_flow), `w = 5d3c:0000()` (VCR overlay draw;
  1 if drawn), **page flip** (`1d32:540b` = `jmp [DS:353A]` = driver entry 8, `page_flip(w)`),
  then if `pend_src`: `dac_write(pend_src, pend_first, pend_count)` and clear the three words;
  then `5d3c:0023()`. If `!doit` nothing (no flip, pending stays).
* `5440:0164` clears the three words at frame-loop start (sim init path); `5440:023f`: the per-frame
  palette effect update `17ce:0013` runs **only when no upload is pending**.

Port: apply the pending palette **with the flip** (same presented frame).

### 8.4 AP palette effect system `pal_fx` (segments `51a8`, `1792`; verified unless noted)

Global `fx = DS:5BD8` (near pointer to the record). Record layout:

| Off | Size | Field |
|---|---|---|
| `+000` | u16 | capacity (max entries) |
| `+002` | u16 | n (entries in use = highest index + 1) |
| `+004` | far ptr | base palette (AP passes `DS:408A` = the sim palette `ACES.PAL`) |
| `+008` | 768 | **work palette** (uploaded to the DAC) |
| `+308`…`+386` | s8[127] | delta table `T[d]`, `d = −63…63`, centred at `+347` |
| `+387` | 37 × cap | entries |

Entry (25h = 37 bytes):

| Off | Size | Field |
|---|---|---|
| `+00` | 6 × {u16 first, u16 last} | colour ranges (inclusive); a range with `last == 0` ends the list |
| `+18` | u8 | 1 = the tint colour is the literal RGB at `+19`; 0 = `+19` is a u16 colour index into the work palette |
| `+19` | 3 bytes | RGB (6-bit) or u16 index |
| `+1C` | s16 | target level (8.8 fixed; `0x4000` = 64.0) |
| `+1E` | u16 | rate up (0 = jump) |
| `+20` | u16 | rate down (0 = jump) |
| `+22` | u8 | active |
| `+23` | s16 | current level (8.8) |

Functions:

* `51a8:0000 pal_fx_create(cap, far base)`: `fx = near_alloc(cap*25h + 3ACh)` (`24d3:0059`), zero it,
  `+0 = cap`, `+4 = base`. Caller: `paltrick.c` `51b4:0000` with cap 13 and `DS:408A`.
* `51a8:004e bool pal_fx_add(near src, int i)`: if `i >= cap` return 0; `n = max(n, i+1)`; copy 37
  bytes from `src` to entry `i`; `active = 0`, `current = 0`; return 1. Caller: `51b4:0000` (13
  entries read from the `pal_maps` data file; render3d spec).
* `1792:0000 s16 pal_fx_level(i)` = entry `i`.current. Caller `490a:0554` (entry 6).
* `1792:0021 pal_fx_set_base(far p)`: `+4 = p`. No caller found.
* `1792:0032 pal_fx_set(i, u8 active, s16 target)`: if `target != −1`: `.target = target`, and if
  `target == 0` then `active = 0`; `.active = active`. Callers: `17ce:0013` (per frame), `51b4:0088`
  (initial states: entry 0 off; 9 on 4000h; 10 on 3800h; 5, 8, 11 off; 6, 7, 12 off keeping target),
  `655d:15f7/1610/164f` (damage; sim_world).
* `1792:009b pal_fx_reset_levels()`: every entry `.current = 0` (for `i < n`).
* `1792:0066 pal_fx_show_base()`: `memcpy(work, base, 300h)` (`0000:4abb`);
  `pal_request_upload(work, 0, 256)`. Caller `5440:083a`.
* `1792:00c0 pal_fx_update(bool force)`:
  ```
  memcpy(work, base, 0x300); changed = 0;
  for (i = 0; i < n; i++) {
      e = &entry[i]; old = e->current >> 8;                  /* sar */
      if (e->active) {
          if (e->current < e->target) {                       /* signed */
              if (e->rate_up == 0) e->current = e->target;
              else { e->current += fscale(e->rate_up); if (e->current > e->target) e->current = e->target; }
          } else if (e->current > e->target) {
              if (e->rate_down == 0) e->current = e->target;
              else { e->current -= fscale(e->rate_down); if (e->current < e->target) e->current = e->target; }
          }
      } else if (e->current != 0) {
          if (e->rate_down == 0) e->current = 0;
          else { e->current -= fscale(e->rate_down); if (e->current < 0) e->current = 0; }
      }
      if ((e->current >> 8) != old) changed = 1;
  }
  if (!changed && !force) return;                            /* work = base, nothing queued */
  for (i = 0; i < n; i++) {
      e = &entry[i];
      col = e->literal ? &e->rgb : &work[e->index * 3];      /* index form reads the work palette as modified so far */
      lvl = e->current >> 8;
      for (r = 0; r < 6 && e->range[r].last != 0; r++)
          pal_fx_tint(work, col, e->range[r].first, e->range[r].last, lvl);
  }
  pal_request_upload(work, 0, 256);
  ```
  `fscale(x)` = `362b:00be`: `(s32)x * frame_factor(DS:711E) >> 8`, clamped to s16 (frame-time
  scaling; sim_world owns it). The `-=`/`+=` are 16-bit; the `< 0` test after subtracting in the
  inactive branch is the sign of the 16-bit result.
  Callers: `17ce:0013` (end; `force = 0`, every flight frame when no upload is pending),
  `644a:0913`/`0962` (view palette switch, force 1), `6cdc:0e0b` (map exit, force 1).
* `1792:0286 pal_fx_tint(work, near col, first, last, lvl)`: if `lvl == 0` return. `r,g,b = col[0..2]`
  (read once). If `lvl != fx_cached_level (DS:1910)`: `fx_cached_level = lvl`; build `T`
  (`1792:038a`): for `d = 1…63`: `T[d] = ((d−1) * lvl) >> 6` (arithmetic shift of the 16-bit
  product), `T[−d] = −T[d]`; `T[0]` is never written (0 from the zeroed allocation). Then for
  `k = first … last` (inclusive): `w = work + 3k`; `w[0] += T[r − (s8)w[0]]`, `w[1] += T[g − w[1]]`,
  `w[2] += T[b − w[2]]` (byte adds), then each component clamped to `0…63` (`35ff:0009`, signed
  after sign-extending the byte). Effect: move the range towards the tint by ≈ `lvl/64` of the
  distance (off by one: `(d−1)`).

Who drives it: `17ce:0013` (flight frame, sim_world/sim_flow) computes each entry's active/target
from the game state (entries 0–12; e.g. entries 0 and 4 active with targets `v` and `v >> 1`,
9 and 10 with a common computed target, 1–3 switched by `0802:000c`, 5–8 from flags, 11 with
target `DS:5798`; meanings not traced) and ends with
`pal_fx_update(0)`. Hand-off (the meanings of the 13 entries come from `pal_maps` and paltrick).

### 8.5 AP palette call sites (all verified as call sequences)

| Where | What |
|---|---|
| `4e0d:0000` sim_init | `DS:408A` (far) = `pal_load("ACES.PAL")` (fatal `2494:0127` if NULL), `DS:06B9` = `pal_load("clouds.PAL")`; if `50c8:0000() != 0` or `drv[1F] == 0` → `pal_set(ACES)`, else only screen clears (`368f:03ed/03b6/01f2`). Names built by `55a4:0000(name, "PAL")` |
| `4e0d:03e9` (restart path) at `4e0d:0520` | clear both pages (`1d32:6ab0`), `pal_set(DS:408A)` |
| `5440:083a` loading screen | draw `clouds.SCR`, wait `4b31:0000(148h)`, `pal_set(DS:06B9)` (clouds palette), dissolve-in `368f:017f(4)`, then `pal_fx_show_base()` (sim palette queued for the next flip) |
| `644a:0912`/`0961` cockpit view change (`644a:0271`) | `p = pal_load("ACES.PAL")` resp. `"GUNNER.PAL"`; `memcpy(DS:408A → , p, 300h)` (copy into the base palette); `pal_free(p)`; `pal_fx_update(1)`. GUNNER when entering the rear-gunner view of a two-seater (`DS:3ED8`), ACES when leaving it |
| `6b3d:0000` | same "ACES.PAL → base" copy for view 1 of a two-seater |
| `6cdc:0e0b` in-flight map (`fltmap.c`) | enter: `368f:01a3` (clear), `p = pal_load("fltmap.PAL")`, `pal_set(p)`; exit: `pal_free(p)`, clear, `pal_set(DS:408A)`, `17ce:0008` (`DS:5BE6 = −1`), `17ce:0013` (fx targets + `pal_fx_update(0)`), `pal_fx_update(1)` |
| `5d56:0000` VCR playback start | if `DS:408A` (offset word) non-zero: `pal_set(DS:408A)` |
| `5d56:00c2` demo title (`vcr_demo.c`) | `pal_load("DEMO.PAL")`, clear, `pal_set`, dissolve `368f:017f`, wait, `pal_free` |
| `24fc` TTM | `24fc:067d` apply `ttm_pal` / `24fc:06ec` free (script end); `2595:038b` opcodes §5.9 |
| `606e:029d` VCR message | §8.6 |
| `565f:022a` screenshot | §8.6 |

No fade on sim exit (`sim_exit 4e0d:0bb0` only clears the screen, likely). Library `pal_fade`,
`pal_cycle_*` have no AP caller.

**Cockpit palettes.** The cockpit TTM scripts (`<plane>.TTM`, frame 0 `LOAD_PAL "COCPAL.PAL"`;
also `COCKPIT.PAL`, `GUNPAL.PAL`) run in AP's TTM (`2595:038b`) → `pal_load` → the file is in no
volume and not on disk, `chunk_seek(NULL)` = −1, the `AMG:` fallback also fails → NULL, no slot
used; SEL_PAL does not upload on VGA anyway. No AP code references these names (searched the
image). So nothing is "built": the cockpit is drawn in the sim palette (`ACES.PAL` / `GUNNER.PAL`
+ `pal_fx`). Likely (Dynamix leftovers from a palette-per-cockpit design).

### 8.6 AP `606e:029d` VCR message dimmer and `565f:022a` screenshot palette

* `vcr_message(text)` (`606e:029d`, `rlsmgfx.c`; via `606e:0396` from `5dd0:00d2` "SEEKING
  LOCATION", `5dd0:02b3` "FAST FORWARDING TAPE"): save the mouse/state (`244d:000b`); write page =
  front; draw `text` (`606e:025f`) if non-NULL; if `DS:0B72` (dim option): `dac_read(buf, 0, 175)`
  (colours 0–174), then for `k = 17 … 0`: `buf2[i] = (s8)buf[i] * k / 18` (signed `idiv`, i =
  0…524), `dac_write(buf2, 0, 175)`, `1c0f:0053()` (sim input/timer poll) — 18 steps, one retrace
  each; then `6396:0159(0C5h)`, clear and redraw the text on both pages, and if `DS:0B72`
  `dac_write(buf, 0, 175)` (restore). Colours 175–255 are never dimmed. **Verified.**
* Screenshot (`565f:008a` → `565f:022a` CMAP chunk; caller `60a9:06e0/071f`): if `drv[1F]`:
  `dac_read(buf, 0, 256)`, each byte `<< 2`, write 768 bytes; else a 16-colour EGA map. Port:
  read the shadow DAC.

## 9. PS palette call sites

PS has no direct DAC programming outside the driver except the scroll effect `30b5` (§7). Library
palette callers outside the TTM (verified):

| Where | What |
|---|---|
| `2e8a:005a` (`alert\screen.c`) | `pal_load(open_screen_file(screen[i].name, "pal"))` (`1193:0115`) |
| `2e8a:0124` shell init | keeps screens 11 and 10's palettes loaded permanently (`DS:6022`, `DS:601E`) |
| `2e8a:0087` | palette for screen `i`: cached permanent ones, else a one-entry cache (`DS:6022`, id `DS:2097`; the previous cached palette is freed) or a fresh load |
| `2e8a:038e` screen show | draw the screen, then either hand the palette to the dialog loop (`2b4f:0007` → `DS:200A`) or `16e3:35d1(0)`, `pal_set(p)`, `2e8a:00ee` (free unless cached) |
| `2b4f:0719` dialog loop | after the first draw: if `DS:200A`: `pal_set(DS:200A)`, free via `2e8a:00ee`, clear `DS:200A` |
| `3b02:065d`/`06c6`, `3baf:0540` | TTM (§5) |

So the shell screens **switch palettes instantly, without fades**, once the new screen has been
drawn (the palette upload happens after drawing); all shell fades are TTM-scripted (awards,
newspapers, intro/war-end scripts; opcodes §5). Screen-by-screen ownership: shell_ui.

## 10. Not palette code

* **INTRO `0fca` / PS `3a73`** (11 functions): the TTM **dirty-rectangle (update) list** module, not
  fades: node pool of 1Ah-byte records (`0fca:0001` allocates 5 at a time, free list `DS:331E`,
  count `DS:32F4`), `0fca:0079` adds a rectangle to list `n` (clips to the clip window or screen,
  8-pixel granularity for type 1, merges rectangles whose union wastes ≤ 20 units), `0fca:03cc`
  flushes all lists (`05da:2fb0` copies), `0fca:0584` list lookup. Hand-off to the TTM/lead.
* **INTRO `10f5:0009`** (PS `3ae6:000c`): additive lagged-Fibonacci RNG over 56 words at `DS:1BF2`
  (indices `DS:1BEE`, `DS:1BF0`): `x[j] += x[i]; r = x[j]; i,j = (i+1)%56, (j+1)%56`; used by
  RAND_DELAY `2022`. `10f5:0056(n)` discards `n` values. Not palette.
* **INTRO `05da:45d3`**: returns four coordinates of the rotated-sprite bounding box
  (`DS:1830/1838` indexed by `DS:1840–1846`; TTM `A5A7`). Not palette.
* **AP `368f:00ff`** (`368f:017f`, `01a3`, `01f2`): column dissolve screen transition timed by
  `DS:31E5` — used around palette changes but draws pixels, not palettes (lead/sim_flow).

## 11. Port notes

* **DAC model**: keep a 256×RGB shadow DAC (6-bit). `dac_upload`/`dac_write` = "at the next vblank
  set shadow[first…] = src"; each call consumes one vblank (70 Hz) — this reproduces fade speeds.
  `dac_read` returns the shadow. Present = convert with the shadow at vblank time
  (`v8 = v << 2 | v >> 4` suggested; lead decides). Values above 63 cannot occur from shipped data;
  mask with 3Fh like the hardware.
* `/* PORT: */` the dummy `3C7h`-state writes/reads in the upload/read routines are dropped.
* `/* PORT: */` `far_memmove` (self-modifying) = `memmove`.
* `/* PORT: */` palette cycling stepping (`pal_cycle_step`) and the `AMG:` loader path may be
  omitted (unreachable with shipped data); keep `pal_cycle_block`'s bookkeeping if the TTM
  opcodes are implemented.
* `/* PORT: */` TTM `3103` scroll: implement at pixel level per §7.1 (composite of old front and
  new back per frame) or, since no shipped script uses it, with the fallback cut (low priority).
* AP: apply `pend_*` together with the page flip; `pal_fx` runs once per flight frame; its rate
  scaling depends on the sim frame-time factor `DS:711E` (sim_world).
* Keep the quirks that change pixels/colours: FADE_OUT's last level `spd/10` followed by a full
  `pal_set`; FADE_IN's leading `pal_set`; SEL_PAL not uploading on VGA; `pal_fx_tint`'s `(d−1)`
  table and 16-bit arithmetic; entry order dependence of index-form tints.

## 12. Hand-offs

* **video lead**: `pal_slot[0]` (`drv[19E]`) is allocated by `pal_set`, freed by `gfx_init`;
  `drv[1F]` is the DAC-present flag (0 until the driver init increments it); VGA adapter id
  `drv[1D] = 8`. FADE_OUT/FADE_IN perform `copy_rect` back→front (and back→third when the TTM
  pages mode ≥ 3) — they are the TTM's "present" for faded frames. AP flips with driver entry 8 via
  `1d32:540b` then uploads the pending palette. `pal_load` quirk writes zeros into `drv[1C6..1C9]`
  when all 9 slots are in use. Direct VGA programming exists only in the scroll effect (§7) and the
  AP DAC routines (§8.1–8.2).
* **TTM part**: palette opcode handlers §5 (INTRO `11d2` table `CS:147A`, PS `3baf` `CS:147B`);
  `ttm_cycle_add` INTRO `11d2:1630` / PS `3baf:1631`; `ttm_timer` §6 (INTRO `10fc`, PS `22a0`);
  apply-current-palette INTRO `1125:065c` / PS `3b02:065d` / AP `24fc:067d`; scripts.md
  corrections: SEL_PAL does not upload on VGA; FADE_PART's last argument is a duration in 59.17 Hz
  ticks (not "steps"); `3103` = hardware scroll (INTRO `103d`, PS `30b5`), not a plain copy;
  INTRO `0fca`/PS `3a73` is the update-rect list (§10); PAL_CYCLE never animates.
* **resources/platform**: `pal_load` chunk choice via `pal_tag_tab[adapter]`, `AMG:` fallback
  (12-bit words LE, ×4); `COCPAL/COCKPIT/GUNPAL.PAL` are never found (not in any volume, not
  generated) — resources.md §3 "built by the sim at run time" should read "missing; load returns
  NULL".
* **sim_world / sim_flow**: `17ce:0013` (per-frame palette effect targets, 13 entries; ends with
  `pal_fx_update(0)`), `655d:15f7…164f` (damage effects), `490a:0554` (reads effect 6 level),
  `362b:00be` frame scaling used by `pal_fx_update`, `5440:018c`/`07e1` frame present order,
  `4b31:0041(148h,3)` frame timer. **sim_flow_cockpit**: `644a:0271` view switch loads
  ACES/GUNNER.PAL into the base palette (`DS:408A`) then `pal_fx_update(1)`; `6b3d:0000` idem.
* **render3d**: `51b4:0000` (paltrick) creates `pal_fx` (13 entries from `pal_maps`) and
  `51b4:0088` sets the initial effect states; the base palette `DS:408A` is also what paltrick's
  shade tables were built from.
* **shell_ui**: PS screens switch palettes instantly after drawing (`2e8a:038e`, `2b4f:0719`,
  pending palette `DS:200A`), palette cache `DS:6022/601E/2097`.
* **VCR (sim_flow)**: `606e:029d` dims colours 0–174 to black in 18 steps while showing
  "SEEKING LOCATION"/"FAST FORWARDING TAPE", option flag `DS:0B72`.

## 13. Open questions

* Frame pacing of fades on the original hardware: one step per 70 Hz retrace assumed (the
  "in retrace" test allows two uploads per retrace on very fast machines). Likely.
* Which adapter id is 4 (SEL_PAL uploads immediately for it) — irrelevant for VGA.
* `50c8:0000` condition in `sim_init` (decides whether ACES.PAL is set immediately).
* PS `30b5` scroll not compared instruction by instruction with INTRO `103d`; `103d:0459`'s
  horizontal re-layout loop not read in detail (effect unused).
* The meaning of the 13 `pal_fx` entries (data from `pal_maps`; paltrick/sim_world).
