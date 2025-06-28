import logging
from datetime import datetime

class Forecast4DayFetcher:
    def __init__(self, weather_manager):
        self.weather_manager = weather_manager
        self.weather_emojis = {
            "clear": "🌙",
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
        if "thunderstorm" in forecast:
            return self.weather_emojis["thunderstorm"]
        for key, emoji in self.weather_emojis.items():
            if key in forecast:
                return emoji
        return "🌡️"

    def _get_rain_chance(self, properties):
        prob = properties.get('probabilityOfPrecipitation', {}).get('value', 0)
        return 0 if prob is None else prob

    def _format_day_name(self, name, is_first_period=False):
        # Handle special cases for the first period
        if is_first_period:
            if 'night' in name.lower():
                return "Tonight"
            return "Today"
        
        # For other periods, use first 3 letters of the day name
        name = name.split()[0]
        return name[:3]

    def get_weekly_emoji_weather(self):
        try:
            data = self.weather_manager.get_daily_data()
            if not data:
                return ["Error: Unable to fetch weather data"]

            if 'properties' not in data or 'periods' not in data['properties']:
                return ["Error: Invalid weather data format"]

            periods = data['properties']['periods']
            result = []

            # Check if first period is night
            starts_with_night = 'night' in periods[0]['name'].lower()

            # If starting with night, we need 9 periods to get 4 full days
            needed_periods = 9 if starts_with_night else 8
            periods = periods[:needed_periods]

            if starts_with_night:
                # First line will only have night data
                night_period = periods[0]
                day_name = self._format_day_name(night_period['name'], True)
                low_temp = night_period['temperature']
                night_emoji = self._get_emoji(night_period['shortForecast'])
                night_rain = self._get_rain_chance(night_period)

                line = f"{day_name} {self.rain_emoji}{night_rain}% ❌ {night_emoji} ❌ ↓{low_temp}°"
                result.append(line)

                # Process remaining days
                for i in range(1, len(periods) - 1, 2):
                    day_period = periods[i]
                    night_period = periods[i + 1]

                    day_name = self._format_day_name(day_period['name'])

                    day_rain = self._get_rain_chance(day_period)
                    night_rain = self._get_rain_chance(night_period)
                    max_rain = max(day_rain, night_rain)

                    day_emoji = self._get_emoji(day_period['shortForecast'])
                    night_emoji = self._get_emoji(night_period['shortForecast'])

                    high_temp = day_period['temperature']
                    low_temp = night_period['temperature']

                    line = f"{day_name} {self.rain_emoji}{max_rain}% {day_emoji} {night_emoji} ↑{high_temp}° ↓{low_temp}°"
                    result.append(line)
            else:
                # Process all days normally, with special handling for first day
                for i in range(0, min(len(periods), 8), 2):
                    day_period = periods[i]
                    night_period = periods[i + 1] if i + 1 < len(periods) else None

                    if not night_period:
                        continue

                    day_name = self._format_day_name(day_period['name'], i == 0)

                    day_rain = self._get_rain_chance(day_period)
                    night_rain = self._get_rain_chance(night_period)
                    max_rain = max(day_rain, night_rain)

                    day_emoji = self._get_emoji(day_period['shortForecast'])
                    night_emoji = self._get_emoji(night_period['shortForecast'])

                    high_temp = day_period['temperature']
                    low_temp = night_period['temperature']

                    line = f"{day_name} {self.rain_emoji}{max_rain}% {day_emoji} {night_emoji} ↑{high_temp}° ↓{low_temp}°"
                    result.append(line)

            return result[:4]  # Only return first 4 days

        except Exception as e:
            error_msg = f"Error fetching weather data: {str(e)}"
            logging.error(error_msg)
            return [error_msg]