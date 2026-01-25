import discord
from discord.ext import commands
import asyncio
import uuid
from typing import Dict, Set, Tuple
from discord import utils
from .groups import mesa_group
from .components import JoinButton, ConfirmButton, LeaveButton
from .models.table_instance import TableInstance
from .services.table_creation_service import TableService
from .services.invite_service import InviteService
from .utils.table_utils import make_embed, get_overwrites, parse_max_role_number, reorder_category_channels
import logging

logger = logging.getLogger("mesa.cog")

RESERVATION_TIMEOUT_SECONDS = 15 * 60
OFFICIAL_MASTER_ROLE = {"Mestre Oficial"}

class TableCog(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot
		self.active_tables: Dict[str, TableInstance] = {}
		self.guild_locks: Dict[int, asyncio.Lock] = {}
		self.guild_reserved_numbers: Dict[int, Set[int]] = {}
		self.pending_invites: Dict[Tuple[int, int, int], str] = {}
		self.invite_service = InviteService(controller=self, pending_invites_ref=self.pending_invites)
	
		self.table_service = TableService(
			bot=self.bot,
			make_embed=make_embed,
			get_overwrites=get_overwrites,
			release_reserved_number_cb=self.release_reserved_number,
			active_tables_ref=self.active_tables,
			reorder_category_channels=reorder_category_channels,
		)

	def _get_lock(self, guild_id: int) -> asyncio.Lock:
		if guild_id not in self.guild_locks:
			self.guild_locks[guild_id] = asyncio.Lock()
		return self.guild_locks[guild_id]

	def _get_reserved_set(self, guild_id: int) -> Set[int]:
		if guild_id not in self.guild_reserved_numbers:
			self.guild_reserved_numbers[guild_id] = set()
		return self.guild_reserved_numbers[guild_id]

	async def reserve_table_number(self, guild: discord.Guild) -> int:
		async with self._get_lock(guild.id):
			base = parse_max_role_number(guild)
			reserved = self._get_reserved_set(guild.id)
			number = base + len(reserved) + 1
			while number in reserved:
				number += 1
			reserved.add(number)
			return number

	async def release_reserved_number(self, guild_id: int, number: int):
		async with self._get_lock(guild_id):
			self._get_reserved_set(guild_id).discard(number)

	def schedule_reservation_release(self, instance: TableInstance):
		async def _auto_release():
			await asyncio.sleep(RESERVATION_TIMEOUT_SECONDS)
			if instance.id in self.active_tables:
					await self.release_reserved_number(instance.guild_id, instance.table_number)
					if instance.embed_message:
						try:
							await instance.embed_message.edit(
									content="**⭕ Reserva de mesa expirada (15 minutos sem confirmação).**",
									embed=None, view=None
							)
						except:
							pass
					self.active_tables.pop(instance.id, None)

		task = asyncio.create_task(_auto_release())
		instance.reserved_cancel_task = task

	async def create_table(self, inst, interaction: discord.Interaction):
		return await self.table_service.create_table(inst, interaction)

	async def start_reservation(self, interaction: discord.Interaction):
		logger.debug("start_reservation called by %s in guild %s", getattr(interaction.user, "id", None), getattr(interaction.guild, "id", None))
		if not interaction.guild:
			return await interaction.response.send_message("Este comando só funciona em servidores.", ephemeral=True)

		user = interaction.user
		has_official_role = any(r.name in OFFICIAL_MASTER_ROLE for r in getattr(user, "roles", []))

		if not (has_official_role):
			return await interaction.response.send_message(
				"Você precisa ser um mestre oficial do servidor para criar mesas.",
				ephemeral=True
			)
   
		await interaction.response.defer()

		try:
			table_number = await self.reserve_table_number(interaction.guild)
		except Exception as e:
			logger.exception("Erro em reserve_table_number")
			try:
				return await interaction.response.send_message("Erro ao reservar número da mesa.", ephemeral=True)
			except Exception:
				try:
					return await interaction.edit_original_response("Erro ao reservar número da mesa.", ephemeral=True)
				except Exception:
					return

		inst_id = str(uuid.uuid4())
		inst = TableInstance(
			id=inst_id,
			guild_id=interaction.guild.id,
			master=interaction.user,
			table_number=table_number
		)
		self.active_tables[inst_id] = inst
		self.schedule_reservation_release(inst)

		view = discord.ui.View(timeout=None)
		view.add_item(JoinButton(self, inst_id))
		view.add_item(ConfirmButton(self, inst_id))
		view.add_item(LeaveButton(self, inst_id))

		embed = make_embed(inst)

		try:
			msg = await interaction.followup.send(embed=embed, view=view, ephemeral=False)
			inst.embed_message = msg
		except Exception as e:
			logger.exception("Erro ao enviar followup com embed/view: %s", e)
			try:
					await interaction.edit_original_response(content="Erro ao enviar a mensagem de reserva.")
			except Exception:
					pass
			if inst.reserved_cancel_task:
					inst.reserved_cancel_task.cancel()
			await self.release_reserved_number(inst.guild_id, inst.table_number)
			self.active_tables.pop(inst_id, None)
  
	async def add_player_role(self, guild: discord.Guild, member: discord.Member, role_name: str) -> None:
		role = utils.get(guild.roles, name=role_name)
		if role is None:
			raise RuntimeError("Papel não encontrado no servidor.")
		if guild.me is None:
			raise RuntimeError("Bot não encontrado no guild (cache).")
		await member.add_roles(role, reason=f"Aceito convite para {role_name}")

	def clear_pending_invite(self, guild_id: int, table_number: int, invitee_id: int) -> None:
		key = (guild_id, table_number, invitee_id)
		try:
			self.pending_invites.pop(key, None)
		except Exception:
			pass

async def setup(bot: commands.Bot):
	await bot.add_cog(TableCog(bot))

	try:
		from . import commands as mesa_commands
	except Exception:
		logger.exception("Falha ao importar mesa.commands")

	try:
		bot.tree.add_command(mesa_group)
	except Exception:
		pass
