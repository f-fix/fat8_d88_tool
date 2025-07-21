#!/usr/bin/env python3

from pathlib import Path

import codecs
import os.path
import sys
import unicodedata

# FAT8 formatting schemes

KNOWN_FAT8_FMTS = {
    'PC-9800 3.5" 2DD/5.25" 2DD': dict(
        # from PC-9801UV21 BASIC User's Manual
        tracks=80,
        fat_tracks=80,
        sides=2,
        sectors=16,
        sector1_start_hints={},
        charset="pc98-8bit",
        obfuscation="pc98",
        metadata_track=40,
        metadata_side=0,
        clusters_per_track=1,
        side_is_cluster_lsb=False,
    ),
    'PC-9800 8" 2D/3.5" 2HD/5.25" 2HD': dict(
        # from PC-9801UV21 BASIC User's Manual
        tracks=77,
        fat_tracks=77,
        sides=2,
        sectors=26,
        sector1_start_hints={
            lambda sector1: len(sector1) == 128,
        },
        charset="pc98-8bit",
        obfuscation="pc98",
        metadata_track=35,
        metadata_side=0,
        clusters_per_track=1,
        side_is_cluster_lsb=False,
    ),
    'PC-9800 8" 2D/3.5" 2HD/5.25" 2HD (wild type, 78 tracks)': dict(
        # seen in the wild
        tracks=78,
        fat_tracks=77,
        sides=2,
        sectors=26,
        sector1_start_hints={
            lambda sector1: len(sector1) == 128,
        },
        charset="pc98-8bit",
        obfuscation="pc98",
        metadata_track=35,
        metadata_side=0,
        clusters_per_track=1,
        side_is_cluster_lsb=False,
    ),
    'PC-8000/PC-8800 5.25" 1D': dict(
        # from PC-8801 mkII BASIC User's Manual
        #      PC-8001 mkII SR N80SR-BASIC Reference Manual
        #      PC-8001 N-BASIC Programming Textbook
        tracks=35,
        fat_tracks=35,
        sides=1,
        sectors=16,
        sector1_start_hints={},
        charset="pc98-8bit",
        obfuscation="pc88",
        metadata_track=18,
        metadata_side=0,
        clusters_per_track=2,
        side_is_cluster_lsb=False,
    ),
    'PC-8000/PC-8800 5.25" 2D': dict(
        # from PC-8801 mkII MR N88-BASIC / N88-Japanese BASIC Guide Book
        #      PC-8801 mkII BASIC User's Manual
        #      PC-8001 mkII SR N80SR-BASIC Reference Manual
        tracks=40,
        fat_tracks=40,
        sides=2,
        sectors=16,
        sector1_start_hints={},
        charset="pc98-8bit",
        obfuscation="pc88",
        metadata_track=18,
        metadata_side=1,
        clusters_per_track=2,
        side_is_cluster_lsb=False,
    ),
    'PC-8801 mkII 8" 2D/5.25" 2HD': dict(
        # from PC-8801 mkII MR N88-BASIC / N88-Japanese BASIC Guide Book
        #      PC-8801 mkII BASIC User's Manual
        #      PC-8001 mkII SR N80SR-BASIC Reference Manual
        tracks=77,
        fat_tracks=77,
        sides=2,
        sectors=26,
        sector1_start_hints={
            lambda sector1: len(sector1) != 128,
        },
        charset="pc98-8bit",
        obfuscation="pc88",
        metadata_track=35,
        metadata_side=0,
        clusters_per_track=1,
        side_is_cluster_lsb=False,
    ),
    'PC-6001 mkII 5.25" 1D': dict(
        # from PC 6001mk II User Manual
        tracks=35,
        fat_tracks=35,
        sides=1,
        sectors=16,
        sector1_start_hints={
            lambda sector1: sector1.startswith(b"SYS"),
        },
        charset="pc6001-8bit",
        obfuscation=None,
        metadata_track=18,
        metadata_side=0,
        clusters_per_track=2,
        side_is_cluster_lsb=False,
    ),
    'PC-6001 mkII 5.25" 1D (wild type, 36 tracks)': dict(
        # seen in the wild
        tracks=36,
        fat_tracks=35,
        sides=1,
        sectors=16,
        sector1_start_hints={
            lambda sector1: sector1.startswith(b"SYS"),
        },
        charset="pc6001-8bit",
        obfuscation=None,
        metadata_track=18,
        metadata_side=0,
        clusters_per_track=2,
        side_is_cluster_lsb=False,
    ),
    'PC-6601 3.5" 1D (wild type)': dict(
        # seen in the wild
        tracks=40,
        fat_tracks=40,
        sides=1,
        sectors=16,
        sector1_start_hints={
            lambda sector1: sector1.startswith(b"SYS"),
        },
        charset="pc6001-8bit",
        obfuscation=None,
        metadata_track=18,
        metadata_side=0,
        clusters_per_track=2,
        side_is_cluster_lsb=False,
    ),
    'PC-6601 SR 3.5" 1DD (wild type)': dict(
        # seen in the wild
        tracks=80,
        fat_tracks=80,
        sides=1,
        sectors=16,
        sector1_start_hints={
            lambda sector1: sector1.startswith(b"IPL"),
            lambda sector1: sector1.startswith(b"RXR"),
        },
        charset="pc6001-8bit",
        obfuscation=None,
        metadata_track=37,
        metadata_side=0,
        clusters_per_track=2,
        side_is_cluster_lsb=False,
    ),
    'PC-6601 SR 3.5" 1DD (wild type, 81 tracks)': dict(
        # seen in the wild
        tracks=81,
        fat_tracks=80,
        sides=1,
        sectors=16,
        sector1_start_hints={
            lambda sector1: sector1.startswith(b"IPL"),
            lambda sector1: sector1.startswith(b"RXR"),
        },
        charset="pc6001-8bit",
        obfuscation=None,
        metadata_track=37,
        metadata_side=0,
        clusters_per_track=2,
        side_is_cluster_lsb=False,
    ),
    'Pasopia 5.25" 2D (wild type)': dict(
        # seen in the wild
        tracks=40,
        fat_tracks=40,
        sides=2,
        sectors=16,
        sector1_start_hints={
            lambda sector1: sector1.startswith(b"\0\0\0\0"),
        },
        charset="pc98-8bit",
        obfuscation=None,
        metadata_track=18,
        metadata_side=0,
        clusters_per_track=2,
        side_is_cluster_lsb=True,
    ),
}

# 8-bit/single-byte character encoding schemes

NO_CONTROLS = b""
MINIMAL_CONTROLS = b"\0\r\n\x1a\x7f"
ASCII_CONTROLS = bytes([i for i in range(0x20)] + [0x7F])

# i am sure this is not the best way to solve this. this mapping
# should work OK for PC-8001 series, PC-8801 series, and PC-98/PC-9821
# series and compatibles when displaying an 8-bit character set with
# no kanji support. once a kanji ROM gets involved the problem gets a
# whole lot trickier since these "narrow" single-byte characters map
# to the same Unicode as those double-byte (but sometimes
# single-width!)  ones. in some cases those are visually distinct, in
# other cases not. in any case, there will be ambiguity or other
# escaping mechanisms will be needed. characters from the private use
# area are used to handle various unassigned or ambiguous mappings. i
# considered '\N{no-break space}' for b'\xA0' but it seems
# semantically wrong. the kanji here are supposed to be halfwidth but
# unicode lacks a way to express that.
PC98_8BIT_CHARSET = (
    "␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬"
    " !\"#$%&'()*+,-./0123456789:;<=>?"
    "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[¥]^_"
    "`abcdefghijklmnopqrstuvwxyz{¦}~␡"
    "▁▂▃▄▅▆▇█▏▎▍▌▋▊▉┼┴┬┤├▔─│▕┌┐└┘╭╮╰╯"
    "\uf8f0｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ"
    "ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ"
    "═╞╪╡◢◣◥◤♠♥♦♣•￮╱╲╳円年月日時分秒\uf8f4\uf8f5\uf8f6\uf8f7\N{REVERSE SOLIDUS}\uf8f1\uf8f2\uf8f3"
)
assert len(PC98_8BIT_CHARSET) == 256
PC98_8BIT_CHARMAP = {PC98_8BIT_CHARSET[i]: bytes([i]) for i in range(256)}
PC98_8BIT_CHARMAP_COMPAT = {
    unicodedata.normalize("NFKD", key): value
    for key, value in PC98_8BIT_CHARMAP.items()
    if unicodedata.normalize("NFKD", key) != key
}


def encode_pc98_8bit_charset(s, try_harder=True):
    s = "".join(
        [
            (
                unicodedata.normalize("NFKD", s[i : i + 1])
                if unicodedata.name(s[i : i + 1], "?")
                .lower()
                .startswith("katakana letter")
                else s[i : i + 1]
            )
            for i in range(len(s))
        ]
    )
    byts, chars_consumed, num_chars = b"", 0, len(s)
    while chars_consumed < num_chars:
        ch = s[chars_consumed]
        byt = PC98_8BIT_CHARMAP.get(ch, PC98_8BIT_CHARMAP_COMPAT.get(ch)) or (
            bytes([ord(ch)]) if ord(ch) <= 0x7F else None
        )
        if byt is None and try_harder:
            cch = unicodedata.normalize("NFKD", ch)
            byt = PC98_8BIT_CHARMAP.get(cch, PC98_8BIT_CHARMAP_COMPAT.get(cch)) or (
                bytes([ord(cch)]) if ord(cch) <= 0x7F else None
            )
        if byt is None:
            raise UnicodeEncodeError(
                "pc98-8bit",
                s,
                chars_consumed,
                chars_consumed + 1,
                f"no mapping for U+{ord(ch):04X} {unicodedata.name(ch, repr(ch))}",
            )
        byts += byt
        chars_consumed += 1
    return byts


def decode_pc98_8bit_charset(byts, preserve=MINIMAL_CONTROLS):
    s, bytes_consumed, num_bytes = "", 0, len(byts)
    while bytes_consumed < num_bytes:
        byt = byts[bytes_consumed]
        s += chr(byt) if byt in preserve else PC98_8BIT_CHARSET[byt]
        bytes_consumed += 1
    round_trip_byts = encode_pc98_8bit_charset(s)
    assert byts == round_trip_byts, UnicodeDecodeError(
        "pc98-8bit",
        byts,
        0,
        num_bytes,
        f"round-trip failure for result:\n {repr(byts)}, got:\n {repr(round_trip_byts)}",
    )
    return s


