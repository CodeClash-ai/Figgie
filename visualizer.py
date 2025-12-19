#!/usr/bin/env python3
"""
Terminal Visualizer for Figgie

Provides a rich terminal display of Figgie game state with colors and formatting.
"""

import os
import time

# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_GRAY = "\033[100m"


# Suit display info
SUITS = {
    "spades": {"symbol": "♠", "color": Colors.WHITE},
    "clubs": {"symbol": "♣", "color": Colors.WHITE},
    "hearts": {"symbol": "♥", "color": Colors.BRIGHT_RED},
    "diamonds": {"symbol": "♦", "color": Colors.BRIGHT_RED},
}


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def hide_cursor():
    """Hide terminal cursor."""
    print("\033[?25l", end="")


def show_cursor():
    """Show terminal cursor."""
    print("\033[?25h", end="")


class FiggieVisualizer:
    """Rich terminal visualizer for Figgie games."""

    def __init__(self, delay: float = 0.3, player_names: list = None):
        """
        Initialize visualizer.

        Args:
            delay: Seconds to pause after each action
            player_names: Optional list of player names
        """
        self.delay = delay
        self.player_names = player_names

    def get_player_name(self, player_id: int, num_players: int) -> str:
        """Get display name for player."""
        if self.player_names and player_id < len(self.player_names):
            return self.player_names[player_id]
        return f"P{player_id}"

    def format_suit(self, suit: str) -> str:
        """Format suit with symbol and color."""
        info = SUITS.get(suit, {"symbol": "?", "color": Colors.WHITE})
        return f"{info['color']}{info['symbol']}{Colors.RESET}"

    def format_money(self, amount: int, show_sign: bool = False) -> str:
        """Format money with color."""
        if show_sign and amount > 0:
            return f"{Colors.BRIGHT_GREEN}+${amount}{Colors.RESET}"
        elif amount < 0:
            return f"{Colors.BRIGHT_RED}-${abs(amount)}{Colors.RESET}"
        else:
            return f"${amount}"

    def render_market_panel(self, game) -> list[str]:
        """Render the market (bids/offers) panel."""
        lines = []
        lines.append(f"{Colors.BOLD}{Colors.YELLOW}╔══════════════════════════════════════════════════╗{Colors.RESET}")
        lines.append(f"{Colors.BOLD}{Colors.YELLOW}║           M A R K E T   Q U O T E S              ║{Colors.RESET}")
        lines.append(f"{Colors.BOLD}{Colors.YELLOW}╠══════════════════════════════════════════════════╣{Colors.RESET}")

        # Header
        header = f"{Colors.YELLOW}║{Colors.RESET}  {'SUIT':^10}  │  {'BID':^10}  │  {'ASK':^10}  │ {'SPREAD':^6} {Colors.YELLOW}║{Colors.RESET}"
        lines.append(header)
        lines.append(f"{Colors.YELLOW}║{Colors.RESET}{'─' * 14}┼{'─' * 14}┼{'─' * 14}┼{'─' * 8}{Colors.YELLOW}║{Colors.RESET}")

        for suit in ["spades", "clubs", "hearts", "diamonds"]:
            suit_display = f"{self.format_suit(suit)} {suit.capitalize():8}"

            bid = game.bids.get(suit)
            offer = game.offers.get(suit)

            if bid:
                bid_str = f"{Colors.BRIGHT_GREEN}${bid.price:3} (P{bid.player_id}){Colors.RESET}"
            else:
                bid_str = f"{Colors.DIM}   ---   {Colors.RESET}"

            if offer:
                offer_str = f"{Colors.BRIGHT_RED}${offer.price:3} (P{offer.player_id}){Colors.RESET}"
            else:
                offer_str = f"{Colors.DIM}   ---   {Colors.RESET}"

            # Calculate spread
            if bid and offer:
                spread = offer.price - bid.price
                spread_str = f"${spread}"
            else:
                spread_str = "  -  "

            line = f"{Colors.YELLOW}║{Colors.RESET}  {suit_display}  │  {bid_str:^20}  │  {offer_str:^20}  │ {spread_str:^6} {Colors.YELLOW}║{Colors.RESET}"
            lines.append(line)

        lines.append(f"{Colors.BOLD}{Colors.YELLOW}╚══════════════════════════════════════════════════╝{Colors.RESET}")
        return lines

    def render_players_panel(self, game) -> list[str]:
        """Render the players info panel."""
        lines = []
        lines.append(f"{Colors.BOLD}{Colors.CYAN}╔═══════════════════════════════════════════════════════════════════╗{Colors.RESET}")
        lines.append(f"{Colors.BOLD}{Colors.CYAN}║                      P L A Y E R S                                ║{Colors.RESET}")
        lines.append(f"{Colors.BOLD}{Colors.CYAN}╠═══════════════════════════════════════════════════════════════════╣{Colors.RESET}")

        # Header
        header = f"{Colors.CYAN}║{Colors.RESET} {'PLAYER':^8} │ {'MONEY':^8} │ "
        for suit in ["spades", "clubs", "hearts", "diamonds"]:
            header += f" {self.format_suit(suit)} │"
        header += f" {'TOTAL':^5} {Colors.CYAN}║{Colors.RESET}"
        lines.append(header)
        lines.append(f"{Colors.CYAN}║{Colors.RESET}{'─' * 10}┼{'─' * 10}┼{'─' * 4}┼{'─' * 4}┼{'─' * 4}┼{'─' * 4}┼{'─' * 7}{Colors.CYAN}║{Colors.RESET}")

        for pid in range(game.num_players):
            name = self.get_player_name(pid, game.num_players)
            money = game.money[pid]
            hand = game.hands[pid]
            total_cards = sum(hand.values())

            money_str = self.format_money(money)

            line = f"{Colors.CYAN}║{Colors.RESET} {name:^8} │ {money_str:^18} │"
            for suit in ["spades", "clubs", "hearts", "diamonds"]:
                count = hand.get(suit, 0)
                line += f" {count:^2} │"
            line += f" {total_cards:^5} {Colors.CYAN}║{Colors.RESET}"
            lines.append(line)

        lines.append(f"{Colors.BOLD}{Colors.CYAN}╚═══════════════════════════════════════════════════════════════════╝{Colors.RESET}")
        return lines

    def render_action(self, player_id: int, action: dict, game) -> str:
        """Render the current action."""
        name = self.get_player_name(player_id, game.num_players)
        action_type = action.get("type", "pass")

        if action_type == "pass":
            return f"{Colors.DIM}{name} passes{Colors.RESET}"

        suit = action.get("suit", "")
        suit_fmt = self.format_suit(suit)

        if action_type == "bid":
            price = action.get("price", 0)
            return f"{Colors.BRIGHT_GREEN}{name} BIDS ${price} for {suit_fmt} {suit}{Colors.RESET}"

        elif action_type == "offer":
            price = action.get("price", 0)
            return f"{Colors.BRIGHT_RED}{name} OFFERS {suit_fmt} {suit} at ${price}{Colors.RESET}"

        elif action_type == "buy":
            offer = game.offers.get(suit)
            if offer:
                return f"{Colors.BRIGHT_YELLOW}{name} BUYS {suit_fmt} {suit} from P{offer.player_id} @ ${offer.price}{Colors.RESET}"
            return f"{Colors.BRIGHT_YELLOW}{name} BUYS {suit_fmt} {suit}{Colors.RESET}"

        elif action_type == "sell":
            bid = game.bids.get(suit)
            if bid:
                return f"{Colors.BRIGHT_YELLOW}{name} SELLS {suit_fmt} {suit} to P{bid.player_id} @ ${bid.price}{Colors.RESET}"
            return f"{Colors.BRIGHT_YELLOW}{name} SELLS {suit_fmt} {suit}{Colors.RESET}"

        return f"{name}: {action}"

    def render_trade_history(self, trades: list, limit: int = 5) -> list[str]:
        """Render recent trade history."""
        lines = []
        lines.append(f"{Colors.BOLD}{Colors.MAGENTA}┌─── Recent Trades ───┐{Colors.RESET}")

        recent = trades[-limit:] if len(trades) > limit else trades
        if not recent:
            lines.append(f"{Colors.DIM}│   No trades yet     │{Colors.RESET}")
        else:
            for trade in reversed(recent):
                suit_fmt = self.format_suit(trade.suit)
                lines.append(f"│ {suit_fmt} ${trade.price:2} P{trade.buyer_id}←P{trade.seller_id} T{trade.turn:3} │")

        lines.append(f"{Colors.BOLD}{Colors.MAGENTA}└─────────────────────┘{Colors.RESET}")
        return lines

    def render_game_state(self, game, current_player: int = None, action: dict = None,
                          show_goal: bool = False) -> None:
        """
        Render the full game state to terminal.

        Args:
            game: FiggieGame instance
            current_player: Current player's turn (optional)
            action: Action being taken (optional)
            show_goal: Whether to reveal the goal suit
        """
        clear_screen()
        hide_cursor()

        # Title
        print(f"\n{Colors.BOLD}{Colors.BRIGHT_YELLOW}  ╔═══════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BRIGHT_YELLOW}  ║     F I G G I E   T R A D I N G   F L O O R     ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BRIGHT_YELLOW}  ╚═══════════════════════════════════════════╝{Colors.RESET}")
        print()

        # Turn info
        turn_info = f"  Turn: {Colors.BRIGHT_WHITE}{game.current_turn}{Colors.RESET}"
        if current_player is not None:
            name = self.get_player_name(current_player, game.num_players)
            turn_info += f"  │  Current: {Colors.BRIGHT_CYAN}{name}{Colors.RESET}"
        if show_goal:
            turn_info += f"  │  Goal: {self.format_suit(game.goal_suit)} {game.goal_suit}"
        print(turn_info)
        print()

        # Market panel
        for line in self.render_market_panel(game):
            print(f"  {line}")
        print()

        # Players panel
        for line in self.render_players_panel(game):
            print(f"  {line}")
        print()

        # Current action
        if action:
            action_str = self.render_action(current_player, action, game)
            print(f"  {Colors.BOLD}► {action_str}{Colors.RESET}")
            print()

        # Trade history (side panel concept - just print below for simplicity)
        if game.trades:
            for line in self.render_trade_history(game.trades):
                print(f"  {line}")

        show_cursor()

        if self.delay > 0:
            time.sleep(self.delay)

    def render_final_scores(self, game, scores: dict) -> None:
        """Render final scores screen."""
        clear_screen()

        print(f"\n{Colors.BOLD}{Colors.BRIGHT_YELLOW}  ╔═══════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BRIGHT_YELLOW}  ║            G A M E   O V E R              ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BRIGHT_YELLOW}  ╚═══════════════════════════════════════════╝{Colors.RESET}")
        print()

        # Reveal goal suit
        print(f"  Goal Suit: {self.format_suit(game.goal_suit)} {Colors.BOLD}{game.goal_suit.upper()}{Colors.RESET}")
        print(f"  Total Trades: {len(game.trades)}")
        print()

        # Scores table
        print(f"  {Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════╗{Colors.RESET}")
        print(f"  {Colors.BOLD}{Colors.CYAN}║              F I N A L   S C O R E S           ║{Colors.RESET}")
        print(f"  {Colors.BOLD}{Colors.CYAN}╠════════════════════════════════════════════════╣{Colors.RESET}")

        # Sort by score
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        for rank, (pid, score) in enumerate(sorted_scores, 1):
            name = self.get_player_name(pid, game.num_players)
            goal_cards = game.hands[pid].get(game.goal_suit, 0)

            # Medal for top 3
            if rank == 1:
                medal = f"{Colors.BRIGHT_YELLOW}🥇{Colors.RESET}"
            elif rank == 2:
                medal = f"{Colors.WHITE}🥈{Colors.RESET}"
            elif rank == 3:
                medal = f"{Colors.YELLOW}🥉{Colors.RESET}"
            else:
                medal = "  "

            score_str = self.format_money(score, show_sign=True)
            goal_str = f"{self.format_suit(game.goal_suit)}×{goal_cards}"

            print(f"  {Colors.CYAN}║{Colors.RESET} {medal} {rank}. {name:^8}  │  {score_str:^20}  │  {goal_str:^10} {Colors.CYAN}║{Colors.RESET}")

        print(f"  {Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════════════╝{Colors.RESET}")
        print()


