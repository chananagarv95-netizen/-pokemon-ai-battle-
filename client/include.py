from poke_env.player.player import Player
from dataclasses import dataclass
from logging import Logger
from typing import Any, Dict, List, Union, Optional
from poke_env import AccountConfiguration
from poke_env.ps_client.account_configuration import CONFIGURATION_FROM_PLAYER_COUNTER
from poke_env.data import GenData, to_id_str
from poke_env.environment import AbstractBattle, Battle
from poke_env.environment.move import Move
from poke_env.environment.pokemon_type import PokemonType
from poke_env.environment.double_battle import DoubleBattle
from poke_env.environment.observation import Observation
from poke_env.environment.observed_pokemon import ObservedPokemon
from poke_env.environment.pokemon import Pokemon
from poke_env.environment.weather import Weather
from poke_env.environment.move_category import MoveCategory
from poke_env.environment.status import Status
from poke_env.environment.effect import Effect
from poke_env.exceptions import ShowdownException
from poke_env.teambuilder.constant_teambuilder import ConstantTeambuilder
import re
import math
import orjson
import hashlib
import random

CHARIZARD = "teams/charizard.txt"
BLASTOISE = "teams/blastoise.txt"
VENUSAUR = "teams/venusaur.txt"
PIKACHU = "teams/pikachu.txt"

TEAMS = [CHARIZARD, BLASTOISE, VENUSAUR, PIKACHU]

pkmn_moves = {}
pkmn_natures = {}
moves = {}
with open("natures.json", "r") as F:
    natures = orjson.loads(F.read())

for t in TEAMS:
    with open(t, "r") as F:
        lines = F.readlines()
        for i in range(0, len(lines), 10):
            id = "".join(lines[i].split("-")).strip().lower()
            move_lines = [x[1:].strip() for x in lines[i+5:i+9]]
            pkmn_moves[id] = move_lines
            moves.update({to_id_str(x): Move(to_id_str(x), 7) for x in move_lines})
            pkmn_natures[id] = lines[i+4].strip()[:-7].lower()

DATA_DICTS = [pkmn_moves, pkmn_natures]

# for i in range(len(DATA_DICTS)):
#     DICT = DATA_DICTS[i]
#     DICT['charizard'] = DICT.get('charizardmegay')
#     DICT['blastoise'] = DICT.get('blastoisemega')
#     DICT['venusaur'] = DICT.get('venusaurmega')

def get_pokemon(pokemon: Pokemon) -> Pokemon:
    moves = pkmn_moves.get(pokemon.species)
    if moves:
        for move in moves:
            pokemon._add_move(move)

    base_stats = pokemon.base_stats
    boosts = pokemon.boosts
    for stat, base_stat in base_stats.items():

        if stat == "hp":
            pokemon._stats[stat] = base_stat + 75
        else:
            boost = 1
            if boosts[stat] > 0:
                boost = (2 + boosts[stat]) / 2
            elif boosts[stat] < 0:
                boost = 2 / (2 - boosts[stat])
            pokemon._stats[stat] = math.floor(math.floor(math.floor((base_stat + 20) * natures.get(pkmn_natures[pokemon.species], "serious")[stat]) * 1.02) * boost)
            if ((stat == "atk") and (pokemon.status == Status.BRN)) or ((stat == "spe") and (pokemon.status == Status.PAR)):
                pokemon._stats[stat] = math.floor(pokemon._stats[stat] * 0.5)

    return pokemon


def calc_damage(attacker: Pokemon, defender: Pokemon, is_crit=False):
    attacker_moves = [moves[to_id_str(x)] for x in pkmn_moves.get(attacker.species)]
    dmg_dict = {}
    for move in attacker_moves:
        if move.category == MoveCategory.PHYSICAL:
            A = attacker.stats["atk"]
            D = defender.stats["def"]
            if is_crit:
                if attacker.boosts["atk"] < 0:
                    A = math.floor(A * (2 - attacker.boosts["atk"]) / 2)
                if defender.boosts["def"] > 0:
                    D = math.floor(D * 2 / (2 + defender.boosts["def"]))
        elif move.category == MoveCategory.SPECIAL:
            A = attacker.stats["spa"]
            D = defender.stats["spd"]
            if is_crit:
                if attacker.boosts["spa"] < 0:
                    A = math.floor(A * (2 - attacker.boosts["spa"]) / 2)
                if defender.boosts["spd"] > 0:
                    D = math.floor(D * 2 / (2 + defender.boosts["spd"]))
        else:
            dmg_dict[move.id] = [0] * 16
            continue
        
        base_power = move.base_power
        if move.id in ["lowkick", "grassknot"]:
            defender_weight = defender.weight
            if defender_weight >= 200:
                base_power = 120
            elif defender_weight >= 100:
                base_power = 100
            elif defender_weight >= 50:
                base_power = 80
            elif defender_weight >= 25:
                base_power = 60
            elif defender_weight >= 10:
                base_power = 40
            else:
                base_power = 20
        crit = 1.5 if is_crit else 1
        stab = 1.5 if move.type in attacker.types else 1
        eff = move.type.damage_multiplier(*defender.types, type_chart=GenData.from_gen(7).type_chart)
        raw_damage = math.floor(math.floor((22 * base_power * A) / D) / 50) + 2
        raw_damage = math.floor(raw_damage * crit)
        dmg_dict[move.id] = [math.floor(math.floor(math.floor(raw_damage * (rand/100)) * stab) * eff) for rand in range(85, 101, 1)]
    
    return dmg_dict

