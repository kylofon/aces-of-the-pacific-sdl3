/* sim_flow: vcr_codec.c (6a63, the VCR frame codec) — sim_flow_vcr.md §4. Part A implements
 * addon1_flag (read by the radio menu and the AI); the rest of the file is part B's. */
#include "sim_flow/sfa_priv.h"

/* AP 6a63:0000 addon1_flag -> DS:51EC (SIM.IN +7 bit 0) */
s16 addon1_flag(void)
{
    return DSS(0x51EC);
}
