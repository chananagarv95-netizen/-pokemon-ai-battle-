import csv
import os

DATASET_FILE = "battle_dataset.csv"
CURRENT_BATTLE_ID = 0

POKEMON_ID_MAP = {
    "charizard": 1,
    "blastoise": 2,
    "venusaur": 3,
    "pikachu": 4,
    "gengar": 5,
    "snorlax": 6,
    "donphan": 7,
    "gyarados": 8,
    "alakazam": 9,
    "breloom": 10,
    "arcanine": 11,
    "tyranitar": 12,
    "dragonite": 13,
    "roserade": 14,
}

# ✅ FIXED CLEANER (important)
def clean_name(name):
    name = str(name).lower().strip()

    # normalize mega forms
    if "charizard" in name:
        return "charizard"

    if "gengar" in name:
        return "gengar"

    # general cleaning
    name = name.replace("mega", "")
    name = name.replace("-", "")

    return name


# Create CSV if not exists
if not os.path.exists(DATASET_FILE):
    with open(DATASET_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "my_hp",
            "opp_hp",
            "my_speed",
            "opp_speed",
            "my_atk",
            "opp_def",
            "my_id",
            "opp_id",
            "move",
            "damage",
            "priority",
            "winner"
        ])


def log_dataset(my_pkmn, opp_pkmn, move, dmg, priority, winner, battle_id):
    try:
        # ✅ DEBUG (correct place)
        print("MY:", my_pkmn.species, "->", clean_name(my_pkmn.species))
        print("OPP:", opp_pkmn.species, "->", clean_name(opp_pkmn.species))

        my_id = POKEMON_ID_MAP.get(clean_name(my_pkmn.species), 0)
        opp_id = POKEMON_ID_MAP.get(clean_name(opp_pkmn.species), 0)

        # ✅ SAFETY CHECK (VERY IMPORTANT)
        if my_id == 0 or opp_id == 0:
            print("⚠️ UNKNOWN POKEMON:", my_pkmn.species, opp_pkmn.species)
            return

        with open(DATASET_FILE, "a", newline="") as f:
            writer = csv.writer(f)

            writer.writerow([
                battle_id,
                round(my_pkmn.current_hp_fraction, 3),
                round(opp_pkmn.current_hp_fraction, 3),
                my_pkmn.stats.get("spe", 0),
                opp_pkmn.stats.get("spe", 0),
                my_pkmn.stats.get("atk", 0),
                opp_pkmn.stats.get("def", 0),
                my_id,
                opp_id,
                move,
                round(dmg, 2),
                priority,
                winner
            ])

    except Exception as e:
        print("Logging error:", e)