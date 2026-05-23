import sys
import json
import subprocess
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QWizard, QWizardPage, QVBoxLayout,
    QLabel, QLineEdit, QComboBox, QProgressBar,
    QTextEdit, QPushButton
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QFont


# ── Install worker ────────────────────────────────────────────────────────────

class InstallWorker(QThread):
    progress = Signal(str)
    finished = Signal(bool, str)

    def __init__(self, config: dict):
        super().__init__()
        self.config = config

    def run(self):
        try:
            import time
            from archinstall.lib.args import ArchConfigHandler
            from archinstall.lib.disk.filesystem import FilesystemHandler
            from archinstall.lib.installer import Installer
            from archinstall.lib.mirror.mirror_handler import MirrorListHandler
            from archinstall.lib.authentication.authentication_handler import AuthenticationHandler
            from archinstall.lib.applications.application_handler import ApplicationHandler
            from archinstall.lib.models import Bootloader
            from archinstall.lib.models.users import User
            from archinstall.lib.output import info

            c = self.config

            # Build archinstall config as JSON and pass via --config
            config_data = {
                "hostname": c["hostname"],
                "kernels": ["linux"],
                "packages": [
                    "base-devel", "git", "nano",
                    "hyprland", "uwsm", "hyprpaper", "hyprpolkitagent",
                    "hyprshot", "hyprsunset",
                    "xdg-desktop-portal-hyprland", "xdg-desktop-portal-gtk",
                    "greetd", "greetd-regreet",
                    "pipewire", "pipewire-pulse", "wireplumber",
                    "qt6ct", "noto-fonts-emoji", "ttf-nerd-fonts-symbols",
                    "btop", "chromium", "dconf-editor", "featherpad",
                    "firefox", "gnome-keyring", "gvfs-smb", "imv",
                    "kitty", "mission-center", "mpv", "nautilus",
                    "power-profiles-daemon", "quickshell", "samba",
                    "timeshift", "wiremix", "xdg-user-dirs", "os-prober",
                ],
                "services": ["NetworkManager", "greetd", "power-profiles-daemon"],
                "timezone": c["timezone"],
                "bootloader": "grub",
                "mirror_config": {
                    "mirror_regions": {
                        "Worldwide": ["https://geo.mirror.pkgbuild.com/$repo/os/$arch"]
                    }
                },
            }

            # Write config to temp file
            config_path = Path("/tmp/archinstall-config.json")
            creds_path = Path("/tmp/archinstall-creds.json")

            config_path.write_text(json.dumps(config_data))

            creds_data = {
                "!users": [
                    {
                        "username": c["username"],
                        "!password": c["password"],
                        "sudo": True
                    }
                ]
            }
            creds_path.write_text(json.dumps(creds_data))

            self.progress.emit("Building disk layout...")

            # Use archinstall CLI in silent mode with our config
            # This is the most stable way to drive archinstall 4.x
            cmd = [
                "python3", "-m", "archinstall",
                "--config", str(config_path),
                "--creds", str(creds_path),
                "--disk-layouts", json.dumps(self._build_disk_layout(c["disk"])),
                "--silent",
            ]

            self.progress.emit("Starting installation...")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            for line in process.stdout:
                self.progress.emit(line.strip())

            process.wait()

            if process.returncode != 0:
                self.finished.emit(False, f"archinstall exited with code {process.returncode}")
                return

            # Copy dotfiles from skel to new user's home
            self.progress.emit("Copying dotfiles...")
            user_home = Path(f"/mnt/home/{c['username']}")
            skel = Path("/etc/skel")
            if skel.exists() and user_home.exists():
                import shutil
                for item in skel.iterdir():
                    dst = user_home / item.name
                    if item.is_dir():
                        if dst.exists():
                            shutil.rmtree(dst)
                        shutil.copytree(item, dst)
                    else:
                        shutil.copy2(item, dst)
                # Fix ownership
                uid_gid = f"{1000}:{1000}"
                subprocess.run(["chown", "-R", uid_gid, str(user_home)])

            self.progress.emit("✓ Installation complete — you can reboot now.")
            self.finished.emit(True, "")

        except Exception as e:
            import traceback
            self.finished.emit(False, traceback.format_exc())

    def _build_disk_layout(self, disk: str) -> list:
        return [
            {
                "device": disk,
                "wipe": True,
                "partitions": [
                    {
                        "boot": True,
                        "esp": True,
                        "mountpoint": "/boot",
                        "size": "512MiB",
                        "fs_type": "fat32",
                    },
                    {
                        "mountpoint": "/",
                        "size": "100%",
                        "fs_type": "ext4",
                    }
                ]
            }
        ]


