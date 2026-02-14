import copy
import random
import os
import time
from pathlib import Path
from collections import Counter, defaultdict

import map_parser as p

TILE_LIMIT = 19
LOCK_SEED = False
BOUNDARY_LIMIT = 4000 # True limit is 4096, but this prevents placing cap tiles
OVERRIDE_SEED = 0#436750099

# + start tile
# + random
# + limit gen (cap all remaining connectors)
# + check collisions for every brush
# todo check tiles on load:
# - for correct connector rotation
# - for 1 brush (what about ducts?)

# TODO / IDEAS:
# - set boundary_limit dynamically by checking cap tiles dimensions

def center(ent):
    xs = []
    ys = []
    zs = []
    for face in ent.brushes[0].faces:
        x, y, z = list(zip(*face.points))
        xs.extend(x)
        ys.extend(y)
        zs.extend(z)
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2


def min_max(brush):
    xs = []
    ys = []
    zs = []
    for face in brush.faces:
        x, y, z = list(zip(*face.points))
        xs.extend(x)
        ys.extend(y)
        zs.extend(z)
    return (min(xs), max(xs)), (min(ys), max(ys)), (min(zs), max(zs))


def get_connectors(tile, con_type=None):
    connectors = list()

    for i, ent in enumerate(tile.entities):
        if ent.params["classname"] == "info_connector":
            if con_type is None or con_type == ent.params["name"]:
                connectors.append((i, ent))

    return connectors


def get_angle(connector_ent):
    return int(connector_ent.params["angles"].split()[1])


def vec_diff(a, b):
    x1,y1,z1 = a
    x2,y2,z2 = b
    return [x1-x2, y1-y2, z1-z2]


def gather_brushes(map_):
    brushes = [*map_.worldspawn.brushes]
    for ent in map_.entities:
        if ent.params["classname"] == "info_connector":
            continue
        brushes += ent.brushes
    return brushes


def is_intersect(root, tmp_tile):
    root_brushes = gather_brushes(root)
    tile_brushes = gather_brushes(tmp_tile)

    for brush_a in root_brushes:
        for brush_b in tile_brushes:
            a = min_max(brush_a)
            b = min_max(brush_b)

            strike = 0
            for i in range(3):
                a_min, a_max = a[i]
                b_min, b_max = b[i]
                if a_min < b_max and a_max > b_min:
                    strike += 1

            if strike == 3:
                print(brush_a)
                print(brush_b)
                if str(brush_a) == str(brush_b):
                    print("error: brushes are identical")
                #print("intersection")
                return True
            # else:
            #     print("Ok")
    return False

def is_outside_world_boundry(tmp_tile):
    for brush in tmp_tile.worldspawn.brushes:
        a = min_max(brush)
        for i in range(3):
            for j in range(2):
                if a[i][j] > BOUNDARY_LIMIT or a[i][j] < -BOUNDARY_LIMIT:
                    return True
    return False

def load_tileset(tileset_dir: Path):
    print("loading tileset:", tileset_dir)

    start_tiles = list()
    cap_tiles = list()
    tiles = list()

    for basename in os.listdir(tileset_dir):
        path = tileset_dir / basename
        if not os.path.isfile(path):
            continue

        # Ignore sledgehammer autosaves
        if '.auto.' in basename:
            continue

        # Ignore not *.map files
        if not basename.endswith(".map"):
            continue

        print("  ", basename)

        if basename == "start.map" or basename.startswith("start_"):
            start_tiles.append((p.parse_map(open(path)), basename))
            continue

        if basename == "cap.map" or basename.startswith("cap_"):
            cap_tiles.append((p.parse_map(open(path)), basename))
            continue

        tiles.append((p.parse_map(open(path)), basename))

    return start_tiles, cap_tiles, tiles


def load_tiles(root_dir: Path):
    tilesets = dict()

    for basename in os.listdir(root_dir):
        path = root_dir / basename
        if os.path.isdir(path):
            tilesets[basename] = load_tileset(path)

    return tilesets

def rename_entities(tile, prefix: int):
    """ Rename certain values of properties to avoid collision.
        Example:
            target: exit_door1  ->  target: tile008_exit_door1

        If name starts with `g_` then it is global across all tiles
        Also there are special names:
        - `$count$<enity_name>` - replaced with int count of entities
                                  with name "enity_name"
    """
    param_names = [
        "target",
        "targetname",
        "killtarget",
    ]
    for ent in tile.entities:
        for name in param_names:
            if name in ent.params and ent.params[name] != "":
                if ent.params[name].startswith("g_"):
                    continue
                elif ent.params[name].startswith("$count$"):
                    continue # see `apply_special_count()`
                elif (ent.params["classname"] == "game_player_equip"
                and ent.params[name] == "game_playerspawn"):
                    continue
                else:
                    ent.params[name] = f"tile{prefix:03}_{ent.params[name]}"



def apply_special_count(root):
    counters_to_replace = []
    counter = defaultdict(int)
    # TODO: currently works only with "Limit value" (health) of game_counter
    for i, ent in enumerate(root.entities):
        if "health" in ent.params and ent.params["health"].startswith("$count$"):
            counters_to_replace.append((i, ent.params["health"][7:]))

    for i, ent in enumerate(root.entities):
        for _, name in counters_to_replace:
            if "targetname" in ent.params and ent.params["targetname"] == name:
                counter[name] += 1

    print("Replace counters:")
    for idx, name in counters_to_replace:
        print(idx, name, counter[name])
        root.entities[idx].params["health"] = counter[name]


