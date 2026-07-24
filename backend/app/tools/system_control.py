"""PC system controls: master volume, Night Light, and sleep.

Volume uses `pycaw` (Windows Core Audio). Night Light is toggled via a registry
flip + a session notification (the cleanest programmatic trigger on Windows
without signing a binary). Sleep uses the OS power command.
"""
from __future__ import annotations

import subprocess
import sys

from ..schemas import ToolResult
from .registry import tool


# =====================================================================
# Volume
# =====================================================================
def _clamp_percent(percent: int | float) -> float:
    try:
        v = float(percent)
    except (TypeError, ValueError):
        return 50.0
    return max(0.0, min(100.0, v))


@tool
def set_volume(percent: int) -> ToolResult:
    """Set the PC's master volume to a specific percentage between 0 and 100 (e.g. 50, 100, 0 to mute).

    :param percent: Target volume from 0 (muted) to 100 (max).
    """
    target = _clamp_percent(percent)
    try:
        if sys.platform != "win32":
            return ToolResult(
                status="error",
                message="Volume control currently supports Windows only.",
            )
        # Lazy imports keep the server bootable on non-Windows dev machines.
        import comtypes  # noqa: F401
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        # pycaw expects 0.0..1.0 scalar.
        volume.SetMasterVolumeLevelScalar(target / 100.0, None)
        return ToolResult(
            status="ok",
            message=f"Volume set to {target:.0f}%.",
            data={"percent": target},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"I couldn't change the volume: {e}",
        )


# =====================================================================
# Night Light (Windows)
# =====================================================================
@tool
def trigger_night_light(enable: bool | None = None) -> ToolResult:
    """Toggle Windows Night Light (warm display color) on or off.

    :param enable: Optional. True=on, False=off. Omit to toggle the current state.
    """
    if sys.platform != "win32":
        return ToolResult(
            status="error",
            message="Night Light control currently supports Windows only.",
        )
    try:
        import winreg

        # The user-facing Night Light state lives under this registry key.
        # 0x44 = on, 0x00 = off (the first byte toggles warm color).
        subkey = (
            r"Software\\Microsoft\\Windows\\CurrentVersion\\CloudStore\\"
            r"Store\\DefaultAccount\\Current\\default\\"
            r"$windows.data.bluelightreduction.bluelightreductionstate\\"
            r"windows.data.bluelightreduction.bluelightreductionstate"
        )
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as k:
                data = winreg.QueryValueEx(k, "Data")[0]
        except FileNotFoundError:
            data = bytearray(b"\\x00" * 44)

        ba = bytearray(data) if not isinstance(data, (bytes, bytearray)) else bytearray(data)
        # Pad/normalize so we have at least a first status byte.
        if len(ba) < 1:
            ba = bytearray([0])
        currently_on = ba[0] in (0x44, 1)
        should_on = (not currently_on) if enable is None else bool(enable)
        ba[0] = 0x44 if should_on else 0x00

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey) as k:
            winreg.SetValueEx(k, "Data", 0, winreg.REG_BINARY, bytes(ba))

        # Nudge Explorer to apply the change immediately.
        subprocess.Popen(
            ["powershell", "-NoProfile", "-Command",
             "(New-Object -ComObject Shell.Application).ToggleDesktop()"],
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        state = "on" if should_on else "off"
        return ToolResult(
            status="ok",
            message=f"Night Light is now {state}.",
            data={"night_light": state},
        )
    except Exception as e:  # noqa: BLE001
        # Fallback: tell the user the keyboard path (Win panel still works).
        return ToolResult(
            status="error",
            message=(
                f"I couldn't toggle Night Light programmatically ({e}). "
                f"Quick way: open Settings > System > Display > Night light."
            ),
        )


# =====================================================================
# Sleep / power
# =====================================================================
@tool
def sleep_pc() -> ToolResult:
    """Put the PC to sleep immediately (Windows: rundll32 powrprof; macOS: pmset)."""
    try:
        if sys.platform == "win32":
            # powrprof SetSuspendState: 0=sleep, hibernate=false, force=true
            subprocess.Popen(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        elif sys.platform == "darwin":
            subprocess.Popen(["pmset", "sleepnow"])
        else:
            subprocess.Popen(["systemctl", "suspend"])
        return ToolResult(
            status="ok",
            message="Putting the PC to sleep now. Talk soon!",
            data={"action": "sleep"},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"I couldn't put the PC to sleep: {e}",
        )


@tool
def shutdown_pc() -> ToolResult:
    """Shutdown the PC immediately."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["shutdown", "/s", "/t", "0"], creationflags=subprocess.CREATE_NO_WINDOW)
        elif sys.platform == "darwin":
            subprocess.Popen(["sudo", "shutdown", "-h", "now"])
        else:
            subprocess.Popen(["systemctl", "poweroff"])
        return ToolResult(
            status="ok",
            message="Shutting down the PC. Goodbye!",
            data={"action": "shutdown"},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"I couldn't shut down the PC: {e}",
        )


@tool
def restart_pc() -> ToolResult:
    """Restart the PC immediately."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["shutdown", "/r", "/t", "0"], creationflags=subprocess.CREATE_NO_WINDOW)
        elif sys.platform == "darwin":
            subprocess.Popen(["sudo", "shutdown", "-r", "now"])
        else:
            subprocess.Popen(["systemctl", "reboot"])
        return ToolResult(
            status="ok",
            message="Restarting the PC. Be right back!",
            data={"action": "restart"},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"I couldn't restart the PC: {e}",
        )


@tool
def lock_pc() -> ToolResult:
    """Lock the PC screen immediately."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], creationflags=subprocess.CREATE_NO_WINDOW)
        elif sys.platform == "darwin":
            subprocess.Popen(["pmset", "displaysleepnow"])
        else:
            subprocess.Popen(["loginctl", "lock-session"])
        return ToolResult(
            status="ok",
            message="PC locked securely.",
            data={"action": "lock"},
        )
    except Exception as e:  # noqa: BLE001
        return ToolResult(
            status="error",
            message=f"I couldn't lock the PC: {e}",
        )

