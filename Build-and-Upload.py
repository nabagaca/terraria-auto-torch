#!/usr/bin/env python3
"""
Build and Upload Script
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict
from urllib import error, request, parse
import zipfile

NEXUS_API_BASE = "https://api.nexusmods.com/v3"

# Project-specific configuration
NEXUS_MOD_ID = "162"
FILE_GROUP_ID = "7154614"
FILE_CATEGORY = "main"

mod_name = "auto-torch"  # Used for display and constructing paths; should match the project folder and csproj name


class ScriptError(Exception):
    pass


def load_env_file(env_path: Path) -> Dict[str, str]:
    if not env_path.exists():
        raise ScriptError(f".env file not found at {env_path}")

    loaded: Dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ[key] = value
            loaded[key] = value

    return loaded


def api_request(
    method: str,
    url: str,
    api_key: str | None = None,
    json_body: Dict[str, Any] | None = None,
    raw_body: bytes | None = None,
    extra_headers: Dict[str, str] | None = None,
) -> Any:
    headers: Dict[str, str] = {}
    if api_key:
        headers["apikey"] = api_key
    if extra_headers:
        headers.update(extra_headers)

    data: bytes | None = None
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw_body is not None:
        data = raw_body

    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
            response_bytes = resp.read()
            if "application/json" in content_type and response_bytes:
                return json.loads(response_bytes.decode("utf-8"))
            return response_bytes
    except error.HTTPError as exc:
        details = ""
        try:
            details = exc.read().decode("utf-8")
        except Exception:
            details = "<failed to read error body>"
        raise ScriptError(f"HTTP {exc.code} {exc.reason} from {url}\n{details}") from exc
    except error.URLError as exc:
        raise ScriptError(f"Network error while calling {url}: {exc.reason}") from exc


def run_build(project_file: Path, configuration: str) -> None:
    print(f"Building {mod_name} ({configuration})...")
    cmd = [
        "dotnet",
        "build",
        str(project_file),
        f"/p:Configuration={configuration}",
        "/p:CreateZipPackage=true",
    ]

    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        raise ScriptError("Build failed")

    print("Build completed successfully")


def get_mod_version(manifest_file: Path) -> str:
    if not manifest_file.exists():
        raise ScriptError(f"manifest.json not found at {manifest_file}")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not version or not isinstance(version, str):
        raise ScriptError("manifest.json is missing a valid string version")

    return version


def get_assembly_name(project_file: Path) -> str:
    # Try to read <AssemblyName> from the csproj; fall back to the project filename stem.
    try:
        import xml.etree.ElementTree as ET

        tree = ET.parse(str(project_file))
        root = tree.getroot()
        for elem in root.iter():
            tag = elem.tag
            if tag.endswith('AssemblyName'):
                if elem.text and elem.text.strip():
                    return elem.text.strip()
    except Exception:
        pass

    return project_file.stem


def find_zip(artifacts_dir: Path, assembly_name: str, version: str) -> Path:
    if not artifacts_dir.exists():
        raise ScriptError(f"Artifacts directory not found: {artifacts_dir}")
    # Use the same naming pattern as the csproj: {AssemblyName}-v{ModVersion}.zip
    expected_name = f"{assembly_name}-v{version}.zip"
    matches = [p for p in artifacts_dir.glob("*.zip") if p.name == expected_name]
    matches = sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise ScriptError(f"Built zip file not found in {artifacts_dir}")

    return matches[0]


def create_zip_package(project_root: Path, artifacts_dir: Path, assembly_name: str, version: str) -> Path:
    # Create a cross-platform zip containing a top-level '{mod_name}/' folder
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    zip_path = artifacts_dir / f"{assembly_name}-v{version}.zip"

    dll_path = project_root / "artifacts" / "bin" / f"{assembly_name}.dll"
    manifest_path = project_root / "src" / f"{mod_name}" / "manifest.json"

    if not dll_path.exists():
        raise ScriptError(f"Built assembly not found: {dll_path}")
    if not manifest_path.exists():
        raise ScriptError(f"manifest.json not found: {manifest_path}")

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(dll_path, arcname=f"{mod_name}/{dll_path.name}")
        zf.write(manifest_path, arcname=f"{mod_name}/{manifest_path.name}")

    print(f"Created zip package: {zip_path}")
    return zip_path


def upload_to_nexus(file_path: Path, version: str, api_key: str, description_override: str | None = None) -> None:
    if not file_path.exists():
        raise ScriptError(f"File not found: {file_path}")

    file_size = file_path.stat().st_size
    file_name = file_path.name

    print("Uploading to Nexus Mods...")
    print(f"File: {file_path}")
    print(f"Version: {version}")
    print(f"Mod ID: {NEXUS_MOD_ID}")
    print(f"File size: {file_size / (1024 * 1024):.3f} MB")

    # 1) Create upload session
    print("\n[1/5] Creating upload session...")
    upload_session = api_request(
        "POST",
        f"{NEXUS_API_BASE}/uploads",
        api_key=api_key,
        json_body={"size_bytes": file_size, "filename": file_name},
    )

    data = upload_session.get("data", {})
    upload_id = data.get("id")
    presigned_url = data.get("presigned_url")
    if not upload_id or not presigned_url:
        raise ScriptError("Create upload did not return data.id and data.presigned_url")

    print(f"Upload session created: {upload_id}")

    # 2) Upload bytes to presigned URL
    print("\n[2/5] Uploading file data...")
    with file_path.open("rb") as fh:
        file_bytes = fh.read()

    api_request(
        "PUT",
        presigned_url,
        raw_body=file_bytes,
        extra_headers={"Content-Type": "application/octet-stream"},
    )
    print("File uploaded successfully")

    # 3) Finalise upload
    print("\n[3/5] Finalizing upload...")
    api_request("POST", f"{NEXUS_API_BASE}/uploads/{upload_id}/finalise", api_key=api_key, json_body={})
    print("Upload finalized")

    # 4) Wait for availability
    print("\n[4/5] Waiting for upload to become available...")
    max_attempts = 20
    upload_state = ""
    for attempt in range(1, max_attempts + 1):
        upload_info = api_request("GET", f"{NEXUS_API_BASE}/uploads/{upload_id}", api_key=api_key)
        upload_state = upload_info.get("data", {}).get("state", "")
        print(f"Upload state (attempt {attempt}/{max_attempts}): {upload_state}")
        if upload_state == "available":
            break
        time.sleep(2)

    if upload_state != "available":
        raise ScriptError(f"Upload did not become available in time. Last state: {upload_state}")

    # 5) Create version in update group
    print("\n[5/5] Creating new update-group version...")
    mod_file_body = {
        "upload_id": upload_id,
        "name": f"{mod_name} v{version}",
        "version": version,
        "description": description_override if description_override is not None else f"Release version {version}",
        "file_category": FILE_CATEGORY,
    }

    mod_file_resp = api_request(
        "POST",
        f"{NEXUS_API_BASE}/mod-file-update-groups/{FILE_GROUP_ID}/versions",
        api_key=api_key,
        json_body=mod_file_body,
    )

    new_file_id = mod_file_resp.get("data", {}).get("id")
    if not new_file_id:
        raise ScriptError("Update group version response did not include data.id")

    print(f"New mod file version created and marked latest: {new_file_id}")
    print("\nUpload complete!")


def create_github_release_and_upload(
    file_path: Path,
    version: str,
    github_token: str,
    github_repo: str,
    description_override: str | None = None,
) -> None:
    if not file_path.exists():
        raise ScriptError(f"File not found: {file_path}")

    tag_name = f"v{version}"
    release_name = f"{mod_name} v{version}"
    body = description_override if description_override is not None else f"Release version {version}"

    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github+json"}

    print("Creating GitHub release...")
    create_url = f"https://api.github.com/repos/{github_repo}/releases"
    release_payload = {
        "tag_name": tag_name,
        "name": release_name,
        "body": body,
        "draft": False,
        "prerelease": False,
    }

    try:
        release_resp = api_request("POST", create_url, json_body=release_payload, extra_headers=headers)
    except ScriptError as exc:
        msg = str(exc)
        if "HTTP 422" in msg:
            print("Release tag already exists; locating existing release by tag...")
            # Find existing release by tag
            tag_url = f"https://api.github.com/repos/{github_repo}/releases/tags/{tag_name}"
            release_resp = api_request("GET", tag_url, extra_headers=headers)
        else:
            raise

    # Normalize response shape: Nexus uses {"data": {...}}, GitHub returns the object directly
    if isinstance(release_resp, dict):
        if "data" in release_resp and isinstance(release_resp.get("data"), dict):
            release_data = release_resp["data"]
        else:
            release_data = release_resp
    else:
        release_data = release_resp

    release_id = release_data.get("id")
    upload_url_template = release_data.get("upload_url")
    if not release_id or not upload_url_template:
        raise ScriptError("Failed to obtain release id/upload_url from GitHub response")

    # Upload asset
    upload_base = upload_url_template.split("{")[0]
    file_name = file_path.name
    upload_url = f"{upload_base}?name={parse.quote(file_name)}"

    print(f"Uploading {file_name} to GitHub release {release_name}...")
    with file_path.open("rb") as fh:
        file_bytes = fh.read()

    asset_headers = {"Authorization": f"token {github_token}", "Content-Type": "application/zip", "Accept": "application/vnd.github+json"}
    asset_resp = api_request("POST", upload_url, raw_body=file_bytes, extra_headers=asset_headers)
    print("GitHub upload response:", asset_resp if isinstance(asset_resp, dict) else "(raw bytes)")
    print("GitHub release asset upload complete")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"Build and upload {mod_name} to Nexus Mods")
    parser.add_argument("--build-configuration", default="Release", help="dotnet build configuration")
    parser.add_argument("--skip-build", action="store_true", help="Skip dotnet build")
    parser.add_argument("--skip-upload", action="store_true", help="Skip Nexus upload")
    parser.add_argument("--skip-github", action="store_true", help="Skip creating GitHub release and upload")
    parser.add_argument("--description", help="Override uploaded file description")
    return parser.parse_args()


def main() -> int:
    print(f"{mod_name} Build & Upload Script (Python)")
    print("========================================\n")

    args = parse_args()

    project_root = Path(__file__).resolve().parent
    env_file = project_root / ".env"
    manifest_file = project_root / "src" / f"{mod_name}" / "manifest.json"
    csproj_file = project_root / "src" / f"{mod_name}" / f"{mod_name}.csproj"
    artifacts_dir = project_root / "artifacts"

    try:
        load_env_file(env_file)
        api_key = os.getenv("nexus_api_key", "")
        if not api_key:
            raise ScriptError("nexus_api_key not found in .env file")

        if not FILE_GROUP_ID:
            raise ScriptError(
                "FILE_GROUP_ID is not configured. Set FILE_GROUP_ID near the top of this script."
            )

        version = get_mod_version(manifest_file)
        print(f"Mod Version: {version}\n")

        if not args.skip_build:
            run_build(csproj_file, args.build_configuration)

        assembly_name = get_assembly_name(csproj_file)
        try:
            zip_file = find_zip(artifacts_dir, assembly_name, version)
        except ScriptError:
            if not args.skip_build:
                # build just ran; attempt to create the zip from build outputs
                print("Built zip not found — creating zip package cross-platform...")
                create_zip_package(project_root, artifacts_dir, assembly_name, version)
                zip_file = find_zip(artifacts_dir, assembly_name, version)
            else:
                # If build was skipped, still attempt to create zip (user may have built earlier)
                print("Built zip not found — creating zip package from existing build outputs...")
                create_zip_package(project_root, artifacts_dir, assembly_name, version)
                zip_file = find_zip(artifacts_dir, assembly_name, version)
        print(f"Found built package: {zip_file.name}\n")

        if not args.skip_upload:
            upload_to_nexus(zip_file, version, api_key, args.description)

        if not args.skip_github:
            github_token = os.getenv("github_token", "")
            github_repo = os.getenv("github_repo", "")
            if not github_token:
                raise ScriptError("github_token not found in .env file")
            if not github_repo:
                raise ScriptError("github_repo not found in .env file (format: owner/repo)")

            create_github_release_and_upload(zip_file, version, github_token, github_repo, args.description)

        return 0
    except ScriptError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())