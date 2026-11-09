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
        default:
            break;
    }
}