# shell_data part `emd2`: aircraft, medals, flights, dates, campaigns, mission info, field generation, convoys, ships, formations, stations, ordnance, 2-D helpers (PS.EXE)

Part of module `shell_data` (lead file `shell_data.md`). Target `Game/PS.EXE`, DGROUP `4D08`. Segments:
`2777` (`emd\aircraft.c`), `27f0` (`emd\medals.c`), `280a` (flight data, untagged), `284f` (`emd\date.c`),
`287b` (`emd\campaign.c`), `28e4` (`emd\missinfo.c`), `2968` (`emd\wldfgen.c`), `29ae` (`emd\convoy.c`),
`29c2` (`emd\ship.c`), `2a56` (`emd\form.c`), `2a85` (`emd\station.c`), `2ab3` (`emd\ordnance.c`), `2b1f`
(2-D geometry helpers, untagged), `2b42` (64-bit multiply, untagged). Symbols: `shell_data_emd2_symbols.csv`.

Everything below was read in the `tools/x86dis.py` disassembly (**verified**) unless marked **likely** /
**guess**; accessors were read in the decompile and spot-checked. File layouts were checked against every
shipped file in `work/dyn/M1SHL` (the 1.2 update volume; the old `SHELL1` names such as `AIRCRAFT.DAT`,
`FLIGHT.DAT`, `MISSINFO.DAT`, `ORDNANCE.DAT` are **not** opened by this PS.EXE — the loaders use the base names
`air`, `flight<n>`, `missinf`, `ordnce`, … and `table_load` tries `<base>0.<ext>` then `<base>.<ext>`).
`MEDALS.DAT` and `CARRFORM.DAT` exist only in SHELL1 and are opened by their exact names.

Conventions as in `shell_data_emd1.md`: `fatal(line)` = `227c:0143(0, <module seg>, line, 0)` (never returns
in practice); dates are u16 **days since 1 Jan 1900**, compared unsigned; `table_load/table_rec/table_text/
table_count/table_free` = extens.c `2008:0aec/12eb/138b/0ca2/0bbd` (sys part §4); list functions
`list_read/list_free/list_first/list_next/list_at/list_find_dated` = `273b:024e/0348/001c/0034/00b6/0121`
(emd1 §1.5); `emd_read/emd_read_far/emd_open/emd_close_rest_far` = `26fc:0098/01eb/004f/0338`;
`enddate_get(set, force)` = `1193:0006`; `module_active()` = `2008:000e` (active data set / extension number).
Service codes: 0 USN, 1 USMC, 2 USAAF, 3 IJN, 4 IJA (5..10 unused by the shipped data). Service bit masks in
the data files are `1 << (service+1)`.

**RNG call sites in these segments (all `rng_pick_weighted` `24b7:0180`)**: `28e4:0270` (2 weights),
`28e4:03a2` (4), `28e4:04da` (4), `28e4:0612` (11), `2968:015b` (3 or 2), `29c2:01a2/01f8/024e` (3 each),
`2ab3:03a7` (3, weights {50,30,20}). Nothing else here draws random numbers. Each call happens exactly once
per invocation of its function (no retry loops around the draw).

---

## 1. The "dated keyed list" lookup (common pattern) — verified

Many records hold a `list` (emd1 §1.5) of dated elements `{u16 date, …, u8 key}` sorted by date, with
entries for several keys interleaved. The lookup used by `280a:0110/021b`, `28e4:0270/03a2/04da/0612`,
`2968:015b/0313` and (with a found-flag) `29c2:02a4/03cc/04f4` is, with `KEY(e)` the key byte at a
function-specific offset and `END` a per-module "end date" global (`enddate_get(module_active(), 1)`):

```c
el *keyed_lookup(list *L, u8 key, u16 date, u16 END, int *found)
{   el *cur = list_first(L);                     /* element 0, whatever its key */
    el *nxt; int last;
    do nxt = list_next(L); while (!(KEY(nxt) == key) && nxt);   /* NB reads KEY(NULL) first */
    u16 end = nxt ? nxt->date : END;  last = (nxt == NULL);
    for (int i = 0; i < L->count; i++) {
        if (KEY(cur) == key && cur->date <= date && date <= end) { *found = 1; return cur; }
        if (last) break;
        cur = nxt;
        do nxt = list_next(L); while (!(KEY(nxt) == key) && nxt);
        end = nxt ? nxt->date : END;  last = (nxt == NULL);
    }
    *found = 0; return cur;                      /* fallback: last element examined */
}
```
Quirks to keep: the first candidate is element 0 even if its key differs (it is only accepted if its key
matches); the "valid until" date is the date of the next element **with the same key**, inclusive on both
ends (`<=`); when nothing matches, the function falls back to the last element examined (= the last one with
the key, or element 0), except the `29c2` variants which then report "not found". `KEY(NULL)` reads the
real-mode IVT (`0000:000x`); the loop still stops because the NULL test follows (port: test NULL first).

---

## 2. Aircraft (`2777`, aircraft.c)

### 2.1 `AIR<n>.DAT` — verified

`2777:0000 air_open()`: if `DS:1E1E == 0`: `DS:5ECA = table_load("air","dat", recsize 0x18, stride 15,
mode 0x12 (all files, far), flags 5 (records + text tail))`, 0 → `fatal(4Dh)`; `DS:5EC8 = table_count(5ECA,
NULL)`; `DS:1E1E = 1`. `2777:04df air_close()`: if loaded, `table_free`, `DS:1E1E = 0`. Ids: `AIR0` 39
aircraft (0..38), `AIR1` (1946 add-on) 7 aircraft at ids 39..45 (stride 15 → `DS:5EC8` = 54 with the add-on,
ids 46..53 are gaps: `table_rec` returns NULL).

Record (24 bytes; offsets verified against the accessors: `012f/0193` read the u16 at record **+02**, `0204`
+04, `0252` +05, `02a0` +06 (3 bytes), `02f8` +09, `0346` +0A, `0394` +0B, `03e2` u32 at +0C, `0434` u32 at
+10, `0486` u32 at +14; the name offset is the u16 at +00):

| Off | Type | Meaning |
|---|---|---|
| 00 | u16 | tail offset of the name (and plural) |
| 02 | u16 | service mask, bit `1 << (service+1)` (`DS:1E08[service]`) |
| 04 | u8 | class 0..3 (as above) |
| 05 | u8 | own id |
| 06 | 3 bytes | first-service date m/d/yy |
| 09 | u8 | altitude band (TABLES `DS:652E` index) |
| 0A | u8 | multi-seat flag (likely) |
| 0B | u8 | unknown (10..80) |
| 0C | u32 | range |
| 10 | u32 | extra range with drop tanks |
| 14 | u32 | cruise altitude (ft) |


### 2.2 Accessors — verified

