class BusinessError(Exception):
    """独立于 HTTP 的业务失败。"""

    def __init__(self, detail: str, status_code: int = 400, *, headers=None):
        self.detail = detail
        self.status_code = status_code
        self.headers = headers
        super().__init__(detail)
