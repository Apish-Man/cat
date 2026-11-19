"""Warm native control center. All purchases and actions share the domain model."""
import math
import time
from datetime import date, timedelta
from pathlib import Path
from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QPainter, QPen, QPixmap, QIcon, QPainterPath
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDateEdit, QDoubleSpinBox, QFileDialog,
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider,
    QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QHeaderView,
)
from .art import STATE_NAMES
from .catalog import ITEMS, gifts_today
from .model import duration_text
from .platform_win import discover_apps, launch_app, set_startup, startup_enabled

STYLE = """
QWidget { font-family:'Microsoft YaHei UI','Segoe UI'; font-size:13px; color:#57483e; }
QMainWindow, #base { background:#faf7f0; }
#sidebar { background:#f0e9df; border-right:1px solid #e7dfd3; }
#brand { font-size:27px; font-weight:700; color:#63513f; }
#tagline { font-size:11px; color:#a3917d; letter-spacing:1px; }
#pageTitle { font-size:26px; font-weight:700; color:#4d4035; }
#muted { color:#9a8b7b; font-size:12px; }
#sectionTitle { font-size:16px; font-weight:600; color:#5c4a3b; }
#bigNumber { font-size:27px; font-weight:600; color:#6f8060; }
#wallet { background:#eee8d6; border-radius:16px; padding:8px 16px; color:#7b724b; font-weight:600; }
#statusPill { background:#eaf0e2; color:#7b8c68; border-radius:12px; padding:6px 12px; font-size:11px; }
#card { background:#fffdf9; border:1px solid #e9e2d6; border-radius:16px; }
#hero { background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #eee7d7,stop:1 #f5eddf); border:1px solid #e4dbc9; border-radius:20px; }
#heroTitle { font-size:30px; font-weight:600; color:#5b4b3a; }
#heroSub { color:#92806b; font-size:13px; }
#toast { background:#6f7e60; color:white; padding:10px 16px; border-radius:12px; }
QPushButton { background:#f0e9df; border:1px solid #e7ddce; border-radius:9px; padding:8px 15px; color:#71604e; min-height:18px; }
QPushButton:hover { background:#e9dfce; border-color:#cebea5; }
QPushButton:pressed { background:#ded2bf; }
QPushButton:disabled { color:#b7ac9f; background:#f6f1e9; border-color:#eee7dc; }
QPushButton[primary="true"] { background:#7b8b68; color:#fffdf7; border:1px solid #7b8b68; }
QPushButton[primary="true"]:hover { background:#6b7b59; }
QPushButton[primary="true"]:disabled { background:#bac2af; border-color:#bac2af; }
QPushButton[nav="true"] { text-align:left; border:0; background:transparent; padding:12px 18px; border-radius:10px; font-size:14px; }
QPushButton[nav="true"]:checked { background:#fffaf1; color:#73805f; font-weight:600; }
QPushButton[nav="true"]:hover { background:#e8dfd1; }
QProgressBar { background:#eee8dc; border:0; border-radius:4px; max-height:7px; min-height:7px; }
QProgressBar::chunk { background:#b3be98; border-radius:4px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit { background:#fffdf9; border:1px solid #dfd5c5; padding:7px; border-radius:7px; min-height:21px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color:#8d9a77; }
QCheckBox { spacing:10px; padding:5px 0; }
QCheckBox::indicator { width:18px; height:18px; border:1px solid #d5c9b7; background:#fffdf9; border-radius:5px; }
QCheckBox::indicator:checked { background:#8b9b75; border:4px solid #c9d2ba; }
QSlider::groove:horizontal { height:5px; background:#e4dccd; border-radius:2px; }
QSlider::handle:horizontal { width:16px; background:#8c9c76; margin:-6px 0; border-radius:8px; }
QScrollArea { border:0; background:transparent; }
QScrollArea > QWidget > QWidget { background:#faf7f0; }
QScrollBar:vertical { width:7px; background:transparent; margin:0; }
QScrollBar::handle:vertical { background:#d9cfbd; border-radius:3px; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QTableWidget { background:#fffdf9; gridline-color:#eee5d8; border:0; border-radius:10px; selection-background-color:#ede8d9; }
QHeaderView::section { background:#f1ebdf; border:0; padding:10px; color:#8d7c68; }
QListWidget { background:#fffdf9; border:1px solid #e5dccd; border-radius:10px; padding:6px; }
QListWidget::item { padding:12px; border-radius:6px; }
QListWidget::item:selected { background:#e9eddf; color:#687c50; }
QToolTip { background:#fffaf2; color:#695646; padding:6px; border:1px solid #ddd0bc; }
"""

