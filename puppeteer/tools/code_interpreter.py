from tools.base.register import global_tool_registry
from tools.base.base_tool import Tool
from tenacity import retry, stop_after_attempt, wait_fixed
import base64
import os
import shutil
from abc import ABC, abstractmethod
import subprocess
from subprocess import check_output
import time
import signal

FILE_REGEX = r"(^//.|^/|^ [a-zA-Z])?:?/.+ (/$)"
class CodeInterpreter(Tool):
    def __init__(self):
        super().__init__("run_code", "run code", self.execute)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def execute(self, *args, **kwargs):
        try: 
            work_path = kwargs.get("work_path", "")
            code = kwargs.get("code", "")
            file_path = kwargs.get("file_path", "")
            self.timeout_detected = kwargs.get("timeout_detected", True)   
            code_path = self.write(work_path, code)
            flag, ans = self.run(work_path, code_path, file_path)

        except AttributeError:
            # raise ValueError(f"Running Error")
            return False, "Running Error"
        
        return flag, ans
    @abstractmethod
    def write(self, work_path, code):
        pass
    @abstractmethod
    def run(self, work_path, code_path, file_path):
        pass

@global_tool_registry("run_python")
class PythonInterpreter(CodeInterpreter):
    def __init__(self, name):
        super().__init__()
        self.name = name
    
    def write(self, work_path, code):
        code_path = os.path.join(work_path, "agent-main.py")

        with open(code_path, 'w') as file:
            file.write(code)
        return code_path

    def move_file(self, src_path, dest_path):
        if not os.path.exists(src_path):
            return
        
        if dest_path == "":
            dest_path = os.getcwd()
        dest_dir = os.path.dirname(dest_path)
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
        
        try:
            shutil.copy2(src_path, dest_path)
        except Exception as e:
            return False

    def robust_kill(self, process):
        """Robustly kill the process based on the OS."""
        if process.poll() is None:  # Check if the process is still running
            if os.name == 'nt':  # For Windows
                os.kill(process.pid, signal.SIGTERM)
                time.sleep(1)  # Allow some time for graceful termination
                if process.poll() is None:  # Force kill if still running
                    os.kill(process.pid, signal.CTRL_BREAK_EVENT)
            else:  # For Linux/macOS
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)  # Terminate the process group
                time.sleep(1)  # Allow some time for graceful termination
                if process.poll() is None:  # Force kill the group if still running
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        
    def run(self, work_path, code_path, file_path):
        """Executes a process and handles file movement, command execution, and timeouts."""
        try:
            if len(file_path) > 0:
                self.move_file(src_path=file_path, dest_path=work_path)

            # Determine the command to run based on the operating system
            if os.name == 'nt':  # Windows
                command = f"cd {work_path} && python agent-main.py"
                process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:  # Linux/macOS
                command = f"cd {work_path} && python3 agent-main.py"
                process = subprocess.Popen(command, shell=True, preexec_fn=os.setsid, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE)

            try:
                # Wait for process completion with a timeout of 10 seconds
                out, err = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                self.robust_kill(process)
                if self.timeout_detected:
                    return False, "The process timed out after 10 seconds."
                else:
                    return True, "The process completes without encountering any errors."

            return_code = process.returncode
            output = out.decode('utf-8', errors='ignore')
            error_output = err.decode('utf-8', errors='ignore')

            # If the process is still running after the timeout
            if process.poll() is None:
                self.robust_kill(process)  # Ensure the process is terminated
            return_code = process.returncode

            # Handle return code and output
            if return_code == 0:
                # Clean up file paths in the output for readability
                work_path = os.getcwd()
                output = output.replace(work_path, "")
                return True, output
            else:
                # Handle errors in the output
                if error_output:
                    work_path = os.getcwd()
                    if "Traceback".lower() in error_output.lower():
                        errs = error_output.replace(work_path + "/", "").replace(work_path, "")
                        return False, errs
                return False, error_output

        except subprocess.CalledProcessError as e:
            return False, f"CalledProcessError: {str(e)}"
        except Exception as ex:
            return False, f"An unexpected error occurred: {str(ex)}"
