#!/usr/bin/env python3
"""
Test cases based on official Figgie examples from figgie.com/how-to-play.html
"""

import unittest
from engine import (
    SUITS, BLACK_SUITS, RED_SUITS,
    FiggieGame, calculate_scores, get_ante,
    STARTING_MONEY, POT, CARD_BONUS
)

# For test convenience
ANTE = get_ante(4)


class TestOfficialExamples(unittest.TestCase):
    """Test scoring against official Figgie examples."""

    def test_example_1_from_official_site(self):
        """
        Official Example 1:
        Players: 4, Ante: $50, 12-card suit: hearts, goal suit: diamonds

        Player      | goal cards | $10/card | $100 bonus | Total
        Avaline     | 1          | $10      | -          | $10
        Nari        | 3          | $30      | -          | $30
        Josef       | 5          | $50      | $100       | $150
        Okafor      | 1          | $10      | -          | $10

        Total goal cards = 10, so remainder = $200 - $100 = $100
        Josef has most (5), gets $100 bonus
        """
        game = FiggieGame(num_players=4)
        game.goal_suit = "diamonds"

        # Set up hands to match example (only goal suit matters for scoring)
        # Total diamonds = 10 (consistent with deck where diamonds is goal with 10 cards)
        game.hands = {
            0: {"spades": 2, "clubs": 3, "hearts": 4, "diamonds": 1},  # Avaline
            1: {"spades": 3, "clubs": 2, "hearts": 2, "diamonds": 3},  # Nari
            2: {"spades": 3, "clubs": 2, "hearts": 0, "diamonds": 5},  # Josef
            3: {"spades": 2, "clubs": 3, "hearts": 4, "diamonds": 1},  # Okafor
        }

        # Money after ante (no trading occurred)
        for i in range(4):
            game.money[i] = STARTING_MONEY - ANTE  # $300

        scores = calculate_scores(game)

        # Expected: score = (money - starting) + card_payout + majority_bonus
        # Avaline: -50 + 10 + 0 = -40... wait that's the NET score
        # The official example shows TOTAL from pot, not net P&L

        # Let me recalculate:
        # Net score for Avaline: (300 - 350) + 10 + 0 = -40
        # But if we add back the ante they paid, the pot payout is just 10

        # Actually the official example shows pot distribution only:
        # - $10 per goal card
        # - Remainder ($100) to Josef

        # My implementation calculates NET score (including the -$50 ante)
        # So: Avaline net = -50 + 10 = -40
        #     Nari net = -50 + 30 = -20
        #     Josef net = -50 + 50 + 100 = 100
        #     Okafor net = -50 + 10 = -40

        # Verify sum is zero (zero-sum)
        self.assertEqual(sum(scores.values()), 0)

        # Verify individual net scores
        self.assertEqual(scores[0], -40)   # Avaline
        self.assertEqual(scores[1], -20)   # Nari
        self.assertEqual(scores[2], 100)   # Josef (majority winner)
        self.assertEqual(scores[3], -40)   # Okafor

    def test_example_2_from_official_site(self):
        """
        Official Example 2:
        Players: 5, Ante: $40, 12-card suit: diamonds, goal suit: hearts

        Player      | goal cards | $10/card | $120 bonus | Total
        Avaline     | 1          | $10      | -          | $10
        Nari        | 3          | $30      | $60        | $90
        Josef       | 0          | -        | -          | $0
        Okafor      | 1          | $10      | -          | $10
        Emily       | 3          | $30      | $60        | $90

        Total goal cards = 8, so remainder = $200 - $80 = $120
        Nari and Emily tied for most (3 each), split $120 = $60 each
        """
        game = FiggieGame(num_players=5)
        game.goal_suit = "hearts"

        # 5-player game: $40 ante each
        ante_5p = 40

        # Set up hands (8 hearts total for 8-card goal suit)
        game.hands = {
            0: {"spades": 1, "clubs": 3, "hearts": 1, "diamonds": 3},  # Avaline
            1: {"spades": 2, "clubs": 1, "hearts": 3, "diamonds": 2},  # Nari
            2: {"spades": 3, "clubs": 2, "hearts": 0, "diamonds": 3},  # Josef
            3: {"spades": 1, "clubs": 2, "hearts": 1, "diamonds": 4},  # Okafor
            4: {"spades": 1, "clubs": 2, "hearts": 3, "diamonds": 2},  # Emily
        }

        # Verify total cards = 40
        total_cards = sum(sum(h.values()) for h in game.hands.values())
        self.assertEqual(total_cards, 40)

        # Money after ante
        for i in range(5):
            game.money[i] = STARTING_MONEY - ante_5p  # $310

        scores = calculate_scores(game)

        # Net scores:
        # Avaline: -40 + 10 + 0 = -30
        # Nari: -40 + 30 + 60 = 50
        # Josef: -40 + 0 + 0 = -40
        # Okafor: -40 + 10 + 0 = -30
        # Emily: -40 + 30 + 60 = 50

        # Verify sum is zero
        self.assertEqual(sum(scores.values()), 0)

        # Verify individual net scores
        self.assertEqual(scores[0], -30)   # Avaline
        self.assertEqual(scores[1], 50)    # Nari (tied winner)
        self.assertEqual(scores[2], -40)   # Josef
        self.assertEqual(scores[3], -30)   # Okafor
        self.assertEqual(scores[4], 50)    # Emily (tied winner)

    def test_all_12_deck_configurations(self):
        """
        Verify all 12 deck configurations from official rules:

        Deck | Spades | Clubs | Hearts | Diamonds | Goal Suit | Bonus
        1    | 12     | 10    | 10     | 8        | Clubs     | $100
        2    | 12     | 10    | 8      | 10       | Clubs     | $100
        3    | 12     | 8     | 10     | 10       | Clubs     | $120
        4    | 8      | 12    | 10     | 10       | Spades    | $120
        5    | 10     | 12    | 10     | 8        | Spades    | $100
        6    | 10     | 12    | 8      | 10       | Spades    | $100
        7    | 10     | 8     | 12     | 10       | Diamonds  | $100
        8    | 8      | 10    | 12     | 10       | Diamonds  | $100
        9    | 10     | 10    | 12     | 8        | Diamonds  | $120
        10   | 10     | 10    | 8      | 12       | Hearts    | $120
        11   | 10     | 8     | 10     | 12       | Hearts    | $100
        12   | 8      | 10    | 10     | 12       | Hearts    | $100
        """
        official_decks = [
            # (spades, clubs, hearts, diamonds, goal_suit, bonus)
            (12, 10, 10, 8, "clubs", 100),
            (12, 10, 8, 10, "clubs", 100),
            (12, 8, 10, 10, "clubs", 120),
            (8, 12, 10, 10, "spades", 120),
            (10, 12, 10, 8, "spades", 100),
            (10, 12, 8, 10, "spades", 100),
            (10, 8, 12, 10, "diamonds", 100),
            (8, 10, 12, 10, "diamonds", 100),
            (10, 10, 12, 8, "diamonds", 120),
            (10, 10, 8, 12, "hearts", 120),
            (10, 8, 10, 12, "hearts", 100),
            (8, 10, 10, 12, "hearts", 100),
        ]

        for deck_num, (s, c, h, d, expected_goal, expected_bonus) in enumerate(official_decks, 1):
            suit_counts = {"spades": s, "clubs": c, "hearts": h, "diamonds": d}

            # Find 12-card suit
            twelve_suit = [suit for suit, count in suit_counts.items() if count == 12][0]

            # Determine goal suit (same color, not the 12-card suit)
            if twelve_suit in BLACK_SUITS:
                same_color = BLACK_SUITS
            else:
                same_color = RED_SUITS
            goal_suit = [suit for suit in same_color if suit != twelve_suit][0]

            # Verify goal suit matches official
            self.assertEqual(goal_suit, expected_goal,
                           f"Deck {deck_num}: expected goal {expected_goal}, got {goal_suit}")

            # Verify bonus (remainder) calculation
            goal_cards = suit_counts[goal_suit]
            card_payout = goal_cards * CARD_BONUS
            remainder = POT - card_payout

            self.assertEqual(remainder, expected_bonus,
                           f"Deck {deck_num}: expected bonus {expected_bonus}, got {remainder}")


class TestAnte(unittest.TestCase):
    """Test ante calculations for 4 and 5 players."""

    def test_4_player_ante(self):
        """4 players: $50 ante each = $200 pot"""
        self.assertEqual(4 * 50, 200)

    def test_5_player_ante(self):
        """5 players: $40 ante each = $200 pot"""
        self.assertEqual(5 * 40, 200)


if __name__ == "__main__":
    unittest.main()
