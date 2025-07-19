#!/usr/bin/env python3

from pathlib import Path

import codecs
import os.path
import sys
import unicodedata

NO_CONTROLS = b''
MINIMAL_CONTROLS = b'\0\r\n\x1A\x7F'
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
PC98_8BIT_CHARSET = ''.join([
    '␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬',
    ' !"#$%&\'()*+,-./0123456789:;<=>?',
    '@ABCDEFGHIJKLMNOPQRSTUVWXYZ[¥]^_',
    '`abcdefghijklmnopqrstuvwxyz{¦}~␡',
    '▁▂▃▄▅▆▇█▏▎▍▌▋▊▉┼┴┬┤├▔─│▕┌┐└┘╭╮╰╯',
    '\uf8f0｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ',
    'ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ',
    '═╞╪╡◢◣◥◤♠♥♦♣•￮╱╲╳円年月日時分秒\uf8f4\uf8f5\uf8f6\uf8f7\N{reverse solidus}\uf8f1\uf8f2\uf8f3',
])
assert len(PC98_8BIT_CHARSET) == 256
PC98_8BIT_CHARMAP = {
    PC98_8BIT_CHARSET[i]: bytes([i])
    for
    i in range(256)
}
PC98_8BIT_CHARMAP_COMPAT = {
    unicodedata.normalize('NFKD', key): value
    for
    key, value in
    PC98_8BIT_CHARMAP.items()
    if unicodedata.normalize('NFKD', key) != key
}

def encode_pc98_8bit_charset(s, try_harder=True):
    s = ''.join([
        unicodedata.normalize('NFKD', s[i:i+1])
        if unicodedata.name(s[i:i+1], '?').lower().startswith('katakana letter')
        else
        s[i:i+1]
        for i in range(len(s))
    ])
    byts, chars_consumed, num_chars = b'', 0, len(s)
    while chars_consumed < num_chars:
        ch = s[chars_consumed]
        byt = PC98_8BIT_CHARMAP.get(ch, PC98_8BIT_CHARMAP_COMPAT.get(ch)) or (bytes([ord(ch)]) if ord(ch) <= 0x7F else None)
        if byt is None and try_harder:
            cch = unicodedata.normalize('NFKD', ch)
            byt = PC98_8BIT_CHARMAP.get(cch, PC98_8BIT_CHARMAP_COMPAT.get(cch)) or (bytes([ord(cch)]) if ord(cch) <= 0x7F else None)
        if byt is None:
            raise UnicodeEncodeError('pc98-8bit', s, chars_consumed, chars_consumed + 1, f"no mapping for U+{ord(ch):04X} {unicodedata.name(ch, repr(ch))}")
        byts += byt
        chars_consumed += 1
    return byts

def decode_pc98_8bit_charset(byts, preserve=MINIMAL_CONTROLS):
    s, bytes_consumed, num_bytes = '', 0, len(byts)
    while bytes_consumed < num_bytes:
        byt = byts[bytes_consumed]
        s += chr(byt) if byt in preserve else PC98_8BIT_CHARSET[byt]
        bytes_consumed += 1
    round_trip_byts = encode_pc98_8bit_charset(s)
    assert byts == round_trip_byts, UnicodeDecodeError('pc98-8bit', byts, 0, num_bytes, f"round-trip failure for result:\n {repr(byts)}, got:\n {repr(round_trip_byts)}")
    return s

