"""Transparent pet and small, input-transparent toy windows (never full-screen)."""
import ctypes
import math
import random
import time
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen, QPixmap, QRegion
from PySide6.QtWidgets import QApplication, QInputDialog, QMenu, QWidget
from .art import STATE_NAMES, blend_pixmaps
from .motion import FramePacer, Locomotion, frame_interval, leap_position, smoothstep
from .platform_win import IS_WINDOWS, desktop_icon_rects, launch_app

FLAGS = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool

class ToyWindow(QWidget):
    def __init__(self):
        super().__init__(None, FLAGS | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(92, 110)
        self.kind = "yarn"
        self.phase = 0.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.kind == "laser":
            for radius in range(18, 2, -3):
                p.setBrush(QColor(255, 62, 69, 10 if radius > 6 else 240))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawEllipse(QPointF(46, 55), radius, radius)
        elif self.kind == "wand":
            p.setPen(QPen(QColor("#7f6659"), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(55, 5, 35, 45)
            p.setPen(QPen(QColor("#e2bda9"), 1.5))
            p.drawLine(35, 45, 45 + int(math.sin(self.phase * 6) * 10), 70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#df9c86"))
            p.drawEllipse(QRectF(29, 65, 20, 34))
            p.setBrush(QColor("#98ae9c"))
            p.drawEllipse(QRectF(43, 67, 16, 29))
        else:
            p.translate(46, 55)
            p.rotate(self.phase * 140)
            p.setPen(QPen(QColor("#a9634b"), 1.5))
            p.setBrush(QColor("#d7987b"))
            p.drawEllipse(QPointF(0, 0), 17, 17)
            for offset in (-10, -5, 0, 5, 10):
                p.drawArc(QRectF(-17, -17 + offset / 2, 34, 27), 20 * 16, 145 * 16)
            p.drawLine(12, 12, 27, 24)

class PetWindow(QWidget):
    open_home = Signal()
    message = Signal(str)
    state_changed = Signal(str)
    request_quit = Signal()
    size_changed = Signal(int)
    shortcuts_requested = Signal()
    eco_changed = Signal(bool)

    def __init__(self, model, art):
        super().__init__(None, FLAGS | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setObjectName("desktopPet")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.model, self.art = model, art
        self.state = "wake"
        self.state_start = time.monotonic()
        self.until = self.state_start + 4
        self._last_tick = self.state_start
        self.facing = 1
        self.target = None
        self.speed = 40
        self._fx, self._fy = 0.0, 0.0
        self.dragging = False
        self._press = None
        self._press_pos = None
        self.hovered = False
        self.paused = False
        self.bubble = ""
        self.bubble_until = 0
        self.mode = ""
        self.toy = ToyWindow()
        self.ball = QPointF()
        self.ball_velocity = QPointF()
        self.ball_ground = 0
        self.ball_active = False
        self.carry_ball_until = 0
        self._left_was_down = True
        self._pet_at = 0.0
        self._mask_key = None
        self.motion = Locomotion()
        self.gait_phase = 0.0
        self._created = self.state_start
        self._transition_from = None
        self._transition_started = 0.0
        self._transition_duration = .22
        self._transition_region = QRegion()
        self._body_region = QRegion()
        self._painted_outfit = self.model.d["outfit"]
        self._game_phase = ""
        self._game_until = 0.0
        self._jump = None
        self._pending_sleep = False
        self._icon_cache = (0, [])
        self._last_toy_cursor = None
        self._pointer_active_until = 0.0
        self._pacer = FramePacer()
        self._refresh_tier = None
        self.resize_pet()
        screen = QApplication.primaryScreen().availableGeometry()
        position = model.d["position"]
        if position:
            self.move_clamped(QPoint(*position))
        else:
            self.move(screen.right() - self.width() - 60, screen.bottom() - self.height())
        self._sync_float()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.start(16)
        self.say(f"我是{model.d['name']}，今天也陪你。", 7)

    def resize_pet(self):
        old_size = self.size()
        old_position = self.pos()
        size = int(self.model.d["settings"]["size"])
        self.setFixedSize(size + 32, size + 100)
        self._transition_from = None
        self._transition_region = QRegion()
        self._body_region = QRegion()
        self.art.clear_cache()
        self._mask_key = None
        if self.isVisible():
            self.move_clamped(QPoint(old_position.x() + (old_size.width()-self.width())//2,
                                     old_position.y() + old_size.height()-self.height()))

    def set_pet_size(self, pixels):
        pixels = max(120, min(420, int(pixels)))
        if self.model.d["settings"]["size"] != pixels:
            self.model.d["settings"]["size"] = pixels
            self.resize_pet()
            self.size_changed.emit(pixels)

    def custom_size(self):
        value, accepted = QInputDialog.getInt(None, "猫咪大小", "显示大小（50%–175%）", round(self.model.d["settings"]["size"]*100/240), 50, 175, 5)
        if accepted:
            self.set_pet_size(round(value*240/100))

    def set_eco(self, enabled):
        enabled = bool(enabled)
        if self.model.d["settings"].get("eco", False) != enabled:
            self.model.d["settings"]["eco"] = enabled
            self._set_rate()
            self.eco_changed.emit(enabled)

    def sprite_rect(self):
        return QRectF(16, 84, self.width() - 32, self.height() - 100)

    def _sync_float(self):
        self._fx, self._fy = float(self.x()), float(self.y())

    def available(self, point=None):
        screen = QApplication.screenAt(point or self.geometry().center()) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def move_clamped(self, pos):
        rect = self.available(pos + QPoint(self.width() // 2, self.height() // 2))
        self.move(max(rect.left(), min(pos.x(), rect.right() - self.width() + 1)),
                  max(rect.top(), min(pos.y(), rect.bottom() - self.height() + 1)))
        self._sync_float()

    def set_state(self, state, seconds=6):
        if self.state != state:
            if "walk" in {state, self.state}:
                self._clear_transition()
            else:
                self._begin_transition()
            self.state = state
            self.state_start = time.monotonic()
            if state != "walk":
                self.motion.reset()
            self.state_changed.emit(state)
            self._mask_key = None
        self.until = time.monotonic() + seconds
        self._set_rate()

    def _begin_transition(self):
        if self.state == "walk":
            self._clear_transition()
            return
        if self.isVisible():
            now = time.monotonic()
            snapshot = QPixmap(self.size())
            snapshot.fill(Qt.GlobalColor.transparent)
            p = QPainter(snapshot)
            self._render_sprite(p, now)
            p.end()
            self._transition_from = snapshot
            self._transition_started = now
            self._transition_region = QRegion(self._body_region)

    def _set_facing(self, facing):
        if facing != self.facing:
            # Velocity already eases through zero when turning. Overlaying the
            # opposite face creates a second cat, so switch a single silhouette.
            self._clear_transition()
            self.facing = facing
            self._mask_key = None

    def _clear_transition(self):
        self._transition_from = None
        self._transition_region = QRegion()

    def _set_rate(self, pace=False):
        if not hasattr(self, "timer"):
            return
        now = time.monotonic()
        toy_moving = self.mode == "yarn" and math.hypot(self.ball_velocity.x(), self.ball_velocity.y()) > 20
        active = self.dragging or self._jump is not None or toy_moving or (self.mode and now < self._pointer_active_until)
        interval = frame_interval(self.state, active=bool(active),
            transitioning=self._transition_from is not None,
            eco=self.model.d["settings"].get("eco", False), hidden=not self.isVisible())
        if self.mode and self.isVisible():
            interval = min(interval, 33)  # idle toys still react to Esc/mouse within 33 ms.
        if self._refresh_tier != interval:
            self._refresh_tier = interval
            self._pacer.reset()
            self.timer.setTimerType(Qt.TimerType.PreciseTimer if interval <= 33 else Qt.TimerType.CoarseTimer)
            self.timer.setInterval(interval)
        if pace:
            delay = self._pacer.delay_ms(now, interval)
            if self.timer.interval() != delay:
                self.timer.setInterval(delay)

    def say(self, text, seconds=5):
        self.bubble = text
        self.bubble_until = time.monotonic() + seconds
        self._mask_key = None
        self.update()

    def sleep(self):
        self.stop_play(silent=True)
        self.target = None
        self.set_state("sleep", 90)
        self.say("盘成一小团。等我睡醒再陪你。")

    def wake(self):
        self.paused = False
        self.set_state("wake", 3)
        self.say("醒啦！刚才梦见小鱼干了。")

    def pet_head(self):
        self.target = None
        self.set_state("pet", 4)
        self.model.pet()
        self.say(random.choice(["呼噜…呼噜…", "再摸一下，就一下。", "这里这里，耳朵后面。"]), 3)

    def start_play(self, mode):
        if mode not in {"yarn", "wand", "laser"}:
            return
        if not self.model.d["inventory"].get(mode):
            self.message.emit("还没有这个玩具，先去玩具屋兑换吧。")
            return
        self.mode = mode
        self._pending_sleep = False
        self._game_phase = "stalk" if mode == "wand" else "chase"
        self._game_until = time.monotonic() + .45
        self._jump = None
        self.paused = False
        self.toy.kind = mode
        self.toy.show()
        self._left_was_down = True
        self.set_state("crouch", 0.8)
        self.say("点击桌面抛毛线球 · Esc 结束" if mode == "yarn" else "移动鼠标逗猫 · Esc 结束", 7)
        if mode == "yarn":
            self.throw_ball(QCursor.pos())

    def stop_play(self, silent=False):
        self._pending_sleep = False
        had_mode = bool(self.mode)
        self.mode = ""
        self.ball_active = False
        self.carry_ball_until = 0
        self.toy.hide()
        self.target = None
        self._jump = None
        self._game_phase = ""
        self.motion.reset()
        self._set_rate()
        if had_mode:
            self.set_state("idle", 5)
            if not silent:
                self.say("先玩到这里。我去舔舔毛。")

    def throw_ball(self, point):
        rect = self.available(point)
        self.ball = QPointF(self.x() + self.width() / 2, self.y() + self.height() - 40)
        self.ball_ground = rect.bottom() - 18
        dest_x = max(rect.left() + 25, min(point.x(), rect.right() - 25))
        self.ball_velocity = QPointF((dest_x - self.ball.x()) / 0.9, -210)
        self.ball_active = True
        self.carry_ball_until = 0
        self._game_phase = "chase"

    def choose_idle(self):
        if self.paused:
            self.set_state("idle", 10)
            return
        d = self.model.d
        choices = ["idle", "proud", "affection", "sleepy", "groom", "stretch", "sleep", "walk"]
        weights = [17, 8, 10, 10, 13, 9, 16, 17 if d["settings"]["wander"] else 0]
        if d["energy"] < 30:
            weights[6] += 65
        if 0 <= time.localtime().tm_hour <= 6:
            weights[6] += 35
        state = random.choices(choices, weights=weights)[0]
        durations = {"sleep": (25, 80), "groom": (5, 11), "stretch": (3, 5), "walk": (5, 14)}
        self.set_state(state, random.uniform(*durations.get(state, (5, 15))))
        if state == "sleep" and d["settings"]["perch"] and random.random() < 0.4:
            self.perch_on_icon()
        if state == "walk":
            rect = self.available()
            self.target = QPointF(random.randint(rect.left(), max(rect.left(), rect.right() - self.width())),
                                  max(rect.top(), rect.bottom() - self.height() + 1))
            self.speed = random.uniform(24, 50)

    def perch_on_icon(self):
        self.stop_play(silent=True)
        self.target = None
        now = time.monotonic()
        if now-self._icon_cache[0] > 15:
            self._icon_cache = (now, desktop_icon_rects())
        rects = self._icon_cache[1]
        candidates = []
        for x0, y0, x1, y1 in rects:
            for screen in QApplication.screens():
                geom = screen.geometry()
                ratio = screen.devicePixelRatio()
                # Windows returns physical coordinates. Qt's virtual screen origin
                # must be preserved on mixed-DPI displays.
                logical = QPoint(round(geom.x() + (x0 - geom.x() * ratio) / ratio),
                                 round(geom.y() + (y0 - geom.y() * ratio) / ratio))
                if geom.contains(logical):
                    candidates.append(logical)
                    break
        if candidates:
            point = random.choice(candidates)
            self.target = self._target_at(point+QPoint(24, 0))
            self._pending_sleep = True
            self.speed = 80
            self.set_state("walk", 60)
            self.say("走过去，借你的图标睡个小觉。")
            return True
        self.set_state("sleep", 60)
        self.say("找个舒服的位置，盘起来睡。")
        return False

    def tick(self):
        try:
            self._tick_logic()
        finally:
            self._set_rate(pace=True)

    def _tick_logic(self):
        now = time.monotonic()
        dt = min(.05, max(0, now - self._last_tick))
        self._last_tick = now
        if self._painted_outfit != self.model.d["outfit"]:
            self._begin_transition()
            self._painted_outfit = self.model.d["outfit"]
            self._mask_key = None
        if self._transition_from is not None and now-self._transition_started >= self._transition_duration:
            self._transition_from = None
            self._transition_region = QRegion()
            self._mask_key = None
        if self.mode:
            pointer = QCursor.pos()
            if self._last_toy_cursor is not None and (pointer-self._last_toy_cursor).manhattanLength() > 2:
                self._pointer_active_until = now+.2
            self._last_toy_cursor = pointer
            if IS_WINDOWS:
                if ctypes.windll.user32.GetAsyncKeyState(0x1B) & 0x8000:
                    self.stop_play()
                    return
                left_down = bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)
                if self.mode == "yarn" and left_down and not self._left_was_down:
                    self.throw_ball(QCursor.pos())
                self._left_was_down = left_down
            self.update_toy(dt, now)
        if not self.dragging and not self.paused:
            if self.mode == "wand":
                self._tick_wand(dt, now)
            elif self.mode == "laser":
                self._tick_laser(dt, now)
            elif self.mode == "yarn":
                self._tick_yarn(dt, now)
            else:
                if self.model.d["settings"]["cursor_chase"] and self.state not in {"sleep", "eat", "pet"}:
                    goal = self._target_at(QPointF(QCursor.pos()))
                    if (goal-QPointF(self._fx, self._fy)).manhattanLength() > 35:
                        self.target = goal
                        self.speed = 65
                        self.set_state("walk", 2)
                if self.state == "walk" and self.target is not None:
                    self.move_towards(dt)
                elif now >= self.until:
                    self.target = None
                    self.choose_idle()
        if self.mode:
            self.toy.phase += dt if self.mode != "yarn" else self.ball_velocity.x()*dt/45
            self.toy.update()
        if self.isVisible():
            self.update()
            self.update_mask(now-self.state_start)
        self._set_rate()

    def _target_at(self, point):
        area = self.available(QPoint(round(point.x()), round(point.y())))
        return QPointF(max(area.left(), min(point.x()-self.width()/2, area.right()-self.width()+1)),
                       max(area.top(), min(point.y()-self.height()+32, area.bottom()-self.height()+1)))

    def _tick_yarn(self, dt, now):
        if self.carry_ball_until <= now and self._game_phase != "rest":
            self.target = self._target_at(self.ball)
            self.speed = 125
            if now >= self.until or self.state not in {"crouch", "walk", "play"}:
                self.set_state("walk", 2)
        if self.state == "walk" and self.target is not None:
            self.move_towards(dt)
        elif self._game_phase == "rest" and now >= self._game_until:
            self._game_phase = "chase"

    def _tick_wand(self, dt, now):
        # Stalk -> crouch -> one committed arcing leap -> soft landing -> reset.
        goal = self._target_at(QPointF(QCursor.pos()))
        if self._jump is not None:
            self._jump["t"] = min(1, self._jump["t"]+dt/self._jump["duration"])
            x, y = leap_position(self._jump["start"], self._jump["end"], self._jump["t"], self._jump["height"])
            self.move_clamped(QPoint(round(x), round(y)))
            if self._jump["t"] >= 1:
                self._jump = None
                self._game_phase = "landing"
                self._game_until = now+.32
                self.set_state("land", .32)
            return
        if self._game_phase == "landing":
            if now >= self._game_until:
                self._game_phase = "stalk"
                self._game_until = now+random.uniform(.35, .7)
                self.set_state("crouch", .8)
            return
        distance = math.hypot(goal.x()-self._fx, goal.y()-self._fy)
        if distance > 230:
            self.target, self.speed = goal, 100
            self.set_state("walk", 2)
            self.move_towards(dt, arrive=False)
            self._game_until = now+.3
        elif now < self._game_until:
            self.target = None
            self.set_state("crouch", .7)
        else:
            self.target = None
            self._set_facing(1 if goal.x() >= self._fx else -1)
            self.set_state("pounce", .65)
            self._jump = {"start": (self._fx, self._fy), "end": (goal.x(), goal.y()), "t": 0.0,
                          "duration": random.uniform(.42, .58), "height": random.uniform(38, 72)}
            self._game_phase = "pounce"

    def _tick_laser(self, dt, now):
        # A red dot cannot be retrieved: quick pursuit, paw taps and searching.
        goal = self._target_at(QPointF(QCursor.pos()))
        distance = math.hypot(goal.x()-self._fx, goal.y()-self._fy)
        if self._game_phase in {"tap", "search"} and distance < 65:
            if now < self._game_until:
                return
            if self._game_phase == "tap":
                self._game_phase, self._game_until = "search", now+.65
                self.set_state("search", .65)
                return
        if distance < 7:
            self.target = None
            self._game_phase, self._game_until = "tap", now+.45
            self.set_state("bat", .45)
        else:
            self._game_phase = "chase"
            self.target, self.speed = goal, 190
            self.set_state("walk", 2)
            self.move_towards(dt, arrive=False)

    def move_towards(self, dt, arrive=True):
        if self.target is None:
            return
        area = self.available()
        step = self.motion.advance(self._fx, self._fy, self.target.x(), self.target.y(), self.speed, dt,
            (area.left(), area.top(), area.right()-self.width()+1, area.bottom()-self.height()+1))
        self._fx, self._fy = step.x, step.y
        self.gait_phase += step.distance/58
        if abs(self.motion.vx) > 9:
            self._set_facing(1 if self.motion.vx > 0 else -1)
        point = QPoint(round(self._fx), round(self._fy))
        if point != self.pos():
            self.move(point)
        if step.arrived and arrive:
            self.target = None
            if self._pending_sleep:
                self._pending_sleep = False
                self.set_state("sleep", 65)
                self.say("到了，盘起来睡个小觉。")
            elif self.mode == "yarn" and self.ball_active and not self.carry_ball_until:
                if random.random() < 0.55:
                    self.carry_ball_until = time.monotonic() + 4
                    rect = self.available()
                    self.target = QPointF(random.randint(rect.left(), max(rect.left(), rect.right()-self.width())), self._fy)
                    self.say("我的了。不还给你。", 4)
                else:
                    self.set_state("play", 1.5)
                    self._game_phase, self._game_until = "rest", time.monotonic()+1.5
            elif self.mode:
                self.set_state("crouch", random.uniform(0.5, 1.5))
            else:
                self.set_state("idle", 6)

    def update_toy(self, dt, now):
        if self.mode != "yarn":
            point = QCursor.pos()
            self.toy.move(point.x() - 46, point.y() - 55)
            return
        if self.carry_ball_until > now:
            self.ball = QPointF(self.x() + self.width() * (0.82 if self.facing > 0 else 0.18),
                                self.y() + self.height() * 0.58)
        elif self.carry_ball_until:
            self.carry_ball_until = 0
            self.ball_velocity = QPointF(0, 0)
            self.say("放这儿了。你自己来拿。")
        elif self.ball_active:
            self.ball_velocity.setY(self.ball_velocity.y() + 650 * dt)
            self.ball += self.ball_velocity * dt
            rect = self.available(QPoint(round(self.ball.x()), round(self.ball.y())))
            if self.ball.y() > self.ball_ground:
                self.ball.setY(self.ball_ground)
                self.ball_velocity.setY(-abs(self.ball_velocity.y()) * 0.48)
                self.ball_velocity.setX(self.ball_velocity.x() * 0.78)
                if abs(self.ball_velocity.y()) < 15:
                    self.ball_velocity.setY(0)
            if self.ball.x() < rect.left() + 20 or self.ball.x() > rect.right() - 20:
                self.ball.setX(max(rect.left() + 20, min(self.ball.x(), rect.right() - 20)))
                self.ball_velocity.setX(-self.ball_velocity.x() * 0.7)
        self.toy.move(round(self.ball.x()) - 46, round(self.ball.y()) - 55)

    def render_into(self, p):
        now = time.monotonic()
        elapsed = now - self.state_start
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.bubble and now < self.bubble_until:
            p.setPen(QPen(QColor("#e8d9ca"), 1))
            p.setBrush(QColor(255, 251, 245, 246))
            p.drawRoundedRect(QRectF(5, 5, self.width() - 10, 66), 18, 18)
            p.setPen(QColor("#665347"))
            font = p.font()
            font.setPixelSize(12)
            p.setFont(font)
            p.drawText(QRectF(17, 11, self.width()-34, 54), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.bubble)
        self._render_sprite(p, now)
        if self.hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(74, 59, 49, 205))
            p.drawRoundedRect(QRectF(self.width()/2-72, self.height()-25, 144, 22), 11, 11)
            p.setPen(QColor("#fff8ee"))
            font = p.font()
            font.setPixelSize(10)
            p.setFont(font)
            p.drawText(QRectF(self.width()/2-72, self.height()-25, 144, 22), Qt.AlignmentFlag.AlignCenter, "双击小屋 · 右键菜单")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.GlobalColor.transparent)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        self.render_into(p)

    def _draw_current_sprite(self, painter, now):
        self.art.draw(painter, self.sprite_rect(), self.state, now-self.state_start,
                      self.facing, self._painted_outfit, gait_phase=self.gait_phase,
                      motion_time=now-self._created)

    def _render_sprite(self, painter, now):
        if self._transition_from is None:
            self._draw_current_sprite(painter, now)
            return
        weight = smoothstep((now-self._transition_started)/self._transition_duration)
        fresh = QPixmap(self.size())
        fresh.fill(Qt.GlobalColor.transparent)
        p = QPainter(fresh)
        self._draw_current_sprite(p, now)
        p.end()
        painter.drawPixmap(0, 0, blend_pixmaps(self._transition_from, fresh, weight))

    def update_mask(self, elapsed):
        key = (self.state, self.width(), self._painted_outfit, self._transition_from is not None,
               self.facing, self.hovered, bool(self.bubble and time.monotonic() < self.bubble_until))
        if self._mask_key == key:
            return
        self._mask_key = key
        side = round(self.sprite_rect().width())
        self._body_region = self.art.body_region(self.state, side, self._painted_outfit, self.facing).translated(16, 84-round(side*80/320))
        region = self._body_region | self._transition_region
        if key[-1]:
            region |= QRegion(5, 5, self.width()-10, 66)
        if self.hovered:
            region |= QRegion(self.width()//2-72, self.height()-25, 144, 22)
        self.setMask(region)

    def enterEvent(self, event):
        self.hovered = True
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def leaveEvent(self, event):
        self.hovered = False
        if self.state == "pet":
            self.unsetCursor()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._press_pos = self.pos()

    def mouseMoveEvent(self, event):
        if self._press is not None and event.buttons() & Qt.MouseButton.LeftButton:
            diff = event.globalPosition().toPoint() - self._press
            if self.dragging or diff.manhattanLength() > 8:
                self.dragging = True
                self.stop_play(silent=True)
                self.set_state("carried", 10)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                self.move_clamped(self._press_pos + diff)
        elif not self.mode and event.position().y() < self.height() * 0.60:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            if self.hovered and time.monotonic() - self._pet_at > 1.2:
                self._pet_at = time.monotonic()
                self.pet_head()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            was_dragging = self.dragging
            self.dragging = False
            self._press = None
            if was_dragging:
                self.model.d["position"] = [self.x(), self.y()]
                self.set_state("idle", 5)
                self.say("轻轻放下，我自己会走。", 3)
            else:
                self.pet_head()
            self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, event):
        self._press = None
        self.open_home.emit()

    def contextMenuEvent(self, event):
        menu = self.create_context_menu()
        menu.exec(event.globalPos())
        menu.deleteLater()

    def create_context_menu(self):
        menu = QMenu()
        menu.setStyleSheet("QMenu {background:#fffaf2;color:#554338;padding:8px;border:1px solid #e4d6c6;border-radius:8px;} QMenu::item{padding:8px 22px;} QMenu::item:selected{background:#f0e1d1;}")
        for label, callback in [("打开猫咪小屋", self.open_home.emit), ("摸摸头", self.pet_head),
                                ("睡个小觉", self.sleep), ("睡醒啦", self.wake),
                                ("找个图标睡", self.perch_on_icon), ("结束玩耍", self.stop_play)]:
            menu.addAction(label, callback)
        apps_menu = menu.addMenu("快捷启动")
        for app in self.model.d["apps"]:
            apps_menu.addAction(app["name"], lambda checked=False, path=app["path"]: self.launch_shortcut(path))
        if not self.model.d["apps"]:
            empty = apps_menu.addAction("先添加常用软件")
            empty.setEnabled(False)
        apps_menu.addSeparator()
        apps_menu.addAction("配置快捷启动…", self.open_shortcut_settings)
        size_menu = menu.addMenu(f"猫咪大小 · {round(self.model.d['settings']['size']*100/240)}%")
        for percent in (50, 70, 100, 130, 160):
            action = size_menu.addAction(f"{percent}%")
            action.setCheckable(True)
            action.setChecked(round(self.model.d["settings"]["size"]*100/240) == percent)
            action.triggered.connect(lambda checked=False, value=percent: self.set_pet_size(round(value*240/100)))
        size_menu.addAction("自定义大小…", self.custom_size)
        eco = menu.addAction("省电模式")
        eco.setCheckable(True)
        eco.setChecked(self.model.d["settings"].get("eco", False))
        eco.toggled.connect(self.set_eco)
        menu.addSeparator()
        action = menu.addAction("继续散步" if self.paused else "待在这里")
        action.triggered.connect(self.toggle_pause)
        menu.addAction("退出猫在", self.request_quit.emit)
        return menu

    def launch_shortcut(self, path):
        try:
            launch_app(path)
            self.say("给你打开啦。")
        except (OSError, ValueError) as exc:
            self.say(str(exc))

    def open_shortcut_settings(self):
        self.open_home.emit()
        self.shortcuts_requested.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self._last_tick = time.monotonic()
        self._set_rate()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._set_rate()

    def toggle_pause(self):
        self.paused = not self.paused
        self.target = None
        self._pending_sleep = False
        self.set_state("idle", 8)

    def closeEvent(self, event):
        self.toy.close()
        super().closeEvent(event)
