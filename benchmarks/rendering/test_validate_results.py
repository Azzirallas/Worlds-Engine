"""Synthetic input tests for the standalone renderer CSV validator."""

import csv
from pathlib import Path
import tempfile
import unittest

from validate_results import validate


def write_csv(path, rows):
    """Write test data with its dictionary key set as CSV headers."""
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


class RenderBenchmarkValidatorTests(unittest.TestCase):
    """Ensure invalid samples never become credible performance results."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.summary_path = root / 'example.csv'
        self.samples_path = root / 'example_samples.csv'
        self.summary = {'mode':'nodes','count':'30','sample_frames':'4','frame_p50_ms':'30',
                        'frame_p95_ms':'40','frame_p99_ms':'40','render_cpu_p50_ms':'2',
                        'render_cpu_p95_ms':'2','render_gpu_p50_ms':'1',
                        'render_gpu_p95_ms':'1','valid_gpu_samples':'2'}
        self.samples = [{'frame':str(i),'frame_delta_ms':str(t), 'render_cpu_ms':'2',
                         'render_gpu_ms':('-1' if i < 2 else '1'),
                         'draw_calls':'3','objects':'30'} for i,t in enumerate((10,20,30,40))]

    def store(self):
        """Write the current synthetic summary and frame samples."""
        write_csv(self.summary_path, [self.summary])
        write_csv(self.samples_path, self.samples)

    def test_valid_run(self):
        self.store()
        summary, frames, gpu = validate(self.summary_path)
        self.assertEqual((frames, gpu, summary['mode']), (4, 2, 'nodes'))

    def test_nonfinite_data_fails(self):
        self.samples[1]['frame_delta_ms'] = 'NaN'
        self.store()
        with self.assertRaisesRegex(ValueError, 'invalid numeric'):
            validate(self.summary_path)

    def test_mismatched_summary_fails(self):
        self.summary['frame_p95_ms'] = '1'
        self.store()
        with self.assertRaisesRegex(ValueError, 'reported'):
            validate(self.summary_path)

    def test_unavailable_gpu_is_valid(self):
        self.summary['valid_gpu_samples'] = '0'
        self.summary['render_gpu_p50_ms'] = '-1'
        self.summary['render_gpu_p95_ms'] = '-1'
        for sample in self.samples:
            sample['render_gpu_ms'] = '-1'
        self.store()
        _, _, gpu = validate(self.summary_path)
        self.assertEqual(gpu, 0)


if __name__ == '__main__':
    unittest.main()