def smoke_test_pc98_8bit_charset():
    assert decode_pc98_8bit_charset(b'') == ''
    assert encode_pc98_8bit_charset('') == b''
    round_trip_test_failures = {
        encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i]))): bytes([i])
        for i in range(256)
        if encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i]))) != bytes([i])
    }
    round_trip_test_failures |= {
        encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEE]))): bytes([i, 0xEE])
        for i in range(256)
        if encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEE]))) != bytes([i, 0xEE])
    }
    round_trip_test_failures |= {
        encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEF]))): bytes([i, 0xEF])
        for i in range(256)
        if encode_pc98_8bit_charset(decode_pc98_8bit_charset(bytes([i, 0xEF]))) != bytes([i, 0xEF])
    }
    assert not round_trip_test_failures, round_trip_test_failures
    unicode_test = '\r\n'.join((
        '╲￮╱ I ♥ PC98! \\o/',
        'ピーシーキュウハチガダイスキデス!',
        'NECノ「PC-8800」ヤ「PC-9800」シリーズ ノ パソコン ガ ニンキデシタガ、ゴゾンジデスカ？',
        '「！？」　･･･',
        '│|¦~▔-ｰ─_▁',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭￪╮ ++-+  /\\ ',
        '├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ ￩┼￫ ++-+ /XX\\',
        '││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰￬╯ ¦|.¦ \\XX/',
        '└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ',
        '▊▋▌▍▎▏█▇▆▅▄▃▂',
        '␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡',
    )) + '\x1A\x00'
    expected_8bit = b'\r\n'.join((
        b'\xef\xed\xee I \xe9 PC98! \xfco/',
        b'\xCB\xDF\xB0\xBC\xB0\xB7\xAD\xB3\xCA\xC1\xB6\xDE\xC0\xDE\xB2\xBD\xB7\xC3\xDE\xBD!',
        b'NEC\xc9\xa2PC-8800\xa3\xd4\xa2PC-9800\xa3\xbc\xd8\xb0\xbd\xde \xc9 \xca\xdf\xbf\xba\xdd \xb6\xde \xc6\xdd\xb7\xc3\xde\xbc\xc0\xb6\xde\xa4\xba\xde\xbf\xde\xdd\xbc\xde\xc3\xde\xbd\xb6?',
        b'\xa2!?\xa3 \xa5\xa5\xa5',
        b'\x96||~\x94-\xb0\x95_\x80',
        b'\\0=0\xf1',
        b'2025\xf207\xf318\xf4 14\xf511\xf616\xf7',
        b'\x98\x91\x95\x99\x9c\x91\x95\x9d \x80\x80  \xee\xef  \xe4\xe5  \x9c\x1e\x9d ++-+  /\xfc ',
        b'\x93\x8f\x95\x92\xe1\xe2\xe0\xe3\x97\x8f\x95\x88\xee\xf0\xf0\xef\xe4\xe7\xe6\xe5 \x1d\x8f\x1c ++-+ /XX\xfc',
        b'\x96\x96\x8e\x96\x96\x96\xec\x96\x97\x96\xa5\x88\xef\xf0\xf0\xee\xe6\xe5\xe4\xe7 \x9e\x1f\x9f ||.| \xfcXX/',
        b'\x9a\x90\x95\x9b\x9e\x90\x95\x9f \x94\x94  \xef\xee  \xe6\xe7.<>O[]++-+  \xfc/ ',
        bytes([ 0x80 + 13 - i for i in range(13) ]),
        bytes([ i for i in range(0x20) ] + [ 0x7F ]),
    )) + b'\x1A\x00'
    assert encode_pc98_8bit_charset(unicode_test) == expected_8bit, f"encode_pc98_8bit_charset({repr(unicode_test)}) returned:\n {repr(encode_pc98_8bit_charset(unicode_test))}, expecting:\n {repr(expected_8bit)}"
    try:
        unexpected_8bit = encode_pc98_8bit_charset(unicode_test, try_harder=False)
        assert False, f"Expected a UnicodeEncodeError for encode_pc98_8bit_charset({repr(unicode_test)}, try_harder=False) but no error was raised"
    except UnicodeEncodeError:
        pass
    except Exception as e:
        assert False, f"Expected a UnicodeEncodeError for encode_pc98_8bit_charset({repr(unicode_test)}, try_harder=False) but {repr(e)} was raised instead"
    pc98_8bit_test = expected_8bit
    expected_unicode = '\r\n'.join((
        '╲￮╱ I ♥ PC98! \\o/',
        'ﾋﾟｰｼｰｷｭｳﾊﾁｶﾞﾀﾞｲｽｷﾃﾞｽ!',
        'NECﾉ｢PC-8800｣ﾔ｢PC-9800｣ｼﾘｰｽﾞ ﾉ ﾊﾟｿｺﾝ ｶﾞ ﾆﾝｷﾃﾞｼﾀｶﾞ､ｺﾞｿﾞﾝｼﾞﾃﾞｽｶ?',
        '｢!?｣ ･･･',
        '│¦¦~▔-ｰ─_▁',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭￪╮ ++-+  /\\ ',
        '├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ ￩┼￫ ++-+ /XX\\',
        '││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰￬╯ ¦¦.¦ \\XX/',
        '└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ',
        '▊▋▌▍▎▏█▇▆▅▄▃▂',
        '\x00␁␂␃␄␅␆␇␈␉\n␋␌\r␎␏␐␑␒␓␔␕␖␗␘␙\x1A␛￫￩￪￬\x7F',
    )) + '\x1A\x00'
    assert decode_pc98_8bit_charset(pc98_8bit_test) == expected_unicode, f"decode_pc98_8bit_charset({repr(pc98_8bit_test)}) returned:\n {repr(decode_pc98_8bit_charset(pc98_8bit_test))}, expecting:\n {repr(expected_unicode)}"
    assert encode_pc98_8bit_charset(expected_unicode, try_harder=False) == pc98_8bit_test, f"encode_pc98_8bit_charset({repr(expected_unicode)}, try_harder=False) returned:\n {repr(encode_pc98_8bit_charset(expected_unicode, try_harder=False))}, expecting:\n {repr(pc98_8bit_test)}"
    expected_no_controls_unicode = '␍␊'.join((
        '╲￮╱ I ♥ PC98! \\o/',
        'ﾋﾟｰｼｰｷｭｳﾊﾁｶﾞﾀﾞｲｽｷﾃﾞｽ!',
        'NECﾉ｢PC-8800｣ﾔ｢PC-9800｣ｼﾘｰｽﾞ ﾉ ﾊﾟｿｺﾝ ｶﾞ ﾆﾝｷﾃﾞｼﾀｶﾞ､ｺﾞｿﾞﾝｼﾞﾃﾞｽｶ?',
        '｢!?｣ ･･･',
        '│¦¦~▔-ｰ─_▁',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭￪╮ ++-+  /\\ ',
        '├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ ￩┼￫ ++-+ /XX\\',
        '││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰￬╯ ¦¦.¦ \\XX/',
        '└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ',
        '▊▋▌▍▎▏█▇▆▅▄▃▂',
        '␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡',
    )) + '␚␀'
    assert decode_pc98_8bit_charset(pc98_8bit_test, preserve=NO_CONTROLS) == expected_no_controls_unicode, f"decode_pc98_8bit_charset({repr(pc98_8bit_test)}, preserve=NO_CONTROLS) returned:\n {repr(decode_pc98_8bit_charset(pc98_8bit_test, preserve=NO_CONTROLS))}, expecting:\n {repr(expected_no_controls_unicode)}"
    expected_ascii_controls_unicode = '\r\n'.join((
        '╲￮╱ I ♥ PC98! \\o/',
        'ﾋﾟｰｼｰｷｭｳﾊﾁｶﾞﾀﾞｲｽｷﾃﾞｽ!',
        'NECﾉ｢PC-8800｣ﾔ｢PC-9800｣ｼﾘｰｽﾞ ﾉ ﾊﾟｿｺﾝ ｶﾞ ﾆﾝｷﾃﾞｼﾀｶﾞ､ｺﾞｿﾞﾝｼﾞﾃﾞｽｶ?',
        '｢!?｣ ･･･',
        '│¦¦~▔-ｰ─_▁',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐╭┬─╮ ▁▁  ╱╲  ◢◣  ╭\x1E╮ ++-+  /\\ ',
        '├┼─┤╞╪═╡▕┼─▏╱╳╳╲◢◤◥◣ \x1D┼\x1C ++-+ /XX\\',
        '││▉│││•│▕│･▏╲╳╳╱◥◣◢◤ ╰\x1F╯ ¦¦.¦ \\XX/',
        '└┴─┘╰┴─╯ ▔▔  ╲╱  ◥◤.<>O[]++-+  \\/ ',
        '▊▋▌▍▎▏█▇▆▅▄▃▂',
        ''.join([ chr(i) for i in range(0x20) ]) + '\x7F',
    )) + '\x1A\x00'
    assert decode_pc98_8bit_charset(pc98_8bit_test, preserve=ASCII_CONTROLS) == expected_ascii_controls_unicode, f"decode_pc98_8bit_charset({repr(pc98_8bit_test)}, preserve=ASCII_CONTROLS) returned:\n {repr(decode_pc98_8bit_charset(pc98_8bit_test, preserve=ASCII_CONTROLS))}, expecting:\n {repr(expected_ascii_controls_unicode)}"

smoke_test_pc98_8bit_charset()

# i am sure this is not the best way to solve this. this mapping
# should work OK for PC-6001/mkII/SR and PC-6601/SR. it does not
# handle the alternate character set shift sequences well. it also
# does not handle Kanji or PC-6001A charset at all! the mapping is
# intentionally close to the PC-98 one above. the hiragana and kanji
# here should all be half-width ones, but Unicode is missing those so
# we live with fullwidth instead.
PC6001_8BIT_CHARSET = ''.join([
    '␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬',
    ' !"#$%&\'()*+,-./0123456789:;<=>?',
    '@ABCDEFGHIJKLMNOPQRSTUVWXYZ[¥]^_',
    '`abcdefghijklmnopqrstuvwxyz{¦}~␡',
    '♠♥♦♣￮•をぁぃぅぇぉゃゅょっーあいうえおかきくけこさしすせそ',
    '\uf8f0｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ',
    'ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ',
    'たちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん\uf8f2\uf8f3',
])
assert len(PC6001_8BIT_CHARSET) == 256
PC6001_8BIT_ALTCHARSET = ''.join([
    '\uf8f1月火水木金土日年円時分秒百千万',
    'π┴┬┤├┼│─┌┐└┘╳大中小',
])
assert len(PC6001_8BIT_ALTCHARSET) == 32
PC6001_8BIT_CHARMAP = {
    PC6001_8BIT_CHARSET[i]: bytes([i])
    for
    i in range(256)
} | {
    PC6001_8BIT_ALTCHARSET[i]: bytes([0x14, i + 0x30])
    for
    i in range(32)
}
PC6001_8BIT_CHARMAP_COMPAT = {
    unicodedata.normalize('NFKD', key): value
    for
    key, value in
    PC6001_8BIT_CHARMAP.items()
    if unicodedata.normalize('NFKD', key) != key
}

def encode_pc6001_8bit_charset(s, try_harder=True):
    s = ''.join([
        unicodedata.normalize('NFKD', s[i:i+1])
        if (unicodedata.name(s[i:i+1], '?').lower().startswith('hiragana letter')
            or
            unicodedata.name(s[i:i+1], '?').lower().startswith('katakana letter'))
        else
        s[i:i+1]
        for i in range(len(s))
    ])
    byts, chars_consumed, num_chars = b'', 0, len(s)
    while chars_consumed < num_chars:
        ch = s[chars_consumed]
        byt = PC6001_8BIT_CHARMAP.get(ch, PC6001_8BIT_CHARMAP_COMPAT.get(ch)) or (bytes([ord(ch)]) if ord(ch) <= 0x7F else None)
        if byt is None and try_harder:
            cch = unicodedata.normalize('NFKD', ch)
            byt = PC6001_8BIT_CHARMAP.get(cch, PC6001_8BIT_CHARMAP_COMPAT.get(cch)) or (bytes([ord(cch)]) if ord(cch) <= 0x7F else None)
        if byt is None:
            raise UnicodeEncodeError('pc6001-8bit', s, chars_consumed, chars_consumed + 1, f"no mapping for U+{ord(ch):04X} {unicodedata.name(ch, repr(ch))}")
        byts += byt
        chars_consumed += 1
    return byts

