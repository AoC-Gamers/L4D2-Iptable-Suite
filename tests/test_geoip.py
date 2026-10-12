#!/usr/bin/python3
"""Data updater regressions; no credentials, downloads, or firewall access."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class GeoDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.csv = self.path / 'csv'
        self.csv.mkdir()
        (self.csv / 'GeoLite2-Country-Locations-en.csv').write_text('geoname_id,country_iso_code\n1,AR\n')
        self.blocks = self.csv / 'GeoLite2-Country-Blocks-IPv4.csv'
        self.blocks.write_text('network,geoname_id\n192.0.2.0/24,1\n')
        self.out = self.path / 'out'

    def build(self, countries='AR'):
        return subprocess.run(['python3','-I',str(ROOT/'scripts/geoip/build_geo_country_sets.py'),
            '--csv-dir',str(self.csv),'--countries',countries,'--output-dir',str(self.out)],
            capture_output=True,text=True,check=False)

    def test_country_cannot_escape_output_directory(self):
        r=self.build('../escaped')
        self.assertEqual(r.returncode,2,r.stderr)
        self.assertFalse(self.out.exists())

    def test_invalid_data_keeps_previous_country_file(self):
        self.out.mkdir()
        target=self.out/'AR.ipv4.txt'
        target.write_text('198.51.100.0/24\n')
        self.blocks.write_text('network,geoname_id\n192.0.2.0/24,1\n192.0.2.1/24,1\n')
        self.assertEqual(self.build().returncode,2)
        self.assertEqual(target.read_text(),'198.51.100.0/24\n')

    def test_atomic_generation_keeps_other_country(self):
        # This test runs unprivileged; root deployments require private ancestors.
        self.out.mkdir()
        foreign=self.out/'US.ipv4.txt'
        foreign.write_text('203.0.113.0/24\n')
        r=self.build()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('192.0.2.0/24',(self.out/'AR.ipv4.txt').read_text())
        self.assertEqual(foreign.read_text(),'203.0.113.0/24\n')
        self.assertFalse(list(self.out.glob('.AR.*')))


if __name__=='__main__':
    unittest.main(verbosity=2)
