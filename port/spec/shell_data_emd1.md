# shell_data part `emd1`: world database, string tables, aces, squadrons, emd/list/text helpers (PS.EXE)

Part of module `shell_data` (lead file `shell_data.md`). Target `Game/PS.EXE`, DGROUP `4D08`. Segments:
`2322` (`emd\wdata.c`), `242f` (`emd\wdutil.c`), `2455` (tag/name list), `249b` (binary file I/O),
`24d5` (string pool / far-near strcpy), `24e3` (`sys\strp.c`: string tables), `2550` (`emd\ace.c`),
`2624` (`emd\squad.c`), `26c4` (`emd\text.c`), `26fc` (`emd\emd.c`), `273b` (`emd\list.c`).
Symbols: `scratchpad\emd1_symbols.csv` (merged by the lead into `shell_data_symbols.csv`).

Everything below was read from `tools/x86dis.py` output where arithmetic, signedness or control flow
matters (marked **verified**); simple accessors were read from the Ghidra decompile and spot-checked
(**verified** unless marked **likely** / **guess**). File layouts were checked against every shipped
file in `work/dyn/*` (scratch scripts `emd1_wd.py`, `emd1_parse.py`, `emd1_strp.py`).

**RNG:** exactly one RNG call site in all of these segments: `2624:035d` (§6.5). Everything else is
deterministic. The world-database queries (§2) consume no random numbers.

Conventions: "far NULL" = 0000:0000. `fatal(line)` = `227c:0143(0, <module seg>, line, arg)`
(shell_fatal, shell_ui); it does not return in practice — code after it (which would dereference
NULL) is irrelevant for the port. Dates are **u16 day numbers, days since 1 Jan 1900** (`3BD4h` =
7 Dec 1941), compared **unsigned**.

---

## 1. Shared low-level helpers

### 1.1 Singly linked far lists (`242f`, wdutil.c) — verified

Every node starts with `+00 far ptr next`. The sort key (for 242f:0004) is the u16 at `+04`.

| Addr | Name | Behaviour |
|---|---|---|
| `242f:0004` | `flist_insert_sorted(head, n)` | If `head == NULL` or `n.key < head.key` (unsigned): `n.next = head`, return `n`. Else walk `p` from head while `p.next != NULL && !(n.key < p.next.key)`; insert `n` after `p`; return `head`. ⇒ ascending, **equal keys stay in insertion order** (new one goes after existing equals). |
| `242f:00ad` | `flist_append(head, n)` | `head == NULL` → `n.next = NULL`, return `n`; else append at tail, return head. |
| `242f:0122` | `flist_unlink(head, n)` | `fatal(3Bh)` if head NULL. If `n == head`: return `n.next`, `n.next = NULL`. Else find predecessor (`fatal(47h)` if not found), relink, `n.next = NULL`, return head. |
| `242f:0224` | `flist_count(head)` | count nodes. Unused. |
| `242f:025b` | — | 3-byte fragment (`push bp; mov bp,sp`) at the end of the segment; not a function. |

### 1.2 Binary stream I/O (`249b`) — verified

`FILE*` = Borland stream; `getc` = `0000:0cee`, `putc` = `0000:0e39`.

| Addr | Name | Behaviour |
|---|---|---|
| `249b:0007` | `rd_u16(f)` | `a = getc; b = getc; return a + b*256` (no EOF check; EOF gives `-1 + -256`). |
| `249b:002d` | `rd_s32(f)` | 4 × getc, little endian. |
| `249b:008a` | `rd_cstring(f)` | reads bytes into `DS:541C` (256-byte buffer, **no bound**) up to and including NUL; `DS:551C` = write cursor. Returns NULL if EOF hit or the string is empty, else `DS:541C`. |
| `249b:00cf` | `wr_u16(v, f)` | 2 bytes LE; returns 1, 0 on write error. |
| `249b:010e` | `wr_u32(v, f)` | 4 bytes LE. Unused. |
| `249b:0185` | `wr_cstring(s, f)` | chars of `s` (if non-NULL) then a NUL; returns `putc != EOF`. |

### 1.3 String helpers (`24d5`) — verified

| Addr | Name | Behaviour |
|---|---|---|
| `24d5:0005` | `strpool_copy(char far *s)` → near `char*` | Ring pool `DS:5592..DS:5785` (499 bytes), cursor `DS:1DB2` (initial `5592h`). `len = _fstrlen(s)`; if `cur + len + 1 > 5785h` → `cur = 5592h`. Copy `s` incl. NUL at `cur`, return old `cur`, `cur += len+1`. Strings returned are valid only until the pool wraps. |
| `24d5:0053` | `fstrcpy_near_src(char far *dst, char *src)` | copy incl. NUL; returns dst. |
| `24d5:0091` | `strcpy_far_src(char *dst, char far *src)` | copy incl. NUL; returns dst. |
| `24d5:00bd` | `strcat_far_src(dst, src)` | `24d5:0091(dst + strlen(dst), src)`. Unused. |

### 1.4 emd sequential reader (`26fc`, emd.c) — verified

One global stream: `DS:5AFA` = `FILE*` (near), `DS:5AF8` = **u16** bytes remaining (initialised from
`filelength` truncated to 16 bits — files ≥ 64 KB would break; none are). `DS:419A` = 128-byte bounce
buffer (near → far copies).

| Addr | Name | Behaviour |
|---|---|---|
| `26fc:000c` | `emd_set_stream(f)` | `fatal(10h)` if NULL; `5AFA = f`; `5AF8 = filelength(f)`. |
| `26fc:004f` | `emd_open(name)` | `fopen(name, "rb")` (`DS:1E04`), `fatal(18h, name)` if missing; set stream; return `5AF8`. |
| `26fc:0098` | `emd_read(dst, size, n)` | `k = size*n` (u16); `fatal(20h)` if `k > remaining`; `fread(dst, k, 1)` must return 1 (`fatal(22h)`); `remaining -= k`; returns remaining. |
| `26fc:0119` | `emd_write(src, size, n)` | `fwrite(src, size*n, 1, f)`. |
| `26fc:013c` | `emd_read_u8()` | 1 byte. Unused. |
| `26fc:015b` | `emd_read_string()` | bytes into `DS:419A` until NUL (no bound), `strdup` on the near heap. Unused. |
| `26fc:0197` | `emd_read_date(u16 far *out)` | reads 3 bytes `month(0..11), day(1..31), year-1900` and stores `284f:0007(&bytes)` = day number (date.c asserts month/day validity). |
| `26fc:01eb` | `emd_read_far(dst, size, n)` | reads `size*n` bytes in ≤128-byte chunks through `DS:419A` into the far `dst`. |
| `26fc:0257` | `emd_write_far(src, size, n)` | inverse, through the bounce buffer. Unused. |
| `26fc:02c0` | `emd_close(char keep_rest)` | if `keep_rest && remaining`: `malloc(remaining)` (near) and read the rest into it. Then `fatal(74h)` unless `getc == EOF && remaining == 0`; `fclose`. Returns the near buffer or NULL. |
| `26fc:0338` | `emd_close_rest_far()` | if `remaining`: far-alloc `remaining` and read the rest (via bounce buffer). Same EOF assertion (`fatal(8Ah)`), `fclose`, return far buffer or NULL. |

