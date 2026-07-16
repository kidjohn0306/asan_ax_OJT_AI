import unittest
from unittest.mock import MagicMock, patch

from services.admin_service import fetch_generation_jobs


class FetchGenerationJobsTests(unittest.TestCase):
    def test_returns_disabled_when_repository_not_configured(self):
        with patch("repositories.generation_v2_repo", None):
            result = fetch_generation_jobs()
        self.assertEqual(result, {"jobs": [], "enabled": False})

    def test_returns_jobs_from_repository_when_configured(self):
        repo = MagicMock()
        repo.list_jobs.return_value = [{"generation_job_id": "job-1"}]
        with patch("repositories.generation_v2_repo", repo):
            result = fetch_generation_jobs()
        self.assertEqual(result, {"jobs": [{"generation_job_id": "job-1"}], "enabled": True})
        repo.list_jobs.assert_called_once()


if __name__ == "__main__":
    unittest.main()
