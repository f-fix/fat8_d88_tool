#!/usr/bin/env python3

"""RBYTE image data decoder and viewer

The RBYTE details here are entirely inferred based on
reverse-engineering of a single game's data and may be wrong in many
respects.

RBYTE is a placeholder name based on the name of the file containing
the decoding routine, and may be a pun on `アルバイト` (Arbeit[er],
i.e. a part-time job [or worker]). The origin of this image format and
decoder are not yet known. It was used in the doujin software `KYOTO討
龍伝` (Kyoto Touryuuden) by Asuka.Load and Halord.Jonson/Lafiel
Soft/Specters for the NEC PC-8801 mkII SR from 1989. This game stores
image data in a compressed form ("RBYTE") on the FAT8-formatted floppy
disk, one image per file. To display an image, it is loaded using the
`RBYTE` BASIC instruction which is implemented by a custom DOS. A
start address is video memory can optionally be supplied from BASIC
too, and if omitted it defaults to the upper left corner of the
graphics screen. The decoder reads the image width (in bytes,
i.e. multiples of 8 pixels; the eighth bit is separate and indicates
the decoding direction) and height (in lines) from the two-byte header
of the image data, then proceeds to decode the image data into video
memory. When the high bit of the image width is set it indicates
decoding in vertical columns 8 pixels wide with pixel data decoding
progressing from top to bottom and then column decoding progressing
from left to right. When the bit is clear, image decoding instead
progresses from left to right in groups of eight pixels, and then row
decoding progresses from top to bottom.

Decoding is in planar order, first filling the blue plane of the
image, then the red plane, and finally the green plane.

The image data consists of bytes with a form of run-length
encoding. Each byte represents eight consecutive pixels in the color
plane being decoded. When a byte value appears twice in a row, the
byte following the second occurrence gives a number of additional
repetitions of the byte value.

"""

from PIL import Image
from PIL.PngImagePlugin import PngInfo

import os
import struct
import sys

RBYTE88_VERBOSE_DEBUGGING = False

RBYTE88_HEADER_SIZE = 2
RBYTE88_MAX_IMAGE_WIDTH = 640 // 8
RBYTE88_MAX_IMAGE_HEIGHT = 200
TRANSPARENT_BLACK_RGBA = (0, 0, 0, 0)


def draw_pixel_byte(
    image,
    color_channel,
    x,
    y,
    data_byte,
    x_offset,
    y_offset,
    rbyte_image_width,
    rbyte_image_height,
):
    """Given a PIL Image (image), a color channel index color_channel,
    an x-offset of x bytes (counting groups of 8 pixels), a y-offset
    of y lines, and pixel data data_byte for the 8-pixel group, draws
    this pixel data into the image. The pixel will be vertically
    scan-doubled to improve viewability on non-PC 8801 mkII SR displays.

    """
    assert color_channel in (
        0,
        1,
        2,
    ), "The color_channel to update must be one of R(0)/G(1)/B(2)"
    message = []
    if x >= RBYTE88_MAX_IMAGE_HEIGHT:
        message += ["x wrapped!!! %r" % dict(x=x)]
    if x < x_offset or x >= x_offset + rbyte_image_width:
        message += ["x out of bounds!!! %r" % dict(x=x)]
    if y < y_offset or y >= y_offset + rbyte_image_height:
        message += ["y out of bounds!!! %r" % dict(y=y)]
    y += x // RBYTE88_MAX_IMAGE_WIDTH
    x %= RBYTE88_MAX_IMAGE_WIDTH
    if RBYTE88_VERBOSE_DEBUGGING:
        print(
            "draw_pixel_byte",
            dict(
                color_channel=color_channel,
                x=x,
                y=y,
                data_byte=bin(0x100 | data_byte)[len(bin(1)) :],
                message=set(message),
            ),
        )
    for i in range(8):
        pixel1 = list(image.getpixel((8 * x + 7 - i, 2 * y)))
        pixel2 = list(image.getpixel((8 * x + 7 - i, 1 + 2 * y)))
        pixel1[color_channel] = pixel2[color_channel] = 255 * ((data_byte >> i) & 1)
        pixel1[3] = pixel2[3] = 255  # completely opaque
        image.putpixel((8 * x + 7 - i, 2 * y), tuple(pixel1))
        image.putpixel((8 * x + 7 - i, 1 + 2 * y), tuple(pixel2))
    assert not len(message), set(message)


