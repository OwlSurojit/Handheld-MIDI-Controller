#include "vibration_motor_utils.h"
#include "consts.h"
#include <Arduino.h>

enum VibrationState {
    OFF,
    ON,
    PULSING,
};

VibrationState vibrationState = OFF;
unsigned long hapticCommandEndTime = 0;

struct VibrationPattern {
    bool motorOn;
    uint16_t onDuration;
    uint16_t offDuration;
    uint8_t remainingPulses;
    unsigned long phaseStartedAt;
} vibrationPattern = {};

void pulseVibration(uint16_t onMs, uint16_t offMs, uint8_t count) {
    if (count == 0) {
        return;
    }

    vibrationState = PULSING;
    digitalWrite(HAPTIC_MOTOR_PIN, HIGH);
    vibrationPattern.motorOn = true;
    vibrationPattern.onDuration = onMs;
    vibrationPattern.offDuration = offMs;
    vibrationPattern.remainingPulses = count;
    vibrationPattern.phaseStartedAt = millis();
}

void updateVibration() {
    switch (vibrationState) {
        case OFF:
            return;
        case ON:
            if (millis() >= hapticCommandEndTime) {
                digitalWrite(HAPTIC_MOTOR_PIN, LOW);
                vibrationState = OFF;
            }
            return;
        case PULSING:
            if (millis() - vibrationPattern.phaseStartedAt <
                    (vibrationPattern.motorOn ? vibrationPattern.onDuration : vibrationPattern.offDuration)) {
                return;
            }
            if (vibrationPattern.motorOn) {
                digitalWrite(HAPTIC_MOTOR_PIN, LOW);
                vibrationPattern.motorOn = false;
                vibrationPattern.phaseStartedAt = millis();
                --vibrationPattern.remainingPulses;
                if (vibrationPattern.remainingPulses == 0) {
                    vibrationState = OFF;
                }
            } else {
                digitalWrite(HAPTIC_MOTOR_PIN, HIGH);
                vibrationPattern.motorOn = true;
                vibrationPattern.phaseStartedAt = millis();
            }
    }
}

void vibrateFor(uint32_t durationMs) {
    vibrationState = ON;
    digitalWrite(HAPTIC_MOTOR_PIN, HIGH);
    hapticCommandEndTime = millis() + durationMs;
}