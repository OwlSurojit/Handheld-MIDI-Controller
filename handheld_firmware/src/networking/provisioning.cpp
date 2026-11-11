#include "provisioning.h"
#include "consts.h"
#include "wifi_credentials_store.h"
#include "peripherals/vibration_motor_utils.h"
#include "peripherals/led_ring_utils.h"
#include <Arduino.h>
#include <WiFi.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

namespace {
enum ProvisioningPacketType : uint8_t {
    PROVISIONING_SET_WIFI = 0x10,
    PROVISIONING_ACK = 0x11,
};

struct __attribute__((packed)) ProvisioningSetWiFiPacket {
    uint8_t type;
    uint8_t mac[6];
    uint8_t auth_type;
    char ssid[WIFI_SSID_MAX_LEN + 1];
    char password[WIFI_PASS_MAX_LEN + 1];
    uint32_t checksum;
};

struct __attribute__((packed)) ProvisioningAckPacket {
    uint8_t type;
    uint8_t mac[6];
    uint8_t status;
};

WiFiUDP *provisioningUdp = nullptr;
uint8_t *provisioningMac = nullptr;
const ProvisioningSettings *provisioningSettings = nullptr;
bool rebootAfterProvisioning = false;
unsigned long provisioningRebootAt = 0;

uint32_t fnv1a32(const uint8_t *data, size_t len) {
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < len; ++i) {
        hash ^= data[i];
        hash *= 16777619u;
    }
    return hash;
}

uint32_t provisioningPacketChecksum(const ProvisioningSetWiFiPacket *packet) {
    return fnv1a32(reinterpret_cast<const uint8_t *>(packet), offsetof(ProvisioningSetWiFiPacket, checksum));
}

bool isBroadcastMac(const uint8_t mac[6]) {
    for (int i = 0; i < 6; ++i) {
        if (mac[i] != 0xFF) {
            return false;
        }
    }
    return true;
}

void sendProvisioningAck(uint8_t status, IPAddress targetIp) {
    ProvisioningAckPacket ack = {
        .type = PROVISIONING_ACK,
        .status = status,
    };
    memcpy(ack.mac, provisioningMac, 6);
    provisioningUdp->beginPacket(targetIp, provisioningSettings->udpRemotePort);
    provisioningUdp->write(reinterpret_cast<const uint8_t *>(&ack), sizeof(ack));
    if (!provisioningUdp->endPacket()) {
        Serial.println("Failed to send provisioning acknowledgement");
    }
}
}

bool beginProvisioningAPMode(
    WiFiUDP &udp,
    uint8_t macAddr[6],
    const ProvisioningSettings &settings) {
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);
    blinkLedRing(0, 0, 255, 100, 100);
    WiFi.macAddress(macAddr);

    char apSsid[32] = {0};
    snprintf(
        apSsid,
        sizeof(apSsid),
        "MIDI-CTRL-%02X%02X%02X%02X%02X%02X",
        macAddr[0],
        macAddr[1],
        macAddr[2],
        macAddr[3],
        macAddr[4],
        macAddr[5]);

    uint8_t status = (settings.apPass == nullptr || strlen(settings.apPass) == 0)
        ? WiFi.beginAP(apSsid)
        : WiFi.beginAP(apSsid, settings.apPass);
    if (status != WL_CONNECTED) {
        Serial.println("Failed to start AP provisioning mode");
        return false;
    }

    provisioningUdp = &udp;
    provisioningMac = macAddr;
    provisioningSettings = &settings;
    udp.begin(settings.udpLocalPort);

    Serial.println("AP provisioning mode active");
    Serial.print("SSID: ");
    Serial.println(apSsid);
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());
    return true;
}

void processProvisioningAPMode() {
    if (provisioningUdp == nullptr) {
        return;
    }
    if (rebootAfterProvisioning) {
        if (millis() - provisioningRebootAt >= 400) {
            rp2040.reboot();
        }
        return;
    }

    int packetSize = provisioningUdp->parsePacket();
    if (packetSize != static_cast<int>(sizeof(ProvisioningSetWiFiPacket))) {
        if (packetSize > 0) {
            uint8_t buffer[packetSize];
            provisioningUdp->readBytes(buffer, packetSize);
        }
        return;
    }

    ProvisioningSetWiFiPacket packet;
    provisioningUdp->read(reinterpret_cast<uint8_t *>(&packet), sizeof(packet));
    if (packet.type != PROVISIONING_SET_WIFI) {
        return;
    }
    if ((memcmp(packet.mac, provisioningMac, 6) != 0) && !isBroadcastMac(packet.mac)) {
        sendProvisioningAck(provisioningSettings->ackWrongTarget, provisioningUdp->remoteIP());
        return;
    }
    if (packet.checksum != provisioningPacketChecksum(&packet)) {
        sendProvisioningAck(provisioningSettings->ackInvalidPayload, provisioningUdp->remoteIP());
        return;
    }

    packet.ssid[WIFI_SSID_MAX_LEN] = '\0';
    packet.password[WIFI_PASS_MAX_LEN] = '\0';
    if (packet.ssid[0] == '\0') {
        sendProvisioningAck(provisioningSettings->ackInvalidPayload, provisioningUdp->remoteIP());
        return;
    }

    uint8_t authType = packet.auth_type;
    if (packet.password[0] == '\0') {
        authType = provisioningSettings->wifiAuthOpen;
    } else if (authType != provisioningSettings->wifiAuthOpen) {
        authType = provisioningSettings->wifiAuthWpa2Psk;
    }

    if (!wifiCredentialsAddOrUpdate(packet.ssid, packet.password, authType)) {
        sendProvisioningAck(provisioningSettings->ackWriteFailed, provisioningUdp->remoteIP());
        return;
    }

    sendProvisioningAck(provisioningSettings->ackOk, provisioningUdp->remoteIP());
    Serial.println("Provisioning payload accepted. Rebooting into STA mode...");
    pulseVibration(120, 80, 2);
    if (!WiFi.disconnectAP()) {
        Serial.println("Unable to stop AP provisioning mode.");
    }
    rebootAfterProvisioning = true;
    provisioningRebootAt = millis();
}
