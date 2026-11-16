// (From aleph-void/ghidra-sh, MIT.)  Prints the program's language and compiler spec.  Script args: <out.txt>
//@category Testing
import java.io.PrintStream;
import ghidra.app.script.GhidraScript;
public class LangId extends GhidraScript {
	@Override
	protected void run() throws Exception {
		PrintStream out = new PrintStream(getScriptArgs()[0]);
		out.println("language: " + currentProgram.getLanguageID() + " compiler: " +
			currentProgram.getCompilerSpec().getCompilerSpecID() + " functions: " +
			currentProgram.getFunctionManager().getFunctionCount());
		out.close();
	}
}
