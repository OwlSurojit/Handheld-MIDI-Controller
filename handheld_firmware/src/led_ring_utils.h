#pragma once

#include <stdint.h>

void setupLedRing();
void updateLedRing();
void blinkLedRing(uint8_t r, uint8_t g, uint8_t b, uint16_t onMs, uint16_t offMs);
void setLedRingColor(uint8_t r, uint8_t g, uint8_t b);
void flashLedRing(uint8_t r, uint8_t g, uint8_t b, uint16_t durationMs);