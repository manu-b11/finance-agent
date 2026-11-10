from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

ChatText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: ChatText