def run_visual_game(player_modules: list, visualizer: FiggieVisualizer = None,
                    player_names: list = None) -> dict:
    """
    Run a game with visualization.

    This is a modified version of run_game() that includes visualization.
    """
    from engine import (
        FiggieGame, create_deck, deal_cards, get_game_state,
        validate_action, execute_action, calculate_scores,
        VALID_PLAYER_COUNTS, STARTING_MONEY, MAX_TURNS_PER_PLAYER, get_ante
    )

    num_players = len(player_modules)
    if num_players not in VALID_PLAYER_COUNTS:
        raise ValueError(f"Figgie requires {VALID_PLAYER_COUNTS} players, got {num_players}")

    if visualizer is None:
        visualizer = FiggieVisualizer(delay=0.3, player_names=player_names)

    ante = get_ante(num_players)

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

    # Initial state
    visualizer.render_game_state(game, show_goal=False)

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
        except Exception:
            action = {"type": "pass"}

        # Validate action
        is_valid, error = validate_action(game, current_player, action)
        if not is_valid:
            action = {"type": "pass"}

        # Visualize before executing
        visualizer.render_game_state(game, current_player, action, show_goal=False)

        # Execute action
        execute_action(game, current_player, action)

        if action.get("type") == "pass":
            consecutive_passes += 1
        else:
            consecutive_passes = 0

        turn_count += 1

    # Calculate final scores
    game.final_scores = calculate_scores(game)

    # Show final state with goal revealed
    visualizer.render_game_state(game, show_goal=True)
    if visualizer.delay > 0:
        time.sleep(max(1, visualizer.delay * 3))  # Pause longer on final state

    # Show final scores
    visualizer.render_final_scores(game, game.final_scores)

    return {
        "goal_suit": goal_suit,
        "suit_counts": suit_counts,
        "final_hands": {i: game.hands[i] for i in range(num_players)},
        "final_money": {i: game.money[i] for i in range(num_players)},
        "scores": game.final_scores,
        "trades": len(game.trades),
        "turns": turn_count,
    }


if __name__ == "__main__":
    # Demo mode - run with sample bot
    import argparse

    parser = argparse.ArgumentParser(description="Figgie Visualizer Demo")
    parser.add_argument("players", nargs="*", help="Paths to player bot files")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between frames (seconds)")
    parser.add_argument("--names", nargs="+", help="Player names")
    args = parser.parse_args()

    if args.players:
        from engine import load_player
        player_modules = [load_player(p) for p in args.players]
        player_names = args.names or [os.path.basename(os.path.dirname(p)) for p in args.players]
    else:
        # Demo with built-in main.py bot
        import main
        player_modules = [main] * 4
        player_names = ["Alice", "Bob", "Carol", "Dave"]

    viz = FiggieVisualizer(delay=args.delay, player_names=player_names)

    try:
        result = run_visual_game(player_modules, viz, player_names)
        print(f"\nGame completed! Winner: P{max(result['scores'], key=result['scores'].get)}")
    except KeyboardInterrupt:
        show_cursor()
        print("\n\nGame interrupted.")
