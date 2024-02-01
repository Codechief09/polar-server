class Cors:
    @classmethod
    def options_cors(cls):
        return {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET',
            'Access-Control-Allow-Headers': '*',
            'Access-Control-Max-Age': '3600'
        }

    @classmethod
    def cors_headers(cls):
        return {
            'Access-Control-Allow-Origin': '*'
        }
