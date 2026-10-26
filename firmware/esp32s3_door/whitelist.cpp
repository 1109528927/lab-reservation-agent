#include "whitelist.h"

#include <Arduino.h>
#include <Preferences.h>
#include <stdio.h>
#include <string.h>

#include "config.h"

static Preferences Prefs;

static bool sameCode(const char* a, const char* b) {
  return a && b && strcmp(a, b) == 0;
}

void whitelistBegin() { Prefs.begin("door", false); }

void whitelistRemember(const char* code) {
  if (!code || !code[0]) return;
  for (int i = 0; i < WHITELIST_CAP; ++i) {
    char key[8];
    snprintf(key, sizeof(key), "c%d", i);
    String cur = Prefs.getString(key, "");
    if (cur == code) return;
  }
  for (int i = 0; i < WHITELIST_CAP; ++i) {
    char key[8];
    snprintf(key, sizeof(key), "c%d", i);
    if (Prefs.getString(key, "").length() == 0) {
      Prefs.putString(key, code);
      return;
    }
  }
  Prefs.putString("c0", code);
}

void whitelistSetMaster(const char* code) {
  if (!code) return;
  Prefs.putString("master", code);
}

bool whitelistMatch(const char* code) {
  for (int i = 0; i < WHITELIST_CAP; ++i) {
    char key[8];
    snprintf(key, sizeof(key), "c%d", i);
    String cur = Prefs.getString(key, "");
    if (sameCode(cur.c_str(), code)) return true;
  }
  return false;
}

bool masterMatch(const char* code) {
  String master = Prefs.getString("master", "");
  return master.length() > 0 && sameCode(master.c_str(), code);
}

void queueOffline(const char* code, bool allowed) {
  int n = Prefs.getInt("qn", 0);
  if (n < 0 || n >= OFFLINE_QUEUE_CAP) n = 0;
  char key[8];
  snprintf(key, sizeof(key), "q%d", n);
  String row = String(allowed ? "1," : "0,") + code;
  Prefs.putString(key, row);
  Prefs.putInt("qn", n + 1);
}

bool popOffline(char* code, size_t codeLen, bool* allowed) {
  int n = Prefs.getInt("qn", 0);
  if (n <= 0 || !code || !allowed) return false;
  String row = Prefs.getString("q0", "");
  for (int i = 1; i < n; ++i) {
    char from[8];
    char to[8];
    snprintf(from, sizeof(from), "q%d", i);
    snprintf(to, sizeof(to), "q%d", i - 1);
    Prefs.putString(to, Prefs.getString(from, ""));
  }
  char last[8];
  snprintf(last, sizeof(last), "q%d", n - 1);
  Prefs.remove(last);
  Prefs.putInt("qn", n - 1);
  if (row.length() < 2) return false;
  *allowed = row.charAt(0) == '1';
  String c = row.substring(2);
  strncpy(code, c.c_str(), codeLen - 1);
  code[codeLen - 1] = '\0';
  return code[0] != '\0';
}
