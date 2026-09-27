# Brief for phase 3 spec writers

You write one subsystem spec for the faithful C/SDL3 port of DOS **Aces of the Pacific** (Dynamix
1992, CD v1.2). Repo `C:\Coding\AcesOfThePacific`. Read, in order: `PLAN.md`, `port/RE_GUIDE.md`,
`port/spec/README.md` (who owns what), `FORMATS.md` and the `port/formats/*.md` relevant to you.

Reference for style and depth: the finished sibling project `C:\Coding\TestDrive3` — read
`port/spec/render3d.md` or `simulation.md` there (a few hundred lines) to see what a spec looks like:
per function: address, name, signature, what it does precisely enough to reimplement it in C
(integer arithmetic, order of operations, quirks, globals read/written with DS offsets), plus data
structures and tables with layouts. The port keeps the original's globals at their DS offsets in an
emulated `mem[]`, so **name every global you touch with its DS offset** and every struct with field
offsets.

Sources:
- Decompiles: `port/decomp/{intro,ps,ap}_ds.c` (+ `*_globals_xref.txt`). Function index:
  `port/{intro,ps,ap}_functions.json/.csv` (callers/callees, strings, source file tags).
- Ground truth: `python tools/x86dis.py <exe> dis SSSS:OOOO LEN` (AP = `work/AP_flat.exe`),
  `python tools/rawdis.py` for loaded driver code in `work/ovl/`.
- Shared functions across exes: `port/shared_matches.csv` — spec shared library code **once**, and
  give the address in each exe (and the DS offsets of its globals in each exe, which differ).
- Existing names: `port/symbols.csv`.

Output:
- `port/spec/<module>.md` (split into `<module>_*.md` parts if it grows past ~3000 lines; keep an
  index at the top of the main file).
- `port/spec/<module>_symbols.csv` with columns `exe,kind,address,name,type,owner,other_names,notes`
  (`kind` = `func` or `data`; `address` = `SSSS:OOOO` for code, `DS:xxxx` for DGROUP data; `owner` =
  your module name). Every function you own gets a row; name the globals you document.
- Things you find that belong to another module: note them under "Hand-offs" at the end of your spec
  (the owner will not see your notes otherwise — keep them precise, with addresses). Don't write
  other modules' specs.
- Settle open questions from `RE_GUIDE.md` / `FORMATS.md` that fall in your scope; list what stays
  open.
- Anything decided for the port (a `/* PORT: */` deviation: e.g. replacing hardware access, EMS, the
  overlay manager, copy protection) goes in a "Port notes" section; the faithful behaviour stays the
  default.

Priorities: completeness of *game logic* first (every function the port must reimplement, with
exact arithmetic), then data layouts, then prose. Borland RTL functions (seg `0000`) are not specced
beyond a one-line list of which ones are used. Mark confidence where you are unsure; never invent.

Machine notes: write Python/scripts with the Write tool (bash heredocs mangle backslashes).
`python` = WindowsApps 3.12. Don't run the game. Don't commit. Don't edit files outside your own
spec/symbol files (other agents are writing theirs at the same time), except appending to
`port/spec/HANDOFFS.md` is **not** allowed either — use your spec's Hand-offs section.

Final report (under ~50 lines): spec files + line counts, function count covered vs owned, key
findings (especially anything affecting the port architecture: time base, frame pacing, memory
use, self-modifying code, hardware access), hand-offs, open questions.
