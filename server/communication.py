import socket
import struct
import threading
import time
from dataclasses import dataclass
from queue import Empty, Full, Queue

from server.config import get_config, update_many
from server.provisioning_service import ProvisioningService
from server.shared_state import controllers, get_controller, has_controller

# ---------------------------------------------------------------------------
# Packet format
# ---------------------------------------------------------------------------
# Packet types
DISCOVERY_REQUEST = 0x01
DISCOVERY_RESPONSE = 0x02
SENSOR_DATA = 0x03
HIT_FEEDBACK = 0x04
IDENTIFY_REQUEST = 0x05
BATTERY_MEASUREMENT = 0x06
MODE_SWITCH_STATE = 0x07
REZERO_COMMAND = 0x08
RELIABLE_PACKET_ACK = 0xFE
LATENCY_CHECK = 0xFF

# Discovery request: type + 6 bytes MAC
_DISCOVERY_REQUEST_FORMAT = '<B6s'
_DISCOVERY_REQUEST_SIZE = struct.calcsize(_DISCOVERY_REQUEST_FORMAT)

# Sensor data: type + 6 bytes MAC + timestamp + 10 floats (qw, qx, qy, qz, ax, ay, az, gx, gy, gz) + 1 byte sustain button state
_SENSOR_DATA_FORMAT = '<B6sIffffffffffB'
_SENSOR_DATA_SIZE = struct.calcsize(_SENSOR_DATA_FORMAT)

# Hit feedback: type + 1 byte mode + 4 bytes velocity
_HIT_FEEDBACK_FORMAT = '<BBI'
_HIT_FEEDBACK_SIZE = struct.calcsize(_HIT_FEEDBACK_FORMAT)

# Identify request: single type byte
_IDENTIFY_REQUEST_FORMAT = '<B'
_IDENTIFY_REQUEST_SIZE = struct.calcsize(_IDENTIFY_REQUEST_FORMAT)

# Latency packet: type + 6 bytes MAC + timestamp
_LATENCY_PACKET_FORMAT = '<B6sI'
_LATENCY_PACKET_SIZE = struct.calcsize(_LATENCY_PACKET_FORMAT)
_LATENCY_CHECK_INTERVAL_SEC = 2.0
_NS_PER_MS = 1_000_000.0
_MAX_PACKET_SIZE = max(
    _SENSOR_DATA_SIZE,
    _DISCOVERY_REQUEST_SIZE,
    _LATENCY_PACKET_SIZE,
    ProvisioningService.max_packet_size(),
)
_SOCKET_TIMEOUT_SEC = 0.002

# Battery measurement: type + 6 bytes MAC + int percentage
_BATTERY_MEASUREMENT_FORMAT = '<B6sB'
_BATTERY_MEASUREMENT_SIZE = struct.calcsize(_BATTERY_MEASUREMENT_FORMAT)

# Mode Switch state: type + 6 bytes MAC + 1 byte mode + sequence
_MODE_SWITCH_STATE_FORMAT = '<B6sBI'
_MODE_SWITCH_STATE_SIZE = struct.calcsize(_MODE_SWITCH_STATE_FORMAT)

# Rezero command: type + 6 bytes MAC + sequence
_REZERO_COMMAND_FORMAT = '<B6sI'
_REZERO_COMMAND_SIZE = struct.calcsize(_REZERO_COMMAND_FORMAT)

# Reliable packet ACK: type + acknowledged type + status + 6 bytes MAC + sequence
_RELIABLE_PACKET_ACK_FORMAT = '<BBB6sI'

@dataclass(frozen=True)
class _HitFeedbackCommand:
    controller_mac: bytes
    command: int
    velocity: int


