# 演讲助手 API 接入验收

用户授权：继续下一步，并预留 API 接口自行填写。按照该授权同步更新 SPEC 的在线例外，保持手势核心离线。

## 本轮实现

- 独立 API 设置对话框及 `assistant_api.local.json`，默认关闭、密钥为空。支持基地址、/v1 和完整 Chat Completions 路径；通过标准库 HTTP 请求，不新增 SDK。
- 后台连接测试、分批逐页计划、精确总预算、生成预览/采用保存/导出，以及已选彩排记录的 AI 解读。
- 每批携带全篇标题提纲，覆盖页面必须完整、正确且不重复。隐藏页不占预算，长输入明确拒绝而非静默截断。
- 彩排建议引用程序计算的事实编号，证据文字从本地统计取出，不采用模型编造的证据；无转写时不认定漏讲或表达质量。
- 取消、切换目标、关闭界面后丢弃迟到响应。后台线程不持有控件，取消不承诺撤回服务端已经发出的请求。

## 验证

- 核心/界面专项命令 `tests/test_assistant_api.py tests/test_assistant_service.py tests/test_assistant_gui.py tests/test_presentation_page.py tests/test_rehearsal.py tests/test_rehearsal_history.py`：**76 passed**，退出码0。
- `tools/verify_assistant_http.py` 已用虚构密钥在127.0.0.1执行真实 HTTP 请求：一次连接测试、两批计划（9页）、一次复盘；计划总计480秒，结果保存与版本绑定完成。证据：本地 `build/assistant_http/aa46b1e1f341435f83de34588909829d/receipt.json`，其中 `supplier_connected=false`。
- 默认1165×720窗口和深浅主题渲染已检查；配置截图使用空密钥，计划截图明确标记为本机模拟结果。
- 全套 `.venv/Scripts/python.exe -X utf8 -m pytest tests/ -q --durations=5 --basetemp=build/assistant-full`：**701 passed, 22 subtests passed**，用时 **365.22 秒**，进程退出码 **0**。日志在本地 `build/assistant-full.log`。模拟接口通过不代表真实供应商实连成功。

## 独立审查及修复

审查发现已保存计划再次另存时预算会逐次漂移，如 `[40,80,360]` 变为 `[41,80,359]`。已添加失败回归并修复，预算总和未改变时保持原值；重新分配后再次保存也保持幂等。审查者独立复跑回归通过。

连接测试原来继承思考模式但只给16个输出token，可能在返回正文前耗尽。已补失败用例并改为仅测试时临时关闭思考，持久配置和生成任务仍遵循用户选择。额外补了 `choices=[null]` 的响应格式回归。

## 交付边界

尚未填写或使用用户的真实 API Key，没有验证真实 DeepSeek 账户、余额或实际生成质量；需用户填写后点击测试并核对真实输出。没有新增语音转写对齐、多工具 Agent 或现场实时 AI 指导；没有重新打包旧 exe。

## 截图

- [API 设置](assistant-settings-20261025.png)
- [计划预览（本机模拟）](assistant-plan-20261025.png)
