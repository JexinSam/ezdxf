# Copyright (c) 2016-2023, Manfred Moitzi
# License: MIT License
import re
import codecs
import binascii

surrogate_escape = codecs.lookup_error("surrogateescape")
BACKSLASH_UNICODE = re.compile(r"(\\U\+[A-Fa-f0-9]{4})")
MIF_ENCODED = re.compile(r"(\\M\+[1-5][A-Fa-f0-9]{4})")


def dxf_backslash_replace(exc: Exception):
    if isinstance(exc, (UnicodeEncodeError, UnicodeTranslateError)):
        s = ""
        # mypy does not recognize properties: exc.start, exc.end, exc.object
        for c in exc.object[exc.start : exc.end]:
            x = ord(c)
            if x <= 0xFF:
                s += "\\x%02x" % x
            elif 0xDC80 <= x <= 0xDCFF:
                # Delegate surrogate handling:
                return surrogate_escape(exc)
            elif x <= 0xFFFF:
                s += "\\U+%04x" % x
            else:
                s += "\\U+%08x" % x
        return s, exc.end
    else:
        raise TypeError(f"Can't handle {exc.__class__.__name__}")


def encode(s: str, encoding="utf8") -> bytes:
    """Shortcut to use the correct error handler"""
    return s.encode(encoding, errors="dxfreplace")


def _decode(s: str) -> str:
    if s.startswith(r"\U+"):
        return chr(int(s[3:], 16))
    else:
        return s


def has_dxf_unicode(s: str) -> bool:
    """Returns ``True``  if string `s` contains ``\\U+xxxx`` encoded characters."""
    return bool(re.search(BACKSLASH_UNICODE, s))


def decode_dxf_unicode(s: str) -> str:
    """Decode ``\\U+xxxx`` encoded characters."""

    return "".join(_decode(part) for part in re.split(BACKSLASH_UNICODE, s))


def decode_bigfont_unicode(s: str, encoding: str = "cp932") -> str:
    """Decode ``\\U+xxxx`` sequences that represent bigfont (Shift-JIS) characters.
    
    When DXF files use bigfont for Asian text (e.g., Japanese Shift-JIS), the double-byte
    characters are stored as bytes that get misinterpreted as Windows-1252 characters,
    then encoded as ``\\U+xxxx`` Unicode escapes. This function:
    1. Decodes the ``\\U+xxxx`` sequences to Unicode characters
    2. Encodes each character to Windows-1252 bytes (with latin-1 fallback)
    3. Decodes those bytes as the target encoding (default: Shift-JIS/cp932)
    
    Args:
        s: String potentially containing bigfont-encoded ``\\U+xxxx`` sequences
        encoding: The target encoding for bigfont text (default: "cp932" for Japanese)
        
    Returns:
        Decoded string with proper Asian characters
        
    Example:
        >>> s = r"\\U+0192v\\U+0192\\U+0152\\U+0081[\\U+0192g"
        >>> decode_bigfont_unicode(s)
        'プレート'  # Japanese text
    """
    if not has_dxf_unicode(s):
        return s
    
    # First decode the \U+xxxx sequences to Unicode characters
    decoded_unicode = decode_dxf_unicode(s)
    
    # Convert each Unicode character to a byte sequence
    byte_list = []
    for ch in decoded_unicode:
        code = ord(ch)
        
        # ASCII pass-through (common to both)
        if code <= 0x7F:
            byte_list.append(code)
            continue
        
        # Try cp1252 first (handles U+0192→0x83, U+0152→0x8C, etc.)
        # This recovers the "Bigfont Misinterpretation" bytes
        try:
            byte_val = ch.encode('cp1252')[0]
            byte_list.append(byte_val)
            continue
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        
        # Fallback to direct code for 0x80-0xFF range (control characters, latin-1)
        if code <= 0xFF:
            byte_list.append(code)
            continue
            
        # If we get here, it's a character > 0xFF that is NOT in cp1252 (e.g. CJK chars)
        # Assume this is a valid Unicode character that should be preserved.
        # To preserve it in the byte stream for Shift-JIS decoding, we must
        # encode it as Shift-JIS bytes.
        try:
            # Encode just this character to Shift-JIS bytes
            # e.g. '工' -> b'\x8dH'
            sjis_bytes = ch.encode(encoding)
            byte_list.extend(sjis_bytes)
        except UnicodeEncodeError:
            # If it can't be encoded to Shift-JIS (e.g. Emoji), we have a problem.
            # We can't include it in the byte stream easily without messing up 
            # subsequent decoding. 
            # Best effort: ignore it or replace?
            # Let's replace with a '?' byte (0x3F) to match 'replace' behavior
            byte_list.append(0x3F)

    
    # Decode the bytes as the target encoding (Shift-JIS)
    # Decode the bytes as the target encoding (Shift-JIS)
    try:
        byte_data = bytes(byte_list)
        return byte_data.decode(encoding, errors='replace')
    except Exception:
        # If decoding fails, return the standard Unicode-decoded version
        return decoded_unicode


def has_mif_encoding(s: str) -> bool:
    """Returns ``True`` if string `s` contains MIF encoded (``\\M+cxxxx``) characters.
    """
    return bool(re.search(MIF_ENCODED, s))


def decode_mif_to_unicode(s: str) -> str:
    """Decode MIF encoded characters ``\\M+cxxxx``."""
    return "".join(_decode_mif(part) for part in re.split(MIF_ENCODED, s))


MIF_CODE_PAGE = {
    # See https://docs.intellicad.org/files/oda/2021_11/oda_drawings_docs/frames.html?frmname=topic&frmfile=FontHandling.html
    "1": "cp932",  # Japanese (Shift-JIS)
    "2": "cp950",  # Traditional Chinese (Big 5)
    "3": "cp949",  # Wansung (KS C-5601-1987)
    "4": "cp1391",  # Johab (KS C-5601-1992)
    "5": "cp936",  # Simplified Chinese (GB 2312-80)
}


def _decode_mif(s: str) -> str:
    if s.startswith(r"\M+"):
        try:
            code_page = MIF_CODE_PAGE[s[3]]
            codec = codecs.lookup(code_page)
            byte_data = binascii.unhexlify(s[4:])
            return codec.decode(byte_data)[0]
        except Exception:
            pass
    return s
