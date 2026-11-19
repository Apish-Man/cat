"""Time-based bounded motion and refresh policy; no GUI dependencies."""
import math
from dataclasses import dataclass

def smoothstep(value):
    v = max(0.0, min(1.0, value))
    return v*v*(3-2*v)

@dataclass
class MotionStep:
    x: float
    y: float
    distance: float
    arrived: bool

class Locomotion:
    def __init__(self):
        self.vx = self.vy = 0.0

    def reset(self):
        self.vx = self.vy = 0.0

    def advance(self, x, y, tx, ty, speed, dt, bounds):
        dt = max(0, min(.05, dt))
        left, top, right, bottom = bounds
        tx, ty = max(left, min(right, tx)), max(top, min(bottom, ty))
        dx, dy = tx-x, ty-y
        remaining = math.hypot(dx, dy)
        if remaining <= .65 and math.hypot(self.vx, self.vy) < 8:
            self.reset()
            return MotionStep(tx, ty, remaining, True)
        desired = min(max(0, speed), remaining*3.0)
        gx, gy = (dx/remaining*desired, dy/remaining*desired) if remaining > 1e-9 else (0, 0)
        tau = .08 if remaining < speed/3 else .115
        decay = math.exp(-dt/tau)
        sx = gx*dt + (self.vx-gx)*tau*(1-decay)
        sy = gy*dt + (self.vy-gy)*tau*(1-decay)
        self.vx = gx + (self.vx-gx)*decay
        self.vy = gy + (self.vy-gy)*decay
        if remaining and sx*dx+sy*dy >= remaining*remaining:
            sx, sy = dx, dy
            self.reset()
        nx, ny = max(left, min(right, x+sx)), max(top, min(bottom, y+sy))
        if nx != x+sx:
            self.vx = 0
        if ny != y+sy:
            self.vy = 0
        arrived = math.hypot(tx-nx, ty-ny) < .65 and math.hypot(self.vx, self.vy) < 8
        if arrived:
            nx, ny = tx, ty
            self.reset()
        return MotionStep(nx, ny, math.hypot(nx-x, ny-y), arrived)

def frame_interval(state, active=False, transitioning=False, eco=False, hidden=False):
    if hidden:
        return 1000
    if active or transitioning or state in {"walk", "pounce", "land", "bat", "wake", "carried"}:
        return 33 if eco else 16
    if state == "sleep":
        return 500 if eco else 125
    return 166 if eco else 83

def leap_position(start, end, progress, height):
    t = max(0, min(1, progress))
    u = smoothstep(t)
    return start[0]+(end[0]-start[0])*u, start[1]+(end[1]-start[1])*u-math.sin(math.pi*t)*height

class FramePacer:
    """Exact 60/30 Hz deadlines without catch-up bursts when the PC is busy."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.deadline = self.period = None

    def delay_ms(self, now, interval):
        period = 1/60 if interval == 16 else (1/30 if interval == 33 else interval/1000)
        if self.period != period or self.deadline is None:
            self.deadline, self.period = now+period, period
        else:
            self.deadline += period
            if self.deadline-now < period*.35:
                self.deadline = now+period
        return max(1, math.ceil((self.deadline-now)*1000-.001))
