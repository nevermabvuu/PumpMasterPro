"""
build_obfuscate.py — Production JavaScript Obfuscation Pipeline.

Safely preserves human-readable source files in `static/js_src/` and outputs
hardened, compact, base64-encrypted, obfuscated JavaScript to `static/js/`
for deployment to the browser.

Usage:
    python build_obfuscate.py          # Obfuscates all JS files from js_src -> js
    python build_obfuscate.py --restore # Restores readable source files from js_src -> js
"""

import os
import sys
import shutil
import subprocess
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JS_DIR = os.path.join(BASE_DIR, 'static', 'js')
JS_SRC_DIR = os.path.join(BASE_DIR, 'static', 'js_src')

TARGET_FILES = [
    'pipe_network.js',
    'pipe_network_simple.js',
    'pump_comparison.js',
    'pump_curves.js',
    'pump_form.js',
    'pump_selection.js',
    'pump_selection_details.js'
]


def backup_sources():
    """Ensure js_src directory exists and contains the pristine source files."""
    os.makedirs(JS_SRC_DIR, exist_ok=True)
    for fname in TARGET_FILES:
        src_path = os.path.join(JS_DIR, fname)
        backup_path = os.path.join(JS_SRC_DIR, fname)
        # Only copy from js to js_src if js_src doesn't have it yet
        if os.path.exists(src_path) and not os.path.exists(backup_path):
            shutil.copy2(src_path, backup_path)
            print(f"[Backup] Saved pristine source: {fname} -> static/js_src/{fname}")


def restore_sources():
    """Restore pristine readable source files back into static/js/."""
    if not os.path.exists(JS_SRC_DIR):
        print("Error: static/js_src directory does not exist. Cannot restore.")
        return
    for fname in TARGET_FILES:
        backup_path = os.path.join(JS_SRC_DIR, fname)
        dest_path = os.path.join(JS_DIR, fname)
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, dest_path)
            print(f"[Restored] {fname} -> static/js/{fname}")
    print("\nAll readable source files restored successfully.")


def obfuscate_all():
    """Runs javascript-obfuscator on all target files."""
    backup_sources()

    print("\n" + "="*70)
    print(" STARTING JAVASCRIPT OBFUSCATION PIPELINE")
    print("="*70)

    # Obfuscator flags:
    # - compact: true (strip whitespace/comments)
    # - string-array: true (extract strings to encrypted array)
    # - string-array-encoding: rc4 (RC4 symmetric key encryption, NOT simple base64)
    # - split-strings: true (chops strings into multiple concatenated fragments)
    # - split-strings-chunk-length: 5
    # - string-array-threshold: 0.8
    # - rename-globals: false (keeps HTML onclick / event listener functions bound)
    # - simplify: true
    base_cmd = [
        'npx', '-y', 'javascript-obfuscator',
        '',  # placeholder for input file
        '--output', '',  # placeholder for output file
        '--compact', 'true',
        '--string-array', 'true',
        '--string-array-encoding', 'rc4',
        '--split-strings', 'true',
        '--split-strings-chunk-length', '5',
        '--string-array-threshold', '0.8',
        '--rename-globals', 'false',
        '--simplify', 'true',
        '--dead-code-injection', 'false'
    ]

    total_start = time.time()
    results = []

    for fname in TARGET_FILES:
        input_file = os.path.join(JS_SRC_DIR, fname)
        output_file = os.path.join(JS_DIR, fname)

        if not os.path.exists(input_file):
            print(f"[Skip] Source file missing: {input_file}")
            continue

        orig_size = os.path.getsize(input_file) / 1024.0

        cmd = list(base_cmd)
        cmd[3] = input_file
        cmd[5] = output_file

        print(f"Obfuscating {fname:30s} ({orig_size:6.1f} KB)...", end="", flush=True)
        t0 = time.time()

        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        elapsed = time.time() - t0

        if res.returncode == 0 and os.path.exists(output_file):
            new_size = os.path.getsize(output_file) / 1024.0
            print(f" DONE in {elapsed:4.1f}s -> {new_size:6.1f} KB")
            results.append((fname, orig_size, new_size, "SUCCESS"))
        else:
            print(f" FAILED (code {res.returncode})")
            if res.stderr:
                print(f"   Stderr: {res.stderr[:200]}")
            results.append((fname, orig_size, 0.0, "FAILED"))

    total_elapsed = time.time() - total_start
    print("\n" + "="*70)
    print(f" SUMMARY (Completed in {total_elapsed:.1f}s)")
    print("="*70)
    print(f"{'Filename':32s} | {'Source (KB)':12s} | {'Obfuscated (KB)':15s} | {'Status':8s}")
    print("-"*70)
    for r in results:
        print(f"{r[0]:32s} | {r[1]:10.1f} KB | {r[2]:13.1f} KB | {r[3]:8s}")
    print("="*70)
    print("\nObfuscated files deployed to static/js/.")
    print("Original readable sources safely preserved in static/js_src/.")


if __name__ == '__main__':
    if '--restore' in sys.argv:
        restore_sources()
    else:
        obfuscate_all()
