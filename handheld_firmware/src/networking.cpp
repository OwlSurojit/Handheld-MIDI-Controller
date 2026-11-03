#include "networking.h"
#include "consts.h"
#include "wifi_credentials_store.h"
#include "vibration_motor_utils.h"
#include "battery_measurement.h"
#include "led_ring_utils.h"
#include "button_logic.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <string.h>

namespace {
const ProvisioningSettings PROVISIONING_SETTINGS = {
    .udpRemotePort = UDP_REMOTE_PORT,
    .udpLocalPort = UDP_LOCAL_PORT,
    .wifiConnectTimeoutMs = 20000,
    .forceApHoldMs = 3000,
    .apPass = "",
    .wifiAuthOpen = 0x00,
    .wifiAuthWpa2Psk = 0x01,
    .ackOk = 0x00,
    .ackInvalidPayload = 0x01,
    .ackWriteFailed = 0x02,
    .ackWrongTarget = 0x03,
};

// Packet type constants
enum PacketType : uint8_t {
    DISCOVERY_REQUEST = 0x01,       // Controller sends to broadcast
    DISCOVERY_RESPONSE = 0x02,      // Server responds with its IP
    SENSOR_DATA = 0x03,             // Normal sensor data
    HIT_FEEDBACK = 0x04,            // Hit feedback command
    IDENTIFY_REQUEST = 0x05,        // Host triggers a short identify vibration
    BATTERY_MEASUREMENT = 0x06,     // Battery level measurement
    MODE_SWITCH_STATE = 0x07,       // Mode switch state change
    REZERO_COMMAND = 0x08,          // Rezero this controller
    PROVISIONING_SET_WIFI = 0x10,   // Server sends Wi-Fi credentials to controller
    PROVISIONING_ACK = 0x11,        // Controller acknowledges Wi-Fi credentials
    RELIABLE_PACKET_ACK = 0xFE,     // Acknowledges a reliable controller packet
    LATENCY_CHECK = 0xFF            // Latency test echo packet
};

struct __attribute__((packed)) DiscoveryRequestPacket {
    uint8_t type; // DISCOVERY_REQUEST
    uint8_t mac[6];
};

struct __attribute__((packed)) DiscoveryResponsePacket {
    uint8_t type; // DISCOVERY_RESPONSE
};

struct __attribute__((packed)) SensorDataPacket {
    uint8_t type; // SENSOR_DATA
    uint8_t mac[6];
    uint32_t ts;
    float qw, qx, qy, qz;
    float ax, ay, az;
    float gx, gy, gz;
    uint8_t sustainPressed;
};

struct __attribute__((packed)) HitFeedbackPacket {
    uint8_t type; // HIT_FEEDBACK
    uint8_t command;
    uint32_t velocity;
};

struct __attribute__((packed)) IdentifyRequestPacket {
    uint8_t type; // IDENTIFY_REQUEST
};

struct __attribute__((packed)) LatencyPacket {
    uint8_t type; // LATENCY_CHECK
    uint8_t mac[6];
    uint32_t ts; // Local milliseconds when sent
};

struct __attribute__((packed)) BatteryMeasurementPacket {
    uint8_t type; // BATTERY_MEASUREMENT
    uint8_t mac[6];
    uint8_t percentage;
};

struct __attribute__((packed)) ModeSwitchStatePacket {
    uint8_t type; // MODE_SWITCH_STATE
    uint8_t mac[6];
    uint8_t mode; // 0 = Hit, 1 = Both, 2 = Map
    uint32_t sequence;
};

struct __attribute__((packed)) RezeroCommandPacket {
    uint8_t type; // REZERO_COMMAND
    uint8_t mac[6];
    uint32_t sequence;
};

struct __attribute__((packed)) ReliablePacketAck {
    uint8_t type; // RELIABLE_PACKET_ACK
    uint8_t acknowledgedType;
    uint8_t status; // 0 = accepted, non-zero = rejected
    uint8_t mac[6];
    uint32_t sequence;
};

uint8_t macAddress[6];
IPAddress broadcastIp(255, 255, 255, 255);
IPAddress serverIp(0, 0, 0, 0);
WiFiUDP udp;
int unsuccessfulPacketSends = 0;
unsigned long lastDiscoveryTime = millis();
enum class NetworkState {
    CheckingBootButton,
    Connecting,
    Provisioning,
    Discovering,
    Ready
};
NetworkState networkState = NetworkState::CheckingBootButton;
unsigned long bootButtonCheckStartedAt = 0;
unsigned long connectionStartedAt = 0;
int credentialIndex = 0;
wifiCredentialEntry currentCredential;
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

void sendUdpPacketBytes(const uint8_t *data, uint8_t size, IPAddress targetIp) {
    udp.beginPacket(targetIp, UDP_REMOTE_PORT);
    udp.write(data, size);
    if (udp.endPacket()) {
        unsuccessfulPacketSends = 0;
    } else if (++unsuccessfulPacketSends > MAX_UNSUCCESSFUL_SENDS) {
        Serial.println("Too many unsuccessful packet sends, resetting...");
        rp2040.reboot();
    }
}

template <typename Packet>
void sendUdpPacket(const Packet &packet, IPAddress targetIp) {
    sendUdpPacketBytes(reinterpret_cast<const uint8_t *>(&packet), sizeof(packet), targetIp);
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
    if (networkState == NetworkState::Ready) {
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

void sendInitialPackets() {
    handleBatteryMeasurement();
}

void handleDiscoveryResponse() {
    if (udp.parsePacket() != sizeof(DiscoveryResponsePacket)) {
        return;
    }

    DiscoveryResponsePacket response;
    udp.read(reinterpret_cast<uint8_t *>(&response), sizeof(response));
    if (response.type == DISCOVERY_RESPONSE) {
        serverIp = udp.remoteIP();
        networkState = NetworkState::Ready;
        Serial.print("Server discovered at: ");
        Serial.println(serverIp);
    }

    flashLedRing(0, 255, 0, 5000);
    pulseVibration(100, 100, 2);

    sendInitialPackets();
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
        flashLedRing(0, packet.velocity*2, 0, packet.velocity*5);
    }
}

void handleIdentifyRequest() {
    IdentifyRequestPacket packet;
    udp.read(reinterpret_cast<uint8_t *>(&packet), sizeof(packet));
    if (packet.type == IDENTIFY_REQUEST) {
        pulseVibration(90, 60, 2);
    }
}

void startNextCredentialOrProvisioning() {
    if (credentialIndex >= wifiCredentialsCount()) {
        if (beginProvisioningAPMode(udp, macAddress, PROVISIONING_SETTINGS, false)) {
            networkState = NetworkState::Provisioning;
        }
        return;
    }

    if (!wifiCredentialsGetByIndex(credentialIndex++, &currentCredential)) {
        startNextCredentialOrProvisioning();
        return;
    }

    blinkLedRing(255, 255, 0, 300, 300);

    Serial.print("Trying SSID: ");
    Serial.println(currentCredential.ssid);
    WiFi.disconnect();
    if ((currentCredential.authType == PROVISIONING_SETTINGS.wifiAuthOpen) ||
        (currentCredential.password[0] == '\0')) {
        WiFi.begin(currentCredential.ssid);
    } else {
        WiFi.begin(currentCredential.ssid, currentCredential.password);
    }
    connectionStartedAt = millis();
    networkState = NetworkState::Connecting;
}

void processConnection() {
    if (WiFi.status() == WL_CONNECTED) {
        wifiCredentialsMarkUsed(currentCredential.ssid, currentCredential.authType);
        udp.begin(UDP_LOCAL_PORT);
        Serial.println("WiFi connected");
        networkState = NetworkState::Discovering;
        blinkLedRing(0, 255, 0, 500, 500);
        return;
    }

    if (millis() - connectionStartedAt >= PROVISIONING_SETTINGS.wifiConnectTimeoutMs) {
        Serial.println("Connection attempt timed out");
        startNextCredentialOrProvisioning();
    }
}
} // namespace

void initializeNetworking() {
    WiFi.mode(WIFI_STA);
    WiFi.macAddress(macAddress);
    bootButtonCheckStartedAt = millis();
    networkState = NetworkState::CheckingBootButton;
}

bool processNetworking() {
    switch (networkState) {
        case NetworkState::CheckingBootButton:
            if (digitalRead(RESET_REZERO_BUTTON_PIN) != LOW) {
                credentialIndex = 0;
                startNextCredentialOrProvisioning();
            } else if (millis() - bootButtonCheckStartedAt >= PROVISIONING_SETTINGS.forceApHoldMs) {
                Serial.println("Boot button hold detected. Wiping saved Wi-Fi credentials.");
                wifiCredentialsClear();
                if (beginProvisioningAPMode(udp, macAddress, PROVISIONING_SETTINGS, true)) {
                    networkState = NetworkState::Provisioning;
                }
            }
            return false;

        case NetworkState::Connecting:
            processConnection();
            return false;

        case NetworkState::Provisioning:
            processProvisioningAPMode();
            return false;

        case NetworkState::Discovering:
            handleDiscoveryResponse();
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

        case NetworkState::Ready:
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
                    // Unknown packet type or size, ignore
                    uint8_t buffer[packetSize];
                    udp.readBytes(buffer, packetSize);
                }
            }
            retryReliablePackets();
            return true;
    }
    return false;
}

