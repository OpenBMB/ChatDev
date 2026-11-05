"""S-GAR tool — per-process memory profile via psutil (https://github.com/giampaolo/psutil, BSD).
Runs the given Python script and reports its peak RSS memory, or (no arg) profiles
the current interpreter process."""
import sys
import os
import subprocess
from _sgar_cli import emit
import psutil

if len(sys.argv) >= 2 and os.path.exists(sys.argv[1]):
    target = sys.argv[1]
    proc = subprocess.Popen([sys.executable, target],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p = psutil.Process(proc.pid)
    peak = 0
    try:
        while proc.poll() is None:
            try:
                peak = max(peak, p.memory_info().rss)
            except psutil.NoSuchProcess:
                break
    finally:
        proc.wait()
    emit({"status": "success", "tool": "psutil", "target": target,
          "exit_code": proc.returncode, "peak_rss_bytes": peak})
else:
    p = psutil.Process(os.getpid())
    emit({"status": "success", "tool": "psutil", "target": None,
          "current_process_rss_bytes": p.memory_info().rss})
