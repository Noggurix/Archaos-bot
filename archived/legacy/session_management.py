import asyncio
import discord
import re
from discord.ext import commands
from utils.database_utils import get_player, update_hp_mp

def get_player_data(user_id):
    return get_player(user_id)

def update_player_hp_mp(user_id, hp, mp):
    update_hp_mp(user_id, hp, mp)

class PersistentView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

class SessionCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.joined_users = set()
        self.session_embed = None
        self.original_message = None
        self.mention_message = None
        self.active_sessions = {}

        async def mesa_autocomplete(ctx: discord.AutocompleteContext):
            guild = ctx.interaction.guild
            member = guild.get_member(ctx.interaction.user.id) or await guild.fetch_member(ctx.interaction.user.id)
            
            if not member:
                return []

            regex = re.compile(r"^Table \d+", re.IGNORECASE)
            
            table_roles = {
                regex.match(role.name).group(0)
                for role in member.roles
                if regex.match(role.name) and ctx.value.lower() in role.name.lower()
            }

            return list(table_roles)

        @bot.slash_command(name="sessao", description="Marcar uma sessão.")
        async def sessao(interaction: discord.Interaction,
            horario: discord.Option(str, description="Defina um horário:"), # type: ignore
            dia: discord.Option(str, choices=["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"], description="Selecione o dia da sessão:", required=True), # type: ignore
            mesa: discord.Option(str, description="Em qual mesa?", autocomplete=mesa_autocomplete, required=True)): # type: ignore

            master_pattern = r"Table \d+ Master"
            player_pattern = r"Table \d+ Player"
            has_master_role = any(re.match(master_pattern, role.name) for role in interaction.user.roles)

            if interaction.channel.id in self.active_sessions:
                await interaction.response.send_message("A sessão já está ativa neste canal.", ephemeral=True)
                return

            if not has_master_role:
                await interaction.response.send_message("Apenas mestres de mesa podem iniciar uma sessão.", ephemeral=True)
                return

            self.active_sessions[interaction.channel.id] = True
            self.session_embed = discord.Embed(title="Waiting for players...", description="Clique em **Entrar** para participar da sessão.")
            session_view = PersistentView()

            session_button = discord.ui.Button(label="Entrar", style=discord.ButtonStyle.blurple)
            initiate_button = discord.ui.Button(label="Initiate session", style=discord.ButtonStyle.green)
            end_session_button = discord.ui.Button(label="Encerrar sessão", style=discord.ButtonStyle.gray)

            session_view.add_item(session_button)
            session_view.add_item(initiate_button)
            session_view.add_item(end_session_button)

            async def session_button_callback(interaction: discord.Interaction):
                user = interaction.user
                player_role = any(re.match(player_pattern, role.name) for role in interaction.user.roles)
                if user.id in self.joined_users:
                    await interaction.response.send_message("Você já entrou na sessão.", ephemeral=True)
                    return

                if player_role:
                    self.session_embed.add_field(name="", value=f"{interaction.user.mention}", inline=False)
                    self.joined_users.add(user.id)
                    await interaction.response.edit_message(embed=self.session_embed, view=session_view)
                else:
                    await interaction.response.send_message("Você não é um player desta mesa.", ephemeral=True)

            session_button.callback = session_button_callback

            async def initiate_button_callback(interaction: discord.Interaction):
                user = interaction.user

                if not has_master_role:
                    await interaction.response.send_message("Apenas o mestre pode iniciar a sessão.", ephemeral=True)
                    return
                
                if not self.joined_users:
                    await interaction.response.send_message("Pelo menos um jogador deve entrar na sessão antes de iniciar.", ephemeral=True)
                    return

                session_view.clear_items()
                self.session_embed.title="Sessão iniciada!"
                self.session_embed.description = ""
                session_view.add_item(end_session_button)

                await self.mention_message.delete()

                await interaction.response.edit_message(embed=self.session_embed, view=session_view)

            initiate_button.callback = initiate_button_callback

            async def end_session_button_callback(interaction: discord.Interaction):
                if not has_master_role:
                    await interaction.response.send_message("Apenas o mestre pode encerrar a sessão.", ephemeral=True)
                    return
                self.active_sessions.pop(interaction.channel.id, None)
                self.joined_users.clear()
                await self.original_message.delete()
                if "Sessão iniciada!" not in self.session_embed.title:
                    await self.mention_message.delete()
                await interaction.response.send_message("A sessão foi finalizada.")

            end_session_button.callback = end_session_button_callback

            slash_response = await interaction.response.send_message("Iniciando sessão...", ephemeral=True)
            self.mention_message = await interaction.channel.send(f"Uma sessão está prestes a ser iniciada!")
            self.original_message = await interaction.channel.send(embed=self.session_embed, view=session_view)
            await asyncio.sleep(3)
            await slash_response.delete_original_response()

def setup(bot):
    bot.add_cog(SessionCog(bot))