### 1.5 Counted arrays "lists" (`273b`, list.c) — verified

A **list** is a 10-byte struct (far): `+00 u16 elsize`, `+02 u16 count`, `+04 u16 cursor`,
`+06 far ptr data` (count × elsize bytes, far heap). A **dated** element starts with a u16 date.

| Addr | Name | Behaviour |
|---|---|---|
| `273b:024e` | `list_read(l, elsize, rd)` | `memset(l,0,10)`; `l.elsize = elsize`; `l.count = ` 2 bytes from the emd stream; if 0 → data NULL. Else far-alloc `count*elsize` and for each element: if `rd == 273b:0249` (dated marker): `emd_read_date(el+0)` then `emd_read_far(el+2, elsize-2, 1)`; else if `rd == NULL`: `emd_read_far(el, elsize, 1)`; else `rd(el)` (far callback). ⇒ on disk a dated element is `3 + (elsize-2)` bytes. |
| `273b:0348` | `list_free(l, fr)` | if data: call `fr(el)` for each element if `fr` non-NULL; free data; `memset(l,0,10)`. |
| `273b:0249` | `list_dated_marker` | empty function; its address is the "dated" flag for `list_read`. |
| `273b:000e` | `list_count(l)` | `l.count`. Unused. |
| `273b:001c` | `list_first(l)` | `cursor = 0`; return `data` (NULL if empty). |
| `273b:0034` | `list_next(l)` | `cursor++`; return NULL if `data == NULL || cursor >= count`, else `data + cursor*elsize`. |
| `273b:0080` | `list_last(l)` | `cursor = count-1`; return `data + cursor*elsize` (no empty check). |
| `273b:00b6` | `list_at(l, i)` | `fatal(46h)` if data NULL or `i<0` or `i>=count`; `cursor = i`; return element. |
| `273b:0121` | `list_find_dated(l, date)` | NULL if data NULL or `date < el[0].date`. Else for `i = 0 .. count-2`: `fatal(69h)` if `el[i+1].date < el[i].date`; if `el[i].date <= date < el[i+1].date` → `cursor = i`, return `el[i]`. Otherwise `cursor = count-1`, return the last element. (= the entry in force at `date`.) |
| `273b:01f3` | `list_first_date(l)` | `fatal(81h)` if empty; `cursor = 0`; return `el[0].date`. Unused. |

### 1.6 Merged text tables (`26c4`, text.c) — verified

`26c4:02d9 text_load(name, ext, stride)` loads up to 9 files `<name>0.<ext> … <name>8.<ext>` (file 0
falls back to `<name>.<ext>`; opening is `2008:00a8`, extens.c) into one far block:

```
u16 total; u16 offs[total]; char text[]      (string i = text + offs[i])
```

Per file on disk: `u16 n; u16 off[n]; text (to end of file)`, text size = `filelength − 2 − 2n`.
Algorithm: `DS:5ACE = stride`. For each file i (callback via `2008:019e`): `26c4:00de`
`DS:5AE6[i] = n` (0 if file absent), `26c4:0112` `DS:5AD4[i] = filelength − (n+1)*2`.
`last = ` highest i in 8..1 with `n_i != 0` (0 if none) (`26c4:014b`). `total = stride ? n_0 +
last*stride : Σ n_i` (`DS:5AD2`); `DS:5AD0 = Σ size_i`. Far-alloc and zero `(total+1)*2 + DS:5AD0`
bytes; `buf[0] = total` (`26c4:0258`); offset cursor `DS:5AC8 = buf+2`, text cursor
`DS:5AC4 = buf + (total+1)*2`, text base `DS:5ACC = 0`. Per file (`26c4:01c5`): if present, read
`n_i` offsets to the offset cursor, add `DS:5ACC` to each (`26c4:0190`), read `size_i` text bytes to
the text cursor, advance text cursor and `DS:5ACC` by `size_i`. Then the offset cursor advances by
`n_i` entries if the file is present and (`i == 0` or `stride == 0`), otherwise by `stride` entries
(also for an absent file). ⇒ file 0 occupies ids `0..n_0−1`, file k ≥ 1 starts at `n_0 + (k−1)*stride`.
Unfilled slots keep offset 0 (= first string of file 0). Quirk: a file k ≥ 1 with more than `stride`
strings overwrites the next file's slots. Files present = file 0 (`<name>0` or `<name>`) plus
`<name>k` for every add-on bit set in `DS:43B4` (extens.c `2008:00a8`).

| Addr | Name | Behaviour |
|---|---|---|
| `26c4:0039` | `text_get(t, i)` | `fatal(20h)` unless `0 <= i < t[0]`; return `t + (t[0]+1)*2 + t[1+i]`. |
| `26c4:002c` | `text_count(t)` | `t[0]`. |
| `26c4:001a` | `text_free(t)` | far free. |
| `26c4:02b3` | `sum_words(a, n)` | Σ a[0..n-1]. |
| `26c4:0005` | `text_read_whole(?, name)` | `emd_open(name)`; `emd_close_rest_far()` (whole file as far block). Unused. |
| `26c4:00a5` | `extdb_text(db, id)` | `r = 2008:12eb(db, id)`; return `2008:138b(db, id, r->u32 @+0)` = far ptr into the extens text block (used for ACETXT, ORDTXT etc.). |

Users: `2a85:0231` → `text_load("stattxt","dat",100)` (station names: STATTXT0 = 123 names, ids
0..122; STATTXT1 = 32 names, ids 123..154 — matches the 1946 squadrons' station ids 128..153 in
SQUAD1, verified); `1f7f:0001` → `text_load("medabbr","dat",15)` (MEDABBR0: 20 medal names).

---

## 2. World database: `TARGET.n`, `CARRIER.n`, `SHIPPATH.n` (`2322`, wdata.c; `2455` tag list)

### 2.1 File format (all 32 shipped files parse exactly; verified by code and data)

Chunk file (platform chunk API `16e3`): chunks `INF:`, `DAT:`, `TAG:`. `n` = area number
(`1193:0115("TARGET"/"CARRIER"/"SHIPPATH", -1, itoa(area))` in 3164 → `TARGET.<area>`).

```
INF:  u16 P                               points per position entry (1 in every file)       -> DS:1CD8
DAT:  u16 nrec
      nrec x {
        u16 id                               record id (TAG id); records kept in FILE ORDER
        5 lists L = 0..4, each: u16 m; m x { u16 date; payload(L) }
           L0 payload: P x (s32 x, s32 y, s32 z)    position valid from date (ship tracks: waypoints)
           L1 payload: u16 a, u16 b                 (empty in all files)
           L2 payload: u16 kind                     target kind; 99 = "no kind at this date"
           L3 payload: u16 side                     owning side group (0 Japan, 1 US, …); 99 = any
           L4 payload: u16 service_code             who may use it: 99 any; 0..19 one service; 20..35 set
      }
TAG:  u16 n; n x { u16 id; char name[] (NUL-terminated) }
```

