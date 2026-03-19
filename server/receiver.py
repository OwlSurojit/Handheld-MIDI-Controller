import socket
import struct
import time

from server.config import get_config
from server.shared_state import get_controller

# ---------------------------------------------------------------------------
# Packet format
# ---------------------------------------------------------------------------
_PACKET_FORMAT = '<6sIffffffffff'
_PACKET_SIZE = struct.calcsize(_PACKET_FORMAT)
_LATENCY_PACKET_FORMAT = '<B6sI'  # type, mac, ts
_LATENCY_PACKET_SIZE = struct.calcsize(_LATENCY_PACKET_FORMAT)

# ---------------------------------------------------------------------------
# UDP Receiver Thread
# ---------------------------------------------------------------------------
def receiver_thread(stop_event):
    """
    Listens for UDP packets, auto-discovers controllers, and forwards data.
    """

    config = get_config()
    udp_port = config["network"]["udp_port"]

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", udp_port))
    sock.settimeout(0.1)

    print(f"Listening for controller data on UDP port {udp_port}...")

    cur_second = time.monotonic()
    num_packets = 0
    
    while not stop_event.is_set():
        try:
            raw, addr = sock.recvfrom(_PACKET_SIZE)
            
            # Handle latency check packets (echo them back)
            if len(raw) == _LATENCY_PACKET_SIZE:
                pkt_type, mac, ts = struct.unpack(_LATENCY_PACKET_FORMAT, raw)
                if pkt_type == 0xFF:  # Latency check packet
                    # Echo it back immediately
                    sock.sendto(raw, addr)
                    continue
            
            # Handle regular data packets
            if len(raw) != _PACKET_SIZE:
                continue

            mac, ts, qw, qx, qy, qz, ax, ay, az, gx, gy, gz = struct.unpack(_PACKET_FORMAT, raw)
            num_packets += 1
            now_time = time.monotonic()
            if now_time - cur_second >= 1.0:
                print(f"Received {num_packets} data packets in the last second")
                num_packets = 0
                cur_second = now_time

            state = get_controller(mac, addr[0])
            state.last_packet_time = time.monotonic()
            # The tuple is (timestamp, quat, accel, gyro)
            state.add_raw_data(ts, (qw, qx, qy, qz), (ax, ay, az), (gx, gy, gz))

        except socket.timeout:
            pass
        except Exception as e:
            print(f"Receiver thread error: {e}")

    sock.close()
    print("Receiver thread stopped.")

