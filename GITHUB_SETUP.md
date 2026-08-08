# GitHub Repository Setup

## 1. Initialise git at the project root
```bash
cd carbonsense    # your project root (backend lives here)
git init
git add .
git commit -m "feat: initial CarbonSense monorepo — backend + frontend"
```

## 2. Create repository on GitHub
- Go to github.com/new
- Name: `carbonsense`
- Visibility: Public (for portfolio) or Private
- Do NOT initialise with README (you already have one)

## 3. Push
```bash
git remote add origin https://github.com/YOUR_USERNAME/carbonsense.git
git branch -M main
git push -u origin main
```

## 4. Branch protection (recommended)
GitHub repo → Settings → Branches → Add rule:
- Branch name pattern: `main`
- ✅ Require status checks to pass (lint, test, build)
- ✅ Require pull request before merging
- ✅ Dismiss stale pull request approvals

## 5. Repository topics (makes it discoverable)
GitHub repo → About (gear icon) → Topics:
`python` `fastapi` `react` `typescript` `machine-learning` `xgboost`
`langchain` `rag` `csrd` `esg` `carbon-footprint` `celery` `redis`
`kafka` `airflow` `mlflow` `docker` `kubernetes` `prometheus`

## 6. README badges
Already included at the top of `README.md` — replace `YOUR_USERNAME`
with your GitHub username after pushing.
