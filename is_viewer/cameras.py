"""Configuração, consulta de capacidades e movimento PTZ das câmeras."""

from google.protobuf.empty_pb2 import Empty
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
from google.protobuf.wrappers_pb2 import FloatValue
from is_msgs.camera_pb2 import CameraConfig
from is_msgs.common_pb2 import SamplingSettings
from is_msgs.image_pb2 import ColorSpace, ColorSpaces, ImageSettings
from is_wire.core import Message
from pydantic import BaseModel

from .messaging.rpc import RpcClient


class PtzStep(BaseModel):
    pan: int = 0
    tilt: int = 0
    zoom: int = 0
    step_degrees: float = 5.0


class PositionUnavailable(RuntimeError):
    """O gateway não incluiu uma leitura absoluta de PTZ em GetConfig."""


class CameraService:
    """Agrupa o contrato CameraGateway; o transporte RPC fica em RpcClient."""

    def __init__(self, rpc: RpcClient):
        self.rpc = rpc

    def configure_camera(self, camera_id, query):
        config = CameraConfig()
        if "fps" in query:
            config.sampling.CopyFrom(
                SamplingSettings(frequency=FloatValue(value=float(query["fps"])))
            )
        if "color" in query:
            try:
                value = ColorSpaces.Value(query["color"].upper())
            except (KeyError, ValueError):
                raise ValueError(f"unsupported color: {query['color']!r}") from None
            config.image.CopyFrom(ImageSettings(color_space=ColorSpace(value=value)))
        if config.ByteSize():
            self.rpc.publish(
                Message(content=config), topic=f"CameraGateway.{camera_id}.SetConfig"
            )

    def camera_capabilities(self, camera_id):
        reply = self.rpc.call(
            f"CameraGateway.{camera_id}.GetCapabilities", Empty(), Struct
        )
        return MessageToDict(reply, preserving_proto_field_name=True)

    def move_camera(self, camera_id, step):
        config = CameraConfig()
        # No contrato legado, 1 representa o movimento padrão. O valor 5 da
        # interface mantém esse padrão; os três eixos usam a mesma escala.
        factor = step.step_degrees / 5.0
        config.ptzcontrol.step.x = step.pan * factor
        config.ptzcontrol.step.y = step.tilt * factor
        config.ptzcontrol.step.z = step.zoom * factor
        self.rpc.call(f"CameraGateway.{camera_id}.SetConfig", config, Empty)

    def home_camera(self, camera_id: int) -> None:
        """Solicita a posição absoluta (0, 0, 0), não um preset do fabricante."""
        config = CameraConfig()
        # Zeros são omitidos no wire format protobuf; a presença do subcampo
        # distingue um comando absoluto zerado de uma configuração sem PTZ.
        config.ptzcontrol.absolute.SetInParent()
        self.rpc.call(f"CameraGateway.{camera_id}.SetConfig", config, Empty)

    def camera_position(self, camera_id: int) -> dict:
        config = self.rpc.call(
            f"CameraGateway.{camera_id}.GetConfig", Empty(), CameraConfig
        )
        if not config.HasField("ptzcontrol") or not config.ptzcontrol.HasField(
            "absolute"
        ):
            raise PositionUnavailable("camera did not report its absolute PTZ position")
        position = config.ptzcontrol.absolute
        return {
            "pan": position.x,
            "tilt": position.y,
            "zoom": position.z,
            "units": "camera_native",
        }
