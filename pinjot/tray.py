# -*- coding: utf-8 -*-
"""系统托盘图标。

纯 ctypes 调用 Win32（Shell_NotifyIcon），不引入 pystray 等第三方依赖。

用法：
    tray = TrayIcon(tooltip="PinJot", icon_path=ICON_PATH)
    ...
    for ev in tray.drain():          # 在 Tk 的 after 轮询里取事件
        if ev == "left": ...
"""

import ctypes
import sys
from ctypes import wintypes
from pathlib import Path

from .config import APP_NAME

IS_WIN = sys.platform.startswith("win")

WM_APP = 0x8000
WM_TRAY = WM_APP + 1

NIM_ADD, NIM_DELETE = 0, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x0001, 0x0002, 0x0004

WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205

IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x0040
IDI_APPLICATION = 32512
HWND_MESSAGE = -3
CS_HREDRAW, CS_VREDRAW = 0x0002, 0x0001
KLASS = "PinJotTrayWnd"

# 原生弹出菜单
MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
TPM_RETURNCMD = 0x0100
TPM_RIGHTBUTTON = 0x0002
WM_NULL = 0x0000


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_byte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", GUID),
        ("hBalloonIcon", wintypes.HICON),
    ]


if IS_WIN:
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT,
                                 wintypes.WPARAM, wintypes.LPARAM)

    class WNDCLASSEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT),
            ("style", wintypes.UINT),
            ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int),
            ("cbWndExtra", ctypes.c_int),
            ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON),
            ("hCursor", wintypes.HANDLE),
            ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR),
            ("lpszClassName", wintypes.LPCWSTR),
            ("hIconSm", wintypes.HICON),
        ]


class TrayIcon:
    """托盘图标。非 Windows 或创建失败时 ok 为 False，调用方需容错。"""

    def __init__(self, tooltip=APP_NAME, icon_path=None, menu=None):
        self.ok = False
        self._events = []
        self._nid = None
        self._hinst = None
        self._commands = {}
        self._menu = menu or []
        if not IS_WIN:
            return
        try:
            self._create(tooltip, icon_path)
            self.ok = True
        except Exception:
            self.ok = False

    def set_menu(self, menu):
        """menu: [(标签, 回调), None(分隔线), ...]"""
        self._menu = menu or []

    # ------------------------------------------------------------------ #
    def _create(self, tooltip, icon_path):
        u = self.user32 = ctypes.windll.user32
        self.shell32 = ctypes.windll.shell32
        k = self.kernel32 = ctypes.windll.kernel32

        # 64 位下必须声明 argtypes/restype，否则句柄与指针会被当成 int 截断
        u.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE,
            wintypes.LPVOID]
        u.CreateWindowExW.restype = wintypes.HWND
        u.LoadImageW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR,
                                 wintypes.UINT, ctypes.c_int, ctypes.c_int,
                                 wintypes.UINT]
        u.LoadImageW.restype = wintypes.HANDLE
        u.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        u.LoadIconW.restype = wintypes.HICON
        u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM]
        u.DefWindowProcW.restype = LRESULT
        u.DestroyWindow.argtypes = [wintypes.HWND]
        u.UnregisterClassW.argtypes = [wintypes.LPCWSTR, wintypes.HINSTANCE]
        self.shell32.Shell_NotifyIconW.argtypes = [
            wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
        u.CreatePopupMenu.restype = wintypes.HMENU
        u.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT,
                                  ctypes.c_size_t, wintypes.LPCWSTR]
        u.AppendMenuW.restype = wintypes.BOOL
        u.TrackPopupMenu.argtypes = [wintypes.HMENU, wintypes.UINT,
                                     ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                     wintypes.HWND, wintypes.LPVOID]
        u.TrackPopupMenu.restype = ctypes.c_int
        u.DestroyMenu.argtypes = [wintypes.HMENU]
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                   wintypes.WPARAM, wintypes.LPARAM]
        k.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        k.GetModuleHandleW.restype = wintypes.HMODULE
        self._hinst = k.GetModuleHandleW(None)

        self._proc = WNDPROC(self._wndproc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.style = CS_HREDRAW | CS_VREDRAW
        wc.lpfnWndProc = self._proc
        wc.hInstance = self._hinst
        wc.lpszClassName = KLASS
        if not u.RegisterClassExW(ctypes.byref(wc)):
            raise ctypes.WinError()

        self.hwnd = u.CreateWindowExW(0, KLASS, KLASS, 0, 0, 0, 0, 0,
                                      HWND_MESSAGE, None, self._hinst, None)
        if not self.hwnd:
            raise ctypes.WinError()

        self.hicon = self._load_icon(icon_path)
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY
        nid.hIcon = self.hicon
        nid.szTip = tooltip
        if not self.shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            raise ctypes.WinError()
        self._nid = nid

    def _load_icon(self, icon_path):
        if icon_path:
            p = Path(icon_path)
            if p.exists():
                h = self.user32.LoadImageW(None, str(p), IMAGE_ICON, 0, 0,
                                           LR_LOADFROMFILE | LR_DEFAULTSIZE)
                if h:
                    return h
        return self.user32.LoadIconW(None, ctypes.c_wchar_p(IDI_APPLICATION))

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == WM_TRAY:
            code = lparam & 0xFFFF
            if code in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self._events.append("left")
            elif code == WM_RBUTTONUP:
                self._events.append("right")
            return 0
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    # ------------------------------------------------------------------ #
    def show_menu(self):
        """在光标处弹出原生右键菜单（窗口隐藏时也能正常显示）"""
        if not self.ok or not self._menu:
            return
        u = self.user32
        self._commands = {}
        hmenu = u.CreatePopupMenu()
        if not hmenu:
            return
        try:
            cmd = 1
            for item in self._menu:
                if item is None:
                    u.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
                    continue
                label, callback = item
                u.AppendMenuW(hmenu, MF_STRING, cmd, label)
                self._commands[cmd] = callback
                cmd += 1
            pt = wintypes.POINT()
            u.GetCursorPos(ctypes.byref(pt))
            # 必须先把本窗口设为前台，否则菜单不会因点击别处而消失
            u.SetForegroundWindow(self.hwnd)
            chosen = u.TrackPopupMenu(
                hmenu, TPM_RETURNCMD | TPM_RIGHTBUTTON,
                pt.x, pt.y, 0, self.hwnd, None)
            u.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        finally:
            u.DestroyMenu(hmenu)
        cb = self._commands.get(chosen)
        if cb:
            cb()

    def drain(self):
        """取出并清空待处理事件（'left' / 'right'）"""
        evs, self._events = self._events, []
        return evs

    def set_tip(self, text):
        if not self.ok:
            return
        try:
            self._nid.szTip = text
            self.shell32.Shell_NotifyIconW(1, ctypes.byref(self._nid))  # MODIFY
        except Exception:
            pass

    def destroy(self):
        if not self.ok:
            return
        try:
            self.shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._nid))
        except Exception:
            pass
        try:
            self.user32.DestroyWindow(self.hwnd)
            self.user32.UnregisterClassW(KLASS, self._hinst)
        except Exception:
            pass
        self.ok = False
