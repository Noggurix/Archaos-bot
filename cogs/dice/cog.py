from discord.ext import commands
import logging
from .groups import dice_group
from .commands import on_message

logger = logging.getLogger("dice.cog")

class RollDice(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

async def setup(bot: commands.Bot):
	await bot.add_cog(RollDice(bot))
	bot.add_listener(on_message)
 
	try:
		from . import commands as dice_commands
	except Exception:
		logger.exception("Falha ao importar dice.commands")

	try:
		bot.tree.add_command(dice_group)
	except Exception:
		pass
