# shell_ui part 1 — the PS UI toolkit (`alert\*`: hot-spots, drawing, text flow, event loop, dialogs)

Target `Game/PS.EXE` (DGROUP `4D08`), segments `2b4f` alert.c, `2c11` (alert drawing, no assert
file), `2dd0` drawtext.c, `2e25` menu.c, `2e8a` screen.c, `2ed6` soft.c, `2f47` choose.c, `2f7f`
(text entry, far data `4cce`), `2fa5` listbox.c, `3038` (request box, far data `4ce2`), `307d`
fltalert.c. Main file: `shell_ui.md` (index, flow graph). Symbols: `shell_ui_symbols.csv`.

Confidence: **V** verified against the disassembly, **L** likely (decompile read, not every
instruction checked), **G** guess. Unmarked statements in a V section are V.

## 0. Conventions and the shared graphics state

All toolkit code is Borland far cdecl (`[bp+6]` = first argument). Coordinates are 320×200 screen
pixels. Colours are palette indices; the shell palette `PARTS.PAL`/per-screen `.PAL` puts the UI
greys/browns at `B1h`–`CDh` (the names below — "light", "dark"… — are descriptive only; the indices
are what matters).

### 0.1 Graphics library calls used (owned by platform/video; working names)

| Address | Working name | Behaviour as used by the shell (L) |
|---|---|---|
| `16e3:35d5` | `font_select(slot)` | selects loaded font `slot` (handles in `DS:421A–4222`), returns previous |
| `16e3:3736` | `text_width(char *s)` | pixel width of `s` in the current font (sum of glyph widths) |
| `16e3:3a0b` | `draw_text(char *s, x, y)` | draws `s` at (x, y) (top-left) in colour `DS:2300`; flag bits `DS:2302`: bit0 = transparent background (bg colour `DS:2301` otherwise), bit1 = one extra pixel after each glyph |
| `16e3:3c7b` | `draw_line(x0,y0,x1,y1)` | line in colour `DS:230E`, clipped to `DS:2304–230A` when `DS:2303` |
| `16e3:61b5` | `draw_rect(x,y,w,h)` | rectangle; filled with `DS:230D` when `DS:230C` != 0, outline `DS:230E` otherwise; clipped |
| `16e3:4bef` / `4c21` | `get_pixel(x,y)` / `put_pixel(x,y,c)` | return −1 / do nothing outside the clip rect |
| `16e3:11a5` | `fill_poly(n, xs, ys)` | filled polygon (fill colour `DS:230D`) |
| `16e3:0637` | `draw_bitmap(frame, x, y, flags)` | video driver entry `DS:31E8`; `frame` = near pointer to a frame header (+6 w, +8 h); flags 2 = mirrored (Likely: used for the right-hand end caps) |
| `16e3:35c4` | `copy_rect(x,y,w,h)` | driver `DS:3184`: copies a rectangle from page `DS:2316` to page `DS:2318` |
| `16e3:35d1` | `page_flip(0)` | driver `DS:3194`: shows the work page and swaps `DS:2312`/`DS:2314` (see 0.2) |
| `16e3:3bf0` | `save_size(w,h)` | driver `DS:318C`: bytes needed to save a w×h block |
| `16e3:3bec` / `4c53` | `save_rect(buf,x,y,w,h)` / `restore_rect(buf,x,y,w,h)` | driver `DS:3188` / `DS:3190`: save a block of page `DS:2316` into a far buffer / put it back into page `DS:2318` |
| `16e3:0f22`, `16e3:0f94`, `16e3:0d1f` | `pal_set(far pal)`, `pal_free(far pal)`, `pal_load(name)` | palette handles are far pointers |
| `16e3:6658` | `kbd_getkey()` | BIOS keyboard buffer word (scan<<8 \| ASCII), 0 if empty |
| `16e3:66a1` | `key_down(scan)` | held state from the INT 9 table `DS:3394` (bit 0) |
| `16e3:6687` | `kbd_…(0)` | reads a shift-state byte; result unused by the shell |
| `16e3:0296` | `joy_dir(stick)` | bits 1 up, 2 down, 4 left, 8 right (axis beyond ±30 from centre) |
| `2316:007f` | `mouse_move_to(x,y)` | INT 33h/4 unless already there; no-op when DOS < 3 (`DS:0092`) |
| `2316:0041` / `0062` | `mouse_get_pos(&x,&y)` / `mouse_button(n)` | INT 33h wrappers (same DOS ≥ 3 guard) |
| `22ce:004a` | `page_copy_full()` | `copy_rect(0,0,320,200)` |
| `22ce:0063/0074/0085/0096` | set (`DS:2316`,`DS:2318`) = (2310,2312) / (2314,2312) / (2312,2314) / (2312,2310) |
| `22ce:00a7/00bc/00d1/00e6/00fb` | same pairs (2310→2312, 2312→2310, 2310→2314, 2312→2314, 2314→2312) **and** `page_copy_full()` |
| `22ce:0110` | `clip_full()` | `230C=1, 2303=1`, clip 0..319 × 0..199 |
| `22ce:019c` / `021c` | `xmalloc(n)` / `xfree(p)` | near heap; fatal (`227c:0143`) on failure |
| `22ce:022a` / `02b0` | `farmalloc(lo,hi)` / `farfree(p)` | far heap wrappers (`1ed0`) |
| `22a0:0009` / `0050` | `tmr_expired(t)` / `tmr_set(t, ticks, 0)` | timer record `{u32 start, u16 len}` against the 32-bit tick counter `DS:1CC8` (incremented by `229e:0013`, a timer callback registered in `sys_init` with reload 1, i.e. **236.7 Hz**); expired when `now − start > len`; always expired when the timer is not installed (`DS:2E3E` = 0) |
| `464d:0002` | `snd_play(id)` | sound effect by id (sound module) |
| `24e3:021f` | `str_get(id)` | string `id` of the currently loaded `.SCD` (see §5.2) |
| `1193:0115` | `res_name(base, num, ext)` | `DS:4B72` = base [+ decimal num if num > −1] + "." + ext |
| `227c:0143` | `fatal_line(0, file_seg, line, 0)` | assertion failure (the far data segment identifies the source file); see `shell_ui.md` |

### 0.2 Pages

Three 16 KB VGA pages (unchained mode, see video). **`DS:2314` = the displayed (front) page,
`DS:2312` = the work (back) page, `DS:2310` = a spare page** used to keep a clean copy of a
background. `DS:2316` = source and `DS:2318` = destination page of every copy; all drawing goes to
`DS:2318`. `page_flip` shows the work page and swaps 2312/2314 (V from `shell_exit`: it sets
`2312 = A000h`, copies the front page there and flips, so the last image ends up at A000h).

### 0.3 Global UI state (DGROUP)

| DS | Type | Meaning |
|---|---|---|
| `2300` | u8 | text colour |
| `2301` | u8 | text background colour (opaque text) |
| `2302` | u8 | text flags (bit0 transparent, bit1 +1 px per glyph) |
| `2303` | u8 | clip enable; `2304/2306/2308/230A` = clip x0, x1, y0, y1 (inclusive) |
| `230C` | u8 | rectangle fill enable; `230D` fill colour; `230E` line colour |
| `2316`/`2318` | u16 | source / destination page segment |
| `5FDA`,`5FD8`,`5FD6`,`5FD4` | s16 | **current rectangle** x, y, w, h (set from the current hot-spot, or directly) |
| `5FFE`,`5FFC`,`5FFA`,`5FF8` | s16 | saved rectangle (`rect_save`) |
| `1FFA:1FFC` | far | current hot-spot table; `1FFE` = item count (≤ 40) |
| `5FE0` | far | pointer to the current item; `5FDE` = its index |
| `5F74`,`5F72` | s16 | origin (x, y of item 0) added to items 1… |
| `5F7C` | s16 | focused (keyboard-selected) item |
| `5FDC` | u16 | event bits of the item being dispatched (§1.3) |
| `5FA6[40]` | u8 | per-item "button was down over it" |
| `5F7E[40]` | u8 | per-item "callback ran in this dispatch" (dirty) |
| `5F70` | u16 | restart-dispatch flag (`hs_restart`); after a dispatch = its `redraw` argument |
| `5FD0`,`5FCE` | s16 | mouse position of the last dispatch |
| `5FD2` | u16 | value returned by `hs_dispatch` (never written by the toolkit: L) |
| `601A`,`6018` | s16 | pointer position (0..319, 0..199) |
| `2033` | u16 | "button" state: mouse button, Enter (and Space unless `DS:2030`), joystick button |
| `2031` | u16 | previous `2033` |
| `6016`,`6017` | u8 | last key: scan code, ASCII (0 = none) |
| `600E` | u16 | modal-loop result (0 = keep running) |
| `2035` | u8 | keyboard navigation enabled (arrows/Tab move the focus) |
| `2000` | near | current cursor frame; `2002` = cursor visible; `2006:2008` far save buffer |
| `2004`,`5F76`,`5F78`,`5F7A` | s16 | cursor rectangle last put on the front page (w, h, y, x); `5F6E`,`5F6C` = clipped w, h |
| `200A:200C` | far | palette to install at the next full present (0 = none) |
| `5FE6` | near | `PARTS.BMP` frame table (§0.4); `5FE4` = `SYMBOLS.BMP` frame table |
| `6000:6002` | far | 10×10 save buffer used by the title plate (`2c11:0001`) |
| `421A`/`421C`/`421E`/`4220`/`4222` | u16 | font handles `TALK`, `FONT4`, `FONT3`, `FONT2`, `FONT1` (loaded by `0a71:0001`) |
| `43B6`/`43B7` | u8 | joystick / mouse enabled (from `CONTROL.PRF`, shell_data) |

### 0.4 `PARTS.BMP` frames (`DS:5FE6`, loaded by `0a71:00eb`, 9 frames)

