"""Fitted action costumes, blended poses, foot anchoring and bounded caches."""
import math
import os
import re
import sys
from collections import OrderedDict
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFontDatabase, QIcon, QImage, QPainter, QPixmap, QRegion, QTransform
from PySide6.QtWidgets import QApplication
from .motion import smoothstep

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
ASSETS = ROOT / "assets"
ALPHA_LUT = bytes(0 if a < 96 else (255 if a > 235 else round((a-96)/139*255)) for a in range(256))

def load_system_fonts():
    # Native Qt discovers system fonts itself; avoid duplicate font registration.
    if os.name == "nt" and QApplication.platformName() in {"offscreen", "minimal"}:
        directory = Path(os.environ.get("WINDIR", r"C:\Windows"))/"Fonts"
        for name in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf"):
            path = directory/name
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))

FRAMES = {
    "idle": [0, 1], "proud": [2, 0], "affection": [3, 13], "walk": [4, 5, 6, 7],
    "sleep": [8, 9], "sleepy": [1, 2], "stretch": [10], "groom": [11], "carried": [12],
    "pet": [13], "crouch": [14], "eat": [15], "play": [14, 6, 14, 7],
    "wake": [9, 1, 10, 0], "pounce": [16], "land": [14], "bat": [14, 6, 14], "search": [3, 2],
}
STATE_NAMES = {"idle": "发呆", "proud": "高傲", "affection": "撒娇", "walk": "散步", "sleep": "睡觉",
    "sleepy": "犯困", "stretch": "伸懒腰", "groom": "舔毛", "carried": "被拎起来了", "pet": "呼噜呼噜",
    "crouch": "蓄势待扑", "eat": "吃饭", "play": "拨弄毛线球", "wake": "睡醒啦", "pounce": "扑羽毛！",
    "land": "轻轻落地", "bat": "伸爪试探", "search": "小红点去哪了"}
PROFILE_STATES = {"walk", "play", "crouch", "stretch", "pounce", "land", "bat", "search"}
WALK_BASE = 17
WALK_COUNT = 24

def load_cells(name, columns, rows):
    atlas = QImage(str(ASSETS/name)).convertToFormat(QImage.Format.Format_RGBA8888)
    if atlas.isNull():
        raise RuntimeError(f"缺少图片素材：{ASSETS/name}")
    view = atlas.bits()
    view[3::4] = bytes(view[3::4]).translate(ALPHA_LUT)
    if columns == 4 and rows in (2, 4):
        extracted = _extract_actions(atlas, columns, rows)
        if extracted is not None:
            return extracted
    cells = []
    for row in range(rows):
        for col in range(columns):
            x0, x1 = round(col*atlas.width()/columns), round((col+1)*atlas.width()/columns)
            y0, y1 = round(row*atlas.height()/rows), round((row+1)*atlas.height()/rows)
            cells.append(QPixmap.fromImage(atlas.copy(x0, y0, x1-x0, y1-y0)))
    return cells

