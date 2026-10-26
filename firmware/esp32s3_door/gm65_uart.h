#pragma once

#include <stddef.h>

void gm65Begin();
// 读到一行扫码结果返回 true。结果去掉回车换行。
bool gm65ReadCode(char* out, size_t outLen);
