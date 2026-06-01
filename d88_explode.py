#!/usr/bin/env python3

import argparse
import os.path
import sys
import unicodedata
from typing import Callable, Dict, List, NamedTuple, Optional, Set

TRACK_TABLE_OFFSET = 0x20
TRACK_ENTRY_SIZE = 4
SECTOR_HEADER_SIZE = 16

DISK_ATTR_WRITE_PROTECTED = "DiskWriteProtected"


class DiskInfo(NamedTuple):
    disk_name_or_comment: Optional[bytes]
    disk_attrs: Set[str]
    disk_sz: int
    track_offsets: List[int]
    disk_suffix: str


def make_disk_info(**kw) -> DiskInfo:
    return DiskInfo(**kw)


def analyze_disk(*, d88_data: bytes, disk_idx: int):
    disk_name_or_comment = d88_data[:0x10].rstrip(b"\0") or None
    disk_attrs = {DISK_ATTR_WRITE_PROTECTED} if d88_data[0x1A] & 0x10 else set()
    disk_sz = int.from_bytes(d88_data[0x1C:0x20], "little")
    assert disk_sz <= len(
        d88_data
    ), f"Is this a D88 file? The disk size field is too large"
    assert (
        disk_sz > TRACK_TABLE_OFFSET + TRACK_ENTRY_SIZE
    ), f"Is this a D88 file? The disk size field is too small"
    track_offsets: List[int] = []
    i = 0
    while True:
        if i > 0 and (TRACK_TABLE_OFFSET + TRACK_ENTRY_SIZE * i) >= min(track_offsets):
            break
        offset = int.from_bytes(
            d88_data[
                TRACK_TABLE_OFFSET
                + i * TRACK_ENTRY_SIZE : TRACK_TABLE_OFFSET
                + (i + 1) * TRACK_ENTRY_SIZE
            ],
            "little",
        )
        if i == 0:
            assert (
                offset - TRACK_TABLE_OFFSET
            ) % TRACK_ENTRY_SIZE == 0, (
                "Offset of first track must be a multiple of {TRACK_ENTRY_SIZE}"
            )
        if offset not in (0, disk_sz):
            track_offsets += [offset]
            assert offset >= min(
                track_offsets
            ), f"Offset {offset} for track {i:3} is smaller than offset for first track"
            assert (
                offset + SECTOR_HEADER_SIZE < disk_sz
            ), f"Is this a D88 file? Track data spills over past the end"
        i += 1
    return make_disk_info(
        disk_name_or_comment=disk_name_or_comment,
        disk_attrs=disk_attrs,
        disk_sz=disk_sz,
        track_offsets=track_offsets,
        disk_suffix=(
            ""
            if disk_idx == 1 and len(d88_data) == disk_sz
            else f" [Disk {disk_idx:02}]"
        ),
    )


class Logger(NamedTuple):
    append: Callable[[str], None]
    contents: Callable[[], List[str]]


def start_log() -> Logger:
    output = []

    def append(s: str):
        output.append(s)
        print(s)

    def contents() -> List[str]:
        return output

    return Logger(append=append, contents=contents)


def log_disk_information(*, disk_info: DiskInfo, logger: Logger):
    logger.append(f"\n== Disk Information{disk_info.disk_suffix} ==")
    logger.append(f"Disk name/comment: {repr(disk_info.disk_name_or_comment)}")
    logger.append(f"Disk attributes: {', '.join(sorted(disk_info.disk_attrs)) or None}")
    logger.append(f"Disk size: {disk_info.disk_sz}")


class TrackAndSide(NamedTuple):
    track: int
    side: int


def make_track_and_side(**kw) -> TrackAndSide:
    return TrackAndSide(**kw)


class SectorInfo(NamedTuple):
    sec_num: int
    actual_data_offset: int
    sector_data: bytes
    sectors_in_track: int
    sector_header: bytes


def make_sector_info(**kw) -> SectorInfo:
    return SectorInfo(**kw)


class TrackAndSectorInfo(NamedTuple):
    track_sector_map: Dict[TrackAndSide, List[SectorInfo]]
    nominal_sectors_in_track: Dict[TrackAndSide, int]
    found_tracks: int
    found_sides: int
    found_total_sectors: int
    found_sectors: int
    found_disk_size: int
    largest_sector_size: int


def make_track_and_sector_info(**kw) -> TrackAndSectorInfo:
    return TrackAndSectorInfo(**kw)


