#include "communication.h"
#include "consts.h"
#include "state.h"
#include "peripherals/battery_measurement.h"
#include "peripherals/led_ring_utils.h"
#include "peripherals/vibration_motor_utils.h"
#include <Arduino.h>
#include <WiFi.h>
#include <string.h>

WiFiUDP udp;
uint8_t macAddress[6];

namespace {
enum PacketType : uint8_t {
    DISCOVERY_REQUEST = 0x01,
    DISCOVERY_RESPONSE = 0x02,
    SENSOR_DATA = 0x03,
    HIT_FEEDBACK = 0x04,
    IDENTIFY_REQUEST = 0x05,
    BATTERY_MEASUREMENT = 0x06,
    MODE_SWITCH_STATE = 0x07,
    REZERO_COMMAND = 0x08,
    RELIABLE_PACKET_ACK = 0xFE,
    LATENCY_CHECK = 0xFF
};

struct __attribute__((packed)) DiscoveryRequestPacket {
    uint8_t type;
    uint8_t mac[6];
};

struct __attribute__((packed)) DiscoveryResponsePacket {
    uint8_t type;
};

struct __attribute__((packed)) SensorDataPacket {
    uint8_t type;
    uint8_t mac[6];
    uint32_t ts;
    float qw, qx, qy, qz;
    float ax, ay, az;
    float gx, gy, gz;
    uint8_t sustainPressed;
};

struct __attribute__((packed)) HitFeedbackPacket {
    uint8_t type;
    uint8_t command;
    uint32_t velocity;
};

struct __attribute__((packed)) IdentifyRequestPacket {
    uint8_t type;
};

struct __attribute__((packed)) LatencyPacket {
    uint8_t type;
    uint8_t mac[6];
    uint32_t ts;
};

struct __attribute__((packed)) BatteryMeasurementPacket {
    uint8_t type;
    uint8_t mac[6];
    uint8_t percentage;
};

struct __attribute__((packed)) ModeSwitchStatePacket {
    uint8_t type;
    uint8_t mac[6];
    uint8_t mode;
    uint32_t sequence;
};

struct __attribute__((packed)) RezeroCommandPacket {
    uint8_t type;
    uint8_t mac[6];
    uint32_t sequence;
};

struct __attribute__((packed)) ReliablePacketAck {
    uint8_t type;
    uint8_t acknowledgedType;
    uint8_t status;
    uint8_t mac[6];
    uint32_t sequence;
};

IPAddress broadcastIp(255, 255, 255, 255);
IPAddress serverIp(0, 0, 0, 0);
int unsuccessfulPacketSends = 0;
unsigned long lastDiscoveryTime = 0;
bool communicationReady = false;
constexpr unsigned long RELIABLE_RETRY_INTERVAL_MS = 150;
constexpr uint8_t MAX_RELIABLE_SEND_ATTEMPTS = 20;
constexpr uint8_t RELIABLE_PACKET_MAX_SIZE = sizeof(ModeSwitchStatePacket);

struct ReliablePacketState {
    bool pending;
    uint8_t packetType;
    uint8_t size;
    uint32_t sequence;
    uint8_t sendAttempts;
    unsigned long lastSendTime;
    uint8_t data[RELIABLE_PACKET_MAX_SIZE];
};

ReliablePacketState reliablePackets[2] = {};
uint32_t nextModeSequence = 1;
uint32_t nextRezeroSequence = 1;

bool sendUdpPacketBytes(const uint8_t *data, uint8_t size, IPAddress targetIp) {
    udp.beginPacket(targetIp, UDP_REMOTE_PORT);
    udp.write(data, size);
    if (udp.endPacket()) {
        unsuccessfulPacketSends = 0;
        return true;
    } else if (++unsuccessfulPacketSends > MAX_UNSUCCESSFUL_SENDS) {
        Serial.println("Too many unsuccessful packet sends, resetting...");
        rp2040.reboot();
    }
    return false;
}

template <typename Packet>
bool sendUdpPacket(const Packet &packet, IPAddress targetIp) {
    return sendUdpPacketBytes(reinterpret_cast<const uint8_t *>(&packet), sizeof(packet), targetIp);
}

void sendReliablePacket(ReliablePacketState &state) {
    sendUdpPacketBytes(state.data, state.size, serverIp);
    state.sendAttempts++;
    state.lastSendTime = millis();
}

void queueReliablePacket(uint8_t packetType, const void *packet, uint8_t size, uint32_t sequence) {
    ReliablePacketState *state = nullptr;
    for (ReliablePacketState &candidate : reliablePackets) {
        if (candidate.packetType == packetType || !candidate.pending) {
            state = &candidate;
            if (candidate.packetType == packetType) {
                break;
            }
        }
    }

    if (state == nullptr || size > RELIABLE_PACKET_MAX_SIZE) {
        Serial.println("Unable to queue reliable packet");
        return;
    }

    state->pending = true;
    state->packetType = packetType;
    state->size = size;
    state->sequence = sequence;
    state->sendAttempts = 0;
    memcpy(state->data, packet, size);
    Serial.print("Queued reliable packet, type: ");
    Serial.println(packetType);
    if (communicationReady) {
        sendReliablePacket(*state);
    }
}

void handleReliablePacketAck() {
    ReliablePacketAck ack;
    udp.read(reinterpret_cast<uint8_t *>(&ack), sizeof(ack));
    if (memcmp(ack.mac, macAddress, 6) != 0) {
        return;
    }

    for (ReliablePacketState &state : reliablePackets) {
        if (state.pending && state.packetType == ack.acknowledgedType && state.sequence == ack.sequence) {
            if (ack.status != 0) {
                Serial.print("Reliable packet rejected, type: ");
                Serial.println(ack.acknowledgedType);
            }
            state.pending = false;
            return;
        }
    }
}

void retryReliablePackets() {
    for (ReliablePacketState &state : reliablePackets) {
        if (!state.pending || millis() - state.lastSendTime < RELIABLE_RETRY_INTERVAL_MS) {
            continue;
        }
        if (state.sendAttempts >= MAX_RELIABLE_SEND_ATTEMPTS) {
            Serial.print("Reliable packet was not acknowledged, type: ");
            Serial.println(state.packetType);
            state.pending = false;
            continue;
        }
        sendReliablePacket(state);
    }
}

void handleLatencyPing() {
    LatencyPacket ping;
    udp.read(reinterpret_cast<uint8_t *>(&ping), sizeof(ping));
    if (ping.type == LATENCY_CHECK && memcmp(ping.mac, macAddress, 6) == 0) {
        sendUdpPacket(ping, serverIp);
    }
}

void handleHitFeedback() {
    Serial.println("Received hit feedback command");
    HitFeedbackPacket packet;
    udp.read(reinterpret_cast<uint8_t *>(&packet), sizeof(packet));
    if (packet.command == 0x01) {
        vibrateFor(packet.velocity);
        flashLedRing(0, packet.velocity * 2, 0, packet.velocity * 5);
    }
}

void handleIdentifyRequest() {
    IdentifyRequestPacket packet;
    udp.read(reinterpret_cast<uint8_t *>(&packet), sizeof(packet));
    if (packet.type == IDENTIFY_REQUEST) {
        pulseVibration(90, 60, 2);
    }
}
} // namespace

