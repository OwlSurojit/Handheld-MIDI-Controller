/****************************************************************
 * Example6_DMP_Quat9_Orientation.ino
 * ICM 20948 Arduino Library Demo
 * Initialize the DMP based on the TDK InvenSense ICM20948_eMD_nucleo_1.0 example-icm20948
 * Paul Clark, April 25th, 2021
 * Based on original code by:
 * Owen Lyke @ SparkFun Electronics
 * Original Creation Date: April 17 2019
 *
 * ** This example is based on InvenSense's _confidential_ Application Note "Programming Sequence for DMP Hardware Functions".
 * ** We are grateful to InvenSense for sharing this with us.
 *
 * ** Important note: by default the DMP functionality is disabled in the library
 * ** as the DMP firmware takes up 14301 Bytes of program memory.
 * ** To use the DMP, you will need to:
 * ** Edit ICM_20948_C.h
 * ** Uncomment line 29: #define ICM_20948_USE_DMP
 * ** Save changes
 * ** If you are using Windows, you can find ICM_20948_C.h in:
 * ** Documents\Arduino\libraries\SparkFun_ICM-20948_ArduinoLibrary\src\util
 *
 * Please see License.md for the license information.
 *
 * Distributed as-is; no warranty is given.
 ***************************************************************/


#include "ICM_20948.h" // Click here to get the library: http://librarymanager/All#SparkFun_ICM_20948_IMU
#include "imu_calibration.h"
#include <WiFi.h>
#include <WiFiUdp.h>

#define USE_SPI // Uncomment this to use SPI

#define SPI_PORT SPI // Your desired SPI port.       Used only when "USE_SPI" is defined
#define CS_PIN 17    // Which pin you connect CS to. Used only when "USE_SPI" is defined

#define WIRE_PORT Wire // Your desired Wire port.      Used when "USE_SPI" is not defined
// The value of the last bit of the I2C address.
// On the SparkFun 9DoF IMU breakout the default is 1, and when the ADR jumper is closed the value becomes 0
#define AD0_VAL 1

// Wi-Fi and UDP settings
const char *WIFI_SSID = "YY"; //"Why?-Fi"; //
const char *WIFI_PASS = "YE#n11sney"; // "Wh3r3for3?"; //
IPAddress UDP_REMOTE_IP(192, 168, 1, 37); // 117); // Receiver IP on your LAN
const uint16_t UDP_REMOTE_PORT = 47269;   // Receiver UDP port
const uint16_t UDP_LOCAL_PORT = 47269;    // Local UDP port on the Pico W

WiFiUDP udp;

#ifdef USE_SPI
ICM_20948_SPI myICM; // If using SPI create an ICM_20948_SPI object
#else
ICM_20948_I2C myICM; // Otherwise create an ICM_20948_I2C object
#endif

void connectWiFi() {
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
    }

    udp.begin(UDP_LOCAL_PORT);
}

void sendUdpMessage(const char *message) {
    int packetBegun = udp.beginPacket(UDP_REMOTE_IP, UDP_REMOTE_PORT);
    size_t bytes_written = udp.write((const uint8_t *)message, strlen(message));
    int packetSent = udp.endPacket();
}

