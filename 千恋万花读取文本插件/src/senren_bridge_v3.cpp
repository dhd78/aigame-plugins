// Read-only TJS bridge for Senren * Banka (KiriKiri2, x86).
// TJS is executed only from TVP's continuous-event callback (engine main thread).
// No drawing hooks, no window-proc replacement, no synthetic TJS calls from HTTP threads.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <objidl.h>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <mutex>
#include <ctime>
#include "tp_stub.h"

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "user32.lib")

static const int PORT = 15528;
static const wchar_t* kWindowClass = L"TVPMainWindow";
#define SENREN_BRIDGE_VERSION "3.2"

static volatile LONG g_ready = 0;
static volatile LONG g_generation = 0;
static std::mutex g_mu;
static std::string g_state;
static std::string g_lastText;
static std::vector<std::string> g_backlog;
static HWND g_hwnd = nullptr;

static void logline(const char* fmt, ...) {
    char path[MAX_PATH] = {0}; GetTempPathA(MAX_PATH, path); lstrcatA(path, "senren-read-bridge.log");
    FILE* f = nullptr; fopen_s(&f, path, "a");
    if (!f) return;
    SYSTEMTIME st; GetLocalTime(&st);
    fprintf(f, "%04d-%02d-%02d %02d:%02d:%02d ", st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);
    va_list ap; va_start(ap, fmt); vfprintf(f, fmt, ap); va_end(ap); fprintf(f, "\n"); fclose(f);
}

static std::string utf8(const std::wstring& w) {
    if (w.empty()) return {};
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), nullptr, 0, nullptr, nullptr);
    if (n <= 0) return {};
    std::string s(n, '\0');
    WideCharToMultiByte(CP_UTF8, 0, w.c_str(), (int)w.size(), &s[0], n, nullptr, nullptr);
    return s;
}

static std::string getGlobalString(const wchar_t* name) {
    iTJSDispatch2* global = TVPGetScriptDispatch();
    if (!global) return {};
    tTJSVariant v;
    std::string out;
    if (global->PropGet(TJS_MEMBERMUSTEXIST, name, nullptr, &v, global) == TJS_S_OK) {
        const ttstr s = v.GetString();
        out = utf8(std::wstring(s.c_str(), s.GetLen()));
        v.Clear();
    }
    global->Release();
    return out;
}

static int g_inited = 0;
static int g_disabled = 0;

static bool execScript(const wchar_t* src) {
    iTJSDispatch2* global = TVPGetScriptDispatch();
    if (!global) return false;
    bool ok = true;
    try {
        TVPExecuteScript(ttstr(src), global, nullptr);
    } catch (...) {
        logline("TJS exception");
        ok = false;
    }
    global->Release();
    return ok;
}

// One-time initialization on the engine main thread: create a TJS Timer whose
// handler reads the fields and stores a delimited string in a TJS global.
static void initTimer() {
    const wchar_t* script =
        L"global.__wlState='';"
        L"global.__wlTick=function(){"
        L" try {"
        L"  var __h=kag.historyLayer;"
        L"  var __n=__h ? __h.getHistoryCount() : 0;"
        L"  var __r=__n>0 ? __h.data[__n-1] : void;"
        L"  var __t=__r ? __r.text : '';"
        L"  var __a=__r ? __r.name : '';"
        L"  var __c=kag.clickWaiting ? 1 : 0;"
        L"  global.__wlState=__t+'\\x1f'+__a+'\\x1f'+__c;"
        L" } catch(e) { global.__wlState=''; }"
        L"};"
        L"global.__wlTimer=new Timer(global.__wlTick,'');"
        L"global.__wlTimer.interval=200;"
        L"global.__wlTimer.enabled=true;";
    if (!execScript(script)) {
        g_disabled = 1;
        logline("Timer init failed");
    }
}

static void readTimerState() {
    if (g_disabled) return;
    std::string raw = getGlobalString(L"__wlState");
    if (raw.empty()) return;
    std::lock_guard<std::mutex> lock(g_mu);
    g_state = raw;
    InterlockedIncrement(&g_generation);
}

static std::string jsonEscape(const std::string& s) {
    std::string o;
    for (unsigned char c : s) {
        switch (c) {
            case '"': o += "\\\""; break;
            case '\\': o += "\\\\"; break;
            case '\n': o += "\\n"; break;
            case '\r': o += "\\r"; break;
            case '\t': o += "\\t"; break;
            default:
                if (c < 0x20) { char b[8]; sprintf_s(b, "\\u%04x", c); o += b; }
                else o += (char)c;
        }
    }
    return o;
}

