from collections import defaultdict
import logging
import re
import os

import yaml

_LIB_DIR = os.path.dirname(os.path.realpath(__file__))
SCENARIO_PATH = os.path.join(_LIB_DIR, 'scenario.yml')

_RE_TAGS_1ST_PASS = re.compile(r'\$(?P<cmd>(if|default))(/(?P<thing>\w*)(/(?P<key>\w*)(/(?P<arg>[^$]*))?)?)?\$')
_RE_TAGS_2ND_PASS = re.compile(r'\$(?P<cmd>set)(/(?P<thing>\w*)(/(?P<key>\w*)(/(?P<arg>[^$]*))?)?)?\$')

DIRECTIONS = ('north', 'south', 'east', 'west')
DEFAULT_ROOM = 'throne'

class WorldException(Exception):
    pass

class Room:
    def __init__(self, world, name):
        self.world = world
        self.name = name
        self.description = ''
        self.things = {}
        self.moves = {d: None for d in DIRECTIONS}

    def put_thing(self, thing):
        self.things[thing.name] = thing

    def list_things(self):
        return list(self.things.keys())

    def is_thing_here(self, name):
        return name in self.things

    def init_room(self, directions):
        self.description = directions.get('_description', '')
        self.moves = {d: directions.get(d) for d in DIRECTIONS}

    def go(self, direction):
        return self.moves.get(direction)

    def describe(self):
        name = self.name
        description = self.description
        things = self.list_things()
        moves = ('{}: {}'.format(direction, r)
                 for direction, r in self.moves.items() if r)
        resp = '[{}]: {}\ninteractables: {}\n{}'.format(
                name, description, things, '\n'.join(moves))
        return resp


class Thing:
    pass

class Character(Thing):
    def __init__(self, world, name):
        super().__init__()
        self.world = world
        self.directions = {}
        self.description = ''
        self.no_match = ''
        self.hi = ''
        self.name = name

    def init_character(self, directions):
        try:
            self.description = directions['_description']
            del directions['_description']
        except KeyError:
            pass
        try:
            self.no_match = directions['_no_match']
            del directions['_no_match']
        except KeyError:
            pass
        try:
            self.hi = directions['_hi']
            del directions['_hi']
        except KeyError:
            pass
        self.directions = directions

    def describe(self):
        return self.description

    def hear(self, utterance):
        if '$handshake$' in utterance:
            # Just checking if target can hear. No response required
            return ('$keyword/handshake$', self.hi)
        candidates = [k for k in self.directions.keys() if k[0] != '_']
        match = self.world.lang_best_match(utterance, candidates)
        reply = self.directions.get(match)
        if not reply:
            return ('$keyword/_no_match$', self.no_match)
        return ('$keyword/{}$'.format(match), reply)


class _World(Thing):
    def __init__(self):
        super().__init__()
        self.lang_model = None
        self.rooms = {}
        self.chars = {}
        self._hello = ''

    def _init_room(self, name, directions):
        r = Room(self, name)
        self.rooms[name] = r
        r.init_room(directions)

    def _init_char(self, name, directions):
        c = Character(self, name)
        try:
            room = directions['_room']
            self.rooms[room].put_thing(c)
            del directions['_room']
        except KeyError:
            pass
        self.chars[name] = c
        c.init_character(directions)

    def init_world(self, lang_model):
        logging.info('initializing world')
        self.lang_model = lang_model
        with open(SCENARIO_PATH) as f_scenario:
            scenario = yaml.load(f_scenario)
        self._hello = scenario.get('_hello', '')
        for room_name, directions in scenario['rooms'].items():
            self._init_room(room_name, directions)
        for char_name, directions in scenario['characters'].items():
            self._init_char(char_name, directions)

    def _check_char(self, name):
        try:
            return self.chars[name]
        except KeyError:
            raise WorldException('No character named {}'.format(name))

    def _context_match(self, context, name, reply):
        for candidate in reply:
            match = _RE_TAGS_1ST_PASS.search(candidate)
            if not match:
                raise WorldException('Condition tag not found')
            gd = match.groupdict()
            cmd = gd.get('cmd')
            if cmd == 'if':
                thing = gd.get('thing')
                if thing is None:
                    continue
                if thing == '_me':
                    thing = name
                key = gd.get('key')
                if key is None:
                    continue
                if thing == '_inventory':
                    if key in context['inventory']:
                        return _RE_TAGS_1ST_PASS.sub('', candidate)
                    continue
                if thing == '_world':
                    if key in context['world']:
                        return _RE_TAGS_1ST_PASS.sub('', candidate)
                    continue
                if thing[0] != '_':
                    char = context['characters'].get(thing)
                    if char and key in char:
                        return _RE_TAGS_1ST_PASS.sub('', candidate)
                    continue
                continue
            if cmd == 'default':
                return _RE_TAGS_1ST_PASS.sub('', candidate)
            raise WorldException('Invalid condition tag')
        raise WorldException('No condition met')

    def _context_update(self, context, name, reply):
        prepend = ''
        for match in _RE_TAGS_2ND_PASS.finditer(reply):
            gd = match.groupdict()
            cmd = gd.get('cmd')
            if cmd == 'set':
                thing = gd.get('thing')
                if thing == '_me':
                    thing = name
                if thing == '_inventory':
                    key = gd.get('key')
                    if key:
                        context['inventory'].append(key)
                        prepend += '$acquire/{}$ '.format(key)
                elif thing == '_world':
                    key = gd.get('key')
                    if key:
                        val = gd.get('arg')
                        if not val:
                            val = True
                        context['world'][key] = val
                elif thing[0] != '_':
                    key = gd.get('key')
                    if key:
                        val = gd.get('arg')
                        if not val:
                            val = True
                        try:
                            char = context['characters'][thing]
                        except KeyError:
                            char = {}
                            context['characters'][thing] = char
                        char[key] = val

        return prepend + _RE_TAGS_2ND_PASS.sub('', reply)

    def hear(self, context, name, utterance):
        (pre_tags, reply) = self._check_char(name).hear(utterance)
        if isinstance(reply, list):
            reply = self._context_match(context, name, reply)
        reply = self._context_update(context, name, reply)
        return pre_tags + ' ' + ' '.join(reply.split())

    def describe_char(self, context, name):
        return self._check_char(name).describe()

    def describe_room(self, context, name):
        if name == '_this':
            name = context.get('room')
        try:
            room = self.rooms[name]
        except KeyError:
            raise WorldException('No room named {}'.format(name))
        return room.describe()

    def lang_best_match(self, utterance, candidates):
        return self.lang_model.match(utterance, candidates)

    def can_hear(self, context, name):
        room = self.rooms[context['room']]
        return room.is_thing_here(name)

    def go(self, context, direction):
        room = self.rooms[context['room']]
        moved_to = room.go(direction)
        if not moved_to:
            return None
        context['room'] = moved_to
        return moved_to

    def get_default_context(self):
        return dict(inventory=[],
                    world = {},
                    characters = {},
                    room=DEFAULT_ROOM)

    def get_inventory(self, context):
        inv = context.get('inventory', [])
        if len(inv) < 1:
            return 'Not carrying anything'
        return 'You are carrying:\n{}'.format(',\n'.join(inv))

    def hello(self):
        return self._hello

WORLD = _World()
