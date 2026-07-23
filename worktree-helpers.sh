# ~/.claude/worktree-helpers.sh
# ---------------------------------------------------------------------------
# 安裝方式:
#   1. 把這個檔案放到 ~/.claude/worktree-helpers.sh
#   2. 在 ~/.zshrc 末端加一行:
#        source ~/.claude/worktree-helpers.sh
#   3. 重開 Terminal 或執行:  source ~/.zshrc
#
# 啟動行為(自動判斷):
#   - 目前在 tmux 裡      → 開新的 tmux window(分頁),名稱=branch 尾段
#   - 不在 tmux           → 開 iTerm2 新分頁
# ---------------------------------------------------------------------------

# wt <branch> [base-branch]
#   建立(或沿用)一個 worktree,並在新分頁啟動 claude。
#   - branch 已存在      → 直接 checkout 到新 worktree
#   - branch 不存在      → 從 base(預設當前 HEAD)建立新 branch
#
#   例:
#     wt feature/new-ui              # 從目前 HEAD 開新 branch + 新分頁跑 claude
#     wt fix/memory-leak main        # 從 main 開 bugfix branch
#     wt hotfix/login                # 沿用既有 branch
wt() {
  local branch="$1"
  local base="$2"

  if [[ -z "$branch" ]]; then
    echo "用法: wt <branch> [base-branch]"
    echo "  例: wt feature/new-ui"
    echo "      wt fix/memory-leak main"
    return 1
  fi

  # 抓「主 worktree」路徑當基準,不管現在身處哪個 worktree 都正確
  local main_root
  main_root=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')
  if [[ -z "$main_root" ]]; then
    echo "❌ 不在 git repo 內"
    return 1
  fi

  local repo parent dir name
  repo=$(basename "$main_root")
  parent=$(dirname "$main_root")
  name="${branch##*/}"          # branch 尾段,當目錄後綴 / tmux window 名稱
  dir="$HOME/linker/codes/worktrees/${repo}-${name}"

  if [[ -d "$dir" ]]; then
    echo "♻️  Worktree 已存在,直接使用: $dir"
  elif git show-ref --verify --quiet "refs/heads/$branch"; then
    git worktree add "$dir" "$branch" || return 1
  elif [[ -n "$base" ]]; then
    git worktree add -b "$branch" "$dir" "$base" || return 1
  else
    git worktree add -b "$branch" "$dir" || return 1
  fi

  # 啟動 claude ------------------------------------------------------------
  if [[ -n "$TMUX" ]]; then
    # 在 tmux 內:開新 window(分頁),shell 會在 claude 結束後保留
    tmux new-window -c "$dir" -n "$name"
    tmux send-keys "claude" C-m
    echo "✅ 已開 tmux window「$name」並啟動 claude: $dir"
  else
    # 不在 tmux:開 iTerm2 新分頁
    osascript <<EOF
tell application "iTerm2"
  if (count of windows) = 0 then
    create window with default profile
  else
    tell current window to create tab with default profile
  end if
  tell current session of current window to write text "cd '$dir' && claude"
  activate
end tell
EOF
    echo "✅ 已開 iTerm2 新分頁並啟動 claude: $dir"
  fi
}

# wtclean [branch]
#   不帶參數 → 列出目前所有 worktree
#   帶參數   → 移除對應的 worktree 並 prune(branch 本身保留)
#
#   例:
#     wtclean                        # 看現況
#     wtclean feature/new-ui         # 用完收工
wtclean() {
  local main_root
  main_root=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2; exit}')
  if [[ -z "$main_root" ]]; then
    echo "❌ 不在 git repo 內"
    return 1
  fi

  if [[ -z "$1" ]]; then
    git worktree list
    echo ""
    echo "用法: wtclean <branch>   移除對應的 worktree"
    return 0
  fi

  local repo parent dir
  repo=$(basename "$main_root")
  parent=$(dirname "$main_root")
  dir="$HOME/linker/codes/worktrees/${repo}-${1##*/}"

  git worktree remove "$dir" && echo "🗑️  已移除 $dir"
  git worktree prune
}
