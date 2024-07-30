import os
from dotenv import load_dotenv
import sqlite3
import discord
import asyncio
from discord import app_commands
from discord.ext import commands


load_dotenv()


TOKEN = os.getenv('TOKEN')

intents = discord.Intents.default()
intents.message_content = True

class MyClient(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs, command_prefix="/", intents=intents)

    async def setup_hook(self):
        # Sincronizar comandos de barra
        await self.tree.sync()

    async def on_ready(self):
        print(f'Bot {self.user.name} has connected to Discord!')

    async def on_message(self, message):
        # Ignorar mensagens do próprio bot
        if message.author == self.user:
            return

# Instanciar o bot
bot = MyClient()

#Configurar banco de dados
def setup_db():
    conn = sqlite3.connect('players.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players
              (user_id INTEGER PRIMARY KEY, name TEXT, level INTEGER, hp INTEGER, race TEXT, class TEXT)''')
    conn.commit()
    conn.close()

setup_db()

#Adicionar player ao banco de dados
def add_player(user_id, name, level, hp, race, char_class):
    conn = sqlite3.connect('players.db')
    c = conn.cursor()
    c.execute('REPLACE INTO players (user_id, name, level, hp, race, class) VALUES (?, ?, ?, ?, ?, ?)', 
              (user_id, name, level, hp, race, char_class))
    conn.commit()
    conn.close()

#Obter informações do jogador do banco de dados
def get_player(user_id):
    conn = sqlite3.connect('players.db')
    c =conn.cursor ()
    c.execute('SELECT name, level, hp, race, class FROM players WHERE user_id = ?', (user_id,))
    player = c. fetchone()
    conn.close()
    return player

def delete_player(user_id):
    conn = sqlite3.connect('players.db')
    c = conn.cursor()
    c.execute('DELETE FROM players WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

#Valores de raças e classes
races = {'Humano': 100,'Elfo': 80,'Fada': 60,'Gigante': 150,'Dragonida': 120,'Vampiro': 90,'Bruxa': 70}
classes = {'Guerreiro': 30,'Mago': 10,'Arqueiro': 20,'Ladino': 15,'Paladino': 25}

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
            options_list = [discord.SelectOption(label=opt, value=opt) for opt in options.keys()]
            select = discord.ui.Select(placeholder=f"Escolha sua {select_type}", options=options_list)
            return select
       
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
                embed.description = (f"**{name}**")
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
    embed.add_field(name="Raça",  value="Não Selecionada", inline=True)
    embed.add_field(name="Classe", value="Não Selecionada", inline=True)
    await interaction.followup.send(embed=embed, view=view)

@bot.tree.command(name='ficha', description='Mostra a ficha do personagem')
async def ficha(interaction: discord.Interaction):
    user_id = interaction.user.id
    player = get_player(user_id)
    if player:
        embed = discord.Embed(title="Ficha:")
        embed.set_author(name=interaction.user.name, icon_url=interaction.user.avatar.url)
        embed.add_field(name="Nome:",  value=player[0], inline=False)
        embed.add_field(name="Nivel:", value=player[1], inline=False)
        embed.add_field(name="Vida:", value=player[2], inline=False)
        embed.add_field(name="Raça:", value=player[3], inline=False)
        embed.add_field(name="Classe:", value=player[4], inline=False)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message('Você não tem uma ficha, crie uma com **/criar**')

@bot.tree.command(name='apagar', description='Apaga a ficha do personagem')
async def apagar(interaction: discord.Interaction):
    user_id = interaction.user.id
    delete_player(user_id)
    await interaction.response.send_message('Sua ficha foi apagada com sucesso.')
    
bot.run(TOKEN)