import base64
import json

from flask import Flask
from flask import request
from flask import Response

from world import WORLD
from language import MODEL

COOKIE_KEY = 'fb2_eq5'

app = Flask(__name__)

def _encode_context(context):
    return base64.b64encode(json.dumps(context).encode('utf-8'))

def _decode_context(raw):
    return json.loads(
            base64.b64decode(raw).decode('utf-8'))

def _get_ctx():
    cookie = request.cookies.get(COOKIE_KEY)
    if cookie:
        return _decode_context(cookie)
    return WORLD.get_default_context()

@app.route('/v1/character/<name>', methods=['POST', 'GET'])
def v1_character(name):
    context = _get_ctx()
    if request.method == 'POST':
        if not WORLD.can_hear(context, name):
            return Response('{} cannot hear'.format(name), status=404)
        utterance = request.form.get('say')
        resp = Response(WORLD.hear(context, name, utterance), status=200)
        resp.set_cookie(COOKIE_KEY, _encode_context(context))
        return resp
    elif request.method == 'GET':
        return Response(WORLD.describe_char(context, name), status=200)

@app.route('/v1/go/<direction>', methods=['POST'])
def v1_go(direction):
    context = _get_ctx()
    result = WORLD.go(context, direction)
    if result:
        resp = Response('{}'.format(result), status=200)
        resp.set_cookie(COOKIE_KEY, _encode_context(context))
        return resp
    return Response('Cannot go {}'.format(direction), status=404)


@app.route('/v1/room/<name>', methods=['GET'])
def v1_room(name):
    context = _get_ctx()
    return Response(WORLD.describe_room(context, name), status=200)

@app.route('/v1/inventory', methods=['GET'])
def v1_inventory():
    context = _get_ctx()
    return Response(WORLD.get_inventory(context), status=200)

@app.route('/v1/start', methods=['POST'])
def v1_start():
    context = _get_ctx()
    resp = Response(WORLD.hello(), status=200)
    resp.set_cookie(COOKIE_KEY, _encode_context(context))
    return resp

if __name__ == '__main__':
    MODEL.init_model()
    WORLD.init_world(MODEL)
    app.run(host='127.0.0.1', port=2125)
