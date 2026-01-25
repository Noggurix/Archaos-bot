import logging
from typing import Iterable, Optional
import discord

logger = logging.getLogger("mesa.table_service")

class TableCreationError(Exception):
	pass

class TableService:
	def __init__(
		self,
		bot: discord.Client,
		make_embed,
		get_overwrites,
		release_reserved_number_cb,
		active_tables_ref,
		reorder_category_channels=None,
		config_order: Optional[Iterable[str]] = None,
		config_voice_names: Optional[set] = None,
		config_special_forums: Optional[set] = None,
	):
		self.bot = bot
		self.make_embed = make_embed
		self.get_overwrites = get_overwrites
		self.release_reserved_number_cb = release_reserved_number_cb
		self.active_tables = active_tables_ref
		self.reorder_category_channels = reorder_category_channels

		self.order = list(config_order) if config_order is not None else [
			"📒꠵-𝐑𝐞𝐠𝐫𝐚s 𝐝𝐚 𝐌𝐞𝐬𝐚",
			"❗꠵-𝐀𝐯𝐢𝐬𝐨𝘀",
			"╰୨📆୧︰𝐇𝐨𝐫𝐚𝐫𝐢𝐨𝐬",
			"╰୨💬୧︰𝐂𝐡𝐚𝐭",
			"╰୨🎲୧︰𝐑𝐨𝐥𝐚𝐠𝐞𝐧𝐬",
			"╰୨👤୧︰𝐏𝐞𝐫𝐬𝐨𝐧𝐚𝐠𝐞𝐧𝐬",
			"╰୨🌆୧︰𝐂𝐞𝐧𝐚",
			"﹙🧛﹚𝐍𝐏𝐂𝐬",
			"╰୨🎶୧︰𝐁𝐨𝐭 𝐝𝐞 𝐦𝐮𝐬𝐢𝐜𝐚𝐬",
			"╰୨🐲୧︰𝐀𝐯𝐞𝐧𝐭𝐮𝐫𝐚 ˎˊ˗ ",
			"╰୨🙋‍♂️୧︰𝐅𝐚𝐥𝐞 𝐜𝐨𝐦 𝐨 𝐦𝐞𝐬𝐭𝐫𝐞 ˎˊ˗"
		]
		self.voice_names = set(config_voice_names) if config_voice_names is not None else {
			"╰୨🐲୧︰𝐀𝐯𝐞𝐧𝐭𝐮𝐫𝐚 ˎˊ˗ ",
			"╰୨🙋‍♂️୧︰𝐅𝐚𝐥𝐞 𝐜𝐨𝐦 𝐨 𝐦𝐞𝐬𝐭𝐫𝐞 ˎˊ˗"
		}
		self.special_forums = set(config_special_forums) if config_special_forums is not None else {"﹙🧛﹚𝐍𝐏𝐂𝐬"}

	async def create_table(self, inst, interaction: discord.Interaction):
		if inst is None:
			raise TableCreationError("Instância inválida")

		if getattr(inst, "creating", False):
			raise TableCreationError("Criação já em andamento")

		inst.creating = True

		guild = interaction.guild
		if guild is None:
			inst.creating = False
			raise TableCreationError("Interação não é em um servidor")

		try:
			creating_embed = self.make_embed(inst)
			creating_embed.title = f"⏳ Criando Mesa {inst.table_number}..."
			creating_embed.description = "Aguarde enquanto cargos e canais são criados..."
			creating_embed.color = discord.Color.gold()
			creating_view = discord.ui.View(timeout=None)
			creating_view.add_item(discord.ui.Button(label="Participar", disabled=True))
			cb = discord.ui.Button(label="Criando...", style=discord.ButtonStyle.secondary, disabled=True)
			creating_view.add_item(cb)
			if getattr(inst, "embed_message", None):
				try:
					await inst.embed_message.edit(embed=creating_embed, view=creating_view)
				except Exception:
					logger.exception("Falha ao editar embed de criação (não fatal)")
		except Exception:
			logger.exception("Falha ao preparar embed/visual (não fatal)")

		table_role = None
		master_role = None
		created_channels = {}
		created_objects = {"table_role": None, "master_role": None, "category": None, "channels": {}}

		try:
			table_role = await guild.create_role(
				name=f"Mesa {inst.table_number} Jogador",
				mentionable=True,
				color=discord.Color(0x4f5eff)
			)
			created_objects["table_role"] = table_role

			master_role = await guild.create_role(
				name=f"Mesa {inst.table_number} Mestre",
				mentionable=True,
				color=discord.Color(0xffd100)
			)
			created_objects["master_role"] = master_role

			category = await guild.create_category(
				name=f"Mesa {inst.table_number}",
				overwrites=self.get_overwrites(guild, table_role, master_role, is_category=True)
			)
			created_objects["category"] = category

			for name in self.order:
				if name in self.special_forums:
					overwrites = self.get_overwrites(guild, table_role, master_role, player_send_messages=False)
					ch = await guild.create_forum(name=name, category=category, overwrites=overwrites)
				elif name in self.voice_names:
					overwrites = self.get_overwrites(guild, table_role, master_role, player_send_messages=False, is_voice=True)
					user_limit = 2 if "╰୨🙋‍♂️୧︰𝐅𝐚𝐥𝐞 𝐜𝐨𝐦 𝐨 𝐦𝐞𝐬𝐭𝐫𝐞 ˎˊ˗" in name else 0
					ch = await guild.create_voice_channel(name=name, category=category, overwrites=overwrites, user_limit=user_limit)
				else:
					player_send = name not in ("📒꠵-𝐑𝐞𝐠𝐫𝐚s 𝐝𝐚 𝐌𝐞𝐬𝐚", "﹙🧛﹚𝐍𝐏𝐂𝐬", "❗꠵-𝐀𝐯𝐢𝐬𝐨𝘀")
					overwrites = self.get_overwrites(guild, table_role, master_role, player_send_messages=player_send)
					ch = await guild.create_text_channel(name=name, category=category, overwrites=overwrites)

				created_channels[name] = ch
				created_objects["channels"][name] = ch

			if self.reorder_category_channels:
				try:
					await self.reorder_category_channels(guild, category, self.order, created_channels)
				except Exception:
					logger.exception("Falha ao reordenar canais (não fatal)")

			for member in inst.players:
				await member.add_roles(table_role, reason=f"Atribuído jogador Mesa {inst.table_number}")
			await inst.master.add_roles(master_role, reason=f"Atribuído mestre Mesa {inst.table_number}")

			if getattr(inst, "reserved_cancel_task", None):
				try:
					inst.reserved_cancel_task.cancel()
				except Exception:
					pass

			try:
				await self.release_reserved_number_cb(inst.guild_id, inst.table_number)
			except Exception:
				logger.exception("Falha ao liberar número reservado (não fatal)")

			try:
				self.active_tables.pop(inst.id, None)
			except Exception:
				logger.exception("Falha ao remover inst de active_tables (não fatal)")

			if getattr(inst, "embed_message", None):
				try:
					await inst.embed_message.edit(content=f"**✅ Mesa {inst.table_number} criada com sucesso!**", embed=None, view=None)
				except Exception:
					logger.exception("Falha ao editar embed de sucesso (não fatal)")

			inst.creating = False
			return created_objects

		except discord.Forbidden as e:
			logger.exception("Permissões insuficientes ao criar mesa")
			try:
				await interaction.followup.send("❌ Não tenho permissão suficiente para criar cargos/canais.", ephemeral=True)
			except Exception:
				logger.exception("Não foi possível enviar followup de permissão")

			if table_role:
				try:
					await table_role.delete()
				except Exception:
					pass
			if master_role:
				try:
					await master_role.delete()
				except Exception:
					pass

			try:
				await self.release_reserved_number_cb(inst.guild_id, inst.table_number)
			except Exception:
				pass
			try:
				self.active_tables.pop(inst.id, None)
			except Exception:
				pass

			inst.creating = False
			raise TableCreationError("Permissões insuficientes") from e

		except Exception as e:
			logger.exception("Erro inesperado ao criar mesa")
			try:
				await interaction.followup.send(f"❌ Erro inesperado: {e}", ephemeral=True)
			except Exception:
				logger.exception("Não foi possível enviar followup de erro")

			if table_role:
				try:
					await table_role.delete()
				except Exception:
					pass
			if master_role:
				try:
					await master_role.delete()
				except Exception:
					pass

			try:
				await self.release_reserved_number_cb(inst.guild_id, inst.table_number)
			except Exception:
				pass
			try:
				self.active_tables.pop(inst.id, None)
			except Exception:
				pass

			inst.creating = False
			raise TableCreationError("Erro inesperado") from e
