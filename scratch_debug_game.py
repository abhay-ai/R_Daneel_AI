import chess

moves = ["e2e4", "g1f3", "b1c3", "a2a3", "c3b5", "f1d3", "d6", "b5c7", "Kd8", "Nxa8", "d5", "exd5"]
# Let's see what the FENs are for these moves
board = chess.Board()
for idx, m in enumerate(moves, start=1):
    try:
        board.push_uci(m)
        print(f"Move {idx}: {m} -> FEN: {board.fen()}")
    except Exception as e:
        print(f"Error at move {idx} ({m}): {e}")
