#!/usr/bin/env python3
"""
Tennis Predictor - Usage Examples

This file shows common ways to use the tennis_stats_predictor module.
"""

from tennis_stats_predictor import (
    predict_player_stats,
    predict_matchup,
    get_live_matches,
    aggregate_stats,
    load_player_cache
)

# ==========================================================
# EXAMPLE 1: Predict a Single Player's Stats
# ==========================================================
def example_player_stats():
    """Get stats for a single player"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Single Player Stats")
    print("="*80)
    
    stats = predict_player_stats("Sinner", surface="Hard")
    
    if stats:
        print(f"\nPlayer: {stats['player']}")
        print(f"Matches analyzed: {stats['matches_analyzed']}")
        print(f"\nOverall stats:")
        for key, val in stats['overall'].items():
            print(f"  {key}: {val}")

# ==========================================================
# EXAMPLE 2: Compare Two Players Head-to-Head
# ==========================================================
def example_matchup():
    """Predict outcome of specific matchup"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Matchup Prediction")
    print("="*80)
    
    prediction = predict_matchup("Sinner", "Alcaraz", surface="Hard")
    
    if prediction:
        p1 = prediction["player1"]
        p2 = prediction["player2"]
        forecast = prediction["prediction"]
        
        print(f"\n{p1} vs {p2}")
        print(f"Favorite: {forecast['favorite']}")
        print(f"Confidence: {forecast['confidence']:.1f}%")
        print(f"{p1} wins: {forecast['win_probability_p1']:.1%}")
        print(f"{p2} wins: {forecast['win_probability_p2']:.1%}")

# ==========================================================
# EXAMPLE 3: Analyze Multiple Surfaces
# ==========================================================
def example_surface_analysis():
    """Compare player stats across different surfaces"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Surface Analysis")
    print("="*80)
    
    player = "Sinner"
    surfaces = ["Hard", "Clay", "Grass"]
    
    for surface in surfaces:
        stats = predict_player_stats(player, surface=surface)
        
        if stats and "surface_specific" in stats:
            print(f"\n{player} on {surface}:")
            for key, val in stats["surface_specific"].items():
                print(f"  {key}: {val}")

# ==========================================================
# EXAMPLE 4: Get Live Matches from Betting API
# ==========================================================
def example_live_matches():
    """Fetch today's matches from betting API"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Live Matches from Betting API")
    print("="*80)
    
    # Try different sources
    sources = ["sample", "sgo", "rapidapi"]
    
    for source in sources:
        print(f"\nTrying source: {source}")
        matches = get_live_matches(source=source)
        
        if matches:
            print(f"Found {len(matches)} matches:")
            for p1, p2 in matches[:3]:  # Show first 3
                print(f"  {p1} vs {p2}")
            break

# ==========================================================
# EXAMPLE 5: Analyze Full Tournament Day
# ==========================================================
def example_tournament_analysis():
    """Analyze all matches for a day"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Tournament Day Analysis")
    print("="*80)
    
    # Get matches
    matches = get_live_matches(source="sample")
    
    print(f"\nAnalyzing {len(matches)} matches for today...")
    
    predictions = []
    for p1, p2 in matches:
        pred = predict_matchup(p1, p2, surface="Hard")
        if pred:
            predictions.append(pred)
    
    # Summary
    print(f"\nSummary ({len(predictions)} matches):")
    for pred in predictions:
        forecast = pred["prediction"]
        print(f"  {pred['matchup']}: {forecast['favorite']} ({forecast['confidence']:.1f}%)")

# ==========================================================
# EXAMPLE 6: Find High-Value Predictions
# ==========================================================
def example_value_picks():
    """Compare model picks to betting odds (if available)"""
    print("\n" + "="*80)
    print("EXAMPLE 6: Find Value in Predictions")
    print("="*80)
    
    print("\nExample: If model says Sinner 51.2% but odds show +130 (56.6%):")
    print("  Implied odds: 56.6%")
    print("  Model prediction: 51.2%")
    print("  Difference: +5.4% (slight underdog, no value)")
    print("\nExample: If model says Alcaraz 55% but odds show -110 (52.4%):")
    print("  Model prediction: 55%")
    print("  Implied odds: 52.4%")
    print("  Difference: +2.6% (slight edge/value pick)")

# ==========================================================
# EXAMPLE 7: Track Player Trends
# ==========================================================
def example_player_trends():
    """Compare recent form vs overall stats"""
    print("\n" + "="*80)
    print("EXAMPLE 7: Player Form/Trends")
    print("="*80)
    
    player = "Sinner"
    
    # Load cached data
    matches = load_player_cache(player)
    
    if matches:
        print(f"\n{player} Recent Form:")
        
        # Last 5 matches
        recent = aggregate_stats(matches[-5:])
        print(f"\nLast 5 matches:")
        print(f"  Avg aces: {recent.avg_aces:.1f}")
        print(f"  Win rate: {recent.win_rate:.1%}")
        
        # Last 10 matches
        mid = aggregate_stats(matches[-10:-5])
        print(f"\nPrevious 5 matches (5-10 ago):")
        print(f"  Avg aces: {mid.avg_aces:.1f}")
        print(f"  Win rate: {mid.win_rate:.1%}")
        
        print(f"\nTrend: {'↑ Improving' if recent.win_rate > mid.win_rate else '↓ Declining'}")

# ==========================================================
# EXAMPLE 8: Custom Tournament Analysis
# ==========================================================
def example_custom_tournament():
    """Analyze specific tournament matchups"""
    print("\n" + "="*80)
    print("EXAMPLE 8: Custom Tournament")
    print("="*80)
    
    # Custom tournament bracket
    tournament_matchups = [
        ("Sinner", "Alcaraz"),
        ("Djokovic", "Medvedev"),
        ("Sinner", "Djokovic"),  # Hypothetical finals
    ]
    
    print("\nTournament predictions:")
    for p1, p2 in tournament_matchups:
        pred = predict_matchup(p1, p2, surface="Hard")
        
        if pred:
            forecast = pred["prediction"]
            print(f"\n{p1} vs {p2}:")
            print(f"  Winner: {forecast['favorite']} (confidence: {forecast['confidence']:.1f}%)")

# ==========================================================
# MAIN
# ==========================================================
if __name__ == "__main__":
    print("\n" + "="*80)
    print("TENNIS PREDICTOR - USAGE EXAMPLES")
    print("="*80)
    
    # Run examples
    example_player_stats()
    example_matchup()
    example_surface_analysis()
    example_live_matches()
    example_tournament_analysis()
    example_value_picks()
    example_player_trends()
    example_custom_tournament()
    
    print("\n" + "="*80)
    print("Examples complete! See TENNIS_PREDICTOR_SETUP.md for more details.")
    print("="*80)
