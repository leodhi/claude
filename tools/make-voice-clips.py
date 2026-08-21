#!/usr/bin/env python3
"""
Record every word Odd One Out says, as one audio file.

The voice built into an iPad sounds robotic, and Apple does not hand its good
voices to a web page, so the game cannot get a human-sounding voice by asking
for one. Instead every word it will ever say is recorded up front — the
vocabulary is fixed and small — and the game plays those recordings.

What you get is TWO files, both dropped in this folder:

    oddoneout-voice.mp3    all the words, one after another (about 4 MB)
    oddoneout-voice.json   a tiny list of where each word sits inside it

Drag both into GitHub in one go and the game starts using them. There is no
folder of hundreds of files any more, and nothing to upload in batches.

Run it like this. It needs a working internet connection and nothing else:
the voices are Microsoft's neural ones, which are free and need no account.

    pip3 install edge-tts
    python3 tools/make-voice-clips.py

It takes a few minutes. Each word is saved in .voice-cache/ as it is recorded,
so if the connection drops you can run it again and it picks up where it left
off rather than starting over. That folder is scratch space — it is never
uploaded, and you can delete it once you have the two files.

To hear a different voice, pass one in (this re-records everything):

    python3 tools/make-voice-clips.py --voice en-US-AnaNeural

    en-US-JennyNeural   warm and friendly, the default
    en-US-AriaNeural    clear and neutral
    en-US-AnaNeural     a child's voice
    en-US-GuyNeural     male
    python3 tools/make-voice-clips.py --list-voices   to see them all

If you already have the individual clips from an earlier run sitting in some
other folder, point at it and they will be used instead of re-recorded:

    python3 tools/make-voice-clips.py --from ~/Desktop/audio
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import voice_mp3  # noqa: E402

GAME = os.path.join(REPO, "oddoneout.html")
CACHE = os.path.join(REPO, ".voice-cache")
AUDIO_OUT = os.path.join(REPO, "oddoneout-voice.mp3")
INDEX_OUT = os.path.join(REPO, "oddoneout-voice.json")

DEFAULT_VOICE = "en-US-JennyNeural"
# Slower than conversational, to match how the game paces itself for a child.
DEFAULT_RATE = "-15%"

# Silence dropped in front of every word. The game starts playing a couple of
# frames early, inside this gap, so that seeking cannot shave the start off a
# word — landing in silence is free, landing late loses the first sound.
GAP_FRAMES = 10
LEAD_IN_FRAMES = 2


def die(msg):
    print("\n  " + msg + "\n", file=sys.stderr)
    sys.exit(1)


def read_game():
    """Pull the word list out of the game itself, so the two can never drift."""
    if not os.path.exists(GAME):
        die("Can't find oddoneout.html. Run this from inside the project folder.")
    src = open(GAME, encoding="utf-8").read()

    block = re.search(r"var GROUPS = \{(.*?)\n\};", src, re.S)
    if not block:
        die("Couldn't find the picture list in oddoneout.html.")

    # Every ["<emoji>","<name>"] pair is one picture.
    names = []
    for _emoji, name in re.findall(r'\["([^"]+)","([^"]+)"\]', block.group(1)):
        if name not in names:
            names.append(name)

    # many: "fruit" -> the game says "The others are all fruit."
    groups = []
    for many in re.findall(r'many:\s*"([^"]+)"', block.group(1)):
        if many not in groups:
            groups.append(many)

    def const(var):
        m = re.search(r'var %s = "((?:[^"\\]|\\.)*)"' % var, src)
        return m.group(1).replace('\\"', '"').replace("\\'", "'") if m else None

    lines = []
    for var in ("ASK_IN_FULL", "ASK_BRIEFLY"):
        v = const(var)
        if v:
            lines.append(v)

    # Said when they get it right or wrong, and at the end of a game.
    for extra in ["Yes! Well done!", "That's it!", "Brilliant!", "You got it!",
                  "Try again", "All done! Great playing!"]:
        if extra not in lines:
            lines.append(extra)

    if not names or not groups:
        die("Read the game but found no words. Has oddoneout.html changed shape?")

    wanted = list(names)
    wanted += ["The others are all " + g + "." for g in groups]
    wanted += lines
    # Sorted so the file is laid out the same way every time it is built.
    return sorted(set(wanted))


def slug(text):
    """A stable filename for one recorded line, inside the scratch folder.

    Nothing outside this script ever sees these names, so the rule can change
    freely — the worst it costs is re-recording.
    """
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    s = s[:48] or "clip"
    # Keep a short hash so two lines can never collide after squashing.
    return s + "-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]


async def list_voices():
    import edge_tts
    voices = await edge_tts.list_voices()
    for v in sorted(voices, key=lambda v: v["ShortName"]):
        if v["Locale"].startswith("en-"):
            print("  %-28s %s" % (v["ShortName"], v.get("Gender", "")))


def join(wanted, paths, voice, rate):
    """Lay every clip end to end and write down where each one starts.

    Positions are counted in frames rather than seconds because frames are
    whole numbers — there is no rounding anywhere, so a word can never be cut
    short by a fraction that crept in.
    """
    chunks = []
    index = {}
    at = 0            # how many frames are already laid down
    seconds = None
    header = None

    for text in wanted:
        audio, frames, per_frame, head = voice_mp3.read(paths[text])
        if seconds is None:
            seconds, header = per_frame, head
        elif per_frame != seconds:
            die("The clip for %r was recorded at different settings from the "
                "rest. Delete .voice-cache and run this again." % text)

        chunks.append(voice_mp3.silence(header, GAP_FRAMES))
        at += GAP_FRAMES
        # Start a shade early, inside the silence, so nothing gets clipped.
        index[text] = [at - LEAD_IN_FRAMES, frames + LEAD_IN_FRAMES]
        chunks.append(audio)
        at += frames

    with open(AUDIO_OUT, "wb") as f:
        for c in chunks:
            f.write(c)

    with open(INDEX_OUT, "w", encoding="utf-8") as f:
        json.dump({
            "voice": voice,
            "rate": rate,
            # Everything below is measured in frames; this is how long one lasts.
            "frameSeconds": round(seconds, 9),
            "clips": index,
        }, f, indent=1, ensure_ascii=False, sort_keys=True)

    return at, seconds


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--rate", default=DEFAULT_RATE)
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="re-record clips that already exist")
    ap.add_argument("--from", dest="source", default=None,
                    help="a folder of clips from an earlier run, to reuse")
    ap.add_argument("--offline", action="store_true",
                    help="don't record anything; build the file from whatever "
                         "clips are already on disk, even if some are missing")
    args = ap.parse_args()

    if args.list_voices:
        await list_voices()
        return

    wanted = read_game()
    os.makedirs(CACHE, exist_ok=True)

    # Where each line's clip is, or should end up.
    paths = {t: os.path.join(CACHE, slug(t) + ".mp3") for t in wanted}

    # Anything already recorded elsewhere counts, so a re-run costs nothing.
    if args.source:
        spare = os.path.abspath(os.path.expanduser(args.source))
        found = 0
        for text, dest in paths.items():
            other = os.path.join(spare, slug(text) + ".mp3")
            if not os.path.exists(dest) and os.path.exists(other):
                open(dest, "wb").write(open(other, "rb").read())
                found += 1
        print("\n  Reused %d clips from %s" % (found, spare))

    def missing():
        return [t for t in wanted if not (os.path.exists(paths[t])
                                          and os.path.getsize(paths[t]) > 0)]

    todo = wanted if args.force else missing()

    if args.offline:
        # Build with what's here. Any word left out simply isn't in the index,
        # and the game falls back to the device's own voice for it — so a
        # part-recorded file is still an improvement, never a broken one.
        todo = []
        if missing():
            print("\n  %d of %d words have no recording yet. Building without "
                  "them; the game will read those in the device's own voice."
                  % (len(missing()), len(wanted)))
        wanted = [t for t in wanted if t not in set(missing())]

    if todo:
        try:
            import edge_tts
        except ImportError:
            die("edge-tts isn't installed yet. Run:  pip3 install edge-tts")

        print("\n  Recording %d of %d words in %s\n" % (len(todo), len(wanted), args.voice))
        for i, text in enumerate(todo, 1):
            path = paths[text]
            try:
                await edge_tts.Communicate(text, args.voice, rate=args.rate).save(path)
            except Exception as e:
                # Don't leave a half-written file behind to be trusted later.
                if os.path.exists(path):
                    os.remove(path)
                die("Stopped at %r after %d words: %s\n"
                    "  Check the internet connection and run it again — finished "
                    "words are kept, so it carries on from here." % (text, i - 1, e))
            if i % 20 == 0 or i == len(todo):
                print("    %d / %d" % (i, len(todo)))
    else:
        print("\n  All %d words are already recorded." % len(wanted))

    still = [t for t in wanted if t in set(missing())]
    if still:
        die("%d words still have no recording, e.g. %r." % (len(still), still[0]))

    print("\n  Joining them into one file…")
    frames, per_frame = join(wanted, paths, args.voice, args.rate)
    size = os.path.getsize(AUDIO_OUT) / 1024.0 / 1024.0
    print("\n  Done. %d words, %.1f minutes, %.1f MB."
          % (len(wanted), frames * per_frame / 60.0, size))
    print("\n  Two files are ready in this folder:")
    print("      oddoneout-voice.mp3")
    print("      oddoneout-voice.json")
    print("\n  Drag both into GitHub together and the game will use them.\n")


if __name__ == "__main__":
    asyncio.run(main())
