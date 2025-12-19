#!/usr/bin/env python3
"""
Figgie Game Engine for CodeClash

Figgie is a card trading game invented at Jane Street in 2013.
It simulates open-outcry commodities trading.

Rules:
- 4 or 5 players, each starting with $350
- 4 players: 10 cards each, $50 ante
- 5 players: 8 cards each, $40 ante
- 40 cards total: two 10-card suits, one 8-card suit, one 12-card suit
- The goal suit is the same color as the 12-card suit and contains 8 or 10 cards
- Players ante to form a $200 pot
- Players trade cards to collect goal suit cards
- At end: $10 per goal suit card, remainder of pot to player(s) with most goal suit cards
- If tied for most, the remainder is split evenly

This engine implements a SIMULTANEOUS TICK model:
- Each tick, ALL players are polled for their action
- Actions are collected and executed in RANDOM order
- This simulates the race condition of real-time open-outcry trading
- Being randomly selected first = like being faster in real trading
"""

import argparse
import importlib.util
import json
import logging
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("figgie")


# Card suits
SUITS = ["spades", "clubs", "hearts", "diamonds"]
BLACK_SUITS = ["spades", "clubs"]
RED_SUITS = ["hearts", "diamonds"]

# Game constants
VALID_PLAYER_COUNTS = [4, 5]
STARTING_MONEY = 350
POT = 200  # Always $200 regardless of player count
CARDS_PER_SUIT_OPTIONS = [8, 10, 10, 12]  # Must sum to 40
CARD_BONUS = 10  # $10 per goal suit card
MAX_TICKS = 200  # Maximum ticks per game
CONSECUTIVE_PASS_LIMIT = 3  # End if all players pass this many times in a row


def get_ante(num_players: int) -> int:
    """Get ante amount based on player count."""
    if num_players == 4:
        return 50
    elif num_players == 5:
        return 40
    else:
        raise ValueError(f"Invalid player count: {num_players}. Must be 4 or 5.")


@dataclass
class Quote:
    """A bid or ask quote in the order book."""

    price: int = 0
    player_id: int = -1

    def is_valid(self) -> bool:
        return self.price > 0 and self.player_id >= 0

    def reset(self):
        self.price = 0
        self.player_id = -1


@dataclass
class OrderBook:
    """Order book for a single suit with best bid and best ask."""

    suit: str
    bid: Quote = field(default_factory=Quote)  # Best bid (highest buy price)
    ask: Quote = field(default_factory=Quote)  # Best ask (lowest sell price)
    last_trade_price: int | None = None

    def reset_quotes(self):
        """Clear all quotes (called after each trade per Figgie rules)."""
        self.bid.reset()
        self.ask.reset()

    def to_dict(self) -> dict:
        return {
            "bid": {"price": self.bid.price, "player": self.bid.player_id}
            if self.bid.is_valid()
            else None,
            "ask": {"price": self.ask.price, "player": self.ask.player_id}
            if self.ask.is_valid()
            else None,
            "last_trade": self.last_trade_price,
        }


@dataclass
class Trade:
    """Represents a completed trade."""

    suit: str
    price: int
    buyer_id: int
    seller_id: int
    tick: int


@dataclass
class FiggieGame:
    """Represents the state of a Figgie game."""

    num_players: int = 4
    hands: dict = field(default_factory=dict)  # player_id -> {suit: count}
    money: dict = field(default_factory=dict)  # player_id -> amount
    goal_suit: str = ""
    suit_counts: dict = field(default_factory=dict)  # suit -> total cards in deck
    books: dict = field(default_factory=dict)  # suit -> OrderBook
    trades: list = field(default_factory=list)
    current_tick: int = 0
    game_over: bool = False
    final_scores: dict = field(default_factory=dict)

    def __post_init__(self):
        for suit in SUITS:
            self.books[suit] = OrderBook(suit=suit)


