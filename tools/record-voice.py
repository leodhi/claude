#!/usr/bin/env python3
"""
Record the Odd One Out voice on a Mac, with nothing to set up beforehand.

This is the one-paste version. It exists because the other script assumes you
already have the project on your computer and know how to get a Terminal into
the right folder — which is a fair amount to ask of someone who just wants the
game to stop sounding like a robot.

Paste this one line into Terminal and press Return:

    curl -fsSL https://raw.githubusercontent.com/leodhi/claude/main/tools/record-voice.py | python3

It does the following, printing where it has got to as it goes:

  1. Makes a folder called "Odd One Out voice" in your home folder.
  2. Downloads the word list and the recorder into it.
  3. Sets up its own private copy of the bits it needs, so it never has to
     change anything else on the computer.
  4. Records all the words. This is the slow part.
  5. Joins them into one audio file and puts it on your Desktop, along with
     the small list that says where each word is.

Then drag those two files into GitHub and the game uses them.

To hear a few different voices first, instead of recording everything in one
you might not like, add --voices to the end of that line:

    curl -fsSL <the same address> | python3 - --voices

That drops a folder on your Desktop with the same sentence read by each voice.

Running it a second time is safe and quick: words already recorded are kept.
When you're finished you can drag the "Odd One Out voice" folder to the Trash;
nothing outside it was touched.
"""

import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

SOURCE = "https://raw.githubusercontent.com/leodhi/claude/main/"
HOME = os.path.expanduser("~")
WORK = os.path.join(HOME, "Odd One Out voice")
DESKTOP = os.path.join(HOME, "Desktop")

# Laid out the way the recorder expects to find things, so that it is the
# same script doing the work here as in the project — not a second copy of it
# that can quietly drift out of step.
NEEDED = [
    "oddoneout.html",           # the word list is read straight out of the game
    "tools/make-voice-clips.py",
    "tools/voice_mp3.py",
]


def step(n, msg):
    print("\n  %d. %s" % (n, msg))


def stop(msg):
    print("\n  ---")
    print("  " + msg.replace("\n", "\n  "))
    print("  ---\n")
    sys.exit(1)


def fetch(source, rel, dest):
    url = source + rel
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        stop("Couldn't download %s (the server said %s).\n"
             "If you're on a fork, pass --source with your own address." % (rel, e.code))
    except Exception as e:
        stop("Couldn't reach the internet to download %s.\n"
             "Check the connection and run the same line again.\n(%s)" % (rel, e))
    if not data:
        stop("Downloaded %s but it was empty. Try again in a moment." % rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    open(dest, "wb").write(data)
    return len(data)


def python_in(env_dir):
    """Where the private copy of Python lives, on a Mac or anywhere else."""
    for rel in ("bin/python", "Scripts/python.exe"):
        p = os.path.join(env_dir, *rel.split("/"))
        if os.path.exists(p):
            return p
    return None


def main():
    args = sys.argv[1:]
    source = SOURCE
    if "--source" in args:
        i = args.index("--source")
        source = args[i + 1].rstrip("/") + "/"
        del args[i:i + 2]

    print("\n  Odd One Out — recording the voice")
    print("  " + "-" * 34)
    print("\n  Working in: %s" % WORK)

    step(1, "Getting the word list and the recorder…")
    os.makedirs(WORK, exist_ok=True)
    for rel in NEEDED:
        size = fetch(source, rel, os.path.join(WORK, *rel.split("/")))
        print("       %-28s %6.1f KB" % (rel, size / 1024.0))

    step(2, "Setting up the voice software (only slow the first time)…")
    env_dir = os.path.join(WORK, "python-bits")
    py = python_in(env_dir)
    if not py:
        try:
            # A private copy, so nothing already on the computer is disturbed —
            # and so the "externally managed environment" refusal that newer
            # Macs give to a plain install can't happen.
            subprocess.run([sys.executable, "-m", "venv", env_dir], check=True)
        except Exception as e:
            stop("Couldn't set up a private copy of Python.\n(%s)" % e)
        py = python_in(env_dir)
    if not py:
        stop("Set up a private copy of Python but can't find it in %s." % env_dir)

    have = subprocess.run([py, "-c", "import edge_tts"], capture_output=True)
    if have.returncode != 0:
        r = subprocess.run([py, "-m", "pip", "install", "--quiet", "edge-tts"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            stop("Couldn't install the voice software.\n\n" + (r.stderr or r.stdout).strip())
    print("       ready")

    # Hearing a few voices first, rather than recording everything in one you
    # might not like. Nobody can pick a voice from its name.
    if "--voices" in args:
        args.remove("--voices")
        out = os.path.join(DESKTOP, "Odd One Out voices")
        step(3, "Recording the same line in a few voices to compare…")
        r = subprocess.run([py, os.path.join(WORK, "tools", "make-voice-clips.py"),
                            "--sample", out] + args)
        if r.returncode != 0:
            stop("Couldn't record the samples — see the message just above.")
        print("\n  " + "-" * 34)
        print("  Done. There's a folder on your Desktop called")
        print("  \"Odd One Out voices\" with one clip per voice.")
        print("\n  Play each one, then tell Claude which number you liked.\n")
        if sys.platform == "darwin":
            subprocess.run(["open", out], check=False)
        return

    step(3, "Recording the words. This is the slow part — leave it running.")
    r = subprocess.run([py, os.path.join(WORK, "tools", "make-voice-clips.py"),
                        "--brief"] + args)
    if r.returncode != 0:
        stop("Recording stopped early — see the message just above.\n"
             "Nothing is lost: run the same line again and it carries on.")

    step(4, "Putting the finished files on your Desktop…")
    made = []
    for name in ("oddoneout-voice.mp3", "oddoneout-voice.json"):
        src = os.path.join(WORK, name)
        if not os.path.exists(src):
            stop("Expected %s to have been made, but it wasn't there." % name)
        shutil.copyfile(src, os.path.join(DESKTOP, name))
        made.append(os.path.join(DESKTOP, name))
        print("       %s" % os.path.join("~/Desktop", name))

    print("\n  " + "-" * 34)
    print("  Done. Two files are on your Desktop:\n")
    print("      oddoneout-voice.mp3")
    print("      oddoneout-voice.json")
    print("\n  Drag BOTH into GitHub together, into the top level of the")
    print("  project (the same place oddoneout.html is), and commit.")
    print("\n  You can drag the \"Odd One Out voice\" folder to the Trash now.\n")

    # Open a Finder window with them showing, so there's nothing to go and find.
    if sys.platform == "darwin":
        try:
            subprocess.run(["open", "-R", made[0]], check=False)
        except Exception:
            pass


if __name__ == "__main__":
    main()
