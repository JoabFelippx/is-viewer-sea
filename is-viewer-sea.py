from is_msgs.camera_pb2 import CameraConfig
from is_wire.core import Channel, Message, Subscription

import os


class PtzStep:
    pan: int = 5
    tilt: int = -5
    zoom: int = 0
    step_degrees: float = 5.0


def main():

    broker_uri = os.getenv("IS_URI", "amqp://localhost")
    channel = Channel(broker_uri, exchange="is")

    topic = "CameraGateway.5.SetConfig"

    # Create a subscription to receive messages
    subscription = Subscription(channel)

    step = PtzStep

    config = CameraConfig()

    factor = step.step_degrees / 5.0
    config.ptzcontrol.step.x = step.pan * factor
    config.ptzcontrol.step.y = step.tilt * factor
    config.ptzcontrol.step.z = 0

    # Create a message to send
    msg_ptz = Message(content=config, reply_to=subscription)

    channel.publish(msg_ptz, topic)


if __name__ == "__main__":
    main()
