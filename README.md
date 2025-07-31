# fat8_d88_tool
This tool extracts files from FAT8-formatted disks stored in the D88 image format. Encoders and decoders for the `RBYTE` image formats found on some PC98 and PC88 D88 disks are also included. For now those RBYTE tools must be invoked separately, refer to the corresponding file for more information.

# Help
```
Usage: python fat8_d88_tool.py PATH/TO/MY/DISK.D88 [...]
                               ## Disk image extraction mode
   or: python fat8_d88_tool.py --pc98-8bit-to-utf8 < INPUT_PC98.TXT > OUTPUT_UTF8.TXT
       python fat8_d88_tool.py --utf8-to-pc98-8bit < INPUT_UTF8.TXT > OUTPUT_PC98.TXT
       python fat8_d88_tool.py --pc6001-8bit-to-utf8 < INPUT_PC6001.TXT > OUTPUT_UTF8.TXT
       python fat8_d88_tool.py --utf8-to-pc6001-8bit < INPUT_UTF8.TXT > OUTPUT_PC6001.TXT
                               ## Character set filter modes
       python fat8_d88_tool.py --help OR -h
                               ## Display this message and exit
```
## Disk image extraction mode
Each D88 file processed will have an output directory created in the current directory whose name beginning with `DISK [FAT8 Contents]`. The D88 filename `-` by itself indicates stdin, and in this case output will go to a directory named starting with `stdin [FAT8 Contents]`. A D88 file containing multiple disk images will have a suffix like ` [Disk 01]` appended to the directory name for each disk image, where 01 will be replaced by the index of the disk image within the D88 file. Processing errors result in a suffix like ` [Error Count 03]` appended to the directory name for the disk image, where 03 will be replaced by the number of processing errors.

If an intended output directory name already exists, a suffix like ` (2)` will be added, where 2 is a number from 2 onward that is large enough to avoid existing names.

`Non-ASCII` (i.e. tokenized BASIC) extracted files will have a `.bas` extension added if they are not already `.bas`, `.n88`, `.nip`, or `.bin` (case-insensitively)

`ASCII` (i.e. untokenized BASIC or regular character data) extracted files will have a `.asc` extension added if they are not already `.asc`, or `.txt` (case-insensitively)

`Binary` (i.e. BLOAD) extracted files will have a `.bin` extension added if they are not already `.bin` or `.cod` (case-insensitively)

Special file attributes may result in additional extensions like `.r-1`, `.r-2`, `.r-3`, `.r-o` (Read-Only), `.vfy` (Read-after-Write), and/or `.obf` (Obfuscated)

For systems where the deobfuscation method is understood, an additional deobfuscated copy of the file will be created without the `.obf` suffix

If an output file within the created output directory with the same intended name (compared case-insensitively) is already going to be created, a suffix like ` (2)` will be added before the file extension, where 2 is replaced by a number from 2 onward that is large enough to avoid existing files.

Dumped filenames will also often have a version where the suffix is changed from e.g. `.XXX` to `_XXX_utf8_dump.txt` containing a copy of the data with all bytes transformed to Unicode. Whether this contains anything useful will depend on what data was in the original file, though.

A log file for each disk image will be written to stdout and also to a file `_fat8_d88_output.txt` inside the created directory. Additional files beginning with `_` may be written for things like boot sectors, directory sectors, autorun/ID data, and FAT sectors.
## Character set filter modes:
In character set filter modes, character set translation proceeds one line at a time from stdin to stdout.

# Why?
Why am I sharing it here when the code is terrible? In case you want to use it on a disk other tools won't touch.

# History
After a lot of banging my head against the wall and AI's, and eventually rewriting most of the logic after discovering the AI-written code was almost universally wrong, I now have a Python script _(which is uglier than sin and still needs a bunch of cleanup, it started in chatgpt and I have yet to make it not terrible code-wise)_ that can decode FAT8-formatted D88 disk images and dump the files from them into a directory. It doesn't seem to croak or corrupt the extracted files the way other tools do.

# Status
**Working:** D88 FAT8 extraction. Tested with a handful of disk images from PC66, PC66SR, PC88, and PC98. For PC98 and PC88 at least it knows how to deobfuscate "protected" saves too. Implements the 8-bit/single-byte Japanese character sets for PC88/PC98 and PC-6001 series by mapping them clumsily to Unicode when putting them in filenames or log/dump files. A Pasopia disk image worked too.

