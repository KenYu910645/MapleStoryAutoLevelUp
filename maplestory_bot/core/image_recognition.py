"""图像识别模块。

包含：
- 模板匹配（单结果 / 多结果 + 非极大值抑制 NMS）
- 多尺度匹配
- HSV 颜色空间血条百分比分析（红/蓝）
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

# 匹配结果： (x1, y1, x2, y2, score)
MatchResult = Tuple[int, int, int, int, float]


class ImageRecognition:
    """OpenCV 图像识别工具。"""

    # ------------------------------------------------------------------ 模板
    @staticmethod
    def load_template(path: str) -> Optional[np.ndarray]:
        """加载模板图片，返回 BGR 数组；失败返回 None。"""
        if not path:
            return None
        img = cv2.imread(path, cv2.IMREAD_COLOR)
        return img if img is not None else None

    @staticmethod
    def crop_screen(screen: np.ndarray, x: int, y: int, w: int, h: int
                    ) -> np.ndarray:
        """从屏幕截图中裁剪区域。"""
        if screen is None:
            return np.empty((0, 0, 3), dtype=np.uint8)
        H, W = screen.shape[:2]
        x0 = max(0, min(int(x), W - 1))
        y0 = max(0, min(int(y), H - 1))
        x1 = max(x0 + 1, min(int(x + w), W))
        y1 = max(y0 + 1, min(int(y + h), H))
        return screen[y0:y1, x0:x1].copy()

    # ------------------------------------------------------------------ 单匹配
    @staticmethod
    def match_template(screen: Optional[np.ndarray],
                       template: Optional[np.ndarray],
                       threshold: float = 0.75) -> Optional[MatchResult]:
        """单目标模板匹配，返回最佳匹配或 None。"""
        if screen is None or template is None:
            return None
        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            return None
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        if max_val >= threshold:
            h, w = template.shape[:2]
            return (int(max_loc[0]), int(max_loc[1]),
                    int(max_loc[0] + w), int(max_loc[1] + h),
                    float(max_val))
        return None

    # ------------------------------------------------------------------ 多匹配
    @staticmethod
    def match_template_multi(screen: Optional[np.ndarray],
                             template: Optional[np.ndarray],
                             threshold: float = 0.75,
                             max_results: int = 20) -> List[MatchResult]:
        """多目标模板匹配 + 非极大值抑制。"""
        if screen is None or template is None:
            return []
        if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
            return []
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locs = np.where(res >= threshold)
        h, w = template.shape[:2]
        boxes: List[List[float]] = []
        for pt in zip(*locs[::-1]):
            x, y = int(pt[0]), int(pt[1])
            boxes.append([x, y, x + w, y + h, float(res[y, x])])
        boxes = ImageRecognition.non_max_suppression(boxes, overlap_thresh=0.3)
        boxes.sort(key=lambda b: b[4], reverse=True)
        return [(int(b[0]), int(b[1]), int(b[2]), int(b[3]), float(b[4]))
                for b in boxes[:max_results]]

    @staticmethod
    def non_max_suppression(boxes: List[List[float]],
                            overlap_thresh: float = 0.3) -> List[List[float]]:
        """标准非极大值抑制。"""
        if not boxes:
            return []
        arr = np.asarray(boxes, dtype=np.float32)
        x1, y1, x2, y2, scores = arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4]
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        keep: List[int] = []
        while order.size > 0:
            i = order[0]
            keep.append(int(i))
            if order.size == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            iw = np.maximum(0.0, xx2 - xx1 + 1)
            ih = np.maximum(0.0, yy2 - yy1 + 1)
            inter = iw * ih
            iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
            inds = np.where(iou <= overlap_thresh)[0]
            order = order[inds + 1]
        return [boxes[i] for i in keep]

    # ------------------------------------------------------------------ 多尺度
    @staticmethod
    def match_multi_scale(screen: Optional[np.ndarray],
                          template: Optional[np.ndarray],
                          threshold: float = 0.75,
                          scales: Sequence[float] = (0.8, 0.9, 1.0, 1.1, 1.2)
                          ) -> Optional[MatchResult]:
        """多尺度模板匹配，返回最佳匹配。"""
        if screen is None or template is None:
            return None
        best: Optional[MatchResult] = None
        for scale in scales:
            if scale == 1.0:
                scaled = template
            else:
                scaled = cv2.resize(template, None, fx=scale, fy=scale,
                                     interpolation=cv2.INTER_AREA if scale < 1.0
                                     else cv2.INTER_LINEAR)
            if scaled.shape[0] > screen.shape[0] or scaled.shape[1] > screen.shape[1]:
                continue
            res = cv2.matchTemplate(screen, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= threshold and (best is None or max_val > best[4]):
                h, w = scaled.shape[:2]
                best = (int(max_loc[0]), int(max_loc[1]),
                        int(max_loc[0] + w), int(max_loc[1] + h),
                        float(max_val))
        return best

    # ------------------------------------------------------------------ 血条
    @staticmethod
    def analyze_bar_percentage(bar_img: Optional[np.ndarray],
                               color: str = "red") -> float:
        """通过 HSV 颜色比例估算血条百分比（0-100）。"""
        if bar_img is None or bar_img.size == 0:
            return 0.0
        if bar_img.ndim != 3 or bar_img.shape[2] < 3:
            return 0.0

        hsv = cv2.cvtColor(bar_img, cv2.COLOR_BGR2HSV)
        if color.lower() == "red":
            # 红色在 HSV 中跨越 0°，需要两段
            mask1 = cv2.inRange(hsv, np.array([0, 70, 70]),
                                np.array([10, 255, 255]))
            mask2 = cv2.inRange(hsv, np.array([170, 70, 70]),
                                np.array([180, 255, 255]))
            mask = cv2.bitwise_or(mask1, mask2)
        elif color.lower() == "blue":
            mask = cv2.inRange(hsv, np.array([100, 70, 70]),
                              np.array([130, 255, 255]))
        else:
            return 0.0

        total = bar_img.shape[0] * bar_img.shape[1]
        if total == 0:
            return 0.0
        matched = int(cv2.countNonZero(mask))
        return (matched / total) * 100.0

    # ------------------------------------------------------------------ 工具
    @staticmethod
    def center_of(box: MatchResult) -> Tuple[int, int]:
        """返回匹配框中心坐标。"""
        return ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)

    @staticmethod
    def distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """欧氏距离。"""
        return float(np.hypot(a[0] - b[0], a[1] - b[1]))
