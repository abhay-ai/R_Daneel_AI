import lichess_bot
import time

def run_tests():
    print("=== Testing Qwen 2.5 7B chess logic on various positions ===")
    model_name = "Qwen/Qwen2.5-7B-Instruct"
    
    # Position 1: Hanging piece
    # White to move. Black's knight on e4 is undefended. White queen on d1 can capture it, or white knight on c3.
    # FEN: r1bqkb1r/pppp1ppp/2n5/8/4n3/2N1P3/PPPP1PPP/R1BQKBNR w KQkq - 0 1
    fen1 = "r1bqkb1r/pppp1ppp/2n5/8/4n3/2N1P3/PPPP1PPP/R1BQKBNR w KQkq - 0 1"
    print(f"\n--- Position 1: Hanging Piece (FEN: {fen1}) ---")
    start = time.time()
    move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(fen1, model_name, current_strategy="Capture hanging pieces and develop.")
    print(f"Proposed Move: {move}")
    print(f"Retries: {retries}")
    print(f"Time: {time.time() - start:.2f}s")
    print(f"Thoughts:\n{thoughts}\n")
    
    # Position 2: Starting position
    fen2 = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    print(f"\n--- Position 2: Starting Position (FEN: {fen2}) ---")
    start = time.time()
    move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(fen2, model_name, current_strategy="Control the center and develop minor pieces.")
    print(f"Proposed Move: {move}")
    print(f"Retries: {retries}")
    print(f"Time: {time.time() - start:.2f}s")
    print(f"Thoughts:\n{thoughts}\n")

if __name__ == "__main__":
    run_tests()
