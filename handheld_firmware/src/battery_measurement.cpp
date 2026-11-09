#include "battery_measurement.h"
#include "consts.h"
#include "networking/communication.h"
#include <Arduino.h>

const float MAX_BATTERY_VOLTAGE = 4.2;
const float MIN_BATTERY_VOLTAGE = 3.3;

const int SAMPLES_PER_READING = 50;

unsigned long lastBatteryMeasurementTime = 0;

void setupBatteryMeasurement() {
    pinMode(BATTERY_MEASUREMENT_PIN, INPUT);
}

void handleBatteryMeasurement() {
    unsigned long currentTime = millis();
    if (currentTime - lastBatteryMeasurementTime >= BATTERY_MEASUREMENT_INTERVAL_MS) { // Measure every second
        // Average multiple readings to reduce noise
        float totalVoltage = 0;
        for (int i = 0; i < SAMPLES_PER_READING; i++) {
            int rawValue = analogRead(BATTERY_MEASUREMENT_PIN);
            totalVoltage += (rawValue / 1023.0) * 3.3 * 2; // Assuming a voltage divider with equal resistors
        }
        float voltage = totalVoltage / SAMPLES_PER_READING;

        uint8_t percentage = (voltage - MIN_BATTERY_VOLTAGE) / (MAX_BATTERY_VOLTAGE - MIN_BATTERY_VOLTAGE) * 100;

        Serial.printf("Battery: %.2fV (%d%%)\n", voltage, percentage);
        sendBatteryMeasurement(percentage);
        lastBatteryMeasurementTime = currentTime;
    }
}