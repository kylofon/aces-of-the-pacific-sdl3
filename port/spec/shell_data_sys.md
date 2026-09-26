# shell_data — part `sys`: segments `1ed0`–`2316` (except `227c`)

Part of the `shell_data` module (PS.EXE only, DGROUP `4D08`); index and conventions in `shell_data.md`.
Symbols: `scratchpad/sys_symbols.csv` (merged into `shell_data_symbols.csv` by the lead).
Confidence: **V** = verified in the disassembly, **L** = likely, **G** = guess. `DS:xxxx` = DGROUP offset.
Source tags come from assert strings (`sys\farquick.c`, `sys\snario.c`, `sys\extens.c`, `sys\helper.c`,
`d:\1946\s\sys\queue.c`, `sys\threed.c`, `emd\historic.c`, `emd\shiptext.c`, `emd\planetxt.c`, `emd\ranks.c`).
All fatal checks go through `shell_fatal(0, file_seg, line, arg)` (`227c:0143`); below written
`fatal(file, line)` with the line number in hex.

## Index

| § | Segment | Source | Contents | Functions |
|---|---|---|---|---|
| 1 | `1ed0` | farquick.c | far small-block pool allocator behind `farmalloc` | 3 |
| 2 | `22ce` | helper.c | malloc/free wrappers, page-pair setters, wipe, string helpers | 27 |
| 3 | `1efe`, `1f06` | (stream), snario.c | memory stream + mission file reader (MISS/TRN → SCRIPT.DAT, → lead callbacks) | 4 + 8 |
| 4 | `2008` | extens.c | generic numbered-file table loader ("extensions" = add-on modules) | 40 |
| 5 | `1f85` | historic.c | historic-mission tables `hist_`, `histnm_`, `histbf_`, `histov_`, `histsn_` | 27 |
| 6 | `214d`, `2164`, `1f7f` | shiptext.c, planetxt.c, (medabbr) | ship / plane description texts, medal abbreviations | 6 + 3 + 3 |
| 7 | `225d` | ranks.c | `RANKS.DAT` rank table | 8 |
| 8 | `2221` | (medlocs) | TTM hook table: medal drawing (`MEDLOCS.DAT`) | 3 |
| 9 | `2242` | queue.c | circular linked queue | 8 |
| 10 | `217d`, `21d4` | threed.c | 3-D object viewer in the shell (reference screen) | 11 + 5 |
| 11 | `2171`, `21f4`, `229e`, `22a0`, `230d`, `2316` | UI / video glue | wait-for-key, **TTM player (RNG call)**, tick counters, timers, dir listing, input toggles, mouse wrappers | 1+6+2+12+5+5 |

186 functions owned, 186 specced.

Borland / volume RTL used here: `0000:0551` vol_fopen, `084b` fclose, `08a0` fread, `0dea` fwrite, `0b5a`
fseek(fp, long, whence) (volume-aware), `0c17` ftell (volume-aware, long), `0c53` flength(fp) (ftell, fseek end,
ftell, fseek back; long), `317b` ftell, `03c1` malloc, `0454` free, `3508` memset, `34c3` memcpy, `3f33` strcpy,
`3e95` strcat, `3f95` strlen, `3ece` strchr, `343d` itoa, `1fcd` toupper, `1fa1` tolower, `3c66` qsort,
`2d0b` findfirst, `2d3e` findnext, `4794` _fmemset(far, byte, n), `192a` SCOPY@, `18f2` LXMUL@, `198f` LDIV@,
`1996` LUDIV@, `1909` PCMP@, `1b27` PADD@, `1a3d` LXLSH@. Platform: `16e3:3bf4` dos_alloc(long),
`16e3:3c6b` dos_free(far).

---------------------------------------------------------------------------------------------------------

## 1. `farquick.c` — far small-block allocator (`1ed0`, V)

`farmalloc`/`farfree` of the shell (`22ce:022a` / `22ce:02b0` are thin wrappers). Blocks of ≤ 16 bytes come
from up to 10 pools of 256 × 16-byte cells (4096 bytes each, one `dos_alloc`); larger blocks go straight to
`dos_alloc`.

| Global | Type | Meaning |
|---|---|---|
| `DS:4F6E` | u16[10] | `pool_free[i]` number of free cells in pool i |
| `DS:4F82` | far*[10] | `pool_base[i]` (NULL = slot unused) |
| `DS:4FAA` | far*[10] | `pool_head[i]` free-list head (first dword of a free cell = far next) |

```c
void far *pool_create(int cell, int n)            /* 1ed0:0000 — only called (16, 256) */
{   char far *p = dos_alloc((long)(cell*n));       /* 16-bit product */
    if (!p) fatal(farquick, 0x15);
    char far *c = p;
    for (unsigned i = 0; i < n-1; i++) { *(char far* far*)c = c + cell; c += cell; }  /* offset arithmetic */
    *(char far* far*)c = NULL;
    return p;
}
void far *far_alloc(unsigned long size)            /* 1ed0:00b2 (22ce:022a) */
{   if (size <= 16) {                              /* high word 0 and low <= 0x10 (size 0 too) */
        for (i = 0; i < 10 && pool_head[i] == NULL; i++) ;
        if (i == 10) {
            for (i = 0; i < 10 && pool_base[i] != NULL; i++) ;
            if (i > 9) fatal(farquick, 0x34);
            pool_base[i] = pool_head[i] = pool_create(16, 256); pool_free[i] = 256;
        }
        p = pool_head[i]; pool_head[i] = *(far**)p; pool_free[i]--; return p;
    }
    p = dos_alloc(size); if (!p) fatal(farquick, 0x3F); return p;
}
void far_free(void far *p)                         /* 1ed0:01e8 (22ce:02b0) */
{   for (i = 0; i < 10; i++)
        if (pool_base[i] && pool_base[i] <= p && p < pool_base[i] + 0x1000) break;   /* huge compare (PCMP/PADD) */
    if (i < 10) {
        *(far**)p = pool_head[i]; pool_head[i] = p;
        if (++pool_free[i] == 256) { dos_free(pool_base[i]); pool_base[i] = pool_head[i] = NULL; pool_free[i] = 0; }
    } else dos_free(p);
}
```
Note: the cell contents are not cleared (callers that need zeroes memset). **Port:** any allocator will do as
long as `far_alloc` never returns NULL (fatal instead); nothing relies on addresses.

---------------------------------------------------------------------------------------------------------

## 2. `helper.c` (`22ce`, V)

| Address | Name | Behaviour |
|---|---|---|
| `22ce:000d` | `timer_countdown()` | returns `DS:2E3F` (PIT countdown decremented by `timer_isr` at 236.7 Hz) |
| `22ce:0017` | `assert_index(char i, char n)` | if `i < 0 \|\| i >= n` (signed bytes): `fatal(helper, 0x42)`; returns 1 (0 only if fatal returned 0). Uncalled |
| `22ce:004a` | `copy_full_screen()` | `copy_rect(0, 0, 320, 200)` (`16e3:35c4`, page `DS:2316` → `DS:2318`) |
| `22ce:0063` | `pages_spare_to_work()` | `2316 = 2310; 2318 = 2312` |
| `22ce:0074` | `pages_front_to_work()` | `2316 = 2314; 2318 = 2312` |
| `22ce:0085` | `pages_work_to_front()` | `2316 = 2312; 2318 = 2314` |
| `22ce:0096` | `pages_work_to_spare()` | `2316 = 2312; 2318 = 2310` |
| `22ce:00a7` / `00bc` / `00d1` / `00e6` / `00fb` | copy whole page | set (2316,2318) = (2310,2312) / (2312,2310) / (2310,2314) / (2312,2314) / (2314,2312), then `copy_full_screen()` |
| `22ce:0110` | `clip_full()` | `DS:230C = 1; DS:2303 = 1; DS:2304 = 0; DS:2308 = 0; DS:2306 = 319; DS:230A = 199` |
| `22ce:0137` | `wipe_rect(x, y, w, h)` | venetian-blind reveal from page 2316 to 2318: `for pass = 0..9 { DS:2E3F = 5; for (d = 0; y+pass+d <= y+h-1; d += 10) if (w) copy_rect(x, y+pass+d, w, 1); while (timer_countdown()) ; }` — 10 passes × 5 PIT ticks ≈ 0.21 s. Caller `0874:0b57` |
| `22ce:019c` | `xmalloc(unsigned n)` | `n == 0` → `fatal(helper, 0xCE)`; `p = malloc(n)`; NULL → `fatal(helper, 0xD0)`; return p (near) |
| `22ce:01ff` | `memzero(p, n)` | `memset(p, 0, n)`; returns p |
| `22ce:021c` | `xfree(p)` | `free(p)` (no NULL check; Borland free(NULL) is a no-op) |
| `22ce:022a` | `xfarmalloc(unsigned long n)` | `far_alloc(n)` (§1) |
| `22ce:023e` | `fmemset(void far *d, char c, unsigned n)` | byte loop. Uncalled |
| `22ce:026e` | `fmemcpy(void far *d, void far *s, unsigned n)` | byte loop, forward |
| `22ce:02b0` | `xfarfree(void far *p)` | `far_free(p)` (§1) |
| `22ce:02c2` | `str_ordinal(char *s, int n)` | `d = (char)(n % 10)`; suffix = `"th"` (DS:1CD5) if `d < 1 \|\| d > 3 \|\| (char)((n - d) % 100) == 10`, else `"st"` (1CCC) / `"nd"` (1CCF) / `"rd"` (1CD2) for d = 1/2/3; `strcat(s, suffix)`; returns s. (C `%`: negative n → negative d → "th"). Uncalled in PS |
| `22ce:032d` | `str_int(char *s, int n)` | `itoa(n, s, 10)` |
| `22ce:0346` | `str_cat_int(char *s, int n)` | `itoa(n, s + strlen(s), 10)`. Uncalled |
| `22ce:0367` | `str_upper(char *s)` | in place `toupper` each char; returns s |
| `22ce:038d` | `str_lower(char *s)` | in place `tolower`; returns s. Uncalled |
| `22ce:03b3` | `str_capitalize(char *s)` | `up = 1; for each c: c = up ? toupper(c) : tolower(c); up = (c == ' ' \|\| c == '-')`; returns s. Uncalled (the function table size 14 is wrong: it runs to `03fc`) |

