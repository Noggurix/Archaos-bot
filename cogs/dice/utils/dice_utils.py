import random
import re
import discord

def rolar_dados(qtd: int, lados: int):
	return [random.randint(1, lados) for _ in range(qtd)]

async def interpretar_rolagem(entrada: str):
	MAX_DICE = 10000
	MAX_SIDES = 999999999999999
	MAX_EXPLOSIVE = 500

	pattern = re.compile(
		r"^(\d+)(#?d(\d+))((?:[+\-*/](?:[1-9]\d*)?d[1-9]\d*|[+\-*/]\d+)*)$",
		re.IGNORECASE
	)
	grupos = re.findall(pattern, entrada)

	if not grupos or entrada.count('#') >= 2:
		return None, "Formato inválido. Exemplos válidos: 3d20, 3d20+5, 3#d20, 3#d20+3d20+5, 1d20*6, 2d10/3."

	resultados = []
	total_geral = 0

	for grupo in grupos:
		qtd_grupos = int(grupo[0])
		tipo_dado = grupo[1]
		lados_dado = int(grupo[2])
		modificadores_raw = grupo[3]

		modificador_pattern = re.compile(r"([+\-*/])((?:[1-9]\d*)?d[1-9]\d*|\d+)")
		modificadores = re.findall(modificador_pattern, modificadores_raw)

		if '#' not in tipo_dado and qtd_grupos > MAX_DICE:
			return None, f"Quantidade de dados muito alta ({qtd_grupos}). Limite permitido: {MAX_DICE}."

		if lados_dado > MAX_SIDES:
			return None, f"O dado d{lados_dado} tem lados demais. Limite permitido: d{MAX_SIDES}."

		if '#' in tipo_dado and qtd_grupos > MAX_EXPLOSIVE:
			return None, f"Quantidade de explosões muito alta ({qtd_grupos}). Limite: {MAX_EXPLOSIVE}."

		iteracoes = qtd_grupos if '#' in tipo_dado else 1
		for _ in range(iteracoes):
				rolagens = rolar_dados(1 if '#' in tipo_dado else qtd_grupos, lados_dado)
				soma_dados = sum(rolagens)
				total = soma_dados
				extras = []

				for operador, elemento in modificadores:
					if "d" in elemento.lower():
						parts = elemento.lower().split("d")
						qtd = int(parts[0]) if parts[0] else 1
						lados = int(parts[1])
						rolagens_extras = rolar_dados(qtd, lados)
						soma_extras = sum(rolagens_extras)

						if operador == "+":
							total += soma_extras
						elif operador == "-":
							total -= soma_extras
						elif operador == "*":
							total *= soma_extras
						elif operador == "/":
							total = total // soma_extras if soma_extras != 0 else 0

						extras.append(
							f"\\{operador} ({', '.join([f'**{r}**' if r == 20 and lados == 20 else str(r) for r in rolagens_extras])}) {qtd}d{lados}"
						)
					else:
						valor = int(elemento)
						if operador == "+":
							total += valor
						elif operador == "-":
							total -= valor
						elif operador == "*":
							total *= valor
						elif operador == "/":
							total = total // valor if valor != 0 else 0
						extras.append(f"{operador}{valor}")

				total_geral += total
				extras_str = " ".join(extras) if extras else ""
				resultados.append((rolagens, soma_dados, total, lados_dado, extras_str))

		if '#' in tipo_dado:
				if qtd_grupos < 100:
					mensagem = "\n".join(
						f"`[{total}]` ⟵ ({', '.join([f'**{r}**' if r == lados_dado or r == 1 else str(r) for r in rolagens])}) d{lados_dado} {extras_str}"
						for rolagens, _, total, _, extras_str in resultados
					)
				else:
					mensagem = "\n**Definitely a Dice Roll!**"
		else:
				if qtd_grupos < 580:
					mensagem = "\n".join(
						f"`[{total}]` ⟵ ({', '.join([f'**{r}**' if r == lados_dado or r == 1 else str(r) for r in rolagens])}) {qtd_grupos}d{lados_dado} {extras_str}"
						for rolagens, _, total, _, extras_str in resultados
					)
				else:
					mensagem = "\n**Definitely a Dice Roll!**"

	return resultados, mensagem, total_geral, qtd_grupos

async def gerar_embed(entrada: str, resultados, mensagem, total_geral, autor: discord.Member | discord.User, qtd_grupos):
	embed = discord.Embed(
		title=f"{autor.display_name}'s {entrada}:",
		description=mensagem,
		color=discord.Color.blue(),
	)
	embed.set_thumbnail(url="https://i0.wp.com/pawleystudios.com/wp-content/uploads/2020/07/d20-dice-01.png?fit=510%2C510&ssl=1")

	if len(resultados) > 1 or qtd_grupos >= 580:
		embed.add_field(name="", value=f"**↪**  `[{total_geral}]`", inline=False)

	return embed

async def create_roll_button(entrada: str):
	button = discord.ui.Button(label="🎲 Re-roll", style=discord.ButtonStyle.primary)

	async def callback(interaction: discord.Interaction):
		await interaction.response.defer()

		new_result = await interpretar_rolagem(entrada)
		if not new_result[0]:
			await interaction.followup.send(new_result[1], ephemeral=True)
			return
		new_embed = await gerar_embed(
			entrada,
			new_result[0],
			new_result[1],
			new_result[2],
			interaction.user,
			new_result[3]
		)
		view = await create_roll_button(entrada)
		await interaction.followup.send(embed=new_embed, view=view)

	button.callback = callback
	view = discord.ui.View()
	view.add_item(button)
	return view