def smoke_test_pc98_8bit_charset():
    assert decode_pc98_8bit_charset(b"") == ""
    assert encode_pc98_8bit_charset("") == b""
    round_trip_test_failures = {
        encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i]))): bytes([i])
        for i in range(256)
        if encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i]))) != bytes([i])
    }
    round_trip_test_failures |= {
        encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEE]))): bytes(
            [i, 0xEE]
        )
        for i in range(256)
        if encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEE])))
        != bytes([i, 0xEE])
    }
    round_trip_test_failures |= {
        encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEF]))): bytes(
            [i, 0xEF]
        )
        for i in range(256)
        if encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEF])))
        != bytes([i, 0xEF])
    }
    assert not round_trip_test_failures, round_trip_test_failures
    unicode_test = (
        "\r\n".join(
            (
                "╲￮╱ I ♥ PC98! \\o/",
                "キュウハチガダイスキデス!",
                "NECノ「PC-8800」ヤ「PC-9800」シリーズ ノ パソコン ガ ニンキデシタガ、ゴゾンジデスカ？",
                "「！？」　･･･",
                "│|¦~▔-ｰ─_▁",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭￪╮ ++-+  /\\ ",
                "├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ ￩┼￫ ++-+ /XX\\",
                "││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰￬╯ ¦|.¦ \\XX/",
                "└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ",
                "▊▋▌▍▎▏█▇▆▅▄▃▂",
                "␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡",
            )
        )
        + "\x1a\x00"
    )
    expected_8bit = (
        b"\r\n".join(
            (
                b"\xef\xed\xee I \xe9 PC98! \xfco/",
                b"\xb7\xad\xb3\xca\xc1\xb6\xde\xc0\xde\xb2\xbd\xb7\xc3\xde\xbd!",
                b"NEC\xc9\xa2PC-8800\xa3\xd4\xa2PC-9800\xa3\xbc\xd8\xb0\xbd\xde \xc9 \xca\xdf\xbf\xba\xdd \xb6\xde \xc6\xdd\xb7\xc3\xde\xbc\xc0\xb6\xde\xa4\xba\xde\xbf\xde\xdd\xbc\xde\xc3\xde\xbd\xb6?",
                b"\xa2!?\xa3 \xa5\xa5\xa5",
                b"\x96||~\x94-\xb0\x95_\x80",
                b"\\0=0\xf1",
                b"2025\xf207\xf318\xf4 14\xf511\xf616\xf7",
                b"\x98\x91\x95\x99\x9c\x91\x95\x9d \x80\x80  \xee\xef  \xe4\xe5  \x9c\x1e\x9d ++-+  /\xfc ",
                b"\x93\x8f\x95\x92\xe1\xe2\xe0\xe3\x97\x8f\x95\x88\xee\xf0\xf0\xef\xe4\xe7\xe6\xe5 \x1d\x8f\x1c ++-+ /XX\xfc",
                b"\x96\x96\x8e\x96\x96\x96\xec\x96\x97\x96\xa5\x88\xef\xf0\xf0\xee\xe6\xe5\xe4\xe7 \x9e\x1f\x9f ||.| \xfcXX/",
                b"\x9a\x90\x95\x9b\x9e\x90\x95\x9f \x94\x94  \xef\xee  \xe6\xe7.<>O[]++-+  \xfc/ ",
                bytes([0x80 + 13 - i for i in range(13)]),
                bytes([i for i in range(0x20)] + [0x7F]),
            )
        )
        + b"\x1a\x00"
    )
    assert (
        encode_pc98_8bit_charset(unicode_test) == expected_8bit
    ), f"encode_pc98_8bit_charset({repr(unicode_test)}) returned:\n {repr(encode_pc98_8bit_charset(unicode_test))}, expecting:\n {repr(expected_8bit)}"
    try:
        unexpected_8bit = encode_pc98_8bit_charset(unicode_test, try_harder=False)
        assert (
            False
        ), f"Expected a UnicodeEncodeError for encode_pc98_8bit_charset({repr(unicode_test)}, try_harder=False) but no error was raised"
    except UnicodeEncodeError:
        pass
    except Exception as e:
        assert (
            False
        ), f"Expected a UnicodeEncodeError for encode_pc98_8bit_charset({repr(unicode_test)}, try_harder=False) but {repr(e)} was raised instead"
    pc98_8bit_test = expected_8bit
    expected_unicode = (
        "\r\n".join(
            (
                "╲￮╱ I ♥ PC98! \\o/",
                "ｷｭｳﾊﾁｶﾞﾀﾞｲｽｷﾃﾞｽ!",
                "NECﾉ｢PC-8800｣ﾔ｢PC-9800｣ｼﾘｰｽﾞ ﾉ ﾊﾟｿｺﾝ ｶﾞ ﾆﾝｷﾃﾞｼﾀｶﾞ､ｺﾞｿﾞﾝｼﾞﾃﾞｽｶ?",
                "｢!?｣ ･･･",
                "│¦¦~▔-ｰ─_▁",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭￪╮ ++-+  /\\ ",
                "├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ ￩┼￫ ++-+ /XX\\",
                "││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰￬╯ ¦¦.¦ \\XX/",
                "└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ",
                "▊▋▌▍▎▏█▇▆▅▄▃▂",
                "\x00␁␂␃␄␅␆␇␈␉\n␋␌\r␎␏␐␑␒␓␔␕␖␗␘␙\x1a␛￫￩￪￬\x7f",
            )
        )
        + "\x1a\x00"
    )
    assert (
        decode_pc98_8bit_charset(pc98_8bit_test) == expected_unicode
    ), f"decode_pc98_8bit_charset({repr(pc98_8bit_test)}) returned:\n {repr(decode_pc98_8bit_charset(pc98_8bit_test))}, expecting:\n {repr(expected_unicode)}"
    assert (
        encode_pc98_8bit_charset(expected_unicode, try_harder=False) == pc98_8bit_test
    ), f"encode_pc98_8bit_charset({repr(expected_unicode)}, try_harder=False) returned:\n {repr(encode_pc98_8bit_charset(expected_unicode, try_harder=False))}, expecting:\n {repr(pc98_8bit_test)}"
    expected_no_controls_unicode = (
        "␍␊".join(
            (
                "╲￮╱ I ♥ PC98! \\o/",
                "ｷｭｳﾊﾁｶﾞﾀﾞｲｽｷﾃﾞｽ!",
                "NECﾉ｢PC-8800｣ﾔ｢PC-9800｣ｼﾘｰｽﾞ ﾉ ﾊﾟｿｺﾝ ｶﾞ ﾆﾝｷﾃﾞｼﾀｶﾞ､ｺﾞｿﾞﾝｼﾞﾃﾞｽｶ?",
                "｢!?｣ ･･･",
                "│¦¦~▔-ｰ─_▁",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭￪╮ ++-+  /\\ ",
                "├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ ￩┼￫ ++-+ /XX\\",
                "││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰￬╯ ¦¦.¦ \\XX/",
                "└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ",
                "▊▋▌▍▎▏█▇▆▅▄▃▂",
                "␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡",
            )
        )
        + "␚␀"
    )
    assert (
        decode_pc98_8bit_charset(pc98_8bit_test, preserve=NO_CONTROLS)
        == expected_no_controls_unicode
    ), f"decode_pc98_8bit_charset({repr(pc98_8bit_test)}, preserve=NO_CONTROLS) returned:\n {repr(decode_pc98_8bit_charset(pc98_8bit_test, preserve=NO_CONTROLS))}, expecting:\n {repr(expected_no_controls_unicode)}"
    expected_ascii_controls_unicode = (
        "\r\n".join(
            (
                "╲￮╱ I ♥ PC98! \\o/",
                "ｷｭｳﾊﾁｶﾞﾀﾞｲｽｷﾃﾞｽ!",
                "NECﾉ｢PC-8800｣ﾔ｢PC-9800｣ｼﾘｰｽﾞ ﾉ ﾊﾟｿｺﾝ ｶﾞ ﾆﾝｷﾃﾞｼﾀｶﾞ､ｺﾞｿﾞﾝｼﾞﾃﾞｽｶ?",
                "｢!?｣ ･･･",
                "│¦¦~▔-ｰ─_▁",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭\x1e╮ ++-+  /\\ ",
                "├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ \x1d┼\x1c ++-+ /XX\\",
                "││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰\x1f╯ ¦¦.¦ \\XX/",
                "└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ",
                "▊▋▌▍▎▏█▇▆▅▄▃▂",
                "".join([chr(i) for i in range(0x20)]) + "\x7f",
            )
        )
        + "\x1a\x00"
    )
    assert (
        decode_pc98_8bit_charset(pc98_8bit_test, preserve=ASCII_CONTROLS)
        == expected_ascii_controls_unicode
    ), f"decode_pc98_8bit_charset({repr(pc98_8bit_test)}, preserve=ASCII_CONTROLS) returned:\n {repr(decode_pc98_8bit_charset(pc98_8bit_test, preserve=ASCII_CONTROLS))}, expecting:\n {repr(expected_ascii_controls_unicode)}"


# i am sure this is not the best way to solve this. this mapping
# should work OK for PC-6001/mkII/SR and PC-6601/SR. it does not
# handle the alternate character set shift sequences well. it also
# does not handle Kanji or PC-6001A charset at all! the mapping is
# intentionally close to the PC-98 one above. the hiragana and kanji
# here should all be half-width ones, but Unicode is missing those so
# we live with fullwidth instead.
PC6001_8BIT_CHARSET = (
    "␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬"
    " !\"#$%&'()*+,-./0123456789:;<=>?"
    "@ABCDEFGHIJKLMNOPQRSTUVWXYZ[¥]^_"
    "`abcdefghijklmnopqrstuvwxyz{¦}~␡"
    "♠♥♦♣￮•をぁぃぅぇぉゃゅょっーあいうえおかきくけこさしすせそ"
    "\uf8f0｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ"
    "ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ"
    "たちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん\uf8f2\uf8f3"
)
assert len(PC6001_8BIT_CHARSET) == 256
PC6001_8BIT_ALTCHARSET = "\uf8f1月火水木金土日年円時分秒百千万" "π┴┬┤├┼│─┌┐└┘╳大中小"
assert len(PC6001_8BIT_ALTCHARSET) == 32
PC6001_8BIT_CHARMAP = {PC6001_8BIT_CHARSET[i]: bytes([i]) for i in range(256)} | {
    PC6001_8BIT_ALTCHARSET[i]: bytes([0x14, i + 0x30]) for i in range(32)
}
PC6001_8BIT_CHARMAP_COMPAT = {
    unicodedata.normalize("NFKD", key): value
    for key, value in PC6001_8BIT_CHARMAP.items()
    if unicodedata.normalize("NFKD", key) != key
}


def encode_pc6001_8bit_charset(s, try_harder=True):
    s = "".join(
        [
            (
                unicodedata.normalize("NFKD", s[i : i + 1])
                if (
                    unicodedata.name(s[i : i + 1], "?")
                    .lower()
                    .startswith("hiragana letter")
                    or unicodedata.name(s[i : i + 1], "?")
                    .lower()
                    .startswith("katakana letter")
                )
                else s[i : i + 1]
            )
            for i in range(len(s))
        ]
    )
    byts, chars_consumed, num_chars = b"", 0, len(s)
    while chars_consumed < num_chars:
        ch = s[chars_consumed]
        byt = PC6001_8BIT_CHARMAP.get(ch, PC6001_8BIT_CHARMAP_COMPAT.get(ch)) or (
            bytes([ord(ch)]) if ord(ch) <= 0x7F else None
        )
        if byt is None and try_harder:
            cch = unicodedata.normalize("NFKD", ch)
            byt = PC6001_8BIT_CHARMAP.get(cch, PC6001_8BIT_CHARMAP_COMPAT.get(cch)) or (
                bytes([ord(cch)]) if ord(cch) <= 0x7F else None
            )
        if byt is None:
            raise UnicodeEncodeError(
                "pc6001-8bit",
                s,
                chars_consumed,
                chars_consumed + 1,
                f"no mapping for U+{ord(ch):04X} {unicodedata.name(ch, repr(ch))}",
            )
        byts += byt
        chars_consumed += 1
    return byts


def decode_pc6001_8bit_charset(byts, preserve=MINIMAL_CONTROLS):
    s, bytes_consumed, num_bytes = "", 0, len(byts)
    while bytes_consumed < num_bytes:
        byt = byts[bytes_consumed]
        if (
            bytes_consumed > 0
            and byts[bytes_consumed - 1] == 0x14
            and byt >= 0x30
            and byt <= 0x4F
        ):
            s = (
                s[: -len(PC6001_8BIT_CHARSET[0x14])]
                + PC6001_8BIT_ALTCHARSET[byt - 0x30]
            )
        elif byt in preserve:
            s += chr(byt)
        else:
            s += PC6001_8BIT_CHARSET[byt]
        if (
            len(s) > 1
            and s[-1:]
            in "\N{HALFWIDTH KATAKANA VOICED SOUND MARK}\N{HALFWIDTH KATAKANA SEMI-VOICED SOUND MARK}"
            and unicodedata.name(s[-2:-1], "?").lower().startswith("hiragana letter")
        ):
            s = s[:-2] + unicodedata.normalize("NFKC", s[-2:])
        bytes_consumed += 1
    round_trip_byts = encode_pc6001_8bit_charset(s)
    assert byts == round_trip_byts, UnicodeDecodeError(
        "pc6001-8bit",
        byts,
        0,
        num_bytes,
        f"round-trip failure for {repr(s)} with preserve={repr(preserve)}; result:\n {repr(byts)}, got:\n {repr(round_trip_byts)}",
    )
    return s


