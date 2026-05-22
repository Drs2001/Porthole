import sys
import os
import shutil
import subprocess
import json
from pathlib import Path

import archinstall
from archinstall import Installer, disk, locale
from archinstall.models.users import User

from PySide6.QtWidgets import (
    QApplication, QWizard, QWizardPage,
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QProgressBar, QTextEdit, QWidget
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
            c = self.config
            self.progress.emit("Partitioning disk…")

            device = disk.fetch_disk_from_path(c["disk"])
            modifications = disk.DeviceModification(device=device, wipe=True)

            # EFI boot partition
            modifications.add_partition(disk.PartitionModification(
                status=disk.ModificationStatus.Create,
                type=disk.PartitionType.Primary,
                start=disk.Size(1, disk.Unit.MiB),
                length=disk.Size(512, disk.Unit.MiB),
                mountpoint=Path("/boot"),
                fs_type=disk.FilesystemType.Fat32,
                flags=[disk.PartitionFlag.Boot],
            ))

            # Root partition — rest of disk
            modifications.add_partition(disk.PartitionModification(
                status=disk.ModificationStatus.Create,
                type=disk.PartitionType.Primary,
                start=disk.Size(513, disk.Unit.MiB),
                length=disk.Size(100, disk.Unit.Percentage),
                mountpoint=Path("/"),
                fs_type=disk.FilesystemType.Ext4,
            ))

            disk_config = disk.DiskLayoutConfiguration(
                config_type=disk.DiskLayoutType.Default,
                device_modifications=[modifications],
            )
            disk.partition_device(disk_config)

            self.progress.emit("Mounting and installing base system…")
            with Installer(
                target=Path(c["mountpoint"]),
                disk_config=disk_config,
                kernels=["linux"],
            ) as install:
                install.mount_ordered_layout()
                install.minimal_installation(hostname=c["hostname"])

                self.progress.emit("Installing packages…")
                install.add_additional_packages([
                    # Base
                    "base-devel", "linux-headers", "sudo", "nano", "git",
                    "networkmanager", "grub", "efibootmgr", "os-prober",

                    # Hyprland stack
                    "hyprland", "uwsm", "hyprpaper", "hyprpolkitagent",
                    "hyprshot", "hyprsunset",
                    "xdg-desktop-portal-hyprland", "xdg-desktop-portal-gtk",

                    # Display manager
                    "greetd", "greetd-regreet",

                    # Audio
                    "pipewire", "pipewire-pulse", "wireplumber",

                    # Qt / theming
                    "qt6ct", "noto-fonts-emoji", "ttf-nerd-fonts-symbols",

                    # Apps
                    "btop", "chromium", "dconf-editor", "featherpad",
                    "firefox", "gnome-keyring", "gvfs-smb", "imv",
                    "kitty", "mission-center", "mpv", "nautilus",
                    "power-profiles-daemon", "quickshell", "samba",
                    "timeshift", "wiremix",

                    # Misc
                    "xdg-user-dirs",
                ])

                self.progress.emit("Creating user…")
                install.create_users(User(
                    username=c["username"],
                    password=c["password"],
                    sudo=True,
                ))

                self.progress.emit("Setting locale…")
                install.set_locale(c["locale"], c["encoding"])

                self.progress.emit("Enabling services…")
                install.enable_service("NetworkManager")
                install.enable_service("greetd")
                install.enable_service("power-profiles-daemon")

                self.progress.emit("Copying dotfiles from /etc/skel…")
                # skel is already applied by useradd; also copy greetd config
                target = Path(c["mountpoint"])
                greetd_dst = target / "etc/greetd"
                greetd_dst.mkdir(parents=True, exist_ok=True)
                for f in Path("/etc/greetd").iterdir():
                    shutil.copy2(f, greetd_dst / f.name)

                self.progress.emit("Installing bootloader…")
                install.add_bootloader(archinstall.models.bootloader.Bootloader.Grub)

            self.progress.emit("✓ Installation complete — you can reboot now.")
            self.finished.emit(True, "")

        except Exception as e:
            import traceback
            self.finished.emit(False, traceback.format_exc())


# ── Wizard pages ──────────────────────────────────────────────────────────────

class LocalePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Locale & keyboard")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.locale_combo = QComboBox()
        self.locale_combo.addItems([
            "en_US", "en_GB", "de_DE", "fr_FR", "es_ES",
            "pt_BR", "ja_JP", "zh_CN", "ko_KR",
        ])
        self.registerField("locale*", self.locale_combo, "currentText")

        self.kb_combo = QComboBox()
        self.kb_combo.addItems(["us", "uk", "de", "fr", "es", "br", "jp"])
        self.registerField("keymap*", self.kb_combo, "currentText")

        layout.addWidget(QLabel("Locale:"))
        layout.addWidget(self.locale_combo)
        layout.addSpacing(8)
        layout.addWidget(QLabel("Keyboard layout:"))
        layout.addWidget(self.kb_combo)
        layout.addStretch()


class DiskPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Disk selection")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        self.disk_combo = QComboBox()
        self._populate_disks()
        self.registerField("disk*", self.disk_combo, "currentText")

        warning = QLabel("⚠  The selected disk will be completely wiped.")
        warning.setStyleSheet("color: #ff6666; font-weight: bold;")

        layout.addWidget(QLabel("Target disk:"))
        layout.addWidget(self.disk_combo)
        layout.addSpacing(12)
        layout.addWidget(warning)
        layout.addStretch()

    def _populate_disks(self):
        try:
            result = subprocess.run(
                ["lsblk", "-J", "-o", "NAME,SIZE,TYPE,MODEL"],
                capture_output=True, text=True
            )
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
        self.log.setFont(QFont("monospace", 10))

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)

        layout.addWidget(self.log)
        layout.addWidget(self.bar)
        self._worker = None
        self._done = False

    def initializePage(self):
        w = self.wizard()
        disk_raw = w.field("disk").split()[0]

        config = {
            "disk":       disk_raw,
            "mountpoint": "/mnt",
            "hostname":   w.field("hostname"),
            "username":   w.field("username"),
            "password":   w.field("password"),
            "locale":     w.field("locale"),
            "encoding":   "UTF-8",
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


# ── Main wizard ───────────────────────────────────────────────────────────────

class InstallerWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arch Installer")
        self.setMinimumSize(860, 580)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.addPage(LocalePage())
        self.addPage(DiskPage())
        self.addPage(UserPage())
        self.addPage(InstallPage())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("arch-installer")
    wiz = InstallerWizard()
    wiz.show()
    sys.exit(app.exec())