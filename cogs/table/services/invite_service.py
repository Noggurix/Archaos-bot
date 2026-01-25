import uuid
import logging
from typing import Dict, Tuple, Optional
import discord
from ..components import DMInviteView

logger = logging.getLogger("mesa.invite_service")

class InviteService:
	def __init__(self, controller, pending_invites_ref: Dict[Tuple[int, int, int], str]):
		self.controller = controller
		self.bot = getattr(controller, "bot", None)
		self.pending_invites = pending_invites_ref

	async def send_invite(
		self,
		guild: discord.Guild,
		table_number: int,
		member: discord.Member,
		player_role_name: str,
		inviter_id: int,
		dm_text: str,
		timeout: Optional[float] = 3 * 24 * 60 * 60,
	) -> tuple[bool, Optional[discord.Message], Optional[str]]:

		key = (guild.id, table_number, member.id)

		if key in self.pending_invites:
			return False, None, "already_pending"

		view = DMInviteView(
			parent_controller=self.controller,
			guild_id=guild.id,
			table_number=table_number,
			player_role_name=player_role_name,
			inviter_id=inviter_id,
			invitee_id=member.id,
			timeout=timeout,
		)

		try:
			msg = await member.send(dm_text, view=view)
		except Exception as e:
			logger.exception("Falha ao enviar DM para %s: %s", member, e)
			return False, None, "dm_failed"

		view.sent_message = msg

		self.pending_invites[key] = str(uuid.uuid4())

		return True, msg, None

	def clear_pending(self, guild_id: int, table_number: int, invitee_id: int) -> None:
		key = (guild_id, table_number, invitee_id)
		try:
			self.pending_invites.pop(key, None)
		except Exception:
			logger.exception("Erro limpando pending invite %s", key)
