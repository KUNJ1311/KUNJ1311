#!/usr/bin/python3

import asyncio
import os
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
    Generate SVG with Dracula theme
    """
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
    
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" style="isolation:isolate" viewBox="0 0 495 195" width="495px" height="195px" direction="ltr">
    <style>
        @keyframes currstreak {{
            0% {{ font-size: 3px; opacity: 0.2; }}
            80% {{ font-size: 34px; opacity: 1; }}
            100% {{ font-size: 28px; opacity: 1; }}
        }}
        @keyframes fadein {{
            0% {{ opacity: 0; }}
            100% {{ opacity: 1; }}
        }}
    </style>
    <defs>
        <clipPath id="_clipPath_OZGVkNtlxRZM">
            <rect width="495" height="195"/>
        </clipPath>
    </defs>
    <g clip-path="url(#_clipPath_OZGVkNtlxRZM)">
        <g style="isolation:isolate">
            <rect width="495" height="195" style="fill:{theme['background']}" stroke-width="1.5" stroke="{theme['border']}" stroke-linejoin="miter" stroke-linecap="square" stroke-miterlimit="3"/>
        </g>
        <line x1="330" y1="28" x2="330" y2="170" vector-effect="non-scaling-stroke" stroke-width="1" stroke="{theme['stroke']}" stroke-linejoin="miter" stroke-linecap="square" stroke-miterlimit="3"/>
        <line x1="165" y1="28" x2="165" y2="170" vector-effect="non-scaling-stroke" stroke-width="1" stroke="{theme['stroke']}" stroke-linejoin="miter" stroke-linecap="square" stroke-miterlimit="3"/>
        
        <!-- Total Contributions -->
        <g transform="translate(0, 0)">
            <g transform="translate(25, 48)">
                <text x="57.5" y="0" style="font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-weight:700;font-size:14px;font-style:normal;fill:{theme['sideLabels']};stroke:none;animation:fadein 0.5s ease-in-out forwards">Total Contributions</text>
            </g>
            <g transform="translate(25, 84)">
                <text x="57.5" y="0" style="font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-weight:700;font-size:28px;font-style:normal;fill:{theme['sideNums']};stroke:none;animation:fadein 0.5s ease-in-out forwards">{total_contributions:,}</text>
            </g>
        </g>
        
        <!-- Current Streak -->
        <g transform="translate(165, 0)">
            <g transform="translate(82.5, 48)">
                <text x="0" y="0" style="font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-weight:700;font-size:14px;font-style:normal;fill:{theme['currStreakLabel']};stroke:none;text-anchor:middle;animation:fadein 0.5s ease-in-out forwards">Current Streak</text>
            </g>
            <g transform="translate(82.5, 108)">
                <text x="0" y="-20" style="font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-weight:700;font-size:28px;font-style:normal;fill:{theme['currStreakNum']};stroke:none;text-anchor:middle;animation:currstreak 0.6s ease-in-out forwards">{current_streak}</text>
                <text x="0" y="12" style="font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-weight:400;font-size:14px;font-style:normal;fill:{theme['dates']};stroke:none;text-anchor:middle;animation:fadein 0.5s ease-in-out forwards">{date_range}</text>
            </g>
            <g transform="translate(40, 71)">
                <circle r="40" cx="42.5" cy="42.5" fill="none" stroke="{theme['ring']}" stroke-width="5" style="animation:fadein 0.5s ease-in-out forwards"/>
                <g transform="translate(19, 22)">
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 512 512">
                        <path fill="{theme['fire']}" d="M350.6 69.5C345.7 45 324.4 28.6 315.6 35c-4.5 3.3-2.7 20.2 1.8 41.9C311.7 56.3 289 30 264.7 30c-11.7 0-15.7 19.8-9.9 45.4-9.5-15.5-22.4-28.9-36.3-28.9-7.6 0-12.3 15.8-7.6 36.4-8.2-12-18.2-20.3-28.7-20.3-17 0-25.1 38.4-18.5 67.2C120.9 159 103 204.6 103 256c0 109.4 64.6 198 144.5 198 79.9 0 144.5-88.6 144.5-198 0-53.1-18.6-100.4-62.2-131.7 0-.1 12.1-35.8 20.8-54.8z"/>
                    </svg>
                </g>
            </g>
        </g>
        
        <!-- Longest Streak -->
        <g transform="translate(330, 0)">
            <g transform="translate(82.5, 48)">
                <text x="0" y="0" style="font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-weight:700;font-size:14px;font-style:normal;fill:{theme['sideLabels']};stroke:none;text-anchor:middle;animation:fadein 0.5s ease-in-out forwards">Longest Streak</text>
            </g>
            <g transform="translate(82.5, 84)">
                <text x="0" y="0" style="font-family:'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;font-weight:700;font-size:28px;font-style:normal;fill:{theme['sideNums']};stroke:none;text-anchor:middle;animation:fadein 0.5s ease-in-out forwards">{longest_streak}</text>
            </g>
        </g>
    </g>
</svg>"""
    
    return svg


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
