# Sound: SX / SNG banks, SCI1 sound resources, the SCI sound module and the AdLib driver

Addresses: INTRO.EXE `SSSS:OOOO` file segments as in `port/intro_functions.csv` (DGROUP `17E0`);
the sound module is segment `1373` (INTRO), driver offsets are offsets in the unpacked `SSM:ADL:`
chunk. Status tags: **Verified** (read in the code and re-implemented in `tools/aotpsnd.py`, checked
over every sound), **Likely**, **Unknown**. Nothing has been checked by ear yet: the DROs in
`work/sound/` are there for that.

Aces of the Pacific does not have its own music code: it links Sierra's SCI1 sound module
(`midi.s`: C-callable stubs + sequencer + channel remapper, Dynamix was a Sierra company by then) and
loads unmodified Sierra SCI1 sound drivers ("dude" drivers) out of an overlay file. Music and effects
are SCI1 sound resources stored in Dynamix chunk files.

## Tool

`python tools/aotpsnd.py …` (reads `Game/*.DYN` directly):

| Command | Output |
|---|---|
| `list` | every sound of the four banks: id, name, priority, flags, size, loop, device tracks |
| `extract` | `work/sound/<BANK>/<id>_<NAME>.snd` = standalone SCI sound resources (`84 00` + data, loadable by SCI tools); `work/sound/<OVL>/{ADL,M32,NLD,TAN,PS1,STD}.DRV` and `PATCH.001/.003/.101` from the three OVLs; `work/sound/index.txt` |
| `dump BANK ID` | track table, channel headers, event listing of the AdLib track |
| `dro [BANK [ID…]]` | render through Python models of the sequencer (`1373:*`) and of `SSM:ADL:` → `work/sound/<BANK>/<id>_<NAME>.dro` (DOSBox raw OPL v2.0, OPL2) + `.txt` (listing + every driver call with its tick) |
| `all` | `extract` + `dro` for everything, summary in `work/sound/render.txt` |

`--passes N` (looping sounds stop after N restarts and at least 8 s, default 2), `--max S` (cap,
300 s), `--tail S` (release after the stop, 1.5 s). `tools/rawdis.py` disassembles raw drivers
(`rawdis.py FILE [start len]`) or MZ images with resynchronisation (`rawdis.py EXE SSSS:OOOO len`).
Disassemblies used here: `work/sound/dis/` (`intro_1373.asm`, `ADL_OVL.asm`, `adl_code.asm`, …).

## 1. Files (Verified)

| File (volume) | Used by | Contents |
|---|---|---|
| `SHELL.SX` (SHELL1) | PS.EXE | 13 sounds: 8 menu/flyby effects + DYNAMIX logo + MENUS, FLIGHTDK, DEATH, BOARDINQ music |
| `TTD.SX` (SHELL1) | INTRO.EXE (`"ttd.sx"`) | 20 sounds: the same 9 (byte-identical) + 11 intro/career pieces (ACETHEME, MEDAL, CAPTURE, NEWS, RUMORSJP/US, LANDOK, QUIETNSN, WARENDUS/JP, CREDITS) |
| `SIMSNDS.SNG` (SIM2) | AP.EXE | 35 unnamed sim sounds (engines, guns, flak, radio …: meaning Unknown) |
| `SIMSNDS1.SNG` (M1SIM) | AP.EXE with the 1946 add-on | 38 sounds: SIMSNDS 0–34 (13 and 14 changed) + 35–37 |
| `SXCODE.OVL` (SHELL1) | INTRO, PS (`"sxcode.ovl"`) | drivers + patches, below |
| `SX.OVL` (SIM2), `SX1.OVL` (M1SIM) | AP (`"sx1"`) | the same drivers, patch banks differ slightly |
| `Game/ADL.DRV`, `MT32.DRV`, `STD.DRV`, `IBMPS1.DRV` | installer (`INSTALL.SCR` copies `*.drv`) | loose SCI drivers; the game only uses the **name** written to `RESOURCE.CFG` (§5) |

### 1a. `.SX` = `SND:{INF: TAG: FNM: DAT:×n}` (loader `1659:000b`, record `157f:0009`)

