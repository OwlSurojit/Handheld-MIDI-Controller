#pragma once

#include <stdint.h>

void pulseVibration(uint16_t onMs, uint16_t offMs, uint8_t count);
void handleHapticCommand(uint32_t durationMs);
void handleHapticCommandEnd();