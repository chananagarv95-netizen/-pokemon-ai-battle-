import csv
import os
from dataset_logger import log_dataset, POKEMON_ID_MAP, clean_name
DATASET_FILE = "battle_dataset.csv"

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
import sys
import numpy as np
import math
from include import (
    Ply, RPly, CHARIZARD, BLASTOISE, VENUSAUR, PIKACHU,
    Battle, BattleOrder, TEAMS, valid_move, get_pokemon, calc_damage
)
from poke_env.environment.move import Move
from poke_env.environment.pokemon import Pokemon
from poke_env.environment.status import Status


def choose_move_strongest(battle):
    if battle is None:
        return None

    all_moves = Ply.possible_moves(battle)
    if not all_moves:
        return None

    if battle.active_pokemon is None:
        return all_moves[0]

    if battle.opponent_active_pokemon is None:
        return all_moves[0]

    my_pkmn = battle.active_pokemon
    enem_pkmn = get_pokemon(battle.opponent_active_pokemon)

    try:
        damages = calc_damage(my_pkmn, enem_pkmn)
    except:
        return all_moves[0]

    scores = []
    for move in all_moves:
        if isinstance(move.order, Move):
            scores.append(np.mean(damages.get(move.order.id, [0])))
        else:
            scores.append(-1)

    return all_moves[int(np.argmax(scores))]
