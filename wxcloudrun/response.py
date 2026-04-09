import json
import uuid

from flask import Response


def make_succ_empty_response():
    data = json.dumps({'code': 0, 'data': {}})
    return Response(data, mimetype='application/json')


def make_succ_response(data):
    data = json.dumps({'code': 0, 'data': data})
    return Response(data, mimetype='application/json')


def make_err_response(err_msg):
    data = json.dumps({'code': -1, 'errorMsg': err_msg})
    return Response(data, mimetype='application/json')


def make_v1_response(code, message, data=None, request_id=None, http_status=200):
    rid = request_id or "trace-{}".format(uuid.uuid4().hex)
    body = {
        "code": code,
        "message": message,
        "requestId": rid,
        "data": data if data is not None else {}
    }
    payload = json.dumps(body, ensure_ascii=False)
    return Response(payload, status=http_status, mimetype='application/json')


def make_v1_succ_response(data=None, message="ok", request_id=None):
    return make_v1_response(0, message, data=data, request_id=request_id, http_status=200)


def make_v1_err_response(code, message, request_id=None, http_status=400, data=None):
    return make_v1_response(code, message, data=data, request_id=request_id, http_status=http_status)
