from dataclasses import dataclass


@dataclass(frozen=True)
class ImagePart:
    mime_type: str
    data: bytes
