# Copyright 2017-2020 Palantir Technologies, Inc.
# Copyright 2021- Python Language Server Contributors.

import argparse
import logging
import logging.config
import sys
import time

try:
    import ujson as json
except Exception:  # pylint: disable=broad-except
    import json

from .python_lsp import (PythonLSPServer, start_io_lang_server,
                         start_tcp_lang_server, start_ws_lang_server)
from ._version import __version__

LOG_FORMAT = "%(asctime)s {0} - %(levelname)s - %(name)s - %(message)s".format(
    time.localtime().tm_zone)


def add_arguments(parser):
    parser.description = "Python Language Server"

    parser.add_argument(
        "--tcp", action="store_true",
        help="Use TCP server instead of stdio"
    )
    parser.add_argument(
        "--ws", action="store_true",
        help="Use Web Sockets server instead of stdio"
    )
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="Bind to this address"
    )
    parser.add_argument(
        "--port", type=int, default=2087,
        help="Bind to this port"
    )
    parser.add_argument(
        '--check-parent-process', action="store_true",
        help="Check whether parent process is still alive using os.kill(ppid, 0) "
        "and auto shut down language server process when parent process is not alive."
        "Note that this may not work on a Windows machine."
    )

    log_group = parser.add_mutually_exclusive_group()
    log_group.add_argument(
        "--log-config",
        help="Path to a JSON file containing Python logging config."
    )
    log_group.add_argument(
        "--log-file",
        help="Redirect logs to the given file instead of writing to stderr."
        "Has no effect if used with --log-config."
    )

    parser.add_argument(
        '-v', '--verbose', action='count', default=0,
        help="Increase verbosity of log output, overrides log config file"
    )

    parser.add_argument(
        '-V', '--version', action='version', version='%(prog)s v' + __version__
    )


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    args = parser.parse_args()
    _configure_logger(args.verbose, args.log_config, args.log_file)

    if args.tcp:
        start_tcp_lang_server(args.host, args.port, args.check_parent_process,
                              PythonLSPServer)
    elif args.ws:
        start_ws_lang_server(args.port, args.check_parent_process,
                             PythonLSPServer)
    else:
        stdin, stdout = _binary_stdio()
        start_io_lang_server(stdin, stdout, args.check_parent_process,
                             PythonLSPServer)


def _binary_stdio():
    """Construct binary stdio streams (not text mode).

    This seems to be different for Window/Unix Python2/3, so going by:
        https://stackoverflow.com/questions/2850893/reading-binary-data-from-stdin
    """
    stdin, stdout = sys.stdin.buffer, sys.stdout.buffer
    return stdin, stdout


def _configure_logger(verbose=0, log_config=None, log_file=None):
    root_logger = logging.root

    if log_config:
        with open(log_config, 'r', encoding='utf-8') as f:
            logging.config.dictConfig(json.load(f))
    else:
        formatter = logging.Formatter(LOG_FORMAT)
        if log_file:
            log_handler = logging.handlers.RotatingFileHandler(
                log_file, mode='a', maxBytes=50*1024*1024,
                backupCount=10, encoding=None, delay=0
            )
        else:
            log_handler = logging.StreamHandler()
        log_handler.setFormatter(formatter)
        root_logger.addHandler(log_handler)

    if verbose == 0:
        level = logging.WARNING
    elif verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG

    root_logger.setLevel(level)


if __name__ == '__main__':
    main()
