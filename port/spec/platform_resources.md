# Platform §6: volumes, RESOURCE.CFG lines, chunk access, decompressor

Part of the platform spec; index, §1–§5 and §7–§11 are in `platform.md`. Status: complete (phase 3 finisher). Confidence: **verified** = read in the disassembly (INTRO; PS/AP compared with an aligned diff), **likely**, **guess**.

## 6. Volumes, chunk access and decompression

Scope: the Dynamix volume layer (`volume.c`, INTRO seg `049D`, PS/AP inside seg `0000`), the INTRO
RESOURCE.CFG line table (seg `05CB`), the chunk-level file API and the LZW/RLE decompressor of the
system library (INTRO `05DA`, PS `16E3`, AP `1D32`). File format facts are in
`port/formats/resources.md`; this section is the *code* that reads them.

Conventions: `DS:xxxx` offsets are given as INTRO / PS / AP. `FILE*` are Borland near `FILE*`
(medium model, DGROUP). All functions are `far` cdecl unless noted.

### 6.1 volume.c

#### 6.1.1 Function table

| INTRO | PS | AP | name | signature | purpose | conf. |
|---|---|---|---|---|---|---|
| 049d:0008 | 0000:049e | 0000:0448 | `vol_ext_subdir_path` | `char *(char *name)` | builds `"<ext>\<name>"` in a static buffer (fallback path) | verified |
| 049d:0059 | 0000:04ef | 0000:04e1 | `vol_set_log` | `void (char *logname)` | close old debug log, `fopen(logname,"wt")` | verified |
| 049d:008d | 0000:0523 | 0000:0517 | `vol_basename` | `char *(char *path)` | pointer after last `\` (or path) | verified |
| 049d:00bb | 0000:0551 | 0000:0555 | `my_fopen` | `VFILE *(char *name, char *mode)` | open: loose file first, then volumes, then `<ext>\name` | verified |
| 049d:03bc | 0000:084b | 0000:08cc | `my_fclose` | `int (VFILE *f)` | release record / fclose | verified |
| 049d:0411 | 0000:08a0 | 0000:0945 | `my_fread` | `int (void *buf, int size, int n, VFILE *f)` | fread clamped to the entry | verified (AP likely) |
| 049d:04f4 | 0000:0983 | – | `my_hread` | `long (void far *buf, long size, long n, VFILE *f)` | huge (>64K) read clamped to the entry | verified |
| 049d:0616 | 0000:0aa1 | 0000:0a0d | `file_hread` | `long (void far *buf, long size, long n, FILE *fp)` | huge read on a real FILE via the DOS handle | verified |
| 049d:06d1 | 0000:0b5a | 0000:0ae8 | `my_fseek` | `int (VFILE *f, long off, int whence)` | seek inside the entry | verified |
| 049d:078e | 0000:0c17 | 0000:0b79 | `my_ftell` | `long (VFILE *f)` | position inside the entry | verified |
| 049d:07ca | 0000:0c53 | 0000:0bba | `my_filelength` | `long (VFILE *f)` | entry size / file length | verified |
| 049d:084d | 0000:0cd6 | 0000:0c44 | `my_rewind` | `void (VFILE *f)` | `my_fseek(f,0,0)` | verified |
| 049d:0865 | 0000:0cee | 0000:0c58 | `my_fgetc` | `int (VFILE *f)` | one byte, −1 at entry end | verified |
| 049d:0913 | 0000:0d9c | 0000:0d02 | `my_feof` | `int (VFILE *f)` | pos ≥ size / `_F_EOF` | verified |
| 049d:0961 | 0000:0dea | 0000:0d48 | `my_fwrite` | `int (void *buf,int size,int n,VFILE *f)` | 0 for volume entries, else fwrite | verified |
| 049d:09b0 | 0000:0e39 | 0000:0d8d | `my_fputc` | `int (int c, VFILE *f)` | −1 for volume entries, else fputc | verified |
| 049d:09f8 | 0000:0e81 | 0000:0dcd | `my_setbuf` | `void (VFILE *f, char *buf)` | no-op for volume entries, else setbuf | verified |
| 049d:0a2c | 0000:0eb5 | 0000:0e04 | `vol_open_index` | `void (char *volname, u16 mask)` | read a volume header + directory, append a volume record | verified |
| 049d:0c4a | 0000:10d1 | 0000:1057 | `vol_init` | `void (char *logname, u16 mask_a, u16 mask_b)` | scan `*.DYN`, open matching volumes, hook INT 24h | verified |
| 049d:0d50 | 0000:11d7 | 0000:122b | `vol_shutdown` | `void (void)` | free directories/records, restore INT 24h | verified |
| 049d:0e28 | 0000:12af | 0000:12e0 | `vol_force_reopen` | `void (void)` | `vol_reopen_flag = 1` (no callers) | verified |
| 049d:0e32 | 0000:12b9 | 0000:12ea | `vol_find_entry` | `int (char *name, VREC *rec, int vol)` | hash lookup in one volume's directory | verified |
| 049d:0fa3 | 0000:1426 | 0000:1457 | `vol_select` | `FILE *(int vol)` | make volume `vol` the open one (−1 = close) | verified |
| 049d:10c1 | 0000:1544 | 0000:1586 | `vol_seek` | `void (u32 pos)` | fseek the open volume file if its cached position differs | verified |
| 049d:1128 | 0000:15ab | 0000:15d9 | `vol_rec_of` | `VREC *(void *handle)` | map a handle to its open-file record (1-entry cache); `NULL` resets cache | verified |
| 049d:118b | 0000:160e | 0000:163f | `vol_real_file` | `FILE *(VFILE *f)` | the loose FILE* of a record (no callers) | verified |
| 049d:11ab | 0000:162e | 0000:165e | `vol_int24` | `interrupt` | DOS critical-error handler | verified |
| – | – | 0000:0fde | `vol_name_cmp` | `int (char *a, char *b)` | qsort comparator: names starting `M` first (reverse order) | verified |

AP 0000:0420 (40 bytes, inline `strchr`, no callers) sits before `vol_ext_subdir_path` — unused.
PS 0000:0404…048a (calloc/free/strcat/strcpy/strchr wrappers) are not volume.c.

#### 6.1.2 Globals

| name | INTRO | PS | AP | type | meaning |
|---|---|---|---|---|---|
| `vol_hdr_buf` | DS:0794 | DS:2196 | (stack) | char[22] | header signature read buffer |
| `vol_log` | DS:07AA | DS:21AC | DS:1EBA | FILE* | debug log (opened by `vol_init(logname,…)`; never non-zero in shipped callers) |
| `vol_exclude` | – | – | DS:1EBC | char* | AP only: volume names containing this substring are skipped; AP main sets it to `"SH"` (DS:0583) |
| `vol_active` | DS:00C5 | DS:0DFF | DS:06F8 | u16 | set to 1 by `vol_init` if ≥ 1 volume opened. INTRO: read by `chdir_unless` 038e:0097 (no `chdir` while volumes are active) and `make_path` 038e:00cc (§2.4) |
| `data_prefix` | DS:2461 | DS:40CA | DS:4032 | char[?] | loose-file path prefix = `-n<path>` argument + `\` (set by main) |
| `vol_subdir_buf` | DS:24DC | DS:608E | DS:60E2 | char[] | result of `vol_ext_subdir_path` |
| `vol_cache_handle` | DS:2518 | DS:60CA | DS:610A | VFILE* | `vol_rec_of` cache key |
| `vol_cache_rec` | DS:251A | DS:60CC | DS:610C | VREC* | `vol_rec_of` cache value |
| `vol_last_subdir` | DS:251C | DS:60CE | DS:610E | char* | last fallback path tried |
| `vol_count` | DS:251E | DS:60D0 | DS:6110 | int | number of volumes opened (0 = volume layer off) |
| `vol_table` | DS:2520 | DS:60D2 | DS:6112 | VOLUME far* | `dos_alloc(0x17C)` = 10 × 26h |
| `vol_files` | DS:2524 | DS:60D6 | DS:6116 | VREC[10] / VREC[10] / **VREC[3]** | open-file records, 12h bytes each |
| `vol_cur` | DS:25D8 | DS:618A | DS:614C | int | index of the volume whose FILE is open (BSS 0 at start; −1 after `vol_select(-1)`) |
| `vol_open_files` | DS:25DA | DS:618C | DS:614E | u8 | number of records in use |
| `vol_reopen_flag` | DS:25DB | DS:618D | DS:614F | u8 | force `vol_select` to reopen (set by INT 24h) |
| `vol_crit_error` | DS:25DC | DS:618E | DS:6150 | u8 | set by INT 24h |
| `vol_in_open` | DS:25DD | DS:618F | DS:6151 | u8 | 1 while `fopen` runs inside the layer (INT 24h answers "fail") |
| `vol_inited` | DS:25DE | DS:6190 | DS:6152 | u8 | `vol_init` done |
| `vol_old_int24` | DS:25DF | DS:6191 | DS:6153 | void far* | saved INT 24h vector |

#### 6.1.3 Data structures

`VOLUME` (26h bytes, far array `vol_table`, index = order of opening):

| off | type | field |
|---|---|---|
| 00 | char[14] | file name as returned by findfirst (e.g. `SHELL1.DYN`) |
| 0E | int | own index |
| 10 | FILE* | open stream (only for the volume `vol_cur`; 0 otherwise) |
| 12 | u32 | cached file position of that stream |
| 16 | – | unused (2 bytes) |
| 18 | u16[4] | hash keys (header +18h) |
| 20 | int | entry count |
| 22 | u32 far* | directory (`dos_alloc(count*4)`), header +24h verbatim |

`VREC` (open-file record, 12h bytes, `vol_files[]`). The **handle returned by `my_fopen` is the
near address of the record** (not a FILE*) whenever volumes are active:

| off | type | field |
|---|---|---|
| 00 | int | volume index |
| 02 | u32 | absolute offset of the entry data in the volume (after the 13-byte name and u32 size) |
| 06 | u32 | entry size |
| 0A | u32 | current position inside the entry |
| 0E | int | in use |
| 10 | FILE* | loose file (`fopen` result), 0 = volume entry |

#### 6.1.4 Which volumes each program opens (verified)

`vol_init(log, a, b)`: `mask = (a|b) if (a||b) else default`; defaults INTRO `2001h`, PS `8001h`,
AP `8001h`. A volume is kept if `(flags & mask & F000h) && (flags & mask & 0FFFh)`.

| program | call | mask | volumes (Game dir) | order in `vol_table` |
|---|---|---|---|---|
| INTRO | main 038e:0b7c `vol_init(0, 4000h, 1)` | 4001h | COMMON1, M1CMN, M1SHL, SHELL1 | findfirst/findnext order (directory order) |
| PS | main 048e:0317 `vol_init(0, 4000h, 0FFFh)` | 4FFFh | COMMON1, M1CMN, M1SHL, SHELL1 | findfirst/findnext order |
| AP | main 50c8:018a `vol_init(0, 0, 0)`, `vol_exclude = "SH"` | 8001h (default) | COMMON1, M1CMN, M1SIM, SIM1, SIM2 | sorted by `vol_name_cmp`: M1SIM, M1CMN, COMMON1, SIM1, SIM2 |

COMMON1 (E001h) matches every mask. Classes: 2000h = common, 4000h = shell, 8000h = sim.
Duplicates inside one program's set (checked over all entries): INTRO/PS `STATTXT0.DAT` (M1SHL,
SHELL1), AP `PANEL4.BMP` (M1SIM, SIM1) — **byte-identical**, so lookup order never changes content.
At most 10 volumes (`vol_count < 10` in the scan).

#### 6.1.5 Pseudocode

```c
char *vol_ext_subdir_path(char *name) {          /* 049d:0008 */
    char *dot = strchr(name, '.');
    if (!dot) return NULL;
    strcpy(vol_subdir_buf, dot + 1);              /* "DAT"            */
    strcat(vol_subdir_buf, "\\");                 /* DS:07AC          */
    strcat(vol_subdir_buf, name);                 /* "DAT\INTRO1.DAT" */
    return vol_subdir_buf;
}

