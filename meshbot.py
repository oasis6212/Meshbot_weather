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
print(r"""
-----------------Welcome to Meshbot Weather------------------        
""")



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



def infer_nws_grid_from_coords(settings, logger=None):
    """
    Fill in NWS_OFFICE, NWS_GRID_X, NWS_GRID_Y using ALERT_LAT and ALERT_LON.
    Only runs if any NWS_* value is missing or empty. Updates settings in-place.
    Returns True if values were inferred and updated; otherwise False.
    """
    # If already complete, nothing to do
    have_office = bool(str(settings.get("NWS_OFFICE", "")).strip())
    have_x = bool(str(settings.get("NWS_GRID_X", "")).strip())
    have_y = bool(str(settings.get("NWS_GRID_Y", "")).strip())
    if have_office and have_x and have_y:
        office = str(settings.get("NWS_OFFICE", "")).strip()
        grid_x = str(settings.get("NWS_GRID_X", "")).strip()
        grid_y = str(settings.get("NWS_GRID_Y", "")).strip()
        msg = f"Using NWS grid from settings.yaml: office={office}, grid=({grid_x}, {grid_y})"
        logger_obj = globals().get("logger")
        if logger_obj:
            logger_obj.info(msg)
        else:
            print(msg)
        return False

    # Need lat/lon for inference
    lat_raw = settings.get("ALERT_LAT")
    lon_raw = settings.get("ALERT_LON")


    if not lat_raw or not lon_raw:
        if logger:
            logger.warning("Cannot determine NWS grid: ALERT_LAT/ALERT_LON not set.")
        return False

    # Prepare request
    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except (TypeError, ValueError):
        if logger:
            logger.warning("Cannot infer NWS grid: ALERT_LAT/ALERT_LON are not valid numbers.")
        return False

    lat_s = f"{lat:.4f}"
    lon_s = f"{lon:.4f}"
    url = f"https://api.weather.gov/points/{lat_s},{lon_s}"

    user_agent_app = str(settings.get("USER_AGENT_APP", "meshbot-weather"))
    user_agent_email = str(settings.get("USER_AGENT_EMAIL", "contact@example.com"))
    headers = {
        "Accept": "application/geo+json",
        "User-Agent": f"({user_agent_app}, {user_agent_email})",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        props = data.get("properties", {}) or {}
        office = props.get("gridId")
        grid_x = props.get("gridX")
        grid_y = props.get("gridY")

        if not office or grid_x is None or grid_y is None:
            if logger:
                logger.warning("NWS Points API did not return grid info; leaving NWS_* unchanged.")
            return False

        # Update as strings to match settings.yaml style
        settings["NWS_OFFICE"] = str(office)
        settings["NWS_GRID_X"] = str(grid_x)
        settings["NWS_GRID_Y"] = str(grid_y)

        if logger:
            logger.info(f"NWS grid auto-config: office={office}, x={grid_x}, y={grid_y}")
        return True

    except requests.RequestException as e:
        if logger:
            logger.warning(f"Failed to fetch NWS grid from Points API: {e}")
        return False


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

ALERT_LAT = settings.get("ALERT_LAT")
ALERT_LON = settings.get("ALERT_LON")


logger.info(f"ALERT_LAT:{ALERT_LAT} ALERT_LON:{ALERT_LON}")


infer_nws_grid_from_coords(settings, logger=logger if 'logger' in globals() else None)

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



#logger.info(f"DUTYCYCLE: {DUTYCYCLE}")
#logger.info(f"DM_MODE: {DM_MODE}")
#logger.info(f"FIREWALL: {FIREWALL}")
#logger.info(f"MYNODES: {MYNODES}")



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


def split_message(message, max_length=200, message_type="Hourly", start_index=1, total_count=None):
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
    # If total_count is provided, use it for page count
    if total_count is None:
        total_count = len(messages)
    for i in range(len(messages)):
        messages[i] = f"--({start_index + i}/{total_count}) {message_type}\n" + messages[i]
    return messages


def get_forecast_4day():
    global forecast_4day_info
    forecast_4day_info = forecast_4day.get_weekly_emoji_weather()
    return "\n".join(forecast_4day_info)


def get_wind_24hour():
    global wind_24hour_info
    wind_24hour_info = wind_24hour.get_wind_24hour()
    return wind_24hour_info


def get_custom_lookup(message):
    """
    Parse message like 'loc lat/lon command' and return the weather info for that location.
    Uses api.weather.gov /points/{lat},{lon} to get grid/office.
    Supported commands: 2day, 4day, 5day, 7day, hourly, temp, rain, wind
    """
    import re
    import requests
    match = re.match(r"loc\s+([+-]?\d+\.\d+)/([+-]?\d+\.\d+)\s*(\w+)?", message)
    if not match:
        return "Invalid location format. Use 'loc lat/lon [command]'."
    lat, lon, command = match.groups()
    # Get NWS grid info
    try:
        url = f"https://api.weather.gov/points/{lat},{lon}"
        resp = requests.get(url, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        data = resp.json()
        office = data['properties']['cwa']
        grid_x = str(data['properties']['gridX'])
        grid_y = str(data['properties']['gridY'])
    except Exception as e:
        return f"Entered grid is invalid or not found for {lat},{lon}: Not part of NWS coverage area."
    # Create a temporary weather manager for this location
    temp_manager = WeatherDataManager(office, grid_x, grid_y, USER_AGENT)
    # Map commands to fetchers
    fetchers = {
        '2day': lambda: Forecast2DayFetcher(temp_manager).get_daily_weather(),
        '4day': lambda: Forecast4DayFetcher(temp_manager).get_weekly_emoji_weather(),
        '5day': lambda: NWSWeatherFetcher5Day(temp_manager).get_daily_weather(),
        '7day': lambda: Forecast7DayFetcher(temp_manager).get_weekly_emoji_weather(),
        'hourly': lambda: EmojiWeatherFetcher(temp_manager).get_emoji_weather(),
        'temp': lambda: Temperature24HourFetcher(temp_manager).get_temperature_24hour(),
        'rain': lambda: RainChanceFetcher(temp_manager).get_rain_chance(),
        'wind': lambda: Wind24HourFetcher(temp_manager).get_wind_24hour(),
    }
    if command and command in fetchers:
        result = fetchers[command]()
        if isinstance(result, list):
            return '\n'.join(result)
        return str(result)
    else:
        return f"Custom location lookup: lat={lat}, lon={lon}, office={office}, grid=({grid_x},{grid_y})\nSupported commands: {', '.join(fetchers.keys())}"


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
                    # Send the temperature message directly without split_message
                    interface.sendText(" ACK", wantAck=True, destinationId=sender_id)
                elif "?" in message or "menu" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    menu_text_1 = "    --Multi-Message--\n" \
                                  "hourly - 24h outlook\n" \
                                  "7day - 7 day simple\n" \
                                  "5day - 5 day detailed\n" \
                                  "wind - 24h wind\n"
                    menu_text_2 = "    --Single Message--\n" \
                                  "2day - 2 day detailed\n" \
                                  "4day - 4 day simple\n" \
                                  "rain - 24h precipitation\n" \
                                  "temp - 24h temperature\n"
                    # Add alert command if enabled
                    if settings.get("ENABLE_ALERT_COMMAND", True) and settings.get(
                            "SHOW_ALERT_COMMAND_IN_MENU", True):
                        menu_text_2 += "alert - show active alerts\n"
                    if settings.get('SHOW_CUSTOM_LOOKUP_COMMAND_IN_MENU', True):
                        menu_text_2 += "loc lat/lon - custom location lookup\n"
                    #check if both show_alert and loc command are disabled
                    if not settings.get('SHOW_ALERT_COMMAND_IN_MENU', True) and not settings.get(
                                'SHOW_CUSTOM_LOOKUP_COMMAND_IN_MENU',
                                                                                                False):
                        combined_menu = f"{menu_text_1}\n{menu_text_2}".strip()
                        # If both commands are disabled send menu without using split_message
                        interface.sendText(combined_menu,wantAck=True, destinationId=sender_id)
                        return

                    if settings.get('FULL_MENU', True):
                        combined_menu = menu_text_1 + "\n" + menu_text_2
                        messages = split_message(combined_menu, message_type="Menu")
                        send_message_sequence(messages, message_type="Menu")
                    else:
                        simple_menu = "  --Weather Commands--\n" \
                            "2day - 2 day forecast\n" \
                            "4day - 4 day forecast\n" \
                            "temp - 24h temperature\n" \
                            "rain - 24h precipitation"
                        if settings.get('ENABLE_ALERT_COMMAND', True):
                            simple_menu += "\nalert - show active alerts"
                        if settings.get('ENABLE_CUSTOM_LOOKUP', False):
                            simple_menu += "\nloc lat/lon - custom location lookup"
                        messages = split_message(simple_menu, message_type="Menu")
                        send_message_sequence(messages, message_type="Menu")
                elif "loc" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    custom_lookup_result = get_custom_lookup(message)
                    messages = split_message(str(custom_lookup_result), message_type="Custom")
                    send_message_sequence(messages, message_type="Custom")
                elif "temp" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    # Send the temperature message directly without split_message
                    interface.sendText(get_temperature_24hour(), wantAck=True, destinationId=sender_id)

                elif "2day" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    # Send the 2-day forecast directly without split_message
                    interface.sendText(get_forecast_2day(), wantAck=True, destinationId=sender_id)

                elif "hourly" in message:
                    if settings.get('ENABLE_HOURLY_WEATHER', True):
                        transmission_count += 1
                        weather_data = get_emoji_weather()
                        messages = split_message(weather_data, message_type="Hourly")
                        send_message_sequence(messages, message_type="Hourly")
                    else:
                        time.sleep(first_message_delay)
                        messages = split_message("Hourly weather module is disabled.", message_type="Hourly")
                        send_message_sequence(messages, message_type="Hourly")
                elif "rain" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    # Send the rain message directly without split_message
                    interface.sendText(get_rain_chance(), wantAck=True, destinationId=sender_id)

                elif "5day" in message:
                    if settings.get('ENABLE_5DAY_FORECAST', True):
                        transmission_count += 1
                        weather_messages = nws_weather_fetcher_5day.get_daily_weather()
                        messages = split_message('\n'.join(weather_messages), message_type="5day")
                        send_message_sequence(messages, message_type="5day")
                    else:
                        time.sleep(first_message_delay)
                        messages = split_message("5-day forecast module is disabled.", message_type="5day")
                        send_message_sequence(messages, message_type="5day")
                elif "4day" in message:
                    transmission_count += 1
                    time.sleep(first_message_delay)
                    # Send the 4-day forecast directly without split_message
                    interface.sendText(get_forecast_4day(), wantAck=True, destinationId=sender_id)

                elif "wind" in message:
                    transmission_count += 1
                    weather_data = wind_24hour.get_wind_24hour()
                    if isinstance(weather_data, list):
                        weather_text = '\n'.join(weather_data)
                        messages = split_message(weather_text, message_type="Wind")
                        send_message_sequence(messages, message_type="Wind")
                    else:


                        time.sleep(first_message_delay)
                        messages = split_message(weather_data, message_type="Wind")
                        send_message_sequence(messages, message_type="Wind")
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
                        send_message_sequence(messages, message_type="7day")
                    else:
                        time.sleep(first_message_delay)
                        messages = split_message("7-day forecast module is disabled.", message_type="7day")
                        send_message_sequence(messages, message_type="7day")
                elif "alert-status" in message:
                    transmission_count += 1
                    interface.sendText(get_weather_alert_status(), wantAck=True, destinationId=sender_id)
                elif "alert" in message:
                    transmission_count += 1
                    if alerts:
                        if not alerts.broadcast_full_alert(sender_id):
                            time.sleep(first_message_delay)
                            if not settings.get('ENABLE_ALERT_COMMAND', True):
                                messages = split_message(
                                    "The full-alert command is disabled in settings.", message_type="Alert"
                                )
                                send_message_sequence(messages, message_type="Alert")
                            else:
                                messages = split_message(
                                    "No active alerts at this time.", message_type="Alert"
                                )
                                send_message_sequence(messages, message_type="Alert")
                else:
                    # If it's a DM but doesn't match any command, send a random help message
                    if is_direct_message:
                        transmission_count += 1
                        interface.sendText(
                            random.choice(UNRECOGNIZED_MESSAGES),
                            wantAck=True,
                            destinationId=sender_id
                        )
    except KeyError as e:
        node_name = interface.getMyNodeInfo().get('user', {}).get('longName', 'Unknown')
        logger.error(f'Attached node "{node_name}" was unable to decode incoming message, possible key mismatch in its node-database.')
        return
    except Exception as e:
        logger.error(f"Unexpected error in message_listener: {e}")
        return

def signal_handler(sig, frame):
    """Perform a graceful shutdown when CTRL+C is pressed"""
    global interface
    logger.info("\nClosing program. Please wait...")
    try:
        if interface is not None:
            if settings.get('SHUTDOWN_NODE_ON_EXIT', False):
                logger.info("Sending shutdown command to node...")
                try:
                    # Send shutdown command
                    interface.localNode.shutdown()
                    # Give the node sufficient time to complete its shutdown process
                    logger.info("Waiting for node to complete shutdown...")
                    time.sleep(17)  # Time delay for node to finish shutting down
                except Exception as e:
                    logger.error(f"Error sending shutdown command: {e}")

            else:
                logger.info("Node shutdown disabled in settings, skipping sending power off command.")

            logger.info("Closing Meshtastic interface...")
            interface.close()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Error sending shutdown command: {e}")
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

    logger.info(f"Press CTRL-C to close the program")

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