def smoke_test_pc6001_8bit_charset():
    assert decode_pc6001_8bit_charset(b"") == ""
    assert encode_pc6001_8bit_charset("") == b""
    assert decode_pc6001_8bit_charset(b"\x00") == "\x00"
    assert encode_pc6001_8bit_charset("\x00") == b"\x00"
    assert encode_pc6001_8bit_charset("␀") == b"\x00"
    assert encode_pc6001_8bit_charset("\uf8f1") == b"\x14\x30"
    assert encode_pc6001_8bit_charset("小") == b"\x14\x4f"
    assert encode_pc6001_8bit_charset("␔") == b"\x14"
    assert encode_pc6001_8bit_charset("\x14") == b"\x14"
    assert encode_pc6001_8bit_charset("\x14\x4f") == b"\x14\x4f"
    round_trip_test_failures = {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i]))): bytes([i])
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i])))
        != bytes([i])
    }
    round_trip_test_failures |= {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([0x14, i]))): bytes(
            [0x14, i]
        )
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([0x14, i])))
        != bytes([0x14, i])
    }
    round_trip_test_failures |= {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEE]))): bytes(
            [i, 0xEE]
        )
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEE])))
        != bytes([i, 0xEE])
    }
    round_trip_test_failures |= {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEF]))): bytes(
            [i, 0xEF]
        )
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEF])))
        != bytes([i, 0xEF])
    }
    assert not round_trip_test_failures, round_trip_test_failures
    unicode_test = (
        "\r\n".join(
            (
                "\\￮╳•╳o/ I ♥ PC6001!",
                "パピコンが大すきです!",
                "「パピコン」は にっぽんでんき が せいぞうした8ビットコンピュータで、やすいことから いちじき にんき を はくしました。",
                "「！？」　･･･",
                "│|¦~-ｰ─_",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐ ┌￪┐ ++-+  ^/",
                "├┼─┤ ￩┼￫ ++-+ <X>",
                "││•│･└￬┘ ¦|.¦ /v ",
                "└┴─┘<>O[]++-+ π>3",
                "␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡",
            )
        )
        + "\x1a\x00"
    )
    expected_8bit = (
        b"\r\n".join(
            (
                b"\\\x84\x14L\x85\x14Lo/ I \x81 PC6001!",
                b"\xca\xdf\xcb\xdf\xba\xdd\x96\xde\x14M\x9d\x97\xe3\xde\x9d!",
                b"\xa2\xca\xdf\xcb\xdf\xba\xdd\xa3\xea \xe6\x8f\xee\xdf\xfd\xe3\xde\xfd\x97 \x96\xde \x9e\x92\x9f\xde\x93\x9c\xe08\xcb\xde\xaf\xc4\xba\xdd\xcb\xdf\xad\x90\xc0\xe3\xde\xa4\xf4\x9d\x92\x9a\xe4\x96\xf7 \x92\xe1\x9c\xde\x97 \xe6\xfd\x97 \x86 \xea\x98\x9c\xef\x9c\xe0\xa1",
                b"\xa2!?\xa3 \xa5\xa5\xa5",
                b"\x14F||~-\xb0\x14G_",
                b"\\0=0\x149",
                b"2025\x14807\x14118\x147 14\x14:11\x14;16\x14<",
                b"\x14H\x14B\x14G\x14I \x14H\x1e\x14I ++-+  ^/",
                b"\x14D\x14E\x14G\x14C \x1d\x14E\x1c ++-+ <X>",
                b"\x14F\x14F\x85\x14F\xa5\x14J\x1f\x14K ||.| /v ",
                b"\x14J\x14A\x14G\x14K<>O[]++-+ \x14@>3",
                bytes([i for i in range(0x20)] + [0x7F]),
            )
        )
        + b"\x1a\x00"
    )
    assert (
        encode_pc6001_8bit_charset(unicode_test) == expected_8bit
    ), f"encode_pc6001_8bit_charset({repr(unicode_test)}) returned:\n {repr(encode_pc6001_8bit_charset(unicode_test))}, expecting:\n {repr(expected_8bit)}"
    pc6001_8bit_test = expected_8bit
    try:
        unexpected_8bit = encode_pc6001_8bit_charset(unicode_test, try_harder=False)
        assert (
            False
        ), f"Expected a UnicodeEncodeError for encode_pc6001_8bit_charset({repr(unicode_test)}, try_harder=False) but no error was raised"
    except UnicodeEncodeError:
        pass
    except Exception as e:
        assert (
            False
        ), f"Expected a UnicodeEncodeError for encode_pc6001_8bit_charset({repr(unicode_test)}, try_harder=False) but {repr(e)} was raised instead"
    expected_unicode = (
        "\r\n".join(
            (
                "¥￮╳•╳o/ I ♥ PC6001!",
                "ﾊﾟﾋﾟｺﾝが大すきです!",
                "｢ﾊﾟﾋﾟｺﾝ｣は にっぽんでんき が せいぞうした8ﾋﾞｯﾄｺﾝﾋﾟｭーﾀで､やすいことから いちじき にんき を はくしました｡",
                "｢!?｣ ･･･",
                "│¦¦~-ｰ─_",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐ ┌￪┐ ++-+  ^/",
                "├┼─┤ ￩┼￫ ++-+ <X>",
                "││•│･└￬┘ ¦¦.¦ /v ",
                "└┴─┘<>O[]++-+ π>3",
                "\x00␁␂␃␄␅␆␇␈␉\n␋␌\r␎␏␐␑␒␓␔␕␖␗␘␙\x1a␛￫￩￪￬\x7f",
            )
        )
        + "\x1a\x00"
    )
    assert (
        decode_pc6001_8bit_charset(pc6001_8bit_test) == expected_unicode
    ), f"decode_pc6001_8bit_charset({repr(pc6001_8bit_test)}) returned:\n {repr(decode_pc6001_8bit_charset(pc6001_8bit_test))}, expecting:\n {repr(expected_unicode)}"
    assert (
        encode_pc6001_8bit_charset(expected_unicode, try_harder=False)
        == pc6001_8bit_test
    ), f"encode_pc6001_8bit_charset({repr(expected_unicode)}, try_harder=False) returned:\n {repr(encode_pc6001_8bit_charset(expected_unicode, try_harder=False))}, expecting:\n {repr(pc6001_8bit_test)}"
    expected_no_controls_unicode = (
        "␍␊".join(
            (
                "¥￮╳•╳o/ I ♥ PC6001!",
                "ﾊﾟﾋﾟｺﾝが大すきです!",
                "｢ﾊﾟﾋﾟｺﾝ｣は にっぽんでんき が せいぞうした8ﾋﾞｯﾄｺﾝﾋﾟｭーﾀで､やすいことから いちじき にんき を はくしました｡",
                "｢!?｣ ･･･",
                "│¦¦~-ｰ─_",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐ ┌￪┐ ++-+  ^/",
                "├┼─┤ ￩┼￫ ++-+ <X>",
                "││•│･└￬┘ ¦¦.¦ /v ",
                "└┴─┘<>O[]++-+ π>3",
                "␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡",
            )
        )
        + "␚␀"
    )
    assert (
        decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=NO_CONTROLS)
        == expected_no_controls_unicode
    ), f"decode_pc6001_8bit_charset({repr(pc6001_8bit_test)}, preserve=NO_CONTROLS) returned:\n {repr(decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=NO_CONTROLS))}, expecting:\n {repr(expected_no_controls_unicode)}"
    expected_ascii_controls_unicode = (
        "\r\n".join(
            (
                "¥￮╳•╳o/ I ♥ PC6001!",
                "ﾊﾟﾋﾟｺﾝが大すきです!",
                "｢ﾊﾟﾋﾟｺﾝ｣は にっぽんでんき が せいぞうした8ﾋﾞｯﾄｺﾝﾋﾟｭーﾀで､やすいことから いちじき にんき を はくしました｡",
                "｢!?｣ ･･･",
                "│¦¦~-ｰ─_",
                "¥0=0円",
                "2025年07月18日 14時11分16秒",
                "┌┬─┐ ┌\x1e┐ ++-+  ^/",
                "├┼─┤ \x1d┼\x1c ++-+ <X>",
                "││•│･└\x1f┘ ¦¦.¦ /v ",
                "└┴─┘<>O[]++-+ π>3",
                "".join([chr(i) for i in range(0x20)]) + "\x7f",
            )
        )
        + "\x1a\x00"
    )
    assert (
        decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=ASCII_CONTROLS)
        == expected_ascii_controls_unicode
    ), f"decode_pc6001_8bit_charset({repr(pc6001_8bit_test)}, preserve=ASCII_CONTROLS) returned:\n {repr(decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=ASCII_CONTROLS))}, expecting:\n {repr(expected_ascii_controls_unicode)}"


# File data obfuscation schemes

no_obfuscation = lambda i, byt: byt


def deobfuscate_byte_pc98(i, byt):
    # N88-BASIC(86) uses a simple bit-rotation
    return ((byt & 0x7F) << 1) | ((byt & 0x80) >> 7)


def obfuscate_byte_pc98(i, byt):
    # N88-BASIC(86) uses a simple bit-rotation
    return ((byt & 0xFE) >> 1) | ((byt & 0x01) << 7)


def smoke_test_pc98_deobfuscation():
    # Ensure every byte round-trips at offset zero, and also ensure a
    # few selected bytes convert correctly at many different offsets. the
    # implementation shouldn't care about the offset, this just
    # verifies that.
    for i in range(256):
        # plaintext round-trip verification
        assert deobfuscate_byte_pc98(0, obfuscate_byte_pc98(0, i)) == i
        assert deobfuscate_byte_pc98(i, obfuscate_byte_pc98(i, i)) == i
        # verification of specific ciphertext-to-plaintext conversions
        assert deobfuscate_byte_pc98(i, 0x00) == 0x00
        assert deobfuscate_byte_pc98(i, 0xFF) == 0xFF
        assert deobfuscate_byte_pc98(i, 0x55) == 0xAA
        assert deobfuscate_byte_pc98(i, 0xAA) == 0x55
        assert deobfuscate_byte_pc98(i, 0x40) == 0x80
        assert deobfuscate_byte_pc98(i, 0x20) == 0x40
        assert deobfuscate_byte_pc98(i, 0x10) == 0x20
        assert deobfuscate_byte_pc98(i, 0x08) == 0x10
        assert deobfuscate_byte_pc98(i, 0x04) == 0x08
        assert deobfuscate_byte_pc98(i, 0x02) == 0x04
        assert deobfuscate_byte_pc98(i, 0x01) == 0x02
        assert deobfuscate_byte_pc98(i, 0x80) == 0x01
        # ciphertext round-trip verification
        assert obfuscate_byte_pc98(0, deobfuscate_byte_pc98(0, i)) == i
        assert obfuscate_byte_pc98(i, deobfuscate_byte_pc98(i, i)) == i
        # verification of specific plaintext-to-ciphertext conversions
        assert obfuscate_byte_pc98(i, 0x00) == 0x00
        assert obfuscate_byte_pc98(i, 0xFF) == 0xFF
        assert obfuscate_byte_pc98(i, 0x55) == 0xAA
        assert obfuscate_byte_pc98(i, 0xAA) == 0x55
        assert obfuscate_byte_pc98(i, 0x80) == 0x40
        assert obfuscate_byte_pc98(i, 0x40) == 0x20
        assert obfuscate_byte_pc98(i, 0x20) == 0x10
        assert obfuscate_byte_pc98(i, 0x10) == 0x08
        assert obfuscate_byte_pc98(i, 0x08) == 0x04
        assert obfuscate_byte_pc98(i, 0x04) == 0x02
        assert obfuscate_byte_pc98(i, 0x02) == 0x01
        assert obfuscate_byte_pc98(i, 0x01) == 0x80


# NEC PC-88 obfuscated ("encrypted") BASIC saves use a pair of XOR
# keys which are stored in ROM, using the algorithm previously
# documented here:
# https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format
# - but with different key data. One key has length 11, the other has
# length 13. A byte from each one is XOR'ed with each byte being
# de-obfuscated/decrypted or obfuscated/encrypted. However, you can
# de-obfuscate/decrypt (or obfuscate/encrypt) the save data just fine
# without the ROM data, provided you have a "combined XOR key" which
# is 11*13 = 143 bytes long. It turns out you can get BASIC to save
# this key as part of your program, provided you have the right string
# in your program at the right position. So, I wrote a program to do
# this and recovered the "combined XOR key" from my save file.
#
# Here's the BASIC program I typed in for key recovery:
# ```basic
# 10 ' The length of the comment is important. Do not change it! It needs to leave the first byte of KP$ at file offset 143. '''''''
# 20 KP$="▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂"
# 30 WIDTH 80:SCREEN,,0:CLS
# 40 V1$="":FOR J=11 TO 1 STEP -1:FOR I=13 TO 1 STEP -1:V1$=V1$+CHR$(128+I):NEXT I:NEXT J
# 50 IF KP$<>V1$ THEN PRINT"Program is corrupt. Re-enter:":PRINT"20 KP$="+CHR$(34)+V1$+CHR$(34):STOP
# 60 PRINT"Saving known plaintext in temporary file TMP."
# 70 SAVE"TMP"
# 80 PRINT"Verifying known plaintext in temporary file TMP."
# 90 OPEN"TMP"FOR INPUT AS #1
# 100 XP$=INPUT$(143,1) ' Padding
# 110 VP$=INPUT$(143,1) ' To verify
# 120 CLOSE #1
# 130 KILL"TMP"
# 140 PRINT"Removing temporary file TMP."
# 150 IF KP$<>VP$ THEN PRINT"KP$<>VP$":PRINT"KP$:";KP$:PRINT"VP$:"VP$:STOP
# 160 PRINT"Saving ciphertext in temporary file TMP."
# 170 SAVE"TMP",P
# 180 PRINT"Reading cyphertext from temporary file TMP."
# 190 OPEN"TMP"FOR INPUT AS #1
# 200 CX$=INPUT$(143,1) ' Padding
# 210 CT$=INPUT$(143,1) ' To verify
# 220 CLOSE #1
# 230 KILL"TMP"
# 240 PRINT"Removing temporary file TMP."
# 250 CK$="":FOR I=0 TO 142:CK$=CK$+CHR$(((ASC(MID$(CT$,I+1,1))+256-11+(I MOD 11))MOD 256)XOR 128):NEXT I
# 260 PRINT"Combined key:":FOR I=1 TO LEN(CK$):PRINT MID$(HEX$(256+ASC(MID$(CK$,I,1))),2);" ";:NEXT I:PRINT
# 270 DC$="":FOR I=0 TO LEN(CT$)-1:DC$=DC$+CHR$(((((ASC(MID$(CT$,I+1,1))+256-11+(I MOD 11))MOD 256)XOR ASC(MID$(CK$,1+(I MOD 143),1)))+13-(I MOD 13))MOD 256):NEXT I
# 280 IF KP$<>DC$ THEN PRINT"KP$<>DC$":PRINT"KP$:";KP$:PRINT"DC$:"DC$:STOP
# 290 PRINT"Combined key has been verified to decrypt plaintext without ROM data."
# 300 PRINT"Saving combined key in CK.DAT."
# 310 OPEN"CK.DAT" FOR OUTPUT AS #1
# 320 PRINT #1,CK$;
# 330 CLOSE #1
# 340 PRINT"Done."
# 350 END
# ```

