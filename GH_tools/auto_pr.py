#!/usr/local/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import print_function

import argparse
import os
import requests
import subprocess

__version__ = "1.0.0"

ACCESS_TOKEN_FILE = "~/.gh_token"

BASE_BRANCH = "master"
REPO_OWNER = "rynmlng" # TODO allow this to be user-inputted

def prompt(message, options=None, allow_empty=False):
    """ Prompt user for an answer

    :param message: Prompting mesage for the user
    :type message: str

    :param options: Limited answers
    :type options: list

    :param allow_empty: Allow no input
    :type allow_empty: bool

    :returns: Answer from user
    :rtype: str
    """
    ret = ""
    if options:
        query = "{} ({}) > ".format(message, ",".join(options))
    else:
        query = "{} > ".format(message)

    while not ret:
        ret = raw_input(query)
        if allow_empty and not ret:
            break

    return ret


def load_token():
    """ Load the access token from the access token file
    
    :returns: GitHub API access token
    :rtype str:
    """
    token_file_path = os.path.expanduser(ACCESS_TOKEN_FILE)

    access_token = None
    write_to_file = False
    if os.path.exists(token_file_path):
        with open(token_file_path, "rb") as token_file:
            access_token = token_file.read().strip()

        if not access_token and prompt("Token file is malformed, overwrite?", options=["y","N"]) == "N":
            write_to_file = True
    else:
        write_to_file = True

    if not access_token:
        access_token = prompt("Enter your GitHub API token (https://github.com/settings/tokens, scope=repo)")

    if write_to_file:
        with open(token_file_path, "wb") as token_file:
            token_file.write(access_token)

    return access_token


def create_pull_request(access_token):
    """ Create a pull request using the provided access token
    
    :param access_token: GitHub API access token
    :type access_token: str
    """
    headers = {"Authorization": "token {}".format(access_token)}

    repo_path = subprocess.check_output(["git", "rev-parse", "--show-toplevel"]).strip()
    repo = os.path.basename(repo_path)

    url = "https://api.github.com/repos/{owner}/{repo}/pulls".format(owner=REPO_OWNER, repo=repo)

    params = {}

    ########
    # TITLE
    ########
    default_title = subprocess.check_output(["git","log","-1","--pretty=%B"]).strip()
    if default_title:
        title = prompt("Enter a title (default={})".format(default_title), allow_empty=True)

    params["title"] = title or default_title

    ########
    # HEAD
    ########
    pr_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if pr_branch == BASE_BRANCH:
        raise ValueError("Your PR branch cannot be the base branch ({})!".format(BASE_BRANCH))

    params["head"] = pr_branch

    ########
    # BASE
    ########
    params["base"] = BASE_BRANCH

    ###########
    # COMMENTS
    ###########
    body = prompt("Enter a body message (optional)", allow_empty=True)
    if body:
        params["body"] = body

    res = requests.post(url, headers=headers, json=params).json()
    if "errors" in res:
        for error in res["errors"]:
            print("\nERROR! {}\n".format(error))
        print("Some common mistakes:")
        print("  [ ] Did you make sure to push your branch?")
        print("  [ ] Are there any commits on this branch?")
    else:
        print("\nView your PR at {}".format(res["html_url"]))
        print("Don't forget to assign and add labels!")


def main():
    """ Module's main method, easily packagable. """
    parser = argparse.ArgumentParser(description="GitHub Auto-PR Generator, v{}".format(__version__))
    args = parser.parse_args()

    try:
        with open(os.devnull, "w") as FNULL:
            is_work_tree = subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"],
                                                   stderr=FNULL).strip()
    except subprocess.CalledProcessError:
        is_work_tree = "false"

    if is_work_tree == "false":
        raise RuntimeError("Must be run in a git work tree")

    token = load_token()
    create_pull_request(token)


if __name__ == "__main__":
    main()
