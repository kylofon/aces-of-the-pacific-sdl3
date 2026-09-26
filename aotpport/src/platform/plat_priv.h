#pragma once
/* Internal glue between the platform files (not for game code). */
#include "platform/platform.h"

void timer_host_tick(void);           /* timer.c: host 236.69 Hz tick */
void timer_unhook(void);
void kbd_host_byte(u8 raw);           /* kbd.c: one byte from the keyboard (port 60h) */
void kbd_host_focus_lost(void);
void kbd_unhook(void);
void int33_host_event(int x, int y, u8 buttons);   /* int33.c: host mouse state changed */
void int33_unhook(void);
