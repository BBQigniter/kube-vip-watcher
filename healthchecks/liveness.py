#!/usr/bin/env python3

# needed so we can import the logging library from the lib-folder
import os
import sys
import psutil

currentdir = os.path.dirname(os.path.realpath(__file__))
parentdir = os.path.dirname(currentdir)
sys.path.append(parentdir)


def check_if_process_running(process_name):
    for proc in psutil.process_iter():
        try:
            # Check if process name contains the given name string.
            if (process_name.lower() in proc.name().lower()) \
                or \
               (any(process_name.lower() in cmdline_parameter.lower() for cmdline_parameter in proc.cmdline())):
                return True
            # endif
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            print("Readiness-Probe: no process running with %s" % process_name)
        # endtry
    # endfor

    return False
# enddef


def main():
    process_name = "kube-vip-watcher"

    # Check if any the main script is running or not.
    if not check_if_process_running(process_name):
        print('Readiness-Probe: No %s process is running' % process_name)
        sys.exit(1)
    # endif
# endmain


if __name__ == '__main__':
    main()
# endif
