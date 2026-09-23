from dataclasses import dataclass


@dataclass(frozen=True)
class Actor:
    """服务端从已认证身份构造；不能从请求 JSON 中读取用户编号。"""

    user_id: int

    def __post_init__(self):
        if type(self.user_id) is not int or self.user_id <= 0:
            raise ValueError("无效的用户身份")