VFILE *my_fopen(char *name, char *mode) {         /* 049d:00bb */
    if (vol_log) fprintf(vol_log, "my_fopen(\"%s\",\"%s\")", name, mode);
    if (vol_count == 0) {                         /* volume layer off: plain files */
        f = fopen(strcat(strcpy(tmp, data_prefix), name), mode);
        return f ? f : fopen(name, mode);         /* (returns a real FILE*) */
    }
    if (vol_reopen_flag) vol_select(-1);
    rec = first vol_files[i] with in_use == 0;    /* 10 records (AP: 3) */
    if (!rec) { result = NULL; goto log; }
    vol_in_open = 1;
    /* 1. loose file overrides the volumes, for every mode */
    fp = fopen(data_prefix + name, mode);
    if (!fp) fp = fopen(name, mode);
    vol_crit_error = 0; vol_in_open = 0;          /* do{}while(vol_crit_error) never repeats */
    if (fp) { rec->in_use = 1; rec->fp = fp; vol_open_files++;
              if (vol_log) fputs("[not in volume]", vol_log); result = rec; goto log; }
    /* 2. volumes: vol_cur, vol_cur+1 .. count-1, then vol_cur-1 .. 0 */
    cur = up = down = vol_cur;
    do {
        found = vol_find_entry(name, rec, cur);    /* fills rec->vol, rec->data_off=4*Σdelta */
        if (found) {
            vol_select(rec->vol);
            vol_seek(rec->data_off + rec->pos);   /* pos = 0 */
            FILE *v = vol_table[vol_cur].fp;
            fread(stored_name, 13, 1, v);
            fread(&rec->size, 4, 1, v);
            rec->data_off = vol_table[vol_cur].filepos = ftell(v);
            if (stricmp(stored_name, vol_basename(name)) != 0) found = 0;
        }
        if (!found) { if (up < vol_count-1) cur = ++up; else cur = --down; }
    } while (!found && down >= 0);
    if (found) { rec->pos = 0; rec->fp = NULL; rec->in_use = 1; vol_open_files++; result = rec; }
    else {
        /* 3. "<ext>\<name>" loose file (retried while INT 24h flags an error) */
        result = NULL;
        vol_last_subdir = vol_ext_subdir_path(name);
        if (vol_last_subdir) {
            vol_in_open = 1;
            do { vol_crit_error = 0; fp = fopen(vol_last_subdir, mode); } while (vol_crit_error);
            vol_in_open = 0;
            if (fp) { rec->in_use = 1; rec->fp = fp; vol_open_files++; result = rec;
                      if (vol_log) { fputs("=fail\n", vol_log);
                          fprintf(vol_log, "-- add to volume -- my_fopen(\"%s\",\"%s\")", vol_last_subdir, mode); } }
        }
    }
log:
    if (vol_log) { fprintf(vol_log, result ? "=ok\n" : "=fail\n"); fflush(vol_log); }
    /* AP prints "=ok   %p\n" with the handle */
    return result;
}
```

Notes (verified): the name is looked up by **base name** only (`vol_find_entry` hashes
`vol_basename(name)`; the stored name is compared with `stricmp`), so `"C:\X\SHELL.SX"` finds
`SHELL.SX`. The mode is ignored for volume entries (read-only). The search starts at `vol_cur`
(the volume last selected); if `vol_select(-1)` ran (only after an INT 24h error) `vol_cur` is −1
and the first probe indexes `vol_table[-1]` (original bug, harmless in practice). After a
volume miss the stale values written into `rec` are left (rec stays free).

```c
int vol_find_entry(char *name, VREC *rec, int v) {        /* 049d:0e32 */
    char buf[14]; strncpy(buf, vol_basename(name), 13); strupr(buf); len = strlen(buf);
    u32 h = 0;
    for (i = 0; i < 13; i++) h = _lrotl(h, vol_table[v].keys[i % 4]) ^ (i32)(i8)buf[i % len];
    u16 key = (u16)(h % 0x1003F);                          /* LUMOD, unsigned */
    u32 *d = vol_table[v].dir; u32 acc = 0;
    for (i = 0; i < vol_table[v].count && (u16)d[i] != key; i++) acc += d[i] >> 16;
    acc += d[i] >> 16;                  /* d[count] read out of bounds when not found */
    if ((u16)d[i] != key) return 0;
    rec->vol = v; rec->data_off = acc * 4; rec->size = 0; rec->pos = 0;
    return 1;
}
```
First hash match only (no collisions exist inside a volume). When nothing matches, the word
after the directory is compared (out of bounds; a false hit would then fail the name compare).

```c
FILE *vol_select(int v) {                                 /* 049d:0fa3 */
    if (v == -1 || v != vol_cur || vol_open_files == 0 || vol_reopen_flag) {
        if (vol_cur != -1 && vol_table[vol_cur].fp) { fclose(vol_table[vol_cur].fp); vol_table[vol_cur].fp = 0; }
        if (v != -1) {
            vol_in_open = 1;
            _fstrncpy(nm, vol_table[v].name, 14);
            if (!(vol_table[v].fp = fopen(nm, "rb")))
                fatal_error("cannot open volume %s", nm);   /* AP: assert_fail(volume.c line 3E1h) */
            vol_in_open = 0;
            vol_table[v].filepos = 0;
        }
        vol_cur = v; vol_rec_of(NULL); vol_reopen_flag = 0;
        if (vol_cur == -1) return NULL;
    }
    return vol_table[vol_cur].fp;
}
void vol_seek(u32 pos) {                                   /* 049d:10c1 */
    if (vol_cur != -1 && vol_table[vol_cur].filepos != pos) {
        fseek(vol_table[vol_cur].fp, pos, SEEK_SET); vol_table[vol_cur].filepos = pos; }
}
VREC *vol_rec_of(void *h) {                                /* 049d:1128 */
    if (!h) { cache_handle = cache_rec = 0; return 0; }
    if (!vol_count) return 0;
    if (h == cache_handle) return cache_rec;
    search vol_files[0..9] (AP 0..2) for &vol_files[i] == h;
    if (found && in_use) { cache_handle = h; cache_rec = h; return h; }
    cache_handle = cache_rec = 0; return 0;
}
```
Only one volume FILE is open at a time; switching volumes closes/reopens (`fopen("rb")`). With
no records in use every `vol_select` reopens the file.

Operations on a handle `f` (pattern shared by all): if `vol_count && (r = vol_rec_of(f))`: if
`r->fp` use the loose FILE `r->fp`, else operate on the volume entry; if the handle is not a
record, it is treated as a real `FILE*`.

```c
int my_fread(void *buf, int size, int n, VFILE *f) {        /* 049d:0411 */
    entry case:
    vfp = vol_select(r->vol); vol_seek(r->data_off + r->pos);
    for (u16 bytes = size*n; bytes && (r->size - r->pos) < bytes; bytes -= size) n--;   /* u32 compare */
    got = fread(buf, size, n, vfp);
    r->pos += got*size; vol_table[r->vol].filepos += got*size;   /* (u16 product) */
    return got;
}
long my_hread(void far *buf, long size, long n, VFILE *f)      /* 049d:04f4 */
    same with 32-bit bytes = size*n (LXMUL) and n decremented until size*n ≤ size−pos;
    got = file_hread(buf, size, n, vfp); pos/filepos += size*n (the clamped n, not got!)
