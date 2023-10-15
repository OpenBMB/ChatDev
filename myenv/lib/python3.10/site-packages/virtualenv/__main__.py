from __future__ import annotations

import logging
import os
import sys
from datetime import datetime


def run(args=None, options=None, env=None):
    env = os.environ if env is None else env
    start = datetime.now()
    from virtualenv.run import cli_run
    from virtualenv.util.error import ProcessCallFailed

    if args is None:
        args = sys.argv[1:]
    try:
        session = cli_run(args, options, env)
        logging.warning(LogSession(session, start))
    except ProcessCallFailed as exception:
        print(f"subprocess call failed for {exception.cmd} with code {exception.code}")
        print(exception.out, file=sys.stdout, end="")
        print(exception.err, file=sys.stderr, end="")
        raise SystemExit(exception.code)


class LogSession:
    def __init__(self, session, start):
        self.session = session
        self.start = start

    def __str__(self):
        spec = self.session.creator.interpreter.spec
        elapsed = (datetime.now() - self.start).total_seconds() * 1000
        lines = [
            f"created virtual environment {spec} in {elapsed:.0f}ms",
            f"  creator {str(self.session.creator)}",
        ]
        if self.session.seeder.enabled:
            lines.append(f"  seeder {str(self.session.seeder)}")
            path = self.session.creator.purelib.iterdir()
            packages = sorted("==".join(i.stem.split("-")) for i in path if i.suffix == ".dist-info")
            lines.append(f"    added seed packages: {', '.join(packages)}")

        if self.session.activators:
            lines.append(f"  activators {','.join(i.__class__.__name__ for i in self.session.activators)}")
        return "\n".join(lines)


def run_with_catch(args=None, env=None):
    from virtualenv.config.cli.parser import VirtualEnvOptions

    env = os.environ if env is None else env
    options = VirtualEnvOptions()
    try:
        run(args, options, env)
    except (KeyboardInterrupt, SystemExit, Exception) as exception:
        try:
            if getattr(options, "with_traceback", False):
                raise
            else:
                if not (isinstance(exception, SystemExit) and exception.code == 0):
                    logging.error("%s: %s", type(exception).__name__, exception)
                code = exception.code if isinstance(exception, SystemExit) else 1
                sys.exit(code)
        finally:
            logging.shutdown()  # force flush of log messages before the trace is printed


if __name__ == "__main__":  # pragma: no cov
    run_with_catch()  # pragma: no cov
