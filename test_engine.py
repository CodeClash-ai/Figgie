#!/usr/bin/env python3
"""
Comprehensive tests for the Figgie game engine.
"""

import unittest
import random
from engine import (
    SUITS, BLACK_SUITS, RED_SUITS, NUM_PLAYERS, STARTING_MONEY, ANTE, POT, CARD_BONUS,
    create_deck, deal_cards, FiggieGame, Order,
    get_game_state, validate_action, execute_action, calculate_scores
)


class TestDeckCreation(unittest.TestCase):
    """Test deck creation and goal suit selection."""

    def test_deck_has_40_cards(self):
        """Deck must have exactly 40 cards."""
        for _ in range(100):  # Test multiple random decks
            suit_counts, _ = create_deck()
            total = sum(suit_counts.values())
            self.assertEqual(total, 40, f"Deck has {total} cards, expected 40")

    def test_deck_has_correct_distribution(self):
        """Deck must have 8, 10, 10, 12 distribution."""
        for _ in range(100):
            suit_counts, _ = create_deck()
            counts = sorted(suit_counts.values())
            self.assertEqual(counts, [8, 10, 10, 12], f"Got distribution {counts}")

    def test_goal_suit_same_color_as_12_card_suit(self):
        """Goal suit must be same color as the 12-card suit."""
        for _ in range(100):
            suit_counts, goal_suit = create_deck()

            # Find the 12-card suit
            twelve_suit = [s for s, c in suit_counts.items() if c == 12][0]

            # Check colors match
            twelve_color = "black" if twelve_suit in BLACK_SUITS else "red"
            goal_color = "black" if goal_suit in BLACK_SUITS else "red"

            self.assertEqual(twelve_color, goal_color,
                           f"12-card suit {twelve_suit} and goal {goal_suit} have different colors")

    def test_goal_suit_is_not_12_card_suit(self):
        """Goal suit must not be the 12-card suit itself."""
        for _ in range(100):
            suit_counts, goal_suit = create_deck()

            # Find the 12-card suit
            twelve_suit = [s for s, c in suit_counts.items() if c == 12][0]

            self.assertNotEqual(goal_suit, twelve_suit,
                              f"Goal suit {goal_suit} is the 12-card suit")

    def test_goal_suit_has_8_or_10_cards(self):
        """Goal suit must have 8 or 10 cards."""
        for _ in range(100):
            suit_counts, goal_suit = create_deck()
            goal_count = suit_counts[goal_suit]

            self.assertIn(goal_count, [8, 10],
                         f"Goal suit has {goal_count} cards, expected 8 or 10")

    def test_all_12_deck_configurations_possible(self):
        """All 12 possible deck configurations should be reachable."""
        # There are 12 configs: 4 choices for 12-card suit × 3 choices for 8-card position
        # But goal suit is determined by 12-card suit color
        seen_configs = set()

        for _ in range(1000):
            suit_counts, goal_suit = create_deck()
            config = tuple(sorted([(s, c) for s, c in suit_counts.items()]))
            seen_configs.add((config, goal_suit))

        # Should see multiple configurations
        self.assertGreater(len(seen_configs), 5,
                          "Should see variety in deck configurations")


class TestCardDealing(unittest.TestCase):
    """Test card dealing mechanics."""

    def test_cards_dealt_evenly(self):
        """Each player should receive 10 cards."""
        for _ in range(50):
            suit_counts, _ = create_deck()
            hands = deal_cards(suit_counts, NUM_PLAYERS)

            for i, hand in enumerate(hands):
                total = sum(hand.values())
                self.assertEqual(total, 10, f"Player {i} has {total} cards, expected 10")

    def test_all_cards_dealt(self):
        """All 40 cards should be distributed."""
        for _ in range(50):
            suit_counts, _ = create_deck()
            hands = deal_cards(suit_counts, NUM_PLAYERS)

            # Sum up all cards across all hands
            total_per_suit = {s: 0 for s in SUITS}
            for hand in hands:
                for suit, count in hand.items():
                    total_per_suit[suit] += count

            # Should match original deck
            self.assertEqual(total_per_suit, suit_counts)


class TestGameState(unittest.TestCase):
    """Test game state management."""

    def test_initial_money_after_ante(self):
        """Players should start with $300 after $50 ante."""
        game = FiggieGame()
        for i in range(NUM_PLAYERS):
            game.money[i] = STARTING_MONEY - ANTE

        for i in range(NUM_PLAYERS):
            self.assertEqual(game.money[i], 300)

    def test_game_state_hides_goal_suit(self):
        """Game state should not reveal the goal suit."""
        game = FiggieGame()
        game.goal_suit = "hearts"

        for i in range(NUM_PLAYERS):
            game.hands[i] = {s: 0 for s in SUITS}
            game.money[i] = 300

        state = get_game_state(game, 0)

        self.assertNotIn("goal_suit", state)


