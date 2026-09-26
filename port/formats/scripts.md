# Scripts: TTM animation scripts, shell string tables (.SCD, text .DAT)

Addresses are `SSSS:OOOO` file segments as in `port/*_functions.csv` (PS.EXE unless stated;
PS DGROUP `4D08`, AP DGROUP `3EA4`, INTRO DGROUP `17E0`). AP addresses refer to the de-overlaid
`work/AP_flat.exe`. Tags: **Verified** = read in the code and consistent over all data;
**Likely**; **Unknown**.

Tools: `tools/dynttm.py` (disassembler, `work/ttm/<VOL>/<NAME>.TTM.txt`, opcode usage table
`work/ttm/_opcodes.txt`), `tools/dyndata.py` (string tables → `work/data/`).

## 1. TTM scripts (63 entries)

DGDS "TTM" scripts, as in Rise of the Dragon / Heart of China / Willy Beamish (ScummVM `dgds`
engine), in an earlier and reduced variant. 52 scripts say `VER "4.09"`, 11 say `"4.08"`
(`AWRDMED`, `AWRD_JP`, `INTACE2`, `INTACE4`, `JAPFLAG`, `JNPAPER`, `RUMUSA`, `SIMQ_JP/US`,
`USAFLAG`, `USPAPER`); the interpreter does not look at the version.

### 1.1 Entry layout (Verified)

| Chunk | Contents |
|---|---|
| `VER:` | `"4.09\0"` / `"4.08\0"` |
| `PAG:` | u16 = number of **frames** (= number of `0FF0` opcodes; checked on all 63). Loader default 14Ah when absent (`3B02:0030`) |
| `TT3:` | packed (u8 method = 1 RLE, u32 unpacked size, data): the opcode stream |
| `TTI:{TAG:}` | u16 n, n × (u16 tag, NUL-terminated name): labels for `TAG` opcodes (`1 = "init f4u"`, `1 = "something"`) |

Loader `3B02:0030` (INTRO `1125:002F`, AP `24FC`): allocates a D4h-byte script record (linked list
at `DS:36D8`, current `DS:36DC`): +02 frame count, +04/+08 far start/end of the code, +0C u16
bitmap handle[6], +18 font handle[6], +24 far palette[6], +3C far saved area[6], +6C/+84/+9C/+B4
x/y/w/h of the saved areas[12], +CC next, +D0 far pointer to the frame table (frame count + 1
far pointers into `TT3`). A second per-run context (`DS:36E2`) keeps the current slots: +0E
"don't draw" flag, +10 font slot, +12 palette slot, +14 bitmap slot, +16 get/put slot, +1C
brush, +1E/+1F fg/bg colour, +20..+27 clip window.

### 1.2 Opcode encoding (Verified)

u16 opcode: high 12 bits = operation, **low nibble = number of u16 arguments** (as in DGDS).
Nibble `F` = one NUL-terminated string argument, padded so that string + NUL has even length
(`3B02:0381`). Exception: `AF1F`/`AF2F` (polygons) take u16 n followed by n (x, y) pairs
(interpreter `3BAF:0540`, special case at the top of the loop). Arguments are signed 16-bit.
Opcodes `1301`/`1311` (older sound opcodes) are rewritten to `C051`/`C061` before dispatch.

### 1.3 Execution (Verified)

`3BAF:0540 run_frame(frame)` (PS; the same 3811-byte function is INTRO `11D2:053F`) takes the
frame's start from the frame table and executes opcodes until `0FF0`, then returns 1; the
caller waits the frame delay (`DS:76A4`, set by `1021`/`2022`) and steps to the next frame, or
to `DS:7608` if a `GOTO` set it. `GOSUB` runs another frame recursively with a drawing offset.
`find_tag(tag)` (`3BAF:1547`) returns the first frame whose first opcode is `1101`/`1111` with
that argument. Dispatch: class `Axxx` → draw routine `3BAF:01A7` (table `CS:04DC`, then wipes
`A014–A094`/`A0B5` → `3BAF:1689`, strings `A204–A294`); class `Cxxx` → sound `3BAF:000D`
(table `CS:0101`, skipped while drawing is off); others → table `CS:147B` (47 entries), then
`F10F–F19F`. After each `Axxx` op the touched rectangle is added to the update list
(`3B02:096B`, table `CS:1423`).

The AP copy (`2595:038B`, 1770 bytes) knows only 21 opcodes (`0070 0080 0090 00C0 0110 1031 1051
1061 1071 1101 1111 1121 1201 2002 3003 4004 4214 F01F F02F F04F F05F`), the `Axxx` class (same draw
table) and `F10F–F19F`; `Cxxx` is ignored. That is all the cockpit scripts use.

