import streamlit as st
import chat_agents
import tools
import random


# 创建三个聊天代理
agents = []
for name in ['Lucy', 'Charlie', 'Kaka']:
    agents.append(chat_agents.ChatAgent(name))

# 开始聊天
# print(f"起始消息: {chat_agents.initial_message}")
st.title("Three Bots")


# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


# Display chat messages from history on app rerun
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar=tools.avatar_dic[message["role"]]):
        st.markdown(message["role"] + ": " + message["content"])


# React to user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    with st.chat_message("user", avatar=tools.avatar_dic["user"]):
        st.markdown("Me: " + prompt)
        for j in agents:
            j.rem_human(prompt)
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    tools.stop_sound()

while True:
    # talking_agent = random.choice(agents)
    for talking_agent in agents:
        response = talking_agent.reply()

        # Display assistant response in chat message container
        with st.chat_message(talking_agent.name, avatar=talking_agent.avatar):
            st.markdown(talking_agent.name + ": " + response)

            # Add assistant response to chat history
            st.session_state.messages.append({"role": talking_agent.name, "content": response})
            # 让每个参与者记住对话记录
            for j in agents:
                j.rem(talking_agent, response)

            talking_agent.output(response, speak=False)


