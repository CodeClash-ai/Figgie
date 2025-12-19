#!/usr/bin/env python3
"""
Tests for the Figgie game engine.

Tests cover:
- Deck creation and card distribution
- Order book and quote management
- Action validation
- Trade execution
- Score calculation (verified against official examples)
- Simultaneous tick model
"""

import unittest
from engine import (
    SUITS,
    BLACK_SUITS,
    RED_SUITS,
    STARTING_MONEY,
    POT,
    CARD_BONUS,
    get_ante,
    Quote,
    OrderBook,
    FiggieGame,
    create_deck,
    deal_cards,
    validate_action,
    execute_action,
    calculate_scores,
)

ANTE = get_ante(4)


class TestDeckCreation(unittest.TestCase):
    """Test deck creation and distribution."""

    def test_deck_has_40_cards(self):
        """Deck should have exactly 40 cards."""
        for _ in range(100):
            suit_counts, _ = create_deck()
            total = sum(suit_counts.values())
            self.assertEqual(total, 40)

    def test_deck_has_correct_distribution(self):
        """Deck should have one 12, two 10s, and one 8."""
        for _ in range(100):
            suit_counts, _ = create_deck()
            counts = sorted(suit_counts.values())
            self.assertEqual(counts, [8, 10, 10, 12])

    def test_goal_suit_same_color_as_12(self):
        """Goal suit should be same color as the 12-card suit."""
        for _ in range(100):
            suit_counts, goal_suit = create_deck()
            twelve_suit = [s for s, c in suit_counts.items() if c == 12][0]

            if twelve_suit in BLACK_SUITS:
                self.assertIn(goal_suit, BLACK_SUITS)
            else:
                self.assertIn(goal_suit, RED_SUITS)

    def test_goal_suit_not_12_card_suit(self):
        """Goal suit should not be the 12-card suit itself."""
        for _ in range(100):
            suit_counts, goal_suit = create_deck()
            twelve_suit = [s for s, c in suit_counts.items() if c == 12][0]
            self.assertNotEqual(goal_suit, twelve_suit)

    def test_goal_suit_has_8_or_10(self):
        """Goal suit should have 8 or 10 cards."""
        for _ in range(100):
            suit_counts, goal_suit = create_deck()
            self.assertIn(suit_counts[goal_suit], [8, 10])


class TestDealCards(unittest.TestCase):
    """Test card dealing."""

    def test_deal_4_players(self):
        """4 players should get 10 cards each."""
        suit_counts, _ = create_deck()
        hands = deal_cards(suit_counts, 4)

        self.assertEqual(len(hands), 4)
        for hand in hands:
            total = sum(hand.values())
            self.assertEqual(total, 10)

    def test_deal_5_players(self):
        """5 players should get 8 cards each."""
        suit_counts, _ = create_deck()
        hands = deal_cards(suit_counts, 5)

        self.assertEqual(len(hands), 5)
        for hand in hands:
            total = sum(hand.values())
            self.assertEqual(total, 8)

    def test_deal_preserves_total(self):
        """Total cards dealt should equal deck size."""
        suit_counts, _ = create_deck()

        for num_players in [4, 5]:
            hands = deal_cards(suit_counts, num_players)
            total_dealt = sum(sum(h.values()) for h in hands)
            expected = 40 if num_players == 4 else 40
            self.assertEqual(total_dealt, expected)


class TestOrderBook(unittest.TestCase):
    """Test order book functionality."""

    def test_empty_quotes(self):
        """New order book should have no valid quotes."""
        book = OrderBook(suit="spades")
        self.assertFalse(book.bid.is_valid())
        self.assertFalse(book.ask.is_valid())

    def test_set_bid(self):
        """Can set a bid quote."""
        book = OrderBook(suit="spades")
        book.bid = Quote(price=10, player_id=0)
        self.assertTrue(book.bid.is_valid())
        self.assertEqual(book.bid.price, 10)
        self.assertEqual(book.bid.player_id, 0)

    def test_set_ask(self):
        """Can set an ask quote."""
        book = OrderBook(suit="spades")
        book.ask = Quote(price=15, player_id=1)
        self.assertTrue(book.ask.is_valid())
        self.assertEqual(book.ask.price, 15)
        self.assertEqual(book.ask.player_id, 1)

    def test_reset_quotes(self):
        """Reset should clear all quotes."""
        book = OrderBook(suit="spades")
        book.bid = Quote(price=10, player_id=0)
        book.ask = Quote(price=15, player_id=1)
        book.reset_quotes()
        self.assertFalse(book.bid.is_valid())
        self.assertFalse(book.ask.is_valid())

    def test_to_dict(self):
        """to_dict should return proper structure."""
        book = OrderBook(suit="spades")
        book.bid = Quote(price=10, player_id=0)
        book.last_trade_price = 12

        d = book.to_dict()
        self.assertEqual(d["bid"]["price"], 10)
        self.assertEqual(d["bid"]["player"], 0)
        self.assertIsNone(d["ask"])
        self.assertEqual(d["last_trade"], 12)