**Still TODO:** a lot of stuff, including cleaning up the code, adding support for other charsets, decoding tokenized BASIC into ASCII, detecting PC-6001 series autostart in the boot sector, and probably a whole lot more...

# System detection
The FAT8 used on these various NEC PC's seems to have varied a bit in terms of where the metadata track (containing directory, autostart/ID information, and triplicate FAT) is stored, and also in terms of how it is laid out. At the moment the disk parameters (especially the number of sides) and information about the sectors in tracks 0 and 1 (especially the size of the first sector in track 0 along with its contents) are used to attempt to determine which flavor is used. This also determines which character set will be used when constructing filenames or displaying hexadecimal dumps or other debug information.

Some common formats are listed in `KNOWN_FAT8_FORMATS` to improve heuristic detection.

# 8-bit/single-byte character set used for PC88/PC98
I am sure this is not the best way to solve this. This mapping should work OK for PC-8001 series, PC-8801 series, and PC-98/PC-9821 series and compatibles when displaying an 8-bit character set with no kanji support. Once a kanji ROM gets involved the problem gets a whole lot trickier since these "narrow" single-byte characters map to the same Unicode as those double-byte (but sometimes single-width!) ones. In some cases those are visually distinct, in other cases not. In any case, there will be ambiguity or other escaping mechanisms will be needed. Characters from the private use area are used to handle various unassigned or ambiguous mappings. I considered '\N{no-break space}' for b'\xA0' but it seems semantically wrong. The kanji here are supposed to be halfwidth but Unicode lacks a way to express that.
```
␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬
 !"#$%&'()*+,-./0123456789:;<=>?
@ABCDEFGHIJKLMNOPQRSTUVWXYZ[¥]^_
`abcdefghijklmnopqrstuvwxyz{¦}~␡
▁▂▃▄▅▆▇█▏▎▍▌▋▊▉┼┴┬┤├▔─│▕┌┐└┘╭╮╰╯
｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ
ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ
═╞╪╡◢◣◥◤♠♥♦♣•￮╱╲╳円年月日時分秒\
```

# 8-bit/single-byte character set used for PC-6001/mkII/SR and PC-6601/SR (Mr. PC)
I am sure this is not the best way to solve this. This mapping should work OK for PC-6001/mkII/SR and PC-6601/SR. It does not handle the alternate character set shift sequences well. It also does not handle Kanji or PC-6001A charset at all! the mapping is intentionally close to the PC-98 one above. The hiragana and kanji here should all be half-width ones, but Unicode is missing those so we live with fullwidth instead.

Primary character set:
```
␀␁␂␃␄␅␆␇␈␉␊␋␌␍␎␏␐␑␒␓␔␕␖␗␘␙␚␛￫￩￪￬
 !"#$%&'()*+,-./0123456789:;<=>?
@ABCDEFGHIJKLMNOPQRSTUVWXYZ[¥]^_
`abcdefghijklmnopqrstuvwxyz{¦}~␡
♠♥♦♣￮•をぁぃぅぇぉゃゅょっーあいうえおかきくけこさしすせそ
｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿ
ﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ
たちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん
```
Alternate character set:
```
月火水木金土日年円時分秒百千万
π┴┬┤├┼│─┌┐└┘╳大中小
```

# De-obfuscation, PC98 version
Sometimes on FAT8 PC98 disks written using N88-BASIC(86) (disk version) the saved data is obfuscated (specified by `,P` at time of `SAVE` or `BSAVE`.) I saved a file of my own and read back the bytes and they were all rotating one bit position compared to their original values! Rotating the opposite direction will fix it. For these files the tool generates both the obfuscated and deobfuscated versions, since many other tools still lack support for the obfuscation mechanism.

# De-obfuscation, PC88 version
NEC PC-88 obfuscated ("encrypted") BASIC saves use a pair of XOR keys which are stored in ROM, using the algorithm previously documented here: https://robhagemans.github.io/pcbasic/doc/2.0/#protected-file-format - but with different key data. One key has length 11, the other has length 13. A byte from each one is XOR'ed with each byte being de-obfuscated/decrypted or obfuscated/encrypted. However, you can de-obfuscate/decrypt (or obfuscate/encrypt) the save data just fine without the ROM data, provided you have a "combined XOR key" which is 11*13 = 143 bytes long. It turns out you can get BASIC to save this key as part of your program, provided you have the right string in your program at the right position. So, I wrote a program to do this and recovered the "combined XOR key" from my save file.

