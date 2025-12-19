#!/usr/bin/env python3
"""
Figgie Game Engine for CodeClash

Figgie is a card trading game invented at Jane Street in 2013.
It simulates open-outcry commodities trading.

Rules:
- 4 players, each starting with $350 and 10 cards
- 40 cards total: two 10-card suits, one 8-card suit, one 12-card suit
- The goal suit is the same color as the 12-card suit and contains 8 or 10 cards
- Players ante $50 each to form a $200 pot
- Players trade cards to collect goal suit cards
- At end: $10 per goal suit card, remainder of pot to player(s) with most goal suit cards
- If tied for most, the remainder is split evenly

This engine implements a turn-based version where bots take sequential actions.
"""

import argparse
import importlib.util
import json
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Card suits (using text for simplicity)
SUITS = ["spades", "clubs", "hearts", "diamonds"]
BLACK_SUITS = ["spades", "clubs"]
RED_SUITS = ["hearts", "diamonds"]

# Game constants
NUM_PLAYERS = 4
STARTING_MONEY = 350
ANTE = 50
POT = ANTE * NUM_PLAYERS  # $200
CARDS_PER_SUIT_OPTIONS = [8, 10, 10, 12]  # Must sum to 40
CARD_BONUS = 10  # $10 per goal suit card
MAX_TURNS_PER_PLAYER = 50  # Limit turns to prevent infinite games


@dataclass
class Order:
    """Represents a bid or offer in the market."""
    suit: str
    price: int
    player_id: int
    is_bid: bool  # True for bid, False for offer


@dataclass
class Trade:
    """Represents a completed trade."""
    suit: str
    price: int
    buyer_id: int
    seller_id: int
    turn: int


@dataclass
class FiggieGame:
    """Represents the state of a Figgie game."""
    num_players: int = NUM_PLAYERS
    hands: dict = field(default_factory=dict)  # player_id -> {suit: count}
    money: dict = field(default_factory=dict)  # player_id -> amount
    goal_suit: str = ""
    suit_counts: dict = field(default_factory=dict)  # suit -> total cards
    bids: dict = field(default_factory=dict)  # suit -> Order or None
    offers: dict = field(default_factory=dict)  # suit -> Order or None
    trades: list = field(default_factory=list)
    current_turn: int = 0
    game_over: bool = False
    final_scores: dict = field(default_factory=dict)

    def __post_init__(self):
        # Initialize empty bids/offers for each suit
        for suit in SUITS:
            self.bids[suit] = None
            self.offers[suit] = None


def create_deck() -> tuple[dict[str, int], str]:
    """
    Create a Figgie deck with random suit distribution.
    Returns (suit_counts, goal_suit).

    Rules:
    - Two suits have 10 cards
    - One suit has 8 cards
    - One suit has 12 cards
    - Goal suit is same color as the 12-card suit
    - Goal suit has 8 or 10 cards
    """
    # Shuffle the card counts
    counts = CARDS_PER_SUIT_OPTIONS.copy()
    random.shuffle(counts)

    # Assign counts to suits
    suit_counts = {suit: count for suit, count in zip(SUITS, counts)}

    # Find the 12-card suit
    twelve_card_suit = None
    for suit, count in suit_counts.items():
        if count == 12:
            twelve_card_suit = suit
            break

    # Goal suit is same color as 12-card suit, but not the 12-card suit itself
    # Goal suit has 8 or 10 cards
    if twelve_card_suit in BLACK_SUITS:
        same_color = BLACK_SUITS
    else:
        same_color = RED_SUITS

    # The goal suit is the other suit of the same color (which has 8 or 10 cards)
    goal_suit = [s for s in same_color if s != twelve_card_suit][0]

    return suit_counts, goal_suit


