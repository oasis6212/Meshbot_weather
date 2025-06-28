import logging

class Forecast2DayFetcher:
    def __init__(self, weather_manager):
        self.weather_manager = weather_manager

    def get_daily_weather(self):
        try:
            data = self.weather_manager.get_daily_data()
            if not data:
                return "Error: Unable to fetch weather data"

            periods = data['properties']['periods'][:5]  # Get first 5 periods

            result = []
            for i, period in enumerate(periods):
                name = period['name']
                temp = period['temperature']
                forecast = period['shortForecast']

                if 'night' in name.lower():
                    if 'tonight' in name.lower():
                        output = f"Tonight's Low {temp}. {forecast}"
                    else:
                        day = name.replace(' Night', '')
                        output = f"{day} Night Low {temp}. {forecast}"
                else:
                    if name == "Today":
                        output = f"Today's High {temp}. {forecast}"
                    else:
                        output = f"{name} High {temp}. {forecast}"

                # Add double newline before all periods except the first one
                if i > 0:
                    output = "\n\n" + output

                result.append(output)

            # Join and ensure total length is under 200
            full_text = "".join(result)
            if len(full_text) > 200:
                # If too long, reduce to 3 periods
                result = result[:3]
                full_text = "".join(result)

            return full_text

        except Exception as e:
            error_msg = f"Error fetching weather data: {str(e)}"
            logging.error(error_msg)
            return error_msg