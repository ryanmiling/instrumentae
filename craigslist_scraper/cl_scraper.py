#!/usr/bin/python
# -*- coding: utf-8 -*-

__version__ = "1.0.0"

from abc import ABCMeta, abstractproperty
from utils import prompt

import csv
import logging
import os


LOGGING_FORMAT = "%(asctime)s %(levelname)s: %(message)s"
logging.basicConfig(format=LOGGING_FORMAT)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # default

# TODO make filepath absolute for future usage
CSV_DIR = os.path.join(os.getcwd(), "csv")
MAX_CSV_ROWS = 1000 # TODO find the sweet number (i.e. fast I/O, not too much in memory)
SLEEP_TIME = 30

class IntensiveOpException(Exception):
    """ Exception raised when we don't want to repeat an already intensive operation. """
    pass


class MissingDataException(Exception):
    """ Exception raised when content is missing from the HTML document being parsed. """
    pass


def get_matching_csv_files(root_filename):
    """ Get all CSV files that match the passed-in criteria.

    :param root_filename: Return filenames that start with this root
    :type root_filename: str

    :returns: List of filenames matching the criteria
    :rtype: list
    """
    filenames = []
    for filename in os.listdir(CSV_DIR):
        if filename.startswith(root_filename):
            filenames.append(os.path.join(CSV_DIR, filename))

    return filenames


def get_next_csv_filename(root_filename, last_index=0, is_interactive=False):
    """ Get the next CSV filename we should use to avoid overwriting.

    :param root_filename: Filename the CSV should start with
    :type root_filename: str

    :param last_index: Last filename index
    :type last_index: int

    :param is_interactive: Script can expect input from end user
    :type is_interactive: bool

    :returns: CSV filename
    :rtype: str
    """
    if last_index == 0:
        file_index = ""
    else:
        file_index = last_index + 1

    filename = "{}{}.csv".format(root_filename, file_index)

    filename_path = os.path.join(CSV_DIR, filename)
    if os.path.exists(filename_path):
        if last_index == 0 and is_interactive:
            # prompt before repeating an operation already done
            res = prompt(("{} already exists, you may be repeating an intensive operation. "
                          "Continue?").format(filename), ("y", "N"))
            if res == "N":
                ex_msg = "Avoiding operations that would regenerate {}".format(filename)
                logger.warning(ex_msg)
                raise IntensiveOpException(ex_msg)

        return get_next_csv_filename(root_filename, file_index or 1, is_interactive)
    else:
        return filename_path


def csv_out(root_filename, header, rows_per_file=MAX_CSV_ROWS):
    """ CSV file-writer and context manager for writing many CSV files.

    :param root_filename: Filename the CSV should start with
    :type root_filename: str

    :param header: Header of the CSV file
    :type header: tuple<str>

    :param rows_per_file: Max number of rows to write to each CSV file
    :type rows_per_file: int

    :returns: Decorated method's return
    :rtype: Anything
    """
    def csv_out_decorator(method):
        def wrapper(self, *args, **kwargs):
            def save_rows(rows, filename):
                """ Save the provided rows to the CSV file.

                :param rows: List of lists of values
                :type rows: list

                :param filename: CSV file to save
                :type filename: str
                """
                logger.info("Saving %s", filename)

                row_save_count = 0
                with open(filename, "wb") as csv_file:
                    csv_writer = csv.writer(csv_file)
                    csv_writer.writerow(header)
                    for row in rows:
                        if row is None:
                            break

                        csv_writer.writerow(row)
                        row_save_count += 1

                logger.debug("Successfully saved %s rows", row_save_count)

            filename = None
            file_index = 0

            rows_counter = 0 # how many rows will be written, also a signal whether or not to write rows
            empty_rows = [None for i in xrange(rows_per_file)] # init to this size
            rows = empty_rows[:]

            try:
                filename = get_next_csv_filename(root_filename, file_index, self.is_interactive)
                file_index += 1

                logger.debug("Building CSV rows...")

                for row in method(self, *args, **kwargs):
                    rows[rows_counter] = row
                    rows_counter += 1

                    if rows_counter % rows_per_file == 0:
                        save_rows(rows, filename)

                        # prep for next file
                        filename = get_next_csv_filename(root_filename, file_index, self.is_interactive)
                        file_index += 1

                        # reset
                        rows = empty_rows[:]
                        rows_counter = 0

                logger.debug("Done building CSV rows")
            except IntensiveOpException: # nothing will happen, fail gracefully
                logger.info("Skipping an intensive operation")
                rows_counter = 0
            finally:
                # save any intermediary results, then exception is raised
                if rows_counter:
                    save_rows(rows, filename)

        return wrapper
    return csv_out_decorator


class CLScraper(object):
    """ Abstract base class to scrape Craiglist for content and outputs them into CSVs. """
    __metaclass__ = ABCMeta

    def __init__(self, is_interactive=False, scrape_types=None):
        """ Initialize our scraper.

        :param is_interactive: Script is being monitored by an end user
        :type interactivemode: bool

        :param scrape_types: Run these types of scraping
        :type scrape_types: list
        """
        self._scrape_types = scrape_types
        self.is_interactive = is_interactive

    @abstractproperty
    def scrape_types(self):
        pass

    def run(self):
        """ Run the scraper with the initialized configuration from the constructor. """
        if not self._scrape_types:
            scraping_to_do = self.scrape_types
        else:
            if set(self._scrape_types).difference(set(self.scrape_types)): # leftovers means invalidities
                raise ValueError("Actions must be one of {}".format(", ".join(self.scrape_types)))
            scraping_to_do = self._scrape_types

        logger.info("Running scraper with methods %s", ", ".join(scraping_to_do))

        for s_type in scraping_to_do:
            ret = getattr(self, s_type)()

