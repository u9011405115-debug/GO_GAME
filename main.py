"""
main.py — 啟動選擇畫面
"""

import tkinter as tk
import tkinter.ttk as ttk
import tkinter.font as tkfont
import os, sys

from gui import GameGUI
from problem_mode import ProblemMode

# ── 主題預覽配色（與 gui.py THEMES 對應）──────────────────────────────────────
THEME_PREVIEW = {
    '木紋': {'bg': '#DEB887', 'line': '#7A4F2D', 'stone_b': '#1A1A1A', 'stone_w': '#F8F8F8'},
    '星空': {'bg': '#1C1C3A', 'line': '#6666BB', 'stone_b': '#1A1A1A', 'stone_w': '#F8F8F8'},
}

# 21 個難度（30 kyu → 10 kyu），全部使用 GnuGo 引擎
# 格式：(棋力數值, 下拉選單顯示文字)
DIFF_OPTIONS = [
    (30, '30 級 — 初次接觸  🤖 GnuGo lv.1'),
    (29, '29 級 — 初次接觸↑🤖 GnuGo lv.1'),
    (28, '28 級 — 超入門    🤖 GnuGo lv.2'),
    (27, '27 級 — 超入門↑  🤖 GnuGo lv.2'),
    (26, '26 級 — 入門      🤖 GnuGo lv.3'),
    (25, '25 級 — 入門↑    🤖 GnuGo lv.3'),
    (24, '24 級 — 初學      🤖 GnuGo lv.4'),
    (23, '23 級 — 初學↑    🤖 GnuGo lv.4'),
    (22, '22 級 — 初中級    🤖 GnuGo lv.5'),
    (21, '21 級 — 初中級↑  🤖 GnuGo lv.5'),
    (20, '20 級 — 中級      🤖 GnuGo lv.6'),
    (19, '19 級 — 中級↑    🤖 GnuGo lv.6'),
    (18, '18 級 — 中高級    🤖 GnuGo lv.7'),
    (17, '17 級 — 中高級↑  🤖 GnuGo lv.7'),
    (16, '16 級 — 高級      🤖 GnuGo lv.8'),
    (15, '15 級 — 高級↑    🤖 GnuGo lv.8'),
    (14, '14 級 — 強手      🤖 GnuGo lv.9'),
    (13, '13 級 — 強手↑    🤖 GnuGo lv.9'),
    (12, '12 級 — 達人      🤖 GnuGo lv.10'),
    (11, '11 級 — 達人↑    🤖 GnuGo lv.10'),
    (10, '10 級 — 達人巔峰  🤖 GnuGo lv.10'),
]


