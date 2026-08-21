#!/usr/bin/env python3
"""
Record every word Odd One Out says, as real audio files.

The voice built into an iPad sounds robotic, and Apple does not hand its good
voices to a web page, so the game cannot get a human-sounding voice by asking
for one. Instead every word it will ever say is recorded up front — the
vocabulary is fixed and small — and the game plays those recordings.

Run this once. It needs a working internet connection and nothing else:
the voices are Microsoft's neural ones, which are free and need no account.

    pip3 install edge-tts
    python3 tools/make-voice-clips.py

It writes about 270 small files into the audio/ folder, plus a list of what it
made. Upload that whole folder to the repository and the game starts using it.

To hear a different voice, pass one in:

    python3 tools/make-voice-clips.py --voice en-US-AnaNeural

    en-US-JennyNeural   warm and friendly, the default
    en-US-AriaNeural    clear and neutral
    en-US-AnaNeural     a child's voice
    en-US-GuyNeural     male
    python3 tools/make-voice-clips.py --list-voices   to see them all
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
GAME = os.path.join(REPO, "oddoneout.html")
OUT = os.path.join(REPO, "audio")

DEFAULT_VOICE = "en-US-JennyNeural"
# Slower than conversational, to match how the game paces itself for a child.
DEFAULT_RATE = "-15%"


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
    return names, groups, lines


def slug(text):
    """A stable filename for a line of speech.

    The game never recomputes this — it looks names up in manifest.json — so
    the rule can change freely without breaking anything already recorded.
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


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default=DEFAULT_VOICE)
    ap.add_argument("--rate", default=DEFAULT_RATE)
    ap.add_argument("--list-voices", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="re-record clips that already exist")
    args = ap.parse_args()

    try:
        import edge_tts  # noqa: F401
    except ImportError:
        die("edge-tts isn't installed yet. Run:  pip3 install edge-tts")

    if args.list_voices:
        await list_voices()
        return

    names, groups, lines = read_game()
    # What the game will ask for, and the words to say for each.
    wanted = {}
    for n in names:
        wanted[n] = n
    for g in groups:
        wanted["The others are all " + g + "."] = "The others are all " + g + "."
    for l in lines:
        wanted[l] = l

    os.makedirs(OUT, exist_ok=True)
    total = len(wanted)
    print("\n  Recording %d clips in %s\n" % (total, args.voice))

    import edge_tts
    manifest = {}
    made = skipped = 0
    for i, text in enumerate(sorted(wanted), 1):
        name = slug(text) + ".mp3"
        path = os.path.join(OUT, name)
        manifest[text] = name
        if os.path.exists(path) and os.path.getsize(path) > 0 and not args.force:
            skipped += 1
            continue
        try:
            await edge_tts.Communicate(text, args.voice, rate=args.rate).save(path)
        except Exception as e:
            # Don't leave a half-written file behind to be trusted later.
            if os.path.exists(path):
                os.remove(path)
            die("Failed on %r after %d clips: %s\n"
                "  Check the internet connection and run it again — "
                "finished clips are kept, so it picks up where it stopped." % (text, made, e))
        made += 1
        if made % 20 == 0 or i == total:
            print("    %d / %d" % (i, total))

    with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"voice": args.voice, "rate": args.rate, "clips": manifest}, f,
                  indent=1, ensure_ascii=False, sort_keys=True)

    size = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT))
    print("\n  Done. %d recorded, %d already there. %.1f MB in the audio folder."
          % (made, skipped, size / 1024.0 / 1024.0))
    print("\n  Now upload the whole 'audio' folder to the repository and the")
    print("  game will start using it. Nothing else needs changing.\n")


if __name__ == "__main__":
    asyncio.run(main())
