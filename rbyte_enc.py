#!/usr/bin/env python3

from PIL import Image

import struct
import os.path
import sys


def best_line(current_best_line, prospective_best_line, opt_level):
    if opt_level > 0 and (
        (len(prospective_best_line) < len(current_best_line))
        or (opt_level & 1 == 1)
        and (len(current_best_line) == len(prospective_best_line))
        and current_best_line[0] == 0x00
    ):
        return prospective_best_line
    return current_best_line


def opt_line(line, opt_level):
    opt_line = line
    opt_line_40 = b"\x40"  # CMD_REPEATED_BLOCKS_UNTIL_FF
    i = 1
    while i < len(line):
        data_byte, repeat, i = line[i : i + 1], 1, i + 1
        while data_byte == line[i : i + 1]:
            repeat, i = repeat + 1, i + 1
        if i == len(line):
            repeat = 0xFF
        opt_line_40 += data_byte + bytes([repeat])
    opt_line = best_line(opt_line, opt_line_40, opt_level)
    return opt_line


def opt_line_y_offset(line, y_offset, previous_line, opt_line, opt_level):
    assert len(line) == len(previous_line)
    assert line[0] == 0x00 and previous_line[0] == 0x00
    if line == previous_line:
        opt_line = bytes([0x80 | y_offset])  # CMD_COPY_PREVIOUS_LINE
    draw_opt_line = bytes([0x90 | y_offset])  # CMD_MIXED_COPY_PREVIOUS_LINE_AND_DRAW
    i = 1
    while i < len(line):
        if line[i:] == previous_line[i:]:
            break
        count = 0
        while (i + 1) < len(line) and line[i : i + 1] == previous_line[i : i + 1]:
            i += 1
            count += 1
        draw_opt_line += bytes([count, line[i]])
        i += 1
    draw_opt_line += bytes([0xFF])
    opt_line = best_line(opt_line, draw_opt_line, opt_level)
    if (
        line[1 + ((len(line) - 1) // 8) * 8 :]
        == previous_line[1 + ((len(line) - 1) // 8) * 8 :]
    ):
        skip_opt_line = bytes([0xA0 | y_offset])  # CMD_DRAW_AFTER_COPY_PREVIOUS_LINE
        skip_masks = [0x00] * ((len(line) - 1) // 8)
        skip_data = []
        for line_region in range(len(skip_masks)):
            for n in range(8):
                skip_masks[line_region] <<= 1
                x = line_region * 8 + n
                if line[1 + x] != previous_line[1 + x]:
                    skip_masks[line_region] |= 1
                    skip_data.append(line[1 + x])
        skip_opt_line += bytes(skip_masks + skip_data)
        opt_line = best_line(opt_line, skip_opt_line, opt_level)
    draw2_opt_line = bytes(
        [0xB0 | y_offset]
    )  # CMD_MIXED_COPY_PREVIOUS_LINE_AND_LITERAL_PIXEL_DATA
    i = 1
    while i < len(line):
        if line[i:] == previous_line[i:]:
            draw2_opt_line += bytes([0xFF])
            break
        count = 0
        while i < len(line) and line[i] == previous_line[i]:
            i += 1
            count += 1
        if i == len(line):
            count = 0xFF
        draw2_opt_line += bytes([count])
        count2 = 0
        px2 = []
        while i < len(line) and line[i] != previous_line[i]:
            px2.append(line[i])
            i += 1
            count2 += 1
        if i == len(line):
            count2 = 0xFF
        draw2_opt_line += bytes([count2] + px2)
    opt_line = best_line(opt_line, draw2_opt_line, opt_level)
    return opt_line


def opt_frame(frame, opt_level):
    opt_frame = []
    for y, line in enumerate(frame):
        next_opt_line = line
        for y_offset in range(
            1, (min((opt_level - 1) >> 1, 15) if opt_level > 2 else 0) + 1
        ):
            if y - y_offset < 0:
                continue
            next_opt_line_y_offset = opt_line_y_offset(
                line, y_offset, frame[y - y_offset], next_opt_line, opt_level
            )
            next_opt_line = best_line(next_opt_line, next_opt_line_y_offset, opt_level)
        simple_opt_line = opt_line(line, opt_level)
        next_opt_line = best_line(next_opt_line, simple_opt_line, opt_level)
        opt_frame.append(next_opt_line)
    return opt_frame


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


def encode_rbyte(*, image, opt_level):
    if image.width > 640 or image.height > 400:
        scale = min(640 / image.width, 400 / image.height)
        image = image.resize((int(image.width * scale), int(image.height * scale)))
    assert (image.width <= 640) and (image.height <= 400)
    rbyte_image_width = (image.width + 7) // 8
    rbyte_image_height = (image.height + 1) // 2
    byts = struct.pack("<HH", rbyte_image_width, rbyte_image_height)
    opt_byts = byts
    for color_channel in (2, 0, 1):
        frame = []
        for y in range(rbyte_image_height):
            row = b""
            for x in range(rbyte_image_width):
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
                        if int(stipple[::-1], 2) & (1 << ((i + 8 * x) % len(stipple)))
                        else 0
                    )
                    b <<= 1
                    b |= pix
                row += bytes([b])
            frame.append(b"\x00" + row)  # CMD_LITERAL_PIXEL_LINE
        byts += b"".join(frame)
        opt_byts += b"".join(opt_frame(frame, opt_level))
    if byts != opt_byts:
        print(
            dict(
                compressed_savings_percent=round(
                    100 * (len(byts) - len(opt_byts)) / len(byts)
                )
            )
        )
    return opt_byts


def encode_bload(*, start_address, data):
    return struct.pack("<HH", start_address, start_address + len(data)) + data


def main():
    try:
        try:
            _, opt_, level_, image_file_name = sys.argv
            assert opt_ == "-O"
            opt_level = opt_ + level_
        except:
            _, opt_level, image_file_name = sys.argv
        assert opt_level.startswith("-O")
    except:
        opt_level = "-O9"
        _, image_file_name = (
            sys.argv
        )  # usage: python rbyte_enc.py [ -OOPTLEVEL ] INPUT.PNG
    opt_level = int(  # -O9 is the default; -O0 through -O32 are meaningful
        opt_level[len("-O") :]
    )
    assert opt_level >= 0  # -O0 is the minimum, -O32 is the maximum useful value
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
        f"{os.path.splitext(os.path.basename(image_file_name))[0]}_rbyte.bin"
    )
    if os.path.lexists(output_file_name):
        os.remove(output_file_name)
        print(
            "removed previous %(output_file_name)s"
            % dict(output_file_name=output_file_name)
        )
    rbyte_data = encode_rbyte(image=rgb_image, opt_level=opt_level)
    output_bytes = encode_bload(start_address=0x1000, data=rbyte_data)
    open(output_file_name, "wb").write(output_bytes)
    print(f"saved {output_file_name}")


if __name__ == "__main__":
    main()
