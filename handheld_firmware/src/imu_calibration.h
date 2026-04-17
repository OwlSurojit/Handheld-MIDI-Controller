#pragma once

#include "ICM_20948.h"
#include "eeprom_layout.h"
#include <stddef.h>
#include <stdint.h>


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

// Inject previously saved biases into the DMP. Call after DMP is fully started.
void restoreBiasesFromFlash(ICM_20948 &icm);

// Read current DMP biases and write them to flash. Call after calibration has converged.
void saveBiasesToFlash(ICM_20948 &icm);

// Delete any saved biases from flash. Call before rebooting if you want to clear saved calibration.
void deleteStoredBiases();
