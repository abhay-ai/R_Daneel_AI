import lichess_bot
import time
import json
import os

# List of 30 benchmark chess puzzles of varying difficulty ratings (600 to 1500 Elo)
# 3 puzzles per rating tier to reduce variance and compute a statistically sound rating
PUZZLES = [
    # --- 600 Elo ---
    {
        "id": 1,
        "name": "Back Rank Mate-in-1",
        "rating": 600,
        "fen": "6k1/5ppp/8/8/8/8/8/3R2K1 w - - 0 1",
        "best_moves": ["d1d8"],
        "desc": "White rook to d8 delivers immediate checkmate on the back rank."
    },
    {
        "id": 2,
        "name": "Scholar's Mate-in-1",
        "rating": 600,
        "fen": "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
        "best_moves": ["f3f7"],
        "desc": "White Queen captures on f7 to deliver Scholar's mate."
    },
    {
        "id": 3,
        "name": "Fool's Mate-in-1",
        "rating": 600,
        "fen": "rnbqkbnr/ppppp2p/5p2/6p1/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3",
        "best_moves": ["d1h5"],
        "desc": "White Queen moves to h5 delivering checkmate."
    },
    # --- 700 Elo ---
    {
        "id": 4,
        "name": "Capture Undefended Queen",
        "rating": 700,
        "fen": "k7/8/8/8/8/8/q7/1Q4K1 w - - 0 1",
        "best_moves": ["b1a2"],
        "desc": "White Queen captures Black's hanging Queen on a2."
    },
    {
        "id": 5,
        "name": "Capture Hanging Knight",
        "rating": 700,
        "fen": "k7/8/8/8/8/5n2/6K1/8 w - - 0 1",
        "best_moves": ["g2f3"],
        "desc": "White King captures the undefended Black Knight on f3."
    },
    {
        "id": 6,
        "name": "Capture Hanging Rook",
        "rating": 700,
        "fen": "k7/8/8/8/8/8/r7/R5K1 w - - 0 1",
        "best_moves": ["a1a2"],
        "desc": "White Rook captures the undefended Black Rook on a2."
    },
    # --- 800 Elo ---
    {
        "id": 7,
        "name": "Knight Fork on c7",
        "rating": 800,
        "fen": "k3q3/8/8/3N4/8/8/4P3/4K3 w - - 0 1",
        "best_moves": ["d5c7"],
        "desc": "Knight to c7 forks the King on a8 and the Queen on e8."
    },
    {
        "id": 8,
        "name": "Pawn Fork Attack",
        "rating": 800,
        "fen": "k7/8/8/2b1n3/8/3P4/8/3R2K1 w - - 0 1",
        "best_moves": ["d3d4"],
        "desc": "Pawn advances to d4, forking the Bishop on c5 and Knight on e5."
    },
    {
        "id": 9,
        "name": "Bishop Fork with Check",
        "rating": 800,
        "fen": "7k/8/1r6/8/8/2B5/8/6K1 w - - 0 1",
        "best_moves": ["c3d4"],
        "desc": "Bishop moves to d4, checking the King on h8 and attacking the Rook on b6."
    },
    # --- 900 Elo ---
    {
        "id": 10,
        "name": "Capture Pinned Queen",
        "rating": 900,
        "fen": "3k4/8/8/3q4/8/8/3R4/4K3 w - - 0 1",
        "best_moves": ["d2d5"],
        "desc": "White rook captures Black's Queen on d5, which is pinned to the King on d8."
    },
    {
        "id": 11,
        "name": "Pinning Black Rook",
        "rating": 900,
        "fen": "7k/8/8/8/3r4/8/8/2B3K1 w - - 0 1",
        "best_moves": ["c1b2"],
        "desc": "Bishop to b2 pins the Black Rook on d4 to the King on h8."
    },
    {
        "id": 12,
        "name": "Pinning Black Queen",
        "rating": 900,
        "fen": "4k3/8/8/4q3/8/8/8/3R2K1 w - - 0 1",
        "best_moves": ["d1e1"],
        "desc": "Rook to e1 pins the Black Queen on e5 to the King on e8."
    },
    # --- 1000 Elo ---
    {
        "id": 13,
        "name": "Decoy Back Rank Mate",
        "rating": 1000,
        "fen": "3r2k1/5ppp/8/8/8/8/3Q2PP/6K1 w - - 0 1",
        "best_moves": ["d2d8"],
        "desc": "White Queen captures on d8 for a back rank mate."
    },
    {
        "id": 14,
        "name": "Trap the Knight",
        "rating": 1000,
        "fen": "k7/8/8/8/8/8/8/n1B3K1 w - - 0 1",
        "best_moves": ["c1b2"],
        "desc": "Bishop to b2 attacks the Knight on a1, which has no legal escape squares."
    },
    {
        "id": 15,
        "name": "Defend Mate on Back Rank",
        "rating": 1000,
        "fen": "6k1/5ppp/8/8/8/8/5rPP/3R2K1 w - - 0 1",
        "best_moves": ["d1d8"],
        "desc": "Rather than defending, White can checkmate Black on the back rank first."
    },
    # --- 1100 Elo ---
    {
        "id": 16,
        "name": "Discovered Check on Queen",
        "rating": 1100,
        "fen": "3k4/8/3q4/8/8/8/3B4/3R3K w - - 0 1",
        "best_moves": ["d2g5"],
        "desc": "Bishop to g5 discovers an attack from the Rook on d1 to the Queen on d6, while checking the King."
    },
    {
        "id": 17,
        "name": "Discovered Check on Rook",
        "rating": 1100,
        "fen": "3k4/8/3r4/8/8/8/3B4/3R3K w - - 0 1",
        "best_moves": ["d2g5"],
        "desc": "Bishop to g5 discovers an attack on the Rook on d6, while checking the King on d8."
    },
    {
        "id": 18,
        "name": "Counter-Checkmate (Mate-in-1)",
        "rating": 1100,
        "fen": "6k1/5ppp/8/8/8/8/5qPP/4R2K w - - 0 1",
        "best_moves": ["e1e8"],
        "desc": "White Rook to e8 checkmates Black before Black can execute their own mate threats."
    },
    # --- 1200 Elo ---
    {
        "id": 19,
        "name": "Pawn Promotion to Queen",
        "rating": 1200,
        "fen": "3k4/P7/8/8/8/8/8/6K1 w - - 0 1",
        "best_moves": ["a7a8q"],
        "desc": "White advances pawn to a8 to promote to a Queen, winning the game."
    },
    {
        "id": 20,
        "name": "Under-Promotion to Knight Fork",
        "rating": 1200,
        "fen": "8/2P1k3/1q6/8/8/8/8/7K w - - 0 1",
        "best_moves": ["c7c8n"],
        "desc": "Promoting to a Knight on c8 checks the King on e7 and forks the Queen on b6."
    },
    {
        "id": 21,
        "name": "Promotion to win a Rook",
        "rating": 1200,
        "fen": "3r4/P7/8/8/8/8/8/6K1 w - - 0 1",
        "best_moves": ["a7a8q"],
        "desc": "Promoting to a Queen on a8 attacks/deflects the Rook on d8."
    },
    # --- 1300 Elo ---
    {
        "id": 22,
        "name": "Staircase Mate Setup (Mate-in-2)",
        "rating": 1300,
        "fen": "k7/8/8/8/8/7R/7R/K7 w - - 0 1",
        "best_moves": ["h3b3", "h2b2"],
        "desc": "Staircase checkmate setup. Moving one of the Rooks to the b-file restricts Black's King to the a-file."
    },
    {
        "id": 23,
        "name": "Forced Mate-in-2 Back Rank",
        "rating": 1300,
        "fen": "6k1/5qpp/8/8/8/8/5PPP/3R2K1 w - - 0 1",
        "best_moves": ["d1d8"],
        "desc": "Rook d1-d8+ forces Queen block f7-e8, followed by Rook takes Queen checkmate."
    },
    {
        "id": 24,
        "name": "Smothered Mate-in-2",
        "rating": 1300,
        "fen": "r4r1k/5Qpp/7N/8/8/8/8/6K1 w - - 0 1",
        "best_moves": ["f7g8"],
        "desc": "Queen sacrifice g8+ forces Rook to capture f8xg8, leaving the King smothered for Knight f7#."
    },
    # --- 1400 Elo ---
    {
        "id": 25,
        "name": "Knight Fork on e7",
        "rating": 1400,
        "fen": "2r3k1/1p3ppp/p7/3N4/8/8/PP3PPP/6K1 w - - 0 1",
        "best_moves": ["d5e7"],
        "desc": "Knight to e7 checks the King on g8 and forks the Rook on c8."
    },
    {
        "id": 26,
        "name": "Decoy Discovered Attack",
        "rating": 1400,
        "fen": "r1b2rk1/pp3ppp/2n5/3q4/8/3B1N2/PP3PPP/R2Q1RK1 w - - 0 1",
        "best_moves": ["d3h7"],
        "desc": "Bishop sacrifice on h7 checks the King, deflecting it to win the Queen on d5."
    },
    {
        "id": 27,
        "name": "Simple Back Rank Deflection",
        "rating": 1400,
        "fen": "r1r3k1/5ppp/2Q5/8/8/8/5PPP/2R3K1 w - - 0 1",
        "best_moves": ["c6c8"],
        "desc": "Queen captures the rook on c8, deflecting the back rank defender to win material."
    },
    # --- 1500 Elo ---
    {
        "id": 28,
        "name": "Deflection to Win Bishop",
        "rating": 1500,
        "fen": "r4rk1/pp3ppp/2n5/2bQ4/8/3B1N2/PP3PPP/R4RK1 w - - 0 1",
        "best_moves": ["d3h7", "d5c5"],
        "desc": "Bishop sacrifice on h7 checks the King, deflecting it to win the Bishop on c5. Direct capture is also accepted."
    },
    {
        "id": 29,
        "name": "Knight Fork on Queen",
        "rating": 1500,
        "fen": "2r3k1/5ppp/p1q5/3N4/8/8/PP3PPP/3R2K1 w - - 0 1",
        "best_moves": ["d5e7"],
        "desc": "Knight to e7 checks the King on g8 and forks the Queen on c6."
    },
    {
        "id": 30,
        "name": "Greek Gift Sacrifice Setup",
        "rating": 1500,
        "fen": "r1bq1rk1/pppnbppp/4pn2/3p2B1/3P4/2NBPN2/PPP2PPP/R2QK2R w KQ - 3 6",
        "best_moves": ["d3h7"],
        "desc": "Bishop sacrifice on h7 is the classic Greek Gift that cracks open the Black King's defenses."
    }
]

