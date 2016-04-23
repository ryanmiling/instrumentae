# -*- coding: utf-8 -*-

import time


def prompt(message, options=None):
    """ Prompt user in interactive shell for an answer, optionally limiting input

    :param message: Prompting message for the user
    :type message: str

    :param options: Limited answers
    :type options: collection

    :returns: Answer from user
    :rtype: str
    """
    ret = ""

    if options:
        query = "{} ({}) > ".format(message, ",".join(options))
    else:
        query = "{} > ".format(message)

    while not ret or (options and ret not in options):
        ret = raw_input(query)

    return ret


def retry(partial, sleep, max_retries=5):
    """ Calls a partial function until it returns or we hit the max retry count.

    :param partial: Partial function
    :type partial: functools.partial

    :param max_retries: Maximum amount of retries for the function's return value
    :type max_retries: int

    :returns: Function's return value
    :rtype: Anything
    """
    i = 0
    while i < max_retries:
        i += 1
        try:
            return partial()
        except Exception:
            if i == max_retries:
                raise
            time.sleep(sleep)
