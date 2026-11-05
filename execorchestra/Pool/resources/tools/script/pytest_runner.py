import sys
import io
import os
import subprocess
import json
import re

def run_tests(target_path: str) -> dict:
    if not os.path.exists(target_path):
        return {"status": "error", "message": f"Path {target_path} not found."}
        
    try:
        # Run pytest via subprocess
        # Using -tb=short to get clean traceback logs, and -v to list tests
        result = subprocess.run(
            [sys.executable, "-m", "pytest", target_path, "--tb=short", "-v"],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        stdout = result.stdout
        stderr = result.stderr
        
        # Simple regex parsing for the summary line
        # e.g., "=== 2 passed, 1 failed in 0.12s ==="
        summary_match = re.search(r'===+ (.*) in \d+\.\d+s ===+', stdout)
        summary_text = summary_match.group(1) if summary_match else "No summary found"
        
        passed = 0
        failed = 0
        errors = 0
        skipped = 0
        
        # Parse counts from summary text
        # e.g., "2 passed, 1 failed"
        for part in summary_text.split(','):
            part = part.strip()
            if 'passed' in part:
                passed = int(part.split()[0])
            elif 'failed' in part:
                failed = int(part.split()[0])
            elif 'error' in part:
                errors = int(part.split()[0])
            elif 'skipped' in part:
                skipped = int(part.split()[0])
                
        # If no summary line found, maybe pytest failed to run or no tests found
        if not summary_match and "no tests ran" in stdout.lower():
            status = "no_tests"
        elif result.returncode == 0:
            status = "passed"
        else:
            status = "failed"
            
        return {
            "status": status,
            "exit_code": result.returncode,
            "summary": {
                "text": summary_text,
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped
            },
            "stdout": stdout,
            "stderr": stderr
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

if __name__ == "__main__":
    # Force UTF-8 output on Windows
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    if len(sys.argv) < 2:
        print("Usage: python pytest_runner.py <target_path>", file=sys.stderr)
        sys.exit(1)

    target_path = sys.argv[1]
    result = run_tests(target_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