class AIPly1(RPly):
    TEAM = CHARIZARD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dataset = []  # dataset storage

    # ================= TEAM PREVIEW =================
    def teampreview(self, battle):
        return self.random_teampreview(battle)

    # ================= MAIN MOVE ENGINE =================
    def choose_move(self, battle):

        # ===== ULTRA HARD ENGINE SAFETY =====
        if battle is None:
            return Ply.choose_default_move()

        # ===== WAIT / SYNC PHASE =====
        if getattr(battle, "_wait", False):
            return Ply.choose_default_move()

        # ===== TEAM PREVIEW =====
        if getattr(battle, "_teampreview", False):
            return self.random_teampreview(battle)

        # Safely fetch moves AFTER preview/sync
        all_moves = Ply.possible_moves(battle)

        if not all_moves:
            return Ply.choose_default_move()

        # ================= FORCE SWITCH =================
        if battle.force_switch or getattr(battle, "_force_switch", False):
            switches = [
                m for m in all_moves
                if isinstance(m.order, Pokemon)
                and m.order.current_hp_fraction > 0
            ]
            return switches[0] if switches else Ply.choose_default_move()

        # ================= SAFE STATE FETCH =================
        my_pkmn = battle.active_pokemon
        if my_pkmn is None or my_pkmn.current_hp_fraction == 0:
            return Ply.choose_default_move()

        if battle.opponent_active_pokemon is None:
            return all_moves[0]

        opp_pkmn = get_pokemon(battle.opponent_active_pokemon)

        # ================= DAMAGE CALC =================
        try:
            my_hp = max(1, int(my_pkmn.stats["hp"] * my_pkmn.current_hp_fraction))
            opp_hp = max(1, int(opp_pkmn.stats["hp"] * opp_pkmn.current_hp_fraction))

            my_damages = calc_damage(my_pkmn, opp_pkmn)
            opp_damages = calc_damage(opp_pkmn, my_pkmn)

            my_speed = my_pkmn.stats.get("spe", 0)
            opp_speed = opp_pkmn.stats.get("spe", 0)
            i_am_faster = my_speed >= opp_speed

            max_my_damage = max((max(d) for d in my_damages.values()), default=0)
            min_my_damage = max((min(d) for d in my_damages.values()), default=0)
            max_opp_damage = max((max(d) for d in opp_damages.values()), default=0)

        except:
            return choose_move_strongest(battle)

        # ================= FIND BEST ATTACK =================
        best_attack = None
        best_score = -1
        priority_ko = None

        for m in all_moves:
            if isinstance(m.order, Move):
                dmg = np.mean(my_damages.get(m.order.id, [0]))
                acc = getattr(m.order, "accuracy", 100) or 100
                priority = getattr(m.order, "priority", 0)

                score = dmg * (acc / 100)

                if score > best_score:
                    best_score = score
                    best_attack = m

                if min(my_damages.get(m.order.id, [0])) >= opp_hp and priority > 0:
                    priority_ko = m

        if not best_attack:
            return all_moves[0]

        # ================= DECISION RULES =================
        if priority_ko:
            chosen = priority_ko
        elif min_my_damage >= opp_hp:
            if i_am_faster or max_opp_damage < my_hp:
                chosen = best_attack
            else:
                chosen = best_attack
        elif my_pkmn.current_hp_fraction < 0.18 and not i_am_faster:
            chosen = best_attack
        else:
            chosen = best_attack

        # ================= STRATEGIC SWITCH =================
        can_switch = any(isinstance(m.order, Pokemon) for m in all_moves)

        losing_badly = (
            max_opp_damage > my_hp * 0.6
            and max_my_damage < opp_hp * 0.45
        )

        about_to_die = max_opp_damage >= my_hp

        if (
            can_switch
            and not battle.trapped
            and my_pkmn.current_hp_fraction > 0.25
            and (losing_badly or about_to_die)
        ):
            switches = [m for m in all_moves if isinstance(m.order, Pokemon)]

            best_switch = None
            best_trade = max_my_damage - (max_opp_damage * 0.6)

            for s in switches:
                if s.order.current_hp_fraction < 0.30:
                    continue

                try:
                    incoming = calc_damage(opp_pkmn, s.order)
                    outgoing = calc_damage(s.order, opp_pkmn)

                    worst_in = max((max(d) for d in incoming.values()), default=9999)
                    best_out = max((min(d) for d in outgoing.values()), default=0)

                    trade_score = best_out - (worst_in * 0.6)

                    if (
                        s.order.species.lower() == "snorlax"
                        and opp_pkmn.stats["spa"] > opp_pkmn.stats["atk"]
                    ):
                        trade_score += 30

                    if trade_score > best_trade + 12:
                        best_trade = trade_score
                        best_switch = s

                except:
                    continue

            if best_switch:
                chosen = best_switch

        # ================= DATASET COLLECTION (UNCHANGED LOGIC) =================
        try:
            action_type = "attack"
            move_id = "none"

            if isinstance(chosen.order, Move):
                move_id = chosen.order.id
                action_type = "attack"
            else:
                action_type = "switch"

            row = {
                "my_hp": float(my_pkmn.current_hp_fraction),
                "opp_hp": float(opp_pkmn.current_hp_fraction),
                "my_speed": my_speed,
                "opp_speed": opp_speed,
                "faster": int(i_am_faster),
                "max_my_damage": float(max_my_damage),
                "max_opp_damage": float(max_opp_damage),
                "action_type": action_type,
                "move_id": move_id,
            }

            if len(self.dataset) == 0 or self.dataset[-1] != row:
                self.dataset.append(row)

        except:
            pass

        return chosen

    def save_dataset(self, filename="dataset.csv"):
        import csv
        import os
        import random

        if len(self.dataset) == 0:
            print("No data to save")
            return

        file_exists = os.path.isfile(filename)

        with open(filename, "a", newline="") as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow(
                    [
                        "my_hp",
                        "opp_hp",
                        "my_speed",
                        "opp_speed",
                        "faster",
                        "max_my_damage",
                        "max_opp_damage",
                        "action_type",
                        "move_id",
                        "winner",
                    ]
                )

            # ✅ Compute winrate of this run
            valid_battles = [b for b in self.battles.values() if b and b.won is not None]

            if len(valid_battles) == 0:
                winrate = 0.5
            else:
                wins = sum(1 for b in valid_battles if b.won)
                winrate = wins / len(valid_battles)

            # ✅ Assign winner probabilistically (FIXED)
            for row in self.dataset:
                winner = 1 if random.random() < winrate else 0

                writer.writerow(
                    [
                        row["my_hp"],
                        row["opp_hp"],
                        row["my_speed"],
                        row["opp_speed"],
                        row["faster"],
                        row["max_my_damage"],
                        row["max_opp_damage"],
                        row["action_type"],
                        row["move_id"],
                        winner,
                    ]
                )

        print(f"Appended {len(self.dataset)} rows to {filename} (winrate={round(winrate, 2)})")