Frame table = near array of near pointers to frame headers (+6 w, +8 h).

| Index (offset) | Use |
|---|---|
| 0 (`+0`) | title-plate end piece (`2c11:0ed6`; its h = plate height) |
| 1 (`+2`) | background tile (`tile_fill`, tile step w−2 horizontally, 3 px rows with a 4 px shift) |
| 2 (`+4`) | rivet (drawn on 7 px pitch) |
| 3 (`+6`), 4 (`+8`) | title bar left/right pieces (`2c11:0980`) |
| 5 (`+A`) | bottom bar ends (`2c11:0946`) |
| 6 (`+C`) | arrow cursor |
| 7 (`+E`) | busy cursor |

`SYMBOLS.BMP` (24 frames, `DS:5FE4`): rank/service insignia drawn at both ends of the title bar.

## 1. Hot-spot manager (`alert.c`, segment `2b4f`) — V

### 1.1 Item record (22 bytes, in far data tables)

| Off | Type | Field |
|---|---|---|
| +00 | s16 | x (item 0: absolute; items ≥ 1: relative to item 0) |
| +02 | s16 | y (same) |
| +04 | s16 | w |
| +06 | s16 | h |
| +08 | far | callback `void far cb(void)` (0 = none) |
| +0C | u8 | trigger mask: the callback runs when `5FDC & mask` (§1.3) |
| +0D | u8 | flags: 02 = focusable (keyboard navigation), 08 = diamond hit area, 80 = `+0E` is a string id of the loaded `.SCD` |
| +0E | u16 | label: near `char *`, or string id when flag 80 |
| +10 | u16 | user word (button style / quadrant, list count…) |
| +12..+15 | u8[4] | focus links for directions 0 up, 1 down, 2 left, 3 right (item indices; 0 = none) |

Item 0 is by convention the window/panel itself (callback draws the frame, mask 40h).
Tables are loaded with `hs_set_table` and can take their rectangles from files (`hs_load_layout`).

### 1.2 Functions

| Address | Name | Behaviour |
|---|---|---|
| `2b4f:0007` | `ui_set_pending_palette(off, seg)` | `200A = off, 200C = seg` (installed by the next full present) |
| `2b4f:0019` / `0024` / `002f` | `cursor_show` / `cursor_hide` / `cursor_toggle` | `2002 = 1` / `0` / `!2002` |
| `2b4f:003f` | `cursor_set(frame)` | `2000 = 0`; frees the old save buffer (`2006:2008`) if any; if `frame`: allocates `save_size(frame.w, frame.h)` bytes far (returns 0 on failure); `2000 = frame`; returns 1 |
| `2b4f:009d` | `hs_load_rect()` | from `*5FE0`: `5FDA = x, 5FD8 = y`; if `5FDE == 0` → `5F74 = x, 5F72 = y`, else `5FDA += 5F74, 5FD8 += 5F72`; `5FD6 = w, 5FD4 = h` |
| `2b4f:00e9` | `hs_load(tbl_off, tbl_seg, idx)` | if `idx != 0`: first `5FDE = 0, 5FE0 = tbl, hs_load_rect()` (to get the origin); then `5FDE = idx, 5FE0 = tbl + 22·idx, hs_load_rect()` |
| `2b4f:012d` | `hs_focus(idx)` | if `0 ≤ idx < 1FFE`: `5F7C = idx`, `hs_load(1FFA,1FFC,idx)`; fatal (alert.c line 92h) if item not focusable; `hs_center_mouse()` |
| `2b4f:0186` | `hs_hit(x, y)` → bool | current item: rectangle test `x0 ≤ x ≤ x0+w−1`, `y0 ≤ y ≤ y0+h−1`; with flag 08: `r = w>>1` (arithmetic), `dx = x − (x0 + r)`, `dy = y − (y0 + r)`, hit iff `|dx| + |dy| < r` |
| `2b4f:01ff` | `hs_center_mouse()` | `601A = 5FDA + (5FD6 >> 1)`, `6018 = 5FD8 + (5FD4 >> 1)`, `mouse_move_to(601A, 6018)` |
| `2b4f:022e` | `hs_focus_nearest()` → int | if count: scan all items (loading each); for focusable ones: if `hs_hit(601A,6018)` → `5F7C = i`, `hs_center_mouse()`, return 1; else `d = |cx − 601A| + |cy − 6018|` (cx = x + (w>>1), cy = y + (h>>1)); keep the first strictly smaller d. After the scan, if one was found: `5F7C = best`, `hs_load(best)`, `hs_center_mouse()`. Returns 0 |
| `2b4f:0317` | `hs_navigate(dir)` | if `hs_focus_nearest()` returned 1: `n = item[5F7C].links[dir]`; if `n != 0`: `5F7C = n`, `hs_load(n)`, `hs_center_mouse()` |
| `2b4f:035c` | `hs_focus_first()` | first focusable item (index order) → `5F7C`, `hs_load`, `hs_center_mouse`; none → leaves 5FE0 at the table start |
| `2b4f:03b7` | `hs_set_table(off, seg, n)` | fatal (line FDh) if `n > 40`; `1FFA:1FFC = off:seg`, `1FFE = 0`; if `n > 0`: clear `5FA6[0..n)`, `1FFE = n`; `hs_focus_first()` |
| `2b4f:041b` | `hs_restart()` | `5F70 = 1` (a callback that changed the table/screen makes `hs_dispatch` start over) |
| `2b4f:0426` | `hs_dispatch(mx, my, button, redraw)` → `5FD2` | §1.3 |
| `2b4f:05f4` | `cursor_draw(x, y)` | `2316 = 2318 = 2312`; `clip_full()`; if `2000 && 2002`: `5F6E = min(320 − x, frame.w)` (min taken as "if frame.w ≤ 5F6E use frame.w"), `5F6C = min(200 − y, frame.h)`; `save_rect(2006:2008, x, y, 5F6E, 5F6C)`; `draw_bitmap(2000, x, y, 0)` |
| `2b4f:0686` | `cursor_flush(x, y)` | `2316 = 2312, 2318 = 2314`; if `2004 != 0`: `copy_rect(5F7A, 5F78, 2004, 5F76)` (erases the old cursor on the front page from the work page); if `2000 && 2002`: `2004 = 5F6E, 5F76 = 5F6C, 5F78 = y, 5F7A = x`, `copy_rect(x, y, 5F6E, 5F6C)`, `2318 = 2312`, `restore_rect(2006:2008, 5F7A, 5F78, 2004, 5F76)` (removes the cursor from the work page); else `2004 = 0` |
| `2b4f:0719` | `hs_present()` | §1.4 |
| `2b4f:0852` | `hs_default_links(off, seg, n)` | clears links of all n items; then walks the focusable items in index order: for each consecutive pair (p, c): `p.link[1] = p.link[3] = c`, `c.link[0] = c.link[2] = p`; finally if first ≠ last: `last.link[1] = last.link[3] = first`, `first.link[0] = first.link[2] = last` (a ring: up/left = previous, down/right = next) |
| `2b4f:0959` | `hs_load_layout(name, off, seg, n)` | opens `res_name(name,−1,"box")` "rb" (fatal line 1F7h if missing), file length / 8 must equal n (fatal 1F9h); reads n × 8 bytes = x, y, w, h into the n items; closes; opens `name.bl`: if missing → `hs_default_links`; else length / 4 must equal n (fatal 209h) and n × 4 bytes are copied to `+12..+15` |
| `2b4f:0b15` / `0b62` | `hs_push()` / `hs_pop()` | one-level save/restore of 601A, 6018, 5FE0, 5FDE, 5F7C, table 1FFA/1FFC/1FFE, 5FD2 and the modal result (`menu_get_result`) into `5F56..5F6A`; pop = `hs_set_table(saved)`, restore the pointer (and `mouse_move_to`), 5FE0, 5FDE, 5F7C, 5FD2, `menu_set_result(saved)` |
| `2b4f:0bbc` | `ui_busy()` | if `2002`: `cursor_set(PARTS[7])` (busy cursor), `cursor_draw(601A, 6018)`; then `22ce:00e6` (copy the whole work page to the front page) |
| `2b4f:0be7` | `hs_draw_all()` | `hs_dispatch(601A, 6018, 0, 1)` (every item gets bit 40h → full draw); `cursor_set(PARTS[6])` (arrow); `mouse_move_to(601A, 6018)`; `hs_present()` |

### 1.3 `hs_dispatch(mx, my, button, redraw)` (`2b4f:0426`)

```
2316 = 2318 = 2312                       // draw on the work page
5FD0 = mx; 5FCE = my
any_clickable = 0
click_nothing = (button != 0 && 2031 == 0)          // a fresh press
restart:
  5F70 = 0
  for i = 0 .. 1FFE-1:  (5FDE = i, 5FE0 = tbl + 22 i)
     any_clickable |= (item.mask & 1Ch) != 0
     hs_load_rect()
     5FDC = redraw ? 40h : 0
     if !hs_hit(mx, my):
         5FDC |= 02h
         if 5FA6[i]: 5FDC |= 20h; 5FA6[i] = 0         // left while held
     else:
         if click_nothing && (item.mask & 1Ch): click_nothing = 0
         if button == 0: 5FDC |= 01h; if 5FA6[i]: 5FDC |= 10h   // released inside = activate
         else if !5FA6[i]: 5FDC |= 05h                 // pressed now
         else:             5FDC |= 09h                 // held
         5FA6[i] = button
     if (5FDC & item.mask) == 0 || item.cb == 0: 5F7E[i] = 0
     else:
         5F7E[i] = 1
         if item.flags & 80h:                  // label is a string id
             save = item.label; item.label = str_get(save); item.flags ^= 80h
             item.cb(); item.label = save; item.flags ^= 80h
         else item.cb()
         if 5F70: goto restart                  // table replaced by the callback
  5F70 = redraw
  if any_clickable && click_nothing: snd_play(1Ah)      // click on no button
  return 5FD2
```

