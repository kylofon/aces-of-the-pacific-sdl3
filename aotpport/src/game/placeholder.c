/* PLACEHOLDER (phase 4): stand-ins for the three programs' main functions. They are NOT ports; they
 * exercise the skeleton end to end: the chain (0000:0510 marker, exit codes), the c0 start-up state
 * (argv, DGROUP), the shared-library layout (timer, keyboard, driver page variables), codeptr (timer
 * callbacks, the PS Ctrl+Esc hook, an AP stub thunk), EMS, and the VGA model (unchained pages, CRTC
 * flip, DAC). Each draws a test pattern and waits for Esc:
 *     INTRO --Esc--> exit(2) PS --Esc--> exit(3) AP --Esc--> exit(2) PS (from the sim) --Esc--> exit(0)
 * Headless: AOTP_KEYS="3:01,6:01,9:01,12:01" (see host.h). */
#include "game/game.h"

#include <stdio.h>
#include <string.h>

#include "codeptr.h"
#include "ems.h"
#include "host.h"
#include "mem.h"
#include "platform/platform.h"
#include "platform/vga.h"
#include "prog.h"
#include "symbols_ap.h"
#include "symbols_intro.h"
#include "symbols_ps.h"

/* ------------------------------------------------------------------ drawing helpers */

static const u8 font3x5[][6] = {          /* char, 5 rows of 3 bits */
    { 'A', 2, 5, 7, 5, 5 }, { 'B', 6, 5, 6, 5, 6 }, { 'D', 6, 5, 5, 5, 6 }, { 'E', 7, 4, 6, 4, 7 },
    { 'F', 7, 4, 6, 4, 4 }, { 'I', 7, 2, 2, 2, 7 }, { 'N', 6, 5, 5, 5, 5 }, { 'O', 7, 5, 5, 5, 7 },
    { 'P', 6, 5, 6, 4, 4 }, { 'R', 6, 5, 6, 5, 5 }, { 'S', 3, 4, 2, 1, 6 }, { 'T', 7, 2, 2, 2, 2 },
    { 'M', 5, 7, 7, 5, 5 }, { 'K', 5, 5, 6, 5, 5 }, { 'C', 7, 4, 4, 4, 7 }, { 'L', 4, 4, 4, 4, 7 },
};

static void fill(u8 *page, int x, int y, int w, int h, u8 c)
{
    for (int j = y; j < y + h && j < 200; j++)
        for (int i = x; i < x + w && i < 320; i++) page[j * 320 + i] = c;
}

static void text(u8 *page, int x, int y, int scale, const char *s, u8 c)
{
    for (; *s; s++, x += 4 * scale) {
        for (size_t k = 0; k < sizeof font3x5 / sizeof font3x5[0]; k++) {
            if (font3x5[k][0] != (u8)*s) continue;
            for (int r = 0; r < 5; r++)
                for (int b = 0; b < 3; b++)
                    if (font3x5[k][1 + r] & (4 >> b)) fill(page, x + b * scale, y + r * scale, scale, scale, c);
        }
    }
}

/* Palette: 0..63 a ramp in the program's colour, 64..79 fixed test colours, 255 white. */
static void set_palette(int prog)
{
    for (int i = 0; i < 64; i++)
        vga_dac_set((u8)i, prog == PROG_AP ? (u8)i : (u8)(i / 4), prog == PROG_PS ? (u8)i : (u8)(i / 4),
                    prog == PROG_INTRO ? (u8)i : (u8)(i / 4));
    static const u8 fixed[16][3] = { {0,0,0},{63,0,0},{0,63,0},{0,0,63},{63,63,0},{63,0,63},{0,63,63},{63,63,63},
                                     {32,0,0},{0,32,0},{0,0,32},{32,32,0},{32,0,32},{0,32,32},{32,32,32},{48,24,0} };
    for (int i = 0; i < 16; i++) vga_dac_set((u8)(64 + i), fixed[i][0], fixed[i][1], fixed[i][2]);
    vga_dac_set(255, 63, 63, 63);
}

