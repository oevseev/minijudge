# Minijudge

> Lightweight ACM-ICPC batch testing utility

## Synopsis

This utility is designed for effortless batch testing of ACM-ICPC and IOI-style code (primarily designed for use in conjunction with checkers that utilize [testlib.h](https://github.com/MikeMirzayanov/testlib)).

## Installation

You should have these packages installed beforehand:

* `natsort`
* `psutil`
* `termcolor`

Install them by executing `pip install natsort psutil termcolor` (*first install [pip](https://pip.pypa.io/en/stable/) if you don't have it installed*).

Then, use `python3 judge.py ...` to launch the utility. You can also set execute permission via `chmod +x judge.py` and launch the script directly.

## Command line arguments

Minijudge accepts three mandatory arguments in the following order:

* `file` — specifies which file is to be tested;
* `test_dir` — path to test directory; 
* `path_to_checker` — path to checker application.

The following optional arguments can also be specified:

* `-c COMPILER` — which compiler to use. It's guessed from extension by default, although *it's recommended to always state it explicitly*. Information about compiler options is taken from `compilers.json`;

* `--ioi` — enables IOI mode (execution is not aborted after one failed test);

* `-m MEMORY_LIMIT`, `-t TIME_LIMIT` — these arguments specify program limits. If not specified, they are assumed to be **262144 kilobytes** and **2000 milliseconds** respectively;

* `-i INPUT_FILE`, `-o OUTPUT_FILE` — these arguments specify input and output files respectively. If not specified, input and output are read from and written to **the respective standard streams**;

* `--json` — enables JSON mode (standard output is silenced, only JSON report is shown);

* `--out OUTPUT_FILE` — the file to write the testing report to.

You can also launch the utility with the `-h` option to show the help message.

## Requirements to checker application and tests

Each test in the test directory should be labeled *in accordance to its execution order*. The general practice is to label them using numbers with leading zeros, although they can be omitted (as the tests in the directory are sorted naturally by using `natsort`). Input files should have no extension and output files must feature an `.a` extension (e.g. `01` and `01.a`).

The checker application must accept *exactly three* command line arguments in the following order:

* path to input file;
* path to user output;
* path to jury output.

The checker application must return one of the following codes after its termination:

* `0` if the solution is correct;
* `1` in case of wrong answer;
* `2` in case of presentation error.

Any other code than that is considered checker failure. In this case, the utility will terminate and no further tests will be executed.

## Compiler file format

`compilers.json` is a JSON file that specifies which compilers are available for using. Each compiler is described via dictionary entry. The compiler can then be selected by specifying its key with the `-c` option.

These fields describe the compiler/interpreter:

* `extensions` — array of extensions. If the extension of source file is not specified, these ones would be used to help determine the compiler.
* `options` — command to compile the source file with (if not specified, the source file will be treated as executable);
* `executable_file` — which file should be executed (should be used in conjunction with the previous option);
* `runtime` — command to run the executable file with (if not specified, the executable file will be invoked directly).

Note that you can use the following aliases when setting commands and paths (see provided `compilers.json` for example):

* `{0}` — path to source file (or executable file if used within the `runtime` field) with extension;
* `{1}` — file name without extension.