def deal_cards(suit_counts: dict[str, int], num_players: int) -> list[dict[str, int]]:
    """Deal cards evenly to all players."""
    # Create deck as list of cards
    deck = []
    for suit, count in suit_counts.items():
        deck.extend([suit] * count)

    random.shuffle(deck)

    # Deal evenly (40 cards / 4 players = 10 cards each)
    hands = [{suit: 0 for suit in SUITS} for _ in range(num_players)]
    cards_per_player = len(deck) // num_players

    for i, card in enumerate(deck[:cards_per_player * num_players]):
        player = i % num_players
        hands[player][card] += 1

    return hands


def get_game_state(game: FiggieGame, player_id: int) -> dict:
    """Get the game state from a player's perspective."""
    # Clear stale orders (orders from players who no longer have cards to sell)
    active_bids = {}
    active_offers = {}

    for suit in SUITS:
        bid = game.bids[suit]
        offer = game.offers[suit]

        if bid is not None:
            active_bids[suit] = {"price": bid.price, "player": bid.player_id}
        else:
            active_bids[suit] = None

        if offer is not None and game.hands[offer.player_id][suit] > 0:
            active_offers[suit] = {"price": offer.price, "player": offer.player_id}
        else:
            active_offers[suit] = None

    return {
        "position": player_id,
        "hand": game.hands[player_id].copy(),
        "money": game.money[player_id],
        "bids": active_bids,
        "offers": active_offers,
        "trades": [
            {
                "suit": t.suit,
                "price": t.price,
                "buyer": t.buyer_id,
                "seller": t.seller_id,
                "turn": t.turn
            }
            for t in game.trades
        ],
        "num_players": game.num_players,
        "turn": game.current_turn,
    }


def validate_action(game: FiggieGame, player_id: int, action: dict) -> tuple[bool, str]:
    """Validate a player's action. Returns (is_valid, error_message)."""
    if not isinstance(action, dict):
        return False, "Action must be a dictionary"

    action_type = action.get("type")
    if action_type not in ["bid", "offer", "buy", "sell", "pass"]:
        return False, f"Invalid action type: {action_type}"

    if action_type == "pass":
        return True, ""

    suit = action.get("suit")
    if suit not in SUITS:
        return False, f"Invalid suit: {suit}"

    if action_type == "bid":
        price = action.get("price")
        if not isinstance(price, int) or price <= 0:
            return False, "Bid price must be a positive integer"
        if price > game.money[player_id]:
            return False, f"Cannot bid {price}, only have {game.money[player_id]}"
        # Check if there's already a higher bid
        current_bid = game.bids[suit]
        if current_bid is not None and current_bid.price >= price:
            return False, f"Must bid higher than current bid of {current_bid.price}"
        # Check if we'd be crossing the market (bid >= offer)
        current_offer = game.offers[suit]
        if current_offer is not None and price >= current_offer.price:
            return False, f"Bid {price} would cross offer at {current_offer.price}. Use 'buy' instead."
        return True, ""

    if action_type == "offer":
        price = action.get("price")
        if not isinstance(price, int) or price <= 0:
            return False, "Offer price must be a positive integer"
        if game.hands[player_id][suit] <= 0:
            return False, f"Cannot offer {suit}, don't have any"
        # Check if there's already a lower offer
        current_offer = game.offers[suit]
        if current_offer is not None and current_offer.price <= price:
            return False, f"Must offer lower than current offer of {current_offer.price}"
        # Check if we'd be crossing the market (offer <= bid)
        current_bid = game.bids[suit]
        if current_bid is not None and price <= current_bid.price:
            return False, f"Offer {price} would cross bid at {current_bid.price}. Use 'sell' instead."
        return True, ""

    if action_type == "buy":
        offer = game.offers[suit]
        if offer is None:
            return False, f"No offer available for {suit}"
        if offer.player_id == player_id:
            return False, "Cannot buy from yourself"
        if game.hands[offer.player_id][suit] <= 0:
            return False, f"Seller no longer has {suit} to sell"
        if offer.price > game.money[player_id]:
            return False, f"Cannot afford {offer.price}, only have {game.money[player_id]}"
        return True, ""

    if action_type == "sell":
        bid = game.bids[suit]
        if bid is None:
            return False, f"No bid available for {suit}"
        if bid.player_id == player_id:
            return False, "Cannot sell to yourself"
        if game.hands[player_id][suit] <= 0:
            return False, f"Cannot sell {suit}, don't have any"
        return True, ""

    return False, "Unknown validation error"


