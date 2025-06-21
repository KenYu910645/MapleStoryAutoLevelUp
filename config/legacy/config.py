class Config:
    '''
    ====== Configuration Parameters ======
    Tune these values based on your gameplay and detection needs.
    --------------------------------------
    '''
    # ────────────────
    # Keyboard Mapping
    # ────────────────
    # Adjust the following key to match the in-game keybinding for your character.

    # Key to trigger AoE skill (e.g., Monk's AoE heal or Mage's AoE attack).
    aoe_skill_key = "s"

    # Key to trigger the basic attack skill, like Mage's Magic Claw.
    magic_claw_key = "d"

    # Key to trigger Mage's teleport skill
    teleport_key = "" # set to "", if need to disable teleport skill

    # Key for jumping.
    jump_key = "z"

    # Key to use a health potion.
    heal_key = ""

    # Key to use a mana potion.
    add_mp_key = ""

    # ────────────────
    # Buff skill
    # ────────────────
    # Buff skill keys, e.g., magical sheild, angel blessing
    buff_skill_keys     = ["1", "2"]
    buff_skill_cooldown = [140, 45] # Second
    buff_skill_active_duration = 1 # second
    buff_skill_action_cooldown = 1 # second, avoid cast buff skill after attack

    # ────────────────
    # System
    # ────────────────
    # FPS(Frame per Second) limit for main thread
    fps_limit = 10
    show_debug_window = True # False, disable debug window to save system resource

    # ────────────────
    # Mage Teleport
    # ────────────────
    # WIP feature
    # whether to activate Mage's teleport skill while walking
    is_use_teleport_to_walk = False
    # Mage's teleport skill cooldown
    teleport_cooldown = 1 # second

    # ────────────────
    # Edge Teleport
    # ────────────────
    # Mage can use teleport skill if they're too close to edge
    is_edge_teleport = False
    edge_teleport_box_width  = 20
    edge_teleport_box_height = 10
    edge_teleport_color_code = (255,127,127) # (R,G,B)

    # ────────────────
    # NameTag Recongnition
    # ────────────────
    # offset from the nametag's top-left corner to the player's center
    nametag_offset = (-50, 30) # pixel
    nametag_diff_thres = 0.2

    # Nametag template matching threshold.
    # If the matching diff is smaller than <nametag_global_thres>
    # it will only search area near the last frame nametag.
    # If diff is bigger than <nametag_global_thres>, it will search the whole frame
    # and get the best match.
    # If you find the nametag is cached, but the location is incorrect.
    # Disable this feature by setting nametag_global_thres = 0.0
    nametag_global_thres = 0.2
    nametag_split_width = 30 # pixel, vertically split nametag
    nametag_detection_mode = "grayscale" # "grayscale", "white_mask"

    # ────────────────
    # Camera
    # ────────────────
    # only use this vertical range of the screen to localize camera on map
    camera_ceiling = 60  # pixel (top)
    camera_floor = 665   # pixel (bottom)

    # ────────────────
    # Attack Settings
    # ────────────────
    # aoe skill attack range relative to player position
    aoe_skill_range_x = 400 # pixels (horizontal range)
    aoe_skill_range_y = 170  # pixels (vertical range)
    # magic claw skill attack range relative to player position
    # 槍騎
    magic_claw_range_x = 140 # pixels (horizontal range)
    magic_claw_range_y = 100  # pixels (vertical range)
    # 槍手
    # magic_claw_range_x = 380 # pixels (horizontal range)
    # magic_claw_range_y = 90  # pixels (vertical range)
    # attack cooldown time in seconds
    attack_cooldown = 0.05  # seconds between attacks
    # character turn delay before attack
    character_turn_delay = 0.02  # seconds to wait for character to turn before attacking

    # ────────────────
    # Monster Detection
    # ────────────────
    monster_diff_thres = 0.8 # 0.8   # template match similarity threshold
    monster_search_margin = 50  # extra margin around attack box for monster search
    blur_range = 5
    monster_detect_mode = "contour_only" # "contour_only" "color", "grayscale" "template_free"
    monster_detect_with_health_bar = True
    monster_health_bar_color = (71,204,64) # (B,G,R)
    character_width = 100
    character_height = 150

    # ────────────────
    # Route Detection (color code)
    # ────────────────
    color_code_search_range = 10 # radius to find nearest color route from player center

    # ────────────────
    # Movement Behavior
    # ────────────────
    up_drag_duration = 1.0 # hold duration for 'up' key to prevent rope-sticking (in seconds)
    down_drag_duration = 1.0 # seconds
    watch_dog_timeout = 10 # seconds, if player doesn't move for 3 second, random perform an action
    watch_dog_range = 10 # pixel, if player location is smaller than watch_dog_range, consider it doesn't move

    # ────────────────
    # Runes Warning
    # ────────────────
    rune_warning_top_left     = (513, 196)
    rune_warning_bottom_right = (768, 236)
    rune_warning_diff_thres = 0.2

    # ────────────────
    # Rune Detection
    # ────────────────
    rune_detect_box_width = 120
    rune_detect_box_height = 150
    rune_detect_diff_thres = 0.1
    rune_finding_timeout = 1200 # second
    rune_detect_level_coef = 0.1 # raise threshold for each level
    rune_detect_level_raise_interval = 60 # second
    near_rune_duration = 15 # second

    # ────────────────
    # Rune mini-game
    # ────────────────
    arrow_box_size = 80 # pixel, 75x75 box
    arrow_box_interval = 170 # pixel width
    arrow_box_start_point = (355, 365)
    arrow_box_diff_thres = 0.2

    # ────────────────
    # HP Bar and HP bar
    # ────────────────
    heal_ratio = 0.5 # heal when hp is below 50%
    add_mp_ratio = 0.5 # drink potion when mp is below 50%
    # Health monitor cooldowns (to prevent spam)
    heal_cooldown = 0.5  # seconds between heals
    mp_cooldown = 0.5    # seconds between MP potions

    # ────────────────
    # Mini-Map
    # ────────────────
    minimap_upscale_factor = 4 # upscale 4 time for debug route image
    minimap_player_color = (136, 255, 255) # BGR

    # ────────────────
    # Patrol Mode
    # ────────────────
    patrol_range = [0.2, 0.8] # 0.0 - 1.0, 0.0 means the left boarder of game window
                              # 1.0 means the right boarder of game window
    turn_point_thres = 10 # 10 frames
    patrol_attack_interval = 2.5 # sec, attack every 2.5 second

    # ────────────────
    # Map Scan
    # ────────────────
    map_scan_padding = 30 # pixel, How width the black margin on map

    # ────────────────
    # Route recoder
    # ────────────────
    route_recoder_draw_blob_cooldown = 0.7 # second, can only draw blob for every 0.7 second

    # ────────────────
    # Don't modify the following parameter unless you know what you are doing
    # ────────────────
    game_window_title = 'MapleStory Worlds'
    # color code for patrol route
    color_code = {
        # R   G   B
        (255, 0, 0): "walk left", # red
        (0, 0, 255): "walk right", # blue
        (255,127,0): "jump left", # orange
        (0,255,255): "jump right", # sky blue
        (127,255,0): "jump down", # light_green
        (255,0,255): "jump", # purple
        (127,127,127): "up", # gray
        (255,255,127): "down", # light_yellow
        (0,255,127): "stop", # pink_green
        (255,255,0): "goal", # yellow
        # (255,0,127): "teleport up", # pink
        # (127,0,255): "teleport down", # light_purple
        # (0, 127, 0): "teleport left", # dark green
        # (139, 69, 19): "teleport right" # brown
    }

    window_size = (752, 1282)

