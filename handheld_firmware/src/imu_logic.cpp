#include "imu_logic.h"

#include "ICM_20948.h"
#include "imu_calibration.h"
#include "imu_dmp.h"
#include "networking.h"
#include "vibration_motor_utils.h"
#include <Arduino.h>
#include <math.h>

namespace {
constexpr uint8_t CS_PIN = 17;
constexpr uint8_t BATTERY_VOLTAGE_PIN = 28;

ICM_20948_SPI imu;
int packetCount = 0;
unsigned long lastPrintTime = millis();
unsigned long calibrationStartTime = millis();
bool biasesSaved = false;

void readSensorFrame() {
    icm_20948_DMP_data_t data;
    imu.readDMPdataFromFIFO(&data);

    if (imu.status != ICM_20948_Stat_Ok && imu.status != ICM_20948_Stat_FIFOMoreDataAvail) {
        return;
    }

    if ((data.header & DMP_header_bitmap_Quat6) == 0) {
        return;
    }

    double q1 = static_cast<double>(data.Quat6.Data.Q1) / 1073741824.0;
    double q2 = static_cast<double>(data.Quat6.Data.Q2) / 1073741824.0;
    double q3 = static_cast<double>(data.Quat6.Data.Q3) / 1073741824.0;
    double qSumSq = (q1 * q1) + (q2 * q2) + (q3 * q3);

    if (qSumSq > 1.0) {
        Serial.println("Invalid quaternion data: qSumSq > 1.0");
        imu.resetFIFO();
        return;
    }

    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;
    if ((data.header & DMP_header_bitmap_Accel) > 0) {
        ax = static_cast<float>(data.Raw_Accel.Data.X) / 4096.0f;
        ay = static_cast<float>(data.Raw_Accel.Data.Y) / 4096.0f;
        az = static_cast<float>(data.Raw_Accel.Data.Z) / 4096.0f;
    }

    float gx = 0.0f;
    float gy = 0.0f;
    float gz = 0.0f;
    if ((data.header & DMP_header_bitmap_Gyro) > 0) {
        gx = static_cast<float>(data.Raw_Gyro.Data.X) / 16.4f;
        gy = static_cast<float>(data.Raw_Gyro.Data.Y) / 16.4f;
        gz = static_cast<float>(data.Raw_Gyro.Data.Z) / 16.4f;
    }

    IMUReading reading = {
        .timestamp = static_cast<uint32_t>(millis()),
        .qw = static_cast<float>(sqrt(1.0 - qSumSq)),
        .qx = static_cast<float>(q1),
        .qy = static_cast<float>(q2),
        .qz = static_cast<float>(q3),
        .ax = ax,
        .ay = ay,
        .az = az,
        .gx = gx,
        .gy = gy,
        .gz = gz};
    sendSensorData(reading);

    packetCount++;
    if (millis() - lastPrintTime >= 1000) {
        Serial.print("Packets sent in the last second: ");
        Serial.println(packetCount);
        packetCount = 0;
        lastPrintTime = millis();
    }
}
} // namespace

void initializeIMU() {
    SPI.begin();

    bool initialized = false;
    while (!initialized) {
        imu.begin(CS_PIN, SPI);
        if (imu.status != ICM_20948_Stat_Ok) {
            delay(500);
        } else {
            initialized = true;
        }
    }

    if (!configureRuntimeDmp(imu)) {
        pulseVibration(100, 50, 5);
        rp2040.reboot();
    }

    calibrationStartTime = millis();
}

void processIMU() {
    analogRead(BATTERY_VOLTAGE_PIN);
    readSensorFrame();

    if (!biasesSaved && millis() - calibrationStartTime >= BIAS_SAVE_DELAY_MS) {
        biasesSaved = true;
        saveBiasesToFlash(imu);
    }

    if (imu.status != ICM_20948_Stat_FIFOMoreDataAvail) {
        delay(10);
    }
}