class AbstractBattle(AbstractBattle):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def parse_message(self, split_message: List[str]):
        self._current_observation.events.append(split_message)

        # We copy because we directly modify split_message in poke-env; this is to
        # preserve further usage of this event upstream
        event = split_message[:]

        if event[1] in self.MESSAGES_TO_IGNORE:
            return
        elif event[1] in ["drag", "switch"]:
            pokemon, details, hp_status = event[2:5]
            self.switch(pokemon, details, hp_status)
        elif event[1] == "-damage":
            pokemon, hp_status = event[2:4]
            self.get_pokemon(pokemon).damage(hp_status)
            self._check_damage_message_for_item(event)
            self._check_damage_message_for_ability(event)
        elif event[1] == "move":
            failed = False
            override_move = None
            reveal_other_move = False

            for move_failed_suffix in ["[miss]", "[still]", "[notarget]"]:
                if event[-1] == move_failed_suffix:
                    event = event[:-1]
                    failed = True

            if event[-1] == "[notarget]":
                event = event[:-1]

            if event[-1].startswith("[spread]"):
                event = event[:-1]

            if event[-1] in {"[from]lockedmove", "[from]Pursuit", "[zeffect]"}:
                event = event[:-1]

            if event[-1].startswith("[anim]"):
                event = event[:-1]

            if event[-1].startswith("[from]move: "):
                override_move = event.pop()[12:]

                if override_move == "Sleep Talk":
                    # Sleep talk was used, but also reveals another move
                    reveal_other_move = True
                elif override_move in {"Copycat", "Metronome", "Nature Power"}:
                    pass
                elif override_move in {"Grass Pledge", "Water Pledge", "Fire Pledge"}:
                    override_move = None
                elif self.logger is not None:
                    self.logger.warning(
                        "Unmanaged [from]move message received - move %s in cleaned up "
                        "message %s in battle %s turn %d",
                        override_move,
                        event,
                        self.battle_tag,
                        self.turn,
                    )

            if event[-1] == "null":
                event = event[:-1]

            if event[-1].startswith("[from]ability: "):
                revealed_ability = event.pop()[15:]
                pokemon = event[2]
                self.get_pokemon(pokemon).ability = revealed_ability

                if revealed_ability == "Magic Bounce":
                    return
                elif revealed_ability == "Dancer":
                    return
                elif self.logger is not None:
                    self.logger.warning(
                        "Unmanaged [from]ability: message received - ability %s in "
                        "cleaned up message %s in battle %s turn %d",
                        revealed_ability,
                        event,
                        self.battle_tag,
                        self.turn,
                    )
            if event[-1] == "[from]Magic Coat":
                return

            while event[-1] == "[still]":
                event = event[:-1]

            if event[-1] == "":
                event = event[:-1]

            if len(event) == 4:
                pokemon, move = event[2:4]
            elif len(event) == 5:
                pokemon, move, presumed_target = event[2:5]

                if len(presumed_target) > 4 and presumed_target[:4] in {
                    "p1: ",
                    "p2: ",
                    "p1a:",
                    "p1b:",
                    "p2a:",
                    "p2b:",
                }:
                    pass
                elif self.logger is not None:
                    self.logger.warning(
                        "Unmanaged move message format received - cleaned up message %s"
                        " in battle %s turn %d",
                        event,
                        self.battle_tag,
                        self.turn,
                    )
            else:
                pokemon, move, presumed_target = event[2:5]
                if self.logger is not None:
                    self.logger.warning(
                        "Unmanaged move message format received - cleaned up message %s in "
                        "battle %s turn %d",
                        event,
                        self.battle_tag,
                        self.turn,
                    )

            # Check if a silent-effect move has occurred (Minimize) and add the effect
            if move.upper().strip() == "MINIMIZE":
                temp_pokemon = self.get_pokemon(pokemon)
                temp_pokemon.start_effect("MINIMIZE")

            if override_move:
                # Moves that can trigger this branch results in two `move` messages being sent.
                # We're setting use=False in the one (with the override) in order to prevent two pps from being used
                # incorrectly.
                self.get_pokemon(pokemon).moved(override_move, failed=failed, use=False)
            if override_move is None or reveal_other_move:
                self.get_pokemon(pokemon).moved(move, failed=failed, use=True)
        elif event[1] == "cant":
            pokemon, _ = event[2:4]
            self.get_pokemon(pokemon).cant_move()
        elif event[1] == "turn":
            # Saving the beginning-of-turn battle state and events as we go into the turn
            self.observations[self.turn] = self._current_observation

            self.end_turn(int(event[2]))

            opp_active_mon, active_mon = None, None
            if isinstance(self.opponent_active_pokemon, Pokemon):
                opp_active_mon = ObservedPokemon.from_pokemon(
                    self.opponent_active_pokemon
                )
                active_mon = ObservedPokemon.from_pokemon(self.active_pokemon)
            else:
                opp_active_mon = [
                    ObservedPokemon.from_pokemon(mon)
                    for mon in self.opponent_active_pokemon
                ]
                active_mon = [
                    ObservedPokemon.from_pokemon(mon) for mon in self.active_pokemon
                ]

            # Create new Observation and record battle state going into the next turn
            self._current_observation = Observation(
                side_conditions={k: v for (k, v) in self.side_conditions.items()},
                opponent_side_conditions={
                    k: v for (k, v) in self.opponent_side_conditions.items()
                },
                weather={k: v for (k, v) in self.weather.items()},
                fields={k: v for (k, v) in self.fields.items()},
                active_pokemon=active_mon,
                team={
                    ident: ObservedPokemon.from_pokemon(mon)
                    for (ident, mon) in self.team.items()
                },
                opponent_active_pokemon=opp_active_mon,
                opponent_team={
                    ident: ObservedPokemon.from_pokemon(mon)
                    for (ident, mon) in self.opponent_team.items()
                },
            )
        elif event[1] == "-heal":
            pokemon, hp_status = event[2:4]
            self.get_pokemon(pokemon).heal(hp_status)
            self._check_heal_message_for_ability(event)
            self._check_heal_message_for_item(event)
        elif event[1] == "-boost":
            pokemon, stat, amount = event[2:5]
            self.get_pokemon(pokemon).boost(stat, int(amount))
        elif event[1] == "-weather":
            weather = event[2]
            if weather == "none":
                self._weather = {}
                return
            else:
                self._weather = {Weather.from_showdown_message(weather): self.turn}
        elif event[1] == "faint":
            pokemon = event[2]
            self.get_pokemon(pokemon).faint()
        elif event[1] == "-unboost":
            pokemon, stat, amount = event[2:5]
            self.get_pokemon(pokemon).boost(stat, -int(amount))
        elif event[1] == "-ability":
            pokemon, cause = event[2:4]
            if len(event) > 4 and event[4].startswith("[from] move:"):
                self.get_pokemon(pokemon).set_temporary_ability(cause)
            else:
                self.get_pokemon(pokemon).ability = cause
        elif split_message[1] == "-start":
            pokemon, effect = event[2:4]
            pokemon = self.get_pokemon(pokemon)  # type: ignore

            if effect == "typechange":
                pokemon.start_effect(effect, details=event[4])  # type: ignore
            else:
                pokemon.start_effect(effect)  # type: ignore

            if pokemon.is_dynamaxed:  # type: ignore
                if pokemon in set(self.team.values()) and self._dynamax_turn is None:
                    self._dynamax_turn = self.turn
                # self._can_dynamax value is set via _parse_request()
                elif (
                    pokemon in set(self.opponent_team.values())
                    and self._opponent_dynamax_turn is None
                ):
                    self._opponent_dynamax_turn = self.turn
                    self.opponent_can_dynamax = False
        elif event[1] == "-activate":
            target, effect = event[2:4]
            if target and effect == "move: Skill Swap":
                self.get_pokemon(target).start_effect(effect, event[4:6])
                actor = event[6].replace("[of] ", "")
                self.get_pokemon(actor).set_temporary_ability(event[5])
            else:
                self.get_pokemon(target).start_effect(effect)
        elif event[1] == "-status":
            pokemon, status = event[2:4]
            self.get_pokemon(pokemon).status = status  # type: ignore
        elif event[1] == "rule":
            self.rules.append(event[2])

        elif event[1] == "-clearallboost":
            self.clear_all_boosts()
        elif event[1] == "-clearboost":
            pokemon = event[2]
            self.get_pokemon(pokemon).clear_boosts()
        elif event[1] == "-clearnegativeboost":
            pokemon = event[2]
            self.get_pokemon(pokemon).clear_negative_boosts()
        elif event[1] == "-clearpositiveboost":
            pokemon = event[2]
            self.get_pokemon(pokemon).clear_positive_boosts()
        elif event[1] == "-copyboost":
            source, target = event[2:4]
            self.get_pokemon(target).copy_boosts(self.get_pokemon(source))
        elif event[1] == "-curestatus":
            pokemon, status = event[2:4]
            self.get_pokemon(pokemon).cure_status(status)
        elif event[1] == "-cureteam":
            pokemon = event[2]
            team = (
                self.team if pokemon[:2] == self._player_role else self._opponent_team
            )
            for mon in team.values():
                mon.cure_status()
        elif event[1] == "-end":
            pokemon, effect = event[2:4]
            self.get_pokemon(pokemon).end_effect(effect)
        elif event[1] == "-endability":
            pokemon = event[2]
            self.get_pokemon(pokemon).set_temporary_ability(None)
        elif event[1] == "-enditem":
            pokemon, item = event[2:4]
            self.get_pokemon(pokemon).end_item(item)
        elif event[1] == "-fieldend":
            condition = event[2]
            self._field_end(condition)
        elif event[1] == "-fieldstart":
            condition = event[2]
            self.field_start(condition)
        elif event[1] in ["-formechange", "detailschange"]:
            pokemon, species = event[2:4]
            self.get_pokemon(pokemon).forme_change(species)
        elif event[1] == "-invertboost":
            pokemon = event[2]
            self.get_pokemon(pokemon).invert_boosts()
        elif event[1] == "-item":
            if len(event) == 6:
                item, cause, pokemon = event[3:6]

                if cause == "[from] ability: Frisk":
                    pokemon = pokemon.split("[of] ")[-1]
                    mon = self.get_pokemon(pokemon)

                    if isinstance(self.active_pokemon, list):
                        self.get_pokemon(event[2]).item = to_id_str(item)
                    else:
                        if mon == self.active_pokemon:
                            self.opponent_active_pokemon.item = to_id_str(item)
                        else:
                            assert mon == self.opponent_active_pokemon
                            self.active_pokemon.item = to_id_str(item)

                    mon.ability = to_id_str("frisk")
                elif cause == "[from] ability: Pickpocket":
                    pickpocket = event[2]
                    pickpocketed = event[5].replace("[of] ", "")
                    item = event[3]

                    self.get_pokemon(pickpocket).item = to_id_str(item)
                    self.get_pokemon(pickpocket).ability = to_id_str("pickpocket")
                    self.get_pokemon(pickpocketed).item = None
                elif cause == "[from] ability: Magician":
                    magician = event[2]
                    victim = event[5].replace("[of] ", "")
                    item = event[3]

                    self.get_pokemon(magician).item = to_id_str(item)
                    self.get_pokemon(magician).ability = to_id_str("magician")
                    self.get_pokemon(victim).item = None
                elif cause in {"[from] move: Thief"}:
                    thief = event[2]
                    victim = event[5].replace("[of] ", "")
                    item = event[3]

                    self.get_pokemon(thief).item = to_id_str(item)
                    self.get_pokemon(victim).item = None
                else:
                    raise ValueError(f"Unhandled item message: {event}")

            else:
                pokemon, item = event[2:4]
                self.get_pokemon(pokemon).item = to_id_str(item)
        elif event[1] == "-mega":
            if self.player_role is not None and not event[2].startswith(
                self.player_role
            ):
                self._opponent_can_mega_evolve = False
            pokemon, megastone = event[2:4]
            self.get_pokemon(pokemon).mega_evolve(megastone)
        elif event[1] == "-mustrecharge":
            pokemon = event[2]
            self.get_pokemon(pokemon).must_recharge = True
        elif event[1] == "-prepare":
            try:
                attacker, move, defender = event[2:5]
                defender_mon = self.get_pokemon(defender)
                if to_id_str(move) == "skydrop":
                    defender_mon.start_effect("Sky Drop")
            except ValueError:
                attacker, move = event[2:4]
                defender_mon = None
            self.get_pokemon(attacker).prepare(move, defender_mon)
        elif event[1] == "-primal":
            pokemon = event[2]
            self.get_pokemon(pokemon).primal()
        elif event[1] == "-setboost":
            pokemon, stat, amount = event[2:5]
            self.get_pokemon(pokemon).set_boost(stat, int(amount))
        elif event[1] == "-sethp":
            pokemon, hp_status = event[2:4]
            self.get_pokemon(pokemon).set_hp(hp_status)
        elif event[1] == "-sideend":
            side, condition = event[2:4]
            self.side_end(side, condition)
        elif event[1] == "-sidestart":
            side, condition = event[2:4]
            self._side_start(side, condition)
        elif event[1] in ["-singleturn", "-singlemove"]:
            pokemon, effect = event[2:4]
            self.get_pokemon(pokemon).start_effect(effect.replace("move: ", ""))
        elif event[1] == "-swapboost":
            source, target, stats = event[2:5]
            source_mon = self.get_pokemon(source)
            target_mon = self.get_pokemon(target)
            for stat in stats.split(", "):
                source_mon.boosts[stat], target_mon.boosts[stat] = (
                    target_mon.boosts[stat],
                    source_mon.boosts[stat],
                )
        elif event[1] == "-transform":
            pokemon, into = event[2:4]
            self.get_pokemon(pokemon).transform(self.get_pokemon(into))
        elif event[1] == "-zpower":
            if self._player_role is not None and not event[2].startswith(
                self._player_role
            ):
                self._opponent_can_z_move = False

            pokemon = event[2]
            self.get_pokemon(pokemon).used_z_move()
        elif event[1] == "clearpoke":
            self.in_team_preview = True
            for mon in self.team.values():
                mon.clear_active()
        elif event[1] == "gen":
            if self._gen != int(event[2]):
                err = f"Battle Initiated with gen {self._gen} but got: {event}"
                raise RuntimeError(err)
        elif event[1] == "tier":
            self._format = re.sub("[^a-z0-9]+", "", event[2].lower())
        elif event[1] == "inactive":
            if "disconnected" in event[2]:
                self._anybody_inactive = True
            elif "reconnected" in event[2]:
                self._anybody_inactive = False
                self._reconnected = True
        elif event[1] == "player":
            if len(event) == 6:
                player, username, avatar, rating = event[2:6]
            elif len(event) == 5:
                player, username, avatar = event[2:5]
                rating = None
            elif len(event) == 4:
                if event[-1] != "":
                    raise RuntimeError(f"Invalid player message: {event}")
                return
            else:
                if not self._anybody_inactive:
                    if self._reconnected:
                        self._reconnected = False
                    else:
                        raise RuntimeError(f"Invalid player message: {event}")
                return
            if username == self._player_username:
                self._player_role = player
            if rating is not None:
                return self._players.append(
                    {
                        "username": username,
                        "player": player,
                        "avatar": avatar,
                        "rating": rating,
                    }
                )
            else:
                return self._players.append(
                    {
                        "username": username,
                        "player": player,
                        "avatar": avatar,
                    }
                )

        elif event[1] == "poke":
            player, details = event[2:4]
            self._register_teampreview_pokemon(player, details)
        elif event[1] == "raw":
            username, rating_info = event[2].split("'s rating: ")
            rating_int = int(rating_info[:4])
            if username == self.player_username:
                self._rating = rating_int
            elif username == self.opponent_username:
                self._opponent_rating = rating_int
            elif self.logger is not None:
                self.logger.warning(
                    "Rating information regarding an unrecognized username received. "
                    "Received '%s', while only known players are '%s' and '%s'",
                    username,
                    self.player_username,
                    self.opponent_username,
                )
        elif event[1] == "replace":
            pokemon = event[2]
            details = event[3]
            self.end_illusion(pokemon, details)
        elif event[1] == "start":
            self.in_team_preview = False
        elif event[1] == "swap":
            pokemon, position = event[2:4]
            self._swap(pokemon, position)  # type: ignore
        elif event[1] == "teamsize":
            player, number = event[2:4]
            self._team_size[player] = int(number)
        elif event[1] in {"message", "-message"}:
            if self.logger is not None:
                self.logger.info("Received message: %s", event[2])
        elif event[1] == "-immune":
            if len(event) == 4:
                mon, cause = event[2:]  # type: ignore

                if cause.startswith("[from] ability:"):
                    cause = cause.replace("[from] ability:", "")
                    self.get_pokemon(mon).ability = to_id_str(cause)  # type: ignore
        elif event[1] == "-swapsideconditions":
            self._side_conditions, self._opponent_side_conditions = (
                self._opponent_side_conditions,
                self._side_conditions,
            )
        elif event[1] == "title":
            player_1, player_2 = event[2].split(" vs. ")
            self.players = player_1, player_2
        elif event[1] == "-terastallize":
            pokemon, type_ = event[2:]
            pokemon = self.get_pokemon(pokemon)  # type: ignore
            pokemon.terastallize(type_)  # type: ignore

            if pokemon.is_terastallized:  # type: ignore
                if pokemon in set(self.opponent_team.values()):
                    self._opponent_can_terrastallize = False
        else:
            raise NotImplementedError(event)

