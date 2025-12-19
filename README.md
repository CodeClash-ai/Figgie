# Figgie Game Engine for CodeClash

Figgie is a card trading game invented at [Jane Street](https://www.janestreet.com/) in 2013. It simulates open-outcry commodities trading, teaching players about market dynamics, price discovery, and information asymmetry.

## Game Rules

### Overview
- **4 or 5 players** compete to collect cards in the **goal suit**
- Each player starts with $350
- 4 players: $50 ante each, 10 cards each
- 5 players: $40 ante each, 8 cards each
- Pot is always $200
- Players trade cards through a market mechanism
- At game end, only the **goal suit** cards have value

### Deck Composition
Each game uses a 40-card deck with:
- One suit with 12 cards
- Two suits with 10 cards each
- One suit with 8 cards

### The Goal Suit
The goal suit is **secret** until the game ends:
- It's the **same color** (black or red) as the 12-card suit
- It contains either 8 or 10 cards (never 12)
- Example: If spades has 12 cards, the goal suit is clubs (8 or 10 cards)

### Scoring
At game end:
- Each goal suit card pays **$10** from the pot
- The **remainder** of the pot goes to whoever has the **most** goal suit cards
- If tied for most, the remainder is split evenly

### Trading
In this turn-based version:
- Players take turns making market actions
- After each trade, **all bids and offers are cleared**
- The game ends when players pass consecutively or max turns reached

## Bot Interface

Your bot must implement a `get_action(state)` function in `main.py`.

### Input: Game State

```python
state = {
    "position": 0,           # Your player index (0-3)
    "hand": {                # Cards you hold
        "spades": 3,
        "clubs": 2,
        "hearts": 4,
        "diamonds": 1
    },
    "money": 300,            # Your current money
    "bids": {                # Current best bids per suit
        "spades": {"price": 5, "player": 2},
        "clubs": None,       # No bid
        "hearts": {"price": 8, "player": 1},
        "diamonds": None
    },
    "offers": {              # Current best offers per suit
        "spades": {"price": 12, "player": 1},
        "clubs": {"price": 15, "player": 3},
        "hearts": None,
        "diamonds": {"price": 20, "player": 0}
    },
    "trades": [              # Completed trades
        {"suit": "spades", "price": 7, "buyer": 0, "seller": 2, "turn": 5}
    ],
    "num_players": 4,
    "turn": 42               # Current turn number
}
```

### Output: Action

Return one of these action dictionaries:

```python
# Post a bid (offer to buy at a price)
{"type": "bid", "suit": "spades", "price": 8}

# Post an offer (offer to sell at a price)
{"type": "offer", "suit": "clubs", "price": 12}

# Buy at the current best offer
{"type": "buy", "suit": "spades"}

# Sell to the current best bid
{"type": "sell", "suit": "hearts"}

# Do nothing this turn
{"type": "pass"}
```

### Action Rules

- **bid**: Must be higher than current best bid, and below any offer. Cannot exceed your money.
- **offer**: Must be lower than current best offer, and above any bid. Must have the card.
- **buy**: Takes the card at the offer price. Must have enough money.
- **sell**: Gives the card at the bid price. Must have the card.

Invalid actions are converted to `{"type": "pass"}`.

## Running Games

```bash
# Run a 4-player game
python engine.py bot1/main.py bot2/main.py bot3/main.py bot4/main.py -r 10

# Run a 5-player game
python engine.py p1/main.py p2/main.py p3/main.py p4/main.py p5/main.py -r 10

# Verbose output
python engine.py bot1/main.py bot2/main.py bot3/main.py bot4/main.py -r 5 -v

# Save game logs
python engine.py bot1/main.py bot2/main.py bot3/main.py bot4/main.py -r 10 -o logs/
```

## Strategy Tips

1. **Identify the goal suit**: The suit with the most cards in your hand is likely the 12-card suit. The goal suit is the OTHER suit of the same color.

2. **Provide liquidity**: Post bids and offers to facilitate trading and profit from the spread.

3. **Trade information**: Watch what others buy/sell. If someone is aggressively buying hearts, they may believe hearts is the goal suit.

4. **Position management**: Accumulate goal suit cards, but don't overpay. The majority bonus is only $100-120.

5. **Endgame**: In late rounds, consider dumping non-goal suits at any price.

## Repository Structure

```
Figgie/
├── engine.py     # Game engine (run games from here)
├── main.py       # Starter bot implementation
└── README.md     # This file
```

## Credits

- Figgie was invented at [Jane Street](https://www.janestreet.com/) in 2013
- Official game: [figgie.com](https://www.figgie.com/)
- This engine is part of the [CodeClash](https://github.com/CodeClash-ai/CodeClash) project
