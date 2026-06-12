import sys
import csv
import json
import os
import chess

def filter_puzzles_high_elo():
    print("Starting Lichess high-Elo puzzle filtration and sampling...")
    
    # We want 50 puzzles per tier from 1600 to 2500 (10 tiers: 1600, 1700, ..., 2500)
    tiers = {r: [] for r in range(1600, 2600, 100)}
    limit_per_tier = 50
    total_needed = len(tiers) * limit_per_tier
    total_collected = 0
    
    # Read CSV from stdin
    reader = csv.reader(sys.stdin)
    
    # Skip header if present
    try:
        header = next(reader)
        if header[0] != "PuzzleId":
            row = header
            header = None
        else:
            row = None
    except StopIteration:
        print("Error: Empty input stream")
        return

    count = 0
    while True:
        if row is None:
            try:
                row = next(reader)
            except StopIteration:
                break
        
        count += 1
        if count % 100000 == 0:
            print(f"Processed {count} rows... Collected {total_collected}/{total_needed} puzzles.")
        
        try:
            # Columns: PuzzleId, FEN, Moves, Rating, RatingDeviation, Popularity, NbPlays, Themes, GameUrl, OpeningTags
            puzzle_id, fen, moves_str, rating_str = row[0], row[1], row[2], row[3]
            rating = int(rating_str)
            
            # Determine tier
            tier = (rating // 100) * 100
            if tier in tiers and len(tiers[tier]) < limit_per_tier:
                moves = moves_str.split()
                if len(moves) >= 2:
                    opponent_move_uci = moves[0]
                    best_move_uci = moves[1]
                    
                    board = chess.Board(fen)
                    opponent_move = chess.Move.from_uci(opponent_move_uci)
                    
                    if opponent_move in board.legal_moves:
                        board.push(opponent_move)
                        player_fen = board.fen()
                        
                        # Store puzzle
                        tiers[tier].append({
                            "id": puzzle_id,
                            "name": f"Lichess-{puzzle_id}",
                            "rating": rating,
                            "fen": player_fen,
                            "best_moves": [best_move_uci],
                            "desc": f"Lichess puzzle {puzzle_id} (Rating: {rating}). Opponent played {opponent_move_uci}."
                        })
                        total_collected += 1
                        
                        if total_collected >= total_needed:
                            break
        except Exception as e:
            # Skip any malformed rows or moves
            pass
        
        row = None # Reset row for next iteration

    # Flatten and sort by rating
    sampled_puzzles = []
    for tier, p_list in tiers.items():
        print(f"Tier {tier} Elo: Collected {len(p_list)}/{limit_per_tier} puzzles.")
        sampled_puzzles.extend(p_list)
        
    sampled_puzzles.sort(key=lambda x: x["rating"])
    
    # Save to file
    os.makedirs("logs", exist_ok=True)
    output_file = "logs/lichess_500_puzzles_high_elo.json"
    with open(output_file, "w") as f:
        json.dump(sampled_puzzles, f, indent=4)
        
    print(f"\nSuccessfully saved {len(sampled_puzzles)} sampled puzzles to {output_file}")

if __name__ == "__main__":
    filter_puzzles_high_elo()
