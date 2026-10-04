"""Portable configuration checks requiring neither sockets nor models."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from test_jev import jev


class TestPortableConfiguration(unittest.TestCase):
    def test_loopback_default_does_not_start_a_service(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = jev.load_config()
        self.assertEqual(cfg['endpoints'][0]['url'], 'http://127.0.0.1:11434')
        self.assertFalse(cfg['endpoints'][0]['autostart'])

    def test_ollama_url_fallback_and_explicit_endpoint_precedence(self):
        with patch.dict(os.environ, {'OLLAMA_URL': 'http://127.0.0.1:11435'}, clear=True):
            cfg = jev.load_config()
            self.assertEqual(cfg['endpoints'][0]['url'], 'http://127.0.0.1:11435')
            os.environ['JEV_ENDPOINTS'] = 'local=http://127.0.0.1:11434'
            self.assertEqual(jev.load_config()['endpoints'][0]['url'], 'http://127.0.0.1:11434')

    def test_example_preserves_digest_pin(self):
        path = str(Path(__file__).resolve().parent / 'config.example.json')
        with patch.dict(os.environ, {'JEV_CONFIG': path}, clear=True):
            cfg = jev.load_config()
        self.assertEqual(jev.pinned_digest(cfg, cfg['model']), '368717f114a9')
