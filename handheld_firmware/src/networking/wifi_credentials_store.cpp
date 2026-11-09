#include "wifi_credentials_store.h"
#include <Arduino.h>
#include <ctype.h>
#include <stddef.h>
#include <string.h>

static uint32_t fnv1a32(const uint8_t *data, size_t len) {
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < len; ++i) {
        hash ^= data[i];
        hash *= 16777619u;
    }
    return hash;
}

static uint32_t computeWiFiStoreChecksum(const wifiCredentialStore *store) {
    return fnv1a32(reinterpret_cast<const uint8_t *>(store), offsetof(wifiCredentialStore, checksum));
}

static void initEmptyWiFiStore(wifiCredentialStore *store) {
    memset(store, 0, sizeof(*store));
    store->magic = WIFI_CREDENTIAL_MAGIC;
    store->version = WIFI_CREDENTIAL_VERSION;
    store->count = 0;
    store->checksum = computeWiFiStoreChecksum(store);
}

static bool isWiFiStoreValid(const wifiCredentialStore *store) {
    if (store->magic != WIFI_CREDENTIAL_MAGIC) {
        return false;
    }
    if (store->version != WIFI_CREDENTIAL_VERSION) {
        return false;
    }
    if (store->count > WIFI_CREDENTIAL_SLOTS) {
        return false;
    }
    return (store->checksum == computeWiFiStoreChecksum(store));
}

static bool loadWiFiStoreInternal(wifiCredentialStore *store) {
    EEPROM.get(WIFI_CREDENTIAL_EEPROM_ADDR, *store);
    return isWiFiStoreValid(store);
}

static void writeWiFiStoreInternal(const wifiCredentialStore *store) {
    wifiCredentialStore copy = *store;
    copy.checksum = computeWiFiStoreChecksum(&copy);
    EEPROM.put(WIFI_CREDENTIAL_EEPROM_ADDR, copy);
    EEPROM.commit();
}

static void trimCopy(const char *src, char *dst, size_t dstSize) {
    if ((dst == nullptr) || (dstSize == 0)) {
        return;
    }
    dst[0] = '\0';
    if (src == nullptr) {
        return;
    }

    const char *start = src;
    while ((*start != '\0') && isspace(static_cast<unsigned char>(*start))) {
        start++;
    }

    const char *end = start + strlen(start);
    while ((end > start) && isspace(static_cast<unsigned char>(*(end - 1)))) {
        end--;
    }

    size_t len = static_cast<size_t>(end - start);
    if (len >= dstSize) {
        len = dstSize - 1;
    }
    memcpy(dst, start, len);
    dst[len] = '\0';
}

static void boundedCopy(const char *src, char *dst, size_t dstSize) {
    if ((dst == nullptr) || (dstSize == 0)) {
        return;
    }
    dst[0] = '\0';
    if (src == nullptr) {
        return;
    }

    strncpy(dst, src, dstSize - 1);
    dst[dstSize - 1] = '\0';
}


bool wifiCredentialsLoad(wifiCredentialStore *outStore) {
    if (outStore == nullptr) {
        return false;
    }

    if (!loadWiFiStoreInternal(outStore)) {
        initEmptyWiFiStore(outStore);
        return false;
    }
    return true;
}

bool wifiCredentialsSave(const wifiCredentialStore *store) {
    if (store == nullptr) {
        return false;
    }
    if (store->count > WIFI_CREDENTIAL_SLOTS) {
        return false;
    }
    writeWiFiStoreInternal(store);
    return true;
}

void wifiCredentialsClear() {
    wifiCredentialStore store;
    initEmptyWiFiStore(&store);
    writeWiFiStoreInternal(&store);
}

bool wifiCredentialsAddOrUpdate(const char *ssid, const char *password, uint8_t authType) {
    char normalizedSsid[WIFI_SSID_MAX_LEN + 1] = {0};
    trimCopy(ssid, normalizedSsid, sizeof(normalizedSsid));
    if (normalizedSsid[0] == '\0') {
        return false;
    }

    wifiCredentialStore store;
    if (!loadWiFiStoreInternal(&store)) {
        initEmptyWiFiStore(&store);
    }

    int existingIndex = -1;
    for (int i = 0; i < static_cast<int>(store.count); ++i) {
        if ((store.entries[i].authType == authType) && (strcmp(store.entries[i].ssid, normalizedSsid) == 0)) {
            existingIndex = i;
            break;
        }
    }

    wifiCredentialEntry updated;
    boundedCopy(normalizedSsid, updated.ssid, sizeof(updated.ssid));
    boundedCopy(password, updated.password, sizeof(updated.password));
    updated.authType = authType;
    updated.lastUsedAtMs = millis();

    if (existingIndex >= 0) {
        for (int i = existingIndex; i > 0; --i) {
            store.entries[i] = store.entries[i - 1];
        }
        store.entries[0] = updated;
    } else {
        int lastIndex = (store.count < WIFI_CREDENTIAL_SLOTS) ? static_cast<int>(store.count) : (WIFI_CREDENTIAL_SLOTS - 1);
        for (int i = lastIndex; i > 0; --i) {
            store.entries[i] = store.entries[i - 1];
        }
        store.entries[0] = updated;
        if (store.count < WIFI_CREDENTIAL_SLOTS) {
            store.count++;
        }
    }

    writeWiFiStoreInternal(&store);
    return true;
}

bool wifiCredentialsMarkUsed(const char *ssid, uint8_t authType) {
    char normalizedSsid[WIFI_SSID_MAX_LEN + 1] = {0};
    trimCopy(ssid, normalizedSsid, sizeof(normalizedSsid));
    if (normalizedSsid[0] == '\0') {
        return false;
    }

    wifiCredentialStore store;
    if (!loadWiFiStoreInternal(&store)) {
        return false;
    }

    int existingIndex = -1;
    for (int i = 0; i < static_cast<int>(store.count); ++i) {
        if ((store.entries[i].authType == authType) && (strcmp(store.entries[i].ssid, normalizedSsid) == 0)) {
            existingIndex = i;
            break;
        }
    }
    if (existingIndex < 0) {
        return false;
    }

    wifiCredentialEntry updated = store.entries[existingIndex];
    updated.lastUsedAtMs = millis();

    for (int i = existingIndex; i > 0; --i) {
        store.entries[i] = store.entries[i - 1];
    }
    store.entries[0] = updated;

    writeWiFiStoreInternal(&store);
    return true;
}

int wifiCredentialsCount() {
    wifiCredentialStore store;
    if (!loadWiFiStoreInternal(&store)) {
        return 0;
    }
    return static_cast<int>(store.count);
}

bool wifiCredentialsGetByIndex(int index, wifiCredentialEntry *outCredential) {
    if ((index < 0) || (outCredential == nullptr)) {
        return false;
    }

    wifiCredentialStore store;
    if (!loadWiFiStoreInternal(&store)) {
        return false;
    }
    if (index >= static_cast<int>(store.count)) {
        return false;
    }

    *outCredential = store.entries[index];
    return true;
}
