import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.io.*;
import ltsa.lts.*;
import ltsa.dispatcher.TransitionSystemDispatcher;

/** Compile selected original safety controllers from the public Workflow example. */
public final class CompilePublicModel {
  public static void main(String[] args) throws Exception {
    Path input = Path.of(args[0]);
    String source = Files.readString(input, StandardCharsets.UTF_8);
    LTSOutput output = new LTSOutput() {
      public void out(String text) { System.out.print(text); }
      public void outln(String text) { System.out.println(text); }
      public void clearOutput() { }
    };
    LTSCompiler compiler = new LTSCompiler(new LTSInputString(source), output,
        input.toAbsolutePath().getParent().toString());
    compiler.compile();
    if (!compiler.getComposites().containsKey(args[1]))
      throw new IllegalArgumentException("Unknown composition: " + args[1]);
    CompositeState model = compiler.continueCompilation(args[1]);
    TransitionSystemDispatcher.applyComposition(model, output);
    CompactState composed = model.getComposition();
    if (composed == null) throw new IllegalStateException("No composed controller");
    try (PrintStream file = new PrintStream(args[2], StandardCharsets.UTF_8)) {
      composed.printAUT(file);
    }
    System.out.println("RESULT " + args[1] + " states=" + composed.maxStates
        + " transitions=" + composed.ntransitions() + " error=" + composed.hasERROR());
  }
}
