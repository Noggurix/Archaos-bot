import random
import discord
from discord import app_commands
from discord.ext import commands

class StatRoll(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

	def _generate_stat_embed(self, author: discord.abc.Snowflake):
		details = []
		totals = []

		for i in range(6):
			dice = [random.randint(1, 6) for _ in range(4)]
			sorted_dice = sorted(dice)
			dropped = sorted_dice[0]
			kept = sorted_dice[1:]
			total = sum(kept)

			details.append(
				f"`[{total}]` ⟵ ({', '.join(str(d) for d in dice)}) → drop {dropped}"
			)
			totals.append(total)

		results_str = " ".join(f"**`[{t}]`**" for t in totals)
		description = "\n".join(details) + f"\n\n**↪** {results_str}"

		embed = discord.Embed(
			title=f"{getattr(author, 'display_name', str(author))}'s Stat Rolls:",
			description=description,
			color=discord.Color.blue()
		)

		return embed, totals

	async def _create_reroll_view(self):
		view = discord.ui.View()

		button = discord.ui.Button(emoji="🔁", style=discord.ButtonStyle.primary)

		async def callback(interaction: discord.Interaction):
			await interaction.response.defer()

			new_embed, _ = self._generate_stat_embed(interaction.user)

			new_view = await self._create_reroll_view()
			await interaction.followup.send(embed=new_embed, view=new_view)

		button.callback = callback
		view.add_item(button)
		return view

	@app_commands.command(name="statroll", description="Rola 4d6 drop lowest, 6 vezes para D&D")
	async def stat_roll(self, interaction: discord.Interaction):
		embed, _ = self._generate_stat_embed(interaction.user)

		view = await self._create_reroll_view()

		await interaction.response.send_message(
			embed=embed,
			view=view,
			allowed_mentions=discord.AllowedMentions(users=True)
		)

async def setup(bot: commands.Bot):
	await bot.add_cog(StatRoll(bot))
