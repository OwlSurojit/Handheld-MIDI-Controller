from server.wifi_utils._wifi_backend_interface import _WiFiBackendInterface
from server.wifi_utils._subprocess_helpers import _ok, _run


class _LinuxWiFiBackend(_WiFiBackendInterface):
    def __init__(self):
        super().__init__("linux")

    def current_ssid(self) -> str:
        output = _run("nmcli", "-t", "-f", "active,ssid", "dev", "wifi")
        for line in output.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1].strip()
        return ""

    def scan_ssids(self) -> set[str]:
        output = _run("nmcli", "-t", "-f", "SSID", "dev", "wifi")
        return {line.strip() for line in output.splitlines() if line.strip()}

    def disconnect(self) -> bool:
        cur_ssid = self.current_ssid()
        if cur_ssid:
            return _ok("nmcli", "device", "disconnect", cur_ssid)
        return False

    def connect(self, ssid: str, password: str | None = None) -> bool:
        if password:
            return _ok("nmcli", "d", "wifi", "connect", ssid, "password", password)
        return _ok("nmcli", "d", "wifi", "connect", ssid)

    def delete_temp_profiles(self) -> bool:
        return True