| Chunk | Layout |
|---|---|
| `INF:` | `u16 version (1)`, `u16 n`, `u16 id[n]` — id order = `DAT:` order |
| `TAG:` | `u16 n`, n × (`u16 id`, ASCIIZ name) — `SELECT`, `MENUS`, … |
| `FNM:` | `u16 n`, n × (`u16 id`, ASCIIZ source file) — `SFX\M_SELECT.SND`, `MENUS.SND` (development names, not read by the game) |
| `DAT:` | `u16 id`, `u8 priority` (→ node `15Ch`; 7 everywhere), `u8 flags`, then the 5-byte pack header (`u8 method` = 2 LZW, `u32 size`) and the packed sound resource |

`flags` (record `+12h`): bit 0 = memory class (4 instead of 7 in the allocator), bit 1 = **loop**
(node `15Dh`, `16ac:01b1`), bit 4 set at run time (loaded/playing). `snd_load_resource(file, id)`:
id > 0 finds id's index in `INF:` and loads the index-th `DAT:`; id 0 loads all.

### 1b. `.SNG` = `SSM:{SNG:×n INF:}` (AP `3280:0985`)

`SNG:` = RLE-packed (method 1) sound resource; sound number = chunk index. `INF:` = n × (`u8 loop`,
`u8 priority`): byte 0 → node `15Dh`, byte 1 → node `15Ch` (3 everywhere); without `INF:` the caller's
loop flag and priority 1 are used. Volume `7Fh`.

### 1c. `SXCODE.OVL` / `SX.OVL` / `SX1.OVL` = `SSM:{M32: NLD: ADL: TAN: PS1: STD: 001: 003: 101:}`

All LZW-packed. Driver chunks: `M32` Roland MT-32/LAPC-I/CM-32L/CM-64, `NLD` "MT-32 NoLoad Driver
(not for shipping)", `ADL` AdLib, `TAN` Tandy 3-voice + DAC ("tnddrv"), `PS1` IBM PS/1 ("audjoy"),
`STD` PC speaker ("stddrv"). The six driver chunks and `101` are identical in the three files; `001`
and `003` differ slightly. Patch chunks =
SCI patch files: `89h`, `u8 n`, n bytes of description (`"AdLib - ACES "`, `"MT32 - ACES OF THE PA…"`),
data: `001` = MT-32 bank (16.9 KB), `003` = AdLib bank (2690 bytes, §6), `101` = Tandy/PS1 (1020 bytes).
The three `003` banks differ in 4 bytes (instrument 3 mod AR/RR, car RR; instrument 29 car TL).

## 2. SCI1 sound resource (Verified over all 106 sounds)

A resource starts with the SCI patch-file header `84 00` (type 4 = sound, 0 extra header bytes),
skipped by `1700:000f` (`ptr + 2 + byte[1]`). Offsets below are from the byte after it.

```
[F0 prio 6×?]                   optional priority header (8 bytes) - not used by any sound here
track*:  u8 device               00 AdLib, 0C MT-32, 12, 13, 09, 06, 16 (all present; 00 in every sound)
         channel* : u16 0, u16 offset, u16 size     (6 bytes)
         FF
FF
channel data (at offset):
  +0  u8  channel | flags<<4     flags 1: not remapped, starts at +3, events go to its own channel
                                  flags 2: 'locked' (keep this MIDI channel number)   flags 4: start muted
                                  FE = digital sample channel (none in this game)
  +1  u8  voices | priority<<4   voices the channel needs from the driver (ctrl 4Bh); priority 0 = must play
  +2  u8  delta, +3 Cn prog, +5 delta, +6 Bn 07 vol, +9 delta, +A 0A pan, +C first real delta, +D events
```

The sequencer reads the preamble **at fixed offsets** when a sound starts: program `+4`, volume `+8`,
pan `+0Bh`, first delta `+0Ch`, events from `+0Dh`; on a loop restart without loop point it replays
from `+3` (so the preamble is then executed as events). All 732 music channels of all sounds
follow this layout; the 305 control channels (channel 15) have `CF signal`, `BF 50 reverb`,
`0A pan` instead (so `+8` = reverb default, read into node `15Fh`).