def apply_entity_mapgen_choice(tile):
    other_entities = list()
    choice_entities = list()
    weights = list()

    for ent in tile.entities:
        if "mapgen_choice" in ent.params:
            choice_entities.append(ent)
            weights.append(float(ent.params["mapgen_choice"]))
            del ent.params["mapgen_choice"]
        else:
            other_entities.append(ent)

    if len(choice_entities) == 0:
        return

    ent = random.choices(population=choice_entities, weights=weights)[0]
    other_entities.append(ent)
    tile.entities = other_entities


def main():
    if LOCK_SEED:
        seed = 1337
        random.seed(seed)
    elif OVERRIDE_SEED != 0:
        seed = OVERRIDE_SEED
    else:
        seed = random.randint(100_000_000, 999_999_999)
    random.seed(seed)

    tilesets = load_tiles(Path("./tilesets"))
    start_tiles, cap_tiles, tiles = tilesets["simple"]
    root = p.parse_map(open("tiles/empty.map"))

    xxx_crates = p.parse_map(open("tilesets/simple/crates_empty.map"))
    print("xxx_crates", len(xxx_crates.worldspawn.brushes))
    #input()

    # first tile
    start_tile = random.choice(start_tiles)[0]
    rename_entities(start_tile, 0)
    root.merge(start_tile)

    # Iterate over connectors until all a filled
    print("Root Connectors:")

    counter = 0
    success = True
    tile_stats = []

    while True:
        counter += 1

        print("-"*20)

        root_connectors = get_connectors(root)
        print("loop, number of connectors:", len(root_connectors))

        if len(root_connectors) == 0:
            break

        idx_a, ent = random.choice(root_connectors)

        # print(ent.params)
        con_a = center(ent)
        # print("center:", con_a)
        angle_a = get_angle(ent)

        # Choose tile
        # TODO: instead of range(10) enumerate tiles and connectors and go thru them.
        #       When there is 1 tile with 2 connectors, this loop needlesly tries and fails 10 times
        for _ in range(10):
            is_could_not_place_tile = False
            is_intersect_fail = False

            if ent.params["name"] == "crates" and _ > 7:
                print("CARATEAS")
                tile = xxx_crates
                tile_name = "crates_empty.map"
                print("debug:", tile_name, len(tile.worldspawn.brushes))
                #time.sleep(2)
            else:
                tile, tile_name = random.choice(tiles if counter < TILE_LIMIT else cap_tiles)

            tmp_tile = copy.deepcopy(tile)
            print("debug:", tile_name, len(tmp_tile.worldspawn.brushes))

            connectors = get_connectors(tmp_tile, ent.params["name"])
            if len(connectors) == 0:
                print("No connectors with name", ent.params["name"])
                # TODO: meaningful error when we had too many tries fail
                continue

            idx_b, connector = random.choice(connectors)
            angle_b = get_angle(connector)
            # print("angle math:")
            # print("  angle_a: ", angle_a)
            # print("  angle_b: ", angle_b)
            # print("  angle_a - angle_b: ", angle_a - angle_b)
            ang = (180 - (angle_a - angle_b) ) % 360
            # print("  (180 - abs(angle_a - angle_b) ) % 360: ", ang)
            tmp_tile.rotate(ang)
            con_b = center(connector)

            tmp_tile.move(vec_diff(con_a, con_b))

            # Now that new tile is in place, we have to check
            # for brush collision before merging
            print("debug:", tile_name, len(tmp_tile.worldspawn.brushes))
            if is_intersect(root, tmp_tile):
                # tile didn't fit
                # choose different tile
                # todo: try different connector
                is_intersect_fail = True
                print("  intersection", tile_name)
                continue

            if is_outside_world_boundry(tmp_tile):
                is_could_not_place_tile = True
                print("  outside world boundry", tile_name)
                continue

            break # good tile fits perfectly
        else:
            is_could_not_place_tile = True
            print("ent", repr(ent), connectors, "connector_name:", ent.params["name"], ent.brushes[0].faces[0].points)


        if is_could_not_place_tile:
            print("error: Could not place any tile")
            success = False
            break


        # remove connectors
        if not is_intersect_fail:
            root.entities.pop(idx_a)
            tmp_tile.entities.pop(idx_b)
            print("connectors_to_remove:", idx_a, idx_b)
        else:
            print("keeping connector")


        print("merge tile  - ", tile_name)
        rename_entities(tmp_tile, counter)

        # trying to not break seeds, by storing state
        rnd_state = random.getstate()
        apply_entity_mapgen_choice(tmp_tile)
        random.setstate(rnd_state)

        root.merge(tmp_tile)
        tile_stats.append(tile_name)

        # Find extra overlaping connectors:
        connectors_to_remove = set()
        root_connectors = get_connectors(root)
        for idx, (i, ent) in enumerate(root_connectors):
            for j, other_ent in root_connectors[idx+1:]:
                if center(ent) == center(other_ent) and get_angle(ent) == (get_angle(other_ent) + 180) % 360:
                    connectors_to_remove.add(i)
                    connectors_to_remove.add(j)
                    continue

        root.entities = [ent for i, ent in enumerate(root.entities) if i not in connectors_to_remove]

        if is_intersect_fail:
            print("breaking gen early")
            success = False
            break

    apply_special_count(root)

    print("Saving map to out.map")
    root.write("out.map")
    print("Seed used:", seed)

    return success, tile_stats


def debug_count_textures(root):
    count = 0
    for brush in root.worldspawn.brushes:
        for face in brush.faces:
            if face.texture == "LAB1_DOOR2B":
                count += 1

    for ent in root.entities:
        for brush in ent.brushes:
            for face in brush.faces:
                if face.texture == "LAB1_DOOR2B":
                    count += 1

    return count


if __name__ == '__main__':
    for i in range(10):
        success, stats = main()
        # if "ramp.map" in stats:
        #     print("done")
        #     exit()
        if success:
            for k,v in Counter(stats).items():
                print(k, v)
            break
