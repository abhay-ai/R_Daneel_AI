import json
import chess

moves = []
with open("logs/game_X7nYMAhR.jsonl") as f:
    for line in f:
        data = json.loads(line)
        moves.append(data["move"])

print("Moves in log:", moves)

board = chess.Board()
for idx, m in enumerate(moves):
    # Determine whose turn it is
    color = "White" if board.turn == chess.WHITE else "Black"
    try:
        # Find the move in legal moves or parse uci/san
        parsed_move = None
        try:
            parsed_move = board.parse_san(m)
        except Exception:
            try:
                parsed_move = board.parse_uci(m)
            except Exception:
                pass
        
        if parsed_move:
            board.push(parsed_move)
            print(f"Move {idx+1} ({color}): {m} -> FEN: {board.fen()}")
        else:
            print(f"Failed to parse move {idx+1} ({color}): {m}")
            break
    except Exception as e:
        print(f"Error pushing move {idx+1} ({color}) {m}: {e}")
        break