long file_hread(void far *buf, long size, long n, FILE *fp)    /* 049d:0616 */
    fd = fp->fd; p = ftell(fp); if p == -1 return 0;
    if lseek(fd, p, 0) == -1 → fseek(fp,p,0), return 0;
    if __hread(fd, buf, size*n) != size*n → fseek(fp,p,0), return 0;   /* all or nothing */
    fseek(fp, tell(fd), 0); return n;
int my_fseek(VFILE *f, long off, int whence)                   /* 049d:06d1 */
    entry case (u32 arithmetic): whence 1: off += pos;
      whence 2: off = (off < size) ? size - off : 0;          /* NOTE: distance back from end */
      if (off > size) off = size;  pos = off; return 0;
long my_ftell(f)      = entry: pos           else ftell
long my_filelength(f) = entry: size          else ftell/fseek(end)/ftell/fseek(back)
void my_rewind(f)     = my_fseek(f, 0, 0)
int  my_fgetc(f)      = entry: pos >= size ? -1 : (vol_select, vol_seek(data_off+pos), c = fgetc(vfp), pos++, filepos++, c)
int  my_feof(f)       = entry: pos >= size ;  real FILE: fp->flags & 0x20
int  my_fwrite(...)   = entry: 0 (writing into volumes is impossible) ; else fwrite
int  my_fputc(c,f)    = entry: -1 ; else fputc
void my_setbuf(f,b)   = entry: nothing ; else setbuf
int  my_fclose(f)     = record: vol_rec_of(NULL); if r->fp fclose(r->fp) (return value); r->in_use = 0;
                        vol_open_files--; else fclose(f).  (AP logs "my_fclose( %p )\n")
```
The volume FILE itself stays open after `my_fclose` (closed only by `vol_select` switching or
`vol_shutdown`).

```c
void vol_open_index(char *vname, u16 mask) {                 /* 049d:0a2c */
    fp = fopen(vname, "rb"); if (!fp) return;
    fread(vol_hdr_buf, 0x16, 1, fp);
    if (strcmp(vol_hdr_buf, "Dynamix Volume File") != 0) goto close;   /* AP: assert_fail (line 2C1h) */
    fread(&flags, 2, 1, fp);
    if (!(flags & mask & 0xF000) || !(flags & mask & 0x0FFF)) goto close;
    fread(keys, 2, 4, fp); fread(&n, 2, 1, fp);
    if (n == 0) goto close;
    while (ftell(fp) % 4) fseek(fp, 1, SEEK_CUR);            /* 22h → 24h */
    dir = dos_alloc(n*4, 0, 1) or assert_fail(volume.c 2D1h);
    file_hread(dir, n*4, 1, fp) == 1 or assert_fail(2D2h);    /* AP: no check */
    v = &vol_table[vol_count]; _fstrncpy(v->name, vname, 14); v->index = vol_count;
    v->count = n; v->dir = dir; v->keys[0..3] = keys; vol_count++;
close: fclose(fp);
}
void vol_init(char *log, u16 a, u16 b) {                      /* 049d:0c4a */
    mask = default (INTRO 2001h, PS/AP 8001h);
    if (vol_inited) return;
    if (a || b) mask = a | b;
    if (log) vol_set_log(log);
    vol_old_int24 = getvect(0x24); setvect(0x24, vol_int24);
    r = findfirst("*.DYN", &ff, 0);
    if (r == 0 && !vol_table) vol_table = dos_alloc(0x17C) or assert_fail(305h);
    INTRO/PS: while (r == 0 && vol_count < 10) { vol_open_index(ff.name, mask); r = findnext(&ff); }
    AP: collect up to 10 names (uppercased) not containing strupr(vol_exclude) (strstr),
        qsort(names, n, 13, vol_name_cmp), then vol_open_index(name, mask) for each in order;
    if (vol_count) vol_active = 1;
    vol_inited = 1;
}
int vol_name_cmp(char *a, char *b)                           /* AP 0000:0fde */
    { if (a[0]=='M' && b[0]=='M') return -strcmp(a,b); if (a[0]=='M') return -1;
      if (b[0]=='M') return 1; return strcmp(a,b); }
void vol_shutdown(void)                                      /* 049d:0d50 */
    if (vol_log) { fclose(vol_log); vol_log = 0; }   /* AP: fclose without clearing */
    if (!vol_inited) return;
    if (vol_table) { for each volume: if dir dos_free(dir), dir = 0; dos_free(vol_table); }
    vol_table = 0; vol_count = 0;
    if (vol_old_int24) { setvect(0x24, vol_old_int24); vol_old_int24 = 0; }
    vol_inited = 0;
    /* the open volume FILE is not closed here (program exit closes it) */
```
Callers of `vol_shutdown`: INTRO 05bb:000b (exit path), PS 227c:004d, AP 4e0d:0bb0 `sim_exit`.

`vol_int24` (049d:11ab, `interrupt` function, DS reloaded with DGROUP): sets the returned AX
(stack slot of the pushed AX) to **3 (fail)** if `vol_in_open`, else **1 (retry)**; sets
`vol_crit_error = 1` and `vol_reopen_flag = 1`; `iret`. So a DOS critical error (e.g. CD not
ready) during a layer `fopen` fails that open; elsewhere DOS retries forever.

#### 6.1.6 The loose-file prefix and writes

`data_prefix` is built by each main (INTRO 038e:0ac1, PS main, AP 50c8:0008): empty, then
`strcpy(data_prefix, argv[i]+2)` for every argument starting `-n`; then `"\\"` is appended if the
last character is not `\`, and if the string then ends in `\\` (two backslashes) one is removed.
The shipped launcher runs `gcd -nC:\DYNAMIX\AOTP` (AOTPCD.BAT), so the prefix is the install
directory. Without `-n` the prefix is `"\"` (root of the current drive) — an original quirk.

Writes never go into volumes: `my_fwrite` returns 0 for entries. Two write paths exist:
* plain Borland `fopen(data_prefix + name, "wb"/"w")`, e.g. INTRO 038e:0687 `control.prf` "wb",
  PS 1193:0ad2 `resource.cfg` "w";