Here's the BASIC program I typed in for key recovery:
```basic
10 ' The length of the comment is important. Do not change it! It needs to leave the first byte of KP$ at file offset 143. '''''''
20 KP$="▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂▊▋▌▍▎▏█▇▆▅▄▃▂"
30 WIDTH 80:SCREEN,,0:CLS
40 V1$="":FOR J=11 TO 1 STEP -1:FOR I=13 TO 1 STEP -1:V1$=V1$+CHR$(128+I):NEXT I:NEXT J
50 IF KP$<>V1$ THEN PRINT"Program is corrupt. Re-enter:":PRINT"20 KP$="+CHR$(34)+V1$+CHR$(34):STOP
60 PRINT"Saving known plaintext in temporary file TMP."
70 SAVE"TMP"
80 PRINT"Verifying known plaintext in temporary file TMP."
90 OPEN"TMP"FOR INPUT AS #1
100 XP$=INPUT$(143,1) ' Padding
110 VP$=INPUT$(143,1) ' To verify
120 CLOSE #1
130 KILL"TMP"
140 PRINT"Removing temporary file TMP."
150 IF KP$<>VP$ THEN PRINT"KP$<>VP$":PRINT"KP$:";KP$:PRINT"VP$:"VP$:STOP
160 PRINT"Saving ciphertext in temporary file TMP."
170 SAVE"TMP",P
180 PRINT"Reading cyphertext from temporary file TMP."
190 OPEN"TMP"FOR INPUT AS #1
200 CX$=INPUT$(143,1) ' Padding
210 CT$=INPUT$(143,1) ' To verify
220 CLOSE #1
230 KILL"TMP"
240 PRINT"Removing temporary file TMP."
250 CK$="":FOR I=0 TO 142:CK$=CK$+CHR$(((ASC(MID$(CT$,I+1,1))+256-11+(I MOD 11))MOD 256)XOR 128):NEXT I
260 PRINT"Combined key:":FOR I=1 TO LEN(CK$):PRINT MID$(HEX$(256+ASC(MID$(CK$,I,1))),2);" ";:NEXT I:PRINT
270 DC$="":FOR I=0 TO LEN(CT$)-1:DC$=DC$+CHR$(((((ASC(MID$(CT$,I+1,1))+256-11+(I MOD 11))MOD 256)XOR ASC(MID$(CK$,1+(I MOD 143),1)))+13-(I MOD 13))MOD 256):NEXT I
280 IF KP$<>DC$ THEN PRINT"KP$<>DC$":PRINT"KP$:";KP$:PRINT"DC$:"DC$:STOP
290 PRINT"Combined key has been verified to decrypt plaintext without ROM data."
300 PRINT"Saving combined key in CK.DAT."
310 OPEN"CK.DAT" FOR OUTPUT AS #1
320 PRINT #1,CK$;
330 CLOSE #1
340 PRINT"Done."
350 END
```
The BASIC program also demonstrates decryption using the combined key, without reference to the key data in ROM.

