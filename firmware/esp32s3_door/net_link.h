#pragma once

#include <stddef.h>

// 网络链路抽象。原型用 Wi-Fi 连手机热点；4G 只保留同类接口，不作为验收项。
class NetLink {
 public:
  virtual bool begin() = 0;
  virtual bool connected() = 0;
  virtual void loop() = 0;
  // 返回 HTTP 状态码。失败返回负数。resp 以 0 结尾。
  virtual int postJson(const char* url, const char* jsonBody, char* resp, size_t respLen) = 0;
};

class WifiHotspotLink : public NetLink {
 public:
  bool begin() override;
  bool connected() override;
  void loop() override;
  int postJson(const char* url, const char* jsonBody, char* resp, size_t respLen) override;
};

// 架构预留：4G 模组走另一路 UART。未接线时不要 begin。
class LteUartLink : public NetLink {
 public:
  bool begin() override;
  bool connected() override;
  void loop() override;
  int postJson(const char* url, const char* jsonBody, char* resp, size_t respLen) override;
};
