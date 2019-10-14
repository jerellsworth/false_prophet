#!/usr/bin/env python

# TODO move between rooms
# TODO check who is in what room before conversing

import base64
import json
import os
import pathlib
import pickle
import re

import requests

# TODO NEXT 
# * write EQ5 scenario
# * compile to single web site or exe

CHEAT_MODE = True

HOST = 'http://127.0.0.1'
PORT = 2125
PREFIX = 'v1/'
COOKIE_KEY = 'fb2_eq5'

DIRECTIONS = {'n': 'north', 's': 'south', 'e':r'east', 'w': 'west'}

_RE_TAGS = re.compile(r'\$(?P<cmd>\w*)(/(?P<thing>\w*)(/(?P<key>\w*)(/(?P<arg>[^$]*))?)?)?\$')

SAVE_DIR = os.expanduser('~/.false_prophet')

def _decode_context(raw):
    if not raw:
        return raw
    return json.loads(
            base64.b64decode(raw).decode('utf-8'))

class ReplyError(Exception):
    pass

def _get(session, endpoint):
    url = '{}:{}/{}{}'.format(HOST, PORT, PREFIX, endpoint)
    resp = session.get(url)
    return resp.text

def _post(session, endpoint, **kwargs):
    url = '{}:{}/{}{}'.format(HOST, PORT, PREFIX, endpoint)
    resp = session.post(url, data=kwargs)
    if not resp.ok:
        raise ReplyError(resp.text)
    return resp.text

def init_game():
    session = requests.Session()
    print(_post(session, 'start'))
    return session

def save(session, tag):
    pathlib.path(SAVE_DIR).mkdir(parents=True, exist_ok=True)
    target = os.path.join(SAVE_DIR, tag)
    with open(target, 'wb') as fin:
        pickle.dump(session.cookies, fin)

def restore(session, tag):
    target = os.path.join(SAVE_DIR, tag)
    if not os.path.isfile(target):
        print('No save named: {}'.format(tag))
        return session
    new_session = requests.session()
    with open(target, 'rb') as f:
        new_session.cookies.update(pickle.load(fin))
    return new_session

def look(session, thing=None):
    if thing:
        print(_get(
            session,
            'character/{}'.format(thing)))
        return
    print(_get(
        session,
        'room/_this'))

def go(session, direction):
    if direction not in DIRECTIONS:
        print('{} is not a valid direction'.format(direction))
        return
    try:
        new_room = _post(
                session,
                'go/{}'.format(DIRECTIONS[direction]))
    except ReplyError as e:
        print(e)
        return
    print('moved to {}'.format(new_room))


def _handle_tags(session, reply, name):
    # TODO handle a bunch of other tags
    for match in _RE_TAGS.finditer(reply):
        gd = match.groupdict()
        cmd = gd.get('cmd')
        if cmd == 'acquire':
            thing = gd.get('thing')
            print('You got {}!'.format(thing))
        elif cmd == 'keyword':
            if CHEAT_MODE:
                thing = gd.get('thing')
                print('(keyword: {})'.format(thing))
        elif cmd == 'win':
            print('You win!')
            exit(0)

    return _RE_TAGS.sub('', reply)

def talk(session, name):
    try:
        reply = _post(
                session,
                'character/{}'.format(name),
                say='$handshake$')
        reply = _handle_tags(session, reply, name)
        print(reply)
    except ReplyError as e:
        print(e)
        return
    while True:
        say = input('<{}> '.format(name))
        if say.lower().strip() == 'bye' or say == 'q':
            break
        else:
            reply = _post(
                    session,
                    'character/{}'.format(name),
                    say=say)
            reply = _handle_tags(session, reply, name)
            print(reply)

def inventory(session):
    print(_get(session, 'inventory'))

def cli_help():
    print('Explore mode help')
    print('(q)uit')
    print('(h)elp: print this message')
    print('(l)ook: look around')
    print('(l)ook THING: look at THING')
    print('(t)alk CHARACTER: talk to CHARACTER')
    print('(u)se THING: interact with THING')
    print('(i)nventory: list inventory')
    print('(g)o DIRECTION: Go in DIRECTION (north south east or wesst)')
    print('(s)ave TAG: Save a game under name TAG')
    print('(r)estore TAG: restore saved game called TAG')
    print()

def outer_repl():
    session = init_game()
    while True:
        command = input('> ').lower().split()
        cmd_0 = command[0][0]
        if cmd_0 == 'q':
            exit(0)
        elif cmd_0 == 'h':
            cli_help()
        elif cmd_0 == 's':
            tag = 'default'
            if len(command) > 1:
                tag = command[1]
            save(session, tag)
        elif cmd_0 == 'r':
            tag = 'default'
            if len(command) > 1:
                tag = command[1]
            session = restore(session, tag)
        elif cmd_0 == 'l':
            thing = None
            if len(command) > 1:
                thing = command[1]
            look(session, thing)
        elif (cmd_0 == 't'
              or cmd_0 == 'u') and len(command) > 1:
            talk(session, command[1])
        elif cmd_0 == 'i':
            inventory(session)
        elif cmd_0 == 'c' and CHEAT_MODE:
            print(_decode_context(session.cookies.get(COOKIE_KEY)))
        elif cmd_0 in ('n', 's', 'e', 'w'):
            go(session, cmd_0)
        elif cmd_0 == 'g' and len(command) > 1:
            go(session, command[1][0])
        else:
            print('could not understand: {}'.format(' '.join(command)))

if __name__ == '__main__':
    outer_repl()
