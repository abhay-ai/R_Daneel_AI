import lichess_bot
import time
import chess

def run_defeatism_test():
    print("=== Testing local vLLM Defeatism / Resilient Play ===")
    
    # Lost endgame FEN: White King on c1, Black rooks on a2 and h2.
    # If White plays a4b5 or a4a5, Black has mate-in-one (a2a1# or h2h1#).
    # White King must move to b1 or d1 to escape immediate checkmate.
    lost_fen = "8/5kp1/p7/1p5p/PP5P/8/r6r/2K5 w - - 1 46"
    model_name = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
    
    print(f"Position FEN: {lost_fen}")
    print(f"Model Name: {model_name}")
    print("Starting LLM move generation loop...")
    
    start_time = time.time()
    initial_strategy = "Seek drawing chances or stalemate tricks in this lost position. Defend actively."
    move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(
        lost_fen, 
        model_name, 
        current_strategy=initial_strategy
    )
    elapsed = time.time() - start_time
    
    print("\n=== Test Results ===")
    print(f"Proposed Move: {move}")
    print(f"Number of Retries: {retries}")
    print(f"Time Taken: {elapsed:.2f} seconds")
    print(f"Captured Strategy: {strategy}")
    print(f"Captured Thoughts:\n{thoughts}")
    
    # Validate legality
    board = chess.Board(lost_fen)
    try:
        chess_move = board.parse_uci(move)
        is_legal = chess_move in board.legal_moves
    except Exception:
        is_legal = False
        
    print(f"Is Move Legal: {is_legal}")
    
    # Check if White escaped mate-in-one
    mate_in_one_moves = ["a4b5", "a4a5"]
    if move in mate_in_one_moves:
        print("❌ FAILED: LLM played a move that allows mate-in-one!")
        assert False, "Played a losing blunder permitting mate-in-one."
    else:
        print("✅ SUCCESS: LLM successfully avoided the immediate mate-in-one by moving the King.")
        
    assert is_legal, "LLM proposed an illegal move"
    print("✅ All assertions passed successfully.")

if __name__ == "__main__":
    try:
        run_defeatism_test()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import sys
        sys.exit(1)