Integers little endian; s32 read by `249b:002d`. Lists are stored sorted by date in the files; the
loader re-sorts anyway (stable). Shipped value ranges (all files): TARGET L2 ∈ {0,1,2,3,4,5,6,8,10,11,99},
L3 ∈ {0,1,3,10,11,99}, L4 ∈ {0,1,2,3,4,11,20,21,22,23,34,35,99}; CARRIER L2 ∈ {1,2,3,4,18,19,20,22},
L3 ∈ {0,1}, L4 ∈ {0,1,3,20}; SHIPPATH L2 ∈ {0,1,2,4}, L3 ∈ {0,1,2}, L4 empty except one entry in
SHIPPATH.11. Side values 10/11 match no side group (0..5) ⇒ "nobody's". CARRIER records have 2–26
dated positions (a track); SHIPPATH records 1–? (paths).

### 2.2 In-memory structures — verified

| Global | Type | Meaning |
|---|---|---|
| `DS:1CD8` | u16 | `P` (INF:) |
| `DS:5418` | far ptr | head of the record list |
| `DS:1CDA` | far ptr | "current record" (also the cursor of every query) |
| `DS:1CDE` | far ptr | "current entry" |
| `DS:5416` | u16 | current list index 0..4 |
| far `4c8c:000C` | tagnode (37 bytes, zero) | sentinel head of the TAG name list (`4c8c` = wdata.c's far data segment) |
| `DS:5414` | near ptr | name array (`2322:06aa`, unused) |
| `DS:5412` | near ptr | date-string array (`2322:07a2`, unused) |

Record node (far, 1Ah bytes, `2322:030b`): `+00 next`, `+04 u16 id`, `+06 + 4*L` far head of list L
(L = 0..4; +06, +0A, +0E, +12, +16).
Entry node (far, 0Ah bytes, `2322:0147`): `+00 next`, `+04 u16 date`, `+06` payload:
L0 → far ptr to `P*12` bytes of points; L1 → `+06 u16 a, +08 u16 b`; L2..L4 → `+06 u16 value`.
Tag node (far, 25h bytes, `2455:000a`): `+00 next`, `+04 u16 id`, `+06 char name[31]` (strcpy, no bound).

**Valid-at-date rule** (used by every query, verified): entry `e` is valid at `d` iff
`e.date <= d && (e.next == NULL || d < e.next.date)` (unsigned). Only the last of several entries with
the same date can be valid.

**Record lookup** (0888/09d8/0bd5/0cfc, verified): `DS:1CDA = head`; if `by_id == 0`: advance
`index` times (stop at NULL); else advance until `rec.id == id`. NULL → `fatal`.

### 2.3 Loader

**`2322:04b1 wd_load_database(char *name)`** — verified.
1. `wd_close()` (2322:0467).
2. `f = 16e3:55f8(name)` (open resource file); NULL → `fatal(13Ch, name)`.
3. `16e3:568e(f, "INF:", 0)` (seek chunk; returns long, −1 = absent) → absent: `227c:00f8("wd_load_database")` (fatal).
   `DS:1CD8 = rd_u16(f)`.
4. If chunk `DAT:` found: `nrec = rd_u16`; per record: `wd_new_record(rd_u16)`; for `L = 0..4`:
   `wd_select_list(L)`; `m = rd_u16`; per entry: `wd_new_entry(rd_u16 date)`, then
   L0: for `i < P`: `x,y,z = rd_s32 ×3` → `wd_set_point(i, &xyz)`; L1: `a,b = rd_u16 ×2` → `wd_set_pair`;
   L2..4: `wd_set_value(rd_u16)`.
   Then `tag_load_chunk(f, "TAG:", &tag_sentinel)`, `16e3:59a5(f)` (close), and
   `DS:1CDA = DS:1CDE = NULL`.
   Quirk: if `DAT:` is absent the file is **not closed** and the TAG chunk is not read.

Builders (all verified):

| Addr | Name | Behaviour |
|---|---|---|
| `2322:030b` | `wd_new_record(id)` | far-alloc 1Ah; next = NULL; id; 5 list heads NULL; `flist_append` to `DS:5418`; current record = it; current entry = NULL; `DS:5416 = 0`. |
| `2322:02bd` | `wd_select_list(L)` | `fatal(96h)` if no current record or `L ∉ 0..5` (5 would address past the record: never used); `DS:5416 = L`; current entry = NULL; returns 1. |
| `2322:0147` | `wd_new_entry(date)` | `fatal(68h)` if no record. far-alloc 10; next NULL; `+04 = date`; if list 0: `+06 = ` far-alloc `P*12`. `flist_insert_sorted` into the current list; current entry = it. |
| `2322:000b` | `wd_set_point(i, src)` | asserts list 0 and record/entry (`fatal(3Dh)`), `0 <= i < P` (`fatal(3Eh)`); copy 12 bytes to `points + i*12`. |
| `2322:00a6` | `wd_set_pair(u16 v[2])` | asserts list 1 (`fatal(4Bh)`); `+06 = v[0]`, `+08 = v[1]`. |
| `2322:00fc` | `wd_set_value(v)` | asserts list > 1 (`fatal(58h)`); `+06 = v`. |
| `2322:0212` | `wd_delete_entry()` | `fatal(81h)` if no record/entry; unlink from the current list; free the point array if list 0; free the entry; current entry = NULL. |
| `2322:0399` | `wd_delete_record()` | `fatal(BCh)` if no record; unlink from `DS:5418`; for each list delete all entries; `tag_remove(id)`; free; current record/entry = NULL. |
| `2322:0467` | `wd_close()` | delete records until the list is empty; `tag_free_all(sentinel)`; `DS:1CDA = DS:1CDE = NULL`; `DS:1CD8 = 0`. Called by the mission builder after each use. |

### 2.4 Queries used by the mission builder

| Addr | Name / signature | Behaviour (verified) |
|---|---|---|
| `2322:0678` | `int wd_count()` | number of records (walks `DS:5418`). |
| `2322:0e52` | `int wd_record_id(int index)` | walk `index` records; NULL → `fatal(392h)`; return `+04 id`. (`DS:1CDA` left on it.) |
| `2322:0888` | `long *wd_position(int rec, u16 date, long *out /* near (DS) */, char by_id)` | `out[0..2] = −1` (all six words FFFFh). Look up the record (fatal if missing). Walk list 0; at the **first valid** entry copy `points[0]` (12 bytes: x, y, z) to `out`. None valid → `out` stays −1. Returns `out`. (`DS:1CDE` = the entry or NULL.) |
| `2322:09d8` | `long *wd_position_mid(rec, date, long *out /* near (DS) */, by_id)` | Same, but if the valid entry has a successor: `out = 3d50:16b0(&cur.points[0], &next.points[0])` = per-component `floor((a+b)/2)` (s32 add, `sar/rcr`), copied (12 bytes). Last entry → its own point. Used for ships (3164:0fb2). |
| `2322:0bd5` | `char wd_side_matches(int rec, u16 date, char side, char by_id)` | Walk list 3; for each valid entry: if `value == (int)side` (sign-extended) or `value == 99` → return 1. Returns 0 if none. |
| `2322:0cfc` | `int wd_kind(int rec, u16 date, char zero_if_99, char by_id)` | Walk list 2; valid entry: if `zero_if_99 && value == 99` → return 0; if `value != 99` → return value; else keep walking (no later entry can be valid) → return −1. No valid entry → −1. |
| `2322:0ebf` | `char wd_service_allowed(int code, char service)` | `code == 99` → 1; `code < 20` → `(int)service == code`; else `DS:1CCE[service*16 + code] != 0` (service sign-extended ×16). |
| `2322:0efd` | `int wd_find_for_service(u16 date, char service, int skip)` | `k = 0`; for each record in order: find the **first** valid entry of list 4 (if none, next record). If found: if `wd_service_allowed(value, service)` and `k++ >= skip` → return `rec.id`; otherwise continue with the next record (note `k` is incremented only for allowed records). End → `−1` (FFFFh). ⇒ id of the `skip`-th (0-based) record usable by `service` at `date`. |
| `2322:0e2f` | `int wd_id_by_name(char far *name)` | `tag_id(name, sentinel)` (case-insensitive; 0 if unknown). No callers. |
| `2322:0fe0` | `char far *wd_name_by_id(int id)` | `tag_name(id, sentinel)` or NULL. No callers. |
| `2322:0874` / `087e` | `wd_points_per_pos()` / `wd_current_list()` | return `DS:1CD8` / `DS:5416`. No callers. |
| `2322:0760` | `int wd_list_length()` | entries in the current record's current list. |
| `2322:06aa` | `wd_name_array()` | free old `DS:5414`; `malloc((n+1)*4)`; fill far name pointers (`tag_name(rec.id)`) in record order, NULL-terminate; return it. No callers. |
| `2322:07a2` | `wd_date_strings()` | free old `DS:5412`; `malloc(n*12+2)`: `n+1` near pointers then n 10-byte buffers, each `284f:021c(date, buf)` ("%s %d, %d"); NULL-terminated. No callers. |
| `2322:0ffa` | `int wd_find_near(pos*, u16 date)` | No callers; buggy: passes only the offset of the far point array to the near box test `3d50:1702(a, b, 7000L)` (`|dx| ≤ 7000 && |dz|…`), then returns list-3 value valid at date of the first record inside the box (flag never reset). Do not port. |

**Service-set table `DS:1CCE`** (bytes at `DS:1CE2 + s*16 + (code−20)`, s = service 0..10, code 20..35;
the table ends exactly at the `"INF:"` string `DS:1D92`). Decoded as "code → services allowed" (verified dump):

| code | services | code | services | code | services | code | services |
|---|---|---|---|---|---|---|---|
| 20 | 0,1 | 24 | 2,5 | 28 | 0,7 | 32 | 2,8 |
| 21 | 0,2 | 25 | 5,7 | 29 | 1,7 | 33 | 8,9 |
| 22 | 1,2 | 26 | 5,8 | 30 | 2,7 | 34 | 2,10 |
| 23 | 3,4 | 27 | 5,10 | 31 | 7,10 | 35 | 0,1,2 |

(Service codes: 0 USN, 1 USMC, 2 USAAF, 3 IJN, 4 JAF, 5 RAF, 6 FAA, 7 CAF, 8 RedAF, 9 RNAF — STRINGS_ table 5/6; 10 = ?.)

### 2.5 Tag (name) list (`2455`) — verified

List of 25h-byte nodes; the head passed is the static sentinel `4c8c:000C` (id 0, empty name), which
takes part in searches.

| Addr | Name | Behaviour |
|---|---|---|
| `2455:0292` | `tag_find(id, name, list)` | walk from `list` itself: return node if `id != 0 && node.id == id`, or `name != NULL && _fstricmp(node.name, name) == 0` (`0000:4858`, ASCII case-insensitive); NULL at end. |
| `2455:000a` | `tag_add(id, name, list)` | `n = tag_find(0, name, list)`. If `n == NULL || id == 0`: if `n`: `id = n.id`; if `id == 0 && (n == NULL || n.id != 0)`: `id = 1 + max(1−1, all node ids)` (i.e. `id = max(1, max_id+1)`); if `n == NULL`: far-alloc 25h, `{next NULL, id, strcpy name}`, append at tail, return id. Then (found) `n.id = id`, return id. |
| `2455:0117` | `tag_remove(id, list)` | find node with `.id == id` (not the sentinel), unlink, free, return 1; else 0. |
| `2455:01a0` | `tag_free_all(list)` | free every node after the sentinel; `list.next = NULL`. |
| `2455:020e` | `tag_name(id, list)` | first node with `.id == id` → `&node.name` (far), else NULL. (id 0 matches the sentinel.) |
| `2455:024a` | `tag_id(name, list)` | first node with `_fstricmp(name) == 0` → id, else 0. |
| `2455:02f7` | `tag_load_chunk(file, tag, list)` | needs `file`, `tag`, `list` non-NULL. If `16e3:59d4(file)` says it is not an open handle, open it as a name (`16e3:55f8`). Seek chunk `tag` with `16e3:568e(f, tag, 0)`, retry with flag FFFFh (guess: rescan from start). `n = rd_u16`; n × `{id = rd_u16; s = rd_cstring; if s: tag_add(id, s, list)}`. Close only if it opened. Returns n (0 on failure). |
| `2455:03c3` | `tag_write(first, f)` | `wr_u16(#nodes with id != 0)`, then per such node `wr_u16(id)`, `wr_cstring(name)` (via a 32-byte local copy). No callers. |

---

## 3. String tables (`24e3`, sys\strp.c) — verified

### 3.1 Multi-table string file (`strings_load`)

Files: `STRINGS_.DAT` / `STRINGS.DAT`, `SFTBTNS0/1.DAT`, `BRIEF.DAT`, `DEBRIEF.DAT`, `FLTPLAN.DAT`,
`DISPLAYS.DAT`, `CALBRATE.DAT`, `MISC.DAT`, `OPTIONAL.DAT`, `FMAPSTR.DAT` … (13 shipped files parse
exactly; name built by callers with `1193:0115`). **Settles the "records + strings" `.DAT` files of
scripts.md §2**:

```
u16 ntab
ntab x { u16 n; u16 off[n] }          offsets into text
u16 textsize
char text[textsize]                   NUL-terminated strings
```

`24e3:0268 strings_load(name)`: `fatal(BAh)` if `DS:1DC1` (already loaded); `fopen(name,"rb")`
(`fatal(BEh)`); `DS:5786 = ntab`; `DS:5788 = malloc(ntab*2)` (near array of near pointers); per table
`malloc(n*2)` and read n offsets (`fatal(C3h/C9h)` on alloc failure); `textsize` → far-alloc
`textsize+1` at `DS:578A` (seg `DS:578C`); then `while (!feof) *p++ = getc` (stores the final EOF as
FFh in the extra byte); `fclose`; `DS:1DC1 = 1`.
`24e3:0436 strings_free()`: `fatal(E8h)` unless loaded; free every table array, the table array and
the text; `DS:1DC1 = 0`.
`24e3:04b4 strings_get(t, i)` → far `DS:578A + off_t[i]`; `fatal(FFh)` unless loaded; **no bounds check**.

`STRINGS_.DAT` tables (M1SHL; SHELL1 `STRINGS.DAT` has 37/5/4/19/…): 0 briefing sentence templates
(53; `%a`…`%t` fields), 1 status (Active, Retired, Discharged, Deceased), 2 pilot type, 3 rank
abbreviations (43), 4 aircraft role, 5 service names, 6 service abbreviations, 7 skill words
(POOR…BEST). Also: acelist row names use table 0 at index `code` and `code + 0ADh` (§5.4).

| Addr | Name | Behaviour |
|---|---|---|
| `24e3:05b9` | `strings_dup_far(char far **dst, n, t)` | `fatal(13Ch)` unless loaded; for i < n: far-alloc `len+1`, copy `strings_get(t,i)`. |
| `24e3:064a` | `strings_free_far(dst, n)` | far free each. |
| `24e3:050c` / `0591` | near-heap variants | unused. |
| `24e3:0678` | `strings_dup_ranks()` | for i = 0..41: `DS:57A2[i]` (far ptrs) = far copy of `strings_get(3, i)`. **Quirk:** reads 42 entries of table 3; SHELL1 `STRINGS.DAT` has only 19 (M1SHL `STRINGS_` 43) — harmless only with the add-on data. |

### 3.2 Single string table (`.SCD` screen labels)

**Settles scripts.md §2 variant A**: all 34 `.SCD` files are

```
u16 n; u16 off[n] (off[0] = 0); u16 textsize; char text[textsize]
```

(the "u32 n" reading in scripts.md is this with `off[0] = 0` as the high word.)
Buffer `DS:5792` (far) holds `u16 n; u16 off[n]; text` (textsize is not stored): `24e3:0002` reads
`n`, the offsets, `textsize` (to a local), then the text at `buf + (n+1)*2` (`fread_far` 1193:0a46).

| Addr | Name | Behaviour |
|---|---|---|
| `24e3:0087` | `scd_load(name, bufsize)` | `fatal(60h)` if `bufsize == 0`. Buffer (re)allocation: if `DS:1DBF == 0` and a buffer exists, or `bufsize > DS:1DBF`: free old, far-alloc `bufsize`, `DS:1DBF = bufsize`; else reuse. `fatal(70h)` if no buffer; `fopen(name,"rb")` (`fatal(73h)`), read, close. Caller `2e8a:038e` (`<screen>.scd`). |
| `24e3:0177` | `scd_load_new(name, size)` | always far-alloc a new buffer (no free, `DS:1DBF` untouched) then read. No callers. |
| `24e3:0164` | `scd_push()` | `DS:578E/5790 = DS:5792/5794`. |
| `24e3:01fd` | `scd_pop()` | free the current buffer; restore the saved one. (3038:009a/00b6: nested screen.) |
| `24e3:021f` | `scd_string(i)` → near | `strpool_copy(buf + (n+1)*2 + off[i])`. No bounds check. |

---

## 4. Extens databases (`2008`, sys\extens.c — other owner; summary needed for ACE/SQUAD ids)

`2008:0aec(name, ext, recsize, stride, …, list far *, read_cb, free_cb)` returns a handle 1..20
(slot `DS:10A8 + h*7Dh`). It opens `<name>0.<ext>` (fallback `<name>.<ext>`) and `<name>1..8.<ext>`.
Each file: `u32 textsize; u16 n; n records (list_read with read_cb); char text[textsize]`.
Global ids: file 0 → `0 .. n0−1`; with `stride != 0` file k ≥ 1 starts at `end[k−1]` where
`end[0] = n0`, `end[k] = end[k−1] + stride`. `2008:0ca2(h)` = id range (for ACE: `n0 + stride` =
29 + 15 = **44**; ids 41..43 have no record). `2008:12eb(h, id)` → far record ptr or NULL (loads the
right file on demand, records land in the passed list struct); `2008:138b(h, id, long off)` → far ptr
`text + off`. Record text strings are "name\0second\0".

---

## 5. Aces (`2550`, emd\ace.c)

### 5.1 Files — verified by code and data

**`ACETAB.DAT`** (read raw by `2550:0679`, emd stream):
```
u16 n1; n1 x 4 bytes       -> list DS:5A8D (elsize 4)  never read by any code (6 rows: 28 28 14 00,
                              23 2D 14 00, 19 28 23 00, 14 1E 32 00, 0A 14 46 00, 00 0A 5A 00)
u16 n2; n2 x 6 bytes       -> list DS:5A83 (elsize 6)  "postings": +00 u16 station, +02 u8 ?, +03 u16
                              aircraft type, +05 u8 ?     (26 rows)
(no remainder: emd_close asserts EOF)
```
**`ACE0.DAT`, `ACE1.DAT`** (extens "ace","dat", recsize 15h, stride 15 → handle `DS:5AA1`, record
list `DS:5A97`). On-disk record (read by `2550:058d`): `u16 name_off, u16 link, u16 kills, u8 service,
u16 duel_type, date(3), u16 m, m x {date(3), u8 type, s16 value}`. In memory (15h bytes):

| Off | Type | Meaning | Accessor |
|---|---|---|---|
| +00 | u16 | text offset: `"Full Name\0Short name\0"` | `2550:0043` / `00a3` |
| +02 | s16 | id of the same pilot's earlier record (ACE1 → ACE0 index), FFFFh none | `2550:00d0` |
| +04 | u16 | victories (Iwamoto 100, Nishizawa 87, Bong 40 …) | `2550:0164` |
| +06 | u8 | service code (0 USN, 1 USMC, 2 USAAF, 3 IJN, 4 JAF) | `2550:01b2` |
| +07 | s16 | aircraft type the **player** flies in "Dogfight an Ace" (3570: → `DS:62DD`) | `2550:024e` |
| +09 | u16 date | date of the ace duel (3570: → `DS:6277`) | `2550:0200` |
| +0B | list (10) | career, dated 5-byte elements `{u16 date, u8 type, s16 value}` | §5.2 |

Career entry types (from data; value meaning from code): 0 = with squadron `value` (squad id);
1 = posted per ACETAB posting `value`; 2 = unavailable (−1); 3 = retired/survived (−1);
4 = killed (−1: Nishizawa 26 Oct 1944, Sasai 27 Aug 1942); 5 = captured (−1: Boyington 3 Jan 1944)
(**likely** — 2..5 only distinguished by other modules). ACE0 = 29 aces (ids 0..28), ACE1 = 12
(ids 29..40; 1946 add-on, many linking to ACE0 ids).

**`ACETXT0/1.DAT`** (extens "acetxt","dat", recsize 4, stride 15 → handle `DS:5A81`): records are
`u32 text offset`; text = `"biography\0duel briefing\0"` (= scripts.md variant B). SHELL1
`ACETEXT0.DAT` (old u16 format) is not used by this PS.EXE.

### 5.2 Functions — verified

All `fatal` if `2008:12eb` returns NULL (except where noted).

| Addr | Name | Behaviour |
|---|---|---|
| `2550:0679` | `ace_open()` | if `DS:1DCC == 0`: `emd_open(1193:0115("acetab",-1,"dat"))`; `list_read(DS:5A8D,4,NULL)`; `list_read(DS:5A83,6,NULL)`; `emd_close(0)`; `DS:5AA1 = 2008:0aec("ace","dat",15h,15,12h,6,&DS:5A97,2550:058d,2550:064b)` (`fatal(13Eh)` if 0); `DS:1DCC = 1`. Returns 1 (also when already open: it returns the flag value 1). |
| `2550:073f` | `ace_close()` | if loaded: `list_free` both ACETAB lists, `2008:0bbd(DS:5AA1)`, `DS:1DCC = 0`. |
| `2550:058d` | `ace_read_record(r)` | reads +00,+02,+04 (u16), +06 (u8), +07 (u16), `emd_read_date(+09)`, `list_read(+0B, 5, dated)`. |
| `2550:064b` | `ace_free_record(r)` | `list_free(+0B, NULL)`. |
| `2550:000e` | `ace_count()` | `2008:0ca2(DS:5AA1, 0)` (= 44). |
| `2550:0023` | `ace_valid(a)` | record exists. |
| `2550:0043` | `ace_name(a)` | `fatal(4Eh)` if none; `2008:138b(db, a, (long)(s16)r+00)`. |
| `2550:00a3` | `ace_short_name(a)` | `s = ace_name(a); return s + strlen(s) + 1`. |
| `2550:00d0` | `ace_link(a)` | `+02`. |
| `2550:011e` | `ace_has_successor(a)` | for `i < (char)ace_count()`: `r = 2008:12eb(i)`; if `r+02 == a` → 1. **No NULL check** (ids 41..43 read `0000:0002`, the INT 0 vector — never equals a real id in practice). Returns 0. |
| `2550:0164` / `01b2` / `0200` / `024e` | kills / service / duel date / duel player type | fields +04 / +06 / +09 / +07. |
| `2550:0338` | `ace_status(a, date)` | `e = list_find_dated(+0B, date)`; `e ? e.type : 0FFh`. |
| `2550:03aa` | `ace_squadron(a, date)` | `e` as above; `(e && e.type == 0) ? e.value : FFFFh`. |
| `2550:0426` | `ace_posting_station(a, date)` | `e` must exist with type 1 (`fatal(EFh)`); `list_at(DS:5A83, e.value)->+00`. |
| `2550:04d9` | `ace_posting_aircraft(a, date)` | same; `->+03`. |
| `2550:029c` | `ace_first_posting_date(a, d0, d1)` | walks career elements from the first **without an end bound** until one with `d0 <= date <= d1` and type 0 or 1; returns its date (0 only if the pointer wraps to NULL). No callers — do not port. |
| `2550:0780` | `acetxt_open()` | `fatal(168h)` if `DS:5A81` already set; `DS:5A81 = 2008:0aec("acetxt","dat",4,15,12h,5,0,0,0,0)`; `fatal(172h)` if 0; return 1. |
| `2550:0802` | `acetxt_close()` | `2008:0bbd(DS:5A81)`; `DS:5A81 = 0`. |
| `2550:0817` | `acetxt_bio(a)` | `fatal(17Dh)` if not open; `extdb_text(DS:5A81, a)`. |
| `2550:0855` | `acetxt_duel_text(a)` | the string after the biography. |

### 5.3 Ace selection list (Dogfight-an-Ace screens) — verified

Globals: `DS:584A u16[2]` entries per slot; `DS:584E u16[2][70]` enabled flags; `DS:5966 u16[2][70]`
ids; `DS:5A7E` u8 current slot; `DS:5A7F` u8 "slot has 4 pilot rows"; `DS:5A80` u8 ace count.
Row codes: 0..3 = pilot rows, `ace_id + 4` = ace rows.

**`2550:08f8 acelist_build(char service, char slot, char pilot_rows, char same_service)`**
1. `side = 0f67:02ed(service)` (service → side group).
2. `memset(ids[slot], 0, 8Ch)`; `memset(enabled[slot], 1, 8Ch)` (every flag = 0101h ≠ 0); local `tmp[70] = 0`.
3. `pilot_rows`: `count[slot] = 4`, `ids[slot][0..3] = 0..3`; else `count[slot] = 0`.
4. `DS:5A7F = pilot_rows`; `DS:5A80 = ace_count()`; `n = 0`.
5. For `i = 0 .. DS:5A80−1`: skip unless `ace_valid(i)` and `0f67:02ed(ace_service(i)) == side`.
   If `same_service` and `ace_service(i) != service` → skip. `link = ace_link(i)`.
   `link == −1` → `tmp[n++] = i`. Else: search `tmp[0..n−1]` for `link`; if found replace it by `i`
   (the 1946 record supersedes the earlier one, keeping its slot); if not found `tmp[n++] = i`.
6. `count[slot] += n`; **`qsort(tmp, n, 2, ace_cmp_kills)`** (Borland RTL `0000:3c66`); copy `tmp[k]`
   to `ids[slot][k]` (no pilot rows) or `ids[slot][4+k]`.

`2550:08b1 ace_cmp_kills(int *a, int *b)`: `kills(*a) < kills(*b)` → 1; equal → 0; else −1 (descending).
**Port:** ties exist (e.g. US 19/19, 28/28/28) — the order among equal kills depends on Borland's
qsort algorithm; reproduce it exactly (RTL hand-off).

| Addr | Name | Behaviour |
|---|---|---|
| `2550:0b9d` | `acelist_select(slot)` | `DS:5A7E = slot`. |
| `2550:0ba8` | `acelist_id(i)` | `ids[cur][i]`. |
| `2550:0b00` | `acelist_disable(code, slot)` | for `i = 4 .. count[slot]−1`: first `i` with `ids[slot][i] + 4 == code` → `enabled[slot][i] = 0`. (Starts at 4 even without pilot rows.) |
| `2550:0b53` | `acelist_enabled_count()` | number of `i < count[cur]` with `enabled != 0`. |
| `2550:0bc5` | `acelist_code(row)` | `row < 4` → `row`. Else `j = k = 0`; `while (j < count && (k < row || enabled[j] == 0)) { if (enabled[j]) k++; j++; }`; return `ids[cur][j] + 4` (j may equal count: reads the next array slot). |
| `2550:0c3b` | `acelist_name(i)` | `(!DS:5A7F || i > 3) ? ace_name(ids[cur][i]) : strings_get(0, ids[cur][i])` → `strpool_copy`. No callers. |
| `2550:0c99` | `acelist_row_name(row)` | skip leading disabled entries, then find the row-th enabled one as in 0bc5; name as 0c3b but pilot rows use `strings_get(0, ids[j] + 0ADh)`. No callers. |

---

## 6. Squadrons (`2624`, emd\squad.c)

### 6.1 Files — verified

**`SQUADTAB.DAT`** (raw, `2624:0902`):
```
u16 n1; n1 x 4 bytes    -> list DS:5AAE, never read (5 rows, same as ACETAB's first 5)
u16 n2; n2 x 7 bytes    -> list DS:5AA4: mission-type weight rows (7 percentages, sum 100) (18 rows)
```
The trailing `26fc:0338` result (rest of file) is discarded (nothing remains in the shipped file).

**`SQUAD0.DAT` / `SQUAD1.DAT`** (extens "squad","dat", recsize 2Dh, stride 20 → handle `DS:5AC2`,
list `DS:5AB8`; SQUAD0 = 88 squadrons ids 0..87, SQUAD1 = 16 ids 88..103; `squad_count` = 108).
Record (`2624:07a5`): `+00 u16 name_off, +02 u8, +03 u8, +04 u8`, then four dated lists:

| Off | Type | Meaning |
|---|---|---|
| +00 | u16 | text offset `"Name\0\0"` (second string empty) |
| +02 | u8 | service code |
| +03 | u8 | 0/1/2 — squadron role (fighter / torpedo / dive bomber, **likely**, STRINGS_ table 2/4) |
| +04 | u8 | pilot quality class 0..4 |
| +05 | list, elsize 3 | status `{date, u8 s}`: 0 = active, 1 = stood down, 2 = disbanded (**likely**); `squad_status` |
| +0F | list, elsize 4 | aircraft `{date, u16 type}` |
| +19 | list, elsize 4 | station `{date, u16 station}` (STATTXT id) |
| +23 | list, elsize 7 | mission schedule `{date, u8 count, u16 param, s16 time}`: `time == −1` → `count` generated missions in the period, `param` = SQUADTAB weight row; else a historical mission: `param` = `MISS<param>.DAT` number, `time` = hhmm (e.g. 1630) |

### 6.2 Open/close and accessors — verified

| Addr | Name | Behaviour |
|---|---|---|
| `2624:0902` | `squad_open()` | if `DS:1DEC == 0`: `emd_open("squadtab.dat" via 1193:0115(...,-1,...))`; `list_read(DS:5AAE,4,NULL)`; `list_read(DS:5AA4,7,NULL)`; `emd_close_rest_far()` (result dropped); `DS:5AC2 = 2008:0aec("squad","dat",2Dh,20,12h,6,&DS:5AB8,2624:07a5,2624:088c)` (`fatal(20Ch)`); `DS:1DEC = 1`; returns 1 (also when already open). |
| `2624:09c4` | `squad_close()` | free both SQUADTAB lists, `2008:0bbd(DS:5AC2)`, `DS:1DEC = 0`. |
| `2624:07a5` / `088c` | read / free record | u16, u8, u8, u8, then `list_read(+05,3,dated)`, `(+0F,4,dated)`, `(+19,4,dated)`, `(+23,7,dated)`; free the 4 lists. |
| `2624:000d` / `002d` | `squad_valid` / `squad_count` | as ace. |
| `2624:0042` / `007b` | name / second string | as ace (no NULL check). |
| `2624:00a8` / `00cf` / `00f6` | +02 / +03 / +04 | no NULL check. |
| `2624:011d` | `squad_status(sq, date)` | `e = list_find_dated(+05, date)`; `e ? e.s : 0FFh`. |
| `2624:0219` | `squad_aircraft(sq, date)` | `list_find_dated(+0F, date)->+02` — **no NULL check** (date before the first entry reads `0000:0002`). |
| `2624:0256` | `squad_station(sq, date)` | same on `+19`. |

### 6.3 `2624:0293 squad_find_mission(list far *l, u16 date, int after_time)` — verified

```
if (l.data == NULL || date < el[0].date) return NULL;
cur = el[0]; nxt = el[1]; last = (s8)(l.count - 1);  i = 0; res = last;
if (0 < last) loop {
    if (nxt.date > date) { res = i; break; }
    if (nxt.date == date && cur.date == date && nxt.time != -1 &&
        (after_time == -1 || after_time < nxt.time /*signed*/)) { res = i; break; }
    cur = nxt; nxt++; i++;
    if (i >= last) { res = last; break; }
}
l.cursor = res;  return cur;
```
= the schedule entry in force at `date`; among several entries with the same date it stops at the
first whose **successor** is a later-timed historical mission (so `cur` = the last entry not after
`after_time`). Count is truncated to a signed byte (lists > 128 entries misbehave; none do).

### 6.4 Career schedule state (`sched`, near struct, caller-owned)

`+00 u16 date` (period start / current), `+02 s16 time` (last historical time or −1), `+04 u16 next`
(next mission date), `+06 u16 step` (days between missions), `+08 s8 left` (missions left).

**`2624:043a squad_sched_init(sq, sched *s, u16 date)`** — verified
```
s.date = s.next = date;
if (squad_status(sq, s.date) != 0) return;
cur = squad_find_mission(+23, s.date, s.time);  if (!cur) return;      // s.time: caller's value
s.left = cur.count;
nxt = list_next(+23);
if (nxt) { e = list_find_dated(+05, date); while (e && e.date <= date) e = list_next(+05); }
else       e = list_last(+05);
end = (nxt && nxt.date <= e.date) ? nxt.date : e.date;     // e NULL would read 0000:0000
if (cur.date != end) {
    if (cur.date < date)
        s.left = (s8)( (long)(u16)(end - date) * (long)(s8)cur.count / (long)(u16)(end - cur.date) );  // LXMUL, LDIV signed
    s.step = s.left ? (u16)(end - date) / (u16)(int)s.left : 0;
}
if (s.left) s.left--;
```

**`2624:05a6 char squad_sched_next(sq, sched *s)`** — verified. Returns 1 if a mission was scheduled.
```
if (squad_status(sq, s.date) != 0) return 0;
cur = squad_find_mission(+23, s.date, s.time);  if (!cur) return 0;
d = s.date;
while (s.left <= 0) {                               // signed
    cur = list_next(+23);  if (!cur) break;
    d = cur.date;  s.time = cur.time;  s.left = cur.count;
}
if (!cur || s.left <= 0 || squad_status(sq, d) != 0) {
    s.left = 0;  s.date = d;
    e = list_find_dated(+05, d); while (e && e.date <= d) e = list_next(+05);
    if (!e) e = list_last(+05);
    s.next = e.date;                                // date the squadron's status next changes
    return 0;
}
if (s.next >= d) s.next += s.step;
else {
    s.next = d;
    nxt = list_next(+23);
    if (nxt) { e = list_find_dated(+05, d); while (e && e.date <= d) e = list_next(+05); }   // e may end NULL
    else e = list_last(+05);
    if (nxt == NULL || (e.date >= d && e.date < nxt.date))
         s.step = s.left ? (u16)(e.date - d)   / (u16)(int)s.left : 0;
    else s.step = s.left ? (u16)(nxt.date - d) / (u16)(int)s.left : 0;
}
s.date = d;  s.left--;  return 1;
```

**`2624:0163 u16 squad_next_mission_date(sq, u16 d0, u16 d1)`** — verified
```
if (squad_status(sq, d0) == 0 && (e = list_find_dated(+23, d0)) && (s8)e.count >= 2) return d0;
for (e = list_first(+23); e && (e.date < d0 || e.date > d1); e = list_next(+23)) ;
return e ? e.date : 0;
```

### 6.5 Career mission type choice — **RNG**

**`2624:035d u8 squad_pick_mission_type(sq, u16 date, int after_time)`** — verified
```
cur = squad_find_mission(+23, date, after_time);          // no NULL check
if (cur.time != -1) return 0FFh;                          // historical mission: no choice
row = DS:5AA4.data + cur.param*7;                         // SQUADTAB weight row (7 signed bytes)
int w[7] = { (s8)row[0..6] };
k = rng_pick_weighted(w, 7);                              // 24b7:0180  ← the only RNG call here
return far byte 4c9a:000C[k];                             // {2,3,4,6,7,8,9}
```
Table `4c9a:000C` (squad.c far data) = mission types `MT_CAP 2, MT_FSWP 3, MT_SCRM 4, MT_ESCT 6,
MT_INTR 7, MT_ANTI 8, MT_GRND 9`. Caller `3164:0944`.

**`2624:03fb int squad_mission_param(sq, date, after_time)`** = `squad_find_mission(...)->param`
(weights row for generated missions, `MISS<n>` number for historical ones). Callers `3164:0944`, `0c1d:03c6`.

SQUADTAB weight rows (shipped M1SHL, order MT 2,3,4,6,7,8,9): 0 `20 10 20 10 10 10 20`,
1 `100 0 0 0 0 0 0`, 2 `0 0 0 0 0 50 50`, 3 `50 0 30 0 20 0 0`, 4 `0 40 0 20 0 20 20`,
5 `0 10 0 40 0 20 30`, 6 `40 0 10 0 50 0 0`, 7 `10 0 50 0 40 0 0`, 8 `10 20 0 60 0 0 10`,
9 `0 40 10 20 10 10 10`, 10 `0 40 0 40 0 10 10`, 11 `0 0 0 0 0 70 30`, 12 `0 0 0 100 0 0 0`,
13 `0 20 10 10 10 30 20`, 14 `0 0 0 0 100 0 0`, 15 `0 10 0 0 0 20 70`, 16 `0 0 0 0 0 0 100`,
17 `0 0 0 0 0 100 0`.

---

## 7. Data-file summary

| File (volume) | Loader | Layout |
|---|---|---|
| `TARGET.n` (COMMON1/M1CMN), `CARRIER.n`, `SHIPPATH.n` (SHELL1/M1SHL) | `2322:04b1` | §2.1 |
| `STRINGS_/STRINGS`, `SFTBTNS*`, `BRIEF`, `DEBRIEF`, `FLTPLAN`, `DISPLAYS`, `CALBRATE`, `MISC`, `OPTIONAL`, `FMAPSTR` `.DAT` | `24e3:0268` | §3.1 |
| `*.SCD` | `24e3:0087` | §3.2 |
| `ACETAB.DAT`, `ACE0/1.DAT`, `ACETXT0/1.DAT` | `2550:0679/0780` | §5.1 |
| `SQUADTAB.DAT`, `SQUAD0/1.DAT` | `2624:0902` | §6.1 |
| `STATTXT0/1.DAT` (stride 100), `MEDABBR0.DAT` (stride 15) | `26c4:02d9` | §1.6 |

---

## Port notes

* Keep the linked-list world database or replace it with arrays: behaviour depends only on record
  **file order**, the stable date sort, and the valid-at-date rule; `DS:1CDA/1CDE` are left pointing
  at the last record/entry examined but no caller reads them after a query (**likely**).
* `/* PORT: */` NULL-dereference paths (squad aircraft/station before the first date, `ace_has_successor`
  on empty ids, `squad_sched_*` with an exhausted status list) read the real-mode IVT; treat as
  "no match"/0. They do not occur with the shipped data (**likely**).
* Borland `qsort` must be reproduced bit-exactly for the ace list order.

## Hand-offs

* **RTL / platform:** `0000:3c66` = Borland `qsort` (used by `2550:08f8` with ties); `0000:4858` =
  `_fstricmp` (ASCII); `16e3:55f8/568e/59a5/59d4` = open / find chunk (flag 0, FFFFh) / close / is-open
  of the resource chunk files.
* **extens.c (`2008`) owner:** id mapping with a stride (`+37h end[]`, `+25h n[]`, `+1Bh stride`),
  `2008:0ca2` returns the id range incl. empty slots (44 aces, 108 squadrons); files `<name>0..8`.
* **date.c (`284f`):** `284f:0007(u8 m0..11, d, y−1900)` → days since 1 Jan 1900; `284f:021c(date, buf)`
  "%s %d, %d".
* **3d50 (math):** `3d50:16b0` midpoint (used by `2322:09d8`), `3d50:1702(a, b, long d)` box test.
* **Mission builder (lead, 3164/3570):** `2550:024e` = player's aircraft in the ace duel, `2550:0200` =
  duel date; ace career type 1 → station `ACETAB[v].+0`, aircraft `+3`; `2624:035d` returns FFh for a
  historical schedule entry (then `2624:03fb` = MISS number, `time` = hhmm).
* **scripts.md:** `.SCD` = `u16 n, u16 off[n], u16 size, text`; multi-table `.DAT` layout §3.1 settles
  the "records + strings" files listed there. ACETEXT0.DAT (SHELL1) is unused by this PS.EXE.
* **world.md §5:** list 2 = kind (99 = none), list 3 = owning side group (99 = any), list 4 = service
  code / service set (table §2.4); SHIPPATH.n uses the same format; the loader is `2322:04b1`.

## Open questions

* ACETAB posting bytes `+02`, `+05`; ACETAB/SQUADTAB first tables (4-byte rows) are loaded but never
  read (vestigial skill weights?).
* Squad `+03` role and status values 1/2, ace career types 2..5: meanings inferred from data only.
* `16e3:568e` flag semantics (0 vs FFFFh) — platform owner.
