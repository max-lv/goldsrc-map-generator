
import re
import io

# from python docs: https://docs.python.org/3/library/re.html#simulating-scanf
FLOAT_REGEX = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
NUM_REGEX = r'[-+]?\d+(?:\.\d*)'
# r'\( ([-+]?\d+) ([-+]?\d+) ([-+]?\d+) \) '
BRUSH_FACE_REGEXP = re.compile(
    r'^\s*'
    f'( ({NUM_REGEX}) ({NUM_REGEX}) ({NUM_REGEX}) ) '
    f'( ({NUM_REGEX}) ({NUM_REGEX}) ({NUM_REGEX}) ) '
    f'( ({NUM_REGEX}) ({NUM_REGEX}) ({NUM_REGEX}) ) '
    r'([A-Z0-9-+{_~]+) ' # texture name
    # texture attributes
    f'\\[ ({FLOAT_REGEX}) ({FLOAT_REGEX}) ({FLOAT_REGEX}) ({FLOAT_REGEX}) \\] ' # ? ? ? offset-X
    f'\\[ ({FLOAT_REGEX}) ({FLOAT_REGEX}) ({FLOAT_REGEX}) ({FLOAT_REGEX}) \\] ' # ? ? ? offset-Y
    f'({FLOAT_REGEX}) ({FLOAT_REGEX}) ({FLOAT_REGEX})' # degree, scale-X, scale-Y
)

BRUSH_FACE_REGEXP = re.compile(r"(\s[-+]?\d+\.\d+|[A-Z0-9-+{_~]+)")


def rotate(point, deg):
    x,y,z = point
    deg = deg % 360
    if deg == 0:
        return [x,y,z,]
    elif deg == 90:
        return [y,x*-1,z,]
    elif deg == 180:
        return [x*-1,y*-1,z,]
    elif deg == 270:
        return [y*-1,x,z,]

    raise Exception('This is unreachable')


def sign(x):
    if x == 0:
        return 0
    elif x > 0:
        return 1
    else:
        return -1


class Face:
    def __init__(self, points, texture, texture_attr):
        self.points = [[float(v) for v in point] for point in points]
        self.texture = texture
        self.texture_attr = texture_attr

    def _fmt_point(self, point):
        return f'( {point[0]} {point[1]} {point[2]} )'

    def __str__(self):
        # example output:
        # ( -128 128 0 ) ( 128 128 0 ) ( 128 -128 0 ) CRETE4_FLR03 [ 1 0 0 0 ] [ 0 -1 0 0 ] 0 1 1 
        attr = self.texture_attr
        return (
            ' '.join(self._fmt_point(p) for p in self.points) +
            f' {self.texture} '
            f"[ {' '.join(str(v) for v in attr['tex-point-1'])} {attr['offset-x']} ] "
            f"[ {' '.join(str(v) for v in attr['tex-point-2'])} {attr['offset-y']} ] "
            f"{attr['degree']} {attr['scale-x']} {attr['scale-y']}"
        )


