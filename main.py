#!/usr/bin/env python3
"""
Figgie Starter Bot for CodeClash

This bot implements a strategic approach to Figgie:
1. Estimates the goal suit based on hand distribution and market activity
2. Provides liquidity by posting competitive bids and offers
3. Accumulates cards in the likely goal suit
4. Avoids overpaying for cards
"""

import random

# Suits and their colors
SUITS = ["spades", "clubs", "hearts", "diamonds"]
BLACK_SUITS = ["spades", "clubs"]
RED_SUITS = ["hearts", "diamonds"]


def get_color(suit: str) -> str:
    """Get the color of a suit."""
    return "black" if suit in BLACK_SUITS else "red"


def same_color_suit(suit: str) -> str:
    """Get the other suit of the same color."""
    if suit in BLACK_SUITS:
        return [s for s in BLACK_SUITS if s != suit][0]
    else:
        return [s for s in RED_SUITS if s != suit][0]


def estimate_goal_suit(state: dict) -> tuple[str, float]:
    """
    Estimate which suit is likely the goal suit.

    Strategy:
    - The goal suit is the same color as the 12-card suit
    - The goal suit has 8 or 10 cards (not 12)
    - Look at our hand and trading activity to estimate suit distributions
    - Suits with higher counts in our hand are more likely to be common suits

    Returns (estimated_goal_suit, confidence)
    """
    hand = state["hand"]
    trades = state["trades"]

    # Count cards we've seen (our hand + trades)
    seen_counts = {suit: count for suit, count in hand.items()}

    for trade in trades:
        # Just count that we've seen these suits being traded
        suit = trade["suit"]
        seen_counts[suit] = seen_counts.get(suit, 0)

    # The suit with the most cards in our hand is likely the 12-card suit
    # because we're more likely to be dealt cards from larger suits
    hand_counts = [(count, suit) for suit, count in hand.items()]
    hand_counts.sort(reverse=True)

    if hand_counts:
        likely_12_suit = hand_counts[0][1]
        # Goal suit is the OTHER suit of the same color
        estimated_goal = same_color_suit(likely_12_suit)

        # Calculate confidence based on how skewed our hand is
        max_count = hand_counts[0][0]
        second_count = hand_counts[1][0] if len(hand_counts) > 1 else 0
        confidence = min(0.8, 0.3 + (max_count - second_count) * 0.1)

        return estimated_goal, confidence

    return random.choice(SUITS), 0.25


def get_card_value(suit: str, estimated_goal: str, confidence: float) -> int:
    """Estimate the value of a card in a given suit."""
    if suit == estimated_goal:
        # Goal suit cards are worth at least $10, and potentially more for majority bonus
        # With 4 players, majority bonus is $100-120, split among ~3-4 goal cards
        base_value = 10
        majority_bonus = 25 * confidence  # Expect to get some of the majority bonus
        return int(base_value + majority_bonus)
    else:
        # Non-goal suits have no value at end of game
        # But might be worth something for trading
        return max(1, int(5 * (1 - confidence)))


def should_buy(state: dict, suit: str, offer_price: int, estimated_goal: str, confidence: float) -> bool:
    """Decide if we should buy a card at the given offer price."""
    value = get_card_value(suit, estimated_goal, confidence)

    # Only buy if price is below our estimated value
    # Be more willing to buy goal suit cards
    if suit == estimated_goal:
        return offer_price < value * 1.2  # Willing to pay a bit more for goal suit
    else:
        return offer_price < value * 0.5  # Be conservative with non-goal suits


def should_sell(state: dict, suit: str, bid_price: int, estimated_goal: str, confidence: float) -> bool:
    """Decide if we should sell a card at the given bid price."""
    value = get_card_value(suit, estimated_goal, confidence)
    hand = state["hand"]

    # Don't sell goal suit cards unless we have many or price is very high
    if suit == estimated_goal:
        # Only sell if we have multiple and price is good
        if hand[suit] > 3 and bid_price >= value * 0.8:
            return True
        return bid_price >= value * 1.5  # Need a premium to sell goal cards

    # Sell non-goal suits more readily
    return bid_price >= value * 0.8


def get_action(state: dict) -> dict:
    """
    Main bot decision function.

    state contains:
    - position: our player index (0-3)
    - hand: dict of suit -> count of cards we hold
    - money: our current money
    - bids: dict of suit -> {price, player} or None
    - offers: dict of suit -> {price, player} or None
    - trades: list of completed trades
    - num_players: number of players (4)
    - turn: current turn number

    Returns an action dict:
    - {"type": "pass"}
    - {"type": "bid", "suit": "spades", "price": 5}
    - {"type": "offer", "suit": "spades", "price": 10}
    - {"type": "buy", "suit": "spades"}
    - {"type": "sell", "suit": "spades"}
    """
    hand = state["hand"]
    money = state["money"]
    bids = state["bids"]
    offers = state["offers"]
    position = state["position"]

    # Estimate the goal suit
    estimated_goal, confidence = estimate_goal_suit(state)

    # Priority 1: Buy underpriced goal suit cards
    for suit in SUITS:
        offer = offers.get(suit)
        if offer and offer["player"] != position:
            offer_price = offer["price"]
            if suit == estimated_goal and offer_price <= money:
                if should_buy(state, suit, offer_price, estimated_goal, confidence):
                    return {"type": "buy", "suit": suit}

    # Priority 2: Sell overpriced non-goal suit cards
    for suit in SUITS:
        bid = bids.get(suit)
        if bid and bid["player"] != position and hand.get(suit, 0) > 0:
            bid_price = bid["price"]
            if should_sell(state, suit, bid_price, estimated_goal, confidence):
                return {"type": "sell", "suit": suit}

    # Priority 3: Post offers for non-goal suits we have
    for suit in SUITS:
        if suit != estimated_goal and hand.get(suit, 0) > 0:
            current_offer = offers.get(suit)
            our_value = get_card_value(suit, estimated_goal, confidence)

            if current_offer is None:
                # Post an offer
                offer_price = max(our_value + 2, 5)
                return {"type": "offer", "suit": suit, "price": offer_price}
            elif current_offer["player"] != position:
                # Undercut existing offer if we can still profit
                new_price = current_offer["price"] - 1
                current_bid = bids.get(suit)
                min_price = (current_bid["price"] + 1) if current_bid else 1
                if new_price >= min_price and new_price >= our_value:
                    return {"type": "offer", "suit": suit, "price": new_price}

    # Priority 4: Post bids for goal suit
    if money > 50:  # Keep some reserve
        current_bid = bids.get(estimated_goal)
        our_value = get_card_value(estimated_goal, estimated_goal, confidence)

        if current_bid is None:
            # Post a bid
            bid_price = min(our_value - 5, money // 4)
            if bid_price > 0:
                return {"type": "bid", "suit": estimated_goal, "price": bid_price}
        elif current_bid["player"] != position:
            # Outbid if we can
            new_price = current_bid["price"] + 1
            current_offer = offers.get(estimated_goal)
            max_price = (current_offer["price"] - 1) if current_offer else money

            if new_price <= max_price and new_price <= our_value and new_price <= money:
                return {"type": "bid", "suit": estimated_goal, "price": new_price}

    # Priority 5: Occasionally bid on other suits for liquidity
    if random.random() < 0.1 and money > 30:
        for suit in SUITS:
            if bids.get(suit) is None and suit != estimated_goal:
                bid_price = random.randint(1, 5)
                return {"type": "bid", "suit": suit, "price": bid_price}

    return {"type": "pass"}
