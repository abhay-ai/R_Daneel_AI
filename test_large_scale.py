import os
import sys
import time
import json
import re
import argparse
import random
from openai import OpenAI
import queen as prolog_referee
import lichess_bot

# Global OpenAI client reference (initialized in main() after parsing arguments)
client = None

def get_baseline_llm_move(fen, legal_moves, model_name, error_feedback="", retry_count=0):
    if retry_count >= 3:
        # Fallback to the first legal move if it fails 3 times
        return legal_moves[0], retry_count, "Too many retries"
        
    messages = [
        {
            "role": "system",
            "content": (
                "You are an expert chess grandmaster. Your task is to analyze the given chess board position (represented as a FEN string) and choose the absolute best move.\n\n"
                "To help you, the list of all legal moves in this position is provided. You MUST choose your move from this list of legal moves.\n\n"
                "Explain your thoughts step-by-step, and output your final chosen move inside <move>...</move> tags (for example: <move>e2e4</move> or <move>c7c8n</move>)."
            )
        }
    ]
    
    user_content = f"Current Position (FEN): {fen}\n"
    user_content += f"Legal Moves: {', '.join(legal_moves)}\n"
    if error_feedback:
        user_content += f"\nERROR FEEDBACK from previous attempt: {error_feedback}\n"
    user_content += "\nThink step-by-step, analyze the threats and tactical targets, and output your final move in the <move>...</move> tags."
    
    messages.append({"role": "user", "content": user_content})
    
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.15,
            frequency_penalty=0.15
        )
        content = response.choices[0].message.content or ""
        
        # Parse move
        match = re.search(r'<move>\s*(.*?)\s*</move>', content, re.IGNORECASE)
        if match:
            proposed = match.group(1).strip().lower()
            if proposed in legal_moves:
                return proposed, retry_count, content
            else:
                feedback = f"Proposed move '{proposed}' is not in the list of legal moves."
                return get_baseline_llm_move(fen, legal_moves, model_name, feedback, retry_count + 1)
        else:
            feedback = "No move found inside <move>...</move> tags."
            return get_baseline_llm_move(fen, legal_moves, model_name, feedback, retry_count + 1)
            
    except Exception as e:
        print(f"Error during LLM completion: {e}")
        return legal_moves[0], retry_count, str(e)

def calculate_expected_score_elo(results, total_passed):
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
            
    if total_passed == 0:
        return 0
    elif total_passed == len(results):
        return 2000
    else:
        return int(mid)