def decode_pc6001_8bit_charset(byts, preserve=MINIMAL_CONTROLS):
    s, bytes_consumed, num_bytes = '', 0, len(byts)
    while bytes_consumed < num_bytes:
        byt = byts[bytes_consumed]
        if bytes_consumed > 0 and byts[bytes_consumed - 1] == 0x14 and byt >= 0x30 and byt <= 0x4F: 
            s = s[:-len(PC6001_8BIT_CHARSET[0x14])] + PC6001_8BIT_ALTCHARSET[byt - 0x30]
        elif byt in preserve:
            s += chr(byt)
        else:
            s += PC6001_8BIT_CHARSET[byt]
        if len(s) > 1 and s[-1:] in '\N{halfwidth katakana voiced sound mark}\N{halfwidth katakana semi-voiced sound mark}' and unicodedata.name(s[-2:-1], '?').lower().startswith('hiragana letter'):
            s = s[:-2] + unicodedata.normalize('NFKC', s[-2:])
        bytes_consumed += 1
    round_trip_byts = encode_pc6001_8bit_charset(s)
    assert byts == round_trip_byts, UnicodeDecodeError('pc6001-8bit', byts, 0, num_bytes, f"round-trip failure for {repr(s)} with preserve={repr(preserve)}; result:\n {repr(byts)}, got:\n {repr(round_trip_byts)}")
    return s

def smoke_test_pc6001_8bit_charset():
    assert decode_pc6001_8bit_charset(b'') == ''
    assert encode_pc6001_8bit_charset('') == b''
    assert decode_pc6001_8bit_charset(b'\x00') == '\x00'
    assert encode_pc6001_8bit_charset('\x00') == b'\x00'
    assert encode_pc6001_8bit_charset('␀') == b'\x00'
    assert encode_pc6001_8bit_charset('\uf8f1') == b'\x14\x30'
    assert encode_pc6001_8bit_charset('小') == b'\x14\x4F'
    assert encode_pc6001_8bit_charset('␔') == b'\x14'
    assert encode_pc6001_8bit_charset('\x14') == b'\x14'
    assert encode_pc6001_8bit_charset('\x14\x4F') == b'\x14\x4F'
    round_trip_test_failures = {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i]))): bytes([i])
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i]))) != bytes([i])
    }
    round_trip_test_failures |= {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([0x14, i]))): bytes([0x14, i])
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([0x14, i]))) != bytes([0x14, i])
    }
    round_trip_test_failures |= {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEE]))): bytes([i, 0xEE])
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEE]))) != bytes([i, 0xEE])
    }
    round_trip_test_failures |= {
        encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEF]))): bytes([i, 0xEF])
        for i in range(256)
        if encode_pc6001_8bit_charset(decode_pc6001_8bit_charset(bytes([i, 0xEF]))) != bytes([i, 0xEF])
    }
    assert not round_trip_test_failures, round_trip_test_failures
    unicode_test = '\r\n'.join((
        '\\￮╳•╳o/ I ♥ PC6001!',
        'パピコンが大すきです!',
        '「パピコン」は にっぽんでんき が せいぞうした8ビットコンピュータで、やすいことから いちじき にんき を はくしました。',
        '「！？」　･･･',
        '│|¦~-ｰ─_',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐ ┌￪┐ ++-+  ^/',
        '├┼─┤ ￩┼￫ ++-+ <X>',
        '││•│･└￬┘ ¦|.¦ /v ',
        '└┴─┘<>O[]++-+ π>3',
        '␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡',
    )) + '\x1A\x00'
    expected_8bit = b'\r\n'.join((
        b'\\\x84\x14L\x85\x14Lo/ I \x81 PC6001!',
        b'\xca\xdf\xcb\xdf\xba\xdd\x96\xde\x14M\x9d\x97\xe3\xde\x9d!',
        b'\xa2\xca\xdf\xcb\xdf\xba\xdd\xa3\xea \xe6\x8f\xee\xdf\xfd\xe3\xde\xfd\x97 \x96\xde \x9e\x92\x9f\xde\x93\x9c\xe08\xcb\xde\xaf\xc4\xba\xdd\xcb\xdf\xad\x90\xc0\xe3\xde\xa4\xf4\x9d\x92\x9a\xe4\x96\xf7 \x92\xe1\x9c\xde\x97 \xe6\xfd\x97 \x86 \xea\x98\x9c\xef\x9c\xe0\xa1',
        b'\xa2!?\xa3 \xa5\xa5\xa5',
        b'\x14F||~-\xb0\x14G_',
        b'\\0=0\x149',
        b'2025\x14807\x14118\x147 14\x14:11\x14;16\x14<',
        b'\x14H\x14B\x14G\x14I \x14H\x1e\x14I ++-+  ^/',
        b'\x14D\x14E\x14G\x14C \x1d\x14E\x1c ++-+ <X>',
        b'\x14F\x14F\x85\x14F\xa5\x14J\x1f\x14K ||.| /v ',
        b'\x14J\x14A\x14G\x14K<>O[]++-+ \x14@>3',
        bytes([ i for i in range(0x20) ] + [0x7F]),
    )) + b'\x1A\x00'
    assert encode_pc6001_8bit_charset(unicode_test) == expected_8bit, f"encode_pc6001_8bit_charset({repr(unicode_test)}) returned:\n {repr(encode_pc6001_8bit_charset(unicode_test))}, expecting:\n {repr(expected_8bit)}"
    pc6001_8bit_test = expected_8bit
    try:
        unexpected_8bit = encode_pc6001_8bit_charset(unicode_test, try_harder=False)
        assert False, f"Expected a UnicodeEncodeError for encode_pc6001_8bit_charset({repr(unicode_test)}, try_harder=False) but no error was raised"
    except UnicodeEncodeError:
        pass
    except Exception as e:
        assert False, f"Expected a UnicodeEncodeError for encode_pc6001_8bit_charset({repr(unicode_test)}, try_harder=False) but {repr(e)} was raised instead"
    expected_unicode = '\r\n'.join((
        '¥￮╳•╳o/ I ♥ PC6001!',
        'ﾊﾟﾋﾟｺﾝが大すきです!',
        '｢ﾊﾟﾋﾟｺﾝ｣は にっぽんでんき が せいぞうした8ﾋﾞｯﾄｺﾝﾋﾟｭーﾀで､やすいことから いちじき にんき を はくしました｡',
        '｢!?｣ ･･･',
        '│¦¦~-ｰ─_',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐ ┌￪┐ ++-+  ^/',
        '├┼─┤ ￩┼￫ ++-+ <X>',
        '││•│･└￬┘ ¦¦.¦ /v ',
        '└┴─┘<>O[]++-+ π>3',
        '\x00␁␂␃␄␅␆␇␈␉\n␋␌\r␎␏␐␑␒␓␔␕␖␗␘␙\x1A␛￫￩￪￬\x7f',
    )) + '\x1A\x00'
    assert decode_pc6001_8bit_charset(pc6001_8bit_test) == expected_unicode, f"decode_pc6001_8bit_charset({repr(pc6001_8bit_test)}) returned:\n {repr(decode_pc6001_8bit_charset(pc6001_8bit_test))}, expecting:\n {repr(expected_unicode)}"
    assert encode_pc6001_8bit_charset(expected_unicode, try_harder=False) == pc6001_8bit_test, f"encode_pc6001_8bit_charset({repr(expected_unicode)}, try_harder=False) returned:\n {repr(encode_pc6001_8bit_charset(expected_unicode, try_harder=False))}, expecting:\n {repr(pc6001_8bit_test)}"
    expected_no_controls_unicode = '␍␊'.join((
        '¥￮╳•╳o/ I ♥ PC6001!',
        'ﾊﾟﾋﾟｺﾝが大すきです!',
        '｢ﾊﾟﾋﾟｺﾝ｣は にっぽんでんき が せいぞうした8ﾋﾞｯﾄｺﾝﾋﾟｭーﾀで､やすいことから いちじき にんき を はくしました｡',
        '｢!?｣ ･･･',
        '│¦¦~-ｰ─_',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐ ┌￪┐ ++-+  ^/',
        '├┼─┤ ￩┼￫ ++-+ <X>',
        '││•│･└￬┘ ¦¦.¦ /v ',
        '└┴─┘<>O[]++-+ π>3',
        '␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬␡',
    )) + '␚␀'
    assert decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=NO_CONTROLS) == expected_no_controls_unicode, f"decode_pc6001_8bit_charset({repr(pc6001_8bit_test)}, preserve=NO_CONTROLS) returned:\n {repr(decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=NO_CONTROLS))}, expecting:\n {repr(expected_no_controls_unicode)}"
    expected_ascii_controls_unicode = '\r\n'.join((
        '¥￮╳•╳o/ I ♥ PC6001!',
        'ﾊﾟﾋﾟｺﾝが大すきです!',
        '｢ﾊﾟﾋﾟｺﾝ｣は にっぽんでんき が せいぞうした8ﾋﾞｯﾄｺﾝﾋﾟｭーﾀで､やすいことから いちじき にんき を はくしました｡',
        '｢!?｣ ･･･',
        '│¦¦~-ｰ─_',
        '¥0=0円',
        '2025年07月18日 14時11分16秒',
        '┌┬─┐ ┌\x1E┐ ++-+  ^/',
        '├┼─┤ \x1D┼\x1C ++-+ <X>',
        '││•│･└\x1F┘ ¦¦.¦ /v ',
        '└┴─┘<>O[]++-+ π>3',
        ''.join([ chr(i) for i in range(0x20) ]) + '\x7F',
    )) + '\x1A\x00'
    assert decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=ASCII_CONTROLS) == expected_ascii_controls_unicode, f"decode_pc6001_8bit_charset({repr(pc6001_8bit_test)}, preserve=ASCII_CONTROLS) returned:\n {repr(decode_pc6001_8bit_charset(pc6001_8bit_test, preserve=ASCII_CONTROLS))}, expecting:\n {repr(expected_ascii_controls_unicode)}"

