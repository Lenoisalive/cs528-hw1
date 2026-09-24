"""Portable experiment metadata; missing system tools yield null fields."""

import os
from pathlib import Path
import platform
import subprocess
import sys


def command(*args):
    try:
        return subprocess.check_output(args, cwd=Path(__file__).resolve().parent.parent,
                                       stderr=subprocess.DEVNULL, text=True, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return None


def environment_info(label):
    cpu = platform.processor() or None
    memory = None
    if sys.platform == 'darwin':
        cpu = command('sysctl', '-n', 'machdep.cpu.brand_string') or cpu
        memory = command('sysctl', '-n', 'hw.memsize')
    elif sys.platform.startswith('linux'):
        try:
            for line in Path('/proc/cpuinfo').read_text().splitlines():
                if line.startswith('model name'):
                    cpu = line.split(':', 1)[1].strip()
                    break
            for line in Path('/proc/meminfo').read_text().splitlines():
                if line.startswith('MemTotal:'):
                    memory = int(line.split()[1]) * 1024
                    break
        except OSError:
            pass
    status = command('git', 'status', '--porcelain', '--untracked-files=normal')
    return {
        'label': label, 'os': platform.platform(), 'machine': platform.machine(),
        'python_version': platform.python_version(), 'python_implementation': platform.python_implementation(),
        'cpu_model': cpu, 'logical_cpu_count': os.cpu_count(),
        'memory_bytes': int(memory) if memory is not None else None,
        'git_commit': command('git', 'rev-parse', 'HEAD'),
        'git_dirty': bool(status) if status is not None else None,
    }