void sendSensorData(const SensorReading &reading) {
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
        .sustainPressed = reading.sustainPressed
    };
    memcpy(packet.mac, macAddress, 6);
    if (networkState == NetworkState::Ready) {
        sendUdpPacket(packet, serverIp);
    }
}

void sendBatteryMeasurement(uint8_t percentage) {
    BatteryMeasurementPacket packet = {
        .type = BATTERY_MEASUREMENT,
        .percentage = percentage};
    memcpy(packet.mac, macAddress, 6);
    if (networkState == NetworkState::Ready) {
        sendUdpPacket(packet, serverIp);
    }
}

void sendModeSwitchState(uint8_t mode) {
    ModeSwitchStatePacket packet = {
        .type = MODE_SWITCH_STATE,
        .mode = mode,
        .sequence = nextModeSequence++};
    memcpy(packet.mac, macAddress, 6);
    queueReliablePacket(MODE_SWITCH_STATE, &packet, sizeof(packet), packet.sequence);
}

void sendRezeroCommand() {
    RezeroCommandPacket packet = {
        .type = REZERO_COMMAND,
        .sequence = nextRezeroSequence++};
    memcpy(packet.mac, macAddress, 6);
    queueReliablePacket(REZERO_COMMAND, &packet, sizeof(packet), packet.sequence);
}