FAT8_SECTOR_SIZE = 256


def decode_rbyte88_data(rbyte_data, x_offset=None, y_offset=None):
    """Given binary RBYTE data as input, decodes it and produces a PIL
    Image as output. Starting x_offset and y_offset may be
    provided. If either is omitted or None, the returned image will be
    exactly the dimensions specified in the RBYTE data for that
    axis. Otherwise, the image will be placed in a transparent
    screen-dimensioned image for that axis with the image rendered at
    the specified offset. The x_offset counts in bytes (8-pixel
    groups) from the left edge, the y_offset counts in lines from the
    top edge. The generated PIL image will be vertically scan-doubled
    to improve viewability on non-PC 8801 mkII SR displays.

    """
    if x_offset is not None:
        assert x_offset == int(x_offset), "x_offset must be None or an integer"
        assert x_offset in range(0, RBYTE88_MAX_IMAGE_WIDTH + 1), (
            "x_offset may not exceed screen width (%(RBYTE88_MAX_IMAGE_WIDTH)d bytes, representing %(RBYTE88_MAX_IMAGE_WIDTH_px)d pixels)"
            % dict(
                RBYTE88_MAX_IMAGE_WIDTH=RBYTE88_MAX_IMAGE_WIDTH,
                RBYTE88_MAX_IMAGE_WIDTH_px=8 * RBYTE88_MAX_IMAGE_WIDTH,
            )
        )
    if y_offset is not None:
        assert y_offset == int(y_offset), "y_offset must be None or an integer"
        assert y_offset in range(0, RBYTE88_MAX_IMAGE_HEIGHT + 1), (
            "y_offset may not exceed screen height (%(RBYTE88_MAX_IMAGE_HEIGHT)d lines)"
            % dict(
                RBYTE88_MAX_IMAGE_HEIGHT=RBYTE88_MAX_IMAGE_HEIGHT,
            )
        )
    assert len(rbyte_data) >= RBYTE88_HEADER_SIZE, "not enough data for RBYTE header"
    rbyte_image_vertical_and_width, rbyte_image_height = struct.unpack(
        "<BB", rbyte_data[:RBYTE88_HEADER_SIZE]
    )
    rbyte_image_vertical = True if rbyte_image_vertical_and_width & 0x80 else False
    rbyte_image_width = rbyte_image_vertical_and_width & 0x7F
    assert rbyte_image_width <= RBYTE88_MAX_IMAGE_WIDTH, (
        "image width (%(rbyte_image_width)d bytes, representing %(rbyte_image_width_px)d pixels) exceeds screen width (%(RBYTE88_MAX_IMAGE_WIDTH)d bytes, representing %(RBYTE88_MAX_IMAGE_WIDTH_px)d pixels)"
        % dict(
            rbyte_image_width=rbyte_image_width,
            rbyte_image_width_px=8 * rbyte_image_width,
            RBYTE88_MAX_IMAGE_WIDTH=RBYTE88_MAX_IMAGE_WIDTH,
            RBYTE88_MAX_IMAGE_WIDTH_px=8 * RBYTE88_MAX_IMAGE_WIDTH,
        )
    )
    assert rbyte_image_height <= RBYTE88_MAX_IMAGE_HEIGHT, (
        "image height (%(rbyte_image_height)d lines) exceeds screen height (%(RBYTE88_MAX_IMAGE_HEIGHT)d lines)"
        % dict(
            rbyte_image_height=rbyte_image_height,
            RBYTE88_MAX_IMAGE_HEIGHT=RBYTE88_MAX_IMAGE_HEIGHT,
        )
    )
    if x_offset is not None:
        assert x_offset + rbyte_image_width <= RBYTE88_MAX_IMAGE_WIDTH, (
            "x_offset is too large for this image's width and places the image offscreen; maximum x_offset for this image is %(max_x_offset)d bytes, representing %(max_x_offset_px)d pixels"
            % dict(
                max_x_offset=RBYTE88_MAX_IMAGE_WIDTH - rbyte_image_width,
                max_x_offset_px=8 * (RBYTE88_MAX_IMAGE_WIDTH - rbyte_image_width),
            )
        )
        decoded_image_width = 8 * RBYTE88_MAX_IMAGE_WIDTH
    else:
        decoded_image_width = 8 * rbyte_image_width
        x_offset = 0
    if y_offset is not None:
        assert y_offset + rbyte_image_height <= RBYTE88_MAX_IMAGE_HEIGHT, (
            "y_offset is too large for this image's height and places the image offscreen; maximum y_offset for this image is %(max_y_offset)d lines"
            % dict(
                max_y_offset=RBYTE88_MAX_IMAGE_HEIGHT - rbyte_image_height,
            )
        )
        decoded_image_height = 2 * RBYTE88_MAX_IMAGE_HEIGHT
    else:
        decoded_image_height = 2 * rbyte_image_height
        y_offset = 0
    decoded_image = Image.new(
        "RGBA", (decoded_image_width, decoded_image_height), TRANSPARENT_BLACK_RGBA
    )

    # Fill in a rectangular placeholder pattern which will be overwritten by the decoded image
    for y in range(y_offset, y_offset + rbyte_image_height):
        for x in range(x_offset, x_offset + rbyte_image_width):
            for i in range(8):
                decoded_image.putpixel(
                    (8 * x + i, 2 * y),
                    (
                        64 + 18 * ((8 * x + i) % 8),
                        64 + 18 * ((8 * x + i + 2 * y) % 8),
                        64 + 18 * ((2 * y) % 8),
                        127,
                    ),
                )
                decoded_image.putpixel(
                    (8 * x + i, 1 + 2 * y),
                    (
                        64 + 18 * ((8 * x + i) % 8),
                        64 + 18 * ((8 * x + i + 1 + 2 * y) % 8),
                        64 + 18 * ((1 + 2 * y) % 8),
                        127,
                    ),
                )

    decoded_rbyte_data = b""
    previous_data_bytes = b""
    extra_bytes = b""
    i_sz, j_sz = (
        (rbyte_image_height, rbyte_image_width)
        if rbyte_image_vertical
        else (rbyte_image_width, rbyte_image_height)
    )
    i, j = (0, 0)
    i_nm, j_nm = ("y", "x") if rbyte_image_vertical else ("x", "y")
    c = 0
    for data_byte in rbyte_data[RBYTE88_HEADER_SIZE:]:
        if len(decoded_rbyte_data) == 3 * rbyte_image_width * rbyte_image_height:
            if extra_bytes == b"":
                assert (
                    data_byte == 0x1A
                ), "Extra bytes at end of RBYTE data must begin with Ctrl-Z (EOF)"
            extra_bytes += bytes([data_byte])
            assert (
                len(extra_bytes) <= 2 * FAT8_SECTOR_SIZE
            ), f"RBYTE data must be followed by at most 2*{FAT8_SECTOR_SIZE} bytes of sector padding {extra_bytes}"
            continue
        assert (
            len(decoded_rbyte_data) <= 3 * rbyte_image_width * rbyte_image_height
        ), "Decoded data is too large"
        if (
            (previous_data_bytes == b"")
            or len(previous_data_bytes) == 1
            and previous_data_bytes[0] != data_byte
        ):
            previous_data_bytes = bytes([data_byte])
            decoded_rbyte_data += previous_data_bytes
            i += 1
        elif len(previous_data_bytes) == 1 and previous_data_bytes[0] == data_byte:
            previous_data_bytes += bytes([data_byte])
            decoded_rbyte_data += bytes([data_byte])
            i += 1
        elif len(previous_data_bytes) == 2:
            assert data_byte >= 1, "Repeat count canot be zero"
            repeat_count = data_byte - 1
            decoded_rbyte_data += repeat_count * previous_data_bytes[-1:]
            i += repeat_count
            previous_data_bytes = b""
        else:
            assert False, "This code should not be reachable."
        if i >= i_sz:
            # assert i == i_sz, f"Strip overflow at {('plane', c, i_nm, i, i_sz, j_nm, j, j_sz)}"
            j += i // i_sz
            i %= i_sz
        if j >= j_sz:
            assert (
                j == j_sz
            ), f"Plane overflow at {('plane', c, i_nm, i, i_sz, j_nm, j, j_sz)}"
            c += j // j_sz
            j %= j_sz
            previous_data_bytes = b""
        assert c <= 2 or (
            (c, i, j) == (3, 0, 0)
        ), f"Image overflow at {('plane', c, i_nm, i, i_sz, j_nm, j, j_sz)}"
    if extra_bytes:
        assert (
            len(rbyte_data) % FAT8_SECTOR_SIZE == 0
        ), f"When padded, the length of the RBYTE data must be a multiple of {FAT8_SECTOR_SIZE}"
    if False:
        assert (
            len(decoded_rbyte_data) == 3 * rbyte_image_width * rbyte_image_height
        ), "RBYTE data must contain exactly three pixel planes"
    decoded_rbyte_data_offset = 0
    for color_channel in (2, 0, 1):
        try:
            if RBYTE88_VERBOSE_DEBUGGING:
                print(dict(color_channel=color_channel))
            y_range = range(y_offset, y_offset + rbyte_image_height)
            x_range = range(x_offset, x_offset + rbyte_image_width)
            i_range, j_range = (
                (y_range, x_range) if rbyte_image_vertical else (x_range, y_range)
            )
            for j in j_range:
                if RBYTE88_VERBOSE_DEBUGGING:
                    print(dict(color_channel=color_channel, j=j))
                for i in i_range:
                    x, y = (j, i) if rbyte_image_vertical else (i, j)
                    if RBYTE88_VERBOSE_DEBUGGING:
                        print(dict(color_channel=color_channel, y=y, x=x))
                    data_byte, decoded_rbyte_data_offset = (
                        decoded_rbyte_data[decoded_rbyte_data_offset],
                        1 + decoded_rbyte_data_offset,
                    )
                    draw_pixel_byte(
                        decoded_image,
                        color_channel,
                        x,
                        y,
                        data_byte,
                        x_offset,
                        y_offset,
                        rbyte_image_width,
                        rbyte_image_height,
                    )
        except:
            decoded_image.show()
            raise
    return decoded_image


