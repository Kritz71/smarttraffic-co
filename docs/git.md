# Git workflow (main + develop)

One-time: `git config --global user.name "Your Name"` and `user.email`.
Create an EMPTY repo named smarttraffic-co on GitHub first.

    git init
    git branch -M main
    git add README.md LICENSE .gitignore requirements.txt
    git commit -m "chore: initialize project"
    git remote add origin https://github.com/YOUR_USERNAME/smarttraffic-co.git
    git push -u origin main
    git checkout -b develop

Then one commit per step (see the build order in the chat):

    git add src/__init__.py src/config.py main.py && git commit -m "feat: add pygame window and config"
    git add src/traffic.py && git commit -m "feat: add intersection, signals, vehicles and sensors"
    git add src/memory.py && git commit -m "feat: add RAM, cache, buses"
    git add src/cpu.py && git commit -m "feat: add registers, ALU, instruction set and fetch-decode-execute"
    git add src/interrupts.py src/controller.py && git commit -m "feat: run traffic controller on virtual CPU with ambulance interrupt"
    git add src/dashboard.py && git commit -m "feat: add CPU dashboard and statistics"
    git add tests && git commit -m "test: add unit tests"
    git add docs screenshots && git commit -m "docs: add architecture, viva notes and screenshots"
    git push -u origin develop

Merge develop into main at the end: `git checkout main && git merge develop && git push && git tag v1.0 && git push --tags`.
