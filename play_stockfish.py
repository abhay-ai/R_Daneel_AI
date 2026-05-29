import os
import sys
import time
import urllib.request
import tarfile
import shutil
import chess
import chess.engine
import lichess_bot

MODEL_NAME = "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit"
STOCKFISH_BINARY = "./stockfish_engine"

def setup_stockfish():
    """
    Downloads and extracts the official Stockfish 18 precompiled Ubuntu x86-64 binary if not present.
    """
    if os.path.exists(STOCKFISH_BINARY):
        return STOCKFISH_BINARY

    print("====================================================")
    print("Stockfish not found locally. Downloading Stockfish 18...")
    
    # URL for Stockfish 18 release
    url = "https://github.com/official-stockfish/Stockfish/releases/download/sf_18/stockfish-ubuntu-x86-64.tar"
    archive = "stockfish.tar"
    
    try:
        # Download the tarball
        urllib.request.urlretrieve(url, archive)
        print("Download complete. Extracting tar file...")
        
        # Extract files
        with tarfile.open(archive, "r:") as tar:
            tar.extractall()
            
        # Find the stockfish binary inside the extracted files
        binary_src = None
        for root, dirs, files in os.walk("."):
            for f in files:
                # Target the executable inside the extracted folders
                if f.startswith("stockfish-ubuntu") or f == "stockfish":
                    if "stockfish-ubuntu-x86-64" in root:
                        binary_src = os.path.join(root, f)
                        break
            if binary_src:
                break
                
        if binary_src:
            shutil.copy(binary_src, STOCKFISH_BINARY)
            os.chmod(STOCKFISH_BINARY, 0o755)
            print(f"Stockfish setup complete! Saved to {STOCKFISH_BINARY}")
            
            # Clean up
            os.remove(archive)
            # Find the top level folder extracted (e.g. stockfish-ubuntu-x86-64) and remove it
            extracted_dir = binary_src.split(os.sep)[1]
            if os.path.isdir(extracted_dir):
                shutil.rmtree(extracted_dir)
            return STOCKFISH_BINARY
        else:
            raise Exception("Could not find the stockfish binary in the extracted archive.")
            
    except Exception as e:
        print(f"❌ Error setting up Stockfish: {e}")
        print("Please download Stockfish manually and place the executable named 'stockfish_engine' in this folder.")
        return None

