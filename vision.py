import os
import cv2
import numpy as np
import mss
from config import cfg, TPL_DIR, ITEMS


def get_monitor():
    with mss.mss() as s:
        return s.monitors[1]


def _roi_to_area(roi):
    """Превращает список [x, y, w, h] в dict для mss. None → весь монитор."""
    if roi is None:
        return None
    if not (isinstance(roi, (list, tuple)) and len(roi) == 4):
        return None
    x, y, w, h = (int(v) for v in roi)
    if w <= 0 or h <= 0:
        return None
    return {"left": x, "top": y, "width": w, "height": h}


def grab_screen(roi=None):
    mon = get_monitor()
    area = _roi_to_area(roi) or mon
    with mss.mss() as s:
        return np.array(s.grab(area))


def count_template(gray, name):
    path = os.path.join(TPL_DIR, name + ".png")
    if not os.path.exists(path):
        return 0
    t = cv2.imread(path, 0)
    if t is None or t.shape[0] > gray.shape[0] or t.shape[1] > gray.shape[1]:
        return 0
    thresh = float(cfg.get("thresh", 0.8))
    thresh = min(1.0, max(0.0, thresh))
    r = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
    ys, xs = np.where(r >= thresh)
    pts = []
    for p in zip(xs, ys):
        if all(abs(p[0] - q[0]) > t.shape[1] // 2 or abs(p[1] - q[1]) > t.shape[0] // 2
               for q in pts):
            pts.append(p)
    return len(pts)


def count_shells(bgr):
    if bgr is None or bgr.size == 0:
        return 0, 0
    h, s, v = cv2.split(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV))
    red = (((h <= 10) | (h >= 170)) & (s >= 120) & (v >= 70)).astype(np.uint8) * 255
    dark = ((v <= 70) & (s <= 95)).astype(np.uint8) * 255

    def blobs(m):
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(1, int(cfg.get("min_area", 600)))
        return [(cv2.contourArea(c), cv2.boundingRect(c)[2])
                for c in cs if cv2.contourArea(c) >= min_area]

    R, D = blobs(red), blobs(dark)
    if not R + D:
        return 0, 0
    amax = max(a for a, _ in R + D)
    R = [b for b in R if b[0] >= 0.4 * amax]
    D = [b for b in D if b[0] >= 0.4 * amax]
    if not R + D:
        return 0, 0
    base = min(w for _, w in R + D)

    def n(b):
        r = b[1] / base
        return int(round(r)) if r >= 1.6 else 1

    return sum(n(b) for b in R), sum(n(b) for b in D)


def count_bolts(bgr):
    if bgr is None or bgr.size == 0:
        return 0
    h, s, v = cv2.split(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV))
    m = ((v >= 150) & (s <= 110)).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs = []
    for c in cs:
        _, _, w, hh = cv2.boundingRect(c)
        a = cv2.contourArea(c)
        if a >= 8 and 1.25 * w <= hh <= 4.5 * w and hh >= 6:
            blobs.append(a)
    if not blobs:
        return 0
    amax = max(blobs)
    return sum(1 for a in blobs if a >= 0.5 * amax)


def get_counts_in_roi(roi):
    if not _roi_to_area(roi):
        return {}
    img = grab_screen(roi)
    g = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    result = {}
    for n in ITEMS:
        c = count_template(g, n)
        if c:
            result[n] = c
    return result


def get_bolts_in_roi(roi):
    if not _roi_to_area(roi):
        return 0
    img = grab_screen(roi)
    return count_bolts(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))