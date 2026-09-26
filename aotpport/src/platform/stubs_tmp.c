/* TEMPORARY weak stand-ins for other modules' functions the platform module calls, until those
 * modules exist (PORT_BRIEF.md). Every stub is __attribute__((weak)); the real implementations
 * override them. */
#include "platform/rtl_priv.h"

#include "sound/sound.h"
#include "video/video.h"

int platform_stubs_anchor;     /* MinGW: a plain global next to the weak ones */

__attribute__((weak)) s16 gfx_restore_text(void) { return 0; }
__attribute__((weak)) void snd_shutdown(void) { }
__attribute__((weak)) s16 snd_unload(s16 sel) { (void)sel; return 0; }
__attribute__((weak)) void sx_shutdown(void) { }

#include "shell_data/shell_data.h"
#include "shell_ui/shell_ui.h"

__attribute__((weak)) void ace_close(void) { }
__attribute__((weak)) void air_close(void) { }
__attribute__((weak)) void ord_close(void) { }
__attribute__((weak)) void station_close(void) { }
__attribute__((weak)) void best_career_insert(void) { }
__attribute__((weak)) void pilot_store(void) { }
__attribute__((weak)) void dialogs_init(void) { }
__attribute__((weak)) void gfx_flip(s16 wait) { (void)wait; }
__attribute__((weak)) s16 gfx_init(s16 code, s16 unused, u16 file_ds) { (void)unused; (void)file_ds; return code ? code : 8; }
__attribute__((weak)) void main_menu(void) { }
__attribute__((weak)) void parts_load(void) { }
__attribute__((weak)) void plate_buf_alloc(void) { }
__attribute__((weak)) void plate_buf_free(void) { }
__attribute__((weak)) void please_wait(void) { }
__attribute__((weak)) void pref_apply_all(void) { }
__attribute__((weak)) void ps_fonts_load(void) { }
__attribute__((weak)) void scr_init(void) { }
__attribute__((weak)) void screen_show(u16 id, u16 scd_arg, u16 defer_pal) { (void)id; (void)scd_arg; (void)defer_pal; }
__attribute__((weak)) void screens_load(void) { }
__attribute__((weak)) void script_write(s8 resume) { (void)resume; }
__attribute__((weak)) void shell_data_load(void) { }
__attribute__((weak)) void shell_data_save(void) { }
__attribute__((weak)) void sim_end(void) { }
__attribute__((weak)) void sim_in_build_write(void) { }
__attribute__((weak)) s16 snd_init(s16 drv, u16 ovl_ds) { (void)drv; (void)ovl_ds; return 1; }
__attribute__((weak)) s16 snd_load_resource(u16 file_ds, s16 id) { (void)file_ds; (void)id; return 0; }
__attribute__((weak)) s16 snd_play(s16 id) { (void)id; return 0; }

/* ---- loaders.c / ap_main.c / config.c / intro_main.c / emm_pool.c */
#include "host.h"
#include "sim_flow/sim_flow.h"

static void stub_no_driver(void) { host_fatal("stubs_tmp: video driver entry called before video exists"); }
__attribute__((weak)) CodeFn drv_entry(int n) { (void)n; return stub_no_driver; }
__attribute__((weak)) void far_copy(FarPtr dst, FarPtr src, u16 n) { far_memmove_fp(dst, src, n); }
__attribute__((weak)) s16 gfx_cache_upload(u16 list_ds) { (void)list_ds; return 0; }
__attribute__((weak)) void gfx_ega_restore(void) { }
__attribute__((weak)) s16 gfx_font_valid(s16 slot)
{
    return slot >= 1 && slot <= 19 && !far_is_null(ds_far((u16)(lds(G_font_glyphs) + 4 * slot)));
}
__attribute__((weak)) void gfx_nib_put(FarPtr src, u16 xb, u16 y, u16 w, u16 rows) { (void)src; (void)xb; (void)y; (void)w; (void)rows; }
__attribute__((weak)) void gfx_nib_or_hi(FarPtr src, u16 xb, u16 y, u16 w, u16 rows) { (void)src; (void)xb; (void)y; (void)w; (void)rows; }
__attribute__((weak)) u32 gfx_rect_size(u16 w, u16 h) { return (u32)w * h; }
__attribute__((weak)) void gfx_sprite_flip(u16 f_ds, s16 x, s16 y, s16 flags) { (void)f_ds; (void)x; (void)y; (void)flags; }
__attribute__((weak)) void gfx_sprite_rotated_ind(u16 f_ds, s16 x, s16 y, u16 angle, s16 w, s16 h, s16 px, s16 py)
{ (void)f_ds; (void)x; (void)y; (void)angle; (void)w; (void)h; (void)px; (void)py; }
__attribute__((weak)) void gfx_sprite_scaled(u16 f_ds, s16 x, s16 y, s16 flags, s16 w, s16 h)
{ (void)f_ds; (void)x; (void)y; (void)flags; (void)w; (void)h; }
__attribute__((weak)) void mtx_free_row(s16 r) { (void)r; }
__attribute__((weak)) void mtx_free_rows(void) { }
__attribute__((weak)) void read_front(void) { }
__attribute__((weak)) void write_back(void) { }
__attribute__((weak)) void copy_screen(void) { }
__attribute__((weak)) u16 vqt_begin(FarPtr stream) { (void)stream; return 0; }
__attribute__((weak)) void vqt_end(void) { }
__attribute__((weak)) void vqt_mem_node(u16 x, u16 y, u16 w, u16 h) { (void)x; (void)y; (void)w; (void)h; }
__attribute__((weak)) void vqt_scr_node(u16 x, u16 y, u16 w, u16 h) { (void)x; (void)y; (void)w; (void)h; }
__attribute__((weak)) s16 snd_disable(s16 cls) { (void)cls; return 0; }
__attribute__((weak)) void intro_sequence(void) { }
__attribute__((weak)) void real_apply_preset(u16 dst_ds, u16 p) { (void)p; rtl_setmem_ds(dst_ds, 16, 0); }
__attribute__((weak)) u16 res_add_ext(u16 name_ds, u16 ext_ds) { (void)ext_ds; return name_ds; }
__attribute__((weak)) s32 ap_fread_far_4bb7(FarPtr dst, s32 size, s32 count, u16 f_ds) { return my_hread(dst, size, count, f_ds); }
__attribute__((weak)) s16 ap_file_exists(u16 path_ds) { (void)path_ds; return 0; }
__attribute__((weak)) u16 calib_ptr(s16 a0) { return (u16)(0x6000 + 12 * a0); }   /* scratch DS words */
__attribute__((weak)) void controls_apply(void) { }
__attribute__((weak)) void joy_flight_set(s16 a0) { (void)a0; }
__attribute__((weak)) void mouse_flag_set(s16 a0) { (void)a0; }
__attribute__((weak)) void file_load(u16 buf_ds, s16 size, s16 count, u16 name_ds) { (void)buf_ds; (void)size; (void)count; (void)name_ds; }
__attribute__((weak)) void sim_init(void) { }
__attribute__((weak)) void sim_shutdown(void) { }
__attribute__((weak)) void simprefs_save(void) { }
__attribute__((weak)) s16 vcr_session(s16 sim_mode) { (void)sim_mode; return 0; }
