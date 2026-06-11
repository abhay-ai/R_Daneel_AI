import queen as prolog_referee

def test_starting_position():
    print("--- Testing Starting Position ---")
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    
    # 1. Test validate_move (legal)
    is_legal, explanation = prolog_referee.check_move_diagnostics(start_fen, "e2e4")
    print(f"e2e4 legal? {is_legal} (Explanation: {explanation})")
    assert is_legal, "e2e4 should be legal"
    
    # 2. Test validate_move (illegal geometry)
    is_legal, explanation = prolog_referee.check_move_diagnostics(start_fen, "e2e5")
    print(f"e2e5 legal? {is_legal} (Explanation: {explanation})")
    assert not is_legal, "e2e5 should be illegal"
    assert "Illegal geometric trajectory" in explanation, "Should report geometry error"
    
    # 3. Test validate_move (empty square)
    is_legal, explanation = prolog_referee.check_move_diagnostics(start_fen, "e3e4")
    print(f"e3e4 legal? {is_legal} (Explanation: {explanation})")
    assert not is_legal, "e3e4 should be illegal"
    assert "completely empty" in explanation, "Should report empty starting square"

    # 4. Test get_legal_moves
    moves = prolog_referee.get_legal_moves(start_fen)
    print(f"Legal moves count: {len(moves)}")
    print(f"First 10 legal moves: {moves[:10]}")
    assert len(moves) == 20, f"Starting position has 20 legal moves, found {len(moves)}"
    assert "e2e4" in moves
    assert "g1f3" in moves
    
    # 5. Test get_game_status
    status = prolog_referee.get_game_status(start_fen)
    print(f"Game status: {status}")
    assert status["status"] == "active"
    assert status["winner"] is None

def test_checkmate_position():
    print("\n--- Testing Checkmate Position ---")
    # Scholar's mate checkmate FEN (Black's turn, King is in checkmate by Queen on f7)
    checkmate_fen = "r1bqkbnr/pppp1Qpp/2n5/4p3/2B1P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 4"
    
    # 1. Test get_game_status
    status = prolog_referee.get_game_status(checkmate_fen)
    print(f"Game status (checkmate): {status}")
    assert status["status"] == "checkmate", f"Expected checkmate, got {status['status']}"
    assert status["winner"] == "white", f"Expected white to be the winner, got {status['winner']}"
    
    # 2. Test get_legal_moves (should be 0)
    moves = prolog_referee.get_legal_moves(checkmate_fen)
    print(f"Legal moves count in checkmate: {len(moves)}")
    assert len(moves) == 0, f"Expected 0 legal moves, got {len(moves)}"

def test_pins_and_threats():
    print("\n--- Testing Pinned and Threatened Pieces ---")
    # FEN with White King on e1, White Pawn on e2, Black Rook on e8 (pinning e2)
    pin_fen = "4r3/8/8/8/8/8/4P3/4K3 w - - 0 1"
    
    pinned = prolog_referee.get_pinned_pieces(pin_fen)
    print(f"Pinned pieces: {pinned}")
    assert len(pinned) == 1, f"Expected 1 pinned piece, got {len(pinned)}"
    assert pinned[0]["piece"] == "pawn", f"Expected pawn, got {pinned[0]['piece']}"
    assert pinned[0]["square"] == "e2", f"Expected e2, got {pinned[0]['square']}"
    
    threats = prolog_referee.get_threatened_pieces(pin_fen)
    print(f"Threatened friendly pieces: {threats}")
    assert len(threats) == 1
    assert threats[0]["piece"] == "pawn"
    assert threats[0]["square"] == "e2"
    
    defended = prolog_referee.get_defended_pieces(pin_fen)
    print(f"Defended friendly pieces: {defended}")

def test_discovered_attacks():
    print("\n--- Testing Discovered Attacks ---")
    # FEN with White Rook on a1, White Knight on a4, Black Queen on a8
    discovered_fen = "q7/8/8/8/N7/8/8/R3K3 w - - 0 1"
    
    attacks = prolog_referee.get_discovered_attacks(discovered_fen)
    print(f"Discovered attack setups: {attacks}")
    assert len(attacks) > 0
    # The setup should show blocker: a4, attacker: a1, target: a8
    setup = attacks[0]
    assert setup["blocker"] == "a4"
    assert setup["attacker"] == "a1"
    assert setup["target"] == "a8"