def create_deck() -> tuple[dict[str, int], str]:
    """
    Create a Figgie deck with random suit distribution.
    Returns (suit_counts, goal_suit).
    """
    counts = CARDS_PER_SUIT_OPTIONS.copy()
    random.shuffle(counts)
    suit_counts = {suit: count for suit, count in zip(SUITS, counts)}

    # Find the 12-card suit
    twelve_card_suit = [s for s, c in suit_counts.items() if c == 12][0]

    # Goal suit is same color as 12-card suit, but not the 12-card suit itself
    if twelve_card_suit in BLACK_SUITS:
        same_color = BLACK_SUITS
    else:
        same_color = RED_SUITS

    goal_suit = [s for s in same_color if s != twelve_card_suit][0]
    return suit_counts, goal_suit


def deal_cards(suit_counts: dict[str, int], num_players: int) -> list[dict[str, int]]:
    """Deal cards evenly to all players."""
    deck = []
    for suit, count in suit_counts.items():
        deck.extend([suit] * count)

    random.shuffle(deck)

    hands = [{suit: 0 for suit in SUITS} for _ in range(num_players)]
    cards_per_player = len(deck) // num_players

    for i, card in enumerate(deck[: cards_per_player * num_players]):
        player = i % num_players
        hands[player][card] += 1

    return hands


def get_game_state(game: FiggieGame, player_id: int) -> dict:
    """Get the game state from a player's perspective."""
    books_state = {}
    for suit in SUITS:
        book = game.books[suit]
        books_state[suit] = book.to_dict()

    return {
        "position": player_id,
        "hand": game.hands[player_id].copy(),
        "money": game.money[player_id],
        "books": books_state,
        "trades": [
            {
                "suit": t.suit,
                "price": t.price,
                "buyer": t.buyer_id,
                "seller": t.seller_id,
                "tick": t.tick,
            }
            for t in game.trades
        ],
        "num_players": game.num_players,
        "tick": game.current_tick,
    }


def validate_action(game: FiggieGame, player_id: int, action: dict) -> tuple[bool, str]:
    """Validate a player's action. Returns (is_valid, error_message)."""
    if not isinstance(action, dict):
        return False, "Action must be a dictionary"

    action_type = action.get("type")
    valid_types = ["bid", "ask", "buy", "sell", "pass"]
    if action_type not in valid_types:
        return (
            False,
            f"Invalid action type: {action_type}. Must be one of {valid_types}",
        )

    if action_type == "pass":
        return True, ""

    suit = action.get("suit")
    if suit not in SUITS:
        return False, f"Invalid suit: {suit}"

    book = game.books[suit]

    if action_type == "bid":
        price = action.get("price")
        if not isinstance(price, int) or price <= 0:
            return False, "Bid price must be a positive integer"
        if price > game.money[player_id]:
            return False, f"Cannot bid {price}, only have {game.money[player_id]}"
        # Must be higher than current best bid
        if book.bid.is_valid() and price <= book.bid.price:
            return False, f"Must bid higher than current best bid of {book.bid.price}"
        # Cannot cross the market (bid >= ask)
        if book.ask.is_valid() and price >= book.ask.price:
            return (
                False,
                f"Bid {price} would cross ask at {book.ask.price}. Use 'buy' instead.",
            )
        return True, ""

    if action_type == "ask":
        price = action.get("price")
        if not isinstance(price, int) or price <= 0:
            return False, "Ask price must be a positive integer"
        if game.hands[player_id][suit] <= 0:
            return False, f"Cannot ask {suit}, don't have any"
        # Must be lower than current best ask
        if book.ask.is_valid() and price >= book.ask.price:
            return False, f"Must ask lower than current best ask of {book.ask.price}"
        # Cannot cross the market (ask <= bid)
        if book.bid.is_valid() and price <= book.bid.price:
            return (
                False,
                f"Ask {price} would cross bid at {book.bid.price}. Use 'sell' instead.",
            )
        return True, ""

    if action_type == "buy":
        if not book.ask.is_valid():
            return False, f"No ask available for {suit}"
        if book.ask.player_id == player_id:
            return False, "Cannot buy from yourself"
        if book.ask.price > game.money[player_id]:
            return (
                False,
                f"Cannot afford {book.ask.price}, only have {game.money[player_id]}",
            )
        return True, ""

    if action_type == "sell":
        if not book.bid.is_valid():
            return False, f"No bid available for {suit}"
        if book.bid.player_id == player_id:
            return False, "Cannot sell to yourself"
        if game.hands[player_id][suit] <= 0:
            return False, f"Cannot sell {suit}, don't have any"
        return True, ""

    return False, "Unknown validation error"