class AIPly2(RPly):
    TEAM = CHARIZARD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # --- MEMORY TRACKER ---
        self.enemy_setup_boosts = 0       
        self.last_enemy_hp = 1.0          
        self.last_enemy_species = ""      
        self.spore_used_on = set()        

    def teampreview(self, battle):
        self.enemy_setup_boosts = 0 
        self.last_enemy_hp = 1.0
        self.last_enemy_species = ""
        self.spore_used_on = set()

        opp_species = [str(mon.species).lower() for mon in battle.opponent_team.values()]
        lead_idx = 1  

        # 1. Dragonite on enemy team → Lead Donphan (Ice Shard revenge killer)
        if any("dragonite" in s for s in opp_species):
            for i, mon in enumerate(battle.team.values()):
                if "donphan" in str(mon.species).lower():
                    lead_idx = i + 1
                    break
        # 2. Default → ALWAYS Lead Gengar (Fast scout, disrupts enemy)
        else:
            for i, mon in enumerate(battle.team.values()):
                if "gengar" in str(mon.species).lower():
                    lead_idx = i + 1
                    break

        order = [lead_idx] + [x for x in range(1, 7) if x != lead_idx]
        return "/team " + "".join(map(str, order))

    def choose_move(self, battle):

    # ===== SAFETY FIRST =====
        if battle is None:
            return Ply.choose_default_move()

        if battle.active_pokemon is None or battle.opponent_active_pokemon is None:
            return Ply.choose_default_move()

        all_moves = Ply.possible_moves(battle)
        if not all_moves:
            return Ply.choose_default_move()

    # ===== NOW SAFE TO USE =====
        my_pkmn = battle.active_pokemon
        enem_pkmn = get_pokemon(battle.opponent_active_pokemon)

        if enem_pkmn is None:
            return super().choose_move(battle)
    


        enem_max_hp = enem_pkmn.stats["hp"]
        enem_hp = math.floor(enem_max_hp * enem_pkmn.current_hp_fraction)

        my_max_hp = my_pkmn.stats["hp"]
        my_hp = math.floor(my_max_hp * my_pkmn.current_hp_fraction)

        my_species = str(my_pkmn.species).lower()
        current_enemy_species = str(enem_pkmn.species).lower()

        enemy_meta = {
            "blastoise": ["hydropump", "surf", "icebeam", "darkpulse"],
            "charizard": ["fireblast", "flamethrower", "thunderpunch", "earthquake"],
            "gyarados": ["waterfall", "earthquake", "crunch", "taunt"],
            "pikachu": ["thunderbolt", "fakeout", "surf", "voltswitch"],
            "roserade": ["sludgebomb", "gigadrain", "shadowball", "toxic"],
            "alakazam": ["psychic", "shadowball", "taunt", "nastyplot"],
            "donphan": ["earthquake", "rockslide", "firefang", "iceshard"],
            "gengar": ["shadowball", "sludgebomb", "thunderbolt", "nastyplot"],
            "breloom": ["seedbomb", "machpunch", "toxic", "spore"],
            "arcanine": ["flareblitz", "superpower", "flamethrower", "crunch"],
            "tyranitar": ["crunch", "rockslide", "icebeam", "thunderwave"],
            "dragonite": ["dragondance", "dragonclaw", "aerialace", "earthquake"]
        }

        # Memory Check: Did enemy switch or use a setup move last turn?
        if current_enemy_species != self.last_enemy_species:
            self.enemy_setup_boosts = 0 
        elif enem_pkmn.current_hp_fraction >= self.last_enemy_hp:
            setup_moves = ["dragondance", "nastyplot", "swordsdance", "calmmind"]
            if any(move in enem_pkmn.moves for move in setup_moves):
                self.enemy_setup_boosts += 1

        self.last_enemy_hp = enem_pkmn.current_hp_fraction
        self.last_enemy_species = current_enemy_species

        # Damage calculations
        my_damages = calc_damage(my_pkmn, enem_pkmn)
        enemy_damages = calc_damage(enem_pkmn, my_pkmn)

        my_best_dmg = max([np.mean(x) for x in my_damages.values()]) if my_damages else 0

        # The Omniscient Check 
        max_enemy_dmg = 0
        if enemy_damages:
            clean_enem_name = next((key for key in enemy_meta.keys() if key in current_enemy_species), None)
            for move_id, dmg_list in enemy_damages.items():
                if clean_enem_name and str(move_id).lower() in enemy_meta[clean_enem_name]:
                    max_enemy_dmg = max(max_enemy_dmg, max(dmg_list))
                elif not clean_enem_name:
                    max_enemy_dmg = max(max_enemy_dmg, max(dmg_list))

        # Key tactical flags
        im_slower = my_pkmn.stats['spe'] < enem_pkmn.stats['spe']
        im_threatened = max_enemy_dmg >= (my_hp * 0.70)                        
        bad_matchup = (my_best_dmg < enem_max_hp * 0.30) and (max_enemy_dmg > my_hp * 0.50)

        scores = []

        for move in all_moves:
            score = 0
            if isinstance(move.order, Move):
                m = move.order
                m_id = str(m.id).lower()

                expected_dmg = np.mean(my_damages[m.id]) if m.id in my_damages else 0
                score = expected_dmg  

                # --- IMMUNITY FIX ---
                if expected_dmg == 0 and m.base_power > 0:
                    score -= 9999 # NEVER use a move that does 0 damage!

                # ── PRIORITY MOVES ──────────────────────────────────────────
                if m_id == "iceshard" and "dragonite" in current_enemy_species:
                    score += 9999

                if m_id == "machpunch":
                    if "tyranitar" in current_enemy_species:
                        score += 2000
                    elif "snorlax" in current_enemy_species:
                        score += 800
                    elif enem_hp <= expected_dmg:
                        score += 1500  

                if m.priority > 0 and im_slower and im_threatened:
                    score += 800

                # ── SPORE (Breloom) ─────────────────────────────────────────
                if m_id == "spore" and "breloom" in my_species:
                    enemy_types = [str(t).lower() for t in enem_pkmn.types]
                    already_asleep = enem_pkmn.status == Status.SLP
                    grass_immune = any("grass" in t for t in enemy_types)
                    already_slept = current_enemy_species in self.spore_used_on

                    if already_asleep or grass_immune or already_slept:
                        score -= 999  
                    elif enem_hp <= my_best_dmg:
                        score -= 500  
                    elif self.enemy_setup_boosts > 0:
                        score += 3000  
                    else:
                        score += 1500  
                        self.spore_used_on.add(current_enemy_species)

                # ── NASTY PLOT (Gengar) ─────────────────────────────────────
                if m_id == "nastyplot" and "gengar" in my_species:
                    if my_hp < (my_max_hp * 0.6):
                        score -= 500  
                    elif im_threatened:
                        score -= 999  
                    elif self.enemy_setup_boosts > 0:
                        score -= 999  
                    elif max_enemy_dmg < (my_max_hp * 0.4):
                        score += 400  

                # ── TAUNT (Gyarados) ────────────────────────────────────────
                if m_id == "taunt" and "gyarados" in my_species:
                    taunt_targets = ["venusaurmega", "venusaur", "roserade", "snorlax", "breloom", "gengar", "alakazam"]
                    if any(t in current_enemy_species for t in taunt_targets):
                        if enem_pkmn.status is None:
                            score += 600
                    else:
                        score -= 200

                # ── TOXIC (Breloom) ─────────────────────────────────────────
                if m_id == "toxic" and "breloom" in my_species:
                    bulky_targets = ["snorlax", "donphan", "gyarados", "venusaurmega"]
                    if any(t in current_enemy_species for t in bulky_targets):
                        if enem_pkmn.status is None and my_best_dmg < (enem_max_hp * 0.35):
                            score += 700
                        else:
                            score -= 300
                    else:
                        score -= 500

                # ── FIRE BLAST vs FLAMETHROWER (Charizard) ──────────────────
                if "charizard" in my_species:
                    if m_id == "fireblast":
                        score *= 0.85  
                        fire_targets = ["scizor", "venusaurmega", "venusaur", "breloom", "roserade"]
                        if any(t in current_enemy_species for t in fire_targets):
                            score += 500  
                    if m_id == "flamethrower":
                        if enem_hp <= expected_dmg * 1.2:
                            score += 200  

                # --- OVERRIDE: Charizard MUST nuke Snorlax with Fire moves ---
                if "charizard" in my_species and m_id in ["fireblast", "flamethrower"]:
                    if "snorlax" in current_enemy_species:
                        score += 2000 

                # ── ASSASSIN RULES ───────────────────────────────────────────

                if "charizard" in my_species and m_id == "thunderpunch":
                    if "gyarados" in current_enemy_species:
                        score += 2000

                if "charizard" in my_species and m_id == "earthquake":
                    ground_targets = ["nidoking", "arcanine", "rapidash", "donphan", "snorlax"]
                    if any(t in current_enemy_species for t in ground_targets):
                        score += 800

                if "gengar" in my_species and m_id == "shadowball":
                    if "alakazam" in current_enemy_species or "gengar" in current_enemy_species:
                        score += 2000

                if "gengar" in my_species and m_id == "thunderbolt":
                    if "gyarados" in current_enemy_species or "starmie" in current_enemy_species:
                        score += 2000

                if "donphan" in my_species and m_id == "rockslide":
                    if "charizard" in current_enemy_species or "arcanine" in current_enemy_species:
                        score += 1500

                if "donphan" in my_species and m_id == "firefang":
                    if "scizor" in current_enemy_species:
                        score += 1500

                if "snorlax" in my_species and m_id == "thunderpunch":
                    if "gyarados" in current_enemy_species or "charizard" in current_enemy_species:
                        score += 2000

                if "snorlax" in my_species and m_id == "firepunch":
                    if "scizor" in current_enemy_species or "breloom" in current_enemy_species:
                        score += 1500

                # (REMOVED SNORLAX FROM WATERFALL TARGETS)
                if "gyarados" in my_species and m_id == "waterfall":
                    water_targets = ["donphan", "arcanine", "rapidash", "tyranitar"]
                    if any(t in current_enemy_species for t in water_targets):
                        score += 800

                if "gyarados" in my_species and m_id == "crunch":
                    if "alakazam" in current_enemy_species or "gengar" in current_enemy_species:
                        score += 2000

                if "breloom" in my_species and m_id == "seedbomb":
                    if "blastoise" in current_enemy_species:
                        score += 2000

                # ── ANTI-SWEEPER PROTOCOL ────────────────────────────────────
                if self.enemy_setup_boosts > 0 and expected_dmg >= (enem_hp * 0.4):
                    score += 900

                # ── LETHAL CHECK ─────────────────────────────────────────────
                if expected_dmg >= enem_hp and m.base_power > 0:
                    score += 1000

                # ── RECOIL PENALTY ───────────────────────────────────────────
                if m.recoil > 0 and my_hp < (my_max_hp * 0.30):
                    score -= 500

                scores.append(score)

            # ══════════════════════════════════════════════
            # EVALUATE SWITCHES
            # ══════════════════════════════════════════════
            elif isinstance(move.order, Pokemon):
                benched_mon = move.order
                benched_hp = math.floor(benched_mon.stats["hp"] * benched_mon.current_hp_fraction)
                benched_species = str(benched_mon.species).lower()

                next_damages = calc_damage(benched_mon, enem_pkmn)
                benched_out_dmg = max([np.mean(x) for x in next_damages.values()]) if next_damages else 0

                switch_in_taken = calc_damage(enem_pkmn, benched_mon)
                benched_in_dmg = max([max(x) for x in switch_in_taken.values()]) if switch_in_taken else 0

                # SPEED BLINDNESS FIX: Don't send in a slower mon to die instantly
                benched_is_slower = benched_mon.stats['spe'] < enem_pkmn.stats['spe']
                if benched_is_slower and benched_in_dmg >= benched_hp:
                    benched_out_dmg = 0
                    benched_in_dmg = 9999

                # ── PRE-CHAIN INTERCEPTS ─────────────────────────────────────

                # Enemy Grass/Water → Save Donphan!
                if "donphan" in my_species and any(t in current_enemy_species for t in ["venusaur", "blastoise", "starmie"]):
                    if "snorlax" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.4):
                        scores.append(2000)
                        continue

                # Enemy Dragonite → Donphan (Ice Shard)
                if "dragonite" in current_enemy_species and "donphan" not in my_species:
                    if "donphan" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.3):
                        scores.append(2000)
                        continue

                # Enemy Scizor → Charizard (4x Fire)
                if "scizor" in current_enemy_species and "charizard" not in my_species:
                    if "charizard" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.3):
                        scores.append(2000)
                        continue

                # Enemy Breloom → Charizard (Flying, immune to Spore)
                if "breloom" in current_enemy_species and "charizard" not in my_species:
                    if "charizard" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.3):
                        scores.append(1800)
                        continue

                # Enemy Gengar → Snorlax (Normal immune to Ghost)
                if "gengar" in current_enemy_species and "snorlax" not in my_species:
                    if "snorlax" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.3):
                        scores.append(1500)
                        continue

                # Enemy Alakazam → Snorlax (Gyarados gets outsped; Snorlax tanks Psychic)
                if "alakazam" in current_enemy_species and "snorlax" not in my_species:
                    if "snorlax" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.3):
                        scores.append(1500)
                        continue

                # Enemy Blastoise → Snorlax (Breloom dies to Ice Beam; Snorlax absorbs it)
                if "blastoise" in current_enemy_species and "snorlax" not in my_species:
                    if "snorlax" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.3):
                        scores.append(1500)
                        continue

                # Enemy Gyarados → Snorlax (Thunder Punch)
                if "gyarados" in current_enemy_species and "snorlax" not in my_species:
                    if "snorlax" in benched_species and benched_hp > (benched_mon.stats["hp"] * 0.3):
                        scores.append(1400)
                        continue

                # ── SWITCH LOGIC CHAIN ───────────────────────────────────────

                # 1. Revenge killing after faint
                if my_pkmn.status == Status.FNT:
                    score = benched_out_dmg - benched_in_dmg

                # 2. Don't switch if enemy is setting up — attack instead
                elif self.enemy_setup_boosts > 0:
                    scores.append(-999)
                    continue

                # 3. General switching
                else:
                    must_flee = im_threatened and (im_slower or my_best_dmg < enem_hp)
                    
                    # Courage Override: Do not flee if we are an offensive nuke and we outspeed them!
                    if any(nuke in my_species for nuke in ["gengar", "charizard"]) and not im_slower:
                        must_flee = False

                    if must_flee:
                        if benched_in_dmg < benched_hp:
                            score = 800
                        else:
                            score = -999
                    elif bad_matchup:
                        if benched_in_dmg < (benched_hp * 0.8) and benched_out_dmg > (my_best_dmg * 1.4):
                            score = 700
                        else:
                            score = -999
                    else:
                        score = -999

                scores.append(score)

            else:
                scores.append(-999)

        # ── FINAL DECISION ───────────────────────────────────────────────────
        best_move = all_moves[np.argmax(scores)]
        return best_move


    
