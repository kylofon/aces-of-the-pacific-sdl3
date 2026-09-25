"""Function index for the Aces of the Pacific executables (INTRO.EXE, PS.EXE, AP_flat.exe).

All three are Borland C++ 3.0 large-model programs (AP.EXE after tools/unovl.py). Segments come from
the MZ relocation table. A relocated segment value is a CODE segment when it is the target of a
relocated `call far` / `jmp far`, the entry segment, or an overlay stub (starts `CD 3F`); the other
relocated values below DGROUP are far data segments (per-module data, e.g. the `__FILE__` strings of
asserts). In AP_flat the overlay code placed after the resident image (above DGROUP) is code too.

Recursive-descent disassembly (Capstone) from: the entry point, relocated far call / far jump
targets, near call targets, `push bp; mov bp,sp` and `enter` prologues in code segments, far code
pointers built from a relocated segment (`mov r,off / mov r,seg`, `mov r,seg / push r / mov r,off`,
`push seg / push off`, `mov [m],off / mov [m+2],seg`), overlay stub thunks, assembly entry points that
load DGROUP into DS, and switch tables (`cmp bx,N / ... / jmp cs:[bx+tbl]` and Borland's value-search
form `mov cx,N / mov bx,tbl / ... / jmp cs:[bx+2N]`).

Addresses are `SSSS:OOOO` with the segment as stored in the file (load segment 0); image offset =
SSSS*16 + OOOO; Ghidra (image loaded at 1000:0000) shows segment SSSS+1000.

Per function: extent, near/far, callers/callees, DS reads/writes, strings (DGROUP `ds:` offsets and
far `seg:off` pairs), INT numbers with the AH value when known (`21.3d`, `67.40`), I/O ports (the
`mov dx,imm` value when known), far data segments referenced and the source file named in them.

usage: apindex.py EXE port/<name> [gaps]
       writes port/<name>_functions.json/.csv and work/<name>_starts.txt (image offsets for
       tools/ghidra/DecompileAll.java), prints the segment map.
"""
import bisect, json, os, re, struct, sys
from collections import defaultdict
from capstone import Cs, CS_ARCH_X86, CS_MODE_16
from capstone.x86 import (X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_INVALID, X86_REG_BP, X86_REG_SP,
                          X86_REG_DS, X86_REG_CS)

exe, out_base = sys.argv[1], sys.argv[2]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = open(exe, 'rb').read()
hdr = struct.unpack_from('<H', d, 8)[0] * 16
nrel = struct.unpack_from('<H', d, 6)[0]
relo_off = struct.unpack_from('<H', d, 0x18)[0]
lastp, npages = struct.unpack_from('<HH', d, 2)
ss_, sp_ = struct.unpack_from('<HH', d, 0x0E)
entry_ip, entry_cs = struct.unpack_from('<HH', d, 0x14)
img = d[hdr:(npages - 1) * 512 + (lastp or 512)]
IMG_END = len(img)
entry = entry_cs * 16 + entry_ip

# Borland C++ c0.asm: mov dx,DGROUP / mov cs:DGROUP@@,dx / mov ah,30h / int 21h
m = re.match(rb'\xba(..)\x2e\x89\x16..\xb4\x30\xcd\x21', img[entry:entry + 12], re.S)
DGROUP = struct.unpack('<H', m.group(1))[0]
DS_BASE = DGROUP * 16
DS_END = min(IMG_END, ss_ * 16 + sp_) if ss_ > DGROUP else IMG_END

relocs = set()
seg_values = set()
for i in range(nrel):
    o, s = struct.unpack_from('<HH', d, relo_off + 4 * i)
    p = s * 16 + o
    relocs.add(p)
    seg_values.add(struct.unpack_from('<H', img, p)[0])
ALL_SEGS = sorted({0} | {s for s in seg_values if s * 16 < IMG_END and s != DGROUP})
# The first relocated segment at or above the stack end starts code appended by unovl.py.
STACK_SEG = ss_ if ss_ > DGROUP else None
OVL_BASE = next((s * 16 for s in ALL_SEGS if s * 16 >= DS_END), IMG_END)