All accessors (except `0077`) call `r = table_rec(DS:5ECA, id)` and `fatal(line)` when `r == NULL`.

| Addr | Name | Returns |
|---|---|---|
| `2777:0077` | `ac_exists(id)` | `table_rec != NULL` (0/1) |
| `2777:0097` | `ac_count()` | `DS:5EC8` |
| `2777:00a1` | `ac_name(id)` → far char* | `table_text(5ECA, id, r->name_off)` (fatal 7Ch) |
| `2777:0101` | `ac_plural(id)` → far char* | `p = ac_name(id); return p + _fstrlen(p) + 1` (same segment) |
| `2777:012f` | `ac_has_service(id, char s)` | `(r->mask & DS:1E08[s]) != 0` (fatal 98h); `DS:1E08` = u16[11] {2,4,…,0x800} |
| `2777:0193` | `ac_side(id)` | `0f67:02ed(s)` (service → side group) for the **first** s in 0..10 with the mask bit; none → uninitialised local (garbage) (fatal ADh) |
| `2777:0204` | `ac_class(id)` | `r->class` (fatal C4h) |
| `2777:0252` | `ac_selfid(id)` | `r->id` (fatal D4h) |
| `2777:02a0` | `ac_date(id)` | `date_make(&r->date)` (`284f:0007`) (fatal E4h). Uncalled |
| `2777:02f8` | `ac_alt_band(id)` | `r->band` (fatal F4h) |
| `2777:0346` | `ac_multiseat(id)` | `r->+0A` (fatal 104h). Uncalled |
| `2777:0394` | `ac_b0b(id)` | `r->+0B` (fatal 114h). Uncalled |
| `2777:03e2` | `ac_range(id)` → long | u32 +0C (fatal 124h) |
| `2777:0434` | `ac_range_ext(id)` → long | u32 +10 (fatal 134h) |
| `2777:0486` | `ac_cruise_alt(id)` → long | `u32(+14) << 2` (LXLSH by 2: feet → ¼-ft world units) (fatal 144h) |

### 2.3 Aircraft choice lists (`DS:5AFC`) — verified

Three lists `acl[3]` at `DS:5AFC + slot*0x143` (323 bytes each):
`+000 s16 service` (sign-extended char), `+002 u8 flags`, `+003 u16 id[160]`, `+141 u16 count`.
Globals: `DS:5EC5` s8 current slot, `DS:5EC6` u8 "must carry drop tanks", `DS:5EC7` u8 "plural names".
`DS:1E1F` = u8[4] class bits `{04, 08, 10, 20}` (class c → bit `4 << c`; class 4 would read the "a" of
`"air"` = 61h).

`flags`: bit 0 = exact service (`ac_has_service`), bit 1 = any service, neither = same side group
(`ac_side(id) == 0f67:02ed(service)`); bits 2..5 = accepted classes 0..3. flags == 0 → no filtering at all.
Values used by the mission modules: 4, 5, 6, 0x15, 0x1D, 0x38, 0x3C.

```c
void acl_build(char service, u8 flags, char slot, u8 need_tanks)       /* 2777:04fa */
{   int n = 0; int id = 0;
    DS_5EC5 = slot; DS_5EC6 = need_tanks;
    memset(&acl[slot], 0, 0x143);
    acl[slot].service = service; acl[slot].count = 0; acl[slot].flags = flags;
    while (id < DS_5EC8) {
        if (acl[slot].flags) id = acl_next(id);           /* 05c0: first acceptable id >= id */
        if (id < DS_5EC8) { acl[slot].id[n++] = id; id++; }
    }
    acl[slot].count = n;
}
char acl_next(char id)                                   /* 2777:05c0 (id is a signed char!) */
{   char side = 0f67_02ed((char)acl[cur].service);
    if (!acl[cur].flags) return id;
    for (; id < DS_5EC8; id++) {
        if (!ac_exists(id)) continue;
        if (DS_5EC6 && !ord_any_droptank(id)) continue;          /* 2ab3:0557 */
        u8 f = acl[cur].flags;
        if (!(f & 2)) {
            if (f & 1) { if (!ac_has_service(id, (char)acl[cur].service)) continue; }
            else if (ac_side(id) != side) continue;
        }
        if (DS_1E1F[ac_class(id)] & f) return id;
    }
    return id;
}
```
(`acl_next` is evaluated with `cur` = `DS:5EC5`; `id` is a char, so ids ≥ 128 would wrap — not reached.)

| Addr | Name | Behaviour |
|---|---|---|
| `2777:06fd` | `acl_select(slot, plural)` | `DS:5EC5 = slot; DS:5EC7 = plural` |
| `2777:070e` | `acl_count()` | `acl[DS:5EC5].count` |
| `2777:0724` | `acl_id(i)` | `acl[DS:5EC5].id[i]` (no bound check) |
| `2777:0741` | `acl_name(i)` → near char* | `strpool_copy(DS:5EC7 ? ac_plural(id) : ac_name(id))` (`24d5:0005`, emd1 §1.3), `id = acl_id(i)`; the call is made through a pushed far return address (`push cs; push 077e; push seg; push off; retf`) |

Callers: the mission modules fill slot 0 (player side) and slot 1 (enemy) for single missions (`DS:626B ==
0`), and the single-mission screen `100e` reads them.

---

## 3. Medals (`27f0`, medals.c) — verified

`27f0:0004 medals_open()`: `fp = vol_fopen(file_name("medals", -1, "dat"), …)` (`MEDALS.DAT`, SHELL1; fatal 49h
if missing); `fread(&DS:5ED0, 2, 1)` = count n; `DS:5ECE = xmalloc(n*11)`; `fread(DS:5ECE, 11, n)`;
`fread(&len, 2, 1)`; `DS:5ECC = xmalloc(len)`; `fread(DS:5ECC, 1, len)`; `fclose`; then every record's +00
(a text offset) is replaced by the near pointer `DS:5ECC + off`. `27f0:0191 medals_close()`: `xfree(5ECE)`,
`xfree(5ECC)`.

Record (11 bytes): `+00 char* name`, `+02 u8 service mask` (tested with `DS:1E2C[service]` = u8[11]
`{02,04,08,10,20,0,0,0,0,0,0}`), `+03 s16 req[4]` = {victories, air, ground, ships} thresholds (−1 = the
wound medal).

| Addr | Name | Behaviour |
|---|---|---|
| `27f0:00f5` | `medal_name(char m)` | `rec[m].name` (no static caller; reached through the `%h` debrief substitution table) |
| `27f0:010d` | `medal_for_service(char m, char s)` | `(rec[m].mask & DS:1E2C[s]) != 0` |
| `27f0:013c` | `medal_is_wound(char m)` | `m == 0 \|\| m == 11` (Purple Heart / Wounded Badges) |
| `27f0:0155` | `medal_req(char m, s16 out[4])` | copies `rec[m].req[0..3]` |

