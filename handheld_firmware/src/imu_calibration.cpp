#include "imu_calibration.h"
#include <Arduino.h>

static void updateBiasStoreSum(biasStore *s) {
    s->sum = s->header
           + s->biasGyroX  + s->biasGyroY  + s->biasGyroZ
           + s->biasAccelX + s->biasAccelY + s->biasAccelZ;
}

static bool isBiasStoreValid(const biasStore *s) {
    if (s->header != 0x42) return false;
    int32_t sum = s->header
                + s->biasGyroX  + s->biasGyroY  + s->biasGyroZ
                + s->biasAccelX + s->biasAccelY + s->biasAccelZ;
    return (s->sum == sum);
}

static bool readBiasesFromDMP(ICM_20948 &icm, biasStore *s) {
    bool ok = (icm.getBiasGyroX(&s->biasGyroX)   == ICM_20948_Stat_Ok);
    ok &=     (icm.getBiasGyroY(&s->biasGyroY)   == ICM_20948_Stat_Ok);
    ok &=     (icm.getBiasGyroZ(&s->biasGyroZ)   == ICM_20948_Stat_Ok);
    ok &=     (icm.getBiasAccelX(&s->biasAccelX) == ICM_20948_Stat_Ok);
    ok &=     (icm.getBiasAccelY(&s->biasAccelY) == ICM_20948_Stat_Ok);
    ok &=     (icm.getBiasAccelZ(&s->biasAccelZ) == ICM_20948_Stat_Ok);
    return ok;
}

void restoreBiasesFromFlash(ICM_20948 &icm) {
    biasStore s;
    EEPROM.get(BIAS_EEPROM_ADDR, s);
    if (!isBiasStoreValid(&s)) {
        Serial.println("No valid calibration data in flash.");
        return;
    }
    bool ok = (icm.setBiasGyroX(s.biasGyroX)   == ICM_20948_Stat_Ok);
    ok &=     (icm.setBiasGyroY(s.biasGyroY)   == ICM_20948_Stat_Ok);
    ok &=     (icm.setBiasGyroZ(s.biasGyroZ)   == ICM_20948_Stat_Ok);
    ok &=     (icm.setBiasAccelX(s.biasAccelX) == ICM_20948_Stat_Ok);
    ok &=     (icm.setBiasAccelY(s.biasAccelY) == ICM_20948_Stat_Ok);
    ok &=     (icm.setBiasAccelZ(s.biasAccelZ) == ICM_20948_Stat_Ok);
    Serial.println(ok ? "Calibration biases restored from flash." : "Bias restore failed!");
}

void saveBiasesToFlash(ICM_20948 &icm) {
    biasStore s;
    if (!readBiasesFromDMP(icm, &s)) {
        Serial.println("Bias read failed, not saving.");
        return;
    }
    updateBiasStoreSum(&s);
    EEPROM.put(BIAS_EEPROM_ADDR, s);
    EEPROM.commit();
    Serial.println("Calibration biases saved to flash.");
}

void deleteStoredBiases() {
    biasStore s; // Initialized to all zeros, which is invalid
    EEPROM.put(BIAS_EEPROM_ADDR, s);
    EEPROM.commit();
    Serial.println("Stored calibration biases deleted from flash.");
}