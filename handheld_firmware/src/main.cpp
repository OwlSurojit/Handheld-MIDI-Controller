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
#include <Adafruit_NeoPixel.h>


void eeprom_init() {
    EEPROM.begin(EEPROM_TOTAL_SIZE);
}

void setup() {
    Serial.begin(115200);
    delay(100);

    eeprom_init();

    pinMode(RESET_REZERO_BUTTON_PIN, INPUT_PULLUP);
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

unsigned long resetButtonHeldSince = 0;

void handleResetRezero() {
    if (digitalRead(RESET_REZERO_BUTTON_PIN) == LOW) {
        if (resetButtonHeldSince == 0) {
            resetButtonHeldSince = millis();
        } else if (millis() - resetButtonHeldSince >= HOLD_RESET_MS && millis() - resetButtonHeldSince < HOLD_RESET_MS + 1000) {
            pulseVibration(1000, 0, 1);
        } else if (millis() - resetButtonHeldSince >= HOLD_REBOOT_MS && millis() - resetButtonHeldSince < HOLD_REBOOT_MS + 250) {
            pulseVibration(250, 0, 1);
        }
    } else if (resetButtonHeldSince != 0) {
        if (millis() - resetButtonHeldSince >= HOLD_RESET_MS) {
            Serial.println("Factory reset triggered by long button hold");
            clearStoredWifiCredentials();
            deleteStoredSensorBiases();
            rp2040.reboot();
        } else if (millis() - resetButtonHeldSince >= HOLD_REBOOT_MS) {
            rp2040.reboot();
        } else {
            // send rezero command
            resetButtonHeldSince = 0;
        }
    }
}

void loop() {
    handleResetRezero();

    if (!processNetworking()) {
        return;
    }

    handleHapticCommandEnd();
    handleBatteryMeasurement();
    processIMU();
}
