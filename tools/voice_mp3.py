"""Just enough MP3 reading to join clips end to end and know where each one sits.

There is no ffmpeg in this environment, and none on a plain Mac either, so
this does the small amount of MP3 handling the job needs by hand.

An MP3 is nothing but a run of self-contained frames, one after another. Each
frame starts with a four-byte header saying how it was encoded, and every clip
the voice service returns uses the same settings, so the frames from two clips
can be laid end to end and the result is a valid MP3. That is the whole trick:
one file is just all the clips' frames in a row.

Because these particular files are constant bitrate, every frame is exactly the
same number of bytes and lasts exactly the same length of time, so counting
frames gives an exact position in seconds — no guessing, no drift.
"""

# Bits 4-3 of the second header byte: which MPEG version.
MPEG1, MPEG2, MPEG25 = 3, 2, 0
# Layer III bitrates, in kbps, indexed by the top four bits of the third byte.
BITRATE_MPEG1 = [None, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]
BITRATE_MPEG2 = [None, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]
SAMPLE_RATE = {0: 44100, 1: 48000, 2: 32000}


class BadMp3(Exception):
    pass


def _header(b, i):
    """Read one frame header. Returns (length in bytes, samples, sample rate)."""
    if i + 4 > len(b) or b[i] != 0xFF or (b[i + 1] & 0xE0) != 0xE0:
        raise BadMp3("no frame at byte %d" % i)
    ver = (b[i + 1] >> 3) & 3
    layer = (b[i + 1] >> 1) & 3
    bitrate_i = (b[i + 2] >> 4) & 0xF
    rate_i = (b[i + 2] >> 2) & 3
    padding = (b[i + 2] >> 1) & 1
    if layer != 1 or rate_i == 3 or bitrate_i in (0, 15):
        raise BadMp3("not a plain layer III frame at byte %d" % i)

    rate = SAMPLE_RATE[rate_i]
    if ver == MPEG2:
        rate //= 2
    elif ver == MPEG25:
        rate //= 4
    elif ver != MPEG1:
        raise BadMp3("reserved MPEG version at byte %d" % i)

    kbps = (BITRATE_MPEG1 if ver == MPEG1 else BITRATE_MPEG2)[bitrate_i]
    samples = 1152 if ver == MPEG1 else 576
    length = samples // 8 * (kbps * 1000) // rate + padding
    return length, samples, rate


def read(path):
    """Return (frame bytes, frame count, seconds per frame, the 4-byte header).

    Rejects anything it cannot account for byte-for-byte. A clip that is half
    downloaded would otherwise be joined in silently and shift every position
    after it, which is exactly the kind of fault that only shows up as the
    wrong word being spoken three weeks later.
    """
    b = open(path, "rb").read()
    i = 0
    # Some encoders put a tag on the front. Skip it; it is not audio.
    if b[:3] == b"ID3":
        i = 10 + ((b[6] & 0x7F) << 21 | (b[7] & 0x7F) << 14 |
                  (b[8] & 0x7F) << 7 | (b[9] & 0x7F))
    start = i
    count = 0
    first = None
    while i < len(b):
        length, samples, rate = _header(b, i)
        if first is None:
            first = (length, samples, rate, bytes(b[i:i + 4]))
        elif (length, samples, rate) != first[:3]:
            raise BadMp3("%s changes format part-way through" % path)
        i += length
        count += 1
    if not count:
        raise BadMp3("%s has no audio in it" % path)
    if i != len(b):
        raise BadMp3("%s stops in the middle of a frame — re-record it" % path)
    length, samples, rate, head = first
    return b[start:], count, samples / float(rate), head


def silence(head, frames):
    """A run of silent frames in the same format, to sit between clips.

    A layer III frame whose body is all zeros asks the decoder for no audio
    data at all, which comes out as silence. Keeping the same header means it
    is the same shape as every other frame, so the file stays constant bitrate
    and positions stay exact.
    """
    length, _samples, _rate = _header(head + b"\0" * 4, 0)
    return (bytes(head) + b"\0" * (length - 4)) * frames