### 1.4 Opcodes

"Used" = occurrences in the 63 scripts (`work/ttm/_opcodes.txt`). Handler addresses are PS
`3BAF:xxxx`. Mnemonics follow ScummVM where the behaviour matches.

| Op | Mnemonic | Args | Effect (handler) | Used | Status |
|---|---|---|---|---|---|
| `0000` | END | | (not a case: only `INTACE2` ends with it) | 1 | Verified |
| `0010` | NOP | | nothing (`0BC7`) | 0 | Verified |
| `0020` | SAVE_BG | | copy the screen to the background buffer (`3B02:0A2D`) | 22 | Likely (callee not read) |
| `0070` | FREE_PAL | | free the palette of the current palette slot (`0B2E`) | 54 | Verified |
| `0080` | FREE_BMP | | free the bitmap of the current bitmap slot (`084C`) | 788 | Verified |
| `0090` | FREE_FONT | | free the current font (`0A4A`) | 0 | Verified |
| `00C0` | FREE_GETPUT | | free the area saved in the current get/put slot (`0996`) | 0 | Verified |
| `00E0` | ANIM_CLOSE | | close the `39BD` player (flag `DS:36E4`) (`07CA`) | 0 | Likely |
| `0110` | PURGE | | `DS:7606 = 1` (`10B2`) | 62 | Verified (meaning of the flag Likely) |
| `0400` | PAL_RESET | | `16E3:1014(-1,0,0)`, re-apply palette (`0F1A`) | 0 | Likely |
| `0500`/`0510` | | | `DS:3864 = 1 / 0` | 0 | Verified |
| `0FF0` | FRAME_END | | end of frame | 4637 | Verified |
| `1011` | | a | `16E3:35C9(a)` | 0 | Unknown |
| `1021` | SET_DELAY | ticks | frame delay `DS:76A4` | 128 | Verified |
| `1031` | SET_BRUSH | n | context +1C | 0 | Likely |
| `1041` | | a | `DS:7672 = a` | 0 | Unknown |
| `1051` | SEL_BMP | slot | bitmap slot (0–5) | 1539 | Verified |
| `1061` | SEL_PAL | slot | palette slot; on VGA the DAC is **not** changed — the palette is applied at the next FADE_IN/FADE_OUT/PAL_RESET or by the player's apply step (only adapter id 4 uploads at once; `video_palette.md` §5.3) | 144 | Verified |
| `1071` | SEL_FONT | slot | font slot (`16E3:35D5` sets it) | 0 | Verified |
| `1101`, `1111` | TAG | tag | no-op; label for GOTO/GOSUB (names in `TTI:`) | 121 (all `1111`) | Verified |
| `1121` | SEL_GETPUT | slot | get/put slot | 0 | Verified |
| `1201` | GOTO | tag | next frame = `find_tag(tag)` | 0 | Verified |
| `2002` | SET_COLORS | fg bg | drawing colours | 50 | Verified |
| `2012` | SET_FRAME? | a b | `2221:0111(a, b)` | 3 | Unknown (ScummVM: SET FRAME) |
| `2022` | RAND_DELAY | min max | delay = min + rand % (max − min) | 0 | Verified |
| `2032` | | a b | `39BD:03D1(a, b)` (animation player) | 0 | Unknown |
| `2302/2312/2322` | PAL_BLOCK | first last | palette-cycle block 0/1/2 (`DS:768E`, `DS:7694`) | 0 | Verified |
| `2402` | PAL_CYCLE | mask period | registers the blocks selected by mask bits 0–2 for cycling (`3BAF:1631`); the cycle step routine has no caller, so **nothing animates** (`video_palette.md` §4.6, §5.8) | 0 | Verified |
| `3003` | GOSUB | dx dy tag | run frame `tag`, drawing offset (dx, dy) | 0 | Verified |
| `3103` | SCROLL | dir steps dist | **hardware scroll** effect (CRTC/attribute programming, INTRO `103D`, PS `30B5:000F`) + full-screen update; used by no shipped script (`video_palette.md` §7) | 0 | Verified |
| `4004` | SET_CLIP | x1 y1 x2 y2 | clip window | 8 | Verified |
| `4114` | FADE_OUT | first n col speed | fade colours first..first+n−1 to colour col; speed indexes `DS:3868` | 19 | Verified |
| `4124` | FADE_IN | first n col speed | fade in (same arguments) | 29 | Verified |
| `4136` | FADE_PART | first n col from% to% ticks | partial fade between two levels (% × 64/101); the last argument is a **duration in 59.17 Hz ticks**, not a step count (`video_palette.md` §5.7, §6) | 8 | Verified |
| `4204` | STORE_AREA | x y w h | copy area into the background buffer (`3B02:0A94`) | 27 | Likely |
| `4214` | SAVE_GETPUT | x y w h | save a screen area into the current get/put slot | 0 | Verified |
| `5005` | | 5 args | no-op | 0 | Verified |
| `A002` | PIXEL | x y | pixel, fg | 74 | Verified |
| `A014–A094`, `A0B5` | WIPE | x y w h [a] | screen transition number (op>>4)&F (`3BAF:1689`) | 33 (`A044`, `A074`, `A0B5`) | Likely |
| `A0A4` | LINE | x1 y1 x2 y2 | line, fg | 0 | Likely |
| `A104` | RECT_FILL | x y w h | filled rectangle | 47 | Verified |
| `A114` | RECT | x y w h | rectangle outline | 1 | Verified |
| `A204–A294` | TEXT | x y w h | draw string slot (op−A204)>>4 with the current font | 0 | Verified |
| `A304` | | x y w h | `3A5A:000D` | 0 | Unknown |
| `A404`/`A424` | CIRCLE(_FILL) | x y w h | r = h/2, centre (x+r, y+r); `A404` filled, `A424` outline | 0 | Verified |
| `A5f4` | SPRITE | x y frame slot | draw a bitmap frame; f = flip flags: 1 vertical, 2 horizontal (mirror), 3 both | 5835 | Verified (flip meaning Likely) |
| `A5f5` | SPRITE_COL | x y frame slot col | SCN bitmap with base colour col (resources.md §4c) | 652 | Verified |
| `A5f6` | SPRITE_SCALE | x y frame slot w h | draw scaled to w × h (`16E3:2BBA`) | 548 | Verified |
| `A5A7` | SPRITE_ROT | x y frame slot w h angle | `16E3:4021`, angle 0–FFFFh | 261 | Likely |
| `A601` | PUT_GETPUT | slot | redraw the saved area | 0 | Verified |
| `A704` | | x y w h | `39BD:02D3` (animation player) | 0 | Unknown |
| `AF02` | FLOOD | x y | flood fill, bg colour | 0 | Likely |
| `AF1F`/`AF2F` | POLY / POLY_FILL | n, n×(x,y) | polygon outline / filled | 0 | Verified (encoding) |
| `B000`/`B013` | | – / a b c | `3A48:0001` / `3A48:0059` | 0 | Unknown |
| `B606` | COPY_AREA | x y w h src dst | copy an area between screen buffers | 0 | Likely |
| `C01F`/`C02F` | SND_NAME / SND_BANK | name | copy name to `DS:7681` / `DS:7674` (`C02F "TTD.SX"`) | 25 | Verified |
| `C031` | SND_LOAD | id | `45F0:000C(bank, id)` | 24 | Likely |
| `C041`–`C0A1` | | id | sound API calls `4609`, `464D` (**play**, `C051`), `467E` (**stop**, `C061`), `4625`, `462A`, `45E4`, `4675` | 32 (`C051`) | Likely |
| `C0E3` | SND_FADE | id target ticks | `snd_fade(id, target, ticks)` (`sound.md` §9; used once: `C0E3 1001 0 60` in `INTACE5`) | 1 | Verified |
| `C0B2`–`C0F4` (others), `C102`, `CF01`, `CF11` | | 2–4 | further sound API calls (`sound.md` §9) | 0 | Verified (sound) |
| `F01F` | LOAD_SCR | name | load a `.SCR` as the background (`39AA:000A`), then SAVE_BG | 20 | Verified |
| `F02F` | LOAD_BMP | name | load a `.BMP` into the current bitmap slot (`3922:0002`) | 743 | Verified |
| `F04F` | LOAD_FONT | name | load a `.FNT` into the current font slot | 0 | Verified |
| `F05F` | LOAD_PAL | name | load a `.PAL` into the current palette slot (`16E3:0D1F`) | 86 | Verified |
| `F08F` | ANIM_OPEN | name | open the `39BD` animation player | 0 | Likely |
| `F10F–F19F` | SET_STRING | text | string slot (op−F10F)>>4 = text; later slots cleared | 0 | Verified |

