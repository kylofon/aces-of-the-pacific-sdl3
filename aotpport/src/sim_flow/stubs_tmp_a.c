/* Temporary weak stubs for the sim_flow part B functions (VCR/tape/codec, dialogs, the dialog library,
 * preferences, realism, sliders, stdalert, bstream) that part A calls (PORT_BRIEF.md). Every stub is
 * __attribute__((weak)); part B's real implementation replaces it. The session driver below flies
 * one single/career mission without the VCR (no recording, no end-of-mission dialog). */
#include "sim_flow/sfa_priv.h"

#define WEAK __attribute__((weak))

int sim_flow_a_stubs_anchor;

/* ---- sliders (5613): the slider records DS:074E + 32·i {lo, hi, range, ?, pos (+6), …} */
/* 5613:00bc slider_map */
static s16 slider_map(s16 v, s16 a0, s16 a1, s16 b0, s16 b1)
{
    s16 da = (s16)(a1 - a0), db = (s16)(b1 - b0);
    s16 ada = da == (s16)0x8000 ? 0x7FFF : (da < 0 ? (s16)-da : da);
    s16 adb = db == (s16)0x8000 ? 0x7FFF : (db < 0 ? (s16)-db : db);
    if (adb < ada) {
        s16 d = (s16)(ada - 1);
        if (db < 0) d = (s16)-d;
        return (s16)(ldiv_sat((s32)(s16)(v - a0) * db + d, da) + b0);
    }
    return lerp_map(v, a0, a1, b0, b1);
}
WEAK s16 slider_lo(s16 i) { return DSS((u16)(0x074E + 32 * i)); }
WEAK s16 slider_hi(s16 i) { return DSS((u16)(0x0750 + 32 * i)); }
WEAK s16 slider_value(s16 i)
{
    u16 r = (u16)(0x074E + 32 * i);
    return slider_map(DSS(r + 6), 0, DSS(r + 4), DSS(r), DSS(r + 2));
}
WEAK s16 slider_set(s16 i, s16 v)
{
    u16 r = (u16)(0x074E + 32 * i);
    DSW(r + 6) = (u16)slider_map(v, DSS(r), DSS(r + 2), 0, DSS(r + 4));
    return DSS(r + 6);
}
WEAK void sliders_load(u16 name_ds)
{
    DSW(0x074E) = 0x50;                       /* lo(0) = 80, hi(0) = 20 (5613:0068; no bitmaps here) */
    DSW(0x0750) = 0x14;
}
WEAK void iff_write(u16 name_ds) {}

/* ---- dialog library / dialogs */
WEAK void savebuf_alloc(void) {}
WEAK void savebuf_free(void) {}
WEAK u16 pointer_buf_alloc(u16 a0) { return 1; }
WEAK void inset_box_item(FarPtr it) {}
WEAK void window_frame_title(FarPtr it, FarPtr title) {}
WEAK void framed_panel(FarPtr it) {}
WEAK void button_up_c(FarPtr it) {}
WEAK void button_down_c(FarPtr it) {}
WEAK void ap_rect_shrink(u16 r_ds, s16 d) {}
WEAK void ap_rect_restore(u16 r_ds) {}
WEAK void mouse_show_over(void) {}
WEAK s16 mouse_over_panel(void) { return 0; }
WEAK void dlg_activate(FarPtr items, s16 n) {}
WEAK void dlg_force_redraw(void) {}
WEAK s16 dlg_poll(void) { return 9; }
WEAK void tl_init(u16 a0, u16 a1, u16 a2) {}
WEAK u16 tl_format(u32 a0, u16 a1, u32 a2) { return 0; }
WEAK void flight_message(u16 s_ds) {}

/* ---- preferences / realism */
WEAK void prefs_init(void) {}
WEAK s16 prefs_dialog(void) { return 0; }
WEAK void toggle_joystick(void) {}
WEAK void toggle_mouse(void) {}
WEAK void toggle_sound(void) {}
WEAK void realism_timer(void) {}
WEAK void realism_init(void) {}
WEAK void realism_dlg_init(void) {}
WEAK void realism_bind(u16 r_ds) {}
WEAK s16 realism_dialog_in_flight(void) { return 0; }
WEAK s16 ap_realism_percent(void) { return 100; }

