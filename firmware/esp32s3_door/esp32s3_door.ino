#include <Arduino.h>

#include "actuator.h"
#include "config.h"
#include "gm65_uart.h"
#include "net_link.h"
#include "whitelist.h"

WifiHotspotLink gWifi;
NetLink* gLink = &gWifi;

static bool jsonAllowed(const char* json) {
  if (!json) return false;
  return strstr(json, "\"allowed\":true") != nullptr || strstr(json, "\"allowed\": true") != nullptr;
}

static void postVerify(const char* code, bool* httpOk, bool* allowed) {
  *httpOk = false;
  *allowed = false;
  if (!gLink->connected()) return;
  char body[160];
  snprintf(body, sizeof(body), "{\"code\":\"%s\",\"device_id\":\"%s\"}", code, DEVICE_ID);
  char resp[768];
  int status = gLink->postJson(VERIFY_URL, body, resp, sizeof(resp));
  if (status != 200) return;
  *httpOk = true;
  *allowed = jsonAllowed(resp);
}

static Decision decide(const char* code) {
  Decision d{false, DecisionSource::Deny};
  bool httpOk = false;
  bool allowed = false;
  postVerify(code, &httpOk, &allowed);
  if (httpOk) {
    if (allowed) {
      whitelistRemember(code);
      d.allowed = true;
      d.source = DecisionSource::Online;
    }
    return d;
  }
  if (whitelistMatch(code)) {
    d.allowed = true;
    d.source = DecisionSource::Whitelist;
    queueOffline(code, true);
    return d;
  }
  if (masterMatch(code)) {
    d.allowed = true;
    d.source = DecisionSource::Master;
    queueOffline(code, true);
    return d;
  }
  queueOffline(code, false);
  return d;
}

static void flushOffline() {
  if (!gLink->connected()) return;
  char code[64];
  bool allowed = false;
  if (!popOffline(code, sizeof(code), &allowed)) return;
  bool httpOk = false;
  bool serverAllowed = false;
  postVerify(code, &httpOk, &serverAllowed);
  if (!httpOk) queueOffline(code, allowed);
  (void)serverAllowed;
}

static void pollMasterCommand() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (!line.startsWith("MASTER ")) return;
  String code = line.substring(7);
  code.trim();
  whitelistSetMaster(code.c_str());
  Serial.println("master updated");
}

void setup() {
  Serial.begin(115200);
  actuatorBegin();
  gm65Begin();
  whitelistBegin();
  gLink->begin();
  Serial.println("door prototype: wifi hotspot lan");
}

void loop() {
  gLink->loop();
  pollMasterCommand();
  static unsigned long nextFlush = 0;
  if (millis() > nextFlush) {
    flushOffline();
    nextFlush = millis() + 5000;
  }
  char code[64];
  if (!gm65ReadCode(code, sizeof(code))) return;
  Decision d = decide(code);
  if (d.allowed) {
    actAllow();
  } else {
    actDeny();
  }
  Serial.printf("code=%s allowed=%d source=%d\n", code, d.allowed ? 1 : 0, static_cast<int>(d.source));
}