def execute_action(game: FiggieGame, player_id: int, action: dict) -> bool:
    """Execute a validated action. Returns True if a trade occurred."""
    action_type = action["type"]

    if action_type == "pass":
        return False

    suit = action["suit"]

    if action_type == "bid":
        price = action["price"]
        game.bids[suit] = Order(suit=suit, price=price, player_id=player_id, is_bid=True)
        return False

    if action_type == "offer":
        price = action["price"]
        game.offers[suit] = Order(suit=suit, price=price, player_id=player_id, is_bid=False)
        return False

    if action_type == "buy":
        offer = game.offers[suit]
        # Execute trade
        buyer_id = player_id
        seller_id = offer.player_id
        price = offer.price

        game.money[buyer_id] -= price
        game.money[seller_id] += price
        game.hands[buyer_id][suit] += 1
        game.hands[seller_id][suit] -= 1

        trade = Trade(suit=suit, price=price, buyer_id=buyer_id, seller_id=seller_id, turn=game.current_turn)
        game.trades.append(trade)

        # Clear all orders after a trade (per Figgie rules)
        for s in SUITS:
            game.bids[s] = None
            game.offers[s] = None

        return True

    if action_type == "sell":
        bid = game.bids[suit]
        # Execute trade
        buyer_id = bid.player_id
        seller_id = player_id
        price = bid.price

        game.money[buyer_id] -= price
        game.money[seller_id] += price
        game.hands[buyer_id][suit] += 1
        game.hands[seller_id][suit] -= 1

        trade = Trade(suit=suit, price=price, buyer_id=buyer_id, seller_id=seller_id, turn=game.current_turn)
        game.trades.append(trade)

        # Clear all orders after a trade (per Figgie rules)
        for s in SUITS:
            game.bids[s] = None
            game.offers[s] = None

        return True

    return False


def calculate_scores(game: FiggieGame) -> dict[int, int]:
    """Calculate final scores for all players."""
    goal_suit = game.goal_suit

    # Count goal suit cards per player
    goal_cards = {pid: game.hands[pid][goal_suit] for pid in range(game.num_players)}

    # Find who has the most
    max_cards = max(goal_cards.values())
    winners = [pid for pid, count in goal_cards.items() if count == max_cards]

    # Calculate pot distribution
    # $10 per goal suit card
    card_payouts = {pid: count * CARD_BONUS for pid, count in goal_cards.items()}
    total_card_payout = sum(card_payouts.values())
    remainder = POT - total_card_payout

    # Split remainder among winners
    remainder_per_winner = remainder // len(winners) if winners else 0

    # Calculate final scores (money + pot winnings - ante)
    final_scores = {}
    for pid in range(game.num_players):
        score = game.money[pid] - STARTING_MONEY  # Net change from trading
        score += card_payouts[pid]  # Card bonus
        if pid in winners:
            score += remainder_per_winner  # Majority bonus
        final_scores[pid] = score

    return final_scores


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


