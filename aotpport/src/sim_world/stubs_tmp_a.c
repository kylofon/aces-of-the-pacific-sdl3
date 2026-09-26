/* Temporary weak stubs for functions of other modules that sim_world part A calls (PORT_BRIEF.md).
 * Every stub is __attribute__((weak)); the real implementation replaces it when it lands. The sim_flow
 * time-base helpers (362b) and the RNG (1889) are implemented as specified so the flight-model test
 * gives real numbers before sim_flow exists. */
#include "sim_world/swa_priv.h"

#define WEAK __attribute__((weak))

int sim_world_a_stubs_anchor;

/* ---- sim_flow 362b time base (sim_world_fm.md §5, x86dis 362b) ---------------------------------- */
WEAK s16 dt_scale(s16 x)
{
    s32 v = ((s32)x * DT) >> 8;
    if (v < -0x7FFF) v = -0x7FFF;
    else if (v > 0x7FFF) v = 0x7FFF;
    return (s16)v;
}
WEAK s16 steps_to_frames(s16 n) { return n; }
WEAK s16 timer16_dec(u16 p)
{
    s16 r = (s16)(DSS(p) - DT);
    s32 full = (s32)DSS(p) - DT;                          /* jge after sub: SF == OF <=> full >= 0 */
    DSS(p) = full >= 0 ? r : 0;
    return DSS(p);
}
WEAK s16 timer32_dec(u16 p)
{
    int64_t full = (int64_t)DSSL(p) - DT;
    DSSL(p) = full >= 0 ? (s32)full : 0;
    return (s16)DSSL(p);
}
WEAK s16 timer16_dec_far(FarPtr a)
{
    s16 *q = (s16 *)far_mp(a);
    s32 full = (s32)*q - DT;
    *q = full >= 0 ? (s16)full : 0;
    return *q;
}
WEAK s16 timer32_expired(u16 p)
{
    int64_t full = (int64_t)DSSL(p) - DT;                 /* jle after sub: ZF or SF != OF */
    if (full <= 0) { DSSL(p) = 0; return 1; }
    DSSL(p) = (s32)full;
    return 0;
}
WEAK s16 timer16_expired_far(FarPtr a)
{
    s16 *q = (s16 *)far_mp(a);
    s32 full = (s32)*q - DT;
    if (full <= 0) { *q = 0; return 1; }
    *q = (s16)full;
    return 0;
}
WEAK void dt_scale_frac(u16 x, u16 frac)
{
    s32 p = (s32)DSS(x) * DT;
    u32 a = p < 0 ? (u32)-p : (u32)p;
    s32 r = p >> 8;
    DSW(frac) = 0x3FF;
    if (r > 0x7FFF) r = 0x7FFF;
    else if (r < -0x7FFF) r = -0x7FFF;
    else DSW(frac) = (u16)((a & 0xFF) << 2);
    if (r < 0) DSW(frac) = (u16)-DSW(frac);
    DSS(x) = (s16)r;
}
WEAK s16 dt_mul(s16 x) { return (s16)((s32)x * DT); }

/* ---- sim_flow 1889 RNG (x86dis 1889:005f / 00b4) ------------------------------------------------- */
WEAK u16 ap_rng_next(u16 st)
{
    if ((s8)DSB((u16)(st + 0x71)) < 0) return 0xFFFF;      /* PORT: the playback hook (far call) is not modelled here */
    s8 i = (s8)DSB((u16)(st + 0x71)); DSB((u16)(st + 0x71))++;
    u16 v = DSW((u16)(st + i * 2));
    s8 j = (s8)DSB((u16)(st + 0x70)); DSB((u16)(st + 0x70))++;
    DSW((u16)(st + j * 2)) = (u16)(DSW((u16)(st + j * 2)) + v);
    u16 dx = DSW((u16)(st + j * 2));
    if (DSB((u16)(st + 0x70)) == 0x38) DSB((u16)(st + 0x70)) = 0;
    else if (DSB((u16)(st + 0x71)) == 0x38) DSB((u16)(st + 0x71)) = 0;
    return dx;
}
WEAK s16 rng_mod(u16 st, s16 n)
{
    if (n <= 1) return 0;
    return (s16)((s32)(ap_rng_next(st) & 0x7FFF) % n);
}