# Here's the combined key material from CK.DAT:
PC88_COMBINED_KEY = bytes.fromhex(
    "C0CFCC8562810C42C304E5E6CD"
    "1175B690E49735EDB2FC6E3777"
    "6B603086DD384415392DD44D62"
    "ED760929ACC0CFC48357C1CB74"
    "D4D978D1271175BE96D1D7F2DB"
    "A521F3009D6B603880E8788323"
    "2EF0497A88ED76012F998008F2"
    "948A5CFC9ED4D970D71251B288"
    "810C4AC531A521FB06A82BA70E"
    "9735E5B4C92EF0417CBDADB137"
    "38441D3F18948A54FAAB941E46"
)


def deobfuscate_byte_pc88(i, byt):
    # PC88 BASIC uses the same algorithm as
    # https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format
    # but different key material.
    return (
        range(13, 0, -1)[i % 13]
        + (
            ((byt + 0x100 - range(11, 0, -1)[i % 11]) % 0x100)
            ^ PC88_COMBINED_KEY[i % (11 * 13)]
        )
    ) % 0x100


def obfuscate_byte_pc88(i, byt):
    # PC88 BASIC uses the same algorithm as
    # https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format
    # but different key material.
    return (
        range(11, 0, -1)[i % 11]
        + (
            ((byt + 0x100 - range(13, 0, -1)[i % 13]) % 0x100)
            ^ PC88_COMBINED_KEY[i % (11 * 13)]
        )
    ) % 0x100


def smoke_test_p88_deobfuscation():
    # This part of the smoke test mimics the BASIC combined XOR key
    # recovery program to ensure the same result is achievable using
    # the combined XOR key implementation written in Python
    kp = encode_pc98_8bit_charset("▊▋▌▍▎▏█▇▆▅▄▃▂") * 11
    assert len(kp) == 11 * 13
    vp = bytes([128 + 13 - i for i in range(13)] * 11)
    assert len(vp) == 11 * 13
    assert kp == vp, f"{kp} vs. {vp}"
    ct = bytes([obfuscate_byte_pc88(i, kp[i]) for i in range(len(kp))])
    assert len(ct) == 11 * 13
    assert ct != kp
    dc = bytes([deobfuscate_byte_pc88(i, ct[i]) for i in range(len(ct))])
    assert len(dc) == 11 * 13
    assert dc == kp
    ck = bytes(
        [((ct[i] + 0x100 - 11 + (i % 11)) % 0x100) ^ 0x80 for i in range(len(ct))]
    )
    assert ck == PC88_COMBINED_KEY, f"ck={ck} vs. PC88_COMBINED_KEY={PC88_COMBINED_KEY}"
    # Ensure every byte round-trips at offset zero, and also ensure a
    # few selected bytes round-trip at many different offsets (256 is
    # larger than the combined XOR key length, so this ensures there
    # won't be any surprises at the wrapping point or past it.
    for i in range(256):
        # plaintext round-trip verification
        assert deobfuscate_byte_pc88(0, obfuscate_byte_pc88(0, i)) == i
        assert deobfuscate_byte_pc88(i, obfuscate_byte_pc88(i, i)) == i
        assert deobfuscate_byte_pc88(i, obfuscate_byte_pc88(i, 0x00)) == 0x00
        assert deobfuscate_byte_pc88(i, obfuscate_byte_pc88(i, 0x55)) == 0x55
        assert deobfuscate_byte_pc88(i, obfuscate_byte_pc88(i, 0xAA)) == 0xAA
        assert deobfuscate_byte_pc88(i, obfuscate_byte_pc88(i, 0xFF)) == 0xFF
        # ciphertext round-trip verification
        assert obfuscate_byte_pc88(0, deobfuscate_byte_pc88(0, i)) == i
        assert obfuscate_byte_pc88(i, deobfuscate_byte_pc88(i, i)) == i
        assert obfuscate_byte_pc88(i, deobfuscate_byte_pc88(i, 0x00)) == 0x00
        assert obfuscate_byte_pc88(i, deobfuscate_byte_pc88(i, 0x55)) == 0x55
        assert obfuscate_byte_pc88(i, deobfuscate_byte_pc88(i, 0xAA)) == 0xAA
        assert obfuscate_byte_pc88(i, deobfuscate_byte_pc88(i, 0xFF)) == 0xFF


TRACK_TABLE_OFFSET = 0x20
TRACK_ENTRY_SIZE = 4
SECTOR_HEADER_SIZE = 16

DISK_ATTR_WRITE_PROTECTED = "DiskWriteProtected"


def analyze_disk(d88_data, disk_idx):
    disk_name_or_comment = d88_data[:0x10].rstrip(b"\0") or None
    disk_attrs = DISK_ATTR_WRITE_PROTECTED if d88_data[0x1A] & 0x10 else None
    disk_sz = int.from_bytes(d88_data[0x1C:0x20], "little")
    assert disk_sz <= len(
        d88_data
    ), f"Is this a D88 file? The disk size field is too large"
    assert (
        disk_sz > TRACK_TABLE_OFFSET + TRACK_ENTRY_SIZE
    ), f"Is this a D88 file? The disk size field is too small"
    track_offsets = []
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
    return dict(
        disk_name_or_comment=disk_name_or_comment,
        disk_attrs=disk_attrs,
        disk_sz=disk_sz,
        track_offsets=track_offsets,
        disk_suffix=(
            "" if disk_idx == 1 and len(d88_data) == disk_sz else f" #Disk{disk_idx:02}"
        ),
    )


def start_log():
    output = []
    return output


def log_disk_information(disk_info, output):
    output.append(f"\n== Disk Information{disk_info['disk_suffix']} ==")
    output.append(f"Disk name/comment: {disk_info['disk_name_or_comment']}")
    output.append(f"Disk attributes: {disk_info['disk_attrs']}")
    output.append(f"Disk size: {disk_info['disk_sz']}")


