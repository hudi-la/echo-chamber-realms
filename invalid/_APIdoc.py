import openai

api_key = ''
client = openai.OpenAI(api_key=api_key)


if __name__ == '__main__':
    messages = [
        {"role": "system", "content": "You're a vicious stepmother."},
        {"role": "user", "content": "你好，妈妈，我可以出去玩吗"}
    ]

    completion = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages, max_tokens=68)

    print(completion.choices[0].message)


##############################################################################################


from pathlib import Path
from openai import OpenAI

key = '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'
client = OpenAI(api_key=key)

speech_file_path = Path(__file__).parent / "speech.wav"
response = client.audio.speech.create(
  model="tts-1",
  voice="alloy",
  input="Today is a wonderful day to build something people love!"
)

# response.stream_to_file(speech_file_path)
with open(speech_file_path, "wb") as f:
  f.write(response.content)





