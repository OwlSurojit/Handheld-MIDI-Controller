/****************************************************************
 * Firmware for the handheld MIDI controller.
 * Developed by Adrian Surojit Müller for Yens&Yens in April 2026.
 *
 * Based on original code by:
 * Paul Clark, April 25th, 2021
 * which was based on code by Owen Lyke @ SparkFun Electronics
 * Original Creation Date: April 17 2019
 *
 * Distributed as-is; no warranty is given.
 ***************************************************************/

#include "consts.h"
#include "EEPROM.h"
#include "eeprom_layout.h"
#include "networking/state.h"
#include "imu/imu_logic.h"
#include "peripherals/battery_measurement.h"
#include "peripherals/vibration_motor_utils.h"
#include "peripherals/button_logic.h"
#include "peripherals/led_ring_utils.h"
#include <Arduino.h>


void eeprom_init() {
    EEPROM.begin(EEPROM_TOTAL_SIZE);
}

void setup() {
    Serial.begin(115200);
    delay(100);

    eeprom_init();
    setupLedRing();

    setupButtons();
    pinMode(HAPTIC_MOTOR_PIN, OUTPUT);
    digitalWrite(HAPTIC_MOTOR_PIN, LOW);
    setupBatteryMeasurement();

    initializeNetworking();

    initializeIMU();

    pulseVibration(80, 100, 2);
}

void loop() {
    handleButtons();
    updateLedRing();
    updateVibration();
    
    if (!processNetworking()) return;

    handleBatteryMeasurement();
    processSensors();
}
