"""Exercise the actual Arduino eye driver without hardware or serial access."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("dog_yaw_enabled", [0, 1])
def test_all_puppet_gazes_with_reduced_diagonal_ranges(tmp_path, dog_yaw_enabled):
    compiler = shutil.which('clang++') or shutil.which('g++')
    if not compiler:
        pytest.skip('C++ compiler unavailable')
    root = Path(__file__).resolve().parents[1]
    driver = root / 'hardware/current-20261021/PuppetEyes/src'
    harness = root / 'tests/hardware'
    binary = tmp_path / 'check_ranges'
    subprocess.run([compiler, '-std=c++11', f'-DECR_DOG_YAW_ENABLED={dog_yaw_enabled}', '-I', str(harness / 'stubs'),
                    '-I', str(driver), str(harness / 'check_ranges.cpp'),
                    str(driver / 'PuppetEyes.cpp'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
