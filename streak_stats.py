#!/usr/bin/python3

import asyncio
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import aiohttp
import requests


class StreakStats:
    """
    Calculate and generate GitHub streak statistics
    """
    
    def __init__(self, username: str, access_token: str, session: aiohttp.ClientSession):
        self.username = username
        self.access_token = access_token
        self.session = session
        
    async def get_contribution_calendar(self) -> Dict:
        """
        Fetch contribution calendar data from GitHub GraphQL API
        """
        query = """
        query($username: String!) {
          user(login: $username) {
            contributionsCollection {
              contributionCalendar {
                totalContributions
                weeks {
                  contributionDays {
                    contributionCount
                    date
                  }
                }
              }
            }
          }
        }
        """
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }
        
        variables = {
            "username": self.username
        }
        
        try:
            async with self.session.post(
                "https://api.github.com/graphql",
                headers=headers,
                json={"query": query, "variables": variables}
            ) as response:
                data = await response.json()
                return data
        except Exception as e:
            print(f"Error fetching contribution calendar: {e}")
            # Fallback to requests
            try:
                r = requests.post(
                    "https://api.github.com/graphql",
                    headers=headers,
                    json={"query": query, "variables": variables}
                )
                return r.json()
            except Exception as fallback_error:
                print(f"Fallback request also failed: {fallback_error}")
                return {}
    
    def calculate_streaks(self, contribution_data: Dict) -> Tuple[int, int, int, str, str]:
        """
        Calculate current streak, longest streak, and total contributions
        Returns: (current_streak, longest_streak, total_contributions, start_date, end_date)
        """
        try:
            calendar = contribution_data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            total_contributions = calendar["totalContributions"]
            weeks = calendar["weeks"]
            
            # Flatten all contribution days
            all_days = []
            for week in weeks:
                all_days.extend(week["contributionDays"])
            
            # Sort by date
            all_days.sort(key=lambda x: x["date"])
            
            # Calculate current streak
            current_streak = 0
            current_streak_start = None
            current_streak_end = None
            today = datetime.now().date()
            
            # Check backwards from today
            for i in range(len(all_days) - 1, -1, -1):
                day = all_days[i]
                day_date = datetime.strptime(day["date"], "%Y-%m-%d").date()
                
                # If we're looking at today or yesterday (to account for timezone)
                if day_date <= today and (today - day_date).days <= 1:
                    if day["contributionCount"] > 0:
                        if current_streak == 0:
                            current_streak_end = day["date"]
                        current_streak += 1
                        current_streak_start = day["date"]
                    elif current_streak > 0:
                        # Streak is broken
                        break
                elif day_date < today - timedelta(days=1):
                    if day["contributionCount"] > 0:
                        if current_streak == 0:
                            # No active streak found
                            break
                        current_streak += 1
                        current_streak_start = day["date"]
                    else:
                        # Streak ended
                        break
            
            # Calculate longest streak
            longest_streak = 0
            temp_streak = 0
            longest_start = None
            longest_end = None
            temp_start = None
            
            prev_date = None
            for day in all_days:
                day_date = datetime.strptime(day["date"], "%Y-%m-%d").date()
                
                if day["contributionCount"] > 0:
                    if prev_date is None or (day_date - prev_date).days == 1:
                        if temp_streak == 0:
                            temp_start = day["date"]
                        temp_streak += 1
                        if temp_streak > longest_streak:
                            longest_streak = temp_streak
                            longest_start = temp_start
                            longest_end = day["date"]
                    else:
                        temp_streak = 1
                        temp_start = day["date"]
                    prev_date = day_date
                elif temp_streak > 0:
                    # Reset streak when there are no contributions
                    temp_streak = 0
                    temp_start = None
            
            return (
                current_streak,
                longest_streak,
                total_contributions,
                current_streak_start or "",
                current_streak_end or ""
            )
        except Exception as e:
            print(f"Error calculating streaks: {e}")
            return (0, 0, 0, "", "")
    
    async def get_stats(self) -> Dict:
        """
        Get all streak statistics
        """
        data = await self.get_contribution_calendar()
        current_streak, longest_streak, total_contributions, start_date, end_date = self.calculate_streaks(data)
        
        return {
            "currentStreak": current_streak,
            "longestStreak": longest_streak,
            "totalContributions": total_contributions,
            "currentStreakStart": start_date,
            "currentStreakEnd": end_date
        }


