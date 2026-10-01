import unittest

from job_finder import Job, is_location_eligible, score_job
from linkedin_outreach import blocked, make_draft


class OutreachTests(unittest.TestCase):
    def test_draft_uses_contact_and_user_supplied_summary(self):
        draft = make_draft(
            {
                "name": "Alex Example",
                "role_company": "Platform Lead | Example Co",
            },
            "I build reliable cloud platforms.",
            "Platform Engineering roles",
            "remote",
        )
        self.assertIn("Hi Alex,", draft)
        self.assertIn("Platform Lead at Example Co", draft)
        self.assertIn("I build reliable cloud platforms.", draft)
        self.assertIn("would you be comfortable referring me?", draft)

    def test_configured_current_and_past_employer_exclusions(self):
        contact = {"name": "Alex Example", "role_company": "Engineer | Other Co"}
        self.assertTrue(
            blocked(
                contact,
                [],
                set(),
                ("former employer",),
            )
            is False
        )
        contact["work_history"] = "Former Employer — Platform Engineer"
        self.assertTrue(blocked(contact, [], set(), ("former employer",)))

    def test_previously_contacted_name_is_excluded(self):
        contact = {"name": "Alex Example", "role_company": "Engineer"}
        history = [
            {
                "name": "Alex Example",
                "status": "Sent",
                "linkedin_profile": "https://www.linkedin.com/in/alex-example/",
            }
        ]
        self.assertTrue(blocked(contact, history, set(), ()))


class JobFinderTests(unittest.TestCase):
    def test_remote_role_must_be_eligible_in_location(self):
        profile = {"locations": ["Pune", "Remote"]}
        self.assertTrue(
            is_location_eligible(
                Job("SRE", "Example", "Remote - India", "", "", "test"), profile
            )
        )
        self.assertFalse(
            is_location_eligible(
                Job("SRE", "Example", "Remote - US only", "", "", "test"), profile
            )
        )

    def test_score_includes_matching_skill(self):
        profile = {
            "skills": ["Kubernetes"],
            "target_titles": ["Platform Engineer"],
        }
        job = Job(
            "Platform Engineer",
            "Example",
            "Pune",
            "https://example.test/job",
            "Kubernetes",
            "test",
        )
        score, matched = score_job(job, profile)
        self.assertGreater(score, 0)
        self.assertEqual(matched, ["Kubernetes"])


if __name__ == "__main__":
    unittest.main()
