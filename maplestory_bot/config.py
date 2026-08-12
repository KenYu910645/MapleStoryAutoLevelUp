"""配置管理模块。

使用 dataclass 定义所有可配置项，支持 JSON 持久化。
配置会自动保存到 ``bot_config.json``，也可以手动保存/加载到指定路径。
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class SkillConfig:
    """单个技能配置。"""

    name: str = ""           # 技能名称（仅用于显示）
    key: str = ""            # 释放按键（单字符或方向键名称）
    cooldown: float = 1.0    # 冷却时间（秒）


@dataclass
class BotConfig:
    """挂机工具全部配置。"""

    # ---------- 窗口选择 ----------
    window_title_keyword: str = "冒险岛"
    window_handle: int = 0  # 选中的窗口句柄（HWND 整数）

    # ---------- 图片模板 ----------
    character_template_path: str = ""
    monster_template_paths: List[str] = field(default_factory=list)
    match_threshold: float = 0.75

    # ---------- 移动与攻击 ----------
    move_center_x: int = 0
    move_center_y: int = 0
    move_radius: int = 100
    attack_key: str = "x"
    attack_range: int = 100
    scan_interval: float = 0.5  # 引擎扫描间隔（秒）
    multi_scale_match: bool = True  # 是否启用多尺度匹配

    # ---------- 自动恢复 ----------
    hp_recovery_key: str = ""
    mp_recovery_key: str = ""
    hp_threshold: float = 50.0   # 百分比
    mp_threshold: float = 50.0
    # HP 血条区域（相对游戏窗口客户区）
    hp_bar_x: int = 0
    hp_bar_y: int = 0
    hp_bar_width: int = 100
    hp_bar_height: int = 10
    # MP 血条区域
    mp_bar_x: int = 0
    mp_bar_y: int = 0
    mp_bar_width: int = 100
    mp_bar_height: int = 10

    # ---------- 技能 ----------
    skills: List[SkillConfig] = field(default_factory=list)

    # ---------- 其它 ----------
    use_postmessage: bool = False  # True=PostMessage 后台按键, False=keybd_event 前台按键

    # ------------------------------------------------------------------ 持久化
    def save(self, path: str = "bot_config.json") -> None:
        """将配置保存为 JSON 文件。"""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str = "bot_config.json") -> "BotConfig":
        """从 JSON 文件加载配置，文件不存在则返回默认配置。"""
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return cls()

        # 技能单独处理
        skills_data = data.pop("skills", [])
        skills = [SkillConfig(**s) for s in skills_data if isinstance(s, dict)]

        # 只保留 dataclass 中已定义的字段，避免旧配置多余字段报错
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}

        return cls(skills=skills, **filtered)

    # ------------------------------------------------------------------ 工具
    def clone(self) -> "BotConfig":
        """深拷贝当前配置。"""
        return BotConfig.load_json_dict(asdict(self))

    @classmethod
    def load_json_dict(cls, data: dict) -> "BotConfig":
        """从字典构建配置。"""
        skills_data = data.pop("skills", [])
        skills = [SkillConfig(**s) for s in skills_data if isinstance(s, dict)]
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(skills=skills, **filtered)

    def get_skill_by_name(self, name: str) -> Optional[SkillConfig]:
        for s in self.skills:
            if s.name == name:
                return s
        return None
