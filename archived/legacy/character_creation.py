import asyncio
import re
import discord
from discord.ext import commands
from utils.database_utils import add_player, add_sk_points

races = ["Humano", "Gigante", "Fada", "Anão", "Bruxa", "Elfo", "Vampiro"]

class_options = {
    "Humano": ["Assassino", "Mago", "Mago de Batalha", "Ferreiro", "Mestre das armas"],
    "Gigante": ["Bastião", "Armeiro", "Gladiador"],
    "Fada": ["Fada de água", "Fada de vento", "Fada de fogo", "Fada de terra", "Fada de estrela"],
    "Anão": ["Artífice", "Ferreiro Arcano", "Ferreiro Orgânico"],
    "Bruxa": ["Original", "Evolutiva"],
    "Elfo": ["Sábio do pacto", "Místico", "Sub-Raça: Druida"],
    "Vampiro": ["Controlador", "Fortalecedor"]
}

class CharacterCreation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.role_ids = {}

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

        class CharacterNameModal(discord.ui.Modal):
            def __init__(self, interaction: discord.Interaction, sistema: str, mesa: str):
                super().__init__(title="Nome do Personagem")
                self.interaction = interaction
                self.sistema = sistema
                self.mesa = mesa
                self.name_input = discord.ui.InputText(
                    label="Nome do personagem",
                    placeholder="Insira aqui",
                    max_length=50
                )
                self.add_item(self.name_input)

            async def callback(self, interaction: discord.Interaction):
                name = self.name_input.value
                embed = discord.Embed(title=name, color=discord.Color.blue())
                embed.add_field(name="Raça", value="Não Selecionada", inline=True)
                embed.add_field(name="Classe", value="Não Selecionada", inline=True)
                view = discord.ui.View()
                select_race = discord.ui.Select(placeholder="Raça", options=[discord.SelectOption(label=race,
                                                value=race) for race in races], custom_id="race")
                view.add_item(select_race)

                async def selection(select_interaction: discord.Interaction):
                    select_type = select_interaction.data["custom_id"]

                    if select_type == "race":
                        race = select_interaction.data["values"][0]
                        embed.set_field_at(0, name="Raça", value=race, inline=True)
                        classes = class_options.get(race, [])
                        select_class = discord.ui.Select(
                            placeholder="Classe",
                            options=[discord.SelectOption(label=cls, value=cls) for cls in classes], custom_id="class")
                        select_class.callback = selection
                        view.clear_items()
                        view.add_item(select_class)
                        await select_interaction.response.edit_message(embed=embed, view=view)
                    elif select_type == "class":
                        char_class = select_interaction.data["values"][0]
                        race = embed.fields[0].value
                        embed.set_field_at(1, name="Classe", value=char_class, inline=True)
                        add_player(select_interaction.user.id, select_interaction.guild.id, self.sistema, name, self.mesa, name, 1, 0, 0, "?", "?", "?", "?", "?", "?", "?", race, char_class, select_interaction.user.avatar.url)
                        view.clear_items()

                        skill_embed = discord.Embed(title="Atributos")
                        skill_embed.add_field(name="", value="**Strength:** 0", inline=False)
                        skill_embed.add_field(name="", value="**Dexterity:** 0", inline=False)
                        skill_embed.add_field(name="", value="**Agility:** 0", inline=False)
                        skill_embed.add_field(name="", value="**Intelligence:** 0", inline=False)
                        skill_embed.add_field(name="", value="**Wisdom:** 0", inline=False)
                        skill_embed.add_field(name="", value="**Social:** 0", inline=False)

                        assign_button = discord.ui.Button(label="Assign skill points 1/2", style=discord.ButtonStyle.primary)

                        async def assign_callback(assign_interaction: discord.Interaction):
                            await assign_interaction.response.send_modal(SkillModal1(skill_embed, assign_interaction.user.id, assign_interaction.guild.id, self.sistema, name, self.mesa))

                        assign_button.callback = assign_callback
                        skill_view = discord.ui.View(timeout=180)
                        skill_view.add_item(assign_button)

                        await select_interaction.response.edit_message(embed=embed, view=view)
                        await select_interaction.followup.send(embed=skill_embed, view=skill_view, ephemeral=True)

                        self.character_creation_completed = True

                        if self.character_creation_completed:
                            await select_interaction.delete_original_response()
                            await asyncio.sleep(8)

                select_race.callback = selection
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        class SkillModal1(discord.ui.Modal):
            def __init__(self, embed, user_id, guild_id, sheet_system, name, mesa):
                self.embed = embed
                self.user_id = user_id
                self.guild_id = guild_id
                self.sheet_system = sheet_system
                self.name = name
                self.mesa = mesa
                super().__init__(title="Assign Skill Points 1/2")

                self.add_item(discord.ui.InputText(label="Strength"))
                self.add_item(discord.ui.InputText(label="Dexterity"))
                self.add_item(discord.ui.InputText(label="Agility"))

            async def callback(self, interaction: discord.Interaction):
                strength = int(self.children[0].value or "0")
                dexterity = int(self.children[1].value or "0")
                agility = int(self.children[2].value or "0")

                self.embed.set_field_at(0, name="", value=f"**Strength:** {strength}", inline=False)
                self.embed.set_field_at(1, name="", value=f"**Dexterity:** {dexterity}", inline=False)
                self.embed.set_field_at(2, name="", value=f"**Agility:** {agility}", inline=False)

                assign_button2 = discord.ui.Button(label="Assign skill points 2/2", style=discord.ButtonStyle.primary)

                async def assign_callback (assign_interaction: discord.Interaction):
                        await assign_interaction.response.send_modal(SkillModal2(
                            self.embed,
                            self.user_id,
                            self.guild_id,
                            self.sheet_system,
                            self.name,
                            self.mesa,
                            strength,
                            dexterity,
                            agility
                        ))

                assign_button2.callback = assign_callback
                view = discord.ui.View()
                view.add_item(assign_button2)

                await interaction.response.edit_message(embed=self.embed, view=view)

        class SkillModal2(discord.ui.Modal):
            def __init__(self, embed, user_id, guild_id, sheet_system, name, mesa, strength, dexterity, agility):
                super().__init__(title="Assign Skill Points 2/2")
                self.embed = embed
                self.user_id = user_id
                self.guild_id = guild_id
                self.sheet_system = sheet_system
                self.mesa = mesa
                self.name = name
                self.strength = strength
                self.dexterity = dexterity
                self.agility = agility

                self.add_item(discord.ui.InputText(label="Intelligence"))
                self.add_item(discord.ui.InputText(label="Wisdom"))
                self.add_item(discord.ui.InputText(label="Social"))

            async def callback(self, interaction: discord.Interaction):
                intelligence = int(self.children[0].value or "0")
                wisdom = int(self.children[1].value or "0")
                social = int(self.children[2].value or "0")

                self.embed.set_field_at(3, name="", value=f"**Intelligence:** {intelligence}", inline=False)
                self.embed.set_field_at(4, name="", value=f"**Wisdom:** {wisdom}", inline=False)
                self.embed.set_field_at(5, name="", value=f"**Social:** {social}", inline=False)

                add_sk_points(self.user_id, self.guild_id, self.sheet_system, self.name, self.mesa, self.strength, self.dexterity, self.agility, intelligence, wisdom, social)

                await interaction.response.edit_message(embed=self.embed, view=None)
                created_message = await interaction.followup.send(f"Você criou **{self.name}**, abra sua ficha com `/ficha`", ephemeral=True)

                self.skill_points_completed = True

                if self.skill_points_completed:
                    try:
                        await interaction.delete_original_response()
                    except discord.NotFound:
                        pass
                    await asyncio.sleep(10)
                    if 'created_message' in locals():
                        await created_message.delete()

        @bot.slash_command(name="criar", description="Cria um novo personagem")
        async def criar(interaction: discord.Interaction,
            sheet_system: discord.Option(str, choices=["Archaos"], description="Selecione o sistema da ficha", required=True), # type: ignore
            mesa: discord.Option(str, description="Qual mesa a ficha pertence", autocomplete=mesa_autocomplete, required=True)): # type: ignore

            modal = CharacterNameModal(interaction, sheet_system, mesa)
            await interaction.response.send_modal(modal)

def setup(bot):
    bot.add_cog(CharacterCreation(bot))
