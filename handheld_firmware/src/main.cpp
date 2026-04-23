/****************************************************************
 * Firmware for the handheld MIDI controller.
 * Developed by Adrian Surojit Müller for Yens&Yens in April 2026.
 * 
 * Based on original code by:
 * Paul Clark, April 25th, 2021
 * which was based on code by Owen Lyke @ SparkFun Electronics
 * Original Creation Date: April 17 2019
 *
 * Distributed as-is; no warranty is given.
 ***************************************************************/

#include "ICM_20948.h" // Click here to get the library: http://librarymanager/All#SparkFun_ICM_20948_IMU
#include "EEPROM.h"
#include "imu_dmp.h"
#include "imu_calibration.h"
#include "wifi_credentials_store.h"
#include "provisioning.h"
#include <WiFi.h>
#include <WiFiUdp.h>
#include <string.h>

#define USE_SPI

#define SPI_PORT SPI // Your desired SPI port.       
#define CS_PIN 17    // Which pin you connect CS to. 

// The value of the last bit of the I2C address.
// On the SparkFun 9DoF IMU breakout the default is 1, and when the ADR jumper is closed the value becomes 0
#define AD0_VAL 1

#define BUTTON_PIN 0
#define HAPTIC_MOTOR_PIN 2
#define HOLD_REBOOT_MS 5000
#define HOLD_RESET_MS 10000

// Wi-Fi and UDP settings
uint8_t MAC_ADDR[6];
IPAddress UDP_BROADCAST_IP(255, 255, 255, 255); // Broadcast address for discovery
IPAddress SERVER_IP(0, 0, 0, 0);                // Server IP (set after discovery)
bool discovered = false;                        // Whether we've discovered the server
const uint16_t UDP_REMOTE_PORT = 5005;          // Receiver UDP port
const uint16_t UDP_LOCAL_PORT = 5005;           // Local UDP port on the Pico W

const ProvisioningSettings PROVISIONING_SETTINGS = {
    .udpRemotePort = UDP_REMOTE_PORT,
    .udpLocalPort = UDP_LOCAL_PORT,
    .wifiConnectTimeoutMs = 20000,
    .forceApHoldMs = 3000,
    .apPass = "",
    .wifiAuthOpen = 0x00,
    .wifiAuthWpa2Psk = 0x01,
    .ackOk = 0x00,
    .ackInvalidPayload = 0x01,
    .ackWriteFailed = 0x02,
    .ackWrongTarget = 0x03,
};

WiFiUDP udp;

// Packet type constants
enum PacketType : uint8_t {
    DISCOVERY_REQUEST = 0x01,  // Controller sends to broadcast
    DISCOVERY_RESPONSE = 0x02, // Server responds with its IP
    SENSOR_DATA = 0x03,        // Normal sensor data
    HAPTIC_FEEDBACK = 0x04,    // Haptic feedback command
    IDENTIFY_REQUEST = 0x05,   // Host triggers a short identify vibration
    LATENCY_CHECK = 0xFF       // Latency test echo packet
};

// Discovery request packet
struct __attribute__((packed)) DiscoveryRequestPacket {
    uint8_t type; // DISCOVERY_REQUEST
    uint8_t mac[6];
};

// Discovery response packet: simple type byte response
struct __attribute__((packed)) DiscoveryResponsePacket {
    uint8_t type; // DISCOVERY_RESPONSE
};

// Per-controller firmware ID, timestamp, and sensor data
struct __attribute__((packed)) SensorDataPacket {
    uint8_t type; // SENSOR_DATA
    uint8_t mac[6];
    uint32_t ts;
    float qw, qx, qy, qz;
    float ax, ay, az;
    float gx, gy, gz;
};

struct __attribute__((packed)) HapticFeedbackPacket {
    uint8_t type;         // HAPTIC_FEEDBACK
    uint8_t command;      // Simple command byte to indicate haptic pattern
    uint32_t duration_ms; // Duration for the haptic feedback
};

struct __attribute__((packed)) IdentifyRequestPacket {
    uint8_t type; // IDENTIFY_REQUEST
};