class StartScreen:
    """遊戲啟動選擇畫面"""

    OUTER_BG  = '#3B2507'
    PANEL_BG  = '#F5E6C8'
    TEXT_COL  = '#3B2507'
    BTN_ON    = '#C8975A'   # 選中
    BTN_OFF   = '#D9C09A'   # 未選中
    BTN_ACT   = '#A0703A'

    def __init__(self, root):
        self.root = root
        self.root.title('圍棋小學堂 — 開始遊戲')
        self.root.resizable(False, False)
        self.root.configure(bg=self.OUTER_BG)

        # 預設選項
        self.sel_size  = tk.IntVar(value=13)
        self.sel_theme = tk.StringVar(value='木紋')
        self._diff_idx = 0   # DIFF_OPTIONS 的索引，預設 25 kyu

        # 動態追蹤按鈕（用於切換高亮）
        self._size_btns  = {}
        self._theme_btns = {}
        self._diff_combo = None

        self._build()

    # ── 版面建構 ───────────────────────────────────────────────────────────────

    def _build(self):
        f_big   = tkfont.Font(family='Helvetica', size=22, weight='bold')
        f_mid   = tkfont.Font(family='Helvetica', size=13, weight='bold')
        f_small = tkfont.Font(family='Helvetica', size=11)
        f_tiny  = tkfont.Font(family='Helvetica', size=9)

        # 標題
        tk.Label(self.root, text='⚫ 圍棋小學堂 ⚪',
                 font=f_big, bg=self.OUTER_BG, fg='#FFD700').pack(pady=(18, 4))
        tk.Label(self.root, text='圍棋對戰遊戲 — 30 至 10 級（全程 GnuGo 引擎）',
                 font=f_small, bg=self.OUTER_BG, fg='#FFEEAA').pack(pady=(0, 14))

        # 主面板
        panel = tk.Frame(self.root, bg=self.PANEL_BG, bd=3, relief='ridge')
        panel.pack(padx=24, pady=4, fill='x')

        # ── 棋盤大小 ──────────────────────────────────────────────────────────
        self._section(panel, '棋盤大小', f_mid)

        size_row = tk.Frame(panel, bg=self.PANEL_BG)
        size_row.pack(pady=4)

        for size, label, desc in [
            (13, '13 × 13', '較快結束，適合入門'),
            (19, '19 × 19', '標準棋盤，更多變化'),
        ]:
            frm = tk.Frame(size_row, bg=self.PANEL_BG)
            frm.pack(side='left', padx=12)
            btn = tk.Button(
                frm, text=label,
                font=f_mid, width=10,
                command=lambda s=size: self._select_size(s),
                **self._btn_kw(),
            )
            btn.pack()
            tk.Label(frm, text=desc, font=f_tiny,
                     bg=self.PANEL_BG, fg='#7A5030').pack()
            self._size_btns[size] = btn

        # ── AI 難度（下拉選單，15 個等級）────────────────────────────────────
        self._section(panel, 'AI 難度', f_mid)

        diff_row = tk.Frame(panel, bg=self.PANEL_BG)
        diff_row.pack(pady=8)

        tk.Label(diff_row, text='選擇難度：', font=f_small,
                 bg=self.PANEL_BG, fg=self.TEXT_COL).pack(side='left', padx=(8, 4))

        style = ttk.Style()
        style.theme_use('default')
        style.configure('Diff.TCombobox',
                        fieldbackground=self.BTN_OFF,
                        background=self.BTN_OFF,
                        foreground=self.TEXT_COL,
                        selectbackground=self.BTN_ON,
                        selectforeground=self.TEXT_COL,
                        font=('Helvetica', 11))

        self._diff_combo = ttk.Combobox(
            diff_row,
            values=[label for _, label in DIFF_OPTIONS],
            state='readonly',
            width=34,
            style='Diff.TCombobox',
            font=('Helvetica', 11),
        )
        self._diff_combo.current(self._diff_idx)
        self._diff_combo.pack(side='left', padx=(0, 8))

        # ── 棋盤主題 ──────────────────────────────────────────────────────────
        self._section(panel, '棋盤主題', f_mid)

        theme_row = tk.Frame(panel, bg=self.PANEL_BG)
        theme_row.pack(pady=6)

        for theme_name in ['木紋', '星空']:
            frm = tk.Frame(theme_row, bg=self.PANEL_BG)
            frm.pack(side='left', padx=16)

            # 主題小預覽圖
            prev = self._make_theme_preview(frm, theme_name)
            prev.pack()

            btn = tk.Button(
                frm, text=theme_name,
                font=f_mid, width=6,
                command=lambda th=theme_name: self._select_theme(th),
                **self._btn_kw(),
            )
            btn.pack(pady=4)
            self._theme_btns[theme_name] = btn

        # 更新按鈕高亮
        self._highlight_all()

        # ── 按鈕列（開始遊戲 + 死活題訓練）──────────────────────────────────
        btn_row = tk.Frame(self.root, bg=self.OUTER_BG)
        btn_row.pack(pady=16)

        tk.Button(
            btn_row,
            text='▶  開始遊戲',
            font=tkfont.Font(family='Helvetica', size=16, weight='bold'),
            bg='#CC7722', fg='white',
            activebackground='#AA5500',
            relief='raised', bd=3,
            padx=20, pady=8,
            command=self._start_game,
        ).pack(side='left', padx=12)

        tk.Button(
            btn_row,
            text='🧩  死活題訓練',
            font=tkfont.Font(family='Helvetica', size=14, weight='bold'),
            bg='#5588AA', fg='white',
            activebackground='#3366AA',
            relief='raised', bd=3,
            padx=12, pady=8,
            command=self._start_problems,
        ).pack(side='left', padx=12)

    def _section(self, parent, title, font):
        """分節標題"""
        tk.Label(parent, text=title, font=font,
                 bg=self.PANEL_BG, fg=self.TEXT_COL).pack(pady=(10, 2))
        tk.Frame(parent, bg='#C8975A', height=1).pack(fill='x', padx=20)

    def _btn_kw(self):
        return dict(bg=self.BTN_OFF, fg=self.TEXT_COL,
                    activebackground=self.BTN_ACT,
                    relief='raised', bd=2)

    # ── 主題預覽 ───────────────────────────────────────────────────────────────

    def _make_theme_preview(self, parent, theme_name):
        """繪製一個 100×80 的主題縮圖 Canvas"""
        p = THEME_PREVIEW[theme_name]
        cv = tk.Canvas(parent, width=100, height=80,
                        bg=p['bg'], highlightthickness=1,
                        highlightbackground=p['line'])
        # 簡單 5×5 格線
        step = 16
        for i in range(5):
            x = 10 + i * step
            y = 10 + i * step
            cv.create_line(x, 10, x, 10 + 4*step, fill=p['line'])
            cv.create_line(10, y, 10 + 4*step, y, fill=p['line'])
        # 幾顆棋子示意
        for (r, c, col) in [(1,1,'b'),(1,3,'w'),(2,2,'b'),(3,1,'w'),(3,3,'b')]:
            x = 10 + c * step
            y = 10 + r * step
            fill = p['stone_b'] if col == 'b' else p['stone_w']
            out  = '#000' if col == 'b' else '#888'
            cv.create_oval(x-7, y-7, x+7, y+7, fill=fill, outline=out)
        return cv

    # ── 選項切換 ───────────────────────────────────────────────────────────────

    def _select_size(self, size):
        self.sel_size.set(size)
        self._highlight_group(self._size_btns, size)

    def _select_theme(self, theme):
        self.sel_theme.set(theme)
        self._highlight_group(self._theme_btns, theme)

    def _highlight_group(self, btn_dict, selected):
        for key, btn in btn_dict.items():
            btn.config(bg=self.BTN_ON if key == selected else self.BTN_OFF)

    def _highlight_all(self):
        self._highlight_group(self._size_btns,  self.sel_size.get())
        self._highlight_group(self._theme_btns, self.sel_theme.get())

    # ── 啟動遊戲 ───────────────────────────────────────────────────────────────

    def _start_game(self):
        """隱藏選擇畫面，開啟遊戲視窗"""
        size       = self.sel_size.get()
        idx        = self._diff_combo.current() if self._diff_combo else 0
        difficulty = DIFF_OPTIONS[idx][0]
        theme      = self.sel_theme.get()

        self.root.withdraw()

        game_win = tk.Toplevel(self.root)
        game_win.title('圍棋小學堂 🎓')

        def on_close():
            game_win.destroy()
            self.root.deiconify()

        game_win.protocol('WM_DELETE_WINDOW', on_close)
        GameGUI(game_win, board_size=size, difficulty=difficulty, theme=theme)

    def _start_problems(self):
        """開啟死活題訓練視窗"""
        self.root.withdraw()

        prob_win = tk.Toplevel(self.root)
        prob_win.title('死活題訓練')

        def on_close():
            prob_win.destroy()
            self.root.deiconify()

        prob_win.protocol('WM_DELETE_WINDOW', on_close)
        ProblemMode(prob_win)


# ── 主程式入口 ─────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # 確保工作目錄是此檔案所在目錄
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    root = tk.Tk()
    app = StartScreen(root)
    root.mainloop()
