# sim_flow — extra: named-id list `5b71` (dead code)

Segment `5b71` (3 functions, no source tag). The loader `5b71:0118` has **no callers** and no
stored far pointer, so the whole segment is unreachable in AP 1.2; specced for completeness
(render3d_world.md calls it "the VCR loader"; nothing ties it to the VCR code). Verified against
x86dis.

Node (25 bytes, from `arena_alloc(19h)` `24d3:0059` or the free list `DS:4DE4`):

| Off | Type | Meaning |
|---|---|---|
| +00 | near ptr | next |
| +02 | i16 | id |
| +04 | char[20] + NUL | name (`_fstrncpy(+4, name, 21)`, `+18 = 0`) |

The list head passed in is itself a node (a sentinel whose own name/id is tested by `find` but
skipped when computing the next free id).

| AP | Name | Behaviour |
|---|---|---|
| 5b71:00cd | `namelist_find(int id, char *name, Node *head)` → Node* | for `n = head; n; n = n->next`: `id && n->id == id` → n; `name && _fstrcmp(n+4, name) == 0` (`0000:4bba`) → n. None → 0 |
| 5b71:0000 | `namelist_add(int id, char *name, Node *head)` → id | `f = namelist_find(0, name, head)`. `f && id` → `f->id = id`, return id. `f` → `id = f->id`. If `id == 0`: `id = 1 + max(id of every node after head)` (at least 1; **quirk**: with `head->next == 0` the walk reads `DS:0000`/`DS:0002` as a node — harmless in the original, avoid in the port). `f` → `f->id = id`, return id. Else take a node from `DS:4DE4` (pop) or `arena_alloc(25)`, `id`, `next = 0`, copy the name (≤ 20 chars), append at the list end; return id |
| 5b71:0118 | `namelist_load(VFILE *f, char *path, Node *head)` → count | any argument 0 → 0. `was_open = chunk_is_open(f)` (`7187:0527`); not open → `f = chunk_open(f)` (`7187:013c`, the argument is then a file name); null → 0. `chunk_find(f, path, 0)` (next), −1 → `chunk_find(f, path, −1)` (again), −1 → 0 (the file stays open — leak quirk). `n = read_u16(f)` (`51ca:0000`); `n` times: `id = read_u16(f)`, `s = read_str(f)` (`51ca:008d`, static `DS:4192`); `s` → `namelist_add(id, s, head)`. `!was_open` → `chunk_close(f)` (`7187:04f7`). Return n |

`DS:4DE4` = free-node list head (only popped here; no other function in AP touches it, so it is always 0 and every node comes from `arena_alloc`).

Port: not needed (unreachable).
