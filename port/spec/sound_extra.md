# sound — AP leftovers of the record/pool API and `sx_sim` fragments

Extra part of `sound.md`. Covers the last AP functions of the sound segments that had no symbols
row. All of them are the shared sound-API library (`sound.md` §6, INTRO/PS addresses) compiled into
AP, or indexer artefacts inside the `sx_sim.c` overlay `5a75`. Verified against x86dis.

## 1. Shared library functions in AP (§6.2 of `sound.md` is the spec)

AP DGROUP offsets differ from INTRO: pool `DS:65EE[7]` (far node pointers; INTRO `DS:33D6`),
record list head `DS:2699/269B` (never written in AP, so the record API sees an empty list —
`sound.md` §12.1).

| AP | INTRO / PS | Name | Live in AP? | Notes (AP specifics) |
|---|---|---|---|---|
| 2fdc:0000 | 15ac:000c / 4543:000d | `snd_node_new(void far *res)` → Node far* | no (only from `3299:0003` `snd_play`, itself reached only from the dead `snd_enable`) | `n = snd_alloc(17Ah, 2)` (`3326:000d`, zero-filled); null → 0. `n+166 = res`; `n+16A = res_skip_header(res)` (`3301:0005`); `n+08 = &n+16A` (far); `n+15E = 7Fh`; `n+172 = 0` (far next); return n |
| 2fe4:01f5 | 15b5:01fa / 454c:01fb | `chlist_free(Ch far *)` | yes (from `snd_res_read` `2fe4:0005`) | byte-identical to INTRO |
| 2fe4:0238 | 15b5:023d / 454c:023e | `res_find_track(FILE *f, u8 dev)` | yes | identical |
| 2fe4:0339 | 15b5:033e / 454c:033f | `chlist_read(FILE *f)` → Ch far* | yes | identical |
| 2fe4:041d | 15b5:0422 / 454c:0423 | `chlist_insert(Ch far *list, Ch far *item)` | yes | identical |
| 2fe4:04c9 | 15b5:04ce / 454c:04cf | `res_build(f, list, dst, size, hdr, dev)` | yes | same instructions (score 0.94 = relocations only) |
| 3048:0006 | 1617:000b / 45ae:000c | `snd_pool_find(void far *res)` → Node far* | no (from `3299:0003`) | for i in 0..6: `n = DS:65EE[i]`; `n+166 == res` and `n+158 != FFh` → return n; else 0 |
| 3056:007a | 1629:007d / 45c0:007e | `snd_rec_node(Rec far *r)` → Node far* | no (only from `3056:000b` `snd_unload`, no callers) | `r+12 & 1` (music) → `r+0E` (far); else `snd_pool_find(r+04)` |
| 3303:0000 | 1702:000a / 4699:000b | `node_stop_nth(Node far *n, int k)` | no (from `32e7:0005` `snd_stop`) | `m = node_nth(n, k)`; m → `snd_node_stop(m)` (`3060:0109`) |
| 3305:000c | 1705:0008 / 469c:0009 | `node_nth(Node far *n, int k)` → Node far* | no | follows the far link `+172` k times, stopping at null |
| 3308:000c | 1708:0008 / 469f:0009 | `node_play_nth(Node far *n, int k, u8 vol)` → Node far* | no (from `3299:0003`) | `m = node_nth(n, k)`; m → `m+15E = vol`, `snd_node_play(m, 1)` (`3060:009f`, locked channels), return m; else 0 |
| 330d:0001 | 170c:000f / 46a4:0000 | `snd_pool_stop_data(void far *res)` | no (from `32e7:0005`) | first pool node i (0..6) with `n+166 == res`: `snd_node_stop(n)`, `n+158 = FFh`, return (stops at the first match, playing or not) |

Port: the dead ones need not be ported (no reachable caller in AP: the chain ends in
`win_task_switch` `2466:0118`, which has no caller). The five `2fe4` helpers are live: they are the
device-track filter of every `SNG:` effect load (`sng_load` → `snd_res_read`) and are ported once
from the INTRO spec.

## 2. `5a75` (`sx_sim.c`) indexer fragments

The overlay's near functions use the VROOMM far-frame convention `inc bp; push bp; mov bp,sp …
pop bp; dec bp; ret`. The indexer split off the leading `inc bp` (45h) of each following function
as a 1-byte "function". None of these is code on its own:

| AP | Size | What it is |
|---|---|---|
| 5a75:00fa, 01dd, 0243, 030a, 034c, 0383, 05d7, 0697, 06b2, 0777, 0797, 0db5 | 1 | the `inc bp` prologue byte of the function at the next address (`00fb`, `01de`, `0244`, `030b`, `034d`, `0384`, `05d8`, `0698`, `06b3`, `0778`, `0798`, `0db6`) — part of that function |
| 5a75:0d1d–0d26 | (data) | 5-word near jump table at the end of `sx_init` (`0CBC, 0CCB, 0CC1, 0CC6, 0CC1` — targets inside `sx_init`, used by `jmp cs:[bx+0D1Dh]` at `5a75:0cb7`, its driver switch); data, not code |
| 5a75:0d27 | 4 | `timer_countdown_get()` near: `mov ax,[DS:31E5]; ret` (platform `timer_countdown`) |
| 5a75:0d2b | 14 | `sx_wait10()` near: `DS:31E5 = 10`; `while (timer_countdown_get()) ;` — busy-waits 10 PIT ticks (10/236.69 s ≈ 42 ms) so the driver can silence the voices; called once from `sx_shutdown` `5a75:0d39` after `snd_driver_close` and `sng_free` |
| 5a75:0db0 | 5 | empty far function (`push bp; mov bp,sp; pop bp; retf`), no callers (a compiled-out debug hook) |

`sx_shutdown` (`5a75:0d39`) in full, for reference: if `DS:48A1`: `DS:48A1 = 0`; `sx_stop_nodes`
(`09a7`); `snd_driver_close` (`32d5:0007`); `sng_free(DS:48A3)` (`3312:000a`); `sx_wait10()`;
`1d32:482f()` (platform: remove the timer client).

Port note: `sx_wait10` → `/* PORT: */` a 42 ms sleep or nothing (the emulated OPL has no release
tail that matters at shutdown).