# ---- classify segments ----
targets = {entry_cs}
for p in relocs:
    if p >= 3 and img[p - 3] in (0x9A, 0xEA):
        targets.add(struct.unpack_from('<H', img, p)[0])
for s in ALL_SEGS:
    if img[s * 16:s * 16 + 2] == b'\xcd\x3f' and s * 16 < DS_BASE:
        targets.add(s)                                  # VROOMM stub segment (thunks)
CODE_SEGS = sorted(s for s in ALL_SEGS if s in targets or s * 16 >= OVL_BASE)
DATA_SEGS = sorted(s for s in ALL_SEGS if s not in CODE_SEGS and s * 16 < DS_BASE)
SEG_STARTS = sorted(set(ALL_SEGS) | {DGROUP} | ({STACK_SEG} if STACK_SEG else set()))
code_seg_set = set(CODE_SEGS)


def seg_of(lin):
    return SEG_STARTS[bisect.bisect_right(SEG_STARTS, lin >> 4) - 1]


def seg_end_of(lin):
    return next((x * 16 for x in SEG_STARTS if x * 16 > lin), IMG_END)


def is_code(lin):
    return 0 <= lin < IMG_END and seg_of(lin) in code_seg_set


def fmt(lin):
    s = seg_of(lin)
    return '%04x:%04x' % (s, lin - s * 16)


def cstring(p):
    if not (0 <= p < IMG_END) or (p > 0 and img[p - 1] not in (0, 0x0a, 0x0d) and False):
        return None
    mm = re.match(rb'[\x20-\x7e\r\n\t]{3,}', img[p:p + 100])
    if mm and p + len(mm.group(0)) < IMG_END and img[p + len(mm.group(0))] == 0:
        return mm.group(0).decode('latin-1')
    return None


def ds_string(off):
    p = DS_BASE + off
    if not DS_BASE <= p < DS_END or (p > DS_BASE and img[p - 1] != 0):
        return None
    return cstring(p)


# source file names in far data segments (assert __FILE__ strings)
SRC_RE = re.compile(rb'[A-Za-z0-9_:\\]*\\([A-Za-z0-9_]+\.(?:c|cpp|asm))\x00')
seg_source = {}
for s in DATA_SEGS:
    e = seg_end_of(s * 16)
    mm = SRC_RE.search(img, s * 16, e)
    if mm:
        seg_source[s] = mm.group(1).decode()

# ---- seeds ----
seeds = {entry}
PROLOGUE = re.compile(rb'\x55\x8b\xec|\xc8..\x00', re.S)
ENDS = (0xC3, 0xCB, 0xCF, 0x90, 0xC2, 0xCA, 0xEA, 0xE9, 0xEB, 0x00)
for s in CODE_SEGS:
    a, e = s * 16, seg_end_of(s * 16)
    for mm in PROLOGUE.finditer(img, a, e):
        q = mm.start()
        if img[q] == 0xC8 and (q == a or img[q - 1] not in ENDS):
            continue
        seeds.add(q)


STUB_SIG = bytes([0xCD, 0x3F])      # INT 3Fh: VROOMM stub header


def code_ptr(sv, off):
    t = sv * 16 + off
    # (a VROOMM stub header `CD 3F` is not code: the segment table in DGROUP points at it)
    if sv in code_seg_set and is_code(t) and seg_of(t) == sv and img[t:t + 2] != STUB_SIG:
        seeds.add(t)


