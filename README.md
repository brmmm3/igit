# iGit - Easy-to-Use Git GUI

A feature-rich Git GUI client built with Python and PySide6, inspired by [Git Tower](https://www.git-tower.com/).

## Features

### Repository Management
- **Open / Init / Clone** repositories with one click
- Quick clone from GitHub, GitLab, Bitbucket
- Background fetch of remote changes
- Multiple tabs for parallel work

### Working Copy
- **File status** overview (staged/unstaged changes)
- **Stage / Unstage** individual files or all at once
- **Discard changes** selectively (file or hunk level)
- **Hunk staging** - stage specific parts of a file
- Color-coded file status indicators

### Diff Viewer
- **Integrated diff viewer** with syntax highlighting
- Line numbers for easy reference
- **Hunk staging** and **hunk discarding** directly from the diff
- Word wrap toggle
- View diffs for staged, unstaged, and committed changes

### Committing
- **Commit message** with optional description
- **Author selection** from configured profiles
- **Sign-off** and **GPG signing** support
- **Amend** last commit

### Branch History Graph
- **Visual commit graph** with branch lines and merge paths
- Color-coded lanes for different branches
- **Search** commits by message, author, or SHA
- Filter by branch
- Branch and tag labels on commits

### Branch Management
- **Create**, **delete**, and **checkout** branches
- **Merge** branches with conflict detection
- **Rebase** current branch onto another
- **Interactive rebase** with drag-and-drop reordering
- Pick, reword, squash, edit, and drop actions
- Remote branch tracking with ahead/behind indicators

### Stash Management
- **Save** stashes with messages
- **Apply**, **pop**, and **drop** stashes
- View stash diffs

### Remote Operations
- **Fetch**, **Pull**, and **Push** with one click
- **Add** and **remove** remotes
- Remote branch tracking

### Conflict Resolution
- **Conflict wizard** listing all conflicted files
- View conflict markers inline
- **Mark as resolved** and stage
- Open external **merge tool**

### Tags
- **Create** lightweight and annotated tags
- **Delete** tags
- Push tags to remote

### Advanced Features
- **Cherry-pick** commits
- **Revert** commits
- **Reset** (soft, mixed, hard)
- **Reflog** browser for recovering lost commits
- **Submodule** support (update, init)
- **Patch** creation and application
- **Git LFS** support
- **Git Flow** initialization
- **File history** and **blame**

### Customization
- **Dark mode** toggle
- **User profiles** for committer identity
- **GPG signing** configuration
- **External diff/merge tool** integration

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run iGit
python main.py

# Or open a repository directly
python main.py /path/to/repo
```

## Requirements

- Python 3.9+
- PySide6 >= 6.6.0
- GitPython >= 3.1.0
- Pygments >= 2.15.0
- Git (installed on the system)

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open repository |
| `Ctrl+Shift+O` | Clone repository |
| `Ctrl+Q` | Quit |
| `Ctrl+,` | Settings |
| `Ctrl+Return` | Commit |
| `Ctrl+Shift+F` | Fetch |
| `Ctrl+Shift+P` | Pull |
| `Ctrl+Shift+U` | Push |
| `F5` | Refresh |
| `Ctrl+D` | Toggle dark mode |

## Project Structure

```
igit/
├── main.py                  # Entry point
├── requirements.txt
├── igit/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── git_operations.py   # Git wrapper (all operations)
│   ├── ui/
│   │   ├── __init__.py
│   │   └── main_window.py      # Main application window
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── working_copy.py     # File status panel
│   │   ├── diff_viewer.py      # Diff viewer with highlighting
│   │   ├── commit_panel.py     # Commit message panel
│   │   ├── branch_graph.py     # History graph visualization
│   │   ├── branch_panel.py     # Branch management
│   │   ├── stash_panel.py      # Stash management
│   │   └── remote_panel.py     # Remote operations
│   ├── dialogs/
│   │   ├── __init__.py
│   │   ├── clone_dialog.py     # Clone repository dialog
│   │   ├── settings_dialog.py  # Settings dialog
│   │   ├── conflict_dialog.py  # Conflict resolver
│   │   ├── rebase_dialog.py    # Interactive rebase
│   │   └── diff_dialog.py      # Generic diff dialog
│   └── resources/
│       ├── __init__.py
│       └── themes.py           # Light/Dark theme styles
```

## License

MIT