def analyze_tracks_and_sectors(*, d88_data: bytes, disk_info: DiskInfo, logger: Logger):
    logger.append("\n== Track/Sector Table ==")
    track_sector_map: Dict[TrackAndSide, List[SectorInfo]] = {}

    all_sector_ranges = []
    nominal_sectors_in_track: Dict[TrackAndSide, int] = {}
    for track_offset in disk_info.track_offsets:
        sectors: List[SectorInfo] = []
        cursor = track_offset
        track_num, side_num = None, None
        while cursor + SECTOR_HEADER_SIZE <= disk_info.disk_sz:
            header = d88_data[cursor : cursor + SECTOR_HEADER_SIZE]
            trk = header[0]
            if track_num is None:
                track_num = trk
            if track_num != trk:
                break
            side = header[1]
            if side_num is None:
                side_num = side
            if side_num != side:
                break
            sec_num = header[2]
            sec_size_code = header[3]
            nominal_data_size = 128 << sec_size_code
            sectors_in_track = int.from_bytes(header[0x04:0x06], "little")
            actual_data_offset = cursor + SECTOR_HEADER_SIZE
            if False:
                # FIXME: apparently this field is often wrong; need to
                # figure out how to detect that and use it when it is
                # correct (it would allow custom sector sizes and empty
                # sectors)
                sector_data_size = int.from_bytes(header[0x0E:], "little")
            else:
                sector_data_size = nominal_data_size
            assert (
                actual_data_offset + sector_data_size <= disk_info.disk_sz
            ), "Is this a D88 file? Sector data spilled off the end"
            for other_sector in sectors:
                assert (
                    other_sector.sec_num != sec_num
                ), f"Is this a D88 file? Track {trk:3}, Side {side}, Sector {sec_num:2} appears more than once"
            sectors.append(
                make_sector_info(
                    sec_num=sec_num,
                    actual_data_offset=actual_data_offset,
                    sector_data=d88_data[
                        actual_data_offset : actual_data_offset + sector_data_size
                    ],
                    sectors_in_track=sectors_in_track,
                    sector_header=header,
                )
            )
            nominal_sectors_in_track[make_track_and_side(track=trk, side=side)] = (
                nominal_sectors_in_track.get(
                    make_track_and_side(track=trk, side=side), sectors_in_track
                )
            )
            assert (
                nominal_sectors_in_track[make_track_and_side(track=trk, side=side)]
                == sectors_in_track
            ), f"Is this a damaged disk? Sectors-per-track varies in Track {trk:3}, Side {side}: {nominal_sectors_in_track[make_track_and_side(track=trk, side=side)]} vs {sectors_in_track}"
            all_sector_ranges.append(
                [actual_data_offset, actual_data_offset + sector_data_size]
            )
            cursor += SECTOR_HEADER_SIZE + sector_data_size
        key = make_track_and_side(track=track_num, side=side_num)
        track_sector_map[key] = sectors
        logger.append(
            f"Track {track_num:3}, Side {side_num}: "
            + ", ".join(f"{s.sec_num:2}:{len(s.sector_data)}" for s in sectors)
        )

    overlap_check_offset = 0
    for start_offset, next_offset in sorted(all_sector_ranges):
        assert (
            start_offset >= overlap_check_offset
        ), "Is this a D88 file? Found overlapping sector data"
        overlap_check_offset = next_offset

    found_tracks = 0
    found_sides = 1
    found_total_sectors = 0
    found_sectors = 0
    found_disk_size = 0
    largest_sector_size = 0

    for track_and_side, sectors in track_sector_map.items():
        found_tracks = max(found_tracks, 1 + track_and_side.track)
        found_sides = max(found_sides, 1 + track_and_side.side)
        for sector_info in sectors:
            found_total_sectors += 1
            found_disk_size += len(sector_info.sector_data)
            largest_sector_size = max(largest_sector_size, len(sector_info.sector_data))
            found_sectors = max(found_sectors, sector_info.sec_num)

    return make_track_and_sector_info(
        track_sector_map=track_sector_map,
        nominal_sectors_in_track=nominal_sectors_in_track,
        found_tracks=found_tracks,
        found_sides=found_sides,
        found_total_sectors=found_total_sectors,
        found_sectors=found_sectors,
        found_disk_size=found_disk_size,
        largest_sector_size=largest_sector_size,
    )


def save_log(*, outdir, logger: Logger):
    log_filename = os.path.join(outdir, "_d88_explode_output.txt")
    with open(log_filename, "w", encoding="utf-8") as f:
        print(f"writing {log_filename}")
        f.write("\n".join(logger.contents()))