* `my_fopen(name, "wb")` + `my_fwrite`: INTRO 038e:0704 reads `INTRO<n>.DAT` (n = 1..7, name
  built by `make_name_n` 038e:0121 from "INTRO"/n/"DAT") with "rb", then reopens `INTRO<n>.DAT` with "wb" and
  writes one byte. Because `my_fopen` tries `fopen(data_prefix+name, mode)` first, "wb" creates or
  truncates the **loose** file (falling back to the current directory) and returns a loose record.
Reads go through `my_fopen`, which tries `data_prefix+name`, then `name`, **before** the
volumes, so a loose file always overrides a volume entry of the same name. `INTRO1.DAT` exists
both loose (Game dir) and in M1SHL; the loose copy wins. None of CONTROL.PRF, SIM.IN,
RESOURCE.CFG, *.PRF is in any volume.

#### 6.1.7 Error handling summary

* Volume file missing at `vol_select`: INTRO/PS `fatal_error("cannot open volume %s")`
  (05bb:0052 / PS 227c:00f8), AP `assert_fail` (2494:0127, volume.c line 3E1h).
* Bad signature: INTRO/PS skip the file silently; AP asserts (line 2C1h).
* Directory alloc/read failure: `assert_fail` (INTRO lines 2D1h/2D2h; AP no read check).
* `my_fopen` failure: returns NULL (no message) — callers decide.
* More than 10 (AP: 3) simultaneously open layer files: `my_fopen` returns NULL.
* DOS critical errors: see `vol_int24`.

### 6.2 RESOURCE.CFG line table (INTRO seg 05CB only)

PS and AP have no counterpart (the string "Too many lines in resource file" exists only in
INTRO.EXE). Its only caller is INTRO `config_read` 038e:0284, which itself has **no callers**
(dead code). PS writes `resource.cfg` (1193:0ad2, plain `fopen(data_prefix+"resource.cfg","w")`,
shell module) but no program reads it through this table.

| INTRO | PS | AP | name | signature | purpose | conf. |
|---|---|---|---|---|---|---|
| 05cb:000e | – | – | `rcfg_clear` | `void (void)` | `rcfg_lines[0..49] = NULL` | verified |
| 05cb:0027 | – | – | `rcfg_load` | `void (FILE *fp)` | read up to 50 lines | verified |
| 05cb:00a6 | – | – | `rcfg_find` | `char *(char *key)` | first line containing `key` | verified |
| 05cb:00dc | – | – | `rcfg_free` | `void (void)` | free all lines | verified |

Globals: `rcfg_count` INTRO DS:25E4 (int), `rcfg_lines` DS:25E6 (char*[50], up to DS:264A).

```c
void rcfg_load(FILE *fp) {
    char line[60]; rcfg_clear();
    for (rcfg_count = 0; rcfg_count < 50; rcfg_count++) {
        if (!fgets(line, 50, fp)) break;                          /* keeps the '\n' */
        rcfg_lines[rcfg_count] = strcpy(malloc(strlen(line) + 1), line);   /* malloc unchecked */
    }
    if (rcfg_count == 50) fprintf(stderr /*DS:20DC*/, "Too many lines in resource file\n");
}
char *rcfg_find(char *key) { for (i = 0; i < rcfg_count; i++) if (strstr(rcfg_lines[i], key)) return rcfg_lines[i]; return NULL; }
void  rcfg_free(void)      { for (i = 0; i < rcfg_count; i++) free(rcfg_lines[i]); }   /* count not reset */
```
Quirks: a file of exactly 50 lines also prints the warning; lines longer than 49 characters are
split by `fgets` into several table lines.

### 6.3 Chunk access (system library)

A "chunk file" is a `my_fopen`ed volume entry or loose file holding a tagged chunk tree
(`resources.md` §2). At most **4** chunk files can be open at once; their state lives in a static
table.

| INTRO | PS | AP | name | signature | purpose | conf. |
|---|---|---|---|---|---|---|
| 05da:5764 (near) | 16e3:54be | 7187:0000 | `chunk_slot` | `CHF *(VFILE *h)` | slot whose handle == h (h = 0: a free slot), searched 3..0 | verified |
| 05da:5795 (near) | 16e3:54ef | 7187:0031 | `chunk_reset` | `void (CHF *s)` | zero the slot except handle and `end[0]`; `my_rewind(h)` | verified |
| 05da:57e2 (near) | 16e3:553c | 7187:007e | `chunk_path_eq` | `int (char *a, char *b, int n)` | `while ((*a||*b) && n--) if (*a++ != *b++) return 0; return 1;` | verified |
| 05da:581a | 16e3:5574 | 7187:00b6 | `chunk_save` | `CHF *(CHF *dst, VFILE *h)` | copy the 43h-byte state out (0 if dst/h null or not open) | verified |
| 05da:5856 | 16e3:55b0 | 7187:00f3 | `chunk_restore` | `int (CHF *src)` | copy state back into h's slot, `my_fseek(h, pos, 0)`; 1 / 0 | verified |
| 05da:589e | 16e3:55f8 | 7187:013c | `chunk_open` | `VFILE *(char *name)` | `my_fopen(name,"rb")` + init slot | verified |
| 05da:5902 (near) | 16e3:565c | 7187:01a2 | `chunk_fail` | `long (CHF *s)` | restore the backup state, reseek, return −1 | verified |
| 05da:5934 | 16e3:568e | 7187:01d4 | `chunk_find` | `long (VFILE *h, char *path, int n)` | find chunk by tag path → payload file offset, or −1 | verified |
| 05da:5c21 | 16e3:597b | 7187:04cc | `chunk_size` | `long (VFILE *h)` | payload size of the current chunk (−1 if h is not a chunk file) | verified |
| 05da:5c4b | 16e3:59a5 | 7187:04f7 | `chunk_close` | `int (VFILE *h)` | `slot.h = 0; my_fclose(h); return 1` (0 if not a chunk file) | verified |
| 05da:5c7a | 16e3:59d4 | 7187:0527 | `chunk_is_open` | `int (VFILE *h)` | `chunk_slot(h) != 0` | verified |

AP moved this group into its own segment 7187 (all far).

Globals: `chunk_slots` INTRO DS:2FD8 / PS DS:72BC / AP DS:6F86 (CHF[4], 4 × 43h);
`chunk_backup` DS:30E4 / DS:73C8 / DS:7092 (one CHF); `"rb"` DS:1934 / DS:3170 / DS:3516.

`CHF` (43h bytes, packed):

| off | type | field |
|---|---|---|
| 00 | VFILE* | handle (0 = free slot) |
| 02 | char[25] | current tag path (`"BMP:INF:"` …), NUL-terminated, 4 chars per level |
| 1B | u32[7] | `end[level]` = file offset just past the chunk at that level, **bit 31 = container flag** of that chunk; `end[0]` = file length \| 80000000h (the root is a container) |
| 37 | int | path length in bytes (4 × depth) |
| 39 | int | occurrence number of the last successful `chunk_find` of this path |
| 3B | u32 | current position; after a header is read = payload start of the current chunk |
| 3F | u32 | payload size of the current chunk (bit 31 cleared) |