def format_date(date_str: str) -> str:
    """Format date string to readable format"""
    if not date_str:
        return "N/A"
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.strftime("%b %d")
    except (ValueError, TypeError):
        return date_str


def generate_svg(stats: Dict) -> str:
    """
    Generate SVG with Dracula theme using template file
    """
    # Read template file
    with open("templates/streak-stats.svg", "r") as f:
        output = f.read()
    
    # Dracula theme colors
    theme = {
        "background": "#282A36",
        "border": "#E4E2E2",
        "stroke": "#E4E2E2",
        "ring": "#FF6E96",
        "fire": "#FF6E96",
        "currStreakNum": "#79DAFA",
        "sideNums": "#FF6E96",
        "currStreakLabel": "#79DAFA",
        "sideLabels": "#FF6E96",
        "dates": "#F8F8F2",
    }
    
    current_streak = stats["currentStreak"]
    longest_streak = stats["longestStreak"]
    total_contributions = stats["totalContributions"]
    
    # Format dates for current streak
    start_date = format_date(stats.get("currentStreakStart", ""))
    end_date = format_date(stats.get("currentStreakEnd", ""))
    date_range = f"{start_date} - Present" if start_date != "N/A" else "No active streak"
    
    # Replace theme colors
    output = re.sub("{{ background }}", theme["background"], output)
    output = re.sub("{{ border }}", theme["border"], output)
    output = re.sub("{{ stroke }}", theme["stroke"], output)
    output = re.sub("{{ ring }}", theme["ring"], output)
    output = re.sub("{{ fire }}", theme["fire"], output)
    output = re.sub("{{ currStreakNum }}", theme["currStreakNum"], output)
    output = re.sub("{{ sideNums }}", theme["sideNums"], output)
    output = re.sub("{{ currStreakLabel }}", theme["currStreakLabel"], output)
    output = re.sub("{{ sideLabels }}", theme["sideLabels"], output)
    output = re.sub("{{ dates }}", theme["dates"], output)
    
    # Replace data values
    output = re.sub("{{ total_contributions }}", f"{total_contributions:,}", output)
    output = re.sub("{{ current_streak }}", str(current_streak), output)
    output = re.sub("{{ longest_streak }}", str(longest_streak), output)
    output = re.sub("{{ date_range }}", date_range, output)
    
    return output


async def main():
    """Main function to generate streak stats"""
    access_token = os.getenv("ACCESS_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not access_token:
        raise Exception("A personal access token is required!")
    
    username = os.getenv("GITHUB_ACTOR")
    if not username:
        raise Exception("GITHUB_ACTOR environment variable is required!")
    
    async with aiohttp.ClientSession() as session:
        streak_stats = StreakStats(username, access_token, session)
        stats = await streak_stats.get_stats()
        
        print(f"Total Contributions: {stats['totalContributions']}")
        print(f"Current Streak: {stats['currentStreak']}")
        print(f"Longest Streak: {stats['longestStreak']}")
        
        # Generate SVG
        svg_content = generate_svg(stats)
        
        # Create output folder if needed
        if not os.path.isdir("generated"):
            os.mkdir("generated")
        
        # Write SVG file
        with open("generated/streak-stats.svg", "w") as f:
            f.write(svg_content)
        
        print("Streak stats SVG generated successfully!")


if __name__ == "__main__":
    asyncio.run(main())
