# shell_data — mission-type modules `miss\s_*.c` (PS `3570`–`37fc`)

Part of `shell_data.md` (read §1 RNG, §6 structures, §7 helpers there first). All read from the
disassembly (**verified**) unless marked; the Ghidra output for these functions loses arguments and shows
immediates as DS symbols (`&DS_4A38` = 19000).

Notation: `B` = player home position, `T` = target position, `EB` = enemy base; positions are 12 bytes
(s32 x, s32 z, s32 alt). `hdg(a,b)` = `2b1f:00b4(a,b)` (16-bit angle from a to b, `-4000h` applied inside);
flights store `hdg >> 8` (sar) in +05. `move(p, ang, d, out)` = `2b1f:0121` (out.x = p.x + f(−sin…)·d,
out.z = p.z + …; alt untouched — emd2). `mid(a,b)` = `3d50:16b0` (floor((a+b)/2) per coordinate, result in a
static buffer `DS:3889`, so it must be copied before the next call). `dist` = `2b1f:021d` (long).
`alt(c)` = `DS:652E + c*8` (min, max) band of TABLES; `ralt(r)` = `DS:651E[r]` (role altitude).
`class(t)` = `2777:02f8(t)`, `cruise(t)` = `2777:0486(t)` (long altitude), `range(t)` = `2777:03e2(t)`,
`reserve(t)` = `2777:0434(t)`. `wp(f)[i]` = waypoint i of flight f. "alt := x" sets the +8 dword of a waypoint.

Common prologue of types 1–4, 6–9 (`mode` = the `kind` argument): `mission_reset`, header kind, type,
`mission_setup(service)` (RNG: reseed, see §7.2), loads `2968:0075` (wldfgen), `28e4:019f` (missinfo),
`280a:00af` (flight.dat) — order 2968/28e4/280a for types 2,3,4,6,7,8,9; 28e4/280a/2968 for type 1 (after
setup). Common epilogue: for kind 0 `2777:04fa(service, a, side, 0)` calls (aircraft availability marks, emd2)
with the listed `a`, then `280a:0431`, `28e4:0820`, `2968:0446` (order per type below).

## Type 0 — `3570:0003` ace duel (MT_DACE) — args (ace, kind)

No `mission_setup`: **no reseed, RSEED stays 0**; runs on the current stream. Loads 28e4:019f, 280a:00af first,
then reset.
```
date = 2550:0200(ace); kind; mtype 0; 6277 = date; 62DB = FFFF; counts side0 = side1 = 1
636B = FFFF; 6363 (ace[0] of side 1) = ace; 635F (skill) = FF; 6355 = 2550:01b2(ace) (ace's service)
62DF = 1 (player alone); 62DD = 2550:024e(ace)   /* player's type */
if 2550:0338(ace,date) == 0:  sq = 2550:03aa(ace,date); st = 2624:0256(sq,date); 626D = 2a85:0127(st)
      62C5 = enemy_service(6355); pick_base(1, st, -1, 67DE); 636F = 1; 636D = 2624:0219(sq,date)
elif == 1:                   st = 2550:0426(ace,date); 626D = area(st); 62C5 = enemy_service(6355)
      pick_base(1, st, -1, 67DE); 636F = 1; 636D = 2550:04d9(ace,date)
(else nothing: area FF, types unset)
6270 = rng_below(3)
pick_base(0, -1, -1, 67D2)                   /* player's base */
m = mid(67D2, 67DE); c1 = class(62DD); c2 = class(636D)
if c1 >= 4 && c2 >= 4: c1 = c2 = 4 else c1 = c2 = min(c1,c2)
A = 67EA = m; Bp = 67F6 = m; A.alt = alt(c1).min; Bp.alt = alt(c2).min; 680A/6816 (the second
waypoints' alt) = the same values; 62CC = c1; 635C = c2
variant 0: A.x += 25000; Bp.x -= 25000; 62CA = hdg(A,Bp)>>8; 635A = hdg(Bp,A)>>8;
           6802 (player's wp1) = Bp, 680E (ace's wp1) = A
variant 1: A.x += 5000; Bp.x -= 5000; h = hdg(A,Bp); 62CA = 635A = h>>8; A.alt += 3000
           6802 = move(A, h, 4,000,000); 680E = move(Bp, h, 4,000,000)
variant 2: same offsets; h = hdg(Bp,A); both headings h>>8; Bp.alt += 3000; moves as variant 1
player wp = [A, 6802], ace wp = [Bp, 680E] (2 each, malloc 0x18)
62C9 = 6359 = 4; 62CD = 0; 62E5 = 1; 635D = 0; 6375 = 0; 62CE = 0; 635E = 0
kind 0: 2777:04fa(62C5,6,0,0), 2777:04fa(6355,6,1,0); then 280a:0431, 28e4:0820
```
(62E5 = 1 points the player at group 1, the ace.)