def extract_everything(
    *,
    disk_info: DiskInfo,
    d88_path: str,
    d88_data: bytes,
    track_and_sector_info: TrackAndSectorInfo,
    error_count: int,
    logger: Logger,
):
    outdir = (
        os.path.splitext(os.path.basename(d88_path))[0]
        + " [D88 Contents]"
        + f"{disk_info.disk_suffix}"
    )

    disambig = ""
    while os.path.exists(outdir + disambig):
        disambig = f" ({1 + int(disambig.strip(' ()') or 0)})"
    outdir += disambig

    print("\n== Extracting ==")
    print(f"mkdir {outdir}")
    os.mkdir(outdir)
    open(os.path.join(outdir, "diskname.bin"), "wb").write(d88_data[:0x10])
    open(os.path.join(outdir, "diskprotectionflag.bin"), "wb").write(d88_data[0x1A:0x1B])
    open(os.path.join(outdir, "mediaflag.bin"), "wb").write(d88_data[0x1B:0x1C])
    for track_and_side, sectors in track_and_sector_info.track_sector_map.items():
        track_and_side_dirname = os.path.join(outdir, f"track{track_and_side.track:02d}_side{track_and_side.side:d}")
        os.mkdir(track_and_side_dirname)
        for sector_index, sector in enumerate(sectors):
            sector_basename = os.path.join(track_and_side_dirname, f"slice{sector_index:02d}_sector{sector.sec_num:02d}")
            print(sector_basename)
            open(sector_basename + ".hdr", "wb").write(sector.sector_header[3:])
            open(sector_basename + ".dat", "wb").write(sector.sector_data)
        print(track_and_side_dirname)
    save_log(outdir=outdir, logger=logger)

def d88_explode(*, d88_path: str, d88_data: bytes, disk_idx: int = 1) -> int:
    error_count = 0
    logger = start_log()
    disk_info = analyze_disk(d88_data=d88_data, disk_idx=disk_idx)
    print(f"Processing disk{disk_info.disk_suffix}.")
    log_disk_information(disk_info=disk_info, logger=logger)
    track_and_sector_info = analyze_tracks_and_sectors(
        d88_data=d88_data, disk_info=disk_info, logger=logger
    )
    logger.append(f"\nDisk error count{disk_info.disk_suffix}: {error_count} error(s)")
    extract_everything(
        disk_info=disk_info,
        d88_path=d88_path,
        d88_data=d88_data,
        track_and_sector_info=track_and_sector_info,
        error_count=error_count,
        logger=logger,
    )
    print(f"\nFinished processing disk{disk_info.disk_suffix}: {error_count} error(s)")
    if len(d88_data) > disk_info.disk_sz:
        error_count += d88_explode(
            d88_path=d88_path,
            d88_data=d88_data[disk_info.disk_sz :],
            disk_idx=disk_idx + 1,
        )
    return error_count


def main():
    parser = argparse.ArgumentParser(
        prog="d88_explode.py",
        description="D88 disk image exploder",
    )

    # D88 files for disk image extraction
    parser.add_argument(
        "d88_files",
        nargs="*",
        help="D88 disk image files to process (use '-' for stdin)",
    )

    args = parser.parse_args()

    if not args.d88_files:
        parser.print_help()
        print(
            "Each D88 file processed will have an output directory created in the current directory whose name ends with `DISK [D88 Contents]`. The D88 filename `-` by itself indicates stdin, and in this case output will go to a directory named starting with `stdin [D88 Contents]`. A D88 file containing multiple disk images will have a suffix like ` [Disk 01]` appended to the directory name for each disk image, where 01 will be replaced by the index of the disk image within the D88 file. Processing errors result in a suffix like ` [Error Count 03]` appended to the directory name for the disk image, where 03 will be replaced by the number of processing errors."
        )
        print("")
        print(
            "If an intended output directory name already exists, a suffix like ` (2)` will be added, where 2 is a number from 2 onward that is large enough to avoid existing names."
        )
        print("")
        print(
            "If an output file within the created output directory with the same intended name (compared case-insensitively) is already going to be created, a suffix like ` (2)` will be added before the file extension, where 2 is replaced by a number from 2 onward that is large enough to avoid existing files."
        )
        print("")
        print(
            "A log file for each disk image will be written to stdout and also to a file `_d88_explode_output.txt` inside the created directory."
        )
        sys.exit(1)

    # Process D88 files
    total_error_count = 0
    print(f"Processing {len(args.d88_files)} D88 file(s).")
    for d88_path in args.d88_files:
        with sys.stdin.buffer if d88_path == "-" else open(d88_path, "rb") as f:
            d88_data = f.read()
            if d88_path == "-":
                d88_path = "stdin"
            print(f"Processing D88 file {d88_path}.")
            try:
                error_count = d88_explode(d88_path=d88_path, d88_data=d88_data)
                print(
                    f"Finished processing D88 file {d88_path}: {error_count} error(s)."
                )
            except Exception as ex:
                error_count = 1
                print(f"Uncaught exception while processing D88 file {d88_path}: {ex}.")
            total_error_count += error_count
    print(f"Finished processing all D88 files: {total_error_count} error(s).")
    if total_error_count:
        sys.exit(1)


if __name__ == "__main__":
    main()
