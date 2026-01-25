from typing import Optional
import discord
from discord.ui import View, Button, Select
import logging
from .utils.table_utils import make_embed

logger = logging.getLogger("mesa.components")

class DMInviteView(View):
	def __init__(
		self,
		parent_controller,
		guild_id: int,
		table_number: int,
		player_role_name: str,
		inviter_id: int,
		invitee_id: int,
		timeout: Optional[float] = 3 * 24 * 60 * 60,
	):
		super().__init__(timeout=timeout)
		self.controller = parent_controller
		self.bot = getattr(self.controller, "bot", None)
		self.guild_id = guild_id
		self.table_number = table_number
		self.player_role_name = player_role_name
		self.inviter_id = inviter_id
		self.invitee_id = invitee_id
		self.sent_message: Optional[discord.Message] = None

	@discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success)
	async def accept(self, interaction: discord.Interaction, button: Button):
		if interaction.user.id != self.invitee_id:
			return await interaction.response.send_message("Este convite não é para você.", ephemeral=True)

		guild = self.bot.get_guild(self.guild_id) if self.bot else None
		if not guild:
			await interaction.response.edit_message(content="Erro: servidor não encontrado. Não foi possível aceitar o convite.", view=None)
			try:
					self.controller.clear_pending_invite(self.guild_id, self.table_number, self.invitee_id)
			except Exception:
					logger.exception("Erro ao limpar pending invite (guild não encontrada)")
			return

		member = guild.get_member(interaction.user.id)
		if not member:
			await interaction.response.edit_message(content="Você não é mais membro deste servidor — não é possível aceitar o convite.", view=None)
			try:
					self.controller.clear_pending_invite(self.guild_id, self.table_number, self.invitee_id)
			except Exception:
					logger.exception("Erro ao limpar pending invite (member não encontrado)")
			return

		try:
			await self.controller.add_player_role(guild, member, self.player_role_name)
		except Exception as e:
			logger.exception("Falha ao adicionar role no accept do DMInviteView: %s", e)
			msg = str(e) if e else "Não foi possível atribuir o cargo (verifique permissões/hierarquia)."

			for c in self.children:
					c.disabled = True
			await interaction.response.edit_message(content=msg, view=self)

			try:
					self.controller.clear_pending_invite(self.guild_id, self.table_number, self.invitee_id)
			except Exception:
					logger.exception("Erro ao limpar pending invite após falha de atribuição")
			return

		for c in self.children:
			c.disabled = True
		await interaction.response.edit_message(content=f"✅ Você aceitou o convite para a Mesa {self.table_number}.", view=None)
  
		try:
			guild = self.bot.get_guild(self.guild_id) if self.bot else None
			inviter_member = guild.get_member(self.inviter_id) if guild else None
			if inviter_member:
					await inviter_member.send(f"{interaction.user.display_name} aceitou seu convite para a Mesa {self.table_number}.")
		except Exception:
			logger.exception("Falha ao notificar o inviter sobre accept (ignorado)")

		try:
			self.controller.clear_pending_invite(self.guild_id, self.table_number, self.invitee_id)
		except Exception:
			logger.exception("Erro ao limpar pending invite (success path)")

	@discord.ui.button(label="Recusar", style=discord.ButtonStyle.danger)
	async def decline(self, interaction: discord.Interaction, button: Button):
		if interaction.user.id != self.invitee_id:
			return await interaction.response.send_message("Este convite não é para você.", ephemeral=True)

		try:
			guild = self.bot.get_guild(self.guild_id) if self.bot else None
			inviter_member = guild.get_member(self.inviter_id) if guild else None
			if inviter_member:
					await inviter_member.send(f"{interaction.user.display_name} recusou seu convite para a Mesa {self.table_number}.")
		except Exception:
			logger.exception("Falha ao notificar o inviter sobre recusa (ignorado)")

		for c in self.children:
			c.disabled = True
		await interaction.response.edit_message(content=f"❌ Você recusou o convite para a Mesa {self.table_number}.", view=None)

		try:
			self.controller.clear_pending_invite(self.guild_id, self.table_number, self.invitee_id)
		except Exception:
			logger.exception("Erro ao limpar pending invite no decline")

	async def on_timeout(self):
		try:
			if self.sent_message:
					for c in self.children:
						c.disabled = True
					await self.sent_message.edit(content=f"⌛ Convite para Mesa {self.table_number} expirou.", view=self)
		except Exception:
			logger.exception("Erro ao editar mensagem na on_timeout")
		finally:
			try:
					self.controller.clear_pending_invite(self.guild_id, self.table_number, self.invitee_id)
			except Exception:
					logger.exception("Erro ao limpar pending invite na on_timeout")