class BridgeHook : public tTVPContinuousEventCallbackIntf {
public:
    void TJS_INTF_METHOD OnContinuousCallback(tjs_uint64) override {
        if (!g_ready) return;
        if (!g_inited) {
            g_inited = 1;
            initTimer();
            logline("Timer initialized");
        }
        readTimerState();
    }
};
static BridgeHook g_hook;

static std::string clickResult(int cx, int cy) {
    if (!g_hwnd || !IsWindow(g_hwnd)) g_hwnd = FindWindowW(kWindowClass, nullptr);
    if (!g_hwnd) return "{\"ok\":false,\"attempted\":false,\"error\":\"window not found\"}";
    if (IsIconic(g_hwnd)) { ShowWindow(g_hwnd, SW_RESTORE); Sleep(400); }
    RECT cr{};
    if (!GetClientRect(g_hwnd, &cr) || cr.right <= 0 || cr.bottom <= 0)
        return "{\"ok\":false,\"attempted\":false,\"error\":\"no client rect\"}";
    if (cx < 0) cx = cr.right / 2;
    if (cy < 0) cy = (int)(cr.bottom * 0.75);
    if (cx >= cr.right) cx = cr.right - 1;
    if (cy >= cr.bottom) cy = cr.bottom - 1;
    LPARAM lp = ((cy & 0xFFFF) << 16) | (cx & 0xFFFF);
    PostMessageW(g_hwnd, WM_MOUSEMOVE, 0, lp);
    Sleep(30);
    PostMessageW(g_hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp);
    Sleep(30);
    PostMessageW(g_hwnd, WM_LBUTTONUP, 0, lp);
    Sleep(120);
    char out[256];
    sprintf_s(out,
              "{\"ok\":true,\"attempted\":true,\"foreground\":%s,\"client\":[%d,%d],\"client_size\":[%d,%d]}",
              (GetForegroundWindow() == g_hwnd ? "true" : "false"), cx, cy, cr.right, cr.bottom);
    return out;
}

static void split(const std::string& s, char sep, std::vector<std::string>& out) {
    size_t start = 0;
    while (true) {
        size_t p = s.find(sep, start);
        if (p == std::string::npos) { out.push_back(s.substr(start)); break; }
        out.push_back(s.substr(start, p - start));
        start = p + 1;
    }
}

static std::string stateJson() {
    std::string raw;
    {
        std::lock_guard<std::mutex> lock(g_mu);
        raw = g_state;
    }
    std::vector<std::string> f;
    split(raw, '\x1f', f);
    std::string text = f.size() > 0 ? f[0] : "";
    std::string author = f.size() > 1 ? f[1] : "";
    int clickWaiting = f.size() > 2 ? atoi(f[2].c_str()) : 0;
    std::string label = f.size() > 3 ? f[3] : "";
    std::string storage = f.size() > 4 ? f[4] : "";
    bool typing = clickWaiting == 0;
    std::string scene = storage;
    if (!label.empty()) scene += "@" + label;
    {
        std::lock_guard<std::mutex> lock(g_mu);
        if (!text.empty() && text != g_lastText) {
            g_lastText = text;
            g_backlog.push_back(text);
            if (g_backlog.size() > 200) g_backlog.erase(g_backlog.begin());
        }
    }
    return "{\"ok\":true,\"text\":\"" + jsonEscape(text) + "\",\"author\":\"" + jsonEscape(author) +
           "\",\"choices\":[],\"typing\":" + (typing ? "true" : "false") +
           ",\"can_advance\":" + ((!typing) ? "true" : "false") +
           ",\"scene\":\"" + jsonEscape(scene) + "\",\"timestamp\":" +
           std::to_string((long long)time(nullptr) * 1000) + "}";
}

static std::string httpResponse(int code, const std::string& body) {
    const char* reason = code == 200 ? "OK" : "Bad Request";
    char head[256];
    sprintf_s(head, "HTTP/1.1 %d %s\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: %zu\r\nConnection: close\r\n\r\n", code, reason, body.size());
    return std::string(head) + body;
}

