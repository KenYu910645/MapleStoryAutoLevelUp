'''
Execute this script:
python mapleStoryAutoLevelUp.py --map cloud_balcony --monster brown_windup_bear,pink_windup_bear
'''
# Standard import
import time
import random
import argparse
import glob
import sys
import logging
import os
import datetime

# Library import
import numpy as np
import cv2
import yaml

# Local import
from logger import logger
from util import find_pattern_sqdiff, draw_rectangle, screenshot, nms, \
                load_image, get_mask, get_minimap_loc_size, get_player_location_on_minimap, \
                is_mac, nms_matches, override_cfg, load_yaml, get_all_other_player_locations_on_minimap, \
                click_in_game_window, mask_route_colors, to_opencv_hsv, debug_minimap_colors, \
                activate_game_window, is_img_16_to_9

from KeyBoardController import KeyBoardController
if is_mac():
    from GameWindowCapturorForMac import GameWindowCapturor
else:
    from GameWindowCapturor import GameWindowCapturor
from HealthMonitor import HealthMonitor
from profiler import Profiler

class MapleStoryBot:
    '''
    MapleStoryBot
    '''
    def __init__(self, args):
        '''
        Init MapleStoryBot
        '''
        self.args = args # User args
        self.status = "hunting" # 'finding_rune', 'near_rune'
        self.idx_routes = 0 # Index of route map
        self.monster_info = [] # monster information
        self.fps = 0 # Frame per second
        self.red_dot_center_prev = None # previous other player location in minimap
        # Flags
        self.is_first_frame = True # first frame flag
        self.is_terminated = False # Close all object and thread if True
        self.is_on_ladder = False # Character is on ladder or not
        # Coordinate (top-left coordinate)
        self.loc_nametag = (0, 0) # nametag location on game screen
        self.loc_party_red_bar = (0, 0) # party red bar location on game screen
        self.loc_minimap = (0, 0) # minimap location on game screen
        self.loc_player = (0, 0) # player location on game screen
        self.loc_player_minimap = (0, 0) # player location on minimap
        self.loc_minimap_global = (0, 0) # minimap location on global map
        self.loc_player_global = (0, 0) # player location on global map
        self.loc_watch_dog = (0, 0) # watch dog location on global map
        self.loc_rune = (0, 0) # rune location on game screen
        # Images
        self.frame = None # raw image
        self.img_frame = None # game window frame
        self.img_frame_gray = None # game window frame graysale
        self.img_frame_debug = None # game window frame for visualization
        self.img_route = None # route map
        self.img_route_debug = None # route map for visualization
        self.img_minimap = np.zeros((10, 10, 3), dtype=np.uint8) # minimap on game screen
        # Timers
        self.t_last_frame = time.time() # Last frame timer, for fps calculation
        self.t_last_switch_status = time.time() # Last status switches timer
        self.t_watch_dog = time.time() # Last movement timer
        self.t_last_teleport = time.time() # Last teleport timer
        self.t_patrol_last_attack = time.time() # Last patrol attack timer
        self.t_last_attack = time.time() # Last attack timer for cooldown
        self.t_last_rune_trigger = time.time() # Last time trigger rune
        self.t_rune_finding_start = 0 # Start time of rune finding. Reset when 'channel_change' and 'solve_rune'.
        self.t_last_minimap_update = time.time()
        # Patrol mode
        self.is_patrol_to_left = True # Patrol direction flag
        self.patrol_turn_point_cnt = 0 # Patrol tuning back counter

        # Load defautl yaml config
        cfg = load_yaml("config/config_default.yaml")
        # Override with platform config
        if is_mac():
            cfg = override_cfg(cfg, load_yaml("config/config_macOS.yaml"))
        # Override with user customized config
        self.cfg = override_cfg(cfg, load_yaml(f"config/config_{args.cfg}.yaml"))
        # Dump config to log for debugging
        logger.debug(yaml.dump(self.cfg, sort_keys=False,
                     indent=2, default_flow_style=False))

        # Parse color code
        self.color_code = {
            tuple(map(int, k.split(','))): v
            for k, v in cfg["route"]["color_code"].items()
        }
        self.color_code_up_down = {
            tuple(map(int, k.split(','))): v
            for k, v in cfg["route"]["color_code_up_down"].items()
        }

        self.is_show_debug_window = self.cfg["system"]["show_debug_window"]

        # Set status to hunting for startup
        if args.aux:
            self.switch_status("aux")
        else:
            self.switch_status("hunting")

        if args.patrol or args.aux:
            # Patrol and aux mode doesn't need map or route
            self.img_map = None
            self.img_routes = []
        else:
            # Load map.png from minimaps/
            self.img_map = load_image(f"minimaps/{args.map}/map.png",
                                      cv2.IMREAD_COLOR)
            # Load route*.png from minimaps/
            route_files = sorted(glob.glob(f"minimaps/{args.map}/route*.png"))
            route_files = [p for p in route_files if not p.endswith("route_rest.png")]
            self.img_routes = []
            for route_file in route_files:
                img = cv2.cvtColor(load_image(route_file), cv2.COLOR_BGR2RGB)
                # Remove pixel in map that is color code
                img = mask_route_colors(self.img_map, img, self.cfg["route"]["color_code"])
                img = mask_route_colors(self.img_map, img, self.cfg["route"]["color_code_up_down"])
                self.img_routes.append(img)

        # Load player's name tag
        self.img_nametag = load_image(f"nametag/{args.nametag}.png")
        self.img_nametag_gray = load_image(f"nametag/{args.nametag}.png", cv2.IMREAD_GRAYSCALE)

        # Load rune images from rune/
        rune_ver = self.cfg["system"]["language"]
        if rune_ver == "chinese":
            self.img_rune_warning = load_image("rune/rune_warning.png", cv2.IMREAD_GRAYSCALE)
        elif rune_ver == "english":
            self.img_rune_warning = load_image("rune/rune_warning_eng.png", cv2.IMREAD_GRAYSCALE)
        else:
            logger.error(f"Unsupported rune warning version: {rune_ver}")

        self.img_runes = [load_image("rune/rune_1.png"),
                          load_image("rune/rune_2.png"),
                          load_image("rune/rune_3.png"),]
        if rune_ver == "english":
            self.img_runes[1] = load_image("rune/rune_2_eng.png")

        self.img_arrows = {
            "left":
                [load_image("rune/arrow_left_1.png"),
                load_image("rune/arrow_left_2.png"),
                load_image("rune/arrow_left_3.png"),],
            "right":
                [load_image("rune/arrow_right_1.png"),
                load_image("rune/arrow_right_2.png"),
                load_image("rune/arrow_right_3.png"),],
            "up":
                [load_image("rune/arrow_up_1.png"),
                load_image("rune/arrow_up_2.png"),
                load_image("rune/arrow_up_3.png")],
            "down":
                [load_image("rune/arrow_down_1.png"),
                load_image("rune/arrow_down_2.png"),
                load_image("rune/arrow_down_3.png"),],
        }

        # Load monsters images from monster/{monster_name}
        self.monsters = {}
        for monster_name in args.monsters.split(","):
            imgs = []
            for file in glob.glob(f"monster/{monster_name}/{monster_name}*.png"):
                # Add original image
                img = load_image(file)
                imgs.append((img, get_mask(img, (0, 255, 0))))
                # Add flipped image
                img_flip = cv2.flip(img, 1)
                imgs.append((img_flip, get_mask(img_flip, (0, 255, 0))))
            if imgs:
                self.monsters[monster_name] = imgs
            else:
                logger.error(f"No images found in monster/{monster_name}/{monster_name}*")
                raise RuntimeError(f"No images found in monster/{monster_name}/{monster_name}*")
        logger.info(f"Loaded monsters: {list(self.monsters.keys())}")

        # Load misc image
        self.img_create_party_enable  = load_image("misc/party_button_create_enable.png")
        self.img_create_party_disable = load_image("misc/party_button_create_disable.png")
        self.img_login_button = load_image("misc/login_button_cn.png")

        # Start keyboard controller thread
        self.kb = KeyBoardController(self.cfg, args)
        if args.disable_control:
            self.kb.disable()

        # Start game window capturing thread
        logger.info("Waiting for game window to activate, please click on game window")
        self.capture = GameWindowCapturor(self.cfg, args)

        # Start health monitoring thread
        self.health_monitor = HealthMonitor(self.cfg, args, self.kb)
        if self.cfg["health_monitor"]["enable"]:
            self.health_monitor.start()

        # Start profiler
        self.profiler = Profiler(self.cfg)

        # Prepare video writer if need to record
        if args.record:
            if not self.is_show_debug_window:
                text = "Please enable 'show_debug_window' in config.yaml to enable recording"
                logger.error(text)
                raise RuntimeError(text)

            # Make sure video/ exist
            os.makedirs("video", exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            path = os.path.join("video", f"{timestamp}.mp4")
            # Get video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # mp4 codec
            self.video_writer = cv2.VideoWriter(path, fourcc, 10, (1296, 759))
            logger.info(f"Recording debug window to {path}")

        # Print mode on log
        if args.patrol:
            logger.info("Init AutoBot with patrol mode")
        elif args.aux:
            logger.info("Init AutoBot with aux mode")
        else:
            logger.info("Init AutoBot with auto mode")

        logger.info("MapleStory Bot Init Done")

    def get_player_location_by_nametag(self):
        '''
        Detects the player's location based on the nametag position in the game window.

        This function works by:
        - Extracting a vertical region of interest (ROI) where the nametag is expected.
        - Padding the ROI to avoid template matching edge issues.
        - Using template matching to locate the nametag, split into left and right halves
        to improve robustness against partial occlusion.
        - Selecting the best match (left or right) based on score and cache status.
        - Computing the player's center position by applying a fixed offset to the nametag.

        Returns:
            loc_player (tuple): The (x, y) coordinates of the player's estimated location.
        '''
        # Get camera region in the game window
        img_camera = self.img_frame_gray[
            self.cfg["camera"]["y_start"]:self.cfg["camera"]["y_end"], :]

        # Get nametag image and search image
        if self.cfg["nametag"]["mode"] == "white_mask":
            # Apply Gaussian blur for smoother white detection
            img_camera = cv2.GaussianBlur(img_camera, (3, 3), 0)
            img_nametag = cv2.GaussianBlur(self.img_nametag_gray, (3, 3), 0)
            lower_white, upper_white = (150, 255)
            img_roi = cv2.inRange(img_camera, lower_white, upper_white)
            img_nametag  = cv2.inRange(img_nametag, lower_white, upper_white)
        elif self.cfg["nametag"]["mode"] == "grayscale":
            img_roi = img_camera
            img_nametag = self.img_nametag_gray
        elif self.cfg["nametag"]["mode"] == "histogram_eq":
            # Apply histogram equalization
            img_nametag_eq = cv2.equalizeHist(self.img_nametag_gray)
            img_camera_eq = cv2.equalizeHist(img_camera)

            # Apply global (fixed) threshold
            _, img_nametag = cv2.threshold(img_nametag_eq, 150, 255, cv2.THRESH_BINARY)
            _, img_roi = cv2.threshold(img_camera_eq, 150, 255, cv2.THRESH_BINARY)
        else:
            logger.error(f"Unsupported nametag detection mode: {self.cfg['nametag']['mode']}")
            return
        # cv2.imshow("img_roi", img_roi)
        # cv2.imshow("img_nametag", img_nametag)

        # Pad search region to deal with fail detection when player is at map edge
        (pad_y, pad_x) = self.img_nametag.shape[:2]
        img_roi = cv2.copyMakeBorder(
            img_roi,
            pad_y, pad_y, pad_x, pad_x,
            borderType=cv2.BORDER_REPLICATE  # replicate border for safe matching
        )

        # Get last frame name tag location
        if self.is_first_frame:
            last_result = None
        else:
            last_result = (
                self.loc_nametag[0] + pad_x,
                self.loc_nametag[1] + pad_y - self.cfg["camera"]["y_start"]
            )

        # Get number of splits
        h, w = img_nametag.shape
        num_splits = max(1, w // self.cfg["nametag"]["split_width"])
        w_split = w // num_splits

        # Get nametag's background mask
        mask = get_mask(self.img_nametag, (0, 255, 0))

        # Vertically split the nametag image
        nametag_splits = {}
        for i in range(num_splits):
            x_s = i * w_split
            x_e = (i + 1) * w_split if i < num_splits - 1 else w
            nametag_splits[f"{i+1}/{num_splits}"] = {
                "img": img_nametag[:, x_s:x_e],
                "mask": mask[:, x_s:x_e],
                "last_result": (
                    (last_result[0] + x_s, last_result[1]) if last_result else None
                ),
                "score_penalty": 0.0,
                "offset_x": x_s
            }

        # Match tempalte
        matches = []
        for tag_type, split in nametag_splits.items():
            loc, score, is_cached = find_pattern_sqdiff(
                img_roi,
                split["img"],
                last_result=split["last_result"],
                mask=split["mask"],
                global_threshold=self.cfg["nametag"]["global_diff_thres"]
            )
            w_match = split["img"].shape[1]
            h_match = split["img"].shape[0]
            score += split["score_penalty"]
            matches.append((tag_type, loc, score, w_match, h_match, is_cached, split["offset_x"]))

        # Select best match and fix offset:
        matches.sort(key=lambda x: (not x[5], x[2]))  # prefer cached, then low score
        tag_type, loc_nametag, score, w_match, h_match, is_cached, offset_x = matches[0]

        # Adjust match location back to full nametag coordinates
        loc_nametag = (loc_nametag[0] - offset_x, loc_nametag[1])
        loc_nametag = (
            loc_nametag[0] - pad_x,
            loc_nametag[1] - pad_y + self.cfg["camera"]["y_start"]
        )

        # Only update nametag location when score is good enough
        if score < self.cfg["nametag"]["diff_thres"]:
            self.loc_nametag = loc_nametag

        loc_player = (
            self.loc_nametag[0] + w // 2,
            self.loc_nametag[1] - self.cfg["nametag"]["offset"][1]
        )

        # Draw name tag detection box for debugging
        draw_rectangle(self.img_frame_debug, self.loc_nametag,
                       self.img_nametag.shape, (0, 255, 0), "")
        text = f"NameTag,{round(score, 2)}," + \
                f"{'cached' if is_cached else 'missed'}," + \
                f"{tag_type}"
        cv2.putText(self.img_frame_debug, text,
                    (self.loc_nametag[0],
                     self.loc_nametag[1] + self.img_nametag.shape[0] + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        return loc_player

    def get_player_location_by_party_red_bar(self):
        '''
        get_player_location_by_party_red_bar
        '''
        # Zero out minimap area in the img_frame
        img_frame = self.img_frame.copy()
        x, y = self.loc_minimap
        h, w = self.img_minimap.shape[:2]
        img_frame[y:y+h, x:x+w] = 0

        # Get camera area
        img_camera = img_frame[
            self.cfg["camera"]["y_start"]:self.cfg["camera"]["y_end"], :]

        # Convert to HSV
        img_hsv = cv2.cvtColor(img_camera, cv2.COLOR_BGR2HSV)
        lower_red = to_opencv_hsv(self.cfg["party_red_bar"]["lower_red"])
        upper_red = to_opencv_hsv(self.cfg["party_red_bar"]["upper_red"])
        mask_red = cv2.inRange(img_hsv, lower_red, upper_red)
        # cv2.imshow("mask_red", mask_red)

        # Find contours on mask_red
        contours, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)

        # Filter contour by specific geometry trait of red bar
        boxs = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            area = cv2.contourArea(c)
            fill_rate = float(area) / (h*w)
            if 5 <= h <= 7 and 1 <= w <= 50 and 10 <= area and fill_rate >= 0.7:
                # cv2.drawContours(self.img_frame_debug, [c], -1, (0, 255, 0), 1)
                boxs.append((x, y, w, h))

        if not boxs:
            return None, None  # red bar not found

        # Sort box by area
        boxs.sort(key=lambda box: box[2] * box[3], reverse=True)

        # Consider the biggest area as party red bar
        x, y, w, h = boxs[0]

        # Offset coordinate
        loc_party_red_bar = (x, y + self.cfg["camera"]["y_start"])
        loc_player = (loc_party_red_bar[0] + self.cfg["party_red_bar"]["offset"][0],
                      loc_party_red_bar[1] + self.cfg["party_red_bar"]["offset"][1])

        # visualize for debug
        draw_rectangle(self.img_frame_debug, loc_party_red_bar,
                    (h, w), (0, 255, 0), "party red bar", thickness=1, text_height=0.4)

        return loc_player, loc_party_red_bar

    def get_player_location_on_global_map(self):
        '''
        get_player_location_on_global_map
        '''
        self.loc_minimap_global, score, _ = find_pattern_sqdiff(
                                        self.img_map,
                                        self.img_minimap)

        x_offset, y_offset = self.cfg["minimap"]["offset"]
        loc_player_global = (
            self.loc_minimap_global[0] + self.loc_player_minimap[0] + x_offset,
            self.loc_minimap_global[1] + self.loc_player_minimap[1] + y_offset
        )

        # Draw local minimap rectangle
        camera_bottom_right = (
            self.loc_minimap_global[0] + self.img_minimap.shape[1],
            self.loc_minimap_global[1] + self.img_minimap.shape[0]
        )
        cv2.rectangle(self.img_route_debug, self.loc_minimap_global,
                      camera_bottom_right, (0, 255, 255), 1)
        cv2.putText(
            self.img_route_debug,
            f"Minimap,score({round(score, 2)})",
            (self.loc_minimap_global[0], self.loc_minimap_global[1]+15),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4,
            (0, 255, 255), 1
        )

        # Draw player center
        cv2.circle(self.img_route_debug,
                   loc_player_global, radius=2,
                   color=(0, 255, 255), thickness=-1)

        return loc_player_global

    def get_nearest_color_code(self):
        '''
        Searches for the nearest color-coded action marker
        around the player on the route map.

        This function:
        - Scans each pixel in the search box to find nearest color code
        - Tracks the closest matching pixel using Manhattan distance (|dx| + |dy|).
        - Returns a dictionary containing the nearest matching
          pixel's position, color, action label, and distance.

        Returns:
            dict or None: Dictionary containing:
                - "pixel": (x, y) coordinate of the matched pixel
                - "color": matched RGB color tuple
                - "action": corresponding action string from config
                - "distance": Manhattan distance from player
            Returns None if no matching color is found within the region.
        '''
        x0, y0 = self.loc_player_global
        h, w = self.img_route.shape[:2]
        x_min = max(0, x0 - self.cfg["route"]["search_range"])
        x_max = min(w, x0 + self.cfg["route"]["search_range"])
        y_min = max(0, y0 - self.cfg["route"]["search_range"])
        y_max = min(h, y0 + self.cfg["route"]["search_range"])

        nearest = None
        nearest_up_down = None
        min_dist = float('inf')
        min_dist_up_down = float('inf')
        for y in range(y_min, y_max):
            for x in range(x_min, x_max):
                pixel = tuple(self.img_route[y, x])  # (R, G, B)
                dist = abs(x - x0) + abs(y - y0)
                # Get nearest color
                if pixel in self.color_code and dist < min_dist:
                    nearest = {
                        "pixel": (x, y),
                        "color": pixel,
                        "command": self.color_code[pixel],
                        "distance": dist
                    }
                    min_dist = dist
                # Get nearest color (up, dowm)
                if pixel in self.color_code_up_down and dist < min_dist_up_down:
                    nearest_up_down = {
                        "pixel": (x, y),
                        "color": pixel,
                        "command": self.color_code_up_down[pixel],
                        "distance": dist
                    }
                    min_dist_up_down = dist

        # Debug
        draw_rectangle(
            self.img_route_debug,
            (x_min, y_min),
            (self.cfg["route"]["search_range"]*2,
             self.cfg["route"]["search_range"]*2),
            (0, 0, 255), "", text_height=0.4, thickness=1,
        )
        # Draw a straigt line from map_loc_player to color_code["pixel"]
        if nearest is not None:
            cv2.line(
                self.img_route_debug,
                self.loc_player_global, # start point
                nearest["pixel"],       # end point
                (0, 255, 0),            # green line
                1                       # thickness
            )
            # Print color code on debug image
            cv2.putText(
                self.img_frame_debug, f"Route Action: {nearest['command']}",
                (650, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255),
                2, cv2.LINE_AA
            )
            cv2.putText(
                self.img_frame_debug, f"Route Index: {self.idx_routes}",
                (650, 150),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255),
                2, cv2.LINE_AA
            )

        if nearest_up_down is not None:
            cv2.putText(
                self.img_frame_debug, f"Route Action: {nearest_up_down['command']}",
                (650, 120),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255),
                2, cv2.LINE_AA
            )
            cv2.line(
                self.img_route_debug,
                self.loc_player_global,  # start point
                nearest_up_down["pixel"],# end point
                (0, 0, 255),             # green line
                1                        # thickness
            )

        return nearest, nearest_up_down  # if not found return none

    def get_nearest_monster(self, is_left = True, overlap_threshold=0.5):
        '''
        Finds the nearest monster within the player's attack range.

        This function:
        - Defines an attack box relative to the player position,
            depending on the facing direction (`is_left`).
        - Iterates through all detected monsters and checks which ones overlap
          with the attack box.
        - Returns the closest valid monster that meets the overlap criteria.

        Args:
            is_left (bool): If True, assume the player is facing left;
                            adjusts attack box accordingly.
            overlap_threshold (float): Minimum IoU area ratio required to consider a hit.

        Returns:
            dict or None: The nearest monster's info dict, or None if no valid match.
        '''
        # Get attack box
        if self.args.attack == "aoe_skill":
            dx = self.cfg["aoe_skill"]["range_x"] // 2
            dy = self.cfg["aoe_skill"]["range_y"] // 2
            x0 = max(0, self.loc_player[0] - dx)
            x1 = min(self.img_frame.shape[1], self.loc_player[0] + dx)
            y0 = max(0, self.loc_player[1] - dy)
            y1 = min(self.img_frame.shape[0], self.loc_player[1] + dy)
        elif self.args.attack == "directional":
            if is_left:
                x0 = self.loc_player[0] - self.cfg["directional_attack"]["range_x"]
                x1 = self.loc_player[0]
            else:
                x0 = self.loc_player[0]
                x1 = x0 + self.cfg["directional_attack"]["range_x"]
            y0 = self.loc_player[1] - self.cfg["directional_attack"]["range_y"] // 2
            y1 = y0 + self.cfg["directional_attack"]["range_y"]
        else:
            logger.error(f"Unsupported attack mode: {self.args.attack}")
            return None

        # Draw attack box on debug window
        draw_rectangle(
            self.img_frame_debug, (x0, y0),
            (y1-y0, x1-x0),
            (0, 0, 255), "Attack Range"
        )

        nearest_monster = None
        min_distance = float('inf')
        for monster in self.monster_info:
            mx1, my1 = monster["position"]
            mw, mh = monster["size"]
            mx2 = mx1 + mw
            my2 = my1 + mh

            # Calculate intersection
            ix1 = max(x0, mx1)
            iy1 = max(y0, my1)
            ix2 = min(x1, mx2)
            iy2 = min(y1, my2)

            iw = max(0, ix2 - ix1)
            ih = max(0, iy2 - iy1)
            inter_area = iw * ih

            monster_area = mw * mh
            if monster_area == 0:
                continue  # skip degenerate box

            if inter_area/monster_area >= overlap_threshold:
                # Compute distance to player center
                monster_center = (mx1 + mw // 2, my1 + mh // 2)
                dx = monster_center[0] - self.loc_player[0]
                dy = monster_center[1] - self.loc_player[1]
                distance = abs(dx) + abs(dy)  # Manhattan distance

                if distance < min_distance:
                    min_distance = distance
                    nearest_monster = monster

        return nearest_monster

    def get_monsters_in_range(self, top_left, bottom_right):
        '''
        get_monsters_in_range
        '''
        x0, y0 = top_left
        x1, y1 = bottom_right

        img_roi = self.img_frame[y0:y1, x0:x1]

        # Shift player's location into ROI coordinate system
        px, py = self.loc_player
        px_in_roi = px - x0
        py_in_roi = py - y0

        # Define rectangle range around player (in ROI coordinate)
        char_x_min = max(0, px_in_roi - self.cfg["character"]["width"] // 2)
        char_x_max = min(img_roi.shape[1], px_in_roi + self.cfg["character"]["width"] // 2)
        char_y_min = max(0, py_in_roi - self.cfg["character"]["height"] // 2)
        char_y_max = min(img_roi.shape[0], py_in_roi + self.cfg["character"]["height"] // 2)

        monster_info = []
        for monster_name, monster_imgs in self.monsters.items():
            for img_monster, mask_monster in monster_imgs:
                if self.args.patrol:
                    pass # Don't detect monster using template in patrol mode
                elif self.cfg["monster_detect"]["mode"] == "template_free":
                    # Generate mask where pixel is exactly (0,0,0)
                    black_mask = np.all(img_roi == [0, 0, 0], axis=2).astype(np.uint8) * 255
                    cv2.imshow("Black Pixel Mask", black_mask)

                    # Zero out mask inside this region (ignore player's own character)
                    black_mask[char_y_min:char_y_max, char_x_min:char_x_max] = 0

                    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (20, 20))
                    closed_mask = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel)
                    # cv2.imshow("Black Mask", closed_mask)

                    # draw player character bounding box
                    draw_rectangle(
                        self.img_frame_debug, (char_x_min+x0, char_y_min+y0),
                        (self.cfg["character"]["height"], self.cfg["character"]["width"]),
                        (255, 0, 0), "Character Box"
                    )

                    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(closed_mask, connectivity=8)

                    monster_info = []
                    min_area = 1000
                    for i in range(1, num_labels):
                        x, y, w, h, area = stats[i]
                        if area > min_area:
                            monster_info.append({
                                "name": "",
                                "position": (x0+x, y0+y),
                                "size": (h, w),
                                "score": 1.0,
                            })
                elif self.cfg["monster_detect"]["mode"] == "contour_only":
                    # Use only black lines contour to detect monsters
                    # Create masks (already grayscale)
                    mask_pattern = np.all(img_monster == [0, 0, 0], axis=2).astype(np.uint8) * 255
                    mask_roi = np.all(img_roi == [0, 0, 0], axis=2).astype(np.uint8) * 255

                    # Zero out mask inside this region (ignore player's own character)
                    mask_roi[char_y_min:char_y_max, char_x_min:char_x_max] = 0

                    # Apply Gaussian blur (soften the masks)
                    blur = self.cfg["monster_detect"]["contour_blur"]
                    img_monster_blur = cv2.GaussianBlur(mask_pattern, (blur, blur), 0)
                    img_roi_blur = cv2.GaussianBlur(mask_roi, (blur, blur), 0)

                    # Check template vs ROI size before matching
                    h_roi, w_roi = img_roi_blur.shape[:2]
                    h_temp, w_temp = img_monster_blur.shape[:2]

                    if h_temp > h_roi or w_temp > w_roi:
                        return []  # template bigger than roi, skip this matching

                    # Perform template matching
                    res = cv2.matchTemplate(img_roi_blur, img_monster_blur, cv2.TM_SQDIFF_NORMED)

                    # Apply soft threshold
                    match_locations = np.where(res <= self.cfg["monster_detect"]["diff_thres"])

                    h, w = img_monster.shape[:2]
                    for pt in zip(*match_locations[::-1]):
                        monster_info.append({
                            "name": monster_name,
                            "position": (pt[0] + x0, pt[1] + y0),
                            "size": (h, w),
                            "score": res[pt[1], pt[0]],
                        })
                elif self.cfg["monster_detect"]["mode"] == "grayscale":
                    img_monster_gray = cv2.cvtColor(img_monster, cv2.COLOR_BGR2GRAY)
                    img_roi_gray = cv2.cvtColor(img_roi, cv2.COLOR_BGR2GRAY)
                    res = cv2.matchTemplate(
                            img_roi_gray,
                            img_monster_gray,
                            cv2.TM_SQDIFF_NORMED,
                            mask=mask_monster)
                    match_locations = np.where(res <= self.cfg["monster_detect"]["diff_thres"])
                    h, w = img_monster.shape[:2]
                    for pt in zip(*match_locations[::-1]):
                        monster_info.append({
                            "name": monster_name,
                            "position": (pt[0] + x0, pt[1] + y0),
                            "size": (h, w),
                            "score": res[pt[1], pt[0]],
                    })
                elif self.cfg["monster_detect"]["mode"] == "color":
                    res = cv2.matchTemplate(
                            img_roi,
                            img_monster,
                            cv2.TM_SQDIFF_NORMED,
                            mask=mask_monster)
                    match_locations = np.where(res <= self.cfg["monster_detect"]["diff_thres"])
                    h, w = img_monster.shape[:2]
                    for pt in zip(*match_locations[::-1]):
                        monster_info.append({
                            "name": monster_name,
                            "position": (pt[0] + x0, pt[1] + y0),
                            "size": (h, w),
                            "score": res[pt[1], pt[0]],
                    })
                else:
                    logger.error(f"Unexpected camera localization mode: {self.cfg['monster_detect']['mode']}")
                    return []

        # Apply Non-Maximum Suppression to monster detection
        monster_info = nms(monster_info, iou_threshold=0.4)

        # Detect monster via health bar
        if self.cfg["monster_detect"]["with_enemy_hp_bar"]:
            # Create color mask for Monsters' HP bar
            mask = cv2.inRange(img_roi,
                               np.array(self.cfg["monster_detect"]["hp_bar_color"]),
                               np.array(self.cfg["monster_detect"]["hp_bar_color"]))

            # Find connected components (each cluster of green pixels)
            num_labels, labels, stats, centroids = \
                cv2.connectedComponentsWithStats(mask, connectivity=8)

            for i in range(1, num_labels):  # skip background (label 0)
                x, y, w, h, area = stats[i]
                if area < 3:  # small noise filter
                    continue

                # Guess a monster bounding box
                y += 10
                x = max(0, x)
                y = max(0, y)
                w = 70
                h = 70

                monster_info.append({
                    "name": "Health Bar",
                    "position": (x0 + x, y0 + y),
                    "size": (h, w),
                    "score": 1.0,
                })

        # Debug
        # Draw attack detection range
        # draw_rectangle(
        #     self.img_frame_debug, (x0, y0), (y1-y0, x1-x0),
        #     (255, 0, 0), "Monster Detection Box"
        # )

        # Draw monsters bounding box
        for monster in monster_info:
            if monster["name"] == "Health Bar":
                color = (0, 255, 255)
            else:
                color = (0, 255, 0)

            draw_rectangle(
                self.img_frame_debug, monster["position"], monster["size"],
                color, str(round(monster['score'], 2))
            )

        return monster_info

    def switch_status(self, new_status):
        '''
        Switch to new status and log the transition.

        Parameters:
        - new_status: string, the new status to switch to.
        '''
        # Ignore dummy transition
        if self.status == new_status:
            return

        t_elapsed = round(time.time() - self.t_last_switch_status)
        logger.info(f"[switch_status] From {self.status}({t_elapsed} sec) to {new_status}.")
        self.status = new_status
        self.t_last_switch_status = time.time()

    def get_img_frame(self):
        '''
        get_img_frame
        '''
        # Get window game raw frame
        self.frame = self.capture.get_frame()
        if self.frame is None:
            logger.warning("Failed to capture game frame.")
            return

        # Make sure the window ratio is as expected
        if self.args.aux:
            if not is_img_16_to_9(self.frame, self.cfg): # Aux mode allow 16:9 resolution
                text = f"Unexpeted window size: {self.frame.shape[:2]} (expect window ratio 16:9)"
                logger.error(text)
                return
        else:
            # Other mode only allow specific resolution
            if self.cfg["game_window"]["size"] != self.frame.shape[:2]:
                text = f"Unexpeted window size: {self.frame.shape[:2]} "\
                       f"(expect {self.cfg['game_window']['size']})"
                logger.error(text)
                return

        # Resize raw frame to (1296, 759)
        return cv2.resize(self.frame, (1296, 759),
                   interpolation=cv2.INTER_NEAREST)

    def solve_rune(self):
        '''
        Automatically solves the rune puzzle mini-game by recognizing directional arrows
        on the screen and simulating the correct key presses.

        This function:
        - Continuously checks whether the rune game is active.
        - For each of the 4 arrows:
            - Compares the cropped image with all known arrow templates.
            - Selects the best-matching arrow direction.
            - Simulates a key press corresponding to the detected arrow direction.
        - Repeats until the rune game ends.

        Note:
            - Skips key press simulation if `--disable_control` flag is set.

        Returns:
            None
        '''
        while self.is_in_rune_game():
            for arrow_idx in [0,1,2,3]:
                # Get lastest game screen frame buffer
                self.img_frame = self.get_img_frame()

                # Crop arrow detection box
                x0, y0 = self.cfg["rune_solver"]["arrow_box_coord"]
                x = x0 + self.cfg["rune_solver"]["arrow_box_interval"] * arrow_idx
                y = y0
                size = self.cfg["rune_solver"]["arrow_box_size"]
                img_roi = self.img_frame[y:y+size, x:x+size]

                # Loop through all possible arrows template and choose the most possible one
                best_score = float('inf')
                best_direction = ""
                for direction, arrow_list in self.img_arrows.items():
                    for img_arrow in arrow_list:
                        _, score, _ = find_pattern_sqdiff(
                                        img_roi, img_arrow,
                                        mask=get_mask(img_arrow, (0, 255, 0)))
                        if score < best_score:
                            best_score = score
                            best_direction = direction
                logger.info(f"[solve_rune] Arrow({arrow_idx}) is {best_direction} with score({best_score})")

                # Update img_frame_debug
                self.img_frame_debug = self.img_frame.copy()
                draw_rectangle(
                    self.img_frame_debug, (x, y), (size, size),
                    (0, 0, 255), str(round(best_score, 2))
                )
                # Update debug window
                self.update_img_frame_debug()
                cv2.waitKey(1)

                # For logging
                screenshot(self.img_frame_debug, "solve_rune")

                # Press the key for 0.5 second
                if not self.args.disable_control:
                    self.kb.press_key(best_direction, 0.5)
                time.sleep(1)

        logger.info(f"[solve_rune] Solved all arrows")

    def is_player_stuck(self):
        """
        Checks whether the player is stuck (not moving)
        based on their global position on map.

        This function:
        - Compares the player's current position with their last known position
          tracked by the watchdog.
        - If the player has moved beyond a threshold (`watch_dog_range`),
          it resets the watchdog timer.
        - If the player hasn't moved and the elapsed time exceeds (`watch_dog_timeout`),
          it flags the player as stuck and resets the watchdog.

        Returns:
            bool: True if the player is stuck, False otherwise.
        """
        dx = abs(self.loc_player_global[0] - self.loc_watch_dog[0])
        dy = abs(self.loc_player_global[1] - self.loc_watch_dog[1])

        current_time = time.time()
        if dx + dy > self.cfg["watchdog"]["range"]:
            # Player moved, reset watchdog timer
            self.loc_watch_dog = self.loc_player_global
            self.t_watch_dog = current_time
            return False

        dt = current_time - self.t_watch_dog
        if dt > self.cfg["watchdog"]["timeout"]:
            # watch dog idle for too long, player stuck
            self.loc_watch_dog = self.loc_player_global
            self.t_watch_dog = current_time
            logger.warning(f"[is_player_stuck] Player stuck for {dt} seconds.")
            return True
        return False

    def is_rune_warning(self):
        '''
        Checks whether the rune warning icon is appear on the game frame.

        This function:
        - Crops a specific region where the rune warning icon is expected.
        - Compare the cropped region against the known rune warning image template.
        - Returns True if rune warning template matched

        Returns:
            bool: True if the rune warning is detected, False otherwise.
        '''
        x0, y0 = self.cfg["rune_warning"]["top_left"]
        x1, y1 = self.cfg["rune_warning"]["bottom_right"]

        # Debug
        # draw_rectangle(
        #     self.img_frame_debug, (x0, y0), (y1-y0, x1-x0),
        #     (0, 0, 255), "")
        _, score, _ = find_pattern_sqdiff(
                        self.img_frame_gray[y0:y1, x0:x1],
                        self.img_rune_warning)
        if self.status == "hunting" and score < self.cfg["rune_warning"]["diff_thres"]:
            logger.info(f"[is_rune_warning] Detect rune warning on screen with score({score})")
            return True
        else:
            return False

    def update_rune_location(self):
        '''
        Checks if a rune icon is visible around the player's position.

        This function:
        - Uses template matching to detect the rune icon within this predefine box.

        Returns:
            nearest rune
        '''
        # Calculate bounding box
        h, w = self.img_frame.shape[:2]
        h_rune_box = self.cfg["rune_detect"]["box_height"]
        w_rune_box = self.cfg["rune_detect"]["box_width"]
        x0 = max(0, self.loc_player[0] - w_rune_box // 2)
        y0 = max(0, self.loc_player[1] - h_rune_box)
        x1 = min(w, self.loc_player[0] + w_rune_box // 2)
        y1 = min(h, self.loc_player[1])

        # Debug
        draw_rectangle(
            self.img_frame_debug, (x0, y0), (y1-y0, x1-x0),
            (255, 0, 0), "Rune Detection Range"
        )

        # Make sure ROI is large enough to hold a full rune
        max_rune_height = max(r.shape[0] for r in self.img_runes)
        max_rune_width  = max(r.shape[1] for r in self.img_runes)
        if (x1 - x0) < max_rune_width or (y1 - y0) < max_rune_height:
            return  # Skip check if box is out of range

        # Extract ROI near player
        img_roi = self.img_frame[y0:y1, x0:x1]

        # Match each rune part separately
        matches = []
        for i, img_rune in enumerate(self.img_runes):
            mask = get_mask(img_rune, (0, 255, 0))
            loc, score, _ = find_pattern_sqdiff(img_roi, img_rune, mask=mask)
            matches.append((i, loc, score, img_rune.shape))

        # # Matches box debug
        # for i, (part_idx, loc, score, shape) in enumerate(matches):
        #     draw_rectangle(
        #         self.img_frame_debug,
        #         (x0 + loc[0], y0 + loc[1]),
        #         shape,
        #         (255, 255, 0),
        #         f"{i},{round(score, 2)}",
        #         thickness=1,
        #         text_height=0.4
        #     )

        # Filter out good matches
        good_matches = [
            (i, loc, score, shape)
            for (i, loc, score, shape) in matches
            if score < self.cfg["rune_detect"]["diff_thres"]
        ]

        # Remove overlapping matches
        good_matches = nms_matches(good_matches)

        # Require at least 2 rune parts
        if len(good_matches) < 2:
            return

        # Horizontal: max distance between part's centers are small
        x_centers = [x0 + loc[0] + shape[1] // 2 for (_, loc, _, shape) in good_matches]
        if max(x_centers) - min(x_centers) > 10:
            return

        # Vertical: check if all Y's are strictly increasing
        ys = [y0 + loc[1] for (_, loc, _, _) in good_matches]
        if not all(ys[i] < ys[i + 1] for i in range(len(ys) - 1)):
            return

        logger.info(f"[Rune Detect] Found rune parts near player with scores:"
                    f" {[round(s, 2) for (_, _, s, _) in matches]}")

        # Update rune location
        self.loc_rune = (int(sum(x_centers) / len(x_centers)),
                         int(sum(ys) / len(ys)))

        # Draw all parts on debug window
        for (i, loc, score, shape) in matches:
            draw_rectangle(
                self.img_frame_debug,
                (x0 + loc[0], y0 + loc[1]),
                shape,
                (255, 0, 255),
                f"{i},{round(score, 2)}",
                text_height=0.5,
                thickness=1
            )

        # Draw rune location on debug window
        cv2.circle(self.img_frame_debug, self.loc_rune,
                   radius=5, color=(0, 255, 255), thickness=-1)

        screenshot(self.img_frame_debug, "rune_detected")

    def is_in_rune_game(self):
        '''
        Determines whether the rune puzzle game screen is currently active.

        This function:
        - Extracts the RoI where the first arrow of the rune puzzle appears.
        - Performs masked template matching with all known arrow templates.
        - Computes the best matching score across all arrow directions.
        - If the best match score is below a threshold,
          the rune puzzle is considered active.

        Returns:
            bool: True if the rune game is detected on screen, False otherwise.
        '''
        # Get lastest game screen frame buffer
        self.img_frame = self.get_img_frame()

        # Crop arrow detection box
        x, y = self.cfg["rune_solver"]["arrow_box_coord"]
        size = self.cfg["rune_solver"]["arrow_box_size"]
        img_roi = self.img_frame[y:y+size, x:x+size]

        # Check if arrow exist on screen
        best_score = float('inf')
        for direc, arrow_list in self.img_arrows.items():
            for img_arrow in arrow_list:
                _, score, _ = find_pattern_sqdiff(
                                img_roi, img_arrow,
                                mask=get_mask(img_arrow, (0, 255, 0)))
                if score < best_score:
                    best_score = score

        draw_rectangle(
            self.img_frame_debug, (x, y), (size, size),
            (0, 0, 255), str(round(best_score, 2))
        )

        if best_score < self.cfg["rune_solver"]["arrow_box_diff_thres"]:
            logger.info(f"Arrow screen detected with score({score})")
            return True
        return False

    def is_near_edge(self):
        '''
        Detects whether the player is near a teleport edge region

        This function:
        - Defines a rectangular search region around the player's current global location.
        - Scans for pixels matching a specific edge teleport color code within the region.
        - If matching pixels are found, it computes the average X position of those pixels.
        - Compares that average to the player's X position to determine whether the edge is on the left or right.

        Returns:
            str: One of:
                - "edge on left"
                - "edge on right"
                - "" (empty string if no edge is detected nearby)
        '''
        x0, y0 = self.loc_player_global
        h, w = self.img_route.shape[:2]
        h_trigger_box = self.cfg["edge_teleport"]["trigger_box_height"]
        w_trigger_box = self.cfg["edge_teleport"]["trigger_box_width"]
        x_min = max(0, x0 - w_trigger_box//2)
        x_max = min(w, x0 + w_trigger_box//2)
        y_min = max(0, y0 - h_trigger_box//2)
        y_max = min(h, y0 + h_trigger_box//2)

        # Debug: draw search box
        # draw_rectangle(
        #     self.img_route_debug,
        #     (x_min, y_min),
        #     (y_max - y_min, x_max - x_min),
        #     (0, 0, 255), "Edge Check", thickness=1, text_height=0.4
        # )

        # Find mask of matching pixels
        roi = self.img_route[y_min:y_max, x_min:x_max]
        mask = np.all(roi == self.cfg["edge_teleport"]["color_code"], axis=2)
        coords = np.column_stack(np.where(mask))

        # No edge pixel
        if coords.size == 0:
            return ""

        # Calculate mean position of matching pixels
        mean_x = np.mean(coords[:, 1])

        # Compare to roi center
        if mean_x < x0:
            return "edge on left"
        else:
            return "edge on right"

    def get_random_action(self):
        '''
        get_random_action - pick a random action except 'up' and teleport command
        '''
        cmd_left_right = random.choice(["left", "right", "none"])
        cmd_up_down = random.choice(["down", "none"])
        cmd_action = random.choice(["jump", "none"])
        logger.warning(f"Perform random command: {cmd_left_right} {cmd_up_down} {cmd_action}")
        return cmd_left_right, cmd_up_down, cmd_action

    def update_info_on_img_frame_debug(self):
        '''
        update_info_on_img_frame_debug
        '''
        # Print text at bottom left corner
        self.fps = round(1.0 / (time.time() - self.t_last_frame))
        text_y_interval = 23
        text_y_start = 520
        dt_screenshot = time.time() - self.kb.t_last_screenshot
        h, w = self.frame.shape[:2]
        text_list = [
            f"FPS: {self.fps}",
            f"Status: {self.status}",
            f"Resolution: {h}x{w}, Ratio: {round(w/h, 2)}",
            f"Press 'F1' to {'pause' if self.kb.is_enable else 'start'} Bot",
            f"Press 'F2' to save screenshot{' : Saved' if dt_screenshot < 0.7 else ''}",
             "Press 'F12' to quit"]
        for idx, text in enumerate(text_list):
            cv2.putText(
                self.img_frame_debug, text,
                (10, text_y_start + text_y_interval*idx),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255),
                2, cv2.LINE_AA
            )

        # Draw minimap rectangle on img debug
        draw_rectangle(
            self.img_frame_debug,
            self.loc_minimap,
            self.img_minimap.shape[:2],
            (0, 0, 255), "minimap",thickness=2
        )

        # Don't draw minimap in patrol mode
        if self.args.patrol or self.args.aux:
            return

        # Compute crop region with boundary check
        crop_w, crop_h = 80, 80
        x0 = max(0, self.loc_player_global[0] - crop_w // 2)
        y0 = max(0, self.loc_player_global[1] - crop_h // 2)
        x1 = min(self.img_route_debug.shape[1], x0 + crop_w)
        y1 = min(self.img_route_debug.shape[0], y0 + crop_h)

        # Check if valid crop region
        if x1 <= x0 or y1 <= y0:
            return

        # Crop region
        mini_map_crop = self.img_route_debug[y0:y1, x0:x1]
        mini_map_crop = cv2.resize(mini_map_crop,
                                (int(mini_map_crop.shape[1] * 3),
                                 int(mini_map_crop.shape[0] * 3)),
                                interpolation=cv2.INTER_NEAREST)
        # Paste into top-right corner of self.img_frame_debug
        h_crop, w_crop = mini_map_crop.shape[:2]
        h_frame, w_frame = self.img_frame_debug.shape[:2]
        x_paste = w_frame - w_crop - 10  # 10px margin from right
        y_paste = 70
        self.img_frame_debug[y_paste:y_paste + h_crop, x_paste:x_paste + w_crop] = mini_map_crop

        # Draw border around minimap
        cv2.rectangle(
            self.img_frame_debug,
            (x_paste, y_paste),
            (x_paste + w_crop, y_paste + h_crop),
            color=(255, 255, 255),   # White border
            thickness=2
        )

        # Draw HP/MP/EXP bar on debug window
        ratio_bars = [self.health_monitor.hp_ratio,
                      self.health_monitor.mp_ratio,
                      self.health_monitor.exp_ratio]
        for i, bar_name in enumerate(["HP", "MP", "EXP"]):
            x_s, y_s = (250, 90)
            # Print bar ratio on debug window
            cv2.putText(self.img_frame_debug,
                        f"{bar_name}: {ratio_bars[i]*100:.1f}%",
                        (x_s, y_s + 30*i),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
            # Draw bar on debug window
            x_s, y_s = (410, 73)
            # print(self.health_monitor.loc_size_bars)
            x, y, w, h = self.health_monitor.loc_size_bars[i]
            self.img_frame_debug[y_s+30*i:y_s+h+30*i, x_s:x_s+w] = \
                self.img_frame[self.cfg["camera"]["y_end"]:, :][y:y+h, x:x+w]

    def update_img_frame_debug(self):
        '''
        update_img_frame_debug
        '''
        cv2.imshow("Game Window Debug",
            self.img_frame_debug[self.cfg["camera"]["y_start"]:
                                 self.cfg["camera"]["y_end"], :])
        # Update FPS timer
        self.t_last_frame = time.time()

    def ensure_is_in_party(self):
        '''
        ensure_is_in_party
        '''
        # open party window
        self.kb.press_key(self.cfg["key"]["party"])

        # Wait party window to show up
        time.sleep(0.5)

        # Update image frame
        self.img_frame = self.get_img_frame()

        # Find the 'create party' button
        loc_enable, score_enable, _ = find_pattern_sqdiff(
                        self.img_frame, self.img_create_party_enable)
        if score_enable < self.cfg["party_red_bar"]["create_party_button_thres"]:
            h, w = self.img_create_party_enable.shape[:2]
            click_in_game_window(self.cfg["game_window"]["title"],
                (loc_enable[0] + w // 2, loc_enable[1] + h // 2)
            )
        else:
            logger.info("Cannot find create party button. Maybe player is in party already?")

        # close party window
        self.kb.press_key(self.cfg["key"]["party"])

    def channel_change(self):
        '''
        channel_change
        '''
        logger.info("[channel_change] Start")

        window_title = self.cfg["game_window"]["title"]
        ui_coords = self.cfg["ui_coords"]
        click_in_game_window(window_title, ui_coords["menu"])
        time.sleep(1)
        click_in_game_window(window_title, ui_coords["channel"])
        time.sleep(1)
        click_in_game_window(window_title, ui_coords["random_channel"])
        time.sleep(1)
        click_in_game_window(window_title, ui_coords["random_channel_confirm"])
        time.sleep(1)

        while self.get_login_button_location() is None:
            self.img_frame = self.get_img_frame()
            logger.info("Waiting for login button to show up...")
            time.sleep(3)
        time.sleep(3) # Wait screen to become brighter

        # Click login button
        click_in_game_window(window_title, self.get_login_button_location())
        time.sleep(2)

        # Click "Select Character"
        click_in_game_window(window_title, ui_coords["select_character"])
        time.sleep(5)

        self.kb.enable()
        self.kb.set_command("none none none")
        self.kb.release_all_key()

        self.ensure_is_in_party() # Make sure player is in party

        self.switch_status("hunting")

        # Clear rune finding timer after channel change
        self.t_rune_finding_start = 0

    def terminate_threads(self):
        '''
        terminate_and_wait_threads
        '''
        self.capture.is_terminated = True
        self.health_monitor.is_terminated = True
        logger.info(f"[terminate_threads] Terminated all threads")

    def get_attack_direction(self, monster_left, monster_right):
        '''
        get_attack_direction
        '''
        # Compute distance for left
        distance_left = float('inf')
        if monster_left is not None:
            mx, my = monster_left["position"]
            mw, mh = monster_left["size"]
            center_left = (mx + mw // 2, my + mh // 2)
            distance_left = abs(center_left[0] - self.loc_player[0]) + \
                            abs(center_left[1] - self.loc_player[1])
        # Compute distance for right
        distance_right = float('inf')
        if monster_right is not None:
            mx, my = monster_right["position"]
            mw, mh = monster_right["size"]
            center_right = (mx + mw // 2, my + mh // 2)
            distance_right = abs(center_right[0] - self.loc_player[0]) + \
                            abs(center_right[1] - self.loc_player[1])
        # Choose attack direction and nearest monster
        attack_direction = None
        # nearest_monster = None

        # Additional validation: check if monster is actually on the correct side
        def is_monster_on_correct_side(monster, direction):
            if monster is None:
                return False
            mx, my = monster["position"]
            mw, mh = monster["size"]
            monster_center_x = mx + mw // 2
            player_x = self.loc_player[0]

            if direction == "left":
                return monster_center_x < player_x  # Monster should be left of player
            else:  # direction == "right"
                return monster_center_x > player_x  # Monster should be right of player

        # Only choose direction if there's a clear winner and monster is on correct side
        if monster_left is not None and monster_right is None and \
            is_monster_on_correct_side(monster_left, "left"):
            attack_direction = "left"
            # nearest_monster = monster_left
        elif monster_right is not None and monster_left is None and \
            is_monster_on_correct_side(monster_right, "right"):
            attack_direction = "right"
            # nearest_monster = monster_right
        elif monster_left is not None and monster_right is not None:
            # Both sides have monsters, check distance and side validation
            left_valid = is_monster_on_correct_side(monster_left, "left")
            right_valid = is_monster_on_correct_side(monster_right, "right")

            if left_valid and not right_valid:
                attack_direction = "left"
                # nearest_monster = monster_left
            elif right_valid and not left_valid:
                attack_direction = "right"
                # nearest_monster = monster_right
            elif left_valid and right_valid and distance_left < distance_right - 50:
                attack_direction = "left"
                # nearest_monster = monster_left
            elif left_valid and right_valid and distance_right < distance_left - 50:
                attack_direction = "right"
                # nearest_monster = monster_right
            # If both valid but distances too close, don't attack to avoid confusion

        # Debug attack direction selection
        if monster_left is not None or monster_right is not None:
            left_side_ok = is_monster_on_correct_side(monster_left, "left") if monster_left else False
            right_side_ok = is_monster_on_correct_side(monster_right, "right") if monster_right else False
            debug_text = f"L:{distance_left:.0f}({left_side_ok}) R:{distance_right:.0f}({right_side_ok}) Dir:{attack_direction}"
            cv2.putText(self.img_frame_debug, debug_text,
                        (10, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)
        return attack_direction

    def is_need_change_channel(self, loc_other_players):
        '''
        is_need_change_channel
        '''
        # Calculate center value
        xs = [x for (x, _) in loc_other_players]
        ys = [y for (_, y) in loc_other_players]
        if len(xs) == 0 or len(ys) == 0:
            return False
        center_x, center_y = (np.mean(xs), np.mean(ys))
        if np.isnan(center_x) or np.isnan(center_y):
            return False
        center = (int(np.mean(xs)), int(np.mean(ys)))
        #logger.info(f"[is_need_change_channel] Center of mass = {center}")

        # Change channel
        if self.cfg["channel_change"]["mode"] == "true":
            logger.warning("[is_need_change_channel] Player detected, immediately change channel.")
            return True
        elif self.cfg["channel_change"]["mode"] == "pixel":
            if self.red_dot_center_prev is None:
                self.red_dot_center_prev = center
            else:
                dx = abs(center[0] - self.red_dot_center_prev[0])
                dy = abs(center[1] - self.red_dot_center_prev[1])
                total = dx + dy
                logger.debug(f"[is_need_change_channel] Movement dx={dx}, dy={dy}, total={total}")
                thres = self.cfg["channel_change"]["other_player_move_thres"]
                if total > thres:
                    logger.warning(f"Other player movement > {thres} pixel detected. "
                                "Trigger channel change.")
                    return True
        return False

    def get_login_button_location(self):
        '''
        get_login_button_location
        '''
        # Extract the region where the login button should appear
        x0, y0 = self.cfg["ui_coords"]["login_button_top_left"]
        x1, y1 = self.cfg["ui_coords"]["login_button_bottom_right"]
        img_roi = self.img_frame[y0:y1, x0:x1]

        # Find the 'login' button
        loc, score, _ = find_pattern_sqdiff(
                        img_roi, self.img_login_button)
        print(score)
        if score < self.cfg["ui_coords"]["login_button_thres"]:
            h, w = self.img_create_party_enable.shape[:2]
            logger.info(f"[get_login_button_location] Found login button with score({score})")
            return (x0 + loc[0] + w // 2, y0 + loc[1] + h // 2)
        else:
            return None

    def run_once(self):
        '''
        Process one game window frame
        '''
        # Start prfiler for performance debugging
        self.profiler.start()

        # Get game window frame
        img_frame = self.get_img_frame()
        if img_frame is not None:
            self.img_frame = img_frame

        # Grayscale game window
        self.img_frame_gray = cv2.cvtColor(self.img_frame, cv2.COLOR_BGR2GRAY)

        # Image for debug use
        if self.is_show_debug_window:
            self.img_frame_debug = self.img_frame.copy()

        self.profiler.mark("Image Preprocessing")

        # Get minimap coordinate and size on game window
        minimap_result = get_minimap_loc_size(self.img_frame)
        if minimap_result is None:
            if time.time() - self.t_last_minimap_update > 30:
                loc_login_button = self.get_login_button_location()
                if loc_login_button:
                    logger.info("Found login button on screen. Proceed to login.")
                    click_in_game_window(self.cfg["game_window"]["title"],
                                         loc_login_button)
                    time.sleep(3)
                    click_in_game_window(self.cfg["game_window"]["title"],
                                         self.cfg["ui_coords"]["select_character"])
                    time.sleep(2)
        else:
            x, y, w, h = minimap_result
            
            # Apply minimap position offset (adjust these values as needed)
            # Positive values move right and down, negative values move left and up
            x_offset = 1  # Move 2 pixels to the right
            y_offset = 1  # Move 2 pixels down
            
            x += x_offset
            y += y_offset
            
            self.loc_minimap = (x, y)
            self.img_minimap = self.img_frame[y:y+h, x:x+w]
            t_last_minimap_update = time.time() # update timer
        self.profiler.mark("get_minimap_loc_size")

        # Get current route image
        if not self.args.patrol and not self.args.aux:
            self.img_route = self.img_routes[self.idx_routes]
            if self.is_show_debug_window:
                self.img_route_debug = cv2.cvtColor(self.img_route, cv2.COLOR_RGB2BGR)

        # Update health monitor with current frame
        self.health_monitor.update_frame(self.img_frame[self.cfg["camera"]["y_end"]:, :])

        self.profiler.mark("Health Monitor")

        # Check whether "Please remove runes" warning appears on screen
        if self.is_rune_warning():
            self.loc_rune = None
            self.switch_status("finding_rune") # Stop hunting and start find runes

        self.profiler.mark("Rune Warning Detection")

        # Get player location in game window
        if self.cfg["nametag"]["enable"]:
            loc_player = self.get_player_location_by_nametag()
        else:
            loc_player, loc_party_red_bar = self.get_player_location_by_party_red_bar()
            if loc_party_red_bar is not None:
                self.loc_party_red_bar = loc_party_red_bar

        # Update player location
        if loc_player is not None:
            # Check if character is on ladder
            dx = abs(loc_player[0] - self.loc_player[0])
            dy = abs(loc_player[1] - self.loc_player[1])
            if self.is_on_ladder:
                if dx > 3: # Leave ladder if there is horizontal move
                    self.is_on_ladder = False
            else:
                if dx < 3 and dy != 0:
                    self.is_on_ladder = True
            # logger.info((self.is_on_ladder, dx, dy))
            # Update player location
            self.loc_player = loc_player

        # Draw player center for debugging
        cv2.circle(self.img_frame_debug,
                self.loc_player, radius=3,
                color=(0, 0, 255), thickness=-1)

        self.profiler.mark("Nametag Detection")

        # Get player location on minimap
        loc_player_minimap = get_player_location_on_minimap(
                                self.img_minimap,
                                minimap_player_color=self.cfg["minimap"]["player_color"])
        if loc_player_minimap:
            self.loc_player_minimap = loc_player_minimap

        self.profiler.mark("Player Location Detection")

        # Get other player location on minimap & change channel


        # Get other player color from config
        if is_mac():
            other_player_color = (20, 15, 228)
        else:
            other_player_color = (0, 0, 255)

        # 調試：分析小地圖顏色（只在第一次執行時）
        # if self.is_first_frame:
        #     logger.info("Running minimap color analysis...")
        #     debug_minimap_colors(self.img_minimap, other_player_color)

        loc_other_players = get_all_other_player_locations_on_minimap(self.img_minimap, other_player_color)
        # logger.info(f"loc_other_players: {loc_other_players}, other_player_color: {other_player_color}")
        if self.is_need_change_channel(loc_other_players):
            self.kb.set_command("none none none")
            self.kb.release_all_key()
            self.kb.disable()
            time.sleep(1)
            self.channel_change()
            self.red_dot_center_prev = None
            return

        self.profiler.mark("Other Player Location Detection")

        # Get player location on global map
        if self.args.patrol or self.args.aux:
            self.loc_player_global = self.loc_player_minimap
        else:
            self.loc_player_global = self.get_player_location_on_global_map()

        self.profiler.mark("Global Map Matching")

        # Check whether a rune icon is near player
        if self.status == "finding_rune":

            # Start timer when entering finding_rune status
            if self.t_rune_finding_start == 0:
                self.t_rune_finding_start = time.time()

            self.update_rune_location()
            if self.loc_rune is not None:
                self.switch_status("near_rune")
                logger.info(abs(self.loc_player[0] - self.loc_rune[0]))

        # Check whether we entered the rune mini-game
        if self.status == "near_rune" and (not self.args.disable_control):
            # Update rune location
            self.update_rune_location()

            dt = time.time() - self.t_last_rune_trigger
            dx = abs(self.loc_player[0] - self.loc_rune[0])
            dy = abs(self.loc_player[1] - self.loc_rune[1])
            logger.info(f"[Near Rune] Player distance to rune: ({dx}, {dy})")

            # Check if close enough to trigger the rune
            if dt > self.cfg["rune_find"]["rune_trigger_cooldown"] and \
                dx < self.cfg["rune_find"]["rune_trigger_distance_x"] and \
                dy < self.cfg["rune_find"]["rune_trigger_distance_y"]:

                self.kb.set_command("none none none")
                self.kb.release_all_key()
                time.sleep(0.1) # Wait for character to stop
                self.kb.disable() # Disable kb thread during rune solving

                # Attempt to trigger rune
                self.kb.press_key("up", 0.02)

                # Wait for rune game to pop up
                if self.cfg["system"]["server"] == "NA":
                    # N.A server needs wait longer for rune scene to pop up
                    time.sleep(4)
                else:
                    time.sleep(1)

                # If entered the game, start solving rune
                if self.is_in_rune_game():
                    self.solve_rune() # Blocking until runes solved
                    self.switch_status("hunting")
                    # Clear rune finding timer after successful rune solving
                    self.t_rune_finding_start = 0

                # Restore kb thread
                self.kb.enable()

                self.t_last_rune_trigger = time.time()

        self.profiler.mark("Rune Detection")

        # Get monster search box
        margin = self.cfg["monster_detect"]["search_box_margin"]
        if self.args.attack == "aoe_skill":
            dx = self.cfg["aoe_skill"]["range_x"] // 2 + margin
            dy = self.cfg["aoe_skill"]["range_y"] // 2 + margin
        elif self.args.attack == "directional":
            dx = self.cfg["directional_attack"]["range_x"] + margin
            dy = self.cfg["directional_attack"]["range_y"] + margin
        else:
            logger.error(f"Unsupported attack mode: {self.args.attack}")
            return
        x0 = max(0, self.loc_player[0] - dx)
        x1 = min(self.img_frame.shape[1], self.loc_player[0] + dx)
        y0 = max(0, self.loc_player[1] - dy)
        y1 = min(self.img_frame.shape[0], self.loc_player[1] + dy)

        # Get monsters in the search box
        if self.status == "hunting":
            self.monster_info = self.get_monsters_in_range((x0, y0), (x1, y1))
        else:
            self.monster_info = []

        self.profiler.mark("Monster Detection")

        # Get attack direction
        if self.args.attack == "aoe_skill":
            if len(self.monster_info) == 0:
                attack_direction = None
            else:
                attack_direction = "I don't care"
            nearest_monster = self.get_nearest_monster()

        elif self.args.attack == "directional":
            # Get nearest monster to player
            monster_left  = self.get_nearest_monster(is_left = True)
            monster_right = self.get_nearest_monster(is_left = False)
            # Determine attack direction
            attack_direction = self.get_attack_direction(monster_left, monster_right)

        else:
            logger.error(f"Unexpected attack mode: {self.args.attack}")
            return

        cmd_left_right = "none"
        cmd_up_down = "none"
        cmd_action = "none"
        if self.args.patrol:
            x, y = self.loc_player
            h, w = self.img_frame.shape[:2]
            loc_player_ratio = float(x)/float(w)
            left_ratio, right_ratio = self.cfg["patrol"]["range"]

            # Check if we need to change patrol direction
            if self.is_patrol_to_left and loc_player_ratio < left_ratio:
                self.patrol_turn_point_cnt += 1
            elif (not self.is_patrol_to_left) and loc_player_ratio > right_ratio:
                self.patrol_turn_point_cnt += 1

            if self.patrol_turn_point_cnt > self.cfg["patrol"]["turn_point_thres"]:
                self.is_patrol_to_left = not self.is_patrol_to_left
                self.patrol_turn_point_cnt = 0

            # Get left-right command
            if self.is_patrol_to_left:
                cmd_left_right = "left"
            else:
                cmd_left_right = "right"

            # Get action command
            if (time.time() - self.t_patrol_last_attack > self.cfg["patrol"]["patrol_attack_interval"] or \
                attack_direction is not None):
                cmd_action = "attack"
                self.t_patrol_last_attack = time.time()

        elif self.args.aux:
            pass

        else:
            # get color code from img_route
            color_code, color_code_up_down = self.get_nearest_color_code()

            # Use color_code and color_code_up_down to complement each other
            # To prevent character stuck at the end of ladder, we use two color color pixels
            # and let them complement with each other, to ensure smoothy ladder climbing
            if color_code and color_code_up_down:
                if color_code["distance"] < color_code_up_down["distance"]:
                    cmd_left_right, cmd_up_down, cmd_action = color_code["command"].split()
                    _, cmd, _ = color_code_up_down["command"].split()
                    if cmd_up_down == "none" and self.is_on_ladder:
                        cmd_up_down = cmd # only complement when player is on ladder
                else:
                    cmd_left_right, cmd_up_down, cmd_action = color_code_up_down["command"].split()
                    cmd, _, _ = color_code["command"].split()
                    if cmd_left_right == "none" and self.is_on_ladder:
                        cmd_left_right = cmd # only complement when player is on ladder
            elif color_code:
                cmd_left_right, cmd_up_down, cmd_action = color_code["command"].split()
            elif color_code_up_down:
                cmd_left_right, cmd_up_down, cmd_action = color_code_up_down["command"].split()

            # Change route map if reached goal
            if cmd_action == "goal":
                # Switch to next route map
                self.idx_routes = (self.idx_routes+1)%len(self.img_routes)
                logger.debug(f"Change to new route:{self.idx_routes}")

            # teleport away from edge to avoid falling off cliff
            if self.is_near_edge() and \
                time.time() - self.t_last_teleport > self.cfg["teleport"]["cooldown"]:
                cmd_action = "teleport"
                self.t_last_teleport = time.time() # update timer

        # replace teleport to jump if user doesn't set teleport key
        if self.cfg["key"]["teleport"] == "" and cmd_action == "teleport":
            cmd_action = "jump"

        # Special logic for each status, overwrite color code action
        if self.status == "hunting":
            # Perform a random action when player stuck
            if not self.args.patrol and self.is_player_stuck():
                cmd_left_right, cmd_up_down, cmd_action = self.get_random_action()
            elif attack_direction is not None and \
                time.time() - self.t_last_attack > self.cfg["directional_attack"]["cooldown"]:
                cmd_action = "attack"
                # Set up attack direction
                if attack_direction in ["left", "right"]:
                    cmd_left_right = attack_direction
                self.t_last_attack = time.time()

        elif self.status == "finding_rune":
            if self.is_player_stuck():
                command = self.get_random_action()

            # If the HP is reduced switch to hurting (other player probably help solved the rune)
            if  time.time() - self.health_monitor.t_last_hp_reduce < 3 and \
                time.time() - self.t_last_switch_status > 3:
                self.switch_status("hunting")

            # Check if finding rune timeout
            diff_timeout = time.time() - self.t_rune_finding_start
            logger.info(f"diff_timeout: {diff_timeout}")
            if diff_timeout > self.cfg["rune_find"]["timeout"]:
                if self.cfg["rune_find"]["timeout_action"] == "change_channel":
                    # Change channel to avoid rune
                    self.channel_change()
                else:
                    # Return home
                    self.kb.press_key(self.cfg["key"]["return_home_key"])
                    self.is_terminated = True
                    self.kb.is_terminated = True

        elif self.status == "near_rune":
            # Stay in near_rune status for only a few seconds
            if time.time() - self.t_last_switch_status > self.cfg["rune_find"]["near_rune_duration"]:
                self.switch_status("hunting")

        elif self.status == "aux": # only for aux mode
            pass

        else:
            logger.error(f"Unknown status: {self.status}")

        # send command to keyboard controller
        command = f"{cmd_left_right} {cmd_up_down} {cmd_action}"
        self.kb.set_command(command)

        self.profiler.mark("Determine Command")

        # Debug: show current command on screen
        if command and len(command) > 0:
            cv2.putText(self.img_frame_debug, f"CMD: {command}",
                       (10, 480), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Check if need to save screenshot
        if self.kb.is_need_screen_shot:
            screenshot(self.img_frame)
            self.kb.is_need_screen_shot = False

        # Make sure player is in party
        if self.is_first_frame and not is_mac():
            activate_game_window(self.cfg["game_window"]["title"])
            time.sleep(0.3)
            self.ensure_is_in_party()

        # Enable cached location since second frame
        self.is_first_frame = False

        #####################
        ### Debug Windows ###
        #####################
        # Don't show debug window to save system resource
        if not self.is_show_debug_window:
            return

        # Print text on debug image
        self.update_info_on_img_frame_debug()

        # Show debug image on window
        self.update_img_frame_debug()

        # Save debug window to video
        if self.args.record:
            self.video_writer.write(self.img_frame_debug)

        # Resize img_route_debug for better visualization
        if not self.args.patrol and not self.args.aux:
            self.img_route_debug = cv2.resize(
                        self.img_route_debug, (0, 0),
                        fx=self.cfg["minimap"]["debug_window_upscale"],
                        fy=self.cfg["minimap"]["debug_window_upscale"],
                        interpolation=cv2.INTER_NEAREST)
            cv2.imshow("Route Map Debug", self.img_route_debug)

        self.profiler.mark("Debug Window Show")

        # Check FPS, TODO: too verbose, only print if many frames has high latency
        # if self.fps < 5:
        #     logger.warning(f"FPS({self.fps}) is too low, AutoBot cannot run properly!")

        # Print profiler result
        if self.cfg["profiler"]["enable"] and \
            self.profiler.total_frames % self.cfg["profiler"]["print_frequency"] == 0:
            logger.info('\n' + self.profiler.report())

def main(args):
    '''
    Main Function
    '''
    try:
        mapleStoryBot = MapleStoryBot(args)
    except Exception as e:
        logger.error(f"MapleStoryBot Init failed: {e}")
        sys.exit(1)
    else:
        while not mapleStoryBot.kb.is_terminated:

            t_start = time.time()

            # Process one game window frame
            mapleStoryBot.run_once()

            # Draw image on debug window
            if mapleStoryBot.is_show_debug_window:
                cv2.waitKey(1)

            # Cap FPS to save system resource
            frame_duration = time.time() - t_start
            target_duration = 1.0 / mapleStoryBot.cfg["system"]["fps_limit_main"]
            if frame_duration < target_duration:
                time.sleep(target_duration - frame_duration)

        # Terminate all other threads
        mapleStoryBot.terminate_threads()

        cv2.destroyAllWindows()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--disable_control',
        action='store_true',
        help='Disable simulated keyboard input'
    )

    parser.add_argument(
        '--patrol',
        action='store_true',
        help='Enable patrol mode'
    )

    # Argument to specify map name
    parser.add_argument(
        '--map',
        type=str,
        default='lost_time_1',
        help='Specify the map name'
    )

    parser.add_argument(
        "--monsters",
        type=str,
        default="evolved_ghost",
        help="Specify which monsters to load, comma-separated"
             "(e.g., --monsters green_mushroom,zombie_mushroom)"
    )

    parser.add_argument(
        '--attack',
        type=str,
        default='directional',
        help='Choose attack method, "directional", "aoe_skill"'
    )

    parser.add_argument(
        '--nametag',
        type=str,
        default='example',
        help='Choose nametag png file in nametag/'
    )

    parser.add_argument(
        '--cfg',
        type=str,
        default='edit_me',
        help='Choose customized config yaml file in config/'
    )

    parser.add_argument(
        '--debug',
        action="store_true",
        help="Enable debug logging"
    )

    parser.add_argument(
        '--record',
        action="store_true",
        help="Record debug window"
    )

    parser.add_argument(
        '--aux',
        action="store_true",
        help="Enable auxiliary mode, where bot only help with buff skill and potion drinking"
    )

    args = parser.parse_args()

    # Set logger level
    if args.debug:
        logger.setLevel(logging.DEBUG)

    main(args)