Event bits (`5FDC`): 01 over, 02 not over, 04 pressed now, 08 held over, 10 released over
(activation), 20 released/left after being pressed, 40 full redraw. Standard masks: 40h = draw
only on redraws (static panels), 74h = buttons (redraw, left, released, pressed: repaint on
press/release, act on 10h), 7Ch = auto-repeat arrows (also 08h), 5Ch = list bodies.

### 1.4 `hs_present()` (`2b4f:0719`)

```
cursor_draw(5FD0, 5FCE)
if 5F70 == 0 && 5F7E[0] == 0:               // incremental: copy dirty items to the front page
    2316 = 2312; 2318 = 2314
    for each item i with 5F7E[i]:
        hs_load_rect(); fatal if x+w > 319 (line 1BDh) or y+h > 199 (1BEh)
        copy_rect(x, y, w+1, h+1)
else:                                        // full: flip
    page_flip(0)
    if 200A:200C: pal_set(200A:200C); screen_pal_release(200A:200C) (2e8a:00ee); 200A:200C = 0
    22ce:00fb                                // copy the new front page back to the work page
cursor_flush(5FD0, 5FCE)
```

## 2. Drawing primitives (segment `2c11`) — V unless marked

All take the current rectangle (x=`5FDA`, y=`5FD8`, w=`5FD6`, h=`5FD4`) unless arguments are
listed. "line c: (x0,y0)-(x1,y1)" means `230E = c; draw_line(...)`; "box c: x,y,w,h" means
`230C = 1, 230D = 230E = c; draw_rect(...)`. Many functions convert w/h to right/bottom edges
inside a `rect_save`/`rect_restore` pair: below, `R = x + w`, `B = y + h`.

| Address | Name | Behaviour |
|---|---|---|
| `2c11:0001` | `plate_buf_alloc()` | `6000:6002 = farmalloc(save_size(10,10))` (called from `sys_init`) |
| `2c11:002e` | `plate_buf_free()` | `farfree(6000:6002)` |
| `2c11:0042` | `rect_grow(n)` | x −= n, y −= n, w += 2n, h += 2n |
| `2c11:005c` | `rect_shrink(n)` | `rect_grow(−n)` |
| `2c11:006c` / `0089` | `rect_save()` / `rect_restore()` | copy current rect to/from `5FFE/5FFC/5FFA/5FF8` |
| `2c11:00a6` | `rect_copy()` | `copy_rect(x, y, w, h)` (page 2316 → 2318) |
| `2c11:00c3` | `text_emboss(s, tx, ty, c1, c2, c3)` | if s: `tx == −1` → `tx = text_center_x(s, x, w)`; `2302 = 1`; `ty == −1` → `ty = y + 5`; draw_text(s,tx,ty) in c1, (tx,ty+2) in c3, (tx,ty+1) in c2 |
| `2c11:014d` | `glyph_edge(ch, px, py)` → width | walks the glyph bitmap of `ch` in the current font (fixed: width `DS:2334`, rows `DS:2348`, row bytes (w+7)/8, first char `DS:235C`, data `DS:71B8:71BA`; proportional: widths at `DS:7258`, offsets at `DS:7208`); for each row, each column (MSB first): a pixel is "ink" if its bit is set, or (text flag bit1 set and the previous column was set). Ink: `c = get_pixel`; `c = (c == DS:201E) ? c : DS:201C`; `put_pixel(c)`. Not ink: if text flag bit0 clear → `put_pixel(DS:2301)`; else nothing. Returns the glyph width |
| `2c11:027c` | `text_edge(s, x, y)` | for each char: `x += glyph_edge(c, x, y)` (+1 when text flag bit1) |
| `2c11:0362` | `text_engrave_center(s, c1, c2, c3)` | `2302 = 1`; `tx = text_center_x(s, x, w)`; draw_text(s, tx, y+4) in c1; (tx, y+5) in c2; `201C = c3, 201E = c1`; `text_edge(s, tx, y+4)` → every glyph pixel not already c1 becomes c3 (the c2 shadow row shows below) |
| `2c11:03d4` | `text_engrave(s, c1, c2, c3, tx, ty)` | as above at (tx, ty): c1 at ty, c2 at ty+1, then the edge pass with c3 (skipping pixels equal to c1). **The standard shell label style** (e.g. c1 = C4h, c2 = C9h, c3 = C7h/C6h on buttons) |
| `2c11:042c` | `draw_bevel_box()` | box B8h: x,y,w,h; `rect_save`; R, B; `230C = 0`; lines: C2h (x,y)-(R,y); B4h (x+1,y+1)-(R−1,y+1); C0h (x,y+1)-(x,B−1) and (R,y+1)-(R,B−1); BFh (x+1,y+2)-(x+1,B) and (R−1,y+2)-(R−1,B); C4h (x+1,B)-(R−1,B); C1h (x,B−1)-(R,B−1); C0h (x,B−2)-(R,B−2); `rect_restore` |
| `2c11:0592` | `draw_rivets(rx, ry, n)` | n × `draw_bitmap(PARTS[2], rx, ry + 7k, 0)` |
| `2c11:05cf` | `draw_groove(no_bottom)` | `rect_save`; R, B; lines C2h (x,y)-(R−1,y); C0h (x,y+1)-(x,B−2) and (R−1,y+1)-(R−1,B−2); C7h (x,B−1)-(R−1,B−1); if `no_bottom == 0`: C0h (x,B)-(R−1,B); `rect_restore` |
| `2c11:069a` | `draw_inset_box()` | `rect_save`; R, B; lines C6h top (x,y)-(R,y); C0h left/right full height; B4h bottom (x,B)-(R,B); C7h (x+1,y+1)-(R−1,y+1), (x+1,y+1)-(x+1,B−1), (R−1,y+1)-(R−1,B−1); C2h (x+1,B−1)-(R−1,B−1); `rect_restore`; box C0h: x+2, y+2, w−3, h−3 |
| `2c11:07de` | `draw_inset_box2()` | calls `069a` |
| `2c11:07e7` | `text_center_x(s, x, w)` → x | `d = w − text_width(s)`; if text flag bit1: `d −= strlen(s)`; if `d > 0`: `x += d/2 + 1` (signed division); return x |
| `2c11:0829` | `tile_fill(tx, ty, tw, th)` | clip to (tx..tx+tw−1, ty..ty+th−1); `step = PARTS[1].w − 2`; for (row y = ty; y ≤ clip y1; y += 3) { col = tx; if col ≥ clip x0: col −= step, and tx = col; for (; col ≤ clip x1; col += step) draw_bitmap(PARTS[1], col, y, 0); tx += 4 }; `2303 = 0`. (Each 3-pixel row band starts 4 px further right: a staggered brick texture) |
| `2c11:08b4` | `tile_fill_rect()` | `tile_fill(x, y, w, h)` |
| `2c11:08d0` | `screen_clear(c)` | `230C = 1, 2303 = 0, 230D = 230E = c, 2318 = 2312; draw_rect(0,0,320,200)` |
| `2c11:0902` / `090f` | `screen_clear_black()` / `screen_clear_panel()` | `screen_clear(0)` / `screen_clear(B8h)` |
| `2c11:091c` | `rect_fill_c1()` | box C1h: x, y, w, h |
| `2c11:0946` | `draw_bottom_bar()` | `yb = y − 25`; `draw_bitmap(PARTS[5], 0, yb, 0)`, `draw_bitmap(PARTS[5], 296, yb, 2)` |
| `2c11:0980` | `draw_title_bar(sym, title)` | `rect_save`; rect = (49, 0, 219, 23); `2318 = 2312, 2303 = 0`; `tile_fill_rect()`; `draw_frame()`; `draw_bitmap(PARTS[3], 0,0,0)`, `(PARTS[3], 295,0,2)`, `(PARTS[4], 21,0,0)`, `(PARTS[4], 266,0,2)`; `draw_bitmap(SYMBOLS[sym], 24, 2, 0)` and `(SYMBOLS[sym], 272, 2, 0)`; `font_select(FONT1)`; `tx = text_center_x(title, 49, 219)`; `text_emboss(title, tx, 3, C1h, C0h, B1h)`; `k = (tx − 49)/7`, max 4; for i = 1..k: `draw_rivets(49 + 7i − 3, 3, 3)` and `draw_rivets(49 + 219 − 7i, 3, 3)`; `rect_restore` |
| `2c11:0b00` | `draw_title_bar_for(service, date, title)` | `today = date_to_days(DS:2020..2025)` (`284f:0007`, shell_data); `2318 = 2312, 2303 = 0`; `sym = (service == 6) ? 7 : 0f67:02ed(service)` (pilot service → symbol, owned by the career part); if `sym == 1 && date > today` → `sym = 6`; `draw_title_bar(sym, title)` |
| `2c11:0b65` | `draw_frame_lines(x0,y0,x1,y1', bx0,by1, bx1,by)` (8 args) | lines C2h (x0,y0)-(x1,y0); B5h (x0,y0+1)-(x1,y0+1); C0h (x0,y1'+1)-(x0,by1) and (x1,y1'+1)-(x1,by1); BFh (x0+1,y1'+2)-(x0+1,by1) and (x1−1,y1'+2)-(x1−1,by1); C1h (bx0,by)-(bx1,by); C4h (bx0,by−1)-(bx1,by−1); `2303 = 0` |
| `2c11:0c46` | `draw_frame()` | clip to (x..R, y..B); `draw_frame_lines(x, y, R, y, x, B, R, B)`; `2303 = 0` |
| `2c11:0c8e` | `draw_frame_inset(n, top)` | clip (x..R, y+2..B); `draw_frame_lines(x, y, R, y + top, x + n, B − n, R − n, B)` |
| `2c11:0cec` | `draw_plate_corners(top)` | four 45° bevels with `2c11:02b1`: C2h from (x+6, y+top−6) going left-down 7 rows; C2h from (R−7, y+top−7) right-down 7 rows; C0h at the bottom corners (x, B−6) and (R, B−6), 6 rows |
| `2c11:02b1` | `bevel_rows(ref_x, x, y, n, dx, c)` | n rows: if `ref_x < x`: `230E = get_pixel(x+n+2, y)`, `put_pixel(x, y, c)`, line (x+1,y)-(x+n+1,y) in the sampled colour; if `x < ref_x`: same mirrored (sample x−n−2, line (x−1,y)-(x−n−1,y)); then `x += dx, y++` |
| `2c11:0d96` | `draw_plate_bottom()` | tabs under the plate at B+1..B+5: C1h (x+15,B+1)-(x+20,B+5), (R−15,B+1)-(R−20,B+5); C0h (x+16,..)-(x+21,..), (R−16,..)-(R−21,..); C4h (x+17,B+1)-(R−17,B+1); C6h (x+18,B+4)-(R−18,B+4); C1h (x+19,B+5)-(R−19,B+5); BEh (x+18,B+2)-(R−18,B+2), (x+19,B+3)-(R−19,B+3) |
| `2c11:0ed6` | `draw_title_plate()` | the panel with a title tab used by menu windows (label = current item's `+0E`); see §2.1 |
| `2c11:136a` | `draw_titled_panel()` | `draw_title_plate(); draw_plate_bottom()` — callback of window items (e.g. main menu item 0 via `04df:0117`) |
| `2c11:142b` | `draw_button_face(pressed)` | box C3h: x+1, y+1, w−2, h−2; `rect_save`; `r = x + w`; w' = r − 2; B; line (x+3,y+2)-(r−4,y+2) in C9h (up) / C6h (pressed); C8h (x+3,y+3)-(x+3,B−3) and (w'−2,y+3)-(w'−2,B−3); bottom (x+3,B−3)-(w'−2,B−3) in C6h (up) / C9h (pressed); `rect_restore`; box C8h (up) / C7h (pressed): x+4, y+3, w−8, h−6 |
| `2c11:1377` / `13d1` | `draw_list_button_down` / `draw_list_button_up` | `draw_groove(0)`; `draw_button_face(0 / 1)`; `font_select(FONT4)`; `text_engrave(label, C4h, C9h, C7h / C6h, text_center_x(label,x,w), y+5 / y+4)` |
| `2c11:1575` / `15d4` | `draw_button_up` / `draw_button_down` | `font_select(FONT4)`; `tx = text_center_x(label, x, w)`; `draw_groove(0)`; `draw_button_face(1 / 0)`; `text_engrave(label, C4h, C9h, C6h / C7h, tx, y+5 / y+6)` |
| `2c11:1633` | `draw_popup_box()` | box B8h x,y,w,h; then outline C4h (`230C = 0`) x,y,w,h; lines C2h (x+1,y)-(x+w−2,y); C0h (x,y+1)-(x,y+h−2), (x+w−1,y+1)-(x+w−1,y+h−2); C7h (x+1,y+h−1)-(x+w−2,y+h−1); box C3h: x+1, y+1, w−2, h−2 |
| `2c11:1746` | `draw_corner_rivets()` | rivets at (x+2,y+2), (x+2,B−6), (R−5,y+2), (R−5,B−6) |
| `2c11:17db` | `draw_riveted_panel()` | `tile_fill_rect(); draw_frame(); draw_corner_rivets()` |
| `2c11:17ec` | `draw_header_panel()` | `draw_bevel_box(); draw_corner_rivets(); font_select(FONT4); text_engrave_center(label, C1h, B1h, C0h)` |
| `2c11:181e` | `draw_side_riveted_panel()` | `tile_fill_rect(); draw_frame();` for ry = y+5 .. B−6 step 7: rivet at (x+4, ry) and (R−6, ry) |
| `2c11:1871` / `18d0` | `draw_small_button_up` / `draw_small_button_down` | as `1575`/`15d4` with `FONT3`, `draw_groove(1)`, text y+4 / y+5 |
| `2c11:192f` | `btn_small_cb(border)` → activated | if border: `rect_grow(2)`, rect_save, x −= 1, R' = x+w+1, B; lines C2h top, BFh left/right, C0h bottom; rect_restore; `rect_shrink(2)`; then `(5FDC & 0Ch) ? draw_small_button_down : _up`; returns `(5FDC & 10h) != 0`, playing `snd_play(18h)` when true |
| `2c11:1a0e` | `btn_cb()` → activated | `(5FDC & 0Ch) ? draw_button_down() : draw_button_up()`; returns `(5FDC & 10h) != 0` with `snd_play(18h)`. **The standard button callback**: screens call it first and act when it returns 1 |
| `2c11:1a40` | `diamond_edge(i)` | line from vertex i to vertex (i+1)&3 of `5FF0[]`/`5FE8[]` |
| `2c11:1a76` | `draw_diamond(fill, phase)` | vertices (top, right, bottom, left): x = {x + w/2, x + w − 1, x + w/2, x}, y = {y, y + w/2, y + h − 1, y + w/2}; `fill_poly(4)` in `fill`; then 4 edges starting at `phase & 3`, colours C9h, C9h, C6h, C6h |
| `2c11:1aff` | `diamond_label(q, pressed)` | `font_select(FONT4)`; `text_engrave(label, C4h, C9h, pressed ? C8h : C7h, x + q + 4, y + pressed + 4)` |
| `2c11:1b65` / `1b8d` | `draw_diamond_up` / `draw_diamond_down` | `draw_diamond(C7h, 1)` / `(C8h, 3)`; `diamond_label(item.user & 3, 0 / 1)` |
| `2c11:1bb5` | `diamond_cb()` → activated | `(5FDC & 0Ch) ? down : up`; activation as `btn_cb` |
| `2c11:1be7` | `panel_fill_frame()` | `2303 = 0; rect_fill_c1(); draw_frame()` |

