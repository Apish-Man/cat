import math
import unittest
from catmate.motion import FramePacer, Locomotion, frame_interval, leap_position

BOUNDS = (-1000, -1000, 2000, 2000)

class MotionTests(unittest.TestCase):
    def test_start_accelerates_instead_of_jumping_to_full_speed(self):
        m = Locomotion()
        first = m.advance(0, 0, 300, 0, 120, 1/60, BOUNDS)
        self.assertGreater(first.x, 0)
        self.assertLess(first.x, 120/60/4)
        self.assertLess(m.vx, 30)

    def test_arrival_decelerates_without_overshoot_or_jitter(self):
        m, x, speeds = Locomotion(), 0.0, []
        for _ in range(600):
            result = m.advance(x, 0, 130, 0, 120, 1/60, BOUNDS)
            self.assertGreaterEqual(result.x, x)
            self.assertLessEqual(result.x, 130)
            x = result.x
            speeds.append(m.vx)
            if result.arrived:
                break
        self.assertTrue(result.arrived)
        self.assertEqual(x, 130)
        self.assertGreater(max(speeds), 80)
        self.assertEqual(m.vx, 0)
        self.assertLess(speeds[-4], max(speeds)/3)

    def test_same_trajectory_at_30_60_and_120_hz(self):
        positions = []
        for hz in (30, 60, 120):
            m, x, y = Locomotion(), 0.0, 0.0
            for _ in range(hz*2):
                step = m.advance(x, y, 800, 300, 125, 1/hz, BOUNDS)
                x, y = step.x, step.y
            positions.append((x, y))
        for position in positions[1:]:
            self.assertLess(math.dist(positions[0], position), .1)

    def test_reversal_preserves_inertia_then_turns(self):
        m, x = Locomotion(), 0.0
        for _ in range(60):
            x = m.advance(x, 0, 500, 0, 120, 1/60, BOUNDS).x
        first = m.advance(x, 0, -500, 0, 120, 1/60, BOUNDS)
        self.assertGreater(first.x, x)
        for _ in range(20):
            first = m.advance(first.x, 0, -500, 0, 120, 1/60, BOUNDS)
        self.assertLess(m.vx, -50)

    def test_offscreen_targets_are_clamped_and_reachable(self):
        m, x, y = Locomotion(), 50.0, 50.0
        for _ in range(500):
            step = m.advance(x, y, 4000, 3000, 180, 1/60, (0, 0, 200, 150))
            x, y = step.x, step.y
            self.assertLessEqual(x, 200)
            self.assertLessEqual(y, 150)
            if step.arrived:
                break
        self.assertTrue(step.arrived)
        self.assertEqual((x, y), (200, 150))

    def test_long_stall_cannot_teleport_cat(self):
        m = Locomotion()
        m.vx = 150
        step = m.advance(0, 0, 1000, 0, 150, 8, BOUNDS)
        self.assertLessEqual(step.x, 7.5)

    def test_idle_has_no_gait_distance(self):
        step = Locomotion().advance(12, 8, 12, 8, 120, 1/60, BOUNDS)
        self.assertEqual(step.distance, 0)
        self.assertTrue(step.arrived)

    def test_leap_is_continuous_and_lands_exactly(self):
        self.assertEqual(leap_position((0, 100), (200, 100), 0, 60), (0, 100))
        self.assertAlmostEqual(leap_position((0, 100), (200, 100), .5, 60)[1], 40)
        end = leap_position((0, 100), (200, 100), 1, 60)
        self.assertAlmostEqual(end[0], 200)
        self.assertAlmostEqual(end[1], 100)

    def test_sleep_hidden_and_eco_reduce_wakeups(self):
        self.assertEqual(frame_interval("walk"), 16)
        self.assertEqual(frame_interval("sleep"), 125)
        self.assertEqual(frame_interval("sleep", eco=True), 500)
        self.assertEqual(frame_interval("walk", eco=True), 33)
        self.assertEqual(frame_interval("walk", hidden=True), 1000)

    def test_pacer_tracks_sixty_hz_instead_of_sixty_two_point_five(self):
        pacer, now = FramePacer(), 0.0
        for _ in range(120):
            now += pacer.delay_ms(now, 16)/1000
        self.assertAlmostEqual(now, 2.0, delta=.002)

    def test_pacer_skips_stalled_frames_without_fast_catchup(self):
        pacer = FramePacer()
        pacer.delay_ms(0, 16)
        self.assertGreaterEqual(pacer.delay_ms(3.5, 16), 16)

    def test_pacer_keeps_thirty_hz_eco_and_coarse_sleep(self):
        pacer, now = FramePacer(), 0.0
        for _ in range(60):
            now += pacer.delay_ms(now, 33)/1000
        self.assertAlmostEqual(now, 2.0, delta=.002)
        self.assertEqual(pacer.delay_ms(now, 500), 500)

if __name__ == "__main__":
    unittest.main()
