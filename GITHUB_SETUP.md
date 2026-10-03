# GitHub setup checklist

This file is a short publishing checklist for GreenRoute Campus.

## 1. Create the repository

On GitHub, create a new repository. A public repository is appropriate if you want to showcase the student project; choose private if the code should remain private.

Do not initialize the new repository with another README, license, or `.gitignore` if you are pushing this complete project folder.

## 2. Initialize locally

```bash
git init
git add .
git status
git commit -m "Initial GreenRoute Campus release"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

## 3. Before the first push

Run:

```bash
git status
git ls-files | grep -E '(^|/)\.env$|\.db$|\.venv/' || true
```

The command should not show `.env`, a SQLite database, or `.venv`.

Also search the source for accidental secrets. Do not paste real keys into issues or chat while doing this.

## 4. Repository settings

Recommended GitHub housekeeping:

- Set a clear repository description.
- Add topics such as `flask`, `python`, `sqlite`, `sustainable-mobility`, `campus`, `openai`, `leaflet`, and `student-project` if they accurately describe the project.
- Add the repository URL/demo URL only if it is genuinely public and reachable.
- Keep the default branch as `main`.
- Enable the included Actions workflow.
- Review Issues and Discussions according to how you want to maintain the project.

## 5. Protect secrets

The repository should contain `.env.example`, not `.env`.

For a deployed GitHub Actions workflow, store secrets in **Settings → Secrets and variables → Actions**. Never hard-code an API key in YAML, Python, JavaScript, HTML, screenshots, or documentation.

## 6. Releases

When you have a stable milestone, create a Git tag such as:

```bash
git tag -a v1.0.0 -m "GreenRoute Campus v1.0.0"
git push origin v1.0.0
```

Then use GitHub Releases to attach a ZIP if you want a downloadable packaged release.

## 7. What should normally be committed

Commit source code, templates, static assets, tests, documentation, configuration templates, CI files, and setup scripts.

Do not commit local virtual environments, `.env`, API keys, SQLite runtime databases, cache files, or private exports.
