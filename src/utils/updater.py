"""Download and stage updates from the project's GitHub Releases."""

import base64
import hashlib
import json
import os
import platform
import re
import ssl
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

import certifi

from version import APP_VERSION, GITHUB_REPOSITORY


MAC_APP = "AI语音提词器.app"
WINDOWS_EXE = "汪同学的AI语音提词器.exe"
WINDOWS_FOLDER = Path(WINDOWS_EXE).stem
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases"
RELEASE_DOWNLOAD = f"https://github.com/{GITHUB_REPOSITORY}/releases/download"
MAX_ARCHIVE_BYTES = 512 * 1024**2
MAX_EXTRACTED_BYTES = 2 * 1024**3


def _request(url):
    request = urllib.request.Request(url, headers={"User-Agent": "WangPrompter-Updater"})
    return urllib.request.urlopen(request, timeout=20,
                                  context=ssl.create_default_context(cafile=certifi.where()))


def _version(value):
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", value)
    return tuple(map(int, match.groups())) if match else ()


def _asset_name(version):
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        target = {"arm64": "macos-arm64", "x86_64": "macos-x64"}.get(machine)
    elif sys.platform == "win32":
        target = "windows-x64" if machine in {"amd64", "x86_64"} else None
    else:
        target = None
    return f"ai-voice-teleprompter-v{version}-{target}.zip" if target else None


def check_latest_release():
    try:
        with _request(f"{RELEASES_API}/latest") as response:
            release = json.loads(response.read(2 * 1024**2))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise RuntimeError("暂时无法访问此仓库的公开正式版本。") from error
        raise
    tag = release.get("tag_name", "")
    version = _version(tag)
    if not version:
        raise ValueError("GitHub 版本号格式无效。")
    if release.get("draft") or release.get("prerelease") or version <= _version(APP_VERSION):
        return None
    version_text = ".".join(map(str, version))
    name = _asset_name(version_text)
    asset = next((asset for asset in release.get("assets", []) if asset["name"] == name), None)
    url = f"{RELEASE_DOWNLOAD}/{tag}/{name}"
    if (not asset or asset.get("browser_download_url") != url
            or asset.get("state") != "uploaded"
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or "")):
        raise ValueError(f"发现 v{version_text}，但当前系统的更新包或校验值尚未发布。")
    return version_text, release.get("body") or "", asset


def _install_location():
    if not getattr(sys, "frozen", False):
        raise RuntimeError("请从已打包的应用执行安装。")
    executable = Path(sys.executable).resolve()
    if sys.platform == "darwin" and executable.parents[2].suffix == ".app":
        return executable.parents[2]
    if sys.platform == "win32" and executable.name == WINDOWS_EXE:
        return executable.parent
    raise RuntimeError("无法识别当前应用安装位置。")


def _download(asset, archive):
    size = asset["size"]
    if not 0 < size <= MAX_ARCHIVE_BYTES:
        raise ValueError("更新包大小无效。")
    digest = hashlib.sha256()
    received = 0
    deadline = time.monotonic() + 600
    with _request(asset["browser_download_url"]) as response, archive.open("wb") as output:
        while chunk := response.read(1024**2):
            if time.monotonic() > deadline:
                raise TimeoutError("下载更新超时。")
            received += len(chunk)
            if received > size:
                raise ValueError("下载大小超过发布记录。")
            output.write(chunk)
            digest.update(chunk)
    if received != size or f"sha256:{digest.hexdigest()}" != asset["digest"]:
        raise ValueError("更新包校验失败，请重新检查更新。")


def _extract(archive, destination, root_name):
    with zipfile.ZipFile(archive, metadata_encoding="utf-8") as package:
        entries = package.infolist()
        if sum(entry.file_size for entry in entries) > MAX_EXTRACTED_BYTES:
            raise ValueError("更新包解压后过大。")
        paths = set()
        links = set()
        for entry in entries:
            path = PurePosixPath(entry.filename)
            mode = stat.S_IFMT(entry.external_attr >> 16)
            if (not path.parts or path.parts[0] != root_name or ".." in path.parts
                    or "\\" in entry.filename or ":" in entry.filename
                    or path.as_posix().casefold() in paths):
                raise ValueError("更新包包含无效路径。")
            paths.add(path.as_posix().casefold())
            if mode == stat.S_IFLNK and sys.platform == "darwin" and entry.file_size <= 4096:
                link = package.read(entry).decode()
                target = Path(os.path.normpath(str(path.parent / link)))
                if not target.parts or target.parts[0] != root_name:
                    raise ValueError("更新包包含越界链接。")
                links.add(path.as_posix().casefold())
            elif mode not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise ValueError("更新包包含不支持的文件类型。")
        for entry in entries:
            if any(parent.as_posix().casefold() in links
                   for parent in PurePosixPath(entry.filename).parents):
                raise ValueError("更新包试图向链接内写入文件。")
        if sys.platform != "darwin":
            package.extractall(destination)
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/ditto", "-x", "-k", str(archive), str(destination)], check=True)