Here's the combined key material from CK.DAT: _(this is just the second 143-byte block of my saved BASIC file with a repeating 11... 1 down-counter subtracted from each byte, it does not contain any NEC ROM data)_
```python
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
```
# Unrelated bonus! De-obfuscation, GW-BASIC version
Basically the same method, with minimal changes for later FAT and syntax changes, works for getting a combined key for obfuscated GW-BASIC saves. I think it's not relevant for FAT8 so the script in this repo does not include it, but here it is for posterity:
```basic
10 ' The length of the comment is important. Do not change it! It needs to leave the first byte of KP$ at file offset 143. ''''''
20 KP$="ìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéüìîïèëêçåàäâéü"
30 WIDTH 80:SCREEN,,0:CLS
40 V1$="":FOR J=11 TO 1 STEP -1:FOR I=13 TO 1 STEP -1:V1$=V1$+CHR$(128+I):NEXT I:NEXT J
50 IF KP$<>V1$ THEN PRINT"Program is corrupt. Re-enter:":PRINT"20 KP$="+CHR$(34)+V1$+CHR$(34):STOP
60 PRINT"Saving known plaintext in temporary file TMP.BAS."
70 SAVE"TMP.BAS"
80 PRINT"Verifying known plaintext in temporary file TMP.BAS."
90 OPEN"TMP.BAS"FOR INPUT AS #1
100 XP$=INPUT$(143,1) ' Padding
110 VP$=INPUT$(143,1) ' To verify
120 CLOSE #1
130 KILL"TMP.BAS"
140 PRINT"Removing temporary file TMP.BAS."
150 IF KP$<>VP$ THEN PRINT"KP$<>VP$":PRINT"KP$:";KP$:PRINT"VP$:"VP$:STOP
160 PRINT"Saving ciphertext in temporary file TMP.BAS."
170 SAVE"TMP.BAS",P
180 PRINT"Reading cyphertext from temporary file TMP.BAS."
190 OPEN"TMP.BAS"FOR INPUT AS #1
200 CX$=INPUT$(143,1) ' Padding
210 CT$=INPUT$(143,1) ' To verify
220 CLOSE #1
230 KILL"TMP.BAS"
240 PRINT"Removing temporary file TMP.BAS."
250 CK$="":FOR I=0 TO 142:CK$=CK$+CHR$(((ASC(MID$(CT$,I+1,1))+256-11+(I MOD 11))MOD 256)XOR 128):NEXT I
260 PRINT"Combined key:":FOR I=1 TO LEN(CK$):PRINT MID$(HEX$(256+ASC(MID$(CK$,I,1))),2);" ";:NEXT I:PRINT
270 DC$="":FOR I=0 TO LEN(CT$)-1:DC$=DC$+CHR$(((((ASC(MID$(CT$,I+1,1))+256-11+(I MOD 11))MOD 256)XOR ASC(MID$(CK$,1+(I MOD 143),1)))+13-(I MOD 13))MOD 256):NEXT I
280 IF KP$<>DC$ THEN PRINT"KP$<>DC$":PRINT"KP$:";KP$:PRINT"DC$:"DC$:STOP
290 PRINT"Combined key has been verified to decrypt plaintext without ROM data."
300 PRINT"Saving combined key in CK.DAT."
310 OPEN"CK.DAT" FOR OUTPUT AS #1
320 PRINT #1,CK$;
330 CLOSE #1
340 PRINT"Done."
350 END
```
The BASIC program also demonstrates decryption using the combined key, without reference to the key data in GW-BASIC's binary executable.

Here's the combined key material from CK.DAT: _(this is just the second 143-byte block of my saved BASIC file with a repeating 11... 1 down-counter subtracted from each byte, it does not contain any data from GW-BASIC's binary executable)_
```python
DOS_V_COMBINED_KEY = (
   0xE0, 0x49, 0x67, 0xB7, 0x46, 0xAD, 0xEC, 0x5D, 0xE9, 0x83, 0xF5,
   0x90, 0x17, 0x8C, 0x93, 0x0D, 0x55, 0xA6, 0x6B, 0x09, 0xE6, 0x15,
   0x9D, 0x63, 0xFC, 0xCD, 0xE2, 0x71, 0xED, 0x93, 0x47, 0xD4, 0xF5,
   0xB6, 0x83, 0xC7, 0xB9, 0x92, 0x2F, 0x02, 0xB7, 0x10, 0x2C, 0xBB,
   0xEC, 0x63, 0xA2, 0x59, 0xAD, 0x5B, 0x72, 0xE9, 0xE3, 0x10, 0xF4,
   0x04, 0x2D, 0x98, 0xB9, 0xCC, 0xBB, 0x4D, 0x9D, 0x93, 0x52, 0x1F,
   0x20, 0x66, 0x70, 0xF7, 0xFE, 0x5B, 0x2C, 0x7D, 0xB0, 0x26, 0x6F,
   0x6A, 0x89, 0x4C, 0xC0, 0x06, 0x15, 0x1E, 0x9D, 0xC9, 0xC6, 0x54,
   0xF6, 0xF9, 0x16, 0x53, 0x22, 0x5E, 0xE6, 0xD3, 0xFF, 0x26, 0x35,
   0xD6, 0xC6, 0x62, 0x23, 0x80, 0xB1, 0xC2, 0x9C, 0x07, 0x6C, 0x03,
   0xF6, 0xA3, 0x82, 0x20, 0x0C, 0xC1, 0xA0, 0x77, 0x23, 0x23, 0xFB,
   0x44, 0x95, 0x62, 0x79, 0xEC, 0xFE, 0xEC, 0x07, 0x7D, 0xD0, 0xDF,
   0xFD, 0x6D, 0x30, 0x4F, 0x0C, 0x9B, 0x0C, 0x3C, 0x09, 0xC0, 0x81,
)
```
