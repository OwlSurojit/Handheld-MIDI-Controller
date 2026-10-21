#include "vibration_motor_utils.h"
#include "consts.h"
#include <Arduino.h>

void pulseVibration(uint16_t onMs, uint16_t offMs, uint8_t count) {
    for (uint8_t i = 0; i < count; ++i) {
        digitalWrite(HAPTIC_MOTOR_PIN, HIGH);
        delay(onMs);
        digitalWrite(HAPTIC_MOTOR_PIN, LOW);
        if (i + 1 < count) {
            delay(offMs);
        }
    }
}

bool hapticActive = false;
unsigned long hapticCommandEndTime = 0;

void handleHapticCommand(uint32_t durationMs) {
    digitalWrite(HAPTIC_MOTOR_PIN, HIGH);
    hapticCommandEndTime = millis() + durationMs;
    hapticActive = true;
}

void handleHapticCommandEnd() {
    if (hapticActive && millis() >= hapticCommandEndTime) {
        Serial.println("Haptic command duration ended, turning off haptic motor");
        digitalWrite(HAPTIC_MOTOR_PIN, LOW);
        hapticActive = false;
    }
}