from server.wifi_utils._wifi_backend_interface import _WiFiBackendInterface

class _UnsupportedWiFiBackend(_WiFiBackendInterface):
    def __init__(self, system: str):
        super().__init__(system)

    def current_ssid(self) -> str:
        return ""

    def scan_ssids(self) -> set[str]:
        return set()

    def disconnect(self) -> bool:
        return False

    def connect(self, ssid: str, password: str | None = None) -> bool:
        return False

    def delete_temp_profiles(self) -> bool:
        return False