## Type 1 — `35b3:000f` dogfight with a squadron (MT_DSQD) — args (service, kind)

```
reset; kind; mtype 1; setup(service); 28e4:019f; 280a:00af; 2968:0075
62C5 = service; 6355 = enemy_service(service)
add_flight(service, 0, 0); pick_base(0, -1, -1, 681A)
6270 = rng_below(3)
add_flight(6355, 1, 0); pick_base(1, -1, -1, 6826)
m = mid(681A, 6826); classes as type 0 -> 6832 (A), 683E (B) = m with alts; 6852/685E second alts
variant 0: A.x += 19000; B.x -= 19000; 62CA = hdg(A,B); 635A = hdg(B,A); 684A = A; 6856 = B
variant 1: ±5000; h = hdg(A,B); both; A.alt += 3000; 684A = move(A,h,4,000,000); 6856 = move(B,h,…)
variant 2: ±5000; h = hdg(B,A); both; B.alt += 3000; moves as 1
player wp = [6832, 684A], enemy wp = [683E, 6856]
626E = 0; 62C9 = 6359 = 4; 62CD = 0; 62E5 = 1; 635D = 0; 6375 = 0; 62CE = 0; 635E = 0
kind 0: 04fa(service,5,0,0), 04fa(6355,4,1,0); 2968:0446; 280a:0431; 28e4:0820
```
Note: in variant 0 of type 1 the second waypoints are copies of the flight's **own** start (`684A = 6832`,
`6856 = 683E`), unlike type 0 where they are swapped (verified in both).

## Type 2 — `35ed:0000` combat air patrol (MT_CAP) — args (service, kind)

```
setup…; 62C5 = service; 6355 = enemy_service; add_flight(service,0,0); pick_base(0,-1,-1,&B)
6270 = rng_below(3)
R = range(62DD) * 21128; d = (R - R*25/100) / 7; d -= d >> 2        (long, signed)
P0 = (B.x-d, B.z), P1 = (B.x, B.z+d), P2 = (B.x+d, B.z), P3 = (B.x, B.z-d)  at DS:6862,686E,687A,6886
    (their alt dwords are not written here)
n = rng_below(4) + 1
for i < n: side1 flight i squad = FFFF; add_flight(6355, 1, 0)
           m = mid(P[i], P[i+1]); r = rng_below(3); r==1: m = mid(m, P[i+1]); r==2: m = mid(P[i], m)
           E[i] = m (DS:6892 + 12i)          /* P[4] = DS:6892 = E[0]: for i = 3 it reads E[0] */
clamp P0..P3: while |x| >= 12,672,000 (0xC15C00, via labs 0000:1c46): x = x < 0 ? -12,572,000 : 12,572,000
              (0xFF402AA0 / 0x00BFD560); same for z
pick_base(1, -1, -1, &EB)
v = cruise(62DD)
player wp (7) = [B, P0 v, P1 v, P2 v, P3 v, P0 v, B alt 10000]
for i < n: side1 flight i: nwp 2 = [E[i] alt v, B alt v]; +05 = hdg(E[0], E[1])>>8 (same for all);
           +08 = 0; +20 = 0; +04 = 0; +09 = 2
62CD = 0; 62E5 = 6261 (= 1: group 1 = first enemy flight); 62C9 = 1; 62CE = 0
kind 0: 04fa(service,5,0,0), 04fa(6355,4,1,0); 280a:0431; 28e4:0820; 2968:0446
```
(the clamp runs after the enemy points are computed, so enemies may lie outside the clamp.)

