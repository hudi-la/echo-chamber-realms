
def response(message):
    if ("I love you" in message) or ("Yes" in message):
        return "I love you too"


starting_message = "do you love me?"
input_message = starting_message

print(starting_message)


while input_message:
    input_message = input()
    answer = response(input_message)
    print(answer)