def stage_update(asset):
    target = _install_location()
    stage_parent = target.parent if sys.platform == "darwin" else target
    stage = tempfile.TemporaryDirectory(prefix=".prompter-update-", dir=stage_parent, delete=False)
    try:
        folder = Path(stage.name)
        archive = folder / "update.zip"
        _download(asset, archive)
        root_name = MAC_APP if sys.platform == "darwin" else WINDOWS_FOLDER
        _extract(archive, folder, root_name)
        archive.unlink()
        replacement = folder / root_name
        if sys.platform == "darwin":
            subprocess.run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(replacement)],
                           capture_output=True, check=True)
        elif not (replacement / WINDOWS_EXE).is_file() or not (replacement / "_internal").is_dir():
            raise ValueError("更新包缺少程序或运行库。")
        return stage, target, replacement
    except Exception:
        stage.cleanup()
        raise


MAC_INSTALL = """
while kill -0 "$1" 2>/dev/null; do sleep 1; done
target=$2
replacement=$3
backup="$4/previous.app"
if mv "$target" "$backup"; then
    if mv "$replacement" "$target"; then
        if /usr/bin/open -n "$target"; then
            rm -rf -- "$4"
            exit 0
        fi
        mv "$target" "$replacement"
    fi
    mv "$backup" "$target"
fi
/usr/bin/open -n "$target"
exit 1
"""


WINDOWS_INSTALL = r"""
$ErrorActionPreference = 'Stop'
$target = $env:PROMPTER_TARGET
$stage = $env:PROMPTER_STAGE
$replacement = $env:PROMPTER_REPLACEMENT
$exe = $env:PROMPTER_EXE
$files = @('_internal', $exe)
$previous = Join-Path $stage 'previous'
$saved = @()
$installed = @()
try {
    Wait-Process -Id ([int]$env:PROMPTER_PID) -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $previous | Out-Null
    foreach ($name in $files) {
        Move-Item -LiteralPath (Join-Path $target $name) -Destination $previous
        $saved += $name
    }
    foreach ($name in $files) {
        Move-Item -LiteralPath (Join-Path $replacement $name) -Destination $target
        $installed += $name
    }
    Start-Process -FilePath (Join-Path $target $exe) -WorkingDirectory $target
} catch {
    foreach ($name in $installed) {
        Move-Item -LiteralPath (Join-Path $target $name) -Destination $replacement
    }
    foreach ($name in $saved) {
        Move-Item -LiteralPath (Join-Path $previous $name) -Destination $target
    }
    Start-Process -FilePath (Join-Path $target $exe) -WorkingDirectory $target
    exit 1
}
Set-Location -LiteralPath $target
Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
"""


def launch_installer(staged):
    stage, target, replacement = staged
    if sys.platform == "darwin":
        subprocess.Popen(["/bin/sh", "-c", MAC_INSTALL, "prompter-update",
                          str(os.getpid()), str(target), str(replacement), stage.name],
                         start_new_session=True, cwd=stage.name)
    else:
        env = dict(os.environ, PROMPTER_TARGET=str(target), PROMPTER_STAGE=stage.name,
                   PROMPTER_REPLACEMENT=str(replacement), PROMPTER_EXE=WINDOWS_EXE,
                   PROMPTER_PID=str(os.getpid()), PYINSTALLER_RESET_ENVIRONMENT="1")
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        command = base64.b64encode(WINDOWS_INSTALL.encode("utf-16-le")).decode("ascii")
        subprocess.Popen([str(powershell), "-NoProfile", "-NonInteractive", "-EncodedCommand", command],
                         env=env, creationflags=subprocess.CREATE_NO_WINDOW, cwd=target)
