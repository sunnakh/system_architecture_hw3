import os
import grpc

from . import image_pb2, image_pb2_grpc

_channel = None
_stub = None


def _get_stub():
    global _channel, _stub

    if _stub is None:
        _channel = grpc.insecure_channel(
            os.environ["IMAGE_SERVICE_ADDR"]
        )
        _stub = image_pb2_grpc.ImageServiceStub(_channel)

    return _stub


def process(
    input_path: str,
    output_path: str,
    operation: int
):
    req = image_pb2.ProcessRequest(
        input_path=input_path,
        output_path=output_path,
        operation=operation
    )

    return _get_stub().ProcessImage(req, timeout=15)