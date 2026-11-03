"""The same-node launcher's metadata argument reaches the exact producers."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from . import coverage,pack_reference


class LauncherCLI(unittest.TestCase):
    def test_same_node_metadata_argument_is_forwarded_without_scientific_work(self):
        for module in (pack_reference,coverage):
            with self.subTest(module=module.__name__),patch.object(module,'run') as run,patch.object(sys,'argv',
                    [module.__name__,'--plan','/fixture/plan.json','--startup-proof','/fixture/startup.json']):
                module.main()
                run.assert_called_once_with(Path('/fixture/plan.json'),startup_proof=Path('/fixture/startup.json'))

    def test_original_plan_only_interface_is_retained(self):
        for module in (pack_reference,coverage):
            with self.subTest(module=module.__name__),patch.object(module,'run') as run,patch.object(sys,'argv',
                    [module.__name__,'--plan','/fixture/plan.json']):
                module.main()
                run.assert_called_once_with(Path('/fixture/plan.json'),startup_proof=None)


if __name__=='__main__':unittest.main()