The page-pair setters are also listed in `shell_ui_toolkit.md` (§1); spec'd here once.

---------------------------------------------------------------------------------------------------------

## 3. Mission file reader: stream (`1efe`) and `snario.c` (`1f06`) — V

### 3.1 File format (`MISS<n>.DAT`, `TRN<n>.DAT`, `SCRIPT.DAT`)

Recap of `port/formats/data.md` §2 (all 94 files parse), with the reader's exact rules:

```
u16 version            must be 4 (else fatal snario 0x103, in the prescan)
repeat:  u16 type, u16 count       (a run; reading stops when fewer than 2 bytes remain for the type)
         count × record(type)      (fewer than 2 bytes left for count → fatal snario 0x86)
```

Record size table `DS:1024` u16[10] = **`90, 22, 16, 6, 10, 58, 0, 2, 2, 1`** (V, img dump). Type 6 is
invalid (fatal 0xA2 in the skipper), types > 9 fatal (0xA1 skipper, 0x17C prescan, 0x1FF parse). Type 7 is
variable: `u8 kind, u8 index` followed by 12 bytes if `kind == 0` (s32 x, s32 z, s32 alt) else 4 bytes
(`kind` must be < 6 in the prescan: fatal 0x12E).

| Type | Size | Prescan `1f06:02c4` | Parse `1f06:0553` |
|---|---|---|---|
| 0 header | 90 | read into scratch `DS:4FE8` (90 bytes, discarded) | read into **`DS:626B`** (mission header) |
| 1 aircraft | 22 | `t = rec[0]` (< 9Fh else fatal 0x13C); `if (ac_used[t]++ == 0) ntypes++`; `n_aircraft++` | `3164:3694(&rec22)` |
| 2 ship | 16 | `t = rec[0]` (< 73h else fatal 0x14D); `if (ship_used[t]++ == 0) ntypes++`; `n_ships++` | `3164:36d0(&rec16)` |
| 3 — | 6 | `n_type3++` **without consuming the record** (the stream desyncs; never present in the data) | `3164:366d(&rec6)` |
| 4 place | 10 | `n_places++`, skip | `3164:36f6(&rec10)` |
| 5 group | 58 | `rec[0] == 1`: `n_ships++`, `ship_used[0] = 1` (set, not incremented; `ntypes` unchanged); `rec[0]` not 0/1 → fatal 0x166; always `n_groups++` | `3164:3788(&rec58)` |
| 6 | — | fatal 0x17C (jump table default) — table entry `0x507` | fatal 0x1FF |
| 7 waypoint | 2+12 / 2+4 | kind 0: skip 12, `wp_bytes += 14`; else skip 4, `wp_bytes += 4`; `n_waypoints++` | `3164:371d(&kind_idx2, &payload)` |
| 8 msg offset | 2 | skip | first record of a run: `msg_ofs = farmalloc((cnt+1)*2)` copy of the whole run (see below); then skip |
| 9 msg text | 1 | skip | first record of a run: `msg_text = farmalloc(cnt+1)` copy of the whole run; then skip |

`cnt` above = the run's remaining count *after* the current record was taken (`DS:4FD6`), so `(cnt+1)`
records = the whole run. The copy is done only while the far pointer is NULL, i.e. once per parse (a second
run of type 8/9 would be ignored). The prescan and parse both clear `DS:5272..5279` first **without freeing**:
the owners free them (`0583:03c2`, `100e:12c9`, `0ed9:010b`, `12c4:023c`: `22ce:02b0` + clear).

### 3.2 Globals

| Global | Type | Meaning |
|---|---|---|
| `DS:4FD2` | s16 | `ms_left` bytes left in the memory stream |
| `DS:4FD4` | u16 | `ms_ptr` near cursor |
| `DS:4FD6` | s16 | `run_left` records left in the current run |
| `DS:4FD8` | s16 | `run_type` type of the current run |
| `DS:4FDD` | u16 | prescan: number of type-5 groups |
| `DS:4FDF` | u16 | prescan: number of type-4 places |
| `DS:4FE1` | u16 | prescan: number of type-3 records |
| `DS:4FE3` | u16 | prescan: number of ships (type 2 + type-5 with rec[0]==1) |
| `DS:4FE5` | u16 | prescan: number of type-1 aircraft |
| `DS:4FE8` | u8[90] | scratch header for the prescan |
| `DS:5042` | u16 | prescan: `2 + distinct aircraft types + distinct ship types` (written only, never read) |
| `DS:5044` | u16 | `mfile_len` file length (low word of `flength`) |
| `DS:5046` | near* | `mfile_buf` whole file, `xmalloc(mfile_len)` |
| `DS:5048` | u16[115] | per ship type use count (prescan) |
| `DS:512E` | u16[159] | per aircraft type use count (prescan) |
| `DS:526C` | u16 | prescan: waypoint bytes (14 per kind-0, 4 per other) — written only |
| `DS:526E` | u16 | prescan: number of waypoints |
| `DS:5270` | u16 | (cleared, unused) |
| `DS:5272` | far* | `msg_ofs` copy of the type-8 run (u16 offsets into the text) |
| `DS:5276` | far* | `msg_text` copy of the type-9 run (NUL-separated strings, lines split by `\|`) |

`DS:5042..5271` (0x230 bytes) is zeroed at every load.

### 3.3 Functions

| Address | Name | Behaviour |
|---|---|---|
| `1efe:000e` | `ms_open(void *p, int len)` | `ms_ptr = p; ms_left = len` |
| `1efe:001f` | `ms_skip(int n)` → n | `ms_left -= n; ms_ptr += n` (no bounds check) |
| `1efe:0033` | `ms_read(void *dst, int size, int n)` → items | `k = 0; while (size <= ms_left` (signed) `&& n) { memcpy(dst, ms_ptr, size); ms_left -= size; ms_ptr += size; dst += size; k++; n--; }` return k |
| `1efe:007e` | `ms_tell()` | returns `ms_ptr` |
| `1f06:0008` | `mr_begin(p, len)` | `ms_open(p, len); run_left = 0` |
| `1f06:0020` | `mr_next()` → bool | `if (run_left == 0) { if (ms_read(&run_type, 2, 1) != 1) return 0; if (ms_read(&run_left, 2, 1) != 1) fatal(snario, 0x86); } run_left--; return 1`. (A run with count 0 still yields one record: `run_left` goes to −1 and the next call keeps decrementing — never seen in data) |
| `1f06:0096` | `mr_skip()` | type 7: `ms_read(&b, 2, 1); ms_skip(b[0] == 0 ? 12 : 4)`; else: type outside 0..9 → fatal 0xA1; type 6 → fatal 0xA2; `ms_skip(DS:1024[type])` |
| `1f06:015c` | `mission_load(char *name, char parse)` | `f = vol_fopen(name, "rb")` (DS:1038), NULL → `fatal(snario, 0xC0, name)`; `memzero(DS:5042, 0x230)`; `mfile_len = flength(f)`; `mfile_buf = xmalloc(mfile_len)` (NULL → fatal 0xC7); `fread(buf, mfile_len, 1, f)` == 0 → fatal 0xCA; fclose. If `parse`: `mission_prescan(); 3164:34ad(n_aircraft 4FE5, n_ships 4FE3, n_places 4FDF, n_waypoints 526E, n_groups 4FDD, n_type3 4FE1)` (allocation of the mission tables, lead); `mission_parse(); 3164:3efe(name)` (lead). All three callers pass parse = 1 |
| `1f06:0269` | `mission_write_script()` | `f = vol_fopen("SCRIPT.DAT", "wb")` (DS:103B / DS:1046), NULL → `fatal(snario, 0xE6, "SCRIPT.DAT")`; `fwrite(mfile_buf, mfile_len, 1, f)`; fclose — **SCRIPT.DAT is a byte copy of the mission file** |
| `1f06:02c4` | `mission_prescan()` | `DS:5272..5279 = 0`; `memzero(DS:4FE8, 90)`; `*(u16*)mfile_buf != 4` → fatal 0x103; counters 4FDD/4FDF/4FE1/4FE3/4FE5 = 0; `ntypes = 2`; `mr_begin(mfile_buf+2, mfile_len-2)`; `while (mr_next()) switch (run_type)` per §3.1 table (jump table `1f06:053f`); `DS:5042 = ntypes` |
| `1f06:0553` | `mission_parse()` | `DS:5272..5279 = 0`; `memzero(DS:4FE8, 90)`; `mr_begin(mfile_buf+2, mfile_len-2)`; `while (mr_next()) switch (run_type)` per §3.1 (jump table `1f06:076e`); records are read into stack buffers and passed by near pointer; for type 7 the 2-byte `{kind, index}` and the payload are separate buffers |
| `1f06:0782` | `mission_free()` | `xfree(mfile_buf)` |

Call sequence at every mission start (historic `0583:03c2` with `MISS<n>.DAT`, training `100e:12c9` with
`TRN<n>.DAT`, career/single `3164:0944` with `MISS<n>.DAT`): `mission_load(name, 1); mission_write_script();
mission_free()`; then the caller sets `DS:626B` kind (2 historic / 0 training / 1–2 script.c).

**Port note:** the prescan/parse run over the exact bytes; keep the type-3 non-skip quirk (irrelevant to
the shipped data). The version check happens only in the prescan (the parse relies on it).

---------------------------------------------------------------------------------------------------------