**Events**: MIDI with running status; each event is followed by a delta time in 60 Hz-ish ticks
(§4): byte `d`; `F8` = 240 ticks and read another byte (repeatable); `00` = the next event is in the
same tick. `FC` = end of this channel. Data used: note-on (`9n`, velocity 0 = off; no `8n` in the
data), program `Cn`, controllers 7 (volume), 10 (pan), 4Bh (voice count), pitch bend `En`, `FC`.
The module also handles 8n, An (→ driver fn 6), Dn (fn 9), ctrl 1 (modulation), 40h (sustain), 4Eh
(channel mute), F0 sysex (skipped to F7).

**Control channel** (any status with channel nibble F): `CF 7F d` = **loop point** (all channels'
positions, delays and running statuses and the tick counter are saved); `CF v` = **signal** v to the
game (node `158h`; the data uses 0 and 1, read by `1373:012a`); `BF 50 v` reverb (7F = default);
`BF 60 x` cue counter +1; `BF 52 v` hold point (jump to the loop point if the node's hold value = v);
other `Fx` events are skipped. In the AdLib tracks: 47 loop points, 47 reverb settings, 47 signals,
no cues or hold points.

End of sound: when every channel has reached `FC`: stop, unless the node's loop flag (`15Dh`, from
the bank) or hold value (`15Ah`) is set → restart at the loop point (default: every channel at `+3`
with delay 0, tick 0).

## 3. The sound module (INTRO `1373`, identical code in PS and AP)

Same bytes in PS.EXE (image `430A1h` ↔ INTRO `1373:0000`) and AP.EXE (`3060:0004` = image `30604h`),
only the data offsets shift. Sierra's SCI1 `midi.s` (Verified by structure: it is the code ScummVM's
`SciMusic` imitates).

### C interface (far stubs, `cdecl`, all in `1373`)

| Stub | Routine | Function |
|---|---|---|
| `0075` | `0398` | attach driver (far ptr to the unpacked driver, stored at `cs:0371`), fn 0 → returns the patch number; keeps CL = voices (`cs:0378`), CH = play id (`0375`), AH>>4 = digital support (`0379`) |
| `0086` | `03c8` | fn 1 init(ES:AX = patch data or 0) → CL/CH = first/last device channel (`037c`/`037e`), then fn 11 reverb 0; returns AX (FFFF = failure) |
| `016a` | `03ed` | fn 12 master volume 15, fn 2 terminate |
| `009b` | `0528` | **play(node, locked)**: see below |
| `0105` | `080c` | stop(node) + remap |
| `0061` | `0816` | pause(node or all, on/off) (`164h` counter) |
| `00af` | `087e` | fade(node, target (bit 7 = stop at end), ticks per step, step) |
| `00da` | `090e` | set node volume (`15Eh`, all mapped channels get ctrl 7) |
| `0016` | `091e` | set priority, re-sort, remap |
| `0116` | `08a2` | set hold value (`15Ah`) |
| `012a` / `0003` / `002a` | `09e7` / `09f1` / `09fb` | get signal (`158h`, FF = stopped) / cue count (`152h`) / position (ticks → min, s, ticks/2) |
| `0150` / `00ee` | `0a1c` / `0b04` | controller / pitch bend to one channel of a node from the game |
| `003f` | `0433` | restore a sound at its saved tick (replays silently with `cs:0388` set) |
| `0050`, `013f`, `00c9`, `017b` | `04c3`, `04da`, `0428`, `08ac` | master volume (fn 12), default reverb (fn 11), sound on/off (fn 13), mute/unmute all channels |
| — | `17de` (far) | **service**, registered as a timer client |

`play` is called as `play(node, 1)` by INTRO/PS (`1708:0008`): state `159h` = 2, which sets the
"locked" bit on every channel, so channels keep their own MIDI channel numbers. AP starts SNG sounds
with `play(node, 0)` (`3280:0a44`): channels are mapped from the highest free device channel down.

