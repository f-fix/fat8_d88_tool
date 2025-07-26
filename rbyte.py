#!/usr/bin/env python3

"""
RBYTE image data decoder and viewer

The RBYTE details here are entirely inferred based on
reverse-engineering of a single game's data and may be wrong in many
respects.

RBYTE is a placeholder name based on the name of the file containing
the decoding routine, and may be a pun on `アルバイト` (Arbeit[er],
i.e. a part-time job [or worker]). The origin of this image format
and decoder are not yet known. It was used in the doujin software
`KYOTO討龍伝` (Kyoto Touryuuden) by Asuka.Load and
Halord.Jonson/Lafiel Soft/Specters for the NEC PC-98 series from
1990. This game stores image data in a compressed form ("RBYTE") on
the FAT8-formatted floppy disk, one image per file. To display an
image, it is first BLOAD'ed, then the RBYTE decoder/viewer is
invoked with start address of the encoded image data, a display
x-offset in bytes (that is, multiples of 8 pixels), and a display
y-offset in lines. The decoder reads the image width (in bytes,
i.e. multiples of 8 pixels) and height (in lines) from the four-byte
header of the image data, then proceeds to decode the image data
into video memory.

The image files are stored in N88-BASIC(86)'s BLOAD format, and
their BLOAD headers indicate they load starting at offset 0x1000 in
the current segment. This is the same segment from which the RBYTE
decoder runs. The RBYTE decoder is BLOAD'ed into that segment
starting at address 0, and apart from code, encoded image data and
video memory it also uses some of the first part of that segment as
working memory.

The image decoder does not clear video memory before it runs, so any
image data already on the screen is simply overlaid by that produced
during the decoding process. The image itself is encoded in a planar
fashion appropriate to the PC-98 video hardware. This game does not
appear to manipulate the video palette on PC-98 graphics systems
that have that feature, so the palette used is the default one. This
game runs in the common PC-98 GDC 8-color mode with a graphics
resolution of 640 pixels x 200 lines.

"""

from PIL import Image
from PIL.PngImagePlugin import PngInfo

import os
import struct
import sys

RBYTE_VERBOSE_DEBUGGING = False

RBYTE_HEADER_SIZE = 4
RBYTE_MAX_IMAGE_WIDTH = 640 // 8
RBYTE_MAX_IMAGE_HEIGHT = 200
TRANSPARENT_BLACK_RGBA = (0, 0, 0, 0)