bool processDiscoveryCommunication() {
    if (udp.parsePacket() == sizeof(DiscoveryResponsePacket)) {
        DiscoveryResponsePacket response;
        udp.read(reinterpret_cast<uint8_t *>(&response), sizeof(response));
        if (response.type == DISCOVERY_RESPONSE) {
            serverIp = udp.remoteIP();
            communicationReady = true;
            Serial.print("Server discovered at: ");
            Serial.println(serverIp);
            flashLedRing(0, 255, 0, 5000);
            pulseVibration(100, 100, 2);
            handleBatteryMeasurement();
            return true;
        }
    }

    if (millis() - lastDiscoveryTime >= 1000) {
        DiscoveryRequestPacket discoveryPacket = {
            .type = DISCOVERY_REQUEST,
        };
        memcpy(discoveryPacket.mac, macAddress, 6);
        sendUdpPacket(discoveryPacket, broadcastIp);
        Serial.println("Sent discovery request");
        lastDiscoveryTime = millis();
    }
    return false;
}

void processReadyCommunication() {
    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        byte type = udp.peek();
        if (type == LATENCY_CHECK && packetSize == sizeof(LatencyPacket)) {
            handleLatencyPing();
        } else if (type == HIT_FEEDBACK && packetSize == sizeof(HitFeedbackPacket)) {
            handleHitFeedback();
        } else if (type == IDENTIFY_REQUEST && packetSize == sizeof(IdentifyRequestPacket)) {
            handleIdentifyRequest();
        } else if (type == RELIABLE_PACKET_ACK && packetSize == sizeof(ReliablePacketAck)) {
            handleReliablePacketAck();
        } else {
            uint8_t buffer[packetSize];
            udp.readBytes(buffer, packetSize);
        }
    }
    retryReliablePackets();
}

bool sendSensorData(const SensorReading &reading) {
    if (!communicationReady) {
        return false;
    }
    SensorDataPacket packet = {
        .type = SENSOR_DATA,
        .ts = reading.timestamp,
        .qw = reading.qw,
        .qx = reading.qx,
        .qy = reading.qy,
        .qz = reading.qz,
        .ax = reading.ax,
        .ay = reading.ay,
        .az = reading.az,
        .gx = reading.gx,
        .gy = reading.gy,
        .gz = reading.gz,
        .sustainPressed = reading.sustainPressed,
    };
    memcpy(packet.mac, macAddress, 6);
    return sendUdpPacket(packet, serverIp);
}

bool sendBatteryMeasurement(uint8_t percentage) {
    if (!communicationReady) {
        return false;
    }
    BatteryMeasurementPacket packet = {
        .type = BATTERY_MEASUREMENT,
        .percentage = percentage,
    };
    memcpy(packet.mac, macAddress, 6);
    return sendUdpPacket(packet, serverIp);
}

bool sendModeSwitchState(uint8_t mode) {
    if (!communicationReady) {
        return false;
    }
    ModeSwitchStatePacket packet = {
        .type = MODE_SWITCH_STATE,
        .mode = mode,
        .sequence = nextModeSequence++,
    };
    memcpy(packet.mac, macAddress, 6);
    queueReliablePacket(MODE_SWITCH_STATE, &packet, sizeof(packet), packet.sequence);
    return true;
}

bool sendRezeroCommand() {
    if (!communicationReady) {
        return false;
    }
    RezeroCommandPacket packet = {
        .type = REZERO_COMMAND,
        .sequence = nextRezeroSequence++,
    };
    memcpy(packet.mac, macAddress, 6);
    queueReliablePacket(REZERO_COMMAND, &packet, sizeof(packet), packet.sequence);
    return true;
}
