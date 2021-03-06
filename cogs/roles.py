from datetime import datetime
from utils.checks import restricted

import discord
from discord.ext import commands
from discord.ext.commands import BucketType, Cooldown


class Roles:
    def __init__(self, bot):
        self.bot = bot
        self.rules_channel = 434836251766423564
        self.req_channel = 442045140261928960
        self.msg_id = 434842027692130304
        self.emoji_server_id = 417804713413836830

    async def cmdcheck(ctx):
        return ctx.author.id == 111158853839654912 or ctx.author.guild_permissions.manage_roles

    @commands.check(cmdcheck)
    @commands.command(hidden=True)
    async def addrole(self, ctx, role: discord.Role, emoji_name, url=None):
        """Adds a new role to the reaction role manager."""

        c = self.bot.get_channel(self.rules_channel)
        msg = await c.get_message(self.msg_id)

        if emoji_name in self.bot.reaction_manager:
            return await ctx.send("Role has already been added!")
        if len(msg.reactions) == 20:
            return await ctx.send("Cannot add role! Too many roles exist. [Reaction reached 20 Emoji]")

        if url is None:
            if len(ctx.message.attachments) > 0:
                url = ctx.message.attachments[0].url
        resp = await self.bot.session.get(url)
        img = await resp.read()

        try:
            guild = self.bot.get_guild(self.emoji_server_id)
            emoji = await guild.create_custom_emoji(name=emoji_name, image=img)
        except:  # noqa
            return await ctx.send("Could not create emoji!")

        await msg.add_reaction(emoji)
        self.bot.reaction_manager[emoji_name] = role.id

        query = """
            INSERT INTO reaction_roles (emoji_name, role_id) VALUES ($1, $2)
        """

        await self.bot.pool.execute(query, emoji_name, role.id)
        await ctx.send(f"Added `{emoji_name}` as an assignable role!")

    @restricted()
    @commands.group()
    async def request(self, ctx):
        """Request a special role.
        More info on each role is in the rules.
        """

    async def request_body(ctx):
        channel = ctx.guild.get_channel(ctx.bot.get_cog('Roles').req_channel)
        if channel is None:
            return

        role = discord.utils.get(ctx.guild.roles, name=ctx.command.name)
        if role.name not in ('Parasites', 'Verified'):
            return await ctx.send("You can't request that role, Darling!")

        if role in ctx.author.roles:
            return await ctx.send("You already have that role, Darling!")

        embed = discord.Embed(title="Role requested!", timestamp=datetime.now(), color=discord.Color.purple()) \
            .add_field(name='Role', value=role.name) \
            .add_field(name="Joined at", value=ctx.author.joined_at.strftime("%Y-%m-%d %H:%M")) \
            .add_field(name="Account Created", value=ctx.author.created_at.strftime("%Y-%m-%d %H:%M")) \
            .set_author(name=f"{ctx.author} / {ctx.author.id}", icon_url=ctx.author.avatar_url) \
            .set_footer(text=ctx.author.id)
        msg = await channel.send(embed=embed)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')
        await ctx.send("Request sent!")

    for r_name in ['Parasites', 'Verified']:
        request_body.__commands_cooldown__ = Cooldown(1, 86400, BucketType.user)
        request.command(r_name, aliases=[r_name.lower()])(request_body)

    async def handle_request(self, author, guild, msg_id, emoji):
        emojis = ('✅', '❌')

        perms = author.guild_permissions
        if not (perms.kick_members and perms.ban_members):
            if author.id != self.bot.owner_id:
                return

        channel = guild.get_channel(self.req_channel)
        if channel is None:
            return
        if emoji.name not in emojis:
            return

        msg = await channel.get_message(msg_id)
        if msg is None:
            return
        if sum(1 for r in msg.reactions if r.emoji in emojis and r.count > 1) == 0:
            return

        r_name = msg.embeds[0].fields[0].value
        role = discord.utils.get(guild.roles, name=r_name)
        embed = msg.embeds[0]
        requester = guild.get_member(int(embed.footer.text))
        if emoji.name == '✅':
            embed.color = discord.Color.green()
            await requester.add_roles(role)
            await msg.edit(embed=embed)
            try:
                await requester.send(f"Your request has been accepted! You now have `{role.name}`")
            except:  # give up if we cant send  # noqa
                pass
        elif emoji.name == '❌':
            embed.color = discord.Color.red()
            await msg.edit(embed=embed)
            try:
                await requester.send(f"Your request for `{role.name}` was denied. Please try again later.")
            except:  # rip  # noqa
                pass
        await msg.clear_reactions()

    async def on_raw_reaction_add(self, event):
        guild = self.bot.get_guild(event.guild_id)
        member = guild.get_member(event.user_id)
        await self.handle_request(member, guild, event.message_id, event.emoji)
        if event.message_id != self.msg_id:
            return

        role = guild.get_role(self.bot.reaction_manager[event.emoji.name])
        if role in member.roles:
            return

        await member.add_roles(role)

    async def on_raw_reaction_remove(self, event):
        guild = self.bot.get_guild(event.guild_id)
        member = guild.get_member(event.user_id)
        if event.message_id != self.msg_id:
            return

        role = guild.get_role(self.bot.reaction_manager[event.emoji.name])
        if role not in member.roles:
            return

        await member.remove_roles(role)


def setup(bot):
    bot.add_cog(Roles(bot))
