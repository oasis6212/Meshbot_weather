# !python3
# -*- coding: utf-8 -*-

"""
Meshbot Weather
=======================

meshbot.py: A message bot designed for Meshtastic, providing information from modules upon request:


Author:
- Andy
- April 2024

MIT License

Copyright (c) 2024 Andy

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""



import argparse
import logging
import threading
import time
import yaml
import datetime
import random
import signal
import sys

try:
    import meshtastic.serial_interface
    import meshtastic.tcp_interface
    from pubsub import pub
except ImportError:
    print(
        "ERROR: Missing meshtastic library!\nYou can install it via pip:\npip install meshtastic\n"
    )

import serial.tools.list_ports
import requests

from modules.temperature_24hour import Temperature24HourFetcher
from modules.forecast_2day import Forecast2DayFetcher
from modules.hourly_weather import EmojiWeatherFetcher
from modules.rain_24hour import RainChanceFetcher
from modules.forecast_5day import NWSWeatherFetcher5Day
from modules.weather_data_manager import WeatherDataManager
from modules.weather_alert_monitor import WeatherAlerts
from modules.forecast_4day import Forecast4DayFetcher
from modules.forecast_7day import Forecast7DayFetcher
from modules.wind_24hour import Wind24HourFetcher

UNRECOGNIZED_MESSAGES = [
    "Oops! I didn't recognize that command. Type 'menu' to see a list of options.",
    "I'm not sure what you mean. Type 'menu' for available commands.",
    "That command isn't in my vocabulary. Send 'menu' to see what I understand.",
    "Hmm, I don't know that one. Send 'menu' for a list of commands I know.",
    "Sorry, I didn't catch that. Send 'menu' to see what commands you can use.",
    "Well that's definitely not in my programming. Type 'menu' before we both crash.",
    "Oh sure, just make up commands. Type 'menu' for the real ones."
]


interface = None

def find_serial_ports():
    ports = [port.device for port in serial.tools.list_ports.comports()]
    filtered_ports = [
        port for port in ports if "COM" in port.upper() or "USB" in port.upper()
    ]
    return filtered_ports


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger()

# GLOBALS
MYNODE = ""
MYNODES = ""
DM_MODE = ""
FIREWALL = ""
DUTYCYCLE = ""
alerts = None

with open("settings.yaml", "r") as file:
    settings = yaml.safe_load(file)

MYNODES = settings.get("MYNODES")
DM_MODE = settings.get("DM_MODE")
FIREWALL = settings.get("FIREWALL")
DUTYCYCLE = settings.get("DUTYCYCLE")

NWS_OFFICE = settings.get("NWS_OFFICE", "HNX")
NWS_GRID_X = settings.get("NWS_GRID_X", "67")
NWS_GRID_Y = settings.get("NWS_GRID_Y", "80")

USER_AGENT_APP = settings.get("USER_AGENT_APP", "myweatherapp")
USER_AGENT_EMAIL = settings.get("USER_AGENT_EMAIL", "contact@example.com")
USER_AGENT = f"({USER_AGENT_APP}, {USER_AGENT_EMAIL})"

logger.info(f"DUTYCYCLE: {DUTYCYCLE}")
logger.info(f"DM_MODE: {DM_MODE}")
logger.info(f"FIREWALL: {FIREWALL}")

transmission_count = 0
cooldown = False

temperature_24hour_info = None
forecast_2day_info = None
emoji_weather_info = None
rain_chance_info = None

weather_manager = WeatherDataManager(
    NWS_OFFICE,
    NWS_GRID_X,
    NWS_GRID_Y,
    USER_AGENT
)

# Initialize weather classes with weather manager
temperature_24hour = Temperature24HourFetcher(weather_manager)
forecast_2day = Forecast2DayFetcher(weather_manager)
emoji_weather_fetcher = EmojiWeatherFetcher(weather_manager)
rain_chance_fetcher = RainChanceFetcher(weather_manager)
nws_weather_fetcher_5day = NWSWeatherFetcher5Day(weather_manager)
forecast_4day = Forecast4DayFetcher(weather_manager)
forecast_7day = Forecast7DayFetcher(weather_manager)
wind_24hour = Wind24HourFetcher(weather_manager)


def get_temperature_24hour():
    global temperature_24hour_info
    temperature_24hour_info = temperature_24hour.get_temperature_24hour()
    return temperature_24hour_info


def get_forecast_2day():
    global forecast_2day_info
    forecast_2day_info = forecast_2day.get_daily_weather()
    return forecast_2day_info


def get_emoji_weather():
    global emoji_weather_info
    emoji_weather_info = emoji_weather_fetcher.get_emoji_weather()
    return emoji_weather_info


def get_rain_chance():
    global rain_chance_info
    rain_chance_info = rain_chance_fetcher.get_rain_chance()
    return rain_chance_info


def reset_transmission_count():
    global transmission_count
    if settings.get('DUTYCYCLE', False):
        transmission_count -= 1
        if transmission_count < 0:
            transmission_count = 0
        logger.info(f"Reducing transmission count {transmission_count}")
        threading.Timer(180.0, reset_transmission_count).start()


def reset_cooldown():
    global cooldown
    cooldown = False
    logger.info("Cooldown Disabled.")
    threading.Timer(240.0, reset_cooldown).start()


def split_message(message, max_length=175, message_type="Hourly"):
    lines = message.split('\n')
    messages = []
    current_message = []
    current_length = 0

    for line in lines:
        line_length = len(line.encode('utf-8')) + (1 if current_message else 0)

        if current_length + line_length > max_length:
            messages.append('\n'.join(current_message))
            current_message = []
            current_length = 0

        current_message.append(line)
        current_length += line_length

    if current_message:
        messages.append('\n'.join(current_message))

    for i in range(len(messages)):
        messages[i] = f"--({i + 1}/{len(messages)}) {message_type}\n" + messages[i]

    return messages


def get_forecast_4day():
    global forecast_4day_info
    forecast_4day_info = forecast_4day.get_weekly_emoji_weather()
    return "\n".join(forecast_4day_info)


def get_wind_24hour():
    global wind_24hour_info
    wind_24hour_info = wind_24hour.get_wind_24hour()
    return wind_24hour_info


def message_listener(packet, interface):
    global transmission_count
    global cooldown
    global DM_MODE
    global FIREWALL
    global DUTYCYCLE
    global MYNODE
    global alerts

    try:
        if packet is not None and packet["decoded"].get("portnum") == "TEXT_MESSAGE_APP":
            message = packet["decoded"]["text"].lower()
            sender_id = packet["from"]
            
            # Check if it's a DM
            is_direct_message = False
            if "to" in packet:
                is_direct_message = str(packet["to"]) == str(MYNODE)

            # Only log if it's a DM
            if is_direct_message:
                logger.info(f"Message {packet['decoded']['text']} from {packet['from']}")
                logger.info(f"transmission count {transmission_count}")

            # Enforce DM_MODE
            if DM_MODE and not is_direct_message:
                return

            # firewall logging
            if FIREWALL and not any(node in str(packet["from"]) for node in MYNODES):
                logger.warning(f"Firewall blocked message from {packet['from']}: {message}")
                return

            if (transmission_count < 16 or DUTYCYCLE == False):
                first_message_delay = settings.get('FIRST_MESSAGE_DELAY', 3)
                subsequent_message_delay = settings.get('MESSAGE_DELAY', 10)

                # Helper function to handle message sequences
                def send_message_sequence(messages, message_type=""):
                    for i, msg in enumerate(messages):
                        if i == 0:  # First message
                            time.sleep(first_message_delay)
                        interface.sendText(msg, wantAck=True, destinationId=sender_id)
                        if i < len(messages) - 1:  # Don't delay after last message
                            time.sleep(subsequent_message_delay)

                if "test" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    interface.sendText(" ACK", wantAck=True, destinationId=sender_id)
                elif "?" in message or "menu" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    if settings.get('FULL_MENU', True):
                        interface.sendText(
                            "    --Multi-Message--\n"
                            "hourly - 24h outlook\n"
                            "7day - 7 day simple\n"
                            "5day - 5 day detailed\n"
                            "wind - 24h wind\n\n"
                            "    --Single Message--\n"
                            "2day - 2 day detailed\n"
                            "4day - 4 day simple\n"
                            "rain - 24h precipitation\n"
                            "temp - 24h temperature\n"
                            , wantAck=True, destinationId=sender_id)
                    else:
                        interface.sendText(
                            "  --Weather Commands--\n"
                            "2day - 2 day forecast\n"
                            "4day - 4 day forecast\n"
                            "temp - 24h temperature\n"
                            "rain - 24h precipitation"
                            , wantAck=True, destinationId=sender_id)
                elif "temp" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    interface.sendText(get_temperature_24hour(), wantAck=True, destinationId=sender_id)
                elif "2day" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    interface.sendText(get_forecast_2day(), wantAck=True, destinationId=sender_id)
                elif "hourly" in message:
                    if settings.get('ENABLE_HOURLY_WEATHER', True):
                        transmission_count += 1
                        weather_data = get_emoji_weather()
                        messages = split_message(weather_data)
                        send_message_sequence(messages)
                    else:
                        time.sleep(first_message_delay)
                        interface.sendText("Hourly weather module is disabled.", wantAck=True, destinationId=sender_id)
                elif "rain" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    interface.sendText(get_rain_chance(), wantAck=True, destinationId=sender_id)
                elif "5day" in message:
                    if settings.get('ENABLE_5DAY_FORECAST', True):
                        transmission_count += 1
                        weather_messages = nws_weather_fetcher_5day.get_daily_weather()
                        send_message_sequence(weather_messages)
                    else:
                        time.sleep(first_message_delay)
                        interface.sendText("5-day forecast module is disabled.", wantAck=True, destinationId=sender_id)
                elif "4day" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    interface.sendText(get_forecast_4day(), wantAck=True, destinationId=sender_id)
                elif "wind" in message:
                    transmission_count += 1
                    weather_data = wind_24hour.get_wind_24hour()
                    if isinstance(weather_data, list):
                        weather_text = '\n'.join(weather_data)
                        messages = split_message(weather_text, max_length=180, message_type="Wind")
                        send_message_sequence(messages)
                    else:
                        time.sleep(first_message_delay)
                        interface.sendText(weather_data, wantAck=True, destinationId=sender_id)
                elif "advertise" in message:
                    transmission_count += 1
                    interface.sendText(
                        "Hello all! I am a weather bot that does weather alerts and forecasts. "
                        "You can DM me \"?\" for a list of my forecast commands.\n\n"
                        "For more information, check me out on Github. https://github.com/oasis6212/Meshbot_weather",
                        wantAck=True,
                        destinationId="^all"
                    )
                elif "7day" in message:
                    if settings.get('ENABLE_7DAY_FORECAST', True):
                        transmission_count += 1
                        weather_data = forecast_7day.get_weekly_emoji_weather()
                        messages = split_message(weather_data, message_type="7day")
                        send_message_sequence(messages)
                    else:
                        time.sleep(first_message_delay)
                        interface.sendText("7-day forecast module is disabled.", wantAck=True, destinationId=sender_id)
                elif "alert-status" in message:
                    transmission_count += 1
                    interface.sendText(get_weather_alert_status(), wantAck=True, destinationId=sender_id)
                elif "alert" in message:
                    transmission_count += 1
                    if alerts:
                        if not alerts.broadcast_full_alert(sender_id):
                            time.sleep(first_message_delay)
                            if not settings.get('ENABLE_FULL_ALERT_COMMAND', True):
                                interface.sendText(
                                    "The full-alert command is disabled in settings.",
                                    wantAck=True,
                                    destinationId=sender_id
                                )
                            else:
                                interface.sendText(
                                    "No active alerts at this time.",
                                    wantAck=True,
                                    destinationId=sender_id
                                )
                else:
                    # If it's a DM but doesn't match any command, send a random help message
                    if is_direct_message:
                        transmission_count += 1
                        interface.sendText(
                            random.choice(UNRECOGNIZED_MESSAGES),
                            wantAck=True,
                            destinationId=sender_id
                        )

            if transmission_count >= 11 and DUTYCYCLE == True:
                if not cooldown:
                    interface.sendText(
                        "❌ Bot has reached duty cycle, entering cool down... ❄",
                        wantAck=False,
                    )
                    logger.info("Cooldown enabled.")
                    cooldown = True
                logger.info(
                    "Duty cycle limit reached. Please wait before transmitting again."
                )

    except KeyError as e:
        node_name = interface.getMyNodeInfo().get('user', {}).get('longName', 'Unknown')
        logger.error(f'Attached node "{node_name}" was unable to decode incoming message, possible key mismatch in its node-database.')
        return


def signal_handler(sig, frame):
    """Perform a graceful shutdown when CTRL+C is pressed"""
    global interface
    logger.info("\nInitiating shutdown...")
    try:
        if interface is not None:
           # logger.info("Sending shutdown command to node...")
            try:
                # Send shutdown command
                interface.localNode.shutdown()
                # Give the node sufficient time to complete its shutdown process
                logger.info("Waiting for node to complete shutdown...")
                time.sleep(17)  # Time delay for node to finish shutting down
            except Exception as e:
                logger.error(f"Error sending shutdown command: {e}")
                
            logger.info("Closing Meshtastic interface...")
            interface.close()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    sys.exit(0)

def main():
    global interface, alerts  # Add alerts to global declaration
    signal.signal(signal.SIGINT, signal_handler)
    
    logger.info("Starting program.")
    reset_transmission_count()
    if settings.get('DUTYCYCLE', False):
        reset_cooldown()

    parser = argparse.ArgumentParser(description="Meshbot_Weather a bot for Meshtastic devices")
    parser.add_argument("--port", type=str, help="Specify the serial port to probe")
    parser.add_argument("--host", type=str, help="Specify meshtastic host (IP address) if using API")

    args = parser.parse_args()

    if args.port:
        serial_ports = [args.port]
        logger.info(f"Serial port {serial_ports}\n")
    elif args.host:
        ip_host = args.host
        print(ip_host)
        logger.info(f"Meshtastic API host {ip_host}\n")
    else:
        serial_ports = find_serial_ports()
        if serial_ports:
            logger.info("Available serial ports:")
            for port in serial_ports:
                logger.info(port)
            logger.info(
                "Im not smart enough to work out the correct port, please use the --port argument with a relevent meshtastic port"
            )
        else:
            logger.info("No serial ports found.")
        exit(0)

    logger.info(f"Press CTRL-C to terminate the program")

    # Create interface
    if args.host:
        interface = meshtastic.tcp_interface.TCPInterface(hostname=ip_host, noProto=False)
    else:
        interface = meshtastic.serial_interface.SerialInterface(serial_ports[0])

    global MYNODE
    MYNODE = get_my_node_id(interface)
    logger.info(f"Automatically detected MYNODE ID: {MYNODE}")

    if DM_MODE and not MYNODE:
        logger.error("DM_MODE is enabled but failed to get MYNODE ID. Please check connection to device.")
        exit(1)

    if settings.get('ENABLE_AUTO_REBOOT', True):
        reboot_thread = threading.Thread(
            target=schedule_daily_reboot,
            args=(interface,),
            daemon=True
        )
        reboot_thread.start()
        logger.info("Daily reboot scheduler started")

    try:
        my_info = interface.getMyNodeInfo()
        logger.info("Connected to Meshtastic Node:")
        logger.info(f"Node Name: {my_info.get('user', {}).get('longName', 'Unknown')}")
    except Exception as e:
        logger.error(f"Failed to get node info: {e}")

    message_delay = settings.get('MESSAGE_DELAY', 10)

    alerts = WeatherAlerts(
        settings.get("ALERT_LAT"),
        settings.get("ALERT_LON"),
        interface,
        settings.get("USER_AGENT_APP"),
        settings.get("USER_AGENT_EMAIL"),
        settings.get("ALERT_CHECK_INTERVAL", 300),
        message_delay=message_delay,
        settings=settings
    )
    alerts.start_monitoring()
    pub.subscribe(message_listener, "meshtastic.receive")

    while True:
        time.sleep(1)


def schedule_daily_reboot(interface):
    if not settings.get('ENABLE_AUTO_REBOOT', True):
        return

    reboot_hour = settings.get('AUTO_REBOOT_HOUR', 3)
    reboot_minute = settings.get('AUTO_REBOOT_MINUTE', 0)
    reboot_delay = settings.get('REBOOT_DELAY_SECONDS', 10)

    while True:
        now = datetime.datetime.now()
        next_reboot = now.replace(
            hour=reboot_hour,
            minute=reboot_minute,
            second=0,
            microsecond=0
        )

        if now >= next_reboot:
            next_reboot += datetime.timedelta(days=1)

        seconds_until_reboot = (next_reboot - now).total_seconds()
        time.sleep(seconds_until_reboot)

        try:
            logger.info(f"Executing scheduled reboot at {next_reboot}")
            interface.localNode.reboot(secs=reboot_delay)
        except Exception as e:
            logger.error(f"Failed to execute scheduled reboot: {e}")


def get_my_node_id(interface):
    try:
        my_info = interface.getMyNodeInfo()
        return str(my_info.get('num', ''))
    except Exception as e:
        logger.error(f"Failed to get node info: {e}")
        return ''


def get_weather_alert_status():
    """
    Check if the weather alert monitor is functioning properly.
    Returns a status message indicating if the system is working or not.
    """
    try:
        # Build the API URL and parameters similar to weather_alert_monitor.py
        base_url = f"https://api.weather.gov/alerts/active"
        params = {
            "point": f"{settings.get('ALERT_LAT')},{settings.get('ALERT_LON')}"
        }
        headers = {
            "User-Agent": f"({settings.get('USER_AGENT_APP')}, {settings.get('USER_AGENT_EMAIL')})"
        }

        # Test the API connection
        response = requests.get(base_url, params=params, headers=headers)
        response.raise_for_status()

        # If we get here, the connection is working
        return "🟢 Alert System: Active and monitoring for weather alerts"

    except requests.exceptions.RequestException as e:
        logger.error(f"Weather Alert Monitor Status Check Failed: {str(e)}")
        return "🔴 Alert System: Unable to connect to weather service"
    except Exception as e:
        logger.error(f"Weather Alert Monitor Status Check Failed: {str(e)}")
        return "🔴 Alert System: Service interrupted - check logs"


if __name__ == "__main__":
    main()