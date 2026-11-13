#pragma once

#include "imu/imu_logic.h"
#include <stdint.h>

#define MAX_UNSUCCESSFUL_SENDS 100

bool processDiscoveryCommunication();
void processReadyCommunication();

bool sendSensorData(const SensorReading &reading);
bool sendBatteryMeasurement(uint8_t percentage);
bool sendModeSwitchState(uint8_t mode);
bool sendRezeroCommand();
