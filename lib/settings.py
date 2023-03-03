import __main__
import os
import socket
import json

# we get the filename from the main calling script
# ATTENTION: if you override this in your main program/script, you also have to override
# the log_format variables! else the override won't have any effect
global_process_name = str(os.path.basename(__main__.__file__))

# settings that may be used in all other classes
# currently one of the following levels may be chosen: "info", "warning", "debug", "error", "critical"
global_log_level = "info"

# set either string or json
global_log_format_type = "json"

if global_log_format_type == "string":
    global_set_log_format = "%(asctime)s " + socket.gethostname() + " " + global_process_name + "[%(process)d]: MODULE: %(name)s LEVEL: %(levelname)s MESSAGE: %(message)s"
else:
    global_set_log_format = {
        "@timstamp": "%(asctime)s",
        "host": {
            "name": socket.gethostname()
        },
        "process": {
            "name": global_process_name,
            "id": "%(process)d",
            "module": "%(name)s"
        },
        "log": {
            "level": "%(levelname)s"
        },
        "message": "%(message)s"
    }
    global_set_log_format = json.dumps(global_set_log_format)
# endif

# the log format shown on the console
# attributes: https://docs.python.org/2/library/logging.html#logrecord-attributes
# global_log_format = "%(asctime)s " + socket.gethostname() + " " + global_process_name + "[%(process)d]: MODULE: %(name)s LEVEL: %(levelname)s MESSAGE: %(message)s"
global_log_format = global_set_log_format

# Set a default log-file - if "disabled" no logfile is written! else give a full-path e.g.: /logs/example.log
global_log_file_path = "disabled"
# the log format written to a file
# global_log_file_format = "%(asctime)s " + socket.gethostname() + " " + global_process_name + "[%(process)d]: MODULE: %(name)s LEVEL: %(levelname)s MESSAGE: %(message)s"
global_log_file_format = global_set_log_format

# send syslog messages
# set to True or False to enable or disable logging to the given syslog-server
# the global_log_format will be used
global_log_server_enable = False
global_log_server = ("127.0.0.1", 1514)  # IP/FQDN and port (UDP)
# the log format for syslog messages
# global_log_server_format = "%(asctime)s " + socket.gethostname() + " " + global_process_name + "[%(process)d]: MODULE: %(name)s LEVEL: %(levelname)s MESSAGE: %(message)s"
global_log_server_format = global_set_log_format
