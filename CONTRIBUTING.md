# Contributing

Ghidra-Rare collects Ghidra processor modules (SLEIGH) for uncommon architectures. Contributions
are new modules, fixes to existing ones, and better tests. Whatever you change, the bar is
[docs/VERIFICATION.md](docs/VERIFICATION.md): a claim needs a number from a test that can fail.

## Adding a module

1. Create the directory with `tools/new-module-skeleton <Name> <language-prefix>`. It writes the
   build files, a stub language that compiles, and the standard `test/` layout.
2. Write the SLEIGH from the vendor manual. Generate repetitive tables from a script in
   `tools/` rather than writing them by hand, and check the generated file in.
3. Work through the [verification bar](docs/VERIFICATION.md) and fill in the module README: sources
   cited, languages, results table, known gaps, confirmed reference-tool bugs.
4. In the same commit that adds the module, update the top-level [README.md](README.md) (the
   module table row and any intro text it makes stale) and [STATUS.md](STATUS.md) (the results
   block). Commit with explicit paths (`git add <Module> README.md STATUS.md`), not `commit -a`.

## Clean-room rules

Modules written here are MIT-licensed, so what you read matters.

- **Allowed sources:** vendor manuals and datasheets (cite them in the README); reference
  disassemblers and emulators run as black boxes (GNU binutils, LLVM, MAME `unidasm`); binaries
  you compile or assemble yourself.
- **Do not** read or transcribe the source code of GPL tools (binutils opcode tables, GPL MAME
  files) into a module. Learn encodings from the manual and from the tool's output.
  BSD/MIT-licensed reference code may be consulted; credit it in the README.
- **Never** use a closed or licensed processor module (IDA's included) or anything whose license
  forbids derivative works.

## Community modules

SLEIGH modules written by others live in an `aleph-void` fork of the original repository, under
the original license, and are included here as git submodules under `community/`. Their fixes go
on the fork's `ghidra-rare` branch, one commit per logical fix, with the upstream license and
copyright headers kept. Each fork carries a `CREDITS.md` naming the original authors and every
change, a `GHIDRA-RARE.md` with the test results, its tests and a release workflow. Don't copy
community code into this repository. See [community/CANDIDATES.md](community/CANDIDATES.md) for
what has been surveyed and the license status of each candidate.

## Building and testing

```sh
export GHIDRA_INSTALL_DIR=/opt/ghidra_12.1.4_PUBLIC
tools/link-modules.sh                       # symlink every module into the install
tools/build-module.sh "$GHIDRA_INSTALL_DIR" <Module> dist
<Module>/test/run-tests.sh [--real <workdir>]
```

Develop against the newest supported Ghidra release and check the other two before sending a
change: `tools/ghidra-versions.sh` lists them and the release workflow builds all three. Building
extensions with Java code needs a full JDK with `javac` (JDK 21 or newer for Ghidra 12.1, JDK 25 for
12.2). Ghidra 12 has no Jython, so test scripts are Java `GhidraScript`s.

## Test inputs

Real binaries are never committed. Fetch them with a script that pins the URL and SHA-256 and
accepts freely licensed samples only (GPL, MIT, BSD, public domain, or vendor-redistributable). If
a sample's license forbids disassembly, don't use it. Build your own from public source with a free
toolchain when no binary exists.

## Commits and pull requests

- One logical change per commit, with a message that says what changed and why.
- Don't commit build output (`*.sla`, `build/`, `dist/`, `lib/`); every module's `.gitignore`
  covers them.
- A pull request that adds or changes a module should show the test results from
  `test/run-tests.sh` and say which Ghidra versions it was built and run on.