```c
VFILE *chunk_open(char *name) {                           /* 05da:589e */
    s = chunk_slot(0); if (!s) return 0;
    s->h = my_fopen(name, "rb"); if (!s->h) return 0;
    my_fseek(s->h, 0, SEEK_END);                          /* volume entry: pos = size */
    s->end[0] = my_ftell(s->h) | 0x80000000;
    chunk_reset(s);                                       /* path "", len 0, count 0, pos 0, size 0; rewind */
    return s->h;
}

long chunk_find(VFILE *h, char *path, int n) {             /* 05da:5934 */
    if (!h || !(s = chunk_slot(h))) return -1;
    plen = strlen(path); if (plen == 0 || (plen & 3)) return -1;
    chunk_backup = *s;
    if (chunk_path_eq(path, s->path, 25)) {               /* same path as the current chunk */
        if (n == 0 && my_ftell(h) == s->pos) return s->pos;    /* nothing read since: same chunk */
        if (n == -1) { my_fseek(h, s->pos, 0); return s->pos; } /* back to its payload start */
        if (s->count == 0) { want = n; if (n) chunk_reset(s); else n = 1; }
        else if (n == 0)   { want = s->count + 1; n = 1; }       /* next occurrence */
        else { want = n;
               if (s->count < n) n -= s->count;                 /* continue forward */
               else if (s->count > n) chunk_reset(s);           /* restart from the file start */
               else { my_fseek(h, s->pos, 0); return s->pos; } }
    } else if (n > 0) { chunk_reset(s); want = n; }
    else              { want = 0; n = 1; }                    /* next match from the current position */

    if (!(s->end[s->len/4] & 0x80000000)) s->pos += s->size; /* current chunk is a leaf: skip its payload */
    my_fseek(h, s->pos, 0);
    while (n-- != 0) {                                    /* n matches needed */
        do {
            for (;;) {
                while ((s->end[s->len/4] & 0x7FFFFFFF) == s->pos) {  /* at the end of this level */
                    if (s->len == 0) return chunk_fail(s);          /* end of file: not found */
                    s->len -= 4;
                }
                if (s->end[s->len/4] & 0x80000000) break;           /* inside a container: read a child */
                s->pos += s->size; my_fseek(h, s->pos, 0);           /* skip a leaf */
            }
            if (my_fread(s->path + s->len, 1, 4, h) != 4) return chunk_fail(s);
            s->len += 4; if (s->len >= 0x18) return chunk_fail(s);  /* depth ≤ 5 */
            s->path[s->len] = 0; s->pos += 8;
            if (my_fread(&s->size, 4, 1, h) != 1) return chunk_fail(s);
            s->end[s->len/4] = s->pos + s->size;                    /* bit 31 of size = container */
            s->size &= 0x7FFFFFFF;
            if (s->size >= (s->end[0] & 0x7FFFFFFF)) return chunk_fail(s);
        } while (!(s->len == plen && chunk_path_eq(s->path, path, plen)));
    }
    s->count = want;
    return s->pos;                                        /* payload start; file pointer is there */
}
long chunk_fail(CHF *s) { *s = chunk_backup; my_fseek(s->h, s->pos, 0); return -1; }
```
Only exact full paths match (`"BMP:VGA:"`, not `"VGA:"`), depth-first in file order. After a
successful find the caller reads `chunk_size(h)` bytes with `my_fread`/`my_hread`, or opens a
packed stream at that position (§6.4). `chunk_size` returns the 31-bit payload size of the current
chunk (after a failed find: of the previous current chunk, restored from the backup).
`chunk_save`/`chunk_restore` let a caller remember a position (e.g. the bitmap loader 0ead:0002
saves before looking for alternative chunks).

### 6.4 Packed streams: the decompressor (system library)

A stream layer over a `VFILE` (file mode) or a far memory buffer (memory mode) with three
methods in a descriptor table. The programs use only the **read** side; the writer (stored,
RLE and a `compress`-4.0 LZW encoder) and the memory-mode open have no callers.

#### 6.4.1 Function table

(The candidates INTRO `0dc5`/`0e2c` sometimes listed for "the decompressor" are the VQT picture
decoder, owned by video; the RLE/LZW code is this group.)

AP = INTRO − 3FA1h and PS = INTRO + 14Eh for the whole group (checked with the method tables
and `port/shared_matches.csv`; the two empty functions are 731d/7322 in INTRO).

| INTRO | PS | AP | name | signature | purpose | conf. |
|---|---|---|---|---|---|---|
| 05da:6b6c | 16e3:6cba | 1d32:2bcb | `pk_open` | `int (int method, VFILE *f, char *mode, u32 packed_size)` | open a packed stream at the current file position → id 0..99 / −1 | verified |
| 05da:6cb9 | 16e3:6e07 | 1d32:2d18 | `pk_open_mem` | `int (int method, void far *buf, char *mode, u32 size)` | same on memory (no callers) | verified |
| 05da:6f3d | 16e3:708b | 1d32:2f9c | `pk_read` | `u16 (int id, void far *dst, u16 n)` | decode up to n bytes → count (0xFFFF bad id) | verified |
| 05da:702d | 16e3:717b | 1d32:308c | `pk_size` | `long (int id)` | unpacked size from the header (−1 bad id) | verified |
| 05da:7050 | 16e3:719e | 1d32:30af | `pk_seek` | `u16 (int id, long off, int whence)` | seek in the unpacked data (decode and discard) | verified |
| 05da:71a3 | 16e3:72f1 | 1d32:3202 | `pk_rewind` | `int (int id)` | restart at the first packed byte | verified |
| 05da:6db5 | 16e3:6f03 | 1d32:2e14 | `pk_close` | `u16 (int id)` | (writer: flush + patch size) and free | verified |
| 05da:6f7a | 16e3:70c8 | 1d32:2fd9 | `pk_write` | `u16 (int id, void far *src, u16 n)` | compress (no callers) | likely |
| 05da:6926 (near) | 16e3:6a74 | 1d32:2985 | `pk_select` | `int (int id)` | load the stream into the working globals | verified |
| 05da:6a4f | 16e3:6b9d | 1d32:2aae | `pk_alloc_id` | `int (void)` | first free id, `calloc(1,21h)` | verified |
| 05da:6a9e | 16e3:6bec | 1d32:2afd | `pk_setup` | `int (int method, char *mode)` | method ≤ 2; ring; scratch | verified |
| 05da:69e5 | 16e3:6b33 | 1d32:2a44 | `pk_free` | `int (int id)` | free ring, own scratch, record; return −1 | verified |
| 05da:69af | 16e3:6afd | 1d32:2a0e | `pk_mode_is_read` | `int (char *mode)` | mode contains `'r'` | verified |
| 05da:69cf | 16e3:6b1d | 1d32:2a2e | `pk_nfree` | `void (void *p)` | `if (p) free(p)` | verified |
| 05da:6efa | 16e3:7048 | 1d32:2f59 | `pk_fill` | `u16 (int id, u16 n)` | ring → method read → ring; pos += delivered | verified |
| 05da:6e85 | 16e3:6fd3 | 1d32:2ee4 | `pk_from_ring` | `void (void)` | serve bytes from the 128-byte ring | verified |
| 05da:668b | 16e3:67d9 | 1d32:26ea | `pk_getbyte` | `int (void)` | next packed byte, −1 at the packed limit | verified |
| 05da:66e3 | 16e3:6831 | 1d32:2742 | `pk_getbytes` | `u16 (u8 *dst, u16 n)` | up to n packed bytes (limit-clamped) | verified |
| 05da:661f | 16e3:676d | 1d32:267e | `pk_copy_file` | `void (void far *dst, u16 n)` | `my_fread` in pieces of ≤ 50 bytes via `pk_litbuf` + far copy | verified |
| 05da:6887 | 16e3:69d5 | 1d32:28e6 | `pk_put1` | `int (u8 c)` | one output byte (to dest, or to the ring when the request is full) | verified |
| 05da:678a | 16e3:68d8 | 1d32:27e9 | `rle_literal` | `int (u16 n)` | RLE literal run, file source | verified |
| 05da:680d | 16e3:695b | 1d32:286c | `rle_fill` | `int (u8 v, u16 n)` | RLE fill run, file source | verified |
| 05da:6567 | 16e3:66b5 | 1d32:25c6 | `m0_read` | method read | stored (method 0) | verified |
| 05da:658b | 16e3:66d9 | 1d32:25ea | `rle_read` | method read | RLE (method 1) | verified |
| 05da:760d | 16e3:775b | 1d32:366c | `rle_read_mem` | near | RLE with a memory source | likely (same semantics, read loosely) |
| 05da:7253 | 16e3:73a1 | 1d32:32b2 | `lzw_read_init` | method read-init | LZW table/state reset | verified |
| 05da:7343 | 16e3:7491 | 1d32:33a2 | `lzw_read` | method read (asm; missing from the function lists) | LZW (method 2) decoder | verified |
| 05da:7546 | 16e3:7694 | 1d32:35a5 | `lzw_getcode` | near asm, code in AX | next code or −1 | verified |
| 05da:731d, 05da:7322 | 16e3:746b, 16e3:7470 | 1d32:337c, 1d32:3381 | – | `void (void)` | empty functions | verified |
| 05da:68d5 | 16e3:6a23 | 1d32:2934 | `pk_putbyte` | `int (u8 c)` | writer output byte | verified |
| 05da:65d9 | 16e3:6727 | 1d32:2638 | `m0_write` | writer | stored | likely |
| 05da:7c51 | 16e3:7d9f | 1d32:3cb0 | `rle_write` | writer | RLE encoder (runs ≥ 3) | likely |
| 05da:7700 | 16e3:784e | 1d32:375f | `lzw_write_init` | writer | encoder init (HSIZE 5003 = DS:1AAA) | likely |
| 05da:7775 | 16e3:78c3 | 1d32:37d4 | `lzw_write` | writer | encoder main loop (open hashing) | likely |
| 05da:7988 | 16e3:7ad6 | 1d32:39e7 | `lzw_output` | writer | emit a code, grow width | likely |
| 05da:7b2b | 16e3:7c79 | 1d32:3b8a | `lzw_cl_block` | writer | compression-ratio check, CLEAR (check gap 10000) | likely |
| 05da:7c03 | 16e3:7d51 | 1d32:3c62 | `lzw_cl_hash` | writer | fill the hash table with −1 | likely |
| 05da:7b15 | 16e3:7c63 | 1d32:3b74 | `pk_ldiv` | `long (long a, long b)` | `LDIV@` wrapper | verified |

