from wxauto import WeChat

# 初始化微信实例
wx = WeChat()

# 切换到test1
target = "test1"
wx.ChatWith(who=target)

# 查看当前窗口信息 (wxauto: ChatInfo在Chat对象上)
chat = wx.GetSubWindow(target)
if chat:
    print(f"当前窗口信息：{chat.ChatInfo()}")
    print(f"聊天对象：{chat.who}")

# 发送消息 (wxauto: 使用who参数指定目标)
if chat and chat.who == target:
    wx.SendMsg("你好", who=target)

# 获取当前聊天窗口消息
msgs = wx.GetAllMessage()

for msg in msgs:
    print(f"[{msg.attr}/{msg.type}] {msg.sender}: {msg.content[:50]}")
