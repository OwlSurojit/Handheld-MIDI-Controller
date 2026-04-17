#pragma once

#include <EEPROM.h>

#define EEPROM_TOTAL_SIZE 1024
#define BIAS_EEPROM_ADDR 0
#define BIAS_EEPROM_SIZE 128
#define WIFI_CREDENTIAL_EEPROM_ADDR 256

// Call once in setup() before restoring biases.
void eeprom_init();