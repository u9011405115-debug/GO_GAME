"""
board.py — 棋盤狀態與圍棋規則邏輯
"""

EMPTY = 0   # 空點
BLACK = 1   # 黑子
WHITE = 2   # 白子


def opponent(color):
    """回傳對手顏色"""
    return WHITE if color == BLACK else BLACK


class Board:
    """棋盤類別，管理棋盤狀態與所有規則判斷"""

    MAX_UNDO = 3  # 每局最多悔棋次數

    def __init__(self, size=19):
        self.size = size
        # 棋盤二維陣列：0=空、1=黑、2=白
        self.grid = [[EMPTY] * size for _ in range(size)]
        # 劫禁著點 (row, col) 或 None
        self.ko_point = None
        # 歷史快照堆疊（用於悔棋）
        # 每筆：(grid_copy, ko_point, captured_black, captured_white)
        self.history = []
        # 已使用悔棋次數
        self.undo_count = 0
        # 被提走的棋子數（用於計分）
        self.captured_black = 0   # 黑子被提走總數
        self.captured_white = 0   # 白子被提走總數
        # 每手棋記錄，用於覆盤：[(row, col, color), ...]
        self.move_record = []

    # ── 工具 ──────────────────────────────────────────────────────────────────

    def neighbors(self, row, col):
        """回傳 (row, col) 上下左右的合法鄰點"""
        result = []
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.size and 0 <= nc < self.size:
                result.append((nr, nc))
        return result

    def _copy_grid(self):
        """深拷貝棋盤陣列"""
        return [row[:] for row in self.grid]

    # ── 棋串與氣 ──────────────────────────────────────────────────────────────

    def find_group(self, row, col):
        """
        DFS 找出 (row,col) 所在棋串及其氣
        回傳 (group: set, liberties: set)
        """
        color = self.grid[row][col]
        if color == EMPTY:
            return set(), set()

        group = set()
        liberties = set()
        stack = [(row, col)]

        while stack:
            r, c = stack.pop()
            if (r, c) in group:
                continue
            group.add((r, c))
            for nr, nc in self.neighbors(r, c):
                cell = self.grid[nr][nc]
                if cell == color and (nr, nc) not in group:
                    stack.append((nr, nc))
                elif cell == EMPTY:
                    liberties.add((nr, nc))

        return group, liberties

    def get_liberties_count(self, row, col):
        """取得指定位置棋串的氣數"""
        _, libs = self.find_group(row, col)
        return len(libs)

    # ── 合法性判斷 ────────────────────────────────────────────────────────────

    def is_valid_move(self, row, col, color):
        """
        判斷 (row, col) 對 color 是否合法落子
        回傳 (bool, reason: str)
        """
        # 邊界檢查
        if not (0 <= row < self.size and 0 <= col < self.size):
            return False, "超出棋盤範圍"
        # 已有棋子
        if self.grid[row][col] != EMPTY:
            return False, "此點已有棋子"
        # 劫禁著
        if self.ko_point == (row, col):
            return False, "劫禁著（請先在其他地方落子）"

        opp = opponent(color)
        captured = set()

        # 模擬落子（用 try/finally 確保一定還原）
        self.grid[row][col] = color
        try:
            # 找出會被提走的對手棋串
            for nr, nc in self.neighbors(row, col):
                if self.grid[nr][nc] == opp:
                    grp, libs = self.find_group(nr, nc)
                    if not libs:
                        captured |= grp

            # 暫時移除被提走的棋子
            for r, c in captured:
                self.grid[r][c] = EMPTY

            # 自殺判斷：落子後本串是否有氣
            _, my_libs = self.find_group(row, col)
            if not my_libs:
                return False, "自殺點（落子後本串無氣）"

            return True, "合法"

        finally:
            # 一定還原棋盤（無論是否發生例外）
            for r, c in captured:
                self.grid[r][c] = opp
            self.grid[row][col] = EMPTY

    # ── 落子 ──────────────────────────────────────────────────────────────────

    def place_stone(self, row, col, color):
        """
        落子並處理提子與 Ko 更新
        回傳 (success: bool, captured_count: int, message: str)
        """
        valid, reason = self.is_valid_move(row, col, color)
        if not valid:
            return False, 0, reason

        # 儲存目前狀態到歷史堆疊
        self.history.append((
            self._copy_grid(),
            self.ko_point,
            self.captured_black,
            self.captured_white,
        ))

        # 落子
        self.grid[row][col] = color
        opp = opponent(color)

        # 提走所有無氣的對手棋串
        total_captured = 0
        captured_positions = []
        for nr, nc in self.neighbors(row, col):
            if self.grid[nr][nc] == opp:
                grp, libs = self.find_group(nr, nc)
                if not libs:
                    for r, c in grp:
                        self.grid[r][c] = EMPTY
                    total_captured += len(grp)
                    captured_positions.extend(grp)

        # 更新提子計數
        if color == BLACK:
            self.captured_white += total_captured
        else:
            self.captured_black += total_captured

        # 更新 Ko 點：恰好提走 1 子時，被提走位置為 Ko 點
        if total_captured == 1:
            self.ko_point = captured_positions[0]
        else:
            self.ko_point = None

        # 記錄此手
        self.move_record.append((row, col, color))

        return True, total_captured, "成功"

    # ── 悔棋 ──────────────────────────────────────────────────────────────────

    def undo(self):
        """
        悔棋（一次退回兩手：玩家 + AI）
        回傳 (success: bool, message: str)
        """
        if self.undo_count >= self.MAX_UNDO:
            return False, f"已達悔棋上限（{self.MAX_UNDO} 次）"

        steps = min(2, len(self.history))
        if steps == 0:
            return False, "目前無法悔棋"

        for _ in range(steps):
            if self.history:
                grid, ko, cap_b, cap_w = self.history.pop()
                self.grid = grid
                self.ko_point = ko
                self.captured_black = cap_b
                self.captured_white = cap_w
            if self.move_record:
                self.move_record.pop()

        self.undo_count += 1
        remain = self.MAX_UNDO - self.undo_count
        return True, f"悔棋成功（剩餘 {remain} 次）"

    # ── 計分 ──────────────────────────────────────────────────────────────────

    def calculate_score(self):
        """
        區域計分法（Area Scoring）
        回傳 (black_score: float, white_score: float, territory: dict)
        territory: {(r,c): BLACK | WHITE | None}  None 表示中立地帶
        """
        territory = {}
        visited = set()

        for row in range(self.size):
            for col in range(self.size):
                if self.grid[row][col] != EMPTY or (row, col) in visited:
                    continue

                # BFS 擴展此塊空地，記錄邊界顏色
                region = []
                border_colors = set()
                queue = [(row, col)]
                in_queue = {(row, col)}

                while queue:
                    r, c = queue.pop(0)
                    region.append((r, c))
                    visited.add((r, c))
                    for nr, nc in self.neighbors(r, c):
                        cell = self.grid[nr][nc]
                        if cell == EMPTY and (nr, nc) not in in_queue:
                            queue.append((nr, nc))
                            in_queue.add((nr, nc))
                        elif cell != EMPTY:
                            border_colors.add(cell)

                # 邊界只有一種顏色 → 屬於該顏色的地盤
                owner = border_colors.pop() if len(border_colors) == 1 else None
                for pos in region:
                    territory[pos] = owner

        # 統計棋子數
        black_stones = sum(
            1 for r in range(self.size)
            for c in range(self.size) if self.grid[r][c] == BLACK
        )
        white_stones = sum(
            1 for r in range(self.size)
            for c in range(self.size) if self.grid[r][c] == WHITE
        )

        # 統計地盤
        black_territory = sum(1 for v in territory.values() if v == BLACK)
        white_territory = sum(1 for v in territory.values() if v == WHITE)

        # 貼目：19x19 用 6.5 目，13x13 用 4.5 目
        komi = 6.5 if self.size == 19 else 4.5

        black_score = black_stones + black_territory + self.captured_white
        white_score = white_stones + white_territory + self.captured_black + komi

        return black_score, white_score, territory
