#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# MiniJudge - WORK IN PROGRESS
#
# WARNING: THE CURRENT CODE IS RATHER UNSAFE AT THE MOMENT. IT MAY ALSO BE
# BUGGY DUE TO BEING WORK IN PROGRESS. DO NOT USE IT IN ACTUAL CONTESTS YET.
#
# Copyright (c) 2016, Oleg Evseev <evs.o@icloud.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.


import argparse
import json
import os
import os.path
import shutil
import subprocess
import sys
import time

import natsort
import psutil
import termcolor


IDLENESS_THRESHOLD = 50.0
DEFAULT_MEMORY_LIMIT = 262144
DEFAULT_TIME_LIMIT = 2000

CODE_COLORS = {
    'OK': 'green',
    'IL': 'magenta',
    'ML': 'magenta',
    'TL': 'magenta',
    'CE': 'red',
    'PE': 'red',
    'RE': 'red',
    'WA': 'red'}


def log(message, *args, color='cyan'):
    formatted_message = str.format(message, *args)
    termcolor.cprint(formatted_message, color)


def log_outcome(report):
    code = report['outcome']['code']

    print("\n>>>", end=' ')
    if 'test' in report['outcome'] and report['outcome']['test'] > 0:
        test = report['outcome']['test']
        log("{0}, test {1}", code, test, color=CODE_COLORS[code])
    else:
        log("{0}", code, color=CODE_COLORS[code])


def format_command(command, filename):
    return str.format(command, filename, os.path.splitext(filename)[0])


