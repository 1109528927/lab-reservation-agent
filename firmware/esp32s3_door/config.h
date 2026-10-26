#pragma once

// 端到端原型：手机热点 + 局域网。改成你电脑在热点里的地址。
#define WIFI_SSID "YOUR_WIFI_SSID"
#define WIFI_PASSWORD "YOUR_WIFI_PASSWORD"
#define DEVICE_ID "DOOR-LAB-1"
#define VERIFY_URL "http://192.168.1.100:8000/api/access/verify"

// 串口二维码扫码模块。RX 接模块 TX。兼容 GM65 等同款 TTL 模块。
#define GM65_RX 18
#define GM65_TX 17
#define GM65_BAUD 9600

// 声光。放行灯、拒绝灯、蜂鸣器分开，便于单独更换。
#define PIN_LED_ALLOW 5
#define PIN_LED_DENY 6
#define PIN_BUZZER 4
// 三脚「低电平触发」有源蜂鸣器：I/O 低=响、高=停。两脚高电平响的模块改成 0。
#define BUZZER_ACTIVE_LOW 1
// 拒绝时长鸣毫秒（用户要求约 5 秒，不要一直响）
#define DENY_BEEP_MS 5000

// 4G 模组 UART 只预留，本期原型不打开。
#define LTE_RX 10
#define LTE_TX 11
#define LTE_BAUD 115200

#define WHITELIST_CAP 32
#define OFFLINE_QUEUE_CAP 16
