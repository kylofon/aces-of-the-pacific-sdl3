# shell_data — PS.EXE game data, mission generation, hand-off files

Module owner: `shell_data`. Program: **PS.EXE** only (DGROUP `4D08`). Addresses as in `../RE_GUIDE.md`
(file segments, `SSSS:OOOO`); `DS:xxxx` = DGROUP offset; far data given as file segment (`4b4c:000e`; the
Ghidra decompile shows these +1000h, e.g. `0x5b4c`). Symbols: `shell_data_symbols.csv`.
Confidence tags: **verified** (read in the disassembly), **likely**, **guess**.

## Index

| Part | File | Contents |
|---|---|---|
| this file | `shell_data.md` | RNG, `file.c` (SIM.IN / SIM.OUT / roster / records / PRF), pilot record, SIM.OUT meanings, `TABLES.DAT`, mission structures in memory, `miss\script.c` (mission building helpers, **SCRIPT.DAT writer**, mission file → memory conversion), flight-plan messages (`1155`), hand-offs, open questions |
| missions | `shell_data_missions.md` | the mission-type modules `miss\s_*.c` (`3570`–`37fc`) |
| sys | `shell_data_sys.md` | `sys\*.c` + neighbours `1ed0`–`2316` (except `227c`): snario (mission file reader), historic, extens (table loader), ranks, helper (allocators), queue, threed, text tables |
| emd1 | `shell_data_emd1.md` | `emd\*.c` `2322`–`273b`: world database (TARGET/CARRIER/SHIPPATH), strings, aces, squadrons, lists |
| emd2 | `shell_data_emd2.md` | `emd\*.c` `2777`–`2b42`: aircraft, medals, flight, dates, campaign, missinfo, wldfgen, convoy, ship, formations, stations, ordnance |

Segments owned: `1193` (file.c), `1155` (fltplan messages, untagged, only used for mission texts),
`1ed0`–`2316` except `227c` (sys part), `2322`–`2b42` (emd parts, `24b7` RNG is specced here),
`3164` (script.c), `3555` (tables.c), `3570`–`37fc` (s_*.c).

Borland/volume RTL used (behaviour only; owner platform): `0000:0551` vol_fopen(name, mode) (volume or disk),
`0000:084b` fclose, `0000:08a0` fread(buf,size,n,fp), `0000:0dea` fwrite(buf,size,n,fp), `0000:0b5a` fseek,
`0000:2f26` fopen (disk only), `0000:343d` itoa, `0000:347f` ltoa/ultoa, `0000:34c3` memcpy, `0000:3508`
memset, `0000:358e` memmove, `0000:3e95` strcat, `0000:3f33` strcpy, `0000:3f95` strlen, `0000:4899` _fstrlen,
`0000:3e5c` sprintf, `0000:192a` SCOPY@ (struct copy, CX bytes), `0000:18f2` LXMUL@, `0000:198f` LDIV@,
`0000:1f3a` time.

---------------------------------------------------------------------------------------------------------

## 1. Random number generator (`24b7`, verified)

Additive lagged-Fibonacci generator (Knuth, lags 24/55), 16-bit words.

| Global | Size | Meaning |
|---|---|---|
| `DS:551E` | u16[56] | state table `rng_tab` |
| `DS:5590` | u8 | index j (starts 55) |
| `DS:5591` | u8 | index k (starts 24) |
| `DS:558E` | u16 | call counter mod 1024 `rng_calls` |
| far `4c91:0000` | u16[56] | initial table (constant, 0x70 bytes), see below |

```c
u16 rng_next(void)                       /* 24b7:000c */
{   int j = rng_j;                       /* sign-extended byte */
    rng_tab[j] += rng_tab[rng_k];        /* 16-bit wrap */
    if (++rng_j == 56) rng_j = 0;
    if (++rng_k == 56) rng_k = 0;
    if (++rng_calls == 1024) rng_calls = 0;
    return rng_tab[j];
}
void rng_seed(u16 s)                     /* 24b7:0070 */
{   _fmemcpy(&rng_tab, MK_FP(0x4c91,0), 0x70);   /* via 16e3:49c1 */
    rng_k = 24; rng_j = 55; rng_calls = 0;
    for (s %= 1024; s; s--) rng_next();
}
u16 rng_count(void)          { return rng_calls; }                 /* 24b7:00be */
int rng_below(int n)         { return n < 2 ? 0 : (long)(rng_next() & 0xFFF) % n; } /* 24b7:00c8 */
long rng_below_long(long n)  { if (!n) return 0; r = rng_next()&0xFFF; return ((u32)rng_next()<<16 | r)... } /* 24b7:00eb: LUMOD(rng_next():(r) , n) — unused (only 0151, itself uncalled) */
int rng_range(int lo,int hi) { return lo + rng_below(hi-lo+1); }   /* 24b7:0132, uncalled */
long rng_range_long(long lo,long hi)                                /* 24b7:0151, uncalled */
void rng_seed_time(void)     { rng_seed((u16)time(0)); }           /* 24b7:01d1 */
char rng_pick_weighted(int *pct, int n)                             /* 24b7:0180 */
{   int r = rng_below(100); if (r == 0) r = 1;
    int i = 1, lo = 0, hi = pct[0];
    while (i < n && (r < lo || hi < r)) { lo = hi; hi += pct[i]; i++; }
    return i - 1;
}
```

Notes: `rng_pick_weighted` tests `lo <= r <= hi` with **inclusive** bounds on both ends, so a value equal to a
cumulative boundary goes to the lower index; weights that do not sum to ≥ 99 leave the last index as the
fall-through (loop ends at `i == n`, returns `n-1`). Since `rng_seed` reduces the seed mod 1024, and seeds are
taken from `rng_count()` (0..1023), there are only 1024 distinct streams.

Initial table (`4c91:0000`, u16): 56611 38195 62413 19394 63458 41695 43632 24746 5195 35144 6442 27405 40459
64497 34311 18013 60148 27133 27716 6951 56177 58255 43956 56391 4062 19854 64637 36152 22856 58223 43554
12070 17402 46501 8427 60805 62915 33183 11676 45677 59691 38869 15777 35309 58356 29877 44 54111 15112 3573
62078 49776 9609 11915 25426 55853.

### 1.1 Seeding and every call site

Seeding (verified):
* `0607:011d` (shell start/career screen) and `0542:01c4` (return from the sim): `rng_seed_time()`; then
  `DS:42C1 = rng_count()` (0542) — the "career day" seed.
* `0787:0181` (career flight deck, "fly mission"): `rng_seed(DS:42C1)`, then `3164:0944` (mission choice) and
  `3164:0a27` (build). Re-entering the flight deck therefore re-creates the same career mission for that day.
* `3164:0b49` (setup of every generated mission): `RSEED` = `DS:00C5` (debug override, 0 in the image, no writer
  found) if > 0, else `rng_count()`; stored in header +0A (`DS:6275`); **draws before the reseed** (single
  missions: `3164:05f9` `rng_below(nfiles)`, `3164:07ef` `rng_below(4)`; both: `rng_pick_weighted(TABLES
  671E+mtype*18, 9)`) use the running stream; then `rng_seed(RSEED)`; everything after (wind and the whole
  mission) is a function of RSEED and the data. Single missions (`100e:09f1`) run on the stream left by the
  last time seed.

Call sites (callers of `24b7:*`, complete list from the index):

| Function | Calls |
|---|---|
| `rng_next` direct | `0b16:013a`, `0ed9:02d2` (shell_ui screens) |
| `rng_below` | shell_ui `0874:0003`, `0c1d:03c6`; `21f4:0245` (sys part); script.c `030b` (100), `05f9` (n files), `07ef` (4), `0fb2` (n−1), `14bc` (n−1), `1a38` (n); every mission module (missions part) |
| `rng_pick_weighted` | `3164:00de` ({20,80},2), `0b49` (671E row 9; 66BE row 4), `0c89` (6646 row 4, per plane), `0f39` ({30,50,20},3), `0fb2` (3), `14bc` (4); `3641:0005`, `36dd:000e`; emd: `2624:035d`, `28e4:0270/03a2/04da/0612`, `2968:015b`, `29c2:01a2/01f8/024e`, `2ab3:03a7` (see emd parts) |