def play_one_game(engine, bot_color, skill_level, limit_time, game_id):
    board = chess.Board()
    current_strategy = "Formulate a strong, active plan in the opening, control the center, and develop minor pieces."
    moves_list = []
    
    # We use a human-readable display of the board status
    print("\n--- NEW GAME STARTED ---")
    print(f"Bot Color: {'White' if bot_color == chess.WHITE else 'Black'}")
    print(board)
    
    while not board.is_game_over():
        move_number = (len(board.move_stack) // 2) + 1
        current_fen = board.fen()
        
        if board.turn == bot_color:
            # Reconstruct previous FEN and opponent's last move for the bot's System 2 spatial eyes
            if moves_list:
                temp_board = chess.Board()
                for m in moves_list[:-1]:
                    temp_board.push_uci(m)
                previous_fen = temp_board.fen()
                opponents_last_move = moves_list[-1]
            else:
                previous_fen = None
                opponents_last_move = None
                
            print(f"\n🧠 Bot thinking (Move {move_number})...")
            start_time = time.time()
            ai_move, retry_count, thoughts, updated_strategy = lichess_bot.get_legal_llm_move(
                current_fen,
                model_name=MODEL_NAME,
                current_strategy=current_strategy,
                previous_fen=previous_fen,
                opponents_last_move=opponents_last_move
            )
            elapsed = time.time() - start_time
            
            print(f"Proposed UCI Move: {ai_move} | Retries: {retry_count} | Time: {elapsed:.2f}s")
            
            if not ai_move:
                print("❌ Bot failed to propose a move. Resigning.")
                return "0-1" if bot_color == chess.WHITE else "1-0"
                
            try:
                move_obj = chess.Move.from_uci(ai_move)
            except ValueError:
                print(f"❌ Proposed move '{ai_move}' is not valid coordinate syntax. Resigning.")
                return "0-1" if bot_color == chess.WHITE else "1-0"
                
            if move_obj not in board.legal_moves:
                print(f"❌ Proposed move '{ai_move}' is illegal in this position! Resigning.")
                return "0-1" if bot_color == chess.WHITE else "1-0"
                
            # Log the bot's move in CSV and JSONL (for visualizer.html)
            lichess_bot.log_experiment_data(game_id, move_number, current_fen, retry_count, elapsed, MODEL_NAME, thoughts, updated_strategy)
            lichess_bot.log_experiment_data_json(game_id, move_number, current_fen, ai_move, retry_count, elapsed, MODEL_NAME, thoughts, updated_strategy)
            
            board.push(move_obj)
            moves_list.append(ai_move)
            current_strategy = updated_strategy
            
        else:
            # Stockfish Engine's Turn
            print(f"\n🐟 Stockfish (Level {skill_level}) thinking...")
            start_time = time.time()
            result = engine.play(board, chess.engine.Limit(time=limit_time))
            elapsed = time.time() - start_time
            sf_move = result.move.uci()
            print(f"Stockfish UCI Move: {sf_move}")
            
            # Log Stockfish's move in CSV and JSONL (with empty thoughts/strategy placeholder)
            lichess_bot.log_experiment_data(game_id, move_number, current_fen, 0, elapsed, f"Stockfish_Lvl_{skill_level}", f"Stockfish Level {skill_level} calculated move {sf_move}", "")
            lichess_bot.log_experiment_data_json(game_id, move_number, current_fen, sf_move, 0, elapsed, f"Stockfish_Lvl_{skill_level}", f"Stockfish Level {skill_level} calculated move {sf_move}", "")
            
            board.push(result.move)
            moves_list.append(sf_move)
            
        print("\n" + str(board))
        
    result_str = board.result()
    print(f"\n🏁 Game finished! Result: {result_str}")
    
    # Save standard PGN
    import chess.pgn
    pgn_game = chess.pgn.Game()
    pgn_game.headers["Event"] = f"Bot vs Stockfish Level {skill_level} Match"
    pgn_game.headers["Site"] = "Local Machine"
    pgn_game.headers["Date"] = time.strftime('%Y.%m.%d')
    pgn_game.headers["Round"] = "1"
    pgn_game.headers["White"] = "R_Daneel_AI" if bot_color == chess.WHITE else f"Stockfish Level {skill_level}"
    pgn_game.headers["Black"] = f"Stockfish Level {skill_level}" if bot_color == chess.WHITE else "R_Daneel_AI"
    pgn_game.headers["Result"] = result_str
    
    # Add moves to PGN
    node = pgn_game
    for m_uci in moves_list:
        node = node.add_main_line(chess.Move.from_uci(m_uci))
        
    pgn_file = os.path.join("logs", f"game_{game_id}.pgn")
    with open(pgn_file, "w", encoding="utf-8") as f:
        f.write(str(pgn_game))
    print(f"PGN successfully logged to: {pgn_file}")
    print(f"JSONL thoughts successfully logged to: logs/game_{game_id}.jsonl")
    
    return result_str

def run_match_play():
    # Configure parameters
    num_games = 3
    skill_level = 0  # Stockfish Skill Level (0 is weakest, ~800-1000 Elo)
    limit_time = 0.05  # Time limit per move for Stockfish
    
    print("====================================================")
    print(f"        BOT VS STOCKFISH LEVEL {skill_level} MATCH")
    print("====================================================")
    
    # 1. Setup Stockfish
    engine_path = setup_stockfish()
    if not engine_path:
        print("Could not start matches without Stockfish.")
        sys.exit(1)
        
    # Start engine process
    print("Starting Stockfish engine...")
    try:
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)
        engine.configure({"Skill Level": skill_level})
    except Exception as e:
        print(f"❌ Failed to run Stockfish executable: {e}")
        sys.exit(1)
        
    bot_wins = 0
    sf_wins = 0
    draws = 0
    
    try:
        for game_idx in range(num_games):
            print(f"\n==========================================")
            print(f"         GAME {game_idx + 1} OF {num_games}")
            print(f"==========================================")
            
            # Alternate colors
            bot_color = chess.WHITE if game_idx % 2 == 0 else chess.BLACK
            
            # Generate a unique game ID for logs
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            game_id = f"sf_match_{timestamp}_{game_idx+1}"
            
            result = play_one_game(engine, bot_color, skill_level, limit_time, game_id)
            
            # Record scores
            if result == "1-0":
                if bot_color == chess.WHITE:
                    bot_wins += 1
                else:
                    sf_wins += 1
            elif result == "0-1":
                if bot_color == chess.BLACK:
                    bot_wins += 1
                else:
                    sf_wins += 1
            else:
                draws += 1
                
            print(f"\nCurrent Standings: Bot {bot_wins} - {sf_wins} Stockfish ({draws} Draws)")
            
    finally:
        # Guarantee engine cleanup
        print("\nShutting down Stockfish...")
        engine.quit()
        
    print("\n====================================================")
    print("                  MATCH SUMMARY")
    print("====================================================")
    print(f"Total Games Played: {num_games}")
    print(f"Bot Wins: {bot_wins}")
    print(f"Stockfish Wins: {sf_wins}")
    print(f"Draws: {draws}")
    
    bot_score = bot_wins + (draws * 0.5)
    win_rate = (bot_score / num_games) * 100
    print(f"Bot Performance: {win_rate:.1f}%")
    print("====================================================")

if __name__ == "__main__":
    run_match_play()
