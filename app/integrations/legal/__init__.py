"""المستشار القانوني — the legal counsel.

Same shape as Nama Expert (corpus -> retrieval -> grounded answer, or the
passages if no model is attached), plus the one thing this domain needs and the
other does not: `citations.py`, which checks every article number in an answer
against the statutes actually on disk and strikes out the ones that are not
there.

That guard is the module. Everything else is plumbing around it.
"""