class TestValidateAction(unittest.TestCase):
    """Test action validation."""

    def setUp(self):
        self.game = FiggieGame(num_players=4)
        self.game.goal_suit = "diamonds"
        for i in range(4):
            self.game.hands[i] = {"spades": 3, "clubs": 3, "hearts": 2, "diamonds": 2}
            self.game.money[i] = STARTING_MONEY - ANTE

    def test_pass_always_valid(self):
        """Pass action should always be valid."""
        valid, _ = validate_action(self.game, 0, {"type": "pass"})
        self.assertTrue(valid)

    def test_bid_valid(self):
        """Valid bid should pass validation."""
        valid, _ = validate_action(
            self.game, 0, {"type": "bid", "suit": "spades", "price": 10}
        )
        self.assertTrue(valid)

    def test_bid_must_improve(self):
        """Bid must be higher than current best bid."""
        self.game.books["spades"].bid = Quote(price=10, player_id=1)
        valid, _ = validate_action(
            self.game, 0, {"type": "bid", "suit": "spades", "price": 10}
        )
        self.assertFalse(valid)

        valid, _ = validate_action(
            self.game, 0, {"type": "bid", "suit": "spades", "price": 11}
        )
        self.assertTrue(valid)

    def test_bid_cannot_exceed_money(self):
        """Cannot bid more than you have."""
        valid, _ = validate_action(
            self.game, 0, {"type": "bid", "suit": "spades", "price": 1000}
        )
        self.assertFalse(valid)

    def test_bid_cannot_cross_ask(self):
        """Bid cannot be >= ask price."""
        self.game.books["spades"].ask = Quote(price=10, player_id=1)
        valid, _ = validate_action(
            self.game, 0, {"type": "bid", "suit": "spades", "price": 10}
        )
        self.assertFalse(valid)

    def test_ask_valid(self):
        """Valid ask should pass validation."""
        valid, _ = validate_action(
            self.game, 0, {"type": "ask", "suit": "spades", "price": 15}
        )
        self.assertTrue(valid)

    def test_ask_must_have_cards(self):
        """Cannot ask for suit you don't have."""
        self.game.hands[0]["spades"] = 0
        valid, _ = validate_action(
            self.game, 0, {"type": "ask", "suit": "spades", "price": 15}
        )
        self.assertFalse(valid)

    def test_ask_must_improve(self):
        """Ask must be lower than current best ask."""
        self.game.books["spades"].ask = Quote(price=15, player_id=1)
        valid, _ = validate_action(
            self.game, 0, {"type": "ask", "suit": "spades", "price": 15}
        )
        self.assertFalse(valid)

        valid, _ = validate_action(
            self.game, 0, {"type": "ask", "suit": "spades", "price": 14}
        )
        self.assertTrue(valid)

    def test_ask_cannot_cross_bid(self):
        """Ask cannot be <= bid price."""
        self.game.books["spades"].bid = Quote(price=10, player_id=1)
        valid, _ = validate_action(
            self.game, 0, {"type": "ask", "suit": "spades", "price": 10}
        )
        self.assertFalse(valid)

    def test_buy_needs_ask(self):
        """Cannot buy if no ask exists."""
        valid, _ = validate_action(self.game, 0, {"type": "buy", "suit": "spades"})
        self.assertFalse(valid)

    def test_buy_valid(self):
        """Valid buy should pass."""
        self.game.books["spades"].ask = Quote(price=10, player_id=1)
        valid, _ = validate_action(self.game, 0, {"type": "buy", "suit": "spades"})
        self.assertTrue(valid)

    def test_buy_cannot_self_trade(self):
        """Cannot buy from yourself."""
        self.game.books["spades"].ask = Quote(price=10, player_id=0)
        valid, _ = validate_action(self.game, 0, {"type": "buy", "suit": "spades"})
        self.assertFalse(valid)

    def test_sell_needs_bid(self):
        """Cannot sell if no bid exists."""
        valid, _ = validate_action(self.game, 0, {"type": "sell", "suit": "spades"})
        self.assertFalse(valid)

    def test_sell_valid(self):
        """Valid sell should pass."""
        self.game.books["spades"].bid = Quote(price=10, player_id=1)
        valid, _ = validate_action(self.game, 0, {"type": "sell", "suit": "spades"})
        self.assertTrue(valid)

    def test_sell_needs_cards(self):
        """Cannot sell suit you don't have."""
        self.game.books["spades"].bid = Quote(price=10, player_id=1)
        self.game.hands[0]["spades"] = 0
        valid, _ = validate_action(self.game, 0, {"type": "sell", "suit": "spades"})
        self.assertFalse(valid)