## Type 3 — `3641:0005` fighter sweep (MT_FSWP) — args (service, kind)

```
w[3] = DS:22DC {45, 40, 15}
setup…; 62C5 = service; 6355 = enemy; add_flight(service,0,0); pick_base(0,-1,-1,&B)
n = rng_pick_weighted(w,3) + 1; for i < n: squad FFFF; add_flight(6355, 1, 0)
pick_base(1, -1, 0 /* ref: player's side */, &T)
if T.x == -1 (both words): pick_ground_target(0, 6355, &B, &T)
k = rng_below(2) + 3               /* number of player waypoints 3 or 4 (5 unreachable) */
2b1f:00f9(&T, &B)                  /* heading in degrees; result discarded */
v = cruise(62DD); ve = v; if alt(class(636D)).max < v: ve = cruise(636D)
R = min(range(62DD), 800) * 21128; D = (R - R*35/100) / k
route = [B, …]:
  k 3: [B, T alt v, B alt 10000]
  k 4: [B, move(T, 0x11C6, D) alt v, T alt v, B alt 10000]
  k 5: [B, move(T,0x1FFE,D) v, T v, move(T,0x038E,D) v, B 10000]   (unreachable)
  (the angles are absolute, not relative to the discarded heading)
r1 = range*21128, r2 = (range+reserve)*21128 (full, not 40 %)
L = dist(B,w1) + dist(w1,w2) + dist(w2,w3) (+ w3-w4 if k>3, + w4-w5 if k>4)
if L > r2: k = 3, route = [B, T v, B 10000], L recomputed (3 legs, the third from B-to-B = 0 terms as coded)
if L > r1: 62C8 = 2ab3:03a7(3, 62DD, 1, 0)
E[0] = T; for i = 1..n-1: r = rng_below(k-2); E[i] = mid(T, route[i + r])
player wp = route (k)
for i < n: side1 flight i: nwp 1 = [E[i] alt ve]; +05 = hdg(E[i], B)>>8; +04 = 0; +08 = 1;
           +20 = 6267-1 (the last place = the enemy base); +09 = 2; +03 = 1
62CD = 0; 62E5 = 6261; 62C9 = 4; 62CE = 0
kind 0: 04fa(service,5,0,0), 04fa(6355,4,1,0); 280a:0431; 28e4:0820; 2968:0446
```

## Type 4 — `36ab:0001` scramble (MT_SCRM) — args (service, kind)

```
setup…; 62C5 = service; e = enemy_service(service) (6355 set only through add_flight)
add_flight(service,0,0); pick_base(0,-1,-1,B=68B6)
n = rng_below(100) > 50 ? 2 : 1; for i < n: squad FFFF; add_flight(e, 1, 1)
6270 = rng_below(3); pick_base(1,-1,-1,EB=68C2); h = hdg(B, EB)
player: nwp 1 = [B]; 62C9 = 5; 62CE = 0; 62CD = 62CB ? 2 : 1; 62E5 = 62E3 (own home is the objective)
for i < n (side1 flight i):
   a = role(i) == 3 ? 20000 : ralt(role(i))          /* role = flight[1][i].+02 */
   S = move(B, h, DS:6357 (flight[1][0] role) != 3 ? (i+1)*75000 : i*75000 + 175000)
   +05 = hdg(S, B)>>8; wp = [S alt a, B alt a, EB alt 10000] (3)
   +04 = 3; +09 = 0; +08 = 62CB ? 2 : 1; +20 = 62E3; +03 = 2ab3:03a7(4, type, 0, 1)
kind 0: 04fa(service,5,0,0), 04fa(e,0x3C,1,0); 280a:0431; 28e4:0820 (no 2968:0446)
```