41 distinct opcodes are used; the sound opcodes (`Cxxx`) are the sound agent's territory
(`port/formats/sound.md`).

### 1.5 Which script runs where

| Scripts | Program | Run by | Notes |
|---|---|---|---|
| `INTACE1`–`INTACE5` (SHELL1), `INTACE31/41/51` (M1SHL, 1946 versions) | INTRO | intro sequence (names `intace1`…`intace5` in INTRO.EXE; the M1 variants are Likely chosen when the add-on volumes are present) | Dynamix logo, clouds, title, quote, `TTD.SX` sounds; `INTACE5` = 365 frames |
| `INTACE6` | PS | `04DF:0002`, shell start | title after returning to the shell |
| `AWRDMED`, `AWRD_JP/US`, `JAPFLAG/USAFLAG`, `MEDJAP/MEDUSA`, `PRISJAP/PRISUSA` | PS | awards/medal ceremony `0F35:01D8`; table `TTMS0.DAT` (`0F35:012D`, data.md §3.6) | 82-frame flag/award builds |
| `USPAPER`, `JNPAPER`, `RUMUSA`, `RUMJAP`, `WARENDA/J`, `WARE46A/J` | PS | career events `EVENTS0/1.EVT` (TTM name per event) | newspapers, rumours, war end |
| `SIMQ_JP/US` | PS | (trigger not traced; uses `SIMQ_HDL/SML.FNT`) | 3 frames: palette + screen + sound |
| `<plane>.TTM` (SIM1: 28, M1SIM: 7) | AP | cockpit construction (`2595:038B`) | always 85 frames (J7W 88): frame 0 `TAG 1 "init <plane>"` + `COCPAL.PAL`; then one frame per cockpit part/view (panels, sights, wing/tail views, emblems, damage), built into the cockpit view buffers (`CPVW.BUF`?) |

