"""Build-time single-source motion warps; NEVER imported by the desktop app.

Each intermediate image samples exactly one registered keyframe. Optical flow
changes geometry, not opacity: unlike a dissolve this cannot double-expose two
different leg/head positions. Runtime only reads the resulting PNG frames.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication
from catmate.art import Art

STEPS = 6
SIDE = 256
HEIGHT = 320

def rgba(pixmap):
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    return np.frombuffer(image.bits(), dtype=np.uint8).reshape(image.height(), image.width(), 4).copy()

def feature(image):
    a = image[:, :, 3:4].astype(np.float32)/255
    rgb = image[:, :, :3].astype(np.float32)*a + 128*(1-a)
    gray = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    return cv2.GaussianBlur(gray, (5, 5), .8)

def register(frames):
    """Remove small AI-sheet camera shifts using only the stable head/torso."""
    result = [frames[0]]
    reference = feature(frames[0])
    roi = (slice(125, 255), slice(90, 250))
    mask = (frames[0][roi][:, :, 3] > 200).astype(np.uint8)*255
    translations = [[0., 0.]]
    for image in frames[1:]:
        matrix = np.eye(2, 3, dtype=np.float32)
        try:
            cv2.findTransformECC(reference[roi], feature(image)[roi], matrix,
                cv2.MOTION_TRANSLATION, (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 50, .0005), mask, 5)
            matrix[0, 2] = np.clip(matrix[0, 2], -8, 8)
            matrix[1, 2] = np.clip(matrix[1, 2], -3, 3)
        except cv2.error:
            matrix = np.eye(2, 3, dtype=np.float32)
        gy, gx = np.mgrid[0:HEIGHT, 0:SIDE].astype(np.float32)
        taper = np.clip((gy-240)/55, 0, 1)
        taper = 1-taper*taper*(3-2*taper)
        # Align head/torso without lifting the planted feet off the ground.
        result.append(cv2.remap(image, gx+matrix[0, 2], gy+matrix[1, 2]*taper,
            cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT))
        translations.append(matrix[:, 2].tolist())
    return result, translations

def flow_between(first, second):
    solver = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    solver.setFinestScale(0)
    solver.setGradientDescentIterations(30)
    solver.setVariationalRefinementIterations(5)
    flow = solver.calc(feature(first), feature(second), None)
    flow = cv2.GaussianBlur(flow, (7, 7), 1.2)
    # Registered head and torso should stay solid instead of wobbling with fur
    # texture differences. The lower legs retain the full inferred displacement.
    y = np.arange(HEIGHT, dtype=np.float32)[:, None]
    phase = np.clip((y-225)/55, 0, 1)
    mobility = .2+.8*phase*phase*(3-2*phase)
    flow *= mobility[:, :, None]
    return np.clip(flow, -36, 36).astype(np.float32)

def warp_one(image, flow, amount):
    if amount == 0:
        return image.copy()
    gy, gx = np.mgrid[0:HEIGHT, 0:SIDE].astype(np.float32)
    mx, my = gx.copy(), gy.copy()
    for _ in range(4):
        sampled = cv2.remap(flow, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        mx, my = gx-amount*sampled[:, :, 0], gy-amount*sampled[:, :, 1]
    # Premultiply before spatial resampling so arbitrary transparent RGB cannot
    # create halos at whiskers. This is not mixing two temporal photographs.
    source = image.astype(np.float32)
    source[:, :, :3] *= source[:, :, 3:4]/255
    warped = cv2.remap(source, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    a = warped[:, :, 3:4]
    warped[:, :, :3] = np.divide(warped[:, :, :3]*255, a, out=np.zeros_like(warped[:, :, :3]), where=a > 0)
    return np.clip(np.rint(warped), 0, 255).astype(np.uint8)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outfits", nargs="*", default=["bare", "birthday", "blue", "daisy", "christmas", "newyear", "pig"])
    args = parser.parse_args()
    cv2.setNumThreads(1)
    app = QApplication([])
    art = Art()
    directory = ROOT/"assets"/"walk"
    directory.mkdir(parents=True, exist_ok=True)
    metadata = {"version": 1, "frames": 24, "columns": 6, "rows": 4, "tile": [SIDE, HEIGHT],
        "method": "registered bidirectional flow; nearest temporal keyframe warped alone; NO crossfade", "outfits": {}}
    for name in args.outfits:
        outfit = "" if name == "bare" else name
        keys, translations = register([rgba(art._pose(index, outfit, SIDE)) for index in (4, 5, 6, 7)])
        output = []
        for index in range(4):
            a, b = keys[index], keys[(index+1) % 4]
            forward, backward = flow_between(a, b), flow_between(b, a)
            for step in range(STEPS):
                t = step/STEPS
                output.append(warp_one(a, forward, t) if t < .5 else warp_one(b, backward, 1-t))
        sheet = Image.new("RGBA", (SIDE*6, HEIGHT*4))
        for index, frame in enumerate(output):
            sheet.paste(Image.fromarray(frame), ((index % 6)*SIDE, (index//6)*HEIGHT))
        path = directory/f"{name}.png"
        sheet.save(path, optimize=True)
        metadata["outfits"][name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "camera_registration": translations}
        print(f"Baked {name}: 24 single-source frames", flush=True)
    (directory/"manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