## 4. `extens.c` — numbered table files ("extensions") (`2008`, V)

### 4.1 Concept

Many shell tables exist once per installed module: `<base>0.<ext>` (or `<base>.<ext>`) for the base game and
`<base><n>.<ext>` (n = 1..8) for add-on module n (the 1946 expansion is n = 1: `HIST_1.DAT`, `SHIPTXT1.DAT`,
`PLTXT1.DAT`, `WLDLOCS1.DAT` in `M1SHL`). A loaded table lives in one of 20 **slots**; records are addressed
by a global **id**; file i contributes ids `[cum[i-1], cum[i-1] + count[i])` (`cum[-1]` = 0). When a table is
declared with a fixed stride `fixed` ≠ 0, each add-on file i ≥ 1 reserves exactly `fixed` ids regardless of its
count (base file: its real count), so ids stay stable when modules are added.

Installed-module globals (`DS:43B4/43B5` lie in the `CONTROL.PRF` buffer `DS:43B0` (+04/+05) and are also
written to `RESOURCE.CFG` as `modules =` / `latest =` by `1193:0ad2`; `0ddd:089a/08d7` touch `DS:43B4` too):

| Global | Type | Meaning |
|---|---|---|
| `DS:43B4` | s8 | `modules` bit mask: bit b set → module b+1 installed |
| `DS:43B5` | s8 | `latest` (returned by `open_module_files`) |
| `DS:5288` | u8 | **active module** of the current mission (0 base, 1 = 1946 …) |
| `DS:5289` | u8 | module-bit iterator |
| `DS:1B01` | s8 | cached highest installed module number (init FFh, computed once, never reset) |

### 4.2 Table file format (all `2008:0aec` tables)

```
u32 tail_size          bytes of the tail block (text etc.), may be 0
u16 count              number of fixed-size records
count × record[recsize]           (flag 1)   — or variable-length records read by a callback (flag 2)
tail_size bytes                   (flag 4)   — addressed by offsets stored in the records
```
Example `HISTNM_0.DAT`: tail 49Ch, count 3Bh, records = u32 offsets into the tail. `SHIPTXT0.DAT`: tail
1358h, count 23h, 23-byte records.

### 4.3 Slot descriptor `DS:10A8 + slot × 7Dh` (slot 1..20; slot 0 unused)