/* ---- link stubs for functions of sim_flow that are not built yet (part B's AI stubs were removed when
 * the AI landed) ---------------------------------------------------------------------------------------- */
WEAK s16 approach_dt(u16 v_ds, s16 target, s16 step) { return DSS(v_ds); }
WEAK s16 orbit_min_dist(u16 o_ds) { return 0; }
WEAK void wcam_note_weapon(FarPtr w) {}
WEAK FarPtr bxl_load(u16 name_ds) { return far_make(0, 0); }
WEAK void bxl_get(s16 slot, u16 out_ds) {}
WEAK void end_request(u8 code) {}
WEAK void guns_jammed(void) {}
WEAK void kill_credit(u16 a0, u16 a1, u16 a2, u16 a3, u16 a4, u16 a5) {}
WEAK void target_credit(u16 shooter, FarPtr rec, FarPtr ref, u16 cls, u16 type, u16 delta, u16 destroyed) {}
WEAK u32 rand_table_pair(void) { return 0; }
WEAK FarPtr str(s16 group, s16 id) { return far_make(0, 0); }
WEAK void msg_show(FarPtr s, s16 prio, FarPtr speaker) {}
WEAK void msg_clear_all(void) {}
WEAK void radio_queue7(u16 a0, u16 a1, u16 a2) {}
WEAK void warn_init(u16 w_ds, s16 group, s16 id, s16 prio) {}
WEAK void warn_tick(u16 w_ds) {}
WEAK void timeout_start(u16 t_ds, s32 n) {}
WEAK void bxl_load_slot(s16 slot, u16 name_ds) {}
WEAK void bxl_table(s16 n) {}
WEAK void cockpit_load(u16 code_ds) {}
WEAK void cockpit_unload(void) {}
WEAK void cockpit_reset(void) {}
WEAK void cockpit_leave(void) {}
WEAK void lso_load(void) {}
WEAK void lso_free(void) {}
WEAK u16 res_load_set(u16 a0, u16 a1, u16 a2, u16 a3) { return 0; }
WEAK void res_free(u16 p0_ds) {}

#ifdef SWA_WRAP_DEVTEST
/* The module's own test build (build_sim_world_a) links with --wrap for the helpers that other modules'
 * weak stubs define as identity functions (the linker keeps the first weak definition it sees), so the
 * flight-model test runs on the specified time base and RNG. */
s16 __wrap_dt_scale(s16 x);
s16 __wrap_dt_scale(s16 x)
{
    s32 v = ((s32)x * DT) >> 8;
    if (v < -0x7FFF) v = -0x7FFF;
    else if (v > 0x7FFF) v = 0x7FFF;
    return (s16)v;
}
s16 __wrap_timer16_dec(u16 p);
s16 __wrap_timer16_dec(u16 p)
{
    s32 full = (s32)DSS(p) - DT;
    DSS(p) = full >= 0 ? (s16)full : 0;
    return DSS(p);
}
u16 __wrap_ap_rng_next(u16 st);
u16 __wrap_ap_rng_next(u16 st)
{
    if ((s8)DSB((u16)(st + 0x71)) < 0) return 0xFFFF;
    s8 i = (s8)DSB((u16)(st + 0x71)); DSB((u16)(st + 0x71))++;
    u16 v = DSW((u16)(st + i * 2));
    s8 j = (s8)DSB((u16)(st + 0x70)); DSB((u16)(st + 0x70))++;
    DSW((u16)(st + j * 2)) = (u16)(DSW((u16)(st + j * 2)) + v);
    u16 dx = DSW((u16)(st + j * 2));
    if (DSB((u16)(st + 0x70)) == 0x38) DSB((u16)(st + 0x70)) = 0;
    else if (DSB((u16)(st + 0x71)) == 0x38) DSB((u16)(st + 0x71)) = 0;
    return dx;
}
#endif
