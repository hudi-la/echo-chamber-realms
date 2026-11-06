import os
import textwrap
import openai
import serial

from pathlib import Path
from PIL import Image
import numpy as np

import time

import librosa
import pygame
import soundfile as sf

pygame.mixer.init(channels=2)

# GPT keys
key = os.environ.get("OPENAI_API_KEY", "")
client = openai.OpenAI(api_key=key)

org_speech_file_path = Path(__file__).parent / "voices/speech.wav"
higher_speech_file_path = Path(__file__).parent / "voices/speech_2.wav"

# 角色设置
chara_prompt_dire = Path(__file__).parent / "charactor_setting/"

avatar_paths = {'Charlie': Path(__file__).parent / 'avatar/charlie.png',
                'Kaka': Path(__file__).parent / 'avatar/kaka.png',
                'Lucy': Path(__file__).parent / 'avatar/lucy.png',
                'user': Path(__file__).parent / 'avatar/user.jpeg'}

pitch_dic = {'Charlie': 6,
             'Kaka': 6,
             'Lucy': 7}

voices_dic = {'Charlie': 'nova',
              'Kaka': 'onyx',
              'Lucy': 'shimmer'}

channel_dic = {'Charlie': (1, 0),
               'Kaka': (0, 1),
               'Lucy': (0.5, 0.5)}


serialPort = "/dev/cu.usbserial-1130"  # 串口
baudRate = 9600  # 波特率

try:
    ser = serial.Serial(serialPort, baudRate, timeout=0.5)
except:
    print('No arduino')


def get_chara_dic():
    chara_dic = {}
    for charactor in ['Charlie', 'Kaka', 'Lucy']:
        with open(chara_prompt_dire/(charactor + '.txt'), 'r') as file:
            chara_dic[charactor] = file.read()
    return chara_dic


def get_image_np(img_path):
    image = Image.open(img_path)
    image.load()
    return np.asarray(image, dtype="int32")


avatar_dic = {}
for name, path in avatar_paths.items():
    avatar_array = get_image_np(path)
    avatar_dic[name] = avatar_array


def print_reply(agent_name, message):
    print(textwrap.fill(f"@{agent_name}:{message}", width=80))


# 下面是声音相关的工具：
def higher_pitch(path_org, path_out, scale):
    """
    改变音频文件的音调。
    :param path_org: 输入音频文件的路径。
    :param path_out: 输出音频文件的路径。
    :param scale: 音调改变的半音数。正数为提高音调，负数为降低音调。
    """
    # 加载音频文件
    y, sr = librosa.load(path_org, sr=None)
    # 改变音调 \ speed
    y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=scale)
    # y_shifted = librosa.effects.time_stretch(y_shifted, rate=0.9)
    # 保存改变音调后的音频文件
    sf.write(path_out, y_shifted, sr)

    duration = librosa.get_duration(y=y_shifted, sr=sr)
    return duration


def play_sound(name, sound_path, duration):
    """
    播放wav文件。
    :param sound_path: 输入音频文件的路径。
    """
    # 加载音频文件
    sound = pygame.mixer.Sound(sound_path)
    # 开始播放音频
    (a, b) = channel_dic[name]

    channel = sound.play()
    channel.set_volume(a, b)
    # 等待音频播放完毕
    # while pygame.mixer.get_busy():
    #     pygame.time.Clock().tick(0)

    # 等待数秒
    time.sleep(int(duration * 0.7))


def stop_sound():
    pygame.mixer.stop()


def voice_and_move(ag_name, voice, pitch, message, path_o=org_speech_file_path, path_h=org_speech_file_path):
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=message
    )
    with open(path_o, "wb") as f:
        f.write(response.content)

    duration = higher_pitch(path_o, path_h, pitch)

    try:
        arduino_start(ag_name)
    except:
        print("No arduino")
    play_sound(ag_name, path_h, duration)
    try:
        arduino_stop(ag_name)
    except:
        print("No arduino")


# 下面关于arduino
def arduino_start(agent_name):
    sig_dic = {'Charlie': '1',
               'Kaka': '2',
               'Lucy': '3'}
    sig = sig_dic[agent_name]
    demo = sig.encode()
    print(demo)
    ser.write(demo)  # ser.write在于向串口中写入数据


def arduino_stop(agent_name):
    sig_dic = {'Charlie': '4',
               'Kaka': '5',
               'Lucy': '6'}
    sig = sig_dic[agent_name]
    demo = sig.encode()
    print(demo)
    ser.write(demo)

