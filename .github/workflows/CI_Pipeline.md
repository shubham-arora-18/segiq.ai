# CI Pipeline Structure

Save the GitHub Actions workflow as:

```
.github/
└── workflows/
    └── ci.yml
```

## What it does (exactly as required):

1. **Build & test** - Builds Docker images and runs services
2. **Run pytest** - Executes the smoke tests  
3. **Execute monitor script for 20s** - Runs `scripts/monitor.sh` for exactly 20 seconds
4. **Archive logs/artifacts** - Saves test reports and Docker logs

## Triggers:
- Push to `main`/`develop` branches
- Pull requests to `main`

## Artifacts:
- Test logs
- Load test reports (if generated)
- Docker container logs

This covers the assignment requirement: *"GitHub Actions or GitLab CI pipeline that: build-&-test, run pytest, execute the monitor script for 20s, and archive logs/artifacts."*