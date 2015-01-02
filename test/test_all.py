# -*- coding: utf-8 -*-

import os
import sys
import shutil
import tempfile
import unittest
import subprocess

HERE =os.path.realpath(os.path.dirname(__file__))
sys.path.insert(0, os.path.realpath(os.path.join(HERE, '..')))

from stepdad.main import DumbSetup


class TestAll(unittest.TestCase):

    def setUp(self):
        self.root_path = tempfile.mkdtemp()
        self.module_path = os.path.realpath(os.path.join(HERE, 'data', 'tinysegmenter.py'))

    def tearDown(self):
        if os.path.exists(self.root_path):
           shutil.rmtree(self.root_path)

    def test_all(self):
        ds = DumbSetup(module_path=self.module_path, root_path=self.root_path)
        ds.write_setup_py()
        ds.install_module_to_root_dir()
        python = sys.executable
        retval = subprocess.call([python, 'setup.py', 'check'], cwd=self.root_path, env={},)
        assert retval == 0, '"check" subcommand exited with: {0}'.format(retval)

if __name__ == '__main__':
    unittest.main()


