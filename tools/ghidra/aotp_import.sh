#!/bin/sh
# Import + auto-analyse INTRO.EXE, PS.EXE and work/AP_flat.exe into _ghidra/AOTP.gpr (phase 1).
# Run from anywhere with Git Bash; logs in work/ghidra_<exe>_import.log. Then run aotp_decompile.sh.
cd "$(dirname "$0")/../.."
export JAVA_HOME="$(cygpath -w "$PWD"/_tools/jdk-21.0.12.1+1)"
H=_tools/ghidra_12.1.3_PUBLIC/support/analyzeHeadless.bat
cmd //c "$(cygpath -w $H)" _ghidra AOTP -import Game/INTRO.EXE -overwrite -scriptPath tools/ghidra -preScript SetDS.java 17E0 -postScript FixNearFlows.java 17E0 > work/ghidra_intro_import.log 2>&1
cmd //c "$(cygpath -w $H)" _ghidra AOTP -import Game/PS.EXE -overwrite -scriptPath tools/ghidra -preScript SetDS.java 4D08 -postScript FixNearFlows.java 4D08 > work/ghidra_ps_import.log 2>&1
cmd //c "$(cygpath -w $H)" _ghidra AOTP -import work/AP_flat.exe -overwrite -scriptPath tools/ghidra -preScript SetDS.java 3EA4 45CC -postScript FixNearFlows.java 3EA4 45CC > work/ghidra_ap_import.log 2>&1
echo done
