#pragma once

#include <WiFiUdp.h>
#include <stdint.h>

struct ProvisioningSettings {
    uint16_t udpRemotePort;
    uint16_t udpLocalPort;
    uint32_t wifiConnectTimeoutMs;
    uint32_t forceApHoldMs;
    const char *apPass;
    uint8_t wifiAuthOpen;
    uint8_t wifiAuthWpa2Psk;
    uint8_t ackOk;
    uint8_t ackInvalidPayload;
    uint8_t ackWriteFailed;
    uint8_t ackWrongTarget;
};

using PulseHapticCallback = void (*)(uint16_t onMs, uint16_t offMs, uint8_t count);

bool isProvisioningButtonHeldOnBoot(uint8_t buttonPin, uint32_t holdMs);
bool connectFromStoredCredentials(const ProvisioningSettings &settings);
void enterProvisioningAPMode(
    WiFiUDP &udp,
    uint8_t macAddr[6],
    const ProvisioningSettings &settings,
    bool wipedCredentials,
    PulseHapticCallback pulseHaptic);
