from abc import ABC, abstractmethod
import os
import platform
import re
import subprocess
import tempfile


class _WiFiBackendInterface(ABC):
    """Contract implemented by all Wi-Fi backend variants."""

    def __init__(self, system: str):
        self.system = system

    @abstractmethod
    def current_ssid(self) -> str:
        pass

    @abstractmethod
    def scan_ssids(self) -> set[str]:
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        pass

    @abstractmethod
    def connect(self, ssid: str, password: str | None = None) -> bool:
        pass

    @abstractmethod
    def delete_temp_profiles(self) -> bool:
        pass

    def system_is(self, name: str) -> bool:
        return self.system == name.lower()

    def _run(self, *cmd: str) -> str:
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=8)
            return completed.stdout or ""
        except Exception:
            return ""

    def _ok(self, *cmd: str) -> bool:
        try:
            completed = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=8)
            return completed.returncode == 0
        except Exception:
            return False


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
        output = self._run("netsh", "wlan", "show", "interfaces")
        for line in output.splitlines():
            line = line.strip()
            if line.lower().startswith("ssid") and ":" in line:
                return line.split(":", 1)[1].strip()
        return ""

    def scan_ssids(self) -> set[str]:
        output = self._run("netsh", "wlan", "show", "networks", "mode=bssid")
        pattern = re.compile(r"^\s*SSID\s+\d+\s*:\s*(.*)$")
        values: set[str] = set()
        for line in output.splitlines():
            match = pattern.match(line)
            if match:
                values.add(match.group(1).strip())
        return values

    def disconnect(self) -> bool:
        return self._ok("netsh", "wlan", "disconnect")

    def connect(self, ssid: str, password: str | None = None) -> bool:
        ssid = ssid.strip()
        if not ssid:
            return False

        profiles_raw = self._run("netsh", "wlan", "show", "profiles")
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
            if not self._ok("netsh", "wlan", "add", "profile", f"filename={profile_path}"):
                return False

        return self._ok("netsh", "wlan", "connect", f"name={ssid}", f"ssid={ssid}")

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
            success &= self._ok("netsh", "wlan", "delete", "profile", f"name={ssid}")
            try:
                os.unlink(profile_path)
            except OSError:
                success = False

        self._temp_created_profiles.clear()
        return success


class _LinuxWiFiBackend(_WiFiBackendInterface):
    def __init__(self):
        super().__init__("linux")

    def current_ssid(self) -> str:
        output = self._run("nmcli", "-t", "-f", "active,ssid", "dev", "wifi")
        for line in output.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1].strip()
        return ""

    def scan_ssids(self) -> set[str]:
        output = self._run("nmcli", "-t", "-f", "SSID", "dev", "wifi")
        return {line.strip() for line in output.splitlines() if line.strip()}

    def disconnect(self) -> bool:
        cur_ssid = self.current_ssid()
        if cur_ssid:
            return self._ok("nmcli", "device", "disconnect", cur_ssid)
        return False

    def connect(self, ssid: str, password: str | None = None) -> bool:
        ssid = ssid.strip()
        if not ssid:
            return False

        if password:
            return self._ok("nmcli", "d", "wifi", "connect", ssid, "password", password)
        return self._ok("nmcli", "d", "wifi", "connect", ssid)

    def delete_temp_profiles(self) -> bool:
        return True


class _DarwinWiFiBackend(_WiFiBackendInterface):
    _AIRPORT = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"

    def __init__(self):
        super().__init__("darwin")

    def current_ssid(self) -> str:
        output = self._run(self._AIRPORT, "-I")
        for line in output.splitlines():
            if " SSID:" in line:
                return line.split(":", 1)[1].strip()
        return ""

    def scan_ssids(self) -> set[str]:
        output = self._run(self._AIRPORT, "-s")
        return {line.strip().split("  ", 1)[0].strip() for line in output.splitlines()[1:] if line.strip()}

    def disconnect(self) -> bool:
        return self._ok(self._AIRPORT, "-z")

    def connect(self, ssid: str, password: str | None = None) -> bool:
        ssid = ssid.strip()
        if not ssid:
            return False

        args = ["networksetup", "-setairportnetwork", "airport", ssid]
        if password:
            args.append(password)
        return self._ok(*args)

    def delete_temp_profiles(self) -> bool:
        return True


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


class WiFiBackend:
    """Facade that delegates Wi-Fi operations to an OS-specific backend implementation."""

    _BACKEND_MAP = {
        "windows": _WindowsWiFiBackend,
        "linux": _LinuxWiFiBackend,
        "darwin": _DarwinWiFiBackend,
    }

    def __init__(self):
        detected_system = platform.system().lower()
        backend_cls = self._BACKEND_MAP.get(detected_system)
        self._backend: _WiFiBackendInterface
        if backend_cls:
            self._backend = backend_cls()
        else:
            self._backend = _UnsupportedWiFiBackend(detected_system)

    @property
    def system(self) -> str:
        return self._backend.system

    def current_ssid(self) -> str:
        return self._backend.current_ssid()

    def scan_ssids(self) -> set[str]:
        return self._backend.scan_ssids()

    def disconnect(self) -> bool:
        return self._backend.disconnect()

    def connect(self, ssid: str, password: str | None = None) -> bool:
        return self._backend.connect(ssid, password)

    def delete_temp_profiles(self) -> bool:
        return self._backend.delete_temp_profiles()

    def system_is(self, name: str) -> bool:
        return self._backend.system_is(name)
