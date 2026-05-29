import sys
import csv
import json
import os
import chess

def filter_puzzles():
    print("Starting Lichess puzzle filtration and sampling...")
    
    # We want 100 puzzles per tier from 600 to 1500 (10 tiers: 600, 700, ..., 1500)
    tiers = {r: [] for r in range(600, 1600, 100)}
    limit_per_tier = 100
    total_needed = len(tiers) * limit_per_tier
    total_collected = 0
    
    # Read CSV from stdin
    reader = csv.reader(sys.stdin)
    
    # Skip header if present
    try:
        header = next(reader)
        # Check if the first row is indeed the header
        if header[0] != "PuzzleId":
            # If it's not the header, process it as a data row
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
                # Process FEN and Moves
                # In Lichess, the FEN is BEFORE the opponent's last move.
                # The first move in the moves string is the opponent's last move.
                # We need to make that move to set up the player's puzzle position.
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
    output_file = "logs/lichess_1000_puzzles.json"
    with open(output_file, "w") as f:
        json.dump(sampled_puzzles, f, indent=4)
        
    print(f"\nSuccessfully saved {len(sampled_puzzles)} sampled puzzles to {output_file}")

if __name__ == "__main__":
    filter_puzzles()
