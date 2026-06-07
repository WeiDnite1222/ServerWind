import logging
import sys
import threading
import time
import os
import discord
import dotenv
from discord.ext import commands
from helper import CloudflareHelper

class DiscordServer(threading.Thread):
    def __init__(self, daemon=False, **kwargs):
        threading.Thread.__init__(self, daemon=daemon, **kwargs)
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.client = discord.Client(intents=self.intents)
        self.token = os.getenv("DISCORD_TOKEN")

        self.bot = commands.Bot(command_prefix="!", intents=self.intents)

        self.commands = {}

        @self.client.event
        async def on_ready():
            print(f'Logged in as {self.client.user}')

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return

            if message.content.startswith('/test'):
                await message.channel.send(f'Hello, {message.author.name}!')

            if message.content.startswith('/echo'):
                msg = message.content[len('/echo'):]
                await message.channel.send(msg)

            if message.content.startswith('/where'):
                if hasattr(message, 'guild'):
                    await message.channel.send(f'You are in server {message.guild.name}')
                else:
                    await message.channel.send(f'You are in private chat.')

            if message.content.startswith('/help'):
                msg = "Commands:\n"
                for command in self.commands:
                    msg += f'- {command}: {self.commands[command].get('help') if self.commands[command].get('help') else "A command"}\n'

                await message.channel.send(
                    msg
                )

            for command in self.commands:
                if message.content.startswith(command):
                    await self.commands[command].get("func")(self.client, message)

    def handle_command(self, command_prefix, help=None):
        def decorator(func):
            self.commands[command_prefix] = {
                "func": func,
                "help": help
            }

            def inner(*args, **kwargs):
                return func(*args, **kwargs)

            return inner

        return decorator

    def run(self):
        if self.token is None:
            raise Exception('Discord bot token is required. Place it (DISCORD_TOKEN) in .env file.')

        self.client.run(self.token)

        while True:
            time.sleep(1)


class App:
    def __init__(self):
        self.logger = logging.getLogger('ServerWind.Main')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s][%(name)s]: %(message)s')
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(formatter)
        self.logger.addHandler(sh)

        self.dc_server = DiscordServer(daemon=True)
        self.cf_helper = CloudflareHelper(self.dc_server)

    def main(self):
        self.logger.info("WorkDir: {}".format(os.getcwd()))
        try:
            while self.dc_server.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.warning('User interrupted.')
        finally:
            self.logger.info("Server stopped.")

    def on_startup(self):
        self.logger.info("SeverHelper starting...")

        self.logger.info("Starting Discord server...")
        self.dc_server.start()

        self.logger.info("Starting CF helper...")
        self.cf_helper.start()

        self.logger.info("Registering command handlers...")
        @self.dc_server.handle_command("/userinfo")
        async def userinfo(client, message):
            await message.channel.send("unfinished")

        @self.dc_server.handle_command("/info")
        async def info(client, message):
            await message.channel.send(f"My name is {client.user.name}\n")

    def on_shutdown(self):
        pass

    def run(self):
        self.on_startup()
        self.main()
        self.on_shutdown()


if __name__ == '__main__':
    try:
        dotenv.load_dotenv()
    except Exception:
        raise Exception('Failed to load .env file. Create it before running.')

    app = App()
    app.run()