## 2. Shell string tables: `.SCD` and text `.DAT` (Verified)

All little-endian; strings NUL-terminated, Latin-1.

| Variant | Where | Layout |
|---|---|---|
| A | all 35 `.SCD` (SHELL1, M1SHL, `Game/MAINMENU.SCD`) | u32 n, u16 end[n]; strings start at 4+2n; string i = [end[i−1], end[i]) with end[−1] = 0; end[n−1] = rest of the file |
| A′ | shell text `.DAT` (`ACETEXT0`, `CMPTXT0`, `HIST*0`, `PLTEXT0`, …) | u32 n, u16 start[n−1] of strings 1…n−1; strings at 4+2(n−1), string 0 first |
| B | 1946 add-on text `.DAT` (`ACETXT0`, `CMPTEXT0`, `HISTBF_0`, …) | u32 text size, u16 n, u32 start[n] (start[0] = 0); strings at 6+4n |
| B′ | 1946 `PLTXT0/1` | as B with u16 starts, strings at 6+2n |

67 tables decode (`dyndata.py`; each boundary checked against the NULs). `.SCD` = the labels
of one shell screen (`MAINMENU.SCD`: `MAIN MENU`, `FLY SINGLE MISSION`, `CAREER MENU`, `VIEW
VEHICLES`, `OTHER OPTIONS`, `MISSION RECORDER`, `EXIT TO DOS`, `MISSION RECORDER`); the loose
`Game/MAINMENU.SCD` differs only by `QUIT` for `EXIT TO DOS`. **Corrected:** `my_fopen` opens a
loose file on disk before searching the volumes (resources.md §1), so the loose copy **is** the one
the shell shows (QUIT). The PS reader's view of variant A is `u16 n, u16 off[n], u16 size, text`
(`shell_data_emd1.md`), byte-for-byte the same as `u32 n, u16 end[n]` above.

27 further shell `.DAT` files mix records and strings (`BRIEF`, `DEBRIEF`, `DISPLAYS`,
`FLTPLAN`, `STRINGS`, `SFTBTNS`, `SHIPTEXT`, `MISC`, `OPTIONAL`, `RANKS`, `MEDALS`, `STATION`,
`SCREENS0/1` (screen/background names per shell page, and the mission-type codes `MT_DACE`
`MT_DSQD` `MT_CAP` `MT_FSWP` `MT_SCRM` `MT_TRNG` `MT_ESCT` `MT_INTR` `MT_ANTI` `MT_GRND`), …):
not decoded, `dyndata.py` lists their strings with offsets.

## Open questions

* `1101` vs `1111` (both labels here); `2012`, `A5A7` argument meanings; the wipe numbers.
* Caller loop of `run_frame` (delay units, when PURGE unloads); what `SAVE_BG`/`STORE_AREA`
  buffers are exactly (`3B02:0A2D`, `3B02:0A94`).
* How the AP maps cockpit views to the 85 frames (cockpit.c) — for the 3D/cockpit work.
* How INTRO picks `INTACE31` etc.; who runs `SIMQ_*`.