class JoinButton(Button):
    def __init__(self, controller, inst_id: str):
        super().__init__(label="Participar", style=discord.ButtonStyle.primary)
        self.controller = controller
        self.inst_id = inst_id

    async def callback(self, interaction: discord.Interaction):
        inst = self.controller.active_tables.get(self.inst_id)
        if not inst:
            return await interaction.response.send_message("Esta mesa expirou ou foi cancelada.", ephemeral=True)

        if inst.creating:
            return await interaction.response.send_message("⏳ A mesa está sendo criada, aguarde.", ephemeral=True)

        if interaction.user.id == inst.master.id:
            return await interaction.response.send_message("O mestre não pode entrar como jogador!", ephemeral=True)

        if any(p.id == interaction.user.id for p in inst.players):
            return await interaction.response.send_message("Você já está na mesa!", ephemeral=True)

        inst.players.append(interaction.user)

        if inst.embed_message:
            try:
                await inst.embed_message.edit(embed=make_embed(inst), view=self.view)
            except Exception:
                logger.exception("Falha ao editar embed após JoinButton callback")

        await interaction.response.send_message("Você entrou na mesa!", ephemeral=True)


class ConfirmButton(Button):
    def __init__(self, controller, inst_id: str):
        super().__init__(label="Criar mesa", style=discord.ButtonStyle.success)
        self.controller = controller
        self.inst_id = inst_id

    async def callback(self, interaction: discord.Interaction):
        inst = self.controller.active_tables.get(self.inst_id)
        if not inst:
            return await interaction.response.send_message("Esta mesa expirou ou foi cancelada.", ephemeral=True)

        if inst.creating:
            return await interaction.response.send_message("⏳ A criação da mesa já está em andamento!", ephemeral=True)

        if interaction.user.id != inst.master.id:
            return await interaction.response.send_message("Apenas o mestre pode criar a mesa!", ephemeral=True)

        if len(inst.players) == 0:
            return await interaction.response.send_message("É necessário pelo menos **1 jogador** para criar a mesa!", ephemeral=True)

        try:
            await interaction.response.defer()
        except Exception:
            pass

        try:
            await self.controller.create_table(inst, interaction)
        except Exception as e:
            logger.exception("Erro no ConfirmButton ao chamar create_table: %s", e)
            inst.creating = False

            try:
                await interaction.followup.send(f"❌ Erro ao criar a mesa: {e}", ephemeral=True)
            except Exception:
                logger.exception("Não foi possível enviar followup após erro de create_table")
                
class LeaveButton(Button):
	def __init__(self, controller, inst_id: str):
		super().__init__(label="Sair/Remover", style=discord.ButtonStyle.red)
		self.controller = controller
		self.inst_id = inst_id

	async def callback(self, interaction: discord.Interaction):
		inst = self.controller.active_tables.get(self.inst_id)
		if not inst:
			return await interaction.response.send_message("Esta mesa expirou ou foi cancelada.", ephemeral=True)

		if interaction.user.id == inst.master.id:
			if not inst.players:
				return await interaction.response.send_message(
					"Não há jogadores para remover",
					ephemeral=True
				)
    
			view = RemovePlayerView(self.controller, inst)
			return await interaction.response.send_message(
				"Selecione um jogador para remover",
				view=view,
				ephemeral=True
			)

		if not any(p.id == interaction.user.id for p in inst.players):
			return await interaction.response.send_message("Você não está nesta reserva.", ephemeral=True)

		inst.players = [p for p in inst.players if p.id != interaction.user.id]

		if inst.embed_message:
			try:
				await inst.embed_message.edit(embed=make_embed(inst))
			except Exception:
				pass

		await interaction.response.send_message("Você saiu da mesa (reserva).", ephemeral=True)
  
class RemovePlayerView(View):
	def __init__(self, controller, inst):
		super().__init__(timeout=60)
		self.add_item(RemovePlayerSelect(controller, inst))
  
class RemovePlayerSelect(Select):
	def __init__(self, controller, inst):
		options = [
			discord.SelectOption(
					label=p.display_name,
					value=str(p.id)
			)
			for p in inst.players
		]

		super().__init__(
			placeholder="Remover jogador da mesa",
			options=options,
			min_values=1,
			max_values=1
		)

		self.controller = controller
		self.inst = inst

	async def callback(self, interaction: discord.Interaction):
		target_id = int(self.values[0])

		removed = None
		for p in list(self.inst.players):
			if p.id == target_id:
					removed = p
					self.inst.players.remove(p)
					break

		if self.inst.embed_message:
			try:
				await self.inst.embed_message.edit(embed=make_embed(self.inst))
			except Exception:
				logger.exception("Erro ao atualizar embed após remoção")
     
		for child in self.view.children:
			child.disabled = True

		await interaction.response.edit_message(
			content=f"✅ {removed.display_name} foi removido da mesa.",
			view=None
		)
  
		self.view.stop()

		try:
			await removed.send(
					f"Você foi removido da reserva da Mesa {self.inst.table_number}."
			)
		except Exception:
			pass
