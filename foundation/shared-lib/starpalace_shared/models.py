"""Pydantic基础模型 — 严格模式 + 常用类型别名"""

from typing import Optional

from pydantic import BaseModel, ConfigDict

OptionalStr = Optional[str]


class StrictBaseModel(BaseModel):
    """严格模式的BaseModel，不允许隐式类型转换。

    用法:
        class User(StrictBaseModel):
            name: str
            age: int

        User(name="张三", age=18)     # OK
        User(name=None, age="18")     # ValidationError
    """
    model_config = ConfigDict(strict=True)