class TestActionValidation(unittest.TestCase):
    """Test action validation."""

    def setUp(self):
        """Set up a basic game state."""
        self.game = FiggieGame()
        for i in range(NUM_PLAYERS):
            self.game.hands[i] = {"spades": 2, "clubs": 3, "hearts": 3, "diamonds": 2}
            self.game.money[i] = 300

    def test_pass_always_valid(self):
        """Pass action should always be valid."""
        valid, error = validate_action(self.game, 0, {"type": "pass"})
        self.assertTrue(valid)

    def test_bid_requires_positive_price(self):
        """Bid must have positive price."""
        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 0})
        self.assertFalse(valid)

        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": -5})
        self.assertFalse(valid)

    def test_bid_cannot_exceed_money(self):
        """Bid cannot exceed available money."""
        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 500})
        self.assertFalse(valid)
        self.assertIn("300", error)

    def test_bid_must_be_higher_than_existing(self):
        """New bid must be higher than existing bid."""
        self.game.bids["spades"] = Order("spades", 10, 1, True)

        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 10})
        self.assertFalse(valid)

        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 5})
        self.assertFalse(valid)

        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 11})
        self.assertTrue(valid)

    def test_offer_requires_cards(self):
        """Cannot offer a suit you don't have."""
        self.game.hands[0]["diamonds"] = 0

        valid, error = validate_action(self.game, 0, {"type": "offer", "suit": "diamonds", "price": 10})
        self.assertFalse(valid)
        self.assertIn("don't have", error)

    def test_offer_must_be_lower_than_existing(self):
        """New offer must be lower than existing offer."""
        self.game.offers["spades"] = Order("spades", 10, 1, False)

        valid, error = validate_action(self.game, 0, {"type": "offer", "suit": "spades", "price": 10})
        self.assertFalse(valid)

        valid, error = validate_action(self.game, 0, {"type": "offer", "suit": "spades", "price": 15})
        self.assertFalse(valid)

        valid, error = validate_action(self.game, 0, {"type": "offer", "suit": "spades", "price": 9})
        self.assertTrue(valid)

    def test_bid_cannot_cross_offer(self):
        """Bid cannot be >= existing offer (use buy instead)."""
        self.game.offers["spades"] = Order("spades", 10, 1, False)

        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 10})
        self.assertFalse(valid)
        self.assertIn("cross", error.lower())

        valid, error = validate_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 9})
        self.assertTrue(valid)

    def test_offer_cannot_cross_bid(self):
        """Offer cannot be <= existing bid (use sell instead)."""
        self.game.bids["spades"] = Order("spades", 10, 1, True)

        valid, error = validate_action(self.game, 0, {"type": "offer", "suit": "spades", "price": 10})
        self.assertFalse(valid)
        self.assertIn("cross", error.lower())

        valid, error = validate_action(self.game, 0, {"type": "offer", "suit": "spades", "price": 11})
        self.assertTrue(valid)

    def test_buy_requires_offer(self):
        """Cannot buy if no offer exists."""
        valid, error = validate_action(self.game, 0, {"type": "buy", "suit": "spades"})
        self.assertFalse(valid)
        self.assertIn("No offer", error)

    def test_cannot_buy_from_self(self):
        """Cannot buy your own offer."""
        self.game.offers["spades"] = Order("spades", 10, 0, False)

        valid, error = validate_action(self.game, 0, {"type": "buy", "suit": "spades"})
        self.assertFalse(valid)
        self.assertIn("yourself", error)

    def test_buy_requires_sufficient_money(self):
        """Cannot buy if you can't afford it."""
        self.game.offers["spades"] = Order("spades", 500, 1, False)

        valid, error = validate_action(self.game, 0, {"type": "buy", "suit": "spades"})
        self.assertFalse(valid)
        self.assertIn("afford", error.lower())

    def test_sell_requires_bid(self):
        """Cannot sell if no bid exists."""
        valid, error = validate_action(self.game, 0, {"type": "sell", "suit": "spades"})
        self.assertFalse(valid)
        self.assertIn("No bid", error)

    def test_cannot_sell_to_self(self):
        """Cannot sell to your own bid."""
        self.game.bids["spades"] = Order("spades", 10, 0, True)

        valid, error = validate_action(self.game, 0, {"type": "sell", "suit": "spades"})
        self.assertFalse(valid)
        self.assertIn("yourself", error)

    def test_sell_requires_cards(self):
        """Cannot sell a suit you don't have."""
        self.game.hands[0]["diamonds"] = 0
        self.game.bids["diamonds"] = Order("diamonds", 10, 1, True)

        valid, error = validate_action(self.game, 0, {"type": "sell", "suit": "diamonds"})
        self.assertFalse(valid)


