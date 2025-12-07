# Standard import
import time
import threading

# Library import
import mss
import cv2
import numpy as np
import Quartz

# Local import
from src.utils.logger import logger

def get_window_title(token):
    '''
    Get window title that contain token
    '''
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )
    # Get all exist windows
    for window in window_list:
        logger.debug(f"[get_window_title] Raw window: {window}")
        title = window.get(Quartz.kCGWindowOwnerName, '')
        if token in title:
            logger.info(f"[get_window_title] Found match: {title}")
            return title
    return None


def get_window_region(window_title):
    logger.debug(f"[get_window_region] Looking for: {window_title}")

    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID
    )
    logger.debug(f"[get_window_region] Retrieved {len(window_list)} windows")
    all_titles = []
    for window in window_list:
        logger.debug(f"[get_window_region] Raw window: {window}")
        title = window.get(Quartz.kCGWindowOwnerName, '')
        owner = window.get(Quartz.kCGWindowOwnerName, '')
        if not title:
            logger.debug(f"[get_window_region] Skipped unnamed window: {window}")
        if title:
            all_titles.append(f"{title} (Owner: {owner})")
    logger.debug(f"[get_window_region] All titles: {all_titles}")

    for window in window_list:
        current_title = window.get(Quartz.kCGWindowOwnerName, '')
        logger.debug(f"[get_window_region] Comparing '{current_title}' to target '{window_title}'")
        if current_title == window_title:
            bounds = window.get(Quartz.kCGWindowBounds, {})
            logger.info(f"[get_window_region] Match found. Bounds: {bounds}")
            # Return the region in the format expected by mss
            return {
                "left": int(bounds.get('X', 0)),
                "top": int(bounds.get('Y', 0)),
                "width": int(bounds.get('Width', 0)),
                "height": int(bounds.get('Height', 0))
            }

    # No matching window found
    logger.warning(f"[get_window_region] No window found with title: {window_title}")
    return None


class GameWindowCapturor:
    '''
    GameWindowCapturor for macOS
    '''

    def __init__(self, cfg):
        self.cfg = cfg
        self.frame = None
        self.lock = threading.Lock()
        self.is_terminated = False
        self.window_title = get_window_title(cfg["game_window"]["title"])
        if self.window_title is None:
            logger.error(
                f"[GameWindowCapturor] Unable to find window titles that contain {cfg['game_window']['title']}"
            )
            raise RuntimeError(
                f"[GameWindowCapturor] Unable to find window titles that contain {cfg['game_window']['title']}")

        self.fps = 0
        self.fps_limit = cfg["system"]["fps_limit_window_capturor"]
        self.t_last_run = 0.0

        # 使用 mss 來擷取特定螢幕區域
        self.capture = mss.mss()
        logger.info("[GameWindowCapturor] mss.mss() called")

        # Get game window region
        self.update_window_region()

        # start game window capture
        threading.Thread(target=self.start_capture, daemon=True).start()

        # Wait for initial frame with timeout
        start = time.time()
        while self.frame is None and time.time() - start < 5:
            time.sleep(0.05)

        if self.frame is None:
            raise RuntimeError("[GameWindowCapturor] Failed to capture initial frame.")

    def start_capture(self):
        '''
        開始螢幕擷取，並不斷更新 frame。
        '''
        while not self.is_terminated:
            # Update self.frame
            try:
                self.capture_frame()
            except Exception as e:
                logger.warning(f"[start_capture] Failed to capture frame: {e}")
                # Only update window region if capture fails
                self.update_window_region()

            # Limit FPS to save systme resources
            self.limit_fps()

    def stop(self):
        '''
        Stop capturing thread
        '''
        self.is_terminated = True
        logger.info("[GameWindowCapturor] Terminated")

    def update_window_region(self):
        '''
        Update window region
        '''
        logger.info(f"Searching title: {self.window_title}")
        self.region = get_window_region(self.window_title)
        if self.region is None:
            text = f"[update_window_region] Cannot find window: {self.window_title}"
            logger.error(text)
            raise RuntimeError(text)

    def capture_frame(self):
        '''
        捕捉當前遊戲區域畫面
        '''
        img = self.capture.grab(self.region)
        frame = np.array(img)
        with self.lock:
            self.frame = frame

    def get_frame(self):
        '''
        安全地獲取最新的螢幕畫面
        '''
        with self.lock:
            if self.frame is None:
                return None
            # cv2.imwrite("debug_frame.png", self.frame)
            return cv2.cvtColor(self.frame, cv2.COLOR_BGRA2BGR)

    def on_closed(self):
        '''
        捕捉結束後的回調
        '''
        logger.warning("Capture session closed.")
        cv2.destroyAllWindows()

    def limit_fps(self):
        '''
        Limit FPS
        '''
        # If the loop finished early, sleep to maintain target FPS
        target_duration = 1.0 / self.fps_limit  # seconds per frame
        frame_duration = time.time() - self.t_last_run
        if frame_duration < target_duration:
            time.sleep(target_duration - frame_duration)

        # Update FPS
        self.fps = round(1.0 / (time.time() - self.t_last_run))
        self.t_last_run = time.time()
        # logger.info(f"FPS = {self.fps}")