#### 6.4.2 Method descriptor table

`pk_methods` INTRO DS:1A5C / PS DS:3428 / AP DS:256C, 3 entries × 0Eh (INTRO values):

| off | field | 0 stored | 1 RLE | 2 LZW |
|---|---|---|---|---|
| +0 | ring size (read mode; write mode always 80h) | 80h | 80h | 80h |
| +2 | scratch size, read | 0 | 0 | **3AB3h** |
| +4 | scratch size, write | 0 | 0 | 7566h |
| +6 | read fn | 6567 | 658B | **7343** |
| +8 | write fn | 65D9 | 7C51 | 7775 |
| +A | write-init fn | 0 | 0 | 7700 |
| +C | read-init fn | 0 | 0 | 7253 |

PS: 66B5/6727, 66D9/7D9F, 7491/78C3/784E/73A1; AP: 25C6/2638, 25EA/3CB0, 33A2/37D4/375F/32B2.
Method bytes > 2 make `pk_open` fail.

#### 6.4.3 Stream record (`calloc(1, 21h)`; `pk_streams[100]` INTRO DS:3174 / PS DS:7458 / AP DS:64D4)

| off | type | field |
|---|---|---|
| 00 | u8 near* | ring buffer (80h bytes, `calloc`) |
| 02 | void far* | scratch (LZW tables) |
| 06 | VFILE* / far ptr | file handle (file mode) or buffer (memory mode: +06 offset, +08 segment) |
| 0A | u32 | packed bytes consumed, starts at **5** (the header) |
| 0E | u32 | packed limit = the `packed_size` argument (= chunk size incl. the 5-byte header) |
| 12 | u32 | unpacked size (header bytes 1–4) |
| 16 | u32 | unpacked position (bytes delivered or skipped) |
| 1A | u8 | ring head (write index) |
| 1B | u8 | ring tail (read index) |
| 1C | u32 | file position of the method byte (`my_ftell` at open) |
| 20 | u8 | flags: bits 0–4 method, 20h file source, 40h opened for reading |

#### 6.4.4 Working globals

| name | INTRO | PS | AP | type | meaning |
|---|---|---|---|---|---|
| `pk_shared_scratch` | DS:1A58 | DS:3424 | DS:2568 | void far* | if non-NULL, used as every LZW stream's scratch (§6.4.6) |
| `pk_methods` | DS:1A5C | DS:3428 | DS:256C | struct[3] | §6.4.2 |
| `lzw_buf` | DS:1A90 | DS:345C | DS:25A0 | u8[12] | current code group |
| `lzw_rmask` | DS:1A9C | DS:3468 | DS:25AC | u8[9] | 00 01 03 07 0F 1F 3F 7F FF |
| `lzw_resume` | DS:1AA5 | DS:3471 | DS:25B5 | u16 | stack index to resume a partly output string |
| `rle_ringptr` | DS:1AA8 | DS:3474 | DS:25B8 | u16 | ring + head (memory RLE path) |
| `pk_litbuf` | DS:313C | DS:7420 | DS:649C | u8[50] | file-read bounce buffer |
| `pk_io` | DS:316E | DS:7452 | DS:64CE | u8 | 20h file source; 40h store output (clear = skip) |
| `pk_file` | DS:3170 | DS:7454 | DS:64D0 | VFILE* | file of the selected stream |
| `pk_method` | DS:3172 | DS:7456 | DS:64D2 | u8 | method of the selected stream |
| `pk_streams` | DS:3174 | DS:7458 | DS:64D4 | rec*[100] | stream table |
| `pk_flags` | DS:323C | DS:7520 | DS:659C | u8 | flags byte (+20h) of the selected stream |
| `pk_cur` | DS:323E | DS:7522 | DS:659E | rec* | selected stream |
| `pk_scratch` | DS:3240 | DS:7524 | DS:65A0 | void far* | its scratch |
| `pk_want` | DS:3244 | DS:7528 | DS:65A4 | u16 | bytes still wanted by the current request |
| `pk_ring` | DS:3246 | DS:752A | DS:65A6 | u8 near* | its ring |
| `pk_dest` | DS:3248 | DS:752C | DS:65A8 | u8 huge* | output pointer |
| `pk_src` | DS:324C | DS:7530 | DS:65AC | u8 huge* | memory-mode input pointer |
| `pk_count` | DS:3250 | DS:7534 | DS:65B0 | u16 | bytes written (writer) |
| `lzw_pending` | DS:3252 | DS:7536 | DS:65B2 | u8 | a decoded string is partly output |
| `lzw_clear` | DS:3254 | DS:7538 | DS:65B4 | u16 | CLEAR seen: reset the width at the next group read |
| `lzw_oldcode` | DS:3256 | DS:753A | DS:65B6 | u16 | previous code |
| `lzw_stackp` | DS:3258 | DS:753C | DS:65B8 | void far* | scratch + 3720h (set, not used by the decoder) |
| `lzw_finchar` | DS:325C | DS:7540 | DS:65BC | u16 | first char of the last string |
| `lzw_first` | DS:325E | DS:7542 | DS:65BE | u8 | next code is the first after init |
| `lzw_incode` | DS:3260 | DS:7544 | DS:65C0 | u16 | code being decoded |
| `lzw_offset` | DS:3262 | DS:7546 | DS:65C2 | u16 | bit offset in `lzw_buf` |
| `lzw_size` | DS:3264 | DS:7548 | DS:65C4 | u16 | usable bits in `lzw_buf` |
| `lzw_maxcode` | DS:3266 | DS:754A | DS:65C6 | u16 | (1 << n_bits) − 1; 1000h at 12 bits |
| `lzw_nbits` | DS:3268 | DS:754C | DS:65C8 | u16 | code width 9..12 |
| `lzw_free` | DS:326A | DS:754E | DS:65CA | u16 | next free code |
| encoder state | DS:326C–3285, 1AAA–1ABF | DS:7550–7569, 3476–348B | DS:65CC–65E5, 25BA–25CF | | writer only |

The LZW state is **global**, not per stream (and the dictionary may be in the shared scratch):
decoding two LZW streams interleaved would corrupt both. Every caller opens, reads and closes
one packed chunk at a time.

#### 6.4.5 Pseudocode (read side)