def label(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w

def button(text, callback=None, primary=False, name=""):
    w = QPushButton(text)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    w.setProperty("primary", primary)
    if name:
        w.setObjectName(name)
    if callback:
        w.clicked.connect(callback)
    return w

def card(title=None):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(20, 18, 20, 18)
    layout.setSpacing(12)
    if title:
        layout.addWidget(label(title, "sectionTitle"))
    return frame, layout

def nav_icon(index):
    """Code-native line icons, independent of the installed symbol fonts."""
    from PySide6.QtCore import QPointF
    pix = QPixmap(24, 24)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#8b8068"), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if index == 0:
        path = QPainterPath(QPointF(3, 11)); path.lineTo(12, 3); path.lineTo(21, 11)
        p.drawPath(path); p.drawRoundedRect(QRectF(6, 10, 12, 11), 1, 1)
        p.drawLine(10, 21, 10, 15); p.drawLine(10, 15, 14, 15); p.drawLine(14, 15, 14, 21)
    elif index == 1:
        path = QPainterPath(QPointF(12, 21)); path.cubicTo(1, 14, 1, 4, 7, 4)
        path.cubicTo(10, 4, 12, 7, 12, 7); path.cubicTo(14, 3, 21, 2, 21, 9)
        path.cubicTo(21, 14, 16, 18, 12, 21); p.drawPath(path)
    elif index == 2:
        p.drawEllipse(QRectF(4, 6, 16, 14)); p.drawArc(QRectF(6, 6, 16, 12), 70*16, 180*16)
        p.drawLine(4, 17, 1, 22); p.drawLine(8, 6, 15, 20)
    elif index == 3:
        path = QPainterPath(QPointF(7, 8)); path.lineTo(12, 5); path.lineTo(17, 8)
        path.lineTo(22, 12); path.lineTo(18, 15); path.lineTo(17, 12); path.lineTo(17, 21)
        path.lineTo(7, 21); path.lineTo(7, 12); path.lineTo(6, 15); path.lineTo(2, 12); path.closeSubpath()
        p.drawPath(path); p.drawArc(QRectF(9, 3, 6, 7), 180*16, 180*16)
    elif index == 4:
        p.drawEllipse(QRectF(3, 3, 18, 18)); p.drawLine(12, 6, 12, 12); p.drawLine(12, 12, 17, 14)
    elif index == 5:
        p.drawRoundedRect(QRectF(3, 8, 13, 13), 2, 2); p.drawLine(10, 14, 21, 3)
        p.drawLine(15, 3, 21, 3); p.drawLine(21, 3, 21, 9)
    else:
        for y, x in [(5, 8), (12, 16), (19, 10)]:
            p.drawLine(3, y, 21, y); p.setBrush(QColor("#f0e9df")); p.drawEllipse(QPointF(x, y), 2.5, 2.5)
    p.end()
    return QIcon(pix)

class CatPreview(QWidget):
    def __init__(self, art, model, outfit=None, size=240):
        super().__init__()
        self.art, self.model, self.outfit = art, model, outfit
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        outfit = self.model.d["outfit"] if self.outfit is None else self.outfit
        self.art.draw(p, QRectF(5, 20, self.width()-10, self.height()-22), "idle", time.monotonic() % 8, outfit=outfit, preview=True)

class FocusDial(QWidget):
    def __init__(self, model):
        super().__init__()
        self.model = model
        self.setFixedSize(218, 218)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(14, 14, 190, 190)
        p.setPen(QPen(QColor("#eee8db"), 9))
        p.drawEllipse(rect)
        m = self.model
        total = m.focus_duration or m.d["settings"]["focus_minutes"] * 60
        remaining = m.focus_remaining or m.d["settings"]["focus_minutes"] * 60
        progress = (total - remaining) / total if m.focus_remaining else 0
        p.setPen(QPen(QColor("#93a17a"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 90*16, -round(360*16*progress))
        p.setPen(QColor("#61714e"))
        p.setFont(QFont("Segoe UI", 32, QFont.Weight.Light))
        text = f"{math.ceil(remaining)//60:02d}:{math.ceil(remaining)%60:02d}"
        p.drawText(QRectF(10, 72, 198, 60), Qt.AlignmentFlag.AlignCenter, text)
        p.setFont(QFont("Microsoft YaHei UI", 10))
        p.setPen(QColor("#a19682"))
        p.drawText(QRectF(10, 127, 198, 30), Qt.AlignmentFlag.AlignCenter,
                   "休息一下也很好" if m.focus_paused else "小猫陪你专注")

class ControlCenter(QMainWindow):
    def __init__(self, model, art, pet, persist):
        super().__init__()
        self.model, self.art, self.pet, self.persist = model, art, pet, persist
        self.setObjectName("controlCenter")
        self.setWindowTitle("猫在 · 你的桌面小猫")
        self.setWindowIcon(art.icon)
        self.resize(1040, 760)
        self.setMinimumSize(900, 650)
        self.setStyleSheet(STYLE)
        self._products = []
        self._previews = []
        self._stats = []
        self._nav = []
        base = QWidget()
        base.setObjectName("base")
        self.setCentralWidget(base)
        root = QHBoxLayout(base)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(185)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(16, 28, 16, 22)
        side.setSpacing(8)
        side.addWidget(label("猫在  ˘", "brand"))
        side.addWidget(label("A LITTLE EVERYDAY JOY", "tagline"))
        side.addSpacing(26)
        pages = ["今日陪伴", "喂食照顾", "一起玩耍", "猫咪衣橱", "工作与专注", "快捷启动", "偏好设置"]
        for i, text in enumerate(pages):
            b = button(text, lambda checked=False, n=i: self.navigate(n), name=f"nav{i}")
            b.setProperty("nav", True)
            b.setIcon(nav_icon(i))
            from PySide6.QtCore import QSize
            b.setIconSize(QSize(20, 20))
            b.setCheckable(True)
            self._nav.append(b)
            side.addWidget(b)
        side.addStretch()
        side.addWidget(label("一只猫的生活哲学\n认真工作，也认真打盹。", "muted", True))
        side.addSpacing(12)
        side.addWidget(button("回到小猫身边", self.locate_pet))
        root.addWidget(self.sidebar)
        right = QWidget()
        content = QVBoxLayout(right)
        content.setContentsMargins(28, 25, 28, 16)
        content.setSpacing(16)
        header = QHBoxLayout()
        self.title_label = label("今日陪伴", "pageTitle")
        header.addWidget(self.title_label)
        header.addStretch()
        self.status_pill = label("● 小猫在线", "statusPill")
        header.addWidget(self.status_pill)
        self.wallet = label("", "wallet")
        self.wallet.setToolTip("猫爪币是应用内积分，可兑换食物、玩具和装扮。")
        header.addWidget(self.wallet)
        content.addLayout(header)
        self.stack = QStackedWidget()
        content.addWidget(self.stack, 1)
        self.toast_label = label("", "toast")
        self.toast_label.hide()
        content.addWidget(self.toast_label)
        self.toast_timer = QTimer(self)
        self.toast_timer.setSingleShot(True)
        self.toast_timer.timeout.connect(self.toast_label.hide)
        content.addWidget(label("本地陪伴 · 自动存档     /     双击小猫打开小屋，右键查看更多互动", "muted"))
        root.addWidget(right, 1)
        self.home_page()
        self.food_page()
        self.play_page()
        self.wardrobe_page()
        self.work_page()
        self.apps_page()
        self.settings_page()
        self.navigate(0)
        self.refresh(force=True)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.setInterval(1000)

    def page(self, subtitle):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 8, 8)
        layout.setSpacing(18)
        layout.addWidget(label(subtitle, "muted", True))
        scroll.setWidget(body)
        self.stack.addWidget(scroll)
        return layout

    def navigate(self, index):
        titles = ["今日陪伴", "喂食照顾", "一起玩耍", "猫咪衣橱", "工作与专注", "快捷启动", "偏好设置"]
        self.stack.setCurrentIndex(index)
        self.title_label.setText(titles[index])
        for i, b in enumerate(self._nav):
            b.setChecked(i == index)
        if index == 4:
            self.refresh_history()
        self.refresh()

    def toast(self, text):
        self.toast_label.setText(text)
        self.toast_label.show()
        self.toast_timer.start(5000)

    def save(self):
        self.persist()
        self.refresh()

    def locate_pet(self):
        self.pet.show()
        screen = self.screen().availableGeometry()
        self.pet.move_clamped(screen.bottomRight() - self.pet.rect().bottomRight())
        self.pet.say("在这里呢。摸摸我的头吧。")
        self.toast("小猫在屏幕右下角。")

    def home_page(self):
        layout = self.page("给忙碌的日常，留一个软乎乎的角落。")
        hero = QFrame()
        hero.setObjectName("hero")
        h = QHBoxLayout(hero)
        h.setContentsMargins(28, 12, 18, 12)
        words = QVBoxLayout()
        words.addStretch()
        words.addWidget(label("THE SOFTEST PART OF YOUR DAY", "tagline"))
        self.greeting = label("", "heroTitle")
        words.addWidget(self.greeting)
        words.addWidget(label("你负责闪闪发光，\n我负责陪在身旁。", "heroSub"))
        words.addSpacing(14)
        buttons = QHBoxLayout()
        buttons.addWidget(button("摸摸头  ♡", self.pet.pet_head, True, "petHead"))
        buttons.addWidget(button("陪它玩一会", lambda: self.navigate(2)))
        buttons.addStretch()
        words.addLayout(buttons)
        words.addStretch()
        h.addLayout(words, 1)
        preview = CatPreview(self.art, self.model, size=230)
        self._previews.append(preview)
        h.addWidget(preview)
        layout.addWidget(hero)
        row = QHBoxLayout()
        for key, title, color in [("hunger", "饱饱的小肚子", "#c6a57d"), ("joy", "今天的好心情", "#a4b388"), ("energy", "小猫的电量", "#c3b0a4")]:
            frame, box = card(title)
            number = label("", "bigNumber")
            progress = QProgressBar()
            progress.setTextVisible(False)
            progress.setStyleSheet(f"QProgressBar::chunk{{background:{color};border-radius:4px;}}")
            box.addWidget(number)
            box.addWidget(progress)
            self._stats.append((key, number, progress))
            row.addWidget(frame)
        layout.addLayout(row)
        bottom = QHBoxLayout()
        f, b = card("今天，也有好好工作")
        self.home_work = label("00:00:00", "bigNumber")
        b.addWidget(self.home_work)
        self.home_income = label("预计收入 ¥0.00  ·  小猫会为你记着", "muted")
        b.addWidget(self.home_income)
        self.home_work_button = button("开始上班", self.toggle_work, True, "homeStartWork")
        b.addWidget(self.home_work_button)
        bottom.addWidget(f)
        f, b = card("小猫此刻")
        self.cat_state = label("睡醒啦", "bigNumber")
        b.addWidget(self.cat_state)
        self.bond_text = label("", "muted")
        b.addWidget(self.bond_text)
        b.addWidget(button("让它睡一会", self.pet.sleep))
        bottom.addWidget(f)
        layout.addLayout(bottom)
        layout.addStretch()

    def product_card(self, item_id, layout_grid, row, col):
        item = ITEMS[item_id]
        frame, box = card()
        if item["kind"] == "outfit":
            preview = CatPreview(self.art, self.model, item_id, size=170)
            self._previews.append(preview)
            box.addWidget(preview, 0, Qt.AlignmentFlag.AlignHCenter)
        else:
            icon = label(item["icon"])
            icon.setStyleSheet("font-size:34px; background:#f6efe2; border-radius:12px; padding:12px;")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.addWidget(icon)
        box.addWidget(label(item["name"], "sectionTitle"))
        box.addWidget(label(item["desc"], "muted", True))
        box.addStretch()
        stock = label("", "muted")
        box.addWidget(stock)
        purchase = button(f"{item['price']} 币 · 兑换", lambda checked=False, k=item_id: self.purchase(k), name=f"buy_{item_id}")
        box.addWidget(purchase)
        if item["kind"] == "food":
            use = button("喂给小猫", lambda checked=False, k=item_id: self.feed(k), True, f"use_{item_id}")
        elif item["kind"] == "toy":
            use = button("开始互动", lambda checked=False, k=item_id: self.play(k), True, f"use_{item_id}")
        else:
            use = button("穿上这套", lambda checked=False, k=item_id: self.equip(k), True, f"use_{item_id}")
        box.addWidget(use)
        self._products.append((item_id, stock, purchase, use))
        layout_grid.addWidget(frame, row, col)

    def food_page(self):
        layout = self.page("好吃的值得慢慢享用。每天补一点粮，再摸摸小脑袋。")
        f, box = card()
        box.addWidget(label("猫爪币小铺", "sectionTitle"))
        box.addWidget(label("工作每满 1 分钟 +2 币，完成一轮专注 +50 币。所有兑换只使用猫爪币。", "muted", True))
        layout.addWidget(f)
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, key in enumerate(k for k, v in ITEMS.items() if v["kind"] == "food"):
            self.product_card(key, grid, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addStretch()

    def purchase(self, key):
        ok, message = self.model.buy(key)
        self.toast(message)
        if ok:
            self.save()

    def feed(self, key):
        ok, message = self.model.feed(key)
        self.toast(message)
        if ok:
            self.pet.stop_play(silent=True)
            self.pet.set_state("eat", 7)
            self.pet.say(message)
            self.save()

    def play_page(self):
        layout = self.page("把工作放一放，一起做一点没有目的的小事。")
        f, b = card("怎么玩")
        b.addWidget(label("毛线球：点击桌面抛球，小猫会追，有时叼走藏起来。\n逗猫棒 / 激光笔：让鼠标慢慢移动，引诱它扑过去。\n按 Esc 随时结束互动；拖拎小猫也会结束。", "muted", True))
        b.addWidget(button("结束当前互动", self.pet.stop_play, name="stopPlay"))
        layout.addWidget(f)
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, key in enumerate(k for k, v in ITEMS.items() if v["kind"] == "toy"):
            self.product_card(key, grid, i // 2, i % 2)
        layout.addLayout(grid)
        layout.addStretch()

    def play(self, key):
        if not self.model.d["inventory"].get(key):
            self.toast("先兑换这个玩具，再和小猫玩吧。")
            return
        if self.model.focus_remaining and not self.model.focus_paused:
            self.toast("正在专注，先暂停或结束本轮，再和小猫玩吧。")
            return
        self.pet.start_play(key)
        self.hide()

    def wardrobe_page(self):
        layout = self.page("参考你的照片做的小衣橱。帽子、围兜，和一点点仪式感。")
        top = QHBoxLayout()
        top.addWidget(label("柔软针织 · 四季都可爱", "sectionTitle"))
        top.addStretch()
        top.addWidget(button("脱下装扮", lambda: self.equip(""), name="unequip"))
        layout.addLayout(top)
        self.gift_button = button("领取今天的节日礼物", self.claim_gifts, True, "claimGift")
        layout.addWidget(self.gift_button)
        grid = QGridLayout()
        grid.setSpacing(14)
        for i, key in enumerate(k for k, v in ITEMS.items() if v["kind"] == "outfit"):
            self.product_card(key, grid, i // 3, i % 3)
        layout.addLayout(grid)
        layout.addStretch()

    def equip(self, key):
        if self.model.equip(key):
            self.pet.say("今天穿这套，怎么样？" if key else "还是毛茸茸的自己最舒服。")
            self.toast(f"已穿上{ITEMS[key]['name']}。" if key else "已经脱下装扮。")
            self.save()
        else:
            self.toast("先兑换这套装扮吧。")

    def claim_gifts(self):
        received = []
        for item_id in gifts_today(date.today(), self.model.d["settings"]["birthday"]):
            if self.model.claim_gift(item_id):
                received.append(ITEMS[item_id]["name"])
        self.toast("节日快乐！获得：" + "、".join(received) if received else "今天的礼物已经收好啦。")
        self.save()

    def work_page(self):
        layout = self.page("把认真工作的时间变成记录，也变成小猫的零食。")
        row = QHBoxLayout()
        f, b = card("今日工作")
        self.work_time = label("", "bigNumber")
        self.work_time.setStyleSheet("font-size:34px; color:#71815d;")
        b.addWidget(self.work_time)
        self.work_money = label("", "sectionTitle")
        b.addWidget(self.work_money)
        self.work_status = label("", "muted", True)
        b.addWidget(self.work_status)
        salary_row = QHBoxLayout()
        salary_row.addWidget(label("时薪 ¥", "muted"))
        self.salary = QDoubleSpinBox()
        self.salary.setRange(0, 100000)
        self.salary.setValue(self.model.d["settings"]["salary"])
        self.salary.setDecimals(2)
        self.salary.valueChanged.connect(lambda v: self.setting("salary", float(v)))
        salary_row.addWidget(self.salary)
        salary_row.addStretch()
        b.addLayout(salary_row)
        b.addWidget(label("收入按记录时的时薪估算，历史收入保持原值。", "muted", True))
        self.work_toggle = button("开始上班", self.toggle_work, True, "startWork")
        b.addWidget(self.work_toggle)
        row.addWidget(f, 1)
        f, b = card("一段安静的专注")
        self.focus_dial = FocusDial(self.model)
        b.addWidget(self.focus_dial, 0, Qt.AlignmentFlag.AlignHCenter)
        fr = QHBoxLayout()
        fr.addWidget(label("时长（分钟）", "muted"))
        self.focus_minutes = QSpinBox()
        self.focus_minutes.setRange(1, 180)
        self.focus_minutes.setValue(int(self.model.d["settings"]["focus_minutes"]))
        self.focus_minutes.valueChanged.connect(lambda v: self.setting("focus_minutes", v))
        fr.addWidget(self.focus_minutes)
        b.addLayout(fr)
        actions = QHBoxLayout()
        self.focus_button = button("开始专注", self.toggle_focus, True, "startFocus")
        actions.addWidget(self.focus_button)
        self.focus_stop = button("结束", self.cancel_focus, name="cancelFocus")
        actions.addWidget(self.focus_stop)
        b.addLayout(actions)
        b.addWidget(label("专注时小猫安静休息；完成 +50 币。", "muted", True))
        row.addWidget(f, 1)
        layout.addLayout(row)
        f, b = card("最近七天")
        self.history_table = QTableWidget(7, 4)
        self.history_table.setHorizontalHeaderLabels(["日期", "工作时长", "预计收入", "完成专注"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.verticalHeader().hide()
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setMinimumHeight(260)
        b.addWidget(self.history_table)
        b.addWidget(button("导出全部工作记录 CSV", self.export_history, name="exportHistory"))
        layout.addWidget(f)

    def toggle_work(self):
        self.model.working = not self.model.working
        self.pet.say("开始上班啦，我陪你。" if self.model.working else "辛苦啦。今天也有好好生活。")
        self.save()

    def toggle_focus(self):
        m = self.model
        if m.focus_remaining:
            m.focus_paused = not m.focus_paused
            if not m.focus_paused:
                self.pet.stop_play(silent=True)
                self.pet.paused = True
                self.pet.set_state("sleep", m.focus_remaining + 10)
        else:
            m.start_focus()
            self.pet.stop_play(silent=True)
            self.pet.paused = True
            self.pet.set_state("sleep", m.focus_remaining + 10)
            self.pet.say("你专心，我安静陪着。", 4)
        self.refresh()

    def cancel_focus(self):
        self.model.focus_remaining = 0
        self.model.focus_paused = False
        self.pet.paused = False
        self.pet.set_state("stretch", 4)
        self.toast("本轮专注已结束；未完成的轮次不发放奖励。")
        self.refresh()

    def refresh_history(self):
        for row in range(7):
            day = date.today() - timedelta(days=row)
            r = self.model.d["history"].get(day.isoformat(), {})
            values = [day.strftime("%m / %d"), duration_text(r.get("seconds", 0)),
                      f"¥ {r.get('income', 0):.2f}", f"{r.get('focus', 0)} 轮"]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.history_table.setItem(row, col, item)

    def export_history(self):
        import csv
        path, _ = QFileDialog.getSaveFileName(self, "导出工作记录", f"猫在-工作记录-{date.today()}.csv", "CSV 文件 (*.csv)")
        if path:
            try:
                with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["日期", "工作秒数", "工作时长", "预计收入(元)", "专注轮数"])
                    for day, r in sorted(self.model.d["history"].items()):
                        writer.writerow([day, round(r["seconds"], 2), duration_text(r["seconds"]), round(r["income"], 2), r["focus"]])
                self.toast("工作记录已导出。")
            except OSError as exc:
                self.toast(f"导出失败：{exc}")

    def apps_page(self):
        layout = self.page("把常用软件交给小猫。右键桌面小猫 → 快捷启动，即可直接打开。")
        f, b = card("常用软件")
        b.addWidget(label("这里配置软件；启动时右键桌面小猫 → 快捷启动。支持 .exe 和 .lnk 快捷方式。", "muted", True))
        self.app_list = QListWidget()
        self.app_list.setMinimumHeight(220)
        b.addWidget(self.app_list)
        r = QHBoxLayout()
        r.addWidget(button("到小猫右键启动", self.locate_pet, True, "locateForLaunch"))
        r.addWidget(button("添加软件", self.add_app, name="addApp"))
        r.addWidget(button("移除", self.remove_app))
        b.addLayout(r)
        b.addWidget(button("查找已安装的豆包", self.find_doubao, name="findDoubao"))
        layout.addWidget(f)
        f, b = card("还没有安装豆包？")
        b.addWidget(label("也可以将豆包网页版添加到小猫的右键菜单。", "muted", True))
        b.addWidget(button("添加豆包网页版到右键", self.add_doubao_web))
        layout.addWidget(f)
        layout.addStretch()
        if not self.model.d["apps"]:
            self.model.d["apps"].extend(discover_apps())
        self.refresh_apps()

    def refresh_apps(self):
        self.app_list.clear()
        for app in self.model.d["apps"]:
            self.app_list.addItem(f"↗  {app['name']}\n    {app['path']}")
        if self.app_list.count():
            self.app_list.setCurrentRow(0)

    def add_app(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择软件或快捷方式", "", "软件 (*.exe *.lnk *.appref-ms)")
        if path:
            if any(a["path"].lower() == path.lower() for a in self.model.d["apps"]):
                self.toast("这个软件已经添加过啦。")
                return
            self.model.d["apps"].append({"name": Path(path).stem, "path": path})
            self.refresh_apps()
            self.save()

    def remove_app(self):
        row = self.app_list.currentRow()
        if row >= 0:
            self.model.d["apps"].pop(row)
            self.refresh_apps()
            self.save()

    def add_doubao_web(self):
        path = "https://www.doubao.com/"
        if not any(app["path"] == path for app in self.model.d["apps"]):
            self.model.d["apps"].append({"name": "豆包网页版", "path": path})
            self.refresh_apps()
            self.save()
        self.toast("已添加。右键小猫 → 快捷启动 → 豆包网页版。")

    def open_selected_app(self):
        row = self.app_list.currentRow()
        if row < 0:
            self.toast("先添加或选中一个软件吧。")
            return
        app = self.model.d["apps"][row]
        try:
            launch_app(app["path"])
            self.pet.say(f"给你打开{app['name']}啦。")
        except (OSError, ValueError) as exc:
            self.toast(str(exc))

    def find_doubao(self):
        apps = discover_apps()
        if apps:
            for app in apps:
                if not any(a["path"].lower() == app["path"].lower() for a in self.model.d["apps"]):
                    self.model.d["apps"].append(app)
            self.refresh_apps()
            self.save()
            self.toast("找到豆包啦，选中它就能打开。")
        else:
            self.toast("常见安装位置没有找到豆包，可通过“添加软件”手动选择快捷方式。")

    def settings_page(self):
        layout = self.page("调整成你喜欢的陪伴方式。设置会自动保存在这台电脑。")
        f, b = card("关于这只小猫")
        r = QHBoxLayout()
        r.addWidget(label("小猫名字"))
        name = QLineEdit(self.model.d["name"])
        name.setObjectName("catName")
        name.setMaxLength(12)
        name.editingFinished.connect(lambda: self.rename_cat(name))
        r.addWidget(name)
        b.addLayout(r)
        r = QHBoxLayout()
        r.addWidget(label("生日（月-日）"))
        birthday = QDateEdit()
        from PySide6.QtCore import QDate
        month, day = map(int, self.model.d["settings"]["birthday"].split("-"))
        birthday.setDate(QDate(2000, month, day))
        birthday.setDisplayFormat("MM-dd")
        birthday.setCalendarPopup(True)
        birthday.dateChanged.connect(lambda value: self.setting("birthday", value.toString("MM-dd")))
        r.addWidget(birthday)
        b.addLayout(r)
        b.addWidget(label("生日当天可免费领取生日套装，也可以提前在衣橱兑换。", "muted", True))
        r = QHBoxLayout()
        r.addWidget(label("猫咪大小"))
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setObjectName("petSize")
        self.size_slider.setRange(50, 175)
        self.size_slider.setValue(round(self.model.d["settings"]["size"]*100/240))
        self.size_slider.valueChanged.connect(lambda v: self.change_size(round(v*240/100)))
        r.addWidget(self.size_slider)
        self.size_label = label(f"{self.size_slider.value()}%", "muted")
        self.size_label.setMinimumWidth(45)
        r.addWidget(self.size_label)
        b.addLayout(r)
        layout.addWidget(f)
        f, b = card("陪伴习惯")
        for key, text in [("wander", "在桌面随意散步"), ("cursor_chase", "平时也会跟着鼠标走"),
                          ("perch", "偶尔找桌面图标睡觉"), ("idle_pause", "离开电脑 5 分钟后暂停工作与专注计时"),
                          ("quiet", "安静模式：仅显示小猫气泡提醒"),
                          ("eco", "省电模式：降低动画帧率，进一步减少后台开销")]:
            check = QCheckBox(text)
            check.setObjectName(f"setting_{key}")
            check.setChecked(self.model.d["settings"][key])
            check.toggled.connect(lambda value, k=key: self.setting(k, value))
            b.addWidget(check)
        startup = QCheckBox("登录 Windows 时叫醒小猫")
        startup.setChecked(startup_enabled())
        startup.toggled.connect(self.change_startup)
        b.addWidget(startup)
        layout.addWidget(f)
        f, b = card("记得照顾你自己")
        for key, minutes, text in [("water", "water_minutes", "喝水提醒"), ("breaks", "break_minutes", "工作休息提醒")]:
            r = QHBoxLayout()
            c = QCheckBox(text)
            c.setChecked(self.model.d["settings"][key])
            c.toggled.connect(lambda v, k=key: self.setting(k, v))
            r.addWidget(c)
            r.addStretch()
            r.addWidget(label("每", "muted"))
            spin = QSpinBox()
            spin.setRange(1, 240)
            spin.setValue(int(self.model.d["settings"][minutes]))
            spin.valueChanged.connect(lambda v, k=minutes: self.setting(k, v))
            r.addWidget(spin)
            r.addWidget(label("分钟", "muted"))
            b.addLayout(r)
        layout.addWidget(f)
        f, b = card("我的存档")
        b.addWidget(label(str(self.model.store.path), "muted", True))
        b.addWidget(button("打开存档文件夹 ↗", self.open_data_dir))
        b.addWidget(label("食物、衣橱、设置和工作记录自动保存；关闭软件会停止本轮工作及专注计时。", "muted", True))
        layout.addWidget(f)
        layout.addStretch()

    def open_data_dir(self):
        self.persist()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.model.store.directory)))

    def rename_cat(self, editor):
        self.model.d["name"] = editor.text().strip() or "奶油"
        editor.setText(self.model.d["name"])
        self.save()

    def setting(self, key, value):
        self.model.d["settings"][key] = value
        self.save()

    def change_size(self, value):
        self.pet.set_pet_size(value)

    def sync_size(self, pixels):
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(round(pixels*100/240))
        self.size_slider.blockSignals(False)
        self.size_label.setText(f"{round(pixels*100/240)}%")

    def sync_eco(self, enabled):
        checkbox = self.findChild(QCheckBox, "setting_eco")
        if checkbox:
            checkbox.blockSignals(True)
            checkbox.setChecked(enabled)
            checkbox.blockSignals(False)

    def change_startup(self, value):
        try:
            set_startup(value)
            self.toast("小猫会在下次登录时醒来。" if value else "已关闭登录启动。")
        except OSError as exc:
            self.toast(f"设置登录启动失败：{exc}")

    def refresh(self, force=False):
        if not force and (not self.isVisible() or self.isMinimized()):
            return
        d, m = self.model.d, self.model
        self.wallet.setText(f"{d['coins']:,} 猫爪币")
        self.greeting.setText(f"今天也有{d['name']}陪你。")
        self.status_pill.setText("◷ 专注陪伴中" if m.focus_remaining and not m.focus_paused else "● 小猫在线")
        for key, number, progress in self._stats:
            value = round(d[key])
            number.setText(f"{value} / 100")
            progress.setValue(value)
        record = m.record()
        self.home_work.setText(duration_text(record["seconds"]))
        self.home_income.setText(f"预计收入 ¥{record['income']:.2f}  ·  每分钟 +2 猫爪币")
        self.cat_state.setText(STATE_NAMES.get(self.pet.state, "陪着你"))
        self.bond_text.setText(f"亲密度 {d['bond']}  ·  多摸摸它，它会记住你的温柔。")
        for key, stock, purchase, use in self._products:
            item, count = ITEMS[key], d["inventory"].get(key, 0)
            stock.setText(f"背包里有 {count} 份" if item["kind"] == "food" else ("已经拥有 · 可一直使用" if count else "尚未拥有"))
            purchase.setEnabled(d["coins"] >= item["price"] and (item["kind"] == "food" or count == 0))
            purchase.setText("已经拥有" if item["kind"] != "food" and count else f"{item['price']} 币 · 兑换")
            use.setEnabled(count > 0)
            if item["kind"] == "outfit":
                use.setText("正在穿着" if d["outfit"] == key else "穿上这套")
        gifts = [k for k in gifts_today(date.today(), d["settings"]["birthday"]) if f"{date.today().year}:{k}" not in d["claimed"]]
        self.gift_button.setVisible(bool(gifts))
        text = "结束上班" if m.working else "开始上班"
        self.home_work_button.setText(text)
        self.work_toggle.setText(text)
        self.work_time.setText(duration_text(record["seconds"]))
        self.work_money.setText(f"预计收入  ¥ {record['income']:.2f}")
        self.work_status.setText("离开电脑中 · 计时已自动暂停" if m.working and m.idle_paused else
                                 ("正在记录 · 每满 1 分钟获得 2 猫爪币" if m.working else "准备好了，就开始今天的工作吧。"))
        self.focus_button.setText(("继续专注" if m.focus_paused else "暂停专注") if m.focus_remaining else "开始专注")
        self.focus_stop.setEnabled(m.focus_remaining > 0)
        self.focus_minutes.setEnabled(not m.focus_remaining)
        self.focus_dial.update()
        if self.stack.currentIndex() == 4:
            self.refresh_history()
        for preview in self._previews:
            if preview.isVisible():
                preview.update()

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "refresh_timer"):
            self.refresh()
            self.refresh_timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        if hasattr(self, "refresh_timer"):
            self.refresh_timer.stop()

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "refresh_timer"):
            if self.isMinimized() or not self.isVisible():
                self.refresh_timer.stop()
            elif not self.refresh_timer.isActive():
                self.refresh_timer.start()
                self.refresh()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
        self.pet.say("小屋收好啦，我还在桌面上。", 4)
