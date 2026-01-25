import discord
from discord.ext import commands
from discord import app_commands
import re

class OneShotAnnounce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def update_embed_field(self, embed: discord.Embed, field_name: str, new_name: str, new_value: str):
        for index, field in enumerate(embed.fields):
            if field.name.startswith(field_name):
                embed.set_field_at(index, name=new_name, value=new_value, inline=field.inline)
                return embed
        embed.add_field(name=new_name, value=new_value, inline=False)
        return embed

    @app_commands.command(name='criar_fissura', description='Crie uma nova fissura!')
    async def criar_fissura(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Nome da Fissura",
            description="### **Sinopse:** *Sinopse da Fissura.*",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url="https://i.pinimg.com/736x/d6/ab/51/d6ab51e1249c480dc72cd534ca91550d.jpg")
        embed.set_footer(text=f"Mestre: {interaction.user.display_name}")
        embed.add_field(name="📅 Data e Horário:", value="---", inline=False)
        embed.add_field(name="⚔️ Tier:", value="---", inline=False)
        embed.add_field(name="🔞 Classificação indicativa:", value="---", inline=False)
        embed.add_field(name="🌐 Plataformas:", value="---", inline=False)
        embed.add_field(name="📝 Observações:", value="---", inline=False)
        embed.add_field(name="🎭 Estilo:", value="---", inline=False)
        embed.add_field(name="🌌 Ambientação:", value="---", inline=False)
        embed.add_field(name="⚙️ Regras Da Casa:", value="---", inline=False)
        embed.add_field(name=f"👤 Jogadores 0/4:", value="Nenhum participante.", inline=False)

        view = FissuraView(self, author_id=interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class FissuraView(discord.ui.View):
    def __init__(self, cog: OneShotAnnounce, author_id: int, participantes=None):
        super().__init__(timeout=None)
        self.cog = cog
        self.author_id = author_id
        self.participantes = participantes or set()

        self.add_item(JoinButton(self.cog))
        self.add_item(RemoveButton(self.cog))
        self.add_item(EditButton(self.cog))
        self.add_item(AnnounceButton(self.cog))
        self.add_item(DeleteButton(self.cog))

class JoinButton(discord.ui.Button):
    def __init__(self, cog: OneShotAnnounce):
        super().__init__(label="Participar", style=discord.ButtonStyle.green)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        embed = interaction.message.embeds[0]

        current_participants = list(self.view.participantes)
        author_id = self.view.author_id

        if user_id == author_id:
            await interaction.response.send_message("Você é o mestre da mesa e não pode participar como jogador!", ephemeral=True)
            return

        if user_id in current_participants:
            await interaction.response.send_message("Você já está participando da fissura!", ephemeral=True)
            return

        jogadores_field = next((field for field in embed.fields if field.name.startswith("👤 Jogadores")), None)
        if not jogadores_field:
            await interaction.response.send_message("Erro: campo de jogadores não encontrado.", ephemeral=True)
            return

        match = re.search(r'(\d+)/(\d+)', jogadores_field.name)
        if not match:
            await interaction.response.send_message("Erro: formato do campo jogadores inválido.", ephemeral=True)
            return

        max_players = int(match.group(2))

        if len(current_participants) >= max_players:
            await interaction.response.send_message("❌ Esta fissura está cheia!", ephemeral=True)
            return

        self.view.participantes.add(user_id)

        current_players = len(self.view.participantes)
        new_field_name = f"👤 Jogadores {current_players}/{max_players}:"
        new_field_value = ", ".join(f"<@{uid}>" for uid in self.view.participantes) or "Nenhum participante."

        updated = self.cog.update_embed_field(embed, "👤 Jogadores", new_field_name, new_field_value)

        try:
            mestre = await interaction.client.fetch_user(self.view.author_id)
            await mestre.send(f"📥 {interaction.user.mention} Entrou na sua fissura **{embed.title}**!")
        except discord.Forbidden:
            print("❌ Não foi possível enviar uma DM para o mestre.")

        await interaction.message.edit(embed=updated, view=self.view)
        await interaction.response.send_message(f"{interaction.user.mention}, você entrou na fissura!", ephemeral=True)

class RemoveButton(discord.ui.Button):
    def __init__(self, cog: OneShotAnnounce):
        super().__init__(label="Sair", style=discord.ButtonStyle.red)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        if user_id not in self.view.participantes:
            await interaction.response.send_message("Você não está participando da fissura.", ephemeral=True)
            return

        self.view.participantes.remove(user_id)
        embed = interaction.message.embeds[0]

        jogadores_field = next((field for field in embed.fields if field.name.startswith("👤 Jogadores")), None)
        if not jogadores_field:
            await interaction.response.send_message("Erro: campo de jogadores não encontrado.", ephemeral=True)
            return

        match = re.search(r'(\d+)/(\d+)', jogadores_field.name)
        if not match:
            await interaction.response.send_message("Erro: formato do campo jogadores inválido.", ephemeral=True)
            return

        max_players = int(match.group(2))

        current_players = len(self.view.participantes)
        new_name = f"👤 Jogadores {current_players}/{max_players}:"
        new_value = ", ".join(f"<@{uid}>" for uid in self.view.participantes) or "Nenhum participante."

        updated = self.cog.update_embed_field(embed, "👤 Jogadores", new_name, new_value)

        await interaction.message.edit(embed=updated, view=self.view)
        await interaction.response.send_message(f"{interaction.user.mention}, você saiu da fissura.", ephemeral=True)

class EditButton(discord.ui.Button):
    def __init__(self, cog: OneShotAnnounce):
        super().__init__(label="Editar Mesa", style=discord.ButtonStyle.blurple)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.author_id:
            await interaction.response.send_message("❌ Apenas o criador da fissura pode editar as informações dela.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label="📝 Nome da Fissura", value="Nome"),
            discord.SelectOption(label="📝 Sinopse da Fissura", value="Sinopse"),
            discord.SelectOption(label="📅 Data e Horário", value="📅 Data e Horário:"),
            discord.SelectOption(label="👥 Vagas", value="👤 Jogadores:"),
            discord.SelectOption(label="⚔️ Tier", value="⚔️ Tier:"),
            discord.SelectOption(label="🔞 Classificação indicativa", value="🔞 Classificação indicativa:"),
            discord.SelectOption(label="🌐 Plataformas", value="🌐 Plataformas:"),
            discord.SelectOption(label="📝 Observações", value="📝 Observações:"),
            discord.SelectOption(label="🎭 Estilo", value="🎭 Estilo:"),
            discord.SelectOption(label="🌌 Ambientação", value="🌌 Ambientação:"),
            discord.SelectOption(label="⚙️ Regras Da Casa", value="⚙️ Regras Da Casa:"),
            discord.SelectOption(label="🌆 Imagem da mesa", value="Imagem"),
        ]
        select = discord.ui.Select(placeholder="Selecione o campo para editar", options=options, min_values=1, max_values=1)
        tmp_view = discord.ui.View()
        tmp_view.add_item(select)

        async def select_callback(inter_select: discord.Interaction):
            selected = select.values[0]
            target_message = inter_select.message
            await inter_select.response.send_modal(EditModal(selected, self.cog, self.view, target_message))

        select.callback = select_callback
        await interaction.response.edit_message(view=tmp_view)

class AnnounceButton(discord.ui.Button):
    def __init__(self, cog: OneShotAnnounce):
        super().__init__(label="Anunciar Mesa", style=discord.ButtonStyle.green, custom_id="announce_button")
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        author_id = self.view.author_id
        private_view = FissuraView(self.cog, author_id, participantes=set(self.view.participantes))

        cargo = discord.utils.get(interaction.guild.roles, name="Mago")
        if not cargo:
            await interaction.channel.send(content=f"📣 Uma nova fissura foi aberta!", embed=embed, view=private_view)
        else:
            await interaction.channel.send(content=f"📣 Uma nova fissura foi aberta {cargo.mention}!", embed=embed, view=private_view)

        await interaction.response.send_message("Fissura anunciada!", ephemeral=True)

class DeleteButton(discord.ui.Button):
    def __init__(self, cog: OneShotAnnounce):
        super().__init__(label="Apagar Mesa", style=discord.ButtonStyle.danger)
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.author_id:
            await interaction.response.send_message("❌ Apenas o criador da fissura pode apagar a mesa.", ephemeral=True)
            return

        self.view.participantes.clear()
        try:
            await interaction.message.delete()
        except discord.Forbidden:
            await interaction.response.send_message("Não foi possível apagar a mensagem (permissão).", ephemeral=True)
            return

        try:
            await interaction.user.send("🗑️ Sua mesa foi apagada com sucesso.")
        except discord.Forbidden:
            pass

class EditModal(discord.ui.Modal):
	def __init__(self, field_name: str, cog: OneShotAnnounce, original_view: discord.ui.View, target_message: discord.Message):
		super().__init__(title=f"Editar {field_name}")
		self.field_name = field_name
		self.cog = cog
		self.original_view = original_view
		self.target_message = target_message

		self.text_input = discord.ui.TextInput(
			label="Novo valor",
			placeholder=f"Digite o novo valor para {field_name}",
			custom_id="edit_modal_value"
		)
		self.add_item(self.text_input)

	async def on_submit(self, interaction: discord.Interaction):
		novo_valor = self.text_input.value

		try:
			embed_atual = self.target_message.embeds[0]
		except Exception:
			embed_atual = discord.Embed(title="(sem embed encontrado)")

		updated_embed = embed_atual.copy()

		if self.field_name == "Nome":
			updated_embed.title = novo_valor

		elif self.field_name == "Sinopse":
			updated_embed.description = f"**Sinopse:** *{novo_valor}*"

		elif self.field_name == "Imagem":
			if not novo_valor.startswith("http") or not any(novo_valor.endswith(ext) for ext in (".jpg", ".png", ".webp", ".jpeg")):
					await interaction.response.send_message("❌ Forneça uma URL válida (.jpg/.png/.webp/.jpeg).", ephemeral=True)
					return
			updated_embed.set_thumbnail(url=novo_valor)

		elif self.field_name.startswith("👤 Jogadores"):
			try:
					novo_max = int(novo_valor)
					if novo_max < 1:
						raise ValueError
			except ValueError:
					await interaction.response.send_message("❌ Insira um número válido de vagas (mínimo 1).", ephemeral=True)
					return

			current_players = len(self.original_view.participantes)
			new_name = f"👤 Jogadores {current_players}/{novo_max}:"
			new_value = ", ".join(f"<@{uid}>" for uid in self.original_view.participantes) or "Nenhum participante."
			updated_embed = self.cog.update_embed_field(updated_embed, "👤 Jogadores", new_name, new_value)

			setattr(self.original_view, "max_players", novo_max)

		else:
			updated_embed = self.cog.update_embed_field(updated_embed, self.field_name, self.field_name, novo_valor)

		if self.field_name == "Nome":
			setattr(self.original_view, "title", novo_valor)

		nova_view = FissuraView(self.cog, self.original_view.author_id, participantes=set(self.original_view.participantes))

		await interaction.response.send_message("Campo atualizado. Aplicando alteração...", ephemeral=True)

		try:
			await self.target_message.edit(embed=updated_embed, view=nova_view)
			return
		except Exception as exc:
			print("Falha ao editar target_message:", repr(exc))

		try:
			await interaction.followup.send(embed=updated_embed, view=nova_view, ephemeral=True)
		except Exception:
			try:
				await interaction.user.send("Preview da alteração (não foi possível editar a mensagem original):", embed=updated_embed, view=nova_view)
			except Exception:
				print("Não foi possível enviar preview nem DM ao usuário.")

		return

async def setup(bot: commands.Bot):
	cog = OneShotAnnounce(bot)
	await bot.add_cog(cog)

	try:
		bot.tree.add_command(cog.criar_fissura)
	except Exception:
		pass