Shipped `MEDALS.DAT` (20 medals, US 0..10, Japan 11..19; `req` = victories, the other three are 250 = never
the binding term in practice / 0 for the wound medals):

| m | medal (services) | victories |
|---|---|---|
| 0 | Purple Heart (USN/USMC/USAAF) | −1 (wound) |
| 1 | Air Medal (US) | 4 |
| 2 | Distinguished Flying Cross (US) | 10 |
| 3 | Legion Of Merit (US) | 18 |
| 4 | Silver Star (US) | 30 |
| 5 | Distinguished Service Medal (USAAF) | 50 |
| 6 | Distinguished Service Medal (USN/USMC) | 50 |
| 7 | Navy Cross (USN/USMC) | 75 |
| 8 | Distinguished Service Cross (USAAF) | 75 |
| 9 | Congressional Medal Of Honor (USAAF) | 100 |
| 10 | Congressional Medal Of Honor (USN/USMC) | 100 |
| 11 | Wounded Badges (IJN/IJA) | −1 |
| 12..19 | Sacred Treasure 2nd, Golden Kite 3rd, Rising Sun 3rd, Sacred Treasure 1st, Golden Kite 2nd, Rising Sun 2nd, Golden Kite 1st, Rising Sun 1st (IJN/IJA) | 4, 10, 18, 25, 40, 75, 100, 150 |

The award rule itself (`050c:0035 medal_check`, one medal per mission, wound medal when SIM.OUT +02 bit 2)
is specced in `shell_ui_debrief.md`; promotion (ranks, merit points) in `shell_data_sys.md` (`225d`).

---

## 4. Flight sizes and formations (`280a`) — verified

`280a:00af flight_open()`: if `DS:1E46 == 0`: `emd_open(file_name("flight", module_active(), "dat"))` —
**only the file of the active data set** (`FLIGHT0` or `FLIGHT1`, identical in the shipped data);
`list_read(&DS:5ED2, elsize 0x15, cb 280a:000a)`; `emd_close_rest_far()`; `DS:1E46 = 1`. Always:
`DS:5EDC = enddate_get(module_active(), 1)`. `280a:0431 flight_close()`: if loaded
`list_free(&DS:5ED2, 280a:006b)`, `DS:1E46 = 0`.

List `DS:5ED2` = one 21-byte element per service code (list index = service; 5 elements; `list_at` fatal
46h for services ≥ 5):
`+00 u8 service` (read by the callback `280a:000a`: `emd_read_far(el, 1, 1)`), `+01 list A` (elsize 4, dated:
`{u16 date, u8 role, u8 planes}`), `+0B list B` (elsize 4, dated: `{u16 date, u8 formation, u8 role}`).
`280a:006b` frees both sub-lists.

| Addr | Name | Behaviour |
|---|---|---|
| `280a:0110` | `flight_planes(char service, char role, u16 date)` → u8 | `keyed_lookup(list A, key = +02 role, date, END = DS:5EDC)` → `+03` planes |
| `280a:021b` | `flight_formation(char service, char role, u16 date)` → u8 | `keyed_lookup(list B, key = +03 role, …)` → `+02` formation (FORM id, §11) |
| `280a:032c` | `flight_formations(char service, char role, u16 date, s8 *out)` → count | see below (formation chooser of the flight map, `1513:0c71`) |

```c
int flight_formations(service, role, date, s8 *out)      /* 280a:032c */
{   int n = 0; u16 prev = 0;
    for (e = list_first(B); e; e = list_next(B)) {
        if (e->role != role) continue;
        if (e->date > date) break;
        int v = (s8)e->form;  if (v == 14 || v == 15) v = 0; else if (v > 7) v -= 8;
        if (n == 0 || e->date <= prev) out[n++] = v;
        else {                               /* a later entry: v becomes the default (front) */
            s8 old = out[0];
            if (old != v) {
                out[0] = v;
                int c; for (c = 1; c < n; c++) if (out[c] == v) { out[c] = old; break; }
                if (c == n) out[n++] = old;
            }
        }
        prev = e->date;
    }
    return n;
}
```

