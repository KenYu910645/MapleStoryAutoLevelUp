import threading
import time
import cv2

# Local import
from logger import logger
from util import get_bar_ratio

class HealthMonitor:
    '''
    Independent health monitoring thread that can heal while other actions are running
    '''
    def __init__(self, cfg, args, kb_controller):
        self.cfg = cfg
        self.args = args
        self.kb = kb_controller
        self.running = False
        self.enabled = True
        self.thread = None

        # Health monitoring state
        self.hp_ratio = 1.0
        self.mp_ratio = 1.0
        self.exp_ratio = 1.0

        # Timers
        self.last_heal_time = 0
        self.last_mp_time = 0
        self.last_hp_reduce_time = 0
        self.t_last_run = 0

        # Frame data (will be updated by main thread)
        self.img_frame = None
        self.frame_lock = threading.Lock()

        self.fps_limit = self.cfg["health_monitor"]["fps_limit"]
        self.fps = 0

        # Debug information
        # hp/mp/exp bars loc and size, [(x,y,w,h), ...]
        self.loc_size_bars = [(0, 0, 0, 0),
                              (0, 0, 0, 0),
                              (0, 0, 0, 0)]

    def start(self):
        '''
        Start health monitoring thread
        '''
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self.thread.start()
            logger.info("[Health Monitor]: Started")

    def stop(self):
        '''
        Stop health monitoring thread
        '''
        self.running = False
        if self.thread:
            self.thread.join()
            logger.info("[Health Monitor]: Stopped")

    def enable(self):
        '''
        Enable health monitoring
        '''
        self.enabled = True

    def disable(self):
        '''
        Disable health monitoring
        '''
        self.enabled = False

    def update_frame(self, img_frame):
        '''
        Update frame data from main thread
        '''
        with self.frame_lock:
            self.img_frame = img_frame

    def get_hp_mp_exp_ratio(self):
        '''
        Extracts the player's HP, MP, and EXP ratios from game frame.

        This function:
        - Crops the predefined HP, MP, and EXP bar regions from the game frame.
        - Identifies empty areas in each bar.
        - Computes the fill ratio for each bar as: 1 - (empty_pixels / total_pixels).

        Returns:
            tuple: (hp_ratio, mp_ratio, exp_ratio), each a float between 0 and 1.
        '''
        if self.img_frame is None:
            return None, None, None

        with self.frame_lock:
            img_frame = self.img_frame.copy()

        img_frame_gray = cv2.cvtColor(img_frame, cv2.COLOR_BGR2GRAY)
        white_mask = cv2.inRange(img_frame_gray, 240, 255)
        # cv2.imshow("white_mask", white_mask)

        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        loc_size_bars = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            # for game window resolution 752x1282, w/h == 7.5, w*h == 3630
            if 4 < w/h < 10 and 2500 < w*h < 5000:
                loc_size_bars.append((x, y, w, h))

        # sort contours by x coordinate
        loc_size_bars = sorted(loc_size_bars, key=lambda bar: bar[0])
        if len(loc_size_bars) != 3:
            logger.warning(f"[Health Monitor]: HP/MP/EXP bar detection has an unexpected result:{loc_size_bars}")
            return (None, None, None)

        # Update loc_size_bars
        self.loc_size_bars = loc_size_bars

        # Get bar filled ratio
        ratio_bars = []
        for x, y, w, h in loc_size_bars:
            ratio_bars.append(get_bar_ratio(img_frame[y:y+h, x:x+w]))
        return ratio_bars

    def get_hp_mp_ratio_legacy(self):
        '''
        Deprecated: This hp/mp bar detection method require specific window resolution as input
                    and use hard-coded pixel coordinate to capture hp/mp bar
                    This function is replaced by get_hp_mp_exp_ratio() which is more flexiable and
                    can work on different window resolution
        Extract HP and MP ratios from current frame
        '''
        if self.img_frame is None:
            return 1.0, 1.0

        with self.frame_lock:
            img_frame = self.img_frame.copy()

        # HP crop
        hp_bar = img_frame[self.cfg.hp_bar_top_left[1]:self.cfg.hp_bar_bottom_right[1]+1,
                          self.cfg.hp_bar_top_left[0]:self.cfg.hp_bar_bottom_right[0]+1]
        # MP crop
        mp_bar = img_frame[self.cfg.mp_bar_top_left[1]:self.cfg.mp_bar_bottom_right[1]+1,
                          self.cfg.mp_bar_top_left[0]:self.cfg.mp_bar_bottom_right[0]+1]

        # HP Detection (detect empty part)
        empty_mask_hp = (hp_bar[:,:,0] == hp_bar[:,:,1]) & (hp_bar[:,:,0] == hp_bar[:,:,2])
        empty_pixels_hp = max(0, len(empty_mask_hp[empty_mask_hp]) - 6)  # 6 pixel always be white
        total_pixels_hp = hp_bar.shape[0] * hp_bar.shape[1] - 6
        hp_ratio = 1 - (empty_pixels_hp / max(1, total_pixels_hp))

        # MP Detection (detect empty part)
        empty_mask_mp = (mp_bar[:,:,0] == mp_bar[:,:,1]) & (mp_bar[:,:,0] == mp_bar[:,:,2])
        empty_pixels_mp = max(0, len(empty_mask_mp[empty_mask_mp]) - 6)  # 6 pixel always be white
        total_pixels_mp = mp_bar.shape[0] * mp_bar.shape[1] - 6
        mp_ratio = 1 - (empty_pixels_mp / max(1, total_pixels_mp))

        return max(0, min(1, hp_ratio)), max(0, min(1, mp_ratio))

    def _monitor_loop(self):
        '''
        Main monitoring loop running in separate thread
        '''
        while self.running:
            try:
                if not self.enabled or self.args.disable_control:
                    self.limit_fps()
                    continue

                # Get current HP/MP ratios
                hp_ratio, mp_ratio, exp_ratio = self.get_hp_mp_exp_ratio()
                if hp_ratio is not None:
                    # Check if HP bar has reduced
                    if self.hp_ratio > hp_ratio:
                        self.last_hp_reduce_time = time.time()
                    self.hp_ratio = hp_ratio
                if mp_ratio is not None:
                    self.mp_ratio = mp_ratio
                if exp_ratio is not None:
                    self.exp_ratio = exp_ratio

                current_time = time.time()

                # Check if need to heal (with cooldown)
                if (self.hp_ratio <= self.cfg["health_monitor"]["add_hp_ratio"] and
                    current_time - self.last_heal_time > self.cfg["health_monitor"]["add_hp_cooldown"]):
                    self._heal()
                    self.last_heal_time = current_time
                    # logger.info(f"[Health Monitor]: Auto heal triggered, HP: {self.hp_ratio*100:.1f}%")

                # Check if need MP (with cooldown)
                if (self.mp_ratio <= self.cfg["health_monitor"]["add_mp_ratio"] and
                    current_time - self.last_mp_time > self.cfg["health_monitor"]["add_mp_cooldown"]):
                    self._add_mp()
                    self.last_mp_time = current_time
                    # logger.info(f"[Health Monitor]: Auto MP triggered, MP: {self.mp_ratio*100:.1f}%")

                # Sleep to avoid excessive CPU usage
                self.limit_fps()

            except Exception as e:
                logger.error(f"[Health Monitor]: {e}")
                self.limit_fps()

    def _heal(self):
        '''
        Execute heal action
        '''
        try:
            self.kb.press_key(self.cfg["key"]["add_hp"], 0.05)
        except Exception as e:
            logger.error(f"[Health Monitor]: Heal action failed: {e}")

    def _add_mp(self):
        '''
        Execute MP recovery action
        '''
        try:
            self.kb.press_key(self.cfg["key"]["add_mp"], 0.05)
        except Exception as e:
            logger.error(f"[Health Monitor]: MP action failed: {e}")

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
