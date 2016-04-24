#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import print_function

from collections import namedtuple

import argparse
import languages
import logging
import os
import re


LOGGING_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
logging.basicConfig(format=LOGGING_FORMAT)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Task(object):
    """ Represents a TODO task """
    def __init__(self, text, filename):
        self.text = text
        self.filename = filename

    def __str__(self):
        return "[ ] {} ({})".format(self.text, self.filename)


class LanguageScanner(object):
    """ Recursively scans through the current directory looking for any
          "TODO definitions" and outputs them.
    """
    OUTPUT_FILE = "tasks_todo.out"

    def __init__(self, languages_to_scan, output_to_file=False):
        """ Initializes our language scanner.

        :param languages_to_scan: Languages of the languages modules that will be scanned
        :type languages_to_scan: list

        :param output_to_file: Output the TODO tasks to file
        :type output_to_file: bool
        """
        self._languages_to_scan = languages_to_scan
        self._output_to_file = output_to_file

    def get_tasks_from_file(self, filename_path, filename, todo_grammar):
        """ Get all TODO tasks from the passed in file that match the provided regex grammar.

        :param filename_path: Absolutely path of the file
        :type filename_path: str

        :param filename: Name of the file, not including the path
        :type filename: str

        :param todo_grammar: Regex grammar to find a TODO task
        :type todo_grammar: str

        :returns: Generator of Tasks with relevant fields
        :rtype: generator<Task>
        """
        with open(filename_path, "rb") as in_file:
            for line in in_file:
                match_obj = re.match(todo_grammar, line)
                if match_obj is not None:
                    yield Task(match_obj.group(1), filename)

    def scan_for_tasks(self, file_exts, todo_grammar, start_dir=None, level=1):
        """ Scanning the current working directory for files that match the
              extension criteria and return all the tasks found.

        :param file_exts: File extensions that qualify files for scanning
        :type file_exts: tuple

        :param todo_grammar: Regex with a match to the TODO initiative
        :type todo_grammar: str

        :param start_dir: Path of the directory to start scanning from
        :type start_dir: str

        :param level: Level of depth we have traversed to
        :type level: int

        :returns: Generator of TODO tasks ready to be reported on
        :rtype: generator<Task>
        """
        if start_dir is None:
            start_dir = os.getcwd()

        lpad_spaces = "  ".join("" for i in xrange(level))

        dir_files = os.listdir(start_dir)
        if dir_files:
            max_filename_len = max(len(f) for f in dir_files)

        for filename in dir_files:
            filename_path = os.path.join(start_dir, filename)

            # ignore sym-links
            if os.path.islink(filename_path):
                logger.debug(("{lpad_spaces}{:<{rpad_space_count}} - ignoring symlink"
                             ).format(filename, lpad_spaces=lpad_spaces, rpad_space_count=max_filename_len))

            # recurse and scan this directory's files
            elif os.path.isdir(filename_path):
                logger.debug(("{lpad_spaces}{:<{rpad_space_count}} - scanning directory"
                             ).format(filename, lpad_spaces=lpad_spaces, rpad_space_count=max_filename_len))

                for t in self.scan_for_tasks(file_exts, todo_grammar, filename_path, level+1):
                    yield t
            # ignore mis-matchd file-extensions
            elif os.path.splitext(filename)[1][1:] not in file_exts:
                logger.debug(("{lpad_spaces}{:<{rpad_space_count}} - ignoring mismatched file-extension"
                             ).format(filename, lpad_spaces=lpad_spaces, rpad_space_count=max_filename_len))

            # scan this file
            elif os.path.isfile(filename_path):
                task_count = 0
                for t in self.get_tasks_from_file(filename_path, filename, todo_grammar):
                    task_count += 1
                    yield t

                logger.debug(("{lpad_spaces}{:<{rpad_space_count}} - {task_count} TODO "
                              "tasks defined").format(filename, lpad_spaces=lpad_spaces,
                                                      rpad_space_count=max_filename_len,
                                                      task_count=task_count))

    def output(self, tasks):
        """ Output the provided tasks to the configured output medium.

        :param tasks: Tasks to be outputted
        :type tasks: list
        """
        if not self._output_to_file:
            do_std_out_print = True
        elif self._output_to_file and os.path.exists(LanguageScanner.OUTPUT_FILE):
            do_std_out_print = True
            logger.error("%s output file already exists, falling back to writing to stdout",
                         LanguageScanner.OUTPUT_FILE)
        else:
            do_std_out_print = False

        if do_std_out_print:
            logger.debug("Outputting tasks to stdout...")
            print()
            for task in tasks:
                print(str(task))
            print()
            logger.debug("Done")
        else:
            logger.debug("Outputting tasks to %s...", LanguageScanner.OUTPUT_FILE)
            with open(LanguageScanner.OUTPUT_FILE, "wb") as out_file:
                for task in tasks:
                    out_file.write(str(task))
            logger.debug("Done")

    def run(self):
        """ Run method that facilitates building and outputting TODO tasks """
        logger.info("Running Language Scanner")

        for lang_mod_name in self._languages_to_scan:
            lang_mod = getattr(languages, lang_mod_name)

            try:
                file_exts = lang_mod.FILE_EXTENSIONS
            except AttributeError:
                logger.info("Skipping language %s, missing FILE_EXTENSIONS definition", lang_mod_name)
                continue

            try:
                todo_grammar = lang_mod.TODO_GRAMMAR
            except AttributeError:
                logger.info("Skipping language %s, missing TODO_GRAMMAR definition", lang_mod_name)
                continue

            logger.debug("Scanning for tasks")
            tasks = list(self.scan_for_tasks(file_exts, todo_grammar))
            self.output(tasks)


def main():
    """ Module's main method, easy enough to be packaged """
    parser = argparse.ArgumentParser(description="Scan for \"TODO definitions\" in developmental files and report on them")

    parser.add_argument("-a", "--all", action="store_true", help="Scan all languages")

    parser.add_argument("-l", "--language", action="append",
                        help="Specify the language(s) you want scanned ({})".format(", ".join(languages.__all__))
                       )

    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Provide debugging information"
                       )

    parser.add_argument("-o", "--output-to-file", action="store_true",
                        help="Output the TODO tasks to file instead of stdout"
                       )

    args = parser.parse_args()

    if args.all:
        languages_to_scan = languages.__all__
    elif args.language:
        languages_to_scan = args.language
        if set(languages_to_scan).difference(languages.__all__):
            raise argparse.ArgumentTypeError("Invalid or unsupported language provided")
    else:
        raise argparse.ArgumentTypeError("Either specify to scan for all languages or specified ones")

    if args.verbose:
        logger.setLevel(logging.DEBUG) # TODO ensure this actually works

    ls = LanguageScanner(languages_to_scan, args.output_to_file)
    ls.run()

if __name__ == "__main__":
    main()
