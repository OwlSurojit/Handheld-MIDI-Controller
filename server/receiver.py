import socket
import struct
import threading
import time
from typing import Dict

from server.controller_state import ControllerState
from server.config import get_config

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_running = True
_controllers: Dict[int, ControllerState] = {}
_state_lock = threading.Lock()
_next_controller_id = 0

# ---------------------------------------------------------------------------
# Packet format
# ---------------------------------------------------------------------------
_PACKET_FORMAT = '<BIffffffffff'
_PACKET_SIZE = struct.calcsize(_PACKET_FORMAT)

# ---------------------------------------------------------------------------
# UDP Receiver Thread
# ---------------------------------------------------------------------------
def receiver_thread():
    """
    Listens for UDP packets, auto-discovers controllers, and forwards data.
    """
    global _next_controller_id
    config = get_config()
    udp_port = config["network"]["udp_port"]
    vis_port = config["network"]["visualiser_forward_port"]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", udp_port))
    sock.settimeout(0.1)

    vis_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) if vis_port else None

    print(f"Listening for controller data on UDP port {udp_port}...")

    cur_second = time.monotonic()
    num_packets = 0
    while _running:
        try:
            raw, addr = sock.recvfrom(_PACKET_SIZE)
            if len(raw) != _PACKET_SIZE:
                continue
            num_packets += 1
            if time.monotonic() - cur_second >= 1.0:
                print(f"Received {num_packets} packets in the last second.")
                num_packets = 0
                cur_second = time.monotonic()

            # Forward raw packet to visualiser if enabled
            if vis_sock:
                vis_sock.sendto(raw, ("127.0.0.1", vis_port))

            cid, ts, qw, qx, qy, qz, ax, ay, az, gx, gy, gz = struct.unpack(_PACKET_FORMAT, raw)

            with _state_lock:
                if cid not in _controllers:
                    if not config["controllers"]["auto_assign"]:
                        continue
                    # Auto-assign a new ID
                    # In a real scenario, you might want to check against a list of known MACs
                    # or have a more robust registration process.
                    new_id = _next_controller_id
                    _controllers[new_id] = ControllerState(new_id, addr[0])
                    _next_controller_id += 1
                    print(f"Discovered new controller ID {new_id} from {addr[0]}")
                    cid = new_id

                state = _controllers[cid]
                state.last_packet_time = time.monotonic()
                # The tuple is (timestamp, quat, accel, gyro)
                state.raw_data_queue.append((ts, (qw, qx, qy, qz), (ax, ay, az), (gx, gy, gz)))

        except socket.timeout:
            pass
        except Exception as e:
            print(f"Receiver thread error: {e}")

    sock.close()
    if vis_sock:
        vis_sock.close()
    print("Receiver thread stopped.")

def stop_receiver():
    global _running
    _running = False

def get_controllers():
    with _state_lock:
        return _controllers
