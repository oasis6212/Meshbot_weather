from datetime import datetime
import requests
import logging

class Wind24HourFetcher:
    """
    A class to fetch and format 24-hour wind speed and direction data
    """
    def __init__(self, weather_manager):
        """
        Initialize the Wind24HourFetcher with a weather manager
        
        Args:
            weather_manager: WeatherDataManager instance for fetching weather data
        """
        self.weather_manager = weather_manager
        self.wind_direction_map = {
            'N': 'N',
            'NNE': 'NE',
            'NE': 'NE',
            'ENE': 'NE',
            'E': 'E',
            'ESE': 'SE',
            'SE': 'SE',
            'SSE': 'SE',
            'S': 'S',
            'SSW': 'SW',
            'SW': 'SW',
            'WSW': 'SW',
            'W': 'W',
            'WNW': 'NW',
            'NW': 'NW',
            'NNW': 'NW'
        }

    def _get_direction_abbrev(self, direction):
        """
        Convert full wind direction to two-letter abbreviation
        
        Args:
            direction: Full wind direction (e.g., 'NNW', 'ESE')
            
        Returns:
            Two-letter wind direction abbreviation
        """
        return self.wind_direction_map.get(direction, '--')

    def get_wind_24hour(self):
        """
        Fetch and format 24-hour wind data
        
        Returns:
            List of formatted strings containing hourly wind speed and direction
        """
        try:
            data = self.weather_manager.get_hourly_data()
            if not data:
                return "Error: Unable to fetch weather data"

            periods = data['properties']['periods']
            result = []
            count = 0
            
            # Create timezone-aware current time
            current_time = datetime.now().astimezone()
            
            for period in periods:
                try:
                    time_str = period['startTime']
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    
                    # Skip periods that are in the past
                    if dt <= current_time:
                        continue

                    if count >= 24:  # Limit to 24 entries
                        break

                    hour = dt.strftime("%I").lstrip('0')
                    period_str = dt.strftime("%p").lower()
                    
                    # Format time based on hour digits
                    if len(hour) == 1:
                        time_str = f"{hour}{period_str}"
                    else:
                        time_str = f"{hour}{period_str[0]}"
                    
                    # Get and format wind data
                    wind_speed = round(float(period['windSpeed'].split()[0]))
                    wind_dir = period['windDirection']
                    dir_abbrev = self._get_direction_abbrev(wind_dir)
                    
                    formatted_entry = f"{time_str}:{wind_speed}mph {dir_abbrev}"
                    
                    result.append(formatted_entry)
                    count += 1
                    
                except Exception as e:
                    logging.error(f"Error processing period: {str(e)}")
                    continue
            
            if not result:
                return "Error: Could not process weather data"
            
            return result  # Return list instead of joined string
            
        except requests.exceptions.RequestException as e:
            return f"Error fetching weather data: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"