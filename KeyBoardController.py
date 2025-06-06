import threading
import time
import keyboard
import pygetwindow as gw

class KeyBoardController():
    '''
    KeyBoardController
    '''
    def __init__(self, cfg):
        self.cfg = cfg
        self.command = ""
        self.t_last_up = 0.0
        self.is_enable = True
        self.window_title = cfg.game_window_title
        self.attack_key = ""

        # set up attack key
        if cfg.is_use_aoe:
            self.attack_key = cfg.aoe_skill_key
        else:
            self.attack_key = cfg.magic_claw_key

        # Register F1 hotkey to toggle enable/disable
        keyboard.add_hotkey('F1', self.toggle_enable)

        # Start keyboard control thread
        threading.Thread(target=self.run, daemon=True).start()

    def toggle_enable(self):
        '''
        toggle_enable
        '''
        self.is_enable = not self.is_enable
        print(f"Player pressed F1, is_enable:{self.is_enable}")

        # Make sure all key are released
        self.release_all_key()

    def press_key(self, key, duration):
        '''
        Simulates a key press for a specified duration
        '''
        keyboard.press(key)
        time.sleep(duration)
        keyboard.release(key)

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
        self.command = new_command

    def is_game_window_active(self):
        '''
        Check if the game window is currently the active (foreground) window.

        Returns:
        - True
        - False
        '''
        active_window = gw.getActiveWindow()
        return active_window is not None and self.window_title in active_window.title

    def release_all_key(self):
        '''
        Release all key
        '''
        keyboard.release("left")
        keyboard.release("right")
        keyboard.release("up")
        keyboard.release("down")

    def run(self):
        '''
        run
        '''
        while True:
            # Check if game window is active
            if not self.is_enable or not self.is_game_window_active():
                time.sleep(0.001)
                continue

            # check if is needed to release 'Up' key
            if time.time() - self.t_last_up > self.cfg.up_drag_duration:
                keyboard.release("up")

            if self.command == "walk left":
                keyboard.release("right")
                keyboard.press("left")

            elif self.command == "walk right":
                keyboard.release("left")
                keyboard.press("right")

            elif self.command == "jump left":
                keyboard.release("right")
                keyboard.press("left")
                self.press_key(self.cfg.jump_key, 0.02)
                keyboard.release("left")

            elif self.command == "jump right":
                keyboard.release("left")
                keyboard.press("right")
                self.press_key(self.cfg.jump_key, 0.02)
                keyboard.release("right")

            elif self.command == "jump down":
                keyboard.release("right")
                keyboard.release("left")
                keyboard.press("down")
                self.press_key(self.cfg.jump_key, 0.02)
                keyboard.release("down")

            elif self.command == "jump":
                keyboard.release("left")
                keyboard.release("right")
                self.press_key(self.cfg.jump_key, 0.02)

            elif self.command == "up":
                keyboard.press("up")
                self.t_last_up = time.time()

            if self.command == "teleport left":
                keyboard.release("right")
                keyboard.press("left")
                self.press_key(self.cfg.teleport_key, 0.02)

            elif self.command == "teleport right":
                keyboard.release("left")
                keyboard.press("right")
                self.press_key(self.cfg.teleport_key, 0.02)

            elif self.command == "teleport up":
                keyboard.press("up")
                self.press_key(self.cfg.teleport_key, 0.02)
                keyboard.release("up")

            elif self.command == "teleport down":
                keyboard.press("down")
                self.press_key(self.cfg.teleport_key, 0.02)
                keyboard.release("down")

            elif self.command == "attack":
                self.press_key(self.attack_key, 0.02)

            elif self.command == "attack left":
                keyboard.release("right")
                keyboard.press("left")
                self.press_key(self.attack_key, 0.02)
                keyboard.release("left")

            elif self.command == "attack right":
                keyboard.release("left")
                keyboard.press("right")
                self.press_key(self.attack_key, 0.02)
                keyboard.release("right")

            elif self.command == "stop":
                self.release_all_key()

            elif self.command == "heal":
                self.press_key(self.cfg.heal_key, 0.02)
                self.command = ""

            elif self.command == "add mp":
                self.press_key(self.cfg.add_mp_key, 0.02)
                self.command = ""

            else:
                pass

            time.sleep(0.001)
