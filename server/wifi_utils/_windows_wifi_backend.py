import os
import re
import tempfile
from server.wifi_utils._wifi_backend_interface import _WiFiBackendInterface
from server.wifi_utils._subprocess_helpers import _ok, _run


class _WindowsWiFiBackend(_WiFiBackendInterface):
    
    _WIFI_PROFILE_TEMPLATE = """<?xml version="1.0"?>
    <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
        <name>{ssid}</name>
        <SSIDConfig>
            <SSID>
                <name>{ssid}</name>
            </SSID>
        </SSIDConfig>
        <connectionType>ESS</connectionType>
        <connectionMode>manual</connectionMode>
        <MSM>
            <security>
                <authEncryption>
                    <authentication>{auth_type}</authentication>
                    <encryption>{encryption}</encryption>
                    <useOneX>false</useOneX>
                </authEncryption>
                {key}
            </security>
        </MSM>
        <MacRandomization xmlns="http://www.microsoft.com/networking/WLAN/profile/v3">
            <enableRandomization>false</enableRandomization>
        </MacRandomization>
    </WLANProfile>
    """

    _WIFI_PROFILE_KEY_TEMPLATE = """<sharedKey>
        <keyType>passPhrase</keyType>
        <protected>false</protected>
        <keyMaterial>{password}</keyMaterial>
    </sharedKey>"""
    
    def __init__(self):
        super().__init__("windows")
        self._temp_created_profiles: dict[str, str] = {}

    def current_ssid(self) -> str:
        output = _run("netsh", "wlan", "show", "interfaces")
        for line in output.splitlines():
            line = line.strip()
            if line.lower().startswith("ssid") and ":" in line:
                return line.split(":", 1)[1].strip()
        return ""

    def scan_ssids(self) -> set[str]:
        output = _run("netsh", "wlan", "show", "networks", "mode=bssid")
        pattern = re.compile(r"^\s*SSID\s+\d+\s*:\s*(.*)$")
        values: set[str] = set()
        for line in output.splitlines():
            match = pattern.match(line)
            if match:
                values.add(match.group(1).strip())
        return values

    def disconnect(self) -> bool:
        return _ok("netsh", "wlan", "disconnect")

    def connect(self, ssid: str, password: str | None = None) -> bool:
        profiles_raw = _run("netsh", "wlan", "show", "profiles")
        profile_pattern = re.compile(r"^\s*All User Profile\s*:\s*(.*)$")
        existing_profiles = set()
        for line in profiles_raw.splitlines():
            match = profile_pattern.match(line)
            if match:
                existing_profiles.add(match.group(1).strip())

        if ssid not in existing_profiles:
            profile_path = self._create_wlan_profile(ssid, password)
            if not profile_path:
                return False
            if not _ok("netsh", "wlan", "add", "profile", f"filename={profile_path}"):
                return False

        return _ok("netsh", "wlan", "connect", f"name={ssid}", f"ssid={ssid}")

    def _create_wlan_profile(self, ssid: str, password: str | None = None) -> str | None:
        key_profile_xml = self._WIFI_PROFILE_KEY_TEMPLATE.format(password=password) if password else ""
        profile_xml = self._WIFI_PROFILE_TEMPLATE.format(
            ssid=ssid,
            auth_type="WPA2PSK" if password else "open",
            encryption="AES" if password else "none",
            key=key_profile_xml,
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8") as temp_file:
            temp_file.write(profile_xml)
            path = temp_file.name

        self._temp_created_profiles[ssid] = path
        return path

    def delete_temp_profiles(self) -> bool:
        success = True
        for ssid, profile_path in list(self._temp_created_profiles.items()):
            success &= _ok("netsh", "wlan", "delete", "profile", f"name={ssid}")
            try:
                os.unlink(profile_path)
            except OSError:
                success = False

        self._temp_created_profiles.clear()
        return success
