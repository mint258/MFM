import unittest
from workflows.benchmark_data.acquire import quota_headroom, safe_asset

class AdmissionTests(unittest.TestCase):
    def test_real_quota_units_and_identity(self):
        text = "Disk quotas for user zixiao (uid 1278):\n /dev/sda1 3860254404 0 4294967296 142437135 0 0\n"
        self.assertEqual(quota_headroom(text, 1278), 445146001408)
        with self.assertRaises(ValueError):
            quota_headroom(text, 999)
        with self.assertRaises(ValueError):
            quota_headroom(text.replace("4294967296", "0"), 1278)

    def test_unsafe_transport_names_and_unknown_sizes_are_rejected(self):
        base = {"name": "task.csv", "url": "https://raw.githubusercontent.com/a/b/c", "bytes": 10}
        self.assertEqual(safe_asset(base), "task.csv")
        for patch in ({"name": "../task.csv"}, {"name": "a\\\\task.csv"}, {"bytes": -1},
                      {"url": "http://raw.githubusercontent.com/a"}, {"url": "https://untrusted.example/a"}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                safe_asset(dict(base, **patch))


    def test_official_source_hosts_require_https_and_no_credentials(self):
        for url in ("https://huggingface.co/datasets/a/b/resolve/rev/file.csv",
                    "https://ndownloader.figshare.com/files/23637518",
                    "https://polarishub.io/api/v1/dataset/biogen/adme-fang-v1",
                    "https://data.polarishub.io/dataset/biogen/adme-fang-v1/table.parquet",
                    "https://yzhang.hpc.nyu.edu/IMA/Datasets/NMRShiftDB2_DFT.zip",
                    "https://dataverse.harvard.edu/api/access/datafile/4426004"):
            self.assertEqual(safe_asset({"name": "asset.csv", "url": url, "bytes": 1}), "asset.csv")
        for url in ("https://huggingface.co.evil.example/file",
                    "https://user:password@huggingface.co/file"):
            with self.assertRaises(ValueError):
                safe_asset({"name": "asset.csv", "url": url, "bytes": 1})

if __name__ == "__main__":
    unittest.main()
