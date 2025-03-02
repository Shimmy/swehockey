import json
import re
import time
import requests
from typing import Dict, Union, List, Optional, Any

class SwehockeyAPI:
    """
    API wrapper for the Swedish Hockey API.
    Provides functions to fetch and convert hockey game data into a standardized format.
    """
    
    BASE_URL = "https://backend-app.swehockey.se/GameTicker/"
    HEADERS = {
        "X-Backendversion": "2",
        "X-Useridentity": "_",
    }
    
    def __init__(self, rate_limit_delay: float = 0.5):
        """
        Initialize the SwehockeyAPI client.
        
        Args:
            rate_limit_delay (float): Delay between API requests in seconds to avoid rate limiting
        """
        self.rate_limit_delay = rate_limit_delay
        self._current_game_id = None
        self._lineups_data = None
        self._summary_data = None
        self._events_data = None
        self._converted_data = None
    
    def _make_request(self, endpoint: str, game_id: int) -> Dict:
        """
        Make a request to the Swedish Hockey API.
        
        Args:
            endpoint (str): API endpoint to call
            game_id (int): ID of the game to fetch
            
        Returns:
            dict: Response data as a dictionary
            
        Raises:
            Exception: If the API request fails
        """
        # Construct the full URL
        url = f"{self.BASE_URL}{endpoint}/{game_id}"
        
        # Make the GET request
        response = requests.get(url, headers=self.HEADERS)
        
        # Add a small delay to avoid rate limiting
        time.sleep(self.rate_limit_delay)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            return response.json()
        else:
            raise Exception(f"API request failed with status code: {response.status_code} for endpoint {endpoint}")
    
    def get_line_ups(self, game_id: int) -> Dict:
        """Get line-ups data for a game."""
        return self._make_request("LineUps", game_id)
    
    def get_summary(self, game_id: int) -> Dict:
        """Get summary/statistics data for a game."""
        return self._make_request("Summary", game_id)
    
    def get_actions(self, game_id: int) -> Dict:
        """Get actions/events data for a game."""
        return self._make_request("Actions", game_id)
    
    def load_game(self, game_id: int) -> Dict:
        """
        Load complete game data and convert it to a standardized format.
        Caches the raw data and converted result for later refresh operations.
        
        Args:
            game_id (int): ID of the game to fetch
            
        Returns:
            dict: Converted hockey game data in a standardized format
        """
        self._current_game_id = game_id
        self._lineups_data = self.get_line_ups(game_id)
        self._summary_data = self.get_summary(game_id)
        self._events_data = self.get_actions(game_id)
        
        self._converted_data = self._convert_hockey_data(self._lineups_data, self._summary_data, self._events_data)
        return self._converted_data
    
    def refresh_lineups(self) -> Dict:
        """
        Refresh only the line-ups data for the current game and reconvert the full dataset.
        
        Returns:
            dict: Updated converted hockey game data
            
        Raises:
            Exception: If no game has been loaded yet
        """
        if self._current_game_id is None:
            raise Exception("No game loaded. Call load_game() first.")
        
        self._lineups_data = self.get_line_ups(self._current_game_id)
        self._converted_data = self._convert_hockey_data(self._lineups_data, self._summary_data, self._events_data)
        return self._converted_data
    
    def refresh_summary(self) -> Dict:
        """
        Refresh only the summary/statistics data for the current game and reconvert the full dataset.
        
        Returns:
            dict: Updated converted hockey game data
            
        Raises:
            Exception: If no game has been loaded yet
        """
        if self._current_game_id is None:
            raise Exception("No game loaded. Call load_game() first.")
        
        self._summary_data = self.get_summary(self._current_game_id)
        self._converted_data = self._convert_hockey_data(self._lineups_data, self._summary_data, self._events_data)
        return self._converted_data
    
    def refresh_actions(self) -> Dict:
        """
        Refresh only the actions/events data for the current game and reconvert the full dataset.
        
        Returns:
            dict: Updated converted hockey game data
            
        Raises:
            Exception: If no game has been loaded yet
        """
        if self._current_game_id is None:
            raise Exception("No game loaded. Call load_game() first.")
        
        self._events_data = self.get_actions(self._current_game_id)
        self._converted_data = self._convert_hockey_data(self._lineups_data, self._summary_data, self._events_data)
        return self._converted_data
    
    def refresh_all(self) -> Dict:
        """
        Refresh all data for the current game (equivalent to calling load_game again).
        
        Returns:
            dict: Updated converted hockey game data
            
        Raises:
            Exception: If no game has been loaded yet
        """
        if self._current_game_id is None:
            raise Exception("No game loaded. Call load_game() first.")
        
        return self.load_game(self._current_game_id)
    
    def get_current_data(self) -> Optional[Dict]:
        """
        Get the currently loaded and converted data without making any API calls.
        
        Returns:
            dict: Current converted hockey game data or None if no data is loaded
        """
        return self._converted_data
    
    def _convert_hockey_data(self, lineups_data: Dict, summary_data: Dict, events_data: Dict) -> Dict:
        """
        Convert hockey game data from three separate data sources into a unified, improved structure.
        
        Args:
            lineups_data: Lineups data
            summary_data: Game summary/statistics data
            events_data: Game events data
            
        Returns:
            dict: Unified hockey game data in the improved structure
        """
        # Initialize the output structure
        result = {
            "game": {},
            "teams": {
                "home": {},
                "away": {}
            },
            "personnel": {
                "coaches": {
                    "home": [],
                    "away": []
                },
                "officials": []
            },
            "roster": {
                "home": {
                    "goalies": [],
                    "players": []
                },
                "away": {
                    "goalies": [],
                    "players": []
                }
            },
            "statistics": {
                "byPeriod": [],
                "total": {
                    "home": {},
                    "away": {}
                }
            },
            "events": []
        }
        
        # Extract game information
        game_ticker = lineups_data["GameTicker"]
        
        # Fill game information
        result["game"] = {
            "id": game_ticker["Id"],
            "date": game_ticker["GameDate"],
            "tournament": {
                "name": self._get_tournament_name(summary_data),
                "shortName": game_ticker["TournamentGroupShortName"]
            },
            "venue": self._get_venue(summary_data),
            "attendance": self._get_attendance(summary_data),
            "status": {
                "isStarted": game_ticker["IsStarted"],
                "isEnded": game_ticker["IsEnded"],
                "isOfficial": game_ticker["IsOfficial"],
                "currentSituation": game_ticker["CurrentSituation"]
            },
            "result": {
                "score": f"{game_ticker['Home']['Goals']}-{game_ticker['Guest']['Goals']}",
                "periodResults": self._format_period_results(game_ticker["PeriodResults"])
            }
        }
        
        # Fill team information
        result["teams"]["home"] = {
            "id": game_ticker["Home"]["Id"],
            "clubId": game_ticker["Home"]["ClubId"],
            "name": game_ticker["Home"]["Name"],
            "shortName": game_ticker["Home"]["Shortname"],
            "fullName": game_ticker["Home"]["Fullname"],
            "color": game_ticker["Home"]["Color"],
            "hasLogo": game_ticker["Home"]["ClubHasLogo"],
            "goals": game_ticker["Home"]["Goals"]
        }
        
        result["teams"]["away"] = {
            "id": game_ticker["Guest"]["Id"],
            "clubId": game_ticker["Guest"]["ClubId"],
            "name": game_ticker["Guest"]["Name"],
            "shortName": game_ticker["Guest"]["Shortname"],
            "fullName": game_ticker["Guest"]["Fullname"],
            "color": game_ticker["Guest"]["Color"],
            "hasLogo": game_ticker["Guest"]["ClubHasLogo"],
            "goals": game_ticker["Guest"]["Goals"]
        }
        
        # Fill personnel information (coaches and officials)
        if "LineUp" in game_ticker and "TeamOfficials" in game_ticker["LineUp"]:
            for official in game_ticker["LineUp"]["TeamOfficials"]:
                if "Home" in official and official["Home"]:
                    result["personnel"]["coaches"]["home"].append({
                        "id": official["Home"]["Id"],
                        "name": official["Home"]["Name"],
                        "type": official["Home"]["Type"]
                    })
                
                if "Guest" in official and official["Guest"]:
                    result["personnel"]["coaches"]["away"].append({
                        "id": official["Guest"]["Id"],
                        "name": official["Guest"]["Name"],
                        "type": official["Guest"]["Type"]
                    })
        
        if "OfficialTypes" in game_ticker:
            for official_type in game_ticker["OfficialTypes"]:
                type_name = official_type["Name"]
                for official in official_type["Officials"]:
                    result["personnel"]["officials"].append({
                        "id": official["Id"],
                        "name": official["Name"],
                        "type": type_name
                    })
        
        # Fill roster information
        if "LineUp" in game_ticker and "Lines" in game_ticker["LineUp"]:
            for line in game_ticker["LineUp"]["Lines"]:
                line_id = line["Id"]
                line_name = line["Name"]
                
                for player_item in line["Players"]:
                    # Process home player
                    if "Home" in player_item and player_item["Home"]:
                        player = player_item["Home"]
                        is_goalie = player["Position"] == "GK"
                        player_data = {
                            "id": player["Id"],
                            "jerseyNo": player["JerseyNo"],
                            "name": player["Name"],
                            "position": player["Position"],
                            "starter": player["Starts"]
                        }
                        
                        if is_goalie:
                            result["roster"]["home"]["goalies"].append(player_data)
                        else:
                            player_data["line"] = line_id
                            result["roster"]["home"]["players"].append(player_data)
                    
                    # Process away player
                    if "Guest" in player_item and player_item["Guest"]:
                        player = player_item["Guest"]
                        is_goalie = player["Position"] == "GK"
                        player_data = {
                            "id": player["Id"],
                            "jerseyNo": player["JerseyNo"],
                            "name": player["Name"],
                            "position": player["Position"],
                            "starter": player["Starts"]
                        }
                        
                        if is_goalie:
                            result["roster"]["away"]["goalies"].append(player_data)
                        else:
                            player_data["line"] = line_id
                            result["roster"]["away"]["players"].append(player_data)
        
        # Fill statistics information
        if "Categories" in summary_data["GameTicker"]:
            # Process period statistics
            for category in summary_data["GameTicker"]["Categories"]:
                if category["Name"].startswith("Period"):
                    period_num = int(category["Name"].split(" ")[1])
                    period_stats = {
                        "period": period_num,
                        "home": {},
                        "away": {}
                    }
                    
                    for item in category["Items"]:
                        if item["TeamItem"]:
                            stat_name = self._normalize_stat_name(item["Name"])
                            period_stats["home"][stat_name] = self._parse_stat_value(item["TeamItem"]["ValueHome"])
                            period_stats["away"][stat_name] = self._parse_stat_value(item["TeamItem"]["ValueGuest"])
                    
                    result["statistics"]["byPeriod"].append(period_stats)
            
            # Process total statistics
            for category in summary_data["GameTicker"]["Categories"]:
                if category["Name"] == "Totalt":
                    for item in category["Items"]:
                        if item["TeamItem"]:
                            stat_name = self._normalize_stat_name(item["Name"])
                            
                            if stat_name == "shots":
                                # Extract shot percentage and total shots
                                result["statistics"]["total"]["home"]["shotPercentage"] = self._extract_percentage(item["TeamItem"]["ValueHome"])
                                result["statistics"]["total"]["home"]["shots"] = self._extract_number_in_parenthesis(item["TeamItem"]["ValueHome"])
                                result["statistics"]["total"]["away"]["shotPercentage"] = self._extract_percentage(item["TeamItem"]["ValueGuest"])
                                result["statistics"]["total"]["away"]["shots"] = self._extract_number_in_parenthesis(item["TeamItem"]["ValueGuest"])
                            elif stat_name == "saves":
                                # Extract save percentage and total saves
                                result["statistics"]["total"]["home"]["savePercentage"] = self._extract_percentage(item["TeamItem"]["ValueHome"])
                                result["statistics"]["total"]["home"]["saves"] = self._extract_number_in_parenthesis(item["TeamItem"]["ValueHome"])
                                result["statistics"]["total"]["away"]["savePercentage"] = self._extract_percentage(item["TeamItem"]["ValueGuest"])
                                result["statistics"]["total"]["away"]["saves"] = self._extract_number_in_parenthesis(item["TeamItem"]["ValueGuest"])
                            elif stat_name == "powerPlayPercentage":
                                # Extract power play percentage and time
                                result["statistics"]["total"]["home"]["powerPlayPercentage"] = self._extract_percentage(item["TeamItem"]["ValueHome"])
                                result["statistics"]["total"]["home"]["powerPlayTime"] = self._extract_time_in_parenthesis(item["TeamItem"]["ValueHome"])
                                result["statistics"]["total"]["away"]["powerPlayPercentage"] = self._extract_percentage(item["TeamItem"]["ValueGuest"])
                                result["statistics"]["total"]["away"]["powerPlayTime"] = self._extract_time_in_parenthesis(item["TeamItem"]["ValueGuest"])
                            else:
                                result["statistics"]["total"]["home"][stat_name] = self._parse_stat_value(item["TeamItem"]["ValueHome"])
                                result["statistics"]["total"]["away"][stat_name] = self._parse_stat_value(item["TeamItem"]["ValueGuest"])
        
        # Fill events information
        if "Periods" in events_data["GameTicker"]:
            for period in events_data["GameTicker"]["Periods"]:
                period_id = period["Id"]
                
                for event in period["Events"]:
                    is_home_team = event["IsHome"]
                    event_data = {
                        "id": event["Id"],
                        "period": period_id,
                        "time": event["Time"],
                        "team": "home" if is_home_team else "away",
                        "type": self._get_event_type(event["EventTypeId"]),
                        "typeId": event["EventTypeId"],
                        "isHighlighted": event["IsHighlighted"]
                    }
                    
                    if event["Player"]:
                        player_info = self._parse_player_info(event["Player"])
                        if player_info:
                            event_data["player"] = player_info
                    
                    if event["Description"] and "min" in event["Description"]:
                        event_data["duration"] = int(event["Description"].split(" ")[0])
                    
                    if event["ExtraInfo"]:
                        event_data["reason"] = event["ExtraInfo"]
                    
                    # Handle goal-specific information
                    if event["EventTypeId"] == 3:  # Goal
                        # Extract score state from description (e.g., "4-1 (EQ)")
                        score_match = re.search(r"(\d+-\d+)", event["Description"])
                        if score_match:
                            event_data["scoreState"] = score_match.group(1)
                        
                        # Extract strength from description (e.g., "(EQ)", "(PP1)", "(SH)")
                        strength_match = re.search(r"\((.*?)\)", event["Description"])
                        if strength_match:
                            event_data["strength"] = strength_match.group(1)
                        
                        # Extract goal number for player (e.g., "Player Name (3)")
                        if event["Player"]:
                            goal_num_match = re.search(r"\((\d+)\)$", event["Player"])
                            if goal_num_match:
                                event_data["goalNumber"] = int(goal_num_match.group(1))
                        
                        # Parse assists as a list of player objects instead of a string
                        # Pass the team information (is_home_team) to the assist parser
                        if event["Assist"]:
                            event_data["assists"] = self._parse_assists(event["Assist"], result["roster"], is_home_team)
                    else:
                        # For non-goal events, keep the original assist field if present
                        if event["Assist"]:
                            event_data["assist"] = event["Assist"]
                    
                    result["events"].append(event_data)
        
        # Add timestamp
        result["timestamp"] = events_data.get("Timestamp", "")
        
        return result
    
    # Helper methods
    
    def _format_period_results(self, period_results: str) -> str:
        """Extract just the period results without the total score"""
        match = re.search(r"\((.*?)\)", period_results)
        if match:
            return match.group(1)
        return period_results
    
    def _get_tournament_name(self, summary_data: Dict) -> str:
        """Extract tournament name from summary data"""
        for category in summary_data["GameTicker"]["Categories"]:
            if category["Name"] == "Matchinformation":
                for item in category["Items"]:
                    if item["Name"] == "Serie" and item["InfoItem"]:
                        return item["InfoItem"]["ValueStr"]
        return ""
    
    def _get_venue(self, summary_data: Dict) -> str:
        """Extract venue from summary data"""
        for category in summary_data["GameTicker"]["Categories"]:
            if category["Name"] == "Matchinformation":
                for item in category["Items"]:
                    if item["Name"] == "Arena" and item["InfoItem"]:
                        return item["InfoItem"]["ValueStr"]
        return ""
    
    def _get_attendance(self, summary_data: Dict) -> str:
        """Extract attendance from summary data"""
        for category in summary_data["GameTicker"]["Categories"]:
            if category["Name"] == "Matchinformation":
                for item in category["Items"]:
                    if item["Name"] == "Åskådare" and item["InfoItem"]:
                        return item["InfoItem"]["ValueStr"]
        return ""
    
    def _normalize_stat_name(self, name: str) -> str:
        """Convert Swedish stat names to standardized English names"""
        name_map = {
            "Mål": "goals",
            "Skott": "shots",
            "Räddningar": "saves",
            "Utvisningsminuter": "penalties",
            "PP": "powerPlayPercentage"
        }
        return name_map.get(name, name.lower())
    
    def _parse_stat_value(self, value_str: str) -> Union[int, float, str, None]:
        """Parse stat value to appropriate type (int, float, etc.)"""
        if not value_str:
            return None
        
        # If it's a simple number
        if value_str.isdigit():
            return int(value_str)
        
        # Check if it contains percentage or time information
        if "%" in value_str or ":" in value_str:
            return value_str
        
        # Try to parse as float
        try:
            return float(value_str.replace(",", "."))
        except ValueError:
            return value_str
    
    def _extract_percentage(self, value_str: str) -> float:
        """Extract percentage value from a string like '10,81% (37)'"""
        match = re.search(r"(\d+,\d+)%", value_str)
        if match:
            return float(match.group(1).replace(",", "."))
        return 0.0
    
    def _extract_number_in_parenthesis(self, value_str: str) -> int:
        """Extract number in parenthesis from a string like '10,81% (37)'"""
        match = re.search(r"\((\d+)\)", value_str)
        if match:
            return int(match.group(1))
        return 0
    
    def _extract_time_in_parenthesis(self, value_str: str) -> str:
        """Extract time in parenthesis from a string like '0,00% (03:09)'"""
        match = re.search(r"\((\d+:\d+)\)", value_str)
        if match:
            return match.group(1)
        return ""
    
    def _get_event_type(self, event_type_id: int) -> str:
        """Convert event type ID to descriptive name"""
        event_types = {
            1: "goalie-in",
            2: "goalie-out",
            3: "goal",
            4: "penalty",
            7: "timeout"
        }
        return event_types.get(event_type_id, f"unknown-{event_type_id}")
    
    def _parse_player_info(self, player_str: str) -> Optional[Dict[str, Any]]:
        """Parse player info from a string like '30 Hugo Jortby'"""
        if not player_str:
            return None
        
        # Try to extract jersey number and name
        match = re.match(r"(\d+)\s+(.*?)(?:\s+\(\d+\))?$", player_str)
        if match:
            return {
                "jerseyNo": int(match.group(1)),
                "name": match.group(2)
            }
        return {"name": player_str}
    
    def _parse_assists(self, assist_str: str, roster: Dict, is_home_team: bool) -> List[Dict[str, Any]]:
        """
        Parse the assist string into a list of player objects with jerseyNo and name.
        
        Args:
            assist_str: The assist string (e.g., "26. A Rejdvik" or "28. S Fakt, 55. L Videll")
            roster: The roster dictionary containing player information
            is_home_team: Whether the goal was scored by the home team
            
        Returns:
            List of player objects with jerseyNo and name fields
        """
        if not assist_str or assist_str.strip() == "":
            return []
        
        # Split by comma to handle multiple assists
        assist_players = [player.strip() for player in assist_str.split(",")]
        result = []
        
        for player_str in assist_players:
            # Extract jersey number and abbreviated name
            match = re.match(r"(\d+)\.\s+(.*)", player_str)
            if match:
                jersey_no = int(match.group(1))
                abbr_name = match.group(2)
                
                # Find the corresponding player in the roster to get the full name
                full_name = self._find_player_by_jersey_number(jersey_no, roster, is_home_team)
                
                result.append({
                    "jerseyNo": jersey_no,
                    "name": full_name if full_name else abbr_name
                })
        
        return result
    
    def _find_player_by_jersey_number(self, jersey_no: int, roster: Dict, is_home_team: bool) -> Optional[str]:
        """
        Find a player's full name by jersey number in the roster for the specified team.
        
        Args:
            jersey_no: The jersey number to look for
            roster: The roster dictionary containing player information
            is_home_team: Whether to look in the home team roster
            
        Returns:
            The player's full name or None if not found
        """
        team_key = "home" if is_home_team else "away"
        
        # Check team players
        for player in roster[team_key]["players"]:
            if player["jerseyNo"] == jersey_no:
                return player["name"]
        
        # Check team goalies
        for player in roster[team_key]["goalies"]:
            if player["jerseyNo"] == jersey_no:
                return player["name"]
        
        return None
        
    def save_game(self, game_id: int, filepath: str) -> None:
        """
        Load game data and save it to a JSON file.
        
        Args:
            game_id: ID of the game to fetch
            filepath: Path where the JSON file should be saved
        """
        game_data = self.load_game(game_id)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(game_data, f, ensure_ascii=False, indent=2)
            
        print(f"Game data saved to {filepath}")