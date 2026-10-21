#include "networking.h"
#include "consts.h"
#include "wifi_credentials_store.h"
#include "vibration_motor_utils.h"
#include "battery_measurement.h"
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
    HAPTIC_FEEDBACK = 0x04,         // Haptic feedback command
    IDENTIFY_REQUEST = 0x05,        // Host triggers a short identify vibration
    BATTERY_MEASUREMENT = 0x06,     // Battery level measurement
    MODE_SWITCH_STATE = 0x07,       // Mode switch state change
    PROVISIONING_SET_WIFI = 0x10,   // Server sends Wi-Fi credentials to controller
    PROVISIONING_ACK = 0x11,        // Controller acknowledges Wi-Fi credentials
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
};

struct __attribute__((packed)) HapticFeedbackPacket {
    uint8_t type; // HAPTIC_FEEDBACK
    uint8_t command;
    uint32_t duration_ms;
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
};

uint8_t macAddress[6];
IPAddress broadcastIp(255, 255, 255, 255);
IPAddress serverIp(0, 0, 0, 0);
WiFiUDP udp;
bool discovered = false;
int unsuccessfulPacketSends = 0;
unsigned long lastDiscoveryTime = millis();

template <typename Packet>
void sendUdpPacket(const Packet &packet, IPAddress targetIp) {
    udp.beginPacket(targetIp, UDP_REMOTE_PORT);
    udp.write(reinterpret_cast<const uint8_t *>(&packet), sizeof(packet));
    if (udp.endPacket()) {
        unsuccessfulPacketSends = 0;
    } else if (++unsuccessfulPacketSends > MAX_UNSUCCESSFUL_SENDS) {
        Serial.println("Too many unsuccessful packet sends, resetting...");
        rp2040.reboot();
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
        discovered = true;
        Serial.print("Server discovered at: ");
        Serial.println(serverIp);
    }

    sendInitialPackets();
}

void handleLatencyPing() {
    LatencyPacket ping;
    udp.read(reinterpret_cast<uint8_t *>(&ping), sizeof(ping));
    if (ping.type == LATENCY_CHECK && memcmp(ping.mac, macAddress, 6) == 0) {
        sendUdpPacket(ping, serverIp);
    }
}

void handleHapticFeedback() {
    Serial.println("Received haptic feedback command");
    HapticFeedbackPacket packet;
    udp.read(reinterpret_cast<uint8_t *>(&packet), sizeof(packet));
    if (packet.command == 0x01) {
        handleHapticCommand(packet.duration_ms);
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

void initializeNetworking() {
    WiFi.mode(WIFI_STA);
    WiFi.macAddress(macAddress);

    if (isProvisioningButtonHeldOnBoot(PROVISIONING_SETTINGS.forceApHoldMs)) {
        Serial.println("Boot button hold detected. Wiping saved Wi-Fi credentials.");
        wifiCredentialsClear();
        enterProvisioningAPMode(udp, macAddress, PROVISIONING_SETTINGS, true);
    }

    while (!connectFromStoredCredentials(PROVISIONING_SETTINGS)) {
        Serial.println("Unable to connect using saved credentials. Entering AP provisioning mode.");
        enterProvisioningAPMode(udp, macAddress, PROVISIONING_SETTINGS, false);
    }

    WiFi.macAddress(macAddress);
    udp.begin(UDP_LOCAL_PORT);
    Serial.println("WiFi connected");
}

bool processNetworking() {
    if (!discovered) {
        handleDiscoveryResponse();
        if (!discovered && millis() - lastDiscoveryTime >= 1000) {
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

    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        byte type = udp.peek();
        if (type == LATENCY_CHECK && packetSize == sizeof(LatencyPacket)) {
            handleLatencyPing();
        } else if (type == HAPTIC_FEEDBACK && packetSize == sizeof(HapticFeedbackPacket)) {
            handleHapticFeedback();
        } else if (type == IDENTIFY_REQUEST && packetSize == sizeof(IdentifyRequestPacket)) {
            handleIdentifyRequest();
        } else {
            // Unknown packet type or size, ignore
            uint8_t buffer[packetSize];
            udp.readBytes(buffer, packetSize);
        }
    }
    return true;
}

void sendSensorData(const IMUReading &reading) {
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
        .gz = reading.gz};
    memcpy(packet.mac, macAddress, 6);
    if (discovered) {
        sendUdpPacket(packet, serverIp);
    }
}

void sendBatteryMeasurement(uint8_t percentage) {
    BatteryMeasurementPacket packet = {
        .type = BATTERY_MEASUREMENT,
        .percentage = percentage};
    memcpy(packet.mac, macAddress, 6);
    if (discovered) {
        sendUdpPacket(packet, serverIp);
    }
}

// TODO what if this packet gets lost?
void sendModeSwitchState(uint8_t mode) {
    ModeSwitchStatePacket packet = {
        .type = MODE_SWITCH_STATE,
        .mode = mode};
    memcpy(packet.mac, macAddress, 6);
    if (discovered) {
        sendUdpPacket(packet, serverIp);
    }
}