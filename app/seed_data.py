"""Sample data for ApplyTrack.

12 realistic internship applications with dates relative to *today*,
so the stats dashboard and "upcoming deadlines" list always have
something to show in a demo. Statuses are spread across the whole
pipeline (Applied -> OA/Assessment -> Interview -> Offer / Rejected).

These are SAMPLE rows only — company names are real employers the
author has applied to, but the req IDs, pay figures and dates are
illustrative, not a record of real applications. Run ``seed_db.py
--clear`` to wipe them and start with an empty tracker.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.models import ApplicationCreate, Status

TODAY = date.today()


def _days(n: int) -> date:
    return TODAY + timedelta(days=n)


def sample_applications() -> list[ApplicationCreate]:
    return [
        ApplicationCreate(
            company="Texas Instruments", role="Software Engineering Intern — Compiler",
            location="Sugar Land, TX", term="Summer 2027", req_id="25019103",
            date_applied=_days(-14), status=Status.INTERVIEW,
            deadline=_days(4), pay="$28/hr",
            notes="OA passed, technical interview scheduled.",
            link="https://careers.ti.com/",
        ),
        ApplicationCreate(
            company="Google", role="Forward Deployed Engineering Intern",
            location="Sunnyvale, CA", term="Summer 2027", req_id="75665705386549958",
            date_applied=_days(-13), status=Status.OA,
            deadline=_days(6), pay="$45/hr",
            notes="Coding assessment invite received; due this week.",
            link="https://careers.google.com/",
        ),
        ApplicationCreate(
            company="Micron", role="Intern — Product Yield Software Engineer",
            location="Boise, ID", term="Summer 2027", req_id="JR115864",
            date_applied=_days(-12), status=Status.APPLIED,
            deadline=_days(10), pay="$30/hr",
            notes="Waiting to hear back after applying.",
            link="https://www.micron.com/careers",
        ),
        ApplicationCreate(
            company="Lockheed Martin", role="Software Engineer Intern — Aeronautics",
            location="Fort Worth, TX", term="Summer 2027", req_id="21637",
            date_applied=_days(-11), status=Status.INTERVIEW,
            deadline=_days(2), pay="$26/hr",
            notes="Recruiter screen done; hiring-manager interview next.",
            link="https://www.lockheedmartinjobs.com/",
        ),
        ApplicationCreate(
            company="Cloudflare", role="Software Engineer Intern",
            location="Austin, TX", term="Summer 2027", req_id="8199958",
            date_applied=_days(-9), status=Status.OFFER,
            deadline=None, pay="$45/hr",
            notes="Offer received! Decide by end of month.",
            link="https://www.cloudflare.com/careers/",
        ),
        ApplicationCreate(
            company="Jump Trading", role="Campus Software Engineer Intern",
            location="Chicago, IL", term="Summer 2027", req_id="8002989",
            date_applied=_days(-8), status=Status.REJECTED,
            deadline=None, pay="$250,000/yr (est.)",
            notes="Rejected after OA. Reapply next cycle.",
            link="https://www.jumptrading.com/careers",
        ),
        ApplicationCreate(
            company="Point72", role="Summer Internship — Software Engineer",
            location="New York, NY", term="Summer 2027", req_id="8885733002",
            date_applied=_days(-7), status=Status.APPLIED,
            deadline=_days(12), pay="$130,000/yr",
            notes="Application under review.",
            link="https://www.point72.com/careers/",
        ),
        ApplicationCreate(
            company="NBCUniversal", role="Software Engineering Intern",
            location="New York, NY", term="Summer 2027", req_id="744000160659459",
            date_applied=_days(-6), status=Status.OA,
            deadline=_days(5), pay="$30/hr",
            notes="Cover letter + transcript submitted with application.",
            link="https://www.nbcunicareers.com/",
        ),
        ApplicationCreate(
            company="PayPal", role="Software Engineer Intern",
            location="San Jose, CA", term="Summer 2027", req_id="R0138586",
            date_applied=_days(-5), status=Status.APPLIED,
            deadline=_days(20), pay="$32–$55/hr",
            notes="Closes Dec 6 — applied early.",
            link="https://careers.pypl.com/",
        ),
        ApplicationCreate(
            company="Nintendo", role="Intern Software Engineer — Connectivity",
            location="Redmond, WA", term="Summer 2027", req_id="464",
            date_applied=_days(-4), status=Status.APPLIED,
            deadline=_days(15), pay="$45/hr",
            notes="Onsite role; relocation would be needed.",
            link="https://careers.nintendo.com/",
        ),
        ApplicationCreate(
            company="Microsoft", role="Software Engineer Intern",
            location="Redmond, WA", term="Summer 2027", req_id="200061280",
            date_applied=_days(-3), status=Status.INTERVIEW,
            deadline=_days(1), pay="$5,690–$11,210/mo",
            notes="Final-round interview tomorrow — prep system design.",
            link="https://careers.microsoft.com/",
        ),
        ApplicationCreate(
            company="Firefly Aerospace", role="Internship — Software Engineering",
            location="Cedar Park, TX", term="Spring 2027", req_id="JR100188",
            date_applied=_days(-2), status=Status.APPLIED,
            deadline=_days(8), pay="—",
            notes="Spring term; overlaps spring semester — check schedule.",
            link="https://fireflyspace.com/careers/",
        ),
    ]
