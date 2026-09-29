#pragma once
/* PORT: key bindings and the flaps up / flaps down keys (keymap.c; the launcher's Settings > Key Bindings).
 * A key is an XT set-1 make code, KEYMAP_GREY = sent after an E0 prefix, with the modifiers held with it.
 * The flaps up / down keys reach AP as two scancodes no keyboard sends (no ASCII, no direction bits in its
 * tables), which controls_map turns into two new commands. */
#include "types.h"

#define KEYMAP_GREY  0x0100
#define KEYMAP_SHIFT 0x1000
#define KEYMAP_CTRL  0x2000
#define KEYMAP_ALT   0x4000
#define KEYMAP_FLAPS_UP    0x55
#define KEYMAP_FLAPS_DOWN  0x56
#define KEYMAP_CMD_FLAPS_UP    0x60
#define KEYMAP_CMD_FLAPS_DOWN  0x61

/* main.c --keys "name=code,...": the actions not on their default keys (code 0 = no key). False if the
 * list can't be read. */
bool keymap_parse(const char *spec);
/* host.c key_event: key x went down / up. Returns -1 to send x as it is, or the number of keys put in
 * out[] (at most 16; 0x80 = break, KEYMAP_GREY = E0 prefix) to send instead. */
int keymap_map(u16 x, bool down, u16 *out);
void keymap_focus_lost(void);          /* kbd.c: every key counts as up */
