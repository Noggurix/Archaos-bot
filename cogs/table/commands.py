import asyncio
import discord
from discord import app_commands
from discord import utils
from .groups import mesa_group
from zoneinfo import ZoneInfo
from datetime import timezone
import logging

logger = logging.getLogger("commands.cog")

def table_name_parts(table_number: int):
	base = f"Mesa {table_number}"
	return (
		f"{base} Mestre",
		f"{base} Jogador",
		base
	)

def get_roles_and_category(guild, table_number: int, utils_module=utils):
	master_name, player_name, category_name = table_name_parts(table_number)

	master_role = utils_module.get(guild.roles, name=master_name)
	player_role = utils_module.get(guild.roles, name=player_name)
	category = utils_module.get(guild.categories, name=category_name)

	return master_role, player_role, category

@mesa_group.command(name="criar", description="Inicia a criação/reserva de uma nova mesa")
async def mesa_criar(interaction: discord.Interaction):
	cog = interaction.client.get_cog("TableCog")
	if cog is None:
		return await interaction.response.send_message("Cog de mesas não registrado.", ephemeral=True)
	await cog.start_reservation(interaction)

@mesa_group.command(name="deletar", description="Deleta a mesa (categoria + canais + papéis).")
@app_commands.rename(table_number="numero_da_mesa")
@app_commands.describe(table_number="Número da mesa a deletar (ex: 3)")
async def mesa_deletar(interaction: discord.Interaction, table_number: int):
	guild = interaction.guild
	if not guild:
		return await interaction.response.send_message("Este comando só funciona em servidores.", ephemeral=True)
 
	master_role, player_role, category = get_roles_and_category(guild, table_number)
 
	if not (master_role or player_role or category):
		return await interaction.response.send_message(
			f"❌ Não encontrei nada referente à Mesa {table_number}. Verifique se o número está correto.",
			ephemeral=True
		)

	me = interaction.user
	if not ( (master_role and master_role in getattr(me, "roles", [])) or interaction.user.guild_permissions.manage_guild ):
		return await interaction.response.send_message("Você não tem permissão para deletar esta mesa (só o mestre ou admin).", ephemeral=True)

	confirm_phrase = f"sim, desejo deletar tudo referente à mesa {table_number}"
	try:
		await interaction.response.send_message(
			(
				"⚠️ **Confirmação necessária**\n\n"
				f"Para confirmar, digite **exatamente** (sem aspas):\n\n`{confirm_phrase}`\n\n"
				"Você tem 60 segundos para confirmar no mesmo canal. "
				"Se não confirmar, a operação será cancelada."
			),
			ephemeral=True
		)
	except Exception:
		try:
			await interaction.followup.send(
				(
					"⚠️ **Confirmação necessária**\n\n"
					f"Para confirmar, digite **exatamente** (sem aspas):\n\n`{confirm_phrase}`\n\n"
					"Você tem 60 segundos para confirmar no mesmo canal."
				),
				ephemeral=True
			)
		except Exception:
			return

	channel = interaction.channel
	author = interaction.user

	def _check(msg: discord.Message):
		return (
			msg.author.id == author.id
			and msg.channel == channel
			and msg.content.strip().lower() == confirm_phrase
		)

	try:
		confirm_msg = await interaction.client.wait_for("message", check=_check, timeout=60.0)
	except asyncio.TimeoutError:
		try:
			if not interaction.response.is_done():
				await interaction.response.send_message("⏳ Tempo esgotado — operação cancelada.", ephemeral=True)
			else:
				await interaction.followup.send("⏳ Tempo esgotado — operação cancelada.", ephemeral=True)
		except Exception:
			pass
		return

	try:
		await confirm_msg.delete()
		deleting_message = await interaction.followup.send(f"**Deletando Mesa {table_number}...**", ephemeral=True)
	except Exception:
		pass

	try:
		await interaction.response.defer(ephemeral=True)
	except Exception:
		pass

	permission_error = False

	if category:
		for ch in list(category.channels):
			try:
					await ch.delete(
						reason=f"Deletado pelo comando /mesa deletar por {interaction.user}"
					)
			except discord.Forbidden:
					permission_error = True
			except discord.NotFound:
					pass

		try:
			await category.delete(
					reason=f"Deletado pelo comando /mesa deletar por {interaction.user}"
			)
		except discord.Forbidden:
			permission_error = True
		except discord.NotFound:
			pass

	for role in (player_role, master_role):
		if not role:
			continue

		try:
			await role.delete()
		except discord.Forbidden:
			permission_error = True
		except discord.NotFound:
			pass

	try:
		await deleting_message.delete()
	except Exception:
		pass

	if permission_error:
		await interaction.followup.send(
			"⚠️ Não consegui deletar a mesa. Verifique se o bot tem permissões suficientes.",
			ephemeral=True
		)
	else:
		await interaction.followup.send(f"**✅ Mesa {table_number} removida (categoria e papéis).**", ephemeral=True)


