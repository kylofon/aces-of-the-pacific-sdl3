/* sim_flow: vcr_tape.c (618d) — sim_flow_vcr.md §5. Part A implements module_flags (called from the
 * world set-up and the autopilot); the rest of the file is part B's. */
#include "sim_flow/sfa_priv.h"

/* AP 618d:04e4 module_flags(bits): bits != 0 -> DS:0BDC | bits (not stored: verified quirk);
 * bits == 0 -> DS:0BDC, then cleared */
u16 module_flags(u16 bits)
{
    if (bits) return (u16)(bits | DSW(0x0BDC));
    u16 r = DSW(0x0BDC);
    DSW(0x0BDC) = 0;
    return r;
}