def test_forks():
    print("\n--- Testing Forks ---")
    # Knight fork position: Knight on c7 attacking king on a8 and queen on e8
    fork_fen = "k3q3/2N5/8/8/8/8/8/4K3 w - - 0 1"
    forks_info = prolog_referee.get_forks(fork_fen)
    print(f"Forks info (existing): {forks_info['existing']}")
    assert len(forks_info["existing"]) == 1
    assert forks_info["existing"][0]["forker"] == "c7"
    assert set(forks_info["existing"][0]["targets"]) == {"a8", "e8"}
    
    # Fork-creating move: Knight on d5 can move to c7 to fork a8 and e8 (with check blocked by e2 pawn)
    create_fork_fen = "k3q3/8/8/3N4/8/8/4P3/4K3 w - - 0 1"
    forks_info2 = prolog_referee.get_forks(create_fork_fen)
    print(f"Forks info (creating moves): {forks_info2['moves_creating_forks']}")
    assert len(forks_info2["moves_creating_forks"]) > 0
    # There should be a move d5c7 that forks a8 and e8
    found_fork_move = False
    for m in forks_info2["moves_creating_forks"]:
        if m["move"] == "d5c7" and set(m["targets"]) == {"a8", "e8"}:
            found_fork_move = True
            break
    assert found_fork_move, "Should detect d5c7 creates fork on a8 and e8"

def test_tactical_summary():
    print("\n--- Testing Tactical Summary ---")
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    summary = prolog_referee.get_tactical_summary(start_fen)
    print(f"Summary keys: {list(summary.keys())}")
    assert "pinned_pieces" in summary
    assert "threatened_pieces" in summary
    assert "defended_pieces" in summary
    assert "discovered_attacks" in summary
    assert "forks" in summary
    assert "game_status" in summary

def test_material_status():
    print("\n--- Testing Material Status ---")
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    mat = prolog_referee.get_material_status(start_fen)
    print(f"Starting position material: {mat}")
    assert mat['white_lost'] == {'pawn': 0, 'knight': 0, 'bishop': 0, 'rook': 0, 'queen': 0}
    assert mat['black_lost'] == {'pawn': 0, 'knight': 0, 'bishop': 0, 'rook': 0, 'queen': 0}
    assert mat['material_values'] == {'white': 39, 'black': 39}
    assert mat['advantage'] == {'color': 'none', 'margin': 0}
    assert 'dynamic_material_values' in mat
    assert 'dynamic_advantage' in mat
    
    # Custom test position: Black has lost 1 pawn and 1 bishop
    test_fen = "r1bqk1nr/pppp1ppp/2n5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 1"
    mat2 = prolog_referee.get_material_status(test_fen)
    print(f"Custom position material: {mat2}")
    assert mat2['white_lost'] == {'pawn': 0, 'knight': 0, 'bishop': 0, 'rook': 0, 'queen': 0}
    assert mat2['black_lost'] == {'pawn': 1, 'knight': 0, 'bishop': 1, 'rook': 0, 'queen': 0}
    assert mat2['material_values'] == {'white': 39, 'black': 35}
    assert mat2['advantage'] == {'color': 'white', 'margin': 4}
    assert 'dynamic_material_values' in mat2
    assert 'dynamic_advantage' in mat2

def test_positional_evaluation():
    print("\n--- Testing Positional Evaluation ---")
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    pos = prolog_referee.get_positional_evaluation(start_fen)
    print(f"Starting position positional eval: {pos}")
    assert pos['development']['white_complete'] is False
    assert len(pos['development']['white_undeveloped']) == 4
    assert pos['development']['black_complete'] is False
    assert len(pos['development']['black_undeveloped']) == 4
    assert pos['passed_pawns'] == []
    assert pos['backward_pawns'] == []
    
    # Passed pawn FEN: White pawn on e6, no black pawns at all
    passed_fen = "k7/8/4P3/8/8/8/8/4K3 w - - 0 1"
    pos3 = prolog_referee.get_positional_evaluation(passed_fen)
    print(f"Passed FEN positional eval: {pos3}")
    assert len(pos3['passed_pawns']) == 1
    assert pos3['passed_pawns'][0]['square'] == 'e6'
    assert pos3['passed_pawns'][0]['color'] == 'white'
    
    # Backward pawn FEN: White pawn on d3, white pawns on c4 and e4, black pawn on e5 (attacks d4)
    backward_fen = "k7/8/8/4p3/2P1P3/3P4/8/4K3 w - - 0 1"
    pos4 = prolog_referee.get_positional_evaluation(backward_fen)
    print(f"Backward FEN positional eval: {pos4}")
    assert len(pos4['backward_pawns']) == 1
    assert pos4['backward_pawns'][0]['square'] == 'd3'
    assert pos4['backward_pawns'][0]['color'] == 'white'

    # Game phase check inside positional eval
    assert pos['game_phase'] == 'opening'
    assert pos3['game_phase'] == 'endgame'

