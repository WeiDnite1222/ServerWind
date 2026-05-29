import asyncio
import logging
import os
import sys
import threading
import time
import requests
from utils.yaml import yaml_parser, yaml_writer
from settings import CONFIG_DIR

CF_ZONE_ENDPOINT = "https://api.cloudflare.com/client/v4/zones"


class Helper(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self, daemon=True)

    def on_startup(self):
        pass

    def on_shutdown(self):
        pass


cf_config = {
    "zone": None,
    "domains": [],
    "doUpdate": False,
    "doIPCheckInterval": 600,
    "cfSecret": None,
    "allowedBroadcastServer": [
    ],
    "ddnsBroadcastCode": "code-here",
    "maintenancePageURL": ""
}


class CloudflareHelper(Helper):
    def __init__(self, dc):
        Helper.__init__(self)
        self.dc = dc
        self.cfg_path = str(CONFIG_DIR / "cf.yaml")
        self.logger = logging.getLogger("CFHelper")
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s][%(name)s]: %(message)s')
        dc_formatter = logging.Formatter('[%(name)s]: %(message)s')
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        dc_sh = logging.StreamHandler(self.DCStream(self))
        dc_sh.setFormatter(dc_formatter)
        self.logger.addHandler(dc_sh)
        self.logger.addHandler(sh)

        self.init = False
        self.ip = None

        # maintenance mode
        self.is_maintenance = False

        self.config = cf_config
        self.allowed_broadcast_channels = {}

        @self.dc.handle_command("/cf:update_ddns", help="Update cloudflare DNS")
        async def renew(client, message):
            guild = getattr(message, "guild", None)
            if guild is None:
                await message.channel.send("This command can only be used in server channels.")
                return

            if self.is_allowed_broadcast_server(guild.name):
                self.update_ddns()
                await message.channel.send(f"Updating DDNS...")
            else:
                await message.channel.send(f"Unsupported server: {guild.name}")

        @self.dc.handle_command("/cf:add_channel", help="Add channel to the cf operator list")
        async def add_channel(client, message):
            guild = getattr(message, "guild", None)
            if guild is None:
                await message.channel.send("This command can only be used in server channels.")
                return

            raw = message.content[len("/cf:add_channel"):].strip()
            if raw == "":
                await message.channel.send("Usage: /cf:add_channel SECRET_CODE")
                return

            ok, result = self.add_broadcast_channel(
                server_name=guild.name,
                channel_id=message.channel.id,
                input_code=raw
            )
            await message.channel.send(result)

        @self.dc.handle_command("/cf:maintenance", help="Toggle maintenance mode")
        async def enable_maintenance(client, message):
            guild = getattr(message, "guild", None)
            if guild is None:
                await message.channel.send("This command can only be used in server channels.")
                return

            if self.is_allowed_broadcast_server(guild.name):
                if not self.is_maintenance:
                    self.is_maintenance = True
                    self.update_ddns()
                    await message.channel.send(f"Maintenance mode is enabled. Updating DDNS...")
                else:
                    self.is_maintenance = False
                    self.update_ddns()
                    await message.channel.send(f"Maintenance mode is disabled. Updating DDNS...")
            else:
                await message.channel.send(f"Unsupported server: {guild.name}")

        @self.dc.handle_command("/cf:status-maintenance", help="Check status of maintenance mode")
        async def check_maintenance(client, message):
            guild = getattr(message, "guild", None)
            if guild is None:
                await message.channel.send("This command can only be used in server channels.")
                return

            if self.is_allowed_broadcast_server(guild.name):
                await message.channel.send("Maintenance mode is on" if self.is_maintenance else "Maintenance mode is off")
            else:
                await message.channel.send(f"Unsupported server: {guild.name}")

    class DCStream:
        def __init__(self, helper):
            self.helper = helper

        def write(self, data):
            content = str(data).strip()

            if not content:
                return

            for server_name, channels in self.helper.allowed_broadcast_channels.items():
                for ch_id in channels:
                    channel = self.helper.dc.client.get_channel(ch_id)

                    if channel is None:
                        continue

                    guild = getattr(channel, "guild", None)
                    if guild is None or guild.name != server_name:
                        continue

                    asyncio.run_coroutine_threadsafe(channel.send(content), self.helper.dc.client.loop)

        def flush(self):
            pass

    def run(self):
        self.on_startup()
        while True:
            result = self.detect_ip_change()

            if result:
                self.update_ddns()

            time.sleep(self.config.get("doIPCheckInterval", cf_config["doIPCheckInterval"]))

    def detect_ip_change(self):
        if not self.init:
            self.ip = self.what_is_my_ip()
            self.init = True
            return False

        ip = self.what_is_my_ip()

        if self.ip is None:
            self.logger.warning("Unable to get IP. Is the internet connected?")
            return False

        if self.ip != ip:
            self.logger.info("IP change detected!")
            self.ip = ip
            return True

        return False

    def what_is_my_ip(self):
        try:
            response = requests.get('https://api.ipify.org', timeout=5)
            public_ip = response.text
            return public_ip
        except requests.exceptions.RequestException as e:
            self.logger.error("An error occurred while getting ip: {}".format(e))
            return None

    def update_ddns(self):
        domains = self.config.get('domains', [])

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.get('cfSecret')}",
        }

        try:
            r = requests.get(CF_ZONE_ENDPOINT, headers=headers, params={
                "name": self.config.get('zone', None),
            })

            if r.status_code == 200:
                data = r.json()
            else:
                self.logger.error("Unable to get DDNS data. Status code: {}".format(r.status_code))
                return

        except requests.exceptions.RequestException as e:
            self.logger.error("An error occurred while getting CF zone: {}".format(e))
            return

        try:
            zone_id = data.get("result", {})[0].get("id", None)
        except Exception as e:
            if type(e) == requests.exceptions.RequestException:
                self.logger.error("An error occurred while getting CF zone id: {}".format(e))
            elif type(e) == IndexError:
                self.logger.error("Unable to get zone id. Is the zone name correct?")
            return

        try:
            r = requests.get(f"{CF_ZONE_ENDPOINT}/{zone_id}/dns_records", headers=headers, timeout=5)

            if r.status_code == 200:
                dns_records = r.json().get("result", {})
            else:
                self.logger.error("Unable to get dns records. Status code: {}".format(r.status_code))
                return
        except requests.exceptions.RequestException as e:
            self.logger.error("An error occurred while getting DNS records: {}".format(e))
            return

        maintenance_url = self.config.get('maintenancePageURL')
        start_maintenance = False

        if self.is_maintenance and maintenance_url is not None:
            self.logger.info("Maintenance mode is on. Redirecting support dns records to maintenance page...")
            start_maintenance = True
        elif self.is_maintenance and not maintenance_url:
            self.logger.warning("Maintenance mode is on but maintenancePageURL is not set yet. Ignoring...")

        for item in domains:
            domain = item.get("name", None)
            proxied = item.get("proxied", False)
            domain_type = item.get("type", "A")
            allow_maintenance = item.get("allowMaintenance", False)

            if domain is None:
                continue

            record_id = None

            for record in dns_records:
                name = record.get("name", None)
                # record_type = record.get("type", None)

                # if name == domain and record_type == domain_type:
                #     record_id = record.get("id", None)

                if name == domain:
                    record_id = record.get("id", None)

            if record_id is None:
                self.logger.warning(
                    f"The domain {domain} ({domain_type}) does not in CF zone {self.config.get('zone', None)}")
                continue

            request_data = {
                "type": domain_type if not start_maintenance or not allow_maintenance else "CNAME",
                "name": domain,
                "content": self.ip if not start_maintenance or not allow_maintenance else maintenance_url,
                "ttl": 120,
                "proxied": proxied
            }

            try:
                r = requests.put(f"{CF_ZONE_ENDPOINT}/{zone_id}/dns_records/{record_id}",
                                 json=request_data,
                                 headers=headers, timeout=5)

                if r.status_code == 200:
                    self.logger.info("Successfully updated DNS record for: {} > {}".format(domain, self.ip))
                else:
                    try:
                        error_detail = r.json()
                    except ValueError:
                        error_detail = r.text
                    self.logger.error(
                        "Unable to update DNS record for domain name {}, HTTP Code: {}, response: {}".format(
                            domain, r.status_code, error_detail))
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Unable to update dns record for domain name {domain}: {e}")
                continue

    def parse_allowed_broadcast_channels(self):
        raw = self.config.get("allowedBroadcastServer", [])
        allowed = {}

        if type(raw) is not list:
            self.logger.warning("allowedBroadcastServer is not list, skip channel broadcast.")
            return allowed

        for server_entry in raw:
            if type(server_entry) is not dict:
                continue

            for server_name, server_cfg in server_entry.items():
                if type(server_cfg) is not dict:
                    continue

                channels = server_cfg.get("channels", [])
                if type(channels) is not list:
                    continue

                parsed_channels = set()
                for channel_id in channels:
                    try:
                        parsed_channels.add(int(channel_id))
                    except (TypeError, ValueError):
                        self.logger.warning(f"Invalid channel id in {server_name}: {channel_id}")

                if len(parsed_channels) > 0:
                    allowed[server_name] = parsed_channels

        return allowed

    def is_allowed_broadcast_server(self, server_name):
        return server_name in self.allowed_broadcast_channels

    def get_broadcast_code(self):
        for key in ("broadcastCode", "ddnsBroadcastCode", "code"):
            value = self.config.get(key, None)
            if value is not None:
                return str(value).strip()
        return None

    def serialize_allowed_broadcast_channels(self):
        result = []
        for server_name, channels in self.allowed_broadcast_channels.items():
            result.append({
                server_name: {
                    "channels": [str(ch_id) for ch_id in sorted(channels)]
                }
            })
        return result

    def save_config(self):
        yaml_writer(self.cfg_path, self.config)

    def add_broadcast_channel(self, server_name, channel_id, input_code):
        expected_code = self.get_broadcast_code()

        if expected_code is None or expected_code == "":
            return False, "Broadcast code is not configured in cf.yaml."

        if str(input_code).strip() != expected_code:
            return False, "Invalid code."

        if server_name not in self.allowed_broadcast_channels:
            self.allowed_broadcast_channels[server_name] = set()

        if channel_id in self.allowed_broadcast_channels[server_name]:
            return True, "This channel is already in DDNS broadcast list."

        self.allowed_broadcast_channels[server_name].add(channel_id)
        self.config["allowedBroadcastServer"] = self.serialize_allowed_broadcast_channels()

        try:
            self.save_config()
        except Exception as e:
            self.logger.error(f"Unable to save cf.yaml: {e}")
            return False, "Failed to save configuration."

        return True, "Added current channel to DDNS broadcast list."

    def on_startup(self):
        self.logger.info("Starting...")

        if not os.path.exists(self.cfg_path):
            try:
                yaml_writer(self.cfg_path, cf_config)
            except Exception as e:
                self.logger.error("Unable to create configuration file: {}".format(e))
        else:
            try:
                data = yaml_parser(self.cfg_path)
                if type(data) is not dict:
                    self.logger.warning("The configuration file type is incorrect. Expect dict, got str.")
                else:
                    self.config = data
            except Exception as e:
                self.logger.error("Unable to parse configuration file: {}".format(e))

        self.allowed_broadcast_channels = self.parse_allowed_broadcast_channels()