### 2.1 `draw_title_plate()` (`2c11:0ed6`) — L (checked against the call sequence)

```
save 2316; label = item.+0E; if label == 0 return
2316 = 2318; font_select(FONT2)
tx = text_center_x(label, x, w); tw = text_width(label)
lpad = tx − x − 2; rpad = x + w − (tx + tw) − 1
P = PARTS[0]; ph = P.h
tile_fill(x, y + ph, w, h − ph − 5)                 // body
tile_fill(x + 6, y + ph − 7, w − 12, 7)             // shoulder
lines C2h (x+lpad−4, y)-(x+w−rpad, y); (x+7, y+ph−7)-(x+lpad−12, y+ph−7)
      B5h (x+lpad−4, y+1)-(x+w−rpad, y+1); (x+6, y+ph−6)-(x+lpad−17, y+ph−6)
      C2h (x+w−rpad+10, y+ph−7)-(x+w−7, y+ph−7); B5h (x+w−rpad+16, y+ph−6)-(x+w−6, y+ph−6)
L = x + lpad; Rr = x + w − rpad
save_rect(6000, L−15, y+ph, 10, 10); restore_rect(6000, L−15, y+4, 10, 10)   // copy a tile patch up
230E = get_pixel(L−15, y+5); for k = 8..1: line (L−16−j, y+5+j)-(L−16−j, y+5+j+k)   // left slope
for (c = L−5; c < Rr; c += 10): copy the 10×10 patch from (c, y+ph) to (c, y+2) and (c, y+ph−8)
copy patch (Rr−4, ...) to y+2 and y+ph−8; (Rr+6, y+ph) → (Rr+6, y+4); right slope mirrored
for (c = x+5; c < x+w−9; c += 10): patch (c, y+h−20) → (c, y+h−10)
draw_frame_inset(6, ph); text_emboss(label, −1, −1, C1h, C0h, B1h)   // tx centred, ty = y+5
draw_bitmap(P, tx − P.w − 2, y, 2); draw_bitmap(P, tx + tw + 1, y, 0)
draw_plate_corners(ph)
restore 2316
```

(The exact slope loops: `for k = 8; k > 0; k--: line (lx, ly)-(lx, ly+k); lx--; ly++` starting at
`lx = L−16, ly = y+5` on the left and `lx = Rr+16`, `lx++` on the right, colour sampled at
(L−15, y+5) / (Rr+15, y+5).)

## 3. Text flow (`drawtext.c`, segment `2dd0`) — V

State: `6006` left margin x, `6004` right margin x, `6009` line height, `6008` draw enable (0 =
measure only), `600B` style (0 = `draw_text`, else `text_engrave(s, C7h, B3h, C0h, x, y)`).
Scratch word buffer `DS:419A` (~150 bytes).