class AIPly3(RPly):
    TEAM = CHARIZARD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # ================= TEAM PREVIEW =================\
    def teampreview(self, battle):
         return self.random_teampreview(battle)
        

    # ================= MAIN MOVE ENGINE =================
    def choose_move(self, battle):

        # ===== ULTRA HARD ENGINE SAFETY =====
        if battle is None:
            return Ply.choose_default_move()

        # ===== WAIT / SYNC PHASE =====
        if getattr(battle, "_wait", False):
            return Ply.choose_default_move()

        # ===== TEAM PREVIEW =====
        if getattr(battle, "_teampreview", False) or len(getattr(battle, "team", {})) == 0:
            try:
                return self.teampreview(battle)
            except:
                return Ply.choose_default_move()

        # Safely fetch moves AFTER preview/sync
        all_moves = Ply.possible_moves(battle)

        if not all_moves:
            return Ply.choose_default_move()

        # ================= FORCE SWITCH =================
        if battle.force_switch or getattr(battle, "_force_switch", False):
            switches = [
                m for m in all_moves
                if isinstance(m.order, Pokemon)
                and m.order.current_hp_fraction > 0
            ]
            return switches[0] if switches else Ply.choose_default_move()

        # ================= SAFE STATE FETCH =================
        my_pkmn = battle.active_pokemon
        if my_pkmn is None or my_pkmn.current_hp_fraction == 0:
            return Ply.choose_default_move()
        if battle.opponent_active_pokemon is None:
            return Ply.choose_default_move()

        opp_pkmn = get_pokemon(battle.opponent_active_pokemon)

        # ================= DAMAGE CALC =================
        try:
            my_hp = max(1, int(my_pkmn.stats["hp"] * my_pkmn.current_hp_fraction))
            opp_hp = max(1, int(opp_pkmn.stats["hp"] * opp_pkmn.current_hp_fraction))

            my_damages = calc_damage(my_pkmn, opp_pkmn)
            opp_damages = calc_damage(opp_pkmn, my_pkmn)

            my_speed = my_pkmn.stats.get("spe", 0)
            opp_speed = opp_pkmn.stats.get("spe", 0)
            i_am_faster = my_speed >= opp_speed

            max_my_damage = max((max(d) for d in my_damages.values()), default=0)
            min_my_damage = max((min(d) for d in my_damages.values()), default=0)
            max_opp_damage = max((max(d) for d in opp_damages.values()), default=0)

        except:
            return Ply.choose_default_move()

        # ================= FIND BEST ATTACK =================
        best_attack = None
        best_score = -1
        priority_ko = None

        for m in all_moves:
            if isinstance(m.order, Move):
                dmg = np.mean(my_damages.get(m.order.id, [0]))
                acc = getattr(m.order, "accuracy", 100) or 100
                priority = getattr(m.order, "priority", 0)

                score = dmg * (acc / 100)
                 
                if score > best_score:
                    best_score = score
                    best_attack = m

                if min(my_damages.get(m.order.id, [0])) >= opp_hp and priority > 0:
                    priority_ko = m

        if not best_attack:
            return all_moves[0]
        # ===== DON'T SWITCH IF WE CAN WIN =====
        if max_my_damage >= opp_hp * 0.7:
            return best_attack
        # ===== STAY AND FIGHT =====
        if max_my_damage > opp_hp * 0.5:
            return best_attack

        # ================= DECISION RULES =================

        # RULE 1: PRIORITY KO
        if priority_ko:
            return priority_ko

        # RULE 2: SECURE KO
        if min_my_damage >= opp_hp:
            if i_am_faster or max_opp_damage < my_hp:
                return best_attack

        # RULE 3: SMART SACRIFICE
        if my_pkmn.current_hp_fraction < 0.18 and not i_am_faster:
            return best_attack

        # RULE 4: STRATEGIC SWITCH
        can_switch = any(isinstance(m.order, Pokemon) for m in all_moves)

        losing_badly = (
            max_opp_damage > my_hp * 0.6
            and max_my_damage < opp_hp * 0.45
        )

        about_to_die = max_opp_damage >= my_hp

        if (
            can_switch
            and not battle.trapped
            and my_pkmn.current_hp_fraction > 0.25
            and (losing_badly or about_to_die)
        ):

            switches = [m for m in all_moves if isinstance(m.order, Pokemon)]

            best_switch = None
            best_trade = max_my_damage - (max_opp_damage * 0.6)

            for s in switches:
                if s.order.current_hp_fraction < 0.30:
                    continue

                try:
                    incoming = calc_damage(opp_pkmn, s.order)
                    outgoing = calc_damage(s.order, opp_pkmn)

                    worst_in = max((max(d) for d in incoming.values()), default=9999)
                    best_out = max((min(d) for d in outgoing.values()), default=0)

                    trade_score = best_out - (worst_in * 0.6)

                    if (
                        s.order.species.lower() == "snorlax"
                        and opp_pkmn.stats["spa"] > opp_pkmn.stats["atk"]
                    ):
                        trade_score += 30

                    if trade_score > best_trade + 12:
                        best_trade = trade_score
                        best_switch = s

                except:
                    continue

            if best_switch:
                return best_switch

        # RULE 5: DEFAULT ATTACK
        return best_attack