// Small latency check packet for echo-back latency measurement
struct __attribute__((packed)) LatencyPacket {
    uint8_t type; // LATENCY_CHECK
    uint8_t mac[6];
    uint32_t ts; // Local milliseconds when sent
};


ICM_20948_SPI myICM;

int unsuccessfulPacketSends = 0;
const int MAX_UNSUCCESSFUL_SENDS = 100;

void sendUdpPacket(const uint8_t *packet, size_t size, IPAddress target_ip = IPAddress(255, 255, 255, 255)) {
    udp.beginPacket(target_ip, UDP_REMOTE_PORT);
    udp.write(packet, size);
    if (udp.endPacket()) {
        unsuccessfulPacketSends = 0;
    } else if (++unsuccessfulPacketSends > MAX_UNSUCCESSFUL_SENDS) {
        Serial.println("Too many unsuccessful packet sends, resetting...");
        rp2040.reboot();
    }
}

void pulseHaptic(uint16_t onMs, uint16_t offMs, uint8_t count) {
    for (uint8_t i = 0; i < count; ++i) {
        digitalWrite(HAPTIC_MOTOR_PIN, HIGH);
        delay(onMs);
        digitalWrite(HAPTIC_MOTOR_PIN, LOW);
        if (i + 1 < count) {
            delay(offMs);
        }
    }
}

void eeprom_init() {
    EEPROM.begin(EEPROM_TOTAL_SIZE);
}

void setup() {
    Serial.begin(115200);
    delay(100);

    eeprom_init();

    pinMode(BUTTON_PIN, INPUT_PULLUP);
    pinMode(HAPTIC_MOTOR_PIN, OUTPUT);
    digitalWrite(HAPTIC_MOTOR_PIN, LOW);

    WiFi.mode(WIFI_STA);
    WiFi.macAddress(MAC_ADDR);

    if (isProvisioningButtonHeldOnBoot(BUTTON_PIN, PROVISIONING_SETTINGS.forceApHoldMs)) {
        Serial.println("Boot button hold detected. Wiping saved Wi-Fi credentials.");
        wifiCredentialsClear();
        enterProvisioningAPMode(udp, MAC_ADDR, PROVISIONING_SETTINGS, true, pulseHaptic);
    }

    while (!connectFromStoredCredentials(PROVISIONING_SETTINGS)) {
        Serial.println("Unable to connect using saved credentials. Entering AP provisioning mode.");
        enterProvisioningAPMode(udp, MAC_ADDR, PROVISIONING_SETTINGS, false, pulseHaptic);
    }

    WiFi.macAddress(MAC_ADDR);
    udp.begin(UDP_LOCAL_PORT);
    Serial.println("WiFi connected");

    pulseHaptic(80, 60, 1);

    SPI_PORT.begin();

    bool initialized = false;
    while (!initialized) {

        // Initialize the ICM-20948
        // If the DMP is enabled, .begin performs a minimal startup. We need to configure the sample mode etc. manually.
        myICM.begin(CS_PIN, SPI_PORT);

        if (myICM.status != ICM_20948_Stat_Ok) {
            delay(500);
        } else {
            initialized = true;
        }
    }

    if (!configureRuntimeDmp(myICM)) {
        pulseHaptic(100, 50, 5);
        rp2040.reboot();
    }
}

int packetCount = 0;
unsigned long lastPrintTime = millis();
unsigned long lastDiscoveryTime = millis();

void handleDiscoveryResponse() {
    // Check if there's a discovery response waiting
    int packetSize = udp.parsePacket();
    if (packetSize == sizeof(DiscoveryResponsePacket)) {
        DiscoveryResponsePacket resp;
        udp.read((uint8_t *)&resp, sizeof(DiscoveryResponsePacket));

        if (resp.type == DISCOVERY_RESPONSE) {
            SERVER_IP = udp.remoteIP(); // Extract IP from the UDP packet source
            discovered = true;
            Serial.print("Server discovered at: ");
            Serial.println(SERVER_IP);
        }
    }
}