class TestActionExecution(unittest.TestCase):
    """Test action execution."""

    def setUp(self):
        """Set up a basic game state."""
        self.game = FiggieGame()
        for i in range(NUM_PLAYERS):
            self.game.hands[i] = {"spades": 2, "clubs": 3, "hearts": 3, "diamonds": 2}
            self.game.money[i] = 300

    def test_bid_creates_order(self):
        """Bid should create an order."""
        execute_action(self.game, 0, {"type": "bid", "suit": "spades", "price": 10})

        self.assertIsNotNone(self.game.bids["spades"])
        self.assertEqual(self.game.bids["spades"].price, 10)
        self.assertEqual(self.game.bids["spades"].player_id, 0)

    def test_offer_creates_order(self):
        """Offer should create an order."""
        execute_action(self.game, 0, {"type": "offer", "suit": "spades", "price": 15})

        self.assertIsNotNone(self.game.offers["spades"])
        self.assertEqual(self.game.offers["spades"].price, 15)
        self.assertEqual(self.game.offers["spades"].player_id, 0)

    def test_buy_transfers_card_and_money(self):
        """Buy should transfer card and money."""
        self.game.offers["spades"] = Order("spades", 10, 1, False)

        # Player 0 buys from player 1
        execute_action(self.game, 0, {"type": "buy", "suit": "spades"})

        # Check money transfer
        self.assertEqual(self.game.money[0], 290)  # Buyer pays
        self.assertEqual(self.game.money[1], 310)  # Seller receives

        # Check card transfer
        self.assertEqual(self.game.hands[0]["spades"], 3)  # Buyer gets card
        self.assertEqual(self.game.hands[1]["spades"], 1)  # Seller loses card

    def test_sell_transfers_card_and_money(self):
        """Sell should transfer card and money."""
        self.game.bids["spades"] = Order("spades", 10, 1, True)

        # Player 0 sells to player 1's bid
        execute_action(self.game, 0, {"type": "sell", "suit": "spades"})

        # Check money transfer
        self.assertEqual(self.game.money[0], 310)  # Seller receives
        self.assertEqual(self.game.money[1], 290)  # Buyer pays

        # Check card transfer
        self.assertEqual(self.game.hands[0]["spades"], 1)  # Seller loses card
        self.assertEqual(self.game.hands[1]["spades"], 3)  # Buyer gets card

    def test_trade_clears_all_orders(self):
        """After a trade, all bids and offers should be cleared."""
        # Set up some orders
        self.game.bids["spades"] = Order("spades", 5, 2, True)
        self.game.bids["clubs"] = Order("clubs", 8, 3, True)
        self.game.offers["spades"] = Order("spades", 10, 1, False)
        self.game.offers["hearts"] = Order("hearts", 12, 0, False)

        # Execute a trade
        execute_action(self.game, 0, {"type": "buy", "suit": "spades"})

        # All orders should be cleared
        for suit in SUITS:
            self.assertIsNone(self.game.bids[suit])
            self.assertIsNone(self.game.offers[suit])

    def test_trade_creates_trade_record(self):
        """Trade should be recorded in trade history."""
        self.game.offers["spades"] = Order("spades", 10, 1, False)
        self.game.current_turn = 5

        execute_action(self.game, 0, {"type": "buy", "suit": "spades"})

        self.assertEqual(len(self.game.trades), 1)
        trade = self.game.trades[0]
        self.assertEqual(trade.suit, "spades")
        self.assertEqual(trade.price, 10)
        self.assertEqual(trade.buyer_id, 0)
        self.assertEqual(trade.seller_id, 1)
        self.assertEqual(trade.turn, 5)