```c
int pk_open(int method, VFILE *f, char *mode, u32 packed_size) {   /* 05da:6b6c */
    id = pk_alloc_id(); if (id == -1) return -1;      /* 100 slots */
    r->file = f; r->start = my_ftell(f); r->consumed = 5;
    if (!pk_mode_is_read(mode)) {                     /* writer, unused */
        pk_setup(method, mode); my_fputc(method, f); my_fwrite(4 bytes, f); write_init(); }
    else {
        m = my_fgetc(f); r->flags = m;                /* the method argument is ignored */
        if (pk_setup(m, mode) == -1) { my_fseek(f, -1, SEEK_CUR); return pk_free(id); }
        r->limit = packed_size;
        my_fread(&r->unpacked, 1, 4, f);
        if (methods[m].read_init) methods[m].read_init();
        r->flags |= 0x40;
    }
    r->flags |= 0x20; return id;
}
int pk_setup(int m, char *mode) {                     /* 05da:6a9e */
    if (m > 2) return -1;
    r->ring = calloc(1, read ? methods[m].ring : 0x80); if (!r->ring) return -1;
    sz = read ? methods[m].scratch_r : methods[m].scratch_w;
    if (sz) { r->scratch = pk_scratch = pk_shared_scratch ? pk_shared_scratch : dos_alloc(sz, 0, 0);
              if (!r->scratch) return -1; }
    r->flags = m; return m;
}
int pk_free(int id) {                                 /* 05da:69e5 */
    pk_nfree(r->ring);
    if (r->scratch && !pk_shared_scratch) dos_free(r->scratch);
    pk_nfree(r); pk_streams[id] = 0; return -1;
}
int pk_select(int id) {                               /* 05da:6926 */
    if (id < 0 || id > 99 || !(r = pk_streams[id])) return 0;
    pk_cur = r; pk_scratch = r->scratch; pk_ring = r->ring;
    pk_flags = r->flags; pk_method = pk_flags & 0x1F;
    if (pk_flags & 0x20) { pk_file = r->file; pk_io = 0x20; }
    else { pk_io = 0; pk_src = normalize(r->buf + r->consumed); }
    return 1;
}
u16 pk_read(int id, void far *dst, u16 n) {           /* 05da:6f3d */
    if (!pk_select(id)) return 0xFFFF;
    pk_dest = normalize(dst); pk_io |= 0x40;
    return pk_fill(id, n);
}
u16 pk_fill(int id, u16 n) {                          /* 05da:6efa */
    pk_want = n;
    pk_from_ring();
    if (pk_want) { methods[pk_method].read(); if (pk_want) pk_from_ring(); }
    r->pos += n - pk_want; return n - pk_want;
}
void pk_from_ring(void) {                             /* 05da:6e85 */
    t = r->tail; avail = r->head - t;
    if (pk_want < avail) { k = pk_want; r->tail = t + k; } else { k = avail; r->head = r->tail = 0; }
    if (k) { if (pk_io & 0x40) far_memcpy(pk_dest, pk_ring + t, k); pk_want -= k; pk_dest += k; }
}
int pk_getbyte(void) {                                /* 05da:668b */
    if (r->consumed == r->limit) return -1;
    r->consumed++;
    return (pk_flags & 0x20) ? my_fgetc(pk_file) : *pk_src++;
}
u16 pk_getbytes(u8 *dst, u16 n) {                     /* 05da:66e3 */
    left = r->limit - r->consumed; if (left == 0) return 0;
    k = (left >= n) ? n : (u16)left;
    r->consumed += k;
    if (pk_flags & 0x20) return my_fread(dst, 1, k, pk_file);
    far_memcpy(dst, pk_src, k); pk_src += k; return k;
}
int pk_put1(u8 c) {                                   /* 05da:6887 */
    if (pk_want == 0) { pk_ring[r->head++] = c; return 0; }
    if (pk_io & 0x40) *pk_dest = c;
    pk_dest++; pk_want--; return 1;
}
```

**Method 0 (stored)** `m0_read`: `while ((c = pk_getbyte()) != -1 && pk_put1(c)) ;`

**Method 1 (RLE)** `rle_read` (memory source: `rle_read_mem`, same results):
```c
ok = 1;
while (ok && (c = pk_getbyte()) != -1) {
    if (!(c & 0x80)) ok = rle_literal(c & 0x7F);             /* copy the next c bytes */
    else             ok = rle_fill(pk_getbyte(), c & 0x7F);   /* next byte repeated c&7F times */
}
int rle_literal(u16 n) {                              /* 05da:678a */
    r->consumed += n;
    if (pk_want < n) { r->head += n; pk_copy_file(pk_ring /* base */, n); return 0; }
    if (pk_io & 0x40) pk_copy_file(pk_dest, n); else my_fseek(pk_file, n, SEEK_CUR);
    pk_want -= n; pk_dest += n; return 1;
}
int rle_fill(u8 v, u16 n) {                           /* 05da:680d */
    if (pk_want < n) { far_memset(pk_ring + r->head, v, n); r->head += n; return 0; }
    if (pk_io & 0x40) far_memset(pk_dest, v, n);
    pk_want -= n; pk_dest += n; return 1;
}
```
A run is never split between the caller's buffer and the ring: a run longer than the rest of
the request goes wholly into the ring (the ring is empty at that point; runs ≤ 127 < 128) and
`pk_fill`'s second `pk_from_ring` serves the part that fits. Count 0 is a no-op (a fill still
consumes its value byte). `rle_literal` does not check the packed limit for the run's bytes.
Decoding stops at the packed limit, never at the unpacked size.

**Method 2 (LZW)** = the Unix `compress` 4.0 decoder (block mode, 9..12 bits):
```c
/* scratch, paragraph aligned and addressed as offset 0 (segment arithmetic):
   prefix u16[4096] at +0000h, suffix u8[4096] at +2720h, decode stack at +3720h..+3AB3h (915 bytes) */
void lzw_read_init(void) {                            /* 05da:7253 */
    far_memset(scratch, 0, 0x3AA1);
    n_bits = 9; maxcode = 0x1FF;
    for (i = 255; i >= 0; i--) { prefix[i] = 0; suffix[i] = i; }
    free_ent = 0x101; clear_flg = 0; first = 1; pending = 0; offset = 0; size = 0;
    lzw_stackp = scratch + 0x3720;
}
int lzw_getcode(void) {                               /* 05da:7546 */
    if (free_ent > maxcode) {
        n_bits++; maxcode = (n_bits == 12) ? 0x1000 : (1 << n_bits) - 1;
        if (clear_flg) goto reset;
        goto fill;
    }
    if (clear_flg) { reset: n_bits = 9; maxcode = 0x1FF; clear_flg = 0; goto fill; }
    if (offset >= size) {
fill:   got = pk_getbytes(lzw_buf, n_bits);          /* one group = n_bits bytes = 8 codes */
        if (got <= 0) { size = got; return -1; }
        offset = 0; size = got * 8 - (n_bits - 1);
    }
    bp = lzw_buf + (offset >> 3); r_off = offset & 7; bits = n_bits; offset += n_bits;
    code = *bp++ >> r_off; bits -= 8 - r_off; r_off = 8 - r_off;
    if (bits >= 8) { code |= *bp++ << r_off; r_off += 8; bits -= 8; }
    code |= (*bp & rmask[bits]) << r_off;
    return code;
}
void lzw_read(void) {                                 /* 05da:7343 (pk_want > 0) */
    if (pending) { pending = 0; sp = lzw_resume; goto output; }   /* rest of the last string */
    if (first) { first = 0; oldcode = finchar = lzw_getcode(); pk_put1(finchar); }  /* no −1 check */
    for (;;) {
        code = lzw_getcode(); if (code < 0) return;
        if (code == 0x100) {                          /* CLEAR */
            prefix[0..255] = 0; clear_flg = 1; free_ent = 0x100;
            code = lzw_getcode(); if (code < 0) return;
        }
        incode = code; sp = 0;
        if (code >= free_ent) { stack[sp++] = finchar; code = oldcode; }    /* KwKwK */
        while (code >= 256) { stack[sp++] = suffix[code]; code = prefix[code]; }
        stack[sp++] = finchar = suffix[code];
output: while (sp > 0) {                              /* the string, first character first */
            c = stack[--sp];
            if (pk_want == 0) { pk_ring[r->head++] = c; lzw_resume = sp; pending = 1; return; }
            if (pk_io & 0x40) *pk_dest = c;
            pk_dest++; pk_want--;
        }
        if (free_ent < 0x1000) { prefix[free_ent] = oldcode; suffix[free_ent] = finchar; free_ent++; }
        oldcode = incode;
    }
}
```
Notes (verified): after a CLEAR `free_ent = 100h`, so the next string creates a dummy entry
100h (never referenced) and 101h is the first real code — identical in effect to `resources.md`.
The "8-code group" quirk of `resources.md` is exactly the `fill` rule: the group buffer is
refilled (its unread bits discarded) when the width grows, after a CLEAR, or when used up; a
short last group gives `size = got·8 − (n_bits−1)`. Dictionary full (`free_ent == 1000h`): no
more entries, width stays 12, no automatic reset. No end code: decoding ends at the packed limit
or when the caller stops asking. The decoder always runs one character ahead of the request (it
waits in the ring, the rest of the string on the stack).

Stack quirk: the decode stack holds only 3AB3h − 3720h = 915 bytes (+ ≤ 15 bytes alignment slack
in the shared buffer); a longer string would overwrite memory past the scratch. Shipped data
never gets near it (a string of length L needs about L²/2 input bytes).