def test_game_phase():
    print("\n--- Testing Game Phase Detection ---")
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    phase_start = prolog_referee.get_game_phase(start_fen)
    print(f"Starting position phase: {phase_start}")
    assert phase_start == "opening"
    
    # Middlegame FEN: all minor pieces developed, still plenty of material
    middlegame_fen = "r1bqk2r/pppp1ppp/2n1pn2/2b5/2B1P3/2N1BN2/PPPP1PPP/R2QK2R w KQkq - 0 1"
    phase_mid = prolog_referee.get_game_phase(middlegame_fen)
    print(f"Middlegame phase: {phase_mid}")
    assert phase_mid == "middlegame"
    
    # Endgame FEN: very little material
    endgame_fen = "k7/8/4P3/8/8/8/8/4K3 w - - 0 1"
    phase_end = prolog_referee.get_game_phase(endgame_fen)
    print(f"Endgame phase: {phase_end}")
    assert phase_end == "endgame"

def test_mate_in_one():
    print("\n--- Testing Mate in One ---")
    # Scholar's mate setup (White to move, f3f7 is checkmate)
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5Q2/PPPP1PPP/RNB1KBNR w KQkq - 4 4"
    mates = prolog_referee.get_mate_in_one(fen)
    print(f"Mate in one moves: {mates}")
    assert "f3f7" in mates, f"Expected f3f7 in mate_in_one, got {mates}"

def test_mate_in_two():
    print("\n--- Testing Mate in Two ---")
    # Staircase mate setup: White to move, h3h7 is blocked, so h3b3 or h2b2 are the correct mates in 2
    fen = "k7/8/8/8/8/7R/7R/K7 w - - 0 1"
    mates = prolog_referee.get_mate_in_two(fen)
    print(f"Mate in two moves: {mates}")
    assert "h3b3" in mates, f"Expected h3b3 in mate_in_two, got {mates}"

def test_mate_in_three():
    print("\n--- Testing Mate in Three ---")
    # FEN from 02Lqe puzzle where White plays a6a8, forcing checkmate in 3 moves
    fen = "6k1/5ppp/R2r4/p3r3/8/1P4P1/5P1P/6K1 w - - 0 25"
    mates = prolog_referee.get_mate_in_three(fen)
    print(f"Mate in three moves: {mates}")
    assert "a6a8" in mates, f"Expected a6a8 in mate_in_three, got {mates}"

def test_forced_material_wins():
    print("\n--- Testing Forced Material Wins ---")
    # Knight fork setup: Knight on d5 can fork King on a8 and Queen on e8.
    # FEN: Black King on a8, Black Queen on e8, White Knight on d5.
    # Black Bishop on a7 is NOT attacking c7.
    # Move d5c7 forks a8 and e8, winning the Queen.
    fen = "k3q3/b7/8/3N4/8/8/4P3/4K3 w - - 0 1"
    wins = prolog_referee.get_forced_material_wins(fen)
    print(f"Forced material wins: {wins}")
    # Should show move d5c7 with gain of 9 (Queen)
    found_win = False
    for w in wins:
        if w['move'] == 'd5c7' and w['gain'] == 9:
            found_win = True
            break
    assert found_win, f"Expected d5c7 with gain of 9, got {wins}"

if __name__ == "__main__":
    test_starting_position()
    test_checkmate_position()
    test_pins_and_threats()
    test_discovered_attacks()
    test_forks()
    test_tactical_summary()
    test_material_status()
    test_positional_evaluation()
    test_game_phase()
    test_mate_in_one()
    test_mate_in_two()
    test_mate_in_three()
    test_forced_material_wins()
    print("\n✅ All tests passed successfully!")