---------------------------------------------------------------------------------------------------------

## 2. `shell\file.c` (segment `1193`, 25 functions)

File names: `file_name(base, n, ext)` builds `<base>[<n>].<ext>`; when no volume file was found at start-up
(`DS:0DFF` == 0, set to 1 by the volume scanner `0000:11..`) the name becomes `<ext>\<base><n>.<ext>` (the
developers' per-extension directories). Files written to the work directory are prefixed with `DS:40CA`
(the `-n<dir>` path).

| Address | Name | Signature | Behaviour | Conf. |
|---|---|---|---|---|
| 1193:0006 | enddate_get | far int(char campaign, char force) | if `DS:0B6C`==0 or force: read u16 from `enddate<campaign>.dat` into `DS:0B6C` (fatal if missing); return it | verified |
| 1193:0084 | service_load | far void() | `memset(DS:49CE, FF, 0x16)`; table `service.dat` via `2008:0aec("service","dat",2,0,0x11,1,…)`; for i < count: `DS:49CE[i] = *(u16*)2008:12eb(t,i)`; `2008:0bbd(t)` | verified |
| 1193:0115 | file_name | far char*(char *base, int n, char *ext) | `strcpy(DS:4B72, base)`; if n ≥ 0 `strcat(itoa(n))`; `strcpy(DS:4B72, file_ext(DS:4B72, ext))`; return `DS:4B72` | verified |
| 125a:000f | file_ext (shell_ui seg, listed here for the rule) | char*(char *name, char *ext) | `strcat(name,"."); strcat(name,ext)`; if `DS:0DFF`==0: `strcpy(DS:4B94,ext); strcat(DS:4B94,"\\"); strcat(DS:4B94,name)`, return 4B94; else return name | verified |
| 1193:0176 | file_read_n | far int(void *buf, int size, int n, char *name) | `vol_fopen(name,"rb")`; 0 → return 0; `fread(buf,size,n)`; close; return items | verified |
| 1193:01b7 | file_read | far int(char *name, void *buf, int size) | as above, `fread(buf,1,size)`, returns bytes (0 if no file) | verified |
| 1193:01ff | file_write | far void(char *name, void *buf, int size) | `fopen(DS:40CA+name,"wb")` (disk), fatal line 0xF5 if NULL; `fwrite(buf,1,size)`; close | verified |
| 1193:027a | control_prf_read | far void() | `file_read("control.prf", DS:43B0, 0x25)`; if ≠ 37 bytes: `shell_fatal(…,0x109,"size of control")` (continues if it returns), if 0 bytes `DS:43B0 = DS:43B2 = 0`; `DS:43B6..43BC` = 1 (7 bytes). Then if `DS:43BD == DS:43C1` or `DS:43C3 == DS:43C7`: joystick calibration reset X/Y min −127, centre 0, max 127 | verified |
| 1193:0306 | control_prf_write | far void() | `file_write("control.prf", DS:43B0, 0x25)` | verified |
| 1193:031e | roster_read | far void() | `roster.dat`: u16 `DS:4A18` count (0 if no file); count × 122-byte records into far `4b4c:000e` via `fread_chunked(…,0x7A,count)`; u16 len (fatal if <0 or > 0x200); len bytes into `DS:47CE` (fatal if short) | verified |
| 1193:0421 | roster_write | far void() | writes `roster.dat` through `vol_fopen(…,"wb")` (fatal 0x15D): u16 count, each record (via a 122-byte stack copy) summing record +0x79, u16 sum, sum bytes of `DS:47CE` | verified |
| 1193:050d | topace_read | far void() | `topace.dat`: u16 `DS:4341` (0 if absent); `fread(stack, 0x7A, n)`; copy each to far `4a08:033b + i*0x7A` | verified |
| 1193:05b8 | topmiss_read | far void() | `topmiss.dat`: u16 `DS:433F`; n × 55 bytes → far `4a08:0115 + i*0x37` | verified |
| 1193:065c | topace_write | far void() | clamp `DS:4341` ≥ 0; write u16 n + n × 122 | verified |
| 1193:0727 | topmiss_write | far int() | if `DS:433F` ≥ 11 → `shell_fatal(0x1DA)`; if n ≠ 0 write u16 n + n × 55 (nothing written when n = 0) | verified |
| 1193:0818 | prf_read16 | far void(char *name, void *buf) | `file_read(name, buf, 16)`; if 0 → `0a8d:0192(buf,0)` (realism defaults, shell_ui) | verified |
| 1193:0840 | prf_write16 | far void(name, buf) | `file_write(name, buf, 16)` | verified |
| 1193:0856 | real_prf_write | far void() | if SIM.IN mode `DS:4B87`==1: `creal.prf` ← `DS:47A9` (career pilot's realism), else `mreal.prf` ← `DS:4357` | verified |
| 1193:0881 | shell_data_load | far void() | roster_read, control_prf_read, strings_load (08b9), `tables_load` (3555:0133), service_load, topace_read, topmiss_read | verified |
| 1193:08a4 | shell_data_save | far void() | roster_write, control_prf_write, topace_write, topmiss_write (called by `shell_exit`) | verified |
| 1193:08b9 | strings_load | far void() | `24e3:0268("strings_.dat")`, `24e3:05b9(DS:5796,3,2)`, `24e3:0678()`, `24e3:0436()` (emd1 part) | verified |
| 1193:08f6 | sim_in_read | far int() | `file_read("sim.in", DS:4B86, 13)`; 0 bytes → fatal 0x28E | verified |
| 1193:093e | sim_in_build_write | far void() | §3.1 | verified |
| 1193:09fe | sim_out_read | far int() | `file_read("sim.out", DS:4227, 36)`; ≠ 36 → fatal 0x2CC | verified |
| 1193:0a46 | fread_far | far u16(void far *dst, u16 size, u16 n, FILE *fp) | reads in pieces of `128/size` items into `DS:419A`, copies bytes to dst; returns items read (stops at a short read) | verified |
| 1193:0ad2 | config_write | far void() | writes `resource.cfg` (platform owns; = INTRO `038e:04d6`) — not specced here | — |

`shell_fatal` = `227c:0143(file, seg, line, msg)` (shell_ui; prints "A SHELL system error…", the file/line, and
RSEED/MODE/MTYPE/DATE/WORLD/PLYR SINDEX (`DS:62DB`)/ENEMY SERVICE (`DS:6355`), waits for a key, `exit(0)`).

---------------------------------------------------------------------------------------------------------

## 3. The hand-off files (settled from the PS side)

### 3.1 `SIM.IN` (13 bytes at `DS:4B86`, writer `1193:093e`, verified)

```
SCOPY 8 bytes DS:0B6E -> local  {00 01 02 04 08 10 20 40}   (service -> name-list bit)
+00 u8  = kind==1 ? DS:4774 (career pilot's roster index) : FF
+01 u8  mode = kind 2 -> 0, 3 -> 2, 4 -> 3, else kind (0 or 1)
+02 u8  = header+01 mission type
+03 u8  (not written here; flymiss2 100e:0648 sets 4 or DS:4B3D before) — training sub-type: debrief uses
        group 10 when mission type 5 and +03 == 4, else group 11 (§3.4)
+04 u16 = header+08 (always 50 for generated missions)
+06 u8  = header+02 area
+07 u8  = kind 1 or 2: DS:4B8D |= bit[2008:000e()] (bit of the active extension, extens.c); else header+06
        (NB: the kind-1/2 branch ORs into the old +07 value, it does not take header+06)
+08 u8  = flight[0][0]+00 service of the player
+09 u8  = DS:6355 = flight[1][0]+00 enemy service
+0A u16 = DS:62DD player's aircraft type
+0C u8  never written
```

`file_write("sim.in", DS:4B86, 13)`. The shell re-reads it after the sim (`0542:01c4`) to know what was flown.

### 3.2 `SIM.OUT` (36 bytes at `DS:4227`), meanings settled from the PS readers

| Off | Type | Meaning (PS use) | Conf. |
|---|---|---|---|
| 00 | u16 | **mission result code**, 1-based index of the debrief sentence of the mission type (`DEBRIEF.DAT`, group per type §3.4); success = bit (code−1) of `DS:0512[group']` (§3.4). FFFF = no result (fatal 0x140 in `0542:01c4`) | verified |
| 02 | u8 | fate flags: **1 killed** (career status 3, `DISPLAYS` 1–3), **2 captured** (status 1 = POW, career date = `enddate`), **4 wounded** (hospital: date +90 days `2624:043a(squad,&date,date+90)`, Purple Heart / wound badge eligibility `27f0:013c`), **10/20/40 friendly fire** (aircraft / ship / ground target; any → pilot +0x40 incident count +1; 3 incidents → status 2 "cook") | verified |
| 03 | u8 | 0 (unused by PS) | verified |
| 04 | u16 | **aircraft lost** (debrief "AIRCRAFT LOST"; kept in TOPMISS +1A) | verified |
| 06 | u16[4] | not read by PS | verified |
| 0E | u16 | if 1: the career date jumps forward to the next campaign date (`0542:0086`, `0874:1113`) and the idle-days processing `0874:0ec5` is skipped — likely "mission ended without returning to base normally / time passed" | likely |
| 10 | s16 | player ground strikes | verified |
| 12 | s16 | player ships hit | verified |
| 14 | s16 | player ships sunk | verified |
| 16 | s16 | player aircraft shot down | verified |
| 18..1E | s16×4 | same four for the player's flight | verified |
| 20 | u16 | **merit points** (added to pilot +0x69, compared with rank thresholds `225d:0128` for promotion `050c:0147`; TOPMISS +16) | verified |
| 22 | s16 | **mission score** (added sign-extended to pilot +0x65 u32; TOPMISS +12 u32 and +18) | verified |

Debrief screen (`MISSDEBR.SCD`): MISSION SCORE = +22, AIRCRAFT LOST = +04; PERSONAL / FLIGHT columns:
AIRCRAFT +16/+1E, SHIPS HIT +12/+1A, SHIPS SUNK +14/+1C, GROUND STRIKES +10/+18, TOTAL STRIKES
(+12)+(+10) / (+1A)+(+18) (`0637:060e` builds 12 longs at `DS:426E`).

Career accumulation (`0542:0180` → `011a`, `0168`, verified): pilot +0x6B air += +16; +0x6D sunk += +14;
+0x6F ground += +10; +0x3E victories += +16 + +14; +0x71 += +1E; +0x73 += +1C; +0x75 += +18 (flight ships
hit +1A is not accumulated); +0x65 (u32) += (s32)+22; +0x69 += +20; +0x30 missions += 1; +0x32 successful
missions += success(mtype, +00).

### 3.3 Career status after a mission (`0542:000a`, verified)

`DS:4778` (pilot +0x24): +02 bit0 → 3 (killed); else bit1 → 1 (captured; `DS:477B = DS:477F =
enddate_get(campaign,1)`); else if incidents `DS:4794`==3 → 2 (grounded as cook). 0 = active.

### 3.4 Result → debrief group and success table (verified)

`0637:069e` group g from mission type `DS:4B88`: 0→0, 1→1, 2→2, 3→3, 4→4, 5→(SIM.IN+03==4 ? 10 : 11),
6→5, 7→6, 8→8, 9→9, 10→7 (kamikaze sentences); sentence = `24e3:04b4(g, result−1)` of `debrief.dat`
(training: from `optional.dat`).

Success (`0542:004b(mtype, result)`): if mtype == 8 and result > 8 → mtype 9, result −= 8; else if mtype > 8 →
mtype+1; return `DS:0512[mtype] & (1 << (result−1))`. `DS:0512` = `28 2C E0 16 1F 00 0B 0F 8A 4A 3C 0F`
(index 0..11). E.g. type 0 (ace duel) 0x28 = results 4 "You shot down the respected %j" and 6 "%j did not
survive the dogfight".

---------------------------------------------------------------------------------------------------------

## 4. Pilot record (122 bytes) and records files

In memory: roster far array `4b4c:000e + i*0x7A` (count `DS:4A18`, max 13: `0ed9:0347`/`0f67:00f9` refuse at
> 12); the **current career pilot** is copied to `DS:4754..47CD` (`0f67:0001` copies back). Offsets
(record-relative; `DS` = 4754 + off). Verified by users unless marked.

| Off | DS | Type | Meaning |
|---|---|---|---|
| 00 | 4754 | char[16] | pilot name (entered with max 15 chars, `2f7f:0143(0,4754,15,…)`) |
| 10 | 4764 | char[16] | second text: shown while active instead of the status text (`13be:0161`); set by `0f67:00f9` (pilot transfer/copy) — likely assignment / unit name |
| 20 | 4774 | u8 | roster index (checked == position, fatal 0x79) |
| 21 | 4775 | u8 | side group = `0f67:02ed(service)` |
| 22 | 4776 | u8 | service code (0..10) |
| 23 | 4777 | u8 | rank (index for `ranks.dat`, `225d`) |
| 24 | 4778 | u8 | status 0 active, 1 POW, 2 cook, 3 KIA (§3.3); `DISPLAYS` table 1 text when ≠ 0 |
| 25 | 4779 | u8 | campaign index (`date<n>.dat`, `enddate<n>.dat`, `1f85:0833` extension) |
| 26 | 477A | u8 | unknown |
| 27 | 477B | u16 | date (day number) used for the next mission / squadron look-ups |
| 29 | 477D | u16 | second date parameter for `2624:035d/03fb` (career mission choice) — likely |
| 2B | 477F | u16 | current career date (shown on the roster) |
| 2D | 4781 | 3 bytes | unknown |
| 30 | 4784 | u16 | missions flown |
| 32 | 4786 | u16 | successful missions |
| 34 | 4788 | u16 | counter incremented by `0874:1113` (days/turns passed) — likely |
| 36 | 478A | u16 | aircraft type of the squadron (`2624:0219`) |
| 38 | 478C | u16 | station (`2624:0256`; name `2a85:027c`) |
| 3A | 478E | u16 | squadron id (FFFF none) |
| 3C | 4790 | u16 | campaign event/progress index (`287b:03e1/0389/0439/062a`) |
| 3E | 4792 | u16 | victories (air + ships sunk) used by medal thresholds |
| 40 | 4794 | u8 | friendly-fire incidents |
| 41 | 4795 | u8[20] | medals awarded (1 = awarded), `050c:0035` |
| 55 | 47A9 | 16 bytes | career realism settings (`creal.prf` image) |
| 65 | 47B9 | s32 | total score |
| 69 | 47BD | u16 | merit points (promotion) |
| 6B | 47BF | u16 | aircraft shot down |
| 6D | 47C1 | u16 | ships sunk |
| 6F | 47C3 | u16 | ground targets |
| 71 | 47C5 | u16 | flight aircraft |
| 73 | 47C7 | u16 | flight ships sunk |
| 75 | 47C9 | u16 | flight ground targets |
| 77 | 47CB | u16 | offset of this pilot's event list in the roster text blob `DS:47CE` |
| 79 | 47CD | u8 | length of that list |

Roster text blob (`DS:47CE`, ≤ 0x200 bytes, saved after the records): per pilot a list of bytes = career event
letters already shown (`0f67:021a(c)` tests membership, `0f67:0252(c)` inserts at the front and shifts the
following pilots' +0x77; `0f67:0024` deletes a pilot and compacts). `ROSTER.DAT` = u16 n, n × 122, u16 len,
len bytes. `TOPACE.DAT` = u16 n (≤ 10), n × 122 (same record).

**TOPMISS record (55 bytes, far `4a08:0115`; built at `DS:4308` by `0874` case 2, restored by `09a9:03e6`):**
+00 char[16] name, +10 u16 aircraft type, +12 s32 score (sort key, `09a9`), +16 u16 SIM.OUT+20, +18 s16
SIM.OUT+22, +1A u16 SIM.OUT+04, +1C s16[4] SIM.OUT+10..16, +24 s16[4] SIM.OUT+18..1E, +2C u16 SIM.OUT+00,
+2E u8 side group of the service, +2F u8 SIM.IN+08, +30 u8 rank of the service (`225d:018d`), +31 u8 SIM.IN+09,
+32 u8 SIM.IN+01, +33 u8 SIM.IN+02, +34 u8 SIM.IN+03, +35 u16 date.

`CONTROL.PRF` (37 bytes, `DS:43B0`): +00 u16 control device (index into the name table `DS:0B76` for
`resource.cfg`), +02 u16 second device (`DS:0B7E`), +04 u8, +05 u8 (written as numbers to resource.cfg), +06..0C
u8 toggles (default 1), +0D..+18 s16 joystick X min/centre/max, Y min/centre/max (defaults −127/0/127),
+19..+24 unused. `MREAL.PRF` (`DS:4357`) / `CREAL.PRF` (pilot +0x55): 16 bytes realism (field order: shell_ui).

---------------------------------------------------------------------------------------------------------

## 5. `TABLES.DAT` (`miss\tables.c`, `3555`, verified)

`tables_load` `3555:0133` opens `tables.dat` (fatal 0xAE) and reads, in order (functions `000f`, `003c`,
`0068`, `0094`, `00c1`, `00ee`, `011a`):

| Dest | Shape | Contents (shipped file, 612 bytes) | Used by |
|---|---|---|---|
| `DS:671E` | 10 × s16[9] | per mission type weights of header +0E: 0 `25 25 25 25 0 0 0 0 0`, 1 same, 2 `20 20 20 20 0 0 0 0 20`, 3 `20 20 20 0 0 0 0 20 20`, 4 `20 20 15 20 0 0 0 0 25`, 5 `25×4 …0`, 6 `20 20 20 10 0 0 0 10 20`, 7 `30 30 30 10 0…`, 8 `20 20 20 20 0 0 0 0 20`, 9 `15 15 15 15 15 0 0 10 15` | `3164:0b49` |
| `DS:66BE` | 12 × s16[4] | per month wind weights (still, light, strong, stormy): Jan/Feb/Dec `10 30 30 30`; Mar–May, Sep–Nov `20 40 40 0`; Jun–Aug `40 40 20 0` | `3164:0b49` |
| `DS:6646` | 5 × s16[4] | per pilot-quality class, AI skill 0..3 weights: `50 40 10 0`, `40 50 20 0`, `20 50 30 0`, `10 40 40 10`, `0 30 40 30` | `3164:0c89` |
| `DS:65CE` | 10 × s16[6] | per mission type "new aircraft type" pools per slot (0..2 side 0, 3..5 side 1): `2 0 0 3 0 0`, `2 0 0 3 0 0`, `2 0 1 2 2 1`, `2 0 0 3 1 1`, `2 0 0 2 3 0`, `2 2 0 3 0 0`, `2 2 0 3 0 0`, `2 0 0 3 2 0`, `2 1 0 3 0 1`, `2 1 0 3 0 1` | copied to `DS:61D5` by `3164:09bd` (11 rows: row 10 = `50 40 10 0 40 50` from 6646) |
| `DS:6556` | 5 × s16[12] | per aircraft class (`2777:0204`), 4 × 3 ordnance choices: `0 0 0 4 5 5 4 5 5 4 4 4` / `0 0 0 1 4 1 4 5 5 4 4 4` / `0 0 0 2 4 2 2 4 5 2 2 2` / `0 0 0 3 3 1 3 3 3 3 3 3` / `7 7 7 8 9 9 8 9 9 8 8 8` | `2ab3:03a7` (emd2) |
| `DS:652E` | 5 × s32[2] | per aircraft class (`2777:02f8`) altitude band: (8000,16000) (28000,36000) (56000,64000) (88000,96000) (108000,116000) (world units; the sim's altitude unit — likely ¼ ft) | mission modules |
| `DS:651E` | s32[4] | per flight role category (flight +02): 40000, 24000, 60000, 48000 (altitudes) | missions part |

---------------------------------------------------------------------------------------------------------

## 6. Mission data in memory (verified)

`3164:09bd mission_reset`: `memset(DS:6261, 0, 700)` (clears `6261..651C`: counts, header, flights,
convoys, places), `memset(DS:625A, 0, 2)` (only 2 of 7 bytes), copy 11 × 12 bytes `DS:65CE → DS:61D5`,
`DS:6259 = 0`, `DS:6271 = 0`, `DS:626D = FF`.

| Global | Type | Meaning |
|---|---|---|
| `DS:6259` | u8 | number of aircraft types in `DS:625A` |
| `DS:625A` | u8[7] | aircraft types already used (`3164:0206`) |
| `DS:6261` | u16[3] | flights per side (0 player's side, 1 enemy, 2 third party, e.g. escorted bombers) |
| `DS:6267` | u16 | places in `DS:64B1` |
| `DS:6269` | u16 | convoys in `DS:6475` |
| `DS:61D3` | near ptr | u8[n_aces] ace-used flags (malloc'ed by `0a27`) |
| `DS:61D5` | s16[11][6] | pools (TABLES) |
| `DS:61A2` | s16[11] | per player waypoint the message index (from a mission file, `3c1a`) |
| `DS:61B6..61CE` | | mission-file loader tables, §9 |

**Header `DS:626B` (90 bytes = SCRIPT.DAT type-0 record):**
+00 `626B` kind (0 single/generated, 1 career generated, 2 historical file, 3/4 recorder),
+01 `626C` mission type (0 DACE … 9 GRND; 10 appears only via the debrief tables), +02 `626D` area,
+03 `626E` (0 set by some modules; unknown), +04 `626F` wind 0..3, +05 `6270` variant (modules:
`rng_below(3)`), +06 `6271` name-list mask, +07 unused, +08 `6273` u16 = 50 (set after each build),
+0A `6275` RSEED, +0C `6277` date, +0E `6279` condition index from `DS:671E` weights (values 5..7 forced to 1;
AP meaning: sim_flow), +10..+59 not written by the generator (zero).

**Flight `DS:62C5 + side*0x90 + i*0x24`** (4 per side; see also the field users):

| Off | DS (s0 f0) | Type | Meaning | → SCRIPT |
|---|---|---|---|---|
| 00 | 62C5 | u8 | service code | aircraft +01 |
| 01 | 62C6 | u8 | `280a:021b(service, role, date)` (formation, emd2) | group +01 |
| 02 | 62C7 | u8 | role category 0..3 (`3164:00de`) | — |
| 03 | 62C8 | u8 | loadout (`2ab3:03a7`) | aircraft ordnance |
| 04 | 62C9 | u8 | 1 (`0c89`) / 4 / 2 by modules | group +03 |
| 05 | 62CA | u8 | callsign/heading byte (modules put a heading from `2b1f:00b4`; files: `'@'+n`) | group +04 |
| 06 | 62CB | u8 | home is a carrier (1) / land base (0) | group +05 |
| 07 | 62CC | u8 | 0 for side 0 flight 0, else 3 (modules may override) | group +02 |
| 08 | 62CD | u8 | target reference kind: 0/1 place index, 2 convoy index | group +06 |
| 09 | 62CE | u8 | | group +1E |
| 0A | 62CF | u8[4] | per plane: 0..3 AI skill, 4 player, FF ace | aircraft +02 |
| 0E | 62D3 | u16[4] | ace id per plane | aircraft +02 |
| 16 | 62DB | u16 | squadron (FFFF none) | — |
| 18 | 62DD | u16 | aircraft type (stored from a sign-extended char) | aircraft +00 |
| 1A | 62DF | u16 | number of planes | group +0A |
| 1C | 62E1 | u16 | number of waypoints | group +1A (−1) |
| 1E | 62E3 | u16 | home place / carrier convoy index | group +08 |
| 20 | 62E5 | u16 | target index | group +14 |
| 22 | 62E7 | near ptr | waypoints, 12 bytes each: s32 x, s32 z, s32 altitude | waypoint records |

Side 1 flight 0: `6355` service … `636B` squad, `636D` type, `636F` count, `6371` nwp, `6377` wp ptr; side 2
flight 0 at `63E5`.

**Convoy `DS:6475 + i*0x14`**: +00 u8 service, +01 u8 kind (0x18 for a carrier group), +02 u8 name/type
index (fltplan `%a` table 0x17), +03 u8 callsign, +04 u8[8] ship types, +0C u16 world record index, +0E u16 ship
count, +10 u16 waypoint count (always 1 for generated), +12 near ptr waypoints.

**Place `DS:64B1 + i*0x12`**: +00 u8 class (`3164:00aa`), +01 u8 world target kind (0x0D unknown), +02 u8
service, +03 u8 flag (player's objective/home), +04 u16 world record index, +06 12-byte position.

`3164:00aa target_class(kind)`: kind < 2 → 0; 2..6 → 1; 7 → 2; 8..11 → 3; else FF.

---------------------------------------------------------------------------------------------------------

## 7. `miss\script.c` — mission building helpers (`3164`)

### 7.1 Entry points

| Address | Name | Signature | Behaviour | Conf. |
|---|---|---|---|---|
| 3164:0a27 | mission_build | far void(char type, char service, char kind) | `DS:61D3 = malloc(n_aces)` (`2550:000e`), zero it; switch type (table `CS:0B35`): 0 `3570:0003`, 1 `35b3:000f`, 2 `35ed:0000`, 3 `3641:0005`, 4 `36ab:0001`, 5 nothing, 6 `36dd:000e`, 7 `3769:0866`, 8 `372e:000c`, 9 `37fc:0005`, other → fatal 0x28D; each called `(service, kind)`; then `DS:6273 = 50`, `mission_player_slot()`, free `DS:61D3`. (Two `cmp [kind],1` with no effect: debug leftovers.) Callers: career `0787:0181` (type from `3164:0944`, service `DS:4776`, kind 1), single `100e:09f1` (`DS:4B2F`, service, 0) | verified |
| 3164:0944 | career_pick_mission | far char() | `m = 2624:035d(DS:478E squad, DS:477B, DS:477D)`; if −1: `h = 2624:03fb(same)`, load `MISS<h>.dat` via `1f06:015c(name)`, `1f06:0269()`, `1f06:0782()`, kind = 2, return h; else kind = 1, return m (a mission type) | verified |
| 3164:0005 | mission_free | far void() | for each side and flight with waypoints: free `+22`, zero `+22`, `+1C`; same for convoys (+12, +10) | verified |

### 7.2 `3164:0b49 mission_setup(char service)` (verified; RNG order matters)

```
si = 0
if kind == 0:
    RSEED = DS:00C5 > 0 ? DS:00C5 : rng_count()
    single_pick_context(service)          /* 07ef: sets DS:62DB squadron, DS:6277 date (RNG before reseed) */
    si = DS:62DB
    DS:636B = DS:63FB = FFFF              /* side-1 and side-2 flight 0 without squadron */
    DS:6279 = rng_pick_weighted(&DS:671E[mtype*9], 9); if (6279 > 4 && 6279 != 8) 6279 = 1
elif kind == 1:
    RSEED = rng_count(); DS:6277 = DS:477F; si = DS:62DB = DS:478E
    DS:636B = DS:63FB = FFFF
    DS:6279 = rng_pick_weighted(&DS:671E[mtype*9], 9)       /* no 5..7 -> 1 clamp here */
rng_seed(RSEED)
date_split(DS:6277, &d)                   /* 284f:0131: d[0] = month 0..11 */
DS:626F = rng_pick_weighted(&DS:66BE[d[0]*4], 4)             /* wind */
DS:626D = station_area(squad_station(si, DS:6277))           /* 2a85:0127(2624:0256(si,date)) */
```

Kinds other than 0/1: only the reseed/wind/area part runs (with the old RSEED).

`3164:07ef single_pick_context(service)` (verified): `fp = single_open(service, &n)` (05f9); n > 36 → fatal
0x1C3; `r = rng_below(4)`; read 6-byte records `{u16 mtype, u16 squadron, u16 date}` until n is exhausted,
taking the (r+1)-th whose mtype == `DS:626C`; if not found → fatal 0x1CB; `DS:62DB = squadron`, `DS:6277 = date`;
close.

`3164:05f9 single_open(char block, int *n)` (verified): `2008:00a8(fp[9], "single", "dat")` opens up to 9
files (`single.dat` + one per installed extension, `single1.dat` = 1946 add-on); for each open file: skip
`block` blocks (`u16 cnt` + fseek `cnt*6`, fatal 0x190/0x193 on errors), read the block's `u16 cnt`, count
files with cnt ≠ 0 (none → fatal 0x19F); `k = rng_below(nonempty)`; take the k-th non-empty file, close the
others, `1f85:0833(k)` (select that extension), `*n = cnt`, return fp.

`SINGLE.DAT` (SHELL1, 982 bytes): 11 blocks (one per service code 0..10; 5..10 empty) of u16 n (32) + n ×
{mtype, squadron, date}: 4 entries for each of mission types 1–4, 6–9 (types 0 and 5 have none).

### 7.3 Flight creation

`3164:0c50 enemy_service(service)` → `28e4:0612(28e4:0237(DS:626D), 0f67:02ed(service), DS:6277)` (missinfo,
emd2): the opposing service for area/date.

`3164:0c89 add_flight(char service, char side, char mode)` (verified):
```
n = (char)DS:6261[side]; f = &flight[side][n]; date = DS:6277
sq = f->squad (u16, preset by the caller: FFFF or a squadron)
f->service = service
if sq < 0:
    role = pick_role(side, mode, service, n)                   /* 00de */
    areaIdx = -1; for i < 2968:00f9(): if 2968:010e(i) == DS:626D { areaIdx = i; break }
    type = 2968:015b(areaIdx, service, role, date)             /* wldfgen: aircraft for area/date */
else:
    type = 2624:0219(sq, date); role = 2777:0204(type)
type = reuse_type(type, mode, n, side)                          /* 0206 */
f->role = role; f->type = (s16)(char)type
planes = 280a:0110(service, role, date); f->planes = (u16)(char)planes
cls = sq >= 0 ? 2624:00f6(sq) : 2968:0313(areaIdx, service, date)   /* pilot quality 0..4 */
aces = role == 0 ? assign_ace(planes, side, n) : 0              /* 030b */
for i < planes: if aces { f->skill[i] = FF; aces-- } else f->skill[i] = rng_pick_weighted(&DS:6646[cls*4], 4)
f->b01 = 280a:021b(service, role, date)
f->loadout = 2ab3:03a7(mtype, type, 0, side)
if side == 0 && n == 0: DS:62CC = 0 else f->b07 = 3
f->b04 = 1; DS:6261[side] = n + 1
```
(the `b04` write uses the offset computed for the player when side 0 flight 0, i.e. always the new flight.)

`3164:00de pick_role(side, mode, service, n)` (verified): mode 2 → `rng_pick_weighted({20,80},2)` selects
mode 0 or 1; mode 0 → role 0 (fighter). Else `a = 28e4:0237(area)`, `c = 28e4:0270(a, service, date)`;
if mtype == 9 or c == 1: `f->b08 = 1`, `role = 28e4:03a2(a, service, date)`, and for kind 0 repeat 03a2 while
role == 0; elif mtype == 8 or c == 0: `f->b08 = 2`, `role = 28e4:04da(a, service, date)`, kind 0: repeat
**03a2** (not 04da) while role == 0; else role stays FF.

`3164:0206 reuse_type(type, slot, n, side)` (verified): if side == 1, or mtype == 7 and side == 2: slot += 3.
If `DS:61D5[mtype][slot] == 0` and `DS:6259 < 7`: return the first type t of `DS:625A[0..6]` with
`2777:012f(t, flight[side][n].service) != 0` and `2777:0204(t) == flight.role`; none → return −1 (0xFF).
Else: if type already in `625A[0..6259]` (compares `2777:0252` result) return it; else pool−−, append type,
`6259++`, return type. (NB the list scan uses `<=` count and `2777:0252`'s AL, as decompiled.)

`3164:030b assign_ace(planes, side, n)` (verified): builds the list of aces (index 0..`2550:000e`) that are
alive (`2550:0023`) and match: if the flight has no squadron: same service (`2550:01b2`) and either (not at
sea `2550:0338 == 0`, squadron `2550:03aa(ace,date)` without `2624:011d` flag, whose aircraft
`2624:0219` == flight type and whose station's area == `DS:626D`) or (`2550:0338 == 1`, `2550:04d9` == type,
area of `2550:0426` == area); with a squadron: `2550:03aa(ace,date) == squadron`. Removes aces whose
`2550:00d0(other)` equals them (FF), then one pass moving FF entries up by swapping with the next (reads one
past the end), n = count − FF entries. If n > 0: `r = rng_below(100)`; planes = min(planes, n); for i <
planes while none assigned: if `r <= planes*100/6` and ace[i] unused: **`flight.ace[i]` = ace id** (slot i,
while the skill loop marks plane 0 FF — a mismatch when i > 0), mark used, return 1. Returns 0/1.

`3164:0f39 add_escort_flights(service, side, mode)`: `k = rng_pick_weighted({30,50,20},3)`; k times: preset
the next flight's squad = FFFF, `add_flight(service, side, mode)`.

`3164:08b3 mission_player_slot()` (verified): mtype 0 → `DS:62CF = 4` (player alone). Else `225d:0006`
(ranks load); pos = 3 for kind 0, `225d:0141(DS:4777 rank)` for kind 1 (**uninitialised for other kinds**);
if `DS:62DF < pos+1` then `DS:62DF++`; for i = 3..0: if i == pos { ace[i] = FFFF; skill[i] = 4; break }
else { ace[i] = ace[i−1]; skill[i] = skill[i−1] } (inserts the player at position pos, shifting the others);
`225d:01de`.

### 7.4 Targets, bases, convoys

Common range computation (0fb2 with 40, 14bc with 45, 1a38 with 40):
```
A = 2777:03e2(type) (long), B = 2777:0434(type) (long)       /* aircraft ranges (emd2) */
r1 = (A * P / 100) * 21128;   r2 = ((A + B) * P / 100) * 21128   /* LXMUL/LDIV signed, P = 40 or 45 */
"in range" = dist < r1 || dist < r2      (dist = 2b1f:021d(a,b), long)
```

`3164:14bc pick_ground_target(char side, char service, pos *from, pos *out)` (verified): out = −1 ×12 bytes;
A, B, r1, r2 (45 %) for the side's last flight (`n = count−1`); cls weights `w[4]` from
`28e4:074a(28e4:0237(area), date, w)`; open `TARGET<area>` (`2322:04b1`); for every record i with
`2322:0bd5(i,date,sidegroup,0)` and kind = `2322:0cfc(i,date,0,0)` ≥ 0, position `2322:0888(i,date,out,0)`
valid: d = dist(out, from), c = target_class(kind); if d < 3,169,200 (0x305BB0): accept when c ≠ 3 or the
flight role == 3, adding **2·w[c]** to sum[c]; else if in range: accept likewise adding w[c]; accepted → list
of `2322:0e52(i)`. None → close, out.x,z = −1, return. pct[c] = sum[c]*100/Σsum (LDIV; Σ = 0 divides by zero);
`c = rng_pick_weighted(pct,4)`; filter list by class c (via `0cfc(id,date,0,1)`); `pick = list[rng_below(m−1)]`
(**never the last candidate**); `2322:0888(pick,date,out,1)`, kind = `0cfc(pick,date,0,1)`, close. If a place
with the same x,z exists: flight.target = its index, flight.b08 = 1; else append place {class c, kind, service,
flag = (c == 0), id pick, pos} and flight.target/b08 are set to it. If dist(out, from) > r1: flight.loadout =
`2ab3:03a7(mtype, type, 1, side)` (long-range load).

`3164:0fb2 pick_convoy(char side, char ckind, char service, char quality, pos *from, pos *out)` (verified):
flags[3] = 0; `29c2:061c()` (ship db); A,B,r1,r2 (40 %); find world convoy slot `c = i` with
`29c2:06b5(i) == area && 29c2:0704(i) == ckind` (else −1); `q = 29c2:0752(c, quality, date)`; open
`SHIPPATH<area>`; loop: flags[q] = 1; collect paths i with `2322:0cfc(i,date,0,0) == q`,
`2322:0bd5(i,date,sidegroup,0)`, `2322:09d8(i,date,out,0)` valid and in range → list `2322:0e52(i)`; if none:
q = last index with flags == 0 (none → close, out = −1, return); retry. Found: `29c2:080c(c,q,sidegroup,date,
types[3])`, `29c2:092b()`, `29ae:0001()` (convoy.dat), `w[k] = 29ae:00e3(types[k])` k<3, `t =
rng_pick_weighted(w,3)`, `29ae:0082(buf, types[t])` → convoy record {+01 n?,…}: new convoy `DS:6269`:
+00 service, +01 = buf+0B, +02 = buf+01, +0E = buf+02 (ship count), +10 = 1, +12 = malloc(12), +04.. =
buf+03.. (count bytes); `29ae:0131()`; `p = rng_below(m−1)`; +0C = list[p]; `2322:09d8(list[p], date,
DS:6196, 1)`; copy DS:6196 into the waypoint and *out; if dist(out, from) > r1 → reloadout as above;
close, free, `DS:6269++`.

`3164:1a38 pick_base(char side, int station, char ref_side, pos *out)` (verified; `side` low byte = side,
the flight is the side's last one; `ref_side` −1 = none):
* station given: `2a85:00f1(station,&rec,&area)`, flight.carrier = `2a85:0180(station)`; open `CARRIER`/`TARGET`
  `<area>`; if `2322:0bd5(rec,date,sidegroup,1)`: `2322:0888(rec,date,out,1)`.
* else if (char)flight.squad > −1 (low byte, signed): station = `2624:0256(squad,date)`, then as above.
* else: area = header area; if ref_side ≠ −1: ref = position of flight 0 of ref_side's target (convoy
  waypoint when that flight's carrier flag, else place +06; uses **flight 0**, not the last); A,B,r1,r2 (40 %);
  open `TARGET<area>`; candidates `i = 2322:0efd(date, service, j++)` until −1: valid when `0bd5(i,date,
  sidegroup,1)`; without ref: kind `0cfc(i,date,1,1)` must be 0 or 1 (airfields); with ref: in range of ref.
  If any: `rec = list[rng_below(count)]`. Else: open `CARRIER<area>`, first candidate `0efd` that is `0bd5`-valid
  and (with ref) in range; found → flight.carrier = 1. With ref and rec ≤ 0 (record 0 counts as failure) →
  out.x = −1, return. `2322:0888(rec,date,out,1)`.
* Carrier home: convoy index = `DS:6269`, flight.home = it, ship kind = `0cfc(rec,date,0,1)`. Side 0: read
  `CARRFORM.DAT` (u16 n; n × {s16 sidegroup, s16 type[4]}; shipped: `(0,−1,26,26,26)`, `(1,−1,8,8,8)`), row
  whose sidegroup == `0f67:02ed(service)` (none → index −1, reads garbage), ship types = row types with −1 →
  the carrier kind, count 4. Other sides: one ship (the carrier). Convoy +00 service, +01 0x18, +02 0, +03 0,
  +0C rec, +10 1, +12 malloc(12) = *out; `DS:6269++`.
* Land home: if a place with the same x,z exists: flight.home = its index, place class = 0; else append place
  {kind = `0cfc(rec,date,0,1)` (FF→0x0D), service, flag = (side 0 flight 0) or (mtype 3 and ref ≠ −1), id rec,
  pos}; flight.home is **not** set for a new place (stays as before, usually 0).
* Close; with ref and dist(out, ref) > r1 → flight.loadout = `2ab3:03a7(mtype, type, 1, side)`.

### 7.5 Other script.c functions

| Address | Name | Behaviour | Conf. |
|---|---|---|---|
| 3164:2387 | pilot_code(side, flight, plane) | skill 4 → 44 (`','`, the player); skill < 0 → ace id + 45; else service*4 + skill | verified |
| 3164:349d | wp_message(i) | `DS:61A2[i]` | verified |
| 3164:3ad3 | code_skill(c) | c < 44 → c % 4; 44 → 4; else FF | verified |
| 3164:3afa | code_ace(c) | c − 45 | verified |
| 3164:3e6d | flight_to_front(k) | k > 127 → fatal 0xA5F; if k ≠ 0: rotate side-0 flights 0..k so that flight k becomes flight 0 (SCOPY 0x24) | verified |

---------------------------------------------------------------------------------------------------------

## 8. The SCRIPT.DAT writer `3164:23e3 script_write(char resume)` (verified)

Early exits: kind == 2 and `resume` ≠ 0 → kind = 1, return (a historic career mission is flown from its own
file already copied by snario). kind 2, 3, 4 or mission type 5 → return (SCRIPT.DAT is the loaded file,
written by `1f06`). Otherwise `225d:0006`; `fp = vol_fopen("script.dat","wb")` (fatal 0x6C4); all writes are
`fwrite`, little-endian:

```
u16 4                                          version
u16 0, u16 1, header (90 bytes DS:626B)        before writing: kind 1 -> DS:6271 |= bit[2008:000e()]
                                               (SCOPY of DS:2257 {00 01 02 04 08 10 20 40})
u16 7, u16 nwp, nwp x (u8 kind, u8 msg, 12 bytes)    waypoints
u16 1, u16 nac, nac x 22                        aircraft
u16 2, u16 nsh, nsh x 16                        ships            (only if nsh != 0)
u16 4, u16 npl, npl x 10                        places           (only if npl != 0)
u16 5, u16 ngr, ngr x 58                        groups
u16 8, u16 nmsg, nmsg x u16                     message offsets
u16 9, u16 nbytes, strings                      message texts
```

**Waypoints (type 7)**: nwp = Σ flights `+1C` + Σ convoys `+10`; buffer of 14-byte records (`22ce:019c`
malloc). Order: side 0 flight 0 (msg byte = its index 0..n−1), side 0 flights 1.., sides 1 and 2 (msg FF), then
convoys (msg FF). Each: kind 0, msg, the 12 position bytes. The first-waypoint index of each group is
remembered in a local array `fw[]` (flights in that order, then convoys). **Quirk**: in the convoy loop the
record index advances once per convoy, not per waypoint (harmless: convoys have one waypoint). **Quirk**:
`fw[]` has room for 12 entries; entries 12+ lie on locals reused by the aircraft pass (more than 12
flights+convoys would corrupt them). Written as 2 + 12 bytes per record.

**Aircraft (type 1, 22 bytes)**: n = Σ planes; for side, flight, plane (`fa[]` = first index per flight):
```
+00 u8  flight type (low byte)       +01 u8 flight service       +02 u8 pilot_code(side,flight,plane)
+03 u8  0 (1 if ordnance item 0)      +04 80 00 80                  (bytes +04..+06)
+07 u8  kind 0: 225d:018d(service) (default rank of the service); else DS:4777 (career rank)
+08 u8 0, +09 u8 0, +0A u16 FFFF, +0C..+15 u8 FF
ordnance: n = 2ab3:01c7(type, loadout); 2ab3:021d(type, loadout, cnt[], code[]);
for each item: switch code: 0 -> +03 = 1; 1..9 ignored; 10..16 -> slot s (0,1,2 in order of appearance):
  +10+2s = code-10, +11+2s = cnt (a 4th such item is ignored); 17 -> +0C = 0, +0D = cnt;
  18 -> +0E = 1, +0F = cnt; 19 -> +0E = 0, +0F = cnt
```
(meaning of the codes: ordnance, emd2 part.)

**Ships (type 2, 16 bytes)**: n = Σ convoys `+0E`; per convoy per ship (`fs[]` first index):
+00 ship type (`+04[i]`), +01 convoy service, +02 u16 0, +04 u16 FFFF, +06 0, +07 0, +08 u32 0, +0C u32 0.

**Places (type 4, 10 bytes)**: n = `DS:6267`: +00 kind (`+01`), +01 service (`+02`), +02 s32 x, +06 s32 z.

**Groups (type 5, 58 bytes)**, n = Σ flights + convoys; flights first (side, flight order), then convoys:

| Off | Flight group | Convoy group |
|---|---|---|
| 00 u8 | 0 | 1 |
| 01 u8 | flight +01 | convoy +01 |
| 02 u8 | flight +07 | 0 |
| 03 u8 | flight +04 | 0 |
| 04 u8 | flight +05 | convoy +03 |
| 05 u8 | flight +06 (carrier) | 0 |
| 06 u8 | flight +08 (0 if +08 == 2) | FF |
| 07 u8 | FF | FF |
| 08 u16 | carrier: home == 0 ? 0 : **`DS:6483`** (ship count of convoy 0 — first ship index of convoy 1; only right for convoys 0/1); land: flight +1E | 0 |
| 0A u16 | planes | ship count |
| 0C u16 | first aircraft record | first ship record |
| 0E u16 | first waypoint | first waypoint |
| 10 u16 | FFFF | FFFF |
| 12 u16 | 1 | 0 |
| 14 u16 | +08 ∈ {0,1}: flight +20; +08 == 2: (Σ flights) + flight +20 (target convoy's group); other: not written (malloc garbage) | 0 |
| 16, 18 u16 | 0, 0 | 0, 0 |
| 1A u16 | waypoints − 1 | waypoints − 1 |
| 1C u16 | first waypoint + 1 | first waypoint + 1 |
| 1E u8 | flight +09 | 1 |
| 1F u8 | not written | 0 |
| 20 u8 | 3 | 0 |
| 21..23 u8 | 0 | 0 |
| 24 u32 | 50000 | 0 |
| 28,2A,2C u16 | 0 | 0 |
| 2E u16 | FFFF | FFFF |
| 30..39 | 5 × (FF, 00) | same |

**Messages**: `2a85:0231` (stations), `1155:03d2` (`DS:0B51 = 1`: sim variant), `1155:02a3` (build,
§10), `2a85:02c1`, `p = 1155:0398()` (far pointer array `DS:4B49`). Type 8: count = `DS:62E1` (player
waypoints; 0 → fatal 0x87E), offsets[0] = 0, offsets[i] = offsets[i−1] + _fstrlen(msg[i−1]) + 1. Type 9:
count = Σ (len+1); each string copied to a 0x270-byte stack buffer (`24d5:0091`) and written with its NUL.
Then `1155:03a2` (free, `DS:0B50 = 0`), fclose, `225d:01de`.

---------------------------------------------------------------------------------------------------------

## 9. Mission file → memory (`3164:34ad`–`3efe`, verified)

Used when a `MISS*.DAT` / SCRIPT file is loaded (`1f06:015c` → reader `1f06:0553`, sys part).

| Address | Name | Behaviour |
|---|---|---|
| 3164:34ad | load_alloc(nac, nsh, npl, nwp, ngr, n3) | `mission_reset()`; malloc tables: aircraft `DS:61C0` (22×), ships `61BE` (16×), places `61BC` (10×), waypoints `61BA` (14×), groups `61B8` (58×), type-3 records `61B6` (6×) (0 → NULL), zero them; counters `61C2` (type 3), `61C4` (wp), `61C6` (groups), `61C8` (places), `61CA` (ships), `61CC` (aircraft) = 0 |
| 3164:3602 | load_free | frees the six tables |
| 3164:366d | load_add3(rec6) | append 6-byte type-3 record |
| 3164:3694 | load_add_aircraft(rec22) | append; if rec+02 == 44 (player): `DS:61CE` = index, `DS:61D2` = rec+01 (player's service) |
| 3164:36d0 | load_add_ship(rec16) | append |
| 3164:36f6 | load_add_place(rec10) | append |
| 3164:371d | load_add_waypoint(u8 hdr[2], data) | copy 2 bytes, then 12 bytes if kind 0 else 4 |
| 3164:3788 | load_add_group(rec58) | append |
| 3164:3efe | load_finish(p) | `DS:61D0 = p`; `load_places()`; `k = load_groups()`; `flight_to_front(k)` |
| 3164:3b08 | load_places | place i: +01 kind, +02 service, +03 = 1, +04 FFFF, +06 x, +0A z (alt and class untouched); `DS:6267 = 61C8` |
| 3164:3e0f | load_groups | for each group: kind 1 → `load_convoy(next convoy slot, g)`; kind 0 → `load_flight(g)` (player → k = side-0 count − 1); returns k (−1 none) |
| 3164:3b5f | load_convoy(conv, g) | +03 = g+04 + '@'; +0E = g+0A; +10 = g+1A + 1; +00 = ship[g+0C].+01; +12 = malloc((g+1A+1)*12); types[i] = ship[g+0C+i].+00 (no bound on 8); waypoints via `resolve_wp`; `DS:6269++` |
| 3164:3c1a | load_flight(g) | side = (aircraft[g+0C].+01 ≠ `DS:61D2`); f = next flight of that side (no check against 4); +01 = g+01; +05 = g+04 + '@'; +06 = g+05; +1A = g+0A; +1C = g+1A + 1; +03 = g+07 + 1; +00 = aircraft.+01; +18 = aircraft.+00; waypoints malloc + `resolve_wp`; per plane code: 44 → player flag; skill = `code_skill`, ace = skill == FF ? code−45 : FFFF; player flight: g+1A > 10 → fatal 0xA2B, `DS:61A2[0]` = (s8) wp[g+0E].msg, `DS:61A2[i]` = (s8) wp[g+1C+i−1].msg; +1E = g+08; if g+05 == 0: place[g+08].+03 = player flag; count++ |
| 3164:3811 | resolve_wp(dst, i, first, start) | wp index = i ? first + i − 1 : start (< 0 → fatal 0x978); by wp kind (table `CS:3AC7`): 0 own position; 1 group g → g.+0E (the group's start waypoint); 2 aircraft a → a.+0A, if FFFF `find_group(a,0)`; 3 ship s → s.+04 or `find_group(s,1)`; 4 type-3 record r → r.+02 or `find_group(r,2)`; 5 place p → (x, z, 0); other → fatal 0x9AB; then copies 12 bytes (bounds fatal 0x9AF) |
| 3164:37af | find_group(idx, kind) | first group of kind with `+0C <= idx < +0C + +0A` → its `+0E`; none → fatal 0x96E, FFFF |

So in files a waypoint of kind ≠ 0 is a reference (u16 index, u16 parameter) resolved to the start of the
referenced object: SCRIPT waypoint record = `u8 kind, u8 msg, kind 0: s32 x, s32 z, s32 alt; else u16 ref,
u16 param`.

---------------------------------------------------------------------------------------------------------

## 10. Flight-plan messages (`1155`, `fltplan.dat`, verified)

`1155:02a3 fltplan_build()`: `DS:4B42 = DS:62E1`; group `DS:4B44 = mtype + (DS:0B51 ? 11 : 0)` (11 = the
`|…|` sim variants); load `fltplan.dat` strings; `DS:4B45 = str(0x18, 0)` (far, carrier prefix); message 0 =
`expand(str(g,0))`; if g % 11 is 2 or 3 (CAP, sweep): messages 1..n−2 = `str(g,1)` (with `%d` = index), n−1 =
`str(g,2)`; else message i = `str(g,i)`, i = 1..n−1. `1155:0230` expands into a 500-byte buffer and stores a far
copy (`22ce:022a`/`026e`) in `DS:4B49[i]`. `1155:03a2` frees them, `1155:03d2`/`03dc` set/clear `DS:0B51`,
`1155:0398` returns `DS:4B49`. Also used by the briefing screen `12c4:02d4` (shell_ui).

`1155:01a5 expand(dst, src)` copies src, replacing `%x` by `1155:0042(x)` (table `CS:0197`, x = 'a'..'g'):
`%a` objective name: player flight +08 == 1 → place kind string (table 0x16, place[+20].+01), else convoy
string (table 0x17, convoy[+20].+02) (`1155:0002`); `%b` home base: `2a85:027c(2a85:01a7(area, home record,
carrier))`, printed `"%Fs%Fs"` with `DS:4B45` prefix when carrier else "" ; `%c` side-2 flight-0 aircraft name
`2777:0101`; `%d` waypoint number `DS:4B40`; `%e` ace name `2550:0043(side-1 flight 0 ace[0])`; `%f`
enemy aircraft plural `"%Fss"` of `2777:00a1(side-1 type)`; `%g` bearing `06c7:0125(side-1 wp, side-0 wp)`
(unsigned decimal).

---------------------------------------------------------------------------------------------------------

## Port notes

* File names: keep `file_name` semantics; the port always behaves as with volumes (`DS:0DFF` = 1).
* `SIM.IN`/`SIM.OUT`/`SCRIPT.DAT` are still written as files (PLAN decision 2); layouts above are exact.
* The quirks listed (rng_below(n−1), uninitialised group +14/+1F, `fw[]` overflow, slot mismatch of aces,
  CARRFORM miss) are kept: they influence generated missions. Garbage bytes from `malloc` are
  deterministic only in the original heap; the port should write 0 there (`/* PORT: */`), since the sim never
  reads those fields for these cases (group +14 only matters for +06 ∈ {0,1,2}; +1F unknown).

## Hand-offs

* **sim_flow / sim_world**: SIM.OUT +00 is a per-mission-type result code (1-based `DEBRIEF.DAT` sentence;
  success bits `PS DS:0512`), +02 bits 1 killed / 2 captured / 4 wounded / 10-20-40 friendly fire, +04 aircraft
  lost, +20 merit points, +22 score; +0E = 1 advances the career date. SCRIPT.DAT group/aircraft/waypoint
  layouts as written by PS: §8; waypoint kinds 1–5 are references (§9).
* **shell_ui**: `125a:000f` file_ext rule; `0542:01c4` seeds the RNG by time and stores `DS:42C1`;
  `0787:0181` reseeds with `DS:42C1` before the career mission; `1155` (fltplan) is shared with the briefing
  `12c4:02d4`.
* **platform**: `1193:0ad2` config_write = INTRO `038e:04d6`; `DS:0DFF` is the "volumes present" flag set by
  the volume scanner; `16e3:49c1` = far memcpy.
* **render3d / video**: PS `3d50` is an asm math library (`3d50:16b0` midpoint of two s32 positions →
  static `DS:3889`); no owner in README.

## Open questions

* Header +03, +05 beyond the modules' use, +0E meaning on the sim side; group +01/+02/+03/+04 and +1E meanings
  (sim_world); aircraft +04..+06 `80 00 80`.
* SIM.OUT +0E exact AP semantics; +06..+0C.
* `DS:00C5` debug seed: writer not found (probably a `-p` option reached through a table).
* Pilot +0x26, +0x2D..+0x2F.
