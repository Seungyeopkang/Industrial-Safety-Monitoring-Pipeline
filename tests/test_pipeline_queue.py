import asyncio
import unittest

from fastapi import HTTPException

from api import main


class PipelineQueueTests(unittest.TestCase):
    def test_bounded_queue_rejects_new_upload_when_full(self):
        async def scenario():
            original_queue = main.PIPELINE_QUEUE
            original_jobs = main.JOBS.copy()
            original_metrics = main.PIPELINE_METRICS.copy()
            try:
                main.PIPELINE_QUEUE = asyncio.Queue(maxsize=1)
                main.JOBS.clear()
                main.PIPELINE_METRICS.update({"accepted": 0, "dropped": 0, "rejected": 0})
                position = await main._enqueue_pipeline("first", "first.jpg", "image")
                self.assertEqual(position, 1)
                with self.assertRaises(HTTPException) as raised:
                    await main._enqueue_pipeline("second", "second.jpg", "image")
                self.assertEqual(raised.exception.status_code, 429)
            finally:
                main.PIPELINE_QUEUE = original_queue
                main.JOBS.clear()
                main.JOBS.update(original_jobs)
                main.PIPELINE_METRICS.clear()
                main.PIPELINE_METRICS.update(original_metrics)

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
