import random
import itertools
from typing import List, Tuple

def generate_random_round_robin(teams: List[str]) -> List[Tuple[str, str]]:
    """
    Generate a random round-robin tournament schedule.

    Args:
        teams: List of team names

    Returns:
        List of matchups as tuples of (team1, team2)
    """
    n = len(teams)

    if n < 2:
        print("Need at least 2 teams for a tournament!")
        return []

    # Generate all possible matchups
    all_matchups = list(itertools.combinations(teams, 2))

    # Shuffle the matchups randomly
    random.shuffle(all_matchups)

    return all_matchups

def print_tournament_schedule(teams: List[str], matchups: List[Tuple[str, str]]):
    """Print the tournament schedule in a readable format."""
    print(f"\n🏆 ROUND ROBIN TOURNAMENT SCHEDULE")
    print(f"Teams: {', '.join(teams)}")
    print(f"Total teams: {len(teams)}")
    print(f"Total games: {len(matchups)}")
    print("=" * 50)

    for i, (team1, team2) in enumerate(matchups, 1):
        print(f"Game {i:2d}: {team1} vs {team2}")

    print(f"\n📊 TOURNAMENT STATISTICS:")
    print(f"Each team plays {len(teams) - 1} games")
    print(f"Total matchups: {len(matchups)}")

def main():
    """Main function to run the tournament generator."""
    print("Random Round Robin Tournament Generator")
    print("=" * 40)

    # Predefined teams
    teams = ["Salt", "Sornico", "Sottocastello", "Sottomonte", "Villa"]

    # Generate tournament
    matchups = generate_random_round_robin(teams)

    # Print schedule
    print_tournament_schedule(teams, matchups)

if __name__ == "__main__":
    # Set random seed for reproducible results (optional)
    # random.seed(42)

    main()