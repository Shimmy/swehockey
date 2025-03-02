import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from jinja2 import Environment, FileSystemLoader, select_autoescape

class HockeyAnnouncer:
    """
    Converts hockey game events into natural language announcements
    using customizable templates.
    """
    
    def __init__(self, templates_dir: str = "templates", language: str = "en"):
        """
        Initialize the announcer with templates directory and language.
        
        Args:
            templates_dir: Directory containing announcement templates
            language: Language code for announcements (e.g., 'en', 'sv')
        """
        self.templates_dir = templates_dir
        self.set_language(language)
        
        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
    
    def set_language(self, language: str):
        """Change the announcement language"""
        self.language = language
    
    def format_time(self, period: int, time_str: str) -> str:
        """
        Format game time as a readable string.
        
        Args:
            period: Period number
            time_str: Time string in format "MM:SS"
            
        Returns:
            Formatted time string (e.g., "5:43 in the 2nd period")
        """
        # Parse time string
        minutes, seconds = map(int, time_str.split(':'))
        
        # Convert time to numeric format
        period_prefix = self._get_period_prefix(period)
        
        return f"{minutes}:{seconds:02d} {period_prefix}"
    
    def _get_period_prefix(self, period: int) -> str:
        """Get the period description based on language"""
        if self.language == "sv":
            period_names = {
                1: "i första perioden",
                2: "i andra perioden",
                3: "i tredje perioden",
                4: "i förlängningen",
                5: "i straffläggningen"  # Shootout
            }
        else:  # Default to English
            period_names = {
                1: "in the 1st period",
                2: "in the 2nd period",
                3: "in the 3rd period",
                4: "in overtime",
                5: "in the shootout"
            }
        
        return period_names.get(period, f"in period {period}")
    
    def format_strength(self, strength: str) -> str:
        """
        Format the strength situation (EQ, PP, SH) as readable text.
        
        Args:
            strength: Strength code (e.g., "EQ", "PP1", "SH1")
            
        Returns:
            Human-readable strength description
        """
        strength_map = {
            "en": {
                "EQ": "at even strength",
                "PP1": "on the power play",
                "PP2": "on a 5-on-3 power play",
                "SH1": "shorthanded",
                "SH2": "on a 3-on-5 penalty kill"
            },
            "sv": {
                "EQ": "i lika styrka",
                "PP1": "i numerärt överläge",
                "PP2": "i 5 mot 3-spel",
                "SH1": "i numerärt underläge",
                "SH2": "i 3 mot 5-spel"
            }
        }
        
        language_map = strength_map.get(self.language, strength_map["en"])
        return language_map.get(strength, "")
    
    def get_goal_context(self, score_state: str, team: str, game_data: Dict[str, Any]) -> str:
        """
        Determine the context of a goal (takes the lead, equalizes, etc.)
        
        Args:
            score_state: Score after the goal (e.g., "2-1")
            team: Team that scored ("home" or "away")
            game_data: Full game data for context
            
        Returns:
            Context description
        """
        # Parse the score
        try:
            home_score, away_score = map(int, score_state.split("-"))
        except:
            return ""
        
        # Determine team's score and opponent's score
        if team == "home":
            team_score = home_score
            opponent_score = away_score
        else:
            team_score = away_score
            opponent_score = home_score
        
        # Calculate previous score
        prev_team_score = team_score - 1
        
        # Determine goal context
        context_map = {
            "en": {
                "takes_lead": "takes the lead",
                "extends_lead": "extends their lead",
                "equalizes": "ties the game",
                "reduces_deficit": "cuts the deficit"
            },
            "sv": {
                "takes_lead": "tar",
                "extends_lead": "utökar",
                "equalizes": "kvitterar",
                "reduces_deficit": "reducerar"
            }
        }
        
        language_map = context_map.get(self.language, context_map["en"])
        
        if prev_team_score < opponent_score and team_score > opponent_score:
            return language_map["takes_lead"]
        elif prev_team_score > opponent_score and team_score > opponent_score:
            return language_map["extends_lead"]
        elif prev_team_score < opponent_score and team_score == opponent_score:
            return language_map["equalizes"]
        elif prev_team_score < opponent_score and team_score < opponent_score:
            return language_map["reduces_deficit"]
        
        return language_map["takes_lead"]
    
    def announce_event(self, event: Dict[str, Any], game_data: Dict[str, Any]) -> str:
        """
        Generate an announcement for a game event.
        
        Args:
            event: The event data to announce
            game_data: The full game data for context
            
        Returns:
            Formatted announcement text
        """
        event_type = event.get("type")
        
        if event_type == "goal":
            return self._announce_goal(event, game_data)
        elif event_type == "penalty":
            return self._announce_penalty(event, game_data)
        elif event_type == "timeout":
            return self._announce_timeout(event, game_data)
        elif event_type == "goalie-in" or event_type == "goalie-out":
            return self._announce_goalie_change(event, game_data)
        else:
            return ""  # No announcement for other event types
    
    def _announce_goal(self, event: Dict[str, Any], game_data: Dict[str, Any]) -> str:
        """Generate announcement for goal events"""
        template_name = f"goal.{self.language}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except:
            # Fallback to English if template doesn't exist
            template = self.env.get_template(f"goal.en.j2")
        
        # Get team names
        team_key = event["team"]
        team_name = game_data["teams"][team_key]["name"]
        
        # Get player name
        scorer = event["player"] if "player" in event else "Unknown Player"
        
        # Format assists
        assists = event.get("assists", [])
        
        # Format game time
        game_time = self.format_time(event["period"], event["time"])
        
        # Get the score after this goal
        score_state = event.get("scoreState", "0-0")
        
        # Get strength situation
        strength = self.format_strength(event.get("strength", "EQ"))
        
        # Get goal context
        goal_context = self.get_goal_context(score_state, team_key, game_data)
        
        # Render the template
        return template.render(
            team=team_name,
            scorer=scorer,
            assists=assists,
            time=game_time,
            score=score_state,
            strength=strength,
            goal_context=goal_context,
            goal_number=event.get("goalNumber", 1)
        )
    
    def _announce_penalty(self, event: Dict[str, Any], game_data: Dict[str, Any]) -> str:
        """Generate announcement for penalty events"""
        template_name = f"penalty.{self.language}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except:
            # Fallback to English if template doesn't exist
            template = self.env.get_template(f"penalty.en.j2")
        
        # Get team names
        team_key = event["team"]
        team_name = game_data["teams"][team_key]["name"]
        
        # Get player name
        player_name = event["player"]["name"] if "player" in event else "Bench penalty"
        
        # Format game time
        game_time = self.format_time(event["period"], event["time"])
        
        # Get penalty reason and duration
        reason = event.get("reason", "Unknown penalty")
        duration = event.get("duration", 2)
        
        # Render the template
        return template.render(
            team=team_name,
            player=player_name,
            time=game_time,
            reason=reason,
            duration=duration
        )
    
    def _announce_timeout(self, event: Dict[str, Any], game_data: Dict[str, Any]) -> str:
        """Generate announcement for timeout events"""
        template_name = f"timeout.{self.language}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except:
            # Fallback to English if template doesn't exist
            template = self.env.get_template(f"timeout.en.j2")
        
        # Get team names
        team_key = event["team"]
        team_name = game_data["teams"][team_key]["name"]
        
        # Format game time
        game_time = self.format_time(event["period"], event["time"])
        
        # Render the template
        return template.render(
            team=team_name,
            time=game_time
        )
    
    def _announce_goalie_change(self, event: Dict[str, Any], game_data: Dict[str, Any]) -> str:
        """Generate announcement for goalie change events"""
        if event["type"] == "goalie-in":
            template_name = f"goalie_in.{self.language}.j2"
        else:
            template_name = f"goalie_out.{self.language}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except:
            # Fallback to English if template doesn't exist
            fallback = "goalie_in.en.j2" if event["type"] == "goalie-in" else "goalie_out.en.j2"
            template = self.env.get_template(fallback)
        
        # Get team names
        team_key = event["team"]
        team_name = game_data["teams"][team_key]["name"]
        
        # Get player name
        goalie_name = event["player"]["name"] if "player" in event else "Unknown Goalie"
        
        # Format game time
        game_time = self.format_time(event["period"], event["time"])
        
        # Render the template
        return template.render(
            team=team_name,
            goalie=goalie_name,
            time=game_time
        )
    def announce_welcome(self, game_data: Dict[str, Any]) -> str:
        """Generate announcement for timeout events"""
        template_name = f"welcome.{self.language}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except:
            # Fallback to English if template doesn't exist
            template = self.env.get_template(f"timeout.en.j2")
        
        # Render the template
        return template.render(
            game=game_data
        )
    
    def announce_lineups(self, game_data: Dict[str, Any]) -> str:
        """Generate announcement for timeout events"""
        template_name = f"lineups.{self.language}.j2"
        
        try:
            template = self.env.get_template(template_name)
        except:
            # Fallback to English if template doesn't exist
            template = self.env.get_template(f"timeout.en.j2")
        
        # Render the template
        return template.render(
            game=game_data
        )
