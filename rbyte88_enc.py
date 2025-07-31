#!/usr/bin/env python3

from PIL import Image

import struct
import os.path
import sys


STIPPLES = [
    line.split(" ")
    for line in [
        "0000 00000001 000001000 0001 001 0011 0101 011 1101 111110111 11101111 1111",
        "0000 00000000 000000001 0000 010 0011 1010 110 1111 111111110 11111111 1111",
        "0000 00010000 001000000 0100 100 1100 0101 101 0111 110111111 11111110 1111",
        "0000 00000000 000001000 0000 /// 1100 1010 /// 1111 111110111 11111111 1111",
        "//// 00000001 000000001 //// /// //// //// /// //// 111111110 11101111 ////",
        "//// 00000000 001000000 //// /// //// //// /// //// 110111111 11111111 ////",
        "//// 00010000 000001000 //// /// //// //// /// //// 111110111 11111110 ////",
        "//// 00000000 000000001 //// /// //// //// /// //// 111111110 11111111 ////",
        "//// //////// 001000000 //// /// //// //// /// //// 110111111 //////// ////",
    ]
]


def encode_rbyte88(*, image):
    if image.width > 640 or image.height > 400:
        scale = min(640 / image.width, 400 / image.height)
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    assert (image.width <= 640) and (image.height <= 400)
    rbyte_image_width = (image.width + 7) // 8
    rbyte_image_height = (image.height + 1) // 2
    byts = []
    last_frame_byts = []
    for is_vertical in (False, True):
        byts.append(
            struct.pack(
                "<BB",
                rbyte_image_width | (0x80 if is_vertical else 0x00),
                rbyte_image_height,
            )
        )
        last_frame_byts.append(b"")
        for color_channel in (2, 0, 1):
            frame = b""
            y_range, x_range = range(rbyte_image_height), range(rbyte_image_width)
            j_range, k_range = (x_range, y_range) if is_vertical else (y_range, x_range)
            for j in j_range:
                for k in k_range:
                    x, y = (j, k) if is_vertical else (k, j)
                    b = 0x00
                    for i in range(8):
                        if (8 * x + i) < image.width:
                            pixel1 = image.getpixel((8 * x + i, 2 * y))
                            pixel2 = (
                                image.getpixel((8 * x + i, 1 + 2 * y))
                                if (1 + 2 * y) < image.height
                                else pixel1
                            )
                            mpix = pixel1 if sum(pixel1) >= sum(pixel2) else pixel2
                            lum = mpix[color_channel]
                        else:
                            lum = 0
                        lumx = (lum * (len(STIPPLES[0]) - 1) + 128) // 255
                        stipple = STIPPLES[y % len(STIPPLES)][lumx]
                        stipple = STIPPLES[y % len(stipple) % len(STIPPLES)][lumx]
                        pix = (
                            1
                            if int(stipple[::-1], 2)
                            & (1 << ((i + 8 * x) % len(stipple)))
                            else 0
                        )
                        b <<= 1
                        b |= pix
                    frame += bytes([b])
            opt_frame = b""
            previous_data_bytes = b""
            for i, data_byte in enumerate(frame):
                if previous_data_bytes == b"" or previous_data_bytes[0] != data_byte:
                    opt_frame += bytes([data_byte])
                    previous_data_bytes = bytes([data_byte])
                elif previous_data_bytes == bytes([data_byte]):
                    opt_frame += bytes([data_byte, 0x01])
                    previous_data_bytes += bytes([data_byte])
                elif previous_data_bytes == bytes([data_byte] * 2):
                    repeat_count = 1 + opt_frame[-1]
                    opt_frame = opt_frame[:-1] + bytes([repeat_count])
                    if repeat_count == 0xFF:
                        previous_data_bytes = b""
                else:
                    assert False, "This code should not be reachable."
            if len(previous_data_bytes) == 2 and opt_frame[-1] == 0x01:
                opt_frame = opt_frame[:-1]
            last_frame_byts[-1] = opt_frame
            byts[-1] += opt_frame
    # return byts[0] if len(byts[0]) < len(byts[1]) else byts[1]  # smarter, but apparently not what Lafiel soft chose
    return byts[0] if len(last_frame_byts[0]) < len(last_frame_byts[1]) else byts[1]


def main():
    (
        _,
        image_file_name,
    ) = (  # usage: python rbyte88_enc.py INPUT.PNG  ## generates INPUT_rbyte88.bin
        sys.argv
    )
    with Image.open(image_file_name) as im:
        if im.mode.startswith("I;16"):
            # PIL conversion to RGB is broken for I;16* formats!
            im8 = im.convert("I")
            for y in range(im.height):
                for x in range(im.width):
                    im8.putpixel((x, y), im.getpixel((x, y)) >> 8)
            im = im8
        rgb_image = im.convert("RGB")
    output_file_name = (
        f"{os.path.splitext(os.path.basename(image_file_name))[0]}_rbyte88.bin"
    )
    if os.path.lexists(output_file_name):
        os.remove(output_file_name)
        print(
            "removed previous %(output_file_name)s"
            % dict(output_file_name=output_file_name)
        )
    rbyte88_data = encode_rbyte88(image=rgb_image)
    open(output_file_name, "wb").write(rbyte88_data)
    print(f"saved {output_file_name}")


if __name__ == "__main__":
    main()
