"""Registro de protobufs conhecidos e conversão para o formato HTTP."""

import base64
import json

from google.protobuf.json_format import MessageToDict, ParseError
from google.protobuf.message import DecodeError
from google.protobuf.struct_pb2 import Struct
from is_msgs import camera_pb2, common_pb2, image_pb2, power_pb2, robot_pb2, ros_pb2
from is_msgs.image_pb2 import Image

MODULES = (camera_pb2, common_pb2, image_pb2, power_pb2, robot_pb2, ros_pb2)
PROTO_TYPES = {
    cls.DESCRIPTOR.full_name: cls
    for module in MODULES
    for cls in module.__dict__.values()
    if isinstance(cls, type) and hasattr(cls, "DESCRIPTOR")
}
PROTO_TYPES[Struct.DESCRIPTOR.full_name] = Struct
SHORT_TYPES = {cls.DESCRIPTOR.name: cls for cls in PROTO_TYPES.values()}


def decode_message(message, schema_hint=None) -> tuple[str, bytes]:
    """Converte uma entrega em imagem ou JSON sem recomprimir imagens."""
    if schema_hint == "Json":
        return "json", message.body
    schema = schema_hint or message.metadata.get("is-schema")
    if schema in SHORT_TYPES:
        schema = SHORT_TYPES[schema].DESCRIPTOR.full_name
    if schema in ("Image", "is.vision.Image"):
        return "image", bytes(message.unpack(Image).data)
    message_class = PROTO_TYPES.get(schema)
    if message_class is not None:
        decoded = message.unpack(message_class)
        value = {
            "topic": message.topic,
            "schema": decoded.DESCRIPTOR.full_name,
            "message": MessageToDict(decoded, preserving_proto_field_name=True),
        }
        return "json", json.dumps(value, separators=(",", ":")).encode()
    try:
        return "image", bytes(message.unpack(Image).data)
    except (DecodeError, ParseError, ValueError, TypeError, NotImplementedError):
        value = {
            "topic": message.topic,
            "schema": schema or "unknown",
            "bytes": len(message.body),
            "body_base64": base64.b64encode(message.body).decode(),
        }
        return "json", json.dumps(value, separators=(",", ":")).encode()
