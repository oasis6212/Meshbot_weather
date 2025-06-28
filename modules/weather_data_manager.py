import requests
import logging
from datetime import datetime, timedelta

class WeatherDataManager:
    def __init__(self, office="HNX", grid_x="67", grid_y="80", user_agent="(myweatherapp, contact@example.com)"):
        self.hourly_url = f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast/hourly"
        self.daily_url = f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast"
        self.headers = {"User-Agent": user_agent}
        
        self.hourly_data = None
        self.daily_data = None
        self.last_hourly_update = None
        self.last_daily_update = None
        self.update_interval = timedelta(hours=1)  # Update every hour
        
    def _fetch_hourly_data(self):
        try:
            response = requests.get(self.hourly_url, headers=self.headers)
            if response.status_code == 200:
                self.hourly_data = response.json()
                self.last_hourly_update = datetime.now()
                logging.info("Updated hourly weather data")
                return True
            else:
                logging.error(f"Failed to fetch hourly data: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"Error fetching hourly weather data: {str(e)}")
            return False

    def _fetch_daily_data(self):
        try:
            response = requests.get(self.daily_url, headers=self.headers)
            if response.status_code == 200:
                self.daily_data = response.json()
                self.last_daily_update = datetime.now()
                logging.info("Updated daily weather data")
                return True
            else:
                logging.error(f"Failed to fetch daily data: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"Error fetching daily weather data: {str(e)}")
            return False

    def needs_update(self, last_update):
        if last_update is None:
            return True
        return datetime.now() - last_update > self.update_interval

    def get_hourly_data(self):
        if self.needs_update(self.last_hourly_update):
            self._fetch_hourly_data()
        return self.hourly_data

    def get_daily_data(self):
        if self.needs_update(self.last_daily_update):
            self._fetch_daily_data()
        return self.daily_data

    def force_update(self):
        """Force an immediate update of both hourly and daily data"""
        return self._fetch_hourly_data() and self._fetch_daily_data()