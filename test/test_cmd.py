""" Tests for the command line executable. """

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

from edx_lint.cmd import main


PYLINTRC = "pylintrc"
PYLINTRC_TWEAKS = "pylintrc_tweaks"
PYLINTRC_BACKUP = "pylintrc_backup"

EDITORCONFIG = ".editorconfig"

JUST_TESTING = "just_for_testing.txt"


class CommandTest(unittest.TestCase):
    """Helpers for testing commands."""

    def setUp(self):
        super().setUp()

        # Make a temporary directory to work in, and rm-rf it when we're done.
        tempdir = tempfile.mkdtemp(suffix="_edx_lint_test")
        self.addCleanup(shutil.rmtree, tempdir)

        # Change into the temp directory, and change back when we are done.
        thisdir = os.getcwd()
        self.addCleanup(os.chdir, thisdir)
        os.chdir(tempdir)

        # Assure the file does not already exist.
        self.assert_not_file(PYLINTRC)

    def call_command(self, argv=None):
        """Call an edx_lint script command.

        Arguments:
            argv (list) -- arguments to pass to the edx_lint script
        """
        self    # pylint: disable=pointless-statement
        return main.main(argv)

    def assert_file(self, filename, contains=None, not_contains=None):
        """Assert that a file exists, and optionally, contains some text."""
        self.assertTrue(os.path.isfile(filename))
        if contains is not None or not_contains is not None:
            with open(filename) as f:
                text = f.read()
                if contains is not None:  # pragma: no branch
                    self.assertIn(contains, text)
                if not_contains is not None:  # pragma: no branch
                    self.assertNotIn(not_contains, text)

    def assert_not_file(self, filename):
        """Assert that a file doesn't exist."""
        self.assertFalse(os.path.isfile(filename))


class WriteCommandTest(CommandTest):
    """Tests for the write command."""

    def test_write_arg_errors(self):
        self.assertEqual(1, self.call_command(["write"]))
        self.assertEqual(2, self.call_command(["write", "xyzzy"]))

    def test_write_creates_pylintrc(self):
        """ Verify the command writes a pylintrc file. """
        # Create the pylintrc.
        self.assertEqual(0, self.call_command(["write", PYLINTRC]))
        self.assert_file(PYLINTRC, contains="*****\n# ** DO NOT EDIT THIS FILE **\n# *****")
        self.assert_file(PYLINTRC, not_contains="you must edit the central file", contains="LOCAL CHANGE")
        self.assert_file(PYLINTRC, contains="\n[MASTER]\n")
        self.assert_file(PYLINTRC, not_contains="\n# \n")

        # Try to create it again, it will verify it.
        self.assertEqual(0, self.call_command(["write", PYLINTRC]))

    def test_write_backups_modified_file(self):
        # Make the pylintrc.
        self.assertEqual(0, self.call_command(["write", PYLINTRC]))
        self.assert_file(PYLINTRC)
        self.assert_not_file(PYLINTRC_BACKUP)

        # Modify it.
        with open(PYLINTRC, "a") as pylintrc:
            pylintrc.write("# modified!\n")

        # Try to write again.
        self.assertEqual(0, self.call_command(["write", PYLINTRC]))
        self.assert_file(PYLINTRC_BACKUP, contains="# modified!")

        # And if we write again, the previous backup is deleted.
        with open(PYLINTRC, "a") as pylintrc:
            pylintrc.write("# changed!\n")
        self.assertEqual(0, self.call_command(["write", PYLINTRC]))
        self.assert_file(
            PYLINTRC_BACKUP, contains="# changed!", not_contains="# modified!"
        )

    def test_write_applies_tweaks(self):
        # Create a tweaks file.
        with open(PYLINTRC_TWEAKS, "w") as tweaks:
            tweaks.write("[MASTER]\nxyzzy = plugh\n")

        # Write the pylintrc.
        self.assertEqual(0, self.call_command(["write", PYLINTRC]))

        # The tweak is in there!
        self.assert_file(PYLINTRC, contains="xyzzy = plugh")

    def test_file_types(self):
        self.assertEqual(0, self.call_command(["write", JUST_TESTING]))
        self.assert_file(JUST_TESTING, contains="\n-- ** DO NOT EDIT")
        self.assert_file(JUST_TESTING, contains="you must edit the central file", not_contains="LOCAL CHANGE")


class UpdateCommandTest(CommandTest):
    """Tests for the update command."""

    def test_no_files_exist(self):
        self.assertEqual(0, self.call_command(["update"]))
        self.assert_not_file(PYLINTRC)
        self.assert_not_file(EDITORCONFIG)

    def test_one_file_exists(self):
        # Write the initial version of pylintrc.
        self.assertEqual(0, self.call_command(["write", PYLINTRC]))
        self.assert_file(PYLINTRC, contains="[MASTER]")
        self.assert_not_file(EDITORCONFIG)

        # Pretend edx-lint has a newer version of pylintrc, and update files.
        with patch("edx_lint.write.get_file_content") as get_file_content:
            get_file_content.return_value = "[xyz]\nsetting = True"
            self.assertEqual(0, self.call_command(["update"]))

        # pylintrc is re-written with new content.
        self.assert_file(PYLINTRC, contains="setting = True")
        self.assert_file(PYLINTRC, not_contains="[MASTER]")
        # .editorconfig still hasn't been written.
        self.assert_not_file(EDITORCONFIG)

    def test_update_backs_up_handwritten_files(self):
        # Create a hand-written pylintrc file:
        with open(PYLINTRC, "w") as pylintrc:
            pylintrc.write("[bogus]\nnot_really = pylintrc\n")

        # Update will see it's not one made by edx-lint, and move it aside.
        self.assertEqual(0, self.call_command(["update"]))

        # The backup file is our original hand-written file.
        self.assert_file(PYLINTRC_BACKUP, contains="not_really = pylintrc")
        # The pylintrc file was written by edx-lint.
        self.assert_file(PYLINTRC, contains="[MASTER]")