## Type 6 — `36dd:000e` escort (MT_ESCT) — args (service, kind) (`36dd:0009` is an empty function)

```
w = DS:22E2 {70, 30}
setup…; 62C5 = service; e = enemy_service; add_flight(service,0,0); pick_base(0,-1,-1,B=68DA)
6270 = rng_below(3); n = rng_pick_weighted(w,2) + 1
for i < n: squad FFFF; add_flight(e, 1, 0)
pick_base(1,-1,-1,EB=68E6)
63FB = FFFF; add_flight(service, 2, 1) (bombers); pick_base(2,-1,-1,BB=68F2)
if 63ED (bomber +08) == 1: pick_ground_target(0, e, &B, T=68FE); 63ED = 1; 6405 = 6267-1
else: pick_convoy(0, service, e, 6357, &B, &T); 63ED = 0; 6405 = Σflights + 6269 - 1
m = mid(B,T); A1 = A2 = m
R = range(62DD)*21128 (+ reserve(62DD)*21128 if 62C8 > 7); R /= 4 (LDIV)
d0 = dist(B, m); off = d0 < R ? (R - d0) >> 1 : 0; A1.x += off; A2.x -= off
ab = ralt(63E7 bomber role); ae = ab; if alt(class(636D)).max < ab: ae = cruise(636D)
player wp (5) = [B, A1 ab, T ab, A2 ab, B 10000]
bombers (6401 = 4) = [A1 ab, T ab, A2 ab, BB 10000]
side1 flight 0: nwp 1 = [mid(A1, T) alt ae]
if n > 1: side1 flight 1: nwp 1 = [T alt ae]; +08 (6381) = 63ED; +20 (6399) = 6405
62C9 = 6; 6359 = 5; 63E9 = 3; 62CD = 0; 62E5 = 6261 + 6263 (group of the bombers); 635D = 63ED;
6375 = 6405; 62CE = 0; 635E = 2; 63EE = 1
kind 0: 04fa(service,5,0,0), 04fa(6355,4,1,0), 04fa(service,0x38,2,0); 280a:0431; 28e4:0820; 2968:0446
```
(side-1 flight 0 gets no +08/+20; the other side-1 flights beyond 1 get no waypoints.)

## Type 8 — `372e:000c` anti-shipping (MT_ANTI) — args (service, kind)

```
w = DS:22E6 {40, 70} (used as two thresholds)
setup…; 62C5 = service; e = 6355 = enemy_service; add_flight(service, 0, 1); pick_base(0,-1,-1,P)
A = rng_below(100) > 50: add_flight(6355,1,0); pick_base(1,-1,-1,EB)
B = (62C7 == 0 && rng_below(100) <= 40) || (62C7 > 0 && rng_below(100) <= 70)
        (role 0 with a failed draw does not draw again)
626F = rng_below(4)                  /* wind re-drawn, overrides setup's */
pick_convoy(0, service, e, 62C7, &P, &T)
a = ralt(62C7); ae = a; if A and alt(class(636D)).max < a: ae = cruise(636D)
player wp (3) = [P, T alt a, P alt 10000]; 62CA = hdg(P, EB)>>8 (EB uninitialised when !A)
62C9 = 3; 62CD = 2; 62E5 = 6269-1; 62CE = 0
if A: m1 = mid(P,T); m2 = mid(T, m1); X = dist(T, m2) < 25000 ? m1 : m2
      side1 flight 0: [X alt ae]; +05 = hdg(T,P)>>8; +04 = 5; +08 = 2; +20 = 6269-1; +09 = 2; +03 = 1
if B: add_flight(service, 2, 0); 6401 = 3: [P alt 10000, T alt a, P alt 10000]; 63EA = hdg(P,EB)>>8;
      63E9 = 6; 63ED = 0; 6405 = 0; 63EE = 0
kind 0: 04fa(service,0x1D,0,0); 280a:0431; 28e4:0820 (no 2968:0446)
```

