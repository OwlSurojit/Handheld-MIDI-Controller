import platform
from server.wifi_utils._wifi_backend_interface import _WiFiBackendInterface

class WiFiBackend:
    """Facade that delegates Wi-Fi operations to an OS-specific backend implementation."""

    def __init__(self):
        detected_system = platform.system().lower()
        self._backend: _WiFiBackendInterface
        if detected_system == 'windows':
            from server.wifi_utils._windows_wifi_backend import _WindowsWiFiBackend
            self._backend = _WindowsWiFiBackend()
        elif detected_system == "linux":
            from server.wifi_utils._linux_wifi_backend import _LinuxWiFiBackend
            self._backend = _LinuxWiFiBackend()
        elif detected_system == "darwin":
            from server.wifi_utils._darwin_airport_wifi_backend import _DarwinAirportWiFiBackend
            if _DarwinAirportWiFiBackend.is_supported():
                self._backend = _DarwinAirportWiFiBackend()
            else:
                from server.wifi_utils._darwin_CoreWLAN_wifi_backend import _DarwinCoreWLANWiFiBackend
                self._backend = _DarwinCoreWLANWiFiBackend()
        else:
            from server.wifi_utils._unsupported_wifi_backend import _UnsupportedWiFiBackend
            self._backend = _UnsupportedWiFiBackend(detected_system)

    @property
    def system(self) -> str:
        return self._backend.system

    def is_authorized(self) -> bool:
        return self._backend.is_authorized()

    def current_ssid(self) -> str:
        return self._backend.current_ssid()

    def scan_ssids(self) -> set[str]:
        return self._backend.scan_ssids()

    def disconnect(self) -> bool:
        return self._backend.disconnect()

    def connect(self, ssid: str, password: str | None = None) -> bool:
        ssid = ssid.strip()
        if not ssid:
            return False
        if self.current_ssid() == ssid:
            return True
        return self._backend.connect(ssid, password)

    def delete_temp_profiles(self) -> bool:
        return self._backend.delete_temp_profiles()

    def system_is(self, name: str) -> bool:
        return self._backend.system_is(name)