/* ---- stdalert */
WEAK s16 plane_in_trouble(u16 p_ds) { return 0; }
WEAK u16 end_danger(u16 p_ds) { return 0; }
WEAK s16 end_prompt(void) { return 5; }                 /* "end mission" -> flight_keys returns 3 */
WEAK void end_reset(void) {}
WEAK void end_init(void) {}
WEAK u32 quit_box(u16 a0) { return 0; }
WEAK void quit_box_close(u32 h) {}

/* ---- VCR */
WEAK s16 vcr_put(s16 type, u16 ptr_ds) { return 0; }
WEAK s16 vcr_put_data(s16 sub, s16 len, u16 ptr_ds, ...) { return 0; }
WEAK void vcr_redraw_all(void) {}
WEAK s16 vcr_is_playing(void) { return 0; }
WEAK void vcr_world_reset(void) {}
WEAK void vcr_sound_idle(void) {}
WEAK s16 director_mode(s16 set) { return 0; }
/* 5b93:003f: the clip rectangle below the VCR panel */
WEAK void vcr_clip_full(void)
{
    DSW(0x26C4) = 0;
    DSB(0x26C3) = 1;
    DSW(0x26C6) = (u16)(DSW(AP_DS_drv_scr_w) - 1);
    DSW(0x26C8) = 0x79;
    DSW(0x26CA) = (u16)(DSW(AP_DS_drv_scr_h) - 1);
}
/* 5c5f:0083 */
WEAK void vcr_world_init_hook(void)
{
    redraw_all();
    DSW(0x4E56) = 0;
    set_panel_top((s16)(DSS(AP_DS_drv_scr_h) - 1));
    controls_reset();
    DSL(0x4E1C) = 30000;
    clock_reset();
    DSB(0x4E6F) = 0;
    end_prompt_reset();
}

/* 618d:0067 load_script_file(name, &p, &n): the whole file into a far block DS:5010, length DS:5014 */
WEAK s16 load_script_file(u16 name, u16 p_ds, u16 n_ds)
{
    u16 f = my_fopen(name, 0x05EB /* "rb" */);
    if (!f) assert_fail(far_make(SEG(0x394C), 0), 0xAB, name);
    DSW(0x5014) = (u16)my_filelength(f);
    ds_far_wr(0x5010, mem_far_new((u32)(s32)DSS(0x5014), 0));
    ap_fread_far_55a4(ds_far(0x5010), (s32)DSS(0x5014), f);
    my_fclose(f);
    DSL(p_ds) = DSL(0x5010);
    DSW(n_ds) = DSW(0x5014);
    return 1;
}
/* 618d:00fb */
WEAK s16 free_script(void)
{
    mem_far_delete(ds_far(0x5010));
    DSW(0x5014) = 0;
    return 0;
}

/* 5c9b:0000 vcr_session — PORT (part A stand-in): state 1 only (fly the SIM.IN/SCRIPT.DAT mission,
 * then END MISSION: SIM.OUT, teardown); no recording, film or end dialog. */
WEAK s16 vcr_session(s16 sim_mode)
{
    u16 m = stk_mark();
    u16 p = stk_alloc(4), n = stk_alloc(2);
    s16 ret = 1;
    DSW(0x4010) = 0;
    DSB(AP_DS_vcr_session_mode) = (u8)sim_mode;
    DSB(0x4E01) = 0;
    if (sim_mode == 0 || sim_mode == 1) {
        file_load(0x4E2E, 0x0D, 1, 0x0932 /* "sim.in" */);
        DSW(0x51EC) = DSB(0x4E35) & 1;
    }
    DSW(0x4010) = 1;
    load_script_file(DSW(0x0534), p, n);
    ap_mission_load(ds_far(p), DSW(n));
    DSB(0x0886) = 0;
    mission_start();
    s16 r = flight_loop();
    if (r == 0) ret = 0;
    results_write();
    mission_end();
    mission_unload();
    free_script();
    stk_release(m);
    return ret;
}
