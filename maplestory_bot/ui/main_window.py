"""PyQt5 主窗口。

包含 6 个标签页：
1. 窗口选择      - 枚举并选中游戏窗口
2. 图片模板      - 上传角色 / 怪物截图
3. 移动与攻击    - 巡逻范围、攻击范围、扫描间隔
4. 自动恢复      - HP/MP 阈值与血条区域
5. 技能设置      - 多技能按键与冷却
6. 运行状态      - 实时日志与统计

引擎在独立线程运行，通过 ``SignalBridge`` 跨线程安全更新 UI。
"""

from __future__ import annotations

import os
from typing import List

from PyQt5.QtCore import Qt, QObject, pyqtSignal, pyqtSlot, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QApplication, QCheckBox, QComboBox,
    QDialog, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget, QInputDialog,
)

from config import BotConfig, SkillConfig
from core.bot_engine import (
    BotEngine, STATE_ATTACK, STATE_IDLE, STATE_MOVE, STATE_PATROL,
    STATE_RECOVER,
)
from core.window_manager import WindowManager


CONFIG_FILE = "bot_config.json"

STATE_LABELS = {
    STATE_IDLE: "空闲",
    STATE_PATROL: "巡逻",
    STATE_ATTACK: "攻击",
    STATE_MOVE: "移动",
    STATE_RECOVER: "恢复",
}


class SignalBridge(QObject):
    """跨线程信号桥接。BotEngine 回调 -> Qt 信号 -> UI 槽。"""
    log = pyqtSignal(str)
    stats = pyqtSignal(dict)
    state = pyqtSignal(str)


# ============================================================================
# 标签页 1：窗口选择
# ============================================================================
class WindowTab(QWidget):
    """枚举并选择游戏窗口。"""

    def __init__(self, config: BotConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self.wm = WindowManager()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 搜索栏
        search_box = QGroupBox("搜索窗口")
        s_layout = QHBoxLayout(search_box)
        s_layout.addWidget(QLabel("标题关键字:"))
        self.keyword_edit = QLineEdit(self.config.window_title_keyword)
        self.keyword_edit.setPlaceholderText('如 "冒险岛"')
        s_layout.addWidget(self.keyword_edit, 1)
        self.btn_search = QPushButton("搜索")
        self.btn_search.clicked.connect(self.on_search)
        s_layout.addWidget(self.btn_search)
        self.btn_refresh = QPushButton("刷新所有窗口")
        self.btn_refresh.clicked.connect(self.on_refresh)
        s_layout.addWidget(self.btn_refresh)
        layout.addWidget(search_box)

        # 窗口列表
        list_box = QGroupBox("窗口列表")
        l_layout = QVBoxLayout(list_box)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        l_layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.btn_select = QPushButton("选择此窗口")
        self.btn_select.clicked.connect(self.on_select)
        btn_layout.addWidget(self.btn_select)
        btn_layout.addStretch()
        l_layout.addLayout(btn_layout)

        self.label_current = QLabel("当前选中: 无")
        l_layout.addWidget(self.label_current)
        layout.addWidget(list_box, 1)

        layout.addStretch()
        self.on_refresh()

    def on_search(self):
        keyword = self.keyword_edit.text().strip()
        try:
            windows = self.wm.search_windows(keyword)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"枚举窗口失败:\n{e}")
            return
        self._populate(windows)

    def on_refresh(self):
        try:
            windows = self.wm.enum_windows()
        except Exception as e:
            QMessageBox.warning(self, "错误", f"枚举窗口失败:\n{e}")
            return
        self._populate(windows)

    def _populate(self, windows):
        self.list_widget.clear()
        for hwnd, title in windows:
            item_text = f"[{hwnd}]  {title}"
            self.list_widget.addItem(item_text)

    def on_select(self):
        row = self.list_widget.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先在列表中选择一个窗口")
            return
        text = self.list_widget.item(row).text()
        try:
            hwnd = int(text.split("]")[0].replace("[", "").strip())
        except (ValueError, IndexError):
            QMessageBox.warning(self, "错误", "无法解析窗口句柄")
            return
        self.config.window_handle = hwnd
        self.config.window_title_keyword = self.keyword_edit.text().strip()
        self.label_current.setText(f"当前选中: hwnd={hwnd}")
        if self.wm.select_window(hwnd):
            QMessageBox.information(self, "成功", f"已选中窗口 hwnd={hwnd} 并置于前台")
        else:
            QMessageBox.information(self, "提示",
                f"已记录 hwnd={hwnd}，但前台置顶失败（窗口可能最小化）")


