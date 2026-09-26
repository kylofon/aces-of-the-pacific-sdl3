# sim_flow — radio order menu: item builders (`1660:07bb/0bae/0c12/0c47`)

Extra part of `sim_flow.md` (ownership map: `1660` radio-command menu → sim_flow). Completes
`sim_flow_cockpit.md` §7, which lists the menu front end (`1660:0f5f/0f6e/0f85/110f/0685`,
`6e5a:*`) but left these four builders unrowed on the assumption that sim_world had them (it did
not; sim_world_ai.md §15 in turn assumed sim_flow had them). Verified against x86dis.

Notation: `P` = the player's plane (`DS:3B09`). Plane fields as in `sim_world.md` / `sim_world_ai.md`
§16: `+04` position (lvec), `+14` heading, `+19` model type, `+1B` flags, `+26` side (0 US, 1 Japan),
`+34` flight, `+4A` brain state id, `+DD` leader (0 = flight leader). `AC(p)` = aircraft `.DAT` of p =
`WORD[DS:55D2 + 2·BYTE[DS:54BC + p+19]]`, `SH(s)` = ship `.DAT` = `WORD[DS:55D0 + 2·BYTE[DS:555B +
s+19]]`.

## Globals

| DS | Type | Meaning |
|---|---|---|
| 5B6C | 8 × 12 bytes | **order target table**, parallel to the menu item array: entry `i` describes the target of item `i` for items 40h–42h (read by `1660:0685 order_text` and passed to `1660:01bc` by `order_send`) |
| 5BD0 | i16 | menu page / recipient (−2 top, −1 choose recipient, 0 wingman, 1 other section, 2 whole flight) |
| 5BCE | i16 | sub-menu flag ("Attack the.."/"Strike the.." chosen) |
| 18EC | 9 × i16 | ship-class table {1, 0, 7, 2, 3, 4, 8, 5, 6}: used by `ship_priority` (`1660:0787`) as `table[class]` and here as the *listing order* (classes `table[0]`, `table[1]`, … in turn) — same table, two meanings (quirk, keep) |
| 476E | i16 | number of places (`DS:4755`, 20h bytes each) |
| 4774 | i16 | number of ships (`DS:4759`, near ptr list) |

Order target record (12 bytes, at `DS:5B6C + 12·i`):

| Off | Type | Meaning |
|---|---|---|
| +00 | u8 | aircraft role (`AC+38`, 0..3) / ship class (`SH+6C`) / place kind (`place+1C`) |
| +01 | u8 | target kind: 0 aircraft group, 1 ship, 2 place (`ai_order_execute` uses `tgt[1]`: 0 → task kind `tgt[0]+1`, else `tgt[1]+4`) |
| +02 | i32 | −10000 (`0xFFFFD8F0`) for ships/places; not written for aircraft groups |
| +06 | i16 | bearing from P to the target minus `P+14` (ships/places only) |
| +08 | i16 | count (aircraft: number of spotted enemies of that role; ships/places: 1) — `aircraft_name` appends "s" when > 1 |
| +0A | ptr | the target object (ship / place); 0 for aircraft groups |

## Functions

### `1660:07bb targets_list(u16 *items, int n, int air)` → new n (far)

Appends target items to `items[n..]` and fills `DS:5B6C[n..]` in step. `code = air ? 41h : 42h`.

1. `fighter = (AC(P)+38 == 0)` (player flies a pure fighter).
2. `addon = 6a63:0000()` (add-on flag `DS:51EC`). `k = mates_of(P, DS:5BD0, m)` (`1660:0065`);
   `armed = 1` if any `m[i]` has `has_ordnance` (`0deb:1490`) or (`addon` and `rockets_left`
   (`0deb:1500`)).
3. **Aircraft** — only if `air || fighter`: `cnt[4] = 0`; `e = spotted_split(buf, P, 0)`
   (`583c:0b51`, enemies first); for each of the `e` enemies: `cnt[(i8)AC(q)+38]++`. For role
   `r = 0..3` with `cnt[r] != 0`: `items[n] = 40h`; record `{+0 = r, +1 = 0, +8 = cnt[r], +A = 0}`;
   `n++`. (No `n < 8` check here.)
