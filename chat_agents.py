import tools


# 定义起始消息
language = '讲中文'
initial_message = "让新朋友给你讲讲如何社会化呢？" + language
remember_space = 20


class ChatAgent:
    def __init__(self, name):
        self.name = name
        self.personality = tools.get_chara_dic()[name]
        self.voice = tools.voices_dic[name]
        self.pitch = tools.pitch_dic[name]
        self.avatar = tools.avatar_dic[name]

        self.messages = [
            {"role": "system", "content": self.personality},
            {"role": "user", "content": initial_message}
        ]

        self.client = tools.client

    # @property
    def reply(self):
        # 生成内容
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=self.messages
        )
        ans = response.choices[0].message.content
        return ans

    def output(self, ans, speak=True):
        # 输出的方法包括【终端打印log】和【声音输出】和【arduino信号发送】
        tools.print_reply(self.name, ans)
        if speak:
            tools.voice_and_move(self.name, self.voice, self.pitch, ans)

    def rem(self, talking_ag, ans):
        if self.name == talking_ag.name:
            self.messages.append({"role": "assistant", "content": ans})
        else:
            self.messages.append({"role": "user",
                                  "content": f"群聊中的{talking_ag.name}说：{ans}，你认为应该怎么回复？不要和稀泥，不要道歉，不要重复，请结合你的人设拿出犀利的观点" + language})
        if len(self.messages) > remember_space:
            del self.messages[1]

    def rem_human(self, ans):
        self.messages.append({"role": "user",
                              "content": f"群聊中的{'新朋友'}说：{ans}，你认为应该怎么回复？" + language})
        if len(self.messages) > remember_space:
            del self.messages[1]



