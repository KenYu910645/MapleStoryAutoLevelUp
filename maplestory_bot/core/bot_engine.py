"""挂机引擎模块。

``BotEngine`` 在独立线程中运行主循环，依次完成：

1. 捕获游戏窗口画面
2. 模板匹配定位角色位置
3. HSV 分析 HP/MP 血条，低于阈值自动使用药水
4. 匹配所有怪物模板
5. 怪物进入攻击范围 → 自动攻击；否则向最近怪物移动
6. 无怪物时在中心点周围 ``move_radius`` 内巡逻
7. 按冷却时间循环释放技能

引擎通过回调函数把日志、统计、状态推送到 UI 层（不直接依赖 Qt）。
"""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from config import BotConfig, SkillConfig
from core.image_recognition import ImageRecognition
from core.input_simulator import InputSimulator
from core.screen_capture import ScreenCapture


# 引擎状态
STATE_IDLE = "idle"          # 等待/未运行
STATE_PATROL = "patrol"      # 巡逻中
STATE_ATTACK = "attack"      # 攻击中
STATE_MOVE = "move"          # 移动向怪物
STATE_RECOVER = "recover"    # 使用药水中


@dataclass
class EngineStats:
    """引擎运行统计。"""
    total_loops: int = 0
    attacks: int = 0
    skills_used: int = 0
    hp_potions: int = 0
    mp_potions: int = 0
    monsters_detected: int = 0
    runtime_seconds: float = 0.0
    hp_percent: float = 100.0
    mp_percent: float = 100.0
    state: str = STATE_IDLE
    character_pos: Tuple[int, int] = (0, 0)

    def to_dict(self) -> Dict:
        return {
            "total_loops": self.total_loops,
            "attacks": self.attacks,
            "skills_used": self.skills_used,
            "hp_potions": self.hp_potions,
            "mp_potions": self.mp_potions,
            "monsters_detected": self.monsters_detected,
            "runtime_seconds": round(self.runtime_seconds, 1),
            "hp_percent": round(self.hp_percent, 1),
            "mp_percent": round(self.mp_percent, 1),
            "state": self.state,
            "character_pos": list(self.character_pos),
        }


