"""Configuração por ambiente e validação dos tópicos de câmera."""

import os
import re
from dataclasses import dataclass

CAMERA_TOPIC = re.compile(r"^CameraGateway\.(\d+)\.Frame$")


def normalize_camera_topic(value: str) -> str:
    """Aceita um ID ou o tópico completo do CameraGateway."""
    value = value.strip().strip("/")
    if value.isdigit():
        value = f"CameraGateway.{value}.Frame"
    if CAMERA_TOPIC.fullmatch(value) is None:
        raise ValueError("camera topic must match CameraGateway.<id>.Frame")
    return value


def camera_topics() -> list[str]:
    configured = os.getenv("CAMERA_TOPICS") or os.getenv("CAMERA_IDS", "1,2,3,4")
    return [
        normalize_camera_topic(value)
        for value in configured.split(",")
        if value.strip()
    ]


@dataclass(frozen=True)
class Settings:
    broker_uri: str = "amqp://localhost"
    port: int = 3000

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            broker_uri=os.getenv("IS_URI", "amqp://localhost"),
            port=int(os.getenv("IS_PORT", "3000")),
        )
