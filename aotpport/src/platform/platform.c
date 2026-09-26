/* Platform glue: host handlers and the per-program hardware state. */
#include "platform/plat_priv.h"

#include "host.h"

void platform_init(void)
{
    host_set_tick_handler(timer_host_tick);
    host_set_kbd_handler(kbd_host_byte);
    host_set_focus_lost_handler(kbd_host_focus_lost);
    host_set_mouse_handler(int33_host_event);
}

void platform_prog_start(void)
{
    timer_unhook();
    kbd_unhook();
    int33_unhook();
}

/* Every program calls sys_shutdown (kbd_restore, mouse_shutdown, timer_restore) before exit. A vector
 * left pointing into a terminated program would crash DOS; PORT: the chain loop unhooks them. The EMS,
 * the VGA state (mode, pages, DAC) and low memory survive, as in the original. */
void platform_prog_end(void)
{
    timer_unhook();
    kbd_unhook();
    int33_unhook();
    host_set_sound_service(NULL);
}
