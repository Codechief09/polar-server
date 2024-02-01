from firebase_admin import auth


def options_cors():
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET',
        'Access-Control-Allow-Headers': '*',
        'Access-Control-Max-Age': '3600'
    }
    return ('', 204, headers)


def cors_headers():
    return {
        'Access-Control-Allow-Origin': '*'
    }


def verified_uid(request):
    id_token = request.headers.get('Authorization')
    # verify token
    decoded_token = auth.verify_id_token(id_token)
    # get uid
    uid = decoded_token['uid']
    return uid
