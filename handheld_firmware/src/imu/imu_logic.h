#pragma once

#include <stdint.h>

struct SensorReading {
    uint32_t timestamp;
    float qw;
    float qx;
    float qy;
    float qz;
    float ax;
    float ay;
    float az;
    float gx;
    float gy;
    float gz;
    bool sustainPressed;
};

SensorReading readSensorFrame();
void initializeIMU();
void processSensors();
