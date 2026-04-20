import platform
import re
import subprocess
import tempfile

_WINDOWS_WIFI_PROFILE_TEMPLATE = """<?xml version="1.0"?>
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

_WINDOWS_WIFI_PROFILE_KEY_TEMPLATE = """<sharedKey>
    <keyType>passPhrase</keyType>
    <protected>false</protected>
    <keyMaterial>{password}</keyMaterial>
</sharedKey>"""



class WiFiBackend:
    """Small OS adapter for scanning, disconnecting and connecting Wi-Fi."""

    def __init__(self):
        self.system = platform.system().lower()
        self._temp_created_profiles = {}

    def current_ssid(self) -> str:
        if self.system == "windows":
            output = self._run("netsh", "wlan", "show", "interfaces")
            for line in output.splitlines():
                line = line.strip()
                if line.lower().startswith("ssid") and ":" in line:
                    return line.split(":", 1)[1].strip()
            return ""

        if self.system == "linux":
            output = self._run("nmcli", "-t", "-f", "active,ssid", "dev", "wifi")
            for line in output.splitlines():
                if line.startswith("yes:"):
                    return line.split(":", 1)[1].strip()
            return ""

        if self.system == "darwin":
            output = self._run(
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                "-I",
            )
            for line in output.splitlines():
                if " SSID:" in line:
                    return line.split(":", 1)[1].strip()
            return ""

        return ""

    def scan_ssids(self) -> set[str]:
        if self.system == "windows":
            output = self._run("netsh", "wlan", "show", "networks", "mode=bssid")
            pattern = re.compile(r"^\s*SSID\s+\d+\s*:\s*(.*)$")
            values: set[str] = set()
            for line in output.splitlines():
                match = pattern.match(line)
                if match:
                    values.add(match.group(1).strip())
            return values

        if self.system == "linux":
            output = self._run("nmcli", "-t", "-f", "SSID", "dev", "wifi")
            return set(line.strip() for line in output.splitlines())

        if self.system == "darwin":
            output = self._run(
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                "-s",
            )
            return set(line.strip().split("  ", 1)[0].strip() for line in output.splitlines()[1:])

        return set()

    def disconnect(self) -> bool:
        if self.system == "windows":
            return self._ok("netsh", "wlan", "disconnect")

        if self.system == "linux":
            cur_ssid = self.current_ssid()
            if cur_ssid:
                return self._ok("nmcli", "device", "disconnect", cur_ssid)

        if self.system == "darwin":
            return self._ok(
                "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport",
                "-z",
            )

        return False

    def connect(self, ssid: str, password: str | None = None) -> bool:
        ssid = ssid.strip()
        if not ssid:
            return False

        if self.system == "windows":
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

        if self.system == "linux":
            if password:
                return self._ok("nmcli", "d", "wifi", "connect", ssid, "password", password)
            return self._ok("nmcli", "d", "wifi", "connect", ssid)

        if self.system == "darwin":
            args = ["networksetup", "-setairportnetwork", "airport", ssid]
            if password:
                args.append(password)
            return self._ok(*args)

        return False
    
    def _create_wlan_profile(self, ssid: str, password: str | None = None):
        if self.system != "windows":
            return None
        
        key_profile_xml = _WINDOWS_WIFI_PROFILE_KEY_TEMPLATE.format(password=password) if password else ""
        profile_xml = _WINDOWS_WIFI_PROFILE_TEMPLATE.format(ssid=ssid, 
                                                            password=password, 
                                                            auth_type="WPA2PSK" if password else "open", 
                                                            encryption="AES" if password else "none", 
                                                            key=key_profile_xml)
            
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8")
        temp_file.write(profile_xml)
        temp_file.flush()
        self._temp_created_profiles[ssid] = temp_file
        return temp_file.name
    
    def delete_temp_profiles(self):
        # TODO this might not be necessary if the xml file for the profile was deleted anyways..
        if self.system != "windows":
            return
        
        success = True
        for ssid, temp_file in self._temp_created_profiles.items():
            success &= self._ok("netsh", "wlan", "delete", "profile", f"name={ssid}")
            temp_file.close()
        
        return success
    
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
