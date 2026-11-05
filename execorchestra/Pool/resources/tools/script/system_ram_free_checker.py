"""S-GAR tool — system memory snapshot via psutil (https://github.com/giampaolo/psutil, BSD)."""
import sys
from _sgar_cli import emit
import psutil

vm = psutil.virtual_memory()
sm = psutil.swap_memory()
emit({
    "status": "success", "tool": "psutil",
    "virtual_memory": {
        "total_bytes": vm.total, "available_bytes": vm.available,
        "used_bytes": vm.used, "free_bytes": vm.free, "percent_used": vm.percent,
    },
    "swap": {"total_bytes": sm.total, "used_bytes": sm.used, "percent_used": sm.percent},
})
