# sim_world — AP.EXE world simulation (index)

**Status: complete for the port (finish pass 2026-09-26).** Scope: flight model, AI pilots and
flights, weapons, damage, collisions, ships and ground targets, the sim-side scenario
(`snario.c`), `acedata.c`, clouds. Segment ownership follows `sim_flow.md` §0; every function of
the sim_world segments has a row in one of the symbol files below (except the four radio-menu
functions of `1660` that the ownership map gives to sim_flow, see `sim_world_ai.md` §21).

## Parts

| File | Covers | Symbols |
|---|---|---|
| `sim_world_fm.md` | flight model `0b01`, per-aircraft step and steering primitives `4bf9`, `.FMD`, `362b` time helpers (sim_flow's, described as used) | `sim_world_fm_symbols.csv` |
| `sim_world_ai.md` | state executor and descriptors, alerts, per-frame flight update, target choice, elements and spotting, gunnery and aiming, dog-fight states, manoeuvre library, tactics, g_attack (ground/ship attack), flight-level states (take-off, formation, waypoints, escort, return), waypoints, spawning, LSO, radio-order reactions | `sim_world_ai_symbols.csv` |
| `sim_world_wpn.md` | weapons: guns, bullets, bombs, rockets, torpedoes, flak, impacts, hit boxes, `.MEC .GL .GLT` | `sim_world_wpn_symbols.csv` |
| `sim_world_dmg.md` | scenario set-up (`56ac`, `45cc`, `465c`), damage, collisions, crashes, parachutes, G load, ship movement, clouds (`490a`) | `sim_world_dmg_symbols.csv` |

## Frame order (from `5440:1317`, sim_flow §6) and time base

The world is stepped **once per rendered frame**; every rate is scaled by the frame's time step
`DS:711E` (100h = one nominal step; sim_flow §4 derives it from the measured PIT ticks and the
time-scale slider and clamps it to 40h..1C2h). The flight model integrates with `DS:711E` as is
when it is below 100h and in **two half steps** otherwise (`0b01:1860`); positions advance by
`v·DS:3F22/1024` per nominal step (`DS:3F22 = 70`), gravity is `DS:3F24 = 66`. AI timers,
weapon timers, fuel burn and damage timers all count down by `DS:711E` per frame
(`362b:0165..02e3`); the mission clock `DS:4086` grows by `DS:711E`. Nothing in sim_world runs on
a fixed tick of its own, so the port's pacing only has to reproduce the `ticks → DS:711E` mapping
and feed the same values (from the clock or from a film).

## Plane object (0x107 bytes, pool `DS:3B05`, created by `465c:015f`)

Details per part: FM state `sim_world_fm.md` §2, damage/status fields `sim_world_dmg.md` (Data
structures), AI fields `sim_world_ai.md` §16, weapon fields `sim_world_wpn.md` §3.1.

| Off | Type | Meaning |
|---|---|---|
| 00 | u16 | 3Space object flags (`|= 8800h` on creation; low 5 bits = class: 3 aircraft, 4 ship; 2000h hidden) |
| 02 | u16 | shape handle; start of the posture used by the FM |
| 04/08/0C | i32 | x, y, z (altitude) |
| 10/12/14 | u16 | pitch, roll, heading |
| 16 | ptr | per-object byte block (`[0]` toggled by `plane_fly`, `[1]` gear-retraction delay, `[3..4]` fire flags) |
| 18 | u8 | kind: 0 aircraft, 1 ship |
| 19 | u8 | model type → `DS:54BC[type]` slot → `DS:55D2[slot]` aircraft `.DAT` |
| 1A–1F | u8 | status bits (dmg part: dead, smoking, drop tank, low fuel, going down; ai part: aim valid, element roles, orders) |
| 20 | ptr | 42-byte matrix block; 22 (ships) 12-byte block; 24 box list |
| 26 | u8 | side 0 US, 1 Japan |
| 28, 2A | ptr | `.DMG` image, damage state |
| 2C–33 | | alert state (ai §3) |
| 34 | ptr | flight record (56h bytes) |
| 36 | lvec | previous position |
| 42–49 | u32 ×2 | situation flags (ai §16) |
| 4A–57 | | brain (ai §1.1); 54 = scratch pointer |
| 5E, 60 | ptr | `.GL` image, gun state |
| 64 | FmState | 48h bytes (fm §2.2) |
| AC | Controls | fm §2.3 |
| BB | u8 | pilot index; 44 = the player (`DS:3B09`) |
| BC | i8 | index in the flight |
| BD, CA, E3, E7 | | orders / ground-attack task (ai §15) |
| C1 | u16 | `plane_fly` requests |
| C3 | u8[6] | known planes bit set |
| C9 | u8 | serial number |
| CB–D6 | | aim record (ai §7.1) |
| D7, D9, DB, DD | ptr | target, attacker slots, element leader |
| DF, F2, F9, FB, FD, FF, 101 | | AI timers and closure angles (ai §16) |
| EB–F8 | | ordnance (rocket rack, torpedo, 3 stations) |
| EF | ptr | ship under the plane |

## Globals (main ones; the parts list the rest)

| DS | Name | Meaning |
|---|---|---|
| 3B09 | player_plane | the player's Plane |
| 3B05, 3B03 | plane_pool, ship_pool | pools (107h / 88h bytes) |
| 4751, 4753, 4755, 4759, 475B | flights, places, lists | scenario (dmg §1) |
| 54BC, 555B | model / ship slot by type | |
| 55D2, 55D0, 55CE | aircraft `.DAT`, ship `.DAT`, pilot profiles | |
| 42D2 | realism_combat_level | 0..2 |
| 42D3 | realism_flight_model | 0..2 → fm mode `DS:02CE` = {1, 2, 3} |
| 711E | dt | frame time step (sim_flow) |
| 4454 | rng_state | sim_flow's RNG; every draw of the world code is listed in the parts' "RNG call sites" |
