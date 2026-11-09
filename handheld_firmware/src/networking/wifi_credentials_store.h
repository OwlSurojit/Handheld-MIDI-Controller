#pragma once

#include "eeprom_layout.h"
#include <stdint.h>

#define WIFI_CREDENTIAL_MAGIC 0x57494649u // "WIFI"
#define WIFI_CREDENTIAL_VERSION 1u
#define WIFI_CREDENTIAL_SLOTS 4
#define WIFI_SSID_MAX_LEN 32
#define WIFI_PASS_MAX_LEN 64

struct wifiCredentialEntry {
    char ssid[WIFI_SSID_MAX_LEN + 1]     = {0};
    char password[WIFI_PASS_MAX_LEN + 1] = {0};
    uint8_t authType                     = 0;
    uint8_t reserved[3]                  = {0};
    uint32_t lastUsedAtMs                = 0;
};

struct wifiCredentialStore {
    uint32_t magic                            = WIFI_CREDENTIAL_MAGIC;
    uint16_t version                          = WIFI_CREDENTIAL_VERSION;
    uint16_t count                            = 0;
    wifiCredentialEntry entries[WIFI_CREDENTIAL_SLOTS];
    uint32_t checksum                         = 0;
};

// Load all saved Wi-Fi credentials. Returns false if no valid store is present.
bool wifiCredentialsLoad(wifiCredentialStore *outStore);

// Save a full Wi-Fi credential store. Returns false if the input is invalid.
bool wifiCredentialsSave(const wifiCredentialStore *store);

// Clear all persisted Wi-Fi credentials.
void wifiCredentialsClear();

// Add or update one Wi-Fi entry and move it to the most-recent position.
bool wifiCredentialsAddOrUpdate(const char *ssid, const char *password, uint8_t authType);

// Mark an existing Wi-Fi entry as used, moving it to most-recent position.
bool wifiCredentialsMarkUsed(const char *ssid, uint8_t authType);

// Convenience helpers to iterate credentials in recency order.
int wifiCredentialsCount();
bool wifiCredentialsGetByIndex(int index, wifiCredentialEntry *outCredential);