void handleLatencyPing() {
    LatencyPacket ping;
    udp.read((uint8_t *)&ping, sizeof(LatencyPacket));

    if (ping.type == LATENCY_CHECK && memcmp(ping.mac, MAC_ADDR, 6) == 0) {
        // Echo the packet back unchanged so the server can measure round-trip time.
        sendUdpPacket((const uint8_t *)&ping, sizeof(LatencyPacket), SERVER_IP);
    }
}

bool hapticActive = false;
unsigned long hapticCommandEndTime = 0;

void handleHapticFeedback() {
    Serial.println("Received haptic feedback command");
    HapticFeedbackPacket hapticPacket;
    udp.read((uint8_t *)&hapticPacket, sizeof(HapticFeedbackPacket));

    if (hapticPacket.command == 0x01) { // Simple command to trigger haptic feedback
        digitalWrite(HAPTIC_MOTOR_PIN, HIGH);
        hapticCommandEndTime = millis() + hapticPacket.duration_ms;
        hapticActive = true;
    }
}

void handleIdentifyRequest() {
    IdentifyRequestPacket identifyPacket;
    udp.read((uint8_t *)&identifyPacket, sizeof(IdentifyRequestPacket));
    if (identifyPacket.type != IDENTIFY_REQUEST) {
        return;
    }

    pulseHaptic(90, 60, 2);
}

unsigned long buttonHeldSince = 0;

