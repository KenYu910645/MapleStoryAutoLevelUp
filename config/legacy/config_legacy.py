class Config:
    '''
    ====== Configuration Parameters ======
    Tune these values based on your gameplay and detection needs.
    --------------------------------------
    '''
    # ────────────────
    # Perference
    # ────────────────
    is_use_teleport_to_walk = False # use teleport to walk
    teleport_cooldown = 1 # second
    is_edge_teleport = False
    fps_limit = 10

    # Buff skill keys, e.g., magical sheild, angel blessing
    buff_skill_keys     = ["1", "2"]
    buff_skill_cooldown = [140, 45] # Second
    buff_skill_active_duration = 1 # second

    # ────────────────
    # Keyboard Mapping
    # ────────────────
    aoe_skill_key = "s" # It can be monk's healing skill
    magic_claw_key = "d"
    jump_key = "z"
    heal_key = "q"
    add_mp_key = "2" # Drink potion
    teleport_key = "" # Mage's teleport skill

    # ────────────────
    # Edge Teleport
    # ────────────────
    edge_teleport_box_width  = 150
    edge_teleport_box_height = 70
    edge_teleport_minimap_box_width  = 50
    edge_teleport_minimap_box_height = 20
    edge_teleport_color_code = (255,127,127) # (R,G,B)

    # ────────────────
    # Player Localization
    # ────────────────
    # offset from the nametag's top-left corner to the player's center
    nametag_offset = (-50, 30) # pixel
    nametag_diff_thres = 0.4

    # ────────────────
    # Camera Localization
    # ────────────────
    # only use this vertical range of the screen to localize camera on map
    camera_ceiling = 60  # pixel (top)
    camera_floor = 665   # pixel (bottom)
    localize_diff_thres = 0.5
    localize_downscale_factor = 1.0 #0.25 # ratio = 1/4
    localize_cached_interval = 3 # second, how long to use cached camera location until full search

    # ────────────────
    # Attack Settings
    # ────────────────
    # aoe skill attack range relative to player position
    aoe_skill_range_x = 400 # pixels (horizontal range)
    aoe_skill_range_y = 150  # pixels (vertical range)
    # magic claw skill attack range relative to player position
    magic_claw_range_x = 350 # pixels (horizontal range)
    magic_claw_range_y = 70  # pixels (vertical range)

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
    color_code_search_range = 80 # radius to find nearest color route from player center

    # ────────────────
    # Movement Behavior
    # ────────────────
    up_drag_duration = 1.0 # hold duration for 'up' key to prevent rope-sticking (in seconds)
    down_drag_duration = 1.0 # seconds
    watch_dog_timeout = 10 # seconds, if player doesn't move for 3 second, random perform an action
    watch_dog_range = 10 # pixel, if player location is smaller than watch_dog_range, consider it doesn't move

    # ────────────────
    # Debug Options
    # ────────────────
    enable_debug_windows = True   # show debug window (false = better performance)

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
    near_rune_duration = 5 # second

    # ────────────────
    # Rune mini-game
    # ────────────────
    arrow_box_size = 80 # pixel, 75x75 box
    arrow_box_interval = 170 # pixel width
    arrow_box_start_point = (355, 355)
    arrow_box_diff_thres = 0.2

    # ────────────────
    # HP Bar and HP bar
    # ────────────────
    hp_bar_top_left = (348, 732)
    hp_bar_bottom_right = (509, 749)
    mp_bar_top_left = (517, 732)
    mp_bar_bottom_right = (678, 749)
    exp_bar_top_left = (699, 732)
    exp_bar_bottom_right = (860, 749)
    heal_ratio = 0.5 # heal when hp is below 50%
    add_mp_ratio = 0.5 # drink potion when mp is below 50%

    # ────────────────
    # Mini-Map
    # ────────────────
    is_use_minimap = False # True, False
    minimap_player_color = (136, 255, 255) # yellow dot, (B, G, R)
    minimap_color_code_search_range = 30 # pixel
    minimap_upscale_factor = 4 # upscale 4 time for debug route image

    # ────────────────
    # Patrol
    # ────────────────
    patrol_range = [0.2, 0.8] # 0.0 - 1.0, 0.0 means the left boarder of game window
                              # 1.0 means the right boarder of game window
    turn_point_thres = 10 # 10 frames
    patrol_attack_interval = 2.5 # sec, attack every 2.5 second

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
    }

    window_size = (752, 1282)