class Judge():
    class MemoryLimitExceeded(Exception):
        pass

    class TimeLimitExceeded(Exception):
        pass

    def __init__(self, memory_limit, time_limit, input_file, output_file):
        self.memory_limit = memory_limit
        self.time_limit = time_limit
        self.input_file = input_file
        self.output_file = output_file

        self.executable_file = None
        self.runtime = None

        self.ready = False
        self.report = {}

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self.executable_file and os.path.isfile(self.executable_file):
            os.remove(self.executable_file)

        if self.input_file and os.path.isfile(self.input_file):
            os.remove(self.input_file)

        if self.output_file and os.path.isfile(self.output_file):
            os.remove(self.output_file)
        elif os.path.isfile('output'):
            os.remove('output')

    def compile_file(self, input_file, compiler):
        if 'options' not in compiler:
            self.runtime = format_command(compiler['runtime'], input_file)
            self.ready = True
            return

        # {0} in command is replaced by full filename, and {1} is replaced
        # by filename without extension
        self.executable_file = format_command(compiler['executable_file'],
                                              input_file)
        if 'runtime' in compiler:
            self.runtime = format_command(compiler['runtime'],
                                          self.executable_file)

        command = format_command(compiler['options'], input_file)
        log("Executing command \"{0}\"", command)
        p = subprocess.Popen(command.split())
        p.wait()
        log("Process finished with return code {0}.", p.returncode)

        if p.returncode != 0:
            self.report['outcome'] = {'code': 'CE', 'test': 1}
        else:
            self.ready = True

    def run(self, ioi_mode, tests, path_to_checker):
        if not self.ready:
            return

        self.report['test_data'] = []
        halt = False
        input_file, output_file = None, None

        for i, test in enumerate(tests, 1):
            log("\nRunning on test #{0}...", i)
            skip = False

            # Either way, input is linked to a corresponding file (or stdin)
            if self.input_file is None:
                input_file = open(test, 'r')
            else:
                shutil.copy(test, self.input_file)

            # And output is routed to a generic file named "output" if no
            # filename was specified.
            if self.output_file is None:
                output_file = open('output', 'w')

            # If specified, runtime command is preferred
            command = self.executable_file
            if self.runtime is not None:
                command = self.runtime

            p = subprocess.Popen(command.split(), stdin=input_file,
                                 stdout=output_file)
            pp = psutil.Process(p.pid)

            # It shouldn't affect IL checking as the code has finished running
            # by the time when exception is raised
            try:
                pp.cpu_percent()
            except psutil.AccessDenied:
                pass

            start = time.clock()
            time_elapsed, memory_used = 0, 0

            try:
                while p.poll() is None:
                    time_elapsed = int((time.clock() - start) * 1000)
                    try:
                        memory_used = pp.memory_info()[0] // 1024

                    # Process terminated mid-cycle
                    except psutil.AccessDenied:
                        break

                    if time_elapsed >= self.time_limit:
                        raise Judge.TimeLimitExceeded
                    if memory_used >= self.memory_limit:
                        raise Judge.MemoryLimitExceeded

            except Judge.TimeLimitExceeded:
                description, code = "Time", 'TL'
                if pp.cpu_percent() < IDLENESS_THRESHOLD:
                    description, code = "Idleness", 'IL'

                p.kill()

                log("{2} limit exceeded ({0} ms, {1} KB).", self.time_limit,
                    memory_used, description, color=CODE_COLORS[code])
                self.report['test_data'].append({
                    'code': code,
                    'time': self.time_limit,
                    'memory': memory_used
                })

                if not ioi_mode:
                    self.report['outcome'] = {'code': code, 'test': i}
                    halt = True

                skip = True

            except Judge.MemoryLimitExceeded:
                p.kill()
                log("Memory limit exceeded ({0} ms, {1} KB).", time_elapsed,
                    self.memory_limit, color=CODE_COLORS['ML'])

                self.report['test_data'].append({
                    'code': 'ML',
                    'time': time_elapsed,
                    'memory': self.memory_limit
                })

                if not ioi_mode:
                    self.report['outcome'] = {'code': 'ML', 'test': i}
                    halt = True

                skip = True

            finally:
                if input_file is not None:
                    input_file.close()
                if output_file is not None:
                    output_file.close()
                if halt:
                    return

            if skip:
                continue

            p.wait()
            log("Process terminated with code {0} ({1} ms, {2} KB).",
                p.returncode, time_elapsed, memory_used)

            self.report['test_data'].append({
                'code': 'OK',
                'time': time_elapsed,
                'memory': memory_used
            })

            # Any return code other than 0 is considered runtime error
            if p.returncode != 0:
                log("Runtime error occured.", color=CODE_COLORS['RE'])
                self.report['test_data'][-1]['code'] = 'RE'

                if not ioi_mode:
                    self.report['outcome'] = {'code': 'RE', 'test': i}
                    return

                continue

            output_filename = self.output_file
            if output_filename is None:
                output_filename = 'output'

            # Checkers that utilize testlib take 3 arguments: input file,
            # participant output and jury output
            p = subprocess.Popen([path_to_checker, test, output_filename,
                                  test + '.a'])
            p.wait()
            if p.returncode in (1, 2):
                code = ['WA', 'PE'][p.returncode - 1]
                description = ['wrong answer', 'presentation error'][
                    p.returncode - 1]
                log("Test not passed: {0}.", description,
                    color=CODE_COLORS[code])

                self.report['test_data'][-1]['code'] = code

                if not ioi_mode:
                    self.report['outcome'] = {'code': code, 'test': i}
                    return

            elif p.returncode > 2:
                fail(5, "Unexpected verdict was issued.")

            else:
                log("Test passed.", color=CODE_COLORS['OK'])

        if not ioi_mode:
            self.report['outcome'] = {'code': 'OK', 'test': -1}


def parse_args():
    parser = argparse.ArgumentParser(
        description="An utility for batch testing ACM-ICPC and IOI code and "
        "producing test reports in JSON format.")

    parser.add_argument('file',
        help="file to test")
    parser.add_argument('test_dir',
        help="path to test directory. Each test in there should be labeled "
        "in accordance to its execution order. Input files should have no "
        "extension and output file must feature an .a extension.")
    parser.add_argument('path_to_checker',
        help="path to checker application. It must accept exactly three "
        "arguments: path to input file, path to user output and path to jury "
        "output.")

    parser.add_argument('-c', '--compiler',
        help="which compiler to use (guessed from extension by default; "
        " however, it's recommended to always state it explicitly)")

    parser.add_argument('--ioi', action='store_true',
        help="enables IOI mode (execution is not aborted after one failed "
        "test)")

    parser.add_argument('-m', '--memory-limit', type=int,
        default=DEFAULT_MEMORY_LIMIT,
        help=str.format("memory limit in kilobytes (default: {0})",
                        DEFAULT_MEMORY_LIMIT))
    parser.add_argument('-t', '--time-limit', type=int,
        default=DEFAULT_TIME_LIMIT,
        help=str.format("time limit in milliseconds (default: {0})",
                        DEFAULT_TIME_LIMIT))
    parser.add_argument('-i', '--input-file',
        help="name of the file that the program acquires input from "
        "(default: stdin)")
    parser.add_argument('-o', '--output-file',
        help="name of the file that the program writes output to (default: "
        "stdout)")

    parser.add_argument('--json', action='store_true',
        help="enables JSON mode (standart output is silenced, only JSON "
        "report is shown)")
    parser.add_argument('--out',
        help="path to output file (into which JSON output will be written)")

    return parser.parse_args()


