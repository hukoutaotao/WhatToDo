"""Prevent a synthetic spike from writing/probing an unrelated local target."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from tools.bootstrap_toolchain import owned_path, archive_members
from tools.verify_toolchain import ROOT, SpikeFailure, require_local_cluster, verify_server_identity


class ToolchainIsolationTests(unittest.TestCase):
    def test_cluster_and_artifact_paths_cannot_escape_owned_roots(self):
        with self.assertRaises(SpikeFailure): require_local_cluster(ROOT / "database")
        with self.assertRaises(ValueError): owned_path(ROOT / "unrelated", ROOT / ".dev-tools")
        self.assertEqual(require_local_cluster(ROOT / ".local-state/toolchain/owned/cluster"), (ROOT / ".local-state/toolchain/owned/cluster").resolve())

    def test_archive_traversal_is_rejected_before_extraction(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            with ZipFile(path / "bad.zip", "w") as archive:
                archive.writestr("pgsql/bin/../../../outside.exe", b"synthetic")
            with ZipFile(path / "bad.zip") as archive:
                with self.assertRaises(ValueError): archive_members(archive, path / "destination")
            self.assertFalse((path / "outside.exe").exists())

    def test_archive_selection_keeps_pgadmin_and_unrelated_assets_out(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            with ZipFile(path / "fixture.zip", "w") as archive:
                archive.writestr("pgsql/bin/postgres.exe", b"synthetic")
                archive.writestr("pgsql/pgAdmin 4/unneeded", b"synthetic")
            with ZipFile(path / "fixture.zip") as archive:
                self.assertEqual([item.filename for item, _ in archive_members(archive, path / "destination")], ["pgsql/bin/postgres.exe"])

    def test_port_reuse_cannot_redirect_probes_into_another_database(self):
        class WrongConnection:
            def execute(self, statement):
                if statement != "SHOW data_directory": raise AssertionError("Write attempted before identity check")
                return self
            def fetchone(self): return [str(ROOT / "unrelated-cluster")]
        with self.assertRaises(SpikeFailure): verify_server_identity(WrongConnection(), ROOT / ".local-state/toolchain/owned/cluster")


if __name__ == "__main__": unittest.main()
