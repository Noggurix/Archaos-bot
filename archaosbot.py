import os
import sqlite3
import discord
import asyncio
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv('TOKEN')

intents = discord.Intents.default()
intents.message_content = True

class MyClient(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs, command_prefix="/", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f'Bot {self.user.name} has connected to Discord!')

bot = MyClient()

def setup_db():
    with sqlite3.connect('players.db') as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS players
                        (user_id INTEGER PRIMARY KEY, name TEXT, level INTEGER, hp INTEGER, race TEXT, class TEXT)''')

setup_db()

def execute_db(query, params=()):
    with sqlite3.connect('players.db') as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()

def add_player(user_id, name, level, hp, race, char_class):
    execute_db('REPLACE INTO players (user_id, name, level, hp, race, class) VALUES (?, ?, ?, ?, ?, ?)',
               (user_id, name, level, hp, race, char_class))

def get_player(user_id):
    result = execute_db('SELECT name, level, hp, race, class FROM players WHERE user_id = ?', (user_id,))
    return result[0] if result else None

def delete_player(user_id):
    execute_db('DELETE FROM players WHERE user_id = ?', (user_id,))

races = {'Humano': 100, 'Elfo': 80, 'Fada': 60, 'Gigante': 150, 'Dragonida': 120, 'Vampiro': 90, 'Bruxa': 70}
classes = {'Guerreiro': 30, 'Mago': 10, 'Arqueiro': 20, 'Ladino': 15, 'Paladino': 25}

@bot.tree.command(name='criar', description='Cria um novo personagem')
async def criar(interaction: discord.Interaction):
    await interaction.response.send_message("Qual vai ser o nome do seu personagem?")

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel
    
    try:
        msg = await bot.wait_for('message', check=check, timeout=60.0)
        name = msg.content
    except asyncio.TimeoutError:
        await interaction.followup.send('Você demorou muito tempo para responder!')
        return

    def create_select_menu(select_type, options):
        return discord.ui.Select(
            placeholder=f"Escolha sua {select_type}",
            options=[discord.SelectOption(label=opt, value=opt) for opt in options.keys()]
        )

    async def select_callback(interaction, select_type):
        await interaction.response.defer()
        choice = interaction.data['values'][0]
        if select_type == "Raça":
            race = choice
            embed.set_field_at(0, name="Raça", value=race, inline=True)
            select_class = create_select_menu("Classe", classes)
            select_class.callback = lambda i: asyncio.create_task(select_callback(i, "Classe"))
            embed.description = "Selecione uma classe"
            view.clear_items()
            view.add_item(select_class)
            await interaction.message.edit(embed=embed, view=view)
        elif select_type == "Classe":
            char_class = choice
            race = embed.fields[0].value
            embed.set_field_at(1, name="Classe", value=char_class, inline=True)
            embed.title = "Ficha criada!"
            embed.description = f"**{name}**"
            level = 1
            hp = races[race] + classes[char_class]
            add_player(interaction.user.id, name, level, hp, race, char_class)
            view.clear_items()
            await interaction.message.edit(embed=embed, view=view)

    view = discord.ui.View()
    select_race = create_select_menu("Raça", races)
    select_race.callback = lambda i: asyncio.create_task(select_callback(i, "Raça"))
    view.add_item(select_race)

    embed = discord.Embed(title=name, description="Selecione uma raça e uma classe.")
    embed.add_field(name="Raça", value="Não Selecionada", inline=True)
    embed.add_field(name="Classe", value="Não Selecionada", inline=True)
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name='ficha', description='Mostra a ficha do personagem')
async def ficha(interaction: discord.Interaction):
    player = get_player(interaction.user.id)
    if player:
        embed = discord.Embed(title="Ficha:")
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
        embed.add_field(name="Nome:", value=player[0], inline=False)
        embed.add_field(name="Nivel:", value=player[1], inline=False)
        embed.add_field(name="Vida:", value=player[2], inline=False)
        embed.add_field(name="Raça:", value=player[3], inline=False)
        embed.add_field(name="Classe:", value=player[4], inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message('Você não tem uma ficha, crie uma com **/criar**')

@bot.tree.command(name='apagar', description='Apaga a ficha do personagem')
async def apagar(interaction: discord.Interaction):
    delete_player(interaction.user.id)
    await interaction.response.send_message('Sua ficha foi apagada com sucesso.')

bot.run(TOKEN)