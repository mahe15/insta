"""Install the small, hash-pinned OpenCV YuNet model compatible with OpenCV 4.x."""
import hashlib
from pathlib import Path

SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"
BASE = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/"


def install(target: Path):
    import httpx
    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == SHA256:
        return target
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        response = client.get(BASE + "face_detection_yunet_2023mar.onnx")
        response.raise_for_status()
        data = response.content
        if len(data) != 232589 or hashlib.sha256(data).hexdigest() != SHA256:
            raise ValueError("YuNet model did not match the pinned OpenCV artifact")
        license_response = client.get("https://raw.githubusercontent.com/opencv/opencv_zoo/main/models/face_detection_yunet/LICENSE")
        license_response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".partial")
    temporary.write_bytes(data)
    temporary.replace(target)
    target.with_suffix(".LICENSE.txt").write_text(license_response.text, encoding="utf-8")
    return target


if __name__ == "__main__":
    from .config import Config
    print(install(Config.load().face_model_path))
