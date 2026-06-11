import os
import sys
import time
import json
import chess
import queen as prolog_referee
import test_puzzles
from lichess_bot import sort_legal_moves

def run_queen_only_benchmark():
    print("====================================================")
    print("   CHESS BOT BASELINE (QUEEN-ONLY) ELO BENCHMARK")
    print("====================================================")
    
    results = []
    
    for idx, puzzle in enumerate(test_puzzles.PUZZLES):
        print(f"\n--- [Puzzle {idx+1}/{len(test_puzzles.PUZZLES)}] {puzzle['name']} (Est. Rating: {puzzle['rating']}) ---")
        print(f"FEN: {puzzle['fen']}")
        print(f"Target Moves: {', '.join(puzzle['best_moves'])}")
        
        start_time = time.time()
        
        # Get starting FEN data and legal moves using the referee
        start_summary = prolog_referee.get_tactical_summary(puzzle["fen"])
        legal_moves = prolog_referee.get_legal_moves(puzzle["fen"])
        
        # Select the first move from the sorted list
        sorted_moves = sort_legal_moves(legal_moves, puzzle["fen"], start_summary)
        chosen_move = sorted_moves[0] if sorted_moves else None
        
        elapsed = time.time() - start_time
        
        success = chosen_move in puzzle["best_moves"]
        status_str = "✅ PASSED" if success else f"❌ FAILED (Played: {chosen_move})"
        
        print(f"Proposed Move: {chosen_move} | Time: {elapsed:.4f}s")
        print(f"Status: {status_str}")
        
        results.append({
            "name": puzzle["name"],
            "rating": puzzle["rating"],
            "success": success,
            "played": chosen_move,
            "targets": puzzle["best_moves"],
            "time": elapsed
        })
        
    print("\n====================================================")
    print("             QUEEN-ONLY BENCHMARK SUMMARY")
    print("====================================================")
    
    total_passed = sum(1 for r in results if r["success"])
    total_puzzles = len(results)
    pass_rate = (total_passed / total_puzzles) * 100
    
    print(f"Overall Score: {total_passed}/{total_puzzles} ({pass_rate:.1f}% Pass Rate)\n")
    
    print(f"{'Puzzle Name':<30} | {'Rating':<6} | {'Status':<8} | {'Played':<6} | {'Time (s)':<8}")
    print("-" * 70)
    for r in results:
        status_str = "PASS" if r["success"] else "FAIL"
        print(f"{r['name']:<30} | {r['rating']:<6} | {status_str:<8} | {str(r['played']):<6} | {r['time']:<8.4f}")
        
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
        
    print(f"\nEstimated Queen-Only Baseline Tactical Elo (Expected Score Matching): ~{estimated_elo} Elo")
    
    # Save results to log file
    os.makedirs("logs", exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join("logs", f"puzzle_benchmark_queen_only_{timestamp}.json")
    benchmark_data = {
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "model_name": "Queen-Only Heuristics (No LLM)",
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
    run_queen_only_benchmark()