void setup() {
    Serial.begin(115200);
    delay(100);

    calibration_init();

    connectWiFi();
    Serial.println("WiFi connected");

#ifdef USE_SPI
    SPI_PORT.begin();
#else
    WIRE_PORT.begin();
    WIRE_PORT.setClock(400000);
#endif

    bool initialized = false;
    while (!initialized) {

        // Initialize the ICM-20948
        // If the DMP is enabled, .begin performs a minimal startup. We need to configure the sample mode etc. manually.
#ifdef USE_SPI
        myICM.begin(CS_PIN, SPI_PORT);
#else
        myICM.begin(WIRE_PORT, AD0_VAL);
#endif

        if (myICM.status != ICM_20948_Stat_Ok) {
            delay(500);
        } else {
            initialized = true;
        }
    }

    bool success = true; // Use success to show if the DMP configuration was successful

    // Initialize the DMP. initializeDMP is a weak function. You can overwrite it if you want to e.g. to change the sample rate
    success &= (myICM.initializeDMP() == ICM_20948_Stat_Ok);

    // initializeDMP() hardcodes ±4g (8192 LSB/g). Override to ±8g (4096 LSB/g) which gives better
    // headroom for hit detection without clipping moderate swings. Also update the two DMP memory
    // registers that tell the DMP how to normalize hardware units to its internal 2^25 = 1g scale
    // and how to scale the output back to hardware units. Values derived from the Q-format defined
    // in ICM_20948_DMP.h: ACC_SCALE *= 2, ACC_SCALE2 /= 2 when FSR doubles from 4g to 8g.
    ICM_20948_fss_t myFSS;
    myFSS.a = gpm8;    // ±8g → 4096 LSB/g
    myFSS.g = dps2000; // keep gyro setting from initializeDMP
    success &= (myICM.setFullScale((ICM_20948_Internal_Acc | ICM_20948_Internal_Gyr), myFSS) == ICM_20948_Stat_Ok);
    const unsigned char accScale[4]  = {0x08, 0x00, 0x00, 0x00}; // ACC_SCALE  for ±8g
    const unsigned char accScale2[4] = {0x00, 0x02, 0x00, 0x00}; // ACC_SCALE2 for ±8g
    success &= (myICM.writeDMPmems(ACC_SCALE,  4, &accScale[0])  == ICM_20948_Stat_Ok);
    success &= (myICM.writeDMPmems(ACC_SCALE2, 4, &accScale2[0]) == ICM_20948_Stat_Ok);

    // DMP sensor options are defined in ICM_20948_DMP.h
    //    INV_ICM20948_SENSOR_ACCELEROMETER               (16-bit accel)
    //    INV_ICM20948_SENSOR_GYROSCOPE                   (16-bit gyro + 32-bit calibrated gyro)
    //    INV_ICM20948_SENSOR_RAW_ACCELEROMETER           (16-bit accel)
    //    INV_ICM20948_SENSOR_RAW_GYROSCOPE               (16-bit gyro + 32-bit calibrated gyro)
    //    INV_ICM20948_SENSOR_MAGNETIC_FIELD_UNCALIBRATED (16-bit compass)
    //    INV_ICM20948_SENSOR_GYROSCOPE_UNCALIBRATED      (16-bit gyro)
    //    INV_ICM20948_SENSOR_STEP_DETECTOR               (Pedometer Step Detector)
    //    INV_ICM20948_SENSOR_STEP_COUNTER                (Pedometer Step Detector)
    //    INV_ICM20948_SENSOR_GAME_ROTATION_VECTOR        (32-bit 6-axis quaternion)
    //    INV_ICM20948_SENSOR_ROTATION_VECTOR             (32-bit 9-axis quaternion + heading accuracy)
    //    INV_ICM20948_SENSOR_GEOMAGNETIC_ROTATION_VECTOR (32-bit Geomag RV + heading accuracy)
    //    INV_ICM20948_SENSOR_GEOMAGNETIC_FIELD           (32-bit calibrated compass)
    //    INV_ICM20948_SENSOR_GRAVITY                     (32-bit 6-axis quaternion)
    //    INV_ICM20948_SENSOR_LINEAR_ACCELERATION         (16-bit accel + 32-bit 6-axis quaternion)
    //    INV_ICM20948_SENSOR_ORIENTATION                 (32-bit 9-axis quaternion + heading accuracy)

    // Enable the DMP linear acceleration sensor (outputs Quat6 + raw accel in each FIFO frame)
    success &= (myICM.enableDMPSensor(INV_ICM20948_SENSOR_LINEAR_ACCELERATION) == ICM_20948_Stat_Ok);

    // Enable raw gyroscope (outputs 16-bit gyro X/Y/Z at ±2000 dps in each FIFO frame)
    success &= (myICM.enableDMPSensor(INV_ICM20948_SENSOR_RAW_GYROSCOPE) == ICM_20948_Stat_Ok);
    // success &= (myICM.enableDMPSensor(INV_ICM20948_SENSOR_RAW_ACCELEROMETER) == ICM_20948_Stat_Ok);
    // success &= (myICM.enableDMPSensor(INV_ICM20948_SENSOR_MAGNETIC_FIELD_UNCALIBRATED) == ICM_20948_Stat_Ok);

    // Configuring DMP to output data at multiple ODRs:
    // DMP is capable of outputting multiple sensor data at different rates to FIFO.
    // Setting value can be calculated as follows:
    // Value = (DMP running rate / ODR ) - 1
    // E.g. For a 5Hz ODR rate when DMP is running at 55Hz, value = (55/5) - 1 = 10.
    success &= (myICM.setDMPODRrate(DMP_ODR_Reg_Quat6, 0) == ICM_20948_Stat_Ok);  // Set to the maximum
    success &= (myICM.setDMPODRrate(DMP_ODR_Reg_Accel, 0) == ICM_20948_Stat_Ok);  // Set to the maximum
    success &= (myICM.setDMPODRrate(DMP_ODR_Reg_Gyro,  0) == ICM_20948_Stat_Ok);  // Set to the maximum
    // success &= (myICM.setDMPODRrate(DMP_ODR_Reg_Gyro_Calibr, 0) == ICM_20948_Stat_Ok); // Set to the maximum
    // success &= (myICM.setDMPODRrate(DMP_ODR_Reg_Cpass, 0) == ICM_20948_Stat_Ok); // Set to the maximum
    // success &= (myICM.setDMPODRrate(DMP_ODR_Reg_Cpass_Calibr, 0) == ICM_20948_Stat_Ok); // Set to the maximum

    // Enable the FIFO
    success &= (myICM.enableFIFO() == ICM_20948_Stat_Ok);

    // Enable the DMP
    success &= (myICM.enableDMP() == ICM_20948_Stat_Ok);

    // Reset DMP
    success &= (myICM.resetDMP() == ICM_20948_Stat_Ok);

    // Reset FIFO
    success &= (myICM.resetFIFO() == ICM_20948_Stat_Ok);

    // Check success
    if (!success) {
        Serial.println("DMP Initialization failed");
        while (1)
            ; // Do nothing more
    }

    // Restore previously saved calibration biases (if any)
    restoreBiasesFromFlash(myICM);
}

