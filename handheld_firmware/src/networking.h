#pragma once

#include <stdint.h>

#include "provisioning.h"
#include "imu_logic.h"

#define MAX_UNSUCCESSFUL_SENDS 100

void initializeNetworking();
bool processNetworking();
void sendSensorData(const SensorReading &reading);
void sendBatteryMeasurement(uint8_t percentage);
void sendModeSwitchState(uint8_t mode);
void sendRezeroCommand();