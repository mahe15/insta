import os
import sys
from types import SimpleNamespace

import pytest

from cliper.hardware import check_cuda, configure_cuda_paths
from cliper.media import video_encoder_args


def test_gpu_encoder_uses_nvenc_and_selected_device(cfg):
    cfg.video_encoder, cfg.gpu_device_index = "h264_nvenc", 0
    args = video_encoder_args(cfg, 4500)
    assert args[args.index("-c:v") + 1] == "h264_nvenc"
    assert args[args.index("-gpu") + 1] == "0"
    assert args[args.index("-b:v") + 1] == "4500k"
    assert "-crf" not in args and "libx264" not in args
    cfg.video_encoder = "libx264"
    assert "-crf" in video_encoder_args(cfg, 4500)
    cfg.video_encoder = "unknown"
    with pytest.raises(ValueError, match="Unknown VIDEO_ENCODER"):
        video_encoder_args(cfg, 4500)


def test_runtime_path_registration_is_idempotent(monkeypatch, tmp_path):
    folder = tmp_path / "cuda-bin"
    folder.mkdir()
    monkeypatch.setattr("cliper.hardware.cuda_library_dirs", lambda: [folder])
    monkeypatch.setattr("cliper.hardware._REGISTERED", set())
    monkeypatch.setattr("cliper.hardware._DLL_HANDLES", [])
    if os.name == "nt":
        monkeypatch.setattr(os, "add_dll_directory", lambda path: object())
    variable = "PATH" if os.name == "nt" else "LD_LIBRARY_PATH"
    monkeypatch.setenv(variable, "existing-runtime")
    configure_cuda_paths()
    configure_cuda_paths()
    assert os.environ[variable].split(os.pathsep).count(str(folder)) == 1
    assert "existing-runtime" in os.environ[variable]


def test_gpu_validation_and_missing_libraries(monkeypatch):
    monkeypatch.setattr("cliper.hardware.configure_cuda_paths", lambda: [])
    monkeypatch.setattr("cliper.hardware._DLL_HANDLES", [])
    monkeypatch.setattr("cliper.hardware.ctypes.CDLL", lambda path: object())
    runtime = SimpleNamespace(__version__="test", get_cuda_device_count=lambda: 1,
                              get_supported_compute_types=lambda device, device_index: {"int8_float16", "float16"})
    monkeypatch.setitem(sys.modules, "ctranslate2", runtime)
    assert check_cuda(0, "int8_float16")["libraries"] == "loaded"
    with pytest.raises(ValueError, match="unavailable"):
        check_cuda(1, "int8_float16")
    with pytest.raises(ValueError, match="does not support"):
        check_cuda(0, "unsupported")

    def fail(path):
        raise OSError("Missing DLL")
    monkeypatch.setattr("cliper.hardware.ctypes.CDLL", fail)
    with pytest.raises(RuntimeError, match="GPU dependencies"):
        check_cuda(0, "float16")
