# 主动招呼多计划实施计划

## 1. 修复 BOSS 登录加载竞态

**文件：** `tests/test_boss.py`、`app/boss.py`

1. 增加页面先无登录标记、随后出现推荐卡片的测试，并验证首次切换不会抛出 `login_required`。
2. 増加明确登录 URL 的测试。
3. 用短轮询替换一次性正文判断；区分 `logged_in`、`logged_out` 和 `loading`。
4. 运行 `python -m unittest tests.test_boss -v`。

## 2. 将单计划存储迁移为计划列表

**文件：** `tests/test_greetings.py`、`app/greetings.py`

1. 先增加默认迁移、CRUD、相邻时间、重叠冲突和删除测试。
2. 新建 `greeting_plans` 表，并在首次打开数据库时复制旧 `greeting_settings`。
3. 给日志增加 `plan_id`，保留旧日志。
4. 实现计划创建、读取、更新、启停和删除；启用冲突抛出专用异常。
5. 运行 `python -m unittest tests.test_greetings -v`。

## 3. 让调度器选择具体计划

**文件：** `tests/test_greetings.py`、`app/greetings.py`

1. 增加多个非重叠计划、全局频率、按计划暂停和单次执行测试。
2. 保留单后台线程和单执行锁，扫描当前到期计划。
3. 成功或失败日志关联计划，完成后恢复沟通页。
4. 运行 `python -m unittest tests.test_greetings -v`。

## 4. 替换 API

**文件：** `tests/test_api.py`、`app/main.py`

1. 增加计划列表、创建、编辑、启停、删除、执行和 `409` 冲突响应测试。
2. 增加计划请求模型和 REST 接口，保留日志接口。
3. 运行 `python -m unittest tests.test_api -v`。

## 5. 改造主动招呼抽屉

**文件：** `tests/test_static.py`、`app/static/index.html`、`app/static/app.js`、`app/static/app.css`

1. 更新静态测试，要求计划列表、新建/编辑表单和新 API。
2. 用计划列表替换单计划表单，复用原生 `datetime-local`。
3. 增加启停、编辑、执行、删除和冲突错误反馈。
4. 保留打开推荐页、关闭后返回沟通页的现有流程。
5. 运行 `python -m unittest tests.test_static -v`。

## 6. 全量验证与交付

1. 运行 `python -m unittest discover -s tests -v`。
2. 启动本地系统并验证登录、计划 CRUD、冲突提示和首次切换推荐页。
3. 构建桌面程序与安装包。
4. 安装覆盖当前版本，启动后复验本地页面和 BOSS 浏览器连接。