class Battle(AbstractBattle):
    def __init__(
        self,
        battle_tag: str,
        username: str,
        logger: Logger,
        gen: int,
        save_replays: Union[str, bool] = False,
    ):
        super(Battle, self).__init__(battle_tag, username, logger, save_replays, gen)

        # Turn choice attributes
        self._available_moves: List[Move] = []
        self._available_switches: List[Pokemon] = []
        self._can_dynamax: bool = False
        self._can_mega_evolve: bool = False
        self._can_tera: Optional[PokemonType] = None
        self._can_z_move: bool = False
        self._opponent_can_dynamax = True
        self._opponent_can_mega_evolve = True
        self._opponent_can_z_move = True
        self._opponent_can_tera: bool = False
        self._force_switch: bool = False
        self._maybe_trapped: bool = False
        self._trapped: bool = False

        # Turn choice attributes
        self._can_mega_evolve_x: bool = False
        self._can_mega_evolve_y: bool = False

    def clear_all_boosts(self):
        if self.active_pokemon is not None:
            self.active_pokemon.clear_boosts()
        if self.opponent_active_pokemon is not None:
            self.opponent_active_pokemon.clear_boosts()

    def end_illusion(self, pokemon_name: str, details: str):
        if pokemon_name[:2] == self._player_role:
            active = self.active_pokemon
        else:
            active = self.opponent_active_pokemon

        if active is None:
            raise ValueError("Cannot end illusion without an active pokemon.")

        self._end_illusion_on(
            illusioned=active, illusionist=pokemon_name, details=details
        )

    def parse_request(self, request: Dict[str, Any]) -> None:
        """
        Update the object from a request.
        The player's pokemon are all updated, as well as available moves, switches and
        other related information (z move, mega evolution, forced switch...).

        :param request: Parsed JSON request object.
        :type request: dict
        """
        if "wait" in request and request["wait"]:
            self._wait = True
        else:
            self._wait = False

        side = request["side"]

        self._available_moves = []
        self._available_switches = []
        self._can_mega_evolve = False
        self._can_mega_evolve_x = False
        self._can_mega_evolve_y = False
        self._can_z_move = False
        self._can_dynamax = False
        self._can_tera = None
        self._maybe_trapped = False
        self._reviving = any(
            [m["reviving"] for m in side.get("pokemon", []) if "reviving" in m]
        )
        self._trapped = False
        self._force_switch = request.get("forceSwitch", [False])[0]

        if self._force_switch:
            self._move_on_next_request = True

        self._last_request = request

        if request.get("teamPreview", False):
            self._teampreview = True
            number_of_mons = len(request["side"]["pokemon"])
            self._max_team_size = request.get("maxTeamSize", number_of_mons)
        else:
            self._teampreview = False
        self._update_team_from_request(request["side"])

        if "active" in request:
            active_request = request["active"][0]

            if active_request.get("trapped"):
                self._trapped = True

            if self.active_pokemon is not None:
                self._available_moves.extend(
                    self.active_pokemon.available_moves_from_request(active_request)
                )

            if active_request.get("canMegaEvo", False):
                self._can_mega_evolve = True
            if active_request.get("canMegaEvoX", False):
                self._can_mega_evolve_x = True
            if active_request.get("canMegaEvoY", False):
                self._can_mega_evolve_y = True
            if active_request.get("canZMove", False):
                self._can_z_move = True
            if active_request.get("canDynamax", False):
                self._can_dynamax = True
            if active_request.get("maybeTrapped", False):
                self._maybe_trapped = True
            if active_request.get("canTerastallize", False):
                self._can_tera = PokemonType.from_name(
                    active_request["canTerastallize"]
                )

        if side["pokemon"]:
            self._player_role = side["pokemon"][0]["ident"][:2]

        if not self.trapped and not self.reviving:
            for pokemon in side["pokemon"]:
                if pokemon:
                    pokemon = self._team[pokemon["ident"]]
                    if not pokemon.active and not pokemon.fainted:
                        self._available_switches.append(pokemon)

        if not self.trapped and self.reviving:
            for pokemon in side["pokemon"]:
                if pokemon and pokemon.get("reviving", False):
                    pokemon = self._team[pokemon["ident"]]
                    if not pokemon.active:
                        self._available_switches.append(pokemon)

    def switch(self, pokemon_str: str, details: str, hp_status: str):
        identifier = pokemon_str.split(":")[0][:2]

        if identifier == self._player_role:
            if self.active_pokemon:
                self.active_pokemon.switch_out()
        else:
            if self.opponent_active_pokemon:
                self.opponent_active_pokemon.switch_out()

        pokemon = self.get_pokemon(pokemon_str, details=details)

        pokemon.switch_in(details=details)
        pokemon.set_hp_status(hp_status)

    @property
    def active_pokemon(self) -> Optional[Pokemon]:
        """
        :return: The active pokemon
        :rtype: Optional[Pokemon]
        """
        for pokemon in self.team.values():
            if pokemon.active:
                return pokemon
        return None

    @property
    def all_active_pokemons(self) -> List[Optional[Pokemon]]:
        """
        :return: A list containing all active pokemons and/or Nones.
        :rtype: List[Optional[Pokemon]]
        """
        return [self.active_pokemon, self.opponent_active_pokemon]

    @property
    def available_moves(self) -> List[Move]:
        """
        :return: The list of moves the player can use during the current move request.
        :rtype: List[Move]
        """
        return self._available_moves

    @property
    def available_switches(self) -> List[Pokemon]:
        """
        :return: The list of switches the player can do during the current move request.
        :rtype: List[Pokemon]
        """
        return self._available_switches

    @property
    def can_dynamax(self) -> bool:
        """
        :return: Whether or not the current active pokemon can dynamax
        :rtype: bool
        """
        return self._can_dynamax

    @property
    def can_mega_evolve(self) -> bool:
        """
        :return: Whether or not the current active pokemon can mega evolve.
        :rtype: bool
        """
        return self._can_mega_evolve

    @property
    def can_tera(self) -> Optional[PokemonType]:
        """
        :return: None, or the type the active pokemon can terastallize into.
        :rtype: PokemonType, optional
        """
        return self._can_tera

    @property
    def can_z_move(self) -> bool:
        """
        :return: Whether or not the current active pokemon can z-move.
        :rtype: bool
        """
        return self._can_z_move

    @property
    def force_switch(self) -> bool:
        """
        :return: A boolean indicating whether the active pokemon is forced to switch
            out.
        :rtype: Optional[bool]
        """
        return self._force_switch

    @property
    def maybe_trapped(self) -> bool:
        """
        :return: A boolean indicating whether the active pokemon is maybe trapped by the
            opponent.
        :rtype: bool
        """
        return self._maybe_trapped

    @property
    def opponent_active_pokemon(self) -> Optional[Pokemon]:
        """
        :return: The opponent active pokemon
        :rtype: Pokemon
        """
        for pokemon in self.opponent_team.values():
            if pokemon.active:
                return pokemon
        return None

    @property
    def opponent_can_dynamax(self) -> bool:
        """
        :return: Whether or not opponent's current active pokemon can dynamax
        :rtype: bool
        """
        return self._opponent_can_dynamax

    @opponent_can_dynamax.setter
    def opponent_can_dynamax(self, value: bool):
        self._opponent_can_dynamax = value

    @property
    def opponent_can_mega_evolve(self) -> Union[bool, List[bool]]:
        """
        :return: Whether or not opponent's current active pokemon can mega-evolve
        :rtype: bool
        """
        return self._opponent_can_mega_evolve

    @opponent_can_mega_evolve.setter
    def opponent_can_mega_evolve(self, value: bool):
        self._opponent_can_mega_evolve = value

    @property
    def opponent_can_tera(self) -> bool:
        """
        :return: Whether or not opponent's current active pokemon can terastallize
        :rtype: bool
        """
        return self._opponent_can_tera

    @property
    def opponent_can_z_move(self) -> Union[bool, List[bool]]:
        """
        :return: Whether or not opponent's current active pokemon can z-move
        :rtype: bool
        """
        return self._opponent_can_z_move

    @opponent_can_z_move.setter
    def opponent_can_z_move(self, value: bool):
        self._opponent_can_z_move = value

    @property
    def trapped(self) -> bool:
        """
        :return: A boolean indicating whether the active pokemon is trapped, either by
            the opponent or as a side effect of one your moves.
        :rtype: bool
        """
        return self._trapped

    @trapped.setter
    def trapped(self, value: bool):
        self._trapped = value

    @property
    def can_mega_evolve_x(self) -> bool:
        """
        :return: Whether or not the current active pokemon can mega evolve X.
        :rtype: bool
        """
        return self._can_mega_evolve_x
    
    @property
    def can_mega_evolve_y(self) -> bool:
        """
        :return: Whether or not the current active pokemon can mega evolve Y.
        :rtype: bool
        """
        return self._can_mega_evolve_y