def run_game(player_modules: list, verbose: bool = False) -> dict:
    """Run a single game of Figgie."""
    num_players = len(player_modules)
    if num_players != NUM_PLAYERS:
        raise ValueError(f"Figgie requires exactly {NUM_PLAYERS} players, got {num_players}")

    # Create deck and deal
    suit_counts, goal_suit = create_deck()
    hands = deal_cards(suit_counts, num_players)

    # Initialize game state
    game = FiggieGame(num_players=num_players)
    game.suit_counts = suit_counts
    game.goal_suit = goal_suit

    for i in range(num_players):
        game.hands[i] = hands[i]
        game.money[i] = STARTING_MONEY - ANTE  # After ante

    if verbose:
        print(f"Deck: {suit_counts}")
        print(f"Goal suit: {goal_suit}")
        for i in range(num_players):
            print(f"Player {i} hand: {game.hands[i]}")

    # Run trading rounds
    consecutive_passes = 0
    turn_count = 0
    max_total_turns = MAX_TURNS_PER_PLAYER * num_players

    while turn_count < max_total_turns and consecutive_passes < num_players * 2:
        current_player = turn_count % num_players
        game.current_turn = turn_count

        # Get game state for current player
        state = get_game_state(game, current_player)

        # Get action from player
        try:
            action = player_modules[current_player].get_action(state)
        except Exception as e:
            if verbose:
                print(f"Player {current_player} raised exception: {e}")
            action = {"type": "pass"}

        # Validate action
        is_valid, error = validate_action(game, current_player, action)
        if not is_valid:
            if verbose:
                print(f"Player {current_player} invalid action: {action} - {error}")
            action = {"type": "pass"}

        # Execute action
        trade_occurred = execute_action(game, current_player, action)

        if action.get("type") == "pass":
            consecutive_passes += 1
        else:
            consecutive_passes = 0

        if verbose and action.get("type") != "pass":
            print(f"Turn {turn_count}: Player {current_player} -> {action}")

        turn_count += 1

    # Calculate final scores
    game.final_scores = calculate_scores(game)

    if verbose:
        print(f"\nFinal hands:")
        for i in range(num_players):
            print(f"  Player {i}: {game.hands[i]} (money: {game.money[i]})")
        print(f"Goal suit was: {goal_suit}")
        print(f"Final scores: {game.final_scores}")

    return {
        "goal_suit": goal_suit,
        "suit_counts": suit_counts,
        "final_hands": {i: game.hands[i] for i in range(num_players)},
        "final_money": {i: game.money[i] for i in range(num_players)},
        "scores": game.final_scores,
        "trades": len(game.trades),
        "turns": turn_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Figgie Game Engine")
    parser.add_argument("players", nargs="+", help="Paths to player bot files")
    parser.add_argument("-r", "--rounds", type=int, default=10, help="Number of rounds to play")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-o", "--output", type=str, help="Output directory for game logs")
    args = parser.parse_args()

    if len(args.players) != NUM_PLAYERS:
        print(f"Error: Figgie requires exactly {NUM_PLAYERS} players, got {len(args.players)}")
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

    # Track wins by total score across rounds
    total_scores = defaultdict(int)
    round_wins = defaultdict(int)

    for round_num in range(args.rounds):
        if args.verbose:
            print(f"\n{'='*50}")
            print(f"Round {round_num + 1}")
            print(f"{'='*50}")

        result = run_game(player_modules, verbose=args.verbose)

        # Track scores
        for pid, score in result["scores"].items():
            total_scores[pid] += score

        # Determine round winner (highest score)
        max_score = max(result["scores"].values())
        round_winners = [pid for pid, score in result["scores"].items() if score == max_score]

        if len(round_winners) == 1:
            round_wins[round_winners[0]] += 1
        else:
            round_wins["draw"] += 1

        # Save game log if output directory specified
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            with open(output_dir / f"round_{round_num}.json", "w") as f:
                json.dump(result, f, indent=2)

    # Print final results in the expected format
    print()
    print("FINAL_RESULTS")
    for i, path in enumerate(args.players):
        name = os.path.basename(os.path.dirname(path))
        wins = round_wins.get(i, 0)
        print(f"Bot_{i+1}_main: {wins} rounds won ({name})")
    print(f"Draws: {round_wins.get('draw', 0)}")

    if args.verbose:
        print(f"\nTotal scores across all rounds:")
        for i in range(len(args.players)):
            print(f"  Player {i}: {total_scores[i]}")


if __name__ == "__main__":
    main()
