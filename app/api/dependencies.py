import os

from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyQuery
from starlette.status import HTTP_403_FORBIDDEN


API_KEY_NAME = 'token'

api_key_query = APIKeyQuery(name=API_KEY_NAME, auto_error=False)

try:
    path = os.path.join(os.getcwd(), '.env')
    with open (path, 'r') as env_file:
        lines = env_file.readlines()
        env = {l.split('=')[0]: l.split('=')[1].strip() for l in lines}
except FileNotFoundError:
    env = {}


async def get_token(query_token: str = Security(api_key_query)):
    api_key = env.get('API_KEY')
    if not api_key:
        return api_key_query
    if query_token == api_key:
        return api_key_query
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN, detail='Token is invalid.'
    )
