#pragma once
/* Platform module (platform.md): the parts of the Dynamix system library the skeleton already needs,
 * written once for the three programs through the shared-library layout (LW(G_x), symbols_layout.h),
 * plus the hardware/DOS models that replace interrupts and ports.
 *
 * Ported library functions carry the original addresses in their comment (INTRO / PS / AP). */
#include "codeptr.h"
#include "mem.h"

void platform_init(void);             /* once: host tick/keyboard/mouse handlers */
void platform_prog_start(void);       /* after a program is loaded: vectors unhooked */
void platform_prog_end(void);         /* after it exited: PORT: detach anything left hooked */

/* ---- Timer (platform.md §4), timer.c */
int  timer_install(int mult);         /* 05da:2374 / 16e3:2988 / 1d32:47c2 */
int  timer_restore(void);             /* 05da:23e1 / 16e3:29f5 / 1d32:482f */
int  timer_add(FarPtr fn, int rate);  /* 05da:2307 / 16e3:291b / 1d32:4755 */
int  timer_remove(int handle);        /* 05da:2351 / 16e3:2965 / 1d32:479f */
void timer_isr(void);                 /* 05da:241a / 16e3:2a2e / 1d32:4868: one IRQ0 */
int  is_tandy(void);                  /* 05da:2b08 / 16e3:311c / 1d32:4f56 */
bool timer_hooked(void);              /* INT 8 points at timer_isr */

/* ---- Keyboard (platform.md §3.3), kbd.c */
int  kbd_install(int hook_1c);        /* 05da:0014 / 16e3:62c9 / 1d32:0668 */
int  kbd_restore(void);               /* 05da:00d9 / 16e3:638d / 1d32:072d */
void kbd_isr(u8 raw);                 /* 05da:0117 / 16e3:63cb (INTRO/PS) / 1d32:075e (AP): one IRQ1 */
u16  key_read(void);                  /* 05da:03ab / 16e3:6658 (INTRO/PS) */
u16  key_queue_read(void);            /* 1d32:0939 (AP) */
int  kbd_dir_bits(int set);           /* 05da:03da / 16e3:6687 / 1d32:095e */
int  key_held(int scancode);          /* 05da:03f4 / 16e3:66a1 / 1d32:0978 */
u8   key_name_char(int scancode);     /* 1d32:098c (AP) */
/* BIOS services used while INT 9 is not hooked (fatal-error "press a key", kbhit/getch). */
bool bios_key_available(void);        /* INT 16h AH=01h */
u16  bios_key_get(void);              /* INT 16h AH=00h (pumps until a key arrives) */

/* ---- INT 33h mouse driver model, int33.c (platform.md §3.5.3). Coordinates are driver units; the
 * Dynamix library keeps them as 4 x pixels, so the host pixel position maps to x4/y4 clamped to the
 * range the program sets. The event handler (fn 0Ch) is called with AX = event mask, BX = buttons,
 * CX = x, DX = y; the port looks it up with codeptr and calls it as Int33Handler. */
typedef void (*Int33Handler)(u16 ax, u16 bx, u16 cx, u16 dx);
u16  int33_reset(u16 *buttons);       /* fn 00h: returns FFFFh (present), BX = 2 */
void int33_show(void);                /* fn 01h */
void int33_hide(void);                /* fn 02h */
void int33_get(u16 *buttons, u16 *x, u16 *y);   /* fn 03h */
void int33_set_pos(u16 x, u16 y);     /* fn 04h */
void int33_set_xrange(u16 min, u16 max);        /* fn 07h */
void int33_set_yrange(u16 min, u16 max);        /* fn 08h */
void int33_set_handler(u16 mask, FarPtr fn);    /* fn 0Ch */
void int33_set_ratio(u16 h, u16 v);   /* fn 0Fh */

/* ---- Game port 201h model, gameport.c (platform.md §3.4.6). Counts on the synthetic scale
 * raw = 200 + axis * 200 / 32767 (0..399, centre 200); 400 (timeout) for a missing stick. */
u8   gameport_in(void);               /* in al, 201h after firing: axis bits (1 = timing), buttons 4-7 */
void gameport_read_axes(u8 mask, u16 *si, u16 *di);   /* joy_read_axes' results (05da:3667) */
