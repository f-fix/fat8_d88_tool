#!/usr/bin/env python3
#
# mkrom - build Warrior's cartridge/mkII/mkIII paged ROM images for games converted from NONTAMA loader
#
# The loader on tape XOR's the game as it reads it into RAM, so use nontama_to_bload.py to convert from P6/P6T to BLOAD format. The expected filename is something like `GAME_0103_5327_0103.bin`. By default all such files in the current directory will be processed. The generated ROM will be `GAME_warrior.rom` or so.

import fnmatch
import glob
import os
import re
import struct
import sys

Z80 = dict(  # just enough Z80 opcodes to make a loader and trampoline
    LD_A_immed=lambda immed8: struct.pack("BB", 0x3E, immed8),
    OUT_immed_A=lambda immed8: struct.pack("BB", 0xD3, immed8),
    LD_A_mem=lambda addr16: struct.pack("<BH", 0x3A, addr16),
    AND_immed=lambda immed8: struct.pack("BB", 0xE6, immed8),
    OR_immed=lambda immed8: struct.pack("BB", 0xF6, immed8),
    LD_mem_A=lambda addr16: struct.pack("<BH", 0x32, addr16),
    NOP=lambda: b"\x00",
    XOR_A=lambda: b"\xaf",
    LD_B_H=lambda: b"\x44",
    LD_C_L=lambda: b"\x4d",
    JP_HL=lambda: b"\xe9",
    JP_addr=lambda addr16: struct.pack("<BH", 0xC3, addr16),
    JR_index=lambda index8: struct.pack("BB", 0x18, index8),
    LD_DE_mem=lambda addr16: struct.pack("<BBH", 0xED, 0x5B, addr16),
    LD_HL_mem=lambda addr16: struct.pack("<BH", 0x2A, addr16),
    LD_HL_immed=lambda immed16: struct.pack("<BH", 0x21, immed16),
    SBC_HL_DE=lambda: struct.pack("BB", 0xED, 0x52),
    LDIR=lambda: struct.pack("BB", 0xED, 0xB0),
)


def n60_rom_header(rom_entry_point):
    return b"AB" + struct.pack("<H", rom_entry_point)


PAGE_LOADER_SIZE = 0x47
ROM_START_ADDR = 0x4000
FAKE_BLOAD_MAGIC = b"\xfe"  # magic byte used for BLOAD data on FAT12/16/etc.
PAGE_LOADER_CONTINUATION_ENTRY_POINT = ROM_START_ADDR + 0x38

BELUGA_BANK_C_SWITCH_PORT = 0x70
WARRIOR_MK2_BANK_C_SWITCH_PORT = 0x32


def fake_bload_header(load_start_addr, load_stop_addr, entry_point):
    # resembles BLOAD header on FAT12/16/etc.
    return FAKE_BLOAD_MAGIC + struct.pack(
        "<HHH", load_start_addr, load_stop_addr, entry_point
    )


def page_loader(page_load_start_addr, page_load_stop_addr, page_entry_point, next_page):
    rom_entry_point = ROM_START_ADDR + 0x0010
    payload_start_addr = ROM_START_ADDR + PAGE_LOADER_SIZE  # 0x4047
    page_load_start_addr_storage_addr = payload_start_addr - 6  # 0x4041
    page_load_stop_addr_storage_addr = payload_start_addr - 4  # 0x4043
    page_entry_point_storage_addr = payload_start_addr - 2  # 0x4045
    header = n60_rom_header(rom_entry_point)
    loader = (
        header
        + 18 * Z80["NOP"]()
        + Z80["LD_A_mem"](0xF3E0)  # MSX VDP register 1 shadow (no effect on PC-6001)
        + Z80["AND_immed"](0xFC)
        + Z80["OR_immed"](0x02)
        + Z80["LD_mem_A"](0xF3E0)  # MSX VDP register 1 shadow (no effect on PC-6001)
        + 3 * Z80["NOP"]()
        + Z80["LD_DE_mem"](page_load_start_addr_storage_addr)
        + Z80["XOR_A"]()
        + Z80["LD_HL_mem"](page_load_stop_addr_storage_addr)
        + Z80["SBC_HL_DE"]()
        + Z80["LD_B_H"]()
        + Z80["LD_C_L"]()
        + Z80["LD_HL_immed"](payload_start_addr)
        + Z80["LDIR"]()
        + Z80["LD_HL_mem"](page_entry_point_storage_addr)
        + Z80["JP_HL"]()
        + Z80["LD_A_immed"](next_page)
        + Z80["OUT_immed_A"](BELUGA_BANK_C_SWITCH_PORT)
        + Z80["OUT_immed_A"](WARRIOR_MK2_BANK_C_SWITCH_PORT)
    )
    loader += Z80["JR_index"](
        0x100 - (len(Z80["JR_index"](0x00)) + len(loader[len(header) :]))
    ) + fake_bload_header(  # jr 0x4004
        page_load_start_addr, page_load_stop_addr, page_entry_point
    )
    assert len(loader) == PAGE_LOADER_SIZE
    return loader


