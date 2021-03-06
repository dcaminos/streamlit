# -*- coding: utf-8 -*-
# Copyright 2018-2019 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Manage the user's Streamlit credentials."""

import os
import sys
import textwrap
from collections import namedtuple

import click
import toml

from streamlit import util
from streamlit.logger import get_logger

LOGGER = get_logger(__name__)

Activation = namedtuple(
    "Activation",
    [
        "email",  # str : the user's email.
        "is_valid",  # boolean : whether the email is valid.
    ],
)

# For python 2.7
try:
    FileNotFoundError
except NameError:  # pragma: nocover
    FileNotFoundError = IOError


EMAIL_PROMPT = """
  👋 %(welcome)s

  If you are one of our development partners or are interested in
  getting personal technical support, please enter your email address
  below. Otherwise, you may leave the field blank.

  Email""" % {
    "welcome": click.style("Welcome to Streamlit!", fg="green")
}

TELEMETRY_TEXT = """
  Telemetry: as an open source project, we collect summary statistics
  and metadata to understand how people are using Streamlit.

  If you'd like to opt out, add the following to ~/.streamlit/config.toml,
  creating that file if necessary:

  [browser]
  gatherUsageStats = false
"""

INSTRUCTIONS_TEXT = """
  Get started by typing:
  $ %(hello)s
""" % {
    "hello": click.style("streamlit hello", bold=True)
}


class Credentials(object):
    """Credentials class."""

    _singleton = None

    @classmethod
    def get_current(cls):
        """Return the singleton instance."""
        if cls._singleton is None:
            Credentials()

        return Credentials._singleton

    def __init__(self):
        """Initialize class."""
        if Credentials._singleton is not None:
            raise RuntimeError(
                "Credentials already initialized. Use .get_current() instead"
            )

        self.activation = None
        self._conf_file = util.get_streamlit_file_path("credentials.toml")

        Credentials._singleton = self

    def load(self, auto_resolve=False):
        """Load from toml file."""
        if self.activation is not None:
            LOGGER.error("Credentials already loaded. Not rereading file.")
            return

        try:
            with open(self._conf_file, "r") as f:
                data = toml.load(f).get("general")
            self.activation = _verify_email(data.get("email"))
        except FileNotFoundError:
            if auto_resolve:
                return self.activate(show_instructions=not auto_resolve)
            raise RuntimeError(
                'Credentials not found. Please run "streamlit activate".'
            )
        except Exception as e:
            if auto_resolve:
                self.reset()
                return self.activate(show_instructions=not auto_resolve)
            raise Exception(
                textwrap.dedent(
                    """
                Unable to load credentials from %s.
                Run "streamlit reset" and try again.
                """
                )
                % (self._conf_file)
            )

    def check_activated(self, auto_resolve=False):
        """Check if streamlit is activated.

        Used by `streamlit run script.py`
        """
        try:
            self.load(auto_resolve)
        except (Exception, RuntimeError) as e:
            _exit(str(e))

        if not self.activation.is_valid:
            _exit("Activation email not valid.")

    @classmethod
    def reset(cls):
        """Reset credentials by removing file.

        This is used by `streamlit activate reset` in case a user wants
        to start over.
        """
        Credentials._singleton = None
        c = Credentials()
        try:
            os.remove(c._conf_file)
        except OSError as e:
            LOGGER.error("Error removing credentials file: %s" % e)

    def save(self):
        """Save to toml file."""
        data = {"email": self.activation.email}
        with open(self._conf_file, "w") as f:
            toml.dump({"general": data}, f)

    def activate(self, show_instructions=True):
        """Activate Streamlit.

        Used by `streamlit activate`.
        """
        try:
            self.load()
        except RuntimeError:
            pass

        if self.activation:
            if self.activation.is_valid:
                _exit("Already activated")
            else:
                _exit(
                    "Activation not valid. Please run "
                    "`streamlit activate reset` then `streamlit activate`"
                )
        else:
            activated = False

            while not activated:

                email = click.prompt(text=EMAIL_PROMPT, default="", show_default=False)

                self.activation = _verify_email(email)
                if self.activation.is_valid:
                    self.save()
                    click.secho(TELEMETRY_TEXT)
                    if show_instructions:
                        click.secho(INSTRUCTIONS_TEXT)
                    activated = True
                else:  # pragma: nocover
                    LOGGER.error("Please try again.")


def _verify_email(email):
    """Verify the user's email address.

    The email can either be an empty string (if the user chooses not to enter
    it), or a string with a single '@' somewhere in it.

    Parameters
    ----------
    email : str

    Returns
    -------
    Activation
        An Activation object. Its 'is_valid' property will be True only if
        the email was validated.

    """
    email = email.strip()

    if len(email) > 0 and email.count("@") != 1:
        LOGGER.error("That doesn't look like an email :(")
        return Activation(None, False)

    return Activation(email, True)


def _exit(message):  # pragma: nocover
    """Exit program with error."""
    LOGGER.error(message)
    sys.exit(-1)