4. **Places** — for each place `pl = DS:4755 + 20h·i`, `i < DS:476E`: if `(i8)pl+1C <= 7` and
   `465c:00ee((i8)pl+1D)` (side of the place's country) `!= (i8)P+26` and
   `ldist2(pl+4, P+4)` (`277a:3bfc`, u32) `< 49000`: `items[n] = code`; record `{+0 = pl+1C, +1 = 2,
   +A = pl, +6 = bearing_between(pl+4, P+4) (3629:0004) − P+14, +2 = −10000, +8 = 1}`; `n++`.
   (No `n < 8` check.)
5. **Ships** — collect candidates `c[]` (stack array of 12): ships `s = DS:4759[i]`, `i < DS:4774`,
   with `(s+1B & 2) == 0` (not sunk), (`armed` or `SH(s)+6D != 0`), `(i8)s+26 != (i8)P+26` and
   `ldist2(s+4, P+4) < 49000`. Then for `j = 0..8`: for each candidate `s` in collection order with
   `(i8)SH(s)+6C == DS:18EC[j]`: **if `n >= 8` return n**; `items[n] = code`; record `{+1 = 1,
   +0 = (u8)DS:18EC[j], +A = s, +6 = bearing_between(s+4, P+4) − P+14, +2 = −10000, +8 = 1}`; `n++`.
6. Return `n`.

Quirk: the aircraft and place loops can overflow the 8-entry target table (and the menu's item
buffer) if many roles/places qualify; only the ship loop checks `n >= 8`. Keep the checks as they
are, but size the port's buffers for the worst case (4 + places + 8).

### `1660:0bae targets_exist(int bombers)` → bool (far)

`return targets_list(tmp[20], 0, bombers == 0) > 0` — writes into a stack buffer but **also
overwrites `DS:5B6C[0..]`** (harmless: the menu rebuild runs `targets_list` again).

### `1660:0c12 add_attack_item(u16 *items, int n, int bombers)` → n (far)

`if (targets_exist(bombers)) items[n++] = bombers ? 32h ("Strike the..") : 31h ("Attack the..")`;
return n.

### `1660:0c47 orders_list(u16 *items, int max, Plane **near, int k)` → n (far)

`near[0..k)` = the flight members ≠ P within 80000 (built by `orders_items`, `1660:110f`). `max` is
unused.

```
shotai  = (P+34→+06 == 3 && P+34→+42 == 1)      // Japanese 3-plane flight
p_lead  = (P+DD == 0)
side    = (i8)P+26
lead_near = 0; all_cover = 1; led = 0
for m in near: if m+DD == 0: lead_near = 1
               else if m+DD == P: led++; if m+4A != 1809h (state "cover the leader"): all_cover = 0
bomb = mates_have_bombers(P, DS:5BD0, &torp)      // 1660:0706
if !lead_near: DS:5BD0 = (k < 2) ? 0 : 2
is_leader = plane_in_formation(P)                // 583c:1a7c (flight leader)
n = 0
if DS:5BCE:                       n = targets_list(items, 0, bomb == 0)
elif !is_leader || (!bomb && shotai) || DS:5BD0 == 0:
    DS:5BD0 = 0
    if !bomb:
        if side == 0: items[n++] = 33h                     // "Cover me" (US only)
        if P+DD == 0:
            if led:
                if !shotai: items[n++] = 36h; items[n++] = 37h   // break left/right
                else:        items[n++] = 38h                    // split
                items[n++] = (all_cover ? 39h : 3Bh) + shotai
                items[n++] = 3Dh                                  // resume
        else: items[n++] = 34h + shotai                           // check six
        if is_leader: n = add_attack_item(items, n, 0)
        if p_lead && !lead_near: items[n++] = 50h                 // hold formation
    elif is_leader: n = targets_list(items, 0, 0)
elif DS:5BD0 < 0:
    DS:5BD0 = -1
    if led: items[n++] = 2Eh; if lead_near: items[n++] = 2Fh
    if targets_exist(bomb): items[n++] = 30h
elif DS:5BD0 == 1:
    n = targets_list(items, 0, bomb == 0)
    f = P+34
    if torp && f+02 == 3 && f+43 == 2:             // escort/cover mode "object f+10"
        t = f+10
        if within_50000(t, P) (1142:0b73):
            if !(t+1E & 40h): items[n++] = 43h     // attack from the right
            if !(t+1E & 80h): items[n++] = 44h     // attack from the left
elif DS:5BD0 == 2:
    n = targets_list(items, 0, bomb == 0)
    if !bomb: items[n++] = 50h
return n
```

Item codes are STR group 7 ids (text by `order_text`); their execution is `ai_order_execute`
(`1660:01bc`, sim_world_ai.md §15.1). Note the 30h entry uses `targets_exist(bomb)` (inverse sense
of the other calls, which pass `bomb == 0`) — faithful quirk.

## Hand-offs

* sim_world: `ship_priority` (`1660:0787`) and this file share `DS:18EC`; it is a word table (x86dis
  `mov ax,[bx+18ECh]` after `shl bx,1`) — sim_world_ai.md §15 writes it without the element size.