| Off | DS (slot s) | Type | Field |
|---|---|---|---|
| +00 | `10A8+7Dh·s` | far* | `data`: record array, or the list header (list mode) — NULL = slot free |
| +04 | `10AC` | far* | `tail`: tail block (all tails concatenated, or one file's tail) |
| +08 | `10B0` | char[9] | base name |
| +11 | `10B9` | char[4] | extension |
| +15 | `10BD` | s8 | `rec_file`: FFh = all files' records resident; else the file whose records are resident |
| +16 | `10BE` | s8 | `tail_file`: FFh = all tails resident; else file whose tail is (supposedly) resident |
| +17 | `10BF` | u8 | `owned`: 1 = `data` is a plain record array allocated here; 0 = list mode (`273b` list) |
| +18 | `10C0` | u8 | `far`: 1 = far heap (`xfarmalloc`/`1193:0a46`), 0 = near heap (`xmalloc`/`fread`) |
| +19 | `10C1` | u16 | `recsize` |
| +1B | `10C3` | u16 | `fixed` id stride per add-on file (0 = use the counts) |
| +1D | `10C5` | far fn | `read_cb` (list mode, p9:p10) |
| +21 | `10C9` | far fn | `free_cb` (list mode, p11:p12) |
| +25 | `10CD` | u16[9] | `count[i]` records in file i (0 if the file is missing) |
| +37 | `10DF` | s16[8] | `cum[i]`: `cum[0] = count[0]`, `cum[i] = cum[i-1] + (fixed ? fixed : count[i])` (i = 1..7) |
| +47 | `10EF` | u16[9] | `tail_pos[i]`: file position after the records (low word of ftell), FFFFh = unknown |
| +59 | `1101` | u32[9] | `tail_size[i]` |

### 4.4 Loader modes

`table_load(base, ext, recsize, fixed, mode, flags, list_hdr far, read_cb far, free_cb far)` (`2008:0aec`).
`flags`: bit 0 = records array, bit 1 = list via callback, bit 2 = tail. Valid (`2008:08b0`) iff any of bits
0/1/2 is set and not both 0 and 1.
`mode` selects the loader (`2008:0914` → far fn table `DS:1AE9`):

| mode bits | idx | loader | meaning |
|---|---|---|---|
| 08 + 01 | 0 | `2008:0334` → `load_one(…, far=0)` | swap mode, near |
| 08, not 01, not 04 | 1 | `2008:035b` → `load_one(…, far=1)` | swap mode, far |
| 08 + 04 (no 01) | 2 | `2008:01ea` returns 0 (fail) | unsupported |
| 01 (no 08) | 3 | `2008:0889` → `load_all(…, far=0)` | all files, near |
| neither 08 nor 01 nor 04 | 4 | `2008:0862` → `load_all(…, far=1)` | all files, far |
| 04 (no 08, no 01) | 5 | `2008:01ea` fail | unsupported |

(Bits 02h and 10h are passed by the callers — 0x11/0x12 = all near/far, 0x09/0x0A = swap near/far — but
are not tested.) **Swap mode** keeps only one file's records (and tail) resident and reloads another file
from disk on demand.

### 4.5 Users (all `table_load` calls)

| Caller | base.ext | recsize | fixed | mode | flags | Notes |
|---|---|---|---|---|---|---|
| `06c7:0a25` | `wldnms.dat` | 2 | 3 | 12h far | 5 | world names (u16 text offset) |
| `0c8a:0009` | `aceface.dat` | 8 | 0 | 11h near | 1 | |
| `0d16:09d8` | `wldlocs.dat` | 4 | 3 | 11h near | 1 | |
| `0ddd:0824` | `pitch_.dat` | 6 | 15 | 09h swap near | 1 | |
| `1193:0084` | `service.dat` | 2 | 0 | 11h near | 1 | |
| `1f85:00b7` | `hist_.dat` | 6 | 20 | 12h far | 2 | list `DS:527A`, cb `1f85:0027` / `1f85:0094` |
| `1f85:043b` | `histnm_.dat` | 4 | 20 | 12h far | 5 | |
| `1f85:04fb` | `histbf_.dat` | 4 | 20 | 0Ah swap far | 5 | |
| `1f85:05bb` | `histov_.dat` | 4 | 20 | 0Ah swap far | 5 | |
| `1f85:067b` | `histsn_.dat` | 4 | 20 | 12h far | 5 | |
| `214d:0005` | `shiptxt.dat` | 23 | 15 | 12h far | 5 | |
| `2164:000c` | `pltxt.dat` | 2 | 15 | 12h far | 5 | |

### 4.6 Functions

```c
void  module_set_active(u8 m)  { DS_5288 = m; }          /* 2008:0003 (= 1f85:0833, same address) */
u8    module_active(void)      { return DS_5288; }       /* 2008:000e */
s8    module_latest(void)      { return DS_43B5; }       /* 2008:0018 */
s8    module_iter_reset(void)  { DS_5289 = 0; return 0; }   /* 2008:0022 */
s8 module_iter_next(void)                                /* 2008:002e */
{   for (b = DS_5289; b < 8; b++) if ((DS_43B4 >> b) & 1) { DS_5289 = b+1; return b+1; }
    return 9;                                            /* DS_5289 unchanged */
}
s8 module_highest(void)                                  /* 2008:0064 */
{   if (DS_1B01 == -1)
        for (DS_1B01 = 8; !((DS_43B4 >> (DS_1B01-1)) & 1) && DS_1B01 != 0; DS_1B01--) ;
    return DS_1B01;                                      /* 0 if no module installed (the shift by -1 evaluated at 0
                                                            does not matter: the && ends the loop) */
}
s8 open_module_files(FILE *fp[9], char *base, char *ext) /* 2008:00a8 (used by text.c 26c4:02d9, 0874, 0f35, 3164:05f9) */
{   memset(fp, 0, 18);
    fp[0] = vol_fopen(file_name(base, module_iter_reset(), ext), "rb");      /* "<base>0.<ext>" */
    if (!fp[0]) fp[0] = vol_fopen(file_name(base, -1, ext), "rb");          /* "<base>.<ext>" */
    while ((m = module_iter_next()) <= module_highest())
        fp[m] = vol_fopen(file_name(base, m, ext), "rb");                   /* only installed modules */
    return module_latest();
}
```
`file_name` = `1193:0115(base, n, ext)` (lead): `strcpy(DS:4B72, base)`; n > −1 → append decimal n;
append `125a:000f(DS:4B72, ext)` result. The `"rb"` mode string is the 4th argument left on the stack
(Borland argument reuse); DS:1B02..1B1D are eleven copies of `"rb"`.

| Address | Name | Behaviour |
|---|---|---|
| `2008:0143` | `files_total(FILE *fp[9], far fn)` | sum over non-NULL fp[i] of `fn ? fn(fp[i]) : flength(fp[i])` (16-bit). Uncalled |
| `2008:019e` | `files_foreach(FILE *fp[9], far fn)` | `for i in 0..8: fn(fp[i], i)` (also NULL entries) |
| `2008:01c0` | `file_close_nz(FILE *f)` | `if (f) fclose(f)` |
| `2008:01d3` | `files_close(FILE *fp[9])` | `files_foreach(fp, file_close_nz)` |
| `2008:01ea` | `load_fail()` | returns 0 |
| `2008:0a71` | `open_all_files(FILE *fp[9], base, ext)` | fp[0] = `<base>0.<ext>` else `<base>.<ext>`; fp[1..8] = `<base><i>.<ext>` for **every** i 1..8 (installed-mask not consulted) |
| `2008:08b0` | `flags_valid(u8 f)` | see §4.4 |
| `2008:08e9` | `slot_free()` → s | first s in 1..20 with `data == NULL`, else 0 |
| `2008:0914` | `loader_index(u8 mode)` | see §4.4 |
| `2008:0952` | `slot_init(base, ext, s, fp[9], recsize, fixed, read_cb, free_cb)` | strcpy name/ext; store recsize, fixed, cbs; for i 0..8: `tail_pos[i] = FFFFh`; fp[i] NULL → count, tail_size = 0; else `fread(&tail_size[i], 4, 1, fp[i]); fread(&count[i], 2, 1, fp[i])`; then `cum[]` as §4.3 |
| `2008:0aec` | `table_load(…)` → slot | `open_all_files`; none open → return 0; `s = slot_free()`; `s == 0` → close, return 0; `!flags_valid(flags)` → s = 0; else `slot_init`; `r = DS:1AE9[loader_index(mode)](s, fp, flags, list_hdr, read_cb)`; r == 0 → s = 0 (the slot is not released: `data` may already be set — leak/lost slot); `files_close(fp)`; return s |
| `2008:0334` / `035b` | `load_one_near` / `load_one_far` | `load_one(args…, far = 0 / 1)` |
| `2008:01f3` | `load_one(s, fp, flags, list_hdr, read_cb, far)` | swap mode, uses **fp[0] only**: `rec_file = tail_file = 0`; `far` stored. flags 1: `owned = 1`; `data = alloc(count[0]*recsize)` (far: `xfarmalloc((long)(s16)(count*recsize))`, read with `fread_far` `1193:0a46(data, recsize, count[0], fp[0])`; near: `xmalloc`, `fread`). flags 2: `owned = 0; data = list_hdr; fseek(fp[0], 4, SEEK_SET)` (the list code re-reads the u16 count); `emd_set_file(fp[0])` (`26fc:000c`); `list_load(list_hdr, recsize, read_cb)` (`273b:024e`). flags 4: `tail_pos[0] = ftell(fp[0])` (low word, `0000:317b`); `tail = alloc(tail_size[0])` (near: low word; far: long) and read it. Returns 1 |
| `2008:0862` / `0889` | `load_all_far` / `load_all_near` | `load_all(args…, far = 1 / 0)` |
| `2008:07e6` | `load_all(s, fp, flags, list_hdr, read_cb, far)` | `rec_file = tail_file = FFh`; `far` stored; `r` = CL garbage; flags 1: `r = load_records`; flags 2: `r = load_list`; flags 4 **and r ≠ 0**: `r = load_tails`. Returns r (flags = 4 alone uses the stale CL value — never done) |
| `2008:0382` | `load_records(s, fp, far)` | `far` stored, `owned = 1`; `total = Σ count[0..8]`; `data = alloc(recsize*total)` (16-bit product; far: sign-extended); `ok = 1`; `for i = 0; i < 9 && ok; i++: if fp[i] { ok = fread(p, recsize, count[i], fp[i]); tail_pos[i] = ftell(fp[i]); p += count[i]*recsize; }` — a present file with count 0 makes fread return 0 and **aborts** (returns 0). Returns ok ? 1 : 0 |
| `2008:04d9` | `load_list(s, fp, far, list_hdr, read_cb)` | `data = list_hdr; owned = 0`; `_fmemset(list_hdr, 0, 10)`; `hdr.recsize = recsize; hdr.count = Σ count[i]`; count 0 → `hdr.items = NULL`; else `hdr.items = xfarmalloc(count*recsize)` (always far), then per present file: `emd_set_file(fp[i])`; for each of its count[i] records at `q`: if `read_cb == 273b:0249` (the list module's "dated record" marker): `emd_read_date(q)` (`26fc:0197`, u16 at q+0) then `emd_read(q+2, recsize-2, 1)`; else if `read_cb` non-NULL: `read_cb(q)`; else `emd_read(q, recsize, 1)` (`26fc:01eb`); `q += recsize`; after the file: `tail_pos[i] = ftell(fp[i])`. Returns 1. List header layout (10 bytes): `+0 u16 recsize, +2 u16 count, +4 u16 (0), +6 far items` |
| `2008:064d` | `load_tails(s, fp, far)` | `far` stored; `sum = Σ tail_size[i]` (u32); if `sum ≤ 10000h && (sum ≤ 8000h \|\| far)`: `tail = alloc(sum)` and for each present file `fread(p, 1, tail_size[i], fp[i]); p += tail_size[i]` (near: `xmalloc(low word)`); else (too big for near): `tail_file = 0` and load only file 0's tail from fp[0] (at its current position). Returns 1 |
| `2008:0bbd` | `table_free(s)` | s outside 1..20 → `fatal(extens, 0x3AA)`; `owned == 0` (list): free `tail` if set (near/far per `far`), `list_free(data, free_cb)` (`273b:0348`); else free `data` and `tail` if set (`xfree` of the offset when near, `xfarfree` when far); `data = tail = NULL` |
| `2008:0ca2` | `table_count(s, u16 *counts)` → n | s check (fatal 0x3E9); `data == NULL` → 0; `i = 8; while (i > 0 && count[i] == 0) i--`; `i == 8` → `n = cum[7] + (fixed ? fixed : count[8])`, else `n = cum[i]`; if `counts`: copy `count[0..8]`. With fixed stride, n = count[0] + i·fixed = one past the last id of the highest present module |
| `2008:0d61` | `table_tail_size(s, u32 *sizes)` → u16 | s check (fatal 0x40A); returns Σ low words of `tail_size[i]`; copies the 9 u32 if `sizes`. Uncalled |
| `2008:0fc7` | `id_split(slot*, int id, int *local, int *file)` | `if rec_file == FFh { acc = 0; for (f = 0; f < 8 && cum[f] <= id; f++) acc += count[f]; } else for (f = 0; f < 8 && cum[f] <= id; f++) ;` `*file = f`; `f == 0` → `*local = id` (no bound check); else `rel = id - cum[f-1]`; `rel < count[f]` → `*local = rel + (rec_file == FFh ? acc : 0)`, else `*local = -1` |
| `2008:105c` | `rec_locate(slot*, id)` → local | `id_split`; if `rec_file != FFh && rec_file != file`: `swap_records(slot, file)`; return local |
| `2008:0df6` | `swap_records(slot*, char f)` | only if `count[f] > 0`: open `<base><f>.<ext>` (f == 0 also tries `<base>.<ext>`), NULL → `fatal(extens, 0x42F, name)`; list mode (`owned == 0`): `list_free(data, free_cb)`, `fseek(fp, 4, 0)`, `emd_set_file(fp)`, `list_load(data, recsize, read_cb)`; else `fseek(fp, 6, 0)`, free old `data` if set, `data = alloc(count[f]*recsize)`, read `count[f]` records; `rec_file = f`; `tail_pos[f] = ftell(fp)`; fclose |
| `2008:12eb` | `table_rec(s, id)` → far* | s check (fatal 0x502); `data == NULL` → NULL; `local = rec_locate(id)`; −1 → NULL; list mode → `list_item(data, local)` (`273b:00b6`); else `data + recsize*local` (offset arithmetic) |
| `2008:1258` | `tail_base(slot*, int f, u32 ofs)` → u32 | `ofs + Σ_{i<f} tail_size[i]` |
| `2008:128e` | `tail_locate(slot*, id, u32 *ofs)` → local | `id_split`; `tail_file == FFh` → `*ofs = tail_base(slot, file, *ofs)` (writes both words: the high word lands in the caller's stack slot after its u16 argument — harmless, normally 0); else if `tail_file != file` → `swap_tail(slot, file)`; returns local |
| `2008:109d` | `swap_tail(slot*, char f)` | only if `tail_size[f] > 0` (signed long): open file as above (fatal 0x4A5); `tail_pos[f] < 1` → `fatal(extens, 0x4A6)`; `fseek(fp, (long)(s16)tail_pos[f], 0)`; free old `tail`; alloc `tail_size[f]` (near: low word) and read; fclose. **Does not update `tail_file`** (quirk, see below) |
| `2008:138b` | `table_text(s, id, u16 ofs)` → far char* | s check (fatal 0x523); `data == NULL` → NULL; `tail_locate(slot, id, &ofs) == -1` → NULL; returns `tail + ofs` (offset add, segment of `tail`) |
| `2008:13fa` | `table_file_data(s, char f)` → far* | s check (fatal 0x53A); `rec_file != f` → `swap_records(slot, f)`; returns `data`. Caller `287b:0104` |

Text lookup idiom (`26c4:00a5 table_string(s, id)`, emd part): `rec = table_rec(s, id); return
table_text(s, id, *(u16 far*)rec)` — records of 4 bytes hold a u32 offset of which only the low word is used.

**Quirks (faithful port must keep):**
* `swap_tail` never sets `tail_file`: in the swap-mode tables (`histbf_`, `histov_`) `tail_file` stays 0, so
  every text of module ≥ 1 reloads its tail from disk, and after that a text of file 0 is served from the last
  loaded (wrong) tail with the file-0 offset. (Only matters with an add-on installed; `HISTBF_1`/`HISTOV_1`
  exist in `M1SHL`.) In swap mode `tail_pos[f]` is FFFFh (→ fatal 0x4A6) for a file whose records were never
  swapped in; the historic screens always fetch the record first, which sets it.
* `id_split` for file 0 never checks `id < count[0]` (it cannot exceed `cum[0]` there anyway).
* `load_records` fails on a present file with 0 records; the slot then stays allocated.

**Port:** keep the 20-slot table in emulated memory; the file access can be host `fopen` of the extracted
data (the volume layer is platform's). Swap mode can be implemented as "load everything" only if the tail
quirk above is reproduced deliberately (or declared a fix under `/* PORT: */`).

---------------------------------------------------------------------------------------------------------

## 5. `historic.c` — historic missions (`1f85`, V)

### 5.1 Tables

| Slot global | File (M1SHL) | Record | Meaning |
|---|---|---|---|
| `DS:5284` (`hist_slot`), count `DS:5286`, list header `DS:527A` (10 bytes), loaded flag `DS:1064` | `HIST_<n>.DAT` | list record 6 bytes: `+0 u16 key`, `+2 u16 n`, `+4 near* entries` (n × 8 bytes) | one record per historic **battle/period** (the list the player scrolls); entries = the missions of that battle |
| `DS:1065` | `HISTNM_<n>.DAT` | u32 text offset | mission names |
| `DS:1067` | `HISTBF_<n>.DAT` | u32 text offset | briefings (swap mode) |
| `DS:1069` | `HISTOV_<n>.DAT` | u32 text offset | overviews (swap mode; also read by `13be:0339`) |
| `DS:106B` | `HISTSN_<n>.DAT` | u32 text offset | synopses |

File layout of `HIST_<n>.DAT` (flag 2, tail 0): `u32 0, u16 count`, then count × `{u16 key, u16 n, n × {u16 e0,
e2, e4, e6}}`. Example `HIST_0.DAT`: 14 records; first `{key 10, n 1, {0, 0, 8, 3}}`, second `{40, 1, {1, 1, 4,
2}}`, third `{13, 3, {8,8,6,3},{9,9,8,3},{10,10,8,3}}`. `HIST_1.DAT` (1946): 8 records, ids 20.. (fixed 20).

Entry fields (from the users in `0583` flyhist.c, L): `e0` = text id into `histnm_`/`histsn_` (mission name /
synopsis), `e2` = **mission file number** (`MISS<e2>.DAT`; `e2 > 58` → module 1), `e4` = index into the
bitmap table `DS:424E` (picture), `e6` = side/service selector compared with `DS:4267` (the side the player
chose). Record `key` → `287b:026e(key)` (emd2: probably a date or campaign id → text).

### 5.2 Functions

| Address | Name | Behaviour |
|---|---|---|
| `1f85:0007` | `hist_exists(id)` | `table_rec(hist_slot, id) != NULL` |
| `1f85:0027` | `hist_read_rec(far *rec)` | list read callback: `emd_read(rec, 2, 1)` (key); `emd_read_near(&n, 2, 1)` (`26fc:0098`); `rec.+2 = n`; `rec.+4 = xmalloc(n << 3)`; `emd_read_near(rec.+4, 8, n)` |
| `1f85:0094` | `hist_free_rec(far *rec)` | list free callback: `xfree(rec.+4)` |
| `1f85:00b7` | `hist_open()` | if `!DS:1064`: `hist_slot = table_load("hist_", "dat", 6, 20, 12h, 2, &DS:527A, hist_read_rec, hist_free_rec)`; 0 → `fatal(historic, 0x58)`; `DS:5286 = table_count(hist_slot, NULL)`; `DS:1064 = 1` |
| `1f85:0139` | `hist_close()` | `table_free(hist_slot); DS:1064 = 0` |
| `1f85:014d` | `hist_count()` | `DS:5286` |
| `1f85:0157` | `hist_key(id)` | rec NULL → fatal 0x8F; returns `rec.+0` |
| `1f85:01a4` | `hist_n(id)` | rec NULL → fatal 0x9E; `rec.+2` |
| `1f85:01f2` | `hist_e0(id, i)` | rec NULL → fatal 0xAD; `entries[i].e0` (no bound check on i) |
| `1f85:024b` | `hist_e2(id, i)` | fatal 0xBC; `entries[i].e2` |
| `1f85:02a5` | `hist_e4(id, i)` | fatal 0xCB; `entries[i].e4` |
| `1f85:02ff` | `hist_e6(id, i)` | fatal 0xDA; `entries[i].e6` |
| `1f85:0359` | `hist_has_side(id, v)` | `hist_exists(id)` and some `i < n` with `e6 == v` → 1, else 0 |
| `1f85:039f` | `hist_count_side(id, v)` | 0 if not exists; else number of entries with `e6 == v` |
| `1f85:03e9` | `hist_nth_side(id, v, k)` | `n = hist_n(id); seen = 0; for (i = 0; i < n; i++) { if (seen >= k && e6(i) == v) return i; if (e6(i) == v) seen++; } return n` — index of the k-th (0-based) entry with side v |
| `1f85:043b` / `04bd` | `histnm_open()` / `histnm_close()` | open: slot `DS:1065` must be 0 (fatal 0x137); `table_load("histnm_", "dat", 4, 20, 12h, 5, 0…)`; 0 → fatal 0x143; returns 1. close: slot 0 → fatal 0x149; `table_free`; slot = 0 |
| `1f85:04fb` / `057d` | `histbf_open()` / `close()` | same for `DS:1067`, `"histbf_"`, mode 0Ah (swap far); fatals 0x156 / 0x162 / 0x168 |
| `1f85:05bb` / `063d` | `histov_open()` / `close()` | `DS:1069`, `"histov_"`, mode 0Ah; fatals 0x175 / 0x181 / 0x188 |
| `1f85:067b` / `06fd` | `histsn_open()` / `close()` | `DS:106B`, `"histsn_"`, mode 12h; fatals 0x195 / 0x1A1 / 0x1A7 |
| `1f85:073b` | `histnm_text(id)` | slot 0 → fatal 0x1B0; `table_string(DS:1065, id)` (`26c4:00a5`) → far char* |
| `1f85:0779` | `histbf_text(id)` | `DS:1067` (fatal 0x1BE) |
| `1f85:07b7` | `histov_text(id)` | `DS:1069` (fatal 0x1CB) |
| `1f85:07f5` | `histsn_text(id)` | `DS:106B` (fatal 0x1D9) |

`1f85:0833` (the "select active extension" function named in the brief) is `module_set_active` =
`2008:0003` (§4.6). The historic screen calls it with `mission_number > 58` (0 or 1) after loading
`MISS<n>.DAT` (`0583:03c2`), and `3164:05f9 single_open` with the index of the chosen `SINGLE*.DAT` file.
The active module is later OR-ed as a bit into SIM.IN (`1193:093e`: `DS:4B8D |= bit[module_active()]`).

---------------------------------------------------------------------------------------------------------

## 6. Description texts (`214d`, `2164`, `1f7f`, V)

### 6.1 `shiptext.c` (`214d`)

`SHIPTXT<n>.DAT`: 23-byte records `{+0 u16 text offset, +2 u8 nation (FFh = none: "GHOST SHIP"; 1 = US …),
+3 char[20] name}` + text tail (descriptions). Slot `DS:528C`, count `DS:528A`.

| Address | Name | Behaviour |
|---|---|---|
| `214d:0005` | `shiptxt_open()` | `DS:528C = table_load("shiptxt", "dat", 23, 15, 12h, 5, 0…)`; 0 → `fatal(shiptext, 0x31)`; `DS:528A = table_count(DS:528C, NULL)` |
| `214d:006f` | `shiptxt_close()` | `table_free(DS:528C)` (slot variable not cleared) |
| `214d:007e` | `shiptxt_name(id)` | rec NULL → fatal 0x41; `24d5:0005(rec + 3)` (emd string helper, returns the name) |
| `214d:00d6` | `shiptxt_is_nation(id, char v)` | rec NULL → 0; else `rec.+2 == v` |
| `214d:0112` | `shiptxt_count()` | `DS:528A` |
| `214d:011c` | `shiptxt_text(id)` | rec NULL → fatal 0x62; `table_text(DS:528C, id, rec.+0)` |

### 6.2 `planetxt.c` (`2164`)

`PLTXT<n>.DAT`: 2-byte records = text offset; tail = plane descriptions ("The P-38F was …"). Slot `DS:1B2C`.

| Address | Name | Behaviour |
|---|---|---|
| `2164:000c` | `pltxt_open()` | slot ≠ 0 → `fatal(planetxt, 0x11)`; `DS:1B2C = table_load("pltxt", "dat", 2, 15, 12h, 5, 0…)` (no failure check) |
| `2164:0065` | `pltxt_close()` | `table_free(DS:1B2C); DS:1B2C = 0` |
| `2164:007a` | `pltxt_text(id)` | rec NULL → fatal 0x2A; `table_text(DS:1B2C, id, *(u16*)rec)` |

### 6.3 Medal abbreviations (`1f7f`)

Uses the emd text-table loader `26c4:02d9(base, ext, stride)` (emd1 part: merges `<base>0..8.<ext>` via
`open_module_files`; format `u16 n, u16 off[n], strings`, string i at `base + (n+1)*2 + off[i]`).
`MEDABBR0.DAT` = 20 strings ("Purple Heart", "Air Medal", …). Handle far `DS:1054`.

| Address | Name | Behaviour |
|---|---|---|
| `1f7f:0001` | `medabbr_open()` | `DS:1054:1056 = 26c4:02d9("medabbr", "dat", 15)` |
| `1f7f:0021` | `medabbr_close()` | `26c4:001a(DS:1054)` (farfree); handle = NULL |
| `1f7f:0041` | `medabbr_text(i)` | `26c4:0039(handle, i)` (fatal text.c 0x20 if i out of range) |

Callers: `1656:0095` (open/close), `0f35:01d8` (text).

---------------------------------------------------------------------------------------------------------

## 7. `ranks.c` — `RANKS.DAT` (`225d`, V)

File (`SHELL1\RANKS.DAT`, 505 bytes): `u16 n` (18); n × 6-byte records; `u16 text_len` (393); text (NUL-terminated
names). Record: `+0 u16 name offset` (converted to a near pointer at load), `+2 u8 service` (0 USN, 1 USMC,
2 USAAF, 3 IJN, 4 IJA), `+3 u16 points` (unaligned: **promotion threshold**), `+5 u8 extra` (L: the skill /
wingman class used by `3164:08b3`).

| # | Name | svc | points | +5 |
|---|---|---|---|---|
| 0–2 | NAVY ENSIGN / LIEUTENANT JUNIOR GRADE / LT | 0 | 0 / 300 / 600 | 3 / 1 / 0 |
| 3–5 | MARINE 2ND LIEUTENANT / 1ST LIEUTENANT / CAPTAIN | 1 | 0 / 300 / 600 | 3 / 1 / 0 |
| 6–8 | ARMY 2ND LIEUTENANT / 1ST LIEUTENANT / CAPTAIN | 2 | 0 / 300 / 600 | 3 / 1 / 0 |
| 9–12 | IMPERIAL NAVY PETTY OFFICER 2ND CLASS / 1ST CLASS / WARRANT OFFICER / LIEUTENANT JUNIOR GRADE | 3 | 0 / 200 / 400 / 600 | 3 / 2 / 1 / 0 |
| 13–17 | ARMY SERGEANT / MASTER SERGEANT / 2ND LIEUTENANT / 1ST LIEUTENANT / CAPTAIN | 4 | 0 / 100 / 200 / 300 / 400 | 3 / 2 / 1 / 0 / 0 |

| Global | Meaning |
|---|---|
| `DS:52AE` | near* text block |
| `DS:52B0` | near* record array (n × 6) |
| `DS:52B2` | s16 n |

| Address | Name | Behaviour |
|---|---|---|
| `225d:0006` | `ranks_load()` | `f = vol_fopen(file_name("ranks", -1, "dat"), "rb")`, NULL → `fatal(ranks, 0x2F)`; `fread(&DS:52B2, 2, 1)`; `DS:52B0 = xmalloc(n*6)`; `fread(DS:52B0, 6, n)`; `fread(&len, 2, 1)`; `DS:52AE = xmalloc(len)`; `fread(DS:52AE, 1, len)`; fclose; `rec[i].+0 += DS:52AE` for all i |
| `225d:00f7` | `rank_name(char r)` | `rec[r].+0` (char*). Uncalled |
| `225d:010f` | `rank_service(char r)` | `rec[r].+2` |
| `225d:0128` | `rank_points(char r)` | `*(u16*)&rec[r].+3` — promotion-point threshold (`050c:0147` promotion, `0ed9:*`) |
| `225d:0141` | `rank_extra(char r)` | `rec[r].+5` (`3164:08b3`) |
| `225d:015a` | `rank_first(char svc)` | `for (r = 0; r < n && rec[r].svc != svc; r++) ; return r` (s8; n if none) |
| `225d:018d` | `rank_last(char svc)` | skip to the first r with svc, then advance while svc matches; return r − 1 (n − 1 if none). = the service's top rank |
| `225d:01de` | `ranks_free()` | `xfree(DS:52B0); xfree(DS:52AE)` |

Index arithmetic is on signed chars (`r * 6` sign-extended).

---------------------------------------------------------------------------------------------------------

## 8. TTM hook table and `MEDLOCS.DAT` (`2221`, V)

`DS:1B80` = far function table called by the TTM interpreter's "call hook n" (`3baf:0540` → `2221:0111(n)`):
`[0] = 2221:0003`, `[1] = 2221:0107`, `[2] = 2221:0107` (V img dump; the table is `DS:1B80..1B8B`, 3 entries:
`DS:1B7C` is "TTD" before it and the "medals" string follows; no bound check on n).

| Address | Name | Behaviour |
|---|---|---|
| `2221:0111` | `ttm_hook(int n)` | `if (DS:1B80[n] != NULL) DS:1B80[n]()` |
| `2221:0003` | `hook_draw_medal()` | `125a:00ab()` (leave the TTD dir, shell_ui); `DS:0A16 = bmp_load_planes(file_name("medals", -1, "bmp"))` (`168a:011c`); read `MEDLOCS.DAT` = 20 × 4 bytes into a stack array (`1193:0176(buf, 4, 20, name)`); `125a:0060("TTD")`; `m = (s8)DS:0500` (the medal being awarded); `w = medlocs[m].+2`; `h = frame[m].+8` (bitmap height); `x = 106 − (w >> 1)`, `y = 105 − (h >> 1)` (sar); `pages_front_to_work()`; `draw_bitmap(frame[m], x, y, 0)`; `pages_work_to_spare()`; `copy_rect(x, y, w, h)`; `3a73:0085(x, y, w, h, 1, DS:2310, DS:2314, 0, 0, 0)` (TTM: register the rectangle as a sprite/background region, video part); `168a:04b1(DS:0A16)` (free bitmap) |
| `2221:0107` | `hook_1()` | `0874:0aa5()` (shell_ui) |

`MEDLOCS.DAT` (80 bytes): 20 × `{u16 a, u16 w}`; `a` = 82h..86h (unused here), `w` = 17h..23h (medal width).

---------------------------------------------------------------------------------------------------------

## 9. `queue.c` — circular queue (`2242`, V)

Queue (6 bytes, near heap): `+0 head` (sentinel node), `+2 cur` (cursor node), `+4 count`. Node (4 bytes):
`+0 data`, `+2 next`. The sentinel's `next` closes the ring. Only user: `050c:01ba` (shell_ui).

| Address | Name | Behaviour |
|---|---|---|
| `2242:0005` | `q_new()` | `q = xmalloc(6); s = xmalloc(4); q.head = q.cur = s; q.count = 0; s.data = 0; s.next = s` |
| `2242:003f` | `q_seek_last(q)` → data | `n = q.head; while ((q.cur = n.next).next != q.head) n = q.cur;` returns `q.cur.data` (empty queue: cur = sentinel, data 0) |
| `2242:0067` | `q_next(q)` → data | `q.cur = q.cur.next; return q.cur.data` (returns 0 at the sentinel). Uncalled |
| `2242:0081` | `q_append(q, data)` → data | `data == 0` → `fatal(queue, 0x66)`; `q_seek_last(q)`; `n = xmalloc(4); n.data = data; n.next = q.cur.next; q.cur.next = n; q.cur = n; q.count++` |
| `2242:00e6` | `q_clear(q)` | `while ((n = head.next) != head) { head.next = n.next; xfree(n); q.count--; }` (data not freed) |
| `2242:011e` | `q_delete(q)` | `q == NULL` → fatal 0x9C; `q_clear`; `count != 0` → fatal 0x9E; `xfree(head); xfree(q)` |
| `2242:018b` | `q_rewind(q)` | `q.cur = q.head` |
| `2242:019a` | `q_at_end(q)` | `q.cur.next == q.head` (AL = 1/0) |

Iteration idiom: `q_rewind; while (!q_at_end) { d = q_next … }` (the caller inlines `q_next`).

---------------------------------------------------------------------------------------------------------

## 10. `threed.c` — 3-D object viewer (`217d`, `21d4`, V/L)

Used by the reference ("view planes / ships") screen `0ddd` (shell_ui): shows one aircraft or ship shape
over a small 3-D background ("land" or "sea" world with ships). The 3-D engine calls belong to render3d:
`48ea:0158(slot, name)` load shape table (far* or NULL), `48ea:0236(slot)` unload, `47c8:0132` create view,
`47c8:0188` free view, `47c8:02f1/0336/0267/03b1` shape queries, `3d50:237b(view)` set camera,
`4708:0925(obj)` draw object, `48ac:0005(pos, out)` projection test, `48ac:013a(n)` set background/sky,
`2b1f:021d(a, b)` distance (emd2). `DS:76D2` = render3d shape-table descriptor (fields +6/+8 and +12h/+14h
set to FFFFh / 100h after each load).

Object record (22 bytes, `DS:52A4` main object, `DS:52A2` camera target, background objects): `+00 u16 shape`,
`+02 s32 x, +06 s32 y?, +0A s32 z/alt` (L: 3 × s32 position), `+0E 6 bytes` (3 × s16 angles, L), `+14 near*
draw attributes` (DS:1B38 `02 00 FF 00 00` for aircraft view / DS:1B3D `02 FF FF…` otherwise; DS:1B3E for
background objects; byte +1 = sub-shape/detail).

| Global | Meaning |
|---|---|
| `DS:528E` | u8 `is_aircraft` view flag (enables the altitude offset and shadow) |
| `DS:528F` | u8 side (1 = allied → `a_ship`, else `j_ship`); copied to `DS:1B3F` |
| `DS:5294` | s16 altitude offset of the main object (0 unless `is_aircraft`) |
| `DS:1B45` | u8 main shape loaded |
| `DS:52A0` | near* view (camera) from `47c8:0132`; `+00 u16 = 7` (shift), `+0A..+10` window rect, `+12 near* shades` (256 bytes of `SHADES.DAT`) |
| `DS:52A2` | near* camera target object (22 bytes); `+06 s32` = −distance |
| `DS:52A4` | near* main object (22 bytes) |
| `DS:5296` | s16 number of background objects |
| `DS:5298` | near* background objects (n × 22) |
| `DS:529A` | near* u16[n] draw-order pointer array |
| `DS:529C` | far* background shape table |
| `DS:5290` | far* s32[n] distance scratch |
| `DS:52A6` | s16 number of leading "always first" objects (not distance-sorted) |

| Address | Name | Behaviour |
|---|---|---|
| `217d:0170` | `view3d_init(u8 side, u8 is_aircraft)` | `DS:528E = is_aircraft; DS:3B55 = 4; DS:528F = side`; `DS:52A4 = memzero(xmalloc(22))`, `.+14 = is_aircraft ? DS:1B38 : DS:1B3D`; `DS:52A2 = memzero(xmalloc(22))`; `DS:52A0 = 47c8:0132(DS:52A2)`; `*DS:52A0 = 7`; `DS:52A0.+12 = xmalloc(256)`; `file_read(.+12, 1, 256, file_name("shades", -1, "dat"))` (`1193:0176`) |
| `217d:0227` | `view3d_done()` | `xfree(view.+12); 47c8:0188(view); xfree(DS:52A2); xfree(DS:52A4)` |
| `217d:000a` | `view3d_load_model(u8 type, int alt)` | `DS:5294 = is_aircraft ? alt : 0`; if not loaded: `name = file_name(0ddd:0094(type), -1, "tbl")` (0ddd:0094 = model base name, shell_ui); `if (48ea:0158(0, name))` { `DS:76D2.+6 = FFFFh, +8 = 100h`; if `is_aircraft && 47c8:02f1(0) > 1`: `DS:52A4.+14[1] = 47c8:0336(0, 1) − 1`; `DS:1B45 = 1` } |
| `217d:009f` | `view3d_unload_model()` | if loaded: `48ea:0236(0); DS:1B45 = 0` |
| `217d:00b9` | `view3d_set_window()` | if loaded: `view.+0A = DS:5FDA, +0C = DS:5FD8, +0E = DS:5FD6, +10 = DS:5FD4` (current window x, y, w, h) |
| `217d:00e1` | `view3d_distance()` → int | `r = 47c8:03b1(DS:52A4.+0)` (shape radius), `v = (s16)(((long)r << view.+0) / (long)DS:5FD6)` (LXLSH by the u8 at view+0, LDIV by the window width); returns `(v >> 1) + (v >> 2) + (v >> 4)` (arithmetic shifts, ≈ 0.8125 v) |
| `217d:0130` | `view3d_draw_model()` | if loaded: `d = view3d_distance(); DS:52A2.+06 (s32) = -(long)d; view3d_set_window(); DS:2318 = DS:2312; 3d50:237b(view); 4708:0925(DS:52A4); DS:2303 = 0` |
| `217d:0257` | `view3d_load_scene(char scene)` | `48ac:013a(scene ? 0x28 : 2)`; `DS:1B3F = DS:528F`; world = scene ? `"sea"` : `"land"`; shapes = scene ? (`DS:528F == 1` ? `"a_ship"` : `"j_ship"`) : `"land"`; **scene == 2** → no background (5290/5292/5296/5298/529A = 0). Else: `DS:529C = 48ea:0158(1, file_name(shapes, -1, "tbl"))`, NULL → `fatal(threed, 0xE7)`; `DS:76D2.+12 = FFFFh, +14 = 100h`; `f = vol_fopen(file_name(world, -1, "wld"), "rb")`, NULL → fatal 0xED; `n = flength(f) / 20` (LDIV) → `DS:5296`; `DS:529A = xmalloc(2n)`; `DS:5298 = xmalloc(22n)`; per record: `fread(rec, 20, 1, f)`; `obj = memzero(22)`; `obj.+0 = rec.+0 + 1`; `obj.+14 = DS:1B3E`; `obj.+0E = rec.+2` (6 bytes); `obj.+2 = rec.+8` (12 bytes); `order[i] = obj`; fclose; `DS:5290 = xfarmalloc(4n)`; `DS:52A6 = view3d_presort(order, n, DS:5290)` |
| `217d:045d` | `view3d_sort_scene()` | `21d4:01e1(view, order, n, DS:5290)` |
| `217d:047e` | `view3d_unload_scene()` | `xfarfree(DS:5290); xfree(DS:5298); xfree(DS:529A); 48ea:0236(1)` |
| `217d:04b0` | `view3d_draw_scene()` | `tmp = *DS:52A4` (22-byte copy); draw every `order[i]` (`4708:0925`); if `is_aircraft`: `di = DS:52A4.+0A` (low word), `DS:52A4.+0A = (long)DS:5294`; if `48ac:0005(DS:52A4 + 2, &tmp + 2)`: `tmp.+0A += (long)(s16)di; DS:3B53 = 1; draw(tmp) /* shadow */; DS:3B53 = 0`; `DS:52A4.+0A += (long)(s16)di`. Then `DS:52A4.+0 = 0`; `draw(DS:52A4)`; if `is_aircraft`: `DS:52A4.+0A = (long)(s16)di` (restore); `DS:2303 = 0`. (L: the main object is drawn with shape 0 of table 0; exact meaning of `48ac:0005` belongs to render3d) |

`WLD` file (`LAND.WLD`, `SEA.WLD`): n × 20 bytes `{u16 shape index, 6 bytes angles, 12 bytes position}`.

Depth sort (`21d4`):

| Address | Name | Behaviour |
|---|---|---|
| `21d4:0150` | `cmp_priority(a, b)` | qsort comparator: `47c8:0267(**b) − 47c8:0267(**a)` (u8 shape priority, descending) |
| `21d4:017f` | `presort(u16 *order, int n)` → k | `qsort(order, n, 2, cmp_priority)`; returns the first index whose priority byte is 0 (n if none) |
| `21d4:01cd` | `view3d_presort(order, n, far dist)` | `DS:52A6 = presort(order, n)` (dist unused) |
| `21d4:0008` | `sort_by_distance(view, u16 *order, int n, s32 far *dist)` | if n ≥ 2: `eye = view.+2` (object pointer) `+ 2`; `dist[i] = 2b1f:021d(eye, order[i] + 2)`; selection sort descending: for i in 0..n−2: find j > i with the largest dist (strictly greater, signed high word / unsigned low word) and swap `dist` and `order` entries — painter's order, farthest first |
| `21d4:01e1` | `view3d_sort(view, order, n, dist)` | `sort_by_distance(view, order + DS:52A6, n − DS:52A6, dist)` |

Note: qsort (Borland) is not stable; the port must use the same algorithm (`0000:3c66`, platform RTL) or
the order of equal-priority objects may differ (cosmetic).

---------------------------------------------------------------------------------------------------------

## 11. UI / video glue

These segments carry no source tag. `2171`, `21f4`, `229e`, `22a0`, `230d`, `2316` are shell input/video
helpers; by content they belong to **shell_ui** (21f4 = the PS copy of INTRO `0460` "intro.c" TTM player,
2316 = INTRO `0491` mouse glue, 22a0 = INTRO `10fc` timers). Specced here because they sit in the sys range.

### 11.1 `2171:000a wait_ticks_or_key(int ticks)` (V)

`DS:2E3F = ticks` (PIT countdown, 236.7 Hz, decremented by `timer_isr`); `hit = 0`; `while (DS:2E3F && !hit)
{ k = kbd_getkey(); DS:6017 = k & FFh; DS:6016 = k >> 8 (sar); if (menu_hotkey(DS:6016) == 0) { hit =
scan ∈ {1Ch, 01h, 39h}; if (DS:43B6 /*joystick*/ && !hit) hit = joy_button(0) || joy_button(1); if (DS:43B7
/*mouse*/ && !hit) hit = mouse_button(0) || mouse_button(1); } }` — a keypress handled as a hotkey leaves
`hit` unchanged. Callers `0874:0b57`, `1305:02bd`.

### 11.2 TTM player (`21f4`) — contains an RNG call

PS twin of INTRO `0460` (spec: `shell_ui.md` §2.4); differences are noted.

| Global | Meaning |
|---|---|
| `DS:52AA` | u32 TTM tick counter (59.17 Hz: timer callback with reload 4) |
| `DS:52A8` | timer handle |
| `DS:76A4` | frame delay set by the TTM script (FFFFh = unchanged) |

| Address | Name | Behaviour |
|---|---|---|
| `21f4:0009` | `ttm_tick()` | timer callback: `DS:52AA` (u32) += 1 |
| `21f4:0018` | `ttm_skip_check()` → continue | `if (menu_hotkey(…) != 0) return 1`; `skip = key_down(1Ch) \|\| key_down(01h) \|\| key_down(39h)`; `kbd_getkey()` (discard one key); joystick (`DS:43B6`) / mouse (`DS:43B7`) buttons as in §11.1; return `!skip`. (INTRO has no hotkey test) |
| `21f4:00cd` | `ttm_open(name)` → ok | `clip_full()`; `DS:52A8 = timer_add(21f4:0009, reload 4)`; `DS:52AA = 0`; `ttm_init` (`3b02:0014`); `ttm_load(name)` (`3b02:0030`) == −1 → `ttm_free` (`3b02:095d`), `timer_remove(DS:52A8)`, return 0; else return `3b02:03a8(0) >= 1` |
| `21f4:0134` | `ttm_close()` | `3b02:06c6(0)`; `ttm_free`; `timer_remove(DS:52A8)` |
| `21f4:0151` | `ttm_play(first, last, far cb)` → r | identical to `intro_ttm_play` (shell_ui §2.4) with `ttm_run_frame = 3b02:05ef`, show = `16e3:35d1(1)` (page flip) and `3a73:03d8(0)`; delay persists across frames; wait loop `while (t0 + delay > DS:52AA)` (unsigned 32-bit) calling `cb` each spin if non-NULL; returns −1 (cb returned 0), −2 (script ended), else the next frame index. (No Windows sound hook in PS) |
| `21f4:0245` | `ttm_play_file(name, last, nrand, span, end_frame, far cb)` | see below |

```c
void ttm_play_file(char *name, int last, int nrand, int span, int end_frame, far int (*cb)(void))   /* 21f4:0245 */
{   if (!ttm_open(name)) return;
    chdir_ttd("TTD");                               /* 125a:0060 */
    r = ttm_play(0, last, cb);
    if (r == -2) goto out;
    if (r != -1) {
        r += rng_below(nrand) * span;               /* **RNG: 24b7:00c8(nrand)** picks one of nrand variants */
        r = ttm_play(r, r + span, cb);              /* play frames [r, r+span) */
        if (r == -2) goto out;
    }
    ttm_run_frame(end_frame - 1);                   /* skipped or finished: run the exit frame */
out:
    chdir_back();                                   /* 125a:00ab */
    ttm_close();
}
```
The INTRO version adds a fixed `extra` instead of `rng_below(nrand) * span`. RNG call site: **one
`rng_below(nrand)` per call, only when the first part was not skipped (r ≠ −1) and did not end (r ≠ −2)**;
with nrand < 2 `rng_below` returns 0 without calling `rng_next` (no draw). Callers: `04df:0002`, `0874:0b57`,
`0f35:01d8` (shell_ui); every caller passes `cb = ttm_skip_check` (`21f4:0018`). `04df` (`end_frame` 1CDh),
`0874` and the second `0f35` call (`end_frame` 19h) pass `last = −1`, `nrand = span = 0` (no draw); `0f35:01d8` passes the
four s16 of a `TTMS0.DAT` entry (`data.md` §3.6) as `last, nrand, span, end_frame`: `PRISJAP/PRISUSA [-1,0,0,7]`
(no draw), `MEDJAP/MEDUSA [1,2,1,4]` and `JAPFLAG/USAFLAG [75,2,3,82]` → **`rng_below(2)` picks one of two
variants** (medal ceremony / flag scene); its second call (`0f35:0314`) is a fixed script. This draw happens in the shell between missions,
so it shifts the RNG stream only if the RNG is not re-seeded before the next mission build (mission set-up
`3164:0b49` re-seeds, so mission contents are unaffected).

### 11.3 Tick counters and timers (`229e`, `22a0`)

| Address | Name | Behaviour |
|---|---|---|
| `229e:0013` | `shell_tick()` | timer callback (reload 1, 236.7 Hz, registered by `sys_init`): `DS:1CC8` (u32) += 1 |
| `229e:001f` | `shell_ticks()` | returns `DS:1CC8` (DX:AX) |
| `22a0:0009` | `tmr_expired(t)` | timer record `{u32 start, u16 len}`: `DS:2E3E == 0` (timer not installed) → 1; `el = shell_ticks() − start` (u32); expired iff `el > len` |
| `22a0:0050` | `tmr_set(t, len)` | `start = shell_ticks(); t.len = len` |
| `22a0:006a` | `tmr_set_expired(t)` | `len = 0; start = shell_ticks() − 1` |
| `22a0:0089` | `ttm_tmr_expired(t)` | as `tmr_expired` on the TTM counter `DS:52AA`, but expired iff `el >= len` (`len > el` = running) |
| `22a0:00d2` | `ttm_tmr_lerp(t, int a, int b)` → int | `DS:2E3E == 0` → a; `el = DS:52AA − start`; if `!(len > el) \|\| len == 0` → b; if `a > b` { swap a, b; `el = len − el` }; `v = a + (int)((u32)((long)(b − a) * el) / len)` (LXMUL, LUDIV unsigned); clamp v to [a, b]. Used by the TTM interpreter (`3baf:0540`) for timed fades/moves |
| `22a0:018e` | `ttm_tmr_set(t, len)` | `start = DS:52AA; t.len = len` |
| `22a0:01aa` | `ttm_tmr_set_expired(t)` | `len = 0; start = DS:52AA − 1` |
| `22a0:01cb` | `dir_first(char *pattern, int attr)` | `DS:540F = 1; DS:540D = pattern; DS:540B = attr` |
| `22a0:01e2` | `dir_next()` → char* | `DS:540F ? findfirst(DS:540D, &ffblk DS:52B4, DS:540B) : findnext(&ffblk)`; `DS:540F = 0`; success → `DS:52D2` (ffblk.ff_name) else NULL |
| `22a0:0225` | `strip_ext(char **names, int n)` | for each: `p = strchr(name, '.'); if (p) *p = 0` |
| `22a0:025d` | `dir_list(char *pattern, int *n)` → char** | `DS:53E3[i] = DS:52DF + 13 i` (i < 20); `dir_first(pattern, 0)`; copy up to 20 names (`strcpy`); `*n` = count; 0 → NULL; else `strip_ext` and return `DS:53E3`. (Uncalled here; `1513:0208` has an inlined copy — pilot / tape lists) |
| `22a0:02cb` | `file_exists(char *pattern)` | `dir_first(pattern, 0); return dir_next() != NULL`. Uncalled |

`22a0:0009`/`0050` are also listed in `shell_ui_toolkit.md`.

### 11.4 Input toggles (`230d`) and mouse glue (`2316`)

| Address | Name | Behaviour |
|---|---|---|
| `230d:000d` | `mouse_enabled()` | `(int)(s8)DS:43B7` |
| `230d:0018` | `mouse_toggle()` | `DS:43B7 ^= 1`; if now on: `DS:43B7 = (DS:308E != 0)` (driver present); if still on: `mouse_move_to(DS:601A, DS:6018)` (current cursor x, y) |
| `230d:0058` | `joy_enabled()` | `(int)(s8)DS:43B6` |
| `230d:0063` | `joy_recheck()` | if enabled: `DS:0FF8 = 0; 16e3:00ac()` (joystick detect); `DS:43B6 = (DS:0FF8 != 0)` |
| `230d:008b` | `joy_toggle()` | `DS:43B6 ^= 1; joy_recheck()` |
| `2316:000f` | `mouse_glue_init()` | DOS < 3 (`DS:0092`) → 0; else `mouse_init()` (`16e3:3d64`) |
| `2316:0028` | `mouse_glue_shutdown()` | DOS < 3 → 0; else `16e3:3f14` |
| `2316:0041` | `mouse_get_pos(int *x, int *y)` | DOS < 3 → 0; else `16e3:3f30(x, y)` |
| `2316:0062` | `mouse_button(n)` | DOS < 3 → 0; else `16e3:3f85(n)` |
| `2316:007f` | `mouse_move_to(x, y)` | DOS < 3 → 0; `mouse_get_pos`; already there → 1; else `mouse_set_pos(x, y)` (`16e3:3f5a`) |

`DS:43B6` / `DS:43B7` are CONTROL.PRF bytes +06/+07 (joystick / mouse enabled, `DS:43B0` buffer).

---------------------------------------------------------------------------------------------------------

## Port notes

* `/* PORT: */` `far_alloc` / `far_free` / `xmalloc` → host allocator with the same fatal-on-NULL contract;
  the far/near distinction of `extens.c` only selects the heap and the read routine.
* `/* PORT: */` volume-aware `vol_fopen`/`fseek`/`ftell`/`flength` → platform file layer over the extracted
  `.DYN` volumes (`M1SHL` shadows `SHELL1`).
* Timers: `DS:1CC8` (236.7 Hz) and `DS:52AA` (59.17 Hz) must advance in real time (platform timer), and
  `DS:2E3F` must count down at 236.7 Hz; the TTM player and `wipe_rect` busy-wait on them — the port loop
  must pump events/present inside those waits.
* `mission_write_script` writes the mission file byte-for-byte to `SCRIPT.DAT`: keep.
* `extens.c` quirks (§4.6) are faithful by default.

## Hand-offs

* **lead (script.c `3164`)**: `mission_load` calls `3164:34ad(n_aircraft, n_ships, n_places, n_waypoints,
  n_groups, n_type3)` then the per-record callbacks `3164:3694` (type 1, 22 bytes), `36d0` (type 2, 16),
  `366d` (type 3, 6), `36f6` (type 4, 10), `3788` (type 5, 58), `371d(&{kind,index}, &payload)` (type 7,
  payload 12 or 4 bytes); the header goes straight to `DS:626B` (90 bytes); then `3164:3efe(name)`. Type-8/9
  runs end up in far `DS:5272` (u16 offsets) / `DS:5276` (text) and are freed by the callers. `ships` count
  includes type-5 groups with `rec[0] == 1`.
* **lead / shell_ui**: `module_set_active` = `2008:0003` = `1f85:0833` (same code); `DS:5288`; RESOURCE.CFG
  `modules` = `DS:43B4`, `latest` = `DS:43B5`.
* **emd1/emd2**: `26c4:00a5 table_string(slot, id)` = `table_text(slot, id, *(u16*)table_rec(slot, id))`;
  `26c4:02d9` uses `open_module_files` (`2008:00a8`) + `files_foreach`/`files_close`; `273b:0249` is a marker
  callback that `load_list` special-cases (u16 date + raw record); `26fc:000c` = `emd_set_file(fp)` (sets
  `DS:5AFA`, `DS:5AF8 = flength`), `26fc:01eb emd_read(far dst, size, n)`, `26fc:0098 emd_read_near`.
  `287b:0104` uses `table_file_data` (`2008:13fa`, swap mode).
* **shell_ui**: `21f4:0245` (TTM player with `rng_below(nrand)`), `2171:000a`, `22a0` timers/dir list,
  `230d` toggles, `2316` mouse glue, `22ce` page setters and `wipe_rect` are UI code by function; `2221`
  hook 1/2 → `0874:0aa5`. `0ddd:0094(type)` returns the model base name for `view3d_load_model`.
* **render3d**: `threed.c` uses `48ea:0158/0236`, `47c8:0132/0188/02f1/0336/0267/03b1`, `3d50:237b`,
  `4708:0925`, `48ac:0005/013a`, flags `DS:3B53` (shadow pass), `DS:3B55 = 4`, `DS:2303`.
* **video (TTM)**: `3baf:0540` calls `2221:0111(n)` (hook), `22a0:0009/00d2/018e`.

## Open questions

* Hist entry fields `e0/e4/e6` and record `key` meanings are inferred from the flyhist screen (L); `287b:026e`
  (emd2) will tell what `key` is.
* `RANKS.DAT` +5 byte meaning (used by `3164:08b3`, lead).
* `MEDLOCS.DAT` first word per entry (82h–86h) unused in PS — maybe used by the AP or a leftover.
* `threed.c`: the object field at +06/+0A (which axis is altitude) and `48ac:0005` semantics (shadow?) are
  render3d's; the main object drawn with shape 0 (`+0 = 0`) is L.
* Which TTM scripts call hooks 1/2 (`0874:0aa5`, shell_ui).