def main():
    parser = argparse.ArgumentParser(description="Large-Scale Chess Puzzle Benchmark")
    parser.add_argument("--mode", choices=["baseline", "neuro_symbolic"], required=True, help="Bot mode to evaluate")
    parser.add_argument("--puzzles-per-tier", type=int, default=50, help="Number of puzzles per tier (10 tiers, total = 10 * this value)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling reproducibility")
    parser.add_argument("--model", type=str, default="cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit", help="vLLM model name")
    parser.add_argument("--puzzles-file", type=str, default="logs/lichess_1000_puzzles.json", help="Path to the puzzles JSON file")
    parser.add_argument("--min-rating", type=int, default=600, help="Minimum rating for tiers (inclusive)")
    parser.add_argument("--max-rating", type=int, default=1600, help="Maximum rating for tiers (exclusive)")
    parser.add_argument("--output-suffix", type=str, default="", help="Suffix for checkpoint and report files")
    parser.add_argument("--api-key", type=str, default=os.environ.get("DEEPSEEK_API_KEY") or "token-not-needed", help="API key for LLM client")
    parser.add_argument("--base-url", type=str, default=os.environ.get("DEEPSEEK_API_BASE") or os.environ.get("OPENAI_API_BASE") or "http://localhost:8000/v1", help="Base URL for LLM client")
    args = parser.parse_args()
    
    global client
    client = OpenAI(base_url=args.base_url, api_key=args.api_key)
    lichess_bot.openai_client = client
    
    # Load all Lichess puzzles
    puzzles_file = args.puzzles_file
    if not os.path.exists(puzzles_file):
        print(f"Error: {puzzles_file} not found. Ensure puzzle file exists.")
        sys.exit(1)
        
    with open(puzzles_file, "r") as f:
        all_puzzles = json.load(f)
        
    # Group puzzles by 100-Elo tiers
    tiers = {r: [] for r in range(args.min_rating, args.max_rating, 100)}
    for p in all_puzzles:
        tier = (p["rating"] // 100) * 100
        if tier in tiers:
            tiers[tier].append(p)
            
    # Sample from each tier using the provided seed
    random.seed(args.seed)
    sampled_puzzles = []
    for tier, p_list in sorted(tiers.items()):
        if len(p_list) < args.puzzles_per_tier:
            print(f"Warning: Tier {tier} only has {len(p_list)} puzzles, requested {args.puzzles_per_tier}.")
            sampled = p_list
        else:
            sampled = random.sample(p_list, args.puzzles_per_tier)
        sampled_puzzles.extend(sampled)
        
    # Sort sampled puzzles by rating
    sampled_puzzles.sort(key=lambda x: x["rating"])
    total_puzzles = len(sampled_puzzles)
    print(f"Sampled {total_puzzles} puzzles ({args.puzzles_per_tier} per tier, seed={args.seed}) for mode '{args.mode}'.")
    
    # Define files for checkpoints and final reports
    suffix = f"_{args.output_suffix}" if args.output_suffix else f"_{total_puzzles}"
    checkpoint_file = f"logs/large_scale_checkpoint_{args.mode}{suffix}.json"
    report_file = f"logs/large_scale_report_{args.mode}{suffix}.json"
    
    # Check if checkpoint exists
    completed_results = []
    completed_ids = set()
    if os.path.exists(checkpoint_file):
        try:
            with open(checkpoint_file, "r") as f:
                checkpoint_data = json.load(f)
                completed_results = checkpoint_data.get("results", [])
                completed_ids = {r["id"] for r in completed_results}
                print(f"Resuming from checkpoint. Loaded {len(completed_results)} completed puzzles.")
        except Exception as e:
            print(f"Warning: Could not load checkpoint file ({e}). Starting fresh.")
            
    # Filter out completed puzzles
    remaining_puzzles = [p for p in sampled_puzzles if p["id"] not in completed_ids]
    print(f"Puzzles remaining to process: {len(remaining_puzzles)}")
    
    for idx, puzzle in enumerate(remaining_puzzles):
        curr_idx = len(completed_results) + 1
        print(f"\n--- [Puzzle {curr_idx}/{total_puzzles}] {puzzle['name']} (Rating: {puzzle['rating']}) --- FEN: {puzzle['fen']}")
        
        start_time = time.time()
        move = None
        retries = 0
        thoughts = ""
        
        try:
            if args.mode == "baseline":
                legal_moves = prolog_referee.get_legal_moves(puzzle["fen"])
                move, retries, thoughts = get_baseline_llm_move(
                    puzzle["fen"],
                    legal_moves,
                    model_name=args.model
                )
            else: # neuro_symbolic
                move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(
                    puzzle["fen"],
                    model_name=args.model,
                    current_strategy="Analyze the tactical board layout and select the best move."
                )
        except Exception as e:
            print(f"Execution error on puzzle {puzzle['id']}: {e}")
            # Fallback in case of code-level crash
            legal_moves = prolog_referee.get_legal_moves(puzzle["fen"])
            move = legal_moves[0] if legal_moves else "a2a3"
            retries = 1
            thoughts = f"Execution error: {e}"
            
        elapsed = time.time() - start_time
        success = move in puzzle["best_moves"]
        status_str = "✅ PASSED" if success else f"❌ FAILED (Played: {move}, Target: {puzzle['best_moves'][0]})"
        
        print(f"Played: {move} | Retries: {retries} | Time: {elapsed:.2f}s | {status_str}")
        
        completed_results.append({
            "id": puzzle["id"],
            "name": puzzle["name"],
            "rating": puzzle["rating"],
            "success": success,
            "played": move,
            "targets": puzzle["best_moves"],
            "time": elapsed,
            "retries": retries
        })
        
        # Save to checkpoint file immediately
        try:
            with open(checkpoint_file, "w") as f:
                json.dump({
                    "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                    "mode": args.mode,
                    "total_puzzles": total_puzzles,
                    "results": completed_results
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving checkpoint: {e}")

    # Complete! Report calculations
    total_passed = sum(1 for r in completed_results if r["success"])
    pass_rate = (total_passed / total_puzzles) * 100
    estimated_elo = calculate_expected_score_elo(completed_results, total_passed)
    
    print("\n====================================================")
    print(f"       BENCHMARK COMPLETE - {args.mode.upper()}")
    print("====================================================")
    print(f"Overall Score: {total_passed}/{total_puzzles} ({pass_rate:.1f}% Pass Rate)")
    print(f"Estimated Puzzle Rating: ~{estimated_elo} Rating")
    print("====================================================")
    
    # Save final report
    try:
        report_data = {
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
            "model_name": args.model,
            "mode": args.mode,
            "total_passed": total_passed,
            "total_puzzles": total_puzzles,
            "pass_rate": pass_rate,
            "estimated_elo": estimated_elo,
            "results": completed_results
        }
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=4)
        print(f"Final report written to {report_file}")
        
        # Clean up checkpoint file
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
    except Exception as e:
        print(f"Error saving report: {e}")

if __name__ == "__main__":
    main()