static void pattern(u8 *page, int prog, const char *label, int y0)
{
    for (int y = y0; y < 200; y++)
        for (int x = 0; x < 320; x++) page[y * 320 + x] = (u8)((x + y) * 63 / 520);
    for (int i = 0; i < 16; i++) fill(page, 8 + i * 19, y0 + 8, 17, 20, (u8)(64 + i));
    text(page, 16, y0 + 40, 8, label, 255);
    for (int i = 0; i < prog; i++) fill(page, 16 + i * 24, 180, 16, 12, 66);   /* GCD code as bars */
}

/* The driver's page protocol on the shared variables (video.md §2.4, §3.8), through the layout. */
static void driver_reset_pages(void)
{
    LW(G_drv_page_front) = 0xA000;
    LW(G_drv_page_back) = 0xA400;
    LW(G_drv_page_bg) = 0xA800;
    LW(G_drv_page_read) = LW(G_drv_page_front);
    LW(G_drv_page_write) = LW(G_drv_page_back);
}

static void driver_flip(bool wait)
{
    u16 old_back = LW(G_drv_page_back);
    LW(G_drv_page_back) = LW(G_drv_page_front);
    LW(G_drv_page_front) = old_back;
    u16 start = (u16)(old_back << 4);
    vga_outw(0x3D4, (u16)((start & 0xFF00) | 0x0C));
    vga_outw(0x3D4, (u16)((start << 8) | 0x0D));
    if (wait) vga_wait_vretrace_start();
}

/* Waits for Esc (scan code 01), drawing the tick counter as a bar on the shown page. */
static void wait_esc(u16 ticks_ds, int shift, bool ap_queue)
{
    u32 last = 0xFFFFFFFFu;
    for (;;) {
        host_pump();
        u32 t = DSL(ticks_ds) >> shift;
        if (t != last) {
            last = t;
            u8 *page = vga_page(vga_shown_seg());
            fill(page, 0, 196, 320, 4, 64);
            fill(page, 0, 196, (int)(t % 320), 4, 71);
        }
        u16 k = ap_queue ? key_queue_read() : key_read();
        if ((k >> 8) == 0x01) return;
        if (!ap_queue && prog_current_id() == PROG_PS && DSB(PS_DS_quit_flag)) return;
        if (ap_queue && DSB(AP_DS_ap_quit_request)) return;
    }
}

static const char *arg(u16 argv_ds, int i) { return (const char *)DSP(DSW(argv_ds + 2 * i)); }

/* ------------------------------------------------------------------ timer callbacks / hooks */

static void intro_tick_cb(void) { DSL(INTRO_DS_intro_ticks) += 1; }          /* 0460:000b */
static void shell_tick(void) { DSL(PS_DS_step_clock_ps_done) += 1; }         /* 229e:0013 */
static void ap_tick(void) { DSL(AP_DS_tick_count) += 1; }                    /* 0000:02db */
static void kbd_break_hook(int x) { (void)x; }                              /* INTRO 05bb:0006 */
static void ctrl_esc_hook(int x)                                            /* PS 227c:0034 */
{
    if (x) prog_exit(0);                                  /* placeholder for shell_exit(0) */
    DSB(PS_DS_quit_flag) = 1;
}
static void ap_sim_exit_stub(void) { }                                      /* AP 4e0d:0bb0 (via stub) */

static void ems_free_everything(void)                                       /* AP atexit(24e5:00b6) */
{
    for (u16 h = 1; h < EMS_MAX_HANDLES; h++) ems_dealloc(h);
}

/* ------------------------------------------------------------------ INTRO */

