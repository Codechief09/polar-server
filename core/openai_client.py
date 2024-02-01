import openai
import os
from openai import BadRequestError, PermissionDeniedError, AuthenticationError
from openai import OpenAI
from variables import get_gpt_api_key

def get_openai_client():
    return OpenAI(api_key=get_gpt_api_key())
