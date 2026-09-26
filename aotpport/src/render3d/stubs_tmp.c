/* Temporary weak stubs for functions of other modules that render3d calls (PORT_BRIEF.md). Every stub
 * is __attribute__((weak)); the real implementation replaces it when it lands. */
#include "render3d/r3d_priv.h"
#include "platform/platform.h"
#include "sim_world/sim_world.h"
#include "sim_flow/sim_flow.h"

#define WEAK __attribute__((weak))

/* MinGW: one plain global per stub file (REQUESTS "all modules"). */
int render3d_stubs_anchor;

/* sim_world 07fe:000a: the 4-point bitmap "draw" of polygon flag 10h is an assert helper in AP */
WEAK void ces_check(u16 a, u16 b, u16 c) { (void)a; (void)b; (void)c; }

/* sim_flow time base (362b) */
WEAK s16 steps_to_frames(s16 n) { return n; }
WEAK s16 dt_scale(s16 a0) { return a0; }

/* sim_flow (views, cockpit window, time base, RNG, file helper) */
WEAK s16 camera_obj_ref(void) { return (s16)(DSW(DSW(0x437E) + 2) + 2); }
WEAK s16 clip_to_view(void) { return 0; }
WEAK s16 fullscreen_view(void) { return 1; }
WEAK void limit_window(u16 c_ds) { (void)c_ds; }
WEAK s16 cockpit_view_window(u16 r)
{
    DSW(r) = 0; DSW(r + 2) = 0; DSW(r + 4) = 320; DSW(r + 6) = 200;
    return 100;
}
WEAK s16 view_get(void) { return 0; }
WEAK u16 view_outside_target(void) { return 0; }
WEAK s16 timer16_dec(u16 p) { return (s16)DSW(p); }
WEAK u16 ap_rng_next(u16 st_ds) { (void)st_ds; return 0; }
WEAK u8 xor_bytes(u16 p, s16 n) { u8 x = 0; while (--n >= 0) x ^= DSB(p++); return x; }
WEAK s16 ap_fread_far_55a4(FarPtr dst, s32 n, u16 fp)
{
    u16 mk = stk_mark(), buf = stk_alloc(512);
    s32 done = 0;
    while (done < n) {
        s16 k = (s16)(n - done > 512 ? 512 : n - done);
        s16 r = my_fread(buf, 1, k, fp);
        if (r <= 0) break;
        huge_memcpy_fp(far_norm(far_lin(dst) + (u32)done), ds_ptr(buf), (u16)r);
        done += r;
    }
    stk_release(mk);
    return (s16)done;
}

/* sim_world (objects, clouds, spotting, special draws) */
WEAK u16 obj_alive(u16 o) { (void)o; return 1; }
WEAK u16 objtype_class(u16 s) { (void)s; return 0; }
WEAK u16 objtype_shape(u16 i) { (void)i; return 0xFFFF; }
WEAK u16 sun_dir(void) { return 0; }
WEAK u16 ap_sun_glare_583c(u16 a0, u16 a1, u32 a2, u16 a3, u16 a4) { (void)a0; (void)a1; (void)a2; (void)a3; (void)a4; return 0; }
WEAK u16 sun_in_cloud(u32 sun) { (void)sun; return 0; }
WEAK u16 point_in_cloud(u16 p) { (void)p; return 0; }
WEAK u16 cloud_blocks_segment(u16 a, u16 b) { (void)a; (void)b; return 0; }
WEAK void clouds_draw(u16 cam) { (void)cam; }
WEAK u16 segment_hits_boxes(u16 a0, u16 a1, u16 a2, u16 a3, u16 a4) { (void)a0; (void)a1; (void)a2; (void)a3; (void)a4; return 0; }
WEAK void flak_visible_test(FarPtr e, u16 eye) { (void)e; (void)eye; }
WEAK void ordnance_draw(FarPtr o) { (void)o; }
WEAK void parachute_draw(FarPtr o) { (void)o; }
