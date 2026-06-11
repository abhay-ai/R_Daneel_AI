import berserk
import chess
import csv
import os
import time
import re
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

openai_client = OpenAI(base_url="http://localhost:8000/v1", api_key="token-not-needed")


# Move this to the global scope at the top of lichess_bot.py
import queen as prolog_referee

def log_experiment_data(game_id, move_number, fen, retries, execution_time, model_name, thoughts="", strategy=""):
    os.makedirs('logs', exist_ok=True)
    file_path = os.path.join('logs', f'game_{game_id}.csv')
    file_exists = os.path.isfile(file_path)
    
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Escape newlines to preserve single-line CSV formatting for easy raw file inspection
    escaped_thoughts = thoughts.replace('\n', '\\n')
    escaped_strategy = strategy.replace('\n', '\\n')
    
    with open(file_path, mode='a', newline='') as file:
        writer = csv.writer(file)
        # Write headers if the file is being created for the first time
        if not file_exists:
            writer.writerow(['Timestamp', 'Game_ID', 'Model_Name', 'Move_Number', 'FEN_State', 'Prolog_Rejections', 'Compute_Time_Sec', 'LLM_Thoughts', 'Active_Strategy'])
        
        # Log the metrics for your paper
        writer.writerow([timestamp, game_id, model_name, move_number, fen, retries, execution_time, escaped_thoughts, escaped_strategy])

def log_experiment_data_json(game_id, move_number, fen, move, retries, execution_time, model_name, thoughts="", strategy=""):
    os.makedirs('logs', exist_ok=True)
    file_path = os.path.join('logs', f'game_{game_id}.jsonl')
    
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    
    log_entry = {
        'timestamp': timestamp,
        'game_id': game_id,
        'model_name': model_name,
        'move_number': move_number,
        'fen': fen,
        'move': move,
        'retries': retries,
        'compute_time_sec': execution_time,
        'thoughts': thoughts,
        'strategy': strategy
    }
    
    with open(file_path, mode='a', encoding='utf-8') as file:
        file.write(json.dumps(log_entry) + '\n')

# --- LLM Response Flow ---

def extract_fallback_move(content, board):
    """
    Attempts to extract a legal chess move from the text content if tags are missing.
    """
    if not content or not content.strip():
        return None
        
    # 1. Search for patterns like "move: <move>", "best move is <move>", "play <move>"
    pattern = r"(?:therefore|so|best move|chosen move|play|move|should play)\s*(?::|is)?\s*\b(O-O-O|O-O|[NQRBKP]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NQRB])?[+#]?|[a-h][1-8][a-h][1-8][qrbn]?)\b"
    matches = re.findall(pattern, content, re.IGNORECASE)
    if matches:
        # Check if any match is a legal move
        for match in reversed(matches): # start from the last match
            move_str = match.strip()
            # Try to parse as UCI
            try:
                move = chess.Move.from_uci(move_str.lower())
                if move in board.legal_moves:
                    return move.uci()
            except Exception:
                pass
            # Try to parse as SAN
            try:
                # Normalize castling
                if move_str.lower() in ('o-o', '0-0'):
                    move_str = 'O-O'
                elif move_str.lower() in ('o-o-o', '0-0-0'):
                    move_str = 'O-O-O'
                move = board.parse_san(move_str)
                if move in board.legal_moves:
                    return move.uci()
            except Exception:
                pass
                
    # 2. If no specific pattern matched, scan the last 300 characters of the content for any word that is a legal move
    recent_content = content[-300:] if len(content) > 300 else content
    # Check all legal moves
    for move in board.legal_moves:
        uci = move.uci()
        san = board.san(move)
        # Search for exact word matches of UCI or SAN
        if re.search(r'\b' + re.escape(uci) + r'\b', recent_content, re.IGNORECASE):
            return uci
        # Also check for SAN (normalize castling for regex safety)
        san_regex = san.replace('+', r'\+').replace('#', r'\#')
        if re.search(r'\b' + san_regex + r'\b', recent_content):
            return uci
            
    return None

def sort_legal_moves(legal_moves, fen, start_summary):
    import chess
    board = chess.Board(fen)
    
    mate_1 = set(start_summary.get("mate_in_one") or [])
    mate_2 = set(start_summary.get("mate_in_two") or [])
    
    forced_wins = set()
    for f_win in (start_summary.get("forced_material_wins") or []):
        if isinstance(f_win, dict) and "move" in f_win:
            forced_wins.add(f_win["move"])
            
    giving_check = set(start_summary.get("moves_giving_check") or [])
    
    creating_pins = set()
    for item in (start_summary.get("moves_creating_pins") or []):
        if isinstance(item, dict) and "move" in item:
            creating_pins.add(item["move"])
            
    creating_attacks = set()
    for item in (start_summary.get("moves_creating_attacks") or []):
        if isinstance(item, dict) and "move" in item:
            creating_attacks.add(item["move"])
    
    captures = set()
    for m_str in legal_moves:
        try:
            m = chess.Move.from_uci(m_str)
            if board.is_capture(m):
                captures.add(m_str)
        except Exception:
            pass
            
    # Assign score to each move (lower score = higher priority)
    def get_move_score(move_str):
        if move_str in mate_1:
            return 0
        if move_str in mate_2:
            return 1
        if move_str in forced_wins:
            return 2
        if move_str in captures:
            return 3
        if move_str in giving_check:
            return 4
        if move_str in creating_pins:
            return 5
        if move_str in creating_attacks:
            return 6
        return 7
        
    sorted_moves = sorted(legal_moves, key=get_move_score)
    return sorted_moves

def trim_tactical_summary(summary):
    if not isinstance(summary, dict):
        return summary
    trimmed = summary.copy()
    trimmed.pop("moves_giving_check", None)
    trimmed.pop("moves_creating_pins", None)
    trimmed.pop("moves_creating_attacks", None)
    return trimmed

