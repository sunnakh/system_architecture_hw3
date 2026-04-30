import os
from concurrent import futures

import grpc
from PIL import Image, ImageDraw, ImageFont
import image_pb2
import image_pb2_grpc

IMAGES_DIR = "/images"


class ImageServicer(image_pb2_grpc.ImageServiceServicer):
    def ProcessImage(self, request, context):
        op = request.operation

        img = Image.open(request.input_path)
        img = img.convert("RGB")  # drop alpha for JPEG

        if op == image_pb2.COMPRESS:
            # lossy recompression; quality 70 is a visually near-identical sweet spot
            img.save(
                request.output_path,
                "JPEG",
                quality=70,
                optimize=True
            )

        elif op == image_pb2.THUMBNAIL:
            # in-place, preserves aspect ratio
            img.thumbnail((256, 256))
            img.save(
                request.output_path,
                "JPEG",
                quality=80
            )

        elif op == image_pb2.WATERMARK:
            draw = ImageDraw.Draw(img)
            text = "Image Pastebin"

            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    24
                )
            except IOError:
                font = ImageFont.load_default()

            w, h = img.size
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            draw.text(
                (w - tw - 15, h - th - 15),
                text,
                fill="white",
                font=font,
                stroke_width=2,
                stroke_fill="black"
            )

            img.save(
                request.output_path,
                "JPEG",
                quality=85
            )

        else:
            context.abort(
                grpc.StatusCode.INVALID_ARGUMENT,
                "Unknown operation"
            )

        out = Image.open(request.output_path)

        return image_pb2.ProcessResponse(
            output_path=request.output_path,
            width=out.width,
            height=out.height,
            size_bytes=os.path.getsize(request.output_path),
        )


def serve():
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=4)
    )

    image_pb2_grpc.add_ImageServiceServicer_to_server(
        ImageServicer(),
        server
    )

    server.add_insecure_port("[::]:50051")
    server.start()

    print("image_service listening on :50051", flush=True)

    server.wait_for_termination()


if __name__ == "__main__":
    serve()