import os
import json
import sqlite3
import asyncio
import logging
import discord
import aiohttp
from dotenv import load_dotenv
from discord.ext import commands


logging.basicConfig(level=logging.INFO)

load_dotenv()
TOKEN = os.getenv("TOKEN")

MASTER_IDS_FILE = "master_ids.json"

def load_master_ids():
    if os.path.exists(MASTER_IDS_FILE):
        with open(MASTER_IDS_FILE, "r") as f:
            ids = json.load(f)
            return [str(id) for id in ids]
    return []

def save_master_ids(master_ids):
    with open(MASTER_IDS_FILE, "w") as f:
        json.dump([str(id) for id in master_ids], f)

MASTER_IDS = load_master_ids()

intents = discord.Intents.default()
intents.message_content = True

with open("emojis.json", encoding="utf-8") as f:
    config = json.load(f)

custom_emojis = config["custom_emojis"]

bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot {bot.user.name} has connected to Discord!")


def setup_db():
    with sqlite3.connect("players.db") as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS players
        (user_id INTEGER PRIMARY KEY, name TEXT, level INTEGER, hp INTEGER, race TEXT, class TEXT,
            strength INTEGER, constitution INTEGER, intelligence INTEGER, wisdom INTEGER, charisma INTEGER, avatar TEXT)''')

setup_db()

def execute_db(query, params=()):
    with sqlite3.connect("players.db") as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur.fetchall()


def add_player(user_id, name, level, hp, race, char_class, avatar_url):
    execute_db('''REPLACE INTO players (user_id, name, level, hp, race, class, avatar)  VALUES (?, ?, ?, ?, ?, ?, ?)''',
               (user_id, name, level, hp, race, char_class, avatar_url))

def add_sk_points(user_id, strength, constitution, intelligence, wisdom, charisma):
    execute_db('''UPDATE players SET strength = ?, constitution = ?, intelligence = ?, wisdom = ?, charisma = ?
                   WHERE user_id = ?''',
               (strength, constitution, intelligence, wisdom, charisma, user_id))
    
def edit_player(user_id, name, level, hp, race, char_class, strength, constitution, intelligence, wisdom, charisma):
    execute_db('''UPDATE players SET name = ?, level = ?, hp = ?, race = ?, class = ?, strength = ?, constitution = ?, intelligence = ?, wisdom = ?, charisma = ?
                   WHERE user_id = ?''',
               (name, level, hp, race, char_class, strength, constitution, intelligence, wisdom, charisma, user_id))

def get_player(user_id):
    result = execute_db('''SELECT name, level, hp, race, class, strength, constitution, intelligence,
                        wisdom, charisma, avatar FROM players WHERE user_id = ?''', (user_id,))
    return result[0] if result else None


def delete_player(user_id):
    execute_db("DELETE FROM players WHERE user_id = ?", (user_id))

races = {"Humano": 100,"Elfo": 80,"Fada": 60,"Gigante": 150,"Dragonida": 120,"Vampiro": 90,"Bruxa": 70}
classes = {"Guerreiro": 30, "Mago": 10, "Arqueiro": 20, "Ladino": 15, "Paladino": 25}

class SkillModal1(discord.ui.Modal):
    def __init__(self, embed, user_id):
        self.embed = embed
        self.user_id = user_id
        super().__init__(title="Assign Skill Points")

        self.add_item(discord.ui.InputText(label="Strength"))
        self.add_item(discord.ui.InputText(label="Constitution"))
        self.add_item(discord.ui.InputText(label="Intelligence"))
        self.add_item(discord.ui.InputText(label="Wisdom"))
        self.add_item(discord.ui.InputText(label="Charisma"))

        

    async def callback(self, interaction: discord.Interaction):
        logging.info("SkillModal1 submitted")
        strength = int(self.children[0].value or "0")
        constitution = int(self.children[1].value or "0")
        intelligence = int(self.children[2].value or "0")
        wisdom = int(self.children[3].value or "0")
        charisma = int(self.children[4].value or "0")

        self.embed.set_field_at(0, name="", value=f"**Strength:** {strength}", inline=False)
        self.embed.set_field_at(1, name="", value=f"**Constitution:** {constitution}", inline=False)
        self.embed.set_field_at(2, name="", value=f"**Intelligence:** {intelligence}", inline=False)
        self.embed.set_field_at(3, name="", value=f"**Wisdom:** {wisdom}", inline=False)
        self.embed.set_field_at(4, name="", value=f"**Charisma:** {charisma}", inline=False)

        await interaction.response.send_message(embed=self.embed, ephemeral=True)
        add_sk_points(self.user_id, strength, constitution, intelligence, wisdom, charisma)


@bot.slash_command(name="create", description="Cria um novo personagem")
async def criar(interaction: discord.Interaction):
    await interaction.response.send_message("Qual vai ser o nome do seu personagem?")

    if interaction.user and interaction.channel:
        try:
            msg = await bot.wait_for("message", timeout=30.0)
            name = msg.content
        except asyncio.TimeoutError:
            await interaction.followup.send("Você demorou muito tempo para responder!", ephemeral=True)

    embed = discord.Embed(title=name)
    embed.add_field(name="Raça", value="Não Selecionada", inline=True)
    embed.add_field(name="Classe", value="Não Selecionada", inline=True)
    view = discord.ui.View()
    select_race = discord.ui.Select(placeholder="Raça", options=[discord.SelectOption(label=race,
                                    value=race) for race in races], custom_id="race")
    view.add_item(select_race)


    async def selection(interaction: discord.Interaction):
        select_type = interaction.data["custom_id"]
        if select_type == "race":
            race = interaction.data["values"][0]
            embed.set_field_at(0, name="Raça", value=race, inline=True)
            select_class = discord.ui.Select(
                placeholder="Classe",
                options=[discord.SelectOption(label=cls, value=cls) for cls in classes], custom_id="class")
            select_class.callback = selection
            view.clear_items()
            view.add_item(select_class)
            await interaction.response.edit_message(embed=embed, view=view)
        elif select_type == "class":
            char_class = interaction.data["values"][0]
            race = embed.fields[0].value
            embed.set_field_at(1, name="Classe", value=char_class, inline=True)
            level = 1
            avatar_url = interaction.user.avatar.url
            hp = races[race] + classes[char_class]
            add_player(interaction.user.id, name, level, hp, race, char_class, avatar_url)
            view.clear_items()

            skill_embed = discord.Embed(title="Assign Skill Points:")
            skill_embed.add_field(name="", value="**Strength:** 0", inline=False)
            skill_embed.add_field(name="", value="**Constitution:** 0", inline=False)
            skill_embed.add_field(name="", value="**Intelligence:** 0", inline=False)
            skill_embed.add_field(name="", value="**Wisdom:** 0", inline=False)
            skill_embed.add_field(name="", value="**Charisma:** 0", inline=False)

            assign_button = discord.ui.Button(label="Assign skill points", style=discord.ButtonStyle.primary)
            async def assign_callback(interaction: discord.Interaction):
                await interaction.response.send_modal(SkillModal1(skill_embed, interaction.user.id))

            assign_button.callback = assign_callback
            skill_view = discord.ui.View()
            skill_view.add_item(assign_button)

            await interaction.response.edit_message(embed=embed, view=view)
            await interaction.followup.send(embed=skill_embed, view=skill_view, ephemeral=True)

    select_race.callback = selection
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


@bot.slash_command(name="ficha", description="Exibe a ficha de um personagem")
async def ficha(interaction: discord.Interaction, player_argument: discord.User = discord.Option(description="Jogador que você que ver a ficha (apenas mestre da mesa)", required=False)):
    
        if player_argument is not None:
            def clean_user_id(player_argument):
                return player_argument.replace('<@', '').replace('>', '').replace('!', '')
            player_argument = clean_user_id(str(player_argument))

            if get_player(player_argument):
                if str(player_argument) != str(interaction.user.id) and str(interaction.user.id) in MASTER_IDS:
                    player_to_show = get_player(player_argument)
                    await send_character_sheet(interaction, player_to_show)
                if str(player_argument) != str(interaction.user.id) and str(interaction.user.id) not in MASTER_IDS:
                    await interaction.response.send_message("Você não tem permissão para ver a ficha de outros jogadores.")
                if str(player_argument) == str(interaction.user.id):
                    player_to_show = get_player(interaction.user.id)
                    await send_character_sheet(interaction, player_to_show)
            else:
                await interaction.response.send_message("Ficha não encontrada, crie uma com `/create`")
        elif get_player(interaction.user.id):
            player_to_show = get_player(interaction.user.id)
            await send_character_sheet(interaction, player_to_show)
        else:
            await interaction.response.send_message("Ficha não encontrada, crie uma com `/create`")


async def send_character_sheet(interaction, player_to_show):
    level_emoji = custom_emojis["LEVEL"]
    hp_emoji = custom_emojis["HP"]
    race_emoji = custom_emojis["RACE"]
    class_emoji = custom_emojis["CLASS"]

    embed = discord.Embed(title=player_to_show[0], description="")
    embed.set_thumbnail(url=player_to_show[10])
    embed.add_field(name="", value=f"{level_emoji} **Level:** {player_to_show[1]}")
    embed.add_field(name="", value=f"{hp_emoji} **HP:** {player_to_show[2]}", inline=False)
    embed.add_field(name="",value=f"{race_emoji} **Raça:** {player_to_show[3]}", inline=False)
    embed.add_field(name="", value=f"{class_emoji} **Classe:** {player_to_show[4]}", inline=False)
    embed.add_field(name="Atributes:",
                    value=(f'''```Strength: {player_to_show[5]}\nConstitution: {player_to_show[6]}\nIntelligence: {player_to_show[7]}\nWisdom: {player_to_show[8]}\nCharisma: {player_to_show[9]}```'''),
                            inline=False)

    async def edit(interaction: discord.Interaction):
        select_options = [
        discord.SelectOption(label="Nome", value="name"),
        discord.SelectOption(label="Level", value="level"),
        discord.SelectOption(label="HP", value="hp"),
        discord.SelectOption(label="Raça", value="race"),
        discord.SelectOption(label="Classe", value="class")
        ]
        view = discord.ui.View()
        select_edit = discord.ui.Select(placeholder="Edit", options=select_options)
        back_button = discord.ui.Button(label="◀️", style=discord.ButtonStyle.secondary)
        back_button.callback = lambda i: send_character_sheet(i, player_to_show)
        view.add_item(select_edit)
        view.add_item(back_button)
        await interaction.response.edit_message(view=view)

    view = discord.ui.View()
    button_edit = discord.ui.Button(label="Edit", style=discord.ButtonStyle.secondary)
    button_edit.callback = lambda i: edit(i)
    view.add_item(button_edit)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.slash_command(name="delete", description="Apaga a ficha de um personagem", ephemeral=True)
async def apagar(interaction: discord.Interaction):
    player = get_player(interaction.user.id)
    if player:
        delete_player(interaction.user.id)
        await interaction.response.send_message(
            "Sua ficha foi apagada com sucesso.", ephemeral=True
        )
    else:
        await interaction.response.send_message("Não há nada para deletar.", ephemeral=True)


@bot.slash_command(name="roll", description="Rola um dado")
async def roll(interaction: discord.Interaction, dice: str = discord.Option(description="O tipo de dado a ser rolado (ex: 3d20+15)")):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://dicer-api.vercel.app/{dice}") as response:
                if response.status == 200:
                    results = await response.json()
                    embed = discord.Embed(title="Results")
                    print(results)

                    for key, result in results.items(): # 'key' is needed here for unpacking
                        roll_info = result["info"]
                        roll_results = result["results"]
                        mods = result['mods']
                        dices_sum_w_mod = result["dicesSumWMod"]
                        total_mods = sum(mods)
                        embed.set_thumbnail(url="https://i0.wp.com/pawleystudios.com/wp-content/uploads/2020/07/d20-dice-01.png?fit=510%2C510&ssl=1")

                        embed.add_field(
                        name=f"{roll_info}+{mods}:"if mods else f"{roll_info}:",
                        value='\n'.join(f"`{r + total_mods}` ⟵ **({r})** 1d{roll_info.split('d', 1)[1]} + {mods}"
                        if mods else
                        f"`[{r}]` ⟵ 1d{roll_info.split('d', 1)[1]}" for r in roll_results),
                        inline=False)
                        embed.add_field(name="", value=f"**{str(roll_results)[1:-1]}** = `[{dices_sum_w_mod}]`",
                        inline=True)

                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message("Formato invalido.")
    except ValueError:
        await interaction.response.send_message("Houve um erro ao rolar o dado.")

@bot.slash_command(name="add_master", description="Adiciona um novo mestre")
@commands.has_permissions(administrator=True)
async def add_master(interaction: discord.Interaction, user: discord.User):
    user_id_str = str(user.id)
    if user_id_str not in MASTER_IDS:
        MASTER_IDS.append(user_id_str)
        save_master_ids(MASTER_IDS)
        await interaction.response.send_message(f"O usuário {user} foi adicionado como mestre.")
    else:
        await interaction.response.send_message("Esse usuário já é um mestre.")

@bot.slash_command(name="remove_master", description="Remove um mestre")
@commands.has_permissions(administrator=True)
async def remove_master(interaction: discord.Interaction, user: discord.User):
    user_id_str = str(user.id)
    if user_id_str in MASTER_IDS:
        MASTER_IDS.remove(user_id_str)
        save_master_ids(MASTER_IDS)
        await interaction.response.send_message(f"O usuário {user} foi removido como mestre.")
    else:
        await interaction.response.send_message("Esse usuário não é um mestre.")


class ImageModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Atualizar Imagem do Personagem")
        self.add_item(discord.ui.InputText(label="Nova URL da Imagem", style=discord.InputTextStyle.short, placeholder="Cole a nova URL da imagem aqui"))

    async def callback(self, interaction: discord.Interaction):
        player = get_player(interaction.user.id)
        new_avatar_url = self.children[0].value.strip()
        # Verifica se o jogador possui uma ficha
        player = get_player(interaction.user.id)
        if player:
            # Atualiza a URL da imagem do personagem
            add_player(interaction.user.id, player[0], player[1], player[2], player[3], player[4], new_avatar_url)
            add_sk_points(interaction.user.id, player[5], player[6], player[7], player[8], player[9])
            await interaction.response.send_message("A imagem do personagem foi atualizada com sucesso.", ephemeral=True)
        else:
            await interaction.response.send_message("Você não tem uma ficha para atualizar.", ephemeral=True)


@bot.slash_command(name="character_image", description="Muda a foto de um personagem existente")
async def change_img(interaction: discord.Interaction):
    await interaction.response.send_modal(ImageModal())
    
bot.run(TOKEN)