class TestExecuteAction(unittest.TestCase):
    """Test action execution."""

    def setUp(self):
        self.game = FiggieGame(num_players=4)
        self.game.goal_suit = "diamonds"
        for i in range(4):
            self.game.hands[i] = {"spades": 3, "clubs": 3, "hearts": 2, "diamonds": 2}
            self.game.money[i] = STARTING_MONEY - ANTE

    def test_bid_sets_quote(self):
        """Bid should set the best bid."""
        execute_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 10})
        self.assertEqual(self.game.books["spades"].bid.price, 10)
        self.assertEqual(self.game.books["spades"].bid.player_id, 0)

    def test_ask_sets_quote(self):
        """Ask should set the best ask."""
        execute_action(self.game, 0, {"type": "ask", "suit": "spades", "price": 15})
        self.assertEqual(self.game.books["spades"].ask.price, 15)
        self.assertEqual(self.game.books["spades"].ask.player_id, 0)

    def test_buy_executes_trade(self):
        """Buy should execute trade at ask price."""
        self.game.books["spades"].ask = Quote(price=10, player_id=1)
        initial_buyer_money = self.game.money[0]
        initial_seller_money = self.game.money[1]

        trade = execute_action(self.game, 0, {"type": "buy", "suit": "spades"})

        self.assertIsNotNone(trade)
        self.assertEqual(trade.suit, "spades")
        self.assertEqual(trade.price, 10)
        self.assertEqual(trade.buyer_id, 0)
        self.assertEqual(trade.seller_id, 1)

        # Check money transferred
        self.assertEqual(self.game.money[0], initial_buyer_money - 10)
        self.assertEqual(self.game.money[1], initial_seller_money + 10)

        # Check cards transferred
        self.assertEqual(self.game.hands[0]["spades"], 4)
        self.assertEqual(self.game.hands[1]["spades"], 2)

    def test_sell_executes_trade(self):
        """Sell should execute trade at bid price."""
        self.game.books["spades"].bid = Quote(price=10, player_id=1)
        initial_buyer_money = self.game.money[1]
        initial_seller_money = self.game.money[0]

        trade = execute_action(self.game, 0, {"type": "sell", "suit": "spades"})

        self.assertIsNotNone(trade)
        self.assertEqual(trade.buyer_id, 1)
        self.assertEqual(trade.seller_id, 0)

        # Check money transferred
        self.assertEqual(self.game.money[0], initial_seller_money + 10)
        self.assertEqual(self.game.money[1], initial_buyer_money - 10)

    def test_trade_clears_all_books(self):
        """Trade should clear quotes in ALL suits (per Figgie rules)."""
        # Set up quotes in multiple suits
        self.game.books["spades"].bid = Quote(price=5, player_id=2)
        self.game.books["spades"].ask = Quote(price=10, player_id=1)
        self.game.books["clubs"].bid = Quote(price=7, player_id=3)

        # Execute a trade in spades
        execute_action(self.game, 0, {"type": "buy", "suit": "spades"})

        # All books should be cleared
        for suit in SUITS:
            self.assertFalse(self.game.books[suit].bid.is_valid())
            self.assertFalse(self.game.books[suit].ask.is_valid())


class TestCalculateScores(unittest.TestCase):
    """Test score calculation."""

    def test_basic_scoring(self):
        """Basic scoring with clear winner."""
        game = FiggieGame(num_players=4)
        game.goal_suit = "diamonds"
        game.hands = {
            0: {"spades": 3, "clubs": 3, "hearts": 3, "diamonds": 1},
            1: {"spades": 3, "clubs": 3, "hearts": 3, "diamonds": 1},
            2: {"spades": 3, "clubs": 3, "hearts": 3, "diamonds": 1},
            3: {"spades": 1, "clubs": 1, "hearts": 1, "diamonds": 7},
        }
        for i in range(4):
            game.money[i] = STARTING_MONEY - ANTE

        scores = calculate_scores(game)

        # Player 3 has most goal cards, should win the remainder
        self.assertGreater(scores[3], scores[0])
        self.assertGreater(scores[3], scores[1])
        self.assertGreater(scores[3], scores[2])

    def test_scores_are_zero_sum(self):
        """Net scores across all players should sum to 0."""
        for _ in range(50):
            game = FiggieGame(num_players=4)
            suit_counts, goal_suit = create_deck()
            hands = deal_cards(suit_counts, 4)

            game.goal_suit = goal_suit
            for i in range(4):
                game.hands[i] = hands[i]
                game.money[i] = STARTING_MONEY - ANTE

            scores = calculate_scores(game)
            total = sum(scores.values())
            self.assertEqual(total, 0, f"Scores {scores} sum to {total}, expected 0")

    def test_tie_splitting(self):
        """Tied winners should split the remainder evenly."""
        game = FiggieGame(num_players=4)
        game.goal_suit = "diamonds"
        game.hands = {
            0: {"spades": 2, "clubs": 2, "hearts": 2, "diamonds": 4},
            1: {"spades": 2, "clubs": 2, "hearts": 2, "diamonds": 4},
            2: {"spades": 3, "clubs": 3, "hearts": 3, "diamonds": 1},
            3: {"spades": 3, "clubs": 3, "hearts": 3, "diamonds": 1},
        }
        for i in range(4):
            game.money[i] = STARTING_MONEY - ANTE

        scores = calculate_scores(game)

        # Players 0 and 1 tied, should have equal scores
        self.assertEqual(scores[0], scores[1])
        # Players 2 and 3 also equal
        self.assertEqual(scores[2], scores[3])