@dataclass
class BattleOrder:
    order: Optional[Union[Move, Pokemon]]
    mega: bool = False
    megax: bool = False
    megay: bool = False
    z_move: bool = False
    dynamax: bool = False
    terastallize: bool = False
    move_target: int = DoubleBattle.EMPTY_TARGET_POSITION

    DEFAULT_ORDER = "/choose default"

    def __str__(self) -> str:
        return self.message

    @property
    def message(self) -> str:
        if isinstance(self.order, Move):
            if self.order.id == "recharge":
                return "/choose move 1"
            
            message = f"/choose move {self.order.id}"
            # if self.mega:
            #     message += " mega"
            # if self.megax:
            #     message += " megax"
            # if self.megay:
            #     message += " megay"
            # elif self.z_move:
            #     message += " zmove"
            # elif self.dynamax:
            #     message += " dynamax"
            # elif self.terastallize:
            #     message += " terastallize"

            if self.move_target != DoubleBattle.EMPTY_TARGET_POSITION:
                message += f" {self.move_target}"
            return message
        elif isinstance(self.order, Pokemon):
            return f"/choose switch {self.order.species}"
        else:
            return ""

class DefaultBattleOrder(BattleOrder):
    def __init__(self, *args: Any, **kwargs: Any):
        pass

    @property
    def message(self) -> str:
        return self.DEFAULT_ORDER