### Timing (Verified)

`snd_init` (`1593:0004`) installs the timer `05da:2374(13)`: PIT divisor `0x10000/13` = 5041 →
**236.69 Hz**, the old INT 8 is chained every 13th interrupt (18.2 Hz). The sound service is a timer
client called every **4th** interrupt (`05da:2307(1373:17de, 4)`): **59.17 Hz, 16.90 ms per tick** —
the SCI "60 Hz" tick. One delta unit = one service tick.

### Node (0x17A bytes, `1593:019c`) — offsets used by the module

| Off | Size | Field |
|---|---|---|
| 08 | far ptr | → +16Ah (the "handle"); `+16A` = resource data after `84 00`; `+166` = raw resource |
| 0C / 2C | u16[16] | channel position (0 = ended) / loop position |
| 4C / 6C | u16[16] | delay counter (8000h bit = inside an F8 run) / loop delay |
| 8C / 9C / AC | u8[16] | channel number (FF none, FE digital) / running status / loop running status |
| BC | u16[15] | pitch bend (14 bits) + sustain in bit 15, **by MIDI channel** |
| DA, E9, F8, 107, 116, 125, 134, 143 | u8[15] each | by MIDI channel: voices\|prio, modulation, pan, volume, program, sounding note, flags (1 locked, 2 not mapped), mute (low nibble ctrl 4Eh, high nibble mute-all count). Stride 15: channel 15 indexes the next table (Quirk, harmless in the data) |
| 152 / 154 / 156 | u16 | cue counter / tick / loop tick |
| 158 / 159 / 15A | u8 | signal (FF stopped) / state (1 play, 2 play locked) / hold value |
| 15B / 15C / 15D | u8 | fixed-priority flag / priority / loop flag |
| 15E / 15F | u8 | node volume (7Fh) / reverb (7F = default) |
| 160–163 / 164 / 165 | u8 | fade target, step ticks, counter, step / pause count / digital channel+1 |

Module globals (code segment): list of 16 node pointers sorted by priority, highest first (`018f`);
device channel map `020f[16]` (node index<<4 | MIDI channel, FF free); previous map `02df`/`029f`;
queued volumes `032f[16]` (sent 2 per tick, `1796`).

### Play (`0528`) and the device track (`1fef`)

The first play of a resource rewrites its header in place: the 16 channel offsets of the track whose
device byte equals the driver's play id become a `u16[16]` table at offset 0, priority byte at `20h`
(FF = none), marker `FC FD FE` at `21h`. Channels are then initialised from their preamble (above),
flags applied, the node inserted into the list and **remap** run.

### Service tick (`17de`)

`if busy: return`; remap if flagged; for each node (priority order, skipping paused): fade step,
then `1932`: tick+1; per channel: find its device channel in the map (not mapped → events are still
parsed but not sent), count the delay down or run events until the next non-zero delta; when all
channels ended: stop (remap next tick) or restart at the loop point. Then 2 queued volumes, then
driver fn 3.

What reaches the driver per event: note on/off (AL = device channel, CH = note, CL = velocity);
controller: volume is scaled by the node volume `((v+1)(nv+1) >> 8)·2 − 1` (`1fb5`, 127·127 → 127);
4Bh/4Eh also set the remap flag.

### Remap (`0c1e`, run on play/stop and when flagged)