ROM_PAGE_SIZE = 0x2000
TRAMPOLINE_START_ADDR = 0xC800
PC6001_MK2_BANK_SWITCH_REGISTER_0_PORT = 0xF0


def mkrom(*, payload, load_start_addr, load_stop_addr, entry_point):
    block_size = ROM_PAGE_SIZE - len(page_loader(0, 0, 0, 1))
    data_addr = load_start_addr
    next_page = 1
    trampoline = (
        Z80["LD_A_immed"](0xDD)  # PC-6001 mkII internal RAM for all 64K
        + Z80["OUT_immed_A"](PC6001_MK2_BANK_SWITCH_REGISTER_0_PORT)
        + Z80["JP_addr"](entry_point)
        + 9 * Z80["NOP"]()
    )
    rom = page_loader(
        TRAMPOLINE_START_ADDR,
        TRAMPOLINE_START_ADDR + len(trampoline),
        PAGE_LOADER_CONTINUATION_ENTRY_POINT,
        next_page,
    )
    rom += trampoline
    rom += b"\x00" * (block_size - len(trampoline))
    while (data_addr - load_start_addr) < len(payload):
        block_entry_point = TRAMPOLINE_START_ADDR
        data_length = len(payload) - (data_addr - load_start_addr)
        if data_length > block_size:
            block_entry_point = PAGE_LOADER_CONTINUATION_ENTRY_POINT
            data_length = block_size
        pad_length = block_size - data_length
        next_page += 1
        rom += page_loader(
            data_addr, data_addr + data_length, block_entry_point, next_page
        )
        rom += payload[data_addr - load_start_addr :][:data_length]
        rom += b"\x00" * pad_length
        data_addr += data_length
    return rom


NONTAMA_BLOAD_FILE_NAME_PATTERN = "*_[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]_[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]_[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F].[Bb][Ii][In]"
NONTAMA_BLOAD_FILE_NAME_PATTERN_DESCRIPTION = "'*_XXXX_YYYY_ZZZZ.bin' where XXXX is hexadecimal load start address, YYYY is hexadecimal load stop address, and ZZZZ is hexadecimal entry point"


def main():
    _, *input_file_paths = sys.argv
    if not input_file_paths:
        input_file_paths = glob.glob(NONTAMA_BLOAD_FILE_NAME_PATTERN)
    assert (
        input_file_paths
    ), f"Did not find any files in the current working directory named according to nontama_to_bload conventions: {NONTAMA_BLOAD_FILE_NAME_PATTERN_DESCRIPTION}"
    name_pattern_re = re.compile(fnmatch.translate(NONTAMA_BLOAD_FILE_NAME_PATTERN))
    for input_file_path in input_file_paths:
        assert os.path.exists(
            input_file_path
        ), f"{input_file_path}: input file does not exist"
        input_file_name = os.path.basename(input_file_path)
        assert name_pattern_re.match(
            input_file_name
        ), f"{input_file_name}: input file must be named according to nontama_to_bload conventions: {NONTAMA_BLOAD_FILE_NAME_PATTERN_DESCRIPTION}"
        warrior_rom_file_name = (
            "_".join(os.path.splitext(input_file_name)[0].split("_")[:-3])
            + "_warrior.rom"
        )
        if os.path.exists(warrior_rom_file_name):
            os.remove(warrior_rom_file_name)
            print(f"Removed old {warrior_rom_file_name}")
        load_start_addr, load_stop_addr, entry_point = (
            int(hexaddr, 16)
            for hexaddr in os.path.splitext(input_file_name)[0].split("_")[-3:]
        )
        assert load_start_addr < load_stop_addr
        expected_length = 4 + (load_stop_addr - load_start_addr)
        bload_data = open(input_file_path, "rb").read()
        assert (
            len(bload_data) == expected_length
        ), f"{input_file_path}: wrong length, expected 0x{expected_length:04X} from filename but got 0x{len(bload_data):04X}"
        assert struct.unpack("<HH", bload_data[:4]) == (
            load_start_addr,
            load_stop_addr,
        ), f"{input_file_path}: filename suffix and BLOAD header do not match"
        payload = bload_data[4:]
        warrior_rom = mkrom(
            payload=payload,
            load_start_addr=load_start_addr,
            load_stop_addr=load_stop_addr,
            entry_point=entry_point,
        )
        open(warrior_rom_file_name, "wb").write(warrior_rom)
        print(f"generated {warrior_rom_file_name}")


if __name__ == "__main__":
    main()
