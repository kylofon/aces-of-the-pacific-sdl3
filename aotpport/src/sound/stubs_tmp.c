/* Temporary weak stubs for functions of other modules that the sound module calls (PORT_BRIEF.md):
 * every stub is __attribute__((weak)) so the real implementation replaces it when it lands. They
 * return "failure" (no file, no memory, expired timers) so the sound code degrades to silence. */
#include "sound/snd_priv.h"

#include "platform/platform.h"
#include "render3d/render3d.h"
#include "sim_flow/sim_flow.h"

#define WEAK __attribute__((weak))

/* MinGW (PE-COFF) names a weak definition's alias after another global of the same object file; two
 * stub files whose weak symbols have no other global collide ("multiple definition of .weak.f.").
 * This non-weak anchor gives this file's aliases a unique name. */
int sound_stubs_tmp_anchor;

/* platform: volumes, chunks, packed streams (platform_resources.md §6) */
WEAK u16 my_fopen(u16 name_ds, u16 mode_ds) { return 0; }
WEAK s16 my_fclose(u16 f) { return 0; }
WEAK s16 my_fread(u16 buf_ds, s16 size, s16 n, u16 f) { return 0; }
WEAK s16 my_fseek(u16 f, s32 off, s16 whence) { return -1; }
WEAK s32 my_filelength(u16 f) { return 0; }
WEAK u16 chunk_open(u16 name_ds) { return 0; }
WEAK s32 chunk_find(u16 h, u16 path_ds, s16 n) { return -1; }
WEAK s32 chunk_size(u16 h) { return -1; }
WEAK s16 chunk_close(u16 h) { return 0; }
WEAK s16 chunk_is_open(u16 h) { return 0; }
WEAK s16 pk_open(s16 method, u16 f, u16 mode_ds, u32 packed_size) { return -1; }
WEAK u16 pk_close(s16 id) { return 0; }
WEAK u16 pk_read(s16 id, FarPtr dst, u16 n) { return 0xFFFF; }
WEAK s32 pk_size(s16 id) { return -1; }
WEAK u16 pk_seek(s16 id, s32 off, s16 whence) { return 0xFFFF; }

/* platform: memory */
WEAK FarPtr dos_alloc(u32 size, u16 a1, u16 flags) { FarPtr p = { 0, 0 }; return p; }
WEAK void dos_free(FarPtr p) {}
WEAK void huge_memset(u16 off, u16 seg, u16 val, u16 size_lo, u16 size_hi)
{
    u32 n = (u32)size_hi << 16 | size_lo;
    u32 a = far_lin(far_make(seg, off));
    for (u32 i = 0; i < n && a + i < MEM_SIZE; i++) mem[a + i] = (u8)val;
}
WEAK u16 intro_lib_malloc(u16 n) { return 0; }
WEAK u16 lib_realloc(u16 n) { return 0; }
WEAK u16 safe_malloc(u16 n) { return 0; }
WEAK void intro_lib_free(u16 p) {}
WEAK void lib_free(u16 p) {}
WEAK u16 mem_new(u16 n, u16 tag_ds, u16 what_ds, s16 line) { return 0; }
WEAK u16 far_to_near_str(FarPtr s) { return 0; }
WEAK s16 assert_fail(FarPtr file, s16 line, u16 p2_ds) { return 0; }

/* render3d: near pools (token lists) and math used by sx_sim */
WEAK u16 pool_create_near(u16 n, u16 size) { return 0; }
WEAK u16 pool_alloc_zero_near(u16 hdr) { return 0; }
WEAK void pool_free2(u16 hdr, u16 item) {}
WEAK u16 pool_next_near(u16 hdr, u16 prev) { return 0; }
WEAK u32 ldist3(u16 a0, u16 a1, u16 a2, u16 a3, u16 a4, u16 a5) { return 0; }
WEAK s16 ldiv_sat(s32 a, s16 b) { return b ? (s16)(a / b) : 0; }
WEAK u16 ladd_v(u16 dst_ds, u16 src_ds) { return dst_ds; }
WEAK s16 clamp(s16 v, s16 lo, s16 hi) { return v < lo ? lo : v > hi ? hi : v; }

/* sim_flow: timeouts (4b31) */
WEAK s16 timeout_expired(u16 t_ds) { return 1; }
WEAK void timeout_expire(u16 t_ds) {}
