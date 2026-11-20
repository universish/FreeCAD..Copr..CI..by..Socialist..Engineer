import io
import stat
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import normalize_payload


def newc_entry(name, mode, data=b"", ino=1, nlink=1):
    fields = [ino, mode, 0, 0, nlink, 0, len(data), 0, 0, 0, 0, len(name.encode()) + 1, 0]
    header = b"070701" + b"".join(f"{field:08x}".encode() for field in fields)
    body = header + name.encode() + b"\0"
    body += b"\0" * (-len(body) % 4)
    body += data
    body += b"\0" * (-len(body) % 4)
    return body


def newc_archive(*entries):
    return b"".join(entries) + newc_entry("TRAILER!!!", 0)


class NormalizePayloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "root"
        self.root.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def tar_stream(self, members):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as archive:
            for member, content in members:
                archive.addfile(member, io.BytesIO(content) if member.isfile() else None)
        data.seek(0)
        return data

    def ar_member(self, name, data):
        header = (
            name.encode().ljust(16)
            + b"0".ljust(12)
            + b"0".ljust(6)
            + b"0".ljust(6)
            + b"100644".ljust(8)
            + str(len(data)).encode().ljust(10)
            + b"`\n"
        )
        return header + data + (b"\n" if len(data) % 2 else b"")

    def tar_bytes(self, members):
        return self.tar_stream(members).getvalue()

    def test_deb_metadata_and_maintainer_scripts_are_inspected_not_run(self):
        control = tarfile.TarInfo("control")
        control.size = len(b"Package: freecad\nArchitecture: amd64\n")
        postinst = tarfile.TarInfo("postinst")
        postinst.mode = 0o755
        postinst.size = len(b"#!/bin/sh\necho reviewed\n")
        control_tar = self.tar_bytes([(control, b"Package: freecad\nArchitecture: amd64\n"), (postinst, b"#!/bin/sh\necho reviewed\n")])
        binary = tarfile.TarInfo("usr/bin/FreeCAD")
        binary.size = 4
        data_tar = self.tar_bytes([(binary, b"ELF!")])
        deb = self.root / "freecad.deb"
        deb.write_bytes(
            b"!<arch>\n"
            + self.ar_member("debian-binary/", b"2.0\n")
            + self.ar_member("control.tar/", control_tar)
            + self.ar_member("data.tar/", data_tar)
        )
        extracted = self.root / "deb-root"
        normalize_payload.extract_deb(deb, extracted)
        metadata = (extracted / "metadata/upstream-deb-metadata.json").read_text(encoding="utf-8")
        self.assertIn('"postinst"', metadata)
        self.assertEqual((extracted / "metadata/upstream-deb-control/postinst").read_text(), "#!/bin/sh\necho reviewed\n")
        self.assertTrue((extracted / "usr/bin/FreeCAD").is_file())

    def test_tar_extraction_preserves_executable_and_internal_symlink(self):
        executable = tarfile.TarInfo("usr/bin/FreeCAD")
        executable.mode = 0o755
        executable.size = 2
        link = tarfile.TarInfo("usr/bin/freecad")
        link.type = tarfile.SYMTYPE
        link.linkname = "FreeCAD"
        normalize_payload.extract_tar_stream(self.tar_stream([(executable, b"ok"), (link, b"")]), self.root)
        self.assertTrue((self.root / "usr/bin/FreeCAD").stat().st_mode & stat.S_IXUSR)
        self.assertEqual((self.root / "usr/bin/freecad").readlink(), Path("FreeCAD"))

    def test_tar_parent_traversal_is_rejected(self):
        entry = tarfile.TarInfo("../../outside")
        entry.size = 1
        with self.assertRaises(normalize_payload.PayloadError):
            normalize_payload.extract_tar_stream(self.tar_stream([(entry, b"x")]), self.root)

    def test_tar_absolute_symlink_is_rejected(self):
        link = tarfile.TarInfo("escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc/passwd"
        with self.assertRaises(normalize_payload.PayloadError):
            normalize_payload.extract_tar_stream(self.tar_stream([(link, b"")]), self.root)

    def test_cpio_rejects_parent_traversal(self):
        archive = io.BytesIO(newc_archive(newc_entry("../outside", stat.S_IFREG | 0o644, b"x")))
        with self.assertRaises(normalize_payload.PayloadError):
            normalize_payload.extract_newc(archive, self.root)

    def test_cpio_extracts_regular_file_and_symlink(self):
        archive = io.BytesIO(newc_archive(
            newc_entry("usr/bin/FreeCAD", stat.S_IFREG | 0o755, b"cad"),
            newc_entry("usr/bin/freecad", stat.S_IFLNK | 0o777, b"FreeCAD", ino=2),
        ))
        normalize_payload.extract_newc(archive, self.root)
        self.assertEqual((self.root / "usr/bin/FreeCAD").read_bytes(), b"cad")
        self.assertEqual((self.root / "usr/bin/freecad").readlink(), Path("FreeCAD"))

    def test_cpio_preserves_hardlinks_when_data_entry_follows(self):
        archive = io.BytesIO(newc_archive(
            newc_entry("usr/share/freecad/license-copy", stat.S_IFREG | 0o644, b"", ino=7, nlink=2),
            newc_entry("usr/share/freecad/license", stat.S_IFREG | 0o644, b"MIT", ino=7, nlink=2),
        ))
        normalize_payload.extract_newc(archive, self.root)
        first = self.root / "usr/share/freecad/license-copy"
        second = self.root / "usr/share/freecad/license"
        self.assertEqual(first.read_bytes(), b"MIT")
        self.assertEqual(first.stat().st_ino, second.stat().st_ino)

    def test_cpio_rejects_incomplete_hardlink_groups(self):
        archive = io.BytesIO(newc_archive(
            newc_entry("usr/share/freecad/license", stat.S_IFREG | 0o644, b"", ino=7, nlink=2),
        ))
        with self.assertRaisesRegex(normalize_payload.PayloadError, "incomplete RPM hardlink group"):
            normalize_payload.extract_newc(archive, self.root)

    def test_cpio_rejects_duplicate_pending_hardlink_path(self):
        archive = io.BytesIO(newc_archive(
            newc_entry("usr/share/freecad/license", stat.S_IFREG | 0o644, b"", ino=7, nlink=2),
            newc_entry("usr/share/freecad/license", stat.S_IFREG | 0o644, b"MIT", ino=7, nlink=2),
        ))
        with self.assertRaisesRegex(normalize_payload.PayloadError, "duplicate RPM payload path"):
            normalize_payload.extract_newc(archive, self.root)

    def test_cpio_rejects_missing_path_terminator(self):
        name = b"usr/share/freecad/licenseX"
        fields = [7, stat.S_IFREG | 0o644, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name), 0]
        header = b"070701" + b"".join(f"{field:08x}".encode() for field in fields)
        archive = io.BytesIO(newc_archive(header + name + b"\0" * (-len(header + name) % 4)))
        with self.assertRaisesRegex(normalize_payload.PayloadError, "invalid RPM cpio pathname"):
            normalize_payload.extract_newc(archive, self.root)


if __name__ == "__main__":
    unittest.main()
