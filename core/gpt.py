import openai
import time
import tiktoken
from openai import BadRequestError, PermissionDeniedError, AuthenticationError
from core.polar_exception import PolarReadNonRetriableException, PolarReadRetriableException
from typing import List, Optional
from openai import OpenAI

print("loading tiktoken...")
tiktoken_encoder = tiktoken.get_encoding("gpt2")
print("done")

"""
DONT use openai utils that uses tenacity retryer since it doesnt throw base exception
"""


def completion(prompt, client, engine="text-davinci-003", user_id="", override_prompt_for_chat_system=""):
    print("completion... by " + user_id)
    global tiktoken_encoder
    length = len(tiktoken_encoder.encode(prompt))
    succeeded = False
    delay = 8
    for i in range(10):
        try:
            if engine == "text-davinci-003":
                response = client.completions.create(
                    model=engine,
                    prompt=prompt,
                    temperature=0,
                    # use maximum value
                    max_tokens=4096 - length,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                    user=user_id,
                    )
                succeeded = True
            else:
                system_content = "You are a helpful assistant. Please only provide an answer to the question without any additional explanations or general steps."
                if override_prompt_for_chat_system != "":
                    system_content = override_prompt_for_chat_system
                response = client.chat.completions.create(
                    model=engine,
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0,
                    user=user_id,
                    )
                succeeded = True
            break
        except (BadRequestError, AuthenticationError, PermissionDeniedError) as e:
            # non retriable error
            print(e)
            raise PolarReadNonRetriableException("GPT internal error")
        except:
            # retry if request failed
            import traceback
            traceback.print_exc()
            pass
        delay = 8 + (2 ** i)
        if delay > 32:
            delay = 32
        elif delay < 8:
            delay = 8
        print("retrying... within " + str(delay) + "(s)")
        time.sleep(delay)
    if not succeeded:
        raise PolarReadRetriableException("GPT internal error but retrieable")
    if engine == "text-davinci-003":
        return response.choices[0].text, response.usage.total_tokens
    else:
        return response.choices[0].message.content, response.usage.total_tokens


def get_embeddings(
    list_of_text: List[str], client: OpenAI, engine="text-embedding-ada-002", user_id=""
) -> List[List[float]]:
    assert len(
        list_of_text) <= 2048, "The batch size should not be larger than 2048."

    # replace newlines, which can negatively affect performance.
    list_of_text = [text.replace("\n", " ") for text in list_of_text]

    data = client.embeddings.create(
        input=list_of_text, model=engine, user=user_id).data
    # maintain the same order as input.
    data = sorted(data, key=lambda x: x.index)
    return [d.embedding for d in data]


def embed(list_of_text, client, engine="text-embedding-ada-002", user_id=""):
    print("embedding... (" + str(len(list_of_text)) + ") by " + user_id)
    succeeded = False
    for i in range(10):
        try:
            result = get_embeddings(
                list_of_text, client, engine=engine, user_id=user_id)
            succeeded = True
            break
        except (BadRequestError, AuthenticationError, PermissionDeniedError, TypeError) as e:
            # non retriable error
            print(e)
            raise PolarReadNonRetriableException("GPT embed internal error")
        except:
            import traceback
            traceback.print_exc()
            # retry if request failed
            pass
        print("retrying...")
        time.sleep(2)
    if not succeeded:
        raise PolarReadRetriableException(
            "GPT embed internal error but retrieable")
    return result


def embed_grouped_by_1024(list_of_text, client, engine="text-embedding-ada-002", user_id=""):
    print("grouped embedding... (" + str(len(list_of_text)) + ") by " + user_id)
    # groups by 1024
    result = []
    for i in range(0, len(list_of_text), 1024):
        result += embed(list_of_text[i:i+1024], client, engine, user_id)
    return result