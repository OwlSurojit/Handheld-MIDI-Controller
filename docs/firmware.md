# Firmware Documentation — ICM-20948 Pico W MIDI Controller

## Overview

Reads orientation, accelerometer and gyroscope data from an ICM-20948 IMU via SPI, then streams it over Wi-Fi as Teleplot-format UDP packets to a host visualiser.

**Platform:** Raspberry Pi Pico W · **Framework:** Arduino (PlatformIO) · **Library:** SparkFun ICM-20948

---

## Hardware Setup

| Signal | Pico W pin |
|--------|-----------|
| SPI bus | default `SPI` |
| Chip Select | GP17 |
| Bus clock | default SPI clock |

I²C is also supported (disable `USE_SPI` and set `AD0_VAL`).

---

## DMP Configuration

The ICM-20948's on-chip **Digital Motion Processor (DMP)** does the heavy lifting.

### Sensor selection

Two DMP sensors are enabled simultaneously — their data lands in the same FIFO frame:

| Sensor | Data produced | ODR |
|--------|--------------|-----|
| `INV_ICM20948_SENSOR_LINEAR_ACCELERATION` | **Quat6** (6-axis gyro+accel fusion) + raw accel XYZ | max |
| `INV_ICM20948_SENSOR_RAW_GYROSCOPE` | Raw gyro XYZ | max |

Quat9 (9-axis, requires compass) was deliberately avoided — compass calibration adds complexity and degrades in magnetically noisy environments.

### Full-scale ranges

| Axis | FSR | Sensitivity |
|------|-----|------------|
| Accelerometer | ±8 g | 4096 LSB/g |
| Gyroscope | ±2000 dps | 16.4 LSB/(°/s) |

`initializeDMP()` hardcodes ±4 g (8192 LSB/g). This is overridden by calling `setFullScale()` then writing two DMP internal registers that govern the fixed-point scale factor used inside the DMP pipeline:

```cpp
const unsigned char accScale[4]  = {0x08, 0x00, 0x00, 0x00}; // ACC_SCALE  — Q-format normaliser
const unsigned char accScale2[4] = {0x00, 0x02, 0x00, 0x00}; // ACC_SCALE2 — output de-normaliser
myICM.writeDMPmems(ACC_SCALE,  4, &accScale[0]);
myICM.writeDMPmems(ACC_SCALE2, 4, &accScale2[0]);
```

Both values halve/double together when FSR doubles, preserving the DMP's internal 2³⁰ = 1 g convention. Omitting this step causes the DMP to output values doubled relative to the actual acceleration.

### Quaternion reconstruction

The DMP stores only Q1/Q2/Q3 (scaled by 2³⁰). Q0 is reconstructed as:

```cpp
double q0 = sqrt(1.0 - (q1*q1 + q2*q2 + q3*q3));
```

This is safe for unit quaternions and avoids transmitting a redundant field.

---

## FIFO Loop

```
readDMPdataFromFIFO()
  ├─ header & DMP_header_bitmap_Quat6  → quaternion + accel
  └─ header & DMP_header_bitmap_Gyro   → gyro
```

When `FIFOMoreDataAvail` is returned, the loop immediately re-reads without the 10 ms delay to prevent FIFO overflow.

---

## UDP Packet Format

Teleplot wire format — one `key:value|unit` pair per line, 256-byte fixed buffer:

```
quat_w:+0.998712|g
quat_x:+0.012345|g
quat_y:-0.034567|g
quat_z:+0.005678|g
accel_x:0.0123|g
accel_y:-0.9876|g
accel_z:0.0045|g
gyro_x:12.34|g
gyro_y:-5.67|g
gyro_z:0.89|g
```

**Port:** 47269 (both local and remote).

---

## Calibration (`imu_calibration.h/.cpp`)

Gyro and accel biases are persisted to Pico flash via the Arduino `EEPROM` emulation layer.

### Struct layout (32 bytes in EEPROM at address 0)

```cpp
struct biasStore {
    int32_t header;      // magic = 0x42
    int32_t biasGyroX/Y/Z;
    int32_t biasAccelX/Y/Z;
    int32_t sum;         // simple checksum (sum of all other fields)
};
```

Compass biases were explicitly removed — compass fusion is not used.

### Lifecycle

1. **`calibration_init()`** — called first in `setup()`, allocates EEPROM.
2. **`restoreBiasesFromFlash()`** — called after DMP init; injects saved biases via `setBiasGyroX/Y/Z` etc. Validates header magic and checksum before applying.
3. **`saveBiasesToFlash()`** — called once after `BIAS_SAVE_DELAY_MS` (3 minutes). The delay gives the DMP time to converge its internal calibration estimator. Only happens once per power cycle.

---

## Wi-Fi

`connectWiFi()` blocks in `setup()` until connection. UDP socket opened on the same port immediately after. No reconnection logic — intended for a fixed home-network deployment.