class TestOfficialExamples(unittest.TestCase):
    """Test scoring against official Figgie examples from figgie.com."""

    def test_example_1_from_official_site(self):
        """
        Official Example 1 (4 players):
        Goal suit: diamonds (10 cards)
        Josef has 5 diamonds, gets $50 + $100 bonus = $150 from pot
        Net: -50 (ante) + 150 (pot) = +100
        """
        game = FiggieGame(num_players=4)
        game.goal_suit = "diamonds"
        game.hands = {
            0: {"spades": 2, "clubs": 3, "hearts": 4, "diamonds": 1},
            1: {"spades": 3, "clubs": 2, "hearts": 2, "diamonds": 3},
            2: {"spades": 3, "clubs": 2, "hearts": 0, "diamonds": 5},
            3: {"spades": 2, "clubs": 3, "hearts": 4, "diamonds": 1},
        }
        for i in range(4):
            game.money[i] = STARTING_MONEY - ANTE

        scores = calculate_scores(game)

        self.assertEqual(sum(scores.values()), 0)
        self.assertEqual(scores[0], -40)
        self.assertEqual(scores[1], -20)
        self.assertEqual(scores[2], 100)
        self.assertEqual(scores[3], -40)

    def test_example_2_from_official_site(self):
        """
        Official Example 2 (5 players):
        Goal suit: hearts (8 cards)
        Nari and Emily tied with 3 hearts each, split $120 bonus
        """
        game = FiggieGame(num_players=5)
        game.goal_suit = "hearts"
        ante_5p = get_ante(5)

        game.hands = {
            0: {"spades": 1, "clubs": 3, "hearts": 1, "diamonds": 3},
            1: {"spades": 2, "clubs": 1, "hearts": 3, "diamonds": 2},
            2: {"spades": 3, "clubs": 2, "hearts": 0, "diamonds": 3},
            3: {"spades": 1, "clubs": 2, "hearts": 1, "diamonds": 4},
            4: {"spades": 1, "clubs": 2, "hearts": 3, "diamonds": 2},
        }
        for i in range(5):
            game.money[i] = STARTING_MONEY - ante_5p

        scores = calculate_scores(game)

        self.assertEqual(sum(scores.values()), 0)
        self.assertEqual(scores[0], -30)
        self.assertEqual(scores[1], 50)
        self.assertEqual(scores[2], -40)
        self.assertEqual(scores[3], -30)
        self.assertEqual(scores[4], 50)

    def test_all_12_deck_configurations(self):
        """Verify all 12 official deck configurations."""
        official_decks = [
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

        for deck_num, (s, c, h, d, expected_goal, expected_bonus) in enumerate(
            official_decks, 1
        ):
            suit_counts = {"spades": s, "clubs": c, "hearts": h, "diamonds": d}
            twelve_suit = [suit for suit, count in suit_counts.items() if count == 12][
                0
            ]

            if twelve_suit in BLACK_SUITS:
                same_color = BLACK_SUITS
            else:
                same_color = RED_SUITS
            goal_suit = [suit for suit in same_color if suit != twelve_suit][0]

            self.assertEqual(
                goal_suit,
                expected_goal,
                f"Deck {deck_num}: expected goal {expected_goal}, got {goal_suit}",
            )

            goal_cards = suit_counts[goal_suit]
            remainder = POT - (goal_cards * CARD_BONUS)
            self.assertEqual(
                remainder,
                expected_bonus,
                f"Deck {deck_num}: expected bonus {expected_bonus}, got {remainder}",
            )


if __name__ == "__main__":
    unittest.main()
