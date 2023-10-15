import requests
import json
from queue import Queue
import threading
import time
from vits.TTSgenerate import TTSgenerate
import pyaudio
import wave

class AIanswer():
    def __init__(self):
        self.PostJson={"messages": [],"model": "gpt-3.5-turbo","stream": True}
        self.URL="http://127.0.0.1:8000/v1/chat/completions"
        self.ApiKey="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"
        self.Header={"Content-Type": "application/json","Authorization": "Bearer "+self.ApiKey}

        self.StopSign=False
        self.RoleID=0
        self.AIText=""
        self.AIText_Queue=Queue()
        self.AIVoice_Queue=Queue()
        self.RoleList_clear()

        
        self.pyaudio = pyaudio.PyAudio()
        self.stream = self.pyaudio.open(format=pyaudio.paFloat32,
                        channels=1,
                        rate=48000,
                        output=True,
                        frames_per_buffer=1024)
        
        self.TipSound=wave.open(r"tip.wav", 'rb')
        self.TipStream = self.pyaudio.open(format=self.pyaudio.get_format_from_width(self.TipSound.getsampwidth()), channels=self.TipSound.getnchannels(),
                rate=self.TipSound.getframerate(), output=True)

    def start(self):
        self.StopSign=False
        self.AIText_Queue=Queue()
        self.AIVoice_Queue=Queue()
        self.TextReply_Task=threading.Thread(target=self.TextReply)
        self.TextReply_Task.start()
        self.VitsTTS_Task=threading.Thread(target=self.VitsTTS)
        self.VitsTTS_Task.start()
        self.TSpeech_Task=threading.Thread(target=self.TSpeech)
        self.TSpeech_Task.start()

    def broadcast(self,text):
        self.StopSign=False
        self.AIText_Queue=Queue()
        self.AIVoice_Queue=Queue()
        self.AIText_Queue.put(text)
        self.TextReply_Task=None
        self.VitsTTS_Task=threading.Thread(target=self.VitsTTS)
        self.VitsTTS_Task.start()
        self.TSpeech_Task=threading.Thread(target=self.TSpeech)
        self.TSpeech_Task.start()
        while self.GetState():
            time.sleep(0.05)

    def GetState(self):
        return self.TSpeech_Task.is_alive()
    
    def SelectRole(self,name):
        if name in self.RoleName:
            self.RoleID=self.RoleName.index(name)
        else:
            print("角色不存在")


    def RoleList_append(self,role,name,VoiceJson,VoiceModel):
        self.ChatListF.append(list(role))
        self.ChatList.append(list(role))
        self.RoleName.append(name)
        self.TTSVoice.append(TTSgenerate(VoiceJson,VoiceModel,name,1))
    def RoleList_clear(self):
        self.ChatListF=[]
        self.ChatList=[]
        self.RoleName=[]
        self.TTSVoice=[]

    def GetRole_name(self):
        return self.RoleName[self.RoleID]
    def ChatList_append(self,role,Text):
        self.ChatList[self.RoleID].append({"role": role,"content": Text})
    def ChatList_clear(self):
        self.ChatList[self.RoleID]=list(self.ChatListF[self.RoleID])

    def Tip(self):
        self.TipSound.rewind()
        data = self.TipSound.readframes(1024)
        while data != b'':
                self.TipStream.write(data)
                data = self.TipSound.readframes(1024)

    def TextReply(self):
        self.AIText=''
        Text_slit=''
        print(self.GetRole_name()+":")
        self.PostJson["messages"]=self.ChatList[self.RoleID]
        r = requests.post(self.URL, json=self.PostJson,stream=True,headers=self.Header)
        r.encoding = 'utf-8'
        for line in r.iter_lines(decode_unicode=True):
            if self.StopSign:
                break
            else:
                try:
                    line = line[6:]
                    line = json.loads(line)
                    t=line['choices'][0]['delta']['content']
                    Text_slit+=t
                    self.AIText+=t
                    if t in "，。！？,.?!:：。 \n" or len(Text_slit)>20:
                        print(Text_slit)
                        self.AIText_Queue.put(Text_slit)
                        Text_slit=''  
                except:
                    pass
        if Text_slit!='':
            print(Text_slit)
            self.AIText_Queue.put(Text_slit)
        self.ChatList_append("assistant",self.AIText)

    def VitsTTS(self):
        while True:
            time.sleep(0.05)
            if self.TextReply_Task==None:
                Text=self.AIText_Queue.get()
                Voice=self.TTSVoice[self.RoleID].read(Text)
                self.AIVoice_Queue.put(Voice.tobytes())
                break
            else:
                if ((not self.AIText_Queue.empty()) or (self.TextReply_Task.is_alive())) and (not self.StopSign):
                    if not self.AIText_Queue.empty():
                        Text=self.AIText_Queue.get()
                        Voice=self.TTSVoice[self.RoleID].read(Text)
                        self.AIVoice_Queue.put(Voice.tobytes())
                else:
                    break

    def TSpeech(self):
        while True:
            time.sleep(0.05)
            if ((not self.AIVoice_Queue.empty()) or (self.VitsTTS_Task.is_alive())) and (not self.StopSign):
                if not self.AIVoice_Queue.empty():
                    Voice=self.AIVoice_Queue.get()
                    self.stream.write(Voice)
            else:
                break

if __name__ == '__main__':
    AI=AIanswer()
    AI.Tip()
