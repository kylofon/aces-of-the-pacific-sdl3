/* Temporary weak stubs for sim_flow functions that sim_world part B (the AI) calls and that are not built
 * yet (PORT_BRIEF.md). Every stub is __attribute__((weak)); the real implementation replaces it. */
#include "sim_world/swb_priv.h"

#define WEAK __attribute__((weak))

int sim_world_b_stubs_anchor;