# ---------------------------------------------------------------------------
# UDP Receiver Thread
# ---------------------------------------------------------------------------
class CommunicationThread(threading.Thread):
    """Background UDP sender and receiver for discovery, sensor data, and latency checks."""

    def __init__(
        self,
        stop_event: threading.Event,
        host: str = "0.0.0.0",
        daemon: bool = True,
        provisioning_service: ProvisioningService | None = None,
    ):
        super().__init__(name="communication-thread", daemon=daemon)
        self.stop_event = stop_event
        self.host = host
        self.udp_port = get_config()["network"]["udp_port"]
        self.last_data_rate_update = time.monotonic()
        self.next_latency_check = time.monotonic() + _LATENCY_CHECK_INTERVAL_SEC
        self.num_packets_per_controller: dict[bytes, int] = {}
        # Store timestamp echo token plus a high-resolution send timestamp.
        self.pending_latency: dict[bytes, tuple[int, int]] = {}
        self._hit_feedback_commands: Queue[_HitFeedbackCommand] = Queue(maxsize=256)
        self._identify_requests: Queue[bytes] = Queue(maxsize=16)
        self._last_reliable_sequences: dict[tuple[bytes, int], int] = {}
        self.provisioning_service = provisioning_service

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.udp_port))
        sock.settimeout(_SOCKET_TIMEOUT_SEC)
        return sock

    def send_hit_feedback(self, controller_mac: bytes, command: int = 0x01, velocity: int = 35) -> bool:
        """Queue a hit feedback command to be sent by the communication thread."""
        if not isinstance(controller_mac, (bytes, bytearray)) or len(controller_mac) != 6:
            return False

        sanitized_command = int(command) & 0xFF
        sanitized_velocity = max(0, min(int(velocity), 0xFFFFFFFF))
        command_item = _HitFeedbackCommand(bytes(controller_mac), sanitized_command, sanitized_velocity)

        try:
            self._hit_feedback_commands.put_nowait(command_item)
            return True
        except Full:
            print("Hit feedback command queue is full; dropping command.")
            return False

    def _flush_hit_feedback_commands(self, sock: socket.socket, max_batch: int = 32) -> None:
        for _ in range(max_batch):
            try:
                cmd = self._hit_feedback_commands.get_nowait()
            except Empty:
                break

            state = get_controller(cmd.controller_mac)
            if state is None or not state.source_ip:
                continue

            packet = struct.pack(_HIT_FEEDBACK_FORMAT, HIT_FEEDBACK, cmd.command, cmd.velocity)
            sock.sendto(packet, (state.source_ip, self.udp_port))
            print(f"Sent hit feedback command to {state.source_ip} for controller {cmd.controller_mac.hex()} with command {cmd.command} and duration {cmd.velocity}ms")

    def send_identify(self, controller_mac: bytes) -> bool:
        """Queue an identify request packet for a specific controller."""
        if not isinstance(controller_mac, (bytes, bytearray)) or len(controller_mac) != 6:
            return False
        try:
            self._identify_requests.put_nowait(bytes(controller_mac))
            return True
        except Full:
            print("Identify request queue is full; dropping request.")
            return False

    def _flush_identify_requests(self, sock: socket.socket, max_batch: int = 16) -> None:
        for _ in range(max_batch):
            try:
                controller_mac = self._identify_requests.get_nowait()
            except Empty:
                break

            state = get_controller(controller_mac)
            if state is None or not state.source_ip:
                continue

            packet = struct.pack(_IDENTIFY_REQUEST_FORMAT, IDENTIFY_REQUEST)
            sock.sendto(packet, (state.source_ip, self.udp_port))
            print(f"Sent identify request to {state.source_ip} for controller {controller_mac.hex()}")

    def _handle_discovery_request(self, raw: bytes, addr: tuple[str, int], sock: socket.socket) -> None:
        _, mac = struct.unpack(_DISCOVERY_REQUEST_FORMAT, raw)
        for key in [key for key in self._last_reliable_sequences if key[0] == mac]:
            del self._last_reliable_sequences[key]
        print(f"Discovery request from {addr[0]} (MAC: {mac.hex()})")
        response = bytes([DISCOVERY_RESPONSE])
        sock.sendto(response, addr)
        print(f"Sent discovery response to {addr[0]}")

    def _handle_latency_response(self, raw: bytes, addr: tuple[str, int]) -> None:
        _, mac, ts = struct.unpack(_LATENCY_PACKET_FORMAT, raw)
        if mac not in self.pending_latency:
            return

        pending_ts, sent_ns = self.pending_latency.get(mac, (None, None))
        if pending_ts == ts and sent_ns is not None and has_controller(mac):
            rtt_ms = max((time.perf_counter_ns() - sent_ns) / _NS_PER_MS, 0.0)
            one_way_ms = rtt_ms * 0.5
            get_controller(mac, addr[0]).set_one_way_latency_ms(one_way_ms)

        self.pending_latency.pop(mac, None)

    def _handle_sensor_data(self, raw: bytes, addr: tuple[str, int]) -> None:
        _, mac, ts, qw, qx, qy, qz, ax, ay, az, gx, gy, gz, sustainPressed = struct.unpack(_SENSOR_DATA_FORMAT, raw)
        self.num_packets_per_controller[mac] = self.num_packets_per_controller.get(mac, 0) + 1

        state = get_controller(mac, addr[0])
        state.last_packet_time = time.monotonic()
        state.add_raw_data(ts, (qw, qx, qy, qz), (ax, ay, az), (gx, gy, gz), bool(sustainPressed))

        if state.source_ip != addr[0]:
            state.source_ip = addr[0]

    def _handle_battery_measurement(self, raw: bytes, addr: tuple[str, int]) -> None:
        _, mac, percentage = struct.unpack(_BATTERY_MEASUREMENT_FORMAT, raw)
        state = get_controller(mac, addr[0])
        state.last_packet_time = time.monotonic()
        state.battery_percentage = percentage

        if state.source_ip != addr[0]:
            state.source_ip = addr[0]
            
    def _send_reliable_ack(
        self,
        sock: socket.socket,
        addr: tuple[str, int],
        acknowledged_type: int,
        mac: bytes,
        sequence: int,
        status: int = 0,
    ) -> None:
        ack = struct.pack(
            _RELIABLE_PACKET_ACK_FORMAT,
            RELIABLE_PACKET_ACK,
            acknowledged_type,
            status,
            mac,
            sequence,
        )
        sock.sendto(ack, addr)

    def _is_new_reliable_packet(self, mac: bytes, packet_type: int, sequence: int) -> bool:
        key = (mac, packet_type)
        previous = self._last_reliable_sequences.get(key)
        if previous is None:
            return True
        return 0 < ((sequence - previous) & 0xFFFFFFFF) < 0x80000000

    def _remember_reliable_packet(self, mac: bytes, packet_type: int, sequence: int) -> None:
        self._last_reliable_sequences[(mac, packet_type)] = sequence

    def _handle_mode_switch_state(self, raw: bytes, addr: tuple[str, int], sock: socket.socket) -> None:
        _, mac, mode, sequence = struct.unpack(_MODE_SWITCH_STATE_FORMAT, raw)
        state = get_controller(mac, addr[0])
        state.last_packet_time = time.monotonic()
        # MODE switch state: 0 = Hit, 1 = Both, 2 = Map
        if mode not in (0, 1, 2):
            print(f"Ignoring invalid mode {mode} from controller {mac.hex()}")
            self._send_reliable_ack(sock, addr, MODE_SWITCH_STATE, mac, sequence, status=1)
            return
        if self._is_new_reliable_packet(mac, MODE_SWITCH_STATE, sequence):
            mac_key = mac.hex().lower()
            update_many([
                (["controllers", mac_key, "hit", "enabled"], mode in (0, 1)),
                (["controllers", mac_key, "mappings_enabled"], mode in (1, 2)),
            ])
            self._remember_reliable_packet(mac, MODE_SWITCH_STATE, sequence)
        self._send_reliable_ack(sock, addr, MODE_SWITCH_STATE, mac, sequence)

        if state.source_ip != addr[0]:
            state.source_ip = addr[0]

    def _handle_rezero_command(self, raw: bytes, addr: tuple[str, int], sock: socket.socket) -> None:
        _, mac, sequence = struct.unpack(_REZERO_COMMAND_FORMAT, raw)
        state = get_controller(mac, addr[0])
        state.last_packet_time = time.monotonic()
        if self._is_new_reliable_packet(mac, REZERO_COMMAND, sequence):
            state.re_zero()
            self._remember_reliable_packet(mac, REZERO_COMMAND, sequence)
        self._send_reliable_ack(sock, addr, REZERO_COMMAND, mac, sequence)

        if state.source_ip != addr[0]:
            state.source_ip = addr[0]

    def _send_latency_checks(self, now: float, sock: socket.socket) -> None:
        if now < self.next_latency_check:
            return

        self.next_latency_check = now + _LATENCY_CHECK_INTERVAL_SEC
        mono_ms = int(now * 1000.0) & 0xFFFFFFFF
        for mac, state in list(controllers.items()):
            if not state.source_ip:
                continue
            latency_packet = struct.pack(_LATENCY_PACKET_FORMAT, LATENCY_CHECK, mac, mono_ms)
            sent_ns = time.perf_counter_ns()
            sock.sendto(latency_packet, (state.source_ip, self.udp_port))
            self.pending_latency[mac] = (mono_ms, sent_ns)

    def _update_data_rates(self, now: float) -> None:
        if now - self.last_data_rate_update < 1.0:
            return

        for mac, count in self.num_packets_per_controller.items():
            if has_controller(mac):
                get_controller(mac).set_data_rate(count)
            self.num_packets_per_controller[mac] = 0
        self.last_data_rate_update = now

    def _handle_packet(self, raw: bytes, addr: tuple[str, int], sock: socket.socket) -> None:
        if len(raw) < 1:
            return

        if self.provisioning_service and self.provisioning_service.handle_packet(raw, addr):
            return

        packet_type = raw[0]

        if packet_type == DISCOVERY_REQUEST and len(raw) == _DISCOVERY_REQUEST_SIZE:
            self._handle_discovery_request(raw, addr, sock)
        elif packet_type == LATENCY_CHECK and len(raw) == _LATENCY_PACKET_SIZE:
            self._handle_latency_response(raw, addr)
        elif packet_type == SENSOR_DATA and len(raw) == _SENSOR_DATA_SIZE:
            self._handle_sensor_data(raw, addr)
        elif packet_type == BATTERY_MEASUREMENT and len(raw) == _BATTERY_MEASUREMENT_SIZE:
            self._handle_battery_measurement(raw, addr)
        elif packet_type == MODE_SWITCH_STATE and len(raw) == _MODE_SWITCH_STATE_SIZE:
            self._handle_mode_switch_state(raw, addr, sock)
        elif packet_type == REZERO_COMMAND and len(raw) == _REZERO_COMMAND_SIZE:
            self._handle_rezero_command(raw, addr, sock)

    def run(self) -> None:
        print(f"Listening for controller data on UDP port {self.udp_port}...")
        sock = self._create_socket()
        try:
            while not self.stop_event.is_set():
                try:
                    self._flush_hit_feedback_commands(sock)
                    self._flush_identify_requests(sock)
                    if self.provisioning_service:
                        self.provisioning_service.flush_pending(sock, self.udp_port)
                    raw, addr = sock.recvfrom(_MAX_PACKET_SIZE)
                    self._handle_packet(raw, addr, sock)

                    now = time.monotonic()
                    self._send_latency_checks(now, sock)
                    self._update_data_rates(now)
                except socket.timeout:
                    continue
                except Exception as exc:
                    print(f"Communication thread error: {exc}")
        finally:
            sock.close()
            print("Communication thread stopped.")