def prune_tool_call_history(messages):
    # Always keep system (index 0) and starting user prompt (index 1)
    if len(messages) <= 4:
        return messages
        
    system_msg = messages[0]
    user_msg = messages[1]
    
    # Check if there is an error feedback message at index 2
    has_error_feedback = False
    error_msg = None
    start_idx = 2
    if len(messages) > 2 and messages[2].get("role") == "user" and "ERROR" in messages[2].get("content", "").upper():
        has_error_feedback = True
        error_msg = messages[2]
        start_idx = 3
        
    # Group remaining messages by tool blocks
    blocks = []
    i = start_idx
    n = len(messages)
    while i < n:
        msg = messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            block = [msg]
            i += 1
            while i < n and messages[i].get("role") == "tool":
                block.append(messages[i])
                i += 1
            blocks.append(block)
        else:
            blocks.append([msg])
            i += 1
            
    # Try keeping 2, then 1, then 0 blocks to find a fit under 6500 estimated tokens
    for keep_num in [2, 1, 0]:
        if len(blocks) > keep_num:
            pruned_blocks = blocks[-keep_num:] if keep_num > 0 else []
            new_messages = [system_msg, user_msg]
            if has_error_feedback:
                new_messages.append(error_msg)
            for b in pruned_blocks:
                new_messages.extend(b)
                
            # Estimate token count
            est_tokens = len(json.dumps(new_messages)) / 3.8
            if est_tokens <= 6500 or keep_num == 0:
                print(f"✂️ Pruned messages list from {len(messages)} down to {len(new_messages)} messages (kept {keep_num} blocks, estimated tokens: {est_tokens:.0f}).")
                return new_messages
                
    return messages

