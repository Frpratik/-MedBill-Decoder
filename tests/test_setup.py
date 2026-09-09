"""Fail-closed checks for source setup; no live network or fake CMS data."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from medbill.download_sources import ensure_archive


class SourceSetupTests(unittest.TestCase):
    def test_matching_existing_file_is_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.zip'; path.write_bytes(b'test-only-checksum-input')
            digest=hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(ensure_archive(directory,path.name,digest,check_only=True),'verified existing')

    def test_bad_existing_file_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.zip'; path.write_bytes(b'bad-test-input')
            with self.assertRaises(ValueError):
                ensure_archive(directory,path.name,'0'*64)
            self.assertEqual(path.read_bytes(),b'bad-test-input')

    def test_check_only_never_creates_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                ensure_archive(directory,'missing.zip','0'*64,check_only=True)
            self.assertEqual(list(Path(directory).iterdir()),[])


if __name__=='__main__':
    unittest.main()
