#include "provisioning.h"
#include "wifi_credentials_store.h"
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>

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

static uint32_t fnv1a32(const uint8_t *data, size_t len) {
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < len; ++i) {
        hash ^= data[i];
        hash *= 16777619u;
    }
    return hash;
}

static uint32_t provisioningPacketChecksum(const ProvisioningSetWiFiPacket *packet) {
    return fnv1a32(reinterpret_cast<const uint8_t *>(packet), offsetof(ProvisioningSetWiFiPacket, checksum));
}

static bool isBroadcastMac(const uint8_t mac[6]) {
    for (int i = 0; i < 6; ++i) {
        if (mac[i] != 0xFF) {
            return false;
        }
    }
    return true;
}

static void sendProvisioningAck(
    WiFiUDP &udp,
    const uint8_t macAddr[6],
    const ProvisioningSettings &settings,
    uint8_t status,
    IPAddress targetIp) {
    ProvisioningAckPacket ack = {
        .type = PROVISIONING_ACK,
        .status = status,
    };
    static int unsuccessfulPacketSends = 0;
    const int maxUnsuccessfulSends = 100;

    memcpy(ack.mac, macAddr, 6);
    udp.beginPacket(targetIp, settings.udpRemotePort);
    udp.write((const uint8_t *)&ack, sizeof(ack));
    if (udp.endPacket()) {
        unsuccessfulPacketSends = 0;
    } else if (++unsuccessfulPacketSends > maxUnsuccessfulSends) {
        Serial.println("Too many unsuccessful packet sends, resetting...");
        rp2040.reboot();
    }
}

bool isProvisioningButtonHeldOnBoot(uint8_t buttonPin, uint32_t holdMs) {
    unsigned long holdStart = millis();
    while (millis() - holdStart < holdMs) {
        if (digitalRead(buttonPin) != LOW) {
            return false;
        }
        delay(20);
    }
    return true;
}

static bool connectWithCredential(const wifiCredentialEntry &credential, const ProvisioningSettings &settings) {
    Serial.print("Trying SSID: ");
    Serial.println(credential.ssid);

    WiFi.mode(WIFI_STA);
    WiFi.disconnect();
    delay(100);

    if ((credential.authType == settings.wifiAuthOpen) || (credential.password[0] == '\0')) {
        WiFi.begin(credential.ssid);
    } else {
        WiFi.begin(credential.ssid, credential.password);
    }

    unsigned long start = millis();
    while (millis() - start < settings.wifiConnectTimeoutMs) {
        Serial.printf("%s %s %d\n", credential.ssid, credential.password, WiFi.status());
        if (WiFi.status() == WL_CONNECTED) {
            Serial.print("Connected to ");
            Serial.println(credential.ssid);
            return true;
        } else if (WiFi.status() == WL_CONNECT_FAILED) {
            Serial.println("Connection failed");
            return false;
        }
        delay(100);
    }

    Serial.println("Connection attempt timed out");
    return false;
}

bool connectFromStoredCredentials(const ProvisioningSettings &settings) {
    wifiCredentialStore store;
    if (!wifiCredentialsLoad(&store) || store.count == 0) {
        Serial.println("No saved Wi-Fi credentials found.");
        return false;
    }

    for (uint16_t i = 0; i < store.count; ++i) {
        if (connectWithCredential(store.entries[i], settings)) {
            wifiCredentialsMarkUsed(store.entries[i].ssid, store.entries[i].authType);
            return true;
        }
    }

    return false;
}

void enterProvisioningAPMode(
    WiFiUDP &udp,
    uint8_t macAddr[6],
    const ProvisioningSettings &settings,
    bool wipedCredentials,
    PulseHapticCallback pulseHaptic) {
    WiFi.disconnect(true);
    WiFi.mode(WIFI_AP);
    delay(100);

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

    uint8_t status = (settings.apPass == nullptr || strlen(settings.apPass) == 0) ? WiFi.beginAP(apSsid) : WiFi.beginAP(apSsid, settings.apPass);
    if (status != WL_CONNECTED) {
        Serial.println("Failed to start AP provisioning mode. Rebooting...");
        rp2040.reboot();
    }

    udp.begin(settings.udpLocalPort);

    Serial.println("AP provisioning mode active");
    Serial.print("SSID: ");
    Serial.println(apSsid);
    Serial.print("Passphrase: ");
    Serial.println(settings.apPass);
    Serial.print("AP IP: ");
    Serial.println(WiFi.softAPIP());

    if (wipedCredentials && pulseHaptic) {
        pulseHaptic(80, 70, 3);
    }

    while (true) {
        int packetSize = udp.parsePacket();
        if (packetSize == static_cast<int>(sizeof(ProvisioningSetWiFiPacket))) {
            ProvisioningSetWiFiPacket pkt;
            udp.read(reinterpret_cast<uint8_t *>(&pkt), sizeof(pkt));
            Serial.println("Received provisioning packet!");

            if (pkt.type != PROVISIONING_SET_WIFI) {
                continue;
            }

            if ((memcmp(pkt.mac, macAddr, 6) != 0) && !isBroadcastMac(pkt.mac)) {
                sendProvisioningAck(udp, macAddr, settings, settings.ackWrongTarget, udp.remoteIP());
                continue;
            }

            if (pkt.checksum != provisioningPacketChecksum(&pkt)) {
                sendProvisioningAck(udp, macAddr, settings, settings.ackInvalidPayload, udp.remoteIP());
                continue;
            }

            pkt.ssid[WIFI_SSID_MAX_LEN] = '\0';
            pkt.password[WIFI_PASS_MAX_LEN] = '\0';

            if (pkt.ssid[0] == '\0') {
                sendProvisioningAck(udp, macAddr, settings, settings.ackInvalidPayload, udp.remoteIP());
                continue;
            }

            uint8_t authType = pkt.auth_type;
            if (pkt.password[0] == '\0') {
                authType = settings.wifiAuthOpen;
            } else if (authType != settings.wifiAuthOpen) {
                authType = settings.wifiAuthWpa2Psk;
            }

            if (!wifiCredentialsAddOrUpdate(pkt.ssid, pkt.password, authType)) {
                sendProvisioningAck(udp, macAddr, settings, settings.ackWriteFailed, udp.remoteIP());
                continue;
            }

            sendProvisioningAck(udp, macAddr, settings, settings.ackOk, udp.remoteIP());
            Serial.println("Provisioning payload accepted. Rebooting into STA mode...");
            if (pulseHaptic) {
                pulseHaptic(120, 80, 2);
            }
            if (WiFi.disconnectAP()) {
                Serial.println("AP stopped successfully.");
                return;
            } else {
                Serial.println("Rebooting into STA mode.");
                delay(300);
                rp2040.reboot();
            }
        } else if (packetSize > 0) {
            uint8_t buffer[packetSize];
            udp.readBytes(buffer, packetSize);
        }

        delay(10);
    }
}
