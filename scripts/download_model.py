"""Download a pinned model and verify every file against Hub metadata."""
import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_config import MODEL_DIR, MODEL_ID, MODEL_REVISION

def main():
    # The live runtime is offline; first installation explicitly downloads.
    os.environ.pop("HF_HUB_OFFLINE", None)
    from huggingface_hub import HfApi, snapshot_download
    info = HfApi().model_info(MODEL_ID, revision=MODEL_REVISION, files_metadata=True)
    if info.sha != MODEL_REVISION:
        raise RuntimeError("模型版本与发布版本不符")
    print(f"下载 Laya 固定版本 {MODEL_REVISION[:12]}，已有缓存可复用…", flush=True)
    snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_dir=str(MODEL_DIR))
    checked = []
    for item in info.siblings:
        path = MODEL_DIR / item.rfilename
        if not path.is_file():
            raise RuntimeError("模型文件缺失: " + item.rfilename)
        sha256 = hashlib.sha256()
        git_hash = hashlib.sha1(f"blob {path.stat().st_size}\0".encode())
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                sha256.update(chunk)
                git_hash.update(chunk)
        expected = item.lfs.sha256 if item.lfs else item.blob_id
        observed = sha256.hexdigest() if item.lfs else git_hash.hexdigest()
        if expected != observed:
            raise RuntimeError("模型文件校验失败: " + item.rfilename)
        checked.append({"file": item.rfilename, "sha256": sha256.hexdigest()})
    (MODEL_DIR / "verified-revision.json").write_text(json.dumps(
        {"repository": MODEL_ID, "revision": MODEL_REVISION, "files": checked}, indent=2))
    print(f"模型已校验：{len(checked)} 个文件。")

if __name__ == "__main__":
    main()
