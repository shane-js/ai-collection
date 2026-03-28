"""
Seed topics for the Terrible Advice pipeline.

Each topic is a short string describing a life/career/tech scenario
where someone might ask for advice. These get fed into the pipeline
via LoadDataFromDicts as a list of dicts: [{"topic": "..."}, ...]

Add, remove, or edit topics as you like. The more specific the topic,
the more interesting the generated advice tends to be.
"""


import random


TOPICS = [
    "job interviews",
    "first dates",
    "cooking for guests",
    "debugging production issues at 2am",
    "giving presentations to executives",
    "personal finance in your 20s",
    "negotiating a salary offer",
    "managing remote teams",
    "networking at conferences",
    "writing a resume",
    "dealing with difficult coworkers",
    "improving work-life balance",
    "preparing for a performance review",
    "starting a side hustle",
    "training for a marathon",
    "studying for exams",
    "learning a new programming language",
    "getting better at public speaking",
    "asking for a raise",
    "switching careers",
    "managing time effectively",
    "overcoming procrastination",
    "learning to play a musical instrument"
  ]


def get_seed_data(limit: int | None = None) -> list[dict]:
    """
    Convert TOPICS into the format LoadDataFromDicts expects.

    TextGeneration requires an "instruction" column as the user message.
    We keep "topic" alongside it so the final dataset retains the label.

    Example return value:
      [{"topic": "job interviews", "instruction": "Give me advice about: job interviews"}, ...]
    """
    topics = random.sample(TOPICS, limit) if limit else TOPICS
    return [{"topic": t, "instruction": f"Give me advice about: {t}"} for t in topics]
