import socket
import struct
import time

from server.config import get_config
from server.shared_state import get_controller, add_controller, has_controller

# ---------------------------------------------------------------------------
# Packet format
# ---------------------------------------------------------------------------
# Packet types
DISCOVERY_REQUEST = 0x01
DISCOVERY_RESPONSE = 0x02
SENSOR_DATA = 0x03
LATENCY_CHECK = 0xFF

# Discovery request: type + 6 bytes MAC
_DISCOVERY_REQUEST_FORMAT = '<B6s'
_DISCOVERY_REQUEST_SIZE = struct.calcsize(_DISCOVERY_REQUEST_FORMAT)

# Sensor data: type + 6 bytes MAC + timestamp + 12 floats
_SENSOR_DATA_FORMAT = '<B6sIffffffffff'
_SENSOR_DATA_SIZE = struct.calcsize(_SENSOR_DATA_FORMAT)

# Latency packet: type + 6 bytes MAC + timestamp
_LATENCY_PACKET_FORMAT = '<B6sI'
_LATENCY_PACKET_SIZE = struct.calcsize(_LATENCY_PACKET_FORMAT)


# ---------------------------------------------------------------------------
# UDP Receiver Thread
# ---------------------------------------------------------------------------
def receiver_thread(stop_event):
    """
    Listens for UDP packets:
    - Discovery requests: responds with simple ACK (controller reads source IP)
    - Sensor data packets: auto-discovers controllers and forwards data
    - Latency packets: echoes them back
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
            raw, addr = sock.recvfrom(max(_SENSOR_DATA_SIZE, _DISCOVERY_REQUEST_SIZE, _LATENCY_PACKET_SIZE))
            
            if len(raw) < 1:
                continue
                
            packet_type = raw[0]
            
            # Handle discovery requests
            if packet_type == DISCOVERY_REQUEST and len(raw) == _DISCOVERY_REQUEST_SIZE:
                pkt_type, mac = struct.unpack(_DISCOVERY_REQUEST_FORMAT, raw)
                if has_controller(mac):
                    continue
                print(f"Discovery request from {addr[0]} (MAC: {mac.hex()})")
                # add_controller(mac, addr[0]) This will be done when the first sensor data packet arrives. Otherwise the controller might never leave discovery mode
                # Send simple discovery response ACK (controller reads source IP)
                response = bytes([DISCOVERY_RESPONSE])
                sock.sendto(response, addr)
                print(f"Sent discovery response to {addr[0]}")
                continue
            
            # Handle latency check packets (echo them back)
            elif packet_type == LATENCY_CHECK and len(raw) == _LATENCY_PACKET_SIZE:
                pkt_type, mac, ts = struct.unpack(_LATENCY_PACKET_FORMAT, raw)
                if pkt_type == LATENCY_CHECK:  # Double check packet type
                    # Echo it back immediately
                    sock.sendto(raw, addr)
                    continue
            
            # Handle regular sensor data packets
            elif packet_type == SENSOR_DATA and len(raw) == _SENSOR_DATA_SIZE:
                pkt_type, mac, ts, qw, qx, qy, qz, ax, ay, az, gx, gy, gz = struct.unpack(_SENSOR_DATA_FORMAT, raw)
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

