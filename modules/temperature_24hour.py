from datetime import datetime
import requests

class Temperature24HourFetcher:
    def __init__(self, weather_manager):
        self.weather_manager = weather_manager

    def get_temperature_24hour(self):
        try:
            data = self.weather_manager.get_hourly_data()
            if not data:
                return "Error: Unable to fetch weather data"

            periods = data['properties']['periods']
            result = []
            count = 0
            
            for period in periods:
                try:
                    if count >= 24:
                        break

                    time_str = period['startTime']
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    
                    hour = dt.strftime("%I").lstrip('0')
                    period_str = dt.strftime("%p").lower()
                    
                    if len(hour) == 1:
                        time_str = f"{hour}{period_str}"
                    else:
                        time_str = f"{hour}{period_str[0]}"
                    
                    temp = round(float(period['temperature']))
                    formatted_entry = f"{time_str}:{temp}°"
                    
                    result.append(formatted_entry)
                    count += 1
                    
                except Exception as e:
                    continue
            
            if not result:
                return "Error: Could not process weather data"
            
            return "\n".join(result)
            
        except requests.exceptions.RequestException as e:
            return f"Error fetching weather data: {str(e)}"
        except Exception as e:
            return f"Unexpected error: {str(e)}"