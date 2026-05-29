import queen as prolog_referee
import lichess_bot
import chess
import time

def test_tension_logic():
    print("=== Testing Tension Points Detection Logic ===")
    
    # Position 1: Sicilian Defense after 3. d4 (c5 and d4 are in pawn tension)
    fen_sicilian = "r1bqkbnr/pp1ppppp/2n5/2p5/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3"
    tensions = prolog_referee.get_tension_points(fen_sicilian)
    print(f"Sicilian 3.d4 FEN: {fen_sicilian}")
    print(f"Detected Tensions: {tensions}")
    
    # We expect a pawn tension between c5 and d4
    assert "pawns at d4 and c5" in tensions["pawn_tension"], "Failed to detect pawn tension on d4/c5"
    print("✅ Pawn tension detection verified successfully.")
    
    # Position 2: Knights attacking each other mutually
    # White Knight on d4 and Black Knight on c6
    fen_knights = "r1bqkbnr/ppp2ppp/2n5/3pP3/3N4/8/PPP2PPP/RNBQKB1R w KQkq - 0 5"
    tensions_knights = prolog_referee.get_tension_points(fen_knights)
    print(f"Knight mutual attack FEN: {fen_knights}")
    print(f"Detected Tensions: {tensions_knights}")
    
    # We expect a knight mutual tension between d4 and c6
    assert any("knight" in t and "d4" in t and "c6" in t for t in tensions_knights["mutual_piece_tension"]), "Failed to detect knight mutual tension on d4/c6"
    print("✅ Mutual piece tension detection verified successfully.")

    # Position 3: Check get_positional_evaluation integration
    pos_eval = prolog_referee.get_positional_evaluation(fen_sicilian)
    print(f"Positional Evaluation Output: {pos_eval}")
    assert "board_tension" in pos_eval, "Positional evaluation dict is missing board_tension key"
    assert pos_eval["board_tension"]["pawn_tension"] == ["pawns at d4 and c5"], "Unexpected pawn tension content"
    print("✅ Positional evaluation integration verified successfully.")

def test_llm_tension_reasoning():
    print("\n=== Testing LLM Positional Tension Reasoning ===")
    
    # Giuoco Piano FEN with mutual bishop tension between e3 and c5 (material is equal)
    tension_fen = "r1bqk2r/ppp2ppp/2np1n2/2b1p3/4P3/2N1BN2/PPP2PPP/R2QKB1R w KQkq - 2 6"
    model_name = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
    
    print(f"Position FEN: {tension_fen}")
    print("Detected Tensions in this FEN:")
    print(prolog_referee.get_tension_points(tension_fen))
    
    print("Starting LLM move generation to check tension reasoning...")
    start_time = time.time()
    move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(
        tension_fen,
        model_name,
        current_strategy="Develop minor pieces and control the center."
    )
    elapsed = time.time() - start_time
    
    print("\n=== LLM Output ===")
    print(f"Proposed Move: {move}")
    print(f"Retries: {retries}")
    print(f"Time Taken: {elapsed:.2f} seconds")
    print(f"Thoughts:\n{thoughts}")
    print(f"Strategy: {strategy}")
    
    # Bxc5 in UCI is e3c5
    assert move != "e3c5", "❌ FAILED: LLM played the premature capture e3c5, resolving tension in Black's favor!"
    print("✅ SUCCESS: LLM successfully avoided the premature capture e3c5 and maintained the board tension.")

if __name__ == "__main__":
    try:
        test_tension_logic()
        test_llm_tension_reasoning()
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import sys
        sys.exit(1)