def get_legal_llm_move(fen, model_name, error_feedback="", retry_count=0, accumulated_thoughts=None, current_strategy=None, previous_fen=None, opponents_last_move=None):
    if accumulated_thoughts is None:
        accumulated_thoughts = []
        
    system_instruction = (
        "ROLE:\n"
        "You are a blind grandmaster-level chess player playing a match away from the board. Because you are blind, you CANNOT see the board directly, and you have zero spatial vision. "
        "Your assistant, a symbolic Prolog referee, is watching the board for you and describing it. The referee's tool outputs are the absolute, non-negotiable ground truth. "
        "To play successfully, you must rely entirely on the referee to describe the board layout, active threats, pins, and checks. "
        "Any attempt to guess coordinates or rely on your own spatial imagination will result in a blunder, just like a blind player guessing where the pieces are. Trust the referee's reports implicitly!\n\n"
        "YOUR OBJECTIVE:\n"
        "Evaluate the board position, think step-by-step to analyze tactical opportunities and positional values, and choose the single best legal move. "
        "You MUST choose your final move strictly from the list of legal moves provided in the user prompt. "
        "You are allowed to simulate at most 8 moves per turn using the `simulate_move` tool. Any attempt to simulate a 9th move will fail with an error. "
        "You must NEVER propose a move unless you have simulated it first and run `get_tactical_summary` on the simulated FEN to verify that the opponent has no high-utility capturing responses. The only exceptions are: "
        "(1) if the move is part of a forced checkmate sequence (mate_in_one or mate_in_two) or a forced material win where the capture/sacrifice is mathematically justified by the forced win, or "
        "(2) if there is only one single legal move in the current position (in which case you have no choice anyway and do not need to simulate it).\n\n"
        "CRITICAL ANALYSIS CHECKLIST:\n"
        "For the current position, you must thoroughly evaluate:\n"
        "1. Checks & King Safety: Check if your King is in check. When you query the `get_tactical_summary` tool, check the 'in_check' status and the 'checking_pieces' list. If you are in check, your ONLY legal moves are those that defend the King. IMPORTANT: If 'checking_pieces' contains more than one piece, you are in a double check! In a double check, it is mathematically impossible to block or capture; your ONLY legal option is to move the King to a safe square. Conversely, if your candidate move DELIVERS a double check to the opponent (the simulated FEN has 'checking_pieces' with more than one piece), the opponent is forced to move their King and CANNOT capture your checking pieces or block the checks. Thus, any apparently 'hanging' checking pieces in that move are completely safe from capture. Any other move is completely illegal and will be rejected. You must prioritize resolving the check immediately!\n"
        "2. Forced Tactical Combinations (Mates & Material Wins): Check the `mate_in_one`, `mate_in_two`, and `forced_material_wins` lists returned by `get_tactical_summary`:\n"
        "   - If there are any moves listed in `mate_in_one`, play one of them immediately! It is a direct win!\n"
        "   - If there are moves in `mate_in_two`, prioritize them as they guarantee checkmate in 2 moves.\n"
        "   - If there are moves in `forced_material_wins` (e.g. `{'move': 'd5c7', 'gain': 9}`), prioritize them as they guarantee a major material gain in 2 moves.\n"
        "3. Captures & Material: Any potential captures, exchanges, or material imbalances. Query the `get_material_status` tool to see the pieces lost by both sides and which side has a material advantage (and by how many pawns equivalent).\n"
        "4. Threats & Attacks (Hanging Pieces): Identify if any of your own pieces are under attack. You MUST prioritize saving your own threatened pieces (especially high-value ones like the Queen or Rooks) before making other developing moves. A move that ignores a direct threat to a valuable piece is a major blunder, unless you are playing a forced tactical win (e.g., checkmate or a forced winning combination) that immediately overrides the threat.\n"
        "5. Discoveries: Discovered checks or discovered attacks that can be created or defended.\n"
        "6. Positional Structure & Development: Query the `get_positional_evaluation` tool to thoroughly understand:\n"
        "   - Development Status: Which minor pieces (Knights/Bishops) are still undeveloped (on their starting squares). Prioritize developing these pieces! You MUST select at least one quiet developing or reinforcing move (e.g. castling, developing an undeveloped minor piece, or playing a reinforcing pawn push like d3) as one of your 2 to 4 candidate moves. Do not focus solely on captures and checks!\n"
        "   - Passed Pawns: Identify friendly passed pawns that can be advanced, or enemy passed pawns that must be blocked.\n"
        "   - Backward Pawns: Identify weak pawns that cannot be easily defended by other pawns and are targets.\n"
        "   - Weak Squares: Squares on ranks 3-6 that cannot be defended by friendly pawns (holes where enemy Knights can settle).\n"
        "   - Board Tension: Identify active tension points (pawns or pieces of opposite colors attacking each other) returned in `board_tension`.\n"
        "7. Opponent's Intent & Last Move: Analyze the opponent's last move (provided in the user prompt). You should query `get_tactical_summary` on the FEN before their move (provided in the user prompt) and compare it with the current FEN state to identify exactly what threats their move posed and what weaknesses or hanging pieces it left behind.\n\n"
        "STRATEGIC FOCUS & ADAPTATION:\n"
        "You must formulate, review, and adapt a cohesive long-term strategy across turns. At each move, you are provided with the active long-term strategy from your previous turns.\n"
        "You MUST:\n"
        "1. Identify the current game phase (Opening, Middlegame, or Endgame) and make sure your play style matches it.\n"
        "2. Evaluate if the active strategy is still valid given the current position and game phase. If the position has changed significantly (e.g., piece exchanges, tactical shifts, phase change), adapt your strategy accordingly.\n"
        "3. Keep your proposed candidate moves aligned with this strategy.\n"
        "4. Output your updated/refined strategy inside `<strategy>...</strategy>` tags at the very end of your response, alongside your final move inside `<move>...</move>` tags.\n\n"
        "YOUR TOOLS:\n"
        "You have access to symbolic Prolog tools. ALWAYS call these tools in intermediate turns to inspect the board. Your tools are:\n"
        "- `get_legal_moves(fen)`: Returns all legal moves in the position.\n"
        "- `get_tactical_summary(fen)`: Consolidates check status ('in_check': true/false), checking_pieces, pinned/threatened/defended pieces, discovered attacks, forks, mate-in-1, mate-in-2, and forced material wins in a single query. Always call this tool first to analyze the board layout.\n"
        "- `get_material_status(fen)`: Returns pieces lost by both sides and the material advantage margin.\n"
        "- `get_positional_evaluation(fen)`: Returns undeveloped pieces, passed pawns, backward pawns, weak squares, and the game phase.\n"
        "- `simulate_move(fen, move)`: Simulates a move and returns the resulting FEN. Note: You can simulate at most 8 moves per turn.\n"
        "- `convert_san_to_uci(fen, move_san)`: Converts algebraic move (e.g. 'Nf3') to UCI (e.g. 'g1f3').\n"
        "- `convert_uci_to_san(fen, move_uci)`: Converts UCI move to algebraic notation.\n"
        "- `get_attackers_defenders(fen, square)`: Returns all white and black pieces attacking/defending a given square, the counts, and a trade safety rating. Use this when evaluating trades, captures, and coordinate chains ('take take take').\n\n"
        "MATHEMATICAL DECISION PROCESS (MINIMAX UTILITY MAXIMIZATION):\n"
        "Your ultimate goal is to maximize your net utility score on every turn. Because you are blind, you must NOT trust your own spatial intuition or memory to calculate attacks, forks, or captures. You must treat the Prolog referee's tool outputs as the absolute, non-negotiable ground truth. Assume your opponent will always play the absolute best response to minimize your score.\n"
        "For every move, you are required to select 2 to 4 candidate moves and calculate their Net Utility using this formula (crucially, at least one of these candidate moves MUST be a non-capturing quiet developing or reinforcing move, such as castling, developing a minor piece, or a reinforcing pawn push):\n"
        "    Net Utility = (Material/Positional Gain by Me) - (Opponent's Maximum Material Gain on Best Response)\n\n"
        "    CRITICAL RULE FOR TENSION RESOLUTION: If a candidate move is a capture that resolves active board tension (listed in 'board_tension') for a Net Move Utility of 0, you MUST apply a -0.5 penalty to the score (Final Net Utility = -0.5) to represent the positional deficit of a premature capture. This ensures it ranks below any quiet developing/reinforcing move (which keeps its Net Utility at 0).\n\n"
        "For each candidate move, you must ask the referee to simulate the move and report the resulting tactical status. Follow this exact calculation template in your thoughts:\n"
        "1. Candidate Move: [UCI coordinate]\n"
        "   - Immediate Gain: [e.g. +1 for pawn capture, +9 for queen capture, +0 for quiet move]\n"
        "   - Simulation FEN: [You MUST query simulate_move to get the future FEN state]\n"
        "   - Opponent's Best Response: [You MUST query get_tactical_summary on the simulation FEN and identify their maximum 'forced_material_wins' gain reported by the referee]\n"
        "   - Opponent's Gain: [e.g. +3 for capturing my knight, +0 if no threats]\n"
        "   - Net Move Utility: [Immediate Gain] - [Opponent's Gain] = [Result] (Remember: apply the -0.5 tension resolution penalty if this is an equal trade of tension pieces)\n\n"
        "2. Selection: You must strictly choose the candidate move that yields the HIGHEST Net Move Utility (incorporating any -0.5 tension penalties). If a capture and a quiet developing/reinforcing move have equal utility, you MUST choose the quiet developing/reinforcing move. "
        "Do not make a move unless you have had the referee compute its Net Utility using the tools first!\n\n"
        "FIGHTING BACK IN INFERIOR / LOST POSITIONS:\n"
        "If you are in an inferior, difficult, or lost position where all candidate moves have negative Net Utility, DO NOT GIVE UP! You must play with the utmost human-like resilience and grit. A move with negative Net Utility is only considered a blunder if there exists another legal move with higher utility. If all legal moves have negative utility, you must play the one that minimizes the loss (highest/least-negative Net Utility).\n"
        "In difficult or lost positions, your strategic objective shifts from gaining material to maximum resistance. You MUST:\n"
        "1. Choose the move that yields the least negative Net Utility. If your simulated candidate move allows the opponent an immediate checkmate (mate-in-one) or major material win, you MUST NOT propose it! Instead, you must simulate other legal candidate moves (such as King moves, blocking moves, or defenses) to find a move that avoids the immediate checkmate or minimizes the loss. Proposing a move that allows immediate checkmate when another legal move escapes it is the ultimate blunder! Crucially, when evaluating King escape routes, you MUST simulate and evaluate ALL legal King moves available. You cannot assume different King moves (e.g. b1 vs d1) behave similarly or lead to the same result, as different files/ranks have completely different geometric and tactical safety profiles!\n"
        "2. Choose moves that complicate the board and prolong the game for as many moves as possible, avoiding easy trades that simplify the endgame for the opponent.\n"
        "3. Keep pieces active, defend stubbornly, and create tactical complications. Look for stalemate opportunities or trap setups that could force an opponent blunder. NEVER play a passive or random move out of defeatism!\n\n"
        "MANAGING CHESS TENSION (MAINTAINING VS. RESOLVING TENSION):\n"
        "High-level chess players avoid resolving tension too early. When opposing pawns or pieces attack each other (reported in `board_tension`), capturing immediately is often a mistake. If a capture results in a Net Utility of 0 (a neutral exchange), you MUST NOT capture! Doing so is a strategic blunder because it resolves the tension in the opponent's favor. Instead, choose a non-capturing developing or reinforcing move (e.g., developing other pieces, castling, or reinforcing the tension square) which also has a Net Utility of 0 but maintains the tension and improves your position. Keeping the tension forces the opponent to make concessions or capture on your terms! If you are worried that leaving the tension will allow the opponent to capture your piece (e.g., Bxe3) and damage your pawn structure, you MUST query the `get_attackers_defenders(fen, square)` tool for the tension square. This will show you all friendly defenders (such as a Queen or Knight) that can recapture safely without damaging your pawn structure. Recapturing with an active piece is often highly advantageous, making maintaining the tension very safe!\n\n"
        "POSITIONAL PIECE VALUATION & STRATEGIC TRADES:\n"
        "Do not evaluate trades or captures purely on standard material values (e.g., Knight=3, Bishop=3). Consider positional nuances:\n"
        "- Centralized Pieces: A Knight established on the 5th or 6th rank is extremely powerful (worth up to 5 points positionally). Avoid trading it away lightly.\n"
        "- Board Structure: Bishops are much more powerful in open positions (pawns cleared), while Knights are stronger in closed positions (locked pawns). Do not trade a strong Bishop for a weak Knight in an open game, or vice-versa.\n"
        "- Trapped or Inactive Pieces: A piece that is blocked or trapped by its own pawns is worth far less than its nominal value. Avoid capturing a trapped opponent piece if it frees their position or develops their other pieces on recapture.\n"
        "- Endgame Transitions: Trading minor pieces (like Knight for Bishop) is highly favorable if it simplifies the board and transitions you into a won King and Pawn endgame (this only applies to clear endgames, not to premature trades in the middlegame that resolve active board tension for 0 net utility).\n"
        "- Recapture Development: Do not capture opponent pieces if the recapture improves the opponent's piece placement, develops their undeveloped minor pieces, or opens critical files for their Rooks, unless the capture wins significant material.\n\n"
        "BLUNDER REFLECTION PROTOCOL:\n"
        "If you are responding to an ERROR REPORT from a previous attempt (indicating an illegal move or a rejected move):\n"
        "- You must explicitly reflect on why that move was a blunder (e.g. 'I blundered by trying to move my pinned Bishop, which would have put my King in check').\n"
        "- Explain what tactical or geometric constraint you overlooked.\n"
        "- Incorporate this lesson into your evaluation to ensure your new candidate moves are fully legal and safe.\n\n"
        "OUTPUT RULE (FINAL MOVE):\n"
        "When you are ready to propose your final move (and are not calling any tools), your response must contain your thinking process (explaining the checks, captures, threats, discoveries, the opponent's intent, the 2-4 candidate moves (including at least one quiet developing move) and their goals, and your blunder reflection if retrying) and MUST end with the final chosen move enclosed in the `<move>...</move>` tags and your updated strategy enclosed in the `<strategy>...</strategy>` tags.\n"
        "The move must be formatted in standard UCI coordinate notation (e.g. '<move>e2e4</move>' or '<move>e7e8q</move>').\n\n"
        "CASTLING REPRESENTATION IN UCI:\n"
        "In UCI coordinate notation, castling is ALWAYS represented by the King's starting square and destination square, NOT the Rook's squares:\n"
        "- White Kingside Castling (O-O): e1g1\n"
        "- White Queenside Castling (O-O-O): e1c1\n"
        "- Black Kingside Castling (o-o): e8g8\n"
        "- Black Queenside Castling (o-o-o): e8c8\n"
        "Do not write the Rook's move (e.g. do not write 'h1f1' or 'a1d1'). Alternatively, you can write standard algebraic notation for castling ('O-O' or 'O-O-O') inside the tags, and it will be parsed correctly.\n\n"
        "Example output format:\n"
        "[Your detailed positional analysis, strategy review, candidate moves, and blunder reflection if applicable]\n"
        "Therefore, the best move is:\n"
        "<strategy>My updated strategy is to control the center and develop minor pieces.</strategy>\n"
        "<move>e2e4</move>"
    )
    
    fen_parts = fen.split()
    active_color_char = fen_parts[1] if len(fen_parts) > 1 else 'w'
    active_color = "White" if active_color_char == 'w' else "Black"
    
    phase = prolog_referee.get_game_phase(fen)
    
    # Pre-calculate starting FEN data to save round-trips and prevent omissions
    try:
        start_summary = prolog_referee.get_tactical_summary(fen)
        start_material = prolog_referee.get_material_status(fen)
        start_positional = prolog_referee.get_positional_evaluation(fen)
    except Exception as e:
        print(f"Error pre-calculating starting FEN data: {e}")
        start_summary = {"in_check": False}
        start_material = {}
        start_positional = {}

    trimmed_start_summary = trim_tactical_summary(start_summary)

    user_prompt = (
        f"Current Position FEN: {fen}\n"
        f"Your Color (You are playing as): {active_color}\n"
        f"Current Game Phase: {phase.upper()}\n"
        f"\n--- STARTING POSITION TACTICAL SUMMARY (PRE-CALCULATED) ---\n"
        f"Tactical Status: {json.dumps(trimmed_start_summary)}\n"
        f"Material Status: {json.dumps(start_material)}\n"
        f"Positional Evaluation: {json.dumps(start_positional)}\n\n"
    )

    if opponents_last_move:
        user_prompt += f"Opponent's Last Move: {opponents_last_move}\n"
        if previous_fen:
            user_prompt += f"Position FEN Before Opponent's Move: {previous_fen}\n"
            
    legal_moves = prolog_referee.get_legal_moves(fen)
    # Sort legal moves to prioritize critical tactical moves at the front of the list
    try:
        sorted_moves = sort_legal_moves(legal_moves, fen, start_summary)
        user_prompt += f"Legal Moves in the Current Position (Prioritized): {', '.join(sorted_moves)}\n"
    except Exception as e:
        print(f"Error sorting legal moves: {e}")
        user_prompt += f"Legal Moves in the Current Position: {', '.join(legal_moves)}\n"
    
    if current_strategy:
        user_prompt += f"Active Long-term Strategy: {current_strategy}\n"
    else:
        user_prompt += "Active Long-term Strategy: None (Define an initial long-term strategy for this game phase now)\n"
    user_prompt += "\nEvaluate the starting tactical summary, simulate candidate moves using your tools, and make a legal move from the list."

    messages = [
        {'role': 'system', 'content': system_instruction},
        {'role': 'user', 'content': user_prompt}
    ]
    
    if error_feedback:
        messages.append({
            'role': 'user',
            'content': f"ERROR REPORT FROM PREVIOUS ATTEMPT: {error_feedback}\n Please analyze the board state carefully, query tools if needed, and select a completely different, legal coordinate path."
        })
        
    current_retry = retry_count
    max_retries = 5
    max_tool_calls_per_retry = 25
    
    simulated_count = 0
    simulated_moves = set()
    summary_called_on_start_fen = True
    initial_fen_base = " ".join(fen.split()[:4])
    
    while current_retry <= max_retries:
        got_move = False
        tool_call_count = 0
        
        def get_tactical_summary_wrapper(fen: str) -> dict:
            nonlocal summary_called_on_start_fen
            called_fen_base = " ".join(fen.split()[:4])
            if called_fen_base == initial_fen_base:
                summary_called_on_start_fen = True
            raw_summary = prolog_referee.get_tactical_summary(fen)
            return trim_tactical_summary(raw_summary)
        
        def simulate_move(fen: str, move: str) -> str:
            """
            Simulates a move and returns the resulting FEN. Use this to think ahead and look at the consequences of candidate moves.
            You are limited to simulating at most 8 moves per turn.
            
            Parameters:
            - fen: The FEN string representing the board state.
            - move: The move to simulate (in UCI format, e.g. 'e2e4').
            
            Returns:
            The FEN string of the position after the move.
            """
            nonlocal simulated_count, simulated_moves
            if simulated_count >= 8:
                return "Error: You have reached the maximum limit of 8 simulated moves. You cannot simulate any more moves. You must make your final choice based on the evaluations of the 8 moves you have already simulated."
            simulated_count += 1
            norm_move = move.strip().lower()
            simulated_moves.add(norm_move)
            return prolog_referee.simulate_move(fen, move)
            
        available_tools = {
            'get_legal_moves': prolog_referee.get_legal_moves,
            'get_tactical_summary': get_tactical_summary_wrapper,
            'convert_san_to_uci': prolog_referee.convert_san_to_uci,
            'convert_uci_to_san': prolog_referee.convert_uci_to_san,
            'simulate_move': simulate_move,
            'get_material_status': prolog_referee.get_material_status,
            'get_positional_evaluation': prolog_referee.get_positional_evaluation,
            'get_attackers_defenders': prolog_referee.get_attackers_defenders
        }
        
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_legal_moves",
                    "description": "Find all legal moves from the current position.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The FEN string representing the current board state."}
                        },
                        "required": ["fen"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_tactical_summary",
                    "description": "Consolidates check status, pinned/threatened/defended pieces, discovered attacks, forks, mate-in-1, mate-in-2, and forced material wins in a single query.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The FEN string representing the current board state."}
                        },
                        "required": ["fen"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "convert_san_to_uci",
                    "description": "Utility tool for LLM to convert a Standard Algebraic Notation (SAN) chess move to its legal UCI coordinate notation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The current FEN board state."},
                            "move_san": {"type": "string", "description": "The move string in standard algebraic notation."}
                        },
                        "required": ["fen", "move_san"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "convert_uci_to_san",
                    "description": "Utility tool for LLM to convert a UCI coordinate move to standard algebraic notation.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The current FEN board state."},
                            "move_uci": {"type": "string", "description": "The move string in UCI format."}
                        },
                        "required": ["fen", "move_uci"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "simulate_move",
                    "description": "Simulates a move and returns the resulting FEN. Note: You can simulate at most 8 moves per turn.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The FEN string representing the board state."},
                            "move": {"type": "string", "description": "The move to simulate (in UCI format, e.g. 'e2e4')."}
                        },
                        "required": ["fen", "move"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_material_status",
                    "description": "Returns pieces lost by both sides and the material advantage margin.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The FEN string representing the current board state."}
                        },
                        "required": ["fen"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_positional_evaluation",
                    "description": "Returns undeveloped pieces, passed pawns, backward pawns, weak squares, and the game phase.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The FEN string representing the current board state."}
                        },
                        "required": ["fen"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_attackers_defenders",
                    "description": "Finds all white and black pieces attacking a given square. Use this to count attackers vs defenders for trade/capture chains ('take take take').",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "fen": {"type": "string", "description": "The FEN string representing the current board state."},
                            "square": {"type": "string", "description": "The target coordinate square to check (e.g. 'd8', 'f7')."}
                        },
                        "required": ["fen", "square"]
                    }
                }
            }
        ]

        while tool_call_count < max_tool_calls_per_retry:
            try:
                # If we've made too many tool calls, force a final move generation turn without tools
                use_tools = openai_tools if tool_call_count < (max_tool_calls_per_retry - 1) else None
                if use_tools is None:
                    # Append a system/user reminder to output the move now
                    messages.append({
                        'role': 'user',
                        'content': "You have reached the maximum number of tool calls allowed. You must now propose your final move immediately in the <move>...</move> tags and updated strategy in <strategy>...</strategy> tags."
                    })
                
                # Proactively prune messages list if it exceeds context limit
                try:
                    while len(json.dumps(messages)) / 3.8 > 6500:
                        new_messages = prune_tool_call_history(messages)
                        if len(new_messages) == len(messages):
                            break
                        messages = new_messages
                except Exception as prune_err:
                    print(f"Error during message list pruning: {prune_err}")

                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=use_tools,
                    temperature=0.15,
                    frequency_penalty=0.15
                )
                
                assistant_message = response.choices[0].message
                
                # Append assistant message to chat history as standard dict
                msg_to_append = {
                    "role": "assistant",
                    "content": assistant_message.content
                }
                if assistant_message.tool_calls:
                    msg_to_append["tool_calls"] = [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                messages.append(msg_to_append)
                
                # Capture thoughts if output by the LLM
                content = assistant_message.content or ""
                if content and content.strip():
                    print(f"💭 LLM thoughts: {content.strip()}")
                    accumulated_thoughts.append(content.strip())
                
                tool_calls = assistant_message.tool_calls
                if tool_calls and use_tools is not None:
                    tool_call_count += len(tool_calls)
                    for call in tool_calls:
                        func_name = call.function.name
                        func_args = json.loads(call.function.arguments)
                        print(f"🔧 LLM calling tool: {func_name}({func_args}) (Attempt #{current_retry + 1}, Step #{tool_call_count})")
                        
                        if func_name in available_tools:
                            try:
                                result = available_tools[func_name](**func_args)
                            except Exception as e:
                                result = f"Error executing tool '{func_name}': {e}"
                        else:
                            result = f"Error: Tool {func_name} not found"
                        
                        messages.append({
                            'role': 'tool',
                            'content': str(result),
                            'tool_call_id': call.id
                        })
                    continue
                
                # No tool calls (or tools disabled): this is the final response. Find the <move> and <strategy> tags.
                move_match = re.search(r'<move>\s*(.*?)\s*</move>', content, re.IGNORECASE | re.DOTALL)
                strategy_match = re.search(r'<strategy>\s*(.*?)\s*</strategy>', content, re.IGNORECASE | re.DOTALL)
                strategy_val = strategy_match.group(1).strip() if strategy_match else (current_strategy or "Opening development")
                
                move_candidate = None
                if move_match:
                    move_candidate = move_match.group(1).strip()
                else:
                    # Fallback move extraction: check if we can parse any move directly from the raw thoughts
                    try:
                        board = chess.Board(fen)
                        extracted = extract_fallback_move(content, board)
                        if extracted:
                            move_candidate = extracted
                            print(f"💡 Fallback: Extracted move candidate '{move_candidate}' from raw thoughts content.")
                    except Exception as e:
                        print(f"Error during fallback move extraction: {e}")
                
                if move_candidate:
                    # Try to interpret as UCI first
                    raw_move = None
                    if re.match(r'^[a-h][1-8][a-h][1-8][qrbn]?$', move_candidate.lower()):
                        raw_move = move_candidate.lower()
                        # Auto-append 'q' for promotion if the piece is a pawn moving to the back rank but missing the suffix
                        if len(raw_move) == 4:
                            try:
                                board = chess.Board(fen)
                                from_sq = raw_move[:2]
                                to_sq = raw_move[2:]
                                from_square = chess.parse_square(from_sq)
                                piece = board.piece_at(from_square)
                                if piece and piece.piece_type == chess.PAWN:
                                    if (piece.color == chess.WHITE and raw_move[1] == '7' and raw_move[3] == '8') or \
                                       (piece.color == chess.BLACK and raw_move[1] == '2' and raw_move[3] == '1'):
                                        promo_move = raw_move + 'q'
                                        if chess.Move.from_uci(promo_move) in board.legal_moves:
                                            raw_move = promo_move
                                            print(f"✨ Auto-promoted pawn move '{move_candidate}' to '{raw_move}'")
                            except Exception as e:
                                print(f"Error checking auto-promotion: {e}")
                    else:
                        # Try to interpret as SAN (Standard Algebraic Notation)
                        try:
                            board = chess.Board(fen)
                            # Normalize castle representations
                            san_candidate = move_candidate
                            if san_candidate.lower() in ('o-o', '0-0'):
                                san_candidate = 'O-O'
                            elif san_candidate.lower() in ('o-o-o', '0-0-0'):
                                san_candidate = 'O-O-O'
                            
                            candidates = [san_candidate]
                            if len(san_candidate) >= 2 and san_candidate[0] in ('n', 'b', 'r', 'q', 'k'):
                                candidates.append(san_candidate[0].upper() + san_candidate[1:])
                                
                            parsed_move = None
                            for cand in candidates:
                                try:
                                    parsed_move = board.parse_san(cand)
                                    break
                                except Exception:
                                    pass
                            
                            if parsed_move:
                                raw_move = parsed_move.uci()
                                print(f"✨ Converted SAN move '{move_candidate}' to UCI '{raw_move}'")
                        except Exception as e:
                            print(f"Error parsing SAN move: {e}")
                    
                    if raw_move:
                        print(f"🧠 LLM proposed: {raw_move} (Attempt #{current_retry + 1})")
                        
                        # Programmatic tool calling enforcement guardrail
                        if use_tools is not None and not summary_called_on_start_fen:
                            explanation_msg = (
                                "ERROR: You proposed a move without querying the board's tactical summary first. "
                                "To prevent blunders, you are required to call get_tactical_summary on the current FEN "
                                "before finalizing your decision. Please query the tool now."
                            )
                            print("⚠️ Rejection reason: get_tactical_summary was not called on the current FEN.")
                            messages = [
                                {'role': 'system', 'content': system_instruction},
                                {'role': 'user', 'content': user_prompt}
                            ]
                            if content and content.strip():
                                messages.append({
                                    'role': 'assistant',
                                    'content': f"My thoughts/plan/strategy from previous step:\nActive Strategy: {strategy_val}\nThoughts: {content.strip()}"
                                })
                            messages.append({
                                'role': 'user',
                                'content': explanation_msg
                            })
                            current_retry += 1
                            got_move = True
                            break

                        # Programmatic simulation enforcement guardrail
                        # Allow exceptions for mate-in-1, mate-in-2, and forced material wins
                        is_forced_tactical = False
                        try:
                            forced_moves = []
                            if isinstance(start_summary.get("mate_in_one"), list):
                                forced_moves.extend(start_summary["mate_in_one"])
                            if isinstance(start_summary.get("mate_in_two"), list):
                                forced_moves.extend(start_summary["mate_in_two"])
                            if isinstance(start_summary.get("forced_material_wins"), list):
                                for f_win in start_summary["forced_material_wins"]:
                                    if isinstance(f_win, dict) and "move" in f_win:
                                        forced_moves.append(f_win["move"])
                            if raw_move in forced_moves:
                                is_forced_tactical = True
                        except Exception as e:
                            print(f"Error checking forced tactical moves: {e}")

                        if use_tools is not None and len(legal_moves) > 1 and raw_move not in simulated_moves and not is_forced_tactical:
                            explanation_msg = (
                                f"ERROR: You proposed the move '{raw_move}' without simulating it first. "
                                f"Because you are blind, you must simulate a candidate move using the simulate_move tool "
                                f"and check the resulting FEN's tactical summary before playing it. "
                                f"Please call simulate_move(fen, '{raw_move}') to verify its safety first."
                            )
                            print(f"⚠️ Rejection reason: proposed move '{raw_move}' was not simulated.")
                            messages = [
                                {'role': 'system', 'content': system_instruction},
                                {'role': 'user', 'content': user_prompt}
                            ]
                            if content and content.strip():
                                messages.append({
                                    'role': 'assistant',
                                    'content': f"My thoughts/plan/strategy from previous step:\nActive Strategy: {strategy_val}\nThoughts: {content.strip()}"
                                })
                            messages.append({
                                'role': 'user',
                                'content': explanation_msg
                            })
                            current_retry += 1
                            got_move = True
                            break
                        
                        # Validate move using Prolog
                        is_legal, explanation_msg = prolog_referee.check_move_diagnostics(fen, raw_move)
                        if is_legal:
                            return raw_move, current_retry, "\n".join(accumulated_thoughts), strategy_val
                        else:
                            print(f"⚠️ Rejection reason from Prolog: {explanation_msg}")
                            # Rebuild messages to prune history and keep context window small
                            messages = [
                                {'role': 'system', 'content': system_instruction},
                                {'role': 'user', 'content': user_prompt}
                            ]
                            if content and content.strip():
                                messages.append({
                                    'role': 'assistant',
                                    'content': f"My thoughts/plan/strategy from previous step:\nActive Strategy: {strategy_val}\nThoughts: {content.strip()}"
                                })
                            messages.append({
                                'role': 'user',
                                'content': f"PREVIOUS ATTEMPT FAILURE: The move '{raw_move}' is illegal. Reason: {explanation_msg}. Please analyze the board and propose a completely different, legal coordinate path."
                            })
                            current_retry += 1
                            got_move = True  # break the inner loop and start next retry
                            break
                    else:
                        # Parsing failed
                        explanation_msg = (
                            f"ERROR: Could not parse your move '{move_candidate}'. "
                            "Please specify your move in standard UCI coordinate notation (e.g. e2e4) "
                            "or standard algebraic notation (e.g. Nf3, c6, exd5, O-O) inside the <move>...</move> tags."
                        )
                        print(f"⚠️ Rejection reason: failed to parse move '{move_candidate}'")
                        # Rebuild messages to prune history
                        messages = [
                            {'role': 'system', 'content': system_instruction},
                            {'role': 'user', 'content': user_prompt}
                        ]
                        if content and content.strip():
                            messages.append({
                                'role': 'assistant',
                                'content': f"My thoughts/plan/strategy from previous step:\nActive Strategy: {strategy_val}\nThoughts: {content.strip()}"
                            })
                        messages.append({
                            'role': 'user',
                            'content': explanation_msg
                        })
                        current_retry += 1
                        got_move = True
                        break
                else:
                    # Missing move tag format
                    explanation_msg = (
                        "ERROR: Your response did not contain the required <move>...</move> tags. "
                        "Do not start over from scratch or repeat your full analysis. Just state your chosen move "
                        "enclosed in the tags, e.g., <move>e2e4</move>, and your updated strategy in <strategy>...</strategy> tags."
                    )
                    print("⚠️ Rejection reason: missing <move> tag format.")
                    # Rebuild messages to prune history
                    messages = [
                        {'role': 'system', 'content': system_instruction},
                        {'role': 'user', 'content': user_prompt}
                    ]
                    if content and content.strip():
                        messages.append({
                            'role': 'assistant',
                            'content': f"My thoughts/plan/strategy from previous step:\nActive Strategy: {strategy_val}\nThoughts: {content.strip()}"
                        })
                    messages.append({
                        'role': 'user',
                        'content': explanation_msg
                    })
                    current_retry += 1
                    got_move = True
                    break
            except Exception as e:
                import traceback
                print(f"Error during OpenAI tool call loop: {e}")
                traceback.print_exc()
                
                # Rebuild messages to clear context bloat and allow a successful retry
                try:
                    messages = [
                        {'role': 'system', 'content': system_instruction},
                        {'role': 'user', 'content': user_prompt}
                    ]
                    messages.append({
                        'role': 'user',
                        'content': f"PREVIOUS ATTEMPT FAILURE: API request failed with error: {e}. We have pruned the tool history. Please analyze the board and choose a legal move."
                    })
                except Exception as rebuild_err:
                    print(f"Error rebuilding messages on exception: {rebuild_err}")
                
                current_retry += 1
                got_move = True
                break
        
        if not got_move:
            print("⚠️ Warning: Tool call limit reached. Moving to next retry attempt.")
            current_retry += 1

    # --- LAST RESORT FALLBACK ---
    try:
        print("🚨 CRITICAL: LLM failed to produce a valid legal move after all retries. Executing last-resort fallback.")
        legal_moves = prolog_referee.get_legal_moves(fen)
        if legal_moves:
            fallback_move = legal_moves[0]
            print(f"🎲 Fallback Selected: Played first legal move '{fallback_move}' to avoid resignation.")
            return fallback_move, current_retry, "\n".join(accumulated_thoughts) + "\n[System Fallback Used]", current_strategy or "Defensive fallback"
    except Exception as fallback_err:
        print(f"Error during last-resort fallback execution: {fallback_err}")


# --- Lichess Event Framework ---

def process_game(client, game_id, my_color, model_name):
    """Listens to the active Lichess game stream and reacts when it is the bot's turn."""
    # Initialize game strategy
    current_strategy = "Develop minor pieces, control the center, and prepare to castle."
    
    for event in client.bots.stream_game_state(game_id):
        if event['type'] == 'gameFull' or event['type'] == 'gameState':
            state = event if event['type'] == 'gameFull' else event
            moves_list = state['state']['moves'].split() if 'state' in state else state['moves'].split()
            
            board = chess.Board()
            for m in moves_list:
                board.push_uci(m)
                
            is_my_turn = (board.turn == chess.WHITE and my_color == 'white') or (board.turn == chess.BLACK and my_color == 'black')
            
            if is_my_turn and not board.is_game_over():
                print(f"🤖 Bot turn detected. Current FEN: {board.fen()}")
                
                # Reconstruct previous FEN and get opponent's last move
                if moves_list:
                    temp_board = chess.Board()
                    for m in moves_list[:-1]:
                        temp_board.push_uci(m)
                    previous_fen = temp_board.fen()
                    opponents_last_move = moves_list[-1]
                else:
                    previous_fen = None
                    opponents_last_move = None
                
                # --- START RESEARCH EXPERIMENT MEASUREMENT ---
                start_time = time.time()
                move_number = (len(board.move_stack) // 2) + 1
                
                ai_move, retry_count, thoughts, updated_strategy = get_legal_llm_move(
                    board.fen(), 
                    model_name=model_name,
                    current_strategy=current_strategy,
                    previous_fen=previous_fen,
                    opponents_last_move=opponents_last_move
                )
                
                elapsed_time = time.time() - start_time
                # --- END RESEARCH EXPERIMENT MEASUREMENT ---
                
                if ai_move:
                    current_strategy = updated_strategy
                    print(f"🎯 Updated active strategy: {current_strategy}")
                    
                    log_experiment_data(game_id, move_number, board.fen(), retry_count, elapsed_time, model_name, thoughts, current_strategy)
                    log_experiment_data_json(game_id, move_number, board.fen(), ai_move, retry_count, elapsed_time, model_name, thoughts, current_strategy)
 
                    # Wrap submission in try/except block to handle remote game termination gracefully
                    try:
                        client.bots.make_move(game_id, ai_move)
                        print(f"✅ Published move {ai_move} straight to Lichess.")
                    except berserk.exceptions.ResponseError:
                        print("⚠️ Move submission skipped: The game room has already closed.")
                        break
                else:
                    print("❌ Bot failed to find legal move. Resigning game.")
                    try:
                        client.bots.resign_game(game_id)
                    except berserk.exceptions.ResponseError:
                        pass
                    break
 
def main():
    API_TOKEN = os.environ.get("LICHESS_API_TOKEN")
    MY_PERSONAL_USERNAME = os.environ.get("LICHESS_MY_USERNAME", "rusticpenn")
    MODEL_NAME = os.environ.get("LICHESS_MODEL_NAME", "cyankiwi/gemma-4-26B-A4B-it-AWQ-4bit")
    
    if not API_TOKEN:
        print("❌ Error: LICHESS_API_TOKEN environment variable is not set.")
        print("Please set it in your .env file or export it in your shell.")
        return

    session = berserk.TokenSession(API_TOKEN)
    client = berserk.Client(session)
    
    try:
        profile = client.account.get()
        username = profile.get('username')
        is_bot = profile.get('title') == 'BOT'
        
        if not is_bot:
            print("\n" + "*" * 80)
            print("⚠️ WARNING: Your Lichess account is NOT currently designated as a BOT account.")
            print(f"Account profile: https://lichess.org/@/{username}")
            print("Upgrading an account to a BOT designation is IRREVERSIBLE on Lichess.")
            print("Once upgraded, you will only be able to play against bots/AI or accept challenges,")
            print("and you can NEVER play standard rated games against regular human players on this account.")
            print("*" * 80 + "\n")
            
            response = input(f"Do you want to permanently upgrade '{username}' to a BOT account? (yes/no): ")
            if response.strip().lower() in ('yes', 'y'):
                print("Upgrading to BOT...")
                client.account.upgrade_to_bot()
                print("Successfully upgraded Lichess account designation to BOT.")
            else:
                print("Aborting. Bot initialization halted to prevent account modification.")
                return
    except Exception as e:
        print(f"Warning: Could not fetch account details or check BOT status: {e}")
        print("Continuing initialization under the assumption that the account is already a BOT...")
 
    print("\n📡 Listening for private challenges from your main account on Lichess...")
    
    for event in client.bots.stream_incoming_events():
        if event['type'] == 'challenge':
            challenge = event['challenge']
            challenger = challenge['challenger']['id']
            
            if challenger.lower() == MY_PERSONAL_USERNAME.lower():
                print(f"⚔️ Accepting private challenge from {MY_PERSONAL_USERNAME}!")
                client.bots.accept_challenge(challenge['id'])
            else:
                print(f"🚫 Declined random public challenge from user: {challenger}")
                client.bots.decline_challenge(challenge['id'])
                
        elif event['type'] == 'gameStart':
            game_id = event['game']['id']
            game_full = next(client.bots.stream_game_state(game_id))
            my_id = client.account.get()['id']
            my_color = 'white' if game_full['white'].get('id') == my_id else 'black'
            
            print(f"🏁 Game started! Game ID: {game_id}. Playing as {my_color.upper()}.")
            process_game(client, game_id, my_color, MODEL_NAME)
            print("🏁 Game concluded. Returning to listener state.")

if __name__ == "__main__":
    main()
    
