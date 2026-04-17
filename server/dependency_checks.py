import shutil
import sys
from typing import List



def collect_startup_warnings() -> List[str]:
    warnings: List[str] = []

    if sys.platform.startswith("linux") and shutil.which("nmcli") is None:
        warnings.append(
            "Linux Wi-Fi management tool 'nmcli' was not found. Wi-Fi provisioning features will be unavailable "
            "until NetworkManager is installed."
        )

    return warnings