class AIPly4(RPly):
    TEAM = CHARIZARD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # ================= TEAM PREVIEW =================
    def teampreview(self, battle):
         return self.random_teampreview(battle)
        

    # ================= MAIN MOVE ENGINE =================
    def choose_move(self, battle):

        # ===== ULTRA HARD ENGINE SAFETY =====
        if battle is None:
            return Ply.choose_default_move()

        if getattr(battle, "_wait", False):
            return Ply.choose_default_move()

        all_moves = Ply.possible_moves(battle)

        if not all_moves:
            return Ply.choose_default_move()

        # ===== TEAM PREVIEW PHASE =====
        if getattr(battle, "_teampreview", False):
            try:
                return self.teampreview(battle)
            except:
                return Ply.choose_default_move()

        # ================= FORCE SWITCH =================
        if battle.force_switch:
            switches = [
                m for m in all_moves
                if isinstance(m.order, Pokemon)
                and m.order.current_hp_fraction > 0
            ]
            return switches[0] if switches else Ply.choose_default_move()

        # ================= SAFE STATE FETCH =================
        my_pkmn = battle.active_pokemon

        if my_pkmn is None or my_pkmn.current_hp_fraction == 0:
            return Ply.choose_default_move()

        if battle.opponent_active_pokemon is None:
            return Ply.choose_default_move()

        opp_pkmn = get_pokemon(battle.opponent_active_pokemon)

        # ================= DAMAGE CALC =================
        try:
            my_hp = max(1, int(my_pkmn.stats["hp"] * my_pkmn.current_hp_fraction))
            opp_hp = max(1, int(opp_pkmn.stats["hp"] * opp_pkmn.current_hp_fraction))

            my_damages = calc_damage(my_pkmn, opp_pkmn)
            opp_damages = calc_damage(opp_pkmn, my_pkmn)

            my_speed = my_pkmn.stats.get("spe", 0)
            opp_speed = opp_pkmn.stats.get("spe", 0)
            i_am_faster = my_speed >= opp_speed

            max_my_damage = max(
                (max(d) for d in my_damages.values()),
                default=0
            )

            min_my_damage = max(
                (min(d) for d in my_damages.values()),
                default=0
            )

            max_opp_damage = max(
                (max(d) for d in opp_damages.values()),
                default=0
            )

        except:
            return Ply.choose_default_move()

        # ================= FIND BEST ATTACK =================
        best_attack = None
        best_score = -1
        priority_ko = None

        for m in all_moves:
            if isinstance(m.order, Move):
                dmg = np.mean(my_damages.get(m.order.id, [0]))
                acc = getattr(m.order, "accuracy", 100) or 100
                priority = getattr(m.order, "priority", 0)

                score = dmg * (acc / 100)

                if score > best_score:
                    best_score = score
                    best_attack = m

                # Priority KO check
                if (
                    min(my_damages.get(m.order.id, [0])) >= opp_hp
                    and priority > 0
                ):
                    priority_ko = m

        if not best_attack:
            return all_moves[0]

        # ================= DECISION RULES =================

        # RULE 1: PRIORITY KO
        if priority_ko:
            return priority_ko

        # RULE 2: SECURE KO
        if min_my_damage >= opp_hp:
            if i_am_faster or max_opp_damage < my_hp:
                return best_attack

        # RULE 3: SMART SACRIFICE
        if my_pkmn.current_hp_fraction < 0.18 and not i_am_faster:
            return best_attack

        # RULE 4: STRATEGIC SWITCH
        can_switch = any(isinstance(m.order, Pokemon) for m in all_moves)

        losing_badly = (
            max_opp_damage > my_hp * 0.6
            and max_my_damage < opp_hp * 0.45
        )

        about_to_die = max_opp_damage >= my_hp

        if (
            can_switch
            and not battle.trapped
            and my_pkmn.current_hp_fraction > 0.25
            and (losing_badly or about_to_die)
        ):
            switches = [
                m for m in all_moves
                if isinstance(m.order, Pokemon)
            ]

            best_switch = None
            best_trade = max_my_damage - (max_opp_damage * 0.6)

            for s in switches:
                if s.order.current_hp_fraction < 0.30:
                    continue

                try:
                    incoming = calc_damage(opp_pkmn, s.order)
                    outgoing = calc_damage(s.order, opp_pkmn)

                    worst_in = max(
                        (max(d) for d in incoming.values()),
                        default=9999
                    )

                    best_out = max(
                        (min(d) for d in outgoing.values()),
                        default=0
                    )

                    trade_score = best_out - (worst_in * 0.6)

                    # Special Snorlax anti-special logic
                    if (
                        s.order.species.lower() == "snorlax"
                        and opp_pkmn.stats["spa"] > opp_pkmn.stats["atk"]
                    ):
                        trade_score += 30

                    if trade_score > best_trade + 12:
                        best_trade = trade_score
                        best_switch = s

                except:
                    continue

            if best_switch:
                return best_switch

        # RULE 5: DEFAULT ATTACK
        return best_attack
