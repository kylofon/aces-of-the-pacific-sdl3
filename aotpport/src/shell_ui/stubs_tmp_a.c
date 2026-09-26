/* shell_ui part A: TEMPORARY weak stand-ins for part-B functions the part-A files call, until part B
 * delivers them (PORT_BRIEF.md). Every stub is weak; the real definitions override them. */
#include "shell_ui/sui_a_priv.h"

int shell_ui_a_stubs_anchor;

__attribute__((weak)) void best_init(void) { }
__attribute__((weak)) void best_missions(void) { }
__attribute__((weak)) void best_career_remove(void) { }
__attribute__((weak)) void brief_init(void) { }
__attribute__((weak)) void briefing(u16 variant) { (void)variant; }
__attribute__((weak)) void events_init_fonts(void) { }
__attribute__((weak)) void fd_init(void) { }
__attribute__((weak)) void fm2_links_init(void) { }
__attribute__((weak)) void flyhist_run(void) { }
__attribute__((weak)) u16 flymiss2_setup(u16 type, u16 arg) { (void)type; (void)arg; return 0; }
__attribute__((weak)) u16 custom_missions(void) { return 0; }
__attribute__((weak)) u16 custmiss_exist(void) { return 0; }
