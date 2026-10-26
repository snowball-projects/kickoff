# snowball rules

Stage

- Early-stage project with one user, the founder. Build for that.
  No guards, migrations, compatibility code, release processes or docs
  for users who don't exist yet.

Design

- Choose the simplest, least costly design that works, in everything:
  architecture, hosting, backend, frontend and data.
- Within that, make it as fast and light as possible.
- When there are several reasonable ways to do something that matters,
  propose the best 2 or 3 with their trade-offs, recommend one, and
  wait for the founder to choose. Make small choices yourself and
  mention them.

Less is more

- Prefer deleting to adding. At the end of each task, say what can now
  be removed, and remove it if it is in scope.
- No dead code, old experiments, research notes or drafts in the repo.
  Tag anything worth keeping, then delete it.
- Validate data once, where it is produced. Trust our own files.
- Keep the README to one screen, written for a person. Add no other
  docs unless asked, and don't edit AGENTS.md unless asked.

Work

- Keep each PR to one coherent piece of work, then stop and report.
- Ask the founder first before anything irreversible (force-push,
  deleting unmerged work, changing repo settings, spending money) or
  any change of direction (new architecture, new service, change of
  scope). Otherwise proceed, and merge when checks pass.
- GitHub is the source of truth. Push all work; nothing lives only on
  one machine.

Public copy and data

- Write snowball and every project name in lowercase.
- Never label anything as made by or with AI, anywhere.
- Never use em dashes.
- No instructions in the interface. Make it obvious to use; on-screen text states facts, like data dates and sources, never how to use the app.
- Code is MIT. Data we create is CC0. Data from others keeps its
  source's license and credit.
- Store each fact with its source link and the date checked, never
  copies of other sites' pages.
- Principles: https://snowball-projects.github.io/principles/

## Repo notes
A static sports calendar rebuilt daily from public schedule feeds.
Python: `.venv/bin/python -m ruff check src tests scripts`; `.venv/bin/python -m ruff format --check src tests scripts`; `.venv/bin/python -m pytest`.
Frontend: `npm --prefix frontend test`; `npm --prefix frontend run test:browser`; `npm --prefix frontend run build`.
