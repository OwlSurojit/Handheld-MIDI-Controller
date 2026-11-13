#include "button_logic.h"
#include "consts.h"
#include "imu/imu_calibration.h"
#include "imu/imu_logic.h"
#include "led_ring_utils.h"
#include "networking/communication.h"
#include "networking/wifi_credentials_store.h"
#include "vibration_motor_utils.h"
#include <Arduino.h>

enum ModeSwitchState {
    MODE_SWITCH_HIT,
    MODE_SWITCH_BOTH,
    MODE_SWITCH_MAP
};

ModeSwitchState currentModeSwitchState = MODE_SWITCH_HIT;

void setupButtons() {
    pinMode(RESET_REZERO_BUTTON_PIN, INPUT_PULLUP);
    pinMode(SUS_BUTTON_PIN, INPUT_PULLUP);
    pinMode(HIT_MODE_SWITCH_PIN, INPUT_PULLUP);
    pinMode(BOTH_MODE_SWITCH_PIN, INPUT_PULLUP);
    pinMode(MAP_MODE_SWITCH_PIN, INPUT_PULLUP);
}

unsigned long rezeroButtonHeldSince = 0;
unsigned long resetButtonsHeldSince = 0;
bool resetVibrationStarted = false;
bool rebootVibrationStarted = false;

void handleResetRezero() {
    if (digitalRead(RESET_REZERO_BUTTON_PIN) == LOW) {
        if (rezeroButtonHeldSince == 0) {
            rezeroButtonHeldSince = millis();
        }
        if (sustainButtonPressed()) {
            if (resetButtonsHeldSince == 0) {
                resetButtonsHeldSince = millis();
            } else if (millis() - resetButtonsHeldSince >= HOLD_RESET_MS &&
                       millis() - resetButtonsHeldSince < HOLD_RESET_MS + 1000 &&
                       !resetVibrationStarted) {
                vibrateFor(1000);
                resetVibrationStarted = true;
            } else if (millis() - resetButtonsHeldSince >= HOLD_REBOOT_MS &&
                       millis() - resetButtonsHeldSince < HOLD_REBOOT_MS + 250 &&
                       !rebootVibrationStarted) {
                vibrateFor(250);
                rebootVibrationStarted = true;
            }
        }
    } else {
        if (resetButtonsHeldSince != 0) {
            if (millis() - resetButtonsHeldSince >= HOLD_RESET_MS) {
                Serial.println("Factory reset triggered by long button hold");
                wifiCredentialsClear();
                deleteStoredBiases();
                rp2040.reboot();
            } else if (millis() - resetButtonsHeldSince >= HOLD_REBOOT_MS) {
                rp2040.reboot();
            } else {
                resetButtonsHeldSince = 0;
                resetVibrationStarted = false;
                rebootVibrationStarted = false;
            }
        }
        if (rezeroButtonHeldSince != 0) {
            if (sendRezeroCommand()) {
                pulseVibration(150, 0, 1);
                flashLedRing(255, 0, 255, 1000);
                Serial.println("Rezero command sent successfully");
            }
            rezeroButtonHeldSince = 0;
        }
    }
}

void handleModeSwitch() {
    ModeSwitchState newState;
    if (digitalRead(HIT_MODE_SWITCH_PIN) == LOW) {
        newState = MODE_SWITCH_HIT;
    } else if (digitalRead(BOTH_MODE_SWITCH_PIN) == LOW) {
        newState = MODE_SWITCH_BOTH;
    } else if (digitalRead(MAP_MODE_SWITCH_PIN) == LOW) {
        newState = MODE_SWITCH_MAP;
    }
    if (newState != currentModeSwitchState) {
        currentModeSwitchState = newState;
        Serial.print("Mode switch state changed to: ");
        switch (currentModeSwitchState) {
        case MODE_SWITCH_HIT:
            Serial.println("HIT");
            break;
        case MODE_SWITCH_BOTH:
            Serial.println("BOTH");
            break;
        case MODE_SWITCH_MAP:
            Serial.println("MAP");
            break;
        }
        sendModeSwitchState(static_cast<uint8_t>(currentModeSwitchState));
    }
}

void handleButtons() {
    handleResetRezero();
    handleModeSwitch();
}

bool sustainButtonPressed() {
    return digitalRead(SUS_BUTTON_PIN) == LOW;
}