import logging
import os
import ssl

import aiohttp
import aioredis
import asyncpg
import discord
from discord.ext import commands
from ruamel.yaml import YAML

startup_extensions = ["fun", "moderation", "admin", "franxx", "logger", "roles", "errors"]
extensions = ["cogs." + ext for ext in startup_extensions]
yaml = YAML()
try:
    with open("config.yaml") as f:
        config = yaml.load(f)
        token = config["token"]
        db = config["db"]
        redis = (config["redis_addr"], config["redis_pw"])
        img_auth = config["img_auth"]
        dev = True
except:  # noqa
    token = os.environ.get("TOKEN")
    db = os.environ.get("DATABASE_URL")
    redis = (os.environ.get("REDIS_ADDR"), os.environ.get("REDIS_PW"))
    img_auth = os.environ.get("WOLKE_TOKEN")
    dev = False

logging.basicConfig(level=logging.INFO)


async def get_prefix(bot, msg):
    return commands.when_mentioned_or("d>")(bot, msg) if dev else commands.when_mentioned_or(">", "02 ")(bot, msg)


class ZeroTwo(commands.Bot):
    def __init__(self):
        game = discord.Game(name="with my Darling~ <3")
        super().__init__(command_prefix=get_prefix,
                         description="Zero Two Bot for the Darling in the FranXX server",
                         activity=game)
        self.img_auth = "Wolke " + img_auth
        self.pool = None
        self.redis = None
        self.session = None

    async def close(self):
        print("Cleaning up...")
        await self.pool.close()
        await self.session.close()
        await super().close()

    async def on_ready(self):
        if self.pool is None:
            self.pool = await asyncpg.create_pool(db, ssl=ssl.SSLContext(), loop=self.loop)

        if self.redis is None:
            self.redis = await aioredis.create_redis_pool("redis://" + redis[0], password=redis[1], minsize=5, maxsize=10, loop=self.loop)

        if self.session is None:
            self.session = aiohttp.ClientSession()

        mute_query = """
            SELECT * FROM mute
        """
        role_query = """
            SELECT * FROM roles
        """
        config_query = """
            SELECT * FROM config
        """

        async with self.pool.acquire() as conn:
            self.muted_roles = {g: r for g, r in await conn.fetch(mute_query)}
            self.reaction_manager = {e: r for e, r in await conn.fetch(role_query)}
            self.config = {g: {'do_welcome': w, 'echo_mod_actions': m} for g, w, m in await conn.fetch(config_query)}
            self.muted_members = {}
            async for key in self.redis.iscan(match="member:*"):
                d = await self.redis.hgetall(key)
                d = {str(k): str(v) for k, v in d.items()}
                self.muted_members[int(key.replace("member:", ""))] = d

        print("Ready!")
        print(self.user.name)
        print(self.user.id)
        print("~-~-~-~")
        print("Cogs loaded:")
        for i, ext in enumerate(extensions):
            try:
                self.load_extension(ext)
                print(f"Loaded {startup_extensions[i]}.")
            except Exception as e:
                exc = f'{type(e).__name__}: {e}'
                print(f'Failed to load extension {ext}\n{exc}')
        print("~-~-~-~")

    async def on_message(self, message):  # allow case-insensitive commands
        ctx = await self.get_context(message)
        if ctx.author.bot:
            return
        if ctx.prefix is not None:
            ctx.command = self.all_commands.get(ctx.invoked_with.lower())
            await self.invoke(ctx)


ZeroTwo().run(token)
