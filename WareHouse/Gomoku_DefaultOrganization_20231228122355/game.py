'''
The game logic for the Gomoku game.
'''
class GomokuGame:
    def __init__(self):
        self.board = [[0] * 15 for _ in range(15)]  # 15x15 game board
        self.current_player = 1  # Player 1 starts the game
    def make_move(self, row, col):
        # Check if the move is valid
        if self.board[row][col] == 0:
            # Make the move
            self.board[row][col] = self.current_player
            # Check for a winning move
            if self.check_win(row, col):
                return self.current_player
            # Switch to the next player
            self.current_player = 2 if self.current_player == 1 else 1
        return None
    def check_win(self, row, col):
        # Check for a horizontal win
        count = 1
        for i in range(col - 1, -1, -1):
            if self.board[row][i] == self.current_player:
                count += 1
            else:
                break
        for i in range(col + 1, 15):
            if self.board[row][i] == self.current_player:
                count += 1
            else:
                break
        if count >= 5:
            return True
        # Check for a vertical win
        count = 1
        for i in range(row - 1, -1, -1):
            if self.board[i][col] == self.current_player:
                count += 1
            else:
                break
        for i in range(row + 1, 15):
            if self.board[i][col] == self.current_player:
                count += 1
            else:
                break
        if count >= 5:
            return True
        # Check for a diagonal win (top-left to bottom-right)
        count = 1
        i, j = row - 1, col - 1
        while i >= 0 and j >= 0:
            if self.board[i][j] == self.current_player:
                count += 1
            else:
                break
            i -= 1
            j -= 1
        i, j = row + 1, col + 1
        while i < 15 and j < 15:
            if self.board[i][j] == self.current_player:
                count += 1
            else:
                break
            i += 1
            j += 1
        if count >= 5:
            return True
        # Check for a diagonal win (top-right to bottom-left)
        count = 1
        i, j = row - 1, col + 1
        while i >= 0 and j < 15:
            if self.board[i][j] == self.current_player:
                count += 1
            else:
                break
            i -= 1
            j += 1
        i, j = row + 1, col - 1
        while i < 15 and j >= 0:
            if self.board[i][j] == self.current_player:
                count += 1
            else:
                break
            i += 1
            j -= 1
        if count >= 5:
            return True
        return False