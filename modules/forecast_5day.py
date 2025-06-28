
import logging


class NWSWeatherFetcher5Day:
    def __init__(self, weather_manager):
        self.weather_manager = weather_manager

    def get_daily_weather(self):
        try:
            data = self.weather_manager.get_daily_data()
            if not data:
                return ["Error: Unable to fetch weather data"]

            periods = data['properties']['periods'][:10]  # Get 10 periods (5 days)

            result = []
            for period in periods:
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

                result.append(output)

            # Format with double newlines before splitting
            formatted_text = "\n\n".join(result)

            # Split into chunks that fit within character limit
            chunks = []
            while formatted_text:
                if len(formatted_text) <= 175:
                    chunks.append(formatted_text)
                    break
                else:
                    # Find last double newline before 175 chars
                    split_point = formatted_text[:175].rfind('\n\n')
                    if split_point == -1:
                        split_point = 175

                    chunks.append(formatted_text[:split_point])
                    formatted_text = formatted_text[split_point:].lstrip()

            # Add message numbering
            messages = []
            for i, chunk in enumerate(chunks):
                messages.append(f"--({i + 1}/{len(chunks)}) 5-Day\n\n{chunk}")

            return messages

        except Exception as e:
            error_msg = f"Error fetching weather data: {str(e)}"
            logging.error(error_msg)
            return [error_msg]