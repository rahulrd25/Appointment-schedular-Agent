# Git Workflow Guide

## Development Workflow

### Branch Strategy
- **Main branch**: Production-ready code only
- **Feature branches**: For new features and improvements
- **Bug fix branches**: For bug fixes and patches

### Branch Naming Convention
```bash
# Features
feature/user-authentication
feature/google-oauth
feature/booking-system

# Bug fixes
fix/login-error
fix/database-connection

# Improvements
improve/error-handling
improve/performance

# Documentation
docs/update-readme
docs/api-documentation
```

### Commit Message Format
```bash
# Format: type: description
git commit -m "feat: add Google OAuth integration"
git commit -m "fix: resolve login authentication issue"
git commit -m "docs: update README with installation steps"
git commit -m "refactor: improve user service modularity"
git commit -m "test: add unit tests for user service"
git commit -m "style: format code with black"
```

### Commit Types
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code formatting, missing semicolons, etc.
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Build process, tooling changes

## Step-by-Step Workflow

### 1. Start New Feature
```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Create and switch to feature branch
git checkout -b feature/new-feature-name
```

### 2. Make Changes
```bash
# Make your code changes
# Test your changes thoroughly
```

### 3. Stage and Commit
```bash
# Check what files have changed
git status

# Add specific files or all changes
git add .
# OR
git add specific-file.py

# Commit with descriptive message
git commit -m "feat: add new feature description"
```

### 4. Push Feature Branch
```bash
# Push to remote repository
git push origin feature/new-feature-name
```

### 5. Create Pull Request
- Go to GitHub/GitLab repository
- Create new Pull Request
- Select your feature branch as source
- Select main as target
- Add description of changes
- Request review if working with team

### 6. Review and Merge
- Address any review comments
- Update code if needed
- Merge to main branch
- Delete feature branch after merge

## Common Commands

### Branch Management
```bash
# List all branches
git branch -a

# Switch to branch
git checkout branch-name
# OR (newer syntax)
git switch branch-name

# Create and switch to new branch
git checkout -b new-branch-name

# Delete local branch
git branch -d branch-name

# Delete remote branch
git push origin --delete branch-name
```

### Status and History
```bash
# Check current status
git status

# View commit history
git log --oneline -10

# View changes in specific commit
git show commit-hash

# View changes in working directory
git diff
```

### Stashing
```bash
# Save current changes temporarily
git stash

# List stashed changes
git stash list

# Apply most recent stash
git stash pop

# Apply specific stash
git stash apply stash@{n}
```

### Merging and Rebasing
```bash
# Merge main into feature branch
git checkout feature-branch
git merge main

# Rebase feature branch on main
git checkout feature-branch
git rebase main
```

## Best Practices

### Before Starting Work
1. Always pull latest changes from main
2. Create feature branch from main
3. Ensure you're on the correct branch

### During Development
1. Commit frequently with clear messages
2. Test your changes before committing
3. Keep commits focused and atomic
4. Don't commit broken code

### Before Pushing
1. Run tests to ensure everything works
2. Check for any sensitive data in commits
3. Review your changes with `git diff`
4. Ensure commit messages are descriptive

### Code Review
1. Create descriptive PR titles
2. Add detailed PR descriptions
3. Include screenshots for UI changes
4. Reference related issues/tickets
5. Request reviews from appropriate team members

## Emergency Procedures

### Revert Last Commit
```bash
# Revert last commit (keeps history)
git revert HEAD

# Reset to last commit (destructive)
git reset --hard HEAD~1
```

### Fix Wrong Branch
```bash
# Stash changes
git stash

# Switch to correct branch
git checkout correct-branch

# Apply changes
git stash pop
```

### Undo Last Push
```bash
# Reset to previous commit
git reset --hard HEAD~1

# Force push (use with caution)
git push -f origin branch-name
```

## Security Checklist

### Before Pushing
- [ ] No `.env` files in commits
- [ ] No API keys or secrets in code
- [ ] No database credentials in commits
- [ ] No personal information in commits
- [ ] `.gitignore` properly configured

### Environment Variables
- Always use environment variables for sensitive data
- Never commit `.env` files
- Use `.env.example` or `.env.template` for documentation
- Rotate credentials if accidentally exposed

## Team Collaboration

### Code Review Process
1. Create PR with clear description
2. Assign reviewers
3. Address feedback promptly
4. Request re-review after changes
5. Merge only after approval

### Conflict Resolution
1. Pull latest changes before starting work
2. Communicate with team about conflicting changes
3. Resolve conflicts carefully
4. Test after resolving conflicts
5. Get review for conflict resolution

---

**Remember: Always work on feature branches, never directly on main!**