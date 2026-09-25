"""Survey of every entry of every Dynamix volume, by extension.

  dynsurvey.py            -> table: extension, count, volumes, size range, chunk structure / first bytes
  dynsurvey.py EXT        -> every entry with that extension (name, volume, size, first bytes)

Chunk structure is shown as the tag sequence ("BMP:{INF: BIN: VGA:}"); entries that are not chunk
lists show "raw" plus a text/binary guess.
"""
import collections, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dynvol, dynchunk


def shape(chunks):
    out = []
    for c in chunks:
        if c.container:
            out.append('%s{%s}' % (c.tag, shape(c.children)))
        else:
            out.append(c.tag + ('*' if c.method is not None else ''))
    # collapse runs of the same tag
    res = []
    for t in out:
        if res and res[-1][0] == t:
            res[-1][1] += 1
        else:
            res.append([t, 1])
    return ' '.join(t if n == 1 else '%sx%d' % (t, n) for t, n in res)


def kind(d):
    if not d:
        return 'empty'
    txt = sum(1 for b in d if 32 <= b < 127 or b in (9, 10, 13, 0))
    return 'text' if txt > 0.95 * len(d) else 'raw'


def ext_of(name):
    return name.rsplit('.', 1)[1] if '.' in name else '(none)'


def main():
    want = sys.argv[1].upper() if len(sys.argv) > 1 else None
    rows = collections.OrderedDict()
    for v in dynvol.all_volumes():
        vn = os.path.splitext(v.name)[0]
        for e in v.entries:
            d = v.get(e)
            x = ext_of(e.name)
            if x.isdigit():
                x = '<n>'
            ch = dynchunk.try_parse(d)
            sh = shape(ch) if ch else kind(d)
            if want:
                if x == want or (want == 'N' and x == '<n>'):
                    print('%-8s %-13s %7d  %-40s %s' % (vn, e.name, e.size, sh[:40], d[:16].hex(' ')))
                continue
            r = rows.setdefault(x, {'n': 0, 'vols': set(), 'min': 1 << 30, 'max': 0, 'shapes': collections.Counter()})
            r['n'] += 1
            r['vols'].add(vn)
            r['min'] = min(r['min'], e.size)
            r['max'] = max(r['max'], e.size)
            r['shapes'][sh if len(sh) < 70 else sh[:67] + '...'] += 1
    if want:
        return
    print('%-6s %4s  %-26s %-15s %s' % ('ext', 'n', 'volumes', 'sizes', 'structure (* = packed)'))
    for x in sorted(rows):
        r = rows[x]
        shapes = '; '.join('%s%s' % (s, '' if c == r['n'] else ' (%d)' % c) for s, c in r['shapes'].most_common(3))
        print('%-6s %4d  %-26s %-15s %s' % (x, r['n'], ','.join(sorted(r['vols'])), '%d-%d' % (r['min'], r['max']), shapes))


if __name__ == '__main__':
    main()
