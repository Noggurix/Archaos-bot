import sqlite3
from datetime import datetime

def execute_query(query, params=(), fetch=False):
    with sqlite3.connect("characters.db") as conn:
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()
        return cur.fetchall() if fetch else None

def setup_db():
    execute_query('''CREATE TABLE IF NOT EXISTS characters
    (user_id INTEGER, guild_id INTEGER, sheet_system TEXT, character TEXT, table_id TEXT, name TEXT, age INTEGER, level INTEGER, hp INTEGER, mp INTEGER, race TEXT, class TEXT, magic TEXT, skills TEXT, worship TEXT, submission TEXT, inventory TEXT, history TEXT,
        strength INTEGER, dexterity INTEGER, agility INTEGER, intelligence INTEGER, wisdom INTEGER, social INTEGER,
            p1 TEXT, p2 TEXT, p3 TEXT, p4 TEXT, p5 TEXT, p6 TEXT, p7 TEXT, avatar TEXT, PRIMARY KEY (user_id, guild_id, sheet_system, character, table_id))''', fetch=False)

    execute_query('''CREATE TABLE IF NOT EXISTS images (
        character TEXT NOT NULL, 
        url TEXT NOT NULL, 
        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        description TEXT, 
        PRIMARY KEY (character, url),
        FOREIGN KEY (character) REFERENCES characters(character) ON DELETE CASCADE
    )''', fetch=False)


setup_db()

def add_player(user_id, guild_id, sheet_system, character, table_id, name, level, hp, mp, p1, p2, p3, p4, p5, p6, p7, race, _class, avatar_url):
    execute_query('''REPLACE INTO characters (user_id, guild_id, sheet_system, character, table_id, name, level, hp, mp, p1, p2, p3, p4, p5, p6, p7, race, class, avatar) 
                  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (user_id, guild_id, sheet_system, character, table_id, name, level, hp, mp, p1, p2, p3, p4, p5, p6, p7, race, _class, avatar_url), fetch=False)

def add_sk_points(user_id, guild_id, sheet_system, character, table_id, strength, dexterity, agility, intelligence, wisdom, social):
    execute_query('''UPDATE characters SET strength = ?, dexterity = ?, agility = ?, intelligence = ?, wisdom = ?, social = ?
                  WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?''',
               (strength, dexterity, agility, intelligence, wisdom, social, user_id, guild_id, sheet_system, character, table_id), fetch=False)

def edit_player(user_id, guild_id, sheet_system, character, table_id, name, age, level, hp, mp, race, _class, magic, skills, worship, submission, strength, dexterity, agility, intelligence, wisdom, social, avatar):
    old_name = execute_query(
        "SELECT name FROM characters WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?",
        (user_id, guild_id, sheet_system, character, table_id), 
        fetch=True
    )
    old_name = old_name[0][0] if old_name else None

    execute_query(
        '''UPDATE characters SET name = ?, age = ?, level = ?, hp = ?, mp = ?, race = ?, class = ?, magic = ?, skills = ?, worship = ?, 
        submission = ?, strength = ?, dexterity = ?, agility = ?, intelligence = ?, wisdom = ?, 
        social = ?, avatar = ? WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?''',
        (name, age, level, hp, mp, race, _class, magic, skills, worship, submission, strength, dexterity, 
         agility, intelligence, wisdom, social, avatar, user_id, guild_id, sheet_system, character, table_id), 
        fetch=False
    )

    if old_name and old_name != name:
        update_character_name_in_images(old_name, name)

def update_proficiency(user_id, guild_id, sheet_system, character, table_id, p1, p2, p3, p4, p5, p6, p7):
    execute_query('''UPDATE characters SET p1 = ?, p2 = ?, p3 = ?, p4 = ?, p5 = ?, p6 = ?, p7 = ?
                  WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?''',
               (p1, p2, p3, p4, p5, p6, p7, user_id, guild_id, sheet_system, character, table_id), fetch=False)

def get_player(user_id, guild_id, sheet_system, character, table_id):
    result = execute_query('''SELECT name, age, level, hp, mp, race, class, magic, skills, worship, submission, inventory, history,
                        strength, dexterity, agility, intelligence, wisdom, social, p1, p2, p3, p4, p5, p6, p7, avatar 
                        FROM characters WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?''', 
                        (user_id, guild_id, sheet_system, character, table_id), fetch=True)
    return result[0] if result else None

def delete_player(user_id, guild_id, sheet_system, character, table_id):
    execute_query("DELETE FROM characters WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?", 
                  (user_id, guild_id, sheet_system, character, table_id), fetch=False)

def update_hp_mp(user_id, guild_id, sheet_system, character, table_id, hp, mp):
    execute_query('''UPDATE characters SET hp = ?, mp = ? WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?''',
               (hp, mp, user_id, guild_id, sheet_system, character, table_id), fetch=False)

def update_inventory(user_id, guild_id, sheet_system, character, table_id, item, action):
    player = get_player(user_id, guild_id, sheet_system, character, table_id)
    current_inventory = player[11] if player else ""

    inventory_list = current_inventory.split(", ") if current_inventory else []

    if action == "add":
        if item not in inventory_list:
            inventory_list.append(item)
    elif action == "remove":
        if item in inventory_list:
            inventory_list.remove(item)

    new_inventory = ", ".join(inventory_list)
    execute_query('''UPDATE characters SET inventory = ? 
                  WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?''',
               (new_inventory, user_id, guild_id, sheet_system, character, table_id), fetch=False)

def update_history(user_id, guild_id, sheet_system, character, table_id, history):
    execute_query('''UPDATE characters SET history = ? WHERE user_id = ? AND guild_id = ? AND sheet_system = ? AND character = ? AND table_id = ?''',
               (history, user_id, guild_id, sheet_system, character, table_id), fetch=False)

def fetch_characters_from_db(user_id, guild_id):
    query = '''
        SELECT name, sheet_system, table_id, character
        FROM characters 
        WHERE user_id = ? AND guild_id = ?
    '''
    return [{"name": row[0], "sheet_system": row[1], "table_id": row[2], "character": row[3]} for row in execute_query(query, (user_id, guild_id), fetch=True)] 

def fetch_characters(user_id, guild_id):
    return [row[0] for row in execute_query("SELECT name FROM characters WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), fetch=True)]

def add_images_to_album(selected_char, image_url, description=None):
    local_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    execute_query("INSERT OR IGNORE INTO images (character, url, description, added_date) VALUES (?, ?, ?, ?)", 
                  (selected_char, image_url, description, local_time), fetch=False)

def pick_character_url_images(selected_char):
    return execute_query("SELECT url FROM images WHERE character = ?", (selected_char,), fetch=True)

def urls_in_row(selected_char):
    return execute_query("SELECT url, added_date, description FROM images WHERE character = ? ORDER BY added_date ASC;", 
                         (selected_char,), fetch=True)

def autocomplete_character_with_images(guild_id):
    return execute_query("SELECT DISTINCT name, user_id FROM characters WHERE guild_id = ?", (guild_id,), fetch=True)

def remove_image(selected_char, selected_url):
    execute_query("DELETE FROM images WHERE character = ? AND url = ?", 
                  (selected_char, selected_url), fetch=False)
    
def update_character_name_in_images(old_name, new_name):
    execute_query(
        "UPDATE images SET character = ? WHERE character = ?", 
        (new_name, old_name), 
        fetch=False
    )