class BotEngine:
    """挂机主引擎。线程安全地通过 ``stop`` 控制启停。"""

    def __init__(self, config: BotConfig,
                 on_log: Optional[Callable[[str], None]] = None,
                 on_stats: Optional[Callable[[Dict], None]] = None,
                 on_state: Optional[Callable[[str], None]] = None) -> None:
        self.config = config
        self._on_log = on_log or (lambda msg: None)
        self._on_stats = on_stats or (lambda s: None)
        self._on_state = on_state or (lambda s: None)

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._pause_event.set()  # 默认非暂停

        self.stats = EngineStats()
        self._start_time = 0.0
        self._skill_last_used: Dict[str, float] = {}
        self._recovery_last_used = {"hp": 0.0, "mp": 0.0}
        # 缓存模板
        self._character_template: Optional[object] = None
        self._monster_templates: List[object] = []
        self._patrol_target: Optional[Tuple[int, int]] = None

    # ------------------------------------------------------------------ 生命周期
    def start(self) -> bool:
        """启动引擎（在后台线程中运行）。返回是否成功启动。"""
        if self._thread and self._thread.is_alive():
            self._log("引擎已在运行")
            return False
        self.config.save()  # 启动前保存配置
        if not self._load_templates():
            self._log("模板加载失败，无法启动")
            return False
        if not self.config.window_handle:
            self._log("未选择游戏窗口，无法启动")
            return False

        self._stop_event.clear()
        self._pause_event.set()
        self._skill_last_used.clear()
        self._recovery_last_used = {"hp": 0.0, "mp": 0.0}
        self._patrol_target = None
        self.stats = EngineStats()
        self._start_time = time.monotonic()
        self._set_state(STATE_PATROL)

        self._thread = threading.Thread(target=self._run, name="BotEngine",
                                        daemon=True)
        self._thread.start()
        self._log("挂机引擎已启动")
        return True

    def stop(self) -> None:
        """停止引擎。"""
        self._stop_event.set()
        self._pause_event.set()  # 解除暂停以便线程退出
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._thread = None
        self._set_state(STATE_IDLE)
        self._log("挂机引擎已停止")

    def pause(self) -> None:
        """暂停（不退出线程）。"""
        self._pause_event.clear()
        self._set_state(STATE_IDLE)
        self._log("引擎已暂停")

    def resume(self) -> None:
        """从暂停恢复。"""
        self._pause_event.set()
        self._set_state(STATE_PATROL)
        self._log("引擎已恢复")

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------ 模板
    def _load_templates(self) -> bool:
        """加载角色与怪物模板图片。"""
        self._character_template = ImageRecognition.load_template(
            self.config.character_template_path)
        if self._character_template is None:
            self._log("警告：未加载到角色模板，将使用移动中心点作为角色位置")
        self._monster_templates = []
        for p in self.config.monster_template_paths:
            t = ImageRecognition.load_template(p)
            if t is not None:
                self._monster_templates.append(t)
        if not self._monster_templates:
            self._log("警告：未加载到怪物模板，将无法识别怪物")
        return True  # 即使部分缺失也允许启动

    # ------------------------------------------------------------------ 主循环
    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                # 暂停：忙等但低 CPU
                while not self._pause_event.wait(timeout=0.2):
                    if self._stop_event.is_set():
                        return
                if self._stop_event.is_set():
                    return
                try:
                    self._tick()
                except Exception as e:  # 单次循环异常不应中断引擎
                    self._log(f"循环异常: {e}")
                    time.sleep(1.0)
        finally:
            self._set_state(STATE_IDLE)
            self._emit_stats()

    def _tick(self) -> None:
        """单次主循环。"""
        loop_start = time.monotonic()
        self.stats.total_loops += 1
        self.stats.runtime_seconds = time.monotonic() - self._start_time

        # 1. 截图
        screen = ScreenCapture.capture(self.config.window_handle)
        if screen is None:
            self._log("截图失败，请确认游戏窗口仍存在")
            time.sleep(1.0)
            return

        # 2. 定位角色
        char_pos = self._locate_character(screen)

        # 3. 自动恢复
        self._do_recovery(screen)

        # 4. 识别怪物
        monsters = self._find_monsters(screen)
        self.stats.monsters_detected = len(monsters)

        # 5. 决策：攻击 / 移动 / 巡逻
        if monsters:
            target = self._pick_target(monsters, char_pos)
            if target is not None:
                dist = ImageRecognition.distance(char_pos, target)
                if dist <= self.config.attack_range:
                    self._do_attack(target, dist)
                else:
                    self._move_toward(char_pos, target, dist)
            else:
                self._patrol(char_pos)
        else:
            self._patrol(char_pos)

        # 6. 技能循环
        self._do_skills()

        # 7. 推送统计
        self._emit_stats()

        # 8. 控制频率
        elapsed = time.monotonic() - loop_start
        sleep_time = self.config.scan_interval - elapsed
        if sleep_time > 0:
            time.sleep(sleep_time)

    # ------------------------------------------------------------------ 角色
    def _locate_character(self, screen) -> Tuple[int, int]:
        """返回角色在客户区中的坐标。"""
        if self._character_template is not None:
            if self.config.multi_scale_match:
                m = ImageRecognition.match_multi_scale(
                    screen, self._character_template, self.config.match_threshold)
            else:
                m = ImageRecognition.match_template(
                    screen, self._character_template, self.config.match_threshold)
            if m is not None:
                pos = ImageRecognition.center_of(m)
                self.stats.character_pos = pos
                return pos
            self._log("未匹配到角色，使用配置中心点", level="debug")
        # 退化为配置中心点
        pos = (self.config.move_center_x, self.config.move_center_y)
        self.stats.character_pos = pos
        return pos

    # ------------------------------------------------------------------ 恢复
    def _do_recovery(self, screen) -> None:
        """HP/MP 自动恢复。"""
        now = time.monotonic()
        # 防止药水连按：至少间隔 1 秒
        if now - self._recovery_last_used["hp"] < 1.0 and \
           now - self._recovery_last_used["mp"] < 1.0:
            pass

        hp_bar = ImageRecognition.crop_screen(
            screen, self.config.hp_bar_x, self.config.hp_bar_y,
            self.config.hp_bar_width, self.config.hp_bar_height)
        mp_bar = ImageRecognition.crop_screen(
            screen, self.config.mp_bar_x, self.config.mp_bar_y,
            self.config.mp_bar_width, self.config.mp_bar_height)

        if hp_bar.size > 0 and self.config.hp_bar_width > 0 and \
           self.config.hp_bar_height > 0:
            hp = ImageRecognition.analyze_bar_percentage(hp_bar, color="red")
            self.stats.hp_percent = hp
            if hp < self.config.hp_threshold and self.config.hp_recovery_key:
                if now - self._recovery_last_used["hp"] >= 1.0:
                    InputSimulator.press_key(
                        self.config.hp_recovery_key,
                        hwnd=self.config.window_handle,
                        use_postmessage=self.config.use_postmessage)
                    self._recovery_last_used["hp"] = now
                    self.stats.hp_potions += 1
                    self._set_state(STATE_RECOVER)
                    self._log(f"HP={hp:.0f}% 低于阈值，使用药水 "
                              f"[{self.config.hp_recovery_key}]")

        if mp_bar.size > 0 and self.config.mp_bar_width > 0 and \
           self.config.mp_bar_height > 0:
            mp = ImageRecognition.analyze_bar_percentage(mp_bar, color="blue")
            self.stats.mp_percent = mp
            if mp < self.config.mp_threshold and self.config.mp_recovery_key:
                if now - self._recovery_last_used["mp"] >= 1.0:
                    InputSimulator.press_key(
                        self.config.mp_recovery_key,
                        hwnd=self.config.window_handle,
                        use_postmessage=self.config.use_postmessage)
                    self._recovery_last_used["mp"] = now
                    self.stats.mp_potions += 1
                    self._set_state(STATE_RECOVER)
                    self._log(f"MP={mp:.0f}% 低于阈值，使用药水 "
                              f"[{self.config.mp_recovery_key}]")

    # ------------------------------------------------------------------ 怪物
    def _find_monsters(self, screen) -> List[Tuple[int, int]]:
        """匹配所有怪物模板，返回中心坐标列表。"""
        results: List[Tuple[int, int, float]] = []
        for t in self._monster_templates:
            boxes = ImageRecognition.match_template_multi(
                screen, t, self.config.match_threshold)
            for b in boxes:
                center = ImageRecognition.center_of(b)
                results.append((center[0], center[1], b[4]))
        if not results:
            return []
        # 按匹配分数降序，简单的去重（相近点合并）
        results.sort(key=lambda r: r[2], reverse=True)
        unique: List[Tuple[int, int]] = []
        for x, y, _ in results:
            if all(ImageRecognition.distance((x, y), u) > 20 for u in unique):
                unique.append((x, y))
        return unique

    def _pick_target(self, monsters, char_pos) -> Optional[Tuple[int, int]]:
        """选择最近怪物。"""
        if not monsters:
            return None
        return min(monsters, key=lambda m: ImageRecognition.distance(char_pos, m))

    # ------------------------------------------------------------------ 攻击
    def _do_attack(self, target, dist) -> None:
        """朝目标方向攻击。"""
        self._set_state(STATE_ATTACK)
        # 朝向怪物：左右调整（仅 x 方向）
        char_x = self.stats.character_pos[0]
        if target[0] < char_x - 5:
            self._face_direction("left")
        elif target[0] > char_x + 5:
            self._face_direction("right")
        InputSimulator.press_key(
            self.config.attack_key,
            hwnd=self.config.window_handle,
            use_postmessage=self.config.use_postmessage)
        self.stats.attacks += 1
        self._log(f"攻击怪物 距离={dist:.0f}px [{self.config.attack_key}]")

    def _face_direction(self, direction: str) -> None:
        """短暂按方向键以朝向目标（不实际移动）。"""
        InputSimulator.hold_key(
            direction, seconds=0.05,
            hwnd=self.config.window_handle,
            use_postmessage=self.config.use_postmessage)

    # ------------------------------------------------------------------ 移动
    def _move_toward(self, char_pos, target, dist) -> None:
        """向怪物方向移动一步。"""
        self._set_state(STATE_MOVE)
        dx = target[0] - char_pos[0]
        step = min(0.3, max(0.05, dist / 500.0))
        if dx > 5:
            self._log(f"向右移动接近怪物 距离={dist:.0f}px")
            InputSimulator.hold_key("right", seconds=step,
                                    hwnd=self.config.window_handle,
                                    use_postmessage=self.config.use_postmessage)
        elif dx < -5:
            self._log(f"向左移动接近怪物 距离={dist:.0f}px")
            InputSimulator.hold_key("left", seconds=step,
                                    hwnd=self.config.window_handle,
                                    use_postmessage=self.config.use_postmessage)

    # ------------------------------------------------------------------ 巡逻
    def _patrol(self, char_pos) -> None:
        """在中心点附近巡逻。"""
        self._set_state(STATE_PATROL)
        cx, cy = self.config.move_center_x, self.config.move_center_y
        radius = self.config.move_radius
        if radius <= 0:
            return
        # 若无目标或已到达，生成新目标
        if self._patrol_target is None or \
           ImageRecognition.distance(char_pos, self._patrol_target) < 20:
            angle = random.uniform(0, 2 * math.pi)
            r = random.uniform(0, radius)
            self._patrol_target = (int(cx + r * math.cos(angle)),
                                   int(cy + r * math.sin(angle)))
            self._log(f"生成新巡逻点 {self._patrol_target}")

        tx, ty = self._patrol_target
        dx = tx - char_pos[0]
        step = 0.2
        if abs(dx) < 5:
            self._patrol_target = None  # 到达，下次重新生成
            return
        if dx > 0:
            InputSimulator.hold_key("right", seconds=step,
                                    hwnd=self.config.window_handle,
                                    use_postmessage=self.config.use_postmessage)
        else:
            InputSimulator.hold_key("left", seconds=step,
                                    hwnd=self.config.window_handle,
                                    use_postmessage=self.config.use_postmessage)

    # ------------------------------------------------------------------ 技能
    def _do_skills(self) -> None:
        """按冷却时间循环释放技能。"""
        if not self.config.skills:
            return
        now = time.monotonic()
        for skill in self.config.skills:
            if not skill.key:
                continue
            last = self._skill_last_used.get(skill.name or skill.key, 0.0)
            if now - last >= skill.cooldown:
                InputSimulator.press_key(
                    skill.key,
                    hwnd=self.config.window_handle,
                    use_postmessage=self.config.use_postmessage)
                self._skill_last_used[skill.name or skill.key] = now
                self.stats.skills_used += 1
                self._log(f"释放技能 [{skill.name or skill.key}] "
                          f"按键={skill.key} 冷却={skill.cooldown}s")

    # ------------------------------------------------------------------ 工具
    def _log(self, msg: str, level: str = "info") -> None:
        try:
            self._on_log(f"[{level}] {msg}")
        except Exception:
            pass

    def _set_state(self, state: str) -> None:
        if self.stats.state == state:
            return
        self.stats.state = state
        try:
            self._on_state(state)
        except Exception:
            pass

    def _emit_stats(self) -> None:
        try:
            self._on_stats(self.stats.to_dict())
        except Exception:
            pass
