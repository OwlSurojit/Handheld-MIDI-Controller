#pragma once

#include "ICM_20948.h"
#include <EEPROM.h>
#include <stdint.h>

// EEPROM layout
#define BIAS_EEPROM_SIZE 128
#define BIAS_EEPROM_ADDR 0

// How long to run before saving biases (ms). Give the DMP time to converge.
// Move the sensor through all orientations and do figure-8s during this window.
#define BIAS_SAVE_DELAY_MS (3UL * 60UL * 1000UL) // 3 minutes

struct biasStore {
    int32_t header     = 0x42;
    int32_t biasGyroX  = 0;
    int32_t biasGyroY  = 0;
    int32_t biasGyroZ  = 0;
    int32_t biasAccelX = 0;
    int32_t biasAccelY = 0;
    int32_t biasAccelZ = 0;
    int32_t sum        = 0;
};

// Call once in setup() before restoring biases.
void calibration_init();

// Inject previously saved biases into the DMP. Call after DMP is fully started.
void restoreBiasesFromFlash(ICM_20948 &icm);

// Read current DMP biases and write them to flash. Call after calibration has converged.
void saveBiasesToFlash(ICM_20948 &icm);
