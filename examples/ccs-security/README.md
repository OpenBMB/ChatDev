# CCS Security Integration for ChatDev

[CCS](https://github.com/Correctover/ccs-verifier) provides sub-millisecond runtime verification for ChatDev's AI code execution pipeline.

## Integration

```python
from examples.ccs_security.ccs_guard import safe_execute_code

# CCS-verified code execution
result = safe_execute_code("import os; print(os.listdir('.'))")

# Dangerous code is blocked before execution:
# safe_execute_code("import urllib.request; urllib.request.urlopen('http://169.254.169.254/')")
# → "[CCS] Code execution denied: SSRF: cloud metadata access"
```

## Install

```bash
pip install ccs-verifier
```

## Reference

- [CCS IETF Draft](https://datatracker.ietf.org/doc/draft-correctover-ccs/)
- [CCS Zenodo DOI](https://doi.org/10.5281/zenodo.21783723)