smoke_test_pc6001_8bit_charset()

TRACK_TABLE_OFFSET = 0x20
TRACK_ENTRY_SIZE = 4
SECTOR_HEADER_SIZE = 16

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python fat8_d88_tool.py <file.d88>")
        sys.exit(1)

    d88_path = sys.argv[1]
else:
    d88_path = 'Kyoto Touryuuden [Original-looking disk].d88'

with open(d88_path, "rb") as f:
    d88_data = f.read()

DISK_ATTR_WRITE_PROTECTED = 'DiskWriteProtected' 

disk_name_or_comment = d88_data[:0x10].rstrip(b"\0") or None
disk_attrs = DISK_ATTR_WRITE_PROTECTED if d88_data[0x1A] & 0x10 else None
disk_sz = int.from_bytes(d88_data[0x1C:0x20], "little")
assert disk_sz <= len(d88_data), f"Is this a D88 file? The disk size field is too large"
assert disk_sz > TRACK_TABLE_OFFSET + TRACK_ENTRY_SIZE, f"Is this a D88 file? The disk size field is too small"
track_offsets = []
i = 0
while True:
    if  i > 0 and (TRACK_TABLE_OFFSET + TRACK_ENTRY_SIZE * i) >= min(track_offsets):
        break
    offset = int.from_bytes(d88_data[TRACK_TABLE_OFFSET + i * TRACK_ENTRY_SIZE: TRACK_TABLE_OFFSET + (i + 1) * TRACK_ENTRY_SIZE], "little")
    if i == 0:
        assert (offset - TRACK_TABLE_OFFSET) % TRACK_ENTRY_SIZE == 0, "Offset of first track must be a multiple of {TRACK_ENTRY_SIZE}"
    if offset not in (0, disk_sz):
        track_offsets += [offset]
        assert offset >= min(track_offsets), f"Offset {offset} for track {i} is smaller than offset for first track"
        assert offset + SECTOR_HEADER_SIZE < disk_sz, f"Is this a D88 file? Track data spills over past the end"
    i += 1

output = []
output.append("\n== Disk Information ==")
output.append(f"Disk name/comment: {disk_name_or_comment}")
output.append(f"Disk attributes: {disk_attrs}")

output.append("\n== Track/Sector Table ==")
track_sector_map = {}

all_sector_ranges = []
nominal_sectors_in_track = {}
for track_offset in track_offsets:
    sectors = []
    cursor = track_offset
    track_num, side_num = None, None
    while cursor + SECTOR_HEADER_SIZE <= disk_sz:
        header = d88_data[cursor:cursor + SECTOR_HEADER_SIZE]
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
        assert actual_data_offset + sector_data_size <= disk_sz, "Is this a D88 file? Sector data spilled off the end"
        for other_sector in sectors:
            assert other_sector[0] != sec_num, f"Is this a D88 file? Track {trk}, Side {side}, Sector {sec_num} appears more than once"
        sectors.append((sec_num, actual_data_offset, d88_data[actual_data_offset:actual_data_offset + sector_data_size], sectors_in_track))
        nominal_sectors_in_track[(trk, side)] = nominal_sectors_in_track.get((trk, side), sectors_in_track)
        assert nominal_sectors_in_track[(trk, side)] == sectors_in_track, f"Is this a damaged disk? Sectors-per-track varies in Track {trk}, Side {side}: {nominal_sectors_in_track[(trk, side)]} vs {sectors_in_track}"
        all_sector_ranges.append([actual_data_offset, actual_data_offset + sector_data_size])
        cursor += SECTOR_HEADER_SIZE + sector_data_size
    key = (track_num, side_num)
    track_sector_map[key] = sectors
    output.append(f"Track {track_num}, Side {side_num}: " + ", ".join(f"{s[0]}:{len(s[2])}" for s in sectors))

overlap_check_offset = 0
for start_offset, next_offset in sorted(all_sector_ranges):
    assert start_offset >= overlap_check_offset, "Is this a D88 file? Found overlapping sector data"
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

FAT8_FINAL_CLUSTER_OFFSET = 0xC0
FAT8_RESERVED_CLUSTERS = 0x02
FAT8_MAX_CLUSTERS = 0xA0
FAT8_CHAIN_TERMINAL_LINK = 0xFE
FAT8_UNALLOCATED_CLUSTER = 0xFF
FAT8_METADATA_CLUSTER_PC88 = 0x4A
FAT8_METADATA_CLUSTER_PC98 = 0x46
FAT8_METADATA_CLUSTER_PC66 = 0x24
FAT8_METADATA_CLUSTER_PC66SR = 0x4A

boot_sector = ([sector_data for sec_num, actual_data_offset, sector_data, sectors_in_track in sum([sectors for (trk, side), sectors in track_sector_map.items() if trk == 0 and side == 0], []) if sec_num == 1][:1] or [None])[0]