def execute_action(game: FiggieGame, player_id: int, action: dict) -> Trade | None:
    """Execute a validated action. Returns Trade if one occurred, else None."""
    action_type = action["type"]

    if action_type == "pass":
        return None

    suit = action["suit"]
    book = game.books[suit]

    if action_type == "bid":
        price = action["price"]
        book.bid = Quote(price=price, player_id=player_id)
        return None

    if action_type == "ask":
        price = action["price"]
        book.ask = Quote(price=price, player_id=player_id)
        return None

    if action_type == "buy":
        # Execute trade at ask price
        buyer_id = player_id
        seller_id = book.ask.player_id
        price = book.ask.price

        game.money[buyer_id] -= price
        game.money[seller_id] += price
        game.hands[buyer_id][suit] += 1
        game.hands[seller_id][suit] -= 1

        trade = Trade(
            suit=suit,
            price=price,
            buyer_id=buyer_id,
            seller_id=seller_id,
            tick=game.current_tick,
        )
        game.trades.append(trade)
        book.last_trade_price = price

        # Clear ALL order books after a trade (per Figgie rules)
        for s in SUITS:
            game.books[s].reset_quotes()

        return trade

    if action_type == "sell":
        # Execute trade at bid price
        buyer_id = book.bid.player_id
        seller_id = player_id
        price = book.bid.price

        game.money[buyer_id] -= price
        game.money[seller_id] += price
        game.hands[buyer_id][suit] += 1
        game.hands[seller_id][suit] -= 1

        trade = Trade(
            suit=suit,
            price=price,
            buyer_id=buyer_id,
            seller_id=seller_id,
            tick=game.current_tick,
        )
        game.trades.append(trade)
        book.last_trade_price = price

        # Clear ALL order books after a trade (per Figgie rules)
        for s in SUITS:
            game.books[s].reset_quotes()

        return trade

    return None


def calculate_scores(game: FiggieGame) -> dict[int, int]:
    """Calculate final scores for all players."""
    goal_suit = game.goal_suit

    # Count goal suit cards per player
    goal_cards = {pid: game.hands[pid][goal_suit] for pid in range(game.num_players)}

    # Find who has the most
    max_cards = max(goal_cards.values())
    winners = [pid for pid, count in goal_cards.items() if count == max_cards]

    # Calculate pot distribution: $10 per goal suit card
    card_payouts = {pid: count * CARD_BONUS for pid, count in goal_cards.items()}
    total_card_payout = sum(card_payouts.values())
    remainder = POT - total_card_payout

    # Split remainder among winners evenly (NO +1 bug like 0xDub!)
    remainder_per_winner = remainder // len(winners) if winners else 0
    leftover = remainder % len(winners) if winners else 0

    # Calculate final scores (net change from starting position)
    final_scores = {}
    for pid in range(game.num_players):
        score = game.money[pid] - STARTING_MONEY  # Net from trading
        score += card_payouts[pid]  # Card bonus
        if pid in winners:
            score += remainder_per_winner
            if leftover > 0:
                score += 1
                leftover -= 1
        final_scores[pid] = score

    return final_scores