| Address | Name | Behaviour |
|---|---|---|
| `2dd0:0009` | `flow_setup(style, line_h, draw)` | `600B = style, 6009 = line_h, 6008 = draw` |
| `2dd0:0020` | `flow_line_h()` | returns `6009` |
| `2dd0:002a` | `flow_word(char *w, int *x, int *y)` | leading ',' / '.' characters are drawn one by one at (x,y) and x advances (they are never wrapped away from the previous word); then if `*x + text_width(w) > 6004`: `*y += 6009, *x = 6006`; if `w[0] == ' '` and `*x == 6006`: skip the leading spaces; draw w (if `6008`) at (x, y); `*x += text_width(w)` |
| `2dd0:0123` | `flow_emit(char *buf, int *x, int *y)` | repeat until empty: find the first ' ', else TAB, else LF; if found: cut after it, `flow_word(piece)`; else find '$': if found: cut there, `flow_word(piece)`, newline (`*y += 6009, *x = 6006`), continue after '$'; else `flow_word(rest)` and stop |
| `2dd0:01eb` | `flow_text(char far *txt, char nstr, char far *(far *subst)(char))` → u8 height | uses the current rect: `6006 = x, 6004 = x + w − 1`; starting at (x, y) processes `nstr` consecutive NUL-terminated strings (each after the first begins with an implicit space). Per char: `'%'` with a subst function: the following char c is consumed and the string `subst(c)` (if non-null) is appended; `'%'` without subst is literal; `'$'`, or a space (ctype bit 1 at `DS:3CD1`) when the buffer is not empty: append it and `flow_emit` the buffer; spaces with an empty buffer are skipped; others appended. End of string: `flow_emit`. At the end, if x > left margin: `y += 6009`. Returns `(y − y0)` as a byte |
| `2dd0:0355` | `flow_text_buttons(tbl_off, tbl_seg, first, subst, strings, x, y, right)` → lines | font FONT3, `2302 = 1`, margins x..right, `flow_setup(−3, 11, 1)`; `strings` = near array of `char *` ending with 0; same parsing, but `%c` calls `subst(c, &tbl[first + (c − 'a')])` (item record pointer): if it returns non-null the text is inserted; if it returns 0 the item becomes an **inline button**: `tw = text_width(item.label)`; wrap if `x + tw + 5 > right`; item.x = x − 1 − tbl[0].x, item.y = y − 3 − tbl[0].y, item.w = tw + 4, item.h = 6009 − 2, item.user = 1, item.mask = 3; `x += tw + 5`. A '%' at the end of a string is fatal (drawtext.c line 123h). Returns `(y_end − y0) / 6009` (+1 line if x > margin at the end) |

## 4. Event loop and input (`menu.c`, segment `2e25`) — V

### 4.1 Input polling `menu_poll()` (`2e25:0049`)

```
2031 = 2033
k = kbd_getkey(); 6017 = k & FFh; 6016 = k >> 8
if 6016 == 0Fh (Tab) && (key_down(2Ah) || key_down(36h)): 6016 = 29h     // Shift-Tab
kbd_…(0)
2033 = 2030 ? key_down(1Ch) : (key_down(1Ch) || key_down(39h))          // Enter (, Space)
if 43B6 (joystick):
    2033 = 2033 || joy_button(0) || joy_button(1)
    if 6016 == 0:
        d = joy_dir(0)
        if d == 0 || !tmr_expired(6010): goto mouse
        6016 = d&2 ? 'P'(50h, Down) : d&1 ? 'H'(48h, Up) : d&4 ? 'K'(4Bh, Left) : d&8 ? 'M'(4Dh, Right) : 6016
        tmr_set(6010, 45)                       // 45 ticks = 0.19 s auto-repeat
    else tmr_set(6010, 0)
mouse:
if 43B7 (mouse): mouse_get_pos(&601A, &6018); 2033 = 2033 || mouse_button(0) || mouse_button(1)
if 6016 in NAVKEYS (DS:2024 = {0Fh Tab, 29h Shift-Tab, 48h Up, 50h Down, 4Bh Left, 4Dh Right}): snd_play(19h)
clamp 601A to 0..319, 6018 to 0..199; if mouse: mouse_move_to(601A, 6018)
```

(Down is tested before Up, so a diagonal gives Down/Up rather than Left/Right.)

### 4.2 Functions

| Address | Name | Behaviour |
|---|---|---|
| `2e25:0008` / `0012` | `menu_nav_off` / `menu_nav_on` | `2035 = 0 / 1` |
| `2e25:001c` | `menu_key_nav()` | if `6016` is in NAVKEYS (index i): `hs_navigate(DS:202A[i])` with dirs `{3, 2, 0, 1, 2, 3}` (Tab = right/next, Shift-Tab = left/previous) |
| `2e25:0246` | `menu_message(char *s, yes_no)` → bool | pop-up box at the bottom: `font_select(FONT3)`, `2302 = 1`; `w = text_width(s) + 10`, `h = 20`, `x = 160 − w/2`, `y = 170`; `rect_grow(3)`; saves the front page area (`2316 = 2312`… actually saves page 2312 into a farmalloc buffer of `save_size(w, h)`; fatal menu.c line 9Dh if no memory); `rect_shrink(3)`; on the work page: `draw_popup_box()`, `2300 = C5h`, `text_engrave(s, C7h, B3h, C0h, text_center_x(s), y + 7)`; `rect_grow(3)`; copy that rect to the front page; `menu_flush()`; wait: plain mode → until a key or the button is pressed, then until the button is released; yes/no mode → until scan `15h` ('Y') or `31h` ('N'); restores the saved block to the work page, copies it to the front page, frees the buffer, `cursor_draw`/`cursor_flush` at `5FD0,5FCE`. Returns 1 (plain) or `6016 == 15h` (yes/no) |
| `2e25:0419` | `menu_hotkey(scan)` → handled | **Alt** held (`key_down(38h)`): scan table at `2e25:04C3`: Q (10h) and X (2Dh) → `227c:002a` (sets `DS:00C1 = 1`: quit request); T (14h) → screenshot (`0000:032c`: saves page 2314 as `SNAPSHOT.LBM` through `3a13:031e`); S (1Fh) → `0b48:03c7(2)`; D (20h) → `0b48:03c7(1)`; J (24h) → `0b48:03c7(0)`; M (32h) → `0b48:03c7(3)` (sound/music/joystick/mouse toggles, see `shell_ui_screens.md` `0b48`); C (2Eh) → `230d:0063` (joystick re-calibrate: `joy_detect`, `DS:43B6 = present`); V (2Fh) → `menu_message(version string DS:2036, 0)`. **Ctrl** held (`1Dh`): Q → quit request, T → screenshot, V → version. Returns 1 when Alt/Ctrl combination was handled, also 1 for an unknown Ctrl key; 0 when neither modifier is down |
| `2e25:04e7` / `04f2` | `menu_set_result(v)` / `menu_get_result()` | `600E` |
| `2e25:04fc` | `menu_run(void far (*frame)(void))` → result | §4.3 |
| `2e25:05d7` | `menu_busy()` → bool | `menu_poll(); menu_hotkey(6016)`; returns 1 while the button is down or the key is Esc (scan 1) |
| `2e25:0602` | `menu_wait_timer()` | loops while `DS:2E3F != 0` and `menu_busy() == 0` (a timed wait that input interrupts) |
| `2e25:0621` | `menu_flush()` | drains the BIOS keyboard buffer; `2033 = 2031 = 6016 = 6017 = 0` |
| `2e25:063f` | `menu_delay(n)` | `DS:2E3F = 13 n` (PIT ticks, i.e. n BIOS ticks of 1/18.2 s); `menu_flush(); menu_wait_timer()` |
| `2e25:0659` | (empty) | |

### 4.3 `menu_run(frame)` (`2e25:04fc`)

```
600E = 0
menu_flush(); while (menu_busy()) ;            // wait until the button is released
6016 = 6017 = 0; 2033 = 0
if frame: frame()                               // first frame (normally hs_dispatch + hs_present)
600E = 0
while 600E == 0:
    if win_detect() && 4F6D && !4F6C: 166d:0009 (Windows focus handling, shell.md) else 4F6D = 0
    if 00C1 (quit requested): if menu_message("Exit to DOS? (Y/N)", 1): shell_exit(0) else 00C1 = 0
    menu_poll()
    if 6016 == 1 (Esc): menu_set_result(2)
    else: if 2035: menu_key_nav(); if menu_hotkey(6016): 6016 = 6017 = 0
    if frame: frame()
return 600E
```

Result convention used everywhere: **1 = accept/OK, 2 = cancel/Esc**, other values = screen
specific. The loop has **no frame limiter**: it spins as fast as the machine allows; all visible
timing comes from `menu_delay`, `tmr_*` (236.7 Hz ticks) and the TTM player.

## 5. Screens, palettes and string tables (`screen.c`, segment `2e8a`) — V

### 5.1 The screen table `SCREENS<n>.DAT`

`2e8a:0164 screens_load()` opens `res_name("screens", 2008:0018("dat","rb"), "dat")` — the digit
is the data set chosen by shell_data's extension check (0 = base game, 1 = with the 1946 add-on:
`SCREENS1.DAT` differs only in entry 52, `REQUEST1`). Layout: u32 text size, u16 n, n × (u16
name offset, u16 scd offset), then the text. `DS:601C` = xmalloc'ed array of n × (char *bg, char
*scd). Both files have 62 entries:

| Id | Background | Labels (`.SCD`) | Id | Background | Labels |
|---|---|---|---|---|---|
| 0–9 | `MT_DACE` `MT_DSQD` `MT_CAP` `MT_FSWP` `MT_SCRM` `MT_TRNG` `MT_ESCT` `MT_INTR` `MT_ANTI` `MT_GRND` | `FLYMISS2` | 36 | `START8` | — |
| 10 | `PARTS` | — | 37 | `CLOUDS` | — |
| 11 | `MAINMENU` | `MAINMENU` | 38–41 | `FLTDK0`–`FLTDK3` | `FLTDECK` |
| 12 | `PRECORD` | `PRECORD` | 42 | `PARTS` | `BEST` |
| 13 | `BIGMAP` | `BIGMAP` | 43 | `CLOUDS` | `CAMPBOX` |
| 14 | `DOGACE` | `DOGACE` | 44 | `CLOUDS` | `CAMPSET` |
| 15 | `CAMPSEL` | `CAMPSEL` | 45 | `MAINMENU` | `CAREER` |
| 16 | `CAMPSELJ` | `CAMPSEL` | 46 | `MAINMENU` | `CONTROL` |
| 17, 18 | `RUMUSA`, `RUMJAP` | — | 47 | `CLOUDS` | `DECISION` |
| 19, 20 | `SQD_A`, `SQD_J` | `SQUADINF` | 48 | `CLOUDS` | `FLYFOR` |
| 21 | `BRIEF` | `MISSBRF` | 49 | `MAINMENU` | `FLYMISS` |
| 22 | `MISSDEBR` | `MISSDEBR` | 50 | `PARTS` | `FULL` |
| 23 | `FLYHIST` | `FLYHIST` | 51 | `PARTS` | `REALISM` |
| 24 | `NEWAIR` | — | 52 | `PARTS` | `REQUEST` / `REQUEST1` |
| 25 | `SIM` | `VIEW` | 53 | `PARTS` | `RESULTS` |
| 26 | `PREFLITE` | `PREFLITE` | 54 | `PARTS` | `STRTNEAR` |
| 27 | `FLTMAP` | `FLTMAP` | 55 | `CLOUDS` | `VWHICH` |
| 28 | `START0` | `SIGNIN` | 56 | `PARTS` | `TEXTBOX` |
| 29–35 | `START1`–`START7` | — | 57 | `PARTS` | `FIELD` |
|  |  |  | 58, 59 | `LOGPAGE` | —, `INQUIRY` |
|  |  |  | 60, 61 | `PARTS` | `CUSTMISS`, `CWHICH` |

