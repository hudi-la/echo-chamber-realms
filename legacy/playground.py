import os
# import streamlit as st
# import time
#
# st.title("Echo Bot")
#
# # Initialize chat history
# if "messages" not in st.session_state:
#     st.session_state.messages = []
#
# # Display chat messages from history on app rerun
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])
#
# # React to user input
#
# if prompt := st.chat_input("What is up?"):
#     # Display user message in chat message container
#     st.chat_message("user").markdown(prompt)
#     # Add user message to chat history
#     st.session_state.messages.append({"role": "user", "content": prompt})
#
#
# while True:
#     for i in range(5):
#         response = f"Echo: {prompt}" + str(i)
#         # Display assistant response in chat message container
#
#         with st.chat_message("assistant"):
#             st.markdown(response)
#         # Add assistant response to chat history
#             print(response)
#
#         st.session_state.messages.append({"role": "assistant", "content": response})
#
#         time.sleep(5)

#
# import time
# import tools
# import serial
#
# serialPort = tools.serialPort  # 串口
# baudRate = 9600  # 波特率
# ser = serial.Serial(serialPort, baudRate, timeout=0.5)
#
#
# def to_arduino(agent_name):
#     dic_start = {'Charlie': '1',
#                  'Kaka': '2',
#                  'Lucy': '3'}
#
#     sig = dic_start[agent_name]
#     demo = sig.encode()
#     print(demo)
#     ser.write(demo)  # ser.write在于向串口中写入数据
#
#
# def stop_arduino(agent_name):
#     dic_stop = {'Charlie': '4',
#                 'Kaka': '5',
#                 'Lucy': '6'}
#     sig = dic_stop[agent_name]
#     demo = sig.encode()
#     print(demo)
#     ser.write(demo)  # ser.write在于向串口中写入数据
#
#
# while True:
#     # to_arduino('Kaka')
#     # time.sleep(300)
#     stop_arduino('Kaka')



import tools
import openai
from pathlib import Path

# GPT keys
key = os.environ.get("OPENAI_API_KEY", "")
client = openai.OpenAI(api_key=key)


i = 1
with open(Path(__file__).parent / "ConversationSample.txt") as file:
    for item in file:
        print(item)
        parts = item.split(':', 1)
        agent = parts[0].strip()
        speech = parts[1].strip()

        response = client.audio.speech.create(
            model="tts-1",
            voice=tools.voices_dic[agent],
            input=speech
        )

        path_o = Path(__file__).parent / ("voices/speech_" + str(i) + ".wav")
        path_h = Path(__file__).parent / ("voices/speech_h_" + str(i) + ".wav")


        with open(path_o, "wb") as f:
            f.write(response.content)

        duration = tools.higher_pitch(path_o, path_h, tools.pitch_dic[agent])

        tools.play_sound(agent, path_h, duration)

        i += 1