@mesa_group.command(name="sair", description="Sair de uma mesa (remove seu cargo de jogador).")
@app_commands.rename(table_number="numero_da_mesa")
@app_commands.describe(table_number="Número da mesa que você deseja sair (ex: 3)")
async def mesa_sair(interaction: discord.Interaction, table_number: int):
	guild = interaction.guild
	if not guild:
		return await interaction.response.send_message("Este comando só funciona em servidores.", ephemeral=True)

	master_role, player_role, _ = get_roles_and_category(guild, table_number)
	me = interaction.user
 
	has_player_role = player_role and player_role in me.roles
	has_master_role = master_role and master_role in me.roles

	if not has_player_role and not has_master_role:
		return await interaction.response.send_message("Você não está nesta mesa ou o cargo não existe.", ephemeral=True)

	if has_master_role:
		try:
			await me.remove_roles(master_role, reason=f"Mestre saiu da mesa {table_number}")
		except Exception:
			return await interaction.response.send_message(
				"Não consegui remover seu cargo de mestre (permissões).",
				ephemeral=True
			)
		return await interaction.response.send_message(
			f"✅ Você saiu da mesa {table_number}.\n\n"
			f"{player_role.mention} A mesa agora está sem mestre.",
			allowed_mentions=discord.AllowedMentions(roles=True)
		)

	try:
		await me.remove_roles(player_role, reason=f"{me} saiu da mesa via /mesa sair")
		await interaction.response.send_message(f"Você saiu da Mesa {table_number}.", ephemeral=True)
	except Exception:
		await interaction.response.send_message("Não pude remover seu cargo (permissões).", ephemeral=True)

@mesa_group.command(name="expulsar", description="Expulsar um jogador da mesa (remove cargo de Jogador).")
@app_commands.rename(table_number="numero_da_mesa", member="membro")
@app_commands.describe(table_number="Número da mesa", member="Membro a ser expulso")
async def mesa_expulsar(interaction: discord.Interaction, table_number: int, member: discord.Member):
	guild = interaction.guild
	if not guild:
		return await interaction.response.send_message("Este comando só funciona em servidores.", ephemeral=True)

	master_role, player_role, _ = get_roles_and_category(guild, table_number)

	me = interaction.user
	if not ((master_role and master_role in getattr(me, "roles", [])) or interaction.user.guild_permissions.manage_roles):
		return await interaction.response.send_message("Você não tem permissão para expulsar nesta mesa (só o mestre ou quem gerencia papéis).", ephemeral=True)

	if player_role is None:
		return await interaction.response.send_message("Cargo de jogador desta mesa não encontrado.", ephemeral=True)

	if player_role not in getattr(member, "roles", []):
		return await interaction.response.send_message("O membro não é jogador desta mesa.", ephemeral=True)

	try:
		await member.remove_roles(player_role, reason=f"Expulso por {interaction.user} via /mesa expulsar")
		await interaction.response.send_message(f"{member.mention} foi expulso da Mesa {table_number}.", ephemeral=True)
	except Exception:
		await interaction.response.send_message("Não consegui remover o cargo (verifique permissões do bot).", ephemeral=True)

