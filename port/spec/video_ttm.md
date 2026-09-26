# video — part `ttm`: the DGDS TTM animation-script player

Scope: the TTM player shared by the three programs: script loader/indexer, the per-frame
interpreter, the draw/sound dispatchers, the screen-transition ("wipe") routines, the
**update list** (deferred page-to-page rectangle copies = the dirty-rectangle system), the
TTM-only helper modules (tile-map "MTX" animation, bitmap scroller, text box, LFSR
dissolves, timer stepper, random generator), and the frame/timing contract with the callers.
Builds on and corrects `port/formats/scripts.md` (section "Corrections to scripts.md").
Out of scope (cited only): palette load/set/fade primitives (`05da:070b–0b46`), picture/bitmap
loaders and decoders (`0ead`, `0f35`, `0dc5`, `0e2c`, `05da:5001`/`54ae`), library draw
primitives (`05da`/`16e3`/`1d32`), the VGA-register scroll (`103d`/`30b5`), the intro
sequence (`0460`) and the PS/AP callers beyond timing, sound API internals.

Addresses: `SSSS:OOOO` file segments (AP = `work/AP_flat.exe`). The INTRO and PS players are
the same source compiled twice: every PS routine in `3b02`/`3baf` is at the INTRO offset
**+1** (`1125:xxxx` → `3b02:xxxx+1`, `11d2:xxxx` → `3baf:xxxx+1`), except where noted. The AP
copy (`24fc`/`2595`) is a reduced version. Confidence: **verified** = read instruction by
instruction; **likely**; **guess**. Everything below is verified unless tagged.

Driver variables are written `drv[X]` = `DS:(base+X)` with base INTRO `0A80`, PS `2300`,
AP `26C0` (see the lead's `video.md`). Page roles: `drv[10]` **bg** (A800, third page),
`drv[12]` **back**, `drv[14]` **front** (displayed), `drv[16]` **read page**, `drv[18]`
**write page**. VGA driver init: front = A000, back = A400, bg = A800, `drv[1D]` = 8.

## Index

1. Summary for the port (pages, flip, timing)
2. Globals (DS offsets per exe)
3. Data structures (script record, context, update-list node, stepper, MTX state)
4. Loader / indexer / run / free (`1125` / `3b02` / `24fc`)
5. The interpreter `run_frame` (`11d2:053f` / `3baf:0540` / `2595:038b`)
6. Opcode reference (all opcodes, per exe)
7. Draw dispatch (`11d2:01a6` / `3baf:01a7` / `2595:0061`) and sprite helpers
8. Update rectangles after draws (table `CS:1422`/`CS:1423`) and `update_rect`
9. The update list (`0fca` / `3a73`)
10. SAVE_BG / STORE_AREA (`1125:0a2c`, `1125:0a93`)
11. Wipes (`11d2:1688`, `0f88:000a`, `1111:0001`)
12. Helper modules: MTX tile map (`0f48`), bitmap scroller (`0f9e`), text box (`0fb0`),
    random (`10f5`), timer stepper (`10fc`), `2012` hook
13. Sound opcodes (table)
14. Callers: frame loop and timing (INTRO `0460:0174`, PS `21f4:0151`, AP)
15. Library functions called (names used)
16. Corrections to scripts.md / settled questions
17. Port notes
18. Hand-offs
19. Open questions

---

## 1. Summary for the port

* **Every INTRO/PS opcode starts with `write page = read page = back` (`drv[18] = drv[16] =
  drv[12]`)** (`11d2:05bd`). All drawing opcodes therefore draw into the back page. Handlers
  that need other pages (wipes, fades, `B606`, SAVE_BG, STORE_AREA) set pages themselves; the
  next opcode resets them. The AP interpreter does **not** touch the page variables: it draws
  wherever the AP caller (cockpit code `644a`) pointed `drv[18]`.
* **Double buffering with a clean background page (INTRO/PS; `DS:1BC2`/`35AA` = 1, never
  changed).** The background (`LOAD_SCR`, then SAVE_BG) lives in the **bg page A800**. Each
  frame draws only sprites into the back page. After the frame the caller **flips**
  (driver entry 8, with vsync wait) and **flushes the update list**. Every drawing opcode
  queues "copy bg → this back page, this rectangle, one frame later" (key 1); that copy runs
  after the *next* frame's flip, i.e. just before this page becomes the drawing page again,
  and erases the sprites drawn two frames earlier. SAVE_BG/STORE_AREA copy back → bg and
  queue a bg → other page copy after the flip, so both display pages get the new background.
* **Wipes** (`A014–A094`, `A0B5`) copy from the back page (read) **into the front page
  (visible) directly**, during the opcode, with no vsync and (mostly) no delay; the flip at
  the frame end then shows the (identical) back page.
* **Fades** `4114`/`4124` copy back → front (full screen, and back → bg) between the palette
  steps; the palette primitives are the palette module's.
* **Frame timing**: the caller measures from the frame start; the frame delay (`1021`,
  `2022`) is in ticks of a **59.18 Hz** counter (the 236.7 Hz PIT divided by 4: INTRO
  `DS:24D8`, PS `DS:52AA`), sticky until changed (initial 0 = no wait). The in-opcode timed
  effects (`4136` fade steps, `A0B5` dissolve batches) use the stepper of §12.5: in INTRO on the
  59.18 Hz counter `DS:24D8`; **in PS they are effectively untimed** (the PS player mixes two
  clocks, so every wait ends at once — §12.5). AP has no frame delay.
* Level `DS:1CFD` (PS `36E5`, AP `209F`) = 4, or 2 if `drv[1D]` = 0Ch (not VGA). All
  paged effects require level ≥ 3; with VGA they are always on.

## 2. Globals

Script player (per exe). "—" = not present.

| INTRO | PS | AP | Name | Meaning |
|---|---|---|---|---|
| `1CF0` far | `36D8` | `2092` | ttm_rec_list | head of the script-record list |
| `1CF4` far | `36DC` | `2096` | ttm_rec | current script record (set by find/load) |
| `1CF8` near | `36E0` | `209A` | ttm_ctx_list | head of the context list (near, link `+3B`) |
| `1CFA` near | `36E2` | `209C` | ttm_ctx | current context = last one created |
| `1CFC` byte | `36E4` | `209E` | ttm_mtx_open | MTX tile map loaded |
| `1CFD` word | `36E5` | `209F` | ttm_level | 4; 2 if `drv[1D]`=0Ch; paged effects need ≥ 3 |
| `1CDE` 9×near | `36C6` | `2080` | ttm_str_slot[9] | string slots, 41 (29h) bytes each at `1CFF`/`36E7`/`20A1` |
| `1BC0` "` `" | `35A8` | — | ttm_space_str | one-space string (text box) |
| `1BC2` word = 1 | `35AA` | — | ttm_dblbuf | 1 = restore-from-bg mode (never written) |
| `1BC4` word = FFFF | `35AC` | — | upd_src_none | the "no source" page value (mode-4 lists) |
| `1BC6` 9×2 near | `35AE` | — | upd_flush_pairs | (src var, dst var) pointer pairs, §9 |
| `1E7C` | `3864` | — | ttm_no_restore | `0500`=1/`0510`=0: suppress bg restore queuing |
| `1E7E` | `3866` | `2220` | ttm_gosub_depth | >0 while inside GOSUB (offset active) |
| `1E80` 7 words | `3868` | — | ttm_fade_speed[7] | 0, 80, 20, 10, 5, 2, 1 (level step ×10) |
| `3328` | `7604` | — | ttm_full_dirty | set by SAVE_BG; handled at `0FF0` |
| `332A` | `7606` | `6394` | ttm_purge | `0110` / scroller done; never read by callers |
| `332C` | `7608` | `6396` | ttm_goto | `1201` target; never read (GOTO has no effect) |
| `332E` far | `760A` | `639A` | ttm_pending_pal | palette to apply after the frame |
| `3332` 100 bytes | `760E` | `639E` | ttm_argbuf | copied string / polygon argument |
| `3396` | `7672` | — | ttm_1041 | `1041` argument, unused |
| `3398` | `7674` | — | ttm_snd_bank | `C02F` name |
| `33A5` | `7681` | — | ttm_snd_name | `C01F` name |
| `33B2` 3 w | `768E` | — | ttm_cyc_first[3] | palette-cycle block first colour |
| `33B8` 3 w | `7694` | — | ttm_cyc_last[3] | palette-cycle block last colour |
| `33BE` | `769A` | `6408` | ttm_skip | = ctx+0E at frame start; never nonzero |
| `33C0` | `769C` | `6402` | ttm_op | current opcode |
| `33C2` | `769E` | `6406` | ttm_flip | sprite flip flags (op>>4)&0F |
| `33C4` | `76A0` | `6410` | ttm_gosub_dy | |
| `33C6` | `76A2` | `640E` | ttm_gosub_dx | |
| `33C8` | `76A4` | — | ttm_delay | frame delay, FFFF = unchanged |
| `33CA` | `76A6` | — | ttm_cyc_step | abs(step) of `2402` (unused elsewhere) |
| `33CC` | `76A8` | — | ttm_cyc_on | 1 after `2402`, 0 after `0400` (unused elsewhere) |
| `1BEE`,`1BF0`,`1BF2`[56] | `35D6`,`35D8`,`35DA` | — | rnd_j, rnd_k, rnd_tab | §12.4 |
| `1B44` 31 dwords | `3510` | — | lfsr_taps32 | dissolve `A014` taps |
| `1C62` 31 dwords | `364A` | — | lfsr_taps16 | dissolve `A0B5` taps (low words used) |
| `116A`,`116C` | `29EA`,`29EC` | `2DAC` (h) | scr_w, scr_h | 320, 200 (library) |
| `24D8` dword | `52AA` | — | ttm_ticks | 59.18 Hz counter of the caller |
| `24D8` | `52AA` (start, value) / `1CC8` (done test) | — | step_clock | clocks of the stepper (§12.5): INTRO 59.18 Hz; PS mixed 59.18 / 236.7 Hz |
| `15BE` byte | `2E3E` | — | timer_installed | library flag |

Update list (`0fca`/`3a73`): `DS:32F6` (PS `75DA`) 20 near list heads; `DS:331E` (`7602`)
free-node list; `DS:32F4` (`75D8`) number of nodes allocated.
MTX (`0f48`/`39bd`): `1B2A` (PS `34F6`) tile-offset array (near); `1B2C` frame record
(5 words: `1B2C` seg, `1B2E` off, `1B30`, `1B32` w, `1B34` h; PS `34F8..3500`); `1B36`
(`3502`) scroll x; `1B38` (`3504`) scroll y; `1B3A` (`3506`) `"MTX:"`; `32A8`/`32AA`
(`758C`/`758E`) 320−tw, 200−th; `32AC`/`32AE` (`7590`/`7592`) tile w, h; `32B0` 30 near row
pointers (`7594`); `32EC`/`32EE` (`75D0`/`75D2`) map cols, rows.
Scroller (`0f9e`/`3a48`): `32F0` (`75D4`) scroll offset, `32F2` (`75D6`) max frame width.

Driver variables used: `drv[00]` text colour, `drv[02]` text transparent, `drv[03]` clip on,
`drv[04/06/08/0A]` clip x1,x2,y1,y2, `drv[0C]` **fill flag** (1 = filled, 0 = outline, for
rect/circle/polygon), `drv[0D]` fill/bg colour, `drv[0E]` current colour, `drv[10..18]` pages,
`drv[1D]` adapter id, `drv[1F]` palette-effects flag: zeroed by `gfx_init` (`05da:5ca3`) and incremented by the VGA driver's init (`OVL:VGA:` `003B`), so it is **1 with VGA** — fades, cycling and the `A0B5` dissolve are always enabled in the port (settled by the finisher).

## 3. Data structures

### 3.1 Script record (D4h bytes, far, `dos_alloc(0xD4, 1)`)

| Off | Type | Field |
|---|---|---|
| +00 | u16 | id (the loader always stores 0) |
| +02 | u16 | frame count (`PAG:`, default 14Ah) |
| +04 | far | code start (unpacked `TT3:`) |
| +08 | far | code end = start + size − 1 (only the offset is compared) |
| +0C | u16[6] | bitmap handle per slot (near pointer to a 0-terminated array of near frame-record pointers) |
| +18 | u16[6] | font handle per slot |
| +24 | far[6] | palette per slot |
| +3C | far[12] | get/put saved area per slot |
| +6C/+84/+9C/+B4 | u16[12] each | x / y / w / h of the saved areas |
| +CC | far | next record |
| +D0 | far | frame table: (count+1) far pointers to the first opcode of each frame; entry[count] = 0 |

Slot indices are never range-checked (bitmap/font/palette 0–5, get/put 0–11).

### 3.2 Context (3Dh bytes, near `malloc`, created by the indexer for every `1111` TAG)

| Off | Field |
|---|---|
| +00 | script id |
| +02 | tag value |
| +04, +08 | frame index where the TAG was found |
| +0A | FFFF |
| +0E | skip flag (copied to `ttm_skip` at each frame start; never set by any code) |
| +10 | font slot |
| +12 | palette slot |
| +14 | bitmap slot |
| +16 | get/put slot |
| +1C | brush (`1031`, unused) |
| +1E / +1F | fg / bg colour (bytes) |
| +20 | clip enable (byte) |
| +21 / +23 / +25 / +27 | clip x1 / x2 / y1 / y2 (words at odd offsets) |
| +3B | next context |

The interpreter always uses `ttm_ctx` = the **last context created** (the last `1111` TAG of
the last indexed script). If a script has no `1111` TAG, `ttm_ctx` is 0 and all context
accesses go to `DS:0000+off` (quirk; the shipped scripts all have one — likely).

### 3.3 Update-list node (1Ah bytes, allocated in blocks, `calloc(n, 0x1A)`)

| Off | Field |
|---|---|
| +00 | x (in 8-pixel units for mode 1, pixels for mode 4) |
| +02 | y |
| +04 | w (8-pixel units for mode 1) |
| +06 | h |
| +08 | source page segment (FFFF for mode 4) |
| +0A | destination page segment |
| +0C | mode: 1 = page copy, 4 = put buffer |
| +0E | key (frames to wait; decremented by each full flush) |
| +10 | area (w·h in list units) |
| +12 | bit 0 = first node of an allocation block |
| +14 | far pointer (mode 4: buffer for `put_rect`) |
| +18 | next node |

### 3.4 Stepper (6 bytes, on the caller's stack): +0 u32 start tick, +4 u16 duration.

## 4. Loader, indexer, run, free

### 4.1 INTRO `1125:0013` / PS `3b02:0014` / AP `24fc:0016` — ttm_init()
If `drv[1D]` = 0Ch: `ttm_level` = 2. INTRO/PS then `upd_alloc_nodes(100)` (`0fca:0001`/
`3a73:000d`). AP has no update list.

### 4.2 INTRO `1125:002f` / PS `3b02:0030` / AP `24fc:0028` — int ttm_load(name_or_handle)
1. `h = arg`; if `res_is_open(arg)` (`05da:5c7a` / `16e3:59d4` / `7187:0527`) is 0: `h =
   res_open(arg)` (`05da:589e`), remember to close. h = 0 → return −1.
2. `count = 0x14A`; if chunk `"PAG:"` found (`05da:5934`): read u16 count (`049d:0411`).
3. Chunk `"TT3:"` required (else close, −1). `size = chunk_size` (`05da:5c21`); open the
   packed stream (`05da:6b6c(-1, h, "…", size)`), `usize = packed_size` (`05da:702d`),
   `buf = dos_alloc(usize)`, read `usize` bytes (`05da:6f3d`), close stream and file. If the
   byte count read (low word) ≠ usize → free, return −1.
4. Allocate a record (D4h), append at the tail of `ttm_rec_list`, `ttm_rec` = it; +02 =
   count; +D0 = `dos_alloc((count+1)*4, 1)`; +04 = buf; +08 = buf + usize − 1; +00 = 0.
   Return 1. (Allocation failures jump back to "return −1" and leak.)

### 4.3 `1125:02b7` / `3b02:02b8` / `24fc:02c9` — ttm_find(id)
Walk the list from the head; `ttm_rec` = the first record with +00 == id → return 1; else
`ttm_rec` = 0, return 0.

### 4.4 `1125:02f8` / `3b02:02f9` / `24fc:0311` — ttm_new_ctx(frame, id, tag)
`malloc(0x3D)` (near), appended to `ttm_ctx_list` (walk `+3B`), `ttm_ctx` = it; if non-null:
zero it, +04 = +08 = frame, +00 = id, +02 = tag, +0A = −1.

### 4.5 `1125:0380` / `3b02:0381` / `24fc:039c` — far char *skip_str(far p)
Skip the NUL-terminated string; if its length (without NUL) is even, skip one more byte
(i.e. string + NUL padded to even). Returns the pointer after it.

### 4.6 `1125:0006` / `3b02:0007` / `24fc:0009` — u16 peek(far p) = *p.

### 4.7 `1125:03a7` / `3b02:03a8` / `24fc:03c5` — int ttm_index(id)
`ttm_find(id)` else return 0; code start null → 0. Clear frame table entries 0..count.
`p = start`, `frame = 0`, `tagframe = 0`; loop `i` over 0..count−1: table[i] = p; then scan:
while true: if `rec+08 <= p.off` → return 0 (script too short); `op = *p; p += 2`:
* `op == 0FF0`: tagframe++, next i (store the next frame start).
* nibble 0: nothing. Nibble 1: read the argument, p += 2; if op == `1111`:
  `ttm_new_ctx(tagframe, id, arg)` (only `1111`, not `1101`).
* nibbles 2–7: p += 2·n. Nibbles 8–E: **return −1**.
* nibble F: `AF1F`/`AF2F`: `n = *p`, p += 2 + 4n; other: `p = skip_str(p)`.
Return 1 when all `count` frame starts are stored.

### 4.8 `1125:05ee` / `3b02:05ef` / `24fc:0610` — int ttm_run(frame)
`r = ttm_run_frame_checked(frame)` (`1125:060e`: returns 0 if no record, frame < 0,
frame ≥ count or table[frame] null; else `run_frame(frame)`), then `ttm_apply_pal()`
(`1125:065c`: if `ttm_pending_pal` non-null: `pal_set(pending)` (`05da:090e`/`16e3:0f22`/
`1d32:400e`), pending = 0). Returns r. **The pending palette is applied after the frame's
opcodes and before the caller's page flip.**

### 4.9 `1125:06c5` / `3b02:06c6` / `24fc:06ec` — ttm_free(id)
`ttm_find(id)` else return. If `ttm_mtx_open`: `mtx_close()`, flag = 0. Free fonts
(`05da:4e01`), bitmaps (`0f2c:0002` → `05da:53c1`), palettes (clearing `ttm_pending_pal`
if equal; `05da:0980`), the 12 saved areas, the frame table, the code; unlink the record
from the list and free it. Contexts are not freed here.

### 4.10 `1125:0685` / `3b02:0686` / `24fc:06a6` — ttm_free_all()
`ttm_free(head->id)` until the list is empty; free every context; `ttm_ctx = 0`.
`1125:095c` / `3b02:095d` = `upd_free_all()` (`0fca:0543`) + `ttm_free_all()`.
AP `24fc:0989` = `ttm_free_all()` (+ nothing else visible here).

## 5. The interpreter — INTRO `11d2:053f` / PS `3baf:0540` / AP `2595:038b`
`int run_frame(int frame)` (far, recursive through GOSUB). Returns 0 if no record, else 1
when `0FF0` is reached.

```
p = rec->frametab[frame]            (no range check here)
ttm_skip = ctx->+0E                 (always 0)
ttm_goto = -1
loop:
  op = *p; ttm_op = op; n = op & 0x0F
  if op == 0x1301: op = 0xC051; if op == 0x1311: op = 0xC061    (ttm_op rewritten)
  if op == 0x0FF0: goto frame_end
  [INTRO/PS only]  drv[18] = drv[12]; drv[16] = drv[12]      // write = read = back
  p += 2
  a0..a6 = the 7 words at p (always read, whatever n is)
  if n == 0x0F:
      if op in (AF1F, AF2F): str = copy_arg(a0*4, p+2) ; p += a0*4 + 2
      else:                  str = copy_arg(0, p)      ; p = skip_str(p)
  else: str = 0; p += 2n
  if ttm_gosub_depth and 0xA000 <= op <= 0xAFFF:              // table CS:1536 (4 entries)
      A0A4: a2 += dx; a3 += dy; then a0 += dx; a1 += dy
      A601, AF1F, AF2F: no offset
      others: a0 += dx; a1 += dy
  class C (op & F000 == C000): [INTRO/PS] if !ttm_skip: sound_op(a0,a1,a2,a3,str); [AP] ignored
  class A: draw_op(a0..a6, str)   (§7; called whatever ttm_skip is)
  else: table CS:147A (INTRO) / CS:147B (PS) / CS:0A75 (AP): 47 / 47 / 21 opcodes (§6);
        not found: F10F..F19F → SET_STRING; anything else (0000, unknown) ignored
  [INTRO/PS] if 0xA000 <= op <= 0xAFFF: update rectangle (§8)
  goto loop
frame_end:
  [INTRO/PS] if ttm_full_dirty:
      if ttm_level >= 3:
          c = drv[03]; drv[03] = 0
          upd_add(0, 0, scr_w, scr_h, 1, src = ttm_dblbuf ? drv[10] : drv[12],
                  dst = drv[14], key 0, 0)
          drv[03] = c
      ttm_full_dirty = 0
  return 1
```

`copy_arg(count, far src)` (`11d2:15b3` / `3baf:15b4` / `2595:0b4a`): into `ttm_argbuf`:
if `count >= scr_h` (200!) → empty string; count 0 → copy up to the NUL; else copy `count`
bytes; append NUL; return `ttm_argbuf`. The buffer is 100 bytes (INTRO `3332..3395`); longer
strings overflow into `ttm_1041`… (quirk).

`find_tag(tag)` (`11d2:1546` / `3baf:1547` / `2595:0ad9`): for i = 0,1,…: if table[i] is
null → return −1; if the first opcode of frame i is `1101` or `1111` and its argument ==
tag → return i. (Scans until a null entry = entry `count`.)

## 6. Opcode reference

Arguments `a0…a6` are signed 16-bit. "skip" = does nothing when `ttm_skip` (never true).
Handler offsets: INTRO `11d2:` (PS = +1). AP column: handler `2595:` or "—" (not handled =
ignored).

| Op | Name | INTRO | AP | Effect |
|---|---|---|---|---|
| `0010` | NOP | 0bc6 | — | nothing |
| `0020` | SAVE_BG | 0f8a | — | skip; `save_bg()` (§10) |
| `0070` | FREE_PAL | 0b2d | 08e5 | skip; s = ctx+12; if pal[s]: if == pending → pending = 0; `pal_free(pal[s])`; pal[s] = 0 |
| `0080` | FREE_BMP | 084b | 0603 | skip; s = ctx+14; if bmp[s]: `bmp_free` (`0f2c:0002`/`39a1:0002`/`26d2:0001`); bmp[s] = 0 |
| `0090` | FREE_FONT | 0a49 | 07f7 | skip; f = &font[ctx+10]; if *f: `font_free` (`05da:4e01`/`16e3:5125`/`7115:0372`); *f = 0 |
| `00C0` | FREE_GETPUT | 0995 | 0742 | skip; free saved[ctx+16] (`dos_free`), = 0 |
| `00E0` | MTX_CLOSE | 07c9 | — | skip; if `ttm_mtx_open`: `mtx_close()`, flag = 0 |
| `0110` | PURGE | 10b1 | 09b7 | `ttm_purge = 1` (no reader: no effect) |
| `0400` | PAL_RESET | 0f19 | — | skip; if drv[1F]: `pal_cycle(-1,0,0)`; `pending = pal_set(pending)` (return value stored back); `ttm_cyc_on = 0` |
| `0500` / `0510` | NO_RESTORE on/off | 110e / 1117 | — | `ttm_no_restore = 1 / 0` |
| `0FF0` | FRAME_END | — | — | end of frame (§5) |
| `1011` | | 0bc9 | — | driver entry 25 (`05da:2fb5`/`16e3:35c9`) with a0: `retf` in VGA → no-op |
| `1021` | SET_DELAY | 0f81 | — | `ttm_delay = a0` (59.18 Hz ticks, §14) |
| `1031` | SET_BRUSH | 07e4 | 05a1 | ctx+1C = a0 (unused) |
| `1041` | | 0bbd | — | `ttm_1041 = a0` (unused) |
| `1051` | SEL_BMP | 07f1 | 05ae | ctx+14 = a0 |
| `1061` | SEL_PAL | 0a7b | 0829 | ctx+12 = a0; skip; `pending = pal[a0]`; if `drv[1D] == 4`: `pal_set(pending)` now (not VGA). Otherwise applied after the frame (§4.8) |
| `1071` | SEL_FONT | 09e8 | 0795 | ctx+10 = a0; `font_select(font[a0])` (`05da:2fc1`/`16e3:35d5`/`1d32:540f`) |
| `1101`,`1111` | TAG | 10ba | 09c0 | no-op (labels, §5 find_tag; `1111` also creates a context at index time) |
| `1121` | SEL_GETPUT | 0891 | 0644 | ctx+16 = a0 |
| `1201` | GOTO | 10ff | 0a04 | `ttm_goto = find_tag(a0)`; nobody reads it → **no effect** |
| `2002` | SET_COLORS | 0751 | 056e | ctx+1E = drv[0E] = drv[00] = (u8)a0; ctx+1F = drv[0D] = (u8)a1 |
| `2012` | HOOK | 105f | — | INTRO `0fc9:000c` = empty (no-op). PS `2221:0111(a0, a1)`: if far ptr `DS:1B80[a0]` (3 entries: `2221:0003`, `2221:0107`, `2221:0107`) is non-null, call it (shell code, hand-off) |
| `2022` | RAND_DELAY | 0f58 | — | skip; `r = rnd()`; `ttm_delay = a0 + abs((int)(r % (u16)(a1 − a0)))` (`div` unsigned; a1 == a0 → divide error) |
| `2032` | MTX_SCROLL | 07ab | — | skip; if MTX open: `mtx_scroll(a0, a1)` (§12.1) |
| `2302/2312/2322` | PAL_BLOCK | 0e54 | — | if drv[1F]: i = (op−2302)>>4; `ttm_cyc_first[i] = a0`, `ttm_cyc_last[i] = a1` |
| `2402` | PAL_CYCLE | 0e83 | — | skip; if drv[1F]: s = a1 (0 → 1); dir = s/abs(s); `ttm_cyc_step = abs(s)`; `ttm_cyc_on = 1`; `pal_cycle(-1,0,0)`; for bit b in 0..2 of a0: `pal_cycle(first[b], last[b]−first[b]+1, dir)` (`11d2:1630`; `05da:0a00`/`16e3:1014`) |
| `3003` | GOSUB | 10bd | 09c3 | depth++; `dx = a0`, `dy = a1`; `was0 = (ttm_purge == 0)`; `run_frame(find_tag(a2))` (−1 not checked); if `ttm_purge && was0`: ttm_purge = 0; depth−−. dx/dy are **not restored** (a nested GOSUB changes the outer offset); the inner frame's `0FF0` also does the §5 frame-end work |
| `3103` | SCROLL | 1030 | — | skip; INTRO `103d:0000(a0,a1,a2)` / PS `30b5:000f(a0,a1,a2)` (VGA-register effect, out of scope); then `update_rect(0,0,320,200)` |
| `4004` | SET_CLIP | 106f | 0975 | ctx+21 = drv[04] = a0 (x1); ctx+25 = drv[08] = a1 (y1); ctx+23 = drv[06] = a2 (x2); ctx+27 = drv[0A] = a3 (y2); ctx+20 = drv[03] = 1. Inclusive |
| `4114` | FADE_OUT | 0bd5 | — | §6.1 |
| `4124` | FADE_IN | 0cd9 | — | §6.1 |
| `4136` | FADE_PART | 0dce | — | §6.1 (no skip test) |
| `4204` | STORE_AREA | 0f99 | — | §10 |
| `4214` | SAVE_GETPUT | 089e | 0651 | skip; s = ctx+16; x[s],y[s],w[s],h[s] = a0..a3; free saved[s]; `size = rect_size(w,h)` (driver entry 6, **low word only**); if size: saved[s] = `dos_alloc(size)`; `get_rect(saved[s], a0, a1, a2, a3)` (entry 5, from the **read page = back** in INTRO/PS; the caller's read page in AP) |
| `5005` | | 102d | — | no-op |
| `B000` | SCROLLER_INIT | 111f | — | skip; `scroller_init()` (§12.2) |
| `B013` | SCROLLER_STEP | 112d | — | `scroller_step(a0, a1, a2)` (no skip test) |
| `B606` | COPY_AREA | 0fed | — | skip; `drv[16] = page(a4)`, `drv[18] = page(a5)`, `copy_rect(a0,a1,a2,a3)` (entry 4); then drv[16] = drv[14], drv[18] = drv[12]. page(v) (`11d2:165f`): 0 → front, 2 → bg, anything else → back |
| `F01F` | LOAD_SCR | 0771 | 058e | skip; `scr_load(name)` (`0f35:000a`/`39aa:000a`/`6f83:0000`; decodes into the current write page = back, likely); INTRO/PS then `save_bg()`. **AP: no save_bg** |
| `F02F` | LOAD_BMP | 07fe | 05bb | skip; s = ctx+14; free bmp[s]; bmp[s] = `bmp_load(name)` (`0ead:0002`/`3922:0002`/`6f97:0000`) |
| `F04F` | LOAD_FONT | 0a09 | 07b7 | skip; f = &font[ctx+10]; free; *f = `font_load(name)` (`05da:4a8f`/`16e3:4db3`/`7115:0000`); `font_select(*f)` |
| `F05F` | LOAD_PAL | 0ac1 | 086f | skip; s = ctx+12; free pal[s]; pal[s] = `pal_load(name)` (`05da:070b`/`16e3:0d1f`/`1d32:3e0b`); `pending = pal[s]` |
| `F08F` | MTX_OPEN | 0789 | — | skip; if open: `mtx_close()`; `ttm_mtx_open = mtx_open(name)` (§12.1) |
| `F10F–F19F` | SET_STRING | 113e | 0a12 | i = (op−F10F)>>4; `strcpy(str_slot[i], str)` (no length check; slots are 41 bytes); `str_slot[i+1..8][0] = 0` |
| `Axxx` | draw | §7 | §7 | |
| `Cxxx` | sound | §13 | ignored | |

Opcodes the AP table lacks (all non-A, non-C, non-F1x ops except the 21 listed in
scripts.md) are silently ignored in AP; in particular AP has no delay, fades, SAVE_BG,
STORE_AREA, wipes or MTX.

### 6.1 Fades (INTRO/PS only; palette primitives cited)

`fade_step(first, count, colour, level)` = `05da:09da` / `16e3:0fee` (driver entry 34: current
= target·l/63 + target[colour]·(63−l)/63). `speed = ttm_fade_speed[a3]` (index unchecked).
`lvl(v) = clamp(v / 10, 0, 63)` (signed division).

**`4114` FADE_OUT(first=a0, count=a1, colour=a2, speed=a3)** — skip:
1. If drv[1F]: if speed == 0: `fade_step(a0,a1,a2,0)`; else for `v = 640; v != 0; v −= speed`:
   `fade_step(a0,a1,a2,lvl(v))` (no timing: CPU/vsync bound by the driver's upload; a speed
   that does not divide 640 loops forever — quirk; the table values all divide 640).
2. `drv[16] = back, drv[18] = front`; `copy_rect(0,0,scr_w,scr_h)` (back → front).
3. If `ttm_level >= 3`: `drv[18] = bg`; `copy_rect(0,0,scr_w,scr_h)` (back → bg).
4. `drv[18] = back`; `pending = pal_set(pending)`.

**`4124` FADE_IN(first, count, colour, speed)** — skip:
1. `pending = pal_set(pending)` (before anything else).
2. If drv[1F]: `fade_step(a0,a1,a2,0)`.
3. `drv[18] = front, drv[16] = back`; `copy_rect(0,0,scr_w,scr_h)`; `drv[18] = back`.
4. If drv[1F]: speed == 0 → `fade_step(a0,a1,a2,63)`; else `for v = 0; v <= 640; v += speed`:
   `fade_step(a0,a1,a2,lvl(v))`.

**`4136` FADE_PART(first, count, colour, from%, to%, dur)** — if drv[1F] (no skip test):
`l1 = ((a3 << 6) / 101) & 63`, `l2 = ((a4 << 6) / 101) & 63` (signed 16-bit); stepper init
(dur = a5); while `!step_done`: `fade_step(a0,a1,a2, step_value(l1, l2))`; finally
`fade_step(a0,a1,a2,l2)`. Timed by the stepper (§12.5): INTRO 59.18 Hz ticks; in PS
`step_done` is true immediately, so only the final `fade_step(…, l2)` happens (quirk).

## 7. Draw dispatch — INTRO `11d2:01a6` / PS `3baf:01a7` / AP `2595:0061`
`int draw_op(x=a0, y=a1, a2, a3, a4, a5, a6, str)`; returns 0, or −1 for an unknown A-op.
Table `CS:04DB` (INTRO, 25 entries) / `CS:04DC` (PS) / `CS:032F` (AP, 23 entries: no
`A304`, `A704`). All drawing goes to the current write page with the driver's clipping.

| Op | Args | Library call (INTRO / PS / AP) | Effect |
|---|---|---|---|
| `A002` PIXEL | x y | `gfx_pixel(x, y, (s8)drv[0E])` `05da:48fd`/`16e3:4c21`/`1d32:6a5b` | put pixel if inside the clip window (when clip on) → entry 22 |
| `A0A4` LINE | x1 y1 x2 y2 | `gfx_line(x1,y1,x2,y2)` `05da:3957`/`16e3:3c7b`/`1d32:5ab5` | colour drv[0E] |
| `A104` RECT_FILL | x y w h | drv[0C] = 1; `gfx_rect(x,y,w,h)` `05da:645b`/`16e3:61b5`/`1d32:6ab0` | filled |
| `A114` RECT | x y w h | drv[0C] = 0; `gfx_rect`; drv[0C] = 1 | outline |
| `A404` / `A424` CIRCLE_FILL / CIRCLE | x y w h | drv[0C] = 1 / 0; r = h>>1 (sar); `gfx_circle(r, x+r, y+r)` `05da:0408`/`16e3:035a`/`1d32:6bbc`; drv[0C] = 1 | w ignored |
| `A5f4` SPRITE | x y frame slot | `ttm_flip = (op>>4)&0F` (0–3); `bmp_draw(fr, x, y, flip)` `0f2c:0032`/`39a1:0032`/`26d2:0031` | §7.1 |
| `A5f5` SPRITE_COL | x y frame slot col | `sprite_col(fr, x, y, flip, (u8)col)` `11d2:0148`/`3baf:0149`/`2595:0002` | §7.1 |
| `A5f6` SPRITE_SCALE | x y frame slot w h | `gfx_sprite_scaled(fr, x, y, flip, w, h)` `05da:25a6`/`16e3:2bba`/`1d32:49f4` | |
| `A5A7` SPRITE_ROT | x y frame slot a4 a5 a6 | `gfx_sprite_rotated(fr, x, y, a6, a4, a5, fr.w>>1, fr.h>>1)` `05da:3cfd`/`16e3:4021`/`1d32:5e5b` | a6 = angle (0–FFFF, likely), a4/a5 = size (guess), pivot = frame centre (likely); flip flags ignored |
| `A601` PUT_GETPUT | slot | skip; if saved[slot]: `put_rect(saved, x[s], y[s], w[s], h[s])` (entry 7) `05da:492f`/`16e3:4c53`/`1d32:6a8d` | GOSUB offset not applied |
| `A704` MTX_DRAW | x y w h | if MTX open: `mtx_draw(x,y,w,h)` (§12.1) | INTRO/PS only |
| `A304` TEXTBOX | x y w h | `textbox(x,y,w,h)` `0fb0:000c`/`3a5a:000d` (§12.3) | INTRO/PS only |
| `AF02` FLOOD | x y | `gfx_flood(x, y, drv[0D])` `05da:2893`/`16e3:2ea7`/`1d32:4ce1` | |
| `AF1F` / `AF2F` POLY / POLY_FILL | n, data | drv[0C] = 0 / 1; `k = data[0]`; `gfx_polygon(k, &data[1], &data[1+k])` `05da:0b91`/`16e3:11a5`/`1d32:09ce`; drv[0C] = 1 | xs[] then ys[]; data layout guess: `k, x1..xk, y1..yk` (+pad) in the 2n words; unused by the scripts |
| `A014–A094`, `A0B5` WIPE | x y w h [a4] | INTRO/PS: if !skip and w > 0 and h > 0 and x+w ≤ 320 and y+h ≤ 200: `wipe(x,y,w,h,a4,op)` (§11). **AP: no-op** | |
| `A204–A294` TEXT | x y (w h) | `font_select(font[ctx+10])`; drv[02] = 1; `gfx_text(str_slot[(op−A204)>>4], x, y)` `05da:33f7`/`16e3:3a0b`/`1d32:5845`; drv[02] = 0 | transparent, colour drv[00]; w,h ignored |

Frame lookup for `A5xx`: `h = rec.bmp[slot]`; if h = 0 → nothing; `fr = ((u16*)h)[frame]`
(near frame record, 5 words: +0 seg, +2 off, +4 type, +6 w, +8 h); fr = 0 → nothing (no
range check on frame).

### 7.1 Sprite helpers

**`bmp_draw(fr, x, y, flip)`** — INTRO `0f2c:0032` / PS `39a1:0032` / AP `26d2:0031`, by
`fr+4` (type):
* −3 (FFFD): `05da:06e9(fr, x, y)` / `16e3:063b` / `1d32:3de9` — flip ignored.
* −2 (FFFE): `05da:1e38(fr, x, y, flip)` / `16e3:244c` / `1d32:4286` (SCN-type bitmap).
* −1 (FFFF): `0dc5:0049(fr, x, y, flip)` / `383a:0049` / `6f1c:003f` (packed bitmap).
* other: `05da:06e5(fr, x, y, flip)` / `16e3:0637` / `1d32:3de5` (plain bitmap →
  `blit_sprite_flip`, likely).

**`sprite_col(fr, x, y, flip, col)`** — INTRO `11d2:0148` / PS `3baf:0149` / AP `2595:0002`:
only if `fr+4 == −2`: normalise the far pointer (`seg += off>>4; off &= 0Fh`, written back
into the frame record), save the first pixel byte, store `col` there, draw with
`05da:1e38(fr, x, y, flip)`, restore the byte. (The SCN format keeps its base colour in the
first byte, resources.md §4c.) Other types draw nothing.

## 8. Update rectangles after draws (INTRO/PS only)

After every opcode in A000–AFFF (whether or not it drew), the interpreter calls
`update_rect(x, y, w, h)` (`1125:096a` / `3b02:096b`) with a rectangle chosen by table
`CS:1422` (INTRO, 22 entries) / `CS:1423` (PS); args are after the GOSUB offset:

| Op | Rectangle |
|---|---|
| `A002` | (x, y, 8, 1) |
| `A0A4` | (min(x1,x2), min(y1,y2), \|x1−x2\|+8, \|y1−y2\|+2) |
| `A404`, `A424` | (x−20, y, w+48, h+1) |
| `A504–A536` (all 12) | if low nibble 6: (x, y, a4, a5); else if frame exists: (x, y, \|fr.w\|, fr.h+2) if fr.w ≠ 0; nothing if the bitmap/frame is missing |
| `A5A7` | `gfx_last_bbox(&x1,&y1,&x2,&y2)` (`05da:45d3`/`16e3:48f7`): (x1, y1, x2−x1, y2−y1) |
| `A601` | if saved[a0]: (x[s], y[s], w[s], h[s]) |
| `A704` | if MTX open: (x, y, w, h) |
| `AF02` | none |
| `AF1F`, `AF2F` | (0, 0, 320, 200) |
| all others (`A104`, `A114`, `A304`, `A2x4`, wipes, unknown) | (x, y, w+8, h+2) |

**`update_rect(x, y, w, h)`** — INTRO `1125:096a` / PS `3b02:096b`:
* `ttm_dblbuf` ≠ 0 (always): if `!ttm_no_restore && ttm_level >= 3`:
  `upd_add(x, y, w, h, 1, src = drv[10] (bg), dst = drv[12] (back), key 1, 0)`.
* `ttm_dblbuf` = 0 (dead code): `upd_add(…, back → front, key 0)`; `upd_add(…, back →
  front, key 1)`; if `!no_restore && level >= 3`: `upd_add(…, bg → back, key 0)`.

So the "update list" entries created by drawing are **background restores**, not
screen updates: the drawn pixels reach the screen by the page flip.

## 9. The update list — INTRO `0fca` / PS `3a73`

A pool of nodes (§3.3) in up to 20 lists; each list holds nodes with the same (source
segment, destination segment, key); list heads `DS:32F6[20]`.

**`upd_alloc_nodes(n)`** `0fca:0001` / `3a73:000d`: n rounded up to a multiple of 5;
`calloc(n, 0x1A)`; first node +12 = 1; link all into the free list; `+= n` to `DS:32F4`.
Returns 1 (0 if the allocation failed).

**`upd_find(src, dst, key)`** `0fca:0584` / `3a73:0590`: for the 20 heads: non-empty head
whose first node has +0E == key, +08 == src, +0A == dst → return &head; else return the
first empty head slot, or 0 if none.

**`upd_add(x, y, w, h, mode, src, dst, key, far p)`** `0fca:0079` / `3a73:0085`:
1. mode 4: src = −1.
2. `L = upd_find(src, dst, key)`; 0 → return (rectangle dropped).
3. mode 1 only — clip and convert to 8-pixel columns:
   * if drv[03] (clip on): reject if `x > x2c`, `x+w < x1c`, `y > y2c` or `y+h < y1c`
     (drv[04..0A]); clip x/y to x1c/y1c (reducing w/h), `w = x2c − x + 1` if
     `x+w−1 > x2c`, same for h.
   * else: reject if `x > scr_w−1`, `x+w < 0`, `y > scr_h−1`, `y+h < 0`; clip to the screen.
   * `w = (w + x%8 + 7) / 8`, `x = x / 8` (signed division). If w == 0 or h == 0 → return.
4. Take a node from the free list (if empty `upd_alloc_nodes(5)`, fail → return); fill
   +00..+16; +10 = w·h.
5. mode 1: **merge** — scan the list L: for each node d: `U` = bounding box of d and the new
   node; if `d.area + new.area + 20 >= area(U)`: new = U (area = area(U)), unlink and free
   d, and continue scanning (wrapping round to the head) until the node after the last
   merged one is reached again; otherwise continue with the next node (see
   `0fca:02b2..03b6` for the exact circular scan).
6. Insert the new node at the head of L.

**`upd_flush_list(src, dst, key)`** `0fca:05ce` / `3a73:05da`: find L (none/empty →
return); `drv[16] = L.first.src`, `drv[18] = L.first.dst`; for each node: mode 1:
`copy_rect(x·8, y, w·8, h)` (driver entry 4, read → write page, whole 4-pixel columns);
mode 4: `put_rect(p, x, y, w, h)` (entry 7). Return all nodes to the free list; head = 0.
Page variables are left as set.

**`upd_flush(only_front)`** `0fca:03cc` / `3a73:03d8` (called by the frame loop with 0):
save drv[16]/drv[18]; walk the pair table `DS:1BC6` (PS `35AE`), each pair = (pointer to
source page variable, pointer to destination page variable), resolved **at flush time**:

| # | src | dst |
|---|---|---|
| 0 | none (FFFF) | front |
| 1 | back | front |
| 2 | none | back |
| 3 | bg | back |
| 4 | none | bg |
| 5 | front | bg |
| 6 | front | back |
| 7 | back | bg |
| 8 | bg | front |

With `only_front` ≠ 0 start at pair 1 and stop after it. For each pair
`upd_flush_list(*src, *dst, 0)`. Restore drv[16]/drv[18]. If `only_front` == 0: decrement
+0E of every node of every list (key 1 → 0: flushed after the next frame).
Because a node stores segment values captured when it was added and the pairs are resolved
after the flip, e.g. "bg → back" nodes added during frame N (dst = page P) are copied at
the flush after frame N+1, when P is the back page again.

Other: `upd_discard(src, dst, key)` `0fca:0679` / `3a73:0685` frees a list without copying;
`upd_free_lists()` `0fca:0461` / `3a73:046d` returns every list to the free list;
`upd_free_all()` `0fca:0543` / `3a73:054f` frees the node blocks (walks the free list,
freeing block heads; `DS:331E = 0`); `upd_count()` `0fca:057a` / `3a73:0586` returns
`DS:32F4`; `0fca:049b` (uncalled) returns the mode of the first mode-1 node overlapping a
rectangle; `0fca:06b9` (uncalled) re-adds a list into another and loops forever (bug).

## 10. SAVE_BG and STORE_AREA (INTRO/PS)

**`copy_back_to_bg(x, y, w, h)`** `1125:0a93` / `3b02:0a94`: if level ≥ 3: save
drv[16]/drv[18]; `drv[16] = back (drv[12])`, `drv[18] = bg (drv[10])`;
`copy_rect(x, y, w, h)`; restore.

**`save_bg()`** `1125:0a2c` / `3b02:0a2d` (opcodes `0020`, `F01F`): `ttm_full_dirty = 1`;
if level ≥ 3: `copy_back_to_bg(0, 0, scr_w, scr_h)`;
`upd_discard(bg, back, key = ttm_dblbuf)` (drops this frame's pending restores);
else: `upd_add(0,0,scr_w,scr_h, 1, back, front, key 0, 0)`.
At the frame end (§5) the full-dirty flag queues bg → front(now) key 0, which after the flip
copies the whole new background into the page that becomes the back page.

**`4204` STORE_AREA(x, y, w, h)** (`11d2:0f99`): skip; if level ≥ 3:
`copy_back_to_bg(x,y,w,h)`; `upd_add(x,y,w,h, 1, src = ttm_dblbuf ? bg : back,
dst = front, key 0, 0)` (clipped by the script clip window if on).

## 11. Wipes — INTRO `11d2:1688` / PS `3baf:1689`
`wipe(x, y, w, h, a4, op)`: save drv[18]; `drv[18] = front`; (read page = back from the
opcode start). `x1 = x, x2 = x+w, y1 = y, y2 = y+h`. Dispatch table `CS:19A4` / `CS:19A5`.
`cpy(x,y,w,h)` = `11d2:19ea`: `copy_rect(x,y,w,h)` only if w ≥ 3 and h ≥ 3.
`dly()` = `11d2:19c4`: 100 calls of `cpy(0,0,0,0)` — a CPU-speed-dependent pause that copies
nothing. Finally restore drv[18]. All copies are back page → front page (visible), 4-pixel
column granularity (driver entry 4).

| Op | Effect |
|---|---|
| `A014` | `dissolve(x,y,w,h)` (`0f88:000a`/`39fd:000a`), §11.1 |
| `A024` | `cpy(x, y, w, h)` (instant) |
| `A034` / `A094` | box: `w' = w>>1, h' = h>>1` (sar), `cx = x + w'`, `cy = y + h'`, `m = max(w', h')`, `fx = w'·1000/m`, `fy = h'·1000/m` (32-bit signed). `A034`: s = m; while s ≥ 1: s−−; `A094`: s = 1; while s ≤ m: s++. Each step: `dx = fx·s/1000`, `dy = fy·s/1000`, `bx = cx−dx`, `by = cy−dy`, `bw = 2dx`, `bh = 2dy`. `A034` (closing, outside in): `cpy(x1, y1, bx−x1, y2−y1)`, `cpy(bx+bw, y1, x2−bx−bw, y2−y1)`, `cpy(bx, y1, bw, by−y1)`, `cpy(bx, by+bh, bw, y2−by−bh)`. `A094` (opening): `cpy(bx, by, bw, bh)`. No delay |
| `A044` | blinds: for s = 1..10: for o = 0; y1+s+o ≤ y2; o += 10: if w ≠ 0: `copy_rect(x1, y1+s+o, w, 1)`; `dly()` |
| `A054` / `A064` | vertical strip sweep: for s = 3; s ≤ w−3; s++: xs = `A064` ? x2−s : **s−3** (absolute, ignores x — quirk); `cpy(xs, y, 3, h)`. No delay |
| `A074` / `A084` (default) | horizontal band sweep: for s = 3; s ≤ h−3; s++: ys = `A084` ? y2−s : **s−3** (absolute); `cpy(x, ys, w, 3)`; `dly()` |
| `A0B5` | `dissolve_timed(x,y,w,h,a4)` (`1111:0001`/`3aee:0002`), §11.2 |

Opcodes `A014–A094` not in the table (only `A074`, `A084` exist in that range) take the
default branch.

### 11.1 INTRO `0f88:000a` / PS `39fd:000a` — dissolve(x, y, w, h)
`xb` = bit length of w, `yb` = bit length of h; `ymask = 2^yb − 1` (32-bit);
`taps = lfsr_taps32[xb + yb − 2]` (`DS:1B44`/`3510`: 3, 6, 0Ch, 14h, 30h, 60h, 0B8h, 110h,
240h, 500h, 0CA0h, 1B00h, 3500h, 6000h, 0B400h, 12000h, 20400h, 72000h, 90000h, 140000h,
300000h, 400000h, 0D80000h, 1200000h, 3880000h, 7200000h, 9000000h, 14000000h, 32800000h,
48000000h, 0A3000000h). `drv[18] = front, drv[16] = back`. `s = 1` (u32); do:
`py = s & ymask`; `px = (u16)(s >> yb)`; if `py <= h−1` and `px <= w−1` (unsigned):
`put_pixel(x+px, y+py, get_pixel(x+px, y+py))` (driver entries 21/22, unclipped);
`s = (s & 1) ? (s >> 1) ^ taps : s >> 1`; while `s != 1`. Then copy pixel (x, y). Returns 1.
No delay (CPU-bound).

### 11.2 INTRO `1111:0001` / PS `3aee:0002` — dissolve_timed(x, y, w, h, dur)
`n = (u16)(w·h)`; `per = max(n >> 5, 1)`; `drv[16] = back, drv[18] = front`. If
`drv[1F] == 0`: `copy_rect(x,y,w,h)`, return. `dt = max(dur >> 5 (sar), 1)`;
`taps = (u16)lfsr_taps16[bitlen(n) − 2]` (`DS:1C62`/`364A`, low word). `s = 1` (u16),
`c = per`, stepper init(dt). Loop: if `s < n` (unsigned): `put_pixel(x + s%w, y + s/w,
get_pixel(…))`; `c−−`; if c == 0: c = per; wait until `step_done`; stepper init(dt). Then
LFSR step as above (16-bit); until s == 1. Finally pixel (x, y). → 32 batches, each lasting
`dt` stepper ticks (INTRO 59.18 Hz), i.e. ≈ `dur` ticks in total. In PS the waits end at once
(§12.5), so the dissolve runs CPU-bound like `A014`.

## 12. Helper modules

### 12.1 MTX tile map — INTRO `0f48` / PS `39bd` / AP `26db` (AP copy unreferenced except close)

Unused by the 63 shipped scripts (`F08F`, `2032`, `A704`, `00E0` never occur). A tile map
(`BMP:MTX:` bitmap resource: `BMP:` tiles + `MTX:` map) drawn from the driver's
video-memory bitmap cache.

**`mtx_open(name)`** `0f48:000c` / `39bd:000c` → 1/0:
1. If `drv[1D]` is 8 (VGA) or 2: driver entry 32 (`[DS:19B8]`, cache reset) with 0.
2. `tiles = bmp_load(name)` (`0ead:0002`); 0 → return 0. Scroll x `1B36` = y `1B38` = 0.
   `tw = tiles[0].w` → `32AC`, `1B32`; `th = tiles[0].h` → `32AE`, `1B34`;
   `32A8 = 320 − tw`; `32AA = 200 − th`; `nt = frame_count(tiles)` (`0f2c:0010`).
3. `c = 05da:1e21(tiles)` (driver entry 31, upload to the cache; 0 → return 0);
   `1B2C = c[0]->seg`; `05da:539d(c)`.
4. `1B2A` = `malloc(nt·2)` (old one freed); `off[i]` for i = 0..nt−1 = running sum, step by
   `drv[1D]`: 1 → +th, 2 → +th, 3 → +4·th, **8 (VGA) → +2·th**, 4–7 → +0.
5. Reopen the file (`05da:589e`), find `"MTX:"` (else → fail): u16 cols → `32EC`, u16 rows →
   `32EE`; for r < rows (max 30): `32B0[r] = malloc(cols·2)` (old freed); then for c < cols:
   for r < rows: read u16 → `32B0[r][c]` (column-major in the file). Close; return 1.
   Failures after step 3 free the rows, close, return 0.

**`mtx_draw(x, y, w, h)`** `0f48:02d3` / `39bd:02d3`: if tw and th: `nc = w / tw`,
`nr = h / th`; for r < nr: `rr = (r + scroll_y) mod rows` (made non-negative); for c < nc:
`cc = (c + scroll_x) mod cols`; `t = 32B0[rr][cc]`; `px = x + c·8` (**8, not tw** — quirk),
`py = y + r·th`; if `0 < px < 32A8` and `0 < py < 32AA`: `1B2E = off[t]`;
`05da:1e1d(&1B2C, px, py)` (driver entry 30: blit from the cache into the write page).

**`mtx_scroll(dir, n)`** `0f48:03d1` / `39bd:03d1`: dir 0: scroll_y −= n; 1: scroll_y += n;
2: scroll_x −= n; 3: scroll_x += n; else nothing.

**`mtx_close()`** `0f48:0282` / `39bd:0282` / `26db:027f`: free the row arrays
(`0f48:026a` → `0f48:023d` per row); if `drv[1D]` is 8 or 2: entry 32 (cache reset);
else if 1 or 3: `dos_free(1B2C:off[0])`; `free(1B2A)`.

### 12.2 Bitmap scroller — INTRO `0f9e` / PS `3a48`

**`scroller_init()`** (`B000`) `0f9e:0000` / `3a48:0001`: `32F0 = 0`;
`32F2 = max(frame.w)` over the frames of `bmp[ctx+14]`.

**`scroller_step(gap, speed, x)`** (`B013` a0 a1 a2) `0f9e:0058` / `3a48:0059`: h =
`bmp[ctx+14]`, n = frame count; 0 → return. `y = scr_h − 32F0`; `none = 1`; for i < n:
if `y > scr_h` break; `fw, fh` of frame i; if `y > −32F2` (compares with the max
**width** — quirk): `bmp_draw(frame i, x, y, 0)`; `update_rect(x, y, fw, fh)`; none = 0;
`y += gap + fh`. Then `32F0 += speed`; `ttm_purge |= none` (set when every frame has
scrolled off the top). A vertical credits-style scroller drawing into the back page.

### 12.3 Text box — INTRO `0fb0:000c` / PS `3a5a:000d` (`A304` x y w h)
`f = font[ctx+10]`; `font_select(f)`; `sw = text_width(" ")` (`05da:3122`/`16e3:3736`);
`fh = font_height(f)` (`05da:30c8`/`16e3:36dc`); either 0 → return.
1. drv[0E] = 0; drv[0D] = ctx+1F (bg colour): `gfx_rect(x, y, w−3, fh+3)` (title bar;
   filled if drv[0C]).
2. drv[0D] = ctx+1E (fg colour): `gfx_rect(x, y+fh+3, w−3, h−fh−6)` (body).
3. drv[0D] = 0: `gfx_rect(x+w−3, y+3, 3, h−3)`; `gfx_rect(x+3, y+h−3, w−3, 3)` (shadow).
4. drv[02] = 1 (transparent text), drv[00] = 0 (text colour 0, **not restored**).
   `tx = x + ((w − text_width(slot0)) >> 1) + sw − 1` (sar). For i = 0..8: if
   `text_width(slot i) + sw < w`: i = 0: `gfx_text(slot0, tx, y+2)`; else if
   `(i+2)·fh < h`: `gfx_text(slot i, x+sw, y + i·fh + 5)`. drv[02] = 0.

### 12.4 Random — INTRO `10f5:0009` / PS `3ae6:000c`
Additive lagged-Fibonacci generator: `t[k] += t[j]; r = t[k]; k = (k+1) % 56;
j = (j+1) % 56; return r` with `j = DS:1BEE` (initial 24), `k = DS:1BF0` (initial 55),
`t = DS:1BF2[56]` (PS `35D6/35D8/35DA`), initial table:
`dd23 9533 f3cd 4bc2 f7e2 a2df aa70 60aa 144b 8948 192a 6b0d 9e0b fbf1 8607 465d eaf4 69fd
6c44 1b27 db71 e38f abb4 dc47 0fde 4d8e fc7d 8d38 5948 e36f aa22 2f26 43fa b5a5 20eb ed85
f5c3 819f 2d9c b26d e92b 97d5 3da1 89ed e3f4 74b5 002c d35f 3b08 0df5 f27e c270 2589 2e8b
6352 da2d`. `10f5:0056(n)` (uncalled) discards n values.

### 12.5 Timer stepper — INTRO `10fc` / PS `22a0` (functions owned by the palette part §6 and shell_data)
Clock: INTRO reads `DS:24D8` (the caller's 59.18 Hz counter, §14) in all three functions.
**PS mixes two clocks (corrected by the finisher, verified at `3baf:0e05/0e17/0e38` and
`3aee:009b/00f0/0104`)**: `step_init` = `22a0:018e` and `step_value` = `22a0:00d2` use the
59.18 Hz TTM counter `DS:52AA`, but `step_done` is the shell's `22a0:0009`, which reads the
**236.7 Hz** shell clock `DS:1CC8` (`229e:001f`: cli; read; sti; incremented by the timer
callback `229e:0013` registered by PS `sys_init` `048e:0097` with period 1) and tests
`(clock − start) > dur` (strict). The TTM's own `22a0:0089` (59.18 Hz, `>=`) has no caller.
Because `DS:52AA` is zeroed when each TTM sequence starts (`21f4:00cd`) while `DS:1CC8` has
counted 4× faster since PS started, `DS:1CC8 − start` is always large and **PS `step_done`
returns 1 immediately**: `4136` does only its final step, `A0B5` never waits.
* `step_init(st, long d)` `10fc:0114` / `22a0:018e`: st.start = clock; st.dur = (u16)d.
* `step_done(st)` `10fc:000f` / PS as called `22a0:0009`: if the timer is not installed
  (`DS:15BE`/`2E3E` = 0) → 1; else INTRO `(clock − start) >= dur` (u32); PS
  `(DS:1CC8 − start) > dur`.
* `step_value(st, a, b)` `10fc:0058` / `22a0:00d2`: timer not installed → a. `e = clock −
  start`; if `e >= dur` or dur == 0 → b. If a > b: swap a, b and `e = dur − e`.
  `v = a + (u32)((b−a)·e) / dur` (unsigned 32-bit); clamp to [a, b]; return v.
* `10fc:0130` (uncalled): dur = 0, start = clock − 1.

### 12.6 `2012` hook
INTRO `0fc9:000c`: empty. PS `2221:0111(i)`: calls far pointer `DS:1B80[i]` if non-null
(i unchecked; entries 0 = `2221:0003`, 1 and 2 = `2221:0107`) — shell code (hand-off).

## 13. Sound opcodes (INTRO `11d2:000c` / PS `3baf:000d`, table `CS:0100`/`CS:0101`, 18 entries)

Called only when `!ttm_skip`; AP ignores class C. Args as passed: (a0, a1, a2, a3, str).

| Op | INTRO call | PS call |
|---|---|---|
| `C01F` | `strcpy(DS:33A5, str)` | `strcpy(DS:7681, str)` |
| `C02F` | `strcpy(DS:3398, str)` | `strcpy(DS:7674, str)` |
| `C031` | `1659:000b(DS:3398, a0)` | `45f0:000c(DS:7674, a0)` |
| `C041` | `1672:000b(a0)` | `4609:000c(a0)` |
| `C051` (and `1301`) | `16b6:0001(a0)` | `464d:0002(a0)` |
| `C061` (and `1311`) | `16e6:000f(a0)` | `467e:0000(a0)` |
| `C071` | `168d:000f(a0)` | `4625:0000(a0)` |
| `C081` | `1693:0005(a0)` | `462a:0006(a0)` |
| `C091` | `164d:0006(a0)` | `45e4:0007(a0)` |
| `C0A1` | `16de:0002(a0)` | `4675:0003(a0)` |
| `C102` | `1698:000a(a0, a1)` | `462f:000b(a0, a1)` |
| `C0B2` | `1637:000a(a0, a1)` | `45ce:000b(a0, a1)` |
| `C0C2` | `161d:0005(a0, a1)` | `45b4:0006(a0, a1)` |
| `C0D3` | `1712:0002(a0, a1, a2)` | `46a9:0003(a0, a1, a2)` |
| `C0E3` | `16a4:0002(a0, a1, a2)` | `463b:0003(a0, a1, a2)` |
| `C0F4` | `16a0:0003(a0, a1, a2, a3)` | `4637:0004(a0, a1, a2, a3)` |
| `CF01` | `163b:0003(a0)` | `45d2:0004(a0)` |
| `CF11` | `1633:000a(a0)` | `45ca:000b(a0)` |

Other `Cxxx`: nothing (returns −1, ignored).

## 14. Callers: frame loop and timing

**INTRO `0460:0174` / PS `21f4:0151` — `int ttm_play_frames(first, stop, far abort_cb)`**
(the sequence logic around it — `0460:028c`, `21f4:0245` — belongs to shell_ui). Before, the
setup (`0460:00d3` / `21f4:00cd`) registers a timer callback with period 4
(`timer_add(0460:000b, 4)` / `timer_add(21f4:0009, 4)`) that increments the 32-bit counter
`DS:24D8` / `DS:52AA` → **59.18 Hz** (236.7 / 4) (the PS setup also zeroes it), then calls
`ttm_init`, `ttm_load`, `ttm_index(0)`. INTRO also sets `drv[0C] = 1`, `drv[03] = 1`, clip
window (0, 0)–(319, 199).

```
cont = 1; ran = 1; delay = 0 (32-bit, persists across the frames of this call); f = first
while cont && ran && (stop == -1 || f < stop):
    [INTRO only: Windows/DOS-box idle check 0db2:0002 / 0dc0:000d]
    ttm_delay = -1
    t0 = counter
    ran = ttm_run(f)                       // opcodes + pending palette (4.8)
    if ran:
        page_flip(1)                       // driver entry 8: swap drv[12]/drv[14], CRTC start, vsync wait
        upd_flush(0)                       // 9: restores / background propagation
    if ttm_delay != -1: delay = (s32)ttm_delay
    if delay != 0:
        while t0 + delay > counter:        // u32 compare
            if abort_cb: cont = abort_cb(); if !cont: break
    else if abort_cb: cont = abort_cb()
    f++
return !cont ? -1 : !ran ? -2 : f
```

A frame therefore lasts `max(delay, run time + flip)` ticks of 1/59.18 s measured from the
frame start; `1021 n` gives n/59.18 s per frame until changed. The frame index is purely
sequential (GOTO is ignored). The flip happens after the frame's opcodes and after the
pending-palette upload.

**AP**: the cockpit code (`644a`, `6b3d`; cockpit/sim spec) calls `ttm_init`, `ttm_load`,
`ttm_index(0)` and then `ttm_run(frame)` for individual frames (frame numbers chosen by the
cockpit view logic), with `drv[18]`/`drv[16]` set by the caller (e.g. `644a:0341`: write
page = `drv[10]`). No flip, no update list, no delay inside the TTM code.

## 15. Library functions called (names used in this spec)

| Name | INTRO | PS | AP | Notes |
|---|---|---|---|---|
| copy_rect | `05da:2fb0` | `16e3:35c4` | — | driver entry 4 (read → write page, 4-px columns) |
| page_flip | `05da:2fbd` | `16e3:35d1` | — | entry 8 |
| drv_entry25 | `05da:2fb5` | `16e3:35c9` | — | no-op in VGA |
| get_rect / rect_size / put_rect | `05da:35d8`/`35dc`/`492f` | `16e3:3bec`/`3bf0`/`4c53` | `1d32:5a26`/`5a2a`/`6a8d` | entries 5/6/7 |
| get_pixel / put_pixel | `[DS:198C]`/`[DS:1990]` | `[31C8]`/`[31CC]` | — | entries 21/22 (direct) |
| gfx_pixel (clipped) | `05da:48fd` | `16e3:4c21` | `1d32:6a5b` | |
| gfx_line | `05da:3957` | `16e3:3c7b` | `1d32:5ab5` | |
| gfx_rect | `05da:645b` | `16e3:61b5` | `1d32:6ab0` | filled if drv[0C] |
| gfx_circle(r, cx, cy) | `05da:0408` | `16e3:035a` | `1d32:6bbc` | |
| gfx_polygon(n, xs, ys) | `05da:0b91` | `16e3:11a5` | `1d32:09ce` | |
| gfx_flood(x, y, c) | `05da:2893` | `16e3:2ea7` | `1d32:4ce1` | |
| gfx_sprite_scaled | `05da:25a6` | `16e3:2bba` | `1d32:49f4` | |
| gfx_sprite_rotated | `05da:3cfd` | `16e3:4021` | `1d32:5e5b` | |
| gfx_last_bbox | `05da:45d3` | `16e3:48f7` | — | |
| gfx_sprite_scn | `05da:1e38` | `16e3:244c` | `1d32:4286` | type −2 |
| gfx_sprite_plain / _noflip | `05da:06e5` / `06e9` | `16e3:0637` / `063b` | `1d32:3de5` / `3de9` | |
| bmp_draw_packed | `0dc5:0049` | `383a:0049` | `6f1c:003f` | type −1 |
| font_select / font_height / text_width / gfx_text | `05da:2fc1`/`30c8`/`3122`/`33f7` | `16e3:35d5`/`36dc`/`3736`/`3a0b` | `1d32:540f`/—/—/`5845` | |
| font_load / font_free | `05da:4a8f`/`4e01` | `16e3:4db3`/`5125` | `7115:0000`/`0372` | |
| bmp_load / bmp_free / frame_count | `0ead:0002`/`0f2c:0002`/`0f2c:0010` | `3922:0002`/`39a1:0002`/`39a1:0010` | `6f97:0000`/`26d2:0001`/`26d2:000f` | |
| scr_load | `0f35:000a` | `39aa:000a` | `6f83:0000` | |
| pal_load / pal_free / pal_set | `05da:070b`/`0980`/`090e` | `16e3:0d1f`/`0f94`/`0f22` | `1d32:3e0b`/`4080`/`400e` | palette module |
| fade_step / pal_cycle | `05da:09da`/`0a00` | `16e3:0fee`/`1014` | — | palette module |
| vga_scroll (3103) | `103d:0000` | `30b5:000f` | — | out of scope |
| cache blit / upload / reset | `05da:1e1d`/`1e21`/`[19B8]` | `16e3:2431`/`2435`/`[31F4]` | — | entries 30/31/32 |
| dos_alloc / dos_free | `05da:35e0`/`3657` | `16e3:3bf4`/`3c6b` | `1d32:5a2e`/`5aa5` | |
| timer_add | `05da:2307` | `16e3:291b` | — | (far func, period) |

## 16. Corrections to scripts.md / settled questions

* **1101 vs 1111**: both are run-time no-ops and both are accepted by `find_tag`; only `1111`
  creates a context at index time (§4.7). The interpreter uses the last context created.
* **GOTO `1201` has no effect**: `ttm_goto` (`DS:7608`) is written, never read; frames run
  sequentially. **PURGE `0110`** likewise only sets a flag nobody reads (also set by the
  `B013` scroller when done).
* **"Don't draw" flag** (ctx+0E): never set; the skip tests always pass and `Cxxx` always runs.
* **Update list**: the rectangle queued after each `Axxx` is a *background restore* for the
  frame after next (bg → back, key 1), not a screen update (§8, §9). `AF02` queues none; the
  default rectangle is (x, y, w+8, h+2).
* **Frame delay units**: ticks of 59.18 Hz (236.7/4), sticky, measured from frame start (§14).
* **SAVE_BG** = copy back page → bg page (A800) + propagate to the other page; **STORE_AREA**
  = the same for a rectangle (§10). **F01F** in AP does *not* SAVE_BG.
* **SEL_PAL** does not set the DAC immediately on VGA: the pending palette is set after the
  frame (§4.8); immediate only if `drv[1D]` = 4.
* **TEXT `A2x4`**: w, h ignored; transparent, colour drv[00].
* **`2012`**: no-op in INTRO; a shell callback hook in PS (§12.6).
* **`A5A7`**: `gfx_sprite_rotated(fr, x, y, angle=a6, a4, a5, fr.w/2, fr.h/2)`.
* **Wipe numbers**: §11 (A014 LFSR dissolve, A024 instant, A034 box closing, A044 blinds,
  A054/A064 vertical sweeps, A074/A084 horizontal sweeps, A094 box opening, A0B5 timed
  dissolve).
* **`2022`**: `a0 + abs((s16)(rand % (u16)(a1−a0)))`.
* **`A304`** = text box (title = string slot 0, lines = slots 1–8); **`A704`/`F08F`/`2032`/
  `00E0`** = MTX tile map; **`B000`/`B013`** = bitmap scroller; `0500`/`0510` = suppress the
  background restores.
* Arg nibbles 8–E make `ttm_index` fail (−1). `0000` is ignored (not an END).
* AF1F/AF2F: `u16 n` then 2n words; the drawing uses `k = word0` points with x[] and y[]
  arrays (§7).
* `4136`: from/to are percentages → level `((p << 6) / 101) & 63`; the 6th argument is a
  duration in stepper ticks (INTRO 59.18 Hz; untimed in PS, §12.5), not a step count.

## 17. Port notes

* Implement pages as three linear 320×200 buffers with the role variables `drv[10..18]`;
  keep the update list exactly (segment values → page ids; list keyed by (src, dst, key);
  flush-table order; merge rule), because merges copy extra pixels between pages.
* `/* PORT: */` the busy waits: `dly()` (`11d2:19c4`, 100 empty calls) and the un-timed
  wipes/fade loops run as fast as the CPU; a faithful-looking port should pace them (e.g.
  `A044`/`A074`/`A084`: present once per `dly()`; `A034`/`A094`/`A054`/`A064`/`A014`: present
  every step or every N pixels; fades: one present per `fade_step`, which in the original is
  bounded by the DAC upload's vretrace wait — driver entry 34/35). Wipes write straight into
  the front page, so the port must present the front page during these loops.
* The 59.18 Hz frame counter can be derived from the platform's 236.7 Hz tick (÷4).

## 18. Hand-offs

* **shell_ui** (INTRO `0460:00d3/0157/0174/028c`, PS `21f4:00cd/0134/0151/0245`): the frame
  loop contract of §14 (flip + `upd_flush(0)` after each frame, sticky delay from
  `DS:33C8`/`76A4` in 59.18 Hz ticks, return −1 abort / −2 end of script / next frame index).
* **shell_ui / shell_data**: PS `2012` hook `2221:0111` → `DS:1B80` far-pointer table
  (`2221:0003`, `2221:0107`) — used 3 times by award scripts (scripts.md).
* **palette part/module**: `pal_set` (`05da:090e`) returns a value that `0400`/`4114`/`4124`
  store back into the pending pointer; `pal_cycle(-1,0,0)` is called by `0400`/`2402`;
  `DS:33CA/33CC` (PS `76A6/76A8`) cycle step/flag are written here and read nowhere in these
  segments — check whether a timer callback reads them.
* **sim cockpit (AP `644a`, `6b3d`)**: selects `drv[18]`/`drv[16]` before `ttm_run(f)`
  (`24fc:0610`); AP ignores `1021`, fades, wipes, sound; `F01F` loads the SCR into the
  caller's write page without SAVE_BG.
* **pictures part**: confirmed (`video_pictures.md` §1): `scr_load` decodes into the write page
  `drv[18]` (VQT via driver entry 22, nibble planes via entries 17/18), i.e. the back page here.
* **video lead**: `drv[0C]` is the fill flag (1 filled / 0 outline) for rect/circle/polygon;
  `drv[1F]` gates fades/cycling/`A0B5`; `drv[1D]` = 4 makes `SEL_PAL` immediate; entries
  30/31/32 are used by MTX (unused by the data). The segment `0fca`/`3a73` is the update
  list (not palette code).
* **platform**: timer callbacks with period 4 (INTRO `0460:000b`, PS `21f4:0009`) and 1
  (PS `229e:0013`).

## 19. Open questions

* `A5A7`: exact meaning of a4/a5 (target size?) and angle units — depends on
  `gfx_sprite_rotated` (`05da:3cfd`).
* Polygon data layout (unused by the data).
* Whether `ttm_cyc_on`/`ttm_cyc_step` are consumed anywhere (palette cycling looks like a
  single rotation per `2402`).
* Exact semantics of `05da:0a00(-1, 0, 0)` (called before every cycle/reset) — palette part.
