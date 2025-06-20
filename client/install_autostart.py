#!/usr/bin/env python3

import os
from pathlib import Path

if __name__ == "__main__":
    script_path = Path(os.path.abspath(__file__)).parent / "memory_monitor.py"
    autostart_path = Path("~/.config/autostart/server-memory-monitor.desktop").expanduser()

    with open(autostart_path, "w") as f:
        f.write(f"""[Desktop Entry]
Name=Server Memory Monitor
Comment=Monitor server memory usage
Exec=python3 {script_path}
Terminal=false
Type=Application
Icon=utilities-system-monitor
Categories=System;Monitor;
StartupNotify=false
X-GNOME-Autostart-enabled=true
""")

    print(f"Script path: {script_path}")
    print(f"Installed to autostart: {autostart_path}")
    print("Server Memory Monitor will start automatically on login.")