# Example Jinja2 templates with goal context added:

# templates/goal.en.j2
"""
GOAL! {{ team }} scores! {{ scorer }} finds the back of the net {{ time }}{% if strength %} {{ strength }}{% endif %}{% if goal_context %} and {{ goal_context }}{% endif %}. {% if assists|length == 1 %}Assisted by {{ assists[0].name }}.{% elif assists|length == 2 %}Assisted by {{ assists[0].name }} and {{ assists[1].name }}.{% elif assists|length > 2 %}Assisted by {% for assist in assists[:-1] %}{{ assist.name }}, {% endfor %}and {{ assists[-1].name }}.{% else %}Unassisted.{% endif %} The score is now {{ score }}.
"""

# templates/goal.sv.j2
"""
MÅL! {{ team }} gör mål! {{ scorer }} hittar nätet {{ time }}{% if strength %} {{ strength }}{% endif %}{% if goal_context %} och {{ goal_context }}{% endif %}. {% if assists|length == 1 %}Passning från {{ assists[0].name }}.{% elif assists|length == 2 %}Passningar från {{ assists[0].name }} och {{ assists[1].name }}.{% elif assists|length > 2 %}Passningar från {% for assist in assists[:-1] %}{{ assist.name }}, {% endfor %}och {{ assists[-1].name }}.{% else %}Utan assist.{% endif %} Ställningen är nu {{ score }}.
"""

# Other templates remain the same as in the previous version

# Usage example
if __name__ == "__main__":
    from swehockey import SwehockeyAPI
#    
#    # Initialize API and load a game
    api = SwehockeyAPI()
    game_data = api.load_game(862422)
#    
#  
#    # Initialize the announcer
    announcer = HockeyAnnouncer(language="sv")
    print(announcer.announce_welcome(game_data))
    print(announcer.announce_lineups(game_data))
#    
#    # Find goal events to announce
#    goal_events = [event for event in game_data["events"] if event["type"] == "goal"]
#
#    for event in goal_events:
#        announcement = announcer.announce_event(event, game_data)
#        print(announcement)
#        print()