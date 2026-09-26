/* Temporary weak stubs for sim_flow functions that sim_world part B (the AI) calls and that are not built
 * yet (PORT_BRIEF.md). Every stub is __attribute__((weak)); the real implementation replaces it. */
#include "sim_world/swb_priv.h"

#define WEAK __attribute__((weak))

int sim_world_b_stubs_anchor;

WEAK void radio_queue5(u16 a0, u16 a1, u16 a2) {}          /* 1815:06d0 (sim_flow/messages.c) */
WEAK u32 vcr_frame(void) { return 0; }                     /* 5d3c:0064 (sim_flow/frame.c) */
WEAK u16 module_flags(u16 bits) { return 0; }              /* 618d:04e4 (sim_flow/vcr_tape.c) */
WEAK s16 addon1_flag(void) { return DSW(0x51EC); }         /* 6a63:0000 (sim_flow/vcr_codec.c): DS:51EC */
