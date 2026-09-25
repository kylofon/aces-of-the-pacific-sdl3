"""Extract the run-time loaded code modules from the Dynamix volumes (phase 1, code map).

Besides the three EXEs, code is loaded at run time from volume resources (port/formats/resources.md):
  SHELL1.DYN VMCODE.OVL  = OVL:{VGA: EGA: MCG: CGA: TAN: HEG: EVG: EVA:} video drivers, one per adapter;
                           INTRO/PS load the one for the detected adapter (gfx_init -> gfx_load_driver)
  SIM2.DYN   VMCODE2.OVL = OVL:{VGA:}, the simulator's copy (identical VGA driver)
  SHELL1.DYN SXCODE.OVL, SIM2.DYN SX.OVL, M1SIM.DYN SX1.OVL
                         = SSM:{M32: NLD: ADL: TAN: PS1: STD: 001: 003: 101:}: Sierra SCI sound
                           drivers (87654321h), chosen by the sound driver number (snd_init)
Decompression is tools/dynchunk.py (phase 2).

usage: ovlcode.py            writes work/ovl/<RESOURCE>_<TAG>.bin and prints a list
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynchunk, dynvol

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESOURCES = [('SHELL1.DYN', 'VMCODE.OVL'), ('SIM2.DYN', 'VMCODE2.OVL'), ('SHELL1.DYN', 'SXCODE.OVL'),
             ('SIM2.DYN', 'SX.OVL'), ('M1SIM.DYN', 'SX1.OVL')]


def leaves(chunks):
    for c in chunks:
        if c.container:
            yield from leaves(c.children)
        else:
            yield c


out_dir = os.path.join(ROOT, 'work', 'ovl')
os.makedirs(out_dir, exist_ok=True)
for vol, name in RESOURCES:
    v = dynvol.Volume(os.path.join(ROOT, 'Game', vol))
    e = v.find(name)
    if e is None:
        print('%s: no %s' % (vol, name))
        continue
    for c in leaves(dynchunk.parse(v.get(e))):
        blob = c.data
        fn = '%s_%s.bin' % (name.replace('.', '_'), c.tag[:-1])
        open(os.path.join(out_dir, fn), 'wb').write(blob)
        sig = 'SCI driver' if blob[4:8] == b'\x21\x43\x65\x87' else blob[:4].hex()
        print('%-11s %-11s %-9s %6d -> %6d  %-24s %s' % (vol, name, c.path, c.size, len(blob), fn, sig))
