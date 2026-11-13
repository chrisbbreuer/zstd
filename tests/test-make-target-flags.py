#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
# This source code is licensed under both the BSD-style license (found in the
# LICENSE file in the root directory of this source tree) and the GPLv2 (found
# in the COPYING file in the root directory of this source tree).
# You may select, at your option, one of the above-listed licenses.

"""Exercise actual native and target-specific 32-bit compiler capability checks."""

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--make", default="make")
    args = parser.parse_args()
    library_makefile = Path(__file__).resolve().parent.parent / "lib/libzstd.mk"
    with tempfile.TemporaryDirectory(prefix="zstd-make-target-flags-") as directory:
        root = Path(directory)
        (root / "probe.c").write_text("int main(void) { return 0; }\n")
        (root / "Makefile").write_text(
            ".PHONY: native compat32\n"
            "default: native compat32\n"
            "include {}\n".format(library_makefile.as_posix().replace(" ", "\\ "))
            + "compat32: override CFLAGS += -m32\n"
            "native compat32:\n"
            "\t$(file >$@.base,$(CC) $(CPPFLAGS) $(CFLAGS) $(ASFLAGS) $(LDFLAGS))\n"
            "\t$(file >$@.flags,$(CC) $(FLAGS))\n"
            "\t$(CC) $(FLAGS) probe.c -o $@\n"
        )
        environment = dict(os.environ)
        subprocess.run(
            shlex.split(args.make) + ["-C", directory, "native", "compat32", "V=1"],
            env=environment,
            check=True,
            close_fds=False,
        )
        for target in ("native", "compat32"):
            base = shlex.split((root / (target + ".base")).read_text())
            flags = shlex.split((root / (target + ".flags")).read_text())
            probe = subprocess.run(
                base + ["-z", "cet-report=error", "-Werror", "probe.c", "-o", "capability"],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            expected = probe.returncode == 0
            actual = "cet-report=error" in flags
            if expected != actual:
                raise AssertionError("{}: CET flags do not match its actual compiler target".format(target))
            subprocess.run([str(root / target)], check=True)
            print("{}: real link, runtime and target-specific CET capability passed".format(target))


if __name__ == "__main__":
    main()
