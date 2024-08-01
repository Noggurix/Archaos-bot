import os
import json
import sqlite3
import discord
import asyncio
import aiohttp
import re
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("TOKEN")
DICE_url = os.getenv("DICE_url")

intents = discord.Intents.default()
intents.message_content = True

with open("emojis.json") as f:
    config = json.load(f)

custom_emojis = config["custom_emojis"]

bot = commands.Bot(command_prefix="/", intents=intents)


@bot.event
async def on_ready():
    print(f"Bot {bot.user.name} has connected to Discord!")


def setup_db():
    with sqlite3.connect("players.db") as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS players
                        (user_id INTEGER PRIMARY KEY, name TEXT, level INTEGER, hp INTEGER, race TEXT, class TEXT)""")


setup_db()


def execute_db(query, params=()):
    with sqlite3.connect("players.db") as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        return cur.fetchall()


def add_player(user_id, name, level, hp, race, char_class):
    execute_db(
        "REPLACE INTO players (user_id, name, level, hp, race, class) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, level, hp, race, char_class),
    )


def get_player(user_id):
    result = execute_db(
        "SELECT name, level, hp, race, class FROM players WHERE user_id = ?", (
            user_id,)
    )
    return result[0] if result else None


def delete_player(user_id):
    execute_db("DELETE FROM players WHERE user_id = ?", (user_id,))


races = {
    "Humano": 100,
    "Elfo": 80,
    "Fada": 60,
    "Gigante": 150,
    "Dragonida": 120,
    "Vampiro": 90,
    "Bruxa": 70,
}
classes = {"Guerreiro": 30, "Mago": 10,
           "Arqueiro": 20, "Ladino": 15, "Paladino": 25}


@bot.slash_command(name="create", description="Cria um novo personagem")
async def criar(interaction: discord.Interaction):
    await interaction.response.send_message("Qual vai ser o nome do seu personagem?")

    if interaction.user and interaction.channel:
        try:
            msg = await bot.wait_for("message", timeout=30.0)
            name = msg.content
        except asyncio.TimeoutError:
            await interaction.followup.send("Você demorou muito tempo para responder!")

    embed = discord.Embed(title=name)
    embed.add_field(name="Raça", value="Não Selecionada", inline=True)
    embed.add_field(name="Classe", value="Não Selecionada", inline=True)
    view = discord.ui.View()
    select_race = discord.ui.Select(
        placeholder="Raça",
        options=[discord.SelectOption(label=race, value=race)
                 for race in races],
        custom_id="race",
    )
    view.add_item(select_race)

    async def select_callback(interaction: discord.Interaction):
        select_type = interaction.data["custom_id"]
        if select_type == "race":
            race = interaction.data["values"][0]
            embed.set_field_at(0, name="Raça", value=race, inline=True)
            select_class = discord.ui.Select(
                placeholder="Classe",
                options=[discord.SelectOption(
                    label=cls, value=cls) for cls in classes],
                custom_id="class",
            )
            select_class.callback = select_callback
            view.clear_items()
            view.add_item(select_class)
        elif select_type == "class":
            char_class = interaction.data["values"][0]
            race = embed.fields[0].value
            embed.set_field_at(1, name="Classe", value=char_class, inline=True)
            embed.title = "Ficha criada!"
            embed.description = f"### {name}"
            level = 1
            hp = races[race] + classes[char_class]
            add_player(interaction.user.id, name, level, hp, race, char_class)
            view.clear_items()
        await interaction.response.defer()
        await interaction.edit_original_response(embed=embed, view=view)

    select_race.callback = select_callback
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


@bot.slash_command(name="ficha", description="Exibe a ficha de um personagem")
async def ficha(interaction: discord.Interaction):
    level_emoji = custom_emojis["LEVEL"]
    HP_emoji = custom_emojis["HP"]
    race_emoji = custom_emojis["RACE"]
    class_emoji = custom_emojis["CLASS"]
    player = get_player(interaction.user.id)
    if player:
        embed = discord.Embed(title=player[0], description="")
        embed.set_thumbnail(url=interaction.user.avatar.url)
        embed.add_field(name="", value=f"{level_emoji} **Level:** {player[1]}")
        embed.add_field(
            name="",
            value=f"{
                HP_emoji} **HP:** {player[2]}",
            inline=False,
        )
        embed.add_field(
            name="",
            value=f"{
                race_emoji} **Raça:** {player[3]}",
            inline=False,
        )
        embed.add_field(
            name="",
            value=f"{
                class_emoji} **Classe:** {player[4]}",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(
            "Ficha não encontrada, crie uma com `/create`"
        )


@bot.slash_command(name="delete", description="Apaga a ficha de um personagem")
async def apagar(interaction: discord.Interaction):
    player = get_player(interaction.user.id)
    if player:
        delete_player(interaction.user.id)
        await interaction.response.send_message(
            "Sua ficha foi apagada com sucesso.", ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "Não há nada para deletar.", ephemeral=True
        )


@bot.slash_command(name="roll", description="Rola um dado")
async def roll(
    interaction: discord.Interaction,
    dice: str = discord.Option(
        description="O tipo de dado a ser rolado (ex: 3d20+15)"),
):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://dicer-api.vercel.app/{dice}") as response:
                if response.status == 200:
                    results = await response.json()
                    embed = discord.Embed(title="Results:")

                    for result in results:
                        roll_info = result["info"]
                        roll_results = result["results"]
                        mods = result["mods"]
                        dices_sum_w_mod = result["dicesSumWMod"]
                        embed.set_thumbnail(url=DICE_url)
                        embed.add_field(
                            name="",
                            value=f'\n `({
                                dices_sum_w_mod})` **{str(roll_results)[1:-1]}** <- {roll_info} + {"+ ".join(mods)}',
                        )

                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.response.send_message("Formato invalido.")

    except Exception as error:
        interaction.response.send_message("Houve um erro ao rolar o dado.")


bot.run(TOKEN)