def run_puzzle_benchmark():
    print("====================================================")
    print("      CHESS BOT PUZZLE ELO BENCHMARK SUITE")
    print("====================================================")
    
    model_name = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
    print(f"Model under test: {model_name}\n")
    
    results = []
    
    for idx, puzzle in enumerate(PUZZLES):
        print(f"\n--- [Puzzle {idx+1}/{len(PUZZLES)}] {puzzle['name']} (Est. Rating: {puzzle['rating']}) ---")
        print(f"FEN: {puzzle['fen']}")
        print(f"Target Moves: {', '.join(puzzle['best_moves'])}")
        
        start_time = time.time()
        # Call get_legal_llm_move. Since this is a one-shot puzzle position, we don't supply previous moves.
        move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(
            puzzle["fen"],
            model_name=model_name,
            current_strategy="Analyze the tactical board layout and select the best move."
        )
        elapsed = time.time() - start_time
        
        success = move in puzzle["best_moves"]
        status_str = "✅ PASSED" if success else f"❌ FAILED (Played: {move})"
        
        print(f"Proposed Move: {move} | Retries: {retries} | Time: {elapsed:.2f}s")
        print(f"Status: {status_str}")
        
        results.append({
            "name": puzzle["name"],
            "rating": puzzle["rating"],
            "success": success,
            "played": move,
            "targets": puzzle["best_moves"],
            "time": elapsed
        })
        
    print("\n====================================================")
    print("                  BENCHMARK SUMMARY")
    print("====================================================")
    
    total_passed = sum(1 for r in results if r["success"])
    total_puzzles = len(results)
    pass_rate = (total_passed / total_puzzles) * 100
    
    print(f"Overall Score: {total_passed}/{total_puzzles} ({pass_rate:.1f}% Pass Rate)\n")
    
    print(f"{'Puzzle Name':<30} | {'Rating':<6} | {'Status':<8} | {'Played':<6} | {'Time (s)':<8}")
    print("-" * 70)
    for r in results:
        status_str = "PASS" if r["success"] else "FAIL"
        print(f"{r['name']:<30} | {r['rating']:<6} | {status_str:<8} | {str(r['played']):<6} | {r['time']:<8.2f}")
        
    # Calculate Expected Score Matching Elo
    # Solve for ELO where expected score sum equals total passed
    def expected_score(elo):
        return sum(1.0 / (1.0 + 10.0 ** ((r["rating"] - elo) / 400.0)) for r in results)

    # Simple bisection solver (handles 0 to 3000 Elo bounds)
    low, high = 0.0, 3000.0
    for _ in range(100):
        mid = (low + high) / 2
        val = expected_score(mid)
        if val < total_passed:
            low = mid
        else:
            high = mid
    
    # Boundary check for 0 or 100% pass rates
    if total_passed == 0:
        estimated_elo = 0
    elif total_passed == total_puzzles:
        estimated_elo = 2000
    else:
        estimated_elo = int(mid)
        
    print(f"\nEstimated Puzzle Rating (Expected Score Matching): ~{estimated_elo} Rating")
    
    # Save results to log file
    os.makedirs("logs", exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join("logs", f"puzzle_benchmark_{timestamp}.json")
    benchmark_data = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "model_name": model_name,
        "total_passed": total_passed,
        "total_puzzles": total_puzzles,
        "pass_rate": pass_rate,
        "estimated_elo": estimated_elo,
        "results": results
    }
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(benchmark_data, f, indent=4)
    print(f"Results successfully logged to: {log_file}")
    print("====================================================")

if __name__ == "__main__":
    run_puzzle_benchmark()
