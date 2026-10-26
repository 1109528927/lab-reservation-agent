#include "net_link.h"

#include <HTTPClient.h>
#include <WiFi.h>
#include <string.h>

#include "config.h"

bool WifiHotspotLink::begin() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  return true;
}

bool WifiHotspotLink::connected() { return WiFi.status() == WL_CONNECTED; }

void WifiHotspotLink::loop() {}

int WifiHotspotLink::postJson(const char* url, const char* jsonBody, char* resp, size_t respLen) {
  if (!connected() || resp == nullptr || respLen == 0) return -1;
  resp[0] = '\0';
  HTTPClient http;
  if (!http.begin(url)) return -2;
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(4000);
  int code = http.POST(reinterpret_cast<uint8_t*>(const_cast<char*>(jsonBody)), strlen(jsonBody));
  if (code > 0) {
    String body = http.getString();
    size_t n = body.length();
    if (n >= respLen) n = respLen - 1;
    memcpy(resp, body.c_str(), n);
    resp[n] = '\0';
  }
  http.end();
  return code;
}

bool LteUartLink::begin() {
  // 本期不初始化 4G 串口，避免占用引脚和把未实现功能当成已完成。
  return false;
}

bool LteUartLink::connected() { return false; }

void LteUartLink::loop() {}

int LteUartLink::postJson(const char* url, const char* jsonBody, char* resp, size_t respLen) {
  (void)url;
  (void)jsonBody;
  if (resp && respLen) resp[0] = '\0';
  return -100;
}
