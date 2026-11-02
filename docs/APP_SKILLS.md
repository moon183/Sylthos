# 三套应用 Skill：演讲计划、模拟答辩、材料检查

版本1.0.0，2026-10-27。三套Skill均由本项目程序加载和执行，配有指令文件、结构化清单、Python校验及回归测试，不是单独交给模型自行执行的文档。

## 在软件里使用

新版目录为`dist/three_skills_checked/GesturePPT/`，双击`GesturePPT.exe`。独立分发包不含个人API密钥和历史，首次需自行配置API、导入材料；原目录与数据保留。

### 场景化演讲计划

“演讲材料”导入PPTX并保存材料版本，选择受众、目标时间、重点和演讲场景：

- **大创答辩**：问题、个人实现、实验依据、局限；区分实现与目标，不把API调用说成自研模型。
- **课程汇报**：概念、步骤、例子、知识衔接与总结。
- **项目路演**：用户问题、应用场景、方案、验证依据、下一步；不编造商业数字。

点击“生成演讲计划”，检查逐页建议与原文引用，再“采用并保存计划”。每个非隐藏页必须有本页原文锚点，错页、错字段、伪造引用、缺页、重复页均拒绝。空白页请先补充文字。时间预算仍由代码按权重分配，总和严格等于目标，隐藏页不分配。

计划保存Skill版本、指令哈希及场景；加载历史会恢复原场景。人工编辑保留生成来源和当时的材料锚点，它们不是对修改后全部讲稿事实的验证。改变场景会清空未采用AI结果，但不会自动改写已保存讲稿。

### 证据驱动的模拟答辩

“演讲问答”选择材料或计划，把模式改为“模拟答辩”，选择综合、方法、实验或局限训练。首次输入“开始提问”，后续输入自己的实际回答。

综合训练的主题顺序为方法→证据→局限。第一次只提问，不评价“开始提问”；后续评价必须引用本次回答原句及材料依据。

| 本次评价 | 下一步 |
|---|---|
| 回答依据较充分（adequate） | 推进到下一主题 |
| 需要补充／依据不足／暂无法判断 | 在同一主题追问 |
| 同主题已连续追问两次 | 换到下一主题，保留薄弱问题 |
| 用户点击总结 | 归纳已经进行的回答，不增加新问题 |

单主题训练持续围绕所选主题提出不同问题。每轮只有一个明确问题，重复问题、错误主题跳转和不合法评价会拒绝；失败或取消不推进状态。没有回答实际专业问题前不能总结。

模型负责对回答提出主观教练评价，代码控制主题与追问深度，不把评价当客观成绩。原有最多5次模型请求、8次工具调用、30轮会话限制保持。工具只读取固定选择范围，可提出最多三项待采用练习；用户点击采用后才入库。问答历史与导出含Skill来源及状态。

### 答辩材料证据检查

在“演讲材料”保存当前版本后，点击下方“检查已保存材料”。检查四个方向：

1. **结论依据**：效果陈述是否需要补充实验设计或证据。
2. **数字来源**：样本量、百分比、提升倍数是否说明出处与口径。
3. **口径一致性**：两处陈述是否可能矛盾，是否只是测试条件不同。
4. **表达清晰度**：术语、范围、已完成与计划是否明确。

本地会提示缺少文字、导入盲区和文字较多的页面。模型输出每项的待核实问题、具体修改动作和原文引用；一致性检查必须至少有两处独立引用，不能把同一处重叠文字当两个证据。报告可导出，不会自动修改PPT或讲稿。

图片、图表、外链及外部文献未做视觉理解或网上核验。未在当前文字中找到来源，只能建议核对，不能据此断言没做实验、数据造假或结论错误。无发现不等于材料没有问题。

## Skill文件与运行机制

| Skill | 人工可读指令 | 清单 |
|---|---|---|
| 演讲计划 | `src/assistant_skills/planning/SKILL.md` | 同目录`skill.json` |
| 模拟答辩 | `src/assistant_skills/defense/SKILL.md` | 同目录`skill.json` |
| 材料检查 | `src/assistant_skills/material_review/SKILL.md` | 同目录`skill.json` |

每个清单含id、版本、所需输入、工作步骤、输出核验点和场景。`assistant_skill_runtime.py`限制可加载的三个id，读取文件并计算联合SHA256，固定服务编排流程。修改指令会在下一次运行生效并改变哈希；建议同时升级清单version并保留Git历史。已开始的答辩会话固定使用启动时的Skill快照。

打包后的资源位于`_internal/src/assistant_skills/`。没有动态Python导入、任意命令或额外网络工具；编辑Skill不能解除代码里的页码、引用、预算、状态及次数校验。文件缺失或格式无效时明确报错。

主要代码：

- `assistant_service.py`：场景化分批计划、引用验证和本地预算。
- `defense_skill.py`与`assistant_dialogue.py`：答辩状态转移、回答引用、工具与历史。
- `material_review.py`：本地提示、检查请求、范围和引用校验、报告。
- `presentation_store.py`：保存Skill来源，保存与重读计划时核对原文引用。

## 开发者CLI

以下命令在源码项目目录执行。查看Skill无需联网；其余命令必须显式提供`--online`并复用用户配置的接口。输出使用新路径，避免覆盖已有结果。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m src.skills_cli list

# 输入为logs/presentations/materials/里的已保存材料JSON。
.\.venv\Scripts\python.exe -X utf8 -m src.skills_cli plan 材料.json --scenario innovation --audience 答辩老师 --minutes 8 --focus 实现与验证 --online --out evaluations/skill-plan.json
.\.venv\Scripts\python.exe -X utf8 -m src.skills_cli review 材料.json --online --out evaluations/material-review.json
.\.venv\Scripts\python.exe -X utf8 -m src.skills_cli defense 材料.json --profile adaptive --online --out evaluations/defense-session
```

答辩命令中输入`/quit`退出，`/summary`总结；每个成功回合自动保存本机历史，失败不会推进会话。CLI生成的计划JSON是候选结果，GUI里的“采用并保存”流程仍是软件正式保存入口。

## 验证与真实效果

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_assistant_skills.py -q
.\.venv\Scripts\python.exe -X utf8 tools/verify_three_skills.py --out build/three-skills-demo-new
```

合成演示包括三套Skill执行、保存与深浅主题截图；HTTP测试使用本机服务器和虚构密钥。它们证明流程和校验能运行，不证明真实模型效果或用户成绩提升。本轮未调用真实供应商，也未采集真人效果数据。

需要评估收益时，按[已有采集与对照评测方法](STRATEGY_FRAMEWORK.md)采集真实记录。新的计划、答辩、材料检查任务还需各自建立人工参考与盲评量表；当前彩排四策略的检查项指标不能直接冒充这三套Skill的效果评分。自动校验原句位置也不能证明引用在语义上支持AI判断。