static void handleClient(SOCKET s) {
    DWORD timeoutMs = 5000;
    setsockopt(s, SOL_SOCKET, SO_RCVTIMEO, (const char*)&timeoutMs, sizeof(timeoutMs));
    setsockopt(s, SOL_SOCKET, SO_SNDTIMEO, (const char*)&timeoutMs, sizeof(timeoutMs));
    std::string req;
    char buf[4096];
    for (;;) {
        int n = recv(s, buf, sizeof(buf), 0);
        if (n <= 0) break;
        req.append(buf, n);
        if (req.find("\r\n\r\n") != std::string::npos) break;
        if (req.size() > 65536) break;
    }
    if (req.empty()) { closesocket(s); return; }
    size_t sp1 = req.find(' '), sp2 = req.find(' ', sp1 + 1);
    if (sp1 == std::string::npos || sp2 == std::string::npos || sp2 <= sp1 + 1) {
        const char* bad = "HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
        send(s, bad, (int)strlen(bad), 0);
        closesocket(s);
        return;
    }
    std::string method = req.substr(0, sp1);
    std::string path = req.substr(sp1 + 1, sp2 - sp1 - 1);
    std::string resp;
    if (method == "GET" && path == "/health") {
        resp = httpResponse(200, std::string("{\"ok\":true,\"version\":\"") + SENREN_BRIDGE_VERSION + "\",\"port\":15528}");
    } else if (method == "GET" && path == "/state") {
        resp = httpResponse(200, stateJson());
    } else if (method == "GET" && path == "/label") {
        resp = httpResponse(200, "{\"ok\":true,\"label\":\"\"}");
    } else if (method == "POST" && path == "/advance") {
        resp = httpResponse(200, clickResult(-1, -1));
    } else if (method == "GET" && path.rfind("/backlog", 0) == 0) {
        std::string arr = "[";
        {
            std::lock_guard<std::mutex> lock(g_mu);
            for (size_t i = 0; i < g_backlog.size(); ++i) { if (i) arr += ","; arr += "\"" + jsonEscape(g_backlog[i]) + "\""; }
        }
        arr += "]";
        resp = httpResponse(200, "{\"ok\":true,\"entries\":" + arr + "}");
    } else if (method == "POST" && path == "/choose") {
        resp = httpResponse(200, "{\"ok\":false,\"error\":\"choose-unavailable\"}");
    } else {
        resp = httpResponse(404, "{\"ok\":false,\"error\":\"not found\"}");
    }
    size_t sent = 0;
    while (sent < resp.size()) {
        int n = send(s, resp.data() + sent, (int)(resp.size() - sent), 0);
        if (n <= 0) break;
        sent += (size_t)n;
    }
    shutdown(s, SD_SEND);
    closesocket(s);
}

static DWORD WINAPI serverThread(LPVOID) {
    WSADATA wsa; if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) return 0;
    SOCKET srv = socket(AF_INET, SOCK_STREAM, 0);
    sockaddr_in addr{}; addr.sin_family = AF_INET; addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK); addr.sin_port = htons(PORT);
    if (bind(srv, (sockaddr*)&addr, sizeof(addr)) != 0) { logline("bind failed %d", WSAGetLastError()); return 0; }
    listen(srv, 8);
    g_hwnd = FindWindowW(kWindowClass, nullptr);
    logline("server %d hwnd=%p", PORT, g_hwnd);
    while (true) {
        SOCKET c = accept(srv, nullptr, nullptr);
        if (c != INVALID_SOCKET) handleClient(c);
    }
}

static DWORD WINAPI initThread(LPVOID) {
    for (int i = 0; i < 240; ++i) {
        if (GetModuleHandleA("textrender.dll") && FindWindowW(kWindowClass, nullptr)) break;
        Sleep(250);
    }
    HMODULE tr = GetModuleHandleA("textrender.dll");
    if (!tr) { logline("no textrender"); return 0; }
    void* exporter = *(void**)((BYTE*)tr + 0x33950);
    if (!exporter) { logline("no exporter"); return 0; }
    if (!TVPInitImportStub((iTVPFunctionExporter*)exporter)) { logline("stub failed"); return 0; }
    TVPAddContinuousEventHook(&g_hook);
    InterlockedExchange(&g_ready, 1);
    logline("TJS continuous hook installed");
    CreateThread(nullptr, 0, serverThread, nullptr, 0, nullptr);
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(h);
        // Deliberately no LoadLibrary / TJS call here: the loader lock is held.
        // initThread first waits for textrender.dll and the game window, then
        // initializes the TJS stub from the engine's own thread context.
        CreateThread(nullptr, 0, initThread, nullptr, 0, nullptr);
    }
    return TRUE;
}