int intro_main(int argc, u16 argv_ds)
{
    codeptr_register(PROG_INTRO, INTRO_FN_intro_tick_cb, intro_tick_cb);
    codeptr_register(PROG_INTRO, INTRO_FN_kbd_break_hook, (CodeFn)kbd_break_hook);

    /* mem_check (038e:091b): [0000:0512] << 4 >= 609 200 and >= 21 free EMS pages */
    u16 free_pages = 0;
    FarPtr v67 = ivt_get(0x67);
    bool ems = memcmp(mp(v67.seg, 0x0A), "EMMXXXX0", 8) == 0 && ems_get_page_counts(&free_pages, NULL) == 0;
    if (((u32)rd16(0, 0x512) << 4) < 0x94BB0u || !ems || free_pages < 21)
        host_fatal("INTRO placeholder: memory check failed");
    if (argc < 2 || strncmp(arg(argv_ds, argc - 1), "-n", 2) != 0) host_fatal("INTRO placeholder: no -n argument");

    vga_set_mode(0x13);                                   /* gfx_init: driver init sets the mode */
    vga_set_unchained();
    driver_reset_pages();
    timer_install(13);                                    /* snd_init */
    timer_add(codeptr_far(INTRO_FN_intro_tick_cb), 4);    /* 0460:0104 */
    kbd_install(0);

    set_palette(PROG_INTRO);
    pattern(vga_page(LW(G_drv_page_write)), PROG_INTRO, "INTRO", 0);
    driver_flip(true);                                    /* back page A400 becomes visible */
    host_snapshot_now("intro");
    wait_esc(INTRO_DS_intro_ticks, 0, false);

    kbd_restore();                                        /* sys_shutdown */
    timer_restore();
    /* end of main: make A000 the displayed page (video.md §4.2) */
    if (LW(G_drv_page_front) != 0xA000) {
        memcpy(vga_page(0xA000), vga_page(LW(G_drv_page_front)), 0x10000);
        LW(G_drv_page_back) = 0xA000;
        driver_flip(false);
    }
    return 2;                                             /* exit(2) -> PS */
}

/* ------------------------------------------------------------------ PS */

int ps_main(int argc, u16 argv_ds)
{
    (void)argc; (void)argv_ds;
    codeptr_register(PROG_PS, PS_FN_shell_tick, shell_tick);
    codeptr_register(PROG_PS, PS_FN_ctrl_esc_hook, (CodeFn)ctrl_esc_hook);

    u16 marker = rd16(0, 0x510);                          /* 048e:04a1 */
    if (marker == 0x29A) DSB(PS_DS_returned_from_sim) = 0;
    else if (marker == 0x3E7) DSB(PS_DS_returned_from_sim) = 1;
    else host_fatal("You can run Aces of the Pacific by typing 'AOTPCD' (marker %04X)", marker);
    wr16(0, 0x510, 0);

    vga_set_mode(0x13);
    vga_set_unchained();
    driver_reset_pages();
    timer_install(13);
    timer_add(codeptr_far(PS_FN_shell_tick), 1);          /* 048e:0097 */
    kbd_install(0);

    bool debrief = DSB(PS_DS_returned_from_sim) != 0;
    set_palette(PROG_PS);
    pattern(vga_page(LW(G_drv_page_write)), PROG_PS, debrief ? "DEBRIEF" : "PS", 0);
    driver_flip(true);
    host_snapshot_now(debrief ? "ps_debrief" : "ps");
    wait_esc(PS_DS_step_clock_ps_done, 2, false);

    kbd_restore();
    timer_restore();
    if (debrief || DSB(PS_DS_quit_flag)) return 0;       /* quit to DOS */
    /* shell_exit(1) (227c:0072): A000 displayed, marker, exit(3) */
    if (LW(G_drv_page_front) != 0xA000) {
        memcpy(vga_page(0xA000), vga_page(LW(G_drv_page_front)), 0x10000);
        LW(G_drv_page_back) = 0xA000;
        driver_flip(false);
    }
    wr16(0, 0x510, DSB(PS_DS_returned_from_sim) ? 0x3E7 : 0x29A);
    prog_exit(3);
}