## Type 9 — `37fc:0005` ground attack (MT_GRND) — args (service, kind)

```
w = DS:22FA {40, 70}
setup…; 62C5 = service; 6355 = enemy_service; add_flight(service, 0, 1); pick_base(0,-1,-1,P)
626F = rng_below(4)
A = rng_below(100) > 50: add_flight(6355,1,0); pick_base(1,-1,-1,EB)
B = as type 8 (thresholds 40 / 70)
pick_ground_target(0, 6355, &P, &T)
a = ralt(62C7); j = rng_below(20); j = j > 10 ? (j-20)*1000 : j*1000
ae = a + j; if A and alt(class(636D)).max < ae: ae = cruise(636D)
player wp (3) = [P, T alt a, P alt 10000]; 62CA = hdg(P,T)>>8; 62C9 = 3; 62CD = 1; 62E5 = 6267-1; 62CE = 0
if A: m1 = mid(P,T); m2 = mid(T,m1); X = dist(EB, m2) < 25000 ? m1 : m2
      side1 flight 0: [X alt ae]; +05 = hdg(T,P)>>8; +04 = 5; +08 = 1; +20 = 62E5; +09 = 2; +03 = 1
if B: add_flight(service,2,0); [P 10000, T a, P 10000]; 63EA = hdg(P,T)>>8; 63E9 = 6; 63ED = 0; 6405 = 0; 63EE = 0
kind 0: 04fa(service,0x15,0,0), 04fa(6355,4,1,0); 280a:0431; 28e4:0820
```

## Type 7 — `3769:0866` intercept (MT_INTR), `3769:0009` bombers, `3769:04de` kamikaze

`3769:0866(service, kind)`:
```
setup…; 62C5 = service; e = enemy_service; DS:692E = 6355 = 63E5 = e
add_flight(service, 0, 0); pick_base(0,-1,-1,P=6922)
if service == 0 && 63E7 != 3 && date > 16364 (0x3FEC, 21 Oct 1944) && rng_below(100) <= 65:
     kamikaze(service)                       /* 63E7 is still 0 here, so the test is always true */
else intercept_bombers(service)
62C9 = 5; 62CE = 0; 63EE = 1; 62CD = 63ED; 62E5 = 6405; 280a:0431; 28e4:0820
```

`3769:0009 intercept_bombers(service)`:
```
add_flight(63E5, 2, 1)                                   /* enemy bombers */
if 63ED == 1 || 63E7 == 3: pick_ground_target(0, service, &P, T=690A)
      invalid (x and z == -1): T = P; 63ED = 62CB ? 2 : 1; 6405 = 62E3
      else 63ED = 1; 6405 = 6267-1
else: pick_convoy(0, service, service, 63E7, &P, &T)
      invalid: T = P; 63ED = 62CB ? 2 : 1; 6405 = 62E3
      else 63ED = 2; 6405 = 6269-1
add_escort_flights(692E, 1, 0)                            /* 0..2 enemy escorts, RNG {30,50,20} */
pick_base(2,-1,-1,EB=6916); X = mid(EB, T)
r1 = range*21128, r2 = (range+reserve)*21128 (player type)
loop: s = dist(P,X) + dist(X,P); if s > r1 && s > r2: X = mid(X, T); repeat
if dist(T, X) < 800,000: X = move(T, hdg(P,T), 800,000)     (0x000C3500)
if s > r1 (last s) && 62C8 < 7: 62C8 = 2ab3:03a7(7, 62DD, 1, 0)
player wp (3) = [P, X alt ralt(63E7)+10000, P alt 10000]
for i = 6263 .. 1 (side1 flight i-1): [X alt ralt(63E7), T alt ralt(63E7), EB alt 10000];
      +04 = 6; +08 = 0; +20 = 6261 + 6263; +09 = 1; +03 = 1
bombers 6401 = 3: [X, T, EB 10000] alt ralt(63E7); 63E9 = 3
kind 0: 04fa(service,5,0,0), 04fa(6355,4,1,0), 04fa(63E5,0x38,2,0)
```

