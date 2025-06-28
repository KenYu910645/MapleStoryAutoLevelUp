'''
KeyBoardListener
'''
# Standard Import
import threading
import time

import pyautogui
import pygetwindow as gw
from pynput import keyboard

# Local import
from logger import logger

pyautogui.PAUSE = 0  # remove delay
pyautogui.FAILSAFE = False  # Disable fail-safe to prevent exceptions during automation

class KeyBoardListener():
    '''
    KeyBoardListener
    '''
    def __init__(self, cfg):
        self.cfg = cfg
        self.t_last_run = time.time()
        self.is_enable = True
        self.window_title = cfg["game_window"]["title"]
        self.debounce_interval = 1 # second
        self.is_need_screen_shot = False
        self.is_need_toggle = False
        self.fps = 0
        self.fps_limit = 30
        self.key_pressing = [] # record the key pressed by user
        self.is_pressed_func_key = [False]*12  # 'F1', 'F2', .... 'F12'

        # Timer
        self.t_func_key = [0]*12 # 'F1', 'F2', .... 'F12'


        # Keys
        self.movement_keys = {
            keyboard.Key.up: "up",
            keyboard.Key.down: "down",
            keyboard.Key.left: "left",
            keyboard.Key.right: "right",
            keyboard.Key.space: "space"
        }
        self.func_keys = {
            getattr(keyboard.Key, f"f{i+1}"): i for i in range(12)
        }

        # Start keyboard control thread
        threading.Thread(target=self.run, daemon=True).start()

        listener = keyboard.Listener(on_press=self.on_press,
                                     on_release=self.on_release)
        listener.start()

    def on_release(self, key):
        '''
        Handle key release events and update key_pressing list.
        '''
        try:
            # Regular keys (like 'a', '1', etc.)
            k = key.char.lower()
        except AttributeError:
            k = self.movement_keys.get(key, None)

        # Remove the key from key_pressing list if it's in there
        if k in self.key_pressing:
            self.key_pressing.remove(k)


    def on_press(self, key):
        '''
        Handle key press events.
        '''
        try:
            # Regular character keys (e.g., 'a', 'w', '1')
            k = key.char.lower()
        except AttributeError:
            # Handle F1, F2, F3, ... F12
            if key in self.func_keys:
                idx = self.func_keys[key]
                if time.time() - self.t_func_key[idx] > self.debounce_interval:
                    self.is_pressed_func_key[idx] = True
                    self.t_func_key[idx] = time.time()

            k = self.movement_keys.get(key, None)

        if k and k not in self.key_pressing:
            self.key_pressing.append(k)

    def toggle_enable(self):
        '''
        toggle_enable
        '''
        # self.is_enable = not self.is_enable
        logger.info(f"Player pressed F1, is_enable:{self.is_enable}")

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

    def is_game_window_active(self):
        '''
        Check if the game window is currently the active (foreground) window.

        Returns:
        - True
        - False
        '''
        active_window = gw.getActiveWindow()
        return active_window is not None and self.window_title in active_window.title

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
        while True:
            # Check if game window is active
            if not self.is_enable or not self.is_game_window_active():
                self.limit_fps()
                continue

            self.limit_fps()
