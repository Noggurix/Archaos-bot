import re
import discord
from discord import app_commands
from .groups import dice_group
from .utils.dice_utils import gerar_embed, create_roll_button, interpretar_rolagem

VALIDA_REGEX = re.compile(
	r"^\s*\d*#?d\d+(?:\s*[+\-*/]\s*(?:\d*#?d\d+|\d+))*\s*$",
	re.IGNORECASE
)

@dice_group.command(name="rolar", description="Role dados.")
@app_commands.describe(entrada="Expressões como 3d20+3#d20+5, 1d20*6, 2d10/3")
async def rolar_dados_slash(interaction: discord.Interaction, entrada: str):
	if entrada.lower().startswith("d"):
		entrada = "1" + entrada

	entrada = re.sub(r'\s+', '', entrada)

	if VALIDA_REGEX.match(entrada) and entrada.count('#') <= 1:
		resultados, mensagem, total_geral, qtd_grupos = await interpretar_rolagem(entrada)
		if not resultados:
			await interaction.response.send_message(mensagem, ephemeral=True)
			return

		embed = await gerar_embed(entrada, resultados, mensagem, total_geral, interaction.user, qtd_grupos)
		view = await create_roll_button(entrada)
		await interaction.response.send_message(embed=embed, view=view, allowed_mentions=discord.AllowedMentions(users=True))
	else:
		await interaction.response.send_message(
			"Formato inválido.\nExemplos válidos:\n"
			"`3d20`, `1d20+5`, `2d10*3`, `4d6/2`, `3#d20`, `2d8-5+1d6*4`",
			ephemeral=True
		)

async def on_message(message: discord.Message):
	if message.author.bot:
		return

	content = message.content
	if content.lower().startswith("d") and content[1:].lstrip()[0].isdigit():
		content = "1" + content

	content = re.sub(r'\s+', '', content)

	if VALIDA_REGEX.match(content) and content.count('#') <= 1:
		resultados, mensagem, total_geral, qtd_grupos = await interpretar_rolagem(content)
		if resultados:
			embed = await gerar_embed(content, resultados, mensagem, total_geral, message.author, qtd_grupos)
			view = await create_roll_button(content)
			await message.reply(embed=embed, view=view, mention_author=True)
