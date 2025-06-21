#!/usr/bin/env python3
"""
測試 is_in_rune_game 方法
使用 testing/rune_detected_2025-06-18_21-11-26.png 圖片
"""

import cv2
import numpy as np
import yaml
import sys
import os

# 添加當前目錄到 Python 路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from util import find_pattern_sqdiff, get_mask, load_image, load_yaml, is_mac, override_cfg
from logger import logger

class TestRuneGameDetector:
    def __init__(self):
        # 載入配置
        cfg = load_yaml("config/config_default.yaml")
        if is_mac():
            cfg = override_cfg(cfg, load_yaml("config/config_macOS.yaml"))
        self.cfg = override_cfg(cfg, load_yaml("config/config_edit_me.yaml"))
        
        # 載入箭頭模板
        self.img_arrows = {
            "left": [
                load_image("rune/arrow_left_1.png"),
                load_image("rune/arrow_left_2.png"),
                load_image("rune/arrow_left_3.png"),
            ],
            "right": [
                load_image("rune/arrow_right_1.png"),
                load_image("rune/arrow_right_2.png"),
                load_image("rune/arrow_right_3.png"),
            ],
            "up": [
                load_image("rune/arrow_up_1.png"),
                load_image("rune/arrow_up_2.png"),
                load_image("rune/arrow_up_3.png")
            ],
            "down": [
                load_image("rune/arrow_down_1.png"),
                load_image("rune/arrow_down_2.png"),
                load_image("rune/arrow_down_3.png"),
            ],
        }
        
        # 載入測試圖片
        self.test_image = load_image("testing/rune_detected_2025-06-18_21-11-26.png")
        if self.test_image is None:
            raise RuntimeError("無法載入測試圖片")
        
        # 調整圖片大小到標準尺寸
        self.img_frame = cv2.resize(self.test_image, (1296, 759), interpolation=cv2.INTER_NEAREST)
        
        # 創建除錯圖片
        self.img_frame_debug = self.img_frame.copy()
        
    def is_in_rune_game(self):
        """
        複製原始 is_in_rune_game 方法的邏輯
        """
        # 裁剪箭頭檢測區域
        x, y = self.cfg["rune_solver"]["arrow_box_coord"]
        size = self.cfg["rune_solver"]["arrow_box_size"]
        img_roi = self.img_frame[y:y+size, x:x+size]
        
        print(f"🔍 箭頭檢測區域座標: ({x}, {y}), 大小: {size}x{size}")
        print(f"🔍 ROI 圖片形狀: {img_roi.shape}")
        
        # 檢查箭頭是否存在
        best_score = float('inf')
        best_direction = ""
        best_arrow_idx = -1
        
        for direc, arrow_list in self.img_arrows.items():
            for idx, img_arrow in enumerate(arrow_list):
                _, score, _ = find_pattern_sqdiff(
                    img_roi, img_arrow,
                    mask=get_mask(img_arrow, (0, 255, 0)))
                
                print(f"🔍 方向: {direc}, 箭頭 {idx+1}, 分數: {score:.4f}")
                
                if score < best_score:
                    best_score = score
                    best_direction = direc
                    best_arrow_idx = idx
        
        # 繪製檢測區域
        cv2.rectangle(
            self.img_frame_debug, (x, y), (x + size, y + size),
            (0, 0, 255), 2
        )
        cv2.putText(
            self.img_frame_debug, 
            f"Score: {best_score:.4f} ({best_direction})", 
            (x, y - 10), 
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
        )
        
        threshold = self.cfg["rune_solver"]["arrow_box_diff_thres"]
        print(f"🔍 最佳分數: {best_score:.4f} (方向: {best_direction}, 箭頭: {best_arrow_idx + 1})")
        print(f"🔍 閾值: {threshold}")
        print(f"🔍 是否檢測到符文遊戲: {best_score < threshold}")
        
        return best_score < threshold
    
    def run_test(self):
        """
        執行測試
        """
        print("🚀 開始測試 is_in_rune_game 方法")
        print(f"📸 測試圖片尺寸: {self.test_image.shape}")
        print(f"🖼️ 調整後尺寸: {self.img_frame.shape}")
        
        # 執行檢測
        result = self.is_in_rune_game()
        
        print(f"\n📊 測試結果: {'✅ 檢測到符文遊戲' if result else '❌ 未檢測到符文遊戲'}")
        
        # 顯示圖片
        cv2.imshow("原始測試圖片", self.test_image)
        cv2.imshow("調整後圖片", self.img_frame)
        cv2.imshow("檢測結果", self.img_frame_debug)
        
        print("\n💡 按任意鍵關閉視窗...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        detector = TestRuneGameDetector()
        detector.run_test()
    except Exception as e:
        logger.error(f"測試失敗: {e}")
        import traceback
        traceback.print_exc() 