Shipped `FLIGHT0/1.DAT`: services 0..2 (US): planes role 0 = 3 from 7 Dec 1941, 4 from 11 Mar 1942; roles 1..3
= 4. Services 3, 4 (Japan): 3 for every role, fighters 4 from 2 Oct 1943. Formations: 1 Dec 1941 entries of
formations 0,2,3,4,5,6 for roles 0..2 (the chooser list), then 7 Dec 1941 defaults (US: role 0 → 0, role 3 →
16 (→ 8 in the chooser), role 1 → 4, role 2 → 5; Japan: roles 0..2 → 0, role 3 → 8), fighters → 6 ("Finger
Four") from 11 Mar 1942 (US) / 2 Oct 1943 (Japan).

---

## 5. Dates (`284f`, date.c) — verified

Globals: `DS:1E52` u32 = 2 415 033 (the Julian-day-style count of 1 Jan 1900 in this scheme); `DS:1E5C` u8[12]
month lengths `31 ?? 31 30 31 30 31 31 30 31 30 31` (`DS:1E5D` February, rewritten to 29/28 by every call);
`DS:1E59` = `{7, 15, 45}` (15 Aug 1945, VJ day); `DS:1E68` near char*[12] long month names ("Jan.", "Feb.",
"March", "April", "May", "June", "July", "Aug.", "Sep.", "Oct.", "Nov.", "Dec."); `DS:1E80` short names
("Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.").

```c
u16 date_make(s8 far *mdy)                    /* 284f:0007: {month 0..11, day 1.., year-1900 (signed)} */
{   int y = mdy[2] + 6612;                    /* 0x19D4 */
    if (y < 0) fatal(37h);
    DS_1E5D = (y % 4 == 0) ? 29 : 28;
    if (mdy[0] < 0 || mdy[0] > 11 || mdy[1] < 1 || DS_1E5C[mdy[0]] < mdy[1]) fatal(3Eh);
    int d = mdy[1]; for (int i = 0; i < mdy[0]; i++) d += DS_1E5C[i];
    long t = 365L * y + d + (y - 1) / 4;      /* LXMUL; (y-1)/4 signed idiv */
    return (u16)t - (u16)DS_1E52;             /* low word only */
}
char far *date_split(u16 date, u8 far *out)   /* 284f:0131 -> {month, day, year-1900} */
{   long L = (long)date + DS_1E52;            /* u32 add */
    if (L < 0) fatal(5Fh);
    int y = (int)((L << 2) / 1461);           /* LXLSH 2, LDIV signed, low word */
    int d = (u16)L - (u16)(365L * y) - (y - 1) / 4;
    if (L <= 365) d++;                        /* hi<0, or hi==0 && lo<=0x16D: never for game dates */
    DS_1E5D = (y % 4 == 0) ? 29 : 28;
    int m = 0; while (d > 0) d -= DS_1E5C[m++];
    m--; out[0] = m; out[1] = d + DS_1E5C[m]; out[2] = (u8)y + 0x2C;
    return out;
}
```
Round trip `date_split(date_make(x)) == x` holds for all day numbers 10 000..25 000 (checked by script).
`3BD4h` = 7 Dec 1941; `ENDDATE0.DAT` = 16 663 (15 Aug 1945), `ENDDATE1.DAT` = 17 171 (5 Jan 1947).

| Addr | Name | Behaviour |
|---|---|---|
| `284f:0109` | `date_weekday(date)` | `((u32)date + DS:1E52 + 1) % 7` (LUMOD). Uncalled |
| `284f:021c` | `date_text(date, char *buf)` | `date_split`; `sprintf(buf, "%s %d, %d", DS:1E68[m], day, year + 1900)`; `str_upper(buf)` (`22ce:0367`); returns buf ("DEC. 7, 1941") |
| `284f:026b` | `date_text_short(date, buf)` | `"%s %d, '%d"` with `DS:1E80[m]`, year − 1900; `str_upper` ("DEC. 7, '41") |
| `284f:02b7` | `date_vj_day()` | `date_make(&DS:1E59)`. Uncalled |

---

## 6. Campaigns (`287b`, campaign.c) — verified

### 6.1 `CMP<n>.DAT`

`287b:0104 campaign_load(char set)` (`set` = pilot +25h campaign set = data set; FFh = all sets):
```
if ((s8)set < 0 && DS:1F3C) fatal(66h)             /* "all" requested while loaded */
DS:5EFE = (set == 0xFF)
if (!DS:1F3C) {
    DS:5EFF = table_load("cmp","dat", recsize 0x0D, stride 10, mode (5EFE ? 0x10 : 0x08) | 2,
                         flags 6 (list + tail), hdr DS:5EF4, read_cb 287b:0009, free_cb 287b:00e1)
              /* mode 0x0A = swap mode (one file resident), 0x12 = all files */
    0 -> fatal(76h)
    DS:5F05 = table_count(5EFF, &DS:5EDE)          /* DS:5EDE u16[9] = records per file */
}
if (!DS:5EFE) {
    DS:5F03 = DS:5EDE[set]                           /* campaigns in this set */
    DS:5F01 = set == 0 ? 0 : DS:5EDE[0] + (set-1)*10 /* first id of the set */
    if (DS:5F03) { l = table_file_data(5EFF, set);  /* 2008:13fa, swaps file `set` in */
                   DS:5EF0:5EF2 = l->items (far) }   /* list +06 */
    else DS:5EF0 = DS:5EF2 = 0
}
DS:1F3C = 1
```
Note: once loaded, a later call with a different `set` does **not** reload the table (only the file swap /
counters are redone), and asking for "all" while loaded is fatal.

Record (13 bytes, read by `287b:0009`: `emd_read_far` 2, 1, 2, 3, 3 bytes, then `emd_read(&n, 2, 1)`,
`p = xmalloc((n+1)*2)`, `p[0] = n`, `emd_read(p+1, 2, n)`; freed by `287b:00e1`):
`+00 u16` text offset (name), `+02 u8` (1 in all records), `+03 u16` service mask (`DS:1F26[s]` = u16[11]
`1 << (s+1)`), `+05` start date m/d/yy (raw), `+08` end date m/d/yy (raw), `+0B` near ptr → `{u16 n, u16
squadron[n]}` (squadrons that fly the campaign).

Shipped: `CMP0` 52 campaigns (ids 0..51: IJN 0..17, IJA 18..24, USMC/USN 25..39, USAAF 40..51), `CMP1` 9
(1946: ids 52..60).

| Addr | Name | Behaviour |
|---|---|---|
| `287b:024c` | `campaign_loaded()` | `DS:1F3C` |
| `287b:0256` | `campaign_count()` | `DS:5EFE ? DS:5F05 : DS:5F03` |
| `287b:053f` | `campaign_first()` | `DS:5EFE ? 0 : DS:5F01` |
| `287b:051f` | `campaign_exists(id)` | `table_rec != NULL` |
| `287b:026e` | `campaign_name(id)` → near char* | `strpool_copy(table_text(5EFF, id, rec.+00))` (fatal B7h if no record) |
| `287b:02d7` | `campaign_b02(id)` | `rec.+02` (fatal C6h). Uncalled |
| `287b:0325` | `campaign_has_service(id, char s)` | `(rec.mask & DS:1F26[s]) != 0` (fatal D5h) |
| `287b:0389` | `campaign_start(id)` | `date_make(rec+05)` (fatal E8h) |
| `287b:03e1` | `campaign_end(id)` | `date_make(rec+08)` (fatal F8h) |
| `287b:0439` | `campaign_has_squad(id, int sq)` | 1 if any of the `n` squadrons == sq (scans all, no early exit) (fatal 10Ah) |
| `287b:04b5` | `campaign_available_after(u16 date, char s)` | `fatal(11Dh)` if all-mode; for i < `DS:5F03`: id = `5F01+i`: if `campaign_start(id) >= date` (unsigned) and `campaign_has_service(id, s)` → 1; else 0 |
| `287b:0556` | `campaign_close()` | `table_free(5EFF)`; `DS:1F3C = 0` |

### 6.2 `CMPTEXT<n>.DAT` (briefing / end texts)

`287b:056a cmptext_open()`: `DS:1F3D` must be 0 (fatal 159h); `DS:1F3D = table_load("cmptext","dat", 4,
stride 10, mode 0x0A (swap, far), flags 5)`, 0 → `fatal(163h)`; returns 1. Records = u32 text offsets (ids as
the campaigns); each text block holds two strings.

| Addr | Name | Behaviour |
|---|---|---|
| `287b:05ec` | `cmptext_intro(id)` → far char* | `table_string(DS:1F3D, id)` (`26c4:00a5`) (fatal 16Eh if not open) |
| `287b:062a` | `cmptext_end(id)` → far char* | the string after it (`p + _fstrlen(p) + 1`) (fatal 17Eh) |
| `287b:0686` | `cmptext_close()` | `table_free(1F3D)`; `DS:1F3D = 0` |

### 6.3 Campaign progression (how the pieces fit)

Pilot record (`shell_data.md` §4): `+25h` campaign set, `+3Ch` (`DS:4790`) **campaign id**, `+27h/+2Bh`
dates, `+34h` (`DS:4788`) campaigns completed. Choice (shell_ui_career `0fa1`): for k from
`campaign_first()` over `campaign_count()` ids, list the campaigns with `campaign_exists(k)`, a start date ≥
the pilot's date and `campaign_has_service(k, service)`; the pilot's date is set to `campaign_start`. The
tour ends at `campaign_end(DS:4790)` (`0874:1113 career_tour_end`, shell_ui_debrief: `DS:4788 += 1`, dates
advanced to the end date, end text `cmptext_end`). `campaign_available_after(date, service)` decides whether
another campaign can follow (`0874:11a9`, `0a41:028d`). Squadron membership: `campaign_has_squad`.

---

## 7. Mission info per area (`28e4`, missinfo.c) — verified

`28e4:019f missinf_open()`: if `DS:1F54 == 0`: `DS:5F14 = table_load("missinf","dat", recsize 0x33, stride
0, mode 0x12, flags 2 (list), hdr DS:5F08, read_cb 28e4:000b, free_cb 28e4:00c6)`, 0 → `fatal(6Fh)`;
`DS:1F54 = 1`. Always `DS:5F12 = enddate_get(module_active(), 1)`. `28e4:0820 missinf_close()`: if loaded
`list_free(&DS:5F08, 28e4:00c6)`, `DS:1F54 = 0`.

Record (51 bytes): `+00 u8 area` (world number), then five dated lists (read by `28e4:000b`, freed by
`28e4:00c6`):

| Off | List | Element | Used by |
|---|---|---|---|
| 01 | L1 | 7 bytes `{date, s16 w[2], u8 service}` | `0270` target kind |
| 0B | L2 | 11 `{date, s16 w[4], u8 service}` | `04da` role vs ships |
| 15 | L3 | 11 `{date, s16 w[4], u8 service}` | `03a2` role vs land targets |
| 1F | L4 | 25 `{date, s16 w[11], u8 side group}` | `0612` enemy service |
| 29 | L5 | 6 `{date, u8 w[4]}` | `074a` ground target class weights |

| Addr | Name | Behaviour |
|---|---|---|
| `28e4:0152` | `missinf_area(i)` | `rec[i].area` (fatal 55h) |
| `28e4:0222` | `missinf_count()` | `table_count(5F14, NULL)` |
| `28e4:0237` | `missinf_find(char area)` → int | first i < count (count taken as a signed char) with `missinf_area(i) == area`, else −1 |
| `28e4:0270` | `mi_target_kind(i, char service, u16 date)` | `e = keyed_lookup(L1, key +06, …, END 5F12)`; return **`rng_pick_weighted(e.w, 2)`** (0 = ships, 1 = land, per `3164:00de`) |
| `28e4:04da` | `mi_role_ships(i, service, date)` | `keyed_lookup(L2, key +0A)`; **`rng_pick_weighted(e.w, 4)`** → role 0..3 |
| `28e4:03a2` | `mi_role_land(i, service, date)` | `keyed_lookup(L3, key +0A)`; **`rng_pick_weighted(e.w, 4)`** |
| `28e4:0612` | `mi_enemy_service(i, char side, date)` | `keyed_lookup(L4, key +18)`; **`rng_pick_weighted(e.w, 11)`** → service code |
| `28e4:074a` | `mi_ground_weights(i, u16 date, u8 out[4])` | no key: `cur = first, nxt = next, end = nxt ? nxt.date : 5F12; for (k = 0; k < count && (date < cur.date \|\| end < date) && end != 5F12; k++) { cur = nxt; nxt = next; end = … }`; copies `cur+2..+5` to `out` (no RNG) |

Note `keyed_lookup` with a record index of −1 (`missinf_find` failed) passes `table_rec(-1)` = NULL to the list
functions (the callers in script.c do not check). Shipped: `MISSINF0` 10 records (areas 1..10), `MISSINF1` 1
(area 11). Example area 1 from 1 Jun 1944: USN L1 (40, 60), IJN (100, 0) …; L5 (10, 5, 5, 10).

---

## 8. World field generation (`2968`, wldfgen.c) — verified

`2968:0075 wldfgen_open()`: if `DS:1F62 == 0`: `DS:5F20 = table_load("wldfgen","dat", 0x0B, stride 10, mode
0x12, flags 2, hdr DS:5F16, read_cb 2968:0006, free_cb 2968:0049)`, 0 → `fatal(59h)`; `DS:1F62 = 1`. Always
`DS:5F22 = enddate_get(module_active(), 1)`. `2968:0446 wldfgen_close()`.

Record (11 bytes): `+00 u8 area`, `+01 list` of 23-byte dated elements (callback `2968:0006`):

| Off | Meaning |
|---|---|
| 00 | u16 date |
| 02..04 | u8 type[3] fighters (role 0), FFh = none |
| 05..07 | s8 weight[3] |
| 08..09 | u8 type[2] torpedo bombers (role 1) |
| 0A..0B | s8 weight[2] |
| 0C..0D | type[2] dive bombers (role 2) |
| 0E..0F | weight[2] |
| 10..11 | type[2] level bombers (role 3) |
| 12..13 | weight[2] |
| 14 | u8 pilot quality class 0..4 (TABLES `DS:6646` row) |
| 15 | u8 (second quality value, unused by this PS.EXE) |
| 16 | u8 key = service |

| Addr | Name | Behaviour |
|---|---|---|
| `2968:00f9` | `wf_count()` | `table_count(5F20, NULL)` |
| `2968:010e` | `wf_area(i)` | `rec.+00` (fatal 7Fh) |
| `2968:015b` | `wf_aircraft(i, char service, char role, u16 date)` → type | below |
| `2968:0313` | `wf_quality(i, char service, u16 date)` | `keyed_lookup(list, key +16)` → `+14` (fatal 101h) |

```c
char wf_aircraft(int i, char service, char role, u16 date)            /* 2968:015b */
{   int w[3] = {0,0,0};                                  /* SCOPY from DS:1F63 */
    rec = table_rec(5F20, i);  if (!rec) fatal(9Ch);
    e = keyed_lookup(&rec->list, key +16 == service, date, END = DS:5F22);
    int start = DS_1F69[role];                           /* DS:1F69 = {0,3,5,7,9} */
    int off = start > 0 ? start*2 + 2 : start + 3;       /* weights start: 3, 8, 12, 16 */
    int n = DS_1F69[role+1] - DS_1F69[role];             /* 3, 2, 2, 2 */
    for (k = 0; k < n; k++) w[k] = (s8)e[2 + off + k];
    char c = rng_pick_weighted(w, n);                    /* RNG */
    return e[2 + off - n + c];                           /* the type in front of the weights */
}
```
All-zero weights make `rng_pick_weighted` return `n−1` → usually FFh (no aircraft). Shipped: `WLDFGEN0` 10
areas, `WLDFGEN1` 1 (area 11).

---

## 9. Convoys (`29ae`, convoy.c) — verified

`29ae:0001 convoy_open()`: if `DS:1F7A == 0`: `DS:5F24 = table_load("convoy","dat", 0x0D, stride 10, mode 0x11
(all files, near), flags 1)`, 0 → `fatal(36h)`; `DS:5F26 = table_count`; `DS:1F7A = 1`. `29ae:0131
convoy_close()`.

Record (13 bytes): `+00 u8 id`, `+01 u8 class` (0 transports, 1 warships, 2 carrier group — the `S0..S2` of
`SHIP.DAT`), `+02 u8 ship count`, `+03 u8 ship types[8]` (FFh padding; `SHIPTXT` ids), `+0B u8 name kind`
(11h..17h; becomes convoy +01), `+0C u8 weight` (30/40). `CONVOY0.DAT`: 48 convoys, ids 0..23 US, 24..47
Japanese.

| Addr | Name | Behaviour |
|---|---|---|
| `29ae:0078` | `convoy_count()` | `DS:5F26`. Uncalled |
| `29ae:0082` | `convoy_get(void *dst, int id)` | `SCOPY` 13 bytes of the record to `dst` (fatal 58h); returns dst |
| `29ae:00e3` | `convoy_weight(id)` | `rec.+0C` (fatal 68h) |

---

## 10. Ship (convoy choice) tables (`29c2`, ship.c) — verified

`29c2:061c ship_open()`: if `DS:1F86 == 0`: `DS:5F32 = table_load("ship","dat", 0x3E, stride 10, mode 0x12,
flags 2, hdr DS:5F28, read_cb 29c2:000c, free_cb 29c2:00fc)`, 0 → `fatal(190h)`; `DS:1F86 = 1`. Always
`DS:5F34 = enddate_get(module_active(), 0)` (**force 0**: the cached end date). `29c2:092b ship_close()`.

Record (62 bytes): `+00 u8 area`, `+01 u8 convoy kind` (the `ckind` of `3164:0fb2`), then six dated lists:
`+02 W0`, `+0C W1`, `+16 W2`: elements 5 bytes `{date, s8 w[3]}` (class weights; W index = the caller's
"quality" argument); `+20 S0`, `+2A S1`, `+34 S2`: 6 bytes `{date, u8 convoy[3], u8 side group}` (candidate
`CONVOY` ids of class 0/1/2 for that side). `SHIP0.DAT` 32 records, `SHIP1.DAT` 5 (area 11, kinds 0..4).

| Addr | Name | Behaviour |
|---|---|---|
| `29c2:06a0` | `ship_count()` | `table_count(5F32, NULL)` |
| `29c2:06b5` | `ship_area(i)` | `rec.+00` (fatal 1B5h) |
| `29c2:0704` | `ship_kind(i)` | `rec.+01` (fatal 1C5h) |
| `29c2:01a2` / `01f8` / `024e` | `ship_class_w0/w1/w2(rec far*, u16 date)` | `e = list_find_dated(W0/W1/W2, date)` (emd1 §1.5: the entry in force; NULL before the first date — then reads IVT); `w[k] = (s8)e[2+k]`, k < 3; return **`rng_pick_weighted(w, 3)`** |
| `29c2:0752` | `ship_pick_class(i, char q, u16 date)` | rec (fatal 1D6h); q 0/1/2 → `ship_class_w0/1/2(rec, date)`; q > 2 → `fatal(1E7h)`; q < 0 → returns an uninitialised local |
| `29c2:02a4` / `03cc` / `04f4` | `ship_convoys_s0/s1/s2(rec far*, char side, u16 date, u8 out[3])` | `keyed_lookup(S0/S1/S2, key +05, END = DS:5F34)`; **only on a real match** copies `+02..+04` to `out` and returns 1; fallback → 0 |
| `29c2:080c` | `ship_convoys(i, char cls, char side, u16 date, u8 out[3])` → class | below |

```c
char ship_convoys(int i, char cls, char side, u16 date, u8 *out)       /* 29c2:080c */
{   char tried[3] = {0,0,0};                                            /* DS:1F87 */
    rec = table_rec(5F32, i);  if (!rec) fatal(1FDh);
    for (;;) {
        int ok;
        switch (cls) { case 0: ok = ship_convoys_s0(rec, side, date, out); break;
                       case 1: ok = ship_convoys_s1(…); break;
                       case 2: ok = ship_convoys_s2(…); break;
                       default: return 0xFF; }
        if (ok) return cls;
        tried[cls] = 1;
        cls = 0xFF; for (k = 0; k < 3; k++) if (!tried[k]) cls = k;     /* highest untried */
    }
}
```

---

## 11. Formations (`2a56`, form.c) — verified

`2a56:0114 form_open()` → 1: if `DS:1F94 == 0`: `DS:5F40 = table_load("form","dat", 0x0C, stride 10, mode
0x12, flags 6 (list + tail), hdr DS:5F36, read_cb 2a56:0070, free_cb 2a56:00e4)`, 0 → `fatal(94h)` (returns 1
either way); `DS:1F94 = 1`. `2a56:02db form_close()`.

Record (12 bytes; `2a56:0070` reads `+00 u16` then `list_read(+02, elsize 11, cb 2a56:002d)`): `+00 u16 name
offset`, `+02 list` of 11-byte elements `{u8 planes, list positions (elsize 1, cb 2a56:0006 reads 1 byte)}`.
`2a56:00e4` frees with `2a56:00b8` (frees the inner list).

| Addr | Name | Behaviour |
|---|---|---|
| `2a56:0185` | `form_count()` | `table_count(5F40, NULL)` |
| `2a56:019a` | `form_name(id)` → far char* | `table_text(5F40, id, rec.+00)` (fatal B7h) |
| `2a56:01fa` | `form_layout(id, char planes, u8 *pos, char *n)` | rec (fatal CCh); first element with `planes` == planes: copy its position bytes to `pos`, `*n` = their count; no element → nothing written |

`FORM0.DAT` (8 formations): 0 Vee, 1 Vic, 2 Line Astern, 3 Line Abreast, 4 Echelon Left, 5 Echelon Right, 6
Finger Four, 7 Element; e.g. Finger Four: 2 planes `{7}`, 3 `{3,3}`, 4 `{3,3,5}` (position codes of the
wingmen relative to the leader / previous plane; meaning: sim side, **guess**: compass-style directions).

---

## 12. Stations (`2a85`, station.c) — verified

`2a85:0006 station_open()`: if `DS:1F9E == 0`: `DS:5F44 = table_load("stat","dat", 6, stride 100, mode 0x12,
flags 1)`, 0 → `fatal(3Eh)`; `DS:5F42 = table_count`; `DS:1F9E = 1`. `2a85:0216 station_close()`.

Record (6 bytes): `+00 u16 area`, `+02 u16 record index` in `TARGET.<area>` or `CARRIER.<area>`, `+04 u16
carrier` (≠ 0: the station is a carrier). `STAT0` 123 stations (0..122), `STAT1` 32 (ids 123..154: file 1
starts at `count[0]`; the stride 100 only sizes the id range; the 1946 squadrons use 128..153).

| Addr | Name | Behaviour |
|---|---|---|
| `2a85:007d` | `station_count()` | `DS:5F42`. Uncalled |
| `2a85:0087` | `station_count_area(u8 area)` | number of ids with `+00 == area` (fatal 68h on a gap). Uncalled |
| `2a85:00f1` | `station_get(st, u16 *rec, u16 *area)` | `*area = +00; *rec = +02` (no NULL check) |
| `2a85:0127` | `station_area(st)` | `(u8)+00` (no NULL check) |
| `2a85:014d` | `station_in_area(st, u8 area)` | `+00 == area`. Uncalled |
| `2a85:0180` | `station_is_carrier(st)` | `(u8)+04` (no NULL check) |
| `2a85:01a7` | `station_find(u16 rec, u8 area, char carrier)` | first id with `+02 == rec && +00 == area && (+04 != 0) == (carrier != 0)`, else −1 |
| `2a85:0231` | `stattxt_open()` | `fatal(104h)` if `DS:1F9F:1FA1` ≠ NULL; `DS:1F9F:1FA1 = text_load("stattxt","dat",100)` (`26c4:02d9`, emd1 §1.6) |
| `2a85:027c` | `station_name(st)` → far char* | `text_get(DS:1F9F:1FA1, st)` (fatal 111h if not open) |
| `2a85:02c1` | `stattxt_close()` | `text_free`; far ptr = NULL |

---

## 13. Ordnance (`2ab3`, ordnance.c) — verified

### 13.1 `ORDNCE<n>.DAT`

`2ab3:013b ord_open()`: if `DS:1FB8 == 0`: `DS:5F52 = table_load("ordnce","dat", 0x44, stride 15, mode
0x12, flags 2, hdr DS:5F48, read_cb 2ab3:0001, free_cb 2ab3:0101)`, 0 → `fatal(6Ah)`; `DS:5F54 =
table_count`; `DS:1FB8 = 1`. `2ab3:057f ord_close()`. Ids = aircraft ids.

Record (68 bytes): `+00 u16` aircraft id, `+02 u16 n[11]` items per loadout, `+18 far ptr items[11]`.
Callback `2ab3:0001`: read `+00`; for L = 0..10: read `n[L]`, `items[L] = xfarmalloc(n*6)`, per item read
`u16 count`, `u16 code` and, **for loadout 0 only**, `u16 extra` (6-byte slots; +4 left uninitialised for
L ≥ 1). `2ab3:0101` far-frees the 11 item arrays.

Loadout 0 = the guns (code = gun type, `extra` = rounds per gun); loadouts 1..10 = stores. Codes are
`ORDTXT` ids: 0 drop tank, 1..9 guns (7.7 mm … 37 mm), 10..16 bombs (132 lb … 2 000 lb), 17 5-inch rocket,
18 Mark 13 torpedo, 19 type 91 torpedo; **−1 = loadout not available**, **−2 = valid empty ("clean")
loadout** (`{0, −2}`).

| Addr | Name | Behaviour |
|---|---|---|
| `2ab3:01bd` | `ord_count_ids()` | `DS:5F54`. Uncalled |
| `2ab3:01c7` | `ord_n(type, char L)` | `n[L]` (fatal 94h) |
| `2ab3:021d` | `ord_items(type, char L, s16 *cnt, s16 *code)` | for i < n[L]: `cnt[i] = item.count; code[i] = item.code` (fatal A8h) |
| `2ab3:02d1` | `ord_gun_rounds(type, s16 *out)` | loadout 0: `out[i] = item.extra` (fatal C0h) |
| `2ab3:0504` | `ord_has_droptank(type, char L)` | `ord_items`; 1 if some `code[i] == 0` among `n[L]` items |
| `2ab3:0557` | `ord_any_droptank(type)` | 1 if `ord_has_droptank(type, L)` for some L in 1..10 |

### 13.2 Loadout choice — `2ab3:03a7 ord_pick(char mtype, char type, char longrange, char side)` (RNG)

```c
static u8 ord_mode(char mtype, char side)                 /* 2ab3:0348 */
{   s8 v = DS_1FB9[mtype*3 + side];                       /* u8[11][3] */
    switch (v) { case 0: case 3: return 0;
                 case 1: return 1;  case 2: return 2;
                 case 4: return DS_63ED == 1 ? 2 : 1;     /* side-2 flight 0 target kind (+08) */
                 case 5: return DS_635D == 1 ? 2 : 1;     /* side-1 flight 0 target kind */
                 default: return v; }                     /* > 5: the byte itself (not in the table) */
}
char ord_pick(char mtype, char type, char longrange, char side)     /* 2ab3:03a7 */
{   s16 w[3] = {50, 30, 20};      /* DS:1FDA */
    u8 tried[3] = {0, 0, 0};      /* DS:1FE0 */      u8 done = 0;
    s16 cnt[5], code[5];          cnt[0] = 0;        /* code[] uninitialised */
    char cls = ac_class(type);
    char mode = ord_mode(mtype, side);
    int k = rng_pick_weighted(w, 3);                   /* RNG, always exactly one draw */
    char L;
    while (!done) {
        tried[k] = 1;
        L = (u8)TABLES_6556[cls*12 + mode*3 + k] + 1;  /* DS:6556 s16[5][12], low byte */
        ord_items(type, L, cnt, code);
        if (cnt[0] > 0 || code[0] == -2) {
            if (!longrange) done = 1;
            else {
                if (L == 1) L = 8; else if (L == 5) L = 9; else if (L == 6) L = 10;   /* drop-tank variants */
                ord_items(type, L, cnt, code);
                int n = ord_n(type, L);
                for (i = 0; i < n; i++) if (code[i] == 0) { done = 1; break; }
            }
        }
        if (!done) { k = -1; for (i = 0; i < 3; i++) if (!tried[i]) k = i; }
    }
    return L;
}
```
`DS:1FB9` (mtype 0..10 × side 0..2): all 0 except mtype 4 side 1 = 5, mtype 6 side 2 = 4, mtype 7 side 2 = 4,
mtype 8 side 0 = 1, mtype 9 side 0 = 2. Quirks (keep): `cnt[0]` keeps the value of an earlier call when a
loadout has no items, and `code[0]` is read uninitialised on the first try if `n[L] == 0` (never in the
shipped data: every loadout has ≥ 1 item); with `longrange` the accepted L is the drop-tank variant; if all
three k are tried without success `k = −1` indexes `tried[-1]` (the saved SI on the stack) and
`TABLES[… + mode*3 − 1]`, and the loop may not terminate (the shipped data always succeeds within three
tries — **likely**; the port should stop and return the last L, `/* PORT: */`). At most 5 items per loadout
fit `cnt/code` (shipped maximum: 3).

### 13.3 `ORDTXT<n>.DAT`

`2ab3:059a ordtxt_open()`: `DS:5F46` must be 0 (fatal 19Eh); `DS:5F46 = table_load("ordtxt","dat", 4, 10,
mode 0x0A, flags 5)`, 0 → `fatal(1A8h)`; returns 1. `2ab3:061c ordtxt_name(code)` = `table_string(5F46,
code)` (fatal 1B3h); `2ab3:065a ordtxt_plural(code)` = the string after it (fatal 1BFh); `2ab3:06b7
ordtxt_close()`.

---

## 14. 2-D geometry helpers (`2b1f`, `2b42`) — verified

Positions are the 12-byte `{s32 x, s32 z, s32 alt}` records (`shell_data.md` §6). Angles are 16-bit binary
(65536 = 360°). The trig/atan/distance primitives are in the asm library `3d50` (owner video/ts; semantics
**likely**): `3d50:225a(long x, long y)` → angle (atan2), `3d50:1f7c(a)` / `3d50:1f87(a)` → s16 sine/cosine
×16384 (which is which: see the 3d50 spec), `3d50:01e6(pos far *a, pos far *b)` → long distance,
`3d50:027a(s16 a, s16 b)` → long product.

| Addr | Name | Behaviour |
|---|---|---|
| `2b1f:000c` | `ang_to_deg(u16 a)` | `LXRSH((u32)a * 90, 14)` (a zero-extended) |
| `2b1f:0029` | `deg_to_ang(int d)` | `((long)d << 14) / 90` (LDIV signed). Uncalled |
| `2b1f:0049` | `deg_norm(int d)` | `while (d < 0) d += 360; return d % 360`. Uncalled |
| `2b1f:00b4` | `heading(pos far *a, pos far *b)` → u16 | `3d50:225a(b.x − a.x, b.z − a.z) − 0x4000` (s32 differences); callers use `>> 8` as the byte heading |
| `2b1f:0069` | `pitch(pos far *a, pos far *b)` → s16 | `d = dist(a, b)`; `−(3d50:225a(b.alt − a.alt, d) − 0x4000)` |
| `2b1f:00f9` | `heading_deg(a, b)` | `ang_to_deg(heading(a, b))` |
| `2b1f:0121` | `project(pos far *a, u16 ang, long d, pos near *out)` | `out.x = a.x + fixmul14(d, −3d50:1f7c(ang))`; `out.z = a.z + fixmul14(d, 3d50:1f87(ang))`; **out.alt untouched** |
| `2b1f:0189` | `rotate2(s16 v[2], u16 ang)` → v | `s = 1f87(ang), c = 1f7c(ang)`; `v0' = LXRSH(v0*s + v1*(−c), 14)`, `v1' = LXRSH(v0*c + v1*s, 14)` (products via `3d50:027a`, 32-bit sums); returns v. Uncalled |
| `2b1f:021d` | `dist(pos far *a, pos far *b)` → long | `3d50:01e6(a, b)` |
| `2b42:0002` | `imul32x32` (near, internal) | signed 32×32 → 64-bit product in DX:AX:CX:BX (sign handled by negating the operands and the result) |
| `2b42:00ae` | `fixmul14(long a, int b)` → long | `(s64)a * (long)b >> 14` (arithmetic; bits 14..45 of the product) |

(`2b1f:0000..000b` is the tail of `2b1f`'s predecessor, not code of this segment.)

---

## 15. Data-file summary

| File (M1SHL unless noted) | Loader | Layout |
|---|---|---|
| `AIR0/1.DAT` | `2777:0000` | §2.1 |
| `MEDALS.DAT` (SHELL1) | `27f0:0004` | §3 |
| `FLIGHT<set>.DAT` | `280a:00af` | §4 |
| `CMP0/1.DAT`, `CMPTEXT0/1.DAT` | `287b:0104`, `287b:056a` | §6 |
| `MISSINF0/1.DAT` | `28e4:019f` | §7 |
| `WLDFGEN0/1.DAT` | `2968:0075` | §8 |
| `CONVOY0.DAT` | `29ae:0001` | §9 |
| `SHIP0/1.DAT` | `29c2:061c` | §10 |
| `FORM0.DAT` | `2a56:0114` | §11 |
| `STAT0/1.DAT`, `STATTXT0/1.DAT` | `2a85:0006`, `2a85:0231` | §12 |
| `ORDNCE0/1.DAT`, `ORDTXT0.DAT` | `2ab3:013b`, `2ab3:059a` | §13 |
| `SERVICE0.DAT` (`u16` service codes 0..4) | `1193:0084` (lead file §2) | fills `DS:49CE` |

All extens tables: `u32 tail_size, u16 count, records/list elements, tail` (sys part §4.2).

---

## Port notes

* Keep the lookups exactly (element-0 first candidate, inclusive end dates, fallback to the last examined
  element): they choose aircraft, roles, enemy services and convoys and so shape every generated mission.
* `/* PORT: */` guard the NULL/IVT reads (`KEY(NULL)` in the keyed lookups, `list_find_dated` before the first
  date, `table_rec(-1)` from `missinf_find` failures): treat as "no element". They do not occur with the shipped
  data for valid areas (**likely**).
* `/* PORT: */` `ord_pick`: bound the retry loop (k = −1 case) and initialise `code[]`; identical results for
  the shipped data.
* `ac_side` and `ship_pick_class` return uninitialised values in impossible cases: return 0 / FFh.

## Hand-offs

* **shell_ui (answers to shell_ui.md §8)**: `DS:49CE` u16[11] is filled by `1193:0084 service_load`
  (`memset FF`, then the u16 records of `SERVICE0.DAT` + `SERVICE<k>.DAT` of the installed data sets: 0..4);
  `2b1f:0069` = pitch, `2b1f:00b4` = heading (binary angle, −0x4000 offset), `2b1f:0121` = project x/z along a
  binary angle (altitude kept) — see §14. `2777:0101` returns the **plural** aircraft name (used by fltplan
  `%c`). `2777:0741` names come from the string pool and are overwritten after ~500 bytes.
* **video / ts (3d50 finisher)**: `3d50:225a(long, long)` atan2 → binary angle, `3d50:1f7c/1f87` sin/cos ×16384,
  `3d50:01e6` distance of two 12-byte positions, `3d50:027a` 16×16→32 multiply, `3d50:16b0` midpoint — all used
  by the mission builder; the exact atan/distance approximations decide generated waypoints.
* **sim_world**: `FORM.DAT` position codes (§11) and `ORDTXT` codes (§13.1) are what SCRIPT group +01
  (formation id) and the aircraft ordnance slots refer to.

## Open questions

* AIR `+0A` (multi-seat?) and `+0B` (10..80) — uncalled in PS; the sim may read AIR data of its own.
* `WLDFGEN` element `+15` (second quality value), CMP `+02` (always 1), MISSINF L5 exact class order (script.c
  target classes 0..3).
* FORM position-code meaning (sim side).