void loop() {
    static bool biasesSaved = false;
    static unsigned long startTime = millis();

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
        // SERIAL_PORT.print(F("Received data! Header: 0x")); // Print the header in HEX so we can see what data is arriving in the FIFO
        // if ( data.header < 0x1000) SERIAL_PORT.print( "0" ); // Pad the zeros
        // if ( data.header < 0x100) SERIAL_PORT.print( "0" );
        // if ( data.header < 0x10) SERIAL_PORT.print( "0" );
        // SERIAL_PORT.println( data.header, HEX );

        if ((data.header & DMP_header_bitmap_Quat6) > 0) // Quat6 from LINEAR_ACCELERATION sensor
        {
            // Q0 value is computed from this equation: Q0^2 + Q1^2 + Q2^2 + Q3^2 = 1.
            // The quaternion data is scaled by 2^30.
            double q1 = ((double)data.Quat6.Data.Q1) / 1073741824.0; // Convert to double. Divide by 2^30
            double q2 = ((double)data.Quat6.Data.Q2) / 1073741824.0; // Convert to double. Divide by 2^30
            double q3 = ((double)data.Quat6.Data.Q3) / 1073741824.0; // Convert to double. Divide by 2^30
            double q0 = sqrt(1.0 - ((q1 * q1) + (q2 * q2) + (q3 * q3)));

            // Raw accelerometer data (FSR ±8g, 4096 LSB/g)
            double ax = 0.0, ay = 0.0, az = 0.0;
            if ((data.header & DMP_header_bitmap_Accel) > 0)
            {
                ax = (double)data.Raw_Accel.Data.X / 4096.0;
                ay = (double)data.Raw_Accel.Data.Y / 4096.0;
                az = (double)data.Raw_Accel.Data.Z / 4096.0;
            }

            // Raw gyroscope data (FSR ±2000 dps, 16.384 LSB/(deg/s))
            double gx = 0.0, gy = 0.0, gz = 0.0;
            if ((data.header & DMP_header_bitmap_Gyro) > 0)
            {
                gx = (double)data.Raw_Gyro.Data.X / 16.384;
                gy = (double)data.Raw_Gyro.Data.Y / 16.384;
                gz = (double)data.Raw_Gyro.Data.Z / 16.384;
            }

            char payload[256];
            snprintf(payload, sizeof(payload),
                     "quat_w:%.6f|g\nquat_x:%.6f|g\nquat_y:%.6f|g\nquat_z:%.6f|g\n"
                     "accel_x:%.4f|g\naccel_y:%.4f|g\naccel_z:%.4f|g\n"
                     "gyro_x:%.2f|g\ngyro_y:%.2f|g\ngyro_z:%.2f|g\n",
                     q0, q1, q2, q3, ax, ay, az, gx, gy, gz);
            sendUdpMessage(payload);
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