is_pc66sr_rxr = boot_sector is not None and boot_sector.startswith(b'RXR!')
is_pc66_sys = boot_sector is not None and boot_sector.startswith(b'SYS!')
is_pc98_sys = boot_sector is not None and len(boot_sector) == 128
fat8_sectors_per_track = max(sectors for (trk, side), sectors in nominal_sectors_in_track.items() if trk in (0, 1) and side == 0)
fat8_sides = 1 + max(side for trk, side in nominal_sectors_in_track.keys() if trk in (0, 1))
fat8_sector_size = max(max(len(sector_data) for sec_num, actual_data_offset, sector_data, sectors_in_track in sectors) for (trk, side), sectors in track_sector_map.items() if trk in (0, 1) and side == 0)
fat8_sector_shift = 0
while fat8_sector_size > 0x100 and fat8_sectors_per_track < 16:
    fat8_sector_shift += 1
    fat8_sector_size >>= 1
    fat8_sectors_per_track <<= 1
fat8_metadata_cluster = FAT8_METADATA_CLUSTER_PC66SR if is_pc66sr_rxr else FAT8_METADATA_CLUSTER_PC66 if is_pc66_sys or fat8_sides == 1 else FAT8_METADATA_CLUSTER_PC98 if is_pc98_sys else FAT8_METADATA_CLUSTER_PC88
decode_8bit_charset, encode_8bit_charset = (decode_pc6001_8bit_charset, encode_pc6001_8bit_charset) if is_pc66_sys or fat8_sides == 1 else (decode_pc98_8bit_charset, encode_pc98_8bit_charset)
fat8_disk_size = found_tracks * fat8_sides * fat8_sectors_per_track * fat8_sector_size
fat8_est_bytes_per_cluster = (fat8_disk_size + FAT8_MAX_CLUSTERS - 1) // FAT8_MAX_CLUSTERS
fat8_bytes_per_track = fat8_sectors_per_track * fat8_sector_size
fat8_clusters_per_track = min(2, fat8_bytes_per_track // fat8_est_bytes_per_cluster)
fat8_total_clusters = found_tracks * fat8_sides * fat8_clusters_per_track
fat8_sectors_per_cluster = fat8_sectors_per_track // fat8_clusters_per_track
fat8_bytes_per_cluster = fat8_sectors_per_cluster * fat8_sector_size

metadata_track = fat8_metadata_cluster // fat8_clusters_per_track // fat8_sides
metadata_side = fat8_metadata_cluster // fat8_clusters_per_track % fat8_sides

fat_sector_indices = {fat8_sectors_per_track - 2, fat8_sectors_per_track - 1, fat8_sectors_per_track - 0}
autorun_sector_index = fat8_sectors_per_track - 3
dir_sector_indices = set(range(1, autorun_sector_index, 2)) if fat8_sides == 1 else set(range(1, 10))

output.append('\n== Diagnostic Information ==')
output.append(f"Is PC66 SYS!: {is_pc66_sys}")
output.append(f"Is PC66SR RXR!: {is_pc66sr_rxr}")
output.append(f"Is PC98 boot sector: {is_pc98_sys}")
output.append(f"D88 track count: {found_tracks}")
output.append(f"D88 side count: {found_sides}")
output.append(f"D88 highest sector index: {found_sectors}")
output.append(f"D88 total sectors: {found_total_sectors}")
output.append(f"D88 disk size: {found_disk_size}")
output.append(f"Largest D88 sector size: {largest_sector_size}")
output.append(f"Nominal D88 side count: {fat8_sides}")
output.append(f"Nominal D88 disk size: {fat8_disk_size}")
output.append(f"Nominal D88 sector size: {fat8_sector_size << fat8_sector_shift}")
output.append(f"Virtual sector size: {fat8_sector_size}")
output.append(f"Virtual sectors per D88 sector: {1 << fat8_sector_shift}")
output.append(f"Virtual sectors per track: {fat8_sectors_per_track}")
output.append(f"Virtual sectors per cluster: {fat8_sectors_per_cluster}")
output.append(f"Bytes per cluster: {fat8_bytes_per_cluster}")
output.append(f"Bytes per track: {fat8_bytes_per_track}")
output.append(f"Clusters per track: {fat8_clusters_per_track}")
output.append(f"Total clusters: {fat8_total_clusters}")
output.append(f"Metadata cluster: 0x{fat8_metadata_cluster:02X}")
output.append(f"Metadata track: {metadata_track}")
output.append(f"Metadata side: {metadata_side}")
output.append(f"Directory virtual sector indices: {', '.join(f'{idx}' for idx in sorted(tuple(dir_sector_indices)))}")
output.append(f"Autorun data virtual sector index: {autorun_sector_index}")
output.append(f"FAT virtual sector indices: {', '.join(f'{idx}' for idx in sorted(tuple(fat_sector_indices)))}")

metadata_sectors = track_sector_map.get((metadata_track, metadata_side), [])
directory_entries = []
fat_sectors = {}
autorun_data = None

ATTR_BINARY = 'Binary'
ATTR_1_RESERVED = 'Reserved#1(Hidden?)'
ATTR_2_RESERVED = 'Reserved#2(System?)'
ATTR_3_RESERVED = 'Reserved#3(VolID?)'
ATTR_READ_ONLY = 'Read-Only'
ATTR_OBFUSCATED = 'Obfuscated'  # some documentation calls this "encrypted" or "protected"
ATTR_READ_AFTER_WRITE = 'Read-after-Write'
ATTR_NON_ASCII = 'Non-ASCII'
PSEUDO_ATTR_UNUSED = 'Unused(FF)'
PSEUDO_ATTR_DELETED = 'Deleted(00)'
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
PC88_COMBINED_KEY = (
    0xC0, 0xCF, 0xCC, 0x85, 0x62, 0x81, 0x0C, 0x42, 0xC3, 0x04, 0xE5,
    0xE6, 0xCD, 0x11, 0x75, 0xB6, 0x90, 0xE4, 0x97, 0x35, 0xED, 0xB2,
    0xFC, 0x6E, 0x37, 0x77, 0x6B, 0x60, 0x30, 0x86, 0xDD, 0x38, 0x44,
    0x15, 0x39, 0x2D, 0xD4, 0x4D, 0x62, 0xED, 0x76, 0x09, 0x29, 0xAC,
    0xC0, 0xCF, 0xC4, 0x83, 0x57, 0xC1, 0xCB, 0x74, 0xD4, 0xD9, 0x78,
    0xD1, 0x27, 0x11, 0x75, 0xBE, 0x96, 0xD1, 0xD7, 0xF2, 0xDB, 0xA5,
    0x21, 0xF3, 0x00, 0x9D, 0x6B, 0x60, 0x38, 0x80, 0xE8, 0x78, 0x83,
    0x23, 0x2E, 0xF0, 0x49, 0x7A, 0x88, 0xED, 0x76, 0x01, 0x2F, 0x99,
    0x80, 0x08, 0xF2, 0x94, 0x8A, 0x5C, 0xFC, 0x9E, 0xD4, 0xD9, 0x70,
    0xD7, 0x12, 0x51, 0xB2, 0x88, 0x81, 0x0C, 0x4A, 0xC5, 0x31, 0xA5,
    0x21, 0xFB, 0x06, 0xA8, 0x2B, 0xA7, 0x0E, 0x97, 0x35, 0xE5, 0xB4,
    0xC9, 0x2E, 0xF0, 0x41, 0x7C, 0xBD, 0xAD, 0xB1, 0x37, 0x38, 0x44,
    0x1D, 0x3F, 0x18, 0x94, 0x8A, 0x54, 0xFA, 0xAB, 0x94, 0x1E, 0x46,
)

def deobfuscate_byte(i, byt):
    if is_pc98_sys:
        # N88-BASIC(86) uses a simple bit-rotation
        return ((byt & 0x7F) << 1) | ((byt & 0x80) >> 7)
    # PC88 BASIC uses the same algorithm as
    # https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format
    # but different key material.
    return (range(13, 0, -1)[i%13] + (((byt + 0x100 - range(11, 0, -1)[i%11]) % 0x100) ^ PC88_COMBINED_KEY[i%(11*13)])) % 0x100

def obfuscate_byte(i, byt):
    if is_pc98_sys:
        # N88-BASIC(86) uses a simple bit-rotation
        return ((byt & 0x8E) >> 1) | ((byt & 0x01) << 7)
    # PC88 BASIC uses the same algorithm as
    # https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format
    # but different key material.
    return (range(11, 0, -1)[i%13] + (((byt + 0x100 - range(13, 0, -1)[i%13]) % 0x100) ^ PC88_COMBINED_KEY[i%(11*13)])) % 0x100

# these restrictions on generated filenames are somewhat conservative
# and meant to accomodate MS-DOS, UNIX, macOS, and Windows - however
# generated names may exceed MS-DOS length limitations or contain
# multiple dots. also accomodating case-insensitive file systems
# (e.g. by avoiding collisions across multiple entries) is left to the
# caller of to_host_fs_name.

HOST_FS_UNSAFE_CHARS = set('"*+,/:;<=>?[\\]|\x7f¥¦') | set(chr(i) for i in range(0x20))
HOST_FS_UNSAFE_NAMES_UPPER = set(['CLOCK$', 'CON', 'PRN', 'AUX', 'NUL'] + [f'COM{n}' for n in range(1, 10)] + [f'LPT{n}' for n in range(1, 10)])
HOST_FS_UNSAFE_START_CHARS = set(' ')
HOST_FS_UNSAFE_END_CHARS = set(' .')

def to_host_fs_name(name, ext, fattrs):
    filename = f"{name.rstrip(' ')}{'.' if ext.rstrip(' ') else ''}{ext.rstrip(' ')}"
    filename_chars = [ch for ch in filename]
    for i, ch in enumerate(filename_chars):
        unsafe = ch in HOST_FS_UNSAFE_CHARS
        if filename.upper() in HOST_FS_UNSAFE_NAMES_UPPER or filename == '.' * len(filename) and i == 0:
            unsafe = True
        if ch == '.' and i != len(name.rstrip(' ')):
            unsafe = True
        if i == 0 and ch in HOST_FS_UNSAFE_START_CHARS:
            unsafe = True
        if i == len(filename_chars) - 1 and ch in HOST_FS_UNSAFE_END_CHARS:
            unsafe = True
        if ch >= '\uE000' and ch <= '\uF8FF':
            unsafe = True
        if unsafe or ch == '%':  # quote % too since we use it for quoting
            filename_chars[i] = ''.join(f"%{byt:02X}" for byt in encode_8bit_charset(filename[i]))
    host_fs_name = ''.join(filename_chars)
    if not host_fs_name or host_fs_name[:1] == '.':
        host_fs_name = '(empty)' + host_fs_name
    natural_suffix = ''.join(host_fs_name.split('.')[1:]).lower()
    host_fs_suffix = '..' + '.'.join(sorted(sum([
        ['---'] if PSEUDO_ATTR_UNUSED in fattrs else [],
        ['bas'] if ATTR_NON_ASCII in fattrs and natural_suffix not in ('bas', 'n88', 'nip', 'hd') else [],
        ['bin'] if ATTR_BINARY in fattrs and natural_suffix not in ('bin', 'cod') else [],
        ['era'] if PSEUDO_ATTR_DELETED in fattrs else [],
        ['r-1'] if ATTR_1_RESERVED in fattrs else [],
        ['r-2'] if ATTR_2_RESERVED in fattrs else [],
        ['r-3'] if ATTR_3_RESERVED in fattrs else [],
        ['r-o'] if ATTR_READ_ONLY in fattrs else [],
        ['obf'] if ATTR_OBFUSCATED in fattrs else [],
        ['asc'] if not {ATTR_NON_ASCII, ATTR_BINARY}.intersection(fattrs) and natural_suffix not in ('asc', 'txt') else [],
        ['vfy'] if ATTR_READ_AFTER_WRITE in fattrs else [],
    ], [])))
    if host_fs_suffix == '..':
        host_fs_suffix = ''
    if '.' in host_fs_name:
        host_fs_suffix = host_fs_suffix[len('.'):]
    return host_fs_name + host_fs_suffix

def extend_name(base_filename, name_tail):
    '''Add more stuff at the end of a filename but before eny
    extensions.
    '''
    parts = base_filename.split('.', 1)
    parts[0] += name_tail
    return '.'.join(parts)

# parse directory entries and make matching names for the host file system
raw_metadata_sectors = {}
used_filenames = {}
used_lower_fs_names = set()
for sec_num, offset, data, sectors_in_track in metadata_sectors:
    for vsec_num in range(((sec_num - 1) << fat8_sector_shift) + 1, (sec_num << fat8_sector_shift) + 1):
      vdata = data[fat8_sector_size * ((vsec_num - 1) % (1 << fat8_sector_shift)):fat8_sector_size * (1 + ((vsec_num - 1) % (1 << fat8_sector_shift)))]
      raw_metadata_sectors[vsec_num] = vdata
      if vsec_num in dir_sector_indices:
        for i in range(0, 256, 16):
            entry = vdata[i:i+16]
            raw_name = entry[0:6]
            name = decode_8bit_charset(raw_name, preserve=NO_CONTROLS)
            raw_ext = entry[6:9]
            ext = decode_8bit_charset(raw_ext, preserve=NO_CONTROLS)
            # two pseudo-attributes are encoded using special characters in the first byte of the filename
            attr_mask = entry[9] | (0x100 if entry[0] == 0x00 else 0x000) | (0x200 if entry[0] == 0xFF else 0x000)
            fattrs = set(attr for mask, attr in ALL_ATTRS.items() if attr_mask & mask)
            cluster = entry[10]
            host_fs_name = to_host_fs_name(name, ext, fattrs)
            disambig = ''
            while extend_name(host_fs_name.lower(), disambig) in used_lower_fs_names:
                disambig = f" ({1 + int(disambig.strip(' ()') or 0)})"
            host_fs_name = extend_name(host_fs_name, disambig)
            host_fs_deobf_name = to_host_fs_name(name, ext, fattrs - {ATTR_OBFUSCATED})
            disambig_deobf = ''
            while extend_name(host_fs_deobf_name.lower(), disambig_deobf) in used_lower_fs_names:
                disambig_deobf = f" ({1 + int(disambig.strip(' ()') or 0)})"
            host_fs_deobf_name = extend_name(host_fs_deobf_name, disambig_deobf)
            if entry == 16 * b'\xFF' and PSEUDO_ATTR_UNUSED in fattrs:
                # completely unused entries fresh from the formatter
                # do not need to be printed at all; other-shaped
                # unused ones will still be printed in case they
                # contain useful residual information
                continue
            used_lower_fs_names |= {host_fs_name.lower()}
            if ATTR_OBFUSCATED in fattrs:
                used_lower_fs_names |= {host_fs_deobf_name.lower()}
            parsed_entry = dict(idx=(vsec_num - 1) * 16 + i // 16 + 1, host_fs_name=host_fs_name, host_fs_deobf_name=host_fs_deobf_name, fattrs=fattrs, cluster=cluster, name=name, ext=ext, chain=[], errors=set(), allocated_size=0, raw_entry=entry, file_data=None)
            if PSEUDO_ATTR_DELETED not in fattrs:
                other_entry = used_filenames.get(name + '.' + ext)
                if other_entry is not None:
                    parsed_entry['errors'] |= {'Duplicate filename'}
                    if parsed_entry['raw_entry'] != other_entry['raw_entry']:
                        other_entry['errors'] |= {'Duplicate filename'}
                else:
                    used_filenames[name + '.' + ext] = parsed_entry
            directory_entries.append(parsed_entry)
      elif vsec_num in fat_sector_indices:
          fat_sectors[vsec_num] = vdata
      elif vsec_num == autorun_sector_index:
          autorun_data = vdata

def hexdump_entry_data(file_data, fattrs):
    for i in range(0, len(file_data), 16):
        row = f"{i:06X}: "
        drow = ' '
        dvrow = vrow = '│'
        vtail = dvtail = '│'
        for j in range(i, i + 16):
            row += f" {file_data[j]:02X}" if j < len(file_data) else '   '
            drow += f" {deobfuscate_byte(j, file_data[j]):02X}" if j < len(file_data) else '   '
            if j < len(file_data):
                ch = decode_8bit_charset(bytes([file_data[j - 1] if j else 0, file_data[j]]), preserve=NO_CONTROLS)[-1:]
                vrow += '.' if ch <= '\x1F' or ch == '\x7F' or ch >= '\uE000' and ch <= '\uF8FF' else ch
                dch = decode_8bit_charset(bytes([deobfuscate_byte(j - 1, file_data[j - 1]) if j else 0, deobfuscate_byte(j, file_data[j])]), preserve=NO_CONTROLS)[-1:]
                dvrow += '.' if dch <= '\x1F' or dch == '\x7F' or dch >= '\uE000' and dch <= '\uF8FF' else dch
            else:
                vtail = '╭' + '─' * len(vtail[:-1]) + '╯'
                dvtail = '╭' + '─' * len(dvtail[:-1]) + '╯'
            if j % 8 == 7:
                row += ' '
                drow += ' '
        output.append(f"{row} {vrow}{vtail}" + (f"{drow} {dvrow}{dvtail}" if ATTR_OBFUSCATED in fattrs else ''))
    output.append(f"{len(file_data):06X}{'':53}╰{'─' * ((len(file_data) % 16) or 16)}╯{'' if ATTR_OBFUSCATED not in fattrs else ' ' * ((16 - ((len(file_data) % 16) or 16)) + 52) + '╰' + '─' * ((len(file_data) % 16) or 16) + '╯'}")

if boot_sector is not None:
    output.append(f"\n== Boot Sector (Track 0, Sector 1) =={'':22}╭{'─' * 16}╮")
    hexdump_entry_data(boot_sector, set())

output.append("\n== Raw directory sectors ==")
for vsec_num in sorted(dir_sector_indices):
    sector_data = raw_metadata_sectors.get(vsec_num)
    if sector_data is not None:
        output.append(f"\nDirectory Sector {vsec_num:<3}{'':39}╭{'─' * 16}╮")
        hexdump_entry_data(sector_data, set())
    else:
        output.append(f"Missing directory sector {vsec_num}")
          
if autorun_data is not None:
    output.append(f"\n== Autorun/ID Sector {autorun_sector_index:3} =={'':31}╭{'─' * 16}╮")
    hexdump_entry_data(autorun_data, set())
    output.append(f"Header: {autorun_data[0]:02X} {autorun_data[1]:02X}")
    output.append(f"Payload: {decode_8bit_charset(autorun_data[2:].rstrip(bytes([0x00])).rstrip(b' '))}")

first_fat_sector_idx = sorted(fat_sectors.keys())[0] if fat_sectors else None

fat1 = None

if first_fat_sector_idx is not None:
    fat1 = fat_sectors[first_fat_sector_idx]
    output.append(f"\n== FAT Sector {first_fat_sector_idx:3} =={'':39}╭{'─' * 16}╮")
    hexdump_entry_data(fat1, set())
    output.append("\n== FAT Consistency Check ==")
    matches = {
        fat1 == sector_data
        for sector_data in
        fat_sectors.values()
    }
    if matches =={True}:
        output.append("FAT copies match")
    else:
        output.append("FAT copies DO NOT match")
        for other_fat_sector_idx, other_fat in sorted(fat_sectors.items())[1:]:
            output.append(f"\n== FAT Sector {other_fat_sector_idx:3} =={'':39}╭{'─' * 16}╮")
            hexdump_entry_data(other_fat, set())
        
else:
    output.append('\n== No FAT!!! ==')

# follow FAT chains
chained_blocks = {}
for entry in directory_entries:
    unlisted = True if UNLISTED_ENTRY_ATTRS.intersection(entry['fattrs']) else False
    chain = []
    errors = set()
    if fat1 is None:
        errors |= {'No FAT'}
    elif PSEUDO_ATTR_DELETED in entry['fattrs']:
        errors |= {'Deleted'}
    elif PSEUDO_ATTR_UNUSED in entry['fattrs']:
        errors |= {'Unused'}
    else:
        chain = [entry['cluster']]
        if entry['cluster'] < FAT8_RESERVED_CLUSTERS:
            errors |= {'Reserved cluster at head of chain'}
        elif entry['cluster'] >= FAT8_FINAL_CLUSTER_OFFSET and entry['cluster'] not in (FAT8_CHAIN_TERMINAL_LINK, FAT8_UNALLOCATED_CLUSTER):
            errors |= {'Head of chain cannot be a block count'}
        elif entry['cluster'] < FAT8_FINAL_CLUSTER_OFFSET and entry['cluster'] >= fat8_total_clusters:
            errors |= {'Head of chain falls outside of disk'}
        while chain[-1] < FAT8_FINAL_CLUSTER_OFFSET and not errors:
            next_link = fat1[chain[-1]]
            if next_link < FAT8_FINAL_CLUSTER_OFFSET:
                if next_link < FAT8_RESERVED_CLUSTERS:
                    errors |= {'Reserved cluster in chain'}
                elif next_link >= fat8_total_clusters:
                    errors |= {'Chain entry falls outside of disk'}
                elif next_link in chain:
                    errors |= {'Cycle in FAT chain'}
            chain += [next_link]
        if (FAT8_UNALLOCATED_CLUSTER in chain) and not errors:
            errors |= {'Unallocated cluster in FAT chain'}
        if (chain[-1] < FAT8_FINAL_CLUSTER_OFFSET or chain[-1] == FAT8_UNALLOCATED_CLUSTER) and not errors:
            errors |= {'Unterminated FAT chain'}
    if not errors:
      for link in chain[:-1]:
        other_entry = chained_blocks.get(link)
        if other_entry is not None:
            if entry['raw_entry'][9:11] != other_entry['raw_entry'][9:11]:
                errors |= {f"Overlapping allocation {link:02X}"}
                other_entry['errors'] |= {f"Overlapping allocation {link:02X}"}
        else:
            chained_blocks[link] = entry
    if not errors:
        allocated_size = fat8_bytes_per_cluster * len(chain[:-1])
        if chain[-1] >= FAT8_FINAL_CLUSTER_OFFSET and chain[-1] not in (FAT8_CHAIN_TERMINAL_LINK, FAT8_UNALLOCATED_CLUSTER):
            allocated_size -= fat8_bytes_per_cluster
            allocated_size += fat8_sector_size * (chain[-1] - FAT8_FINAL_CLUSTER_OFFSET)
        entry['allocated_size'] = allocated_size
    entry['chain'] = chain
    entry['errors'] = errors

# reconstruct file data
for idx, entry in sorted((ent['idx'], ent) for ent in directory_entries):
    chain = entry['chain']
    errors = entry['errors']
    if not errors:
        file_data = b''
        final_cluster_offset = 0
        for i, cluster in enumerate(chain[:-1]):
            in_final_cluster = i == len(chain) - 2
            max_fat8_sectors_in_cluster = fat8_sectors_per_cluster
            if in_final_cluster:
                final_cluster_offset = len(file_data)
                if chain[-1] >= FAT8_FINAL_CLUSTER_OFFSET and chain[-1] < FAT8_CHAIN_TERMINAL_LINK:
                    max_fat8_sectors_in_cluster = chain[-1] - FAT8_FINAL_CLUSTER_OFFSET
            cluster_track = cluster // fat8_clusters_per_track // fat8_sides
            cluster_side = cluster // fat8_clusters_per_track % fat8_sides
            cluster_sectors = track_sector_map.get((cluster_track, cluster_side), [])
            for cluster_sec_num in range(1 + (cluster % fat8_clusters_per_track) * (fat8_sectors_per_track // fat8_clusters_per_track), 1 + (cluster % fat8_clusters_per_track) * (fat8_sectors_per_track // fat8_clusters_per_track) + max_fat8_sectors_in_cluster):
                cluster_sector_data = None
                for sec_num, actual_data_offset, sector_data, sectors_in_track in cluster_sectors:
                  for vsec_num in range(((sec_num - 1) << fat8_sector_shift) + 1, (sec_num << fat8_sector_shift) + 1):
                    if vsec_num == cluster_sec_num:
                      vsector_data = sector_data[fat8_sector_size * ((vsec_num - 1) % (1 << fat8_sector_shift)):fat8_sector_size * (1 + ((vsec_num - 1) % (1 << fat8_sector_shift)))]
                      cluster_sector_data = vsector_data
                      break
                  if cluster_sector_data is not None:
                      break
                if cluster_sector_data is None:
                    entry['errors'] |= {'Missing sector'}
                    file_data = None
                    break
                file_data += cluster_sector_data
        if file_data is not None:
            if file_data[-fat8_sector_size:].rstrip(b'\0')[-1:] == b'\x1A':
                file_data = file_data.rstrip(b'\0')[:-1]
        entry['file_data'] = file_data

def quote_filename(filename):
    for ch in list(filename):
        if ord(ch) <= 0x20 or ord(ch) >= 0x7F:
            return f'"{filename}"'
    return filename
    
output.append("\n== Directory Entries ==")

for idx, entry in sorted((ent['idx'], ent) for ent in directory_entries):
    sep = '*' if ATTR_BINARY in entry['fattrs'] else '.' if ATTR_NON_ASCII in entry['fattrs'] else ' '
    output.append(f"{entry['idx']:3}. {'[' if unlisted else ' '}{entry['name']}{sep}{entry['ext']}{']' if unlisted else ' '} {(entry['allocated_size'] + fat8_bytes_per_cluster - 1) // fat8_bytes_per_cluster:3d} {quote_filename(entry['host_fs_name'])+('' if ATTR_OBFUSCATED not in entry['fattrs'] else ', ' + quote_filename(entry['host_fs_deobf_name'])):40} {len(entry['file_data'] or b''):8} ATTRS={entry['fattrs'] or None}  START={entry['cluster']:02X} CHAIN={'→'.join(f'{cluster:02X}' for cluster in entry['chain']) if entry['chain'] else None} STATUS={entry['errors'] or 'OK'}")

output.append(f"\n== File Contents ==")

for idx, entry in sorted((ent['idx'], ent) for ent in directory_entries):
    errors = entry['errors']
    if not errors:
        sep = '*' if ATTR_BINARY in entry['fattrs'] else '.' if ATTR_NON_ASCII in entry['fattrs'] else ' '
        output.append(f"{entry['idx']:3}. {'[' if unlisted else ' '}{entry['name']}{sep}{entry['ext']}{']' if unlisted else ' '} {(entry['allocated_size'] + fat8_bytes_per_cluster - 1) // fat8_bytes_per_cluster:3d} {quote_filename(entry['host_fs_name']):27} {len(entry['file_data'] or b''):8} ╭{'─' * 16}╮" + ('' if ATTR_OBFUSCATED not in entry['fattrs'] else f" {quote_filename(entry['host_fs_deobf_name']):50} ╭{'─' * 16}╮"))
        if file_data is not None:
            hexdump_entry_data(entry['file_data'], entry['fattrs'])

print("\n".join(output))

outdir = os.path.splitext(os.path.basename(d88_path))[0] + ' [FAT8 Contents]'

disambig = ''
while os.path.exists(outdir + disambig):
    disambig = f" ({1 + int(disambig.strip(' ()') or 0)})"
outdir += disambig

print('\n== Extracting ==')
print(f"mkdir {outdir}")
os.mkdir(outdir)

log_filename = os.path.join(outdir, "_fat8_d88_output.txt")
with open(log_filename, "w", encoding="utf-8") as f:
    print(f"writing {log_filename}")
    f.write("\n".join(output))

def utf8_dump_filename(filename):
    parts = filename.rsplit('.', 1)
    return '_'.join(parts) + '_utf8.txt'

if boot_sector is not None:
    boot_sector_filename = os.path.join(outdir, "_boot_sector.dat")
    with open(boot_sector_filename, "wb") as f:
        print(f"writing {boot_sector_filename}")
        f.write(boot_sector)
    with open(utf8_dump_filename(boot_sector_filename), "w") as f:
        print(f"writing {utf8_dump_filename(boot_sector_filename)}")
        f.write(decode_8bit_charset(boot_sector))

for vsec_num in sorted(dir_sector_indices):
    sector_data = raw_metadata_sectors.get(vsec_num)
    if sector_data is None:
        continue
    dir_sector_filename = os.path.join(outdir, f"_dir_sector_{vsec_num}.dat")
    with open(dir_sector_filename, "wb") as f:
        print(f"writing {dir_sector_filename}")
        f.write(sector_data)
    with open(utf8_dump_filename(dir_sector_filename), "w") as f:
        print(f"writing {utf8_dump_filename(dir_sector_filename)}")
        f.write(decode_8bit_charset(sector_data))

if autorun_data is not None:
    autorun_filename = os.path.join(outdir, "_AutoRun.dat")
    with open(autorun_filename, "wb") as f:
        print(f"writing {autorun_filename}")
        f.write(autorun_data)
    with open(utf8_dump_filename(autorun_filename), "w") as f:
        print(f"writing {utf8_dump_filename(autorun_filename)}")
        f.write(decode_8bit_charset(autorun_data))

for fat_sector_idx, fat in sorted(fat_sectors.items()):
    fat_filename = os.path.join(outdir, f"_fat_sector_{fat_sector_idx}.dat")
    with open(fat_filename, "wb") as f:
        print(f"writing {fat_filename}")
        f.write(fat)
    with open(utf8_dump_filename(fat_filename), "w") as f:
        print(f"writing {utf8_dump_filename(fat_filename)}")
        f.write(decode_8bit_charset(fat))

for idx, entry in sorted((ent['idx'], ent) for ent in directory_entries):
    errors = entry['errors']
    if not errors:
        entry_filename = os.path.join(outdir, entry['host_fs_name'])
        file_data = entry['file_data']
        with open(entry_filename, "wb") as f:
            print(f"writing {entry_filename}")
            f.write(file_data)
        with open(utf8_dump_filename(entry_filename), "w") as f:
            print(f"writing {utf8_dump_filename(entry_filename)}")
            f.write(decode_8bit_charset(file_data))
        if ATTR_OBFUSCATED in entry['fattrs']:
            file_deobf_data = bytes([deobfuscate_byte(i, byt) for i, byt in enumerate(file_data)])
            entry_deobf_filename = os.path.join(outdir, entry['host_fs_deobf_name'])
            with open(entry_deobf_filename, "wb") as f:
                print(f"writing {entry_deobf_filename}")
                f.write(file_deobf_data)
            with open(utf8_dump_filename(entry_deobf_filename), "w") as f:
                print(f"writing {utf8_dump_filename(entry_deobf_filename)}")
                f.write(decode_8bit_charset(file_deobf_data))
