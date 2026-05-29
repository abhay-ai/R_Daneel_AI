import lichess_bot
import time

def run_tool_calling_test():
    print("=== Testing local vLLM Tool-Calling Loop ===")
    
    # Let's test with a tactical FEN: Knight fork candidate
    # White Knight on d5 can move to c7 to fork black king on a8 and queen on e8.
    # Check from queen is blocked by white pawn on e2.
    fork_fen = "k3q3/8/8/3N4/8/8/4P3/4K3 w - - 0 1"
    model_name = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
    
    print(f"Position FEN: {fork_fen}")
    print(f"Model Name: {model_name}")
    print("Starting LLM move generation loop with tool support...")
    
    start_time = time.time()
    initial_strategy = "Formulate a strong knight fork on c7 to win the black queen."
    move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(fork_fen, model_name, current_strategy=initial_strategy)
    elapsed = time.time() - start_time
    
    print("\n=== Test Results (Move 1) ===")
    print(f"Proposed Move: {move}")
    print(f"Number of Retries (Prolog Rejections): {retries}")
    print(f"Time Taken: {elapsed:.2f} seconds")
    print(f"Captured Strategy: {strategy}")
    print(f"Captured Thoughts:\n{thoughts}")
    
    assert move is not None, "Failed to get move from LLM"
    
    # Test CSV and JSON logging
    print("\nWriting test run metrics to logs...")
    lichess_bot.log_experiment_data("test_game_123", 1, fork_fen, retries, elapsed, model_name, thoughts, strategy)
    lichess_bot.log_experiment_data_json("test_game_123", 1, fork_fen, move, retries, elapsed, model_name, thoughts, strategy)
    
    # Now simulate a second move to verify strategy adaptation
    print("\n=== Simulating Move 2 (Strategy Adaptation Check) ===")
    import chess
    board = chess.Board(fork_fen)
    board.push_uci(move)
    resulting_fen = board.fen()
    print(f"Resulting FEN after move 1: {resulting_fen}")
    
    start_time2 = time.time()
    move2, retries2, thoughts2, strategy2 = lichess_bot.get_legal_llm_move(resulting_fen, model_name, current_strategy=strategy)
    elapsed2 = time.time() - start_time2
    
    print("\n=== Test Results (Move 2) ===")
    print(f"Proposed Move: {move2}")
    print(f"Number of Retries (Prolog Rejections): {retries2}")
    print(f"Time Taken: {elapsed2:.2f} seconds")
    print(f"Captured Strategy: {strategy2}")
    
    lichess_bot.log_experiment_data("test_game_123", 2, resulting_fen, retries2, elapsed2, model_name, thoughts2, strategy2)
    lichess_bot.log_experiment_data_json("test_game_123", 2, resulting_fen, move2, retries2, elapsed2, model_name, thoughts2, strategy2)
    
    print(f"Test completed successfully. LLM proposed moves: {move} followed by {move2}")

if __name__ == "__main__":
    try:
        run_tool_calling_test()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import sys
        sys.exit(1)
