#include <windows.h>
#include <cstdio>
#include <cstdlib>

static void cleanup(HANDLE process, void* remote) {
    if (remote) VirtualFreeEx(process, remote, 0, MEM_RELEASE);
    if (process) CloseHandle(process);
}

int main(int argc, char** argv) {
    if (argc < 3) { printf("usage: injector <pid> <dll>\n"); return 2; }
    DWORD pid = (DWORD)strtoul(argv[1], nullptr, 10);
    const char* dll = argv[2];
    HANDLE h = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ, FALSE, pid);
    if (!h) { printf("OpenProcess failed %lu\n", GetLastError()); return 3; }
    SIZE_T size = strlen(dll) + 1;
    void* remote = VirtualAllocEx(h, nullptr, size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remote) { printf("VirtualAllocEx failed %lu\n", GetLastError()); CloseHandle(h); return 4; }
    if (!WriteProcessMemory(h, remote, dll, size, nullptr)) {
        printf("WriteProcessMemory failed %lu\n", GetLastError());
        cleanup(h, remote);
        return 5;
    }
    HMODULE k32 = GetModuleHandleA("kernel32.dll");
    FARPROC load = GetProcAddress(k32, "LoadLibraryA");
    HANDLE t = CreateRemoteThread(h, nullptr, 0, (LPTHREAD_START_ROUTINE)load, remote, 0, nullptr);
    if (!t) {
        printf("CreateRemoteThread failed %lu\n", GetLastError());
        cleanup(h, remote);
        return 6;
    }
    DWORD wait = WaitForSingleObject(t, 5000);
    if (wait != WAIT_OBJECT_0) {
        printf("remote thread timeout (%lu)\n", wait);
        CloseHandle(t);
        // The remote thread may still read the path; leak the remote block
        // rather than freeing memory another thread is using.
        CloseHandle(h);
        return 7;
    }
    DWORD code = 0;
    GetExitCodeThread(t, &code);
    printf("injected pid=%lu dll=%s thread=%lu\n", pid, dll, code);
    CloseHandle(t);
    cleanup(h, remote);
    return 0;
}