Walk the nodes in priority order with the driver's voice budget (`cs:0378` = 9 for AdLib). For each
channel (not FF/FE/15, not flag 2, not muted): priority value = 0 for header priority 0 ("must
play") else `16 − prio + 16·node index`; take the channel's own number if locked and free, else the
highest free device channel in `[first, last]`; if there are no free channels or not enough voices,
must-play channels steal the mapped channel with the largest priority value (rolling the whole node
back if nothing can be stolen), other channels are skipped. Then device channels that keep their
owner keep their setup; every newly mapped device channel gets: ctrl 7Bh 0, ctrl 4Bh voices,
program, ctrl 7 scaled volume, ctrl 10 pan, ctrl 1, ctrl 40h, pitch bend, ctrl 4Eh (the sounding
note, ignored by AdLib); freed ones get ctrl 40h 0, 7Bh 0, 4Bh 0. The first node's reverb is sent
(fn 11). Faithful Python: `Sequencer.remap`.

## 4. Driver loading (Verified)

`RESOURCE.CFG` `soundDrv = NAME.DRV` → the name without `.DRV` is looked up in INTRO `DS:00C7`
(`{name, index}`): STD 0, TANDY3V 1, ADL 2, MT32 3, SNDBLAST 4, IBMPS1 5, PROAUDIO 7 (the usage text
also offers `-s<num>`, not traced). `16ac:000b(index, ovlfile)`: `"SSM:" + code[index & 7Fh] + ":"`
with codes `STD TAN ADL M32 SBL PS1 TAN PRO NLD MTB` (`DS:1EFA`), chunk loaded and unpacked from the
OVL (`1620:000e` → `15b5:0001`) into a far block and **called in place** (the drivers are position
independent, data CS-relative; no relocation). `1373:0075` → fn 0 → patch number p; if p ≠ FFh the
chunk `"SSM:%03d:"` (`DS:1E90`) is loaded, its SCI header skipped, and passed to fn 1
(`163c:0006`). Index 88h (NLD with bit 7) becomes 3 afterwards. `SBL`, `PRO` and `MTB` chunks do not
exist in the OVLs: Sound Blaster owners must pick AdLib (Likely: the installer lists the loose
`*.DRV` files and writes the chosen file name to `RESOURCE.CFG`, the game only uses the name).

The loose `Game/ADL.DRV` (v2.24, 9295 bytes) is a different build from `SSM:ADL:` (8070 bytes, no
version string): its fn 1 takes a length-prefixed patch, returns last channel 8, fn 3 (service) is a
`ret`, voice allocation uses a free-voice queue. **Not used by the game**; the port models `SSM:ADL:`.

### Driver header and calling convention (Verified for ADL, same header in all)

```
+00 E9 rel16         jmp entry                     +03 00
+04 21 43 65 87      signature 87654321h           +08 01 (sound driver)
+09 pstring id ("dude", "tnddrv", "audjoy", "stddrv")   pstring description
    98 BA DC FE      second signature, then u16 ?, u16 ? (ADL: 02 00 00 00)
ADL +33 u16 388h index port, +35 u16 388h status port, +37 u16 389h data port
```

Call: `lcall driver:0000` with **BP = function number** and the arguments in registers; the entry
(`143d`) saves flags/SI/DI/BX/DX/DS/ES, does `call [cs:1419h + 2·BP]`, restores, `retf`.

| Fn | ADL | Name | In | Out |
|---|---|---|---|---|
| 0 | 1f7d | PatchReq | — | AL = 3 (PATCH.003), AH = 1, CH = 0 (play id: AdLib track 00), CL = 9 (voices) |
| 1 | 1f2e | Init | ES:AX = patch data | reset chip, master volume 15; AX = 0, CL = 0, CH = 15 (device channels 0–15) |
| 2 | 15d6 | Terminate | | reset chip |
| 3 | 188f | Service | | once per tick: age of sounding voices + 1 |
| 4 | 145a | NoteOff | AL ch, CH note, CL vel | |
| 5 | 1490 | NoteOn | AL ch, CH note, CL vel | |
| 6 | ret | PolyAfterTouch | | |
| 7 | 14d8 | Controller | AL ch, CH ctrl, CL value | 7, 10, 40h, 4Bh, 7Bh handled |
| 8 | 1522 | ProgramChange | AL ch, CL program | |
| 9 | ret | ChannelAfterTouch | | |
| 10 | 1530 | PitchBend | AL ch, CH lsb, CL msb | |
| 11 | 15c5 | SetReverb | CL (FF = query) | AL = old (stored only) |
| 12 | 1595 | MasterVolume | CL 0–15 (FF = query) | AL = old |
| 13 | 1565 | SoundOn | CL 0/1 (FF = query) | AL = old |
| 14–16 | ret | SamplePlay / SampleEnd / SampleCheck | | |
| 17 | 1eb1 | AskDriver | AH = E0h/C0h/B0h + AL ch (+CH ctrl) | pitch bend / program / volume, pan, sustain, voices of a channel |

## 5. AdLib driver `SSM:ADL:` (Verified, model `AdlibDriver`)

OPL2 melodic mode only, 9 voices, 16 MIDI channels. Writes: index to 388h, 5 status reads, data to
389h, 35 status reads (`1b13`).

### Data (driver offsets)

| Off | Size | Contents |
|---|---|---|
| 0039 | u8[508] | block per quarter-semitone index (note·4 + bend) |
| 0236 | u16[508] | F-number per index (157h…2A4h per octave, 4 steps per semitone) |
| 0630 | u8[64] | velocity curve (velocity/2 → 0,12,13,…,63) |
| 0670 | u8[64] | volume curve (0,20,21,…,63) |
| 06B0/1/2 | u8 | reverb, sound on (1), master volume (15) |
| 06B3/C3/D3/E3/F3 | u8[16] | per channel: program, volume/2, pan, hold pedal, voices still owed |
| 0703 | u16[16] | pitch bend (2000h centre) |
| 0723 | u8[16] | last voice used by the channel (round robin) |
| 0733 / 073E / 0749 / 0754 | u8[9] | per voice: owner channel (FF free), note (FF silent), velocity/2, sustained |
| 075F | u16[9] | voice age (ticks since note on) |
| 0775 | u8[9] | instrument loaded in the voice (FF none) |
| 0780 / 0789 | u8[9] | voice → carrier / modulator slot; slot offsets `07A4`, slot → channel `07B6`, voice slot pairs `07C8`, slot is carrier `0792` |
| 07DA / 07E8 | 13 bytes | reset operator params (modulator / carrier) |
| 07F6 | 18 × 14 | operator shadow (13 params + waveform) |
| 08F2 | 2688 | patch bank (96 × 28) |
| 138A–1403 | u16[9] ×6 | per voice: carrier KSL, 63 − carrier TL, …, modulator KSL, 63 − mod TL; `13F8[9]` = modulator scaled by volume |

### Patch bank (`SSM:003:` / PATCH.003)

2690 bytes: 48 instruments × 28, `AB CD`, 48 more (fn 1 copies the second half only if the marker is
there). Instrument: modulator 13 bytes, carrier 13 bytes, modulator waveform, carrier waveform.
Operator bytes: KSL, MULT, FB, AR, SL, EG (sustain), DR, RR, TL, AM, VIB, KSR, ALG. Registers
(`1c20`/`1c69`): `20h` = AM·80h|VIB·40h|EG·20h|KSR·10h|MULT, `40h` = KSL<<6|TL, `60h` = AR<<4|DR,
`80h` = SL<<4|RR, `E0h` = waveform, `C0h+channel` (from the modulator only) = FB<<1 | (ALG == 0).
So ALG = 1 means FM (only the carrier follows the volume), 0 = additive (both do).

### Behaviour

* **Voices** belong to channels: ctrl 4Bh n (`1641`) gives the channel n voices from the free pool
  (voices beyond the pool are remembered as owed, `06F3`), taking back idle then sounding voices
  when n shrinks, then hands freed voices to channels that are owed some. Until a channel has
  received voices through 4Bh it cannot play (the sequencer sends 4Bh in every channel setup).
* **Note on** (`1490`): velocity 0 = note off; notes outside 12–107 ignored; velocity halved. The
  same note already sounding on the channel is retriggered on its voice. Otherwise `15da` takes the
  channel's next voice after the last one used that is silent; if all its voices sound, the
  **oldest** (age ≥, last one wins ties) is cut; if all are younger than one tick (age 0) the note is
  **dropped** (Quirk; e.g. 89 of 439 notes of QUIETNSN).
* **Voice on** (`17f9`): the channel's program is loaded into the voice only if it differs from the
  voice's current instrument (and sound is on): all operator registers are rewritten, with the
  patch's own TL. Then frequency + key on + volume (`18ab`).
* **Frequency** (`18ab`/`1958`): index = note·4 ± (|bend − 2000h| / 170), i.e. ±48 quarter-tones =
  ±12 semitones over the full bend range; index ≥ 508 → nothing is written. `A0h+v` = fnum low,
  `B0h+v` = key<<5 | block<<2 | fnum>>8.
* **Volume**: `x = ((chvol/2+1)·(velcurve[vel/2]+1)) >> 6`, `x = ((x & FFh)·(master+1)) >> 4`,
  `x = x − 1` if > 0, 0 if sound is off; `x = volcurve[x]`; carrier TL = `63 − x·(63 − patchTL)/63`
  (KSL kept); the modulator the same if the instrument is additive. Written on every note on,
  volume/pan/bend change and key off.
* **Note off** (`145a`): first voice of the channel with that note: sustained if the channel's hold
  pedal is down (released by ctrl 40h 0), else key off (`1865`: rewrites frequency/volume with key 0).
* **Ctrl 7Bh**: key off every sounding voice of the channel. **Ctrl 7** / **10**: store, rewrite all
  sounding voices of the channel (pan has no effect on OPL2). **Program**: stored, used at the next
  note on. **Pitch bend**: rewrites every voice of the channel.
* **Reset** (`1e6b`, fn 1/2): reg 01h = 0, every operator loaded with the reset params, BDh = 0,
  08h = 0, A0h–A8h/B0h–B8h = 0, E0h+ = 0, reg 01h = 20h (waveform select on).
* Quirks kept by the model: note dropped when every voice is younger than a tick; stride-14 operator
  shadow; C0h written only from the modulator slot; volume changes rewrite A0h/B0h too.

## 6. Renders (`python tools/aotpsnd.py all`, 106 sounds)

Every sound renders (`work/sound/render.txt`). The AdLib track of every sound is played as the game
plays it (SX: `play(node, 1)`, SNG: `play(node, 0)`, node volume 7Fh, bank loop flag, 59.17 Hz).
Looping sounds are cut after 2 restarts (≥ 8 s), then stopped (sequencer stop + remap) with a 1.5 s
tail. Music lengths: MENUS 78 s, FLIGHTDK 75 s, DEATH 21 s, BOARDINQ 42 s, ACETHEME 87 s, MEDAL
168 s, CAPTURE 49 s, NEWS 45 s, RUMORSJP 55 s, RUMORSUS 78 s, LANDOK 62 s, QUIETNSN 51 s, WARENDUS
67 s, WARENDJP 95 s, CREDITS 77 s. Effects are 1.5–10 s; sim 11 is a 25 s looped phrase; SNG 31 has
only a control channel (silent timer/signal). Notes dropped by the voice-age rule: ACETHEME 2, MEDAL
17, NEWS 6, RUMORSUS 56, LANDOK 3, QUIETNSN 89, CREDITS 3.

## Port notes

* Port the module as code, not data: `midi.s` (`1373`) is ~7 KB of assembly; `aotpsnd.Sequencer` is
  a line-by-line model (including the per-node byte layout, which has overlapping tables) and the
  DROs are its regression reference. Drive it at 59.17 Hz from the audio callback.
* Model the `SSM:ADL:` driver on top of Nuked-OPL3 in OPL2 mode; read the tables and the patch bank
  from the OVL at run time (`AdlibDriver` keeps its state in a copy of the driver image — the C port
  can do the same or use named arrays).
* Sounds are identified by (bank, id); the game-side callers (which id when) belong to the shell/sim
  specs. Signals (ch 15 `C0 0/1`) and loop points must be honoured.

## Open questions

* Listen to the DROs; confirm tempo (16.9 ms ticks) and instrument choice against DOSBox.
* Meaning of the 35–38 sim sounds and of the device tracks 06, 09, 16 (SCI1 ids: 06 Amiga?, 09 CMS?,
  16 ?); play ids of the other drivers (M32 expected 0Ch, STD 12h, TAN/PS1 13h).
* `-s<num>` option and whether INST.EXE ever writes `SNDBLAST.DRV` (→ no `SBL:` chunk → no sound).
* Fade/volume API callers (who fades music out) — shell/sim specs.