def _extract_actions(atlas, columns, rows):
    """Decode connected sprite islands rather than cutting through a tall hat.

    Generated sheets have regular layout but a few bonnet tips cross nominal
    cell boundaries. Row-run component labelling finds each complete silhouette
    and excludes the neighbouring sprite's fragments. No source image is edited.
    """
    width, height = atlas.width(), atlas.height()
    alpha = bytes(atlas.bits()[3::4])
    parents, areas, boxes = [], [], []
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    def union(a, b):
        a, b = root(a), root(b)
        if a == b:
            return a
        if areas[a] < areas[b]:
            a, b = b, a
        parents[b] = a
        areas[a] += areas[b]
        ax, ay, ar, ab = boxes[a]
        bx, by, br, bb = boxes[b]
        boxes[a] = (min(ax, bx), min(ay, by), max(ar, br), max(ab, bb))
        return a
    previous = []
    for y in range(height):
        current, cursor = [], 0
        for match in re.finditer(rb"[\x60-\xff]+", alpha[y*width:(y+1)*width]):
            left, right = match.start(), match.end()-1
            i = len(parents)
            parents.append(i); areas.append(right-left+1); boxes.append((left, y, right, y))
            while cursor < len(previous) and previous[cursor][1] < left-1:
                cursor += 1
            j = cursor
            while j < len(previous) and previous[j][0] <= right+1:
                union(i, previous[j][2])
                j += 1
            current.append((left, right, i))
        previous = current
    islands = sorted((i for i in range(len(parents)) if parents[i] == i), key=lambda i: areas[i], reverse=True)[:columns*rows]
    if len(islands) != columns*rows:
        return None
    slots = {}
    for i in islands:
        left, top, right, bottom = boxes[i]
        col = min(columns-1, int((left+right)/2*columns/width))
        row = min(rows-1, int((top+bottom)/2*rows/height))
        slots[(row, col)] = (max(0, left-2), max(0, top-2), min(width-1, right+2), min(height-1, bottom+2))
    if len(slots) != columns*rows:
        return None
    cell_width = round(width/columns)
    cell_height = max(round(height/rows), max(b-t+5 for l, t, r, b in slots.values()))
    result = []
    for row in range(rows):
        for col in range(columns):
            left, top, right, bottom = slots[(row, col)]
            source = atlas.copy(left, top, right-left+1, bottom-top+1)
            pix = QPixmap(cell_width, cell_height)
            pix.fill(Qt.GlobalColor.transparent)
            p = QPainter(pix)
            p.drawImage((cell_width-source.width())//2, cell_height-source.height()-2, source)
            p.end()
            result.append(pix)
    return result

def blend_pixmaps(first, second, weight):
    """Premultiplied interpolation: fur stays opaque during a frame transition."""
    pix = QPixmap(first.size())
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    p.setOpacity(1-weight)
    p.drawPixmap(0, 0, first)
    # Bake the second alpha before Plus. Qt's global opacity on Plus blends
    # the *operation result* back with the destination, causing a 75% body.
    weighted = QPixmap(second.size())
    weighted.fill(Qt.GlobalColor.transparent)
    q = QPainter(weighted)
    q.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    q.setOpacity(weight)
    q.drawPixmap(0, 0, second)
    q.end()
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    p.setOpacity(1)
    p.drawPixmap(0, 0, weighted)
    p.end()
    return pix

def animation_sample(state, elapsed, gait_phase=None):
    elapsed = max(0, elapsed)
    seq = FRAMES.get(state, [0])
    if len(seq) == 1:
        return seq[0], seq[0], 0.0
    if state == "idle":
        t = elapsed % 5.4
        if t < 4.9:
            return 0, 0, 0.0
        if t < 5.0:
            return 0, 1, smoothstep((t-4.9)/.1)
        if t < 5.12:
            return 1, 1, 0.0
        return 1, 0, smoothstep((t-5.12)/.28)
    if state == "walk":
        # These are complete, single-source motion-warped images baked offline.
        # Never dissolve two different leg positions while walking.
        i = int((gait_phase if gait_phase is not None else elapsed/.8)*WALK_COUNT) % WALK_COUNT
        return WALK_BASE+i, WALK_BASE+i, 0.0
    if state == "play":
        pos = elapsed/.9*len(seq)
        i = int(pos) % len(seq)
        return seq[i], seq[(i+1) % len(seq)], smoothstep(pos % 1)
    period = {"wake": .68, "sleep": 5, "affection": 3.2, "proud": 3.5,
              "sleepy": 2.5, "pounce": .22, "bat": .16, "search": 1}.get(state, 1.2)
    pos = elapsed/period
    if state in {"wake", "pounce", "bat"}:
        i = min(int(pos), len(seq)-1)
        j = min(i+1, len(seq)-1)
    else:
        i, j = int(pos) % len(seq), (int(pos)+1) % len(seq)
    return seq[i], seq[j], smoothstep(((pos % 1)-.72)/.28)

class Art:
    CACHE_LIMIT = 8*1024*1024

    def __init__(self):
        self.cats = load_cells("cat-atlas-v2.png", 4, 4)
        self.icon = QIcon(self.cats[0])
        self._outfit_id = self._outfit_cells = self._fronts = None
        self._leaps = None
        self._walk_outfit = None
        self._walk_frames = None
        self._cache, self._regions = OrderedDict(), OrderedDict()
        self.cache_bytes = 0
        self._offsets = {}

    def clear_cache(self):
        self._cache.clear()
        self.cache_bytes = 0
        self._regions.clear()

    def _remember(self, key, pix):
        size = pix.width()*pix.height()*4
        if size <= self.CACHE_LIMIT:
            while self._cache and self.cache_bytes+size > self.CACHE_LIMIT:
                _, old = self._cache.popitem(last=False)
                self.cache_bytes -= old.width()*old.height()*4
            self._cache[key] = pix
            self.cache_bytes += size
        return pix

    def _cached(self, key):
        pix = self._cache.get(key)
        if pix is not None:
            self._cache.move_to_end(key)
        return pix

    def _cells(self, outfit):
        if not outfit:
            return self.cats
        if self._outfit_id != outfit:
            cells = load_cells(f"dressed/{outfit}.png", 4, 4)
            self._outfit_id, self._outfit_cells = outfit, cells
            self._offsets = {k: v for k, v in self._offsets.items() if not k[0]}
        return self._outfit_cells

    def _pose(self, index, outfit, side):
        key = ("pose", index, outfit, side)
        pix = self._cached(key)
        if pix is not None:
            return pix
        if WALK_BASE <= index < WALK_BASE+WALK_COUNT:
            name = outfit or "bare"
            path = ASSETS/"walk"/f"{name}.png"
            if not path.is_file():
                # A development checkout before baking still draws one opaque
                # keyframe; a missing atlas never re-enables the ghosting blend.
                return self._pose(4+(index-WALK_BASE)//6, outfit, side)
            if self._walk_outfit != name:
                atlas = QImage(str(path)).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                if atlas.isNull():
                    raise RuntimeError(f"无法读取步态素材：{path}")
                w, h = atlas.width()//6, atlas.height()//4
                self._walk_frames = [QPixmap.fromImage(atlas.copy(i%6*w, i//6*h, w, h)) for i in range(WALK_COUNT)]
                self._walk_outfit = name
            source = self._walk_frames[index-WALK_BASE]
            pix = source.scaled(side, round(side*400/320), Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
            return self._remember(key, pix)
        if index == 16:
            from .catalog import ITEMS
            if self._leaps is None:
                self._leaps = load_cells("pounces-atlas.png", 4, 2)
            source = self._leaps[ITEMS[outfit]["index"]+1 if outfit else 0]
        else:
            source = self._cells(outfit)[index]
        anchor = (outfit, index)
        if anchor not in self._offsets:
            bounds = QRegion(source.mask()).boundingRect()
            self._offsets[anchor] = 310-(bounds.bottom()+1)*320/source.width()
        pix = QPixmap(side, round(side*400/320))
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.scale(side/320, side/320)
        p.drawPixmap(QRectF(0, 80+self._offsets[anchor], 320, source.height()*320/source.width()), source, source.rect())
        p.end()
        return self._remember(key, pix)

    def frame_index(self, state, elapsed):
        a, b, weight = animation_sample(state, elapsed)
        return b if weight >= .5 else a

    def _frame(self, state, elapsed, outfit, side, gait_phase):
        a, b, weight = animation_sample(state, elapsed, gait_phase)
        step = round(weight*6)
        first = self._pose(a, outfit, side)
        if a == b or step == 0:
            return first
        second = self._pose(b, outfit, side)
        if step == 6:
            return second
        key = ("mix", a, b, step, outfit, side)
        cached = self._cached(key)
        return cached if cached is not None else self._remember(key, blend_pixmaps(first, second, step/6))

    def draw(self, painter, rect, state="idle", elapsed=0, facing=1, outfit="", *, gait_phase=None, motion_time=None, preview=False):
        from .catalog import ITEMS
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(rect.x(), rect.y())
        painter.scale(rect.width()/320, rect.height()/320)
        if facing < 0 and state in PROFILE_STATES:
            painter.translate(320, 0)
            painter.scale(-1, 1)
        clock = elapsed if motion_time is None else motion_time
        # Walking already has gait and whole-window motion. Keep its cached
        # photographs pixel-aligned; resampling the whole cat for a subpixel
        # breath at 60 Hz needlessly burns CPU and makes fur shimmer.
        breathe = 0 if state in {"walk", "pounce", "carried", "play"} else math.sin(clock*(1.5 if state == "sleep" else 2))*.65
        # The baked gait already carries the limb motion. Extra rounded 1px
        # whole-body bobbing made slow walking jitter against desktop icons.
        painter.translate(160, 310)
        painter.scale(1+breathe/850, 1+breathe/400)
        if state == "land":
            squash = math.sin(min(1, elapsed/.2)*math.pi)*.045
            painter.scale(1+squash*.4, 1-squash)
        elif state == "groom":
            painter.rotate(math.sin(clock*2.5)*.6)
        elif state == "pounce":
            painter.rotate(-5+smoothstep(elapsed/.5)*10)
        painter.translate(-160, -310)
        if preview and outfit in ITEMS:
            if self._fronts is None:
                self._fronts = load_cells("outfits-atlas.png", 3, 2)
            source = self._fronts[ITEMS[outfit]["index"]]
            painter.drawPixmap(QRectF(-23, -30, 367, 367), source, source.rect())
        else:
            dpr = painter.device().devicePixelRatioF()
            side = max(1, round(rect.width()*dpr))
            pix = self._frame(state, elapsed, outfit, side, gait_phase)
            painter.drawPixmap(QRectF(0, -80, 320, 400), pix, pix.rect())
        painter.restore()

    def body_region(self, state, side, outfit, facing):
        frames = tuple(range(WALK_BASE, WALK_BASE+WALK_COUNT)) if state == "walk" else tuple(sorted(set(FRAMES.get(state, [0]))))
        mirrored = facing < 0 and state in PROFILE_STATES
        deformation = state if state in {"pounce", "groom", "land"} else ""
        key = (frames, side, outfit, mirrored, deformation)
        if key in self._regions:
            self._regions.move_to_end(key)
            return self._regions[key]
        region = QRegion()
        for index in frames:
            image = self._pose(index, outfit, side).toImage()
            if mirrored:
                image = image.mirrored(True, False)
            region |= QRegion(QPixmap.fromImage(image).mask())
        original = QRegion(region)
        pivot_x, pivot_y = side/2, side*390/320
        angles = (-5, 5) if state == "pounce" else ((-.7, .7) if state == "groom" else ())
        for angle in angles:
            transform = QTransform().translate(pivot_x, pivot_y).rotate(angle).translate(-pivot_x, -pivot_y)
            region |= transform.map(original)
        if state == "land":
            transform = QTransform().translate(pivot_x, pivot_y).scale(1.018, .955).translate(-pivot_x, -pivot_y)
            region |= transform.map(original)
        result = region | region.translated(2, 0) | region.translated(-2, 0) | region.translated(0, 2) | region.translated(0, -2)
        self._regions[key] = result
        while len(self._regions) > 12:
            self._regions.popitem(last=False)
        return result

    def thumbnail(self, outfit="", size=180):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        self.draw(p, QRectF(0, 16, size, size-16), outfit=outfit, preview=True)
        p.end()
        return pix
