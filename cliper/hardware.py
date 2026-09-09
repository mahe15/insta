"""Load project-local NVIDIA libraries without changing the machine's system PATH."""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import sysconfig
from pathlib import Path

_DLL_HANDLES = []
_REGISTERED = set()


def cuda_library_dirs() -> list[Path]:
    root = Path(sysconfig.get_path("purelib")) / "nvidia"
    return sorted(p.resolve() for pattern in ("*/bin", "*/lib") for p in root.glob(pattern) if p.is_dir())


def configure_cuda_paths() -> list[Path]:
    directories = cuda_library_dirs()
    variable = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
    previous = os.environ.get(variable, "").split(os.pathsep)
    additions = [str(p) for p in directories if str(p) not in previous]
    if additions:
        os.environ[variable] = os.pathsep.join(additions + previous)
    if os.name == "nt":
        for directory in directories:
            if directory not in _REGISTERED:
                _DLL_HANDLES.append(os.add_dll_directory(str(directory)))
                _REGISTERED.add(directory)
    return directories


def check_cuda(device_index: int, compute_type: str) -> dict:
    configure_cuda_paths()
    libraries = (["cublasLt64_12.dll", "cublas64_12.dll", "cudnn64_9.dll"] if os.name == "nt"
                 else ["libcublasLt.so.12", "libcublas.so.12", "libcudnn.so.9"])
    for library in libraries:
        try:
            _DLL_HANDLES.append(ctypes.CDLL(library))
        except OSError as exc:
            raise RuntimeError(f"Cannot load {library}. Install this project's GPU dependencies with "
                               "pip install -e '.[gpu]' and restart.") from exc
    import ctranslate2
    count = ctranslate2.get_cuda_device_count()
    if device_index < 0 or device_index >= count:
        raise ValueError(f"CUDA device {device_index} is unavailable; detected {count} devices")
    supported = ctranslate2.get_supported_compute_types("cuda", device_index=device_index)
    if compute_type not in supported:
        raise ValueError(f"CUDA does not support {compute_type}; supported types: {', '.join(sorted(supported))}")
    return {"cuda_devices": count, "device_index": device_index, "compute_type": compute_type,
            "ctranslate2": ctranslate2.__version__, "libraries": "loaded"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--device-index", type=int, default=0)
    parser.add_argument("--compute", default="int8_float16")
    args = parser.parse_args()
    print(json.dumps(check_cuda(args.device_index, args.compute)))


if __name__ == "__main__":
    main()
