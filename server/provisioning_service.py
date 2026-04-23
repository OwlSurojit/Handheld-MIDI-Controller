import struct
import threading
import time
from queue import Empty, Full, Queue

from server.wifi_utils.wifi_backend import WiFiBackend

PROVISIONING_SET_WIFI = 0x10
PROVISIONING_ACK = 0x11

_PROVISIONING_SET_WIFI_PREFIX_FORMAT = "<B6sB33s65s"
_PROVISIONING_SET_WIFI_SIZE = struct.calcsize("<B6sB33s65sI")

_PROVISIONING_ACK_FORMAT = "<B6sB"
_PROVISIONING_ACK_SIZE = struct.calcsize(_PROVISIONING_ACK_FORMAT)

_WIFI_AUTH_OPEN = 0x00
_WIFI_AUTH_WPA2_PSK = 0x01
_CONTROLLER_AP_PREFIX = "MIDI-CTRL-"
_CONTROLLER_AP_PASSWORD = ""
_CONTROLLER_AP_TARGET_IP = "192.168.4.1"
_BROADCAST_MAC = b"\xFF\xFF\xFF\xFF\xFF\xFF"

_PROVISIONING_ACK_STATUS = {
    0x00: "ok",
    0x01: "invalid_payload",
    0x02: "write_failed",
    0x03: "wrong_target",
}

class _ProvisioningCommand:
    def __init__(self, packet: bytes, target_ip: str):
        self.packet = packet
        self.target_ip = target_ip


def _fnv1a32(data: bytes) -> int:
    hash_value = 2166136261
    for byte in data:
        hash_value ^= byte
        hash_value = (hash_value * 16777619) & 0xFFFFFFFF
    return hash_value


