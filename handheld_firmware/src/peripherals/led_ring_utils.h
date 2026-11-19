#pragma once

#include <stdint.h>

void setupLedRing();
void updateLedRing();
void blinkLedRing(uint8_t r, uint8_t g, uint8_t b, uint16_t onMs, uint16_t offMs);
void setLedRingColor(uint8_t r, uint8_t g, uint8_t b);
void setLedRingAngle(uint8_t r, uint8_t g, uint8_t b, float angleDegrees);
void flashLedRing(uint8_t r, uint8_t g, uint8_t b, uint16_t durationMs);
void ledRingCarousel(uint8_t r, uint8_t g, uint8_t b, uint16_t durationMsPerLed, uint8_t rounds);
void ledRingSmoothCarousel(uint8_t r, uint8_t g, uint8_t b, float angleIncrease, uint8_t rounds);