class Ply(Player):
    async def _create_battle(self, split_message: List[str]) -> AbstractBattle:
        """Returns battle object corresponding to received message.

        :param split_message: The battle initialisation message.
        :type split_message: List[str]
        :return: The corresponding battle object.
        :rtype: AbstractBattle
        """
        # We check that the battle has the correct format
        if split_message[1] == self._format and len(split_message) >= 2:
            # Battle initialisation
            battle_tag = "-".join(split_message)[1:]

            if battle_tag in self._battles:
                return self._battles[battle_tag]
            else:
                gen = GenData.from_format(self._format).gen
                if self.format_is_doubles:
                    battle: AbstractBattle = DoubleBattle(
                        battle_tag=battle_tag,
                        username=self.username,
                        logger=self.logger,
                        save_replays=self._save_replays,
                        gen=gen,
                    )
                else:
                    battle = Battle(
                        battle_tag=battle_tag,
                        username=self.username,
                        logger=self.logger,
                        gen=gen,
                        save_replays=self._save_replays,
                    )

                # Add our team as teampreview_team, as part of battle initialisation
                if isinstance(self._team, ConstantTeambuilder):
                    battle.teampreview_team = set(
                        [
                            Pokemon(gen=gen, teambuilder=tb_mon)
                            for tb_mon in self._team.team
                        ]
                    )

                await self._battle_count_queue.put(None)
                if battle_tag in self._battles:
                    await self._battle_count_queue.get()
                    return self._battles[battle_tag]
                async with self._battle_start_condition:
                    self._battle_semaphore.release()
                    self._battle_start_condition.notify_all()
                    self._battles[battle_tag] = battle

                if self._start_timer_on_battle_start:
                    await self.ps_client.send_message("/timer on", battle.battle_tag)

                return battle
        else:
            self.logger.critical(
                "Unmanaged battle initialisation message received: %s", split_message
            )
            raise ShowdownException()
        
    @staticmethod
    def possible_moves(battle: Battle) -> List[BattleOrder]:
        available_orders = [BattleOrder(move) for move in battle.available_moves]
        available_orders.extend(
            [BattleOrder(switch) for switch in battle.available_switches]
        )

        # if battle.can_mega_evolve and (battle.active_pokemon.species in ["blastoise", "venusaur"]):
        #     available_orders.extend(
        #         [BattleOrder(move, mega=True) for move in battle.available_moves]
        #     )

        # if battle.can_mega_evolve_x:
        #     available_orders.extend(
        #         [BattleOrder(move, megax=True) for move in battle.available_moves]
        #     )
        
        # if battle.can_mega_evolve_y  and (battle.active_pokemon.species in "charizard"):
        #     available_orders.extend(
        #         [BattleOrder(move, megay=True) for move in battle.available_moves]
        #     )
    
        return available_orders

    @staticmethod
    def choose_default_move() -> DefaultBattleOrder:
        """Returns showdown's default move order.

        This order will result in the first legal order - according to showdown's
        ordering - being chosen.
        """
        return DefaultBattleOrder()

    @staticmethod
    def choose_random_singles_move(battle: Battle) -> BattleOrder:
        available_orders = Ply.possible_moves(battle)

        if available_orders:
            return available_orders[int(random.random() * len(available_orders))]
        else:
            return Ply.choose_default_move()
        
    @staticmethod
    def choose_random_move(battle: AbstractBattle) -> BattleOrder:
        """Returns a random legal move from battle.

        :param battle: The battle in which to move.
        :type battle: AbstractBattle
        :return: Move order
        :rtype: str
        """
        if isinstance(battle, DoubleBattle):
            return Player.choose_random_doubles_move(battle)
        elif isinstance(battle, Battle):
            return Ply.choose_random_singles_move(battle)
        else:
            raise ValueError(
                f"battle should be Battle or DoubleBattle. Received {type(battle)}"
            )

    def _create_account_configuration(self, code="default") -> AccountConfiguration:
        key = type(self).__name__
        hk = hashlib.md5(code.encode('utf-8')).hexdigest()[:6]
        CONFIGURATION_FROM_PLAYER_COUNTER.update([key])
        username = "%s%s%d" % (hk, key, CONFIGURATION_FROM_PLAYER_COUNTER[key])
        if len(username) > 18:
            username = "%s%s%d" % (
                hk,
                key[: 18 - len(username)],
                CONFIGURATION_FROM_PLAYER_COUNTER[key],
            )
        return AccountConfiguration(username, code)
    
    @staticmethod
    def create_order(
        order: Union[Move, Pokemon],
        mega: bool = False,
        megax: bool = False,
        megay: bool = False,
        z_move: bool = False,
        dynamax: bool = False,
        terastallize: bool = False,
        move_target: int = DoubleBattle.EMPTY_TARGET_POSITION,
    ) -> BattleOrder:
        """Formats an move order corresponding to the provided pokemon or move.

        :param order: Move to make or Pokemon to switch to.
        :type order: Move or Pokemon
        :param mega: Whether to mega evolve the pokemon, if a move is chosen.
        :type mega: bool
        :param z_move: Whether to make a zmove, if a move is chosen.
        :type z_move: bool
        :param dynamax: Whether to dynamax, if a move is chosen.
        :type dynamax: bool
        :param terastallize: Whether to terastallize, if a move is chosen.
        :type terastallize: bool
        :param move_target: Target Pokemon slot of a given move
        :type move_target: int
        :return: Formatted move order
        :rtype: str
        """
        return BattleOrder(
            order,
            mega=mega,
            megax=megax,
            megay=megay,
            move_target=move_target,
            z_move=z_move,
            dynamax=dynamax,
            terastallize=terastallize,
        )
    
    def __init__(self, *args, code='default', **kwargs):
        super().__init__(*args, account_configuration=self._create_account_configuration(code), **kwargs)

def valid_move(battle: AbstractBattle, move: BattleOrder) -> BattleOrder:
    return move in Ply.possible_moves(battle)

class RPly(Ply):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pr_move = False

    def choose_move(self, battle: AbstractBattle) -> BattleOrder:
        move = self.choose_random_move(battle)
        while not valid_move(battle, move):
            move = self.choose_random_move(battle)

        return move