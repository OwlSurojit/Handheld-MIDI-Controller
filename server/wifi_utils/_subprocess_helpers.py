import subprocess

COMMAND_TIMEOUT = 8

def _run(*cmd: str) -> str:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=COMMAND_TIMEOUT)
        return completed.stdout or ""
    except Exception:
        return ""

def _ok(*cmd: str) -> bool:
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=COMMAND_TIMEOUT)
        return completed.returncode == 0
    except Exception:
        return False
