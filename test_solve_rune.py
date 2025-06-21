import cv2
from mapleStoryAutoLevelUp import MapleStoryBot
from config.config import Config

# Dummy/mock classes to avoid side effects
class DummyCapture:
    def __init__(self, img):
        self.img = img
    def get_frame(self):
        return self.img.copy()

class DummyKB:
    def press_key(self, key, duration=0.05):
        print(f"[MOCK] press_key: {key}, duration={duration}")
    def disable(self): pass
    def enable(self): pass
    def set_command(self, cmd): pass

class DummyHealthMonitor:
    def __init__(self, *a, **kw): pass
    def start(self): pass
    def update_frame(self, img): pass

def test_solve_rune_with_image(image_path):
    # 1. 載入截圖
    img = cv2.imread(image_path)
    assert img is not None, f"Failed to load {image_path}"

    # 2. 準備假 args
    class Args:
        map = "cloud_balcony"  # 需與 minimaps/ 目錄一致
        monsters = "brown_windup_bear,pink_windup_bear"
        nametag = "name_tag"
        patrol = False
        disable_control = True
        attack = "aoe_skill"
    args = Args()
    bot = MapleStoryBot(args)
    bot.capture = DummyCapture(img)
    bot.kb = DummyKB()
    bot.health_monitor = DummyHealthMonitor()
    bot.status = "near_rune"  # 強制進入 solve_rune 狀態

    # 3. 只跑一次 arrow 辨識（不進入無窮迴圈）
    bot.frame = img
    bot.img_frame = cv2.resize(img, (1296, 759), interpolation=cv2.INTER_NEAREST)
    from util import find_pattern_sqdiff, get_mask

    # 複製一份 debug 圖片
    debug_img = bot.img_frame.copy()

    for arrow_idx in [0, 1, 2, 3]:
        x = bot.cfg.arrow_box_start_point[0] + bot.cfg.arrow_box_interval * arrow_idx
        y = bot.cfg.arrow_box_start_point[1]
        size = bot.cfg.arrow_box_size
        img_roi = bot.img_frame[y:y+size, x:x+size]
        best_score = float('inf')
        best_direction = ""
        print(f"--------------------------------")
        for direction, arrow_list in bot.img_arrows.items():
            for img_arrow in arrow_list:
                _, score, _ = find_pattern_sqdiff(
                    img_roi, img_arrow, mask=get_mask(img_arrow, (0, 255, 0))
                )
                print(f"Arrow({arrow_idx}): {direction}, score={score}")
                if score < best_score:
                    best_score = score
                    best_direction = direction
        print(f"Arrow({arrow_idx}): {best_direction}, score={best_score}")
        # 畫出 ROI 方框
        cv2.rectangle(debug_img, (x, y), (x+size, y+size), (0, 255, 255), 2)
        cv2.putText(debug_img, f"{arrow_idx}", (x+5, y+25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    # 存下 debug 圖片
    cv2.imwrite("debug_arrows_on_image.png", debug_img)
    print("已輸出 debug_arrows_on_image.png，請人工檢查箭頭 ROI 是否正確對齊！")

if __name__ == "__main__":
    test_solve_rune_with_image("testing/rune_detected_2025-06-18_21-11-26.png") 