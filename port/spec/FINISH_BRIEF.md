# Brief for phase 3 finishers

The first round of spec writers (brief: `AGENT_BRIEF.md` — read it, its rules still apply) was cut
off twice by usage limits. Their output is on disk and committed, but parts are missing. You finish
one module.

Rules for this round:
- **Do not launch sub-agents.** Do all reading and writing yourself. Helpers died with their parents
  last time and duplicated work.
- Save progress often: write each finished section to its spec file as soon as it is done, and keep
  the module's `*_symbols.csv` up to date as you go, so an interruption loses little.
- Find the gaps with `python tools/spec_coverage.py` → `work/coverage/<exe>_uncovered.txt` lists
  every indexed function with no row in any `port/spec/*_symbols.csv`. Your job is the gaps that
  belong to your module (by segment/content; `port/spec/README.md` and the ownership map at the top
  of `sim_flow.md` say who owns what) plus the explicit items in your task.
- A function is covered when it has a symbols row **and** a spec entry precise enough to port.
  Trivial wrappers may be one table line.
- Read the existing files of your module first and extend them; don't rewrite finished sections.
  Where an existing statement is wrong, fix it and say so in your report.
- Symbol CSVs: columns `exe,kind,address,name,type,owner,other_names,notes`, quote any field with a
  comma, `kind` = `func` / `global`, owner = the module name. One file per spec part is fine
  (`<module>_<part>_symbols.csv`).
- Don't edit other modules' files; put hand-offs in your spec's Hand-offs section.

Report (under 40 lines): files and line counts, coverage before/after for your module's segments
(from `spec_coverage.py`), corrections made, key findings for the port, open questions.