/* ------------------------------------------------------------------ AP */

static bool ems_selftest(void)
{
    u16 h;
    if (ems_alloc(2, &h)) return false;
    bool ok = ems_map(0, 0, h) == 0;
    memset(mp(EMS_FRAME_SEG, 0), 0x55, 0x4000);
    ok = ok && ems_map(0, 1, h) == 0;
    memset(mp(EMS_FRAME_SEG, 0), 0xAA, 0x4000);
    ok = ok && ems_save_map(h) == 0 && ems_map(0, 0, h) == 0 && rd8(EMS_FRAME_SEG, 0x3FFF) == 0x55;
    ok = ok && ems_restore_map(h) == 0 && rd8(EMS_FRAME_SEG, 0x1234) == 0xAA;
    return ems_dealloc(h) == 0 && ok;
}

int ap_main(int argc, u16 argv_ds)
{
    codeptr_register(PROG_AP, 0x000002DBu, ap_tick);      /* 0000:02db, the 236.69 Hz counter */
    codeptr_register(PROG_AP, AP_FN_sim_exit, ap_sim_exit_stub);
    bool debug = argc > 1 && strcmp(arg(argv_ds, 1), "nlkle") == 0;

    /* EMS (50c8:0008): >= 19 free pages, tier 3/4 */
    FarPtr v67 = ivt_get(0x67);
    u16 pages = 0;
    if (memcmp(mp(v67.seg, 0x0A), "EMMXXXX0", 8) != 0 || ems_get_page_counts(&pages, NULL) || pages < 19)
        host_fatal("At least 112K EMS memory required to run.");
    prog_atexit(ems_free_everything);
    DSB(AP_DS_ems_tier) = pages < 33 ? 3 : 4;
    DSW(AP_DS_ems_spare_pages) = (u16)(pages - (pages < 33 ? 21 : 33));
    if (!debug) {
        u16 marker = rd16(0, 0x510);
        if (marker != 0x29A && marker != 0x3E7) return 1;   /* not started through the chain -> INTRO */
        wr16(0, 0x510, 0);
    }

    /* Self-tests of the skeleton: EMS copy model, codeptr through a VROOMM stub (3cd3:0043 -> sim_exit). */
    bool ems_ok = ems_selftest();
    u16 slot = stk_alloc(4);
    ds_far_wr(slot, far_make(SEG(0x3CD3), 0x0043));
    bool thunk_ok = codeptr_lookup(ds_far(slot)) == (CodeFn)ap_sim_exit_stub;
    bool code_ok = code_rd8(SEG(0x50C8), 0x0008) == 0x55;  /* AP main starts with push bp */

    /* AP keeps PS's mode and video memory (drv hw_present = 0, video.md §2.3): draw the lower half only */
    driver_reset_pages();
    timer_install(13);
    timer_add(codeptr_far(0x000002DBu), 1);
    kbd_install(0);
    set_palette(PROG_AP);
    u8 *front = vga_page(LW(G_drv_page_front));
    pattern(front, PROG_AP, "AP", 100);
    fill(front, 200, 150, 30, 20, ems_ok ? 66 : 65);
    fill(front, 240, 150, 30, 20, thunk_ok ? 66 : 65);
    fill(front, 280, 150, 30, 20, code_ok ? 66 : 65);
    if (host_trace())
        fprintf(stderr, "[ap] EMS %u free pages, tier %u, EMS self-test %s, stub thunk %s, overlay code %s\n",
                pages, DSB(AP_DS_ems_tier), ems_ok ? "ok" : "FAILED", thunk_ok ? "ok" : "FAILED", code_ok ? "ok" : "FAILED");
    host_snapshot_now("ap");
    wait_esc(AP_DS_tick_count, 2, true);

    kbd_restore();
    timer_restore();
    wr16(0, 0x510, 0x3E7);                                /* sim_exit(2, 0) */
    prog_exit(2);
}
