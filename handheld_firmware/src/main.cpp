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
#include "networking.h"
#include "imu_logic.h"
#include "battery_measurement.h"
#include "vibration_motor_utils.h"
#include "button_logic.h"
#include <Adafruit_NeoPixel.h>


void eeprom_init() {
    EEPROM.begin(EEPROM_TOTAL_SIZE);
}

void setup() {
    Serial.begin(115200);
    delay(100);

    eeprom_init();

    setupButtons();
    pinMode(HAPTIC_MOTOR_PIN, OUTPUT);
    digitalWrite(HAPTIC_MOTOR_PIN, LOW);
    setupBatteryMeasurement();

    Adafruit_NeoPixel ledRing(NUMLEDS, LED_RING_PIN, NEO_GRB + NEO_KHZ800);
    ledRing.begin();
    ledRing.clear();
    ledRing.fill(ledRing.Color(0, 255, 0), 0, NUMLEDS);
    ledRing.show();

    initializeNetworking();

    pulseVibration(80, 60, 1);

    initializeIMU();
}

void loop() {
    handleButtons();

    if (!processNetworking()) {
        return;
    }

    handleHapticCommandEnd();
    handleBatteryMeasurement();
    processIMU();
}
