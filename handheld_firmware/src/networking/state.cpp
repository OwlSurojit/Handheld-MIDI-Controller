#include "state.h"
#include "provisioning.h"
#include "wifi_credentials_store.h"
#include "communication.h"
#include "consts.h"
#include "peripherals/led_ring_utils.h"
#include <Arduino.h>
#include <WiFi.h>

namespace {
const ProvisioningSettings PROVISIONING_SETTINGS = {
    .udpRemotePort = UDP_REMOTE_PORT,
    .udpLocalPort = UDP_LOCAL_PORT,
    .wifiConnectTimeoutMs = 20000,
    .apPass = "",
    .wifiAuthOpen = 0x00,
    .wifiAuthWpa2Psk = 0x01,
    .ackOk = 0x00,
    .ackInvalidPayload = 0x01,
    .ackWriteFailed = 0x02,
    .ackWrongTarget = 0x03,
};

enum class NetworkState {
    Connecting,
    Provisioning,
    Discovering,
    Ready
};

NetworkState networkState = NetworkState::Connecting;
unsigned long connectionStartedAt = 0;
int credentialIndex = 0;
wifiCredentialEntry currentCredential;

void startNextCredentialOrProvisioning() {
    if (credentialIndex >= wifiCredentialsCount()) {
        if (beginProvisioningAPMode(
                udp,
                macAddress,
                PROVISIONING_SETTINGS)) {
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

    if (WiFi.status() == WL_CONNECT_FAILED ||
        millis() - connectionStartedAt >= PROVISIONING_SETTINGS.wifiConnectTimeoutMs) {
        Serial.println("Connection attempt timed out");
        startNextCredentialOrProvisioning();
    }
}
} // namespace

void initializeNetworking() {
    WiFi.mode(WIFI_STA);
    WiFi.macAddress(macAddress);
    networkState = NetworkState::Connecting;
    credentialIndex = 0;
    startNextCredentialOrProvisioning();
}

bool processNetworking() {
    switch (networkState) {
    case NetworkState::Connecting:
        processConnection();
        return false;

    case NetworkState::Provisioning:
        processProvisioningAPMode();
        return false;

    case NetworkState::Discovering:
        if (processDiscoveryCommunication()) {
            networkState = NetworkState::Ready;
        }
        return false;

    case NetworkState::Ready:
        processReadyCommunication();
        return true;
    }
    return false;
}
