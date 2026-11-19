"""Optional Windows integrations; all fail softly on other systems."""
import ctypes
import os
import subprocess
import sys
from pathlib import Path
from ctypes import wintypes

IS_WINDOWS = sys.platform == "win32"

def idle_seconds():
    if not IS_WINDOWS:
        return 0
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        now = ctypes.windll.kernel32.GetTickCount() & 0xffffffff
        return ((now - info.dwTime) & 0xffffffff) / 1000
    return 0

def startup_command():
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable, "--quiet"])
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return subprocess.list2cmdline([str(pythonw if pythonw.exists() else sys.executable),
                                   str(Path(__file__).resolve().parents[1] / "main.py"), "--quiet"])

def startup_enabled():
    if not IS_WINDOWS:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
            return winreg.QueryValueEx(key, "CatMate")[0] == startup_command()
    except OSError:
        return False

def set_startup(enabled):
    if not IS_WINDOWS:
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled:
            winreg.SetValueEx(key, "CatMate", 0, winreg.REG_SZ, startup_command())
        else:
            try:
                winreg.DeleteValue(key, "CatMate")
            except FileNotFoundError:
                pass

def discover_apps():
    """Find installed Doubao without scanning personal files or invoking a shell."""
    found = []
    roots = [Path(os.environ.get("LOCALAPPDATA", "")), Path(os.environ.get("APPDATA", "")),
             Path(os.environ.get("ProgramFiles", r"C:\Program Files"))]
    candidates = []
    for root in roots:
        candidates.extend(root / p for p in ["Doubao/Doubao.exe", "doubao/Doubao.exe",
                                            "Programs/Doubao/Doubao.exe", "Doubao/Application/Doubao.exe"])
    start = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"
    if start.exists():
        candidates.extend(start.glob("**/*豆包*.lnk"))
        candidates.extend(start.glob("**/*Doubao*.lnk"))
    for candidate in candidates:
        if candidate.is_file():
            found.append({"name": "豆包", "path": str(candidate.resolve())})
            break
    return found

def launch_app(path):
    if path == "https://www.doubao.com/":
        import webbrowser
        if not webbrowser.open(path, new=2):
            raise OSError("无法打开默认浏览器。")
        return
    candidate = Path(path)
    if not candidate.is_file():
        raise FileNotFoundError("文件已移动或不存在，请重新选择软件。")
    if candidate.suffix.lower() not in {".exe", ".lnk", ".appref-ms"}:
        raise ValueError("请选择软件的 .exe 或 .lnk 文件。")
    if IS_WINDOWS:
        os.startfile(str(candidate))
    else:
        subprocess.Popen([str(candidate)], shell=False)

def desktop_icon_rects():
    """Read Explorer's icon bounds. No icon positions or files are modified.

    Explorer owns the ListView, so LVM_GETITEMRECT needs a small remote RECT.
    Always close the handle and release the allocation, including timeout paths.
    Coordinates are physical pixels; caller converts to Qt screen coordinates.
    """
    if not IS_WINDOWS:
        return []
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowW.restype = wintypes.HWND
    user.FindWindowExW.argtypes = [wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user.FindWindowExW.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.SendMessageTimeoutW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t,
                                        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t)]
    user.SendMessageTimeoutW.restype = ctypes.c_size_t
    user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    views = []
    @callback_type
    def visit(hwnd, _):
        view = user.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
        if view:
            lv = user.FindWindowExW(view, None, "SysListView32", None)
            if lv:
                views.append(lv)
        return True
    user.EnumWindows(visit, 0)
    if not views:
        return []
    lv = views[0]
    result = ctypes.c_size_t()
    if not user.SendMessageTimeoutW(lv, 0x1004, 0, 0, 2, 200, ctypes.byref(result)):
        return []
    count = min(result.value, 300)
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(lv, ctypes.byref(pid))
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel.VirtualAllocEx.restype = ctypes.c_void_p
    kernel.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p]
    kernel.ReadProcessMemory.argtypes = list(kernel.WriteProcessMemory.argtypes)
    kernel.VirtualFreeEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x0038, False, pid.value)
    if not handle:
        return []
    remote = None
    rectangles = []
    try:
        remote = kernel.VirtualAllocEx(handle, None, 16, 0x3000, 0x04)
        if not remote:
            return []
        origin = wintypes.POINT(0, 0)
        user.ClientToScreen(lv, ctypes.byref(origin))
        for i in range(count):
            rect = wintypes.RECT(1, 0, 0, 0)  # LVIR_ICON only, excluding label.
            if not kernel.WriteProcessMemory(handle, remote, ctypes.byref(rect), 16, None):
                break
            if not user.SendMessageTimeoutW(lv, 0x100E, i, remote, 2, 100, ctypes.byref(result)):
                break
            if result.value and kernel.ReadProcessMemory(handle, remote, ctypes.byref(rect), 16, None):
                rectangles.append((rect.left + origin.x, rect.top + origin.y,
                                   rect.right + origin.x, rect.bottom + origin.y))
    finally:
        if remote:
            kernel.VirtualFreeEx(handle, remote, 0, 0x8000)
        kernel.CloseHandle(handle)
    return rectangles
