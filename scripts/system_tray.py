"""
Virginia Legal AI - System Tray
==============================
System tray icon with quick access to all GUI tools and system controls.
Right-click the tray icon for the menu.
"""
import sys
import os
import subprocess
import webbrowser
from pathlib import Path

# Fix encoding for Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _launch_script(script_name: str) -> None:
    """Launch a Python script from the project."""
    script = PROJECT_ROOT / "scripts" / script_name
    if script.exists():
        subprocess.Popen(
            [sys.executable, str(script)],
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
    else:
        _show_error(f"Script not found: {script}")


def _launch_bat(bat_name: str) -> None:
    """Launch a .bat file from the project root."""
    bat = PROJECT_ROOT / bat_name
    if bat.exists():
        subprocess.Popen(
            [str(bat)],
            cwd=str(PROJECT_ROOT),
            shell=True,
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
        )
    else:
        _show_error(f"Batch file not found: {bat}")


def _open_url(url: str) -> None:
    """Open URL in default browser."""
    webbrowser.open(url)


def _show_error(msg: str) -> None:
    """Show error in a simple message box (tkinter)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Virginia Legal AI", msg)
        root.destroy()
    except Exception:
        print(msg, file=sys.stderr)


def _create_tray_icon():
    """Create and return the tray icon with menu."""
    try:
        import pystray
        from PIL import Image
    except ImportError as e:
        print("Missing dependency. Install with: pip install pystray Pillow")
        print(str(e))
        sys.exit(1)

    # Create a simple icon: legal blue with white accent
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Background: legal blue
    draw.rectangle([0, 0, size - 1, size - 1], fill=(41, 98, 255), outline=(255, 255, 255))
    # Inner accent (scale/balance symbol)
    draw.rectangle([16, 12, 48, 52], outline=(255, 255, 255), width=3)

    # Resize for tray (typically 32x32 on Windows)
    icon_image = img.resize((32, 32), Image.Resampling.LANCZOS)

    def on_control_panel(icon, item):
        _launch_script("control_panel.py")

    def on_ingest_gui(icon, item):
        _launch_bat("RUN_INGEST_GUI.bat")

    def on_build_monitor(icon, item):
        _launch_bat("RUN_BUILD_MONITOR.bat")

    def on_open_app(icon, item):
        _open_url("http://localhost:3000")

    def on_open_api_docs(icon, item):
        _open_url("http://localhost:5001/docs")

    def on_start_system(icon, item):
        _launch_bat("START_SYSTEM.bat")

    def on_stop_system(icon, item):
        _launch_bat("STOP_SYSTEM.bat")

    def on_system_check(icon, item):
        script = PROJECT_ROOT / "scripts" / "system_check.py"
        if script.exists():
            subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0,
            )
        else:
            _show_error(f"Script not found: {script}")

    def on_exit(icon, item):
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Control Panel", on_control_panel, default=True),
        pystray.MenuItem("Ingest GUI", on_ingest_gui),
        pystray.MenuItem("Build Monitor", on_build_monitor),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open App (localhost:3000)", on_open_app),
        pystray.MenuItem("Open API Docs (localhost:5001)", on_open_api_docs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Start System", on_start_system),
        pystray.MenuItem("Stop System", on_stop_system),
        pystray.MenuItem("Run System Check", on_system_check),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit", on_exit),
    )

    icon = pystray.Icon(
        "Virginia Legal AI",
        icon_image,
        "Virginia Legal AI",
        menu,
    )
    return icon


def main():
    if sys.platform != "win32":
        print("System tray is designed for Windows. On other platforms, use the control panel directly.")
        # Could still run with pystray on Linux/macOS, but menu behavior differs
        # For now, just launch control panel as fallback
        _launch_script("control_panel.py")
        return

    icon = _create_tray_icon()
    icon.run()


if __name__ == "__main__":
    main()
