# (c) Copyright 2025 Mikołaj Kuranowski
# SPDX-License-Identifier: MIT

import concurrent.futures
import shutil
import subprocess
import sys
import threading
import traceback
from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory

MESON_CROSS_FILES_DIR = Path(__file__).with_name("cross")  # NOTE: Absolute dir is necessary
WHEEL_PYTHON_TAG = "py3"
WHEEL_ABI_TAG = "none"


# NOTE: The platform tag must be kept in sync with what Rust claims it supports at
#       https://doc.rust-lang.org/nightly/rustc/platform-support.html.
#       The zig --target argument in cross/*.ini files also hard codes the supported ABI versions,
#       but that is not used to compile anything, it's just so meson doesn't complain.
# NOTE: "manylinux2014" is a legacy alias for "manylinux_2_17".

CONFIGURATIONS = {
    "aarch64-linux-gnu": (
        MESON_CROSS_FILES_DIR / "aarch64-linux-gnu.ini",
        "manylinux2014_aarch64.manylinux_2_17_aarch64",
    ),
    "aarch64-macos": (
        MESON_CROSS_FILES_DIR / "aarch64-macos.ini",
        "macosx_11_0_arm64",
    ),
    "aarch64-windows": (
        MESON_CROSS_FILES_DIR / "aarch64-windows.ini",
        "win_arm64",
    ),
    "x86_64-linux-gnu": (
        MESON_CROSS_FILES_DIR / "x86_64-linux-gnu.ini",
        "manylinux2014_x86_64.manylinux_2_17_x86_64",
    ),
    "x86_64-macos": (
        MESON_CROSS_FILES_DIR / "x86_64-macos.ini",
        "macosx_11_0_x86_64",
    ),
    "x86_64-windows": (
        MESON_CROSS_FILES_DIR / "x86_64-windows.ini",
        "win_amd64",
    ),
}

STDERR_LOCK = threading.Lock()


def eprint(line: str, exc_info: bool = False) -> None:
    with STDERR_LOCK:
        print(line, file=sys.stderr)
        if exc_info:
            traceback.print_exc(file=sys.stderr)


def compile(target_dir: Path, cross_file: Path, verbose: bool = False) -> Path:
    pipe = None if verbose else subprocess.DEVNULL
    subprocess.run(
        [
            "python",
            "-m",
            "build",
            "--wheel",
            "--outdir",
            str(target_dir),
            "-C",
            f"setup-args=--cross-file={cross_file}",
            # "-D buildtype=release" is automatically added by meson-python
        ],
        stdin=pipe,
        stdout=pipe,
        stderr=pipe,
        check=True,
    )

    wheels = list(target_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise ValueError(
            f'{len(wheels)} wheels were created by "python -m build", expected exactly 1',
        )
    return wheels[0]


def fixup_wheel(old_name: Path, platform_tag: str, verbose: bool = False) -> Path:
    default_pipe = None if verbose else subprocess.DEVNULL
    result = subprocess.run(
        [
            "python",
            "-m",
            "wheel",
            "tags",
            "--python-tag",
            WHEEL_PYTHON_TAG,
            "--abi-tag",
            WHEEL_ABI_TAG,
            "--platform-tag",
            platform_tag,
            str(old_name),
        ],
        stdin=default_pipe,
        stdout=subprocess.PIPE,
        stderr=default_pipe,
        check=True,
        text=True,
    )
    output_lines = result.stdout.splitlines()
    output_filename = output_lines[-1]
    if not output_filename.endswith(".whl"):
        raise ValueError(f"'python -m wheel tags' has not printed the fixed wheel path")
    return old_name.with_name(output_filename)


def build(output_dir: Path, cross_file: Path, platform_tag: str, verbose: bool = False) -> bool:
    with TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        log_prefix = cross_file.stem
        try:
            eprint(f"{log_prefix}: starting compilation")
            broken_wheel_path = compile(temp_dir, cross_file, verbose=verbose)
            eprint(f"{log_prefix}: fixing up the wheel")
            fixed_wheel_path = fixup_wheel(broken_wheel_path, platform_tag, verbose=verbose)
            shutil.copy(fixed_wheel_path, output_dir / fixed_wheel_path.name)
            eprint(f"{log_prefix}: done")
            return True
        except Exception:
            eprint(f"{log_prefix}: failed", exc_info=True)
            return False


def main() -> None:
    arg_parser = ArgumentParser()
    arg_parser.add_argument("-v", "--verbose", action="store_true", help="show build output")
    arg_parser.add_argument(
        "configurations",
        nargs="*",
        choices=CONFIGURATIONS.keys(),
        help="which wheels should be built? (defaults to all)",
    )
    args = arg_parser.parse_args()

    out_dir = Path("dist")
    out_dir.mkdir(exist_ok=True)

    with concurrent.futures.ThreadPoolExecutor() as pool:
        futures = [
            pool.submit(build, out_dir, *CONFIGURATIONS[config_name], args.verbose)
            for config_name in (args.configurations or CONFIGURATIONS.keys())
        ]

        exit_code = 0
        for future in futures:
            if not future.result():
                exit_code = 1

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