def rbyte88_main():
    try:
        _, rbyte88_data_file_name = sys.argv
        x_offset, y_offset = None, None
    except ValueError:
        (  # usage: python rbyte88.py RBYTE88_FILE [ X-OFFSET (in bytes, i.e. eight-pixel groups) Y-OFFSET (in lines) ]  # generates RBYTE88_FILE_[X-OFFSET_Y-OFFSET_]rbyte88.png in the current directory
            _,
            rbyte88_data_file_name,
            x_offset,
            y_offset,
        ) = sys.argv
        x_offset, y_offset = int(x_offset), int(y_offset)
    if x_offset is None and y_offset is None:
        output_file_name = rbyte88_data_file_name + "_rbyte88.png"
    else:
        output_file_name = (
            rbyte88_data_file_name
            + "_%(x_offset)d_%(y_offset)d_rbyte88.png"
            % dict(x_offset=x_offset, y_offset=y_offset)
        )
    output_file_name = os.path.basename(output_file_name)
    if os.path.lexists(output_file_name):
        os.remove(output_file_name)
        print(
            "removed previous %(output_file_name)s"
            % dict(output_file_name=output_file_name)
        )
    rbyte88_data = open(rbyte88_data_file_name, "rb").read()
    decoded_image = decode_rbyte88_data(rbyte88_data, x_offset, y_offset)
    pnginfo = PngInfo()
    pnginfo.add(b"gAMA", int(0.45455e5).to_bytes(4, "big"))
    decoded_image.save(output_file_name, pnginfo=pnginfo)
    print("saved %(output_file_name)s" % dict(output_file_name=output_file_name))


if __name__ == "__main__":
    rbyte88_main()