import joblib
import pandas as pd

import joblib
import pandas as pd

import joblib
import numpy as np
import pandas as pd

from include import Ply, RPly, CHARIZARD
from include import Move, Pokemon, get_pokemon, calc_damage


import joblib
import numpy as np
import pandas as pd

from include import Ply, RPly, CHARIZARD
from include import Move, Pokemon, get_pokemon, calc_damage


class AIPly5(RPly):
    TEAM = CHARIZARD

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.model = joblib.load("model.pkl")
        self.encoder = joblib.load("encoder.pkl")

    # ================= TEAM PREVIEW =================
    def teampreview(self, battle):
        return self.random_teampreview(battle)

    # ================= MAIN MOVE ENGINE =================
    def choose_move(self, battle):

        # ===== SAFETY =====
        if battle is None:
            return Ply.choose_default_move()

        if getattr(battle, "_wait", False):
            return Ply.choose_default_move()

        if getattr(battle, "_teampreview", False):
            return self.random_teampreview(battle)

        all_moves = Ply.possible_moves(battle)

        if not all_moves:
            return Ply.choose_default_move()

        # ===== FORCE SWITCH =====
        if battle.force_switch:
            switches = [
                m for m in all_moves
                if isinstance(m.order, Pokemon)
                and m.order.current_hp_fraction > 0
            ]
            return switches[0] if switches else Ply.choose_default_move()

        # ===== STATE =====
        my_pkmn = battle.active_pokemon
        opp_pkmn = get_pokemon(battle.opponent_active_pokemon)

        if my_pkmn is None or opp_pkmn is None:
            return all_moves[0]

        try:
            # ===== FEATURES =====
            my_speed = my_pkmn.stats.get("spe", 0)
            opp_speed = opp_pkmn.stats.get("spe", 0)
            faster = int(my_speed >= opp_speed)

            my_damages = calc_damage(my_pkmn, opp_pkmn)
            opp_damages = calc_damage(opp_pkmn, my_pkmn)

            max_my_damage = max((max(d) for d in my_damages.values()), default=0)
            max_opp_damage = max((max(d) for d in opp_damages.values()), default=0)

            my_hp = max(1, int(my_pkmn.stats["hp"] * my_pkmn.current_hp_fraction))
            opp_hp = max(1, int(opp_pkmn.stats["hp"] * opp_pkmn.current_hp_fraction))

            X = pd.DataFrame([{
                "my_hp": my_pkmn.current_hp_fraction,
                "opp_hp": opp_pkmn.current_hp_fraction,
                "my_speed": my_speed,
                "opp_speed": opp_speed,
                "faster": faster,
                "max_my_damage": max_my_damage,
                "max_opp_damage": max_opp_damage
            }])

            probs = self.model.predict_proba(X)[0]

        except:
            return all_moves[0]

        # ================= SMART RULES =================

        # RULE 1: PRIORITY KO
        for m in all_moves:
            if isinstance(m.order, Move):
                dmg_list = my_damages.get(m.order.id, [0])
                priority = getattr(m.order, "priority", 0)

                if min(dmg_list) >= opp_hp and priority > 0:
                    return m

        # RULE 2: GUARANTEED KO
        for m in all_moves:
            if isinstance(m.order, Move):
                dmg_list = my_damages.get(m.order.id, [0])

                if min(dmg_list) >= opp_hp:
                    return m

        # RULE 3: ABOUT TO DIE → MAX DAMAGE
        if max_opp_damage >= my_hp:
            best = None
            best_dmg = -1

            for m in all_moves:
                if isinstance(m.order, Move):
                    dmg = np.mean(my_damages.get(m.order.id, [0]))
                    if dmg > best_dmg:
                        best_dmg = dmg
                        best = m

            if best:
                return best

        # ================= HYBRID DECISION =================
        best_move = None
        best_score = -1

        for m in all_moves:
            if isinstance(m.order, Move):
                move_id = m.order.id

                # ML score
                try:
                    idx = list(self.encoder.classes_).index(move_id)
                    ml_score = probs[idx]
                except:
                    ml_score = 0

                # damage score
                dmg = np.mean(my_damages.get(move_id, [0]))

                # FINAL SCORE
                score = (ml_score * 0.6) + (dmg * 0.4)

                if score > best_score:
                    best_score = score
                    best_move = m

        if best_move:
            return best_move

        return all_moves[0]

    # ================= DATASET FIX =================
    def save_dataset(self, *args, **kwargs):
        print("AI5: No dataset to save")