# Sound — porting spec (SCI player `1373`/`430a`/`3060`, sound API, `SSM:ADL:` driver, `sx_sim`)

Addresses: `port/RE_GUIDE.md` conventions (`SSSS:OOOO` file segments; AP = `work/AP_flat.exe`).
DGROUP: INTRO `17E0`, PS `4D08`, AP `3EA4`. Confidence tags: **verified** (read in the disassembly;
for the player and the driver also re-implemented in `tools/aotpsnd.py` and exercised on all 106
sounds), **likely**, **guess**. File formats (`.SX`, `.SNG`, SCI sound resources, the OVL chunks, the
patch bank) are in `port/formats/sound.md`; this spec restates only what the code needs and corrects
it where noted (§14). Symbols: `port/spec/sound_symbols.csv`.

Scope decided in `PLAN.md`: the port implements the **SCI player** (device independent) and the
**AdLib driver** (`SSM:ADL:`, fed to Nuked-OPL3 in OPL2 mode). MT-32 (`M32`/`NLD`), Tandy (`TAN`), PS/1
(`PS1`) and PC speaker (`STD`) drivers are parked; their interface is the same (§8.1) so the player
does not change when they are added.

## Index

1. Overview, call graph, what runs where
2. Time base and concurrency
3. Data structures (record, node, effect pool, player tables, DGROUP globals)
4. Address map of the three programs (player, API)
5. The SCI player (`1373`): every routine
6. The sound API (INTRO `157f`–`172c`, PS `4516`–`46c3`, AP `326c`–`333b`)
7. Driver loading, driver numbers, `-s<num>`, the loose `*.DRV` files
8. The AdLib driver `SSM:ADL:` (all 18 functions, internals)
9. TTM sound opcodes (`C0x1`…`CF11`)
10. Game call sites: INTRO
11. Game call sites: PS
12. Game call sites: AP and `sx_sim`
13. Port notes
14. Corrections to `port/formats/sound.md`
15. Hand-offs
16. Open questions

---

## 1. Overview

Three layers, the same in INTRO, PS and AP:

```
game code ──► sound API (C, DGROUP globals)      "play sound id 1002", "stop all effects", volume, fade…
                │   records (one per loaded sound) + nodes (one per playing instance)
                ▼
             SCI player 1373 (Sierra SCI1 midi.s, asm, state in its own code segment)
                │   16 "device channels", priority list of ≤16 playing nodes, channel remapping
                ▼   lcall driver:0000 with BP = function number
             sound driver (SSM:ADL: etc., loaded from SXCODE.OVL / SX.OVL / SX1.OVL, position independent)
                │   OPL2 register writes, port 388h/389h
                ▼
             AdLib (OPL2)
```

* The **player** is byte-identical in the three programs (moved within its segment: PS offsets = INTRO
  + 1, AP offsets = INTRO + 4; its data lives in the code segment and moves with it). It is Sierra's
  SCI1 sound module: priority list, per-sound channel state, device-channel remapping by priority and
  voice budget, fades, loop points, signals.
* The **API** layer is Dynamix C code: sound records loaded from `.SX` banks (INTRO/PS) or a `.SNG`
  bank (AP), music vs effect classes (music: one node per record, exclusive, `play(node,1)`; effects:
  a pool of 7 nodes, `play(node,0)`), enable/disable of each class, load/unload, the driver/patch
  loader and shutdown. INTRO also drives it from TTM script opcodes (§9).
* The **driver** is an unmodified Sierra SCI1 driver ("dude" AdLib driver without version string),
  18 functions selected by BP.
* A **timer client** at 59.17 Hz (every 4th tick of the 236.69 Hz PIT, see platform spec) calls the
  player service `1373:17de`, which advances every sound by one tick and calls driver fn 3.

### Call graph (INTRO names; PS/AP equivalents in §4)

```
sys_init 038e:080d
 ├ snd_init 1593:0004(drvno, "sxcode.ovl")
 │   ├ snd_load_driver 16ac:000b ─┬ ovl_load_chunk 1620:000e("SSM:ADL:") → snd_res_read 15b5:0001 → snd_read_all 172c:000e
 │   │                            ├ player_attach 1373:0075 → 0398 (fn 0: patch no, voices, play id)
 │   │                            └ snd_load_patch 163c:0006 → ovl_load_chunk("SSM:003:") → player_init 1373:0086 → 03c8 (fn 1, fn 11)
 │   ├ timer_install 05da:2374(13)            (only if the timer is not installed yet)
 │   ├ timer_add 05da:2307(1373:17de, 4)       → player_service every 4th PIT tick = 59.17 Hz
 │   └ snd_pool_alloc 1610:0005               (7 effect nodes)
 ├ snd_load_resource 1659:000b("ttd.sx", 0)    → snd_rec_load 157f:0009 × n → snd_res_read 15b5:0001 (device track only)
 └ snd_disable 164d:0006(-2 / -1)              (effects / music off per CONTROL.PRF)

TTM player → ttm_sound_op 11d2:000c → snd_play 16b6 / snd_stop 16e6 / snd_fade 16a4 / … → 1373 stubs

timer ISR 05da:241a ──(every 4th tick)──► player_service 1373:17de
    ├ remap 0c1e (if flagged)
    ├ per node: fade 15fc, sequence 1932 (events → driver fns 4,5,7,8,10), loop/stop
    ├ send_pending_volumes 1796 (≤ 2 per tick, fn 7 ctrl 7)
    └ driver fn 3 (voice ageing)

exit paths: snd_shutdown 1686:0004 → snd_unload(0), timer_remove, timer_restore, pool free, snd_driver_close 16d5:0001 (fn 12, fn 2)
```

---

## 2. Time base and concurrency

* `timer_install(13)` (platform, INTRO `05da:2374`): PIT divisor 65536/13 = 5041 → **236.69 Hz**.
  `snd_init` installs it only when no one else did (`DS:15BE` = 0 in INTRO, "timer installed" flag
  of the platform) and then remembers it in `DS:1F4D` so `snd_shutdown` restores it.
* The player service is a timer client with countdown 4: **59.17 Hz, 16.90 ms per tick**. Every
  delta time unit in the sound data is one service tick; fades step per service tick; the driver's
  voice ages count service ticks.
* **Re-entrancy guard**: word `busy` (player `cs:036f`). The service returns immediately when it is
  non-zero. `remap` (`0c1e`) and `mute_all` (`08ac`) increment it for their duration, so a service
  tick that interrupts them is skipped (not deferred). The only other user is `040c` (lock/unlock,
  no caller found).
* All player entry points that change the node list or node state run with `pushf; cli … popf`
  (`play`, `stop`, `pause`, `fade`, `set_volume`, `set_priority`, `controller`, `restore`) — i.e.
  atomically with respect to the service. `hold` (`08a2`), `pitch_bend` (`0b04`) and the queries
  do not disable interrupts.
* `snd_driver_close` (`16d5:0001`) needs two more service ticks after terminate: if no timer client
  is registered it calls the service twice directly; otherwise it registers a second client
  (`16d5:008d`, countdown 4) that decrements `DS:33D4` from 5 and busy-waits until it reaches 0
  (≈ 85 ms).

**Port**: run the service from the host timer at 59.17 Hz (accumulate 16.90 ms steps in the audio
callback or a dedicated timer; see §13) and serialise every API call with it (one mutex around the
player + driver + OPL state). The busy-skip semantics only matter if the port calls the service
while an API call is in progress, which the mutex prevents; keep `busy` as a plain counter.

---

## 3. Data structures

### 3.1 Sound record (0x14 bytes, class 3 allocation) — API layer (verified)

One per loaded sound, singly linked from `rec_head` (INTRO `DS:1F47` far ptr), newest first.

| Off | Size | Field |
|---|---|---|
| 00 | far | next record |
| 04 | far | resource data (unpacked, filtered to one device track, starts with `84 00`, §6.3) |
| 08 | u16 | resource length (low word) |
| 0A | u16 | sound id (`INF:`/`DAT:` id; in AP the SNG chunk index) |
| 0C | u16 | priority (`DAT:` byte 2; 7 in every SX sound) |
| 0E | far | node (music records only; 0 when not playing) |
| 12 | u16 | flags: bit 0 = **music** class (memory class 4, else 7), bit 1 = **loop**, bit 4 = **pending** (to be (re)started when its class is re-enabled), set/cleared at run time |

### 3.2 Node (0x17A bytes, class 2 allocation) — player (verified; offsets used by `1373`)

| Off | Size | Field |
|---|---|---|
| 008 | far | → handle (normally `node+16A`); `FFFF:FFFF` = no data (play/prepare skip) |
| 00C | u16[16] | channel position (offset from the channel start; 0 = channel ended) |
| 02C | u16[16] | loop position |
| 04C | u16[16] | delay counter: ticks left before the next event; bit 15 set = inside an `F8` run (§5.9) |
| 06C | u16[16] | loop delay |
| 08C | u8[16] | channel number (0–15; FF = no channel, FE = digital) — indexed by *track slot* |
| 09C | u8[16] | running status — by slot |
| 0AC | u8[16] | loop running status — by slot |
| 0BC | u16[15] | pitch bend (14 bits, 2000h centre) + sustain in bit 15 — by **MIDI channel** |
| 0DA | u8[15] | voices (low nibble) \| priority<<4 — by MIDI channel |
| 0E9 | u8[15] | modulation |
| 0F8 | u8[15] | pan |
| 107 | u8[15] | volume (unscaled) |
| 116 | u8[15] | program |
| 125 | u8[15] | sounding note (FF none; only the last note is kept) |
| 134 | u8[15] | flags: 1 locked (keep the channel number), 2 not remapped (fixed) |
| 143 | u8[15] | mute: low nibble = ctrl 4Eh mute (0/1), high nibble = mute-all count |
| 152 | u16 | cue counter (control `B? 60`) |
| 154 | u16 | tick counter (ticks since start / loop) |
| 156 | u16 | loop tick |
| 158 | u8 | **signal**: FF = stopped/not playing, else last `CF v` signal (0 at start) |
| 159 | u8 | state: 0 stopped, 1 playing, 2 playing locked |
| 15A | u8 | hold value (`B? 52 v` jumps to the loop point / ends when equal) |
| 15B | u8 | fixed priority (1 = resource priority byte does not override 15C); never set by the API |
| 15C | u8 | priority (list order, higher first) |
| 15D | u8 | loop flag (restart at the loop point when every channel ended) |
| 15E | u8 | node volume 0–7Fh |
| 15F | u8 | reverb (7F = use the default) |
| 160 | u8 | fade target (bit 7 = stop at end) |
| 161 | u8 | fade ticks per step |
| 162 | u8 | fade tick counter |
| 163 | u8 | fade step (0 = no fade running) |
| 164 | u8 | pause count |
| 165 | u8 | digital channel + 1 (bit 7 = sample started); 0 on AdLib |
| 166 | far | raw resource pointer (with the `84 00` header) — API |
| 16A | far | resource pointer after the header (`res_skip_header`) — the handle target |
| 172 | far | next node of the same sound (chain used by `node_nth`; always 0 here) |

