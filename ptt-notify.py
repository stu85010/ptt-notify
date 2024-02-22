import configparser
import datetime
import re
import sys
import time

import requests
import PyPtt

# 讀取 config.ini
config = configparser.ConfigParser()
config.read('config.ini', encoding='UTF-8')

# 設定參數
Username = str(config['DEFAULT']['Username'])
Password = str(config['DEFAULT']['Password'])
LineAPI = str(config['DEFAULT']['LineAPI'])
RefreshInterval = int(config['DEFAULT']['RefreshInterval'])
LineContent = str(config['DEFAULT']['LineContent'])
BoardFilterDict = dict(config._sections['BOARD'])

def login():
    max_retry = 5

    ptt_bot = None
    for retry_time in range(max_retry):
        try:
            ptt_bot = PyPtt.API()

            ptt_bot.login(Username, Password,
                kick_other_session=False if retry_time == 0 else True)
            break
        except PyPtt.exceptions.LoginError:
            ptt_bot = None
            print('登入失敗')
            time.sleep(3)
        except PyPtt.exceptions.LoginTooOften:
            ptt_bot = None
            print('請稍後再試')
            time.sleep(60)
        except PyPtt.exceptions.WrongIDorPassword:
            print('帳號密碼錯誤')
            raise
        except Exception as e:
            print('其他錯誤:', e)
            break

    return ptt_bot

# 宣告 PTTBot & 登入
PTTBot = login()

#  時間戳
def timestamp():
    ts = '[' + datetime.datetime.now().strftime("%m-%d %H:%M:%S") + ']'
    return ts


# 利用 Line Notify 功能達成推送訊息
def sendMessage(message):
    url = 'https://notify-api.line.me/api/notify'
    headers = {
        'Authorization': 'Bearer ' + LineAPI,
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    payload = {
        'message': message
    }
    r = requests.post(url, data=payload, headers=headers)
    if r.status_code == 200:
        print(timestamp() + '[資訊]' + ' Line 通知已傳送')
    else:
        print(timestamp() + '[警告]' + ' Line 通知傳送失敗 ' + str(r.content))


# 傳入看板名稱、關鍵字，回傳文章編號及內容
def getPTTNewestPost(boardname, filter):
    NewestIndex = PTTBot.get_newest_index(index_type=PyPtt.NewIndex.BOARD, board=boardname)
    Post = PTTBot.get_post(board=boardname, index=NewestIndex)
    # 導入正規表達式判斷關鍵字
    regex = re.compile(filter, re.IGNORECASE)
    match = regex.search(str(Post["title"]))
    # 如果正規表達式有篩選到關鍵字（不為空），便向下執行
    if match is not None:
        print(timestamp() + '[資訊] ' + '符合篩選條件 - ' + boardname + ' ' + Post["title"])
        if LineContent == 'True':
            PostMessage = (
                boardname + '\n' + str(Post["title"]) + '\n' + str(Post["url"]) + '\n' + str(Post["content"])
                )
        else:
            PostMessage = (
                boardname + '\n' + str(Post["title"]) + '\n' + str(Post["url"])
                )
        return NewestIndex, PostMessage
    # 如果沒篩選到關鍵字，則回傳文章編號 = 0 以及空訊息
    else:
        NewestIndex = 0
        PostMessage = ''
        return NewestIndex, PostMessage


# 建立當前看板及文章編號對應表
CurrentIndexDict = {}
for board, search in BoardFilterDict.items():
    CurrentIndexDict[board] = 0

NewestIndexDict = {}
# 每秒取得最新文章編號，若有更新才推送消息
try:
    while True:
        # 遍歷 BoardFilterDict，分別取得看板名稱 & 搜尋內容（support regex）
        for board, search in BoardFilterDict.items():
            NewestIndex, PostMessage = getPTTNewestPost(board, search)
            # 將各看板取得的最新文章編號放入 board: key value
            NewestIndexDict[board] = NewestIndex
            print(timestamp() + '[資訊] ' + board + ' 最新文章編號 ' + str(NewestIndex))
            # 比對當前 board: key value 以及最新的 board: key value 是否相同，若不同且不為 0 則推送消息
            if (CurrentIndexDict[board] != NewestIndexDict[board]) and (NewestIndexDict[board] != 0):
                sendMessage(PostMessage)
                CurrentIndexDict[board] = NewestIndex
        time.sleep(RefreshInterval)
except KeyboardInterrupt:
    print(timestamp() + '[資訊] 偵測到中斷指令')
    PTTBot.logout()
