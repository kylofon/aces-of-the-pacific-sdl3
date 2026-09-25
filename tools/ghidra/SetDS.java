// Headless pre-script: before auto-analysis, tell Ghidra that DS = DGROUP in all code below DGROUP
// (and, for AP_flat.exe, in the overlay code appended after the resident image), so data references
// are resolved against the right segment.
// args: <dgroup segment hex, e.g. 3EA4> [first overlay code segment hex, e.g. 45CC]
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;

import java.math.BigInteger;

public class SetDS extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        int dgroup = Integer.parseInt(args[0], 16);
        Address base = currentProgram.getMinAddress();
        int loadSeg = (int) (base.getOffset() >> 4);
        Register ds = currentProgram.getRegister("ds");
        Address codeEnd = base.add(((long) dgroup << 4) - 1);
        currentProgram.getProgramContext().setValue(ds, base, codeEnd, BigInteger.valueOf(loadSeg + dgroup));
        println(String.format("DS = %04X for %s - %s", loadSeg + dgroup, base, codeEnd));
        if (args.length > 1) {
            Address ovl = base.add((long) Integer.parseInt(args[1], 16) << 4);
            Address end = lastCodeAddress();
            currentProgram.getProgramContext().setValue(ds, ovl, end, BigInteger.valueOf(loadSeg + dgroup));
            println(String.format("DS = %04X for %s - %s (overlays)", loadSeg + dgroup, ovl, end));
        }
    }

    // highest address of an initialized block in the image's address space (getMaxAddress() may be
    // in another space)
    private Address lastCodeAddress() {
        Address base = currentProgram.getMinAddress(), end = base;
        for (ghidra.program.model.mem.MemoryBlock b : currentProgram.getMemory().getBlocks())
            if (b.isInitialized() && b.getStart().getAddressSpace() == base.getAddressSpace()
                    && b.getEnd().compareTo(end) > 0) end = b.getEnd();
        return end;
    }
}
