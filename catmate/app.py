import argparse
import hashlib
import logging
import sys
import time
from pathlib import Path
from PySide6.QtCore import QDir, QLockFile, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon
from .art import Art, load_system_fonts
from .model import Companion, Store
from .pet import PetWindow
from .platform_win import discover_apps, idle_seconds
from .ui import ControlCenter

class Application:
    def __init__(self, qt, store, quiet=False):
        self.qt, self.store = qt, store
        load_system_fonts()
        self.model = Companion(store)
        if not self.model.d["apps"]:
            self.model.d["apps"].extend(discover_apps())
        self.art = Art()
        qt.setWindowIcon(self.art.icon)
        self.pet = PetWindow(self.model, self.art)
        self._panel = None
        self.pet.open_home.connect(self.show_panel)
        self.pet.request_quit.connect(self.quit)
        self.pet.message.connect(self.show_message)
        self.pet.shortcuts_requested.connect(lambda: self.panel.navigate(5))
        self.deferred_save = QTimer(qt)
        self.deferred_save.setSingleShot(True)
        self.deferred_save.setInterval(300)
        self.deferred_save.timeout.connect(self.persist)
        self.pet.size_changed.connect(self.sync_size)
        self.pet.size_changed.connect(lambda _: self.deferred_save.start())
        self.pet.eco_changed.connect(self.sync_eco)
        self.pet.eco_changed.connect(lambda _: self.deferred_save.start())
        self.tray = QSystemTrayIcon(self.art.icon, qt)
        self.tray.setToolTip("猫在 · 你的小猫一直都在")
        menu = QMenu()
        menu.addAction("打开猫咪小屋", self.show_panel)
        menu.addAction("找到小猫", self.locate_pet)
        menu.addAction("睡个小觉", self.pet.sleep)
        menu.addAction("结束玩耍", self.pet.stop_play)
        apps_menu = menu.addMenu("打开软件")
        apps_menu.aboutToShow.connect(lambda: self.populate_apps(apps_menu))
        menu.addSeparator()
        menu.addAction("退出猫在", self.quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.tray_clicked)
        self.tray.show()
        self.pet.show()
        if not quiet:
            self.show_panel()
        self._last = time.monotonic()
        self.clock = QTimer()
        self.clock.timeout.connect(self.tick)
        self.clock.start(1000)
        self.autosave = QTimer()
        self.autosave.timeout.connect(self.persist)
        self.autosave.start(15000)
        qt.aboutToQuit.connect(self.cleanup)
        if store.recovered:
            self.show_message("原存档无法读取，已保留损坏文件并建立新存档。")
        self.persist()

    @property
    def panel(self):
        if self._panel is None:
            self._panel = ControlCenter(self.model, self.art, self.pet, self.persist)
        return self._panel

    def show_message(self, text):
        if self._panel is not None and self._panel.isVisible():
            self._panel.toast(text)
        else:
            self.pet.say(text, 7)

    def sync_size(self, value):
        if self._panel is not None:
            self._panel.sync_size(value)

    def sync_eco(self, value):
        if self._panel is not None:
            self._panel.sync_eco(value)

    def locate_pet(self):
        self.pet.show()
        area = self.pet.available()
        self.pet.move_clamped(area.bottomRight()-self.pet.rect().bottomRight())
        self.pet.say("在这里呢。摸摸我的头吧。")

    def populate_apps(self, menu):
        from .platform_win import launch_app
        menu.clear()
        def launch(path):
            try:
                launch_app(path)
            except (OSError, ValueError) as exc:
                self.pet.say(str(exc))
        for item in self.model.d["apps"]:
            menu.addAction(item["name"], lambda checked=False, path=item["path"]: launch(path))
        menu.addAction("管理快捷启动…", lambda: (self.show_panel(), self.panel.navigate(5)))

    def tray_clicked(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_panel()

    def show_panel(self):
        self.panel.showNormal()
        self.panel.raise_()
        self.panel.activateWindow()

    def tick(self):
        now = time.monotonic()
        dt, self._last = now - self._last, now
        events = self.model.tick(dt, sleeping=self.pet.state == "sleep", idle=idle_seconds() >= 300)
        if self.pet.mode and 0 < dt <= 5:
            self.model.d["joy"] = min(100, self.model.d["joy"] + dt / 20)
        for kind, title, body in events:
            if kind == "focus":
                self.pet.paused = False
                self.pet.set_state("stretch", 4)
                self.persist()
            self.pet.say(body, 10)
            if not self.model.d["settings"]["quiet"]:
                self.tray.showMessage(title, body, QSystemTrayIcon.MessageIcon.Information, 8000)

    def persist(self):
        if hasattr(self, "pet"):
            self.model.d["position"] = [self.pet.x(), self.pet.y()]
        try:
            self.store.save()
        except OSError as exc:
            logging.exception("Failed to save")
            self.show_message(f"存档暂时无法写入：{exc}")

    def cleanup(self):
        self.persist()
        self.pet.timer.stop()
        self.clock.stop()
        self.autosave.stop()
        self.deferred_save.stop()
        self.tray.hide()
        self.pet.toy.hide()

    def quit(self):
        # QApplication.quit() asks every window to close. The control center
        # deliberately ignores close (hide-to-tray), so explicit Exit must
        # bypass that veto. aboutToQuit still performs the final atomic save.
        self.qt.exit(0)

def main(argv=None):
    parser = argparse.ArgumentParser(description="猫在 · 写实桌面猫咪")
    parser.add_argument("--quiet", action="store_true", help="只显示桌宠，不打开小屋")
    parser.add_argument("--data-dir", type=Path, help="指定独立存档目录")
    parser.add_argument("--smoke-test", action="store_true", help="无交互启动检查，2 秒后退出")
    parser.add_argument("--quit", action="store_true", help="关闭同一存档目录下正在运行的小猫")
    args = parser.parse_args(argv)
    qt = QApplication(sys.argv[:1])
    qt.setApplicationName("CatMate")
    qt.setOrganizationName("CatMate")
    qt.setQuitOnLastWindowClosed(False)
    qt.setFont(QFont("Microsoft YaHei UI", 10))
    store = Store(args.data_dir)
    store.directory.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=store.directory / "catmate.log", level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    identity = hashlib.sha256(str(store.directory.resolve()).lower().encode()).hexdigest()[:16]
    server_name = f"CatMate-{identity}"
    lock = QLockFile(QDir.tempPath() + f"/{server_name}.lock")
    lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        socket = QLocalSocket()
        socket.connectToServer(server_name)
        if socket.waitForConnected(1000):
            socket.write(b"quit" if args.quit else b"show")
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
        return 0
    if args.quit:
        lock.unlock()
        return 0
    QLocalServer.removeServer(server_name)
    server = QLocalServer()
    if not server.listen(server_name):
        logging.warning("Cannot listen on local single-instance socket")
    runtime = Application(qt, store, quiet=args.quiet)
    def connection():
        socket = server.nextPendingConnection()
        if socket:
            def receive():
                command = bytes(socket.readAll()).strip()
                if command == b"quit":
                    runtime.quit()
                elif command == b"show":
                    runtime.show_panel()
                socket.disconnectFromServer()
            socket.readyRead.connect(receive)
            if socket.bytesAvailable():
                receive()
            socket.disconnected.connect(socket.deleteLater)
    server.newConnection.connect(connection)
    def exception_handler(kind, value, traceback):
        logging.error("Unhandled exception", exc_info=(kind, value, traceback))
        runtime.panel.toast(f"遇到一个问题，已记录到日志：{value}")
    sys.excepthook = exception_handler
    if args.smoke_test:
        QTimer.singleShot(2200, runtime.quit)
    result = qt.exec()
    server.close()
    lock.unlock()
    return result
