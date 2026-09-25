"""Write the Ghidra symbol lists for tools/ghidra/ApplySymbols.java from port/symbols.csv.

usage: ghidra_syms.py      writes work/<exe>_symbols_ghidra.txt for intro, ps, ap:
       "func 1SSS:OOOO name" (Ghidra loads the image at segment 1000) or "global DS:xxxx name".
"""
import csv, os, re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = defaultdict(list)
for r in csv.DictReader(open(os.path.join(ROOT, 'port', 'symbols.csv'), encoding='utf-8')):
    name = re.sub(r'\W', '_', r['name'].strip())
    a = r['address'].strip().upper()
    if r['kind'] == 'func':
        s, o = a.split(':')
        out[r['exe']].append('func %04X:%s %s' % (int(s, 16) + 0x1000, o, name))
    elif r['kind'] == 'global':
        out[r['exe']].append('global %s %s' % (a, name))
for exe, lines in out.items():
    with open(os.path.join(ROOT, 'work', exe + '_symbols_ghidra.txt'), 'w', newline='\n') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(exe, len(lines))
