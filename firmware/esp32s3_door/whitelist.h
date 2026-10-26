#pragma once

#include <stddef.h>
#include <stdint.h>

enum class DecisionSource { Online, Whitelist, Master, Deny };

struct Decision {
  bool allowed;
  DecisionSource source;
};

void whitelistBegin();
void whitelistRemember(const char* code);
void whitelistSetMaster(const char* code);
bool whitelistMatch(const char* code);
bool masterMatch(const char* code);

void queueOffline(const char* code, bool allowed);
bool popOffline(char* code, size_t codeLen, bool* allowed);
