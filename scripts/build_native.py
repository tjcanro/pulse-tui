#!/usr/bin/env python3
"""Build the optional plain-C rasterizer for the source checkout."""
import argparse
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / 'native/wireframe.c'
    library = root / 'src/pulse_tui/_native/wireframe_native.so'
    library.parent.mkdir(parents=True, exist_ok=True)
    if library.exists() and library.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        try:
            existing = ctypes.CDLL(str(library))
            if existing.pulse_renderer_abi() == 1:
                return 0
        except (OSError, AttributeError):
            pass  # A library built for a different architecture must be rebuilt.
    compiler = shutil.which('clang') or shutil.which('cc')
    if not compiler:
        if not args.quiet:
            print('No C compiler found; the Python renderer remains available.')
        return 1
    flags = ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']
    try:
        with tempfile.TemporaryDirectory(prefix='pulse-build-', dir=library.parent) as temp:
            target = Path(temp) / 'wireframe_native.so'
            result = subprocess.run([compiler, '-O3', '-std=c99', *flags, str(source), '-o', str(target), '-lm'],
                                    capture_output=True, text=True)
            if result.returncode:
                if not args.quiet:
                    print(result.stderr, file=sys.stderr)
                return 1
            os.replace(target, library)
        if not args.quiet:
            print('Built native wireframe rasterizer:', library)
        return 0
    except OSError as e:
        if not args.quiet:
            print(f'Native build unavailable: {e}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
