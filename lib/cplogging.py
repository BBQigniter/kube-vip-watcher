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

# Info
# This module can be used in any Python script/program it's a wrapper
# for easy usage of writing logs to console (in color), files and/or syslog-servers
# simultaneously

# Prerequisites
# non-standard Python modules - coloredlogs (pip install coloredlogs)

# Usage
# Create a subfolder e.g. lib and copy the __init__.py, settings.py and
# cplogging.py into that subfolder. In your main-script you then can use it by
# importing (import lib.settings if you want to override settings in your main
# script):
#     import lib.settings
#     from lib.cplogging import Cplogging
#
# You can override the settings in settings.py - for example if you want to set
# a higher log-level:
#     lib.settings.global_log_level = "debug"
#
# Else you can directly edit the default values in the settings.py file. More
# info about the different options are in the file.
#
# To finally log something you first have to initialize a logger. E.g.
#     # define your own name in main for nicer readability
#     logger_name = "main" # else the '__name__' will be used
#     # you may set explicitly a different log_level and/or log_file
#     # for example if you want to explicitly debug a function/method
#     logger = Cplogging(logger_name)
#     logger.info("info test")

# Example
# log output:
# 2018-03-01 10:07:21 NB674F4F-vm.example.com log_test.py[8499]: MODULE: main LEVEL: INFO MESSAGE: info test

# Changelog:
#
# 2018-02-01 -- initial release
# 2021-04-28 -- added "class MyFormatter" so log-timestamps with real ISO8601 timeformat can be created

import logging
import logging.handlers
import coloredlogs
#from . import settings
import lib.settings as settings
import inspect
import time


# copied from https://stackoverflow.com/a/48212344
class MyFormatter(logging.Formatter):

    def formatTime(self, record, datefmt=None):
        ct = self.converter(record.created)
        if datefmt:
            # print(datefmt)
            if "%F" in datefmt:
                msec = "%03d" % record.msecs
                datefmt = datefmt.replace("%F", msec)
            s = time.strftime(datefmt, ct)
        else:
            t = time.strftime("%Y-%m-%d %H:%M:%S", ct)
            s = "%s,%03d" % (t, record.msecs)
        return s


class Cplogging(object):
    def __init__(self, logger_name, log_level=None, log_file_path=None):
        self.logger_name = logger_name
        self.log_level = log_level
        self.log_file_path = log_file_path

        # we get the global settings
        global_log_level = settings.global_log_level
        global_log_file_path = settings.global_log_file_path
        global_log_format = settings.global_log_format
        global_log_file_format = settings.global_log_file_format
        global_log_server_enable = settings.global_log_server_enable
        global_log_server = settings.global_log_server
        global_log_server_format = settings.global_log_server_format

        if global_log_file_path != log_file_path:
            if log_file_path is None:
                log_file_path = global_log_file_path

        if log_file_path == "disabled":
            # TODO: find a nicer option to disable writting a file
            log_file_path = "/dev/null"

        if global_log_level != log_level:
            if log_level is None:
                log_level = global_log_level
            # else:
            #    log_level = log_level

        # we set the log_level if nothing is defined
        if global_log_level is None and log_level is None:
            log_level = "info"

        global logger
        logger = logging.getLogger(logger_name)
        # coloredlogs supports normal ISO8601 format and strftime variables
        coloredlogs.install(level=log_level, logger=logger, fmt=global_log_format, datefmt="%Y-%m-%dT%H:%M:%S.%f%z")
        if global_log_file_path is not None or log_file_path is not None:
            logfile_writer = logging.FileHandler(log_file_path)
            logger.addHandler(logfile_writer)
            # logfile_writer.setFormatter(logging.Formatter(global_log_file_format, datefmt="%Y-%m-%dT%H:%M:%S.%F%z"))
            # Here we use our own formatter to get a nice ISO8601 timestamp
            logfile_writer.setFormatter(MyFormatter(global_log_file_format, datefmt="%Y-%m-%dT%H:%M:%S.%F%z"))

        # if in the settings sending logs to a syslog server is enabled and a server is set
        # we attach a syslogger handler to the logging stuff
        if global_log_server_enable:
            syslogger = logging.getLogger(logger_name)
            syslogger.setLevel(getattr(logging, global_log_level.upper()))
            handler = logging.handlers.SysLogHandler(address=global_log_server)
            # formatter = logging.Formatter(fmt=global_log_server_format, datefmt="%Y-%m-%dT%H:%M:%S.%F%z")
            # Here we use the our own formatter to get a nice ISO8601 timestamp
            formatter = MyFormatter(global_log_server_format, datefmt="%Y-%m-%dT%H:%M:%S.%F%z")
            handler.setFormatter(formatter)
            syslogger.addHandler(handler)

    # for the following methods we inspect from where the method is called thanks to:
    # https://stackoverflow.com/questions/17065086/how-to-get-the-caller-class-name-inside-a-function-of-another-class-in-python
    # then we shadow the logger variable to write to the correct logging handler
    # @staticmethod
    def info(self, msg):
        stack = inspect.stack()
        # print(stack[1][0].f_locals)
        try:
            logger_name = stack[1][0].f_locals['logger_name']
        except KeyError:
            logger_name = self.logger_name
        logger = logging.getLogger(logger_name)
        logger.info(msg)

    # @staticmethod
    def warning(self, msg):
        stack = inspect.stack()
        try:
            logger_name = stack[1][0].f_locals['logger_name']
        except KeyError:
            logger_name = self.logger_name
        logger = logging.getLogger(logger_name)
        logger.warning(msg)

    # @staticmethod
    def debug(self, msg):
        stack = inspect.stack()
        try:
            logger_name = stack[1][0].f_locals['logger_name']
        except KeyError:
            logger_name = self.logger_name
        logger = logging.getLogger(logger_name)
        logger.debug(msg)

    # @staticmethod
    def error(self, msg):
        stack = inspect.stack()
        try:
            logger_name = stack[1][0].f_locals['logger_name']
        except KeyError:
            logger_name = self.logger_name
        logger = logging.getLogger(logger_name)
        logger.error(msg)

    # @staticmethod
    def critical(self, msg):
        stack = inspect.stack()
        try:
            logger_name = stack[1][0].f_locals['logger_name']
        except KeyError:
            logger_name = self.logger_name
        logger = logging.getLogger(logger_name)
        logger.critical(msg)

    @staticmethod
    def destroy_handler():
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