for p in relocs:
    if not 4 <= p < IMG_END - 6 or not is_code(p):
        continue
    sv = struct.unpack_from('<H', img, p)[0]
    if sv not in code_seg_set:
        continue
    w = lambda q: struct.unpack_from('<H', img, q)[0]
    b = img
    if b[p - 3] in (0x9A, 0xEA):                                # call/jmp far off:seg
        code_ptr(sv, w(p - 2))
    elif 0xB8 <= b[p - 1] <= 0xBF and 0xB8 <= b[p - 4] <= 0xBF:  # mov r,off / mov r,seg
        code_ptr(sv, w(p - 3))
    elif 0xB8 <= b[p - 1] <= 0xBF and 0x50 <= b[p + 2] <= 0x57 and 0xB8 <= b[p + 3] <= 0xBF:
        code_ptr(sv, w(p + 4))                                  # mov r,seg / push r / mov r,off
    elif b[p - 1] == 0x68 and b[p + 2] == 0x68:                 # push seg / push off
        code_ptr(sv, w(p + 3))
    elif b[p - 4:p - 2] == b'\xc7\x06' and b[p - 10:p - 8] == b'\xc7\x06' and w(p - 2) == w(p - 8) + 2:
        code_ptr(sv, w(p - 6))                                  # mov [m],off / mov [m+2],seg
    elif b[p - 3:p - 1] in (b'\xc7\x46', b'\xc7\x47') and b[p - 8:p - 6] == b[p - 3:p - 1] \
            and b[p - 1] == (b[p - 6] + 2) & 0xFF:
        code_ptr(sv, w(p - 5))                                  # mov [bp/bx+d],off / [..+d+2],seg
    elif b[p - 4:p - 1] in (b'\x26\xc7\x46', b'\x26\xc7\x47') and b[p - 10:p - 7] == b[p - 4:p - 1] \
            and b[p - 1] == (b[p - 7] + 2) & 0xFF:
        code_ptr(sv, w(p - 6))
# data tables of far code pointers in DGROUP / far data: off,seg pairs with a relocated seg.
# Runs of relocations 8 bytes apart are the VROOMM segment table (seg, maxoff, flags, minoff), not
# pointers: skipped.
data_rel = sorted(p for p in relocs if not is_code(p) and p >= 2)
segtab = set()
run = [data_rel[0]] if data_rel else []
for p in data_rel[1:] + [None]:
    if p is not None and p - run[-1] == 8:
        run.append(p)
        continue
    if len(run) >= 16:
        segtab.update(run)
    run = [p]
for p in data_rel:
    if p in segtab:
        continue
    sv = struct.unpack_from('<H', img, p)[0]
    if sv in code_seg_set:
        code_ptr(sv, struct.unpack_from('<H', img, p - 2)[0])
# assembly entry points that load DGROUP themselves
PUSHES = (0xFA, 0xFB, 0xFC, 0x9C, 0x1E, 0x06, 0x50, 0x51, 0x52, 0x53, 0x55, 0x56, 0x57, 0x60)
for mm in re.finditer(re.escape(b'\xb8' + struct.pack('<H', DGROUP) + b'\x8e\xd8'), img):
    q = mm.start()
    if not is_code(q):
        continue
    while q > 0 and img[q - 1] in PUSHES:
        q -= 1
    if q > 0 and img[q - 1] in ENDS:
        seeds.add(q)
seeds = {s for s in seeds if is_code(s)}
func_starts = set(seeds)

# ---- recursive descent ----
md = Cs(CS_ARCH_X86, CS_MODE_16)
md.detail = True
insn_at = {}
calls_from = defaultdict(set)
jump_tables = defaultdict(list)
work, seen = list(seeds), set()


def table_targets(tbl, n, base, seg_end):
    out = []
    for k in range(n):
        e = tbl + 2 * k
        if e + 2 > IMG_END:
            break
        t = base + struct.unpack_from('<H', img, e)[0]
        if not base <= t < seg_end:
            break
        out.append(t)
    return out