class ProvisioningService:
    """Owns setup session state and SSID-based provisioning packet flow."""

    def __init__(self, wifi_backend: WiFiBackend):
        self._wifi = wifi_backend
        self._commands: Queue[_ProvisioningCommand] = Queue(maxsize=128)
        self._ack_lock = threading.Lock()
        self._last_ack_time = 0.0
        self._last_ack_status = ""
        self._previous_ssid: str | None = None

    @staticmethod
    def max_packet_size() -> int:
        return max(_PROVISIONING_SET_WIFI_SIZE, _PROVISIONING_ACK_SIZE)

    def current_wifi(self) -> str:
        return self._wifi.current_ssid()

    def start_setup_session(self) -> bool:
        if self._previous_ssid is not None:
            return True
        
        if not self._wifi.is_authorized():
            return False

        previous_ssid = self._wifi.current_ssid()
        if previous_ssid and self._wifi.system_is("windows"):
            self._wifi.disconnect()

        self._previous_ssid = previous_ssid
        return True

    def end_setup_session(self) -> bool:
        self._wifi.delete_temp_profiles()
        
        if self._previous_ssid is None:
            return True

        previous_ssid = self._previous_ssid
        self._previous_ssid = None
        if previous_ssid:
            return self._wifi.connect(previous_ssid)
        return True

    def list_target_ssids(self) -> list[str]:
        current = self._wifi.current_ssid()
        values: list[str] = []
        if current and not current.startswith(_CONTROLLER_AP_PREFIX):
            values.append(current)
        for ssid in self._wifi.scan_ssids():
            if ssid.startswith(_CONTROLLER_AP_PREFIX):
                continue
            if ssid not in values:
                values.append(ssid)
        return values

    def list_controller_aps(self) -> list[str]:
        return sorted(ssid for ssid in self._wifi.scan_ssids() if ssid.startswith(_CONTROLLER_AP_PREFIX))

    def provision_access_points(
        self,
        ap_ssids: list[str],
        target_ssid: str,
        target_password: str,
        ack_timeout_sec: float = 8.0,
        connect_timeout_sec: float = 30.0,
    ) -> dict[str, str]:
        """Provision selected controller APs one-by-one using 192.168.4.1 as the target."""
        results: dict[str, str] = {}
        ssid = target_ssid.strip()
        if not ssid:
            return results

        for ap_ssid in ap_ssids:
            # Connect to AP
            if not self._wifi.connect(ap_ssid, _CONTROLLER_AP_PASSWORD):
                results[ap_ssid] = "ap_connect_failed"
                continue
            
            # Wait until connected
            start_time = time.monotonic()
            while time.monotonic() - start_time <= connect_timeout_sec:
                if self._wifi.current_ssid() == ap_ssid:
                    break
                time.sleep(0.1)
            else:
                results[ap_ssid] = "ap_connect_failed"
            
            # Schedule sending provisioning request
            previous_ack_time = self._get_last_ack_time()
            if not self.queue_config(ssid, target_password, target_ip=_CONTROLLER_AP_TARGET_IP):
                results[ap_ssid] = "send_failed"
                continue

            # wait for provision ACK from the controller
            ack_status = self._wait_for_next_ack(previous_ack_time, ack_timeout_sec)
            results[ap_ssid] = ack_status or "ack_timeout"

        return results

    def queue_config(
        self,
        ssid: str,
        password: str,
        auth_type: int | None = None,
        target_ip: str = _CONTROLLER_AP_TARGET_IP,
    ) -> bool:
        normalized_ssid = ssid.strip()
        if not normalized_ssid:
            return False

        ssid_bytes = normalized_ssid.encode("utf-8", errors="ignore")[:32]
        password_bytes = password.encode("utf-8", errors="ignore")[:64]
        ssid_field = ssid_bytes + (b"\x00" * (33 - len(ssid_bytes)))
        password_field = password_bytes + (b"\x00" * (65 - len(password_bytes)))

        sanitized_auth = _WIFI_AUTH_WPA2_PSK if password_bytes else _WIFI_AUTH_OPEN
        if auth_type is not None and int(auth_type) == _WIFI_AUTH_OPEN:
            sanitized_auth = _WIFI_AUTH_OPEN

        prefix = struct.pack(
            _PROVISIONING_SET_WIFI_PREFIX_FORMAT,
            PROVISIONING_SET_WIFI,
            _BROADCAST_MAC,
            sanitized_auth,
            ssid_field,
            password_field,
        )
        checksum = _fnv1a32(prefix)
        packet = prefix + struct.pack("<I", checksum)

        try:
            self._commands.put_nowait(_ProvisioningCommand(packet=packet, target_ip=target_ip))
            return True
        except Full:
            print("Provisioning command queue is full; dropping command.")
            return False

    def flush_pending(self, udp_socket, udp_port: int, max_batch: int = 16) -> None:
        for _ in range(max_batch):
            try:
                cmd = self._commands.get_nowait()
            except Empty:
                break
            
            try:
                udp_socket.sendto(cmd.packet, (cmd.target_ip, udp_port))
            except Exception as exc:
                print("Provisioning Command couldn't be sent:", exc, "\nRetrying...")
                self._commands.put_nowait(cmd)
                return
            print(f"Sent provisioning packet to {cmd.target_ip}")

    def handle_packet(self, raw: bytes, addr: tuple[str, int]) -> bool:
        if len(raw) < 1:
            return False

        packet_type = raw[0]
        if packet_type == PROVISIONING_ACK and len(raw) == _PROVISIONING_ACK_SIZE:
            self._handle_ack(raw, addr)
            return True
        return False

    def _handle_ack(self, raw: bytes, addr: tuple[str, int]) -> None:
        _, mac, status = struct.unpack(_PROVISIONING_ACK_FORMAT, raw)
        status_name = _PROVISIONING_ACK_STATUS.get(status, f"unknown_{status}")
        with self._ack_lock:
            self._last_ack_time = time.monotonic()
            self._last_ack_status = status_name
        print(f"Provisioning ACK from {addr[0]} ({mac.hex()}): {status_name}")

    def _get_last_ack_time(self) -> float:
        with self._ack_lock:
            return self._last_ack_time

    def _wait_for_next_ack(self, previous_ack_time: float, timeout_sec: float) -> str | None:
        deadline = time.monotonic() + max(timeout_sec, 0.1)
        while time.monotonic() < deadline:
            with self._ack_lock:
                if self._last_ack_time > previous_ack_time:
                    return self._last_ack_status or "unknown"
            time.sleep(0.05)
        return None