import chat_agents
import tools


# 创建三个聊天代理
agents = []
for index, (name, pers) in enumerate(tools.get_chara_dic().items()):
    agents.append(chat_agents.ChatAgent(name))

# 开始聊天
print(f"起始消息: {chat_agents.initial_message}")

while True:
    # a = random.randint(-1, 10)
    # if a < 0:
    #     # 让每个参与者记住对话记录
    #     answer = input('tell me something')
    #     for j in agents:
    #         j.rem_human(answer)
    # else:
    #     talking_id = random.randint(0, 2)
    #     answer = agents[talking_id].reply()
    #     # 输出回复
    #     agents[talking_id].output(answer)
    #     # 让每个参与者记住对话记录
    #     for j in agents:
    #         j.rem(agents[talking_id], answer)

    for talking_agent in agents:
        # 生成回复
        answer = talking_agent.reply()
        # 输出回复
        talking_agent.output(answer)
        # 让每个参与者记住对话记录
        for j in agents:
            j.rem(talking_agent, answer)


# while True:
#     # 生成回复
#     talking_id = random.randint(0, 2)
#     answer = agents[talking_id].reply()
#     # 输出回复
#     agents[talking_id].output(answer)
#     # 让每个参与者记住对话记录
#     for j in agents:
#         j.rem(agents[talking_id], answer)
