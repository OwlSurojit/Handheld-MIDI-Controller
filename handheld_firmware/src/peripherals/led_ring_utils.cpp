#include "consts.h"
#include "led_ring_utils.h"
#include <Adafruit_NeoPixel.h>
#include <stdint.h>

Adafruit_NeoPixel ledRing(
    NUMLEDS,
    LED_RING_PIN,
    NEO_GRB + NEO_KHZ800
);

enum LedRingState {
    ON,
    OFF,
    BLINKING_ON,
    BLINKING_OFF,
    FLASHING,
    CAROUSEL,
    SMOOTH_CAROUSEL
};

struct BlinkState {
    uint32_t color;
    uint16_t onDuration;
    uint16_t offDuration;
    uint32_t lastChangeTime;
} blinkState;

struct FlashState {
    uint8_t r;
    uint8_t g;
    uint8_t b;
    uint16_t duration;
    uint32_t endTime;
} flashState;

struct CarouselState {
    uint32_t color;
    uint8_t remainingRounds;
    uint8_t currentLed;
    uint16_t durationPerLed;
    uint32_t lastChangeTime;
} carouselState;

struct SmoothCarouselState {
    uint32_t color;
    uint8_t remainingRounds;
    float currentAngle;
    float angleIncrease;
} smoothCarouselState;

LedRingState curState = OFF;

void setupLedRing() {
    ledRing.begin();
    ledRing.clear();
    ledRing.show();
}

void fillLedRing(uint32_t color) {
    ledRing.fill(color, 0, NUMLEDS);
    ledRing.show();
}

void fillLedRing(uint8_t r, uint8_t g, uint8_t b) {
    fillLedRing(ledRing.Color(r, g, b));
}

void clearLedRing() {
    ledRing.clear();
    ledRing.show();
}

void blinkLedRing(uint8_t r, uint8_t g, uint8_t b, uint16_t onMs, uint16_t offMs) {
    fillLedRing(r, g, b);
    curState = BLINKING_ON;
    blinkState = {
        .color = ledRing.Color(r, g, b),
        .onDuration = onMs,
        .offDuration = offMs,
        .lastChangeTime = millis()
    };
}

void setLedRingColor(uint8_t r, uint8_t g, uint8_t b) {
    fillLedRing(r, g, b);
    curState = ON;
}

void flashLedRing(uint8_t r, uint8_t g, uint8_t b, uint16_t durationMs) {
    fillLedRing(r, g, b);
    flashState = {
        .r = r,
        .g = g,
        .b = b,
        .duration = durationMs,
        .endTime = millis() + durationMs
    };
    curState = FLASHING;
}

void ledRingCarousel(uint8_t r, uint8_t g, uint8_t b, uint16_t durationMsPerLed, uint8_t rounds) {
    clearLedRing();

    ledRing.setPixelColor(0, ledRing.Color(r, g, b));
    ledRing.show();

    carouselState = {
        .color = ledRing.Color(r, g, b),
        .remainingRounds = rounds,
        .currentLed = 0,
        .durationPerLed = durationMsPerLed,
        .lastChangeTime = millis()
    };
    curState = CAROUSEL;
}

void ledRingSmoothCarousel(uint8_t r, uint8_t g, uint8_t b, float angleIncrease, uint8_t rounds) {
    clearLedRing();

    smoothCarouselState = {
        .color = ledRing.Color(r, g, b),
        .remainingRounds = rounds,
        .currentAngle = 0.0f,
        .angleIncrease = angleIncrease
    };
    curState = SMOOTH_CAROUSEL;
}

constexpr float angleDist(float a, float b) {
    // returns the distance from a to b (range [-180, 180]) in mathematically positive direction (counter-clockwise)
    return fmodf(b - a + 360.0f, 360.0f);
}

struct LEDAngleRange {
    float min;
    float max;
    constexpr float halfRange() const {
        return angleDist(min, max) / 2.0f;
    }