class Brush:
    def __init__(self, brush_str):
        names = 'x1 y1 z1 x2 y2 z2 x3 y3 z3 texture tx1 ty1 tz1 offset-x tx2 ty2 tz2 offset-y degree scale-x scale-y'.split()

        faces = list()
        for line in brush_str.split('\n'):
            #m = BRUSH_FACE_REGEXP.match(line)
            if line in "{}":
                continue

            m = line.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
            m = m.split()

            #m = BRUSH_FACE_REGEXP.findall(line)

            if len(m) != len(names):
                print('===[ Error ]===')
                print("line:", line)
                print("length:", len(m), len(names))
                print("m:", m)
                exit(42)

            data = dict(zip(names, m))
            # print(data)

            points = [
                (data['x1'], data['y1'], data['z1'],),
                (data['x2'], data['y2'], data['z2'],),
                (data['x3'], data['y3'], data['z3'],),
            ]

            texture_attributes = {
                'tex-point-1': [float(v) for v in [data['tx1'], data['ty1'], data['tz1']]],
                'tex-point-2': [float(v) for v in [data['tx2'], data['ty2'], data['tz2']]],
            }
            for k in ['offset-x', 'offset-y', 'degree', 'scale-x', 'scale-y']:
                texture_attributes[k] = float(data[k])

            faces.append(Face(points, data['texture'], texture_attributes))

        self.faces = faces

    def move(self, vec):
        for face in self.faces:
            for p in face.points:
                p[0] += vec[0]
                p[1] += vec[1]
                p[2] += vec[2]

            # TODO:
            # # tex-point is vector along the face of the texture, it precisesly describe texture rotation on the face. But fails to communicate normal vector
            # tex_point = [a+b for a,b in zip(face.texture_attr['tex-point-1'], face.texture_attr['tex-point-2'])]

            # # TODO: This covers X coordinate, but I fail to understand when to descrese offset and when to increase
            # if tex_point[1] == 0 or tex_point[2] == 0:
            #     pass

            # continue

            # About texture move: I have no idea what `tex-point` means, I just looked at differences in ".map" file and wrote ifs accordingly
            # This definitly doesn't work for brushes with not-right-angles (brushes rotated by 45 degrees etc.)

            sign_x = sign(face.texture_attr['scale-x'])
            sign_y = sign(face.texture_attr['scale-y'])

            # X Texture Move
            if face.texture_attr['tex-point-1'] == [-1, 0, 0] and face.texture_attr['tex-point-2'] == [0, -1, 0]:
                face.texture_attr['offset-x'] += vec[0] * sign_x
            if face.texture_attr['tex-point-1'] == [1, 0, 0] and face.texture_attr['tex-point-2'] == [0, -1, 0]:
                face.texture_attr['offset-x'] -= vec[0] * sign_x
            if face.texture_attr['tex-point-1'] == [-1, 0, 0] and face.texture_attr['tex-point-2'] == [0, 0, -1]:
                face.texture_attr['offset-x'] += vec[0] * sign_x
            if face.texture_attr['tex-point-1'] == [1, 0, 0] and face.texture_attr['tex-point-2'] == [0, 0, -1]:
                face.texture_attr['offset-x'] -= vec[0] * sign_x

            # Y Texture Move
            if face.texture_attr['tex-point-1'] == [0, 1, 0]:
                face.texture_attr['offset-x'] -= vec[1] * sign_x
            if face.texture_attr['tex-point-1'] == [0, -1, 0]:
                face.texture_attr['offset-x'] += vec[1] * sign_x
            if face.texture_attr['tex-point-1'] == [1, 0, 0] and face.texture_attr['tex-point-2'] == [0, -1, 0]:
                face.texture_attr['offset-y'] += vec[1] * sign_y
            if face.texture_attr['tex-point-1'] == [-1, 0, 0] and face.texture_attr['tex-point-2'] == [0, -1, 0]:
                face.texture_attr['offset-y'] += vec[1] * sign_y

            # Z texture move
            if face.texture_attr['tex-point-1'] == [0, 0, -1] and face.texture_attr['tex-point-2'] == [0, 1, 0]:
                face.texture_attr['offset-x'] += vec[2] * sign_x
            if face.texture_attr['tex-point-1'] == [0, 0, 1] and face.texture_attr['tex-point-2'] == [0, 1, 0]:
                face.texture_attr['offset-x'] -= vec[2] * sign_x
            # possibly not needed? (added by mistake)
            if face.texture_attr['tex-point-1'] == [1, 0, 0] and face.texture_attr['tex-point-2'] == [0, 0, -1]:
                face.texture_attr['offset-y'] += vec[2] * sign_y
            # possibly not needed? (added by mistake)
            if face.texture_attr['tex-point-1'] == [-1, 0, 0] and face.texture_attr['tex-point-2'] == [0, 0, -1]:
                face.texture_attr['offset-y'] += vec[2] * sign_y
            if face.texture_attr['tex-point-1'] == [0, 1, 0] and face.texture_attr['tex-point-2'] == [0, 0, -1]:
                face.texture_attr['offset-y'] += vec[2] * sign_y
            if face.texture_attr['tex-point-1'] == [0, -1, 0] and face.texture_attr['tex-point-2'] == [0, 0, -1]:
                face.texture_attr['offset-y'] += vec[2] * sign_y


        return self

    def rotate(self, deg):
        assert deg % 90 == 0, 'only right angle rotation is supported'

        if deg == 0:
            return self

        for face in self.faces:
            for i, p in enumerate(face.points):
                face.points[i] = rotate(p, deg)

            if deg % 180 == 90:
                x,y,z = face.texture_attr['tex-point-1']
                face.texture_attr['tex-point-1'] = [y,x,z]
                x,y,z = face.texture_attr['tex-point-2']
                face.texture_attr['tex-point-2'] = [y,x,z]

            if deg in [180, 90]:
                if face.texture_attr['tex-point-1'][0] == 0 and face.texture_attr['tex-point-2'][0] == 0:
                    face.texture_attr['scale-x'] *= -1

            if deg in [180, 270]:
                if face.texture_attr['tex-point-1'][1] == 0 and face.texture_attr['tex-point-2'][1] == 0:
                    face.texture_attr['scale-x'] *= -1

        return self

    def __str__(self):
        return '{\n' + '\n'.join(str(f) for f in self.faces) + '\n}'


