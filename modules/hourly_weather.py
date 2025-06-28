import logging
from datetime import datetime


class EmojiWeatherFetcher:
    def __init__(self, weather_manager):
        self.weather_manager = weather_manager
        self.weather_emojis = {
            "clear": "🌙",  # Changed from ☀️ to 🌙
            "sunny": "☀️",
            "partly sunny": "🌤️",
            "mostly sunny": "🌤️",
            "partly cloudy": "⛅",
            "mostly cloudy": "🌥️",
            "cloudy": "☁️",
            "rain": "🌧️",
            "showers": "🌧️",
            "thunderstorm": "⛈️",
            "snow": "🌨️",
            "fog": "🌫️"
        }
        self.rain_emoji = "💧"

    def _get_emoji(self, forecast):
        forecast = forecast.lower()
        # First check for thunderstorm specifically
        if "thunderstorm" in forecast:
            return self.weather_emojis["thunderstorm"]
        # Then check for other conditions
        for key, emoji in self.weather_emojis.items():
            if key in forecast:
                return emoji
        return "🌡️"  # Default emoji if no match found

    def _get_rain_chance(self, properties):
        prob = properties.get('probabilityOfPrecipitation', {}).get('value', 0)
        return 0 if prob is None else prob

    def _format_time(self, dt):
        # Get hour without leading zero
        hour = dt.strftime("%I").lstrip('0')
        # Get period (AM/PM)
        period_str = dt.strftime("%p").lower()

        # Format time based on hour length
        if len(hour) == 1:
            # Single digit hour - keep the 'm'
            return f"{hour}{period_str}"
        else:
            # Double digit hour - use 'a' or 'p' with a space
            return f"{hour}{period_str[0]} "

    def get_emoji_weather(self):
        try:
            data = self.weather_manager.get_hourly_data()
            if not data:
                return "Error: Unable to fetch weather data"

            if 'properties' not in data or 'periods' not in data['properties']:
                return "Error: Invalid weather data format"

            result = []
            count = 0
            # Create timezone-aware current time in UTC
            current_time = datetime.now().astimezone()

            for period in data['properties']['periods']:
                time_str = period['startTime']
                # Parse the API time (which includes timezone info)
                dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))

                # Skip periods that are in the past
                if dt <= current_time:
                    continue

                if count >= 23:  # Limit to 23 entries
                    break

                time_format = self._format_time(dt)
                emoji = self._get_emoji(period['shortForecast'])
                temp = str(round(period['temperature']))
                rain_chance = self._get_rain_chance(period)

                line = f"{time_format}{emoji}{temp}°{self.rain_emoji}{rain_chance}%"
                result.append(line)
                count += 1

            return "\n".join(result)

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logging.error(error_msg)
            return error_msg