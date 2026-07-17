# 招聘沟通台

本机单账号 BOSS 招聘沟通系统。FastAPI 通过 DrissionPage 连接调试端口 `9333` 的专用 Chrome，并使用本地 RAG 知识库和用户配置的 AI 模型生成待人工审核的短回复草稿。

## 启动

```powershell
.\run.ps1
```

访问：`http://127.0.0.1:8765`

- 用户名：`admin`
- 密码：`123456`

## 配置 AI 模型

登录后点击左侧“AI 模型”，填写服务商名称、OpenAI 兼容 Base URL、API Key 和模型名。可先测试连接，保存后无需重启即可生效。查询接口不会返回 API Key 明文。

源码运行时配置保存在项目 `.env`；桌面版保存在当前 Windows 用户的本机数据目录。配置文件已排除 Git 提交，交付包不会携带开发者的 Key。

已有 Kimi Key 也可继续使用原脚本验证并写入通用配置：

```powershell
D:\python\python.exe scripts\configure_kimi.py "C:\Users\81591\Desktop\kimi-keys.txt"
```

脚本只显示 Key 序号和验证结果，不显示完整 Key。

## AI 草稿流程

1. 打开一位 BOSS 联系人的会话。
2. 对方最后一条消息变化时，系统被动读取当前会话。
3. 本地知识库检索最多 4 条相关资料。
4. 当前配置的 AI 模型生成简短草稿并执行长度、套话、Markdown、占位符和多问题检查。
5. 点击“采用草稿”只会把文字填入输入框。
6. 人工修改并点击“发送”后，才会调用 BOSS 写操作。

AI 草稿不会自动切换联系人或发送；系统不会群发、绕过验证码或重试结果未知的消息。

## 主动招呼计划

左侧“主动招呼”可管理多个计划。每个计划可新建、编辑、启停、删除和执行当前到期任务；多个已启用计划不能时间重叠。所有计划共用 BOSS 账号的每日、每小时计数和发送间隔，并始终串行执行。出现安全验证、明确登录失效、额度用尽或结果未知时，仅暂停当前计划。

## 知识库

左侧“知识库”按钮打开知识库，可新增、编辑、启用、停用和删除条目。初始包含：

- AIHR 项目的 30 条招聘沟通话术
- 8 条隐私、薪资、岗位冲突、拒绝联系和法律争议人工处理规则

数据库位置：`data/knowledge.db`

## 测试

```powershell
D:\python\python.exe -m unittest discover -s tests -v
node --check app\static\app.js
```

无 BOSS 写操作的页面验收：

```powershell
D:\python\python.exe scripts\ui_smoke.py
```