# ── Pages ─────────────────────────────────────────────────────────────────────

class LocalePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Locale & timezone")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.locale_combo = QComboBox()
        self.locale_combo.addItems(["en_US", "en_GB", "de_DE", "fr_FR", "es_ES", "pt_BR"])
        self.registerField("locale*", self.locale_combo, "currentText")

        self.tz_combo = QComboBox()
        self.tz_combo.addItems([
            "UTC", "America/New_York", "America/Chicago",
            "America/Denver", "America/Los_Angeles",
            "Europe/London", "Europe/Berlin", "Europe/Paris",
            "Asia/Tokyo", "Asia/Shanghai", "Australia/Sydney",
        ])
        self.registerField("timezone*", self.tz_combo, "currentText")

        layout.addWidget(QLabel("Locale:"))
        layout.addWidget(self.locale_combo)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Timezone:"))
        layout.addWidget(self.tz_combo)
        layout.addStretch()


class DiskPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Disk selection")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.disk_combo = QComboBox()
        self._populate()
        self.registerField("disk*", self.disk_combo, "currentText")

        warning = QLabel("⚠  The selected disk will be completely wiped.")
        warning.setStyleSheet("color: #ff6666; font-weight: bold;")

        layout.addWidget(QLabel("Target disk:"))
        layout.addWidget(self.disk_combo)
        layout.addSpacing(12)
        layout.addWidget(warning)
        layout.addStretch()

    def _populate(self):
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MODEL"],
                capture_output=True, text=True
            )
            import json
            for dev in json.loads(result.stdout)["blockdevices"]:
                if dev["type"] == "disk":
                    model = dev.get("model") or ""
                    self.disk_combo.addItem(
                        f"/dev/{dev['name']}  {dev['size']}  {model}".strip()
                    )
        except Exception:
            self.disk_combo.addItems(["/dev/sda", "/dev/nvme0n1"])


class UserPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("User account & hostname")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.hostname = QLineEdit("archlinux")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password2 = QLineEdit()
        self.password2.setEchoMode(QLineEdit.EchoMode.Password)

        self.registerField("hostname*", self.hostname)
        self.registerField("username*", self.username)
        self.registerField("password*", self.password)

        for label, widget in [
            ("Hostname:", self.hostname),
            ("Username:", self.username),
            ("Password:", self.password),
            ("Confirm password:", self.password2),
        ]:
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)

        self.err = QLabel("")
        self.err.setStyleSheet("color: #ff6666;")
        layout.addWidget(self.err)
        layout.addStretch()

    def validatePage(self):
        if self.password.text() != self.password2.text():
            self.err.setText("Passwords do not match.")
            return False
        if len(self.password.text()) < 6:
            self.err.setText("Password must be at least 6 characters.")
            return False
        self.err.setText("")
        return True


class InstallPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Installing")
        self.setCommitPage(True)
        layout = QVBoxLayout(self)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setFont(QFont("monospace", 9))

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)

        layout.addWidget(self.log)
        layout.addWidget(self.bar)
        self._done = False

    def initializePage(self):
        w = self.wizard()
        disk_raw = w.field("disk").split()[0]

        config = {
            "disk":     disk_raw,
            "hostname": w.field("hostname"),
            "username": w.field("username"),
            "password": w.field("password"),
            "locale":   w.field("locale"),
            "timezone": w.field("timezone"),
        }

        self._worker = InstallWorker(config)
        self._worker.progress.connect(self.log.append)
        self._worker.finished.connect(self._on_done)
        self._worker.start()

    def _on_done(self, ok: bool, err: str):
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        if not ok:
            self.log.append(f"\n✗ Error:\n{err}")
        self._done = True
        self.completeChanged.emit()

    def isComplete(self):
        return self._done


# ── Wizard ────────────────────────────────────────────────────────────────────

class InstallerWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Porthole Installer")
        self.setMinimumSize(860, 580)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.addPage(LocalePage())
        self.addPage(DiskPage())
        self.addPage(UserPage())
        self.addPage(InstallPage())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("porthole-installer")
    wiz = InstallerWizard()
    wiz.show()
    sys.exit(app.exec())