#pragma once

#include "imu_logic.h"
#include <stdint.h>

#define MAX_UNSUCCESSFUL_SENDS 100

bool processDiscoveryCommunication();
void processReadyCommunication();

void sendSensorData(const SensorReading &reading);
void sendBatteryMeasurement(uint8_t percentage);
void sendModeSwitchState(uint8_t mode);
void sendRezeroCommand();
