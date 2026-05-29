import os
import sys
import time
import json
import re
from openai import OpenAI
import queen as prolog_referee
import test_puzzles

# Initialize OpenAI client (pointing to the local vLLM daemon)
client = OpenAI(base_url="http://localhost:8000/v1", api_key="token-not-needed")

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
        match = re.search(r'<move>\s*(.*?)\s*</move>', content)
        if match:
            proposed = match.group(1).strip().lower()
            if proposed in legal_moves:
                return proposed, retry_count, content
            else:
                feedback = f"Proposed move '{proposed}' is not in the list of legal moves."
                print(f"⚠️ Warning: {feedback}")
                return get_baseline_llm_move(fen, legal_moves, model_name, feedback, retry_count + 1)
        else:
            feedback = "No move found inside <move>...</move> tags."
            print(f"⚠️ Warning: {feedback}")
            return get_baseline_llm_move(fen, legal_moves, model_name, feedback, retry_count + 1)
            
    except Exception as e:
        print(f"Error during LLM completion: {e}")
        return legal_moves[0], retry_count, str(e)

def run_baseline_benchmark():
    print("====================================================")
    print("   CHESS BOT BASELINE (PURE LLM) ELO BENCHMARK")
    print("====================================================")
    
    model_name = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
    print(f"Model under test: {model_name}\n")
    
    results = []
    
    for idx, puzzle in enumerate(test_puzzles.PUZZLES):
        print(f"\n--- [Puzzle {idx+1}/{len(test_puzzles.PUZZLES)}] {puzzle['name']} (Est. Rating: {puzzle['rating']}) ---")
        print(f"FEN: {puzzle['fen']}")
        print(f"Target Moves: {', '.join(puzzle['best_moves'])}")
        
        # Get legal moves using the referee
        legal_moves = prolog_referee.get_legal_moves(puzzle["fen"])
        
        start_time = time.time()
        move, retries, thoughts = get_baseline_llm_move(
            puzzle["fen"],
            legal_moves,
            model_name=model_name
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
    print("              BASELINE BENCHMARK SUMMARY")
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
        
    print(f"\nEstimated Baseline Tactical Elo (Expected Score Matching): ~{estimated_elo} Elo")
    
    # Save results to log file
    os.makedirs("logs", exist_ok=True)
    timestamp = time.strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join("logs", f"puzzle_benchmark_baseline_{timestamp}.json")
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
    run_baseline_benchmark()
