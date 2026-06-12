import os
import sys
import time
import json
import random
import chess
import queen as prolog_referee
from lichess_bot import sort_legal_moves
from test_large_scale import calculate_expected_score_elo

def run_queen_only_500():
    # Load all Lichess puzzles
    puzzles_file = "logs/lichess_1000_puzzles.json"
    if not os.path.exists(puzzles_file):
        print(f"Error: {puzzles_file} not found. Run filter_puzzles.py first.")
        sys.exit(1)
        
    with open(puzzles_file, "r") as f:
        all_puzzles = json.load(f)
        
    # Group puzzles by 100-Elo tiers (600 to 1500)
    tiers = {r: [] for r in range(600, 1600, 100)}
    for p in all_puzzles:
        tier = (p["rating"] // 100) * 100
        if tier in tiers:
            tiers[tier].append(p)
            
    # Sample from each tier using seed 42 (matching test_large_scale.py default)
    random.seed(42)
    puzzles_per_tier = 50
    sampled_puzzles = []
    for tier, p_list in sorted(tiers.items()):
        if len(p_list) < puzzles_per_tier:
            sampled = p_list
        else:
            sampled = random.sample(p_list, puzzles_per_tier)
        sampled_puzzles.extend(sampled)
        
    # Sort sampled puzzles by rating
    sampled_puzzles.sort(key=lambda x: x["rating"])
    total_puzzles = len(sampled_puzzles)
    print(f"Sampled {total_puzzles} puzzles (50 per tier, seed=42) for Queen-only baseline.", flush=True)
    
    checkpoint_file = "logs/large_scale_checkpoint_queen_only_500.json"
    report_file = "logs/large_scale_report_queen_only_500.json"
    
    # Check if checkpoint exists
    completed_results = []
    completed_ids = set()
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)
                completed_results = checkpoint_data.get("results", [])
                completed_ids = {r["id"] for r in completed_results}
                print(f"Resuming from checkpoint. Loaded {len(completed_results)} completed puzzles.", flush=True)
        except Exception as e:
            print(f"Warning: Could not load checkpoint file ({e}). Starting fresh.", flush=True)
            
    remaining_puzzles = [p for p in sampled_puzzles if p["id"] not in completed_ids]
    print(f"Puzzles remaining to process: {len(remaining_puzzles)}", flush=True)
    
    for idx, puzzle in enumerate(remaining_puzzles):
        curr_idx = len(completed_results) + 1
        print(f"\n--- [Puzzle {curr_idx}/{total_puzzles}] {puzzle['name']} (Rating: {puzzle['rating']}) --- FEN: {puzzle['fen']}", flush=True)
        
        start_time = time.time()
        
        try:
            # Note: include_mate_in_three defaults to False, speeding this up greatly
            start_summary = prolog_referee.get_tactical_summary(puzzle["fen"])
            legal_moves = prolog_referee.get_legal_moves(puzzle["fen"])
            
            # Select the first move from the sorted list
            sorted_moves = sort_legal_moves(legal_moves, puzzle["fen"], start_summary)
            chosen_move = sorted_moves[0] if sorted_moves else None
        except Exception as e:
            print(f"Error executing puzzle {puzzle['id']}: {e}", flush=True)
            chosen_move = None
            
        elapsed = time.time() - start_time
        success = chosen_move in puzzle["best_moves"]
        status_str = "✅ PASSED" if success else f"❌ FAILED (Played: {chosen_move}, Target: {puzzle['best_moves'][0]})"
        
        print(f"Played: {chosen_move} | Time: {elapsed:.2f}s | {status_str}", flush=True)
        
        completed_results.append({
            "id": puzzle["id"],
            "name": puzzle["name"],
            "rating": puzzle["rating"],
            "success": success,
            "played": chosen_move,
            "targets": puzzle["best_moves"],
            "time": elapsed,
            "retries": 0
        })
        
        # Save to checkpoint file immediately
        try:
            with open(checkpoint_file, "w") as f:
                json.dump({
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "mode": "queen_only",
                    "total_puzzles": total_puzzles,
                    "results": completed_results
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving checkpoint: {e}", flush=True)
        
    # Calculate overall stats
    total_passed = sum(1 for r in completed_results if r["success"])
    pass_rate = (total_passed / total_puzzles) * 100
    estimated_elo = calculate_expected_score_elo(completed_results, total_passed)
    avg_time = sum(r["time"] for r in completed_results) / total_puzzles
    
    print("\n====================================================", flush=True)
    print("      QUEEN-ONLY 500-PUZZLE BENCHMARK COMPLETE", flush=True)
    print("====================================================", flush=True)
    print(f"Overall Score: {total_passed}/{total_puzzles} ({pass_rate:.1f}% Pass Rate)", flush=True)
    print(f"Estimated Puzzle Rating: ~{estimated_elo} Rating", flush=True)
    print(f"Average Move Latency: {avg_time:.4f}s", flush=True)
    print("====================================================", flush=True)
    
    # Tier breakdown
    tier_groups = {}
    for r in completed_results:
        tier = (r["rating"] // 100) * 100
        if tier not in tier_groups:
            tier_groups[tier] = []
        tier_groups[tier].append(r)
        
    tier_stats = {}
    print("Tier Stats:", flush=True)
    for tier in sorted(tier_groups.keys()):
        tier_results = tier_groups[tier]
        t_total = len(tier_results)
        t_passed = sum(1 for r in tier_results if r["success"])
        t_pass_rate = (t_passed / t_total) * 100
        print(f"  {tier}s: {t_passed}/{t_total} ({t_pass_rate:.1f}%)", flush=True)
        tier_stats[tier] = {
            "passed": t_passed,
            "total": t_total,
            "pass_rate": t_pass_rate
        }
        
    # Save final report
    try:
        report_data = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "model_name": "Queen-Only Heuristics (No LLM)",
            "mode": "queen_only",
            "total_passed": total_passed,
            "total_puzzles": total_puzzles,
            "pass_rate": pass_rate,
            "estimated_elo": estimated_elo,
            "tier_stats": tier_stats,
            "results": completed_results
        }
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=4)
        print(f"Final report written to {report_file}", flush=True)
        
        # Clean up checkpoint file
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
    except Exception as e:
        print(f"Error saving report: {e}", flush=True)

if __name__ == "__main__":
    run_queen_only_500()
