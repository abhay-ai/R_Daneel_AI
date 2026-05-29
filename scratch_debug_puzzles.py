import lichess_bot
import sys

FAILED_PUZZLES = [
    {
        "name": "Under-Promotion to Knight Fork",
        "fen": "8/2P1k3/1q6/8/8/8/8/7K w - - 0 1",
        "best_moves": ["c7c8n"]
    },
    {
        "name": "Smothered Mate-in-2",
        "fen": "r4r1k/5Qpp/7N/8/8/8/8/6K1 w - - 0 1",
        "best_moves": ["f7g8"]
    },
    {
        "name": "Simple Back Rank Deflection",
        "fen": "r1r3k1/5ppp/2Q5/8/8/8/5PPP/2R3K1 w - - 0 1",
        "best_moves": ["c6c8"]
    },
    {
        "name": "Deflection to Win Bishop",
        "fen": "r4rk1/pp3ppp/2n5/2bQ4/8/3B1N2/PP3PPP/R4RK1 w - - 0 1",
        "best_moves": ["d3h7", "d5c5"]
    },
    {
        "name": "Greek Gift Sacrifice Setup",
        "fen": "r1bq1rk1/pppnbppp/4pn2/3p2B1/3P4/2NBPN2/PPP2PPP/R2QK2R w KQ - 3 6",
        "best_moves": ["d3h7"]
    }
]

def debug_one_puzzle(puzzle):
    print("====================================================")
    print(f"DEBUGGING PUZZLE: {puzzle['name']}")
    print(f"FEN: {puzzle['fen']}")
    print(f"Target Moves: {puzzle['best_moves']}")
    print("====================================================")
    
    model_name = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
    
    move, retries, thoughts, strategy = lichess_bot.get_legal_llm_move(
        puzzle["fen"],
        model_name=model_name,
        current_strategy="Analyze the tactical board layout and select the best move."
    )
    
    print("\n----------------------------------------------------")
    print(f"Final Proposed Move: {move}")
    print(f"Retries needed: {retries}")
    print(f"Success? {move in puzzle['best_moves']}")
    print(f"Strategy: {strategy}")
    print("----------------------------------------------------")
    print("LLM FULL THOUGHTS HISTORY:")
    print(thoughts)
    print("====================================================\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        idx = int(sys.argv[1])
        if 0 <= idx < len(FAILED_PUZZLES):
            debug_one_puzzle(FAILED_PUZZLES[idx])
        else:
            print("Invalid index.")
    else:
        for p in FAILED_PUZZLES:
            debug_one_puzzle(p)
