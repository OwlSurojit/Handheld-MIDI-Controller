#include "imu_logic.h"

#include "ICM_20948.h"
#include "imu_calibration.h"
#include "imu_dmp.h"
#include "networking/communication.h"
#include "peripherals/vibration_motor_utils.h"
#include "peripherals/button_logic.h"
#include <Arduino.h>
#include <math.h>

constexpr uint8_t CS_PIN = 17;
constexpr uint8_t BATTERY_VOLTAGE_PIN = 28;

ICM_20948_SPI imu;
int packetCount = 0;
unsigned long lastPrintTime = millis();
unsigned long calibrationStartTime = millis();
bool biasesSaved = false;

SensorReading readSensorFrame() {
    // Read any DMP data waiting in the FIFO
    // Note:
    //    readDMPdataFromFIFO will return ICM_20948_Stat_FIFONoDataAvail if no data is available.
    //    If data is available, readDMPdataFromFIFO will attempt to read _one_ frame of DMP data.
    //    readDMPdataFromFIFO will return ICM_20948_Stat_FIFOIncompleteData if a frame was present but was incomplete
    //    readDMPdataFromFIFO will return ICM_20948_Stat_Ok if a valid frame was read.
    //    readDMPdataFromFIFO will return ICM_20948_Stat_FIFOMoreDataAvail if a valid frame was read _and_ the FIFO contains more (unread) data.
    
    icm_20948_DMP_data_t data;
    imu.readDMPdataFromFIFO(&data);

    if (imu.status != ICM_20948_Stat_Ok && imu.status != ICM_20948_Stat_FIFOMoreDataAvail) {
        return SensorReading{};
    }

    if ((data.header & DMP_header_bitmap_Quat6) == 0) {
        return SensorReading{};
    }

    // Q0 value is computed from this equation: Q0^2 + Q1^2 + Q2^2 + Q3^2 = 1.
    // The quaternion data is scaled by 2^30.
    double q1 = static_cast<double>(data.Quat6.Data.Q1) / 1073741824.0;
    double q2 = static_cast<double>(data.Quat6.Data.Q2) / 1073741824.0;
    double q3 = static_cast<double>(data.Quat6.Data.Q3) / 1073741824.0;
    double qSumSq = (q1 * q1) + (q2 * q2) + (q3 * q3);

    if (qSumSq > 1.0) {
        // This should never happen, but if it does, we can end up with NaNs. In that case, just skip this frame.
        Serial.printf("Invalid quaternion data: qSumSq = %f > 1.0\n", qSumSq);
        imu.resetFIFO();
        return SensorReading{};        
    }

    double q0 = sqrt(1.0 - qSumSq);

    float ax = 0.0f;
    float ay = 0.0f;
    float az = 0.0f;
    if ((data.header & DMP_header_bitmap_Accel) > 0) {
        // Raw accelerometer data (FSR ±8g, 4096 LSB/g)
        ax = static_cast<float>(data.Raw_Accel.Data.X) / 4096.0f;
        ay = static_cast<float>(data.Raw_Accel.Data.Y) / 4096.0f;
        az = static_cast<float>(data.Raw_Accel.Data.Z) / 4096.0f;
    }

    float gx = 0.0f;
    float gy = 0.0f;
    float gz = 0.0f;
    if ((data.header & DMP_header_bitmap_Gyro) > 0) {
        // Raw gyroscope data (FSR ±2000 dps, 16.384 LSB/(deg/s))
        gx = static_cast<float>(data.Raw_Gyro.Data.X) / 16.4f; // 16.384 is a pain, 16.4 is close enough
        gy = static_cast<float>(data.Raw_Gyro.Data.Y) / 16.4f;
        gz = static_cast<float>(data.Raw_Gyro.Data.Z) / 16.4f;
    }

    // Additionally check if the sustain button is pressed.
    // This should be here because it is part of the sensor data that needs to be converted to midi in real time

    SensorReading reading = {
        .timestamp = static_cast<uint32_t>(millis()),
        .qw = static_cast<float>(q0),
        .qx = static_cast<float>(q1),
        .qy = static_cast<float>(q2),
        .qz = static_cast<float>(q3),
        .ax = ax,
        .ay = ay,
        .az = az,
        .gx = gx,
        .gy = gy,
        .gz = gz,
        .sustainPressed = sustainButtonPressed()
    };

    return reading;
}

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

void processSensors() {
    SensorReading reading = readSensorFrame();
    if (reading.timestamp != 0) {
        sendSensorData(reading);

        packetCount++;
        if (millis() - lastPrintTime >= 1000) {
            Serial.print("Packets sent in the last second: ");
            Serial.println(packetCount);
            packetCount = 0;
            lastPrintTime = millis();
        }
    }
    
    if (!biasesSaved && millis() - calibrationStartTime >= BIAS_SAVE_DELAY_MS) {
        biasesSaved = true;
        saveBiasesToFlash(imu);
    }

    if (imu.status != ICM_20948_Stat_FIFOMoreDataAvail) {
        delay(10);
    }
}