def copy_pixel_byte(
    image,
    color_channel,
    x1,
    y1,
    x2,
    y2,
    x_offset,
    y_offset,
    rbyte_image_width,
    rbyte_image_height,
):
    """Given a PIL Image (image), a color channel index color_channel,
    a source x-offset of x1 bytes (counting groups of 8 pixels), a
    source y-offset of y1 lines, a destination x-offset of x2 bytes
    (counting groups of 8 pixels), and a destination y-offset of y2
    lines, copies the source pixel data to the destination. The pixel
    copying assumes vertical scan-doubling to improve viewability on
    non-PC 98 displays.

    """
    message = []
    if x1 >= RBYTE_MAX_IMAGE_HEIGHT:
        message += ["x1 wrapped!!! %r" % dict(x1=x1)]
    if x1 < x_offset or x1 >= x_offset + rbyte_image_width:
        message += ["x1 out of bounds!!! %r" % dict(x1=x1)]
    if y1 < y_offset or y1 >= y_offset + rbyte_image_height:
        message += ["y1 out of bounds!!! %r" % dict(y1=y1)]
    y1 += x1 // RBYTE_MAX_IMAGE_WIDTH
    x1 %= RBYTE_MAX_IMAGE_WIDTH
    if x2 >= RBYTE_MAX_IMAGE_HEIGHT:
        message += ["x2 wrapped!!! %r" % dict(x2=x2)]
    if x2 < x_offset or x2 >= x_offset + rbyte_image_width:
        message += ["x2 out of bounds!!! %r" % dict(x2=x2)]
    if y2 < y_offset or y2 >= y_offset + rbyte_image_height:
        message += ["y2 out of bounds!!! %r" % dict(y2=y2)]
    y2 += x2 // RBYTE_MAX_IMAGE_WIDTH
    x2 %= RBYTE_MAX_IMAGE_WIDTH
    assert x1 == x2
    if RBYTE_VERBOSE_DEBUGGING:
        print(
            "copy_pixel_byte",
            dict(
                color_channel=color_channel,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                message=set(message),
                x_offset=x_offset,
                y_offset=y_offset,
                rbyte_image_width=rbyte_image_width,
                rbyte_image_height=rbyte_image_height,
            ),
        )
    assert color_channel in (
        0,
        1,
        2,
    ), "The color_channel to update must be one of R(0)/G(1)/B(2)"
    for i in range(8):
        pixel1 = list(image.getpixel((8 * x1 + i, 2 * y1)))
        pixel2 = list(image.getpixel((8 * x1 + i, 1 + 2 * y1)))
        if pixel1[color_channel] not in (0, 255) or pixel1[3] != 255:
            message += ["copying uninitialized pixel!!!"]
        pixel3 = list(image.getpixel((8 * x2 + i, 2 * y2)))
        pixel4 = list(image.getpixel((8 * x2 + i, 1 + 2 * y2)))
        pixel3[color_channel] = pixel1[color_channel]
        pixel4[color_channel] = pixel2[color_channel]
        pixel3[3] = pixel4[3] = 255  # completely opaque
        image.putpixel((8 * x2 + i, 2 * y2), tuple(pixel3))
        image.putpixel((8 * x2 + i, 1 + 2 * y2), tuple(pixel4))
    assert not len(message), set(message)


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
    scan-doubled to improve viewability on non-PC 98 displays.

    """
    assert color_channel in (
        0,
        1,
        2,
    ), "The color_channel to update must be one of R(0)/G(1)/B(2)"
    message = []
    if x >= RBYTE_MAX_IMAGE_HEIGHT:
        message += ["x wrapped!!! %r" % dict(x=x)]
    if x < x_offset or x >= x_offset + rbyte_image_width:
        message += ["x out of bounds!!! %r" % dict(x=x)]
    if y < y_offset or y >= y_offset + rbyte_image_height:
        message += ["y out of bounds!!! %r" % dict(y=y)]
    y += x // RBYTE_MAX_IMAGE_WIDTH
    x %= RBYTE_MAX_IMAGE_WIDTH
    if RBYTE_VERBOSE_DEBUGGING:
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


def decode_rbyte_data(rbyte_data, x_offset=None, y_offset=None):
    """Given binary RBYTE data as input, decodes it and produces a PIL
    Image as output. Starting x_offset and y_offset may be
    provided. If either is omitted or None, the returned image will be
    exactly the dimensions specified in the RBYTE data for that
    axis. Otherwise, the image will be placed in a transparent
    screen-dimensioned image for that axis with the image rendered at
    the specified offset. The x_offset counts in bytes (8-pixel
    groups) from the left edge, the y_offset counts in lines from the
    top edge. The generated PIL image will be vertically scan-doubled
    to improve viewability on non-PC 98 displays.

    """
    if x_offset is not None:
        assert x_offset == int(x_offset), "x_offset must be None or an integer"
        assert x_offset in range(0, RBYTE_MAX_IMAGE_WIDTH + 1), (
            "x_offset may not exceed screen width (%(RBYTE_MAX_IMAGE_WIDTH)d bytes, representing %(RBYTE_MAX_IMAGE_WIDTH_px)d pixels)"
            % dict(
                RBYTE_MAX_IMAGE_WIDTH=RBYTE_MAX_IMAGE_WIDTH,
                RBYTE_MAX_IMAGE_WIDTH_px=8 * RBYTE_MAX_IMAGE_WIDTH,
            )
        )
    if y_offset is not None:
        assert y_offset == int(y_offset), "y_offset must be None or an integer"
        assert y_offset in range(0, RBYTE_MAX_IMAGE_HEIGHT + 1), (
            "y_offset may not exceed screen height (%(RBYTE_MAX_IMAGE_HEIGHT)d lines)"
            % dict(
                RBYTE_MAX_IMAGE_HEIGHT=RBYTE_MAX_IMAGE_HEIGHT,
            )
        )
    assert len(rbyte_data) >= RBYTE_HEADER_SIZE, "not enough data for RBYTE header"
    rbyte_image_width, rbyte_image_height = struct.unpack(
        "<HH", rbyte_data[:RBYTE_HEADER_SIZE]
    )
    assert rbyte_image_width <= RBYTE_MAX_IMAGE_WIDTH, (
        "image width (%(rbyte_image_width)d bytes, representing %(rbyte_image_width_px)d pixels) exceeds screen width (%(RBYTE_MAX_IMAGE_WIDTH)d bytes, representing %(RBYTE_MAX_IMAGE_WIDTH_px)d pixels)"
        % dict(
            rbyte_image_width=rbyte_image_width,
            rbyte_image_width_px=8 * rbyte_image_width,
            RBYTE_MAX_IMAGE_WIDTH=RBYTE_MAX_IMAGE_WIDTH,
            RBYTE_MAX_IMAGE_WIDTH_px=8 * RBYTE_MAX_IMAGE_WIDTH,
        )
    )
    assert rbyte_image_height <= RBYTE_MAX_IMAGE_HEIGHT, (
        "image height (%(rbyte_image_height)d lines) exceeds screen height (%(RBYTE_MAX_IMAGE_HEIGHT)d lines)"
        % dict(
            rbyte_image_height=rbyte_image_height,
            RBYTE_MAX_IMAGE_HEIGHT=RBYTE_MAX_IMAGE_HEIGHT,
        )
    )
    if x_offset is not None:
        assert x_offset + rbyte_image_width <= RBYTE_MAX_IMAGE_WIDTH, (
            "x_offset is too large for this image's width and places the image offscreen; maximum x_offset for this image is %(max_x_offset)d bytes, representing %(max_x_offset_px)d pixels"
            % dict(
                max_x_offset=RBYTE_MAX_IMAGE_WIDTH - rbyte_image_width,
                max_x_offset_px=8 * (RBYTE_MAX_IMAGE_WIDTH - rbyte_image_width),
            )
        )
        decoded_image_width = 8 * RBYTE_MAX_IMAGE_WIDTH
    else:
        decoded_image_width = 8 * rbyte_image_width
        x_offset = 0
    if y_offset is not None:
        assert y_offset + rbyte_image_height <= RBYTE_MAX_IMAGE_HEIGHT, (
            "y_offset is too large for this image's height and places the image offscreen; maximum y_offset for this image is %(max_y_offset)d lines"
            % dict(
                max_y_offset=RBYTE_MAX_IMAGE_HEIGHT - rbyte_image_height,
            )
        )
        decoded_image_height = 2 * RBYTE_MAX_IMAGE_HEIGHT
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

    rbyte_data_offset = RBYTE_HEADER_SIZE

    drawn_bytes = 0
    all_planes_success = False
    try:
        for color_channel in (2, 0, 1):
            if RBYTE_VERBOSE_DEBUGGING:
                print(dict(color_channel=color_channel))
            single_plane_success = False
            try:
                for y in range(y_offset, y_offset + rbyte_image_height):
                    if RBYTE_VERBOSE_DEBUGGING:
                        print(dict(color_channel=color_channel, y=y))
                    for x in range(x_offset, x_offset + rbyte_image_width):
                        if drawn_bytes:
                            drawn_bytes -= 1
                            continue
                        if RBYTE_VERBOSE_DEBUGGING:
                            print(dict(color_channel=color_channel, y=y, x=x))
                        line_command_byte, rbyte_data_offset = (
                            rbyte_data[rbyte_data_offset],
                            1 + rbyte_data_offset,
                        )
                        if RBYTE_VERBOSE_DEBUGGING:
                            print(dict(line_command_byte="0x%02X" % line_command_byte))
                        if line_command_byte >= 0x80 and line_command_byte <= 0x8F:
                            y_deflection = line_command_byte & 0x0F
                            if RBYTE_VERBOSE_DEBUGGING:
                                print(
                                    "CMD_COPY_PREVIOUS_LINE",
                                    dict(
                                        y_deflection=y_deflection,
                                    ),
                                )
                            if y_deflection == 0:
                                if RBYTE_VERBOSE_DEBUGGING:
                                    print(
                                        "CMD_COPY_PREVIOUS_LINE command with zero deflection!!!"
                                    )
                            assert (
                                y_deflection > 0
                            ), "CMD_COPY_PREVIOUS_LINE command with zero deflection"
                            assert y_deflection <= y, (
                                "CMD_COPY_PREVIOUS_LINE command deflection underflow %(params)r"
                                % dict(
                                    params=dict(
                                        y_deflection=y_deflection,
                                        y=y,
                                    ),
                                )
                            )
                            for i in range(x, x_offset + rbyte_image_width):
                                copy_pixel_byte(
                                    decoded_image,
                                    color_channel,
                                    i,
                                    y - y_deflection,
                                    i,
                                    y,
                                    x_offset,
                                    y_offset,
                                    rbyte_image_width,
                                    rbyte_image_height,
                                )
                                drawn_bytes += 1
                        elif line_command_byte == 0x40:
                            if RBYTE_VERBOSE_DEBUGGING:
                                print("CMD_REPEATED_BLOCKS_UNTIL_FF")
                            while True:
                                data_byte, rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                                repeat, rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                                assert (
                                    repeat != 0x00
                                ), "encountered a zero-byte repetition (repeat byte 0x00)"
                                if RBYTE_VERBOSE_DEBUGGING:
                                    print(
                                        dict(
                                            data_byte=data_byte,
                                            repeat=repeat,
                                        )
                                    )
                                if repeat == 0xFF:
                                    break
                                for i in range(repeat):
                                    draw_pixel_byte(
                                        decoded_image,
                                        color_channel,
                                        x + drawn_bytes + i,
                                        y,
                                        data_byte,
                                        x_offset,
                                        y_offset,
                                        rbyte_image_width,
                                        rbyte_image_height,
                                    )
                                drawn_bytes += repeat
                            # fill the rest of the line with the given data byte
                            assert (
                                repeat != 0x00
                            ), "encountered an implicit zero-byte repetition (repeat byte 0xFF at end of line)"
                            repeat = (x_offset + rbyte_image_width) - (x + drawn_bytes)
                            for i in range(repeat):
                                draw_pixel_byte(
                                    decoded_image,
                                    color_channel,
                                    x + drawn_bytes + i,
                                    y,
                                    data_byte,
                                    x_offset,
                                    y_offset,
                                    rbyte_image_width,
                                    rbyte_image_height,
                                )
                            drawn_bytes += repeat
                        elif line_command_byte >= 0xB0 and line_command_byte <= 0xFF:
                            y_deflection = line_command_byte & 0x0F
                            if RBYTE_VERBOSE_DEBUGGING:
                                print(
                                    "CMD_MIXED_COPY_PREVIOUS_LINE_AND_LITERAL_PIXEL_DATA",
                                    dict(y_deflection=y_deflection),
                                )
                            # assert y_deflection > 0, "CMD_MIXED_COPY_PREVIOUS_LINE_AND_LITERAL_PIXEL_DATA command with zero deflection"
                            assert y_deflection <= y, (
                                "CMD_MIXED_COPY_PREVIOUS_LINE_AND_LITERAL_PIXEL_DATA command deflection underflow %(params)r"
                                % dict(
                                    params=dict(
                                        y_deflection=y_deflection,
                                        y=y,
                                    ),
                                )
                            )
                            while True:
                                count_byte, rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                                if RBYTE_VERBOSE_DEBUGGING:
                                    print(dict(count_byte=count_byte))
                                if count_byte == 0x00:
                                    count_byte2, rbyte_data_offset = (
                                        rbyte_data[rbyte_data_offset],
                                        1 + rbyte_data_offset,
                                    )
                                    if RBYTE_VERBOSE_DEBUGGING:
                                        print(dict(count_byte2=count_byte2))
                                    for i in range(
                                        x + drawn_bytes, x + drawn_bytes + count_byte2
                                    ):
                                        data_byte, rbyte_data_offset = (
                                            rbyte_data[rbyte_data_offset],
                                            1 + rbyte_data_offset,
                                        )
                                        draw_pixel_byte(
                                            decoded_image,
                                            color_channel,
                                            i,
                                            y,
                                            data_byte,
                                            x_offset,
                                            y_offset,
                                            rbyte_image_width,
                                            rbyte_image_height,
                                        )
                                    drawn_bytes += count_byte2
                                    count_byte3, rbyte_data_offset = (
                                        rbyte_data[rbyte_data_offset],
                                        1 + rbyte_data_offset,
                                    )
                                    if RBYTE_VERBOSE_DEBUGGING:
                                        print(dict(count_byte3=count_byte3))
                                    if count_byte3 == 0xFF:
                                        break
                                    for i in range(count_byte3):
                                        copy_pixel_byte(
                                            decoded_image,
                                            color_channel,
                                            x + drawn_bytes + i,
                                            y - y_deflection,
                                            x + drawn_bytes + i,
                                            y,
                                            x_offset,
                                            y_offset,
                                            rbyte_image_width,
                                            rbyte_image_height,
                                        )
                                    drawn_bytes += count_byte3
                                    count_byte4, rbyte_data_offset = (
                                        rbyte_data[rbyte_data_offset],
                                        1 + rbyte_data_offset,
                                    )
                                    if RBYTE_VERBOSE_DEBUGGING:
                                        print(dict(count_byte4=count_byte4))
                                    if count_byte4 != 0xFF:
                                        rbyte_data_offset -= 2
                                        rbyte_data = (
                                            rbyte_data[:rbyte_data_offset]
                                            + b"\x00"
                                            + rbyte_data[rbyte_data_offset + 1 :]
                                        )
                                        if RBYTE_VERBOSE_DEBUGGING:
                                            print("putting it back with a NUL!!!")
                                        continue
                                    # draw the rest of the line from immediate data
                                    for i in range(
                                        x + drawn_bytes, x_offset + rbyte_image_width
                                    ):
                                        data_byte, rbyte_data_offset = (
                                            rbyte_data[rbyte_data_offset],
                                            1 + rbyte_data_offset,
                                        )
                                        draw_pixel_byte(
                                            decoded_image,
                                            color_channel,
                                            i,
                                            y,
                                            data_byte,
                                            x_offset,
                                            y_offset,
                                            rbyte_image_width,
                                            rbyte_image_height,
                                        )
                                        drawn_bytes += 1
                                    break
                                if count_byte == 0xFF:
                                    break
                                for i in range(count_byte):
                                    copy_pixel_byte(
                                        decoded_image,
                                        color_channel,
                                        x + drawn_bytes + i,
                                        y - y_deflection,
                                        x + drawn_bytes + i,
                                        y,
                                        x_offset,
                                        y_offset,
                                        rbyte_image_width,
                                        rbyte_image_height,
                                    )
                                drawn_bytes += count_byte
                                count_byte5, rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                                if RBYTE_VERBOSE_DEBUGGING:
                                    print(dict(count_byte5=count_byte5))
                                if count_byte5 != 0xFF:
                                    rbyte_data_offset -= 2
                                    rbyte_data = (
                                        rbyte_data[:rbyte_data_offset]
                                        + b"\x00"
                                        + rbyte_data[rbyte_data_offset + 1 :]
                                    )
                                    if RBYTE_VERBOSE_DEBUGGING:
                                        print("putting it back with a NUL!!!")
                                    continue
                                # draw the rest of the line from immediate data
                                for i in range(
                                    x + drawn_bytes, x_offset + rbyte_image_width
                                ):
                                    data_byte, rbyte_data_offset = (
                                        rbyte_data[rbyte_data_offset],
                                        1 + rbyte_data_offset,
                                    )
                                    draw_pixel_byte(
                                        decoded_image,
                                        color_channel,
                                        i,
                                        y,
                                        data_byte,
                                        x_offset,
                                        y_offset,
                                        rbyte_image_width,
                                        rbyte_image_height,
                                    )
                                    drawn_bytes += 1
                                break
                            for i in range(
                                x + drawn_bytes, x_offset + rbyte_image_width
                            ):
                                copy_pixel_byte(
                                    decoded_image,
                                    color_channel,
                                    i,
                                    y - y_deflection,
                                    i,
                                    y,
                                    x_offset,
                                    y_offset,
                                    rbyte_image_width,
                                    rbyte_image_height,
                                )
                                drawn_bytes += 1
                        elif line_command_byte >= 0xA0 and line_command_byte <= 0xAF:
                            # copy remainder of a preceding line, deflection to that line is the low nybble
                            y_deflection = line_command_byte & 0x0F
                            if RBYTE_VERBOSE_DEBUGGING:
                                print(
                                    "CMD_DRAW_AFTER_COPY_PREVIOUS_LINE",
                                    dict(y_deflection=y_deflection),
                                )
                            assert (
                                y_deflection > 0
                            ), "CMD_DRAW_AFTER_COPY_PREVIOUS_LINE command with zero deflection"
                            assert y_deflection <= y, (
                                "CMD_DRAW_AFTER_COPY_PREVIOUS_LINE command deflection underflow %(params)r"
                                % dict(
                                    params=dict(
                                        y_deflection=y_deflection,
                                        y=y,
                                    ),
                                )
                            )
                            for i in range(x, x_offset + rbyte_image_width):
                                copy_pixel_byte(
                                    decoded_image,
                                    color_channel,
                                    i,
                                    y - y_deflection,
                                    i,
                                    y,
                                    x_offset,
                                    y_offset,
                                    rbyte_image_width,
                                    rbyte_image_height,
                                )
                                drawn_bytes += 1
                            # overwrite specified parts of the line with new data
                            skip_masks = {}
                            for line_region in range(rbyte_image_width // 8):
                                skip_masks[line_region], rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                            for line_region in range(rbyte_image_width // 8):
                                skip_mask = skip_masks[line_region]
                                if RBYTE_VERBOSE_DEBUGGING:
                                    print(
                                        dict(
                                            line_region=line_region,
                                            skip_mask=bin(0x100 | skip_mask)[
                                                len(bin(1)) :
                                            ],
                                        )
                                    )
                                for n in range(8):
                                    if RBYTE_VERBOSE_DEBUGGING:
                                        print(dict(n=n))
                                    skip_mask <<= 1
                                    if not (skip_mask & 0x100):
                                        continue
                                    data_byte, rbyte_data_offset = (
                                        rbyte_data[rbyte_data_offset],
                                        1 + rbyte_data_offset,
                                    )
                                    if RBYTE_VERBOSE_DEBUGGING:
                                        print(
                                            dict(
                                                data_byte=bin(0x100 | data_byte)[
                                                    len(bin(1)) :
                                                ]
                                            )
                                        )
                                    draw_pixel_byte(
                                        decoded_image,
                                        color_channel,
                                        x_offset + 8 * line_region + n,
                                        y,
                                        data_byte,
                                        x_offset,
                                        y_offset,
                                        rbyte_image_width,
                                        rbyte_image_height,
                                    )
                                    # do not update drawn_bytes, we already did when copying the previous line data!
                        elif line_command_byte >= 0x90 and line_command_byte <= 0x9F:
                            # copy regions from a preceding line except for override bytes
                            y_deflection = line_command_byte & 0x0F
                            if RBYTE_VERBOSE_DEBUGGING:
                                print(
                                    "CMD_MIXED_COPY_PREVIOUS_LINE_AND_DRAW",
                                    dict(y_deflection=y_deflection),
                                )
                            assert (
                                y_deflection > 0
                            ), "CMD_MIXED_COPY_PREVIOUS_LINE_AND_DRAW command with zero deflection"
                            assert y_deflection <= y, (
                                "CMD_MIXED_COPY_PREVIOUS_LINE_AND_DRAW command deflection underflow %(params)r"
                                % dict(
                                    params=dict(
                                        y_deflection=y_deflection,
                                        y=y,
                                    ),
                                )
                            )
                            while True:
                                count_byte, rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                                if RBYTE_VERBOSE_DEBUGGING:
                                    print(dict(count_byte=count_byte))
                                if count_byte == 0xFF:
                                    break
                                for n in range(count_byte):
                                    copy_pixel_byte(
                                        decoded_image,
                                        color_channel,
                                        x + drawn_bytes + n,
                                        y - y_deflection,
                                        x + drawn_bytes + n,
                                        y,
                                        x_offset,
                                        y_offset,
                                        rbyte_image_width,
                                        rbyte_image_height,
                                    )
                                drawn_bytes += count_byte
                                data_byte, rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                                if RBYTE_VERBOSE_DEBUGGING:
                                    print(dict(data_byte=data_byte))
                                draw_pixel_byte(
                                    decoded_image,
                                    color_channel,
                                    x + drawn_bytes,
                                    y,
                                    data_byte,
                                    x_offset,
                                    y_offset,
                                    rbyte_image_width,
                                    rbyte_image_height,
                                )
                                drawn_bytes += 1
                            for i in range(
                                x + drawn_bytes, x_offset + rbyte_image_width
                            ):
                                copy_pixel_byte(
                                    decoded_image,
                                    color_channel,
                                    i,
                                    y - y_deflection,
                                    i,
                                    y,
                                    x_offset,
                                    y_offset,
                                    rbyte_image_width,
                                    rbyte_image_height,
                                )
                                drawn_bytes += 1
                        elif (
                            line_command_byte >= 0x00
                            and line_command_byte <= 0x7F
                            and line_command_byte != 0x40
                        ):
                            # copy line to video memory
                            if RBYTE_VERBOSE_DEBUGGING:
                                print("CMD_LITERAL_PIXEL_LINE")
                            for i in range(x, x_offset + rbyte_image_width):
                                data_byte, rbyte_data_offset = (
                                    rbyte_data[rbyte_data_offset],
                                    1 + rbyte_data_offset,
                                )
                                draw_pixel_byte(
                                    decoded_image,
                                    color_channel,
                                    i,
                                    y,
                                    data_byte,
                                    x_offset,
                                    y_offset,
                                    rbyte_image_width,
                                    rbyte_image_height,
                                )
                                drawn_bytes += 1
                        else:
                            assert False, "unimplemented line_command_byte!!!"

                        if drawn_bytes:
                            drawn_bytes -= 1
                    assert drawn_bytes == 0, (
                        "drawing operation overflowed a line boundary by %(drawn_bytes)d bytes"
                        % dict(
                            drawn_bytes=drawn_bytes,
                        )
                    )
                single_plane_success = True
            finally:
                if not single_plane_success:
                    plane_image = Image.new(
                        "RGBA",
                        (decoded_image_width, decoded_image_height),
                        TRANSPARENT_BLACK_RGBA,
                    )
                    for y in range(decoded_image_height):
                        for x in range(decoded_image_width):
                            pixel = list(decoded_image.getpixel((x, y)))
                            for other_color_channel in range(3):
                                if other_color_channel != color_channel:
                                    pixel[other_color_channel] = 0
                            if pixel[color_channel] not in (0, 255) or pixel[3] != 255:
                                pixel[3] = 0  # completely transparent
                            plane_image.putpixel((x, y), tuple(pixel))
                    plane_image.show()
        all_planes_success = True
    finally:
        all_planes_rgba_image = Image.new(
            "RGBA", (decoded_image_width, decoded_image_height), TRANSPARENT_BLACK_RGBA
        )
        all_planes_rgb_image = Image.new(
            "P", (decoded_image_width, decoded_image_height), TRANSPARENT_BLACK_RGBA[:3]
        )
        all_planes_rgb_image.putpalette(
            sum(
                [
                    [
                        255 if i & 2 else 127 if i & 8 else 0,
                        255 if i & 1 else 127 if i & 8 else 0,
                        255 if i & 4 else 127 if i & 8 else 0,
                    ]
                    for i in range(16)
                ],
                [],
            )
        )
        has_partial_pixels = False
        has_transparent_pixels = False
        for y in range(decoded_image_height):
            for x in range(decoded_image_width):
                pixel = list(decoded_image.getpixel((x, y)))
                uninitialized_channels = 0
                for color_channel in range(3):
                    if pixel[color_channel] not in (0, 255) or pixel[3] != 255:
                        uninitialized_channels += 1
                    if pixel[color_channel] not in (0, 255):
                        pixel[color_channel] = 0  # any uninitialized channel => black
                if uninitialized_channels == 3:
                    pixel[3] = 0  # completely transparent
                elif uninitialized_channels:
                    pixel[3] = 127  # half-transparent
                    has_partial_pixels = True
                    all_planes_success = False
                if pixel[3] != 255:
                    has_transparent_pixels = True
                all_planes_rgba_image.putpixel((x, y), tuple(pixel))
                all_planes_rgb_image.putpixel((x, y), tuple(pixel[:3]))
        all_planes_image = (
            all_planes_rgba_image if has_transparent_pixels else all_planes_rgb_image
        )
        if not all_planes_success:
            all_planes_image.show()
            decoded_image.show()
            assert (
                has_partial_pixels == False
            ), "Image contains partially-initialized pixels"
        else:
            decoded_image = all_planes_image
    return decoded_image


FAT8_SECTOR_SIZE = 512
BLOAD_HEADER_SIZE = 4


def decode_rbyte_bload_data(rbyte_bload_data):
    """Given binary RBYTE data in a BLOAD wrapper as input, returns
    the unwrapped RBYTE binary data after performing some sanity
    checks.

    """
    assert (
        len(rbyte_bload_data) >= BLOAD_HEADER_SIZE
    ), "not enough data for BLOAD header"
    load_address, stop_address = struct.unpack(
        "<HH", rbyte_bload_data[:BLOAD_HEADER_SIZE]
    )
    assert stop_address >= load_address, "BLOAD header is not correct"
    assert load_address >= 0x1E0, "RBYTE data cannot overwrite RBYTE decoder"
    rbyte_data_length = stop_address - load_address
    rbyte_data = rbyte_bload_data[
        BLOAD_HEADER_SIZE : BLOAD_HEADER_SIZE + rbyte_data_length
    ]
    trailing_data = rbyte_bload_data[BLOAD_HEADER_SIZE + rbyte_data_length :]
    assert (
        len(trailing_data) <= FAT8_SECTOR_SIZE
    ), "Extra FAT8 sectors found at end of BLOAD data %(info)r" % dict(
        info=dict(
            trailing_data=trailing_data,
            load_address=load_address,
            stop_address=stop_address,
            rbyte_data_length=rbyte_data_length,
            expected_size=BLOAD_HEADER_SIZE + rbyte_data_length,
            bload_data_size=len(rbyte_bload_data),
        ),
    )
    if trailing_data:
        assert (
            trailing_data[:1] == b"\x1a"
        ), "Extra bytes at end of BLOAD data must begin with Ctrl-Z (EOF)"
    return rbyte_data


def rbyte_main():
    try:
        _, rbyte_bload_data_file_name = sys.argv
        x_offset, y_offset = None, None
    except ValueError:
        _, rbyte_bload_data_file_name, x_offset, y_offset = (
            sys.argv
        )  # usage: python rbyte.py RBYTE_FILE [ X-OFFSET (in bytes, i.e. eight-pixel groups) Y-OFFSET (in lines) ]  # generates RBYTE_FILE_[X-OFFSET_Y-OFFSET_]rbyte.png
        x_offset, y_offset = int(x_offset), int(y_offset)
    if x_offset is None and y_offset is None:
        output_file_name = rbyte_bload_data_file_name + "_rbyte.png"
    else:
        output_file_name = (
            rbyte_bload_data_file_name
            + "_%(x_offset)d_%(y_offset)d_rbyte.png"
            % dict(x_offset=x_offset, y_offset=y_offset)
        )
    if os.path.lexists(output_file_name):
        os.remove(output_file_name)
        print(
            "removed previous %(output_file_name)s"
            % dict(output_file_name=output_file_name)
        )
    rbyte_bload_data = open(rbyte_bload_data_file_name, "rb").read()
    rbyte_data = decode_rbyte_bload_data(rbyte_bload_data)
    decoded_image = decode_rbyte_data(rbyte_data, x_offset, y_offset)
    pnginfo = PngInfo()
    pnginfo.add(b"gAMA", int(0.45455e5).to_bytes(4, "big"))
    decoded_image.save(output_file_name, pnginfo=pnginfo)
    print("saved %(output_file_name)s" % dict(output_file_name=output_file_name))


if __name__ == "__main__":
    rbyte_main()