def fail(error_code, message, *args):
    prefix = sys.argv[0] + ": " + termcolor.colored("error:", 'red')
    formatted_message = str.format(message, *args)
    print(prefix, formatted_message, file=sys.stderr)
    sys.exit(error_code)


def validate_args(args):
    # Abscence of at least one of the files/directories required by program
    # results in error code 1 (which is less severe than -1, I suppose?)
    if not os.path.isfile(args.file):
        fail(1, "File \"{0}\" does not exist", args.file)
    if not os.path.isfile(args.path_to_checker):
        fail(1, "Checker application is not present at the specified path")
    if not os.path.isdir(args.test_dir):
        fail(1, "Test directory is not present at the specified path")

    # Presence of something in place of the output file results in error code
    # 2 (output file being a directory results in it too)
    if args.out is not None:
        if os.path.isfile(args.out):
            fail(2, "There already exists a file named \"{0}\"", args.out)
        if args.out.endswith('/') or os.path.isdir(args.out):
            fail(2, "Output path can't point to a directory")

    # Memory and time limits must be positive
    if args.memory_limit <= 0 or args.time_limit <= 0:
        fail(3, "Limits must be positive")


def main(args):
    location = os.path.realpath(
        os.path.join(os.getcwd(), os.path.dirname(__file__)))

    if args.json:
        sys.stdout = open(os.devnull, 'w')

    # The only required file is the compiler configuration, and the abscence
    # of it results in an application error with code -1
    compilers_path = os.path.join(location, 'compilers.json')
    if not os.path.isfile(compilers_path):
        fail(-1, "\"compilers.json\" not found")
    with open(compilers_path, 'r') as in_file:
        compilers = json.load(in_file)

    validate_args(args)

    # Converting the paths to absolute ones
    program_file = os.path.abspath(args.file)
    test_dir = os.path.abspath(args.test_dir)
    path_to_checker = os.path.abspath(args.path_to_checker)
    out_file = os.path.abspath(args.out) if args.out is not None else None

    # Changing the directory so that the executable file will be created in
    # the source file directory
    os.chdir(os.path.dirname(program_file))

    # Deducing compiler by extension if not specified
    compiler = args.compiler

    if compiler is None:
        extension = os.path.splitext(program_file)[1]

        # The first compiler that matches the extension will be used to
        # compile the file. But, due to Python's dictionary implementation,
        # it's not guaranteed that it would be the same as the one that
        # appears first in the file, so it's strongly recommended that the
        # compiler should be specified explicitly.
        for c, data in compilers.items():
            if extension in data['extensions']:
                compiler = c

        if compiler is None:
            fail(4, "No compilers found that match the extension")

    # Searching for infile/outfile pairs in test directory and then sorting
    # them naturally
    tests = [os.path.join(test_dir, x) for x in os.listdir(test_dir)
             if '.' not in x and os.path.isfile(os.path.join(test_dir,
             x + '.a'))]
    tests = natsort.natsorted(tests)

    # The judge object in conjunction with "with" statement sandboxes the
    # testing process. It's not enough to prevent the malitious code from
    # doing very bad things, however!
    with Judge(args.memory_limit, args.time_limit,
               args.input_file, args.output_file) as judge:
        judge.compile_file(program_file, compilers[compiler])
        judge.run(args.ioi, tests, path_to_checker)

        if out_file is not None:
            with open(out_file, 'w') as of:
                json.dump(judge.report, of)

        if 'outcome' in judge.report:
            log_outcome(judge.report)

        if args.json:
            sys.stdout.close()
            sys.stdout = sys.__stdout__
            print(json.dumps(judge.report))


if __name__ == '__main__':
    main(parse_args())
