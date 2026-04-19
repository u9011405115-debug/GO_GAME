"""
problem_mode.py — 死活題訓練模式視窗
"""

import tkinter as tk
import tkinter.font as tkfont

from board import Board, BLACK, WHITE, EMPTY
from problems import PROBLEMS


class ProblemMode:
    """死活題訓練主視窗"""

    BG      = '#3B2507'
    BOARD   = '#DEB887'
    LINE    = '#7A4F2D'
    PANEL   = '#F5E6C8'
    TEXT    = '#3B2507'
    BTN     = '#C8975A'
    BTN_ACT = '#A0703A'
    OK_COL  = '#007700'
    ERR_COL = '#CC0000'

    def __init__(self, root):
        self.root = root
        self.root.title('死活題訓練')
        self.root.configure(bg=self.BG)
        self.root.resizable(False, False)

        self._idx   = 0        # 目前題目索引
        self._tries = 0        # 本題嘗試次數
        self._solved = [False] * len(PROBLEMS)

        self._build()
        self._load_problem()

    # ── 版面建構 ───────────────────────────────────────────────────────────────

    def _build(self):
        f_title = tkfont.Font(family='Helvetica', size=15, weight='bold')
        f_mid   = tkfont.Font(family='Helvetica', size=12)
        f_small = tkfont.Font(family='Helvetica', size=10)

        # 標題列
        tk.Label(self.root, text='🧩 死活題訓練',
                 font=f_title, bg=self.BG, fg='#FFD700').pack(pady=(10, 4))

        # 主體（棋盤 + 說明欄）
        body = tk.Frame(self.root, bg=self.BG)
        body.pack(padx=16, pady=4)

        # ── 右側說明欄 ────────────────────────────────────────────────────────
        panel = tk.Frame(body, bg=self.PANEL, bd=2, relief='ridge', width=190)
        panel.pack(side='right', fill='y', padx=(12, 0))
        panel.pack_propagate(False)

        self.lbl_level = tk.Label(panel, text='', font=f_mid,
                                   bg=self.PANEL, fg=self.TEXT)
        self.lbl_level.pack(pady=(12, 2))

        self.lbl_title = tk.Label(panel, text='', font=f_mid,
                                   bg=self.PANEL, fg=self.TEXT,
                                   wraplength=170, justify='center')
        self.lbl_title.pack(pady=2)

        tk.Frame(panel, bg=self.BTN, height=1).pack(fill='x', padx=10, pady=4)

        self.lbl_desc = tk.Label(panel, text='', font=f_small,
                                  bg=self.PANEL, fg=self.TEXT,
                                  wraplength=170, justify='left')
        self.lbl_desc.pack(pady=4, padx=8)

        self.lbl_status = tk.Label(panel, text='',
                                    font=tkfont.Font(family='Helvetica', size=12, weight='bold'),
                                    bg=self.PANEL, fg=self.OK_COL,
                                    wraplength=170, justify='center')
        self.lbl_status.pack(pady=6)

        btn_kw = dict(font=f_mid, bg=self.BTN, fg=self.TEXT,
                      activebackground=self.BTN_ACT,
                      relief='raised', bd=2, width=9)

        tk.Button(panel, text='💡 提示',
                  command=self._show_hint, **btn_kw).pack(pady=3)

        tk.Button(panel, text='↩ 重置',
                  command=self._reset_problem, **btn_kw).pack(pady=3)

        self.btn_next = tk.Button(panel, text='下一題 ▶',
                                   command=self._next_problem,
                                   state='disabled', **btn_kw)
        self.btn_next.pack(pady=3)

        # 進度標籤
        self.lbl_progress = tk.Label(panel, text='', font=f_small,
                                      bg=self.PANEL, fg=self.TEXT)
        self.lbl_progress.pack(pady=(8, 4))

        # 題目選擇按鈕
        tk.Frame(panel, bg=self.BTN, height=1).pack(fill='x', padx=10, pady=4)
        tk.Label(panel, text='直接跳到：', font=f_small,
                 bg=self.PANEL, fg=self.TEXT).pack()
        nav = tk.Frame(panel, bg=self.PANEL)
        nav.pack(pady=4)
        self._nav_btns = []
        for i, p in enumerate(PROBLEMS):
            b = tk.Button(nav, text=str(i + 1),
                          font=f_small, width=3,
                          bg=self.BTN, fg=self.TEXT,
                          activebackground=self.BTN_ACT,
                          relief='raised', bd=2,
                          command=lambda idx=i: self._jump_to(idx))
            b.grid(row=0, column=i, padx=2)
            self._nav_btns.append(b)

        # ── 棋盤畫布 ──────────────────────────────────────────────────────────
        self.cs = 52          # 格距（9×9 棋盤）
        self.mg = self.cs     # 邊距
        cv_size = (9 - 1) * self.cs + 2 * self.mg

        self.canvas = tk.Canvas(body, width=cv_size, height=cv_size,
                                 bg=self.BOARD,
                                 highlightthickness=3,
                                 highlightbackground=self.LINE)
        self.canvas.pack(side='left')
        self.canvas.bind('<Button-1>', self._on_click)

        # 棋盤物件（邏輯層）
        self.board = Board(9)

    # ── 題目管理 ───────────────────────────────────────────────────────────────

    def _load_problem(self):
        """載入目前索引的題目"""
        p = PROBLEMS[self._idx]
        self._tries = 0
        self._current = p

        # 重建棋盤
        self.board = Board(9)
        for r, c in p['white']:
            self.board.grid[r][c] = WHITE
        for r, c in p['black']:
            self.board.grid[r][c] = BLACK

        # 更新說明欄
        self.lbl_level.config(text=p['level'])
        self.lbl_title.config(text=p['title'])
        self.lbl_desc.config(text=p['desc'])
        self.lbl_status.config(text='', fg=self.OK_COL)
        self.btn_next.config(state='disabled')

        done = sum(self._solved)
        self.lbl_progress.config(
            text=f'進度：{done} / {len(PROBLEMS)} 題完成'
        )
        self._update_nav()
        self._redraw()

    def _reset_problem(self):
        self._load_problem()

    def _next_problem(self):
        if self._idx < len(PROBLEMS) - 1:
            self._idx += 1
        else:
            self._idx = 0   # 循環回第一題
        self._load_problem()

    def _jump_to(self, idx):
        self._idx = idx
        self._load_problem()

    def _update_nav(self):
        for i, b in enumerate(self._nav_btns):
            if i == self._idx:
                b.config(relief='sunken', bg=self.BTN_ACT)
            elif self._solved[i]:
                b.config(relief='raised', bg='#77BB77')
            else:
                b.config(relief='raised', bg=self.BTN)

    # ── 互動 ───────────────────────────────────────────────────────────────────

    def _on_click(self, event):
        """玩家落子"""
        # 計算棋盤座標
        col = round((event.x - self.mg) / self.cs)
        row = round((event.y - self.mg) / self.cs)
        col = max(0, min(8, col))
        row = max(0, min(8, row))

        if self.board.grid[row][col] != EMPTY:
            self.lbl_status.config(text='此點已有棋子', fg=self.ERR_COL)
            return

        self._tries += 1
        solutions = self._current['solutions']

        if (row, col) in solutions:
            self._solved[self._idx] = True
            self.board.grid[row][col] = BLACK
            self._redraw()
            tries_str = '一次就對了！👏' if self._tries == 1 else f'（嘗試了 {self._tries} 次）'
            self.lbl_status.config(
                text=f'✅ 答對了！{tries_str}',
                fg=self.OK_COL,
            )
            self.btn_next.config(state='normal')
            done = sum(self._solved)
            self.lbl_progress.config(
                text=f'進度：{done} / {len(PROBLEMS)} 題完成'
            )
            self._update_nav()
            if done == len(PROBLEMS):
                self.lbl_status.config(
                    text='🏆 全部完成！太厲害了！',
                    fg='#CC7722',
                )
        else:
            self.lbl_status.config(text='❌ 再想想看！', fg=self.ERR_COL)

    def _show_hint(self):
        self.lbl_status.config(
            text=f'💡 {self._current["hint"]}',
            fg='#7700AA',
        )

    # ── 繪圖 ───────────────────────────────────────────────────────────────────

    def _redraw(self):
        self.canvas.delete('all')
        s  = 9
        cs = self.cs
        mg = self.mg

        # 格線
        for i in range(s):
            x = mg + i * cs
            y = mg + i * cs
            self.canvas.create_line(x, mg, x, mg + (s - 1) * cs,
                                    fill=self.LINE, width=1)
            self.canvas.create_line(mg, y, mg + (s - 1) * cs, y,
                                    fill=self.LINE, width=1)

        # 外框
        self.canvas.create_rectangle(
            mg, mg, mg + (s - 1) * cs, mg + (s - 1) * cs,
            outline=self.LINE, width=2,
        )

        # 星位（9×9：天元+4個星位）
        for sr, sc in [(4, 4), (2, 2), (2, 6), (6, 2), (6, 6)]:
            hx = mg + sc * cs
            hy = mg + sr * cs
            self.canvas.create_oval(hx - 4, hy - 4, hx + 4, hy + 4,
                                    fill=self.LINE, outline=self.LINE)

        # 棋子
        stone_r = int(cs * 0.45)
        for r in range(s):
            for c in range(s):
                cell = self.board.grid[r][c]
                if cell == EMPTY:
                    continue
                x = mg + c * cs
                y = mg + r * cs
                if cell == BLACK:
                    self.canvas.create_oval(
                        x - stone_r, y - stone_r,
                        x + stone_r, y + stone_r,
                        fill='black', outline='black',
                    )
                else:
                    self.canvas.create_oval(
                        x - stone_r, y - stone_r,
                        x + stone_r, y + stone_r,
                        fill='#F8F8F8', outline='#888888',
                    )
