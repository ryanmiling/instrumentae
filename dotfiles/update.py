#!/usr/bin/python

from __future__ import print_function
import datetime
import os
import subprocess

COMMIT_BRANCH = "master"
DOT_FILE_DIRS = ("conf",)

def main():
    """ Scans each dot-file dir's files for any changes and commits them to the repo.
        Assumes that each dot-file is in the user's home directory.
    """
    this_path = os.path.dirname(os.path.realpath(__file__))
    os.chdir(this_path)

    # if we're not in the commit branch don't do anything
    curr_branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    curr_branch = curr_branch.replace("\n", "")
    if curr_branch != COMMIT_BRANCH:
        raise Exception("Env incorrectly set - must be checked into "
                        "{0} repo!".format(COMMIT_BRANCH))

    has_updates = False
    for rel_file_dir in DOT_FILE_DIRS:
        abs_file_dir = os.path.join(this_path, rel_file_dir)
        print("Scanning {0}".format(rel_file_dir))
        os.chdir(abs_file_dir)

        try:
            for rel_dot_file in os.listdir(abs_file_dir):
                my_dot_file = "{0}/.{1}".format(os.path.expanduser("~"), rel_dot_file)
                out_file = os.path.join(abs_file_dir, rel_dot_file)

                # pull in the latest bash files
                print("  {0}".format(rel_dot_file))
                print("   |-copying")
                subprocess.check_call(["cp", "-f", my_dot_file, out_file])

                # use git to check for changes
                res = subprocess.check_output(["git", "diff", "."])
                if res != "":
                    print("   |-change found, adding to repo")
                    has_updates |= True

                    subprocess.check_call(["git", "add", rel_dot_file])
                else:
                    print("   |-no changes")
        except Exception:
            # rollback any changes, but only for dot-file dir
            print("  Something bad happened, rolling back changes")
            subprocess.call(["git", "checkout", "--", "."])

        print()

    if has_updates:
        today = datetime.date.today().strftime("%Y/%m/%d")
        commit_msg = "AUTO-UPDATE dotfile changes discovered {0}".format(today)
        print("Committing branch")
        subprocess.check_call(["git", "commit", "-m", commit_msg])
        print("Pushing branch")
        subprocess.check_call(["git", "push", "origin", COMMIT_BRANCH])

if __name__ == "__main__":
    main()
