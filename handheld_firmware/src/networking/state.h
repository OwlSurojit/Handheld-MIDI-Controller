#pragma once

#include <stdint.h>
#include <WiFiUdp.h>

extern WiFiUDP udp;
extern uint8_t macAddress[6];

void initializeNetworking();
bool processNetworking();