# ============================================================================
# 标签页 2：图片模板
# ============================================================================
class TemplateTab(QWidget):
    """上传角色 / 怪物截图模板。"""

    def __init__(self, config: BotConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self._refresh_display()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 角色
        char_box = QGroupBox("角色模板")
        c_layout = QHBoxLayout(char_box)
        self.char_label = QLabel("未选择")
        self.char_label.setStyleSheet("color:#888;")
        c_layout.addWidget(self.char_label, 1)
        self.btn_char = QPushButton("上传角色截图")
        self.btn_char.clicked.connect(self.on_upload_char)
        c_layout.addWidget(self.btn_char)
        self.btn_char_clear = QPushButton("清除")
        self.btn_char_clear.clicked.connect(self.on_clear_char)
        c_layout.addWidget(self.btn_char_clear)
        layout.addWidget(char_box)

        # 怪物
        mon_box = QGroupBox("怪物模板 (可多个)")
        m_layout = QVBoxLayout(mon_box)
        self.mon_list = QListWidget()
        m_layout.addWidget(self.mon_list)
        btn_row = QHBoxLayout()
        self.btn_mon_add = QPushButton("添加怪物图片")
        self.btn_mon_add.clicked.connect(self.on_add_monster)
        btn_row.addWidget(self.btn_mon_add)
        self.btn_mon_remove = QPushButton("移除选中")
        self.btn_mon_remove.clicked.connect(self.on_remove_monster)
        btn_row.addWidget(self.btn_mon_remove)
        m_layout.addLayout(btn_row)
        layout.addWidget(mon_box, 1)

        # 阈值
        thresh_box = QGroupBox("匹配参数")
        t_layout = QFormLayout(thresh_box)
        self.thresh_spin = QDoubleSpinBox()
        self.thresh_spin.setRange(0.1, 1.0)
        self.thresh_spin.setSingleStep(0.05)
        self.thresh_spin.setValue(self.config.match_threshold)
        t_layout.addRow("匹配阈值 (越高越严格):", self.thresh_spin)
        self.scale_check = QCheckBox("启用多尺度匹配")
        self.scale_check.setChecked(self.config.multi_scale_match)
        t_layout.addRow(self.scale_check)
        layout.addWidget(thresh_box)
        layout.addStretch()

    def on_upload_char(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择角色截图", "", "图片 (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.config.character_template_path = path
            self._refresh_display()

    def on_clear_char(self):
        self.config.character_template_path = ""
        self._refresh_display()

    def on_add_monster(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择怪物截图 (可多选)", "", "图片 (*.png *.jpg *.jpeg *.bmp)")
        for p in paths:
            if p not in self.config.monster_template_paths:
                self.config.monster_template_paths.append(p)
        self._refresh_display()

    def on_remove_monster(self):
        row = self.mon_list.currentRow()
        if 0 <= row < len(self.config.monster_template_paths):
            del self.config.monster_template_paths[row]
            self._refresh_display()

    def _refresh_display(self):
        if self.config.character_template_path:
            name = os.path.basename(self.config.character_template_path)
            self.char_label.setText(name)
            self.char_label.setStyleSheet("color:#1a1;")
        else:
            self.char_label.setText("未选择")
            self.char_label.setStyleSheet("color:#888;")

        self.mon_list.clear()
        for p in self.config.monster_template_paths:
            self.mon_list.addItem(os.path.basename(p))

    def apply_to_config(self):
        self.config.match_threshold = self.thresh_spin.value()
        self.config.multi_scale_match = self.scale_check.isChecked()


# ============================================================================
# 标签页 3：移动与攻击
# ============================================================================
class MoveAttackTab(QWidget):
    def __init__(self, config: BotConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 移动范围
        move_box = QGroupBox("移动范围 (角色巡逻区域)")
        m_layout = QFormLayout(move_box)
        self.cx = QSpinBox(); self.cx.setRange(0, 10000)
        self.cx.setValue(self.config.move_center_x)
        m_layout.addRow("中心点 X:", self.cx)
        self.cy = QSpinBox(); self.cy.setRange(0, 10000)
        self.cy.setValue(self.config.move_center_y)
        m_layout.addRow("中心点 Y:", self.cy)
        self.radius = QSpinBox(); self.radius.setRange(0, 5000)
        self.radius.setValue(self.config.move_radius)
        m_layout.addRow("巡逻半径 (px):", self.radius)
        layout.addWidget(move_box)

        # 攻击
        atk_box = QGroupBox("攻击设置")
        a_layout = QFormLayout(atk_box)
        self.attack_key = QLineEdit(self.config.attack_key)
        self.attack_key.setMaxLength(10)
        a_layout.addRow("攻击按键:", self.attack_key)
        self.attack_range = QSpinBox(); self.attack_range.setRange(0, 5000)
        self.attack_range.setValue(self.config.attack_range)
        a_layout.addRow("攻击范围 (px):", self.attack_range)
        layout.addWidget(atk_box)

        # 扫描
        scan_box = QGroupBox("扫描参数")
        sc_layout = QFormLayout(scan_box)
        self.scan_interval = QDoubleSpinBox()
        self.scan_interval.setRange(0.05, 10.0)
        self.scan_interval.setSingleStep(0.05)
        self.scan_interval.setValue(self.config.scan_interval)
        sc_layout.addRow("扫描间隔 (秒):", self.scan_interval)
        layout.addWidget(scan_box)

        layout.addStretch()

    def apply_to_config(self):
        self.config.move_center_x = self.cx.value()
        self.config.move_center_y = self.cy.value()
        self.config.move_radius = self.radius.value()
        self.config.attack_key = self.attack_key.text().strip()
        self.config.attack_range = self.attack_range.value()
        self.config.scan_interval = self.scan_interval.value()


# ============================================================================
# 标签页 4：自动恢复
# ============================================================================
class RecoveryTab(QWidget):
    def __init__(self, config: BotConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # HP
        hp_box = QGroupBox("HP 恢复")
        h_layout = QFormLayout(hp_box)
        self.hp_key = QLineEdit(self.config.hp_recovery_key)
        h_layout.addRow("HP 恢复按键:", self.hp_key)
        self.hp_threshold = QDoubleSpinBox()
        self.hp_threshold.setRange(0, 100)
        self.hp_threshold.setSuffix(" %")
        self.hp_threshold.setValue(self.config.hp_threshold)
        h_layout.addRow("HP 阈值:", self.hp_threshold)
        self.hp_x = QSpinBox(); self.hp_x.setRange(0, 10000)
        self.hp_x.setValue(self.config.hp_bar_x)
        h_layout.addRow("血条 X:", self.hp_x)
        self.hp_y = QSpinBox(); self.hp_y.setRange(0, 10000)
        self.hp_y.setValue(self.config.hp_bar_y)
        h_layout.addRow("血条 Y:", self.hp_y)
        self.hp_w = QSpinBox(); self.hp_w.setRange(1, 10000)
        self.hp_w.setValue(self.config.hp_bar_width)
        h_layout.addRow("血条宽:", self.hp_w)
        self.hp_h = QSpinBox(); self.hp_h.setRange(1, 10000)
        self.hp_h.setValue(self.config.hp_bar_height)
        h_layout.addRow("血条高:", self.hp_h)
        layout.addWidget(hp_box)

        # MP
        mp_box = QGroupBox("MP 恢复")
        p_layout = QFormLayout(mp_box)
        self.mp_key = QLineEdit(self.config.mp_recovery_key)
        p_layout.addRow("MP 恢复按键:", self.mp_key)
        self.mp_threshold = QDoubleSpinBox()
        self.mp_threshold.setRange(0, 100)
        self.mp_threshold.setSuffix(" %")
        self.mp_threshold.setValue(self.config.mp_threshold)
        p_layout.addRow("MP 阈值:", self.mp_threshold)
        self.mp_x = QSpinBox(); self.mp_x.setRange(0, 10000)
        self.mp_x.setValue(self.config.mp_bar_x)
        p_layout.addRow("蓝条 X:", self.mp_x)
        self.mp_y = QSpinBox(); self.mp_y.setRange(0, 10000)
        self.mp_y.setValue(self.config.mp_bar_y)
        p_layout.addRow("蓝条 Y:", self.mp_y)
        self.mp_w = QSpinBox(); self.mp_w.setRange(1, 10000)
        self.mp_w.setValue(self.config.mp_bar_width)
        p_layout.addRow("蓝条宽:", self.mp_w)
        self.mp_h = QSpinBox(); self.mp_h.setRange(1, 10000)
        self.mp_h.setValue(self.config.mp_bar_height)
        p_layout.addRow("蓝条高:", self.mp_h)
        layout.addWidget(mp_box)

        tip = QLabel("提示: 血条坐标为相对游戏窗口客户区的左上角偏移。"
                     "建议先用截图工具测量。")
        tip.setStyleSheet("color:#666;")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        layout.addStretch()

    def apply_to_config(self):
        self.config.hp_recovery_key = self.hp_key.text().strip()
        self.config.hp_threshold = self.hp_threshold.value()
        self.config.hp_bar_x = self.hp_x.value()
        self.config.hp_bar_y = self.hp_y.value()
        self.config.hp_bar_width = self.hp_w.value()
        self.config.hp_bar_height = self.hp_h.value()
        self.config.mp_recovery_key = self.mp_key.text().strip()
        self.config.mp_threshold = self.mp_threshold.value()
        self.config.mp_bar_x = self.mp_x.value()
        self.config.mp_bar_y = self.mp_y.value()
        self.config.mp_bar_width = self.mp_w.value()
        self.config.mp_bar_height = self.mp_h.value()


# ============================================================================
# 标签页 5：技能设置
# ============================================================================
class SkillTab(QWidget):
    def __init__(self, config: BotConfig, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self._refresh_table()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["技能名称", "按键", "冷却(秒)", "操作"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("添加技能")
        self.btn_add.clicked.connect(self.on_add)
        btn_row.addWidget(self.btn_add)
        self.btn_edit = QPushButton("编辑选中")
        self.btn_edit.clicked.connect(self.on_edit)
        btn_row.addWidget(self.btn_edit)
        self.btn_del = QPushButton("删除选中")
        self.btn_del.clicked.connect(self.on_delete)
        btn_row.addWidget(self.btn_del)
        btn_row.addStretch()
        layout.addLayout(btn_row)

    def _refresh_table(self):
        self.table.setRowCount(0)
        for i, s in enumerate(self.config.skills):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(s.name))
            self.table.setItem(i, 1, QTableWidgetItem(s.key))
            self.table.setItem(i, 2, QTableWidgetItem(f"{s.cooldown:.2f}"))
            self.table.setItem(i, 3, QTableWidgetItem("右键编辑"))

    def on_add(self):
        s = self._edit_skill_dialog(None)
        if s:
            self.config.skills.append(s)
            self._refresh_table()

    def on_edit(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选择一行")
            return
        s = self._edit_skill_dialog(self.config.skills[row])
        if s:
            self.config.skills[row] = s
            self._refresh_table()

    def on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        del self.config.skills[row]
        self._refresh_table()

    def _edit_skill_dialog(self, existing: SkillConfig = None) -> SkillConfig:
        dlg = QDialog_input(self)
        if existing:
            dlg.name_edit.setText(existing.name)
            dlg.key_edit.setText(existing.key)
            dlg.cd_spin.setValue(existing.cooldown)
        if dlg.exec_() == QDialog_input.Accepted:
            return SkillConfig(
                name=dlg.name_edit.text().strip(),
                key=dlg.key_edit.text().strip(),
                cooldown=dlg.cd_spin.value(),
            )
        return None

    def apply_to_config(self):
        pass  # 直接操作 self.config.skills，无需再同步


class QDialog_input(QDialog):
    """技能编辑对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑技能")
        layout = QFormLayout(self)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("如: 火球术")
        layout.addRow("技能名称:", self.name_edit)
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("如: a / shift / F1")
        self.key_edit.setMaxLength(10)
        layout.addRow("按键:", self.key_edit)
        self.cd_spin = QDoubleSpinBox()
        self.cd_spin.setRange(0.1, 3600)
        self.cd_spin.setSingleStep(0.5)
        self.cd_spin.setValue(1.0)
        self.cd_spin.setSuffix(" s")
        layout.addRow("冷却时间:", self.cd_spin)
        btn_row = QHBoxLayout()
        ok = QPushButton("确定")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        layout.addRow(btn_row)


# ============================================================================
# 标签页 6：运行状态
# ============================================================================
class StatusTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 状态指标
        stats_box = QGroupBox("实时统计")
        s_layout = QFormLayout(stats_box)
        self.lbl_state = QLabel("空闲")
        f = QFont(); f.setBold(True); f.setPointSize(11)
        self.lbl_state.setFont(f)
        s_layout.addRow("当前状态:", self.lbl_state)
        self.lbl_hp = QLabel("HP: --")
        s_layout.addRow("血量:", self.lbl_hp)
        self.lbl_mp = QLabel("MP: --")
        s_layout.addRow("蓝量:", self.lbl_mp)
        self.lbl_runtime = QLabel("运行时间: 0.0s")
        s_layout.addRow("运行时间:", self.lbl_runtime)
        self.lbl_loops = QLabel("扫描次数: 0")
        s_layout.addRow("扫描次数:", self.lbl_loops)
        self.lbl_attacks = QLabel("攻击次数: 0")
        s_layout.addRow("攻击次数:", self.lbl_attacks)
        self.lbl_skills = QLabel("技能释放: 0")
        s_layout.addRow("技能释放:", self.lbl_skills)
        self.lbl_potions = QLabel("药水使用: 0")
        s_layout.addRow("药水使用:", self.lbl_potions)
        self.lbl_monsters = QLabel("当前怪物数: 0")
        s_layout.addRow("当前怪物数:", self.lbl_monsters)
        self.lbl_char_pos = QLabel("角色位置: --")
        s_layout.addRow("角色位置:", self.lbl_char_pos)
        layout.addWidget(stats_box)

        # 日志
        log_box = QGroupBox("运行日志")
        l_layout = QVBoxLayout(log_box)
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        font = QFont("Consolas"); font.setStyleHint(QFont.Monospace)
        self.log_edit.setFont(font)
        l_layout.addWidget(self.log_edit)
        btn_row = QHBoxLayout()
        self.btn_clear_log = QPushButton("清空日志")
        self.btn_clear_log.clicked.connect(self.log_edit.clear)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_clear_log)
        l_layout.addLayout(btn_row)
        layout.addWidget(log_box, 1)

    @pyqtSlot(str)
    def append_log(self, msg: str):
        self.log_edit.append(msg)
        # 自动滚动到底部
        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(dict)
    def update_stats(self, stats: dict):
        self.lbl_state.setText(STATE_LABELS.get(stats.get("state", ""), "未知"))
        self.lbl_hp.setText(f"HP: {stats.get('hp_percent', 0):.1f} %")
        self.lbl_mp.setText(f"MP: {stats.get('mp_percent', 0):.1f} %")
        self.lbl_runtime.setText(f"运行时间: {stats.get('runtime_seconds', 0):.1f} s")
        self.lbl_loops.setText(f"扫描次数: {stats.get('total_loops', 0)}")
        self.lbl_attacks.setText(f"攻击次数: {stats.get('attacks', 0)}")
        self.lbl_skills.setText(f"技能释放: {stats.get('skills_used', 0)}")
        potions = stats.get('hp_potions', 0) + stats.get('mp_potions', 0)
        self.lbl_potions.setText(f"药水使用: {potions}")
        self.lbl_monsters.setText(f"当前怪物数: {stats.get('monsters_detected', 0)}")
        pos = stats.get('character_pos', [0, 0])
        self.lbl_char_pos.setText(f"角色位置: ({pos[0]}, {pos[1]})")


# ============================================================================
# 主窗口
# ============================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("冒险岛怀旧服自动挂机工具")
        self.resize(900, 650)

        self.config = BotConfig.load(CONFIG_FILE)
        self.bridge = SignalBridge()
        self.engine: BotEngine = None

        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 标签页
        self.tabs = QTabWidget()
        self.tab_window = WindowTab(self.config)
        self.tab_template = TemplateTab(self.config)
        self.tab_move = MoveAttackTab(self.config)
        self.tab_recovery = RecoveryTab(self.config)
        self.tab_skill = SkillTab(self.config)
        self.tab_status = StatusTab()

        self.tabs.addTab(self.tab_window, "窗口选择")
        self.tabs.addTab(self.tab_template, "图片模板")
        self.tabs.addTab(self.tab_move, "移动与攻击")
        self.tabs.addTab(self.tab_recovery, "自动恢复")
        self.tabs.addTab(self.tab_skill, "技能设置")
        self.tabs.addTab(self.tab_status, "运行状态")
        root.addWidget(self.tabs, 1)

        # 控制栏
        ctrl_box = QGroupBox("控制")
        ctrl = QHBoxLayout(ctrl_box)
        self.btn_start = QPushButton("▶ 开始挂机")
        self.btn_start.setStyleSheet("background:#1a1;color:white;padding:6px 14px;font-weight:bold;")
        self.btn_start.clicked.connect(self.on_start)
        ctrl.addWidget(self.btn_start)

        self.btn_pause = QPushButton("⏸ 暂停")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self.on_pause)
        ctrl.addWidget(self.btn_pause)

        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("color:#a33;")
        self.btn_stop.clicked.connect(self.on_stop)
        ctrl.addWidget(self.btn_stop)

        ctrl.addStretch(10)

        self.btn_save = QPushButton("💾 保存配置")
        self.btn_save.clicked.connect(self.on_save_config)
        ctrl.addWidget(self.btn_save)

        self.btn_load = QPushButton("📂 加载配置")
        self.btn_load.clicked.connect(self.on_load_config)
        ctrl.addWidget(self.btn_load)

        root.addWidget(ctrl_box)

        # 菜单
        menu = self.menuBar().addMenu("文件")
        a_save = QAction("保存配置", self); a_save.triggered.connect(self.on_save_config)
        menu.addAction(a_save)
        a_load = QAction("加载配置", self); a_load.triggered.connect(self.on_load_config)
        menu.addAction(a_load)
        menu.addSeparator()
        a_quit = QAction("退出", self); a_quit.triggered.connect(self.close)
        menu.addAction(a_quit)

        help_menu = self.menuBar().addMenu("帮助")
        a_about = QAction("关于", self); a_about.triggered.connect(self.on_about)
        help_menu.addAction(a_about)

    def _connect_signals(self):
        self.bridge.log.connect(self.tab_status.append_log)
        self.bridge.stats.connect(self.tab_status.update_stats)
        self.bridge.state.connect(self._on_engine_state)

    # ------------------------------------------------------------------ 控件同步
    def _sync_ui_to_config(self):
        """把各标签页控件值写回 self.config。"""
        self.tab_template.apply_to_config()
        self.tab_move.apply_to_config()
        self.tab_recovery.apply_to_config()
        self.tab_skill.apply_to_config()

    def _sync_config_to_ui(self):
        """把 self.config 同步到各标签页控件。"""
        self.tab_window.keyword_edit.setText(self.config.window_title_keyword)
        if self.config.window_handle:
            self.tab_window.label_current.setText(
                f"当前选中: hwnd={self.config.window_handle}")
        self.tab_template.thresh_spin.setValue(self.config.match_threshold)
        self.tab_template.scale_check.setChecked(self.config.multi_scale_match)
        self.tab_template._refresh_display()
        self.tab_move.cx.setValue(self.config.move_center_x)
        self.tab_move.cy.setValue(self.config.move_center_y)
        self.tab_move.radius.setValue(self.config.move_radius)
        self.tab_move.attack_key.setText(self.config.attack_key)
        self.tab_move.attack_range.setValue(self.config.attack_range)
        self.tab_move.scan_interval.setValue(self.config.scan_interval)
        self.tab_recovery.hp_key.setText(self.config.hp_recovery_key)
        self.tab_recovery.hp_threshold.setValue(self.config.hp_threshold)
        self.tab_recovery.hp_x.setValue(self.config.hp_bar_x)
        self.tab_recovery.hp_y.setValue(self.config.hp_bar_y)
        self.tab_recovery.hp_w.setValue(self.config.hp_bar_width)
        self.tab_recovery.hp_h.setValue(self.config.hp_bar_height)
        self.tab_recovery.mp_key.setText(self.config.mp_recovery_key)
        self.tab_recovery.mp_threshold.setValue(self.config.mp_threshold)
        self.tab_recovery.mp_x.setValue(self.config.mp_bar_x)
        self.tab_recovery.mp_y.setValue(self.config.mp_bar_y)
        self.tab_recovery.mp_w.setValue(self.config.mp_bar_width)
        self.tab_recovery.mp_h.setValue(self.config.mp_bar_height)
        self.tab_skill._refresh_table()

    # ------------------------------------------------------------------ 引擎控制
    def on_start(self):
        self._sync_ui_to_config()
        if self.engine and self.engine.is_running:
            QMessageBox.information(self, "提示", "引擎已在运行")
            return
        # 简单校验
        if not self.config.window_handle:
            QMessageBox.warning(self, "提示", "请先在「窗口选择」标签页选中游戏窗口")
            self.tabs.setCurrentWidget(self.tab_window)
            return
        if not self.config.character_template_path and \
           not self.config.monster_template_paths:
            ret = QMessageBox.question(
                self, "确认",
                "未上传任何模板图片，引擎将无法识别角色/怪物。是否仍要开始？",
                QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                self.tabs.setCurrentWidget(self.tab_template)
                return

        self.engine = BotEngine(
            config=self.config,
            on_log=self.bridge.log.emit,
            on_stats=self.bridge.stats.emit,
            on_state=self.bridge.state.emit,
        )
        if not self.engine.start():
            QMessageBox.warning(self, "错误", "引擎启动失败，请查看日志")
            return
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("⏸ 暂停")
        self.btn_stop.setEnabled(True)
        self.tabs.setCurrentWidget(self.tab_status)

    def on_pause(self):
        if not self.engine:
            return
        if self.engine.is_running and self.engine._pause_event.is_set():
            self.engine.pause()
            self.btn_pause.setText("▶ 继续")
        else:
            self.engine.resume()
            self.btn_pause.setText("⏸ 暂停")

    def on_stop(self):
        if self.engine:
            self.engine.stop()
            self.engine = None
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("⏸ 暂停")
        self.btn_stop.setEnabled(False)

    def _on_engine_state(self, state: str):
        self.tab_status.lbl_state.setText(STATE_LABELS.get(state, "未知"))

    # ------------------------------------------------------------------ 配置
    def on_save_config(self):
        self._sync_ui_to_config()
        path, _ = QFileDialog.getSaveFileName(
            self, "保存配置", CONFIG_FILE, "JSON (*.json)")
        if not path:
            return
        try:
            self.config.save(path)
            QMessageBox.information(self, "成功", f"配置已保存到:\n{path}")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败:\n{e}")

    def on_load_config(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "加载配置", "", "JSON (*.json)")
        if not path:
            return
        try:
            self.config = BotConfig.load(path)
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载失败:\n{e}")
            return
        self._sync_config_to_ui()
        QMessageBox.information(self, "成功", f"配置已加载:\n{path}")

    # ------------------------------------------------------------------ 关闭
    def closeEvent(self, event):
        if self.engine and self.engine.is_running:
            ret = QMessageBox.question(
                self, "确认", "引擎正在运行，是否停止并退出？",
                QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            self.engine.stop()
        # 关闭时自动保存默认配置
        try:
            self._sync_ui_to_config()
            self.config.save(CONFIG_FILE)
        except Exception:
            pass
        event.accept()

    # ------------------------------------------------------------------ 关于
    def on_about(self):
        QMessageBox.about(
            self, "关于",
            "<h3>冒险岛怀旧服自动挂机工具</h3>"
            "<p>基于 Python + PyQt5 + OpenCV 实现的自动化辅助工具。</p>"
            "<p><b>⚠️ 仅供学习和技术研究使用</b>，"
            "使用自动化工具可能违反游戏服务条款，"
            "可能导致账号被封禁。</p>"
            "<p>开发者不对使用本工具造成的任何后果承担责任。</p>"
        )
