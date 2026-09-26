# sim_world — AP.EXE world simulation (index)

**Status: draft (lead), parts in progress.** Scope: flight model, AI pilots and flights, weapons,
damage, collisions, ships and ground targets, the sim-side scenario (`snario.c`), `acedata.c`.
Segment ownership follows `sim_flow.md` §0.

## Parts

| File | Covers |
|---|---|
| `sim_world_fm.md` | flight model `0b01`, per-aircraft step and AI steering primitives `4bf9`, `.FMD` |
| `sim_world_ai1.md` | pilot-level AI: manoeuvres, tactics, gunnery, ground attack |
| `sim_world_ai2.md` | flight-level AI: behaviour states, flights/formation, targeting, carrier ops |
| `sim_world_wpn.md` | weapons: guns, bullets, bombs, rockets, torpedoes, flak, `.MEC .GL .GLT` |
| `sim_world_dmg.md` | damage, collisions, crashes, ships, scenario set-up, acedata, objects |

## Plane object (draft; 0x107 bytes, pool `DS:3B05`, created by `465c:015f`)

| Off | Type | Meaning | Evidence |
|---|---|---|---|
| 00 | u16 | 3Space object flags (`|= 8800h` on creation; low 5 bits = class: 3 aircraft, 4 ship, `637f:0015`) | 465c:015f |
| 02 | u16 | shape handle (`DS:4601[type]`, `6964:06c0`); start of the posture used by the FM | 465c:00fd |
| 04/08/0C | i32 | x, y, z (altitude) | fm |
| 10/12/14 | u16 | pitch, roll, heading | fm |
| 16 | ptr | per-object byte block (toggled by `plane_fly`) | 465c:005a |
| 18 | u8 | kind: 0 aircraft, 1 ship | 465c |
| 19 | u8 | model type (mission record +00) → `DS:54BC[type]` model slot → `DS:55D2[slot]` aircraft `.DAT` image | 465c |
| 1A, 1B | u8 | status bits (1A: 01, 40 = down/dead?; 1B: 01, 02, 08 = player's aircraft with `.DAT`+39) | 4edf:0619, 637f |
| 20 | ptr | 42-byte block (orientation matrix etc.) | 465c:005a |
| 22 | ptr | 12-byte block | 465c:005a |
| 26 | u8 | side/team (`DS:00C0[...]`) | 465c:00fd |
| 28, 2A | u16 | damage data (`4b3a:03ff`) | 465c:015f |
| 34 | ptr | flight (group) record; `+3B & 2` tested | 637f:009a |
| 5E, 60 | u16 | gun data (`4cda:00f8`) | 465c:015f |
| 64 | FmState | flight model state, 0x48 bytes | sim_world_fm.md §2.2 |
| AC | Controls | stick, rudder, throttle, mass, ground height, flap/gear bits | sim_world_fm.md §2.3 |
| BB | u8 | pilot index (`DS:55CE[i]` pilot profile); **44 = player** (`DS:3B09` = player's Plane) | 465c:00fd |
| C0 | i8 | ? | 465c:00ee |
| C1 | u16 | AI request bits for `plane_fly` | 4bf9:0257 |
| C9 | u8 | serial number (`DS:00BA`++) | 465c:015f |
| EB, EC, ED, F1, F3 | | from mission record +0C..+15 (ordnance slots) | 465c:015f |

Parts: record here the fields you establish (the lead merges them).

## Globals (draft)

| DS | Name | Meaning |
|---|---|---|
| 3B09 | player_plane | the player's Plane |
| 3B05 | plane_pool | pool of 0x107-byte planes |
| 3B03 | ship_pool | pool of 0x88-byte ships |
| 54BC | model_slot_by_type | u8[9Fh] aircraft type → loaded model slot (FFh = not loaded); `DS:54BA` = count |
| 555B | ship_slot_by_type | u8[73h]; `DS:54B8` = count |
| 55D2 | aircraft_dat | near ptr[slot] → 131-byte aircraft `.DAT` image |
| 55D0 | ship_dat | near ptr[slot] → 154-byte ship `.DAT` image |
| 55CE | pilot_profiles | near ptr[194] → 112-byte `.PLT` profiles (converted by `45cc:00a0`) |
| 42D2 | realism_combat_level | 0..2 |
| 42D3 | realism_flight_model | 0..2 → fm mode `DS:02CE` = {1, 2, 3} |
