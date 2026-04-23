import os
from server.wifi_utils._wifi_backend_interface import _WiFiBackendInterface
from server.wifi_utils._subprocess_helpers import _ok, _run

class _DarwinAirportWiFiBackend(_WiFiBackendInterface):
    _AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"

    @classmethod
    def is_supported(cls) -> bool:
        if not os.path.exists(cls._AIRPORT):
            return False
        return _ok(cls._AIRPORT, "-I")

    def __init__(self):
        super().__init__("darwin")

    def current_ssid(self) -> str:
        output = _run(self._AIRPORT, "-I")
        for line in output.splitlines():
            if " SSID:" in line:
                return line.split(":", 1)[1].strip()
        return ""

    def scan_ssids(self) -> set[str]:
        output = _run(self._AIRPORT, "-s")
        return {line.strip().split("  ", 1)[0].strip() for line in output.splitlines()[1:] if line.strip()}

    def disconnect(self) -> bool:
        return _ok(self._AIRPORT, "-z")

    def connect(self, ssid: str, password: str | None = None) -> bool:
        args = ["networksetup", "-setairportnetwork", "airport", ssid]
        if password:
            args.append(password)
        return _ok(*args)

    def delete_temp_profiles(self) -> bool:
        return True
    