@dataclass
class GameLog:
    """Captures detailed log of a game for replay/analysis."""

    timestamp: str = ""
    num_players: int = 4
    suit_counts: dict = field(default_factory=dict)
    goal_suit: str = ""
    initial_hands: dict = field(default_factory=dict)
    events: list = field(default_factory=list)
    final_hands: dict = field(default_factory=dict)
    final_money: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)

    def log_setup(self, game: FiggieGame):
        self.timestamp = datetime.now().isoformat()
        self.num_players = game.num_players
        self.suit_counts = game.suit_counts.copy()
        self.goal_suit = game.goal_suit
        self.initial_hands = {pid: hand.copy() for pid, hand in game.hands.items()}
        logger.info(
            f"Game started: {game.num_players} players, simultaneous tick model"
        )
        logger.info(f"Deck distribution: {game.suit_counts}")

    def log_tick(self, tick: int, actions: list[tuple[int, dict, bool, str]]):
        """Log all actions from a tick."""
        event = {"type": "tick", "tick": tick, "actions": []}
        for player_id, action, valid, error in actions:
            action_record = {"player": player_id, "action": action, "valid": valid}
            if not valid:
                action_record["error"] = error
            event["actions"].append(action_record)
        self.events.append(event)

    def log_trade(self, trade: Trade):
        event = {
            "type": "trade",
            "tick": trade.tick,
            "suit": trade.suit,
            "price": trade.price,
            "buyer": trade.buyer_id,
            "seller": trade.seller_id,
        }
        self.events.append(event)
        logger.info(
            f"TRADE: P{trade.buyer_id} buys {trade.suit} from P{trade.seller_id} @ ${trade.price}"
        )

    def log_end(self, game: FiggieGame):
        self.final_hands = {pid: hand.copy() for pid, hand in game.hands.items()}
        self.final_money = game.money.copy()
        self.scores = game.final_scores.copy()
        logger.info(
            f"Game ended after {game.current_tick} ticks, {len(game.trades)} trades"
        )
        logger.info(f"Goal suit revealed: {game.goal_suit}")
        for pid in range(game.num_players):
            goal_cards = game.hands[pid][game.goal_suit]
            logger.info(
                f"P{pid}: {goal_cards} {game.goal_suit}, score={game.final_scores[pid]:+d}"
            )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "num_players": self.num_players,
            "suit_counts": self.suit_counts,
            "goal_suit": self.goal_suit,
            "initial_hands": self.initial_hands,
            "events": self.events,
            "final_hands": self.final_hands,
            "final_money": self.final_money,
            "scores": self.scores,
        }