def descend():
    while work:
        a = work.pop()
        if a in seen or not is_code(a):
            continue
        base = seg_of(a) * 16
        seg_end = seg_end_of(a)
        for ins in md.disasm(img[a:min(a + 0x2000, seg_end)], a - base):
            lin = base + ins.address
            if lin in seen:
                break
            seen.add(lin)
            insn_at[lin] = ins
            mn = ins.mnemonic
            op0 = ins.operands[0] if ins.operands else None
            if ins.bytes[0] in (0x9A, 0xEA) and ins.size == 5:
                if lin + 3 in relocs:
                    t = struct.unpack_from('<H', img, lin + 3)[0] * 16 + struct.unpack_from('<H', img, lin + 1)[0]
                    if is_code(t):
                        calls_from[lin].add(t)
                        func_starts.add(t)
                        work.append(t)
            elif mn == 'call' and op0 is not None and op0.type == X86_OP_IMM:
                t = base + (op0.imm & 0xFFFF)
                calls_from[lin].add(t)
                func_starts.add(t)
                work.append(t)
            elif mn.startswith('j') and op0 is not None and op0.type == X86_OP_IMM:
                work.append(base + (op0.imm & 0xFFFF))
            elif mn == 'jmp' and op0 is not None and op0.type == X86_OP_MEM and op0.mem.segment == X86_REG_CS \
                    and op0.mem.base != X86_REG_INVALID and op0.mem.index == X86_REG_INVALID:
                disp = op0.mem.disp & 0xFFFF
                back = img[max(base, lin - 0x40):lin]
                tg = []
                # Borland value-search switch: mov cx,N / mov bx,tbl / ... / jmp cs:[bx+2N]
                ms = [x for x in re.finditer(rb'\xb9(..)\xbb(..)', back, re.S)
                      if struct.unpack('<H', x.group(1))[0] * 2 == disp]
                if ms:
                    tbl = base + struct.unpack('<H', ms[-1].group(2))[0] + disp
                    tg = table_targets(tbl, disp // 2, base, seg_end)
                elif disp:
                    tbl = base + disp
                    mc = [x for x in re.finditer(rb'\x83\xfb(.)|\x81\xfb(..)', back[-24:], re.S)]
                    if mc:
                        g = mc[-1]
                        n = (g.group(1)[0] if g.group(1) else struct.unpack('<H', g.group(2))[0]) + 1
                        tg = table_targets(tbl, min(n, 512), base, seg_end)
                    else:
                        for k in range(128):
                            e = tbl + 2 * k
                            if e + 2 > seg_end or e in seen:
                                break
                            t = base + struct.unpack_from('<H', img, e)[0]
                            if not base <= t < seg_end or tbl <= t <= e:
                                break
                            tg.append(t)
                if tg:
                    jump_tables[tbl] = tg
                    work.extend(tg)
            if mn in ('ret', 'retf', 'iret', 'jmp', 'ljmp', 'hlt'):
                break
            if mn == 'int' and op0 is not None and op0.imm in (0x20,):
                break


descend()

# ---- functions ----
starts = sorted(func_starts)
funcs = {}
for i, s in enumerate(starts):
    nxt = min(starts[i + 1] if i + 1 < len(starts) else IMG_END, seg_end_of(s))
    body = [a for a in range(s, nxt) if a in insn_at]
    if not body:
        continue
    f = dict(start=fmt(s), image='%05x' % s, far=False, calls=set(), callers=set(), ds_reads=set(),
             ds_writes=set(), strings={}, ints=set(), ports=set(), far_data=set(), sets_ds=False,
             insns=len(body))
    end = s
    reg = {}                        # last immediate loaded into ax/ah/dx in straight-line order
    ax_str = None                   # string key taken from the last `mov ax,imm`
    prev_imm = None                 # (value, is_relocated_seg) of the previous instruction's immediate
    for a in body:
        ins = insn_at[a]
        end = max(end, a + ins.size)
        mn = ins.mnemonic
        if mn == 'retf':
            f['far'] = True
        f['calls'] |= calls_from.get(a, set())
        if mn == 'int':
            n = ins.operands[0].imm & 0xFF
            if ax_str:                          # `mov ax,2508h / int 21h` is a function number
                f['strings'].pop(ax_str, None)
            ah = reg.get('ah')
            f['ints'].add('%02x' % n if ah is None or n in (0x3f,) else '%02x.%02x' % (n, ah))
        if mn in ('in', 'out'):
            ops = ins.op_str.split(', ')
            pr = ops[1] if mn == 'in' else ops[0]
            if pr == 'dx':
                pr = '%xh' % reg['dx'] if 'dx' in reg else 'dx'
            else:
                pr = '%xh' % int(pr, 0)
            f['ports'].add(pr)
        if mn in ('insb', 'outsb', 'insw', 'outsw'):
            f['ports'].add('%xh' % reg['dx'] if 'dx' in reg else 'dx')
        if mn in ('mov', 'pop') and ins.operands and ins.operands[0].type == X86_OP_REG \
                and ins.reg_name(ins.operands[0].reg) == 'ds':
            f['sets_ds'] = True
        # register immediates (for INT AH and port numbers)
        if len(ins.operands) == 2 and ins.operands[0].type == X86_OP_REG:
            r = ins.reg_name(ins.operands[0].reg)
            src = ins.operands[1]
            if mn == 'mov' and src.type == X86_OP_IMM:
                v = src.imm & 0xFFFF
                if r == 'ax':
                    reg['ah'] = v >> 8
                elif r == 'ah':
                    reg['ah'] = v & 0xFF
                elif r == 'dx':
                    reg['dx'] = v
            elif r in ('ax', 'ah', 'eax'):
                reg.pop('ah', None)
            elif r in ('dx', 'edx') and mn not in ('in',):
                if not (mn in ('inc', 'dec', 'add', 'sub') and 'dx' in reg and src.type == X86_OP_IMM):
                    reg.pop('dx', None)
                else:
                    reg['dx'] = (reg['dx'] + (src.imm if mn in ('add',) else -src.imm)) & 0xFFFF
        elif mn in ('inc', 'dec') and ins.operands and ins.operands[0].type == X86_OP_REG \
                and ins.reg_name(ins.operands[0].reg) == 'dx' and 'dx' in reg:
            reg['dx'] = (reg['dx'] + (1 if mn == 'inc' else -1)) & 0xFFFF
        if mn in ('call', 'lcall') or mn.startswith('j'):
            reg = {}
            ax_str = None
        cur_imm = None
        for k, op in enumerate(ins.operands):
            if op.type == X86_OP_MEM:
                mem = op.mem
                if mn == 'lea' or mem.base in (X86_REG_BP, X86_REG_SP):
                    continue
                if mem.segment not in (X86_REG_INVALID, X86_REG_DS):
                    continue
                off = '%04x' % (mem.disp & 0xFFFF)
                is_dest = k == 0 and mn not in ('cmp', 'test', 'push', 'call', 'jmp', 'ljmp', 'lcall')
                if is_dest:
                    f['ds_writes'].add(off)
                if not is_dest or mn != 'mov':
                    f['ds_reads'].add(off)
            elif op.type == X86_OP_IMM and mn in ('push', 'mov'):
                v = op.imm & 0xFFFF
                imm_pos = a + ins.size - 2
                if imm_pos in relocs:                    # a segment
                    cur_imm = (v, True)
                    if v in seg_source or (v not in code_seg_set and v * 16 < DS_BASE):
                        f['far_data'].add(v)
                    if prev_imm and not prev_imm[1]:
                        st = cstring(v * 16 + prev_imm[0])
                        if st and (v * 16 + prev_imm[0]) < DS_BASE:
                            f['strings']['%04x:%04x' % (v, prev_imm[0])] = st
                else:
                    cur_imm = (v, False)
                    if prev_imm and prev_imm[1] and prev_imm[0] != DGROUP:
                        st = cstring(prev_imm[0] * 16 + v)
                        if st and prev_imm[0] * 16 + v < DS_BASE:
                            f['strings']['%04x:%04x' % (prev_imm[0], v)] = st
                            continue
                    # (DS:0004 is the RTL copyright string: small constants are not string pointers)
                    if (mn == 'push' or ins.reg_name(ins.operands[0].reg) not in ('dx', 'cx')) and v >= 0x40:
                        sv = ds_string(v)
                        if sv:
                            f['strings']['ds:%04x' % v] = sv
                            if mn == 'mov' and ins.reg_name(ins.operands[0].reg) == 'ax':
                                ax_str = 'ds:%04x' % v
        if cur_imm is not None:
            prev_imm = cur_imm
        elif mn not in ('push',) or not ins.operands or ins.operands[0].type != X86_OP_REG:
            prev_imm = None
    f['end'] = fmt(end)
    f['size'] = end - s
    f['source'] = sorted({seg_source[x] for x in f['far_data'] if x in seg_source})
    funcs[s] = f

for s, f in funcs.items():
    for t in f['calls']:
        if t in funcs:
            funcs[t]['callers'].add(s)

rows = []
for s in sorted(funcs):
    f = funcs[s]
    f['calls'] = [fmt(t) for t in sorted(f['calls'])]
    f['callers'] = [fmt(t) for t in sorted(f['callers'])]
    f['far_data'] = ['%04x' % x for x in sorted(f['far_data'])]
    for k in ('ds_reads', 'ds_writes', 'ints', 'ports'):
        f[k] = sorted(f[k])
    rows.append(f)

# per code segment: source files named by its functions' far data
seg_src = defaultdict(lambda: defaultdict(int))
for f in rows:
    for sname in f['source']:
        seg_src[int(f['start'][:4], 16)][sname] += 1

name = os.path.basename(out_base)
json.dump(dict(exe=exe, dgroup='%04x' % DGROUP, entry=fmt(entry),
               code_segments=['%04x' % s for s in CODE_SEGS],
               data_segments={'%04x' % s: seg_source.get(s, '') for s in DATA_SEGS},
               overlay_base='%05x' % OVL_BASE if OVL_BASE < IMG_END else None,
               jump_tables={fmt(t): [fmt(x) for x in v] for t, v in sorted(jump_tables.items())},
               functions=rows),
          open(out_base + '_functions.json', 'w'), indent=1)
with open(out_base + '_functions.csv', 'w') as o:
    o.write('start,image,end,size,far,insns,ncalls,ncallers,ints,ports,sets_ds,source,strings\n')
    for f in rows:
        o.write('%s,%s,%s,%d,%d,%d,%d,%d,%s,%s,%d,%s,"%s"\n' % (
            f['start'], f['image'], f['end'], f['size'], f['far'], f['insns'], len(f['calls']),
            len(f['callers']), ' '.join(f['ints']), ' '.join(f['ports']), f['sets_ds'],
            ' '.join(f['source']),
            ' | '.join(f['strings'].values()).replace('"', "'").replace('\r', '').replace('\n', ' ')
            .replace('\t', ' ')[:120]))
os.makedirs(os.path.join(ROOT, 'work'), exist_ok=True)
with open(os.path.join(ROOT, 'work', name + '_starts.txt'), 'w', newline='\n') as o:
    for f in rows:
        o.write(f['image'] + '\n')

print('%s: DGROUP %04x (image %05x), entry %s, %d code / %d far data segments, %d functions, '
      '%d instructions, %d jump tables' % (name, DGROUP, DS_BASE, fmt(entry), len(CODE_SEGS), len(DATA_SEGS),
                                           len(rows), len(insn_at), len(jump_tables)))
code_bytes = 0
for sg in CODE_SEGS:
    a, e = sg * 16, seg_end_of(sg * 16)
    code_bytes += e - a
    n = sum(1 for f in rows if seg_of(int(f['image'], 16)) == sg)
    srcs = ' '.join('%s' % k for k, v in sorted(seg_src[sg].items(), key=lambda kv: -kv[1]))
    print('  seg %04x  image %05x-%05x  %6d bytes  %3d functions  %s' % (sg, a, e, e - a, n, srcs))
cov = 0
for a2, ins in insn_at.items():
    cov += ins.size
for t, v in jump_tables.items():
    cov += 2 * len(v)
print('coverage: %d of %d code bytes (%.0f%%)' % (cov, code_bytes, 100.0 * cov / max(1, code_bytes)))
if len(sys.argv) > 3:
    covb = bytearray(IMG_END)
    for a2, ins in insn_at.items():
        covb[a2:a2 + ins.size] = b'\x01' * ins.size
    for t, v in jump_tables.items():
        covb[t:t + 2 * len(v)] = b'\x01' * (2 * len(v))
    for sg in CODE_SEGS:
        a, e = sg * 16, seg_end_of(sg * 16)
        run = None
        for p in range(a, e + 1):
            if p < e and not covb[p]:
                run = p if run is None else run
            elif run is not None:
                if p - run >= 32 and any(img[run:p]):
                    print('  gap %s-%s %5d bytes  %s' % (fmt(run), fmt(p), p - run, img[run:run + 12].hex(' ')))
                run = None
