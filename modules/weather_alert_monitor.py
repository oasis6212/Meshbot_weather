import time
import threading
import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class WeatherAlerts:
    def __init__(self, lat, lon, interface, user_agent_app, user_agent_email, check_interval=300, sender_id=None, message_delay=10, settings=None):
        """Initialize the WeatherAlerts class.
        
        Args:
            lat (str): Latitude for the alert location
            lon (str): Longitude for the alert location
            interface: Interface object for sending messages
            user_agent_app (str): App name for the user agent
            user_agent_email (str): Contact email for the user agent
            check_interval (int, optional): Time between alert checks in seconds. Defaults to 300.
            sender_id (str, optional): Sender ID for messages. Defaults to None.
            message_delay (int, optional): Delay between split messages in seconds. Defaults to 10.
            settings (dict, optional): Additional settings dictionary. Defaults to None.
        """
        self.lat = lat
        self.lon = lon
        self.interface = interface
        self.sender_id = sender_id
        self.check_interval = check_interval
        self.message_delay = message_delay
        self.settings = settings or {}
        self.last_alert_id = None
        self.base_url = "https://api.weather.gov/alerts/active"
        self.params = {
            "point": f"{self.lat},{self.lon}"
        }
        self.headers = {
            "User-Agent": f"({user_agent_app}, {user_agent_email})"
        }

    def split_message(self, text, max_length=175):
        """Split a message into chunks of specified maximum length, preserving whole words.

        Args:
            text (str): Text to split
            max_length (int, optional): Maximum length of each chunk. Defaults to 175.

        Returns:
            list: List of message chunks
        """
        messages = []
        lines = text.split('\n')
        current_chunk = []
        current_length = 0

        for line in lines:
            words = line.split()
            for word in words:
                # Check if adding this word would exceed the limit
                # +1 for space, another +1 for potential newline
                word_length = len(word) + (1 if current_chunk else 0)

                if current_length + word_length > max_length:
                    # Current chunk is full, save it and start a new one
                    if current_chunk:
                        messages.append(' '.join(current_chunk))
                    current_chunk = [word]
                    current_length = len(word)
                else:
                    current_chunk.append(word)
                    current_length += word_length

            # Add a newline after each original line if we're continuing the same chunk
            if current_chunk:
                current_length += 1  # Account for the newline
                if current_length > max_length:
                    # If adding newline would exceed limit, start new chunk
                    messages.append(' '.join(current_chunk))
                    current_chunk = []
                    current_length = 0

        # Don't forget the last chunk
        if current_chunk:
            messages.append(' '.join(current_chunk))

        return messages

    def check_alerts(self):
        """Check for new weather alerts and send notifications if needed."""
        try:
            logger.info("Updated weather alerts")
            response = requests.get(self.base_url, params=self.params, headers=self.headers)
            response.raise_for_status()  # Raise exception for bad status codes

            data = response.json()
            if not data.get('features'):
                return

            latest_alert = data['features'][0]
            alert_id = latest_alert['properties']['id']

            if alert_id == self.last_alert_id:
                return

            self.last_alert_id = alert_id
            alert_props = latest_alert['properties']

            # Check if description should be included
            include_description = self.settings.get('ALERT_INCLUDE_DESCRIPTION', True)

            # Prepare the alert message based on settings
            if include_description:
                full_message = (
                    f"{alert_props['headline']}\n"
                    f"Description: {alert_props['description']}"
                )
            else:
                full_message = alert_props['headline']

            # Split message into chunks and send
            messages = self.split_message(full_message)

            if not self.interface or not hasattr(self.interface, 'sendText'):
                logger.error("Interface not properly configured for sending messages")
                return

            for i, msg in enumerate(messages, 1):
                formatted_msg = f"--({i}/{len(messages)}) Alert--\n{msg}"
                self.interface.sendText(
                    formatted_msg,
                    wantAck=False,
                    destinationId='^all'
                )
                if i < len(messages):  # Don't sleep after last message
                    time.sleep(self.message_delay)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch weather alerts: {str(e)}")
        except Exception as e:
            logger.error(f"Error checking weather alerts: {str(e)}")

    def start_monitoring(self):
        """Start continuous monitoring of weather alerts in a separate thread."""

        def monitor():
            while True:
                try:
                    self.check_alerts()
                except Exception as e:
                    logger.error(f"Error in monitor thread: {str(e)}")
                finally:
                    time.sleep(self.check_interval)

        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()