`3769:04de kamikaze(service)`:
```
add_flight(63E5, 2, 1)
if file kamikaze.dat opens: read s16 k[10] (shipped 23 23 31 33 34 25 26 27 29 26);
    r = rng_below(5); type = 692E == 3 ? k[r] : k[2r]; 63FD = type; 63E7 = 2777:0204(type);
    63E8 = 2ab3:03a7(7, type, 0, 2); close
if 62CB (player on a carrier): T = P; 63ED = 2; 6405 = 62E3
else intercept_bombers(service)           /* the whole type-7 builder runs, then continues here */
add_escort_flights(692E, 1, 0); pick_base(2,-1,-1,EB); S = move(T, hdg(T,EB), 75000)
player wp (3) = [P, S alt ralt(63E7)+10000, P alt 10000]
for i = 6263 .. 1: side1 flight i-1: [S alt 60000, T alt 60000, EB alt 10000]; +04 = 6; +08 = 0;
      +20 = 6261+6263; +09 = 0; +03 = 1
kamikazes 6401 = 3: [S, T, EB 10000] alt ralt(63E7); 63E9 = 2
626C = 10 (mission type "kamikaze": debrief group 7, success DS:0512[11])
kind 0: 04fa(service,5,0,0), 04fa(6355,4,1,0), 04fa(63E5,0x3C,2,0)
```
(on a land base the kamikaze branch re-runs `intercept_bombers`, whose flights, waypoints and RNG draws
all stay; then the kamikaze assignments overwrite side-1/2 waypoint pointers without freeing the old ones.)

## RNG call order per type (after `mission_setup`, which already consumed its draws)

| Type | Draws in order |
|---|---|
| 0 | (no reseed) add-flight-free; `rng_below(3)` variant; pick_base(0)'s `rng_below(count)` |
| 1 | add_flight(0) [skill picks, aces `rng_below(100)`, role weights]; pick_base; `rng_below(3)`; add_flight(1); pick_base(1) |
| 2 | add_flight(0); pick_base(0); `rng_below(3)`; `rng_below(4)`; per enemy: add_flight, `rng_below(3)`; pick_base(1) |
| 3 | add_flight(0); pick_base(0); `pick({45,40,15})`; n× add_flight; pick_base(1,ref 0); [pick_ground_target]; `rng_below(2)`; [loadout]; (n−1)× `rng_below(k−2)` |
| 4 | add_flight(0); pick_base(0); `rng_below(100)`; n× add_flight(mode 1: role `pick({20,80})`…); `rng_below(3)`; pick_base(1); per enemy loadout |
| 6 | add_flight(0); pick_base(0); `rng_below(3)`; `pick({70,30})`; n× add_flight; pick_base(1); add_flight(2); pick_base(2); target (14bc or 0fb2) |
| 7 | add_flight(0); pick_base(0); [`rng_below(100)` if the date test passes]; bombers/kamikaze as above |
| 8 | add_flight(0,mode 1); pick_base(0); `rng_below(100)` (A); [add_flight, pick_base]; `rng_below(100)` (B, unless role 0 path fails first test); `rng_below(4)` wind; pick_convoy; [add_flight(2)] |
| 9 | add_flight(0,1); pick_base(0); `rng_below(4)` wind; `rng_below(100)` A; [add_flight(1), pick_base(1)]; B draw; pick_ground_target; `rng_below(20)`; [add_flight(2)] |

(`add_flight`, `pick_base`, `pick_ground_target`, `pick_convoy` and the emd helpers they call contain further
draws, listed in `shell_data.md` §7 and the emd parts.)

## Hand-offs / open

* The meaning of flight +04 values (1, 2, 3, 4, 5, 6) and +09 (0, 1, 2) → group +03 / +1E in SCRIPT.DAT: AI
  behaviour codes for sim_world.
* `2777:04fa` second argument (5, 6, 4, 0x38, 0x3C, 0x1D, 0x15): emd2.
