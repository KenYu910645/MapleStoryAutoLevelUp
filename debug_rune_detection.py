#!/usr/bin/env python3
"""
詳細除錯符文遊戲檢測
可以測試不同的檢測區域和參數
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

class DebugRuneDetector:
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
        
    def test_multiple_regions(self):
        """
        測試多個不同的檢測區域
        """
        print("🔍 測試多個檢測區域...")
        
        # 原始配置的區域
        original_x, original_y = self.cfg["rune_solver"]["arrow_box_coord"]
        original_size = self.cfg["rune_solver"]["arrow_box_size"]
        
        # 測試不同的區域
        test_regions = [
            # 原始區域
            (original_x, original_y, original_size, "原始區域"),
            # 稍微調整的區域
            (original_x - 50, original_y - 50, original_size, "向左上偏移50"),
            (original_x + 50, original_y - 50, original_size, "向右上偏移50"),
            (original_x - 50, original_y + 50, original_size, "向左下偏移50"),
            (original_x + 50, original_y + 50, original_size, "向右下偏移50"),
            # 更大的區域
            (original_x, original_y, original_size + 40, "更大區域"),
            # 更小的區域
            (original_x, original_y, original_size - 20, "更小區域"),
        ]
        
        best_result = None
        best_score = float('inf')
        
        for x, y, size, description in test_regions:
            print(f"\n🔍 測試區域: {description} ({x}, {y}, {size}x{size})")
            
            # 確保區域在圖片範圍內
            if x < 0 or y < 0 or x + size > self.img_frame.shape[1] or y + size > self.img_frame.shape[0]:
                print(f"   ❌ 區域超出圖片範圍，跳過")
                continue
            
            img_roi = self.img_frame[y:y+size, x:x+size]
            
            # 測試所有箭頭
            region_best_score = float('inf')
            region_best_direction = ""
            
            for direc, arrow_list in self.img_arrows.items():
                for idx, img_arrow in enumerate(arrow_list):
                    _, score, _ = find_pattern_sqdiff(
                        img_roi, img_arrow,
                        mask=get_mask(img_arrow, (0, 255, 0)))
                    
                    if score < region_best_score:
                        region_best_score = score
                        region_best_direction = direc
            
            print(f"   最佳分數: {region_best_score:.4f} ({region_best_direction})")
            
            if region_best_score < best_score:
                best_score = region_best_score
                best_result = (x, y, size, description, region_best_direction)
        
        return best_result, best_score
    
    def visualize_best_region(self, best_result):
        """
        視覺化最佳檢測區域
        """
        if best_result is None:
            print("❌ 沒有找到有效的檢測區域")
            return
        
        x, y, size, description, direction = best_result
        
        # 創建視覺化圖片
        vis_img = self.img_frame.copy()
        
        # 繪製檢測區域
        cv2.rectangle(vis_img, (x, y), (x + size, y + size), (0, 0, 255), 2)
        
        # 添加文字說明
        text = f"Best: {description} - {direction}"
        cv2.putText(vis_img, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 顯示 ROI
        roi = self.img_frame[y:y+size, x:x+size]
        
        # 顯示圖片
        cv2.imshow("最佳檢測區域", vis_img)
        cv2.imshow("ROI 區域", roi)
        
        print(f"\n🎯 最佳檢測區域: {description}")
        print(f"   座標: ({x}, {y}), 大小: {size}x{size}")
        print(f"   方向: {direction}")
        
    def test_different_thresholds(self, best_result):
        """
        測試不同的閾值
        """
        if best_result is None:
            return
        
        x, y, size, description, direction = best_result
        img_roi = self.img_frame[y:y+size, x:x+size]
        
        print(f"\n🔍 測試不同閾值...")
        
        # 測試不同的閾值
        thresholds = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        
        for threshold in thresholds:
            # 找到最佳匹配
            best_score = float('inf')
            for direc, arrow_list in self.img_arrows.items():
                for img_arrow in arrow_list:
                    _, score, _ = find_pattern_sqdiff(
                        img_roi, img_arrow,
                        mask=get_mask(img_arrow, (0, 255, 0)))
                    if score < best_score:
                        best_score = score
            
            detected = best_score < threshold
            status = "✅ 檢測到" if detected else "❌ 未檢測到"
            print(f"   閾值 {threshold:.1f}: 最佳分數 {best_score:.4f} - {status}")
    
    def run_debug(self):
        """
        執行除錯
        """
        print("🚀 開始詳細除錯符文遊戲檢測")
        print(f"📸 測試圖片尺寸: {self.test_image.shape}")
        
        # 測試多個區域
        best_result, best_score = self.test_multiple_regions()
        
        # 視覺化最佳區域
        self.visualize_best_region(best_result)
        
        # 測試不同閾值
        self.test_different_thresholds(best_result)
        
        # 顯示原始圖片
        cv2.imshow("原始測試圖片", self.test_image)
        
        print(f"\n💡 按任意鍵關閉視窗...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        detector = DebugRuneDetector()
        detector.run_debug()
    except Exception as e:
        logger.error(f"除錯失敗: {e}")
        import traceback
        traceback.print_exc() 