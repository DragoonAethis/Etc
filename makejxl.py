#!/usr/bin/env python3
import os
import glob
import time
import threading
import subprocess
from concurrent.futures import ProcessPoolExecutor

# Convert files in the current directory to JPEG XL,
# preserving modification/access times from the original file.

# Delete the original file after conversion?
DELETE_ORIGINAL = True

# File extensions on which we allow processing
EXTENSIONS = {'.jpg', '.jpeg', '.webp', '.png', '.ppm', '.gif'}
LOSSLESS_EXTS = {'.jpg', '.jpeg'}

# Encoder "effort" setting, higher = slower, but smaller at the same quality level.
# Range is 1..10, cjxl default is 7, 8 generates noticeably smaller files, 9/10 not really.
EFFORT = 8

# Quality is not set here as cjxl has very sane defaults:
# - lossless for lossy inputs (existing JPEG/GIF)
# - visually lossless for lossless inputs (PNGs, etc)

# Extra args if you need them:
CJXL_EXTRA_ARGS = []


def process_file(filename: str):
    old_name, old_ext = os.path.splitext(filename)
    old_stat = os.stat(filename)
    new_filename = old_name + ".jxl"

    process = subprocess.run([
        "cjxl",
        f"--effort={EFFORT}",
        *CJXL_EXTRA_ARGS,
        filename,
        new_filename,
    ], capture_output=True)

    if process.returncode != 0:
        print(f"[-] ERROR: {filename}: {process}")
        return

    os.utime(new_filename, times=None, ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns))
    if DELETE_ORIGINAL:
        os.unlink(filename)


def print_progress(executor):
    while (queue_length := len(executor._pending_work_items)) > 0:
        print(f"Pending items: {queue_length}")
        time.sleep(1)


def process_collection():
    valid_filenames = []

    with ProcessPoolExecutor(max_workers=4) as e:
        counter = 0
        t = threading.Thread(target=print_progress, args=(e, ))
        for fname in glob.glob("*"):
            if os.path.splitext(fname)[1].lower() not in EXTENSIONS:
                continue

            e.submit(process_file, fname)
            counter += 1

        print(f"Scheduled {counter} item(s), please wait...")
        t.start()

    t.join()
    print("All done!")


if __name__ == "__main__":
    try:
        subprocess.run(['cjxl', '--version'])
    except FileNotFoundError:
        exit("cjxl binary was not found in your PATH (did you install libjxl tools?)")

    process_collection()
