#!/bin/sh
# Apply work/<exe>_symbols_ghidra.txt (tools/ghidra_syms.py) and decompile the indexed functions of the
# three programs of _ghidra/AOTP.gpr to port/decomp/<exe>.c + <exe>_ds.c (postprocess.py).
cd "$(dirname "$0")/../.."
export JAVA_HOME="$(cygpath -w "$PWD"/_tools/jdk-21.0.12.1+1)"
H="$(cygpath -w _tools/ghidra_12.1.3_PUBLIC/support/analyzeHeadless.bat)"
run() {  # prog dgroup name [ovlseg]
  cmd //c "$H" _ghidra AOTP -process $1 -noanalysis -scriptPath tools/ghidra \
    -postScript ApplySymbols.java work/$3_symbols_ghidra.txt $2 \
    -postScript DecompileAll.java work/$3_starts.txt port/decomp/$3.c $2 120 only $4 > work/ghidra_$3_decomp.log 2>&1
  python tools/ghidra/postprocess.py port/decomp/$3.c $2 $4
}
run INTRO.EXE 17E0 intro
run PS.EXE 4D08 ps
run AP_flat.exe 3EA4 ap 45CC
echo done
