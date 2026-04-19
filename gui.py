"""
gui.py — Tkinter 介面、動畫、音效
"""

import tkinter as tk
from tkinter import messagebox
import tkinter.font as tkfont
import subprocess, os, math, random
import json, urllib.request, urllib.parse, threading

from board import Board, BLACK, WHITE, EMPTY, opponent
from ai import GoAI
from gnugo_ai import GnuGoAI, is_available as gnugo_available

# GnuGo level 對應（30kyu→10kyu，共 21 個難度全用 GnuGo）
_GNUGO_LEVEL = {
    30: 1,  29: 1,
    28: 2,  27: 2,
    26: 3,  25: 3,
    24: 4,  23: 4,
    22: 5,  21: 5,
    20: 6,  19: 6,
    18: 7,  17: 7,
    16: 8,  15: 8,
    14: 9,  13: 9,
    12: 10, 11: 10, 10: 10,
}

# ── 音效工具 ───────────────────────────────────────────────────────────────────

# macOS 系統內建音效（備援，不需安裝）
_SYS_SOUNDS = {
    'stone':   '/System/Library/Sounds/Tink.aiff',
    'capture': '/System/Library/Sounds/Pop.aiff',
    'win':     '/System/Library/Sounds/Hero.aiff',
}

def play_sound(name):
    """
    播放音效：
    1. 先找 sounds/<name>.wav（自備音效）
    2. 再找 macOS 內建 aiff
    3. 找不到就靜默略過
    """
    candidates = [
        os.path.join('sounds', f'{name}.wav'),
        os.path.join('sounds', f'{name}.aiff'),
        _SYS_SOUNDS.get(name, ''),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                subprocess.Popen(
                    ['afplay', path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
            return

# ── 主題配色 ───────────────────────────────────────────────────────────────────

THEMES = {
    '木紋': {
        'board_bg':   '#DEB887',   # 棋盤格線背景（淺木色）
        'outer_bg':   '#C8A06E',   # 外框背景（深木色）
        'line':       '#7A4F2D',   # 格線顏色
        'panel_bg':   '#F5E6C8',   # 側邊欄背景
        'text':       '#3B2507',   # 一般文字
        'btn_bg':     '#C8975A',   # 按鈕背景
        'btn_active': '#A0703A',   # 按鈕點擊
        'hint':       '#32CD32',   # 提示圓圈（綠色）
        'badge_bg':   '#FFD700',   # 徽章背景
        'badge_text': '#3B2507',
    },
    '星空': {
        'board_bg':   '#1C1C3A',
        'outer_bg':   '#0D0D25',
        'line':       '#6666BB',
        'panel_bg':   '#2A2A50',
        'text':       '#DDDDF0',
        'btn_bg':     '#44448A',
        'btn_active': '#6666AA',
        'hint':       '#00FF99',
        'badge_bg':   '#FFD700',
        'badge_text': '#1C1C3A',
    },
}


class GameGUI:
    """圍棋遊戲主視窗"""

    def __init__(self, root, board_size=19, difficulty=22, theme='木紋'):
        self.root = root
        self.root.title('圍棋小學堂 🎓')
        self.board_size = board_size
        self.difficulty = difficulty
        self.theme = THEMES[theme]
        self.theme_name = theme

        # 棋盤格距（根據螢幕大小自動調整）
        screen_h = root.winfo_screenheight()
        if board_size == 13:
            self.cs = max(40, min(64, screen_h * 82 // 100 // 14))
        else:
            self.cs = max(32, min(52, screen_h * 82 // 100 // 20))
        self.mg = self.cs
        self._fullscreen = False

        # 畫布尺寸
        self.cv_size = (board_size - 1) * self.cs + 2 * self.mg

        # 遊戲物件
        self.board = Board(board_size)
        # 高難度使用 GnuGo 引擎；若未安裝或啟動失敗則降回規則 AI
        if difficulty in _GNUGO_LEVEL and gnugo_available():
            self.ai = GnuGoAI(level=_GNUGO_LEVEL[difficulty], board_size=board_size)
            self._using_gnugo = self.ai.ready
        else:
            self.ai = GoAI(difficulty, board_size)
            self._using_gnugo = False
        self._gnugo_fail_count = 0   # 連續失敗次數，超過閾值時降級

        # 遊戲狀態
        self.current_player = BLACK   # 黑先
        self.game_over = False
        self.pass_count = 0
        self.hint_pos = None          # 提示格
        self.hover_pos = None         # 滑鼠懸停格

        # 成就追蹤
        self._badge_first_capture = False
        self._badge_first_win = False
        self._excellent_streak = 0
        self._genius_shown = False

        # 判定勝負地圖
        self._territory = {}

        # 學習統計（每盤重置）
        self._stats = {
            'moves': 0,        # 黑方總手數
            'great': 0,        # 棒手數（吃子/威脅/要點）
            'captures': 0,     # 黑方累計吃子數
            'lost': 0,         # 黑方累計被吃數
            'hints': 0,        # 使用提示次數
            'undos': 0,        # 悔棋次數
            'difficulty': difficulty,
            'board_size': board_size,
        }

        # 建立 UI
        self._build_ui()
        self._redraw()

        # 視窗關閉時釋放 GnuGo 程序
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        # 首次啟動顯示教學
        if not os.path.exists('.tutorial_done'):
            self.root.after(400, self.show_tutorial)

    # ── UI 建構 ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        t = self.theme
        self.root.configure(bg=t['outer_bg'])

        f_title = tkfont.Font(family='Helvetica', size=15, weight='bold')
        f_label = tkfont.Font(family='Helvetica', size=12)
        f_small = tkfont.Font(family='Helvetica', size=10)

        # ── 右側資訊欄（先 pack，才能確實靠右）───────────────────────────────
        panel = tk.Frame(self.root, bg=t['panel_bg'], bd=2, relief='ridge')
        panel.pack(side='right', fill='y', padx=(0, 12), pady=12)

        tk.Label(panel, text='⚫ 圍棋小學堂',
                 font=f_title, bg=t['panel_bg'], fg=t['text']).pack(pady=(12, 4))

        engine_label = ('🤖 GnuGo 引擎' if self._using_gnugo
                        else f'規則 AI  {self.difficulty} 級')
        tk.Label(panel, text=engine_label,
                 font=f_small, bg=t['panel_bg'], fg='#006600' if self._using_gnugo else t['text']
                 ).pack(pady=(0, 4))

        # 輪到誰
        self.lbl_turn = tk.Label(panel, text='輪到：⚫ 黑方（你）',
                                  font=f_label, bg=t['panel_bg'], fg=t['text'])
        self.lbl_turn.pack(pady=4)

        # 提子計數
        self.lbl_cap = tk.Label(panel,
                                 text='黑方吃子：0 顆\n白方吃子：0 顆',
                                 font=f_small, bg=t['panel_bg'], fg=t['text'],
                                 justify='left')
        self.lbl_cap.pack(pady=4)

        # 狀態訊息
        self.lbl_status = tk.Label(panel, text='',
                                    font=f_small, bg=t['panel_bg'], fg='#009900',
                                    wraplength=190, justify='left')
        self.lbl_status.pack(pady=4)

        # 剩餘悔棋次數
        self.lbl_undo = tk.Label(panel,
                                  text=f'剩餘悔棋：{Board.MAX_UNDO} 次',
                                  font=f_small, bg=t['panel_bg'], fg=t['text'])
        self.lbl_undo.pack(pady=2)

        # 按鈕區
        btn_kw = dict(font=f_label, bg=t['btn_bg'], fg=t['text'],
                      activebackground=t['btn_active'],
                      relief='raised', bd=2, width=8)

        btns = tk.Frame(panel, bg=t['panel_bg'])
        btns.pack(pady=10)

        self.btn_undo = tk.Button(btns, text='↩ 悔棋',
                                   command=self._on_undo, **btn_kw)
        self.btn_undo.pack(pady=3)

        self.btn_hint = tk.Button(btns, text='💡 提示',
                                   command=self._on_hint, **btn_kw)
        self.btn_hint.pack(pady=3)

        self.btn_pass = tk.Button(btns, text='Pass',
                                   command=self._on_pass, **btn_kw)
        self.btn_pass.pack(pady=3)

        self.btn_resign = tk.Button(btns, text='🏳 投降',
                                     command=self._on_resign, **btn_kw)
        self.btn_resign.pack(pady=3)

        self.btn_judge = tk.Button(btns, text='🏁 判定',
                                    command=self._on_judge, **btn_kw)
        self.btn_judge.pack(pady=3)

        tk.Button(btns, text='📖 教學',
                  command=self.show_tutorial, **btn_kw).pack(pady=3)

        self.btn_fs = tk.Button(btns, text='⛶ 全螢幕',
                                command=self._toggle_fullscreen, **btn_kw)
        self.btn_fs.pack(pady=3)

        # 徽章顯示區
        self.badge_cv = tk.Canvas(panel, width=200, height=70,
                                   bg=t['panel_bg'], highlightthickness=0)
        self.badge_cv.pack(pady=6)

        # ── 左側棋盤框（填滿剩餘空間，棋盤置中）──────────────────────────────
        self._left = tk.Frame(self.root, bg=t['outer_bg'])
        self._left.pack(side='left', fill='both', expand=True)

        self.canvas = tk.Canvas(
            self._left,
            width=self.cv_size, height=self.cv_size,
            bg=t['board_bg'],
            highlightthickness=3,
            highlightbackground=t['line'],
        )
        self.canvas.pack(expand=True)
        self.canvas.bind('<Motion>', self._on_hover)
        self.canvas.bind('<Button-1>', self._on_click)
        self.canvas.bind('<Leave>', self._on_leave)

    # ── 座標轉換 ───────────────────────────────────────────────────────────────

    def _b2c(self, row, col):
        """棋盤 → 畫布座標"""
        return self.mg + col * self.cs, self.mg + row * self.cs

    def _c2b(self, x, y):
        """畫布 → 最近棋盤交叉點"""
        col = round((x - self.mg) / self.cs)
        row = round((y - self.mg) / self.cs)
        col = max(0, min(self.board_size - 1, col))
        row = max(0, min(self.board_size - 1, row))
        return row, col

    # ── 繪圖 ───────────────────────────────────────────────────────────────────

    def _redraw(self):
        """全量重繪棋盤"""
        self.canvas.delete('all')
        t = self.theme
        s = self.board_size
        cs = self.cs
        mg = self.mg

        # 座標標籤（欄：A-T 跳過 I；列：1=底部, N=頂部）
        _COLS = 'ABCDEFGHJKLMNOPQRST'
        lbl_font = ('Helvetica', max(8, cs // 5))
        lbl_col  = t['line']
        half     = mg // 2
        for i in range(s):
            cx = mg + i * cs                    # 欄 X 座標
            cy = mg + i * cs                    # 列 Y 座標
            rn = str(s - i)                     # 列號（頂部=N，底部=1）
            lt = _COLS[i]                       # 欄字母
            # 欄字母：上方 + 下方
            self.canvas.create_text(cx, half,
                text=lt, fill=lbl_col, font=lbl_font, anchor='center')
            self.canvas.create_text(cx, mg + (s-1)*cs + half,
                text=lt, fill=lbl_col, font=lbl_font, anchor='center')
            # 列號：左方 + 右方
            self.canvas.create_text(half, cy,
                text=rn, fill=lbl_col, font=lbl_font, anchor='center')
            self.canvas.create_text(mg + (s-1)*cs + half, cy,
                text=rn, fill=lbl_col, font=lbl_font, anchor='center')

        # 格線
        for i in range(s):
            x = mg + i * cs
            y = mg + i * cs
            self.canvas.create_line(x, mg, x, mg + (s-1)*cs,
                                    fill=t['line'], width=1)
            self.canvas.create_line(mg, y, mg + (s-1)*cs, y,
                                    fill=t['line'], width=1)

        # 外框加粗
        self.canvas.create_rectangle(
            mg, mg, mg + (s-1)*cs, mg + (s-1)*cs,
            outline=t['line'], width=2,
        )

        # 星位（Hoshi）
        hoshi_r = 4
        stars = (
            [3, 9, 15] if s == 19 else
            [3, 6, 9]  if s == 13 else []
        )
        for sr in stars:
            for sc in stars:
                hx, hy = self._b2c(sr, sc)
                self.canvas.create_oval(
                    hx - hoshi_r, hy - hoshi_r,
                    hx + hoshi_r, hy + hoshi_r,
                    fill=t['line'], outline=t['line'],
                )

        # 棋子
        stone_r = int(cs * 0.45)
        for r in range(s):
            for c in range(s):
                color = self.board.grid[r][c]
                if color != EMPTY:
                    self._draw_stone(r, c, color, stone_r)

        # 提示格（淡綠圓圈）
        if self.hint_pos:
            hr, hc = self.hint_pos
            hx, hy = self._b2c(hr, hc)
            self.canvas.create_oval(
                hx - stone_r, hy - stone_r,
                hx + stone_r, hy + stone_r,
                outline=t['hint'], fill='', width=3,
            )

        # 懸停預覽 + 氣數
        if self.hover_pos and not self.game_over:
            hr, hc = self.hover_pos
            if self.board.grid[hr][hc] == EMPTY:
                hx, hy = self._b2c(hr, hc)
                # 預覽圓（半尺寸，用外框代替填色，相容 Tk 9.0）
                preview = '#404040' if self.current_player == BLACK else '#C0C0C0'
                sr2 = stone_r // 2
                self.canvas.create_oval(
                    hx - sr2, hy - sr2, hx + sr2, hy + sr2,
                    fill='', outline=preview, width=2,
                )
                # 試算落子後的氣數
                self.board.grid[hr][hc] = self.current_player
                _, libs = self.board.find_group(hr, hc)
                self.board.grid[hr][hc] = EMPTY
                lib_n = len(libs)
                # 在交叉點上方顯示氣數
                self.canvas.create_text(
                    hx, hy - stone_r - 3,
                    text=f'氣:{lib_n}',
                    fill=t['text'],
                    font=('Helvetica', 9),
                )

        # 地盤著色（判定模式）
        if self._territory:
            sq = max(3, cs // 6)
            for (r, c), owner in self._territory.items():
                if self.board.grid[r][c] == EMPTY:
                    tx, ty = self._b2c(r, c)
                    if owner == BLACK:
                        self.canvas.create_rectangle(
                            tx - sq, ty - sq, tx + sq, ty + sq,
                            fill='#1A1A1A', outline='',
                        )
                    elif owner == WHITE:
                        self.canvas.create_rectangle(
                            tx - sq, ty - sq, tx + sq, ty + sq,
                            fill='#E8E8E8', outline='',
                        )

    def _draw_stone(self, row, col, color, radius):
        """繪製單顆棋子"""
        x, y = self._b2c(row, col)
        if color == BLACK:
            self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill='black', outline='black', width=1,
            )
            # 白色高光（提升立體感）
            hr = max(2, int(radius * 0.35))
            self.canvas.create_oval(
                x - int(radius * 0.5), y - int(radius * 0.55),
                x - int(radius * 0.5) + hr, y - int(radius * 0.55) + hr,
                fill='#666666', outline='',
            )
        else:
            self.canvas.create_oval(
                x - radius, y - radius, x + radius, y + radius,
                fill='#F8F8F8', outline='#888888', width=1,
            )
            # 灰色高光
            hr = max(2, int(radius * 0.35))
            self.canvas.create_oval(
                x - int(radius * 0.5), y - int(radius * 0.55),
                x - int(radius * 0.5) + hr, y - int(radius * 0.55) + hr,
                fill='#FFFFFF', outline='',
            )

    # ── 事件處理 ───────────────────────────────────────────────────────────────

    def _toggle_fullscreen(self):
        """切換全螢幕：棋盤依可用空間最大化，選單貼右邊"""
        self._fullscreen = not self._fullscreen
        self.root.attributes('-fullscreen', self._fullscreen)
        self.btn_fs.config(text='✕ 離開全螢幕' if self._fullscreen else '⛶ 全螢幕')
        self.root.update_idletasks()
        screen_h = self.root.winfo_screenheight()
        screen_w = self.root.winfo_screenwidth()
        panel_w = 230   # 右側欄估算寬度（含 padding）
        if self._fullscreen:
            avail_h = int(screen_h * 0.94)
            avail_w = screen_w - panel_w - 48
        else:
            avail_h = int(screen_h * 0.82)
            avail_w = int(screen_w * 0.72)
        # cv_size = (board_size + 1) * cs，解出 cs
        divisor = self.board_size + 1
        cs_from_h = avail_h // divisor
        cs_from_w = avail_w // divisor
        new_cs = min(cs_from_h, cs_from_w)
        if self.board_size == 13:
            new_cs = max(40, min(90, new_cs))
        else:
            new_cs = max(32, min(72, new_cs))
        self.cs = new_cs
        self.mg = new_cs
        self.cv_size = (self.board_size - 1) * self.cs + 2 * self.mg
        self.canvas.config(width=self.cv_size, height=self.cv_size)
        self._redraw()

    def _on_hover(self, event):
        if self.game_over or self.current_player != BLACK:
            return
        row, col = self._c2b(event.x, event.y)
        if (row, col) != self.hover_pos:
            self.hover_pos = (row, col)
            self._redraw()

    def _on_leave(self, event):
        self.hover_pos = None
        self._redraw()

    def _on_click(self, event):
        if self.game_over or self.current_player != BLACK:
            return
        # 只接受棋盤範圍內的點擊
        if not (self.mg <= event.x <= self.cv_size - self.mg and
                self.mg <= event.y <= self.cv_size - self.mg):
            return
        row, col = self._c2b(event.x, event.y)
        self._do_move(row, col, BLACK)

    def _do_move(self, row, col, color):
        """執行落子（含音效、評價、成就、AI 回應）"""
        success, captured, msg = self.board.place_stone(row, col, color)
        if not success:
            self.lbl_status.config(text=f'❌ {msg}')
            return

        self.pass_count = 0
        self.hint_pos = None

        # 音效
        if captured > 0:
            play_sound('capture')
            if not self._badge_first_capture:
                self._badge_first_capture = True
                self._show_badge('🏹 獵人初登場！')
        else:
            play_sound('stone')

        # 玩家手評價 + 統計
        if color == BLACK:
            self._stats['moves'] += 1
            comment = self.ai.evaluate_move(self.board, row, col, color)
            self.lbl_status.config(text=f'💬 {comment}')
            if comment == '這步很棒！':
                self._stats['great'] += 1
                self._excellent_streak += 1
                if self._excellent_streak >= 3 and not self._genius_shown:
                    self._genius_shown = True
                    self._show_badge('🌟 天才棋手！')
            else:
                self._excellent_streak = 0

        self._redraw()
        self._update_info()

        # 通知 GnuGo 引擎玩家的手
        if self._using_gnugo and color == BLACK:
            self.ai.record_opponent(row, col, color)

        # 切換玩家
        self.current_player = opponent(color)
        self._update_turn()

        # AI 回應
        if self.current_player == WHITE and not self.game_over:
            self.root.after(300, self._ai_move)

    def _ai_move(self):
        """AI 落子：GnuGo 使用背景執行緒，避免凍結 UI"""
        if self.game_over:
            return
        if self._using_gnugo:
            self.lbl_status.config(text='🤔 引擎思考中…')
            self.canvas.config(cursor='watch')
            def _think():
                move = self.ai.get_move(self.board, WHITE)
                self.root.after(0, lambda m=move: self._apply_ai_move(m))
            threading.Thread(target=_think, daemon=True).start()
        else:
            move = self.ai.get_move(self.board, WHITE)
            self._apply_ai_move(move)

    def _apply_ai_move(self, move):
        """實際將 AI 的手落到棋盤上（必須在主執行緒呼叫）"""
        self.canvas.config(cursor='')
        if self.game_over:
            return
        if move is None:
            # 若 GnuGo 連續多次回傳 None（引擎故障），自動降級到規則 AI
            if self._using_gnugo:
                self._gnugo_fail_count += 1
                if self._gnugo_fail_count >= 3:
                    self._using_gnugo = False
                    try:
                        self.ai.close()
                    except Exception:
                        pass
                    self.ai = GoAI(self.difficulty, self.board_size)
                    self.lbl_status.config(text='⚠ 引擎失敗，切換規則 AI')
                    move = self.ai.get_move(self.board, WHITE)
                    if move:
                        self._gnugo_fail_count = 0
                        # 走降級後的第一步
                        self.pass_count = 0
                        row, col = move
                        success, captured, _ = self.board.place_stone(row, col, WHITE)
                        if success:
                            play_sound('capture' if captured > 0 else 'stone')
                            self._redraw()
                            self._update_info()
                        self.current_player = BLACK
                        self._update_turn()
                        return
            self.pass_count += 1
            self.lbl_status.config(text='電腦選擇 Pass')
            self.current_player = BLACK
            self._update_turn()
            if self.pass_count >= 2:
                self._end_game()
            return
        self._gnugo_fail_count = 0

        self.pass_count = 0
        row, col = move
        success, captured, _ = self.board.place_stone(row, col, WHITE)
        if success:
            play_sound('capture' if captured > 0 else 'stone')
            self._redraw()
            self._update_info()

        self.current_player = BLACK
        self._update_turn()

    # ── 按鈕動作 ───────────────────────────────────────────────────────────────

    def _on_undo(self):
        if self.game_over:
            return
        success, msg = self.board.undo()
        if success:
            self._stats['undos'] += 1
            self.current_player = BLACK
            self.hint_pos = None
            # 同步 GnuGo 狀態（重啟引擎並重播）
            if self._using_gnugo:
                steps = min(2, len(self.ai._seq))
                self.ai.undo(steps)
            self.lbl_status.config(text=f'↩ {msg}')
            self.lbl_undo.config(
                text=f'剩餘悔棋：{Board.MAX_UNDO - self.board.undo_count} 次'
            )
            self._redraw()
            self._update_info()
            self._update_turn()
        else:
            self.lbl_status.config(text=f'❌ {msg}')

    def _on_hint(self):
        if self.game_over:
            return
        self._stats['hints'] += 1
        hint_ai = GoAI(8, self.board_size)
        move = hint_ai.get_move(self.board, BLACK)
        if move:
            self.hint_pos = move
            self.lbl_status.config(
                text=f'💡 建議落在第 {move[0]+1} 行第 {move[1]+1} 列'
            )
        else:
            self.lbl_status.config(text='💡 建議 Pass')
        self._redraw()

    def _on_pass(self):
        if self.game_over:
            return
        self.pass_count += 1
        self.lbl_status.config(text='你選擇 Pass')
        self.current_player = WHITE
        self._update_turn()
        if self.pass_count >= 2:
            self._end_game()
        else:
            self.root.after(600, self._ai_move)

    def _on_close(self):
        """視窗關閉：釋放 GnuGo 程序再銷毀視窗"""
        if self._using_gnugo:
            try:
                self.ai.close()
            except Exception:
                pass
        self.root.destroy()

    def _on_resign(self):
        if self.game_over:
            return
        if messagebox.askyesno('確認投降', '確定要投降嗎？\n電腦這次算贏！'):
            self.game_over = True
            self.lbl_status.config(text='你選擇投降，繼續加油！')
            self._disable_game_buttons()

    def _on_judge(self):
        """手動判定勝負：填入地盤並即時計算結果"""
        if self.game_over:
            return
        if not messagebox.askyesno('判定勝負',
                                    '確定現在判定勝負？\n\n'
                                    '提示：請先把已死的棋子提走，\n'
                                    '再按判定，結果才準確。'):
            return
        self._end_game()

    # ── 結算 ───────────────────────────────────────────────────────────────────

    def _end_game(self):
        """計分、填入地盤並顯示結果，結束後傳 Telegram 學習報告"""
        self.game_over = True
        self._disable_game_buttons()

        # 快照最終吃子數
        self._stats['captures'] = self.board.captured_white
        self._stats['lost']     = self.board.captured_black

        black_sc, white_sc, territory = self.board.calculate_score()
        self._territory = territory
        self._redraw()

        if black_sc > white_sc:
            play_sound('win')
            if not self._badge_first_win:
                self._badge_first_win = True
                self._show_badge('🏆 圍棋英雄！')
            self._play_win_animation()
            result = (f'🎉 黑方勝！\n'
                      f'黑方 {black_sc:.1f} 目  vs  白方 {white_sc:.1f} 目')
        else:
            result = (f'白方勝！\n'
                      f'黑方 {black_sc:.1f} 目  vs  白方 {white_sc:.1f} 目')

        self.lbl_status.config(text=result)
        self._show_result_dialog(result, black_sc, white_sc)

        # 傳 Telegram 學習報告（背景執行，不卡 UI）
        report = self._generate_report(black_sc, white_sc)
        self._send_telegram(report)

    def _generate_report(self, black_sc, white_sc):
        """產生針對小孩圍棋學習的評估報告（繁體中文）"""
        s = self._stats
        total   = s['moves']
        great   = s['great']
        cap     = s['captures']
        lost    = s['lost']
        hints   = s['hints']
        undos   = s['undos']
        diff    = s['difficulty']
        bsize   = s['board_size']
        won     = black_sc > white_sc
        margin  = abs(black_sc - white_sc)

        diff_name = {
            25: '25級入門', 20: '20級初學', 15: '15級進階',
            10: '10級實戰', 8: '8級強手', 5: '5級高手',
        }.get(diff, f'{diff}級')
        result_str = f'⚫黑方勝 ({black_sc:.1f} vs {white_sc:.1f})' if won else f'⚪白方勝 ({white_sc:.1f} vs {black_sc:.1f})'
        great_pct  = round(great / total * 100) if total else 0

        # ── 棋力估算 ──────────────────────────────────────────────────────────
        rank_pts = 0
        if won:
            rank_pts += {5: 18, 8: 15, 10: 12, 15: 8, 20: 4, 25: 1}.get(diff, 0)
        elif margin < 5:
            rank_pts += {5: 12, 8: 10, 10: 7, 15: 4, 20: 2, 25: 0}.get(diff, 0)
        rank_pts += min(8, great_pct // 6)      # 棒手率加分（最多 +8）
        rank_pts -= min(4, undos)               # 悔棋扣分
        rank_pts -= min(3, hints)               # 提示扣分
        if cap > lost:
            rank_pts += 2                       # 攻擊意識加分

        if rank_pts >= 20:
            rank_est = '約 5～8 kyu（中級初段潛力）'
        elif rank_pts >= 14:
            rank_est = '約 10 kyu（實戰級）'
        elif rank_pts >= 9:
            rank_est = '約 12～15 kyu（進階級）'
        elif rank_pts >= 4:
            rank_est = '約 18～20 kyu（初學級）'
        else:
            rank_est = '約 22～25 kyu（入門級）'

        lines = [
            '📊 圍棋學習評估報告',
            f'棋盤：{bsize}×{bsize}  難度：{diff_name}',
            f'🎯 棋力估算：{rank_est}',
            f'結果：{result_str}  差距：{margin:.1f} 目',
            f'總手數：{total}  棒手：{great}（{great_pct}%）',
            f'吃子：{cap} 顆  被吃：{lost} 顆  提示：{hints} 次  悔棋：{undos} 次',
            '',
            '【預測能力】',
        ]

        # ── 預測分析 ──────────────────────────────────────────────────────────
        if total < 10:
            lines.append('⚠️ 對局太短，預測能力難以評估。')
        elif great_pct >= 45:
            lines.append('🌟 預測能力出色！能主動看到威脅和機會，有明顯的預讀習慣。')
        elif great_pct >= 30:
            lines.append('✅ 預測能力不錯，能察覺部分威脅，偶爾可以看兩步棋。')
        elif great_pct >= 15:
            lines.append('👀 有初步預測意識，但常錯過已在打吃的棋串，需多練習「看一步再落子」。')
        else:
            lines.append('⚠️ 預測能力待培養，落子較隨意，建議每步前先問「這裡安全嗎？有子可吃嗎？」')

        # 攻擊意識
        if cap > 0 and cap >= lost:
            lines.append(f'✅ 攻擊意識良好，吃了 {cap} 顆，比被吃（{lost}顆）多或相當，能掌握局面主動權。')
        elif cap > 0:
            lines.append(f'⚠️ 有吃子意識（吃 {cap} 顆），但被吃（{lost}顆）更多，需注意自己棋子的安全。')
        else:
            lines.append('⚠️ 全局無吃子。可能還不熟悉「打吃→提子」的連貫動作，這是圍棋最基礎的預測練習。')

        # ── 思考分析 ──────────────────────────────────────────────────────────
        lines += ['', '【思考能力】']

        # 獨立思考
        if hints == 0:
            lines.append('✅ 全程獨立思考，未依賴提示，判斷力值得肯定。')
        elif hints <= 2:
            lines.append(f'👍 只用 {hints} 次提示，基本上能自行判斷局面。')
        else:
            lines.append(f'📌 使用了 {hints} 次提示，遇到困難時還需外部引導，建議練習「先想再按提示確認」。')

        # 計劃性（悔棋）
        if undos == 0:
            lines.append('✅ 未使用悔棋，落子前有思考，行棋有計劃感。')
        elif undos <= 3:
            lines.append(f'📝 悔棋 {undos} 次，學習中屬正常，目標是逐步減少。')
        else:
            lines.append(f'⚠️ 悔棋 {undos} 次偏多，可能先落子後悔，建議養成「想清楚再下」的習慣。')

        # 勝負與難度判讀
        if won and diff <= 5:
            lines.append(f'🏆 贏了最高難度 5 級 AI！具備2步以上預讀和地盤意識，實力已達中級！')
        elif won and diff <= 8:
            lines.append(f'🎖️ 贏了 8 級強手 AI！地盤意識和攻防俱佳，可挑戰 5 級高手了。')
        elif won and diff <= 10:
            lines.append(f'🏆 能贏過實戰級 AI，展現了完整的預讀和戰略能力，可嘗試 8 級強手！')
        elif won and diff <= 15:
            lines.append(f'🎯 贏了進階 AI！預讀和攻防能力具備基礎，建議下一步挑戰實戰級（10級）。')
        elif won and diff <= 20:
            lines.append(f'👍 贏了初學 AI，可以升一級（進階 15 級）來測試更深的預讀能力。')
        elif won:
            lines.append(f'🌱 贏了入門 AI，建議挑戰初學 20 級，看看面對「會防守」的對手是否還能取勝。')
        else:
            if margin < 10:
                lines.append(f'💪 輸了但差距只有 {margin:.0f} 目，勢均力敵！同樣難度再戰幾局，觀察進步趨勢。')
            else:
                lines.append(f'💪 繼續練習！核心重點：①看到打吃要立刻吃子；②自己被打吃要先逃。')

        # ── 綜合建議 ──────────────────────────────────────────────────────────
        lines += ['', '【教學建議】']
        if diff >= 20 and not won:
            lines.append('📌 先讓孩子多練「吃子練習棋」（目標：吃越多子越好），建立打吃→提子的條件反射。')
        elif great_pct < 20:
            lines.append('📌 每落子前提醒：①有子可吃嗎？②我的子安全嗎？③這裡重要嗎？三問習慣化後棒手率會明顯提升。')
        elif hints >= 3:
            lines.append('📌 減少使用提示，改為對弈後一起復盤，讓孩子指出「我當時在想什麼」，訓練自我思考意識。')
        else:
            lines.append('📌 表現良好，可加入「死活題」練習，進一步訓練預讀深度（看 3 步以上）。')

        return '\n'.join(lines)

    def _send_telegram(self, message):
        """以背景執行緒傳送 Telegram 訊息，不阻塞 UI"""
        def _worker():
            try:
                cfg_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), 'telegram.json'
                )
                if not os.path.exists(cfg_path):
                    return
                with open(cfg_path, encoding='utf-8') as f:
                    cfg = json.load(f)
                token   = cfg.get('token', '').strip()
                chat_id = cfg.get('chat_id', '').strip()
                if not token or not chat_id:
                    return
                # Telegram 單則上限 4096 字元
                text = message[:4000] + ('\n…（已截斷）' if len(message) > 4000 else '')
                url  = f'https://api.telegram.org/bot{token}/sendMessage'
                data = urllib.parse.urlencode({'chat_id': chat_id, 'text': text}).encode('utf-8')
                req  = urllib.request.Request(url, data=data)
                urllib.request.urlopen(req, timeout=10)
            except Exception:
                pass   # 網路不通或設定錯誤時靜默，不影響遊戲
        threading.Thread(target=_worker, daemon=True).start()

    def _show_result_dialog(self, result_text, black_sc, white_sc):
        t = self.theme
        dlg = tk.Toplevel(self.root)
        dlg.title('遊戲結束')
        dlg.configure(bg=t['outer_bg'])
        dlg.resizable(False, False)

        tk.Label(dlg, text=result_text,
                 font=('Helvetica', 14, 'bold'),
                 bg=t['outer_bg'], fg=t['text'],
                 justify='center', pady=10).pack(padx=20, pady=10)

        tk.Button(dlg, text='覆盤',
                  command=lambda: [dlg.destroy(), self._start_review()],
                  bg=t['btn_bg'], fg=t['text'],
                  font=('Helvetica', 12), width=8).pack(pady=4)
        tk.Button(dlg, text='關閉', command=dlg.destroy,
                  bg=t['btn_bg'], fg=t['text'],
                  font=('Helvetica', 12), width=8).pack(pady=4)

    # ── 勝利動畫 ───────────────────────────────────────────────────────────────

    def _play_win_animation(self):
        """多層彩色圓圈向外擴散動畫"""
        cx = cy = self.cv_size // 2
        colors = ['#FF4444', '#FF8800', '#FFDD00',
                  '#44DD44', '#44AAFF', '#AA44FF']
        max_r = cx - 10
        items = []

        def animate(step):
            for item in items:
                self.canvas.delete(item)
            items.clear()

            if step > 55:
                item = self.canvas.create_text(
                    cx, cy,
                    text='你贏了！好厲害！',
                    font=('Helvetica', 22, 'bold'),
                    fill='#FFD700',
                )
                items.append(item)
                return

            for i, color in enumerate(colors):
                r = (step * 9 + i * 28) % max_r
                if r > 5:
                    item = self.canvas.create_oval(
                        cx - r, cy - r, cx + r, cy + r,
                        outline=color, fill='', width=3,
                    )
                    items.append(item)

            self.root.after(45, lambda: animate(step + 1))

        animate(0)

    # ── 覆盤 ───────────────────────────────────────────────────────────────────

    def _start_review(self):
        """開啟覆盤模式"""
        self.review_moves = list(self.board.move_record)
        self.review_board = Board(self.board_size)
        self.review_step = 0
        self._draw_review()

        t = self.theme
        dlg = tk.Toplevel(self.root)
        dlg.title('覆盤')
        dlg.configure(bg=t['outer_bg'])

        self.lbl_review = tk.Label(
            dlg,
            text=f'第 0 手 / 共 {len(self.review_moves)} 手',
            font=('Helvetica', 12),
            bg=t['outer_bg'], fg=t['text'],
        )
        self.lbl_review.pack(pady=8)

        bf = tk.Frame(dlg, bg=t['outer_bg'])
        bf.pack()

        tk.Button(bf, text='◀ 上一手',
                  command=self._review_prev,
                  bg=t['btn_bg'], fg=t['text'],
                  font=('Helvetica', 11)).pack(side='left', padx=8, pady=4)
        tk.Button(bf, text='下一手 ▶',
                  command=self._review_next,
                  bg=t['btn_bg'], fg=t['text'],
                  font=('Helvetica', 11)).pack(side='left', padx=8, pady=4)

        tk.Button(dlg, text='結束覆盤',
                  command=lambda: [dlg.destroy(), self._end_review()],
                  bg=t['btn_bg'], fg=t['text'],
                  font=('Helvetica', 11)).pack(pady=8)

    def _review_next(self):
        if self.review_step < len(self.review_moves):
            r, c, color = self.review_moves[self.review_step]
            self.review_board.place_stone(r, c, color)
            self.review_step += 1
            self._draw_review()

    def _review_prev(self):
        if self.review_step > 0:
            self.review_step -= 1
            self.review_board = Board(self.board_size)
            for i in range(self.review_step):
                r, c, color = self.review_moves[i]
                self.review_board.place_stone(r, c, color)
            self._draw_review()

    def _draw_review(self):
        """把覆盤棋盤繪製到主畫布"""
        orig = self.board
        self.board = self.review_board
        self._redraw()
        self.board = orig

        # 黃框高亮當前手
        if self.review_step > 0:
            r, c, _ = self.review_moves[self.review_step - 1]
            x, y = self._b2c(r, c)
            sr = int(self.cs * 0.45)
            self.canvas.create_rectangle(
                x - sr, y - sr, x + sr, y + sr,
                outline='yellow', width=3,
            )

        if hasattr(self, 'lbl_review'):
            self.lbl_review.config(
                text=f'第 {self.review_step} 手 / 共 {len(self.review_moves)} 手'
            )

    def _end_review(self):
        self.review_board = None
        self._redraw()

    # ── 成就徽章 ───────────────────────────────────────────────────────────────

    def _show_badge(self, text):
        """在右側欄顯示成就徽章，3 秒後自動消失"""
        t = self.theme
        self.badge_cv.delete('all')
        self.badge_cv.create_rectangle(4, 4, 196, 66,
                                        fill=t['badge_bg'], outline='#AA8800', width=2)
        self.badge_cv.create_text(100, 35, text=text,
                                   font=('Helvetica', 12, 'bold'),
                                   fill=t['badge_text'])
        self.root.after(3000, lambda: self.badge_cv.delete('all'))

    # ── 輔助更新 ───────────────────────────────────────────────────────────────

    def _update_info(self):
        self.lbl_cap.config(
            text=(f'黑方吃子：{self.board.captured_white} 顆\n'
                  f'白方吃子：{self.board.captured_black} 顆')
        )

    def _update_turn(self):
        if self.current_player == BLACK:
            self.lbl_turn.config(text='輪到：⚫ 黑方（你）')
        else:
            self.lbl_turn.config(text='輪到：⚪ 白方（電腦）')

    def _disable_game_buttons(self):
        for btn in (self.btn_undo, self.btn_hint,
                    self.btn_pass, self.btn_resign, self.btn_judge):
            btn.config(state='disabled')

    # ── 教學 ───────────────────────────────────────────────────────────────────

    def show_tutorial(self):
        """顯示 4 步驟互動教學"""
        t = self.theme
        win = tk.Toplevel(self.root)
        win.title('圍棋教學 📖')
        win.configure(bg=t['outer_bg'])
        win.resizable(False, False)

        STEPS = [
            {
                'title': '第 1 步：什麼是「氣」？',
                'text': (
                    '每顆棋子周圍的空格叫做「氣」。\n'
                    '棋盤中央的棋子有 4 口氣，靠邊的少一些。\n'
                    '氣越多越安全！'
                ),
            },
            {
                'title': '第 2 步：怎麼「提子」？',
                'text': (
                    '把對方棋子的所有氣都佔滿，\n'
                    '那顆（或那串）棋子就被你提走囉！\n'
                    '被提走的棋子從棋盤上消失。'
                ),
            },
            {
                'title': '第 3 步：什麼是「劫」？',
                'text': (
                    '如果雙方輪流提同一顆棋子，\n'
                    '棋盤會不斷重複，這叫「劫」。\n'
                    '遊戲會阻止你馬上回提，\n'
                    '你必須先在別處落子。'
                ),
            },
            {
                'title': '第 4 步：怎麼算勝負？',
                'text': (
                    '遊戲結束後，比較：\n'
                    '你的棋子數 + 你圍住的空格數\n'
                    '誰的總數多誰就贏！\n'
                    '（電腦會自動計算）'
                ),
            },
        ]

        step_idx = [0]

        # 示範小畫布（5×5）
        DEMO_CS = 50
        DEMO_MG = 40
        demo_cv = tk.Canvas(win, width=5 * DEMO_CS,
                             height=5 * DEMO_CS,
                             bg=t['board_bg'],
                             highlightthickness=1,
                             highlightbackground=t['line'])
        demo_cv.pack(padx=20, pady=10)

        lbl_title = tk.Label(win, text='',
                              font=('Helvetica', 14, 'bold'),
                              bg=t['outer_bg'], fg=t['text'])
        lbl_title.pack()

        lbl_text = tk.Label(win, text='',
                             font=('Helvetica', 11),
                             bg=t['outer_bg'], fg=t['text'],
                             justify='left', wraplength=280)
        lbl_text.pack(padx=20, pady=6)

        # 示範繪圖
        def draw_demo(idx):
            demo_cv.delete('all')
            # 格線（5×5）
            for i in range(5):
                x = DEMO_MG + i * DEMO_CS // 2
                # 用更簡單的繪法：直接以 DEMO_CS=50 為格距
            # 格線
            for i in range(5):
                xv = DEMO_MG // 2 + i * (DEMO_CS - 10)
                yv = DEMO_MG // 2 + i * (DEMO_CS - 10)
                grid_size = 4 * (DEMO_CS - 10)
                demo_cv.create_line(xv, DEMO_MG//2, xv, DEMO_MG//2 + grid_size,
                                     fill=t['line'])
                demo_cv.create_line(DEMO_MG//2, yv, DEMO_MG//2 + grid_size, yv,
                                     fill=t['line'])

            sr = 18  # 示範棋子半徑

            def stone(r, c, color):
                x = DEMO_MG // 2 + c * (DEMO_CS - 10)
                y = DEMO_MG // 2 + r * (DEMO_CS - 10)
                fill = '#1A1A1A' if color == BLACK else '#F8F8F8'
                out = '#000' if color == BLACK else '#888'
                demo_cv.create_oval(x-sr, y-sr, x+sr, y+sr,
                                     fill=fill, outline=out)

            if idx == 0:
                # 示範氣：中央黑子
                stone(2, 2, BLACK)
                for dr, dc, lbl in [(-1,0,'↑氣'),(1,0,'↓氣'),(0,-1,'←氣'),(0,1,'→氣')]:
                    x = DEMO_MG//2 + (2+dc)*(DEMO_CS-10)
                    y = DEMO_MG//2 + (2+dr)*(DEMO_CS-10)
                    demo_cv.create_oval(x-14, y-14, x+14, y+14,
                                         outline='red', fill='', width=2)
                    demo_cv.create_text(x, y, text='氣', fill='red',
                                         font=('Helvetica', 9, 'bold'))

            elif idx == 1:
                # 示範提子：黑棋圍住白棋
                for r2, c2 in [(1,2),(2,1),(2,3),(3,2)]:
                    stone(r2, c2, BLACK)
                stone(2, 2, WHITE)
                x = DEMO_MG//2 + 2*(DEMO_CS-10)
                y = DEMO_MG//2 + 2*(DEMO_CS-10)
                demo_cv.create_text(x, y - sr - 8, text='被提走！',
                                     fill='red', font=('Helvetica', 9, 'bold'))

            elif idx == 2:
                # 示範劫
                demo_cv.create_text(
                    (5*(DEMO_CS-10)+DEMO_MG)//2 - 5,
                    (5*(DEMO_CS-10)+DEMO_MG)//2 - 20,
                    text='A ⬛ ← 提走 B',
                    fill=t['text'], font=('Helvetica', 10),
                )
                demo_cv.create_text(
                    (5*(DEMO_CS-10)+DEMO_MG)//2 - 5,
                    (5*(DEMO_CS-10)+DEMO_MG)//2 + 10,
                    text='B ⬜ ← 不能馬上提 A！',
                    fill='red', font=('Helvetica', 10),
                )

            elif idx == 3:
                # 示範計分
                for r2 in range(1, 4):
                    stone(r2, 1, BLACK)
                    stone(r2, 3, BLACK)
                stone(1, 2, BLACK)
                stone(3, 2, BLACK)
                x = DEMO_MG//2 + 2*(DEMO_CS-10)
                y = DEMO_MG//2 + 2*(DEMO_CS-10)
                demo_cv.create_rectangle(x-18, y-18, x+18, y+18,
                                          fill='#AAFFAA', outline='green', width=2)
                demo_cv.create_text(x, y, text='目',
                                     fill='green', font=('Helvetica', 12, 'bold'))

        btn_next_var = [None]

        def update():
            i = step_idx[0]
            lbl_title.config(text=STEPS[i]['title'])
            lbl_text.config(text=STEPS[i]['text'])
            draw_demo(i)
            if i < len(STEPS) - 1:
                btn_next_var[0].config(text='下一步 ▶')
            else:
                btn_next_var[0].config(text='完成 ✅')

        def next_step():
            if step_idx[0] < len(STEPS) - 1:
                step_idx[0] += 1
                update()
            else:
                open('.tutorial_done', 'w').close()
                win.destroy()

        def skip():
            open('.tutorial_done', 'w').close()
            win.destroy()

        bf = tk.Frame(win, bg=t['outer_bg'])
        bf.pack(pady=10)

        btn_next = tk.Button(bf, text='下一步 ▶', command=next_step,
                              bg=t['btn_bg'], fg=t['text'],
                              font=('Helvetica', 12), padx=10)
        btn_next.pack(side='left', padx=8)
        btn_next_var[0] = btn_next

        tk.Button(bf, text='跳過教學', command=skip,
                  bg=t['btn_bg'], fg=t['text'],
                  font=('Helvetica', 11)).pack(side='left', padx=8)

        update()
