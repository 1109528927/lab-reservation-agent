#include "gm65_uart.h"

#include <HardwareSerial.h>

#include "config.h"

static HardwareSerial Gm65(1);

void gm65Begin() { Gm65.begin(GM65_BAUD, SERIAL_8N1, GM65_RX, GM65_TX); }

bool gm65ReadCode(char* out, size_t outLen) {
  if (!out || outLen < 2) return false;
  if (!Gm65.available()) return false;
  size_t n = 0;
  unsigned long start = millis();
  while (millis() - start < 200 && n + 1 < outLen) {
    while (Gm65.available() && n + 1 < outLen) {
      char c = static_cast<char>(Gm65.read());
      if (c == '\r' || c == '\n') {
        if (n == 0) continue;
        out[n] = '\0';
        return true;
      }
      out[n++] = c;
      start = millis();
    }
  }
  if (n == 0) return false;
  out[n] = '\0';
  return true;
}