def analyze_tracks_and_sectors(d88_data, disk_info, output):
    output.append("\n== Track/Sector Table ==")
    track_sector_map = {}

    all_sector_ranges = []
    nominal_sectors_in_track = {}
    for track_offset in disk_info["track_offsets"]:
        sectors = []
        cursor = track_offset
        track_num, side_num = None, None
        while cursor + SECTOR_HEADER_SIZE <= disk_info["disk_sz"]:
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
                actual_data_offset + sector_data_size <= disk_info["disk_sz"]
            ), "Is this a D88 file? Sector data spilled off the end"
            for other_sector in sectors:
                assert (
                    other_sector[0] != sec_num
                ), f"Is this a D88 file? Track {trk:3}, Side {side}, Sector {sec_num:2} appears more than once"
            sectors.append(
                (
                    sec_num,
                    actual_data_offset,
                    d88_data[
                        actual_data_offset : actual_data_offset + sector_data_size
                    ],
                    sectors_in_track,
                )
            )
            nominal_sectors_in_track[(trk, side)] = nominal_sectors_in_track.get(
                (trk, side), sectors_in_track
            )
            assert (
                nominal_sectors_in_track[(trk, side)] == sectors_in_track
            ), f"Is this a damaged disk? Sectors-per-track varies in Track {trk:3}, Side {side}: {nominal_sectors_in_track[(trk, side)]} vs {sectors_in_track}"
            all_sector_ranges.append(
                [actual_data_offset, actual_data_offset + sector_data_size]
            )
            cursor += SECTOR_HEADER_SIZE + sector_data_size
        key = (track_num, side_num)
        track_sector_map[key] = sectors
        output.append(
            f"Track {track_num:3}, Side {side_num}: "
            + ", ".join(f"{s[0]:2}:{len(s[2])}" for s in sectors)
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

    for (track_num, side_num), sectors in track_sector_map.items():
        found_tracks = max(found_tracks, 1 + track_num)
        found_sides = max(found_sides, 1 + side_num)
        for sec_num, actual_data_offset, sector_data, sectors_in_track in sectors:
            found_total_sectors += 1
            found_disk_size += len(sector_data)
            largest_sector_size = max(largest_sector_size, len(sector_data))
            found_sectors = max(found_sectors, sec_num)

    return dict(
        track_sector_map=track_sector_map,
        nominal_sectors_in_track=nominal_sectors_in_track,
        found_tracks=found_tracks,
        found_sides=found_sides,
        found_total_sectors=found_total_sectors,
        found_sectors=found_sectors,
        found_disk_size=found_disk_size,
        largest_sector_size=largest_sector_size,
    )


FAT8_FINAL_CLUSTER_OFFSET = 0xC0
FAT8_RESERVED_CLUSTERS = 0x01
FAT8_MAX_CLUSTERS = 0xA0
FAT8_CHAIN_TERMINAL_LINK = 0xFE
FAT8_UNALLOCATED_CLUSTER = 0xFF
FAT8_BOOT_SECTOR_CLUSTER = 0x00
FAT8_FIRST_METADATA_CLUSTER_PC88 = 0x4A
FAT8_FIRST_METADATA_CLUSTER_PC98 = 0x46
FAT8_FIRST_METADATA_CLUSTER_PC66 = 0x24
FAT8_FIRST_METADATA_CLUSTER_PC66SR = 0x4A


def guess_fat8_fmt_heuristics(track_and_sector_info):
    boot_sector = (
        [
            sector_data
            for sec_num, actual_data_offset, sector_data, sectors_in_track in sum(
                [
                    sectors
                    for (trk, side), sectors in track_and_sector_info[
                        "track_sector_map"
                    ].items()
                    if trk == 0 and side == 0
                ],
                [],
            )
            if sec_num == 1
        ][:1]
        or [None]
    )[0]
    is_pc66sr_rxr = boot_sector is not None and (
        boot_sector.startswith(b"RXR") or boot_sector.startswith(b"IPL")
    )
    is_pc66_sys = boot_sector is not None and boot_sector.startswith(b"SYS")
    is_pc98_sys = boot_sector is not None and len(boot_sector) == 128
    side_is_cluster_lsb = boot_sector is not None and boot_sector.startswith(
        b"\0\0\0\0"
    )
    fat8_sectors_per_track = max(
        sectors
        for (trk, side), sectors in track_and_sector_info[
            "nominal_sectors_in_track"
        ].items()
        if trk in (0, 1) and side == 0
    )
    fat8_sides = 1 + max(
        side
        for trk, side in track_and_sector_info["nominal_sectors_in_track"].keys()
        if trk in (0, 1)
    )
    fat8_sector_size = max(
        max(
            len(sector_data)
            for sec_num, actual_data_offset, sector_data, sectors_in_track in sectors
        )
        for (trk, side), sectors in track_and_sector_info["track_sector_map"].items()
        if trk in (0, 1) and side == 0
    )
    fat8_sector_shift = 0
    while fat8_sector_size > 0x100 and fat8_sectors_per_track < 16:
        fat8_sector_shift += 1
        fat8_sector_size >>= 1
        fat8_sectors_per_track <<= 1

    fat8_first_metadata_cluster = (
        FAT8_FIRST_METADATA_CLUSTER_PC66SR
        if is_pc66sr_rxr
        else (
            FAT8_FIRST_METADATA_CLUSTER_PC66
            if is_pc66_sys or fat8_sides == 1
            else (
                FAT8_FIRST_METADATA_CLUSTER_PC98
                if is_pc98_sys
                else FAT8_FIRST_METADATA_CLUSTER_PC88
            )
        )
    )
    fat8_8bit_charset, decode_8bit_charset, encode_8bit_charset = (
        ("pc6001-8bit", decode_pc6001_8bit_charset, encode_pc6001_8bit_charset)
        if is_pc66_sys or is_pc66sr_rxr or fat8_sides == 1
        else ("pc98-8bit", decode_pc98_8bit_charset, encode_pc98_8bit_charset)
    )
    fat8_obfuscation, deobfuscate_byte, obfuscate_byte = (
        (None, no_obfuscation, no_obfuscation)
        if side_is_cluster_lsb or is_pc66_sys or is_pc66sr_rxr or fat8_sides == 1
        else (
            ("pc98", deobfuscate_byte_pc98, obfuscate_byte_pc98)
            if is_pc98_sys
            else ("pc88", deobfuscate_byte_pc88, obfuscate_byte_pc88)
        )
    )
    fat8_disk_size = (
        track_and_sector_info["found_tracks"]
        * fat8_sides
        * fat8_sectors_per_track
        * fat8_sector_size
    )
    fat8_est_bytes_per_cluster = (
        fat8_disk_size + FAT8_MAX_CLUSTERS - 1
    ) // FAT8_MAX_CLUSTERS
    fat8_bytes_per_track = fat8_sectors_per_track * fat8_sector_size
    fat8_clusters_per_track = min(2, fat8_bytes_per_track // fat8_est_bytes_per_cluster)
    fat8_total_clusters = (
        track_and_sector_info["found_tracks"] * fat8_sides * fat8_clusters_per_track
    )
    fat8_sectors_per_cluster = fat8_sectors_per_track // fat8_clusters_per_track
    fat8_bytes_per_cluster = fat8_sectors_per_cluster * fat8_sector_size
    fat8_tracks = {36: 35, 41: 40, 78: 77, 81: 80}.get(
        track_and_sector_info["found_tracks"], track_and_sector_info["found_tracks"]
    )

    metadata_track = (
        fat8_first_metadata_cluster // fat8_clusters_per_track // fat8_sides
    )
    metadata_side = fat8_first_metadata_cluster // fat8_clusters_per_track % fat8_sides

    fat8_fmt_name = f'Unknown format [{"Pasopia" if side_is_cluster_lsb else "PC-6001 mkII SR/6601 SR" if is_pc66sr_rxr else "N60/PC-6001/mkII/6601" if (is_pc66_sys or fat8_sides == 1) else "PC98" if is_pc98_sys else "N80/PC88"}-like {fat8_sides}-sided {track_and_sector_info["found_tracks"]}-track {fat8_sectors_per_track}-sectored (physical {track_and_sector_info["found_sectors"]}-sectored) with {len(boot_sector)}-byte boot sector beginning with {repr(boot_sector[:4])} (largest physical sector is {track_and_sector_info["largest_sector_size"]} bytes) with metadata in track {metadata_track} on side {metadata_side} and {fat8_clusters_per_track} clusters per track]'
    return dict(
        boot_sector=boot_sector,
        is_pc66sr_rxr=is_pc66sr_rxr,
        is_pc66_sys=is_pc66_sys,
        is_pc98_sys=is_pc98_sys,
        side_is_cluster_lsb=side_is_cluster_lsb,
        fat8_sectors_per_track=fat8_sectors_per_track,
        fat8_sides=fat8_sides,
        fat8_sector_size=fat8_sector_size,
        fat8_sector_shift=fat8_sector_shift,
        fat8_first_metadata_cluster=fat8_first_metadata_cluster,
        fat8_8bit_charset=fat8_8bit_charset,
        decode_8bit_charset=decode_8bit_charset,
        encode_8bit_charset=encode_8bit_charset,
        fat8_obfuscation=fat8_obfuscation,
        deobfuscate_byte=deobfuscate_byte,
        obfuscate_byte=obfuscate_byte,
        fat8_disk_size=fat8_disk_size,
        fat8_bytes_per_track=fat8_bytes_per_track,
        fat8_clusters_per_track=fat8_clusters_per_track,
        fat8_total_clusters=fat8_total_clusters,
        fat8_sectors_per_cluster=fat8_sectors_per_cluster,
        fat8_bytes_per_cluster=fat8_bytes_per_cluster,
        fat8_tracks=fat8_tracks,
        metadata_track=metadata_track,
        metadata_side=metadata_side,
        fat8_fmt_name=fat8_fmt_name,
    )


def check_known_fat8_fmts(track_and_sector_info, fat8_basic_info):
    guessed_fmt_name, guessed_fmt, guessed_fmt_score = None, None, None
    for fmt_name, fmt in KNOWN_FAT8_FMTS.items():
        fmt_tracks = fmt["tracks"]
        fmt_fat_tracks = fmt["fat_tracks"]
        fmt_sides = fmt["sides"]
        fmt_sectors = fmt["sectors"]
        fmt_sector1_start_hints = fmt["sector1_start_hints"]
        fmt_charset = fmt["charset"]
        fmt_obfuscation = fmt["obfuscation"]
        fmt_metadata_track = fmt["metadata_track"]
        fmt_metadata_side = fmt["metadata_side"]
        fmt_clusters_per_track = fmt["clusters_per_track"]
        fmt_side_is_cluster_lsb = fmt["side_is_cluster_lsb"]
        assert fmt == dict(
            tracks=fmt_tracks,
            fat_tracks=fmt_fat_tracks,
            sides=fmt_sides,
            sectors=fmt_sectors,
            sector1_start_hints=fmt_sector1_start_hints,
            charset=fmt_charset,
            obfuscation=fmt_obfuscation,
            metadata_track=fmt_metadata_track,
            metadata_side=fmt_metadata_side,
            clusters_per_track=fmt_clusters_per_track,
            side_is_cluster_lsb=fmt_side_is_cluster_lsb,
        )
        if fmt_tracks != track_and_sector_info["found_tracks"]:
            continue
        if fmt_sides != fat8_basic_info["fat8_sides"]:
            continue
        if fmt_sectors != fat8_basic_info["fat8_sectors_per_track"]:
            continue
        fmt_score = sum(
            1
            for hint in fmt_sector1_start_hints
            if fat8_basic_info["boot_sector"] is not None
            and hint(fat8_basic_info["boot_sector"])
        )
        if guessed_fmt is None or fmt_score > guessed_fmt_score:
            guessed_fmt_name, guessed_fmt, guessed_fmt_score = fmt_name, fmt, fmt_score
    if guessed_fmt is not None:
        fat8_basic_info["fat8_fmt_name"] = guessed_fmt_name
        if guessed_fmt["charset"] is not None:
            (
                fat8_basic_info["decode_8bit_charset"],
                fat8_basic_info["encode_8bit_charset"],
            ) = {
                "pc6001-8bit": (decode_pc6001_8bit_charset, encode_pc6001_8bit_charset),
                "pc98-8bit": (decode_pc98_8bit_charset, encode_pc98_8bit_charset),
            }[
                guessed_fmt["charset"]
            ]
            fat8_basic_info["fat8_8bit_charset"] = guessed_fmt["charset"]
        if guessed_fmt["obfuscation"] is not None:
            fat8_basic_info["deobfuscate_byte"], fat8_basic_info["obfuscate_byte"] = {
                "pc98": (deobfuscate_byte_pc98, obfuscate_byte_pc98),
                "pc88": (deobfuscate_byte_pc88, obfuscate_byte_pc88),
            }[guessed_fmt["obfuscation"]]
        else:
            fat8_basic_info["deobfuscate_byte"], fat8_basic_info["obfuscate_byte"] = (
                no_obfuscation,
                no_obfuscation,
            )
        fat8_basic_info["fat8_obfuscation"] = guessed_fmt["obfuscation"]
        fat8_basic_info["metadata_track"] = guessed_fmt["metadata_track"]
        fat8_basic_info["metadata_side"] = guessed_fmt["metadata_side"]
        fat8_basic_info["fat8_clusters_per_track"] = guessed_fmt["clusters_per_track"]
        fat8_basic_info["fat8_first_metadata_cluster"] = (
            fat8_basic_info["metadata_track"] * fat8_basic_info["fat8_sides"]
            + fat8_basic_info["metadata_side"]
        ) * fat8_basic_info["fat8_clusters_per_track"]
        fat8_basic_info["side_is_cluster_lsb"] = guessed_fmt["side_is_cluster_lsb"]
        fat8_basic_info["fat8_tracks"] = guessed_fmt["fat_tracks"]
    return fat8_basic_info


def analyze_fat8_fmt(track_and_sector_info):
    fat8_basic_info = guess_fat8_fmt_heuristics(
        track_and_sector_info=track_and_sector_info
    )
    fat8_basic_info = check_known_fat8_fmts(
        track_and_sector_info=track_and_sector_info, fat8_basic_info=fat8_basic_info
    )

    fat8_basic_info["fat8_total_clusters"] = (
        fat8_basic_info["fat8_tracks"]
        * fat8_basic_info["fat8_sides"]
        * fat8_basic_info["fat8_clusters_per_track"]
    )
    fat8_basic_info["fat8_sectors_per_cluster"] = (
        fat8_basic_info["fat8_sectors_per_track"]
        // fat8_basic_info["fat8_clusters_per_track"]
    )
    fat8_basic_info["fat8_bytes_per_cluster"] = (
        fat8_basic_info["fat8_sectors_per_cluster"]
        * fat8_basic_info["fat8_sector_size"]
    )
    fat_sector_indices = {
        fat8_basic_info["fat8_sectors_per_track"] - 2,
        fat8_basic_info["fat8_sectors_per_track"] - 1,
        fat8_basic_info["fat8_sectors_per_track"] - 0,
    }
    autorun_sector_index = fat8_basic_info["fat8_sectors_per_track"] - 3
    dir_sector_indices = set(range(1, autorun_sector_index))
    metadata_cluster_indices = (
        set(
            range(
                fat8_basic_info["metadata_track"]
                * fat8_basic_info["fat8_clusters_per_track"]
                * fat8_basic_info["fat8_sides"]
                + fat8_basic_info["metadata_side"],
                (1 + fat8_basic_info["metadata_track"])
                * fat8_basic_info["fat8_clusters_per_track"]
                * fat8_basic_info["fat8_sides"]
                + fat8_basic_info["metadata_side"],
                fat8_basic_info["fat8_sides"],
            )
        )
        if fat8_basic_info["side_is_cluster_lsb"]
        else set(
            range(
                (
                    fat8_basic_info["metadata_track"] * fat8_basic_info["fat8_sides"]
                    + fat8_basic_info["metadata_side"]
                )
                * fat8_basic_info["fat8_clusters_per_track"],
                (
                    1
                    + (
                        fat8_basic_info["metadata_track"]
                        * fat8_basic_info["fat8_sides"]
                        + fat8_basic_info["metadata_side"]
                    )
                )
                * fat8_basic_info["fat8_clusters_per_track"],
            )
        )
    )
    assert (
        fat8_basic_info["fat8_first_metadata_cluster"]
        == sorted(metadata_cluster_indices)[0]
    )
    return fat8_basic_info | dict(
        fat_sector_indices=fat_sector_indices,
        autorun_sector_index=autorun_sector_index,
        dir_sector_indices=dir_sector_indices,
        metadata_cluster_indices=metadata_cluster_indices,
    )


def log_fmt_diagnostics(track_and_sector_info, fat8_info, output):
    output.append("\n== Diagnostic Information ==")
    output.append(f"Detected format name: {fat8_info['fat8_fmt_name']}")
    output.append(f"8-bit character set: {fat8_info['fat8_8bit_charset']}")
    output.append(
        f"BASIC obfuscation method: {fat8_info['fat8_obfuscation']}{'; unable to deobfuscate' if fat8_info['fat8_obfuscation'] is None else ''}"
    )
    output.append(
        f"Is side number the cluster LSB, Pasopia-style: {fat8_info['side_is_cluster_lsb']}"
    )
    output.append(f"Is PC66 SYS: {fat8_info['is_pc66_sys']}")
    output.append(f"Is PC66SR RXR: {fat8_info['is_pc66sr_rxr']}")
    output.append(f"Is PC98 boot sector: {fat8_info['is_pc98_sys']}")
    output.append(f"D88 track count: {track_and_sector_info['found_tracks']}")
    output.append(f"D88 side count: {track_and_sector_info['found_sides']}")
    output.append(f"D88 highest sector index: {track_and_sector_info['found_sectors']}")
    output.append(f"D88 total sectors: {track_and_sector_info['found_total_sectors']}")
    output.append(f"D88 disk size: {track_and_sector_info['found_disk_size']}")
    output.append(
        f"Largest D88 sector size: {track_and_sector_info['largest_sector_size']}"
    )
    output.append(f"Nominal D88 side count: {fat8_info['fat8_sides']}")
    output.append(f"Nominal D88 disk size: {fat8_info['fat8_disk_size']}")
    output.append(
        f"Nominal D88 sector size: {fat8_info['fat8_sector_size'] << fat8_info['fat8_sector_shift']}"
    )
    output.append(f"Virtual track count: {fat8_info['fat8_tracks']}")
    output.append(f"Virtual sector size: {fat8_info['fat8_sector_size']}")
    output.append(
        f"Virtual sectors per D88 sector: {1 << fat8_info['fat8_sector_shift']}"
    )
    output.append(f"Virtual sectors per track: {fat8_info['fat8_sectors_per_track']}")
    output.append(
        f"Virtual sectors per cluster: {fat8_info['fat8_sectors_per_cluster']}"
    )
    output.append(f"Bytes per cluster: {fat8_info['fat8_bytes_per_cluster']}")
    output.append(f"Bytes per track: {fat8_info['fat8_bytes_per_track']}")
    output.append(f"Clusters per track: {fat8_info['fat8_clusters_per_track']}")
    output.append(f"Total clusters: {fat8_info['fat8_total_clusters']}")
    output.append(
        f"First metadata cluster: 0x{fat8_info['fat8_first_metadata_cluster']:02X}"
    )
    output.append(f"Metadata track: {fat8_info['metadata_track']}")
    output.append(f"Metadata side: {fat8_info['metadata_side']}")
    output.append(
        f"Directory virtual sector indices: {', '.join(f'{idx}' for idx in sorted(tuple(fat8_info['dir_sector_indices'])))}"
    )
    output.append(
        f"Autorun data virtual sector index: {fat8_info['autorun_sector_index']}"
    )
    output.append(
        f"FAT virtual sector indices: {', '.join(f'{idx}' for idx in sorted(tuple(fat8_info['fat_sector_indices'])))}"
    )


ATTR_BINARY = "Binary"
ATTR_1_RESERVED = "Reserved#1"
ATTR_2_RESERVED = "Reserved#2"
ATTR_3_RESERVED = "Reserved#3"
ATTR_READ_ONLY = "Read-Only"
ATTR_OBFUSCATED = (
    "Obfuscated"  # some documentation calls this "encrypted" or "protected"
)
ATTR_READ_AFTER_WRITE = "Read-after-Write"
ATTR_NON_ASCII = "Non-ASCII"
PSEUDO_ATTR_UNUSED = "Unused(FF)"
PSEUDO_ATTR_DELETED = "Deleted(00)"
UNLISTED_ENTRY_ATTRS = {
    ATTR_1_RESERVED,
    ATTR_2_RESERVED,
    ATTR_3_RESERVED,
    PSEUDO_ATTR_UNUSED,
    PSEUDO_ATTR_DELETED,
}
ALL_ATTRS = {
    0x001: ATTR_BINARY,
    0x002: ATTR_1_RESERVED,
    0x004: ATTR_2_RESERVED,
    0x008: ATTR_3_RESERVED,
    0x010: ATTR_READ_ONLY,
    0x020: ATTR_OBFUSCATED,
    0x040: ATTR_READ_AFTER_WRITE,
    0x080: ATTR_NON_ASCII,
    0x100: PSEUDO_ATTR_DELETED,
    0x200: PSEUDO_ATTR_UNUSED,
}

# these restrictions on generated filenames are somewhat conservative
# and meant to accomodate MS-DOS, UNIX, macOS, and Windows - however
# generated names may exceed MS-DOS length limitations or contain
# multiple dots. also accomodating case-insensitive file systems
# (e.g. by avoiding collisions across multiple entries) is left to the
# caller of to_host_fs_name.

HOST_FS_UNSAFE_CHARS = set('"*+,/:;<=>?[\\]|\x7f¥¦') | set(chr(i) for i in range(0x20))
HOST_FS_UNSAFE_NAMES_UPPER = set(
    ["CLOCK$", "CON", "PRN", "AUX", "NUL"]
    + [f"COM{n}" for n in range(1, 10)]
    + [f"LPT{n}" for n in range(1, 10)]
)
HOST_FS_UNSAFE_START_CHARS = set(" ")
HOST_FS_UNSAFE_END_CHARS = set(" .")


def to_host_fs_name(name, ext, fattrs, fat8_info):
    filename = f"{name.rstrip(' ')}{'.' if ext.rstrip(' ') else ''}{ext.rstrip(' ')}"
    filename_chars = [ch for ch in filename]
    for i, ch in enumerate(filename_chars):
        unsafe = ch in HOST_FS_UNSAFE_CHARS
        if (
            filename.upper() in HOST_FS_UNSAFE_NAMES_UPPER
            or filename == "." * len(filename)
            and i == 0
        ):
            unsafe = True
        if ch == "." and i != len(name.rstrip(" ")):
            unsafe = True
        if i == 0 and ch in HOST_FS_UNSAFE_START_CHARS:
            unsafe = True
        if i == len(filename_chars) - 1 and ch in HOST_FS_UNSAFE_END_CHARS:
            unsafe = True
        if ch >= "\ue000" and ch <= "\uf8ff":
            unsafe = True
        if unsafe or ch == "%":  # quote % too since we use it for quoting
            filename_chars[i] = "".join(
                f"%{byt:02X}" for byt in fat8_info["encode_8bit_charset"](filename[i])
            )
    host_fs_name = "".join(filename_chars)
    if not host_fs_name or host_fs_name[:1] == ".":
        host_fs_name = "(empty)" + host_fs_name
    natural_suffix = "".join(host_fs_name.split(".")[1:]).lower()
    host_fs_suffix = ".." + ".".join(
        sorted(
            sum(
                [
                    ["---"] if PSEUDO_ATTR_UNUSED in fattrs else [],
                    (
                        ["bas"]
                        if ATTR_NON_ASCII in fattrs
                        and natural_suffix not in ("bas", "n88", "nip", "hd")
                        else []
                    ),
                    (
                        ["bin"]
                        if ATTR_BINARY in fattrs
                        and natural_suffix not in ("bin", "cod")
                        else []
                    ),
                    ["era"] if PSEUDO_ATTR_DELETED in fattrs else [],
                    ["r-1"] if ATTR_1_RESERVED in fattrs else [],
                    ["r-2"] if ATTR_2_RESERVED in fattrs else [],
                    ["r-3"] if ATTR_3_RESERVED in fattrs else [],
                    ["r-o"] if ATTR_READ_ONLY in fattrs else [],
                    ["obf"] if ATTR_OBFUSCATED in fattrs else [],
                    (
                        ["asc"]
                        if not {ATTR_NON_ASCII, ATTR_BINARY}.intersection(fattrs)
                        and natural_suffix not in ("asc", "txt")
                        else []
                    ),
                    ["vfy"] if ATTR_READ_AFTER_WRITE in fattrs else [],
                ],
                [],
            )
        )
    )
    if host_fs_suffix == "..":
        host_fs_suffix = ""
    if "." in host_fs_name:
        host_fs_suffix = host_fs_suffix[len(".") :]
    return host_fs_name + host_fs_suffix


def extend_name(base_filename, name_tail):
    """Add more stuff at the end of a filename but before eny
    extensions.
    """
    parts = base_filename.split(".", 1)
    parts[0] += name_tail
    return ".".join(parts)


def analyze_metadata_track(track_and_sector_info, fat8_info):
    # parse metadata track; for directory entries, make matching names for the host file system
    metadata_sectors = track_and_sector_info["track_sector_map"].get(
        (fat8_info["metadata_track"], fat8_info["metadata_side"]), []
    )
    directory_entries = []
    fat_sectors = {}
    autorun_data = None
    raw_metadata_sectors = {}
    used_filenames = {}
    used_lower_fs_names = set()
    end_of_directory = False
    for sec_num, offset, data, sectors_in_track in sorted(metadata_sectors):
        for vsec_num in range(
            ((sec_num - 1) << fat8_info["fat8_sector_shift"]) + 1,
            (sec_num << fat8_info["fat8_sector_shift"]) + 1,
        ):
            vdata = data[
                fat8_info["fat8_sector_size"]
                * ((vsec_num - 1) % (1 << fat8_info["fat8_sector_shift"])) : fat8_info[
                    "fat8_sector_size"
                ]
                * (1 + ((vsec_num - 1) % (1 << fat8_info["fat8_sector_shift"])))
            ]
            raw_metadata_sectors[vsec_num] = vdata
            if vsec_num in fat8_info["dir_sector_indices"] and not end_of_directory:
                for i in range(0, 256, 16):
                    entry = vdata[i : i + 16]
                    raw_name = entry[0:6]
                    name = fat8_info["decode_8bit_charset"](
                        raw_name, preserve=NO_CONTROLS
                    )
                    raw_ext = entry[6:9]
                    ext = fat8_info["decode_8bit_charset"](
                        raw_ext, preserve=NO_CONTROLS
                    )
                    # two pseudo-attributes are encoded using special characters in the first byte of the filename
                    attr_mask = (
                        entry[9]
                        | (0x100 if entry[0] == 0x00 else 0x000)
                        | (0x200 if entry[0] == 0xFF else 0x000)
                    )
                    fattrs = set(
                        attr for mask, attr in ALL_ATTRS.items() if attr_mask & mask
                    )
                    cluster = entry[10]
                    host_fs_name = to_host_fs_name(
                        name, ext, fattrs, fat8_info=fat8_info
                    )
                    disambig = ""
                    while (
                        extend_name(host_fs_name.lower(), disambig)
                        in used_lower_fs_names
                    ):
                        disambig = f" ({1 + int(disambig.strip(' ()') or 0)})"
                    host_fs_name = extend_name(host_fs_name, disambig)
                    host_fs_deobf_name = to_host_fs_name(
                        name, ext, fattrs - {ATTR_OBFUSCATED}, fat8_info=fat8_info
                    )
                    disambig_deobf = ""
                    while (
                        extend_name(host_fs_deobf_name.lower(), disambig_deobf)
                        in used_lower_fs_names
                    ):
                        disambig_deobf = f" ({1 + int(disambig.strip(' ()') or 0)})"
                    host_fs_deobf_name = extend_name(host_fs_deobf_name, disambig_deobf)
                    if PSEUDO_ATTR_UNUSED in fattrs:
                        # directory listing terminates at the first unused entry
                        end_of_directory = True
                        break
                    used_lower_fs_names |= {host_fs_name.lower()}
                    if (
                        ATTR_OBFUSCATED in fattrs
                        and fat8_info["fat8_obfuscation"] is not None
                    ):
                        used_lower_fs_names |= {host_fs_deobf_name.lower()}
                    parsed_entry = dict(
                        idx=(vsec_num - 1) * 16 + i // 16 + 1,
                        host_fs_name=host_fs_name,
                        host_fs_deobf_name=host_fs_deobf_name,
                        fattrs=fattrs,
                        cluster=cluster,
                        name=name,
                        ext=ext,
                        chain=[],
                        errors=set(),
                        allocated_size=0,
                        raw_entry=entry,
                        file_data=None,
                    )
                    if PSEUDO_ATTR_DELETED not in fattrs:
                        other_entry = used_filenames.get(name + "." + ext)
                        if other_entry is not None:
                            parsed_entry["errors"] |= {"Duplicate filename"}
                            if parsed_entry["raw_entry"] != other_entry["raw_entry"]:
                                other_entry["errors"] |= {"Duplicate filename"}
                        else:
                            used_filenames[name + "." + ext] = parsed_entry
                    directory_entries.append(parsed_entry)
            elif vsec_num in fat8_info["fat_sector_indices"]:
                fat_sectors[vsec_num] = vdata
            elif vsec_num == fat8_info["autorun_sector_index"]:
                autorun_data = vdata
    return dict(
        directory_entries=directory_entries,
        fat_sectors=fat_sectors,
        autorun_data=autorun_data,
        raw_metadata_sectors=raw_metadata_sectors,
        used_filenames=used_filenames,
        used_lower_fs_names=used_lower_fs_names,
    )


def hexdump_entry_data(file_data, fattrs, fat8_info, output):
    for i in range(0, len(file_data), 16):
        row = f"{i:06X}: "
        drow = " "
        dvrow = vrow = "│"
        vtail = dvtail = "│"
        for j in range(i, i + 16):
            row += f" {file_data[j]:02X}" if j < len(file_data) else "   "
            drow += (
                f" {fat8_info['deobfuscate_byte'](j, file_data[j]):02X}"
                if j < len(file_data)
                else "   "
            )
            if j < len(file_data):
                ch = fat8_info["decode_8bit_charset"](
                    bytes([file_data[j - 1] if j else 0, file_data[j]]),
                    preserve=NO_CONTROLS,
                )[-1:]
                vrow += (
                    "."
                    if ch <= "\x1f" or ch == "\x7f" or ch >= "\ue000" and ch <= "\uf8ff"
                    else ch
                )
                dch = fat8_info["decode_8bit_charset"](
                    bytes(
                        [
                            (
                                fat8_info["deobfuscate_byte"](j - 1, file_data[j - 1])
                                if j
                                else 0
                            ),
                            fat8_info["deobfuscate_byte"](j, file_data[j]),
                        ]
                    ),
                    preserve=NO_CONTROLS,
                )[-1:]
                dvrow += (
                    "."
                    if dch <= "\x1f"
                    or dch == "\x7f"
                    or dch >= "\ue000"
                    and dch <= "\uf8ff"
                    else dch
                )
            else:
                vtail = "╭" + "─" * len(vtail[:-1]) + "╯"
                dvtail = "╭" + "─" * len(dvtail[:-1]) + "╯"
            if j % 8 == 7:
                row += " "
                drow += " "
        output.append(
            f"{row} {vrow}{vtail}"
            + (
                f"{drow} {dvrow}{dvtail}"
                if ATTR_OBFUSCATED in fattrs
                and fat8_info["fat8_obfuscation"] is not None
                else ""
            )
        )
    output.append(
        f"{len(file_data):06X}{'':53}╰{'─' * ((len(file_data) % 16) or 16)}╯{'' if ATTR_OBFUSCATED not in fattrs or fat8_info['fat8_obfuscation'] is None else ' ' * ((16 - ((len(file_data) % 16) or 16)) + 52) + '╰' + '─' * ((len(file_data) % 16) or 16) + '╯'}"
    )


def log_boot_sector(fat8_info, output):
    if fat8_info["boot_sector"] is not None:
        output.append(f"\n== Boot Sector (Track 0, Sector 1) =={'':22}╭{'─' * 16}╮")
        hexdump_entry_data(
            fat8_info["boot_sector"], set(), fat8_info=fat8_info, output=output
        )


def log_raw_directory_sectors(fat8_info, metadata_track_info, output):
    output.append("\n== Raw directory sectors ==")
    for vsec_num in sorted(fat8_info["dir_sector_indices"]):
        sector_data = metadata_track_info["raw_metadata_sectors"].get(vsec_num)
        if sector_data is not None:
            if sector_data == b"\xff" * len(sector_data):
                output.append(
                    f"\nDirectory Sector {vsec_num:2} unused: {len(sector_data)} 0xFF bytes"
                )
            else:
                output.append(f"\nDirectory Sector {vsec_num:2}{'':40}╭{'─' * 16}╮")
                hexdump_entry_data(
                    sector_data, set(), fat8_info=fat8_info, output=output
                )
        else:
            output.append(f"Missing directory sector {vsec_num:2}")


def log_autorun_data(fat8_info, metadata_track_info, output):
    if metadata_track_info["autorun_data"] is not None:
        output.append(
            f"\n== Autorun/ID Sector {fat8_info['autorun_sector_index']:2} =={'':33}╭{'─' * 16}╮"
        )
        hexdump_entry_data(
            metadata_track_info["autorun_data"],
            set(),
            fat8_info=fat8_info,
            output=output,
        )
        output.append(
            f"Disk attributes: {', '.join([ATTR_READ_ONLY if (1 << i) == 0x10 else ATTR_READ_AFTER_WRITE if (1 << 1) == 0x40 else 'UnknownAttr:0x%02X' % (1 << i) for i in range(8) if metadata_track_info['autorun_data'][0] & (1 << i)] or ['None'])}"
        )
        output.append(
            f"Number of files (0-15) ? {metadata_track_info['autorun_data'][1] if metadata_track_info['autorun_data'][1] != 0xFF else '(ask user)'}"
        )
        output.append(
            f"Payload: {fat8_info['decode_8bit_charset'](metadata_track_info['autorun_data'][2:].rstrip(bytes([0x00])).rstrip(b' '))}"
        )


def check_fat_sectors(fat8_info, metadata_track_info, output):
    first_fat_sector_idx = (
        sorted(metadata_track_info["fat_sectors"].keys())[0]
        if metadata_track_info["fat_sectors"]
        else None
    )
    fat1 = None
    if first_fat_sector_idx is not None:
        fat1 = metadata_track_info["fat_sectors"][first_fat_sector_idx]
        output.append(f"\n== FAT Sector {first_fat_sector_idx:2} =={'':40}╭{'─' * 16}╮")
        hexdump_entry_data(fat1, set(), fat8_info=fat8_info, output=output)
        usable_fat = True
        if fat1[FAT8_BOOT_SECTOR_CLUSTER] not in {
            FAT8_CHAIN_TERMINAL_LINK,
            FAT8_BOOT_SECTOR_CLUSTER,
        } | set(range(fat8_info["fat8_total_clusters"])) | set(
            range(
                FAT8_FINAL_CLUSTER_OFFSET,
                FAT8_FINAL_CLUSTER_OFFSET + fat8_info["fat8_sectors_per_cluster"] + 1,
            )
        ):
            output.append(
                f"Unusable first FAT, it does not reserve cluster 0x{FAT8_BOOT_SECTOR_CLUSTER:02X} for boot sector"
            )
            usable_fat = False
        for cluster_idx in sorted(fat8_info["metadata_cluster_indices"]):
            if fat1[cluster_idx] not in {FAT8_CHAIN_TERMINAL_LINK} | fat8_info[
                "metadata_cluster_indices"
            ] | set(
                range(
                    FAT8_FINAL_CLUSTER_OFFSET,
                    FAT8_FINAL_CLUSTER_OFFSET
                    + fat8_info["fat8_sectors_per_cluster"]
                    + 1,
                )
            ):
                output.append(
                    f"Unusable first FAT, it does not reserve cluster 0x{cluster_idx:02X} for metadata track"
                )
                usable_fat = False
        for i in range(FAT8_RESERVED_CLUSTERS, fat8_info["fat8_total_clusters"]):
            if fat1[i] not in set(range(fat8_info["fat8_total_clusters"])) | set(
                range(
                    FAT8_FINAL_CLUSTER_OFFSET,
                    FAT8_FINAL_CLUSTER_OFFSET
                    + fat8_info["fat8_sectors_per_cluster"]
                    + 1,
                )
            ) | {FAT8_CHAIN_TERMINAL_LINK, FAT8_UNALLOCATED_CLUSTER}:
                output.append(
                    f"Unusable first FAT, cluster 0x{i:02X} has value 0x{fat1[i]:02X}; should be one of {0:02X}..{fat8_info['fat8_total_clusters']-1:02X}, {FAT8_FINAL_CLUSTER_OFFSET:02X}..{FAT8_FINAL_CLUSTER_OFFSET + fat8_info['fat8_sectors_per_cluster']:02X}, {FAT8_CHAIN_TERMINAL_LINK:02X}, {FAT8_UNALLOCATED_CLUSTER:02X}"
                )
                usable_fat = False
        if not usable_fat:
            fat1 = None
            output.append("\n== No usable FAT!!! ==")
        else:
            output.append(
                "First FAT is usable: boot sector and metadata track are marked as reserved and cluster values are plausible"
            )
            output.append("\n== FAT Consistency Check ==")
            matches = {
                {
                    fat1[i] == sector_data[i]
                    for i in range(1, fat8_info["fat8_total_clusters"])
                }
                == {True}
                for sector_data in metadata_track_info["fat_sectors"].values()
            }
            if matches == {True}:
                output.append("FAT copies have matching allocations")
            else:
                output.append("FAT copies DO NOT match")
                for other_fat_sector_idx, other_fat in sorted(
                    metadata_track_info["fat_sectors"].items()
                )[1:]:
                    output.append(
                        f"\n== FAT Sector {other_fat_sector_idx:2} =={'':40}╭{'─' * 16}╮"
                    )
                    hexdump_entry_data(
                        other_fat, set(), fat8_info=fat8_info, output=output
                    )
    else:
        output.append("\n== No FAT!!! ==")
    return fat1


def analyze_fat_chains(fat8_info, fat1, metadata_track_info, output):
    if fat1 is not None:
        output.append(f"\n== FAT Chain Analysis ==")

    # follow FAT chains
    chained_blocks = {}
    for entry in metadata_track_info["directory_entries"]:
        chain = []
        errors = set()
        if fat1 is None:
            errors |= {"No FAT"}
        elif PSEUDO_ATTR_DELETED in entry["fattrs"]:
            errors |= {"Deleted"}
        elif PSEUDO_ATTR_UNUSED in entry["fattrs"]:
            errors |= {"Unused"}
        else:
            chain = [entry["cluster"]]
            if entry["cluster"] < FAT8_RESERVED_CLUSTERS:
                errors |= {"Reserved cluster at head of chain"}
            elif entry["cluster"] >= FAT8_FINAL_CLUSTER_OFFSET and entry[
                "cluster"
            ] not in (
                FAT8_CHAIN_TERMINAL_LINK,
                FAT8_UNALLOCATED_CLUSTER,
            ):
                errors |= {"Head of chain cannot be a block count"}
            elif (
                entry["cluster"] < FAT8_FINAL_CLUSTER_OFFSET
                and entry["cluster"] >= fat8_info["fat8_total_clusters"]
            ):
                errors |= {"Head of chain falls outside of disk"}
            while chain[-1] < FAT8_FINAL_CLUSTER_OFFSET and not errors:
                next_link = fat1[chain[-1]]
                if next_link < FAT8_FINAL_CLUSTER_OFFSET:
                    if next_link < FAT8_RESERVED_CLUSTERS:
                        errors |= {"Reserved cluster in chain"}
                    elif next_link >= fat8_info["fat8_total_clusters"]:
                        errors |= {"Chain entry falls outside of disk"}
                    elif next_link in chain:
                        errors |= {"Cycle in FAT chain"}
                chain += [next_link]
            if (FAT8_UNALLOCATED_CLUSTER in chain) and not errors:
                errors |= {"Unallocated cluster in FAT chain"}
            if (
                chain[-1] < FAT8_FINAL_CLUSTER_OFFSET
                or chain[-1] == FAT8_UNALLOCATED_CLUSTER
            ) and not errors:
                errors |= {"Unterminated FAT chain"}
            elif (
                chain[-1]
                > FAT8_FINAL_CLUSTER_OFFSET + fat8_info["fat8_sectors_per_cluster"]
                and chain[-1] != FAT8_CHAIN_TERMINAL_LINK
            ) and not errors:
                errors |= {
                    "Sector count for final cluster exceeds sectors-per-cluster limit"
                }
        if not errors:
            for link in chain[:-1]:
                other_entry = chained_blocks.get(link)
                if other_entry is not None:
                    if entry["raw_entry"][9:11] != other_entry["raw_entry"][9:11]:
                        errors |= {f"Overlapping allocation {link:02X}"}
                        other_entry["errors"] |= {f"Overlapping allocation {link:02X}"}
                else:
                    chained_blocks[link] = entry
        if not errors:
            allocated_size = fat8_info["fat8_bytes_per_cluster"] * len(chain[:-1])
            if chain[-1] >= FAT8_FINAL_CLUSTER_OFFSET and chain[-1] not in (
                FAT8_CHAIN_TERMINAL_LINK,
                FAT8_UNALLOCATED_CLUSTER,
            ):
                allocated_size -= fat8_info["fat8_bytes_per_cluster"]
                allocated_size += fat8_info["fat8_sector_size"] * (
                    chain[-1] - FAT8_FINAL_CLUSTER_OFFSET
                )
            entry["allocated_size"] = allocated_size
        entry["chain"] = chain
        entry["errors"] = errors


def quote_filename(filename):
    for ch in list(filename):
        if ord(ch) <= 0x20 or ord(ch) >= 0x7F:
            return f'"{filename}"'
    return filename


def reconstruct_file_data(
    track_and_sector_info, fat8_info, metadata_track_info, output
):
    # reconstructs file data while analyzing FAT chains
    for idx, entry in sorted(
        (ent["idx"], ent) for ent in metadata_track_info["directory_entries"]
    ):
        chain = entry["chain"]
        errors = entry["errors"]
        unlisted = True if UNLISTED_ENTRY_ATTRS.intersection(entry["fattrs"]) else False
        if not errors:
            sep = (
                "*"
                if ATTR_BINARY in entry["fattrs"]
                else "." if ATTR_NON_ASCII in entry["fattrs"] else " "
            )
            output.append(
                f"{entry['idx']:3}. {'[' if unlisted else ' '}{entry['name']}{sep}{entry['ext']}{']' if unlisted else ' '} {(entry['allocated_size'] + fat8_info['fat8_bytes_per_cluster'] - 1) // fat8_info['fat8_bytes_per_cluster']:3d} {quote_filename(entry['host_fs_name'])+('' if ATTR_OBFUSCATED not in entry['fattrs'] or fat8_info['fat8_obfuscation'] is None else ', ' + quote_filename(entry['host_fs_deobf_name'])):40} {'':8} ATTRS={entry['fattrs'] or None}  START={entry['cluster']:02X} CHAIN={'→'.join(f'{cluster:02X}' for cluster in entry['chain']) if entry['chain'] else None} STATUS={entry['errors'] or 'OK'}"
            )
            file_data = b""
            final_cluster_offset = 0
            for i, cluster in enumerate(chain[:-1]):
                if file_data is None:
                    # due to a previous error
                    output.append(
                        f"Chain {entry['cluster']:02X} Cluster {cluster:02X}: Skipped due to preceding error"
                    )
                    break
                in_final_cluster = i == len(chain) - 2
                max_fat8_sectors_in_cluster = fat8_info["fat8_sectors_per_cluster"]
                if in_final_cluster:
                    final_cluster_offset = len(file_data)
                    if (
                        chain[-1] >= FAT8_FINAL_CLUSTER_OFFSET
                        and chain[-1] < FAT8_CHAIN_TERMINAL_LINK
                    ):
                        max_fat8_sectors_in_cluster = (
                            chain[-1] - FAT8_FINAL_CLUSTER_OFFSET
                        )
                if fat8_info["side_is_cluster_lsb"]:
                    cluster_track = (
                        cluster
                        // fat8_info["fat8_sides"]
                        // fat8_info["fat8_clusters_per_track"]
                    )
                    cluster_side = cluster % fat8_info["fat8_sides"]
                    first_cluster_sec_num = 1 + (
                        cluster
                        // fat8_info["fat8_sides"]
                        % fat8_info["fat8_clusters_per_track"]
                    ) * (
                        fat8_info["fat8_sectors_per_track"]
                        // fat8_info["fat8_clusters_per_track"]
                    )
                else:
                    cluster_track = (
                        cluster
                        // fat8_info["fat8_clusters_per_track"]
                        // fat8_info["fat8_sides"]
                    )
                    cluster_side = (
                        cluster
                        // fat8_info["fat8_clusters_per_track"]
                        % fat8_info["fat8_sides"]
                    )
                    first_cluster_sec_num = 1 + (
                        cluster % fat8_info["fat8_clusters_per_track"]
                    ) * (
                        fat8_info["fat8_sectors_per_track"]
                        // fat8_info["fat8_clusters_per_track"]
                    )
                cluster_sectors = track_and_sector_info["track_sector_map"].get(
                    (cluster_track, cluster_side), []
                )
                cluster_sector_list = []
                for cluster_sec_num in range(
                    first_cluster_sec_num,
                    first_cluster_sec_num + max_fat8_sectors_in_cluster,
                ):
                    cluster_sector_data = None
                    in_final_sector = (
                        cluster_sec_num
                        == first_cluster_sec_num + max_fat8_sectors_in_cluster - 1
                    )
                    if file_data is None:
                        # due to a previous error
                        break
                    for (
                        sec_num,
                        actual_data_offset,
                        sector_data,
                        sectors_in_track,
                    ) in cluster_sectors:
                        for vsec_num in range(
                            ((sec_num - 1) << fat8_info["fat8_sector_shift"]) + 1,
                            (sec_num << fat8_info["fat8_sector_shift"]) + 1,
                        ):
                            if vsec_num == cluster_sec_num:
                                vsector_data = sector_data[
                                    fat8_info["fat8_sector_size"]
                                    * (
                                        (vsec_num - 1)
                                        % (1 << fat8_info["fat8_sector_shift"])
                                    ) : fat8_info["fat8_sector_size"]
                                    * (
                                        1
                                        + (
                                            (vsec_num - 1)
                                            % (1 << fat8_info["fat8_sector_shift"])
                                        )
                                    )
                                ]
                                cluster_sector_data = vsector_data
                                if (
                                    in_final_cluster
                                    and in_final_sector
                                    and cluster_sector_data.rstrip(b"\0")[-1:]
                                    == b"\x1a"
                                ):
                                    cluster_sector_data = cluster_sector_data.rstrip(
                                        b"\0"
                                    )[:-1]
                                cluster_sector_list += [
                                    (
                                        sec_num,
                                        actual_data_offset,
                                        sector_data,
                                        sectors_in_track,
                                        vsec_num,
                                        cluster_sector_data,
                                    )
                                ]
                                break
                        if cluster_sector_data is not None:
                            break
                    if cluster_sector_data is None:
                        entry["errors"] |= {"Missing sector"}
                        if cluster_sector_list:
                            output.append(
                                f"{'':8}Cluster {cluster:02X}, Track {cluster_track:3}, Side {cluster_side}: "
                                + ", ".join(
                                    f"{s[4]:2}:{len(s[5])}" for s in cluster_sector_list
                                )
                            )
                        output.append(
                            f"Cluster {cluster:02X}: missing track {cluster_track:3}, side {cluster_side}, sector {cluster_sec_num:2} !!!"
                        )
                        file_data = None
                        break
                    file_data += cluster_sector_data
                if file_data is not None:
                    output.append(
                        f"{'':8}Cluster {cluster:02X}, Track {cluster_track:3}, Side {cluster_side}: "
                        + ", ".join(
                            f"{s[4]:2}:{len(s[5])}" for s in cluster_sector_list
                        )
                    )
            entry["file_data"] = file_data


def log_directory_entries(fat8_info, metadata_track_info, output):
    output.append("\n== Directory Entries ==")

    for idx, entry in sorted(
        (ent["idx"], ent) for ent in metadata_track_info["directory_entries"]
    ):
        unlisted = True if UNLISTED_ENTRY_ATTRS.intersection(entry["fattrs"]) else False
        sep = (
            "*"
            if ATTR_BINARY in entry["fattrs"]
            else "." if ATTR_NON_ASCII in entry["fattrs"] else " "
        )
        output.append(
            f"{entry['idx']:3}. {'[' if unlisted else ' '}{entry['name']}{sep}{entry['ext']}{']' if unlisted else ' '} {(entry['allocated_size'] + fat8_info['fat8_bytes_per_cluster'] - 1) // fat8_info['fat8_bytes_per_cluster']:3d} {quote_filename(entry['host_fs_name'])+('' if ATTR_OBFUSCATED not in entry['fattrs'] or fat8_info['fat8_obfuscation'] is None else ', ' + quote_filename(entry['host_fs_deobf_name'])):40} {len(entry['file_data'] or b''):8} ATTRS={entry['fattrs'] or None}  START={entry['cluster']:02X} CHAIN={'→'.join(f'{cluster:02X}' for cluster in entry['chain']) if entry['chain'] else None} STATUS={entry['errors'] or 'OK'}"
        )


def log_file_contents(fat8_info, fat1, metadata_track_info, output):
    if fat1 is not None:
        output.append(f"\n== File Contents ==")

        for idx, entry in sorted(
            (ent["idx"], ent) for ent in metadata_track_info["directory_entries"]
        ):
            unlisted = (
                True if UNLISTED_ENTRY_ATTRS.intersection(entry["fattrs"]) else False
            )
            errors = entry["errors"]
            if not errors:
                sep = (
                    "*"
                    if ATTR_BINARY in entry["fattrs"]
                    else "." if ATTR_NON_ASCII in entry["fattrs"] else " "
                )
                output.append(
                    f"{entry['idx']:3}. {'[' if unlisted else ' '}{entry['name']}{sep}{entry['ext']}{']' if unlisted else ' '} {(entry['allocated_size'] + fat8_info['fat8_bytes_per_cluster'] - 1) // fat8_info['fat8_bytes_per_cluster']:3d} {quote_filename(entry['host_fs_name']):27} {len(entry['file_data'] or b''):8} ╭{'─' * 16}╮"
                    + (
                        ""
                        if ATTR_OBFUSCATED not in entry["fattrs"]
                        or fat8_info["fat8_obfuscation"] is None
                        else f" {quote_filename(entry['host_fs_deobf_name']):50} ╭{'─' * 16}╮"
                    )
                )
                if entry["file_data"] is not None:
                    hexdump_entry_data(
                        entry["file_data"],
                        entry["fattrs"],
                        fat8_info=fat8_info,
                        output=output,
                    )


def print_log(output):
    print("\n".join(output))


def save_log(outdir, output):
    log_filename = os.path.join(outdir, "_fat8_d88_output.txt")
    with open(log_filename, "w", encoding="utf-8") as f:
        print(f"writing {log_filename}")
        f.write("\n".join(output))


def utf8_dump_filename(filename):
    parts = filename.rsplit(".", 1)
    return "_".join(parts) + "_utf8_dump.txt"


def extract_boot_sector(outdir, fat8_info):
    if fat8_info["boot_sector"] is not None:
        boot_sector_filename = os.path.join(outdir, "_boot_sector.dat")
        with open(boot_sector_filename, "wb") as f:
            print(f"writing {boot_sector_filename}")
            f.write(fat8_info["boot_sector"])
        with open(utf8_dump_filename(boot_sector_filename), "w", encoding="utf-8") as f:
            print(f"writing {utf8_dump_filename(boot_sector_filename)}")
            f.write(fat8_info["decode_8bit_charset"](fat8_info["boot_sector"]))


def extract_raw_directory_sectors(outdir, fat8_info, metadata_track_info):
    for vsec_num in sorted(fat8_info["dir_sector_indices"]):
        sector_data = metadata_track_info["raw_metadata_sectors"].get(vsec_num)
        if sector_data is None:
            continue
        if sector_data == b"\xff" * len(sector_data):
            # Do not write out unused directory sector files
            continue
        dir_sector_filename = os.path.join(outdir, f"_dir_sector_{vsec_num}.dat")
        with open(dir_sector_filename, "wb") as f:
            print(f"writing {dir_sector_filename}")
            f.write(sector_data)
        with open(utf8_dump_filename(dir_sector_filename), "w", encoding="utf-8") as f:
            print(f"writing {utf8_dump_filename(dir_sector_filename)}")
            f.write(fat8_info["decode_8bit_charset"](sector_data))


def extract_autorun_data(outdir, fat8_info, metadata_track_info):
    if metadata_track_info["autorun_data"] is not None:
        autorun_filename = os.path.join(outdir, "_AutoRun.dat")
        with open(autorun_filename, "wb") as f:
            print(f"writing {autorun_filename}")
            f.write(metadata_track_info["autorun_data"])
        with open(utf8_dump_filename(autorun_filename), "w", encoding="utf-8") as f:
            print(f"writing {utf8_dump_filename(autorun_filename)}")
            f.write(
                fat8_info["decode_8bit_charset"](metadata_track_info["autorun_data"])
            )


def extract_fat_sectors(outdir, fat8_info, metadata_track_info):
    for fat_sector_idx, fat in sorted(metadata_track_info["fat_sectors"].items()):
        fat_filename = os.path.join(outdir, f"_fat_sector_{fat_sector_idx}.dat")
        with open(fat_filename, "wb") as f:
            print(f"writing {fat_filename}")
            f.write(fat)
        with open(utf8_dump_filename(fat_filename), "w", encoding="utf-8") as f:
            print(f"writing {utf8_dump_filename(fat_filename)}")
            f.write(fat8_info["decode_8bit_charset"](fat))


def extract_file_contents(outdir, fat8_info, metadata_track_info):
    for idx, entry in sorted(
        (ent["idx"], ent) for ent in metadata_track_info["directory_entries"]
    ):
        errors = entry["errors"]
        if not errors:
            entry_filename = os.path.join(outdir, entry["host_fs_name"])
            file_data = entry["file_data"]
            with open(entry_filename, "wb") as f:
                print(f"writing {entry_filename}")
                f.write(file_data)
            with open(utf8_dump_filename(entry_filename), "w", encoding="utf-8") as f:
                print(f"writing {utf8_dump_filename(entry_filename)}")
                f.write(fat8_info["decode_8bit_charset"](file_data))
            if (
                ATTR_OBFUSCATED in entry["fattrs"]
                and fat8_info["fat8_obfuscation"] is not None
            ):
                file_deobf_data = bytes(
                    [
                        fat8_info["deobfuscate_byte"](i, byt)
                        for i, byt in enumerate(file_data)
                    ]
                )
                entry_deobf_filename = os.path.join(outdir, entry["host_fs_deobf_name"])
                with open(entry_deobf_filename, "wb") as f:
                    print(f"writing {entry_deobf_filename}")
                    f.write(file_deobf_data)
                with open(
                    utf8_dump_filename(entry_deobf_filename), "w", encoding="utf-8"
                ) as f:
                    print(f"writing {utf8_dump_filename(entry_deobf_filename)}")
                    f.write(fat8_info["decode_8bit_charset"](file_deobf_data))


def extract_everything(disk_info, d88_path, fat8_info, metadata_track_info, output):
    outdir = (
        os.path.splitext(os.path.basename(d88_path))[0]
        + f"{disk_info['disk_suffix']} [FAT8 Contents]"
    )

    disambig = ""
    while os.path.exists(outdir + disambig):
        disambig = f" ({1 + int(disambig.strip(' ()') or 0)})"
    outdir += disambig

    print("\n== Extracting ==")
    print(f"mkdir {outdir}")
    os.mkdir(outdir)
    save_log(outdir=outdir, output=output)
    extract_boot_sector(outdir=outdir, fat8_info=fat8_info)
    extract_raw_directory_sectors(
        outdir=outdir, fat8_info=fat8_info, metadata_track_info=metadata_track_info
    )
    extract_autorun_data(
        outdir=outdir, fat8_info=fat8_info, metadata_track_info=metadata_track_info
    )
    extract_fat_sectors(
        outdir=outdir, fat8_info=fat8_info, metadata_track_info=metadata_track_info
    )
    extract_file_contents(
        outdir=outdir, fat8_info=fat8_info, metadata_track_info=metadata_track_info
    )
    print(f"\nDone.{disk_info['disk_suffix']}")


def fat8_d88_tool(d88_path, d88_data, disk_idx=1):
    output = start_log()
    disk_info = analyze_disk(d88_data=d88_data, disk_idx=disk_idx)
    log_disk_information(disk_info=disk_info, output=output)
    track_and_sector_info = analyze_tracks_and_sectors(
        d88_data=d88_data, disk_info=disk_info, output=output
    )
    fat8_info = analyze_fat8_fmt(track_and_sector_info=track_and_sector_info)
    log_fmt_diagnostics(
        track_and_sector_info=track_and_sector_info, fat8_info=fat8_info, output=output
    )
    metadata_track_info = analyze_metadata_track(
        track_and_sector_info=track_and_sector_info, fat8_info=fat8_info
    )
    log_boot_sector(fat8_info=fat8_info, output=output)
    log_raw_directory_sectors(
        fat8_info=fat8_info, metadata_track_info=metadata_track_info, output=output
    )
    log_autorun_data(
        fat8_info=fat8_info, metadata_track_info=metadata_track_info, output=output
    )
    fat1 = check_fat_sectors(
        fat8_info=fat8_info, metadata_track_info=metadata_track_info, output=output
    )
    analyze_fat_chains(
        fat8_info=fat8_info,
        fat1=fat1,
        metadata_track_info=metadata_track_info,
        output=output,
    )
    reconstruct_file_data(
        track_and_sector_info=track_and_sector_info,
        fat8_info=fat8_info,
        metadata_track_info=metadata_track_info,
        output=output,
    )
    log_directory_entries(
        fat8_info=fat8_info, metadata_track_info=metadata_track_info, output=output
    )
    log_file_contents(
        fat8_info=fat8_info,
        fat1=fat1,
        metadata_track_info=metadata_track_info,
        output=output,
    )
    print_log(output=output)
    extract_everything(
        disk_info=disk_info,
        d88_path=d88_path,
        fat8_info=fat8_info,
        metadata_track_info=metadata_track_info,
        output=output,
    )
    if len(d88_data) > disk_info["disk_sz"]:
        fat8_d88_tool(d88_path, d88_data[disk_info["disk_sz"] :], disk_idx + 1)


def smoke_test_everything():
    smoke_test_pc98_8bit_charset()
    smoke_test_pc6001_8bit_charset()
    smoke_test_pc98_deobfuscation()
    smoke_test_p88_deobfuscation()


def main():
    if len(sys.argv) < 2:
        print("Usage: python fat8_d88_tool.py <file.d88> [...]")
        sys.exit(1)
    for d88_path in sys.argv[1:]:
        with open(d88_path, "rb") as f:
            d88_data = f.read()
            fat8_d88_tool(d88_path, d88_data)


smoke_test_everything()  # do this at import time so a broken module
# gets noticed as soon as possible

if __name__ == "__main__":
    main()
