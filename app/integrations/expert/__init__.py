"""Nama Expert — the chat that answers about Nama and about this platform.

Three modules, in the order a question travels through them:

- `knowledge.py` builds the index (repo documents + the gateway's own map);
- `retrieve.py` finds the passages that actually bear on the question;
- `answer.py` turns those passages into an answer — or, when no model is
  attached, hands the passages back unchanged rather than improvising.
"""
