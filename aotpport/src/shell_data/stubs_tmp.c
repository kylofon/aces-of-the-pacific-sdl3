/* shell_data: temporary weak stubs for shell_ui functions that shell_data calls. service_side and
 * res_add_ext are exact transcriptions (0f67:02ed, 125a:000f) because file names and the mission
 * generator depend on them; the owners' real definitions replace them. */
#include "shell_data/sd_priv.h"
#include "shell_ui/shell_ui.h"

int shell_data_stubs_anchor;

/* ---- shell_ui */

/* PS 0f67:02ed service_side(char s) -> char */
__attribute__((weak)) u16 service_side(u16 s)
{
    s8 c = (s8)s;
    s8 r;
    if (c <= 2) r = 1;
    else if (c <= 4) r = 0;
    else if (c <= 7) r = 2;
    else if (c == 8) r = 3;
    else if (c == 9) r = 4;
    else if (c == 10) r = 5;
    else r = -1;
    return (u16)(s16)r;
}

__attribute__((weak)) u16 menu_hotkey(u16 scan) { (void)scan; return 0; }
__attribute__((weak)) void dev_chdir(u16 dir) { (void)dir; }
__attribute__((weak)) void dev_chdir_up(void) { }
__attribute__((weak)) void event_ttm_text_hook(void) { }

/* PS 125a:000f res_add_ext(name, ext) — strcat(name, "."), strcat(name, ext); DS:0DFF == 0 (no
 * volumes): "ext\name" in DS:4B94 (shell_data.md §2) */
__attribute__((weak)) u16 res_add_ext(u16 name_ds, u16 ext_ds)
{
    u16 m = stk_mark();
    rtl_strcat(name_ds, sd_lit("."));
    rtl_strcat(name_ds, ext_ds);
    stk_release(m);
    if (DSB(0x0DFF) == 0) {
        rtl_strcpy(0x4B94, ext_ds);
        u16 m2 = stk_mark();
        rtl_strcat(0x4B94, sd_lit("\\"));
        stk_release(m2);
        rtl_strcat(0x4B94, name_ds);
        return 0x4B94;
    }
    return name_ds;
}