```c
u16 pk_seek(int id, long off, int whence) {           /* 05da:7050 */
    if (!pk_select(id)) return 0xFFFF;
    base = (whence == 1) ? r->pos : (whence == 2) ? r->unpacked : 0;  t = base + off;
    if (t == r->pos) return (u16)t;
    if (t > r->pos) delta = min(t, r->unpacked) - r->pos;
    else { pk_rewind(id); if (t <= 0) return 0; delta = t; }
    for (;;) {                                        /* pk_io bit 40h is clear: decode and discard */
        k = (delta > 31999) ? 32000 : delta; delta -= pk_fill(id, k);
        if (delta == 0) break;
        /* memory mode: pk_src = normalize(r->buf + r->consumed) */
    }
    return (u16)r->pos;
}
int pk_rewind(int id) {                               /* 05da:71a3 */
    if (!pk_select(id) || !(pk_flags & 0x40)) return -1;
    if (methods[pk_method].read_init) methods[pk_method].read_init();
    r->consumed = 5;
    if (pk_flags & 0x20) my_fseek(pk_file, r->start + 5, SEEK_SET);
    else pk_src = normalize(r->buf + 5);
    r->pos = 0; r->head = r->tail = 0; return 0;
}
u16 pk_close(int id) {                                /* 05da:6db5 */
    if (!pk_select(id)) return 0xFFFF;
    pk_count = 0;
    if (!(pk_flags & 0x40)) {                         /* writer only */
        methods[pk_method].write(1);
        if (file) { my_fseek(f, r->start + 1, 0); my_fwrite(&r->unpacked, 4, 1, f); my_fseek(f, 0, SEEK_END); }
        else far_memcpy(r->buf + 1, &r->unpacked, 4);
    }
    pk_free(id); return pk_count;                     /* 0 for a reader */
}
```
`pk_seek` on a truncated stream never terminates (`pk_fill` returns 0, `delta` stays > 0) — an
original bug, only reachable with bad data; its only callers are in the sound code (15b5).

#### 6.4.6 The shared LZW scratch (DS:1A58)

The bitmap loader INTRO 05da:5001 (setting code PS 168a:0211, AP 7229:02a7) does
`malloc(3CC4h)`/`free` (a free-memory probe), then `malloc(3AC4h)` from the near heap, rounds
the address up to a paragraph and normalises it to offset 0 (05da:4836), stores it in
`pk_shared_scratch`, loads its packed chunks, then frees it and clears the pointer (05da:533a).
While set, `pk_setup` uses it instead of `dos_alloc(3AB3h)` and `pk_free` does not free it. So the
3AC4h buffer **is** the LZW dictionary + decode stack (3AB3h used, offset 0 required by the
asm decoder). All other readers (TTM 1125:002f, sound 15b5/172c, driver loaders 4933/4a8f/54ae)
get a fresh `dos_alloc(3AB3h)` per LZW stream, freed at `pk_close`.

### 6.5 Resource API as other modules see it

| call | semantics |
|---|---|
| `VFILE *my_fopen(name, mode)` | open by base name: loose file (`data_prefix+name`, then `name`) → volumes → `<ext>\name`; NULL if absent. With volumes active the result is a pointer to a `VREC`, usable only with the `my_*` calls |
| `my_fread / my_hread / my_fgetc / my_fseek / my_ftell / my_filelength / my_feof / my_rewind / my_fclose` | stdio semantics restricted to the entry (`my_fseek` SEEK_END = size − off) |
| `my_fwrite / my_fputc / my_setbuf` | loose files only (0 / −1 / nothing on volume entries) |
| `VFILE *chunk_open(name)` | `my_fopen(name,"rb")` + chunk state (≤ 4 open) |
| `long chunk_find(h, "TAG:TAG:", n)` | n ≥ 1: n-th occurrence from the file start; 0: next occurrence (or the same chunk if nothing was read since); −1: seek back to the current chunk. Returns the payload offset and leaves the file there; −1 = not found (state and position unchanged) |
| `long chunk_size(h)` | payload size of the current chunk |
| `chunk_save / chunk_restore / chunk_close / chunk_is_open` | as above |
| `int pk_open(method, h, "r", chunk_size)` | after `chunk_find` on a packed chunk (`resources.md` §2): reads the 5-byte header; −1 on error |
| `long pk_size(id)` | unpacked size |
| `u16 pk_read(id, far *dst, u16 n)` | next n unpacked bytes (fewer at the end) |
| `pk_seek(id, off, whence)` / `pk_rewind(id)` | random access by re-decoding |
| `pk_close(id)` | free |

Typical sequence (TTM loader 1125:002f): `h = chunk_open(name)`; `chunk_find(h,"VER:",0)` +
`my_fread`; `chunk_find(h,"PAG:",0)` …; `chunk_find(h,"TT3:",0)`; `sz = chunk_size(h)`;
`id = pk_open(-1, h, "r", sz)`; `n = pk_size(id)`; `buf = dos_alloc(n)`; `pk_read(id, buf, n)`;
`pk_close(id)`; `chunk_close(h)`.

### 6.6 Port notes

* **Read the .DYN volumes at run time** with the exact algorithm of §6.1 (hash + directory walk +
  `stricmp` of the stored name, base-name lookup). Keep: the per-program volume selection by
  mask (INTRO/PS 4001h/4FFFh → COMMON1, M1CMN, M1SHL, SHELL1; AP 8001h minus "SH" → COMMON1,
  M1CMN, M1SIM, SIM1, SIM2); the search order (from the last used volume upward, then
  downward) — content-neutral because all in-set duplicates are byte-identical, so any order is
  acceptable; the AP "M first" sort can be kept for fidelity.
* **Loose files override volume entries** and must keep doing so: CONTROL.PRF, SIMPREFS.PRF,
  MREAL.PRF, RESOURCE.CFG, SIM.IN/SIM.OUT, ROSTER.DAT, SCRIPT.DAT, TOP*.DAT, INTRO1.DAT (the
  M1SHL copy of INTRO1.DAT is shadowed by the loose one, and "wb" through `my_fopen` rewrites
  the loose file). Map `data_prefix` to the port's data directory (the game directory) instead
  of `-n`; do **not** reproduce the "root of the current drive" default. The `<ext>\name`
  fallback (e.g. `DAT\X.DAT`) is a developer feature: keep it as a cheap extra probe or drop it.
* Replaceable: the INT 24h handler, `vol_select`'s one-open-volume policy (open all volumes once,
  or mmap/read them whole), the 10/3 open-record limits (keep a limit only if some code depends
  on NULL returns — none found), the debug log (`vol_log`, never enabled), `file_hread`'s DOS
  handle trick (plain `fread`). Case-insensitive name matching must stay (DOS names).
* `my_fseek(SEEK_END)` on entries means `size − off`, clamped: only `chunk_open` uses it (with
  0). Keep the clamping of reads/seeks to the entry.
* The chunk layer can be reimplemented directly on memory (load the entry, walk the tree); the
  observable behaviour to keep is `chunk_find`'s occurrence semantics (n = 0 "next", −1
  "again") and exact-path matching.
* The decompressor can be replaced by a whole-chunk decode (`tools/dynchunk.py` algorithm) for
  all callers that `pk_read` the full `pk_size` in one call; keep a streaming interface for
  `pk_seek`/partial reads if the sound code (15b5) needs them. Use a 4096-byte decode stack
  (the original 915-byte stack is a latent overflow). Per-stream LZW state is a harmless
  improvement. Stop at the packed limit and do not write past the unpacked size.
* The memory-mode open and the whole writer (compressor) are dead code: not needed.

### 6.7 Hand-offs and cross-references

* Program start-up (`data_prefix` from `-n`, `vol_init` calls, AP `vol_exclude = "SH"` at
  50c8:017f) is §2.4–§2.6; `vol_shutdown` callers INTRO 05bb:000b, PS 227c:004d, AP 4e0d:0bb0.
* The bitmap/screen/palette/font loaders built on this API (INTRO 0ead:0002, 05da:5001 which sets
  `pk_shared_scratch`, 0f35:000a, 05da:54ae, 05da:070b, 05da:4a8f) are §7; the video driver loader
  05da:4933 and `gfx_init` 05da:5c93 (driver files through `my_fopen`, LZW via `pk_*`) → video.
* Sound: resource loaders 15b5 (`pk_seek`, `pk_read`), 172c:000e, `snd_load_resource` 1659:000b →
  sound. `pk_seek` never terminates on a truncated stream (§6.4.5): the sound port should decode
  whole chunks.
* TTM loader 1125:002f (and PS/AP equivalents, AP 24fc) → video (TTM).
* `dos_alloc` / `dos_free`, `huge_norm_far`, `huge_memcpy`, `huge_memset`: §5.

### 6.8 Open questions

* INTRO/PS volume order is the DOS directory order of `findfirst("*.DYN")` (not sorted); on the
  CD this is the ISO directory order (alphabetical). Harmless (no conflicting duplicates).
* Why AP limits open layer files to 3 (vs 10) — just a smaller build constant; confirm no AP code
  holds more than 3 `my_fopen` handles at once (a 4th would get NULL).
* `rle_read_mem` (05da:760d) was read from the decompiler only (same observable results as the
  file path assumed; only used for memory-mode streams, which have no callers → moot).
