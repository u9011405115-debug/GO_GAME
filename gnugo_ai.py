"""
gnugo_ai.py — GnuGo 圍棋引擎橋接（GTP 協議）

GnuGo level 對應棋力（概估）：
  level 1  ≈ 20 kyu
  level 3  ≈ 15 kyu
  level 5  ≈ 12 kyu
  level 7  ≈ 9  kyu
  level 10 ≈ 7  kyu

若 gnugo 未安裝，is_available() 回傳 False，呼叫端應自行 fallback 到 GoAI。
"""

import subprocess
import os
import shutil

from board import BLACK, WHITE, EMPTY


# GTP 橫座標（跳過 I）
_LETTERS = 'ABCDEFGHJKLMNOPQRST'


def find_gnugo():
    """找 gnugo 可執行檔，找到回傳路徑，找不到回傳 None。"""
    base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, 'gnugo.exe'),   # Windows 旁置
        os.path.join(base, 'gnugo'),        # macOS/Linux 旁置
        'gnugo',
        'gnugo.exe',
        '/opt/homebrew/bin/gnugo',
        '/usr/local/bin/gnugo',
        '/usr/bin/gnugo',
    ]
    for p in candidates:
        found = p if (os.path.isfile(p) and os.access(p, os.X_OK)) else shutil.which(p)
        if found:
            return found
    return None


def is_available():
    """快速檢查 GnuGo 是否可用（不啟動引擎）。"""
    return find_gnugo() is not None


class GnuGoAI:
    """
    GnuGo 引擎封裝。
    - get_move(board, color) ← 與 GoAI 相同介面
    - record_opponent(row, col, color) ← 每次人類落子後呼叫
    - undo(steps) ← 悔棋，重啟引擎並重播歷史
    """

    def __init__(self, level=5, board_size=19):
        self.level      = level
        self.board_size = board_size
        self._proc      = None
        self._seq       = []   # [(row, col, color), ...]  完整落子紀錄
        self._ready     = False

        path = find_gnugo()
        if path:
            try:
                self._launch(path)
                self._ready = True
            except Exception:
                pass

    # ── 狀態 ──────────────────────────────────────────────────────────────────

    @property
    def ready(self):
        return self._ready and self._proc is not None and self._proc.poll() is None

    # ── 內部 GTP 通訊 ─────────────────────────────────────────────────────────

    def _launch(self, path):
        self._proc = subprocess.Popen(
            [path, '--mode', 'gtp', f'--level={self.level}'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        # Handshake：確認 GnuGo 已進入 GTP 模式並回應
        ver = self._gtp('protocol_version')
        if ver is None:
            raise RuntimeError('GnuGo GTP handshake failed')
        komi = 6.5 if self.board_size == 19 else 4.5
        self._gtp(f'boardsize {self.board_size}')
        self._gtp('clear_board')
        self._gtp(f'komi {komi}')
        self._seq = []

    def _gtp(self, cmd):
        """
        送出一行 GTP 指令，讀回回應，回傳 '= ...' 後的值（字串）。
        失敗（引擎錯誤或 '?' 前綴）回傳 None。
        """
        if not self._proc:
            return None
        # 若程序已結束，立即回傳 None（不阻塞）
        if self._proc.poll() is not None:
            self._ready = False
            return None
        try:
            self._proc.stdin.write(f'{cmd}\n'.encode('utf-8'))
            self._proc.stdin.flush()
            lines = []
            while True:
                raw = self._proc.stdout.readline()
                if not raw:          # b'' → EOF：程序已終止
                    self._ready = False
                    return None
                ln = raw.decode('utf-8', errors='replace').rstrip('\r\n')
                if ln == '':         # 空行 → GTP 回應結束
                    break
                lines.append(ln)
            # 找第一個以 = 或 ? 開頭的行作為主回應
            for ln in lines:
                if ln.startswith('='):
                    return ln[1:].strip()
                if ln.startswith('?'):
                    return None      # GTP 錯誤回應
        except Exception:
            self._ready = False
        return None

    # ── 座標轉換 ──────────────────────────────────────────────────────────────

    def _to_gtp(self, row, col):
        """(row, col) 0-indexed → GTP vertex，如 'D16'"""
        return f'{_LETTERS[col]}{self.board_size - row}'

    def _from_gtp(self, vertex):
        """GTP vertex → (row, col) 0-indexed；超出範圍拋出 ValueError"""
        v = vertex.strip().upper()
        col = _LETTERS.index(v[0])
        row = self.board_size - int(v[1:])
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            raise ValueError(f'GTP vertex {vertex!r} out of range for {self.board_size}×{self.board_size}')
        return row, col

    # ── 公開 API ──────────────────────────────────────────────────────────────

    def record_opponent(self, row, col, color):
        """
        通知引擎對手（人類）落子。
        必須在每次人類落子後呼叫，以保持引擎狀態同步。
        """
        if not self.ready:
            return
        c = 'black' if color == BLACK else 'white'
        self._gtp(f'play {c} {self._to_gtp(row, col)}')
        self._seq.append((row, col, color))

    def get_move(self, board, color=WHITE):
        """
        要求引擎走一手。
        回傳 (row, col)，若 Pass 或引擎未就緒則回傳 None。
        board 參數保留給 GoAI 相容介面，實際上不使用（GnuGo 自維護狀態）。
        """
        if not self.ready:
            return None
        c = 'black' if color == BLACK else 'white'
        resp = self._gtp(f'genmove {c}')
        if not resp or resp.upper() in ('PASS', 'RESIGN'):
            return None
        try:
            row, col = self._from_gtp(resp)
        except (ValueError, IndexError):
            return None
        self._seq.append((row, col, color))
        return row, col

    def undo(self, steps=2):
        """
        悔棋 steps 手：重啟引擎並重播歷史（扣除最後 steps 步）。
        """
        if not self._proc:
            return
        path = find_gnugo()
        if not path:
            return
        try:
            self._gtp('quit')
            self._proc.wait(timeout=2)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        keep = self._seq[:-steps] if steps <= len(self._seq) else []
        self._launch(path)
        for r, c, col in keep:
            cs = 'black' if col == BLACK else 'white'
            self._gtp(f'play {cs} {self._to_gtp(r, c)}')
        self._seq = list(keep)

    def evaluate_move(self, board, row, col, color):
        """
        評價玩家剛落的手品質（委派給 GoAI 的評估邏輯）。
        GnuGoAI 本身不做評估，借用 GoAI 的方法避免重複實作。
        """
        if not hasattr(self, '_eval_ai'):
            from ai import GoAI
            self._eval_ai = GoAI(5, self.board_size)
        return self._eval_ai.evaluate_move(board, row, col, color)

    def close(self):
        """關閉引擎程序。"""
        if self._proc:
            try:
                self._gtp('quit')
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            finally:
                self._proc = None
                self._ready = False
