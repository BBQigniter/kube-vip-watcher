#!/usr/bin/env python

import time
import socket
import lib.settings
from lib.cplogging import Cplogging
from lib.lockJob import LockJob

# OVERRIDE GLOBAL SETTINGS from lib/settings.py
# log-level may be set to: "info" (default), "warning", "debug", "critical", "error"
lib.settings.global_log_level = "debug"
# where do you want a log-file - default "disabled"
lib.settings.global_log_file_path = "/home/administrator/PycharmProjects/log_n_lock/logs/example.log"
# if you override the global_filename you also have to override the log_format variables! else the override won't have any effect
lib.settings.global_process_name = "example.py"
# log_format for console, file and syslog
#     - attributes: https://docs.python.org/2/library/logging.html#logrecord-attributes
#     - hostname a special from coloredlogs python module
# %(asctime)s is configured in cplogging.py - see lines with datefmt="%Y-%m-%dT%H:%M:%S.%F%z"
lib.settings.global_log_format = "%(asctime)s " + socket.gethostname() + " " + lib.settings.global_process_name + \
                                 "[%(process)d]: MODULE: %(name)s LEVEL: %(levelname)s MESSAGE: %(message)s"
lib.settings.global_log_file_format = "%(asctime)s " + socket.gethostname() + " " + lib.settings.global_process_name + \
                                      "[%(process)d]: MODULE: %(name)s LEVEL: %(levelname)s MESSAGE: %(message)s"
lib.settings.global_log_server_format = "%(asctime)s " + socket.gethostname() + " " + lib.settings.global_process_name + \
                                        "[%(process)d]: MODULE: %(name)s LEVEL: %(levelname)s MESSAGE: %(message)s"
# enable or disable sending to syslog
lib.settings.global_log_server_enable = True
# where should the syslogs be sent - IP/FQDN and port (UDP)
lib.settings.global_log_server = ("log-destination.example.com", 1514)


def main():
    # we create a separate logger for the main-program - this shadows the corresponding variable
    # so it writes to the correct logging-handler - in this case we use "main" as logger_name
    # else it would default to __main__
    logger_name = "main"
    # other examples how to create a log-handler
    # logger = Cplogging("main", log_level=lib.settings.global_log_level, log_file_path=lib.settings.global_log_file_path)
    # logger = Cplogging(logger_name, log_file_path="/home/administrator/PycharmProjects/tests/log_n_lock/logs/example.log")
    # logger = Cplogging(logger_name, log_file_path="disabled")
    logger = Cplogging(logger_name)
    logger.info("info test")
    logger.debug("debug test")
    # this will explicitly use the "info" log-level
    lock1 = LockJob(
        process_name="example_part1",
        section="part1",
        log_level="info",
        # log_file_path="/home/administrator/PycharmProjects/tests/log_n_lock/logs/lockJob.log"
        # log_file_path="disabled"
    )
    lock1.create()

    logger.info("will sleep - while sleeping you can 'watch -n1 'netstat -alp | grep example' on a console'")
    time.sleep(5)
    # we destroy the lock as we do not need it anymore. besides the corresponding logger will be removed too
    lock1.destroy()
    logger.info("sleeping finished")
    # this will explicitly log the messages into a different log-file and set a higher log-level
    lock2 = LockJob(
        process_name="example_part2",
        section="part2",
        log_level="debug",
        #log_file_path="/home/administrator/PycharmProjects/tests/log_n_lock/logs/lockJob.log"
        log_file_path=lib.settings.global_log_file_path
    )
    # the lock will stay until the script is finished because later we do not destroy it as seen with lock1
    lock2.create()
    logger.info("will sleep again")
    time.sleep(15)
    logger.info("sleeping finished")
# enddef


if __name__ == '__main__':
    logger_name = "real_main"
    # this will explicitly disable logging to the globally defined log-file
    logger = Cplogging(logger_name, log_file_path="disabled")
    logger.debug("debug test starting main()")
    main()
    logger.debug("debug test finished main()")
# endif
