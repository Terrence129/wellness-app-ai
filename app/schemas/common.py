# Author: Huang Qijun
# Email: 2692341798@qq.com

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ErrorResponse(BaseModel):
    """Stable public error response envelope.

    Author: 2692341798
    """

    model_config = ConfigDict(populate_by_name=True)

    success: Literal[False] = False
    message: str
    error_code: str = Field(alias="errorCode")
    request_id: str = Field(alias="requestId")
