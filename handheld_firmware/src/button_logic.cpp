#include "button_logic.h"
#include "consts.h"
#include "networking.h"
#include "vibration_motor_utils.h"
#include "imu_calibration.h"
#include "wifi_credentials_store.h"
#include "imu_logic.h"
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
            wifiCredentialsClear();
            deleteStoredBiases();
            rp2040.reboot();
        } else if (millis() - resetButtonHeldSince >= HOLD_REBOOT_MS) {
            rp2040.reboot();
        } else {
            sendRezeroCommand();
            Serial.println("Rezero command sent successfully");
            resetButtonHeldSince = 0;
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