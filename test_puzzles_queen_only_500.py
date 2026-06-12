import os
import sys
import time
import json
import random
import chess
import queen as prolog_referee
from lichess_bot import sort_legal_moves
from test_large_scale import calculate_expected_score_elo

def run_queen_only_500(args):
    # Load all Lichess puzzles
    puzzles_file = args.puzzles_file
    if not os.path.exists(puzzles_file):
        print(f"Error: {puzzles_file} not found. Ensure puzzle file exists.", flush=True)
        sys.exit(1)
        
    with open(puzzles_file, "r") as f:
        all_puzzles = json.load(f)
        
    # Group puzzles by 100-Elo tiers
    tiers = {r: [] for r in range(args.min_rating, args.max_rating, 100)}
    for p in all_puzzles:
        tier = (p["rating"] // 100) * 100
        if tier in tiers:
            tiers[tier].append(p)
            
    # Sample from each tier using seed
    random.seed(args.seed)
    puzzles_per_tier = args.puzzles_per_tier
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
    print(f"Sampled {total_puzzles} puzzles ({puzzles_per_tier} per tier, seed={args.seed}) for Queen-only baseline.", flush=True)
    
    suffix = f"_{args.output_suffix}" if args.output_suffix else f"_{total_puzzles}"
    checkpoint_file = f"logs/large_scale_checkpoint_queen_only{suffix}.json"
    report_file = f"logs/large_scale_report_queen_only{suffix}.json"
    
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
    print("      QUEEN-ONLY BENCHMARK COMPLETE", flush=True)
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
    import argparse
    parser = argparse.ArgumentParser(description="Queen-only Heuristics Puzzle Benchmark")
    parser.add_argument("--puzzles-file", type=str, default="logs/lichess_1000_puzzles.json", help="Path to the puzzles JSON file")
    parser.add_argument("--min-rating", type=int, default=600, help="Minimum rating for tiers (inclusive)")
    parser.add_argument("--max-rating", type=int, default=1600, help="Maximum rating for tiers (exclusive)")
    parser.add_argument("--puzzles-per-tier", type=int, default=50, help="Number of puzzles per tier")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling reproducibility")
    parser.add_argument("--output-suffix", type=str, default="", help="Suffix for checkpoint and report files")
    args = parser.parse_args()
    
    run_queen_only_500(args)
