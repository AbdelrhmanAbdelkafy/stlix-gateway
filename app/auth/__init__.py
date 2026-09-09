"""Users, sessions and permissions for the platform (PA2/PA3).

Modelled on the Nama security profiles the company already runs on: a user
holds one or more *roles* (profiles), each role is a matrix of
`resource × action`, and a user can carry explicit allow/deny overrides on top
— deny wins. Resources are the things people open (tools, APIs, the other
systems on our servers); actions are `view`, `edit`, `admin`.

Everything lives in one SQLite file under `data/auth/` so it survives a
container rebuild, and every change is written to an audit table.
"""
