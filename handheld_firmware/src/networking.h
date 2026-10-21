#pragma once

#include <stdint.h>

#include "provisioning.h"
#include "imu_logic.h"

#define MAX_UNSUCCESSFUL_SENDS 100

void clearStoredWifiCredentials();
void initializeNetworking();
bool processNetworking();
void sendSensorData(const IMUReading &reading);
void sendBatteryMeasurement(uint8_t percentage);