void loop() {
    static bool biasesSaved = false;
    static unsigned long startTime = millis();

    if (digitalRead(BUTTON_PIN) == LOW) {
        if (buttonHeldSince == 0) {
            buttonHeldSince = millis();
        } else if (millis() - buttonHeldSince >= HOLD_RESET_MS && millis() - buttonHeldSince < HOLD_RESET_MS + 1000){
            pulseHaptic(1000, 0, 1);
        }else if (millis() - buttonHeldSince >= HOLD_REBOOT_MS && millis() - buttonHeldSince < HOLD_REBOOT_MS + 250){
            pulseHaptic(250, 0, 1);
        }
    } else if (buttonHeldSince != 0) {
        if (millis() - buttonHeldSince >= HOLD_RESET_MS) {
            Serial.println("Factory reset triggered by long button hold");
            wifiCredentialsClear();
            deleteStoredBiases();
            rp2040.reboot();
        } else if (millis() - buttonHeldSince >= HOLD_REBOOT_MS) {
            rp2040.reboot();
        } else {
            buttonHeldSince = 0;
        }
    }


    // Handle discovery response from server
    if (!discovered) {
        handleDiscoveryResponse();
        // Send discovery request every 1 second until discovered
        if (!discovered && millis() - lastDiscoveryTime >= 1000) {
            DiscoveryRequestPacket disc_pkt = {
                .type = DISCOVERY_REQUEST};
            memcpy(disc_pkt.mac, MAC_ADDR, 6);
            sendUdpPacket((const uint8_t *)&disc_pkt, sizeof(disc_pkt), UDP_BROADCAST_IP);
            Serial.println("Sent discovery request");
            lastDiscoveryTime = millis();
        }
        return;
    }

    if (hapticActive && millis() >= hapticCommandEndTime) {
        Serial.println("Haptic command duration ended, turning off haptic motor");
        digitalWrite(HAPTIC_MOTOR_PIN, LOW);
        hapticActive = false;
    }

    int packetSize = udp.parsePacket();
    if (packetSize > 0) {
        byte type = udp.peek();
        if (type == LATENCY_CHECK && packetSize == sizeof(LatencyPacket)) {
            handleLatencyPing();
        } else if (type == HAPTIC_FEEDBACK && packetSize == sizeof(HapticFeedbackPacket)) {
            handleHapticFeedback();
        } else if (type == IDENTIFY_REQUEST && packetSize == sizeof(IdentifyRequestPacket)) {
            handleIdentifyRequest();
        } else {
            // Unknown packet type or size, ignore
            uint8_t buffer[packetSize];
            udp.readBytes(buffer, packetSize); // Clear the packet from the buffer
        }
    }

    // Read any DMP data waiting in the FIFO
    // Note:
    //    readDMPdataFromFIFO will return ICM_20948_Stat_FIFONoDataAvail if no data is available.
    //    If data is available, readDMPdataFromFIFO will attempt to read _one_ frame of DMP data.
    //    readDMPdataFromFIFO will return ICM_20948_Stat_FIFOIncompleteData if a frame was present but was incomplete
    //    readDMPdataFromFIFO will return ICM_20948_Stat_Ok if a valid frame was read.
    //    readDMPdataFromFIFO will return ICM_20948_Stat_FIFOMoreDataAvail if a valid frame was read _and_ the FIFO contains more (unread) data.
    icm_20948_DMP_data_t data;
    myICM.readDMPdataFromFIFO(&data);

    if ((myICM.status == ICM_20948_Stat_Ok) || (myICM.status == ICM_20948_Stat_FIFOMoreDataAvail)) // Was valid data available?
    {
        if ((data.header & DMP_header_bitmap_Quat6) > 0) // Quat6 from LINEAR_ACCELERATION sensor
        {
            // Q0 value is computed from this equation: Q0^2 + Q1^2 + Q2^2 + Q3^2 = 1.
            // The quaternion data is scaled by 2^30.
            double q1 = ((double)data.Quat6.Data.Q1) / 1073741824.0; // Convert to double. Divide by 2^30
            double q2 = ((double)data.Quat6.Data.Q2) / 1073741824.0; // Convert to double. Divide by 2^30
            double q3 = ((double)data.Quat6.Data.Q3) / 1073741824.0; // Convert to double. Divide by 2^30
            double qSumSq = (q1 * q1) + (q2 * q2) + (q3 * q3);

            if (qSumSq > 1.0) {
                // This should never happen, but if it does, we can end up with NaNs. In that case, just skip this frame.
                Serial.println("Invalid quaternion data: qSumSq > 1.0");
                myICM.resetFIFO();
                return;
            }

            double q0 = sqrt(1.0 - qSumSq);

            // Raw accelerometer data (FSR ±8g, 4096 LSB/g)
            float ax = 0.0, ay = 0.0, az = 0.0;
            if ((data.header & DMP_header_bitmap_Accel) > 0) {
                ax = (float)data.Raw_Accel.Data.X / 4096.0f;
                ay = (float)data.Raw_Accel.Data.Y / 4096.0f;
                az = (float)data.Raw_Accel.Data.Z / 4096.0f;
            }

            // Raw gyroscope data (FSR ±2000 dps, 16.384 LSB/(deg/s))
            float gx = 0.0, gy = 0.0, gz = 0.0;
            if ((data.header & DMP_header_bitmap_Gyro) > 0) {
                gx = (float)data.Raw_Gyro.Data.X / 16.4f; // 16.384 is a pain, 16.4 is close enough
                gy = (float)data.Raw_Gyro.Data.Y / 16.4f;
                gz = (float)data.Raw_Gyro.Data.Z / 16.4f;
            }

            SensorDataPacket pkt = {
                .type = SENSOR_DATA,
                .ts = (uint32_t)millis(),
                .qw = (float)q0,
                .qx = (float)q1,
                .qy = (float)q2,
                .qz = (float)q3,
                .ax = ax,
                .ay = ay,
                .az = az,
                .gx = gx,
                .gy = gy,
                .gz = gz};
            memcpy(pkt.mac, MAC_ADDR, 6);

            // Only send sensor data if we've discovered the server
            if (discovered) {
                sendUdpPacket((const uint8_t *)&pkt, sizeof(pkt), SERVER_IP);
            }
            packetCount++;
            if (millis() - lastPrintTime >= 1000) {
                Serial.print("Packets sent in the last second: ");
                Serial.println(packetCount);
                packetCount = 0;
                lastPrintTime = millis();
            }
        }
    }

    if (myICM.status != ICM_20948_Stat_FIFOMoreDataAvail) // If more data is available then we should read it right away - and not delay
    {
        // Save biases once after BIAS_SAVE_DELAY_MS. By then gyro/accel/mag
        // calibration has had time to converge. Only saves once per power cycle.
        if (!biasesSaved && (millis() - startTime >= BIAS_SAVE_DELAY_MS)) {
            biasesSaved = true;
            saveBiasesToFlash(myICM);
        }

        delay(10);
    }
}