class Entity:
    def __init__(self, params, brushes=None):
        assert isinstance(brushes, (type(None), list))
        if brushes is None:
            brushes = list()

        self.params = params
        self.brushes = brushes

    def move(self, vec):
        for b in self.brushes:
            b.move(vec)

        if 'origin' in self.params:
            x,y,z = [float(v) for v in self.params['origin'].split(' ')]
            dx,dy,dz = vec
            self.params['origin'] = f'{x+dx} {y+dy} {z+dz}'

        return self

    def rotate(self, deg):
        if self.brushes is not None:
            for b in self.brushes:
                b.rotate(deg)

        if 'origin' in self.params:
            point = [float(v) for v in self.params['origin'].split(' ')]
            x,y,z = rotate(point, deg)
            self.params['origin'] = f'{x} {y} {z}'

        if "angles" in self.params:
            # print("-------------")
            # print("debug:", self.params["classname"])
            # print("debug: rotate angles")
            # print("debug: before", self.params["angles"])
            a,b,c = self.params["angles"].split()
            self.params["angles"] = f"{a} {(float(b) - deg) % 360:.0f} {c}"
            # print("debug: after", self.params["angles"])

        return self

    def __str__(self):
        s = '{\n'

        fmt_param = lambda k,v: f'"{k}" "{v}"\n'

        if 'classname' in self.params:
            s += fmt_param('classname', self.params['classname'])

        for k,v in self.params.items():
            if k == 'classname':
                continue

            s += fmt_param(k, v)

        for b in self.brushes:
            s += str(b) + '\n'

        s += '}\n'

        return s

    def __repr__(self):
        return f"<Entity classname={self.params.get('classname', "-")} origin={self.params.get('origin', "-")}>"


class Map:
    def __init__(self, entities):
        assert isinstance(entities, list)

        worldspawn_idx = None
        for i, e in enumerate(entities):
            if e.params['classname'] == 'worldspawn':
                worldspawn_idx = i
                break

        assert worldspawn_idx is not None, 'Map doesn\'t contain worldspawn entity'

        self.worldspawn = entities[worldspawn_idx]
        self.entities = entities[:worldspawn_idx] + entities[worldspawn_idx+1:]

    def merge(self, other_map):
        """NOTE: only merges brushes and entities, but ignores worldspawn' params"""
        this_worldspawn  = self.worldspawn      is not None and self.worldspawn.brushes      is not None
        other_worldspawn = other_map.worldspawn is not None and other_map.worldspawn.brushes is not None
        if this_worldspawn and other_worldspawn:
            self.worldspawn.brushes = self.worldspawn.brushes + other_map.worldspawn.brushes
        elif this_worldspawn:
            # we already good, do nothing
            pass
        elif other_worldspawn:
            self.worldspawn.brushes = other_map.worldspawn.brushes

        # merge entities
        self.entities = self.entities + other_map.entities

        return self

    def move(self, vec):
        self.worldspawn.move(vec)

        for ent in self.entities:
            ent.move(vec)

        return self

    def rotate(self, deg):
        self.worldspawn.rotate(deg)

        for ent in self.entities:
            ent.rotate(deg)

        return self

    def text(self):
        return str(self.worldspawn) + ''.join(str(ent) for ent in self.entities)

    def __repr__(self):
        brushes_len = len(self.worldspawn.brushes) \
            if self.worldspawn is not None and self.worldspawn.brushes is not None else None
        return f'<Map brushes={brushes_len} entities={len(self.entities)}>'

    def write(self, filepath):
        with io.open(filepath, 'w', newline='\r\n') as f:
            f.write(self.text())


def parse_brushes(s):
    brushes = re.findall(r'^({[\s\S]+?}\s*)', s, re.MULTILINE)
    # print('groups', brushes)
    # for x in brushes:
    #     print(x.strip())

    return [Brush(b.strip()) for b in brushes]


def parse_entity(s):
    # remove outer `{` and `}`
    s = s[s.find('{')+1:s.rfind('}')].strip()
    # print('------------------------')
    # print('parse_entity', s)
    # print()

    params = dict()
    brushes = None
    for line in s.split('\n'):
        if '{' in line:
            brushes_str = s[s.find('{'):s.rfind('}')+1].strip()
            brushes = parse_brushes(brushes_str)
            break

        key, value = line.strip()[1:-1].split('" "')
        params[key] = value
    return Entity(params, brushes)


def parse_map(_map):
    if isinstance(_map, io.IOBase):
        tmp = _map.read()
        _map.close()
        _map = tmp

    _map = _map.strip()

    entities = list()

    buf = ''
    depth = 0
    for raw_line in _map.split('\n'):
        line = raw_line.strip()
        if line == '{':
            depth += 1
        elif line == '}':
            if depth == 1:
                buf += raw_line + '\n'
                ent = parse_entity(buf)
                entities.append(ent)


                # reset
                buf = ''
                depth = 0
                continue

            depth -= 1

        buf += raw_line + '\n'

    return Map(entities)


if __name__ == '__main__':
    _map = open('tiles/line.map', 'r').read()
    _map = parse_map(_map)

    print('parsed map:')
    for ent in _map.entities:
        print(ent)


    # _map.rotate(180)
    _map.write('out.map')