The background name gives `<name>.SCR` (picture) and `<name>.PAL`. `PARTS` means "no picture:
clear to black" (and keep the current `PARTS` palette); `MAINMENU` pictures are cached in the
spare page when the adapter allows (below).

### 5.2 Functions

| Address | Name | Behaviour |
|---|---|---|
| `2e8a:000e` | `scr_is_parts(id)` | `strcmp(bg[id], "PARTS") == 0` |
| `2e8a:0034` | `scr_is_mainmenu(id)` | `strcmp(bg[id], "MAINMENU") == 0` |
| `2e8a:005a` | `scr_pal_load(id)` → far pal | `pal_load(res_name(bg[id], −1, "pal"))` |
| `2e8a:0087` | `scr_palette(id)` → far pal | `2084 = id`; PARTS → the resident `PARTS` palette `601E:6020`; MAINMENU → cached `6022:6024` (reloaded, the old one freed, when `id != 2097`); else `scr_pal_load(id)` (a new palette each time) |
| `2e8a:00ee` | `scr_pal_release(pal)` | `pal_free(pal)` unless it is one of the two resident palettes |
| `2e8a:0124` | `scr_init()` | `6022:6024 = scr_pal_load(11)` (MAINMENU), `601E:6020 = scr_pal_load(10)` (PARTS); `screen_show(10, 0, 0, 0, 0)`; `22ce:00a7` (work page := spare page copy) |
| `2e8a:0281` | `scr_file(id)` → name | `res_name(bg[id], −1, "scr")` |
| `2e8a:02a7` | `scr_touch(id)` | `fopen(scr_file(id), "rb")` + `fclose` (pre-reads the file: result unused) |
| `2e8a:02c7` | `scr_load(id)` | `2302 = 0`; `39aa:000a(scr_file(id))` (SCR decoder into page `DS:2318`, video) |
| `2e8a:02e0` | `scr_cached_mainmenu(id)` → bool | only when `scr_is_mainmenu(id)` and the adapter type `DS:231D` is 2 or 8: `2316 = 2318 = AC00h` (a 4th page segment above the three), load the SCR there if `2086 != id` (`2086 = id`), then `2318 = 2312; page_copy_full()`; returns 1. Else 0 |
| `2e8a:0331` | `scr_draw_bg(id)` | PARTS → `screen_clear_black()`; else `2318 = 2312`, cached main-menu copy or `scr_load(id)` |
| `2e8a:0363` | `scr_prefetch(id)` | not PARTS and (not MAINMENU or not cached) → `scr_touch(id)` |
| `2e8a:038e` | `screen_open(id, far draw_fn, scd_arg, defer_pal)` | if `scd_arg != 0` and `scd[id] != ""`: `strtab_load_scd(res_name(scd[id], −1, "scd"), scd_arg)` (`24e3:0087`); if `draw_fn == 2e8a:0009`-sentinel (the value `3e8a:0009` = "draw the background"): `scr_prefetch(id)`; `pal = scr_palette(id)`; if draw_fn: sentinel → `scr_draw_bg(id)`, else `draw_fn()`; then `defer_pal == 0` → `page_flip(0); pal_set(pal); scr_pal_release(pal)`, else `ui_set_pending_palette(pal)` (installed by the next full `hs_present`) |
| `2e8a:0454` | `screen_show(id, scd_arg, defer_pal)` | `id == −1` → `2086`; if `2084 == id` (same screen as before): `scr_draw_bg(id)`, and `page_flip(0)` unless deferred; else `screen_open(id, sentinel, scd_arg, defer_pal)`. **Every screen starts with this call** (e.g. main menu: `screen_show(11, 87h, 1)`) |
| `2e8a:049d` | `scr_load_scd(id, arg)` | `24e3:0177(res_name(scd[id], −1, "scd"), arg)` (loads a second string table, used by dialogs) |

`scd_arg` is passed to shell_data's string-table loader (`24e3:0087`/`0177`); the values seen
(87h, 396h, 43h…) are Likely the buffer size/flags of that loader (hand-off).

## 6. Dialogs

All dialogs are hot-spot tables in far data, run with the helpers of `soft.c`:

