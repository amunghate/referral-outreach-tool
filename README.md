# Referral Outreach Toolkit

A local, dependency-free Python toolkit for tracking professional referrals,
preparing personalized message drafts, and discovering public job listings.

The tools deliberately do not log in to LinkedIn, scrape member profiles, send
messages, or submit job applications. Review profiles and drafts yourself, and
send messages manually through LinkedIn.

## Requirements

- Python 3.10 or newer
- Internet access for public job search; no packages to install

## Referral outreach

Start with an empty tracker (or copy `contacts.example.csv` to
`linkedin-referral-outreach.csv`). Import contacts you are authorized to
process from a CSV with `name` and `role_company` columns:

```bash
python3 linkedin_outreach.py import-csv --source connections.csv
```

Optional import columns include `location`, `linkedin_profile`, `experience`,
`work_history`, `employment_history`, `previous_companies`, `past_companies`,
and `notes`. New entries are marked `Needs review`; imports do not assume a
person is qualified based on a name/title alone.

Review the contact's public profile, current and previous employment, role fit,
and whether you have already contacted them. Excluded company terms and names
can be configured with the command-line options below. Then qualify contacts
individually and prepare a batch:

```bash
python3 linkedin_outreach.py --help
python3 linkedin_outreach.py qualify --name "Alex Example"
python3 linkedin_outreach.py prepare --limit 10
```

Drafts are written to `linkedin-referral-drafts.csv`. Confirm the correct
recipient inside LinkedIn before manually sending. After sending, record it:

```bash
python3 linkedin_outreach.py mark-sent --name "Alex Example"
```

The batch size is limited to 20; already-sent and previously-messaged contacts
are excluded. The tracker and generated drafts can contain personal data, so
keep them private and out of public repositories.

## Public job search

Edit `resume_profile.json` with your own target titles, locations, and skills,
then run:

```bash
python3 job_finder.py resume-review
python3 job_finder.py search --query "Senior Platform Engineer" --limit 15
python3 job_finder.py search --query "Cloud DevOps Engineer" --json
```

Job data comes from the public Remotive and Arbeitnow APIs. Results are ranked
against the local profile, filtered to Pune or remote roles with broad India/
APAC/worldwide eligibility by default, and should be checked at the source
before applying. Provider outages are reported as warnings.

## Configuration

The outreach script supports:

```bash
python3 linkedin_outreach.py --help
python3 linkedin_outreach.py prepare --help
```

Use `--tracker PATH` before the subcommand to choose a private tracker file.
The job finder accepts `--profile PATH`; otherwise it reads
`resume_profile.json` beside the script.

## Privacy and responsible use

- Never commit a real resume, contact list, outreach history, drafts, credentials,
  or other personal data.
- Do not use this toolkit to scrape LinkedIn or automate message sending.
- Respect recipient preferences, platform rules, and applicable privacy laws.
- Review all profile information, exclusions, and message drafts yourself.

## License

MIT; see [LICENSE](LICENSE).