@mesa_group.command(name="convidar", description="Convida um jogador para uma mesa.")
@app_commands.rename(table_number="numero_da_mesa", member="membro")
@app_commands.describe(table_number="Número da mesa", member="Membro a convidar")
async def mesa_convidar(interaction: discord.Interaction, table_number: int, member: discord.Member):
	guild = interaction.guild
	if not guild:
		return await interaction.response.send_message("Este comando só funciona em servidores.", ephemeral=True)

	cog = interaction.client.get_cog("TableCog")
	if cog is None:
		return await interaction.response.send_message("Cog de mesas não registrado.", ephemeral=True)

	_, player_role_name, _ = table_name_parts(table_number)
	master_role, player_role, _ = get_roles_and_category(guild, table_number)

	me = interaction.user
	if not ((master_role and master_role in getattr(me, "roles", [])) or interaction.user.guild_permissions.manage_roles):
		return await interaction.response.send_message("Você não tem permissão para convidar (só o mestre ou quem gerencia papéis).", ephemeral=True)

	if player_role is None:
		return await interaction.response.send_message("Cargo de jogador desta mesa não foi encontrado. Certifique-se que a mesa existe.", ephemeral=True)

	if player_role in getattr(member, "roles", []):
		return await interaction.response.send_message(
			f"{member.mention} já é jogador da Mesa {table_number}.",
			ephemeral=True
		)

	dm_text = (
		f"Olá {member.display_name}!\n\n"
		f"{interaction.user.mention} te convidou para a **Mesa {table_number}** em **{guild.name}**.\n\n"
		"Clique em **Aceitar** para receber o papel de jogador desta mesa (você verá os canais da mesa), ou em **Recusar** para rejeitar.\n\n"
		"Este convite expira em 3 dias."
	)

	try:
		await interaction.response.defer(ephemeral=True)
	except Exception:
		pass

	success, sent_msg, err = await cog.invite_service.send_invite(
		guild=guild,
		table_number=table_number,
		member=member,
		player_role_name=player_role_name,
		inviter_id=interaction.user.id,
		dm_text=dm_text,
		timeout=3 * 24 * 60 * 60,
	)

	dm_sent = success

	if dm_sent:
		await interaction.followup.send(f"{member.mention} recebeu o convite por DM.", ephemeral=True)
	else:
		await interaction.followup.send(f"Não consegui enviar DM para {member.mention}. Verifique se as DMs estão abertas.", ephemeral=True)

@mesa_group.command(name="info", description="Mostra informações sobre a mesa.")
@app_commands.rename(table_number="numero_da_mesa")
@app_commands.describe(table_number="Número da mesa para obter informações")
async def mesa_info(interaction: discord.Interaction, table_number: int):
	try:
		guild = interaction.guild
		if not guild:
			return await interaction.response.send_message("Este comando só funciona em servidores.", ephemeral=True)

		master_role_name, _, _ = table_name_parts(table_number)
		master_role, player_role, category = get_roles_and_category(guild, table_number)

		embed = discord.Embed(title=f"Informações — Mesa {table_number}", color=discord.Color.blue())

		mestre_text = "Não encontrado"
		if master_role:
			masters = [m for m in master_role.members]
			if masters:
					mestre_text = masters[0].mention
			else:
					mestre_text = f"(Cargo {master_role_name} existe, mas sem membro atribuído)"
		embed.add_field(name="Mestre:", value=mestre_text, inline=False)

		if player_role:
			players = player_role.members
			if players:
					limit = 20
					display = ", ".join(p.mention for p in players[:limit])
					if len(players) > limit:
						display += f" e mais {len(players)-limit}..."
			else:
					display = "Nenhum jogador"
		else:
			display = "Nenhum"
		embed.add_field(name="Jogadores:", value=display, inline=False)

		if category:
			created_at = getattr(category, "created_at", None)
			if created_at:
					if created_at.tzinfo is None:
						created_at = created_at.replace(tzinfo=timezone.utc)

					ts = int(created_at.timestamp())
					embed.add_field(name="Criada em:", value=f"<t:{ts}:f>", inline=True)
			else:
					embed.add_field(name="Criada em:", value="Desconhecida", inline=True)
		else:
			embed.add_field(name="Criada em:", value="Desconhecida", inline=True)

		embed.set_footer(text=f"Mesa {table_number} • {guild.name}")

		await interaction.response.send_message(embed=embed, ephemeral=True)

	except Exception as exc:
		logger.exception("Erro em mesa_info: %s", exc)

		try:
			if not interaction.response.is_done():
					await interaction.response.send_message("❌ Erro ao obter informações da mesa (verifique logs).", ephemeral=True)
			else:
					await interaction.followup.send("❌ Erro ao obter informações da mesa (verifique logs).", ephemeral=True)
		except Exception:
			pass