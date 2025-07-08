'''
KeyBoardController
'''
# Standard Import
import threading
import time

# Library import
import pyautogui
from pynput import keyboard

# Local import
from logger import logger
from util import is_mac

if is_mac():
    import Quartz
else:
    import pygetwindow as gw

pyautogui.PAUSE = 0  # remove delay
pyautogui.FAILSAFE = False  # Disable fail-safe to prevent exceptions during automation

class KeyBoardController():
    '''
    KeyBoardController
    '''
    def __init__(self, cfg, args):
        self.cfg = cfg
        self.cmd_action = ""
        self.cmd_up_down = ""
        self.cmd_left_right = ""
        self.cmd_up_down_last = ""
        self.cmd_left_right_last = ""
        self.window_title = cfg["game_window"]["title"]
        self.fps = 0 # Frame per seconds
        # Timer
        self.t_last_up = 0.0
        self.t_last_down = 0.0
        self.t_last_toggle = 0.0
        self.t_last_screenshot = 0.0
        self.t_last_jump_down = 0.0
        self.t_last_run = time.time()
        self.t_last_skill = 0.0 # Last time character perform action(attack, cast spell, ...)
        self.t_last_buff_cast = [0] * len(self.cfg["buff_skill"]["keys"]) # Last time cast buff skill
        # Flags
        self.is_enable = True
        self.is_need_screen_shot = False
        self.is_need_toggle = False
        self.is_need_force_heal = False
        self.is_terminated = False
        # Parameters
        self.debounce_interval = self.cfg["system"]["key_debounce_interval"]
        self.fps_limit = self.cfg["system"]["fps_limit_keyboard_controller"]

        # use 'ctrl', 'alt' for mac, because it's hard to get around
        # macOS's security settings
        if is_mac():
            self.toggle_key = keyboard.Key.ctrl
            self.screenshot_key = keyboard.Key.alt
            self.terminate_key = keyboard.Key.esc
        else:
            self.toggle_key = keyboard.Key.f1
            self.screenshot_key = keyboard.Key.f2
            self.terminate_key = keyboard.Key.f12

        # set up attack key
        self.attack_key = ""
        if args.attack == "aoe_skill":
            self.attack_key = cfg["key"]["aoe_skill"]
        elif args.attack == "directional":
            self.attack_key = cfg["key"]["directional_attack"]
        else:
            logger.error(f"Unexpected attack argument: {args.attack}")

        # Start keyboard control thread
        threading.Thread(target=self.run, daemon=True).start()

        listener = keyboard.Listener(on_press=self.on_press)
        listener.start()

    def on_press(self, key):
        '''
        Handle key press events.
        '''
        try:
            # Handle regular character keys
            key.char
        except AttributeError:
            # Handle special keys
            if key == self.toggle_key:
                if time.time() - self.t_last_toggle > self.debounce_interval:
                    self.toggle_enable()
                    self.t_last_toggle = time.time()
            elif key == self.screenshot_key:
                if time.time() - self.t_last_screenshot > self.debounce_interval:
                    self.is_need_screen_shot = True
                    self.t_last_screenshot = time.time()
            elif key == self.terminate_key:
                self.is_terminated = True
                logger.info(f"[on_press] User press terminate key")

    def toggle_enable(self):
        '''
        toggle_enable
        '''
        self.is_enable = not self.is_enable
        logger.info(f"Player pressed F1, is_enable:{self.is_enable}")

        # Make sure all key are released
        self.release_all_key()

    def press_key(self, key, duration=0.05):
        '''
        Simulates a key press for a specified duration
        '''
        if key:
            pyautogui.keyDown(key)
            time.sleep(duration)
            pyautogui.keyUp(key)

    def disable(self):
        '''
        disable keyboard controlller
        '''
        self.is_enable = False

    def enable(self):
        '''
        enable keyboard controlller
        '''
        self.is_enable = True

    def set_command(self, new_command):
        '''
        Set keyboard command
        '''
        self.cmd_left_right, self.cmd_up_down, self.cmd_action = new_command.split()

    def is_game_window_active(self):
        '''
        Check if the game window is currently the active (foreground) window.

        Returns:
        - True
        - False
        '''
        if is_mac():
            active_window = Quartz.CGWindowListCopyWindowInfo(
                Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
                Quartz.kCGNullWindowID
            )
            for window in active_window:
                window_name = window.get(Quartz.kCGWindowName, '')
                if window_name and self.window_title in window_name:
                    return True
            return False
        else:
            try:
                active_window = gw.getActiveWindow()
                if not active_window:
                    return False
                return self.window_title in active_window.title
            except Exception as e:
                return False

    def release_all_key(self):
        '''
        Release all key
        '''
        pyautogui.keyUp("left")
        pyautogui.keyUp("right")
        pyautogui.keyUp("up")
        pyautogui.keyUp("down")
        # Also release attack keys to stop any ongoing attacks
        pyautogui.keyUp(self.attack_key)

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

    def run(self):
        '''
        run
        '''
        while not self.is_terminated:
            # Check if game window is active
            if not self.is_enable or not self.is_game_window_active():
                self.limit_fps()
                continue

            # Buff skill
            for i, buff_skill_key in enumerate(self.cfg["buff_skill"]["keys"]):
                cooldown = self.cfg["buff_skill"]["cooldown"][i]
                if time.time() - self.t_last_buff_cast[i] >= cooldown and \
                    time.time() - self.t_last_skill > self.cfg["buff_skill"]["action_cooldown"]:
                    self.press_key(buff_skill_key)
                    logger.info(f"[Buff] Press buff skill key: '{buff_skill_key}' (cooldown: {cooldown}s)")
                    # Reset timers
                    self.t_last_buff_cast[i] = time.time()
                    self.t_last_skill = time.time()
                    break

            # Force Heal
            if self.is_need_force_heal:
                self.cmd_action = "add_hp"

            ##########################
            ### Left-Right Command ###
            ##########################
            if self.cmd_left_right == "left":
                pyautogui.keyUp("right")
                pyautogui.keyDown("left")
            elif self.cmd_left_right == "right":
                pyautogui.keyUp("left")
                pyautogui.keyDown("right")
            elif self.cmd_left_right == "stop":
                pyautogui.keyUp("left")
                pyautogui.keyUp("right")
            elif self.cmd_left_right == "none":
                if self.cmd_left_right_last != "none":
                    pyautogui.keyUp("left")
                    pyautogui.keyUp("right")
            else:
                logger.error("[KeyBoardController] Unsupported left-right command: "
                             f"{self.cmd_left_right}")
            self.cmd_left_right_last = self.cmd_left_right

            #######################
            ### Up-Down Command ###
            #######################
            if self.cmd_up_down == "up":
                pyautogui.keyUp("down")
                pyautogui.keyDown("up")
            elif self.cmd_up_down == "down":
                pyautogui.keyUp("up")
                pyautogui.keyDown("down")
            elif self.cmd_up_down == "stop":
                pyautogui.keyUp("up")
                pyautogui.keyUp("down")
            elif self.cmd_up_down == "none":
                if self.cmd_up_down_last != "none":
                    pyautogui.keyUp("up")
                    pyautogui.keyUp("down")
            else:
                logger.error("[KeyBoardController] Unsupported up-down command: "
                             f"{self.cmd_up_down}")
            self.cmd_up_down_last = self.cmd_up_down

            ######################
            ### Action Command ###
            ######################
            if self.cmd_action == "jump":
                self.press_key(self.cfg["key"]["jump"])
            elif self.cmd_action == "teleport":
                self.press_key(self.cfg["key"]["teleport"])
            elif self.cmd_action == "attack":
                self.press_key(self.attack_key)
                self.t_last_skill = time.time()
            elif self.cmd_action == "add_hp":
                self.press_key(self.cfg["key"]["add_hp"])
                self.cmd_action = "none"  # Reset command
            elif self.cmd_action == "add_mp":
                self.press_key(self.cfg["key"]["add_mp"])
                self.cmd_action = "none"  # Reset command
            elif self.cmd_action == "goal":
                pass
            elif self.cmd_action == "none":
                pass
            else:
                logger.error("[KeyBoardController] Unsupported action command: "
                             f"{self.cmd_action}")

            self.limit_fps()

        self.release_all_key() # Prevent key keep press down after termination
