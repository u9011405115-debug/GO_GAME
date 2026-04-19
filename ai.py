"""
ai.py — AI 決策模組
難度 25 級（入門/純隨機）→ 10 級（具備預讀、切斷、逃脫邏輯）

等級設計目的：測試學生是否學會「預測」：
  25 級：無預測，純隨機
  20 級：1 步預測（我能立刻吃子嗎？我會被立刻吃嗎？）
  15 級：2 步預測（逃脫打吃、切斷對方、威脅下一步提子）
  10 級：3 步預測（避免走入陷阱、綜合戰略）
"""

import random
from board import Board, BLACK, WHITE, EMPTY, opponent


class GoAI:
    """圍棋 AI，支援多難度等級"""

    def __init__(self, difficulty=25, board_size=19):
        """
        difficulty: 25=入門, 20=初學, 15=進階, 10=實戰
        board_size: 13 或 19
        """
        self.difficulty = difficulty
        self.board_size = board_size
        self.move_count = 0

    # ── 主入口 ────────────────────────────────────────────────────────────────

    def get_move(self, board, color=WHITE):
        """根據難度回傳 AI 下一手 (row, col) 或 None（表示 Pass）"""
        self.move_count += 1
        valid_moves = self._get_valid_moves(board, color)
        if not valid_moves:
            return None

        if self.difficulty >= 23:
            return self._strategy_25(board, color, valid_moves)
        elif self.difficulty >= 17:
            return self._strategy_20(board, color, valid_moves)
        elif self.difficulty >= 12:
            return self._strategy_15(board, color, valid_moves)
        elif self.difficulty >= 9:
            return self._strategy_10(board, color, valid_moves)
        elif self.difficulty >= 6:
            return self._strategy_8(board, color, valid_moves)
        else:
            return self._strategy_5(board, color, valid_moves)

    # ── 合法手列舉 ────────────────────────────────────────────────────────────

    def _get_valid_moves(self, board, color):
        moves = []
        for r in range(board.size):
            for c in range(board.size):
                valid, _ = board.is_valid_move(r, c, color)
                if valid:
                    moves.append((r, c))
        return moves

    # ── 等級策略 ──────────────────────────────────────────────────────────────

    def _strategy_25(self, board, color, valid_moves):
        """25 級：純隨機，完全無預測"""
        return random.choice(valid_moves)

    def _strategy_20(self, board, color, valid_moves):
        """
        20 級：1 步預測
        1. 吃掉已被打吃（1 口氣）的對手棋串
        2. 避免自己棋串只剩 1 口氣（自吃）
        3. 隨機
        """
        # 1. 立刻吃子
        move = self._find_capture_move(board, color, valid_moves)
        if move:
            return move
        # 2. 避免自吃
        return self._filter_safe(board, color, valid_moves)

    def _strategy_15(self, board, color, valid_moves):
        """
        15 級：2 步預測
        1. 吃子
        2. 逃脫己方打吃（被打吃就逃）
        3. 威脅（把對手棋串逼入打吃，下一步可提）
        4. 切斷對手連接
        5. 避免自吃
        6. 隨機
        """
        move = self._find_capture_move(board, color, valid_moves)
        if move:
            return move

        move = self._find_escape_move(board, color, valid_moves)
        if move:
            return move

        move = self._find_threaten_move(board, color, valid_moves)
        if move:
            return move

        move = self._find_cut_move(board, color, valid_moves)
        if move:
            return move

        return self._filter_safe(board, color, valid_moves)

    def _strategy_10(self, board, color, valid_moves):
        """
        10 級：3 步預測（實戰）
        1. 吃子
        2. 逃脫打吃
        3. 威脅（逼入打吃）
        4. 切斷
        5. 搶天元、星位
        6. 避免走入對手下一步能打吃的陷阱（3 步預讀）
        7. 避免自吃
        8. 隨機
        """
        move = self._find_capture_move(board, color, valid_moves)
        if move:
            return move

        move = self._find_escape_move(board, color, valid_moves)
        if move:
            return move

        move = self._find_threaten_move(board, color, valid_moves)
        if move:
            return move

        move = self._find_cut_move(board, color, valid_moves)
        if move:
            return move

        for pos in self._important_points():
            if pos in valid_moves:
                return pos

        # 過濾掉走後對手立刻可打吃己方的「陷阱手」
        safe_moves = self._filter_no_trap(board, color, valid_moves)
        return self._filter_safe(board, color, safe_moves or valid_moves)

    # ── 核心判斷：吃子 ────────────────────────────────────────────────────────

    def _find_capture_move(self, board, color, valid_moves):
        """找能吃最多子的手（對方棋串剩 0 口氣）"""
        opp = opponent(color)
        best, best_n = None, 0
        for r, c in valid_moves:
            board.grid[r][c] = color
            n = 0
            for nr, nc in board.neighbors(r, c):
                if board.grid[nr][nc] == opp:
                    grp, libs = board.find_group(nr, nc)
                    if not libs:
                        n += len(grp)
            board.grid[r][c] = EMPTY
            if n > best_n:
                best_n = n
                best = (r, c)
        return best

    # ── 核心判斷：逃脫打吃 ────────────────────────────────────────────────────

    def _find_escape_move(self, board, color, valid_moves):
        """
        若己方有棋串只剩 1 口氣，找落子後能使該串氣數 ≥ 2 的手。
        優先選逃脫後氣數最多的（逃得越遠越好）。
        """
        visited = set()
        candidates = []
        for r in range(board.size):
            for c in range(board.size):
                if board.grid[r][c] == color and (r, c) not in visited:
                    grp, libs = board.find_group(r, c)
                    visited |= grp
                    if len(libs) == 1:
                        lib_r, lib_c = next(iter(libs))
                        if (lib_r, lib_c) not in valid_moves:
                            continue
                        # 模擬落子後的新氣數
                        board.grid[lib_r][lib_c] = color
                        _, new_libs = board.find_group(lib_r, lib_c)
                        board.grid[lib_r][lib_c] = EMPTY
                        if len(new_libs) >= 2:
                            candidates.append(((lib_r, lib_c), len(new_libs)))
        if candidates:
            candidates.sort(key=lambda x: -x[1])
            return candidates[0][0]
        return None

    # ── 核心判斷：威脅（逼入打吃）────────────────────────────────────────────

    def _find_threaten_move(self, board, color, valid_moves):
        """
        找落子後能把對手棋串逼入 1 口氣（下一手即可提子）的手。
        測試重點：學生是否能讀出「我下這裡，對方下一步要逃跑」。
        """
        opp = opponent(color)
        best, best_n = None, 0
        for r, c in valid_moves:
            board.grid[r][c] = color
            # 先模擬可能的立刻吃子
            captured = set()
            for nr, nc in board.neighbors(r, c):
                if board.grid[nr][nc] == opp:
                    grp, libs = board.find_group(nr, nc)
                    if not libs:
                        captured |= grp
            for cr, cc in captured:
                board.grid[cr][cc] = EMPTY

            # 計算落子後對手有多少棋串剩 1 口氣
            threatened = 0
            vis = set()
            for nr, nc in board.neighbors(r, c):
                if board.grid[nr][nc] == opp and (nr, nc) not in vis:
                    grp, libs = board.find_group(nr, nc)
                    vis |= grp
                    if len(libs) == 1:
                        threatened += len(grp)

            # 還原
            for cr, cc in captured:
                board.grid[cr][cc] = opp
            board.grid[r][c] = EMPTY

            if threatened > best_n:
                best_n = threatened
                best = (r, c)
        return best

    # ── 核心判斷：切斷 ────────────────────────────────────────────────────────

    def _find_cut_move(self, board, color, valid_moves):
        """
        找能切斷對手兩串棋子連絡的手。
        切點定義：落子後，周圍兩個以上屬於不同棋串的對手棋子無法互通。
        """
        opp = opponent(color)
        best_cut, best_score = None, 0
        for r, c in valid_moves:
            opp_adj = [(nr, nc) for nr, nc in board.neighbors(r, c)
                       if board.grid[nr][nc] == opp]
            if len(opp_adj) < 2:
                continue
            groups = []
            for nr, nc in opp_adj:
                grp, _ = board.find_group(nr, nc)
                if not any(grp & g for g in groups):
                    groups.append(grp)
            if len(groups) >= 2:
                score = sum(len(g) for g in groups)
                if score > best_score:
                    best_score = score
                    best_cut = (r, c)
        return best_cut

    # ── 輔助：避免自吃 ────────────────────────────────────────────────────────

    def _filter_safe(self, board, color, valid_moves):
        """過濾掉落子後己方棋串只剩 1 口氣的手，優先選安全手"""
        safe = []
        for r, c in valid_moves:
            board.grid[r][c] = color
            _, libs = board.find_group(r, c)
            board.grid[r][c] = EMPTY
            if len(libs) >= 2:
                safe.append((r, c))
        return random.choice(safe) if safe else random.choice(valid_moves)

    # ── 輔助：陷阱手過濾（10 級用）────────────────────────────────────────────

    def _filter_no_trap(self, board, color, valid_moves):
        """
        過濾掉走後對手只需一手就能把己方逼入打吃的手。
        3 步預讀：我走 → 對手佔我的氣 → 我剩 ≤1 口氣？
        只檢查己方新棋串的氣點（對手只能從氣點逼近），速度快。
        """
        opp = opponent(color)
        safe = []
        for r, c in valid_moves:
            board.grid[r][c] = color
            grp, libs = board.find_group(r, c)
            # 若落子後己方棋串本來就只剩 ≤1 氣，已是危險局面
            if len(libs) <= 1:
                board.grid[r][c] = EMPTY
                continue
            # 檢查對手佔每個氣點後，我的棋串會剩幾口氣
            dangerous = False
            for lr, lc in libs:
                valid_opp, _ = board.is_valid_move(lr, lc, opp)
                if not valid_opp:
                    continue
                board.grid[lr][lc] = opp
                _, libs_after = board.find_group(r, c)
                board.grid[lr][lc] = EMPTY
                if len(libs_after) <= 1:
                    dangerous = True
                    break
            board.grid[r][c] = EMPTY
            if not dangerous:
                safe.append((r, c))
        return safe

    # ── 8 級策略（地盤意識）────────────────────────────────────────────────────

    def _strategy_8(self, board, color, valid_moves):
        """
        8 級：加入地盤影響力評分
        1. 吃子
        2. 逃脫打吃
        3. 威脅
        4. 切斷
        5. 高地盤價值點
        6. 避免自吃
        """
        move = self._find_capture_move(board, color, valid_moves)
        if move:
            return move
        move = self._find_escape_move(board, color, valid_moves)
        if move:
            return move
        move = self._find_threaten_move(board, color, valid_moves)
        if move:
            return move
        move = self._find_cut_move(board, color, valid_moves)
        if move:
            return move

        # 搶佔星位 / 天元（開局優先）
        for pos in self._important_points():
            if pos in valid_moves:
                safe = self._filter_no_trap(board, color, [pos])
                if safe:
                    return pos

        # 接近對手棋子（搶地 / 逼近），再延伸己方
        best, best_val = None, -1e9
        for r, c in valid_moves:
            val = self._territory_value(board, r, c, color)
            if val > best_val:
                best_val = val
                best = (r, c)
        if best and best_val > 0:
            safe = self._filter_no_trap(board, color, [best])
            if safe:
                return best

        safe_moves = self._filter_no_trap(board, color, valid_moves)
        return self._filter_safe(board, color, safe_moves or valid_moves)

    def _territory_value(self, board, r, c, color):
        """
        落子 (r,c) 的戰略價值：
        - 接近對手棋子（距離 3-4）→ 高分（逼近/搶角）
        - 接近己方棋子（距離 2-3）→ 中分（延伸/連絡）
        - 空點本身不計分（避免 AI 包空自閉）
        """
        s = board.size
        opp = opponent(color)
        score = 0.0
        for dr in range(-5, 6):
            for dc in range(-5, 6):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < s and 0 <= nc < s):
                    continue
                dist = abs(dr) + abs(dc)
                if dist == 0 or dist > 5:
                    continue
                cell = board.grid[nr][nc]
                if cell == opp:
                    # 距離 3-4 = 逼近/入侵最佳距離
                    if dist == 3:
                        score += 4.0
                    elif dist == 4:
                        score += 2.5
                    elif dist == 2:
                        score += 1.5
                    elif dist == 5:
                        score += 0.5
                elif cell == color:
                    # 距離 2-3 = 延伸
                    if dist == 2:
                        score += 1.5
                    elif dist == 3:
                        score += 1.0
                    elif dist == 4:
                        score += 0.3
        return score

    # ── 5 級策略（2 步預讀）───────────────────────────────────────────────────

    def _sim(self, board, r, c, color):
        """模擬落子並提子，回傳被提走棋子列表（供 _unsim 還原）"""
        opp = opponent(color)
        board.grid[r][c] = color
        captured = []
        for nr, nc in board.neighbors(r, c):
            if board.grid[nr][nc] == opp:
                grp, libs = board.find_group(nr, nc)
                if not libs:
                    for cr, cc in grp:
                        board.grid[cr][cc] = EMPTY
                        captured.append((cr, cc, opp))
        return captured

    def _unsim(self, board, r, c, color, captured):
        """還原 _sim 所做的變更"""
        board.grid[r][c] = EMPTY
        for cr, cc, col in captured:
            board.grid[cr][cc] = col

    def _eval5(self, board, color):
        """
        快速局面評估（用於 2 步預讀終端節點）
        - 己方棋串氣數多 → 加分；打吃狀態 → 重扣
        - 簡單地盤計數
        """
        opp = opponent(color)
        score = 0
        visited_mine = set()
        visited_opp  = set()

        for r in range(board.size):
            for c in range(board.size):
                cell = board.grid[r][c]
                if cell == color and (r, c) not in visited_mine:
                    grp, libs = board.find_group(r, c)
                    visited_mine |= grp
                    n, l = len(grp), len(libs)
                    if l == 0:
                        score -= n * 20
                    elif l == 1:
                        score -= n * 4
                    else:
                        score += n * l
                elif cell == opp and (r, c) not in visited_opp:
                    grp, libs = board.find_group(r, c)
                    visited_opp |= grp
                    n, l = len(grp), len(libs)
                    if l == 0:
                        score += n * 20
                    elif l == 1:
                        score += n * 4
                    else:
                        score -= n

        # 簡易地盤估計（空點偏向）
        for r in range(board.size):
            for c in range(board.size):
                if board.grid[r][c] == EMPTY:
                    adj_mine = sum(
                        1 for nr, nc in board.neighbors(r, c)
                        if board.grid[nr][nc] == color
                    )
                    adj_opp = sum(
                        1 for nr, nc in board.neighbors(r, c)
                        if board.grid[nr][nc] == opp
                    )
                    if adj_mine > adj_opp:
                        score += 1
                    elif adj_opp > adj_mine:
                        score -= 1
        return score

    def _heuristic5(self, board, r, c, color):
        """5 級候選手快速評分（用於剪枝：取前 12 手）"""
        opp = opponent(color)
        h = 0
        board.grid[r][c] = color
        for nr, nc in board.neighbors(r, c):
            if board.grid[nr][nc] == opp:
                grp, libs = board.find_group(nr, nc)
                n = len(grp)
                if not libs:
                    h += n * 12       # 立刻吃子
                elif len(libs) == 1:
                    h += n * 4        # 威脅打吃
        board.grid[r][c] = EMPTY
        return h + self._territory_value(board, r, c, color)

    def _strategy_5(self, board, color, valid_moves):
        """
        5 級：2 步預讀（我走 → 對手最佳應手 → 評估局面）
        先按 _heuristic5 取前 12 候選手，對每手模擬後評分取最高。
        """
        # 先嘗試立刻吃子（直接勝手，無需預讀）
        move = self._find_capture_move(board, color, valid_moves)
        if move:
            return move

        # 開局搶星位（heuristic5 在空棋盤得分為 0，需先搶要點）
        for pos in self._important_points():
            if pos in valid_moves:
                safe = self._filter_no_trap(board, color, [pos])
                if safe:
                    return pos

        # 候選手剪枝
        scored = [
            (self._heuristic5(board, r, c, color), r, c)
            for r, c in valid_moves
        ]
        scored.sort(reverse=True)
        candidates = [(r, c) for _, r, c in scored[:12]]

        opp = opponent(color)
        best_move, best_score = None, float('-inf')

        for r, c in candidates:
            cap1 = self._sim(board, r, c, color)

            # 對手使用 strategy_15 邏輯找最佳應手
            opp_moves = self._get_valid_moves(board, opp)
            opp_move = None
            if opp_moves:
                opp_move = (
                    self._find_capture_move(board, opp, opp_moves) or
                    self._find_escape_move(board,  opp, opp_moves) or
                    self._find_threaten_move(board, opp, opp_moves)
                )
                if not opp_move:
                    opp_scored = [
                        (self._heuristic5(board, or_, oc, opp), or_, oc)
                        for or_, oc in opp_moves
                    ]
                    opp_scored.sort(reverse=True)
                    if opp_scored:
                        _, or_, oc = opp_scored[0]
                        opp_move = (or_, oc)

            cap2 = None
            if opp_move:
                cap2 = self._sim(board, opp_move[0], opp_move[1], opp)

            sc = self._eval5(board, color)

            # 還原
            if opp_move and cap2 is not None:
                self._unsim(board, opp_move[0], opp_move[1], opp, cap2)
            self._unsim(board, r, c, color, cap1)

            if sc > best_score:
                best_score = sc
                best_move = (r, c)

        return best_move or self._filter_safe(board, color, valid_moves)

    # ── 重要點 ────────────────────────────────────────────────────────────────

    def _important_points(self):
        """天元與星位（依重要性排序）"""
        s = self.board_size
        c = s // 2
        if s == 19:
            edges = [3, 9, 15]
        elif s == 13:
            edges = [3, 6, 9]
        else:
            edges = [s // 4, c, s - 1 - s // 4]
        pts = [(c, c)]
        for er in edges:
            for ec in edges:
                if (er, ec) != (c, c):
                    pts.append((er, ec))
        return pts

    # ── 玩家手評價 ────────────────────────────────────────────────────────────

    def evaluate_move(self, board, row, col, color):
        """
        評價玩家剛落的手品質。stone 已由 place_stone 放好。
        """
        opp = opponent(color)

        # 1. 有吃子
        for nr, nc in board.neighbors(row, col):
            if board.grid[nr][nc] == opp:
                grp, libs = board.find_group(nr, nc)
                if not libs and len(grp) >= 1:
                    return "這步很棒！"

        # 2. 佔天元或星位
        if (row, col) in self._important_points()[:5]:
            return "這步很棒！"

        # 3. 把對手棋串逼入打吃（1 口氣）
        for nr, nc in board.neighbors(row, col):
            if board.grid[nr][nc] == opp:
                _, libs = board.find_group(nr, nc)
                if len(libs) == 1:
                    return "這步很棒！"

        # 4. 切斷對手（周圍有兩個以上不同對手棋串）
        opp_adj = [(nr, nc) for nr, nc in board.neighbors(row, col)
                   if board.grid[nr][nc] == opp]
        if len(opp_adj) >= 2:
            groups = []
            for nr, nc in opp_adj:
                grp, _ = board.find_group(nr, nc)
                if not any(grp & g for g in groups):
                    groups.append(grp)
            if len(groups) >= 2:
                return "這步很棒！"

        return "下得不錯。"
