"""受控 Agent 内核：contracts、providers、runtime、store、tools、prompts。

写操作必须走审批状态机；工具调用 services，不得绕过服务规则直接写库。
"""
