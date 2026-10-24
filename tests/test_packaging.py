import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import zipfile


SCRIPT = Path(__file__).resolve().parents[1] / "Build-and-Upload.py"


class PackagingTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("packaging_script", SCRIPT)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        temporary = tempfile.TemporaryDirectory(prefix="auto torch packaging ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.mod.__file__ = str(self.root / SCRIPT.name)
        self.project = self.root / "src" / "auto-torch"
        self.project.mkdir(parents=True)
        self.manifest = {"id": "auto-torch", "version": "0.4.1"}
        (self.project / "manifest.json").write_text(json.dumps(self.manifest))
        (self.project / "auto-torch.csproj").write_text(
            "<Project><PropertyGroup><AssemblyName>auto-torch</AssemblyName>"
            "</PropertyGroup></Project>"
        )
        self.artifacts = self.root / "artifacts"
        self.dll = self.artifacts / "bin" / "auto-torch.dll"
        self.dll.parent.mkdir(parents=True)
        self.dll.write_bytes(b"original DLL")
        self.archive = self.artifacts / "auto-torch-v0.4.1.zip"
        network = mock.patch.object(
            self.mod.request, "urlopen", side_effect=AssertionError("Unexpected network request")
        )
        network.start()
        self.addCleanup(network.stop)

    def invoke(self, *flags):
        with mock.patch.object(sys, "argv", [str(SCRIPT), *flags]):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return self.mod.main()

    def package(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.mod.create_zip_package(self.root, self.artifacts, "auto-torch", "0.4.1")

    def check_archive(self, dll_bytes):
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(archive.testzip(), None)
            self.assertEqual(set(archive.namelist()), {
                "auto-torch/auto-torch.dll", "auto-torch/manifest.json"
            })
            self.assertEqual(archive.read("auto-torch/auto-torch.dll"), dll_bytes)
            self.assertEqual(json.loads(archive.read("auto-torch/manifest.json")), self.manifest)

    def test_build_replaces_stale_zip_without_loading_credentials(self):
        self.package()
        (self.root / ".env").write_text("credentials must not be loaded")
        def build(project, configuration):
            self.assertEqual(project, self.project / "auto-torch.csproj")
            self.assertEqual(configuration, "Release")
            self.dll.write_bytes(b"freshly built DLL")

        with mock.patch.object(self.mod, "run_build", side_effect=build):
            with mock.patch.object(self.mod, "load_env_file") as credentials:
                self.assertEqual(self.invoke("--skip-upload", "--skip-github"), 0)
                credentials.assert_not_called()
        self.check_archive(b"freshly built DLL")

    def test_skip_build_preserves_existing_archive(self):
        self.package()
        self.dll.write_bytes(b"different local DLL")
        with mock.patch.object(self.mod, "run_build") as build:
            self.assertEqual(self.invoke("--skip-build", "--skip-upload", "--skip-github"), 0)
            build.assert_not_called()
        self.check_archive(b"original DLL")

    def test_skip_build_packages_outputs_when_archive_is_missing(self):
        self.assertEqual(self.invoke("--skip-build", "--skip-upload", "--skip-github"), 0)
        self.check_archive(b"original DLL")

    def test_default_publish_flow_still_calls_both_publishers(self):
        self.package()
        with mock.patch.dict(os.environ, {
            "nexus_api_key": "test-nexus", "github_token": "test-github", "github_repo": "test/repo"
        }, clear=True):
            with mock.patch.object(self.mod, "upload_to_nexus") as nexus:
                with mock.patch.object(self.mod, "create_github_release_and_upload") as github:
                    self.assertEqual(self.invoke("--skip-build", "--description", "Test release"), 0)
                    nexus.assert_called_once_with(self.archive, "0.4.1", "test-nexus", "Test release")
                    github.assert_called_once_with(
                        self.archive, "0.4.1", "test-github", "test/repo", "Test release"
                    )

    def test_build_uses_project_path_as_one_argument(self):
        project = self.project / "auto-torch.csproj"
        with mock.patch.object(self.mod.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            with contextlib.redirect_stdout(io.StringIO()):
                self.mod.run_build(project, "Release")
            self.assertEqual(run.call_args.args[0], [
                "dotnet", "build", str(project), "/p:Configuration=Release", "/p:CreateZipPackage=true"
            ])

    def test_failed_build_does_not_create_archive(self):
        with mock.patch.object(self.mod.subprocess, "run", return_value=SimpleNamespace(returncode=1)):
            self.assertEqual(self.invoke("--skip-upload", "--skip-github"), 1)
        self.assertFalse(self.archive.exists())


if __name__ == "__main__":
    unittest.main()