| Address | Name | Behaviour (V) |
|---|---|---|
| `2ed6:0552` | `dlg_run(off, seg, n, far frame)` → result | `22ce:00bc` (save the work page into the spare page); `hs_push()`; `hs_default_links(tbl, n)`; `hs_set_table(tbl, n)`; `hs_draw_all()`; `r = menu_run(frame)`; `hs_pop()`; `req_close()` (`3038:00b6`); `22ce:00a7` (restore the work page from the spare page); `hs_draw_all()`; `hs_pop()`; returns r (byte) |
| `2ed6:05bc` | `dlg_open(off, seg, n, focus, links)` | `22ce:00bc`; `hs_push()`; if links: `hs_default_links`; `hs_set_table`; `hs_focus(focus)`; `hs_draw_all()` |
| `2ed6:0602` | `dlg_close()` | `22ce:00a7`; `hs_dispatch(601A, 6018, 2033, 1)` (redraws the restored screen's items); `hs_pop()`; `hs_focus(5FDE)`; `cursor_set(PARTS[6])`; `mouse_move_to`; `hs_present()` |
| `2ed6:0654` | `dlg_modal(off, seg, n, focus, far frame, far on_ok)` → result | `dlg_open(..., 1)`; `r = menu_run(frame)`; `hs_pop()`; if `r == 1` and on_ok: `on_ok()`; `dlg_close()`; returns r |
| `2ed6:06a3` | `dlg_modal2(off, seg, n, far frame, far on_ok)` → result | as `dlg_run` (restore + redraw inside), then `on_ok()` when r == 1 |

Frame functions of dialogs are `hs_dispatch(601A, 6018, 2033, 0); hs_present()` (`2ed6:022b`,
`2f47:0083`, `3038:0079`, `307d:00cf`) — the text-entry and list-box frames add their key handler.

### 6.1 Choice list "CHOOSE" (`soft.c`, table `4cb0:000d`, 13 items)

| # | Rect (rel.) | Callback | Mask/flags | Role |
|---|---|---|---|---|
| 0 | 108,23,106,210 (abs; height/x recomputed) | `draw_side_riveted_panel` | 40 | window |
| 1 | 0,0,0,0 | `2ed6:000d` | 40 | title "CHOOSE" (DS:20C3): `font_select(FONT4)`, `text_engrave_center("CHOOSE", C1h, B1h, C0h)`, rivet groups beside it (2 rivets at tx−7 and tx+tw+3, y+4; 1 rivet at tx−15 and tx+tw+11, y+11) |
| 2–12 | 8, 20+17k, 91, 10 (last h 11) | `2ed6:024c` | 74 / 02 | entries; label filled in at run time |

| Address | Name | Behaviour |
|---|---|---|
| `2ed6:00c4` | `choose_draw_entry(pressed)` | FONT3; lines: top (x,y)-(x+w,y) in B3h (up) / C7h (pressed); C0h sides (x,y)-(x,y+h), (x+w,y)-(x+w,y+h); bottom in C7h / B3h; box B8h x+1, y+1, w−1, h−1; `text_engrave(label, B3h, C7h, C0h, text_center_x, y + 2 / y + 3)` |
| `2ed6:01f2` | `choose_entry_cb` → activated | pressed look while `5FDC & 0Ch` (with `snd_play(18h)`), returns `5FDC & 10h` |
| `2ed6:022b` | `choose_frame()` | dispatch + present |
| `2ed6:024c` | `choose_click()` | `602E = 5FDE − 2`; if activated: `menu_set_result(602E < 6030 ? 1 : 2)` (the last entry is CANCEL) |
| `2ed6:027a` | `choose_layout(title, labels[], cb_off, cb_seg)` | `4cb0` item 1 label = title (`4cb0:001B`); for k < 6030: entry k: callback = cb, label = labels[k]; widest label; entry 6030 = "CANCEL" (DS:20BC); window h (`+13`) = `602A + 602C·6030`; window w (`+11`) = maxw + 60; window x (`+0D`) = 160 − w/2; every entry 1..12: x = (160 − (maxw+30)/2) − window.x, w = maxw + 30; `6032 = FFh` |
| `2ed6:03c9` | `choose_on_ok()` | if `6026:6028`: calls it with `(6032 != −1) ? 6032 : 602E` |
| `2ed6:03ee` | `choose_run(far cb, first_str, scd_row)` | `6030 = item.user` of the calling item (count, fatal if > 10); for each k: copies `strtab_get(0, scd_row + k)` into xmalloc'ed strings; `6026:6028 = cb`, `602E = first_str` (initial choice); `choose_layout("CHOOSE" DS:20CA, strings, 2ed6:024c)`; `dlg_modal(4cb0:000d, 13 − (10 − 6030), 602E + 2, choose_frame, choose_on_ok)`; frees the strings |
| `2ed6:050e` | `choose_init()` | `hs_default_links(4cb0:000d, 13)`; `602C = y[3] − y[2]` (entry pitch 17); `602A = window.h − 10·602C` (base height) |

### 6.2 Number/choice spinner (`choose.c`, table `4cc3:000f`, 7 items)

| # | Rect | Callback | Mask/fl | Role |
|---|---|---|---|---|
| 0 | 82,33,200,75 | `2f47:0031` | 40 | window: `draw_side_riveted_panel`; title (item `+0E` = `4cc3:001D`) with FONT3, `2302 = 3`, `text_engrave(label, C7h, B1h, C0h, x+12, y+3)` |
| 1 | 11,12,140,37 | `lbox_draw` (`2fa5:0153`) | 5C | list body (6 px rows) |
| 2 | 157,8,23,42 | `draw_bevel_box` | 40 | scroll frame |
| 3 | 160,10,18,18 | `lbox_arrow_cb` | 7C / 02 | up arrow (label DS:20D2) |
| 4 | 160,29,18,18 | `lbox_arrow_cb` | 7C / 02 | down arrow (DS:20D4) |
| 5 | 12,55,61,13 | `2f47:0009` | 74 / 02 | "CANCEL" |
| 6 | 115,55,65,13 | `2f47:0009` | 74 / 02 | "ACCEPT" |

| Address | Name | Behaviour |
|---|---|---|
| `2f47:0009` | `pick_btn_cb` | `btn_small_cb(0)`; on activation `menu_set_result(5FDE == 6 ? 1 : 2)` |
| `2f47:0031` | `pick_draw_window` | above |
| `2f47:0083` | `pick_frame` | dispatch + present |
| `2f47:00a4` / `0113` | `pick_resize(h)` / `pick_unresize()` | `6038 = h − item1.h`; grows window h (`+13`), item 1 h (`+29`) and moves items 2,3,4,6 (not 5) down by 6038; window x = 160 − h/2 (sic: uses `+13` the height; Likely a bug/unused); undo subtracts |
| `2f47:0178` | `pick_on_ok` | `6034:6036(lbox_selected())` |
| `2f47:0191` | `pick_list(title, n, sel, fmt_off, fmt_seg, far on_ok)` | fatal if n < 1 (line 89h); `4cc3:001D = title`; `lbox_setup(0, 0, n, 5 visible, fmt, 0)`; `lbox_bind(4cc3:000f, 1, 3)`; `lbox_select(sel, 2)`; `6034:6036 = on_ok`; `dlg_modal(4cc3:000f, 7, 6, pick_frame, pick_on_ok)` |
| `2f47:0249` | `pick_aircraft(title, on_ok, …, a, b, sel)` | `2777:06fd(a, b)` (shell_data aircraft filter); list with the aircraft-name formatter `2777:0741`; else as above |
| `2f47:02e6` | `pick_list2(title, on_ok, n)` | list formatter `3550:0c99` (shell_data `tables.c`); selection 0 |
| `2f47:0374` | `pick_init()` | `hs_default_links(4cc3:000f, 7)` |

### 6.3 List box (`listbox.c`, table `4cd4:0010`, 9 items, V)

| # | Rect | Callback | Mask/fl | Role |
|---|---|---|---|---|
| 0 | 86,32,145,134 | `2fa5:0687` (`tile_fill_rect; draw_frame`) | 40 | window |
| 1 | 7,5,100,6 | `2fa5:0696` title (FONT3, `2302 = 3`, `text_engrave(label, C7h, B1h, C0h, x, y)`) | 40 | |
| 2 | 7,15,100,75 | `lbox_draw` | 5C | rows |
| 3 | 119,17,17,17 | `lbox_arrow_cb` | 7C / 02 | up (DS:2115) |
| 4 | 119,70,17,17 | `lbox_arrow_cb` | 7C / 02 | down (DS:2117) |
| 5 | 7,98,100,9 | `lbox_edit_draw` (`2fa5:053c`) | 74 / 02 | text field |
| 6 | 8,115,57,12 | `2fa5:000f` | 74 / 02 | "CANCEL" |
| 7 | 80,115,57,12 | `2fa5:000f` | 74 / 02 | OK (label set by the caller) |
| 8 | 0 | — | 0 | spare |

List state: `6071` item count, `6073` max top (count − visible, ≥ 0), `6075` visible rows,
`20FE` top index, `6079` cursor row, `6077` selected index (= top + row), `6065:6067` the body
item, `6064` index of the "up" arrow in its table, `606D:606F` `char far *fmt(int i)` (text of
entry i), `6069:606B` `void draw(int i, int x, int y)` (custom row drawing). Text field: `6043[21]`
buffer, `6042` max length (≤ 20), `2100` cursor, `2101` length, `2103` insert mode, `6040` allow
space, `2102` caret blink phase, `6058` blink timer, `6041` redraw, `603C:603E` the field item.

| Address | Name | Behaviour |
|---|---|---|
| `2fa5:000f` | `lbox_btn_cb` | `btn_cb()`; activated → `menu_set_result(5FDE == 7 ? 2 : 1)` (V: item 6, labelled CANCEL, returns **1** and item 7 returns 2; the callers of `lbox_run` read the result with that convention) |
| `2fa5:0033` | `lbox_arrow_draw` → pressed | `(5FDC & 0Ch) ? draw_list_button_down : draw_list_button_up`; returns 1 (with `snd_play(18h)`) only on the initial press (`5FDC & 4`) |
| `2fa5:006b` | `lbox_arrow_cb` | on press/auto-repeat (the item mask includes held 08h, and `lbox_arrow_draw` returns 1 only for 04h — V: so one step per press): up arrow (`5FDE == 6064`): `6079 > 0` → row−1, else top−1 if top > 0; down: row+1 if `6079 < 6075−1`, else top+1 if `20FE < 6073`; if changed: `6077 = 20FE + 6079`, `lbox_fill_edit()`, body item mask = 3 (redraw next dispatch) |
| `2fa5:00f6` | `lbox_hit_row(row, n, pitch)` → row | if `5FDC & 0Ch`: `r = (6018 − (y + 1)) / pitch` clamped 0..n−1; `snd_play(18h)` on press, `snd_play(19h)` when the row changes while held; returns r (else the old row) |
| `2fa5:0153` | `lbox_draw` | `6079 = lbox_hit_row(6079, 6075, 6)`; if changed: `6077 = 20FE + 6079`, `lbox_fill_edit()`; `draw_inset_box2()`; FONT3, `2302 = 1`; for each visible row r (row y = y + 2 + 6r): selected → box B9h outline / BEh fill at (x+2, ry+1, w−3, 7), text colour CDh; else CCh; text: custom `draw(20FE + r, ry + 2)` or `draw_text(fmt(20FE + r), x + 5, ry + 2)`; item mask := 5Ch |
| `2fa5:0255` | `edit_set(char *s)` → ok | if `strlen(s) ≤ 6042`: copy to `6043`, cursor = length = strlen, `6041 = 1`, field item mask = 3 |
| `2fa5:02a3` | `lbox_fill_edit()` | if count > 0 and row ≥ 0 and fmt: `edit_set(fmt(6077))` |
| `2fa5:02ce` | `edit_char_ok(c)` | ctype bits 0Eh (alnum) or '_' or (' ' when `6040`) |
| `2fa5:02f9` | `edit_key()` → changed | fatal if cursor > length (135h), length > max (136h), max > 20 (137h); if scan `6016` is one of the 7 editing keys at `DS:2104` (`memchr`), jump through the table `2fa5:04D9` (Backspace, Delete, Left, Right, Home, End, Insert: Likely order — table not decoded here, hand-off to the port: straightforward); else if `edit_char_ok(6017)`: insert mode → needs length < max, shifts the tail right (`memmove`), length+1; overwrite → needs cursor < max, length+1 only when cursor == length; stores the char, cursor+1; returns 1 |
| `2fa5:04f5` | `glyph_width(c)` | width of c (space if 0) in the current font |
| `2fa5:053c` | `lbox_edit_draw` | terminates at length; width of the text before the cursor; if `6041` or redraw: `draw_inset_box2()`, text CCh at (x+5, y+3), `2302 = 1`; caret: line (cx, y+8)-(cx + glyph_width(char at cursor) − 1, y+8) in CCh when `2102` else 0 (black), cx = x + width + 5; `6041 = 1`; item mask := 40h |
| `2fa5:0612` | `edit_poll()` | if the scan code is one of 10 keys at `DS:210B` → `6017 = 0` (no char); `edit_key()` → redraw; `tmr_expired(6058)` → `tmr_set(6058, 59)`, `2102 ^= 1` (caret blink every 59 ticks ≈ 0.25 s) |
| `2fa5:0687`, `0696` | window / title callbacks | above |
| `2fa5:06dd` | `edit_bind(off, seg, idx)` | `603C:603E = &tbl[idx]` |
| `2fa5:06fa` | `edit_setup(char *init, max, allow_space)` | fatal if max > 20 (23Dh); field item = `4cd4:0094`; `6042 = max, 6040 = allow_space`; `tmr_set(6058, 59)`; `edit_set(init)` when given |
| `2fa5:0761` | `lbox_bind(off, seg, idx, up_idx)` | body item `6065:6067 = &tbl[idx]`, `6064 = up_idx` |
| `2fa5:0784` | `lbox_select(i, row)` | fatal unless 0 ≤ i < count (253h) and row ≥ 0 (254h); row clipped to visible−1; `6077 = i`; if i < row: `6079 = i, 20FE = 0`; else `20FE = i − row, 6079 = row`, and if `20FE > 6073`: `20FE = 6073, 6079 = i − 6073` |
| `2fa5:082c` | `lbox_setup(title, …, n, visible, fmt_off, fmt_seg, draw_off, draw_seg)` | body = `4cd4:003C`, up index 4; title (`4cd4:00CE`), OK label (`4cd4:0034`)… (2 words); `6071 = n`; fmt/draw callbacks; `6079 = 6077 = 20FE = 0`; `6073 = max(0, n − visible)`, `6075 = n − 6073`; `edit_setup(0, 15, 0)`; `lbox_fill_edit()` |
| `2fa5:08bd` | `lbox_frame` | dispatch + present + `edit_poll()` |
| `2fa5:08e2` / `08ec` | `edit_text()` / `lbox_selected()` | `DS:6043` / `6077` |
| `2fa5:08f6` | `lbox_run()` | `dlg_run(4cd4:0010, 9, lbox_frame)`; `hs_draw_all()` |
| `2fa5:091c` | `lbox_init()` | `hs_default_links(4cd4:0010, 9)` |

### 6.4 Text entry (`2f7f`, table `4cce:0000`, 4 items) — V

| # | Rect | Callback | Mask/fl | Links | Role |
|---|---|---|---|---|---|
| 0 | 91,50,147,48 (w recomputed) | `2f7f:0035` | 40 | | window: `tile_fill_rect; draw_frame`; prompt (label) FONT3 `text_engrave(label, C7h, B3h, C0h, x+13, y+5)`; 6 rivets at (x+5, y+5) and (x+w−7, y+5) |
| 1 | 15,14,117,11 | `lbox_edit_draw` | 40 | | field |
| 2 | 15,29,55,13 | `2f7f:000d` | 74 / 02 | 03,03 | "CANCEL" |
| 3 | 77,29,55,13 | `2f7f:000d` | 74 / 02 | 02,02 | "ACCEPT" |

| Address | Name | Behaviour |
|---|---|---|
| `2f7f:000d` | `entry_btn_cb` | `btn_small_cb(0)`; activated → `menu_set_result(5FDE == 3 ? 1 : 2)` |
| `2f7f:0035` | `entry_draw_window` | above |
| `2f7f:00bf` | `entry_frame` | dispatch + present + `edit_poll()` |
| `2f7f:00e5` | `entry_trim(anon)` | strips trailing spaces of `*603A`; empty and `anon` → `"(Anonymous)"` (DS:20F2) |
| `2f7f:012d` | `entry_store()` | `strcpy(*603A, edit_text())` |
| `2f7f:0143` | `text_entry(prompt_id, char *buf, max, anon)` → accepted | `603A = buf`; `req_open(57 (FIELD), 43h)` (loads `FIELD.SCD` as the second table); FONT3; prompt = `str_get(prompt_id)` → item 0 label; window w = text_width + strlen + 8; item 2 x… (`4cce:0042 = w − 4cce:0046 − 4cce:002C`: ACCEPT right-aligned), field x centred: `(w − field.w)/2`; `edit_setup(buf, max, 1)`; `edit_bind(4cce:0000, 1)`; `dlg_open(…, 4 items, focus 3, links 0)`; `2030 = 1` (Space types a space instead of pressing); `r = menu_run(entry_frame)`; `2030 = 0`; `req_close()`; `hs_pop()`; accepted → `entry_store()`; `entry_trim(anon)`; `dlg_close()`; returns r == 1 |
| `2f7f:026a` | (empty init) | |

### 6.5 Request / message box (`3038`, table `4ce2:0000`, 4 items) — V

| # | Rect | Callback | Mask/fl | Role |
|---|---|---|---|---|
| 0 | 81,50,180,h | `draw_side_riveted_panel` | 40 | window, h computed |
| 1 | 12,8,158,h | `3038:0005` | 40 | text: FONT3, `2302 = 1`, `flow_setup(3, 8, 1)`, `flow_text(str_get(607D), 607C strings, subst = 6080:6082)` |
| 2 | 15,y,55,13 | `3038:004c` | 74 / 82 | button (label = string id) |
| 3 | 77,y,55,13 | `3038:004c` | 74 / 82 | button |

| Address | Name | Behaviour |
|---|---|---|
| `3038:0005` | `req_draw_text` | above: the message is string `607D` of the loaded `REQUEST.SCD` (plus the following `607C − 1` strings), with `%c` substitutions supplied by the caller's far function `6080:6082` (0 = none) — V |
| `3038:004c` | `req_btn_cb` | `btn_small_cb(0)`; activated → `607F = (5FDE == 3)`, `menu_set_result(1)` |
| `3038:0079` | `req_frame` | dispatch + present |
| `3038:009a` | `req_open(screen_id, arg)` | `24e3:0164()` (push the string table), `scr_load_scd(screen_id, arg)`, `2120 = 1` |
| `3038:00b6` | `req_close()` | if `2120`: `24e3:01fd()` (pop the string table), `2120 = 0` |
| `3038:00cc` | `req_layout(subst_off, subst_seg, str_id, nstr, extra_h)` | saves the table state; `6080:6082 = subst`, `607D = str_id, 607C = nstr`; `req_open(52 (REQUEST), 396h)`; FONT3; `hs_load(4ce2:0000, 1)`; `flow_setup(3, 8, 0)` (measure); `h = flow_text(...)`; window h (`+06`) = h + extra + 40; text item h (`+1C`) = h + extra + 15; button y (`+2E`, `+44`) = window h − button h − 6; restores the table state |
| `3038:01b9` | `req_ok(subst_off, subst_seg, str_id, btn_id)` | `req_layout(…, 1, 0)`; one button: item 2 x = 62 (`+2C`), label id = btn_id (default 2); `hs_default_links(3)`; `dlg_run(4ce2:0000, 3, req_frame)`; item 2 x back to 15 |
| `3038:0237` | `req_yes_no(subst_off, subst_seg, str_id, yes_id, no_id)` → yes | `req_layout`; window and text rect moved up 35 (`4ce2:0024`, `4ce2:003A` −= 23h — L: these are item 1/2 fields); labels yes_id (default 3), no_id (default 5); `607F = 0`; `dlg_run(4 items)`; restores; returns `607F` (1 when item 3 was pressed) |
| `3038:02fe` | `req_yes_no_wide(subst_off, subst_seg, str_id, yes_id, no_id)` → yes | window +15 px high, buttons 130 px wide at x 25 (`+2C = +42 = 19h`, `+30 = +46 = 82h`), moved down 15; otherwise as `req_yes_no`; restores the geometry |
| `3038:043f` | `req_init()` | `hs_default_links(4ce2:0000, 4)` |

### 6.6 Flight roster dialog (`fltalert.c`, table `4ce8:0011`, 12 items) — L

"Your flight of %a includes:" (DS:213F) / "Enemy flight of %a includes:" (DS:2164) with the list
of pilots and an ACCEPT button; used by the flight deck (shell_ui_screens). Items: 0 window
(75,43,170,110) `307d:002a`; 1 (80,3,10,10) `307d:00f0` close box (`6032 = FEh`, result 1); 2–6
(25,30+20k,120,13) `307d:010d` pilot entries; 7–11 spare copies built at run time.

| Address | Name | Behaviour |
|---|---|---|
| `307d:0008` | `flt_subst(c, item)` | `%a` → item label = number word `DS:2122[6085]` (flight size); returns 0 → becomes an inline button |
| `307d:002a` | `flt_draw` | FONT3; `draw_side_riveted_panel`; own flight: "Yourself" (DS:215B) engraved at (x+65, y+20); `flow_text_buttons(4ce8:00AB, 1, flt_subst, {fmt, 0}, x+10, y+6, x+w)`; item mask := 40h |
| `307d:00cf` | `flt_frame` | dispatch + present |
| `307d:00f0` | `flt_close_cb` | `choose_entry_cb`; activated → `6032 = FEh`, result 1 |
| `307d:010d` | `flt_pick_cb` | `btn_small_cb(1)`; activated → `6032 = 5FDE − 2`; result 2 if it is the last entry (own flight: index ≥ n−1; enemy: ≥ n) else 1 |
| `307d:0159` | `flt_build(names[])` | copies the pilot names into items 2…; copies the template items `4ce8:0011+22k` to `4ce8:00AB+22k` for the visible count; last entry label "ACCEPT" (DS:2181) |
| `307d:020f` | `flt_roster(cb_off, cb_seg, char *pilots, enemy)` → bool | `6084 = enemy`, `6085 = item.user` (flight size ≤ 4, fatal F2h); window h = (enemy ? 50 : 30) + 20·n; names: pilot code < 4 → `strtab_get(0, code)`, else `2550:0043(code − 4)` (ace name, shell_data); `6026:6028 = cb`; `flt_build`; `r = dlg_modal2(4ce8:00AB, n + (enemy ? 3 : 2), flt_frame, choose_on_ok)`; frees; returns r != 2 |
| `307d:0376` | `flt_init()` | `hs_default_links(4ce8:0011, 7)` |

## 7. Sounds used by the toolkit

`snd_play` ids: 18h button press/activate, 19h focus move / list row change, 1Ah click on
nothing. (Resource ids of the shell sound bank `SHELL.SX`, loaded in `sys_init`; sound spec.)

## 8. Port notes

* The toolkit is fully software (page copies + driver primitives): model the three pages and the
  AC00h cache page as 320×200 byte buffers; `page_flip` = swap work/front and present.
* `menu_run` has no frame cap; the port should present at most once per host frame and yield
  (sleep) inside `menu_run`/`menu_busy` loops, keeping the 236.7 Hz tick counter `DS:1CC8` and the
  countdown `DS:2E3F` driven by real time.
* Mouse: the INT 33h wrappers become host mouse position scaled to 320×200; `mouse_move_to`
  (focus navigation warps the pointer) should move the virtual pointer only.
* Screenshot (Alt/Ctrl-T, `SNAPSHOT.LBM`) can be kept or mapped to a PNG writer.