def load_player(player_path: str):
    """Load a player module from file path."""
    path = Path(player_path)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {player_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def run_game(
    player_modules: list, verbose: bool = False, enable_logging: bool = True
) -> tuple[dict, GameLog | None]:
    """
    Run a single game of Figgie with SIMULTANEOUS TICK model.

    Each tick:
    1. All players are polled for their action
    2. Actions are shuffled into random order
    3. Actions are executed in that order (simulates racing)

    Returns tuple of (result_dict, game_log or None)
    """
    num_players = len(player_modules)
    if num_players not in VALID_PLAYER_COUNTS:
        raise ValueError(
            f"Figgie requires {VALID_PLAYER_COUNTS} players, got {num_players}"
        )

    ante = get_ante(num_players)
    game_log = GameLog() if enable_logging else None

    # Create deck and deal
    suit_counts, goal_suit = create_deck()
    hands = deal_cards(suit_counts, num_players)

    # Initialize game state
    game = FiggieGame(num_players=num_players)
    game.suit_counts = suit_counts
    game.goal_suit = goal_suit

    for i in range(num_players):
        game.hands[i] = hands[i]
        game.money[i] = STARTING_MONEY - ante

    if game_log:
        game_log.log_setup(game)

    if verbose:
        print(f"Deck: {suit_counts}")
        print(f"Goal suit: {goal_suit}")
        for i in range(num_players):
            print(f"Player {i} hand: {game.hands[i]}")

    # Run game with simultaneous tick model
    consecutive_all_pass = 0

    for tick in range(MAX_TICKS):
        game.current_tick = tick

        # Phase 1: Collect actions from ALL players
        player_actions = []
        for player_id in range(num_players):
            state = get_game_state(game, player_id)
            try:
                action = player_modules[player_id].get_action(state)
            except Exception as e:
                if verbose:
                    print(f"Player {player_id} raised exception: {e}")
                logger.warning(f"P{player_id} exception: {e}")
                action = {"type": "pass"}

            player_actions.append((player_id, action))

        # Phase 2: Shuffle action order (simulates racing)
        random.shuffle(player_actions)

        # Phase 3: Execute actions in shuffled order
        tick_actions = []
        all_passed = True

        for player_id, action in player_actions:
            # Re-validate (state may have changed due to earlier actions this tick)
            is_valid, error = validate_action(game, player_id, action)

            if not is_valid:
                if verbose and action.get("type") != "pass":
                    print(f"Tick {tick}: P{player_id} invalid: {action} - {error}")
                action = {"type": "pass"}

            tick_actions.append((player_id, action, is_valid, error))

            if action.get("type") != "pass":
                all_passed = False

            # Execute if valid
            if is_valid:
                trade = execute_action(game, player_id, action)
                if trade:
                    if game_log:
                        game_log.log_trade(trade)
                    if verbose:
                        print(
                            f"Tick {tick}: P{trade.buyer_id} buys {trade.suit} from P{trade.seller_id} @ ${trade.price}"
                        )

        if game_log:
            game_log.log_tick(tick, tick_actions)

        # Check for game end (all players passing repeatedly)
        if all_passed:
            consecutive_all_pass += 1
            if consecutive_all_pass >= CONSECUTIVE_PASS_LIMIT:
                if verbose:
                    print(
                        f"Game ended: all players passed {CONSECUTIVE_PASS_LIMIT} times"
                    )
                break
        else:
            consecutive_all_pass = 0

    # Calculate final scores
    game.final_scores = calculate_scores(game)

    if game_log:
        game_log.log_end(game)

    if verbose:
        print("\nFinal hands:")
        for i in range(num_players):
            print(f"  Player {i}: {game.hands[i]} (money: {game.money[i]})")
        print(f"Goal suit was: {goal_suit}")
        print(f"Final scores: {game.final_scores}")

    result = {
        "goal_suit": goal_suit,
        "suit_counts": suit_counts,
        "final_hands": {i: game.hands[i] for i in range(num_players)},
        "final_money": {i: game.money[i] for i in range(num_players)},
        "scores": game.final_scores,
        "trades": len(game.trades),
        "ticks": game.current_tick + 1,
    }

    return result, game_log


def main():
    parser = argparse.ArgumentParser(
        description="Figgie Game Engine (Simultaneous Tick Model)"
    )
    parser.add_argument("players", nargs="+", help="Paths to player bot files")
    parser.add_argument(
        "-r", "--rounds", type=int, default=10, help="Number of rounds to play"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument(
        "-o", "--output", type=str, help="Output directory for game logs"
    )
    args = parser.parse_args()

    if len(args.players) not in VALID_PLAYER_COUNTS:
        print(
            f"Error: Figgie requires {VALID_PLAYER_COUNTS} players, got {len(args.players)}"
        )
        sys.exit(1)

    # Load player modules
    player_modules = []
    for path in args.players:
        try:
            module = load_player(path)
            if not hasattr(module, "get_action"):
                print(f"Error: {path} does not have a get_action function")
                sys.exit(1)
            player_modules.append(module)
        except Exception as e:
            print(f"Error loading {path}: {e}")
            sys.exit(1)

    # Track wins
    total_scores = defaultdict(int)
    round_wins = defaultdict(int)

    # Create output directory if specified
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

    for round_num in range(args.rounds):
        if args.verbose:
            print(f"\n{'=' * 50}")
            print(f"Round {round_num + 1}")
            print(f"{'=' * 50}")

        enable_logging = args.output is not None
        result, game_log = run_game(
            player_modules, verbose=args.verbose, enable_logging=enable_logging
        )

        # Track scores
        for pid, score in result["scores"].items():
            total_scores[pid] += score

        # Determine round winner
        max_score = max(result["scores"].values())
        round_winners = [
            pid for pid, score in result["scores"].items() if score == max_score
        ]

        if len(round_winners) == 1:
            round_wins[round_winners[0]] += 1
        else:
            round_wins["draw"] += 1

        # Save game log if output specified
        if args.output and game_log:
            log_path = output_dir / f"round_{round_num}.json"
            with open(log_path, "w") as f:
                json.dump(game_log.to_dict(), f, indent=2)

    # Print final results
    print()
    print("FINAL_RESULTS")
    for i, path in enumerate(args.players):
        name = os.path.basename(os.path.dirname(path))
        wins = round_wins.get(i, 0)
        print(f"Bot_{i + 1}_main: {wins} rounds won ({name})")
    print(f"Draws: {round_wins.get('draw', 0)}")

    if args.verbose:
        print("\nTotal scores across all rounds:")
        for i in range(len(args.players)):
            print(f"  Player {i}: {total_scores[i]}")


if __name__ == "__main__":
    main()
