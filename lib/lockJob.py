#!/usr/bin/env python

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Prerequisites
# non-standard Python modules - Cplogging

# Info
# This module is for locking the process so that it may not started multiple
# times

# Usage
# Create a subfolder e.g. lib and copy the __init__.py, settings.py,
# cplogging.py and lockJob.py into that subfolder.
# In your main-script you then can use it by
# importing (import lib.settings if you want to override log-settings in your
# main script):
#     import lib.settings
#     from lib.lockJob import LockJob
#     from lib.cplogging import Cplogging
#
# You then can use the module to lock the process for example somewhere in your
# code after some checks or from the start of the main script on by just calling:
#     mylock1 = LockJob(section="part1")
#     mylock1.create()
#     # do important stuff that must not run twice at the same time
#     mylock1.destroy()
#     mylock2 = LockJob(section="part2")
#     mylock2.create()
#     # do other stuff
#     mylock2.destroy()
#
# The module has some extra-features, you can set a lock by giving them
# names, set a higher log_level (default "info") for debugging or set a
# different log-file ("disable" by default)
# If you do not destroy your locks, they will stay as long as the program is
# running. After it's finished the sockets will be garbage collected.
#
# LockJob(
#        # process_name="my_programm",
#        # section="my_sublock",
#        # log_level="info",
#        # log_file_path="/home/administrator/PycharmProjects/tests/docker_control_v4/logs/lockJob.log"
# )

# Example
# see above

# Changelog:
#
# 2018-03-01 -- initial release
# 2018-03-06 -- added method to close a socket after it's not needed anymore this makes
#               it possible to lock a process if it reaches critical parts that must
#               not run multiple times.


import __main__
import sys
import os
import socket
from . import settings
from .cplogging import Cplogging


class LockJob(object):
    def __init__(
                 self,
                 process_name=str(os.path.basename(__main__.__file__)),
                 section=None,
                 log_level=None,
                 log_file_path=None,
                ):
        self.process_name = process_name
        self.section = section
        self.log_level = log_level
        self.log_file_path = log_file_path
        self.lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

        # we create a log handler
        self.logger_name = str(__name__)
        self.logger = Cplogging(self.logger_name, log_level=self.log_level, log_file_path=self.log_file_path)

        # we get the global settings
        global_log_level = settings.global_log_level
        global_log_file_path = settings.global_log_file_path

        if global_log_file_path != log_file_path:
            if log_file_path is None:
                self.log_file_path = global_log_file_path
            elif log_file_path == "disabled":
                # TODO: find a nicer option to disable writting a file
                self.log_file_path = "/dev/null"

        if global_log_level != log_level:
            if log_level is None:
                self.log_level = global_log_level
            # else:
            #    log_level = log_level

    def create(self):
        self.logger.info("creating lock")
        if self.log_level == "info":
            self.logger.info("explicit set log_level: %s" % self.log_level)
        else:
            self.logger.debug("explicit set log_level: %s" % self.log_level)

        # Without holding a reference to our socket somewhere it gets garbage
        # collected when the function exits
        if self.section is None:
            section = self.process_name
            self.logger.debug("Section set to process_name: %s" % str(self.process_name))
        else:
            section = self.section
        # endif

        try:
            self.lock_socket.bind('\0' + self.process_name + section)
            self.logger.info("Process locked for %s" % str(self.process_name))
        except socket.error:
            self.logger.error("%s already running. Please, try again later." % str(self.process_name))
            sys.exit(253)
        # endtry
    # enddef

    def destroy(self):
        # we close the corresponding abstract socket
        self.lock_socket.close()
        self.logger.info("Process lock removed for %s" % str(self.process_name))
        # we have to remove the logging handler - else we would see dupilicated messages
        self.logger.destroy_handler()
    # enddef