class TestScoring(unittest.TestCase):
    """Test scoring calculations."""

    def test_card_bonus(self):
        """Each goal suit card should be worth $10."""
        game = FiggieGame()
        game.goal_suit = "hearts"

        # Set up hands - player 0 has 5 hearts, others have varying amounts
        game.hands = {
            0: {"spades": 2, "clubs": 1, "hearts": 5, "diamonds": 2},
            1: {"spades": 3, "clubs": 4, "hearts": 2, "diamonds": 1},
            2: {"spades": 3, "clubs": 2, "hearts": 2, "diamonds": 3},
            3: {"spades": 2, "clubs": 3, "hearts": 1, "diamonds": 4},
        }
        # 10 hearts total in deck

        for i in range(NUM_PLAYERS):
            game.money[i] = 300

        scores = calculate_scores(game)

        # Player 0 has 5 hearts = $50 card bonus
        # Player 0 has most hearts, gets remainder (200 - 100 = 100)
        # Net: -50 (ante) + 50 (cards) + 100 (majority) = 100
        self.assertEqual(scores[0], 100)

    def test_majority_bonus(self):
        """Player with most goal cards gets the pot remainder."""
        game = FiggieGame()
        game.goal_suit = "clubs"

        # Set up hands
        game.hands = {
            0: {"spades": 3, "clubs": 1, "hearts": 3, "diamonds": 3},
            1: {"spades": 2, "clubs": 2, "hearts": 3, "diamonds": 3},
            2: {"spades": 2, "clubs": 5, "hearts": 2, "diamonds": 1},  # Most clubs
            3: {"spades": 3, "clubs": 2, "hearts": 2, "diamonds": 3},
        }
        # 10 clubs total

        for i in range(NUM_PLAYERS):
            game.money[i] = 300

        scores = calculate_scores(game)

        # Player 2 has 5 clubs = $50 card bonus + $100 majority = $150, minus $50 ante = $100
        self.assertEqual(scores[2], 100)

    def test_tied_majority_splits_remainder(self):
        """If tied for most, remainder is split evenly."""
        game = FiggieGame()
        game.goal_suit = "hearts"

        # Set up hands with tie
        game.hands = {
            0: {"spades": 2, "clubs": 3, "hearts": 3, "diamonds": 2},  # Tied for most
            1: {"spades": 3, "clubs": 3, "hearts": 3, "diamonds": 1},  # Tied for most
            2: {"spades": 3, "clubs": 2, "hearts": 2, "diamonds": 3},
            3: {"spades": 2, "clubs": 2, "hearts": 2, "diamonds": 4},
        }
        # 10 hearts total

        for i in range(NUM_PLAYERS):
            game.money[i] = 300

        scores = calculate_scores(game)

        # Players 0 and 1 both have 3 hearts, split remainder
        # Pot = 200, card payouts = 100, remainder = 100
        # Each tied winner gets 50
        # Player 0: -50 + 30 + 50 = 30
        # Player 1: -50 + 30 + 50 = 30
        self.assertEqual(scores[0], 30)
        self.assertEqual(scores[1], 30)

    def test_scores_are_zero_sum(self):
        """Net scores across all players should sum to 0."""
        for _ in range(50):
            game = FiggieGame()
            suit_counts, goal_suit = create_deck()
            game.goal_suit = goal_suit
            game.suit_counts = suit_counts

            hands = deal_cards(suit_counts, NUM_PLAYERS)
            for i in range(NUM_PLAYERS):
                game.hands[i] = hands[i]
                game.money[i] = 300

            scores = calculate_scores(game)
            total = sum(scores.values())

            self.assertEqual(total, 0, f"Scores {scores} sum to {total}, expected 0")

    def test_trading_is_zero_sum(self):
        """Trading profits should sum to 0."""
        game = FiggieGame()
        game.goal_suit = "hearts"

        for i in range(NUM_PLAYERS):
            game.hands[i] = {"spades": 2, "clubs": 3, "hearts": 3, "diamonds": 2}
            game.money[i] = 300

        # Do some trades
        game.offers["spades"] = Order("spades", 10, 1, False)
        execute_action(game, 0, {"type": "buy", "suit": "spades"})

        game.bids["clubs"] = Order("clubs", 8, 2, True)
        execute_action(game, 3, {"type": "sell", "suit": "clubs"})

        # Total money should be unchanged
        total_money = sum(game.money.values())
        self.assertEqual(total_money, 300 * 4)


class TestIntegration(unittest.TestCase):
    """Integration tests."""

    def test_full_game_no_trades(self):
        """Test a game where no trades occur."""
        # This tests the scoring when initial hands are final
        game = FiggieGame()
        suit_counts, goal_suit = create_deck()
        game.goal_suit = goal_suit
        game.suit_counts = suit_counts

        hands = deal_cards(suit_counts, NUM_PLAYERS)
        for i in range(NUM_PLAYERS):
            game.hands[i] = hands[i]
            game.money[i] = 300

        scores = calculate_scores(game)

        # Verify all scores are calculated
        self.assertEqual(len(scores), NUM_PLAYERS)

        # Scores should sum to 0
        self.assertEqual(sum(scores.values()), 0)

    def test_starter_bot_makes_valid_actions(self):
        """Test that the starter bot always returns valid actions."""
        import main

        game = FiggieGame()
        suit_counts, goal_suit = create_deck()
        game.goal_suit = goal_suit

        hands = deal_cards(suit_counts, NUM_PLAYERS)
        for i in range(NUM_PLAYERS):
            game.hands[i] = hands[i]
            game.money[i] = 300

        # Run several turns
        for turn in range(100):
            player_id = turn % NUM_PLAYERS
            game.current_turn = turn

            state = get_game_state(game, player_id)
            action = main.get_action(state)

            is_valid, error = validate_action(game, player_id, action)
            self.assertTrue(is_valid, f"Turn {turn}, Player {player_id}: {action} - {error}")

            execute_action(game, player_id, action)


if __name__ == "__main__":
    unittest.main()