    float getIntensity(float angle) const {
        if (angleDist(min, angle) <= halfRange()) {
            return angleDist(min, angle) / halfRange();
        } else if (angleDist(angle, max) <= halfRange()) {
            return angleDist(angle, max) / halfRange();
        } else {
            return 0.0f;
        }
    }
};

LEDAngleRange ledAngleRanges[NUMLEDS] = {
    {45.0f, -120.0f},
    {-45.0f, 120.0f},
    {-120.0f, 45.0f},
    {120.0f, -45.0f},
};

// LEDAngleRange ledAngleRanges[NUMLEDS] = {
//     {90, 180},
//     {0, 90},
//     {-90, 0},
//     {-180, -90}
// };

void setLedRingAngle(uint8_t r, uint8_t g, uint8_t b, float angleDegrees) {
    clearLedRing();

    // Scale angleDegrees to [-180, 180]
    if (angleDegrees > 180.0f) {
        angleDegrees -= 360.0f;
    } else if (angleDegrees < -180.0f) {
        angleDegrees += 360.0f;
    }

    for (uint8_t i = 0; i < NUMLEDS; ++i) {
        float intensity = ledAngleRanges[i].getIntensity(angleDegrees);
        ledRing.setPixelColor(i, ledRing.Color(r * intensity, g * intensity, b * intensity));
    }
    ledRing.show();
}

void setLedRingAngle(uint32_t color, float angleDegrees) {
    setLedRingAngle(
        (color >> 16) & 0xFF,
        (color >> 8) & 0xFF,
        color & 0xFF,
        angleDegrees
    );
}

void updateLedRing() {
    switch (curState) {
        case BLINKING_ON:
            if (millis() - blinkState.lastChangeTime >= blinkState.onDuration) {
                clearLedRing();
                curState = BLINKING_OFF;
                blinkState.lastChangeTime = millis();
            }
            break;
        case BLINKING_OFF:
            if (millis() - blinkState.lastChangeTime >= blinkState.offDuration) {
                fillLedRing(blinkState.color);
                curState = BLINKING_ON;
                blinkState.lastChangeTime = millis();
            }
            break;
        case FLASHING: {
            int32_t remaining = flashState.endTime - millis();
            if (remaining <= 0) {
                clearLedRing();
                curState = OFF;
            } else {
                // Calculate a fading color based on the elapsed time
                fillLedRing(
                    (flashState.r * remaining) / flashState.duration,
                    (flashState.g * remaining) / flashState.duration,
                    (flashState.b * remaining) / flashState.duration
                );
            }
            break;
        }
        case CAROUSEL: {
            if (millis() - carouselState.lastChangeTime >= carouselState.durationPerLed) {
                // Turn off the current LED
                ledRing.setPixelColor(carouselState.currentLed, 0);
                carouselState.currentLed = (carouselState.currentLed + 1) % NUMLEDS;
                // Turn on the next LED
                ledRing.setPixelColor(carouselState.currentLed, carouselState.color);
                ledRing.show();
                carouselState.lastChangeTime = millis();
                carouselState.remainingRounds -= (carouselState.currentLed == 0) ? 1 : 0;
                if (carouselState.remainingRounds == 0) {
                    clearLedRing();
                    curState = OFF;
                }
            }
            break;
        }
        case SMOOTH_CAROUSEL: {
            setLedRingAngle(smoothCarouselState.color, smoothCarouselState.currentAngle);
            smoothCarouselState.currentAngle += smoothCarouselState.angleIncrease;
            if (smoothCarouselState.currentAngle >= 180.0f) {
                smoothCarouselState.currentAngle -= 360.0f;
                smoothCarouselState.remainingRounds--;
                if (smoothCarouselState.remainingRounds == 0) {
                    clearLedRing();
                    curState = OFF;
                }
            }

            break;
        }   
        default:
            break;
    }
}