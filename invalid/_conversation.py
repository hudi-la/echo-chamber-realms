import openai

api_key = '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'
client = openai.OpenAI(api_key=api_key)
starting_message = "can you help me?"

# input_message = starting_message
print(starting_message)

messages = [
        {"role": "system", "content": "You're an AI assistant."},
        {"role": "user", "content": starting_message}
    ]

while True:

    response = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages, max_tokens=68)

    answer = response.choices[0].message.content
    print(answer)
    messages.append({"role": "assistant", "content": answer})

    input_message = input()
    messages.append({"role": "user", "content": input_message})