The per-MIDI-channel tables have stride 15 but are indexed with channel 0–15: channel 15 (control)
reads/writes the first byte of the next table. **Quirk**, harmless with this data (the control
channel's entries are only written by the preamble init, see §5.5); the port must keep the byte
layout (model the node as a 0x17A-byte array).

### 3.3 Effect pool (API, verified)

`pool[7]` = INTRO `DS:33D6`–`33F1` (7 far pointers to nodes allocated once by `snd_pool_alloc`,
`+158` = FF when free, `+8` = `node+16A`). An effect plays on the first free pool node; at most **7
effects** at a time (an 8th request is ignored). A second request for an effect that is already
playing (same data pointer, signal ≠ FF) is ignored — effects do not restart.

### 3.4 Player variables (in the player's code segment; INTRO `1373:xxxx`, PS +1, AP +4)

| Off | Size | Name | Meaning / initial value |
|---|---|---|---|
| 018F | far[16] | `list` | playing nodes, sorted by priority (highest first), null-terminated |
| 01CF | far[16] | `dig_list` | digital-sample nodes (only [0] written by remap; unused on AdLib) |
| 020F | u8[16] | `map` | device channel → (list index<<4 \| MIDI channel), FF free |
| 021F | u8[16] | `t_locked` | remap work: 1 if the entry is a locked channel |
| 022F | u8[16] | `t_prio` | remap work: priority value (0 = must play) |
| 023F | u8[16] | `t_voices` | remap work: voices taken |
| 024F | u8[16] | `t_entry` | remap work: entry (idx<<4\|ch), FF free |
| 025F–029E | | | remap backup of 021F–025E (rollback per node) |
| 029F | far[16] | `old_owner` | previous owner node per device channel (0 = none) |
| 02DF | u8[16] | `old_chan` | previous MIDI channel per device channel (0Fh = none) |
| 032F | u8[16] | `pend_vol` | queued ctrl-7 value per device channel, FF none |
| 033F | u8[15] | | `restore` save area (mute-all nibbles) |
| 034E | u16[16] + u8 | | `prepare` work table + priority byte (`036E`) |
| 036F | u16 | `busy` | re-entrancy counter |
| 0371 | far | `driver` | driver entry (`driver:0000`) |
| 0375 | u8 | `play_id` | device byte of the track to play (AdLib 00) |
| 0376 | u8 | `cur_dev` | sequencing work: device channel of the current channel (FF none) |
| 0377 | u8 | `cur_fixed` | sequencing work: current channel is fixed (flag 2) |
| 0378 | u8 | `voices` | driver voice budget (AdLib 9) |
| 0379 | u8 | `digital` | driver digital support (AH>>4 of fn 0; AdLib 0) |
| 037A | u8 | `cur_tag` | sequencing work: list index<<4 |
| 037B | u8 | `def_reverb` | default reverb (0) |
| 037C / 037E | u16 | `ch_first` / `ch_last` | device channel range from fn 1 (AdLib 0 / 15) |
| 0380 | u16 | | sequencing work: resource base |
| 0382 | u8 | | remap work: saved voice budget for rollback |
| 0383 | u8 | `remap_flag` | remap at the next service tick |
| 0384 | u8 | | `set_volume` work: queue flag |
| 0385 | u8 | `vol_rr` | round-robin start for `send_pending_volumes` |
| 0388 | u8 | `seeking` | 1 during `restore`: no driver output, no signal/cue updates, play does not reset counters |

---

## 4. Address map

### 4.1 Player (`1373` INTRO, `430a` PS, `3060` AP): PS = INTRO + 1, AP = INTRO + 4 (verified)

| INTRO | PS | AP | Name | Kind |
|---|---|---|---|---|
| 1373:0003 | 430a:0004 | 3060:0007 | `snd_get_cue` (node) → AX = cue count | far stub → 09f1 |
| 1373:0016 | 430a:0017 | 3060:001a | `snd_node_set_priority` (node, u8 prio) | far stub → 091e |
| 1373:002a | 430a:002b | 3060:002e | `snd_get_position` (node) → AX = CX(sec/2-ticks,s), DX = min | far stub → 09fb |
| 1373:003f | 430a:0040 | 3060:0043 | `snd_node_restore` (node) | far stub → 0433 |
| 1373:0050 | 430a:0051 | 3060:0054 | `snd_master_volume` (u16 v) | far stub → 04c3 |
| 1373:0061 | 430a:0062 | 3060:0065 | `snd_node_pause` (node or 0, u8 on) | far stub → 0816 |
| 1373:0075 | 430a:0076 | 3060:0079 | `player_attach` (far drv) → AL = patch no | far stub → 0398 |
| 1373:0086 | 430a:0087 | 3060:008a | `player_init` (far patch) → AX (FFFF fail) | far stub → 03c8 |
| 1373:009b | 430a:009c | 3060:009f | `snd_node_play` (node, u16 locked) | far stub → 0528 |
| 1373:00af | 430a:00b0 | 3060:00b3 | `snd_node_fade` (node, u8 target, u8 ticks, u8 step) | far stub → 087e |
| 1373:00c9 | 430a:00ca | 3060:00cd | `snd_sound_on` (u16 on) | far stub → 0428 |
| 1373:00da | 430a:00db | 3060:00de | `snd_node_volume` (node, u8 v) | far stub → 090e |
| 1373:00ee | 430a:00ef | 3060:00f2 | `snd_node_pitch_bend` (node, u16 value14, u8 chan) | far stub → 0b04 |
| 1373:0105 | 430a:0106 | 3060:0109 | `snd_node_stop` (node) | far stub → 080c |
| 1373:0116 | 430a:0117 | 3060:011a | `snd_node_hold` (node, u8 v) | far stub → 08a2 |
| 1373:012a | 430a:012b | 3060:012e | `snd_node_signal` (node) → AX = signal (0–FF) | far stub → 09e7 |
| 1373:013f | 430a:0140 | 3060:0143 | `snd_default_reverb` (u8 v) → AX | far stub → 04da |
| 1373:0150 | 430a:0151 | 3060:0154 | `snd_node_controller` (node, u8 ctl, u8 val, u8 chan) | far stub → 0a1c |
| 1373:016a | 430a:016b | 3060:016e | `player_terminate` () | far stub → 03ed |
| 1373:017b | 430a:017c | 3060:017f | `snd_node_mute_all` (node, u16 mute) | far stub → 08ac |
| 1373:0398 | 430a:0399 | 3060:039c | `p_attach` | near |
| 1373:03c8 | 430a:03c9 | 3060:03cc | `p_init` | near |
| 1373:03ed | 430a:03ee | 3060:03f1 | `p_terminate` | near |
| 1373:040c | 430a:040d | 3060:0410 | `p_lock` (CX=0 lock, else unlock) — no caller | near |
| 1373:0428 | 430a:0429 | 3060:042c | `p_sound_on` | near |
| 1373:0433 | 430a:0434 | 3060:0437 | `p_restore` | near |
| 1373:04c3 | 430a:04c4 | 3060:04c7 | `p_master_volume` | near |
| 1373:04da | 430a:04db | 3060:04de | `p_default_reverb` | near |
| 1373:0528 | 430a:0529 | 3060:052c | `p_play` | near |
| 1373:080c | 430a:080d | 3060:0810 | `p_stop_remap` | near |
| 1373:0816 | 430a:0817 | 3060:081a | `p_pause` | near |
| 1373:087e | 430a:087f | 3060:0882 | `p_fade` | near |
| 1373:08a2 | 430a:08a3 | 3060:08a6 | `p_hold` | near |
| 1373:08ac | 430a:08ad | 3060:08b0 | `p_mute_all` | near |
| 1373:090e | 430a:090f | 3060:0912 | `p_volume` | near |
| 1373:091e | 430a:091f | 3060:0922 | `p_set_priority` | near |
| 1373:09e7 | 430a:09e8 | 3060:09eb | `p_signal` | near |
| 1373:09f1 | 430a:09f2 | 3060:09f5 | `p_cue` | near |
| 1373:09fb | 430a:09fc | 3060:09ff | `p_position` | near |
| 1373:0a1c | 430a:0a1d | 3060:0a20 | `p_controller` | near |
| 1373:0b04 | 430a:0b05 | 3060:0b08 | `p_pitch_bend` | near |
| 1373:0b6a | 430a:0b6b | 3060:0b6e | `p_unlink` | near |
| 1373:0c1e | 430a:0c1f | 3060:0c22 | `p_remap` | near |
| 1373:15fc | 430a:15fd | 3060:1600 | `p_fade_step` | near |
| 1373:16b8 | 430a:16b9 | 3060:16bc | `p_set_node_volume` | near |
| 1373:1796 | 430a:1797 | 3060:179a | `p_send_pending_volumes` | near |
| 1373:17de | 430a:17df | 3060:17e2 | **`player_service`** (timer client) | far |
| 1373:1865 | 430a:1866 | 3060:1869 | `p_dig_check` (digital) | near |
| 1373:1893 | 430a:1894 | 3060:1897 | `p_dig_service` (digital) | near |
| 1373:1932 | 430a:1933 | 3060:1936 | `p_sequence` (one tick of one node) | near |
| 1373:1b76 | 430a:1b77 | 3060:1b7a | `ev_note_off` (8n) | near |
| 1373:1bc8 | 430a:1bc9 | 3060:1bcc | `ev_note_on` (9n) | near |
| 1373:1c42 | 430a:1c43 | 3060:1c46 | `ev_poly_at` (An) | near |
| 1373:1c73 | 430a:1c74 | 3060:1c77 | `ev_controller` (Bn) | near |
| 1373:1d72 | 430a:1d73 | 3060:1d76 | `ev_program` (Cn) | near |
| 1373:1dc4 | 430a:1dc5 | 3060:1dc8 | `ev_chan_at` (Dn) | near |
| 1373:1de8 | 430a:1de9 | 3060:1dec | `ev_pitch_bend` (En) | near |
| 1373:1e62 | 430a:1e63 | 3060:1e66 | `ev_sysex` (F0) | near |
| 1373:1e66 | 430a:1e67 | 3060:1e6a | `ev_control` (status nibble F: channel 15) | near |
| 1373:1f78 | 430a:1f79 | 3060:1f7c | `ev_skip_control` (unknown control events) | near |
| 1373:1fb5 | 430a:1fb6 | 3060:1fb9 | `scale_volume` | near |
| 1373:1fcd | 430a:1fce | 3060:1fd1 | `p_find` (node → list offset, FF) | near |
| 1373:1fef | 430a:1ff0 | 3060:1ff3 | `p_prepare` (device track table) | near |

All stubs: `push bp; mov bp,sp; push ds di si; les ax,[bp+6] (node) …; call near; pop…; retf`
(cdecl, far node pointer first; results in AX).

### 4.2 API modules

See §6 (tables with the three programs' addresses and DGROUP offsets).

---

## 5. The SCI player

Pseudo-C. `N` = node byte array, `N.w(o)` word. `drv(fn, …)` = `lcall driver:0000` with BP = fn and
the register arguments (§8.1); in the port a direct call into the driver model. Channel *slot* `s`
(0–15) indexes the track's channel list; `c = N[8C+s] & 0F` is its MIDI channel.

### 5.1 `p_attach` (0398) — verified

```
driver = ES:AX; (AH,AL,CH,CL) = drv(0)
voices = CL; play_id = CH; digital = (AH & F0) >> 4; return AL (patch number, FF = none)
```
AdLib fn 0 → AL 3, AH 1, CH 0, CL 9.

### 5.2 `p_init` (03c8) — verified

```
AX = drv(1, ES:AX = patch data)       // AdLib: loads the bank, resets the chip, master volume 15
ch_first = CL; ch_last = CH           // AdLib 0 / 15
drv(11, CL = 0)                        // reverb 0
return AX                              // AdLib 0; FFFF = failure
```

### 5.3 `p_terminate` (03ed): `drv(12, CL=15); drv(2)`. `p_sound_on` (0428): `drv(13, CL)` → AL.
`p_master_volume` (04c3): `if CL != FF && CL > 15: CL = 15; drv(12, CL)` → AL = previous.
`p_default_reverb` (04da): `CL == FF` → `drv(11, FF)` query; `CL > 10` → return `def_reverb`
unchanged; else `old = def_reverb; def_reverb = CL; if list[0] && list[0][15F] == 7F: drv(11, CL)`;
return old. `p_lock` (040c): `CX == 0` → `busy++`, else `if busy: busy--`. All verified.

### 5.4 Queries — verified

* `p_signal` (09e7): `CL = N[158]`; the stub returns `AX = CL` (0–FF; FF = not playing).
* `p_cue` (09f1): `CX = N.w(152)`.
* `p_position` (09fb): `t = N.w(154); DX = t / 3600; r = t % 3600; CH = r / 60; CL = (r % 60) >> 1`
  (minutes, seconds, half-ticks as SCI returns them); the stub returns AX = CX and leaves DX.

### 5.5 `p_play(node, locked)` (0528) — verified (model `Sequencer.play`)

```
cli
if node in list: p_unlink(node); p_remap()          // restart
N[159] = locked ? 2 : 1
p_prepare(node)
for s in 0..14:
    N.w(0C+2s) = 0x0D; N.w(2C+2s) = 3; N.w(4C+2s) = 0; N.w(6C+2s) = 0; N.w(BC+2s) = 0x2000
    N[8C+s] = FF; N[9C+s] = 0; N[AC+s] = 0
    N[DA+s] = FF; N[E9+s] = 0; N[116+s] = FF; N[107+s] = FF; N[F8+s] = FF; N[125+s] = FF
    N[134+s] = 0; N[143+s] = 0
N[8C+15] = FF; N[9C+15] = 0; N[AC+15] = 0
N[165] = 0; N[15A] = 0; N[15F] = 7F
N.w(0C+30) = 0x0D; N.w(2C+30) = 3; N.w(4C+30) = 0; N.w(156) = 0
R = *(far*)N.w(8)                                    // resource after 84 00, header rewritten by prepare
if R[20] != FF && N[15B] == 0: N[15C] = R[20]        // resource priority
for s in 0..15:
    off = R.w(2s); if off == 0: break
    dl = R[off]
    if dl == FE:                                     // digital channel
        if digital == 0: N.w(0C+2s) = 0; N.w(2C+2s) = 0; N[8C+s] = FE; continue
        N[165] = s + 1; break
    N[9C+s] = dl | B0                                // running status default: controller
    d = R[off+0C]; N.w(4C+2s) = (d == F8) ? 0x80F0 : d
    c = dl & 0F; N[8C+s] = c
    if dl & 10: N.w(0C+2s) = 3; N.w(4C+2s) = 0; N[134+c] |= 2; continue     // fixed: events from +3
    if dl & 20: N[134+c] |= 1                        // locked
    if dl & 40: N[143+c] = 1                         // starts muted
    if c == 15:
        if N[15F] == 7F: N[15F] = R[off+8]; continue // control channel: reverb default
    else:
        if N[DA+c]  == FF: N[DA+c]  = R[off+1]       // voices | prio<<4
        if N[116+c] == FF: N[116+c] = R[off+4]       // program
        if N[107+c] == FF: N[107+c] = R[off+8]       // volume
    if N[F8+c] == FF: N[F8+c] = R[off+0B]            // pan   (control channel reaches here only if 15F != 7F)
if N[159] == 2: for s in 0..14: N[134+s] |= 1        // play(node,1): every channel locked
// insert into list: first position whose node has priority <= N[15C]; later entries shift down
for i in 0..15:
    if list[i] == 0 || list[i][15C] <= N[15C]: shift list[i..14] to [i+1..15]; list[i] = node; goto ins
return (list full: node not inserted)
ins: if seeking: return
N.w(152) = 0; N.w(154) = 0; N[158] = 0; N[160..164] = 0
p_remap()
```

Note the channel preamble is read at **fixed offsets** (+1 voices/prio, +4 program, +8 volume, +0B
pan, +0C first delta) and events start at +0Dh (position 0x0D); on a loop restart without a loop
point the positions go back to +3 and the preamble events (`Cn`, `Bn 07`, `Bn 0A`) are executed.

### 5.6 `p_prepare(node)` (1fef) — verified

Done once per resource (in place, the resource stays rewritten; the loaders reserve ≥ 0x26 header
bytes for it, §6.3):
```
if N.w(8) == FFFF && N.w(A) == FFFF: return
R = *handle; if R[21..23] == FC FD FE: return
tab[16] = 0; prio = FF; p = 0
if R[0] == F0: prio = R[1]; p = 8
loop over tracks: dev = R[p]
    if dev == play_id: p++; s = 0; while (b = R[p++]) != FF: p++; tab[s++] = R.w(p); p += 4
                        break
    if dev == FF: break
    p++; while R[p++] != FF: p += 5                  // skip this track's 6-byte channel entries
R.w(0..1E) = tab[0..15]; R[20] = prio; R[21..23] = FC FD FE
```
If the device's track is missing, `tab` stays zero: the sound has no channels and ends at its first
tick.

### 5.7 `p_unlink(node)` (0b6a) / `p_stop_remap` (080c) — verified

`p_unlink`: find node in `list` (not found → return); shift the following entries up, last = 0;
`N[158] = FF; N[159] = 0`; digital: if `N[165] >= 80h` → `drv(15, AX = sample ptr)` (end sample).
`p_stop_remap` = `cli; p_unlink; p_remap`.

### 5.8 `p_remap()` (0c1e) — verified (model `Sequencer.remap`, rolled back per node)

Distributes the device channels `[ch_first, ch_last]` and the driver's voice budget over the
channels of the playing nodes, in list (priority) order, then updates the driver:

```
busy++; remap_flag = 0
new = t_entry = [FF]*16 ; t_locked = t_prio = t_voices = [0]*16 ; dig_list[0] = 0
if list[0] == 0: goto finish(new all FF)
r = list[0][15F]; if r == 7F: r = def_reverb; drv(11, CL = r)
al = voices
for idx in 0..15 while list[idx]:
    n = list[idx]; if n[164] (paused) or n[165] (digital): continue
    backup (t_entry, t_prio, t_voices, t_locked, al)
    for s in 0..15:
        c = n[8C+s]; if c in (FF, FE, 0F): continue
        if n[134+c] & 2 or n[143+c]: continue                     // fixed or muted: not mapped
        e  = idx<<4 | c
        ah = n[DA+c] & 0F                                          // voices wanted
        pr = n[DA+c] >> 4; ch = pr ? (16 - pr + 16*idx) & FF : 0   // priority value, 0 = must play
        dh = FF
        if n[134+c] & 1 and t_entry[c] == FF: dh = c               // locked: own number if free
        else:
            for d in 0..15:                                        // highest free channel in range
                if t_entry[d] == FF: if ch_first <= d <= ch_last: dh = d
                elif t_entry[d] == e: goto next_s                  // already mapped
            if dh == FF:
                if ch: break (rest of this node skipped, no rollback)
                steal → (dh, v) = channel with the largest t_prio (> 0); none → ROLLBACK
                al += v
        if ah > al:
            if ch: continue
            while ah > al: steal (as above; none → ROLLBACK); al += v
        t_entry[dh] = e; t_voices[dh] = ah; al -= ah; t_prio[dh] = ch
        if !(n[134+c] & 1): t_locked[dh] = 0; continue
        t_locked[dh] = 1
        if dh == c: continue
        if t_locked[c] == 0: swap entries dh and c in all four tables; continue
        if ch: free dh (t_entry FF, others 0); al += ah; continue
        if t_prio[c] == 0: ROLLBACK
        al += t_voices[c]; free dh; t_entry[c] = e; t_prio[c] = ch; t_voices[c] = ah; al -= ah
    ROLLBACK: restore the backup of this node (the node gets nothing), continue with the next node
// phase 2 (1258): keep what can be kept
for si in 0..15: if t_entry[si] != FF:
    e = t_entry[si]; n = list[e>>4]; c = e & 0F
    if t_locked[si]: t_entry[si] = FF; new[si] = e; if !(old_chan[si] == c && old_owner[si] == n): setup(si, n, c)
    else: for d in ch_first..ch_last:
              if old_owner[d] == n && old_chan[d] == c: if !t_locked[d]: new[d] = e; t_entry[si] = FF
                                                          break
// phase 3 (1402): the rest from the top free device channel downwards
di = ch_last + 1
for si in 0..15: if t_entry[si] != FF:
    bx = di - 1; while new[bx] != FF: bx--; di = bx; new[di] = t_entry[si]; setup(di, list[e>>4], e & 0F)
finish (1514):
for d in 15..0: if old_chan[d] != 0F && new[d] == FF: drv(7, d, 40h, 0); drv(7, d, 7Bh, 0); drv(7, d, 4Bh, 0)
map = new; old_chan[d] = new[d] & 0F; old_owner[d] = new[d] == FF ? 0 : list[new[d]>>4]
busy--
```
`setup(d, n, c)` (12b3 / 1441), in this order: `drv(7,d,7Bh,0)`, `drv(7,d,4Bh, n[DA+c]&0F)`,
`drv(8,d, n[116+c])`, `pend_vol[d] = FF`, `drv(7,d,7, scale_volume(n[107+c], n[15E]))`,
`drv(7,d,0Ah, n[F8+c])`, `drv(7,d,1, n[E9+c])`, `drv(7,d,40h, n.w(BC+2c) & 8000 ? 7F : 0)`,
`drv(10,d, lsb = w & 7F, msb = (w>>7) & 7F)`, `drv(7,d,4Eh, n[125+c])`.

Note `old_chan` is compared with 0Fh (not FFh) for "was free" — MIDI channel 15 is never mapped, so
this works. The steal search takes the **first** device channel with the strictly largest `t_prio`.

### 5.9 `player_service()` (17de, far, timer client) — verified

```
if busy: return
cli
if remap_flag: p_remap()
si = 0
while si < 16 and list[si]:
    n = list[si]
    if n[164] == 0:                                   // not paused
        if n[163]: p_fade_step(n); if n[158] == FF: continue     // fade ended with stop: same si again
        if n[165]: p_dig_check(n) else p_sequence(n, si)
        if n[158] == FF: continue                    // stopped: list shifted, same si again
    si++
p_dig_service()                                       // digital nodes: nothing on AdLib
p_send_pending_volumes()
drv(3)
```

### 5.10 `p_sequence(n, idx)` (1932) — verified (model `Sequencer.process` / `_events` / `_control`)

```
cur_tag = idx << 4; n.w(154)++
R = resource base (after 84 00)
for s in 0..15:
    c8 = n[8C+s]; if c8 == FF: break; if c8 == FE: continue
    cur_dev = FF; cur_fixed = 0
    if n[134+c8] & 2: cur_dev = c8; cur_fixed = 1
    else: find d with map[d] == ((c8 & 0F) | cur_tag) → cur_dev = d
    pos = n.w(0C+2s); if pos == 0: continue
    base = R.w(2s)
    if n.w(4C+2s):
        n.w(4C+2s)--
        if n.w(4C+2s) == 0x8000:                     // end of an F8 run: read the next delta byte
            d = R[base+pos]; n.w(0C+2s)++; n.w(4C+2s) = (d == F8) ? 0x80F0 : d
        continue
    loop (events of this tick):
        st = R[base + pos++]
        if st < 80: st = n[9C+s]; pos--               // running status
        else: n[9C+s] = st
        if st == FC: n.w(0C+2s) = 0; break            // channel end
        if (st & 0F) == 0F: ev_control(st & F0); if n.w(0C+2s) == 0: break
        else switch st & F0 (cc = c8 & 0F, dev = cur_dev):
            80: note, vel = 2 bytes; note_off
            90: note, vel; vel ? note_on : note_off
            A0: 2 bytes; if dev != FF && !seeking: drv(6, AL=dev, CH, CL)
            B0: ev_controller
            C0: ev_program
            D0: 1 byte; if dev != FF && !seeking: drv(9, …)
            E0: ev_pitch_bend
            F0: skip to F7 (sysex)
            default (cannot happen: status < 80 after running status 0): n.w(0C+2s) = 0; break
        d = R[base + pos++]
        if d == 0: continue loop                       // next event in the same tick
        n.w(4C+2s) = (d == F8) ? 0x80EF : d - 1; break
// end of sound (1b03)
if every slot with n[8C+s] != FF has n.w(0C+2s) == 0:
    if n[15A] == 0 && n[15D] == 0: p_unlink(n); remap_flag = 1
    else: n.w(154) = n.w(156); for s in 0..15: n.w(0C+2s) = n.w(2C+2s); n.w(4C+2s) = n.w(6C+2s); n[9C+s] = n[AC+s]
```
Delta encoding: the delay counts *remaining* ticks: a delta `d` (1–F7h) means the next event runs
`d` ticks later (stored `d−1` because the current tick already counts). `F8` = 240 ticks and read
another delta byte when they elapse (`80EFh` = bit 15 + 239; when the counter reaches exactly 8000h
the next delta byte is read and added the same way; `80F0h` when a run is started from the preamble
or a loop point, where the current tick does not count).

Event handlers (`dev` = `cur_dev`, `cc` = MIDI channel):
* `ev_note_off` (1b76) / `ev_note_on` (1bc8): `vel == 0` or `8n` → if `dev < 10h && n[125+cc] ==
  note: n[125+cc] = FF`; `if dev != FF && !seeking: drv(4, AL = dev & 0F, CH = note, CL = vel)`.
  Note on: `if dev < 10h: n[125+cc] = note`; `if dev != FF && !seeking: drv(5, …)`.
* `ev_controller` (1c73), `ctl, val`: if `cur_fixed && map[dev & 0F] != FF` → ignored (a fixed
  channel whose device channel is used by a remapped channel). Else by controller:
  7 → `n[107+cc] = val; val = scale_volume(val, n[15E]); if dev < 20h: pend_vol[dev] = FF else no
  send`; 0Ah → `n[F8+cc] = val`; 1 → `n[E9+cc] = val`; 40h → sustain bit 15 of `n.w(BC+2cc)`;
  4Bh → `n[DA+cc] = (n[DA+cc] & F0) | val; remap_flag = 1`; 4Eh → `n[143+cc] = (n[143+cc] & F0) |
  (val ? 1 : 0); remap_flag = 1`; then `if dev != FF && !seeking: drv(7, AL = dev & 0F, CH = ctl,
  CL = val)`.
* `ev_program` (1d72): same fixed test; `n[116+cc] = p; drv(8, dev, CL = p)`.
* `ev_pitch_bend` (1de8): same fixed test; `n.w(BC+2cc) = (msb<<7 | lsb) | (old & 8000h)`;
  `drv(10, AL = dev, CH = lsb, CL = msb)`.
* `ev_control` (1e66), status `?F` (control channel):
  * `CF 7F d` **loop point**: `n.w(4C+2s) = (d == F8) ? 80F0 : d; n[9C+s] = CF`; save all 16
    positions → 2C, delays → 6C, running statuses → AC; `n.w(156) = n.w(154)`; then
    `n.w(0C+2s)--; n.w(4C+2s) = 0` (the delta byte is re-read by the event loop).
  * `CF v` (v ≠ 7F): `if !seeking: n[158] = v` (**signal** to the game).
  * `BF 50 v` reverb: `if v == 7F: v = def_reverb; n[15F] = v; drv(11, CL = v)`.
  * `BF 60 x` cue: `if !seeking: n.w(152)++`.
  * `BF 52 v` hold point: `if n[15A] == v`: all 16 positions = 0 (the sound ends now; it restarts at
    the loop point if looping or holding, see end of sound).
  * `F0`: skip to `F7`; other `?F` statuses (`ev_skip_control` 1f78): skip 1 data byte for `CF`/`DF`,
    2 for the others.
* `scale_volume(v, nv)` (1fb5): `c = (((v+1) & FF) * ((nv+1) & FF)) >> 8 << 1` (8-bit); `c ? c−1 : 0`.
  7Fh·7Fh → 7Fh; `v+1` wraps for v = FF.

### 5.11 Fades and volumes — verified

* `p_fade(n, DL = target, CL = ticks, CH = step)` (087e): `cli; if n[15E] == DL: return` (the full
  byte is compared, so a fade *without* the stop bit to the current volume does nothing, while a
  stop-fade (bit 7) always starts); `n[160] = DL; n[161] = CL; n[163] = CH; n[162] = 0`.
* `p_fade_step(n)` (15fc, from the service):
  ```
  if n[162]: n[162]--; return
  n[162] = n[161]; t = n[160] & 7F; v = n[15E]
  if t < v: if v - t <= n[163]: set_node_volume(n, t, queue=1) else: set_node_volume(n, v - n[163], 1); return
  elif t > v: if t - v <= n[163]: set_node_volume(n, t, 1) else: set_node_volume(n, v + n[163], 1); return
  n[163] = 0
  if n[160] & 80: p_unlink(n); remap_flag = 1
  ```
  i.e. one step every `ticks+1` service ticks, the step that reaches the target ends the fade on the
  *next* step time (the target is reached, then one more interval passes before the stop).
* `p_set_node_volume(n, vol, queue)` (16b8): `if vol == n[15E]: return; n[15E] = vol; if n not in
  list: return;` for every device channel d with `map[d] >> 4 == index(n)`: `v = scale_volume(n[107
  + (map[d] & 0F)], vol)`; queued → `pend_vol[d] = v`, else `pend_vol[d] = FF; drv(7, d, 7, v)`. Then
  for every slot s (until FF) whose channel c has flag 2 (fixed) and `map[c] == FF`: same on device
  channel c.
* `p_volume(n, CL)` (090e) = `cli; p_find; p_set_node_volume(n, CL, queue = 0)`.
* `p_send_pending_volumes` (1796): starting at `vol_rr`, walk the 16 device channels round-robin,
  sending `drv(7, d, 7, pend_vol[d])` for entries ≠ FF (clearing them), at most **2 per tick**;
  `vol_rr` = the channel after the last one examined.

### 5.12 Other node operations — verified

* `p_pause(node, CL on)` (0816): `node == 0` → every listed node; `on`: `n[164]++` else `if n[164]:
  n[164]--`; then `p_remap()` (paused nodes release their channels; their state is kept).
* `p_hold(n, CL)` (08a2): `n[15A] = CL` (no cli).
* `p_mute_all(n, CX)` (08ac): `busy++`; for the 15 MIDI channels: CX ≠ 0 → high nibble of `n[143+c]`
  +1 (saturating at F), CX = 0 → −1 (saturating at 0); `p_remap(); busy--`.
* `p_set_priority(n, CL)` (091e): `cli; if n[15C] == CL: return; n[15C] = CL; si = p_find(n); if si
  == FF: return;` remove it from the list and re-insert it by priority (same rule as play); `p_remap`.
* `p_controller(n, CH = ctl, CL = val, DL = chan)` (0a1c), from the game: `cli; if not in list:
  return`; 7 → `n[107+chan] = val; val = scale_volume(val, n[15E])`; 0Ah → pan; 1 → modulation;
  40h → sustain bit; 4Eh → the **high** nibble (mute count) of `n[143+chan]` +10h if val ≠ 0 (up
  to F0h) or −10h if val = 0 (down to 0), then `p_remap()` and return without sending; **7Fh** →
  `n[116+chan] = val` (program change). Then if the channel is mapped (`map[d] == idx<<4 | chan`):
  7Fh → `drv(8, d, CL = val)`, else `drv(7, d, CH = ctl, CL = val)`. (The sequencer's own ctrl 4Eh
  sets the *low* nibble instead, §5.10.)
* `p_pitch_bend(n, CX = value14, DL = chan)` (0b04): stores `value | (sustain bit kept)` in
  `n.w(BC+2chan)`; if mapped: `drv(10, d, CH = value & 7F, CL = value >> 7)`.
* `p_restore(n)` (0433), "seek to the saved tick" (SCI `RestoreSound`): `cli`; save `n[143+c] & F0`
  for c 0–14; `seeking = 1`; `p_play(n, n[159])` (**Quirk**: 1 or 2 both play locked, since any
  non-zero CX locks); `target = n.w(154)` (play does not clear the counters while seeking, so this
  is the saved tick); `n.w(154) = 0`; save and force `n[15D] = 1`; loop: `old = n.w(154);
  p_sequence(n, DI)`; if the tick went back (loop restart) `target -= old − new`; until `n.w(154) ==
  target` (a sequence call that does not advance the tick ends the loop); restore `15D`; `seeking =
  0`; OR the saved mute nibbles back; `p_remap()` (which sends the full channel state). No caller in
  INTRO or PS (AP: §12).
* Digital: `p_dig_check` (1865) / `p_dig_service` (1893) use driver fns 14 (play sample: AX =
  sample, CL = volume, CH = loop), 16 (check: AL done, AH restarted), 15 (end). Never reached with
  AdLib (fn 0 returns digital = 0, so `FE` channels are disabled at play). Not ported.

---

## 6. The sound API

Dynamix C code, cdecl far. INTRO and PS are the same code (PS addresses from a full far-call scan of
PS.EXE, verified); AP's version is in §12.1. Selector convention for ids (`sel`): `> 0` a sound id;
`0` every record; `−1` music records (flags bit 0 set); `−2` effect records (bit 0 clear); `−3`
continue the previous iteration.

### 6.1 DGROUP globals

| INTRO | PS | Name | Meaning |
|---|---|---|---|
| DS:1F40 | DS:3964 | `snd_active` (u8) | driver + patch initialised |
| DS:1F41 | DS:3965 | `patch_no` (u16) | fn 0 AL |
| DS:1F43 | DS:3967 | `patch_block` (far) | temporary patch chunk |
| DS:1F47 | DS:396B | `rec_head` (far) | record list |
| DS:1F4B | DS:396F | `drv_no` (u16) | driver number (init FFFF; FFFE after a failure or shutdown) |
| DS:1F4D | DS:3971 | `snd_timer_owned` | `snd_init` installed the PIT timer |
| DS:1F4F | DS:3973 | `snd_timer_handle` | timer client handle of the service |
| DS:1F51 | DS:3975 | `sng_inf` (near ptr) | SNG `INF:` table (u8 loop, u8 prio per sound); 0 in INTRO/PS |
| DS:1F53 | DS:3977 | `drv_block` (far) | unpacked driver chunk |
| DS:1F57 | DS:397B | `snd_error` | 1 = allocation failed, 2 = load failed |
| DS:1F59 | — | | play id for driver 7Eh (unused) |
| DS:1F5B | DS:397F | `snd_disabled` | −4 (init) nothing disabled, −1 music off, −2 effects off, 0 both off |
| DS:1F5D | — | | ≠ 0: load whole resources (never set) |
| DS:1E90 | DS:38B4 | | `"SSM:000:"` patch tag buffer |
| DS:1E9A / 1EA3 / 1EA8 | DS:38BE / 38C7 / 38CC | | `"SND:INF:"`, `"DAT:"`, `"DAT:"` |
| DS:1EAE | DS:38D2 | `vol_curve[64]` | 00 05 0A 0D 10 13 16 19 1C 1F 22 25 28 2B 2E 2F 32 35 38 3B 3D 3F 41 43 44 46 48 4A 4C 4E 50 52 54 56 58 5A 5C 5E 62 64 65 … 7B 7D |
| DS:1EF0 | DS:3914 | | `"SSM:     "` driver tag buffer |
| DS:1EFA | DS:391E | `drv_code[10]` | → `STD: TAN: ADL: M32: SBL: PS1: TAN: PRO: NLD: MTB:` |
| DS:33CE/33D0/33D2 | DS:76AA/76AC/76AE | | iterator state (current record far, selector) |
| DS:33D4 | DS:76B0 | | shutdown wait counter |
| DS:33D6[7] | DS:76B2[7] | `pool` | effect nodes |

### 6.2 Functions

| INTRO | PS | Name | Signature |
|---|---|---|---|
| 157f:0009 | 4516:000a | `snd_rec_load` | `int (FILE *f)` |
| 1593:0004 | 452a:0005 | **`snd_init`** | `int (int drv, char *ovl)` |
| 159b:0006 | 4532:0007 | `snd_rec_iter` | `Rec far *(int sel)` |
| 15a9:0005 | 4540:0006 | `snd_pool_free` | `int (void)` |
| 15ac:000c | 4543:000d | `snd_node_new` | `Node far *(void far *res)` |
| 15b5:0001 | 454c:0002 | `snd_res_read` | `void far *(FILE *f, u32 size, u32 *len, int cls)` |
| 15b5:01fa | 454c:01fb | `chlist_free` | `void (Ch far *)` |
| 15b5:023d | 454c:023e | `res_find_track` | `int (FILE *f, u8 dev)` |
| 15b5:033e | 454c:033f | `chlist_read` | `Ch far *(FILE *f)` |
| 15b5:0422 | 454c:0423 | `chlist_insert` | `Ch far *(Ch far *list, Ch far *item)` |
| 15b5:04ce | 454c:04cf | `res_build` | `int (FILE *f, Ch far *l, u8 far *dst, u16 size, u16 hdr, u8 dev)` |
| 1610:0005 | 45a7:0006 | `snd_pool_alloc` | `int (void)` |
| 1617:000b | 45ae:000c | `snd_pool_find` | `Node far *(void far *res)` |
| 161d:0005 | 45b4:0006 | `snd_hold` | `int (int sel, int v)` |
| 1620:000e | 45b7:000f | `ovl_load_chunk` | `void far *(char *name, char *tag, int cls)` |
| 1629:0009 | 45c0:000a | `snd_id_node` | `Node far *(int sel)` |
| 1629:007d | 45c0:007e | `snd_rec_node` | `Node far *(Rec far *)` |
| 1633:000a | 45ca:000b | `snd_master_volume` | `int (int v)` |
| 1634:000d | 45cb:000e | `snd_free` | `void (void far *, int cls)` |
| 1637:000a | 45ce:000b | `snd_priority` | `int (int sel, int p)` |
| 163b:0003 | 45d2:0004 | `snd_reverb` | `int (int v)` |
| 163c:0006 | 45d3:0007 | `snd_load_patch` | `int (char *ovl, int *patch_no, int noload)` |
| 164d:0006 | 45e4:0007 | **`snd_disable`** | `int (int cls)` |
| 1659:000b | 45f0:000c | **`snd_load_resource`** | `int (char *file, int id)` |
| 1672:000b | 4609:000c | **`snd_unload`** | `int (int sel)` |
| 1686:0004 | 461d:0005 | **`snd_shutdown`** | `void (void)` |
| 168b:0002 | 4622:0003 | `snd_pool_stop_all` | `void (void)` |
| 168d:000f | 4625:0000 | `snd_pause` | `int (int sel)` |
| 1693:0005 | 462a:0006 | `snd_resume` | `int (int sel)` |
| 1698:000a | 462f:000b | `snd_volume` | `int (int sel, int v)` |
| 16a0:0003 | 4637:0004 | `snd_controller` | `int (int sel, int ctl, int val, int chan)` |
| 16a4:0002 | 463b:0003 | `snd_fade` | `int (int sel, int target, int ticks)` |
| 16ac:000b | 4643:000c | `snd_load_driver` | `int (int n, char *ovl)` |
| 16b6:0001 | 464d:0002 | **`snd_play`** | `int (int id)` |
| 16d5:0001 | 466c:0002 | `snd_driver_close` | `void (void)` |
| 16d5:0054 | 466c:0055 | `snd_wait_5` | `void (void)` |
| 16d5:008d | 466c:008e | `snd_wait_tick` (timer client) | `void (void)`: `DS:33D4--` |
| 16de:0002 | 4675:0003 | **`snd_enable`** | `int (int cls)` |
| 16e6:000f | 467e:0000 | **`snd_stop`** | `int (int sel)` |
| 1700:000f | 4698:0000 | `res_skip_header` | `void far *(void far *p)` = `p + 2 + p[1]` |
| 1702:000a | 4699:000b | `node_stop_nth` | `void (Node far *, int n)` |
| 1705:0008 | 469c:0009 | `node_nth` | `Node far *(Node far *, int n)` (follows `+172` n times) |
| 1708:0008 | 469f:0009 | `node_play_nth` | `Node far *(Node far *, int n, u8 vol)` |
| 170c:000f | 46a4:0000 | `snd_pool_stop_data` | `void (void far *res)` |
| 1712:0002 | 46a9:0003 | `snd_pitch_bend` | `int (int sel, int value, int chan)` |
| 1715:000e | 46ac:000f | `snd_pool_play` | `Node far *(void far *res, int vol, u8 loop)` |
| 1724:0000 | 46bb:0001 | `snd_alloc` | `void far *(u32 size, int cls)` |
| 172c:000e | 46c3:000f | `snd_read_all` | `void far *(FILE *f, u32 size, u32 *len, int cls)` |

(PS `46d0:*` is not sound: it is the "DEMO"/shape module, AP `2edf`.)

### 6.3 Loading

* `snd_load_resource(file, id)` (1659:000b): `id > 0` and `snd_rec_iter(id)` finds it → 1. Open the
  volume file if needed. `id > 0`: open chunk `SND:INF:`, skip 2 (version), read u16 n, read ids until
  `id` is found (index k) → open the k-th `DAT:` chunk → `snd_rec_load`. `id == 0`: every `DAT:`
  chunk → `snd_rec_load` each. Returns 1 if something was loaded (INTRO: result of the last load).
* `snd_rec_load(f)` (157f:0009): read u16 id; already loaded → 1. `rec = snd_alloc(14h, 3)`; `+0A =
  id`; `+0C = u8 prio`; `+12 = u8 flags`; `cls = flags & 1 ? 4 : 7`; `rec+4 = snd_res_read(f,
  chunk_remaining − 4, &len, cls)`; failure → free the record, 0. Else `+8 = len`, link at the head.
* `snd_res_read(f, size, &len, cls)` (15b5:0001): for classes 4/7 (and `DS:1F5D` = 0) builds a
  **device-filtered copy**: opens the decompression stream over the packed data, `res_find_track`
  (checks the `84` header byte, skips byte 1, walks the track list until the device byte equals the
  play id of `drv_no` (§7.1); tracks' channel lists are skipped 6 bytes at a time), `chlist_read`
  (list of `{u16 off, u16 size}` sorted by offset), then allocates `hdr + Σ sizes + 1` with `hdr =
  5 + 6·n` rounded up to even and **at least 26h**, and `res_build` writes `84 00 dev`, per channel
  `00 00 u16 newoff u16 size` (newoff relative to byte 2), `FF FF`, then each channel's data (stream
  seek to old offset + 2, read size). The 26h minimum leaves room for the in-place header rewrite of
  `p_prepare` (24h bytes). Track missing / read error → `DS:1F57 = 2`, 0. Other classes →
  `snd_read_all` (whole chunk).
* `snd_alloc(size, cls)` (1724:0000): classes 6/8 near `malloc`, others DOS far alloc (`05da:35e0`);
  classes 2, 3, 4, 7 zero-filled; failure → `DS:1F57 = 1`. `snd_free(p, cls)` matches.
  Classes: 1 driver/patch/OVL chunk, 2 node, 3 record, 4 music data, 7 effect data, 9 channel list.
* `snd_unload(sel)` (1672:000b): `sel` 0 or −2 → `snd_pool_stop_all` first. For every matching
  record (0 all, id, −1 music, −2 effects): `snd_stop(id)`, unlink, free data (class 4/7), free the
  record (3). `sel > 0` returns after the first match (1), else 0.

### 6.4 Playing and stopping

```
int snd_play(int id)                                   // 16b6:0001
    rec = find id; if !rec: return 0
    if rec.flags & 10h || !rec.data || rec.node: return 1          // pending, no data, or music already playing
    if rec.flags & 1:                                              // music
        for r in records: if r.flags & 1 && r.node && r.id != id: snd_stop(r.id)   // one music at a time
        if disabled == 0 || disabled == -1: rec.flags |= 10h; return 1
        rec.node = snd_node_new(rec.data); if !rec.node: return 0
        node[15D] = rec.flags & 2 ? 1 : 0; node[15C] = rec.prio
        return node_play_nth(rec.node, 0, 7Fh) != 0                // node[15E] = 7F; player play(node, 1): locked channels
    else:                                                          // effect
        if snd_pool_find(rec.data): return 1                       // already playing: no restart
        if disabled == 0 || disabled == -2: if rec.flags & 2: rec.flags |= 10h; return 1
        snd_pool_play(rec.data, 7Fh, rec.flags & 2 ? 1 : 0); return 1
Node *snd_pool_play(res, vol, loop)                    // 1715:000e
    first pool node with [158] == FF (none → 0)
    node[166] = res; node[16A] = res_skip_header(res)
    if sng_inf: node[15D] = sng_inf[2·idx]; node[15C] = sng_inf[2·idx+1]; node[15E] = 7F      // AP (idx = the vol argument there, §12)
    else: node[15D] = loop; node[15C] = 1; node[15E] = vol
    player play(node, 0)                                           // remapped channels
    return node
int snd_stop(int sel)                                  // 16e6:000f
    sel > 0: rec = find; if !rec: return 0; rec.flags &= ~10h
             music: if rec.node: node_stop_nth(rec.node, 0); while rec.node[158] != FF: ;   // immediate (under cli)
                                 snd_free(rec.node, 2); rec.node = 0
             effect: snd_pool_stop_data(rec.data)                  // the pool node with [166] == data: stop, [158] = FF
             return 1
    sel == -1 or 0: for music records: clear 10h; the first one with a node is stopped and freed (as above)
             if sel == -1: return 1
    sel == -2 or 0: for effect records: clear 10h; snd_pool_stop_all()   // stop every pool node with [158] != FF, set FF
    return 1
```
Consequences: effects play at priority 1 on remapped channels, music at the bank priority (7) on
locked channels, so music always gets its channels first and effects take what is left of the 16
device channels and 9 AdLib voices. The iterator is global: `snd_stop` called from inside an
iteration (from `snd_play` or `snd_enable`) resets it (Quirk; harmless with one music record
pending).

### 6.5 Classes on/off

```
int snd_disable(int cls)                               // 164d:0006, cls 0 all, -1 music, -2 effects
    if cls > 0: return 0
    old = disabled
    if cls != -1: snd_stop(-2)                                     // effects stop at once
    if disabled == -4 || cls == 0: disabled = cls else if cls != disabled: disabled = 0
    if old != disabled:
        for r in records of cls: if snd_rec_node(r): snd_stop(r.id); if r.flags & 3: r.flags |= 10h   // resume later
    return 1
int snd_enable(int cls)                                // 16de:0002
    if cls > 0: return 0
    if cls == 0 || cls == disabled: disabled = -4
    else if disabled == 0: disabled = (cls == -1) ? -2 : -1
    for r in records of cls: if r.flags & 10h: r.flags &= ~10h; snd_play(r.id)
    return 1
```
(For effects, `snd_disable(-2)` stops them before the loop, so only looping effects that were
already marked stay pending.)

### 6.6 Per-sound wrappers (all: `for node = snd_id_node(sel); node; node = snd_id_node(-3)`, return 1 / 0 if none)

`snd_id_node(sel)` (1629:0009): records via the iterator; `snd_rec_node(rec)` = music → `rec.node`,
effect → `snd_pool_find(rec.data)`. For `sel > 0` only the first match.

| Wrapper | Player call per node |
|---|---|
| `snd_pause(sel)` / `snd_resume(sel)` | `snd_node_pause(node, 1 / 0)` |
| `snd_volume(sel, v)` | `v` clamped to 0–63 → `snd_node_volume(node, vol_curve[v])` (not queued) |
| `snd_fade(sel, target, ticks)` | `step = (target − node[15E]) / ticks` (signed int division); `step = step ? |step| : 1`; `snd_node_fade(node, target, 1, step)` — one step every 2 service ticks (`p_fade_step` waits `ticks+1`) |
| `snd_priority(sel, p)` | `snd_node_set_priority(node, p)` |
| `snd_hold(sel, v)` | `snd_node_hold(node, v)` |
| `snd_controller(sel, ctl, val, chan)` | `snd_node_controller(node, ctl, val, chan)` |
| `snd_pitch_bend(sel, value, chan)` | `snd_node_pitch_bend(node, value, chan)` |
| `snd_master_volume(v)`, `snd_reverb(v)` | `snd_master_volume(v)`, `snd_default_reverb(v)` (no node) |

Note: `snd_fade` passes **ticks-per-step = 1**, so the INTACE5 fade
(`step 2`) moves 2 volume units every 2 ticks: 127 → 0 in 64 steps ≈ 128 ticks ≈ **2.2 s**.

### 6.7 Init and shutdown

```
int snd_init(int drv, char *ovl)                       // 1593:0004
    if snd_active: return 1
    notimer = (drv == -1); if notimer: drv = 4
    if !snd_load_driver(drv, ovl): return 0
    if !notimer && !timer_installed (INTRO DS:15BE, PS DS:2E3E): timer_install(13); snd_timer_owned = 1
    if !notimer: snd_timer_handle = timer_add(player_service, 4); if !handle: return 0
    snd_pool_alloc(); return 1                                     // 7 nodes: [158] = FF, [8] = &node[16A]
void snd_shutdown(void)                                // 1686:0004
    if !snd_active: return
    snd_unload(0)
    if snd_timer_handle: timer_remove(handle); handle = 0
    if snd_timer_owned: timer_restore(); snd_timer_owned = 0
    snd_pool_free(); snd_driver_close()                            // PS also sets drv_no = FFFE
void snd_driver_close(void)                            // 16d5:0001
    if snd_active: player_terminate()                              // fn 12 (15), fn 2 (chip reset)
    if !snd_timer_handle: player_service(); player_service()      // always this branch from snd_shutdown
    else: snd_wait_5()                                             // timer client counting DS:33D4 from 5
    snd_active = 0; snd_free(drv_block, 1); drv_block = 0
```

Timer functions (platform): `timer_add` INTRO `05da:2307` / PS `16e3:291b`, `timer_remove` `05da:2351`
/ `16e3:2965`, `timer_install` `05da:2374` / `16e3:2988`, `timer_restore` `05da:23e1` / `16e3:29f5`,
ISR `05da:241a` / `16e3:2a2e`. PS also registers `229e:0013` at rate 1 (a 32-bit 236.7 Hz tick
counter `DS:1CC8`, not sound).

---

## 7. Driver loading, driver numbers, `-s<num>`, the loose `*.DRV` files

### 7.1 Driver numbers (verified)

The driver number is an index into `drv_code[10]` (INTRO `DS:1EFA`, PS `DS:391E`, AP see §6.1):

| n | chunk | device | play id (loader `snd_res_read`) | port |
|---|---|---|---|---|
| 0 | `SSM:STD:` | PC speaker ("stddrv") | 12h | parked |
| 1 | `SSM:TAN:` | Tandy 3-voice ("tnddrv") | 13h | parked |
| **2** | **`SSM:ADL:`** | **AdLib** ("dude") | **00h** | **implemented** |
| 3 | `SSM:M32:` | MT-32 / LAPC-I / CM-32L | 0Ch | parked |
| 4 | `SSM:SBL:` | (Sound Blaster: chunk absent) | 00h | mapped to 2 by INTRO `sys_init` / PS `sys_init` |
| 5 | `SSM:PS1:` | IBM PS/1 ("audjoy") | 13h | parked |
| 6 | `SSM:TAN:` | Tandy again | 13h | parked |
| 7 | `SSM:PRO:` | (Pro Audio: chunk absent) | 00h | mapped to 2 by INTRO `sys_init` |
| 8 (as 88h) | `SSM:NLD:` | MT-32 "no-load" (patches not uploaded) | — | parked; PS uses it for driver 3 when chained (§11.1) |
| 9 | `SSM:MTB:` | (absent) | — | — |
| 7Eh | — | loader uses `DS:1F59` as play id | — | unused |

The play-id column is the device byte `snd_res_read` (`15b5:0001`, switch at `15b5:004d` with the
table `cs:01f2`) keeps when a sound is loaded; the driver itself reports its play id in CH of fn 0
(AdLib 00h) and the player's `prepare` searches for that one. Both agree for AdLib.

Names in `RESOURCE.CFG` → numbers (INTRO table `DS:00CF`, 8 × `{char *name, int n}`, matched with
`strstr` against the `soundDrv` value, first hit wins): `ADL` 2, `IBMPS1` 5, `MT32` 3, `PROAUDIO` 7,
`SNDBLAST` 4, `STD` 0, `TANDY3V` 1. INTRO's `config_read` (`038e:0284`, platform spec) stores the
result in `DS:24B3`, which is word +2 of the CONTROL.PRF record `DS:24B1` (0x25 bytes, read by
`038e:0181`); PS reads CONTROL.PRF only (`DS:43B2`), never `RESOURCE.CFG`.

### 7.2 `-s<num>` (verified)

INTRO `main` (`038e:0ac1`, option table `cs:0cf1` = `? h p s`, handlers `cs:0cf9`): `-s<num>` →
`DS:24B3 = atoi(arg + 2)` (`038e:0bd1`), parsed after CONTROL.PRF/RESOURCE.CFG, so it overrides them
for this run. PS `main` has the same option (`048e:036b`: `DS:43B2 = atoi(argv + 2)`). The usage text
(`DS:063e`): "`-s<num>    select sound driver`". Values: §7.1 (4 and 7 become 2; 3 in PS becomes 88h
when chained). `-s` in AP: see §12.

### 7.3 `snd_load_driver(n, ovl)` (INTRO `16ac:000b`, PS `4643:000c`) — verified

```
strcpy(DS:1EF4, drv_code[n & 7F])               // builds "SSM:ADL:" in the buffer DS:1EF0
drv_block (DS:1F53) = ovl_load_chunk(ovl, "SSM:xxx:", class 0)   // unpacked, called in place
if !drv_block: goto fail
patch_no (DS:1F41) = player_attach(drv_block) & FF
active (DS:1F40) = snd_load_patch(ovl, &patch_no, (n & FF80) ? -1 : 0)
if n == 88h: n = 3
drv_no (DS:1F4B) = active ? n : FFFE
return active
```
`snd_load_patch(ovl, &p, noload)` (INTRO `163c:0006`, PS `45d3:0007`): if `noload == -1` or `p ==
FF`: `return player_init(NULL) != FFFF`. Else builds `"SSM:%03d:"` in `DS:1E90` (three decimal digits
of p, `p/100`, `p/10%10`, `p%10`), frees a previous patch block (`DS:1F43`), loads the chunk
(class 0), calls `player_init(res_skip_header(block))` (skips `89 n desc`, i.e. `p + 2 + p[1]`),
frees the block and clears `DS:1F43`; returns `init != FFFF`. AdLib: patch 3 → `SSM:003:` (2690
bytes: 2 + 12 description + 2688 bank... see §8.4).

`ovl_load_chunk(name, tag, class)` (INTRO `1620:000e`, PS `45b7:000f`): opens the volume file if it
is not already open (`05da:5c7a` / `05da:589e`), finds the chunk (`05da:5934`), reads and unpacks it
whole via `snd_res_read(file, size, NULL, class 1)` → `snd_read_all` (`172c:000e`: decompression
stream `05da:6b6c`, length `05da:702d`, `snd_alloc`, read `05da:6f3d`, close `05da:6db5`), closes
the file if it opened it. Platform owns the volume/stream functions.

### 7.4 The loose `*.DRV` files (verified: unused)

`Game/ADL.DRV`, `MT32.DRV`, `STD.DRV`, `IBMPS1.DRV` are never opened by INTRO, PS or AP: the only
`.DRV` string in INTRO and PS is the `soundDrv = <name>.DRV` line written by `config_write` (INTRO
`038e:04d6`, PS `1193:0ad2`, which has no callers); AP has no `.DRV` string at all; every driver is
loaded as an `SSM:` chunk of `SXCODE.OVL` (INTRO, PS) or `SX.OVL`/`SX1.OVL` (AP). `INSTALL.SCR` copies
`*.drv` to the game directory: they are for the installer (its sound test). `ADL.DRV` is also a
different build (v2.24, 9295 bytes: fn 1 takes a length-prefixed patch, returns last channel 8, fn 3
is a `ret`, voice allocation by free-voice queue). The port ignores them.

### 7.5 What the shipped configuration selects

`Game/CONTROL.PRF` word +2 = 3 (MT-32) and `RESOURCE.CFG` `soundDrv = MT32.DRV` in this eXoDOS copy;
the port selects AdLib (2) regardless until MT-32 is implemented (§13).

---

## 8. The AdLib driver `SSM:ADL:` (verified; model `aotpsnd.AdlibDriver`)

Identical in `SXCODE.OVL`, `SX.OVL` and `SX1.OVL` (8070 bytes, `work/ovl/*_OVL_ADL.bin`). Real-mode,
position independent (all data `cs:`-relative), called in place. Offsets below are driver offsets.
The port reads the image from the OVL at run time and keeps the state in a copy of it (the model
does this; out-of-range table reads then behave like the original).

### 8.1 Header, entry, calling convention

```
+00 E9 3A 14      jmp 143D (entry)           +04 21 43 65 87  signature 87654321h   +08 01 (type: sound)
+09 04 "dude"     +0E 1C "AdLib Music Synthesizer Card"      +2B 98 BA DC FE  +2F 02 00 00 00
+33 u16 388h index port   +35 u16 388h status port   +37 u16 389h data port
```
Entry `143D`: `push bp; pushf; push bp si di bx dx ds es; call [cs:1419 + 2·BP]; pop …; popf; pop
bp; retf`. Registers AX, CX (and ES for fn 1) are the arguments and results; flags are restored.

| BP | Routine | Name | In | Out |
|---|---|---|---|---|
| 0 | 1f7d | PatchReq | — | AH = 1, AL = 3 (patch `SSM:003:`), CH = 0 (play id), CL = 9 (voices) |
| 1 | 1f2e | Init | ES:AX = patch (after its `89 n desc` header) | AX = 0, CL = 0, CH = 15 (first/last device channel) |
| 2 | 15d6 | Terminate | — | chip reset (`1e6b`) |
| 3 | 188f | Service | — | ages of sounding voices +1 |
| 4 | 145a | NoteOff | AL ch, CH note, CL vel | |
| 5 | 1490 | NoteOn | AL ch, CH note, CL vel | |
| 6 | 1459 | PolyAT | | `ret` |
| 7 | 14d8 | Controller | AL ch, CH ctl, CL val | 7, 0Ah, 40h, 4Bh, 7Bh handled; others ignored (1, 4Eh…) |
| 8 | 1522 | Program | AL ch, CL prog | |
| 9 | 1459 | ChannelAT | | `ret` |
| 10 | 1530 | PitchBend | AL ch, CH lsb, CL msb | |
| 11 | 15c5 | Reverb | CL (FF = query) | AL = old; stored only (`06B0`) |
| 12 | 1595 | MasterVolume | CL 0–15 (FF = query) | AL = old |
| 13 | 1565 | SoundOn | CL 0/1 (FF = query) | AL = old |
| 14–16 | 1459 | sample play/end/check | | `ret` |
| 17 | 1eb1 | AskDriver | AH = E0h/C0h/B0h, AL = ch, CH = ctl, CL | AX = bend / program / volume, pan, hold, owed voices; `B0 4B` with CL = FF: number of voices owned; else FFFF. No caller in the player |

Hardware: `opl_write(reg BX, val CX)` (`1b13`): `out [33],reg`; 5 × `in [33]`; `out [37],val`; 35 ×
`in [35]` (delays). No OPL detection anywhere (fn 1 writes blindly). **Port**: `opl_write` =
`OPL3_WriteReg(chip, reg, val)` (Nuked, OPL2 mode, register set 0); the delays are dropped.

### 8.2 Data (driver offsets; initial values from the image)

| Off | Size | Contents |
|---|---|---|
| 0039 | u8[508] | block per index (index = note·4 ± bend quarter-tones): 0 for 0–95, then +1 every 48 (… 7 at 432–479; 9 at 480+) |
| 0236 | u16[508] | F-number per index: 157h,15Ch,161h,166h,… (4 steps per semitone, repeating per octave) |
| 0630 | u8[64] | velocity curve (index vel/2): 00 0C 0D 0E 0F 11 12 13 14 16 17 18 1A 1B 1C 1D 1F 20 … 3F |
| 0670 | u8[64] | volume curve: 00 14 15 16 17 18 19 1A … 3F |
| 06B0 / 06B1 / 06B2 | u8 | reverb (0), sound on (1), master volume (15) |
| 06B3 | u8[16] | per channel: program (0) |
| 06C3 | u8[16] | volume/2 (3Fh) |
| 06D3 | u8[16] | pan (40h) |
| 06E3 | u8[16] | hold pedal (0) |
| 06F3 | u8[16] | voices still owed (0) |
| 0703 | u16[16] | pitch bend (2000h) |
| 0723 | u8[16] | last voice used by the channel (0) |
| 0733 | u8[9] | voice owner channel (FF free) |
| 073E | u8[9] | voice note (FF silent) |
| 0749 | u8[9] | voice velocity/2 |
| 0754 | u8[9] | voice sustained by the hold pedal |
| 075F | u16[9] | voice age in ticks |
| 0775 | u8[9] | instrument loaded in the voice (FF none) |
| 0780 | u8[9] | voice → carrier operator: 3 4 5 9 A B F 10 11 |
| 0789 | u8[9] | voice → modulator operator: 0 1 2 6 7 8 C D E |
| 0792 | u8[18] | operator is carrier: 0 0 0 1 1 1 0 0 0 1 1 1 0 0 0 1 1 1 |
| 07A4 | u8[18] | operator → register offset: 0 1 2 3 4 5 8 9 A B C D 10 11 12 13 14 15 |
| 07B6 | u8[18] | operator → OPL channel: 0 1 2 0 1 2 3 4 5 3 4 5 6 7 8 6 7 8 |
| 07C8 | u8[18] | voice → (modulator, carrier) pairs: 0 3 1 4 2 5 6 9 7 A 8 B C F D 10 E 11 |
| 07DA / 07E8 | u8[13] | reset parameters, modulator (01 01 03 0F 05 00 01 03 0F 00 00 00 01) / carrier (00 01 01 0F 07 00 02 04 00 00 00 01 00) |
| 07F6 | 18 × 14 | operator shadow: 13 params + waveform (stride 14) |
| 08F2 | 96 × 28 | patch bank (§8.4) |
| 1372 | u8[13] | reset work copy |
| 1380–1384 | u8 | 08h note-select flag, BDh bits 7/6 (AM/VIB depth), rhythm flag (`1383`), BDh low bits (`1384`) — all 0 |
| 1385 | u16 | waveform-select enabled (0 until reset ends, then 20h) |
| 138A | u16[9] | per voice: carrier KSL |
| 13A0 | u16[9] | 63 − carrier TL |
| 13B6 | u16[9] | (63 − carrier TL) / 15 (unused) |
| 13CC | u16[9] | modulator KSL |
| 13E2 | u16[9] | 63 − modulator TL |
| 13F8 | u8[9] | modulator scaled by volume (1 = additive instrument) |
| 1403 | u16[9] | (63 − modulator TL)/15 (unused; overlaps the next bytes) |
| 1419 | u16[18] | function table |

### 8.3 Routines

```
fn1 init (1f2e):     copy 0x540 bytes ES:AX → 08F2; if next word (big-endian read: first byte high) == ABCDh: copy 0x540 more → 08F2+540
                     reset(); master_volume(15); AX = 0, CL = 0, CH = 15
fn2 terminate (15d6): reset()
fn3 service (188f):  for v 0..8: if note[v] != FF: age[v]++
fn4 note_off (145a): v = first voice with owner == ch && note == n; none → return
                     if hold[ch]: sustained[v] = 1 else voice_off(v)
fn5 note_on (1490):  if vel == 0: note_off; return
                     if n < 12 || n > 107: return
                     vel >>= 1
                     v = voice with owner == ch && note == n → voice_off(v); voice_on(v, n, vel); return
                     v = alloc(ch); if v != FF: voice_on(v, n, vel)          // else: dropped
fn7 controller (14d8): 7 → vol[ch] = val>>1; update(ch)       0Ah → pan[ch] = val; update(ch)
                     40h → hold[ch] = val; if val == 0: every voice of ch with sustained → voice_off
                     4Bh → voice_map(ch, val)                   7Bh → every sounding voice of ch → voice_off
                     update(ch) = every voice of ch with note != FF: set_note(v, note[v], keyon=1)
fn8 program (1522):  prog[ch] = CL                            (applied at the next note on)
fn10 pitch_bend (1530): bend[ch] = msb<<7 | lsb; every voice owned by ch (sounding or not): set_note(v, note[v], 1)
                     // Quirk: a silent voice (note FF) gets set_note with note FF: index = FF·4 = 3FC ≥ 1FC → nothing written, but note[v] = FF kept
fn11 reverb (15c5):  old = 06B0; if CL != FF: 06B0 = CL
fn12 master (1595):  old = 06B2; if CL != FF: 06B2 = CL; every sounding voice: set_note(v, note, 1)
fn13 sound_on (1565): old = 06B1; if CL != FF: 06B1 = CL; every sounding voice: set_note(v, note, 1)
fn17 ask (1eb1):     E0: bend[ch]; C0: prog[ch]; B0 + CH 7/0A/40: vol/pan/hold; B0 4B: CL==FF ? count(owner==ch) : owed[ch]

alloc(ch) (15da):     start after last[ch], scan 9 voices cyclically (v = last+1 … last):
                        owner[v] == ch && note[v] == FF → last[ch] = v; return v
                        owner[v] == ch: if age[v] >= best: best = age[v]; cand = v    // last one wins ties
                      if best == 0: return FF        // every voice of the channel started this tick: note dropped (Quirk)
                      voice_off(cand); last[ch] = cand; return cand
voice_on(v, n, vel) (17f9): age[v] = 0; p = prog[owner[v]]
                      if p != instr[v] && sound_on: instr[v] = p; load_patch(v, 08F2 + 28·p)
                      velo[v] = vel; set_note(v, n, 1)
voice_off(v) (1865):  sustained[v] = 0; set_note(v, note[v], 0); note[v] = FF; age[v] = 0
set_note(v, n, key) (18ab):
    note[v] = n; ch = owner[v]
    i = bend_index(ch, n*4); if i == FFFF: return
    opl_write(A0+v, fnum[i] & FF); opl_write(B0+v, (key<<5 | block[i]<<2 | fnum[i]>>8) & FF)
    x = ((vol[ch] + 1) * (velcurve[velo[v]] + 1)) >> 6          // 8-bit operands, 16-bit product
    x = ((x & FF) * ((master + 1) & FF)) >> 4; x &= FF
    if x: x--; if !sound_on: x = 0
    set_volume(v, x)
bend_index(ch, i) (1958):
    b = bend[ch]; d = |b - 2000h| / 0AAh (16-bit div, quotient & FF); i = b > 2000h ? i + d : i - d
    return i < 1FCh ? i : FFFF
set_volume(v, x) (19b2):
    a = volcurve[x]                                   // 0..3F
    q = (a * (u8)13A0[v]) / 63                        // 8-bit mul, 8-bit div
    opl_write(40 + regoff[car[v]], ((63 - q) | (138A[v] << 6)) & FF)         // TL = 63 - a·(63 - patchTL)/63, KSL kept
    if 13F8[v]: q = (a * (u8)13E2[v]) / 63
                opl_write(40 + regoff[mod[v]], ((63 - q) | (13CC[v] << 6)) & FF)
load_patch(v, p) (1a4e):          // p = 28-byte instrument: mod[13], car[13], mod wave, car wave
    13F8[v] = 1
    if p[0C] (modulator ALG = FM): 13F8[v] = 0
    else: 13CC[v] = p[0]; 13E2[v] = 63 - p[8]; 1403[v] = (63 - p[8]) / 15
    138A[v] = p[0D]; 13A0[v] = 63 - p[15h]; 13B6[v] = (63 - p[15h]) / 15
    write_op(pairs[2v], p, p[1A]); write_op(pairs[2v+1], p + 0D, p[1B])
write_op(op, p, wave) (1c20 → 1c69):
    shadow[op][0..12] = p[0..12]; shadow[op][13] = wave & 3; r = regoff[op]
    opl_write(BD, (1381 ? 80 : 0) | (1382 ? 40 : 0) | 1384)          // 1bcf, every time
    opl_write(08, 1380 ? 40 : 0)                                         // 1cca
    opl_write(40 + r, (KSL<<6 | TL & 3F))                                // 1c82
    if !is_carrier[op]: opl_write(C0 + opch[op], (FB<<1 | (ALG == 0 ? 1 : 0)) & 0F)   // 1ce2
    opl_write(60 + r, AR<<4 | DR & 0F); opl_write(80 + r, SL<<4 | RR & 0F)
    opl_write(20 + r, (AM?80:0)|(VIB?40:0)|(EG?20:0)|(KSR?10:0)|MULT & 0F)
    if 1385: opl_write(E0 + r, wave)
    // operator bytes: 0 KSL, 1 MULT, 2 FB, 3 AR, 4 SL, 5 EG, 6 DR, 7 RR, 8 TL, 9 AM, 10 VIB, 11 KSR, 12 ALG
reset() (1e6b):
    opl_write(01, 0); 1383 = 0; 1384 = 0
    for op 0..17: 1372[0..12] = is_carrier[op] ? 07E8 : 07DA; write_op(op, 1372, 0)     // 1b53
    write_bd(); 1381 = 1382 = 1380 = 0; write_bd(); opl_write(08, 0)
    for v 0..8: opl_write(A0+v, 0); opl_write(B0+v, 0)                                  // 1afb
    1385 = 20h; for op 0..17: opl_write(E0 + regoff[op], 0); opl_write(01, 20h)          // 1b90(1)
voice_map(ch, n) (1641, ctrl 4Bh):
    have = count(owner == ch) + owed[ch]
    if have == n: return
    if have < n: assign(ch, n - have)
    else: release(ch, have - n); redistribute()
assign(ch, k) (16d4): for v 0..8 while k: if owner[v] == FF: owner[v] = ch; k--
                      owed[ch] += k
release(ch, k) (16ff): if owed[ch] >= k: owed[ch] -= k; return
                      k -= owed[ch]; owed[ch] = 0
                      for v 0..8 while k: if owner[v] == ch && note[v] == FF: owner[v] = FF; k--
                      for v 0..8 while k: if owner[v] == ch: voice_off(v); owner[v] = FF; k--
redistribute() (167d): free = count(owner == FF); if !free: return
                      for c 0..15: o = owed[c]; if !o: continue
                          if o < free: free -= o; owed[c] = 0; assign(c, o)
                          else: owed[c] = o - free; assign(c, free); return
```
Voice ownership explains why the player sends ctrl 4Bh in every channel set-up: a channel without
voices plays nothing; when voices run out, channels are *owed* voices and receive them as others
release theirs.

### 8.4 Patch bank `SSM:003:` (verified)

Chunk = SCI patch file: `89`, `u8 n` (= 0Ch), n bytes `"AdLib - ACES"` (description), then **2688
bytes**: 48 instruments × 28, `AB CD`, 48 more × 28 (fn 1 copies the second half only when the
marker is there). Instrument = 13 modulator bytes, 13 carrier bytes (operator bytes as in `write_op`),
modulator waveform, carrier waveform. `SX.OVL`/`SX1.OVL` banks differ from `SXCODE.OVL` in 4 bytes
(instrument 3: modulator AR/RR, carrier RR; instrument 29: carrier TL). Use the bank of the OVL the
program loads (INTRO/PS `SXCODE.OVL`, AP `SX1.OVL`/`SX.OVL` §12).

### 8.5 Behaviour notes (for listening tests)

* OPL2 melodic mode only (BDh = 0, no rhythm), waveform select on, 9 voices, 16 MIDI channels.
* Only the carrier follows the volume for FM instruments (ALG byte 1); both operators for additive.
* Pitch bend: ±12 semitones over the full 14-bit range in quarter-tone steps.
* Volume changes rewrite A0h/B0h (with key on) too; `voice_off` rewrites frequency with key 0 and
  the current volume.
* Notes are **dropped** when every voice of the channel was started in the current tick (age 0).

---

## 9. TTM sound opcodes (verified)

The TTM interpreter (video spec: INTRO `11d2:053f`, PS `3baf:0540`, AP see §12) hands opcodes of class
`C000` to a sound dispatcher: INTRO **`ttm_sound_op` `11d2:000c`**, PS **`3baf:000d`** (skipped when
the TTM thread field `+0E` (`DS:769A`) ≠ 0; old opcodes `1301` → `C051`, `1311` → `C061`). The opcode
word is read from `DS:33C0` (INTRO) and looked up in an 18-entry table (`cs:0100` codes, `cs:0124`
handlers; PS `cs:0101`/`cs:0125`); arguments `a b c d` are the TTM operands, `str` the string operand.
Unknown code → returns −1.

| Opcode | Name | Call (INTRO / PS) |
|---|---|---|
| C01F | SND_NAME str | `strcpy(DS:33A5 / DS:7681, str)` (a second name buffer; not read by the sound code) |
| **C02F** | SND_BANK str | `strcpy(DS:3398 / DS:7674, str)` — the bank file for C031 |
| **C031** | SND_LOAD a | `snd_load_resource(bank, a)` (no-op when loaded) |
| C041 | SND_UNLOAD a | `snd_unload(a)` |
| **C051** | SND_PLAY a | `snd_play(a)` |
| C061 | SND_STOP a | `snd_stop(a)` |
| C071 | SND_PAUSE a | `snd_pause(a)` |
| C081 | SND_RESUME a | `snd_resume(a)` |
| C091 | SND_DISABLE a | `snd_disable(a)` |
| C0A1 | SND_ENABLE a | `snd_enable(a)` |
| C0B2 | SND_PRIORITY a b | `snd_priority(a, b)` |
| C0C2 | SND_HOLD a b | `snd_hold(a, b)` |
| C0D3 | SND_BEND a b c | `snd_pitch_bend(a, b, c)` |
| **C0E3** | SND_FADE a b c | `snd_fade(a, target b, ticks c)` |
| C0F4 | SND_CTRL a b c d | `snd_controller(a, b, c, d)` |
| C102 | SND_VOLUME a b | `snd_volume(a, b)` (0–63 via curve) |
| CF01 | SND_REVERB a | `snd_reverb(a)` |
| CF11 | SND_MASTER a | `snd_master_volume(a)` |

Only `C02F`, `C031`, `C051` and one `C0E3` occur in the shipped scripts (`work/ttm/*/*.TTM.txt`).
`tools/dynttm.py` / `port/formats/scripts.md` name `C0E3` "SND_C0E3"; it is the **fade** (hand-off).

---

## 10. Game call sites: INTRO (verified)

`sys_init` (`038e:080d`): `snd_init(DS:24B3, "sxcode.ovl")` (after mapping 4 and 7 to 2; failure →
`printf(DS:0406)` + `exit(0)`), `snd_load_resource("ttd.sx", 0)` (all 20 sounds, `DS:0452`), then
`snd_disable(-2)` if `DS:24B9` (CONTROL.PRF effects toggle, byte +8) is 0 and `snd_disable(-1)` if
`DS:24BA` (music toggle, byte +9) is 0. Everything else is TTM-driven: `038e:0973` runs `intace1`…
`intace5` (TTM, `DS:0600…0638`) until a key/button sets `DS:00C4`; then `main` calls
`snd_shutdown` (`1686:0004`) and `exit(2)`. Fatal paths: `05bb:001a` (exit: shutdown unless the
driver is MT-32 (3) and the exit chains on, so the MT-32 keeps its uploaded patches), `05bb:0052`,
`05bb:009f` (`snd_unload(0)`). `0dc0:000d` (Windows detection path, from `0460:0174`): disables both
classes around a Windows call and re-enables them.

| Script | Sounds (TTD.SX) |
|---|---|
| INTACE1 | C051 1000 DYNAMIX (logo jingle), C051 31 LOGOSTAR |
| INTACE2 | — |
| INTACE3 | C051 1001 **ACETHEME** (music, not looping), C051 29 DOPPLER |
| INTACE4 | — (ACETHEME continues) |
| INTACE5 | C051 30 FLYBY ×3, then `C0E3 1001 0 60`: fade ACETHEME to 0, step = \|(0 − 127) / 60\| = 2, one step every 2 service ticks (§6.6) → silent after 128 ticks (2.2 s); the node keeps running at volume 0 until `snd_shutdown` |
| INTACE31 / INTACE51 (M1SHL, 1946 add-on versions) | as INTACE3 / INTACE5 (29, 1001 / 30 ×3) |

---

## 11. Game call sites: PS (verified unless marked)

### 11.1 Start-up, driver, toggles, shutdown

* `sys_init` `048e:0009` (from `main` `048e:04db`): driver `n = DS:43B2` (CONTROL.PRF word +2,
  `1193:027a`; `-s<n>` overrides, `048e:036b`); 4 → 2; **3 (MT-32) with `DS:00C2` = 0 (started by the
  chain, not `nlkle`) → 88h = `NLD`** (no patch upload: INTRO already uploaded them, likely);
  `snd_init(n, "sxcode.ovl")` at `048e:0076`; failure → `fatal_error("Cannot initialize sound &
  music driver!…")` (`227c:00f8`). Then `snd_load_resource("shell.sx", 0)` (`048e:00e3`, name built
  by `1193:0115`) loads all 13 sounds, and `snd_play(1002 MENUS)` (`048e:00f6`) unless `DS:00C3`
  (returning from the sim) → **menu music from the start**.
* Toggles: `315c:000e` flips `DS:43B9` (music, CONTROL.PRF byte +9) and calls `snd_enable(-1)` /
  `snd_disable(-1)`; `315c:004f` flips `DS:43B8` (effects, +8) with class −2. Their only caller is
  `166d:0009` (from `menu.c` `2e25:04fc`): when Windows is present it mutes both, runs the on-line
  manual (`1671:0051`), and unmutes both. PS never re-applies the saved toggles at start (likely:
  no other reader of 43B8/43B9).
* Shutdown: `snd_shutdown` from `shell_exit` `227c:0091` (to the sim) and `227c:00e3` (to DOS) and
  `fatal_error` `227c:0102`; `227c:0151` (assert path) `snd_unload(0)`. Music plays until then.
* No PS code queries a signal, cue or position, or calls sound-on/off, restore or mute-all.

### 11.2 Music (SHELL.SX: 1002 MENUS, 1010 FLIGHTDK, 1004 DEATH, 1015 BOARDINQ)

| Site | Module | Call | When |
|---|---|---|---|
| 048e:00f6 | main/sys_init | play 1002 | start (not returning from the sim) |
| 04df:028d | main menu 04df:018d | play 1002 | after "other options" choice 2 (replays the title TTM INTACE6, which plays TTD 1014 and so stops MENUS) |
| 0542:01fd | simend.c 0542:01c4 | play 1002 | back from the sim, SIM.IN mode (`DS:4B87`) 2 or 3 |
| 0542:02dc | simend | play 1002 | career: after the pending event queue (`050c:01ba` → `1656:0095`) |
| 0542:02f8 | simend | stop 1002 | more events pending; `DS:4226 = 1` ("menu music stopped") |
| 0542:0353 | simend | play 1002 | if 4226 and `DS:4778`, before the career menu `0607:011d` |
| 0542:0387 / 0391 | simend | stop −1, play 1010 | next mission after the events → flight deck |
| 0542:03fa / 0404 | simend | stop −1, play 1002 | if 4226 → career menu |
| 1656:00b5 / 00cc | career event dispatcher 1656:0095 | play / stop 1004 DEATH | event 1: death screen `1305:044e` |
| 1656:00fa / 010d | same | play / stop 1015 BOARDINQ | event 4: board of inquiry `1305:0487` |
| 1656:00ea, 013b, 015c | same | stop −1 | events 2, 3, 5, 6: ceremonies (`0f35:01d8`, TTM scripts that play TTD music) |
| 0607:01bc / 01c6, 0254 / 025e | career menu 0607:011d | stop 1002, play 1010 | entering the flight deck `0787:0181` |
| 0607:01dd / 01e7, 028e / 0298 | career menu | stop 1010, play 1002 | back without flying (`DS:43D6` = 0) |
| 0787:02f9 | fltdeck.c 0787:0181 | play 1002 | leaving the flight deck; `DS:4356 = 0` |
| 0874:0bba | career events 0874:0b57 | stop −1 | before an event screen (newspaper / rumour / war end TTM with its own music) |
| 0874:0d4b / 0d55 | 0874:0cd6 | stop −1, play 1010 | aircraft/assignment changed (`strcmp DS:42FA`) → screen `1305:0546`; 4226 = 1 |
| 0874:0db8 / 0dc2 | 0874:0cd6 | stop −1, play 1010 | `DS:478A` changed (transfer?) → `0ddd:0cde`; 4226 = 1 |

TTM screens (via `3baf:000d`, bank `TTD.SX`, loaded on demand and never unloaded; starting one stops
MENUS/FLIGHTDK through music exclusivity): INTACE6 → 1014; AWRD_JP/US, JAPFLAG/USAFLAG → 1003 MEDAL;
AWRDMED → 31 LOGOSTAR; MEDJAP/USA, PRISJAP/USA → 1005 CAPTURE; USPAPER/JNPAPER → 1008 NEWS; RUMJAP →
1009 RUMORSJP; RUMUSA → 1014 RUMORSUS; SIMQ_JP/US → 1007 QUIETNSN; WARENDA/WARE46A → 1011 WARENDUS;
WARENDJ/WARE46J → 1012 WARENDJP.

### 11.3 UI effects (SHELL.SX 24 SELECT, 25 TAB, 26 WRONG)

| Site | Module | Sound | When |
|---|---|---|---|
| 2b4f:05e3 | alert.c 2b4f:0426 (input poll) | 26 WRONG | mouse press on no hotspot (event flags `DS:5FDC`: 1 inside, 2 outside, 4 press, 8 held, 10h release, 20h leave) |
| 2c11:19fd, 1a2f, 1bd6 | alert widgets 2c11:192f / 1a0e / 1bb5 | 24 SELECT | button released on the control (5FDC & 10h) |
| 2e25:01ed | menu.c 2e25:0049 | 25 TAB | keyboard move / hotkey match |
| 2ed6:0209 | soft.c 2ed6:01f2 | 24 SELECT | press or held (5FDC & 0Ch) |
| 2fa5:004f | listbox.c 2fa5:0033 | 24 SELECT | press |
| 2fa5:0144 | listbox 2fa5:00f6 | 24 / 25 | press / selection changed |
| 0787:0139 | 0787:0129 (reached by pointer) | 24 SELECT | after confirm `2c11:1a0e` |

SHELL.SX 27–31 (engine, doppler, flyby, logostar) and 1000 DYNAMIX are not referenced by PS code.

---

## 12. AP: sound API, `sx_sim` and call sites

AP does not use the record/effect API of INTRO/PS for the game: its own positional sound manager
`sx_sim.c` (overlay `5a75`, stub segment `3d6e`) keeps a list of *sources* each frame, sorts them by
priority and volume, and drives the 7 pool nodes directly through the player stubs. Tags as before
(**V** verified in the disassembly, **L** likely, **G** guess).

### 12.1 AP sound API (segments `2fca`–`3326` around the player `3060`) — V

| AP | INTRO | Name | Used by the game |
|---|---|---|---|
| 326c:000d | 1634:000d | `snd_free` | yes |
| 3326:000d | 1724:0000 | `snd_alloc` | yes |
| 304e:0000 | 1620:000e | `ovl_load_chunk` | yes |
| 2fe4:0005 (+01f5, 0238, 0339, 041d, 04c9) | 15b5:0001 (+01fa, 023d, 033e, 0422, 04ce) | `snd_res_read` and helpers | yes |
| 332f:000d | 172c:000e | `snd_read_all` | yes |
| 326f:000a | 163c:0006 | `snd_load_patch` | yes |
| 3290:0000 | 16ac:000b | `snd_load_driver` | yes |
| 3040:000c | 1610:0005 | `snd_pool_alloc` (7 nodes → `DS:65EE`) | yes |
| 2fd8:0003 | 15a9:0005 | `snd_pool_free` | yes |
| 328c:000e | 168b:0002 | `snd_pool_stop_all` | via 32e7 only |
| 3301:0005 | 1700:000f | `res_skip_header` | yes |
| 303f:0000 | — | `snd_node_stop_far(node)` = player stop stub | yes (sx_sim) |
| 32b8:0003 | — | **`sng_load(name)`** | yes |
| 3312:000a | — | `sng_free(table)` | yes |
| 32d5:0007 / 005a / 0093 | 16d5:0001 / 0054 / 008d | `snd_driver_close`, wait, wait tick (`DS:65EC`) | yes |
| 2fca:0004, 2fdc:0000, 3048:0006, 3056:000b/007a, 3280:0009, 3299:0003, 32de:0008, 32e7:0005, 3303:0000, 3305:000c, 3308:000c, 330d:0001, 3318:0005 | 159b, 1617, 15ac, 1672, 164d, 16b6, 16de, 16e6, 1702, 1705, 1708, 170c, 1715 (by structure) | iterator, pool find, node new, unload, disable, play, enable, stop, … | **no**: their entry points (`3056:000b`, `3280:0009`, `32de:0008`) have no callers |

AP DGROUP: `DS:2692` active, `DS:2693` patch no, `DS:262A` `"SSM:"` buffer (`262E` name part),
`DS:2634[10]` driver codes, `DS:269D` driver number (FFFE failed), `DS:26A1` service timer handle
(never set by AP: `sx_init` registers the client itself and discards the handle), `DS:26A3` SNG
`INF:` table (near, class 8), `DS:26A5` driver block, `DS:26AD` disable state (unused path),
`DS:65EE[7]` pool nodes (far), `DS:65EC` close-wait counter.

`sng_load(name)` (32b8:0003): open the volume file if needed; find `SSM:` (`DS:267A`); every `SNG:`
chunk (`DS:267F`) → `snd_res_read(f, size, class 7)` (RLE, whole resource, **not** device-filtered)
into a local list (≤ 204); allocate `(n+1)·4` bytes class 6 (near) and copy the far pointers, 0
terminated → return value (`sx_sim` keeps it in `DS:48A3`); then `INF:` (`DS:2688`) → `(n+1)·4`
bytes class 8 at `DS:26A3`, `fread(2, n)`. The `INF:` bytes (loop, priority) are read only by the
unused `snd_pool_play` path; `sx_sim` takes loop/priority from `SND1.DAT` (§12.3). Failure frees
everything, returns 0.

Files: AP hard-codes `"sx1"` + `.OVL` (`DS:0372`, via `55a4:0000(name, "OVL")`), `"simsnds1.sng"`
(`DS:0376`) and `"snd1"` + `.DAT` (`DS:036D`, `DS:05BC`), all in `M1SIM.DYN`. **`SX.OVL` and
`SIMSNDS.SNG` (SIM2) are never loaded** by this AP build. Since `snd_res_read` is called with class
7 but AP's version keeps whole resources, the player's `prepare` selects the AdLib track (§5.6).

### 12.2 Start-up, switches, shutdown — V

`sim_init` `4e0d:0000`: `DS:43B3` (sound driver, CONTROL.PRF word +2 read into `DS:43B1`, platform)
is replaced by `DS:052E` when that is not −1. `main` `50c8:0008`: `-s` / `/s` is honoured only when
`50c0:0080` returns non-zero (the standalone/debug start check, sim_flow): `-s` alone → `DS:0532 = 1`
(**no sound**); `-s<n>` → `DS:0532 = 0`, `DS:052E = atol(n)`. Then:
* `DS:0532 = 0`: `sx_init(ovl = "sx1.ovl", "snd1.dat", "simsnds1.sng", DS:43B3, DS:0530)` (`4e0d:01db`);
  if the driver is 88h (NLD) and `50c8:0000` returns 0 → error message (`2494:0127`, string `DS:386B`
  +E4h). `sx_enable(DS:43B9)` at `4e0d:0227` (CONTROL.PRF byte +8 = effects on), and `sx_enable(-1)`
  … at `4e0d:04b5` (restart path `4e0d:03e9`).
* `DS:0532 ≠ 0` and `DS:0530 = 0`: only `timer_install(13)` + `timer_add(0000:02db, 1)` (the
  236.7 Hz tick counter `DS:18D2`) — no sound.

Shutdown `sx_shutdown` (`5a75:0d39`): from `sim_exit` `4e0d:0bb5`, and the fatal/message exits
`2494:0064`, `2494:0130`.

Timer (platform, AP `1d32`): `timer_add` `1d32:4755`, `timer_remove` `1d32:479f`, `timer_install`
`1d32:47c2`, `timer_restore` `1d32:482f`.

### 12.3 `sx_sim` data — V

`SND1.DAT` (380 bytes, loaded by `sx_init`): n = size/10 = **38 sound types**; `u16 maxdist[38]`
(`DS:489B`) then `u8 type[38][8]` (`DS:4899`):

| Byte | Meaning |
|---|---|
| +0 | continuous (1: re-registered every frame, looping node; 0: one-shot) |
| +1 | priority when the source is "the player's" (last argument of the play calls = 1) |
| +2 | priority otherwise |
| +3 | substitute type when `sx_update`'s flag is set (0 = none) |
| +4 | not read (0 or 2) |
| +5 | device channels needed |
| +6 | voices needed |
| +7 | cool-down (236.7 Hz ticks) of the channel/voice tokens after the sound ends |

Values (maxdist; +0..+7): 0 1000;0 90 90 0 0 1 4 16 · 1 1000;0 110 110 · 2 1000;1 90 90 · 3 1000;1 60 60 ·
4 3000;0 60 60 · 5 3000;0 70 70 · 6 4000;0 80 80 (6 voices 8) · 7 1350;1 50 50 · 8 2000;0 70 70 (2 ch, 6 v) ·
9–11 500;1 80 60 (6 v, cool-down 240) · 12 500;1 80 60 · 13 1000;1 80 80 · 14 1000;0 100 100 ·
15–17 1000;0 120 120 · 18 4000;0 40 40 (16 v) · 19 2000;1 120 120 subst 7 · 20 0;0 120 120 (9 v) ·
21 1000;0 60 60 (9 v) · 22 4000;0 40 40 · 23 4000;0 60 60 (6 v) · 24 0;0 120 120 · 25 1000;1 120 120 subst 26 ·
26 1500;1 · 27 1000;1 subst 28 · 28 1500;1 · 29 1000;1 50 50 · 30 1500;1 50 50 · 31 1000;1 40 40 ·
32 1500;1 50 50 · 33 1350;1 50 50 · 34 1500;1 50 50 · 35 1000;1 120 120 subst 36 · 36 1500;1 · 37 1500;1 50 50.
(Unlisted +5/+6/+7 are 1/4/16.) **For every driver other than 3 (MT-32) and 88h, `sx_init`
overwrites +5 = 1, +6 = 2, +7 = 4 for all 38 types.**

Globals (AP DGROUP):

| DS | Name | Meaning |
|---|---|---|
| 086C | `sx_oneshot_wait` | 3: frames a one-shot may wait for a free node |
| 086E | `sx_max_channels` | 8 |
| 0870 | `sx_max_voices` | 20h |
| 0872 | `sx_pool_n` | 7 |
| 0874 | `sx_start_timer` | timer object {u32 start, u16 duration} (`4b31`) gating new starts |
| 087A / 087C | | start delay after a stop / after a one-shot ends (per driver, below) |
| 087E | `sx_bend_chan` | MIDI channel that receives the Doppler pitch bend (default 2) |
| 0880 | `sx_mt32` | driver == 3 |
| 4894 | | "may start more this frame" |
| 4895 / 4897 | | voices / channels in use (budget) |
| 4899 / 489B | | type table / maxdist table |
| 489D / 489F | | token lists: channels (8) / voices (32) cooling down (`3546` list objects, each item a `4b31` timer) |
| 48A1 | `sx_active` | |
| 48A2 | `sx_on` | effects enabled |
| 48A3 | | SNG resource table (far ptr per type) |
| 48A5 / 48B1 | | previous / current listener position (3 × s32) |
| 48BD | | set to −1 by `sx_enable` |
| 48BF | | number of audible sources in `48E3` |
| 48C1 / 4983 | | continuous sources: count / array[50] × 14 bytes |
| 48C3 / 4C3F | | one-shot sources: count / array[30] × 14 bytes |
| 48C5 / 48C7 | | nodes to stop this frame: count / far ptr array |
| 48E3 | | audible source pointers (near) |
| 65EE | | pool[7] (far node pointers) |

Source (14 bytes): `+0 pos` (near ptr to 3 × s32 world position, 0 = non-positional), `+2 vel`
(near ptr to 3 × s16 velocity, 0 = none), `+4 volume` (0 = computed from distance), `+6 bend`
(pitch bend base, 2000h), `+8 age`, `+0A type`, `+0B priority`, `+0C pool index` (FF none),
`+0D flags` (bit 0 continuous/looping, bit 1 silent (volume 0), bit 2 reserved budget). Node fields
AP adds: `+16E` owner (source `+0`), `+170` type.

Per-driver setup in `sx_init` (switch on the driver number 0–4, table `cs:0D1D`): 0 (STD) → delays
5/5, bend channel 0, and priorities +1/+2 of types 19, 25, 26, 27, 28, 35, 36 and +2 of 32, 33, 34, 37
set to 40; 1 (TAN) → delays 8/8, bend channel 0; **2 (ADL) and 4 → delays 8/8** (bend channel stays
2); 3 (M32) → delays 10/10, bend channel 1. Other numbers (5 PS1, 88h NLD) keep 0/0 and channel 2.

### 12.4 `sx_sim` functions (`5a75`) — V

| Addr | Name | Signature / behaviour |
|---|---|---|
| 0000 | `tok_hold(list, ticks, n)` | take n tokens from `list` (`3546:0304`) and start each one's timer for `ticks` |
| 0034 | `sx_release(type)` | `tok_hold(489F, T[type].7, T[type].6); tok_hold(489D, T[type].7, T[type].5)` |
| 008A | `tok_busy(list)` | count tokens whose timer has not expired, free the expired ones |
| 00FB | `sx_age_oneshots()` (near) | for each one-shot i: if `age < 086C` and not started → keep, `age++`; not started (waited too long) → drop; started and its node's signal = FF (ended) → drop, `timer_set(0874, 087C)`, `sx_release(type)`; else keep. Compacts `4C3F`, updates `48C3` |
| 01DE | `sx_volume(src, dist)` (near) | if `src.4 == 0`: `vol = maxdist[type] ? 7Fh − sdiv32(dist << 7, maxdist[type]) : 7Fh`, capped at 7Fh → `src.4` |
| 0244 | `sx_collect(dst, src[], n)` (near) | for each source: `d = pos ? dist3(48B1, *pos) : 0` (`277a:3b3c`, render3d math); if `d < 200000`: `d >>= 3`; if `!maxdist[type] || maxdist[type] > d`: append to `dst`, `sx_volume(src, d)`; returns count |
| 02DF | `sx_collect_all()` | one-shots then continuous → `48E3`, count `48BF` |
| 030B | `sx_substitute(flag)` | if flag: every audible source with `T[type].3 ≠ 0` takes that type |
| 034D | `sx_node_stop(node)` | `timer_set(0874, 087A)`; stop the node (`303f:0000`); `sx_release(node[170])` |
| 0384 | `sx_match_nodes()` | for every pool node playing (`158 ≠ FF`) with loop flag (`15D`): find the audible source with the same type and owner (`170`, `16E`) → `src.C = pool index`; none → add the node to the stop list `48C7` |
| 042A | `sx_cmp(a, b)` (far, for qsort) | `b.prio − a.prio`, else `b.vol − a.vol`, else `a − b` (pointer), else −1 |
| 0478 | `sx_sort()` | `qsort(48E3, 48BF, 2, sx_cmp)` when more than one |
| 0497 | `sx_reserve(type)` | `4897 += T.5; 4895 += T.6` |
| 04C5 | `sx_budget_start()` | `4894 = 1; 4897 = tok_busy(489D); 4895 = tok_busy(489F)`; reserve every audible source with a node |
| 051C | `sx_fits(src)` | `4897 + T.5 ≤ 086E − (bit2 ? 0 : 1)` and `4895 + T.6 ≤ 0870 − (bit2 ? 0 : 6)` |
| 05A3 | `sx_can_start(src)` | `4894 && sx_fits(src) && timer_expired(0874)` → 1, else `4894 = 0` (no more starts this frame) and 0 |
| 05D8 | `sx_trim()` | usage = 0; for the sorted sources i: playing and (`i ≥ 7` or not fitting) → queue its node for stop, `C = FF`; every playing source and every waiting one with `i < 7` is reserved (Quirk: stopped ones too) |
| 066F | `sx_free_node()` | first pool index with signal FF, else −1 |
| 0698 | `node_clear(node)` | `memset(node, 0, 17Ah)` |
| 06B3 | `sx_doppler(src, node)` | if `src.2`: `p = *pos + *vel`; `d = dist3(p, 48A5) − dist3(*pos, 48B1)`; `d = clamp(d, −1000, 1000)`; else d = 0; `bend = clamp(src.6 + d, 100, 16000)`; `snd_node_pitch_bend(node, bend, 087E)` |
| 0778 | `sx_eff_vol(src)` | bit 1 ? 0 : `src.4` |
| 0798 | `sx_apply()` | `n = min(48BF, 7)`; stop the queued nodes (`sx_node_stop`); `sx_budget_start()`; for i < n, `prio = n − i`: not playing → if `sx_can_start`: `k = sx_free_node()` (none: skip); `src.C = k`; `sx_reserve`; `node_clear`; `15D = 1` if bit 0; `16E = src.0`; `170 = type`; `166 = sng[type]`, `16A = res_skip_header`; `15E = sx_eff_vol`; `15C = prio`; `158 = FF`; `8 = &node[16A]`; **play(node, 0)**; `sx_doppler`. Playing → `snd_node_volume(node, sx_eff_vol)`, `snd_node_set_priority(node, prio)`, `sx_doppler` |
| 095E | **`sx_update(listener, flag)`** (far, per frame) | if active: clear the stop list; `sx_age_oneshots`; `sx_collect_all`; `sx_substitute(flag)`; `sx_match_nodes`; `sx_sort`; `sx_trim`; `sx_apply`; `48A5 = 48B1; 48B1 = *listener` |
| 09A7 | `sx_stop_nodes()` | stop every playing pool node (`sx_node_stop`) |
| 09D5 / 09F0 / 0A01 | `sx_off` / `sx_on` / `sx_is_on` | off: stop nodes, `48A2 = 0`; on: `48A2 = 1` |
| 0A0A | `sx_clear_continuous()` | `48C1 = 0` |
| 0A1C / 0A2E | `sx_type_valid(t)` (t < 38) / `sx_type_continuous(t)` (no caller) | |
| 0A42 / 0AB3 / 0AC6 / 0AD3 | per-driver setups (§12.3) | |
| 0AE6 | `sx_is_mt32()` | |
| 0AFA | **`sx_init(ovl, datname, sngname, drv, off)`** | `off` → return 0; `0880 = drv == 3`; `snd_load_driver(drv, ovl)` (fail → 0); token lists `489F = list(32, 6)`, `489D = list(8, 6)`; read `SND1.DAT` (maxdist, types; missing → error `2494:0127`); `snd_pool_alloc`; `48A3 = sng_load(sngname)`; `timer_install(13)`; `timer_add(player_service 3060:17e2, 4)`; `timer_add(0000:02db, 1)`; `48A1 = 1`; per-driver setup; drivers ≠ 3/88h: token needs 1/2/4; if `DS:26DD == 3`: `0000:02f1` |
| 0D39 | **`sx_shutdown()`** | if active: `48A1 = 0`; stop nodes; `snd_driver_close`; `sng_free(48A3)`; wait until `DS:31E5` (set to 10) counts down; `timer_restore` |
| 0D66 | **`sx_enable(on)`** | not active → 0; `on == 1` → `sx_on` if off; `on == 0` → `sx_off` if on; `48BD = −1`; reset `0874`; 1 |
| 0DB6 | `sx_add(type, owner/pos, flags, player)` (near) | only when `48A2` and `type < 38`: continuous type → next slot of `4983` (≤ 50), zeroed, bit 0; else next of `4C3F` (≤ 30), zeroed; `6 = 2000h`, `A = type`, `C = FF`, `0 = pos`, `B = player ? T.1 : T.2`, flags bit 0 → bit 1 |
| 0E96 | **`sx_stop_all()`** | stop nodes, clear continuous |
| 0EA9 | `sx_play_vol(type, vol, bend, player)` | non-positional source with volume and bend |
| **0EEA** | **`sx_play(type, pos, vel, player)`** | `sx_add`; `2 = vel`, `6 = 2000h` |
| 0F2C | `sx_play_rsv(type, pos, vel, player)` | as `sx_play` + bit 2 (full budget) |
| 0F72 | `sx_play_ex(type, pos, bend, vel, flags, player)` | `6 = bend`, `2 = vel` |

Timers `4b31`: `timer_expired(t)` = `DS:31E4 == 0 || (now − t.start) > t.duration` with `now` =
`DS:18D2` (u32, 236.7 Hz, client `0000:02db`); `timer_set(t, n)`; `timer_reset(t)` (`4b31:0062`).
Token lists (`3546`) and `dist3` (`277a:3b3c`, approximate 3-D distance) belong to other modules.

Effect of the budget with AdLib: each sound needs 1 channel and 2 voices; channel limit 8 − 1 =
**7 sounds**, the pool is 7 nodes, the player then gives each node's channels voices by priority
(§5.8). A new sound can start only 8 ticks (34 ms) after the last stop/end and a token is held 4
ticks after release.

### 12.5 AP call sites (V for the calls; meaning L unless the context names it)

| Caller | Module | Call | Type | Meaning |
|---|---|---|---|---|
| 4bf9:00e3 | plane step `4bf9:0017` (sim_world_fm §4.2) | `sx_play_ex` | `DS:02D4[eng]` = 19, 28, 26, 29, 30, 35 | **player engine** (continuous), bend = rpm pitch, player = 1 |
| 4bf9:023f | same | `sx_play` | `DS:02DA[eng]` = 33, 32, 34, 29, 30, 37 | **other aircraft engines** (continuous) |
| 4bf9:014b | same | `sx_play` | 16h (22) | gear touchdown (player) |
| 4bf9:0219 | same | `sx_play` | 1Fh (31) | fly-by of the nearest aircraft within 5000 |
| 0769:0072 / 008f | guns `0769:004c` | `sx_play_rsv` (player) / `sx_play` | gun type `[si+1362h]` | **gunfire** |
| 655d:08ce, 09dd | guns/bullets `655d` | `sx_play` | 5 | bullet impact (after `1560:024a` impact effect), player flag = target is player |
| 655d:1869 | same | `sx_play` | 1 | player hit (with message `1614:02ce`) |
| 085b:013c | proximity/collision | `sx_play` (bend 1F40h) | 1 | mid-air collision / hit at the player |
| 088a:02a2 / 02c4, 02fc, 0400 | ground/ship impact, crash | `sx_play` | 17h (23) / 12h (18) | crash explosion / impact (splash or ground) |
| 088a:0543 | same | `sx_play` | `si` (variable) | object-dependent impact |
| 1560:020b | weapon impacts | `sx_play` | 17h | explosion |
| 0688:0642 | bombs.c | `sx_play` (player) | 2 | bomb falling (continuous) |
| 0deb:0089 | g_attack.c | `sx_play` (player, if `DS:19F2`) | 0 | (G) |
| 5440:09f2 | sim input/step `5440:096a` | `sx_play` | 15h (21) | when `0deb:1500(player)` (G: warning, e.g. stall) |
| 5440:1211, 123a, 1262, 128e | `5440:0aee` (sim input) | `sx_play` | 0Eh, 0Dh ×3 | cockpit events gated by `DS:19F2` (G: gear/flaps/hook) |
| 47a8:0d81, 0db6, 0e49; 6396:0359, 0390; 6b4d:0102 | forms, alrtlib2.c, control.c dialogs | `sx_play` | 0Fh (15) | UI click, when `DS:3BCB & 10h` |
| 606e:003c | rlsmgfx.c | `sx_play` | 10h (16) | (G) |
| 5d3c:005a | VCR glue | `sx_update(camera pos, DS:19F2 == 0)` | | the per-frame update; the flag selects the substitute types (§12.3) |
| 5440:13aa, 6163:003f | | `sx_clear_continuous` | | |
| 5c5f:016e, 5cde:000e/01b8/024d/0265/02b9/037b, 5d56:00a3, 5e06:01a4/0920 | vcr2.c, VCR, vcr_gfx.c | `sx_stop_all` | | film playback / view changes |
| 5cde:03c4 | VCR | `sx_is_on` | | |
| 6b4d:0495 / 049f | control.c prefs `6b4d:0480` | `sx_on` / `sx_off` | | the sound option |
| 4e0d:01db, 0227, 04b5 | init.c | `sx_init`, `sx_enable` | | |
| 4e0d:0bb5, 2494:0064, 2494:0130 | sim_exit, fatal | `sx_shutdown` | | |

No AP code uses music, fades, signals or the record API; the sim is effects only.
Types without a constant call site: 3, 4, 6, 8–12, 17, 20, 24, 25, 27 (7, 26, 28, 36 are reached via
`sx_substitute`); probably through the variable ones (gun table `+1362h`, `088a:0543`). Meanings of
the individual SIMSNDS1 sounds beyond this table stay open.

---

## 13. Port notes

* **Device**: `/* PORT: */` always load and run the AdLib driver model (driver number 2) whatever
  CONTROL.PRF / `RESOURCE.CFG` / `-s` say, until MT-32 (Munt) or the other drivers are implemented;
  treat 3/88h (MT-32/NLD) as 2 so the eXoDOS configuration (MT-32) plays AdLib. Keep the driver
  number variable (`DS:1F4B` etc.) and the play-id switch so a later MT-32 driver drops in. The
  `NLD` substitution in PS only matters with a real MT-32.
* **OPL**: Nuked-OPL3 (as TD3) in OPL2 mode (register writes to bank 0 only; the driver never
  touches bank 1 or 105h). `opl_write(reg, val)` → `OPL3_WriteRegBuffered` / `OPL3_WriteReg`; drop
  the status-read delays. Sample rate: Nuked native 49 716 Hz, resampled by SDL.
* **Time base**: the player service runs at **59.17 Hz** (1 193 182 / 5041 / 4 = 59.1734 Hz,
  16.8995 ms). Generate it on the audio thread: per output block, advance a fractional sample counter
  and call `player_service()` each time 16.8995 ms of audio has been produced, writing the OPL
  registers at that sample position. This keeps note timing sample-accurate and independent of the
  game's frame rate. The game-side API calls take the audio lock (`SDL_LockAudioStream` or a mutex)
  so they are atomic against the service, which reproduces the original `cli` sections.
* **Where the state lives**: the player's variables are in its code segment (not in `mem[]`/DGROUP);
  keep them as C statics (`struct sci_player`), with the node as a 0x17A-byte array in `mem[]`
  (the API and the game address nodes by far pointer; the overlapping per-channel tables need the
  byte layout). The driver model keeps its state in a copy of the 8070-byte image (as
  `aotpsnd.AdlibDriver`), or named arrays of the same sizes.
* **Resources**: INTRO/PS keep only the device track (§6.3). The port can do the same (faithful,
  saves nothing that matters) or keep the whole resource — equivalent for playback since `prepare`
  selects the same track, but the header rewrite (§5.6) needs ≥ 0x24 writable bytes at the start.
* **Reference**: `tools/aotpsnd.py dro` renders every sound through a line-by-line Python model of
  the player and driver; its DROs (`work/sound/*/*.dro`, register writes with ms timing) are the
  regression reference for the C port (compare register streams, not audio).
* **Timer / exit waits**: `snd_driver_close` waits ~85 ms for two service ticks; the port can call
  the service twice directly (the no-timer branch).
* **Not ported**: digital-sample paths (driver fns 14–16), `p_lock`, `AskDriver`; `p_restore` is
  never called.
* **Sound toggles**: CONTROL.PRF bytes +8/+9 are applied by INTRO `sys_init` only; PS/AP behaviour
  as in the original.

---

## 14. Corrections to `port/formats/sound.md`

* §1a/§3: record flags bit 0 is the **music class** (set on every id ≥ 1000; it also selects
  allocation class 4 instead of 7), not only a memory class; bit 4 is **pending** (to restart when the
  class is re-enabled), not "loaded/playing".
* §3 "`play` is called as `play(node, 1)` by INTRO/PS": only for **music** (`node_play_nth`);
  effects are started with `play(node, 0)` by `snd_pool_play` in all three programs, at node priority
  1.
* §3/§4: INTRO/PS do not keep whole resources: `snd_res_read` keeps only the track of the current
  driver's play id (§6.3). Play ids: STD 12h, TAN/PS1 13h, ADL/SBL/PRO 00h, MT-32 0Ch.
* §4 "`-s<num>` not traced": sets the driver number directly (§7.2).
* §3 table: the player's stub `0150` takes (node, ctl, val, chan) and ctl 7Fh means program change;
  `00ee` takes (node, value14, chan).
* TTM opcode `C0E3` (`port/formats/scripts.md`, `tools/dynttm.py`) is `snd_fade(id, target, ticks)`.

## 15. Hand-offs

* **video** (TTM player): the TTM interpreter passes opcode class `C000` to the sound dispatcher
  (INTRO `11d2:000c` from `11d2:053f`; PS `3baf:000d` from `3baf:0540` at `3baf:06f6`, skipped when
  the thread field `+0E` / `DS:769A` ≠ 0, old opcodes `1301`/`1311` remapped to `C051`/`C061`). The
  sound side is specified in §9; `C0E3` = fade (rename in `dynttm.py` / `scripts.md`).
* **platform**: CONTROL.PRF record (INTRO `DS:24B1`, PS `DS:43B0`, 0x25 bytes): word +0 video
  driver, word +2 **sound driver number**, byte +8 **effects on**, byte +9 **music on** (INTRO
  `DS:24B9`/`24BA`, PS `DS:43B8`/`43B9`). `RESOURCE.CFG soundDrv` → number via the name table INTRO
  `DS:00CF` (strstr, §7.1). Option `-s<num>` (INTRO `038e:0bd1`, PS `048e:036b`). The sound service
  is timer client #n with countdown 4 (`timer_add`), installed by `snd_init` which calls
  `timer_install(13)` only if the timer flag (INTRO `DS:15BE`, PS `DS:2E3E`) is clear. The
  decompression-stream functions used by the loaders: `05da:6b6c` open, `6f3d` read, `7050` seek,
  `702d` length, `6db5` close (INTRO).
* **shell_ui**: every PS sound call site with its intent is in §11 (menu music transitions,
  SELECT/TAB/WRONG in `alert`/`menu`/`soft`/`listbox`, the Windows manual mute `166d:0009` →
  `315c:000e`/`004f`). The shell only calls `snd_play`, `snd_stop`, `snd_enable/disable`,
  `snd_load_resource`, `snd_unload`, `snd_shutdown`.
* **shell_ui / INTRO flow**: INTRO exit `05bb:001a` skips `snd_shutdown` when the driver is MT-32 and
  the program chains on (keeps the MT-32 patch upload); PS then uses `NLD` (§11.1).
* **sim_flow / sim_world**: AP sound goes only through `sx_sim` (§12): per-frame `sx_update` from
  `5d3c:005a` (camera position, flag `DS:19F2 == 0`), the play calls and types in §12.5 (engine
  tables `DS:02D4`/`DS:02DA`, gun sound `+1362h`), `sx_stop_all` from the VCR modules, `sx_on/off`
  from the prefs dialog `6b4d:0480`, `-s`/`-s<n>` (`DS:0532`/`DS:052E`) in `main`, `sx_init` /
  `sx_enable(DS:43B9)` in `sim_init`, `sx_shutdown` in `sim_exit`. Still to name: `DS:19F2`, the
  gates at `5440:0aee` (types 0Dh/0Eh/15h) and `50c0:0080`. Token lists `3546` and the timer objects
  `4b31` (`DS:31E4`, `DS:31E5`) belong to sim_flow; `277a:3b3c` to render3d.

## 16. Open questions

* Listening: DROs have not been compared with DOSBox captures (tempo, instrument choice, the
  note-drop quirk).
* MT-32 path (`M32`/`NLD` drivers, `SSM:001:` bank, INTRO keeping the MT-32 initialised across the
  chain): parked with the MT-32 TODO.
* Device tracks 06h, 09h and 16h in the resources belong to drivers not shipped here (no loader
  maps to them).
* `p_restore`, cues, positions and sound-on/off are never called; their behaviour is specified from
  the code only.
