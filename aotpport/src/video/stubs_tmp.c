/* TEMPORARY weak stubs for functions of other modules that video calls (PORT_BRIEF.md): every stub is
 * __attribute__((weak)) so the real implementations replace them when they land. The platform ones
 * are minimal working versions on the mem.h DOS arena so that the video dev tests run meanwhile. */
#include "video/vid_priv.h"

#include <stdio.h>
#include <math.h>
#include <string.h>

#include "platform/platform.h"
#include "platform/rtl.h"
#include "render3d/render3d.h"
#include "shell_data/shell_data.h"
#include "sim_flow/sim_flow.h"
#include "sound/sound.h"

#define WEAK __attribute__((weak))

/* ---- platform: DOS memory (platform.md §5.1) */
WEAK FarPtr dos_alloc(u32 size, u16 a1, u16 flags)
{
    (void)a1;
    if (size == 0xFFFFFFFFu) { u16 l = dos_mem_largest(); u32 b = (u32)l << 4; return far_make((u16)(b >> 16), (u16)b); }
    u16 par = (u16)((u16)(size >> 4) + ((size & 0xF) != 0));
    u16 seg;
    if (!dos_mem_alloc(par, &seg)) return far_make(0, 0);
    if (flags & 1) memset(mp(seg, 0), 0, size);
    return far_make(seg, 0);
}
WEAK void dos_free(FarPtr p) { dos_mem_free(p.seg); }

/* ---- platform: BIOS text mode (05da:5f48) */
WEAK void bios_set_text_mode(u16 a0)
{
    wr8(0x40, 0x10, (u8)((rd8(0x40, 0x10) & 0xCF) | (u8)(a0 << 4)));
    vga_set_mode(0x03);
}

/* ---- platform: bitmap table free (05da:539d): free(bmp[0]); free(bmp) */
WEAK void bmp_free_table(u16 p0_ds) { (void)p0_ds; }
/* ---- render3d (approximations until render3d lands; only the rotated-sprite paths use them) */
WEAK u16 cos16(u16 a) { return (u16)(s16)lround(cos(a * (6.283185307179586 / 65536.0)) * 16384.0); }
WEAK s16 sin16(u16 a) { return (s16)lround(sin(a * (6.283185307179586 / 65536.0)) * 16384.0); }
WEAK u16 mul_shr10(u16 a, u16 b) { return (u16)(((s32)(s16)a * (s16)b) >> 10); }
WEAK u16 bitmap_global(s16 i) { (void)i; return 0; }

/* ---- shell_data (PS) */
WEAK void ttm_hook(s16 n) { (void)n; }
WEAK s16 tmr_expired(u16 t_ds) { (void)t_ds; return 1; }          /* PS: always expired (video_ttm.md §12.5) */

/* ---- sim_flow (AP) */
WEAK s16 key_or_click(void) { return 0; }
WEAK void wait_key_release(void) {}
WEAK u16 res_name(u16 p0_ds, u16 p1_ds) { (void)p1_ds; return p0_ds; }
WEAK void banner_text(u16 s_ds) { (void)s_ds; }
WEAK s16 dt_scale(s16 a0) { return a0; }
WEAK void item_center(FarPtr it) { (void)it; }
WEAK s16 vcr_panel_mouse_show(void) { return 0; }
WEAK void vcr_panel_mouse_hide(void) {}
WEAK void vcr_poll_panel(void) {}

int video_stubs_anchor;                          /* MinGW: a plain global so the weak stubs link */
