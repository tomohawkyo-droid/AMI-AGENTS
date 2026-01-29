import subprocess
from pathlib import Path
from typing import Any, NamedTuple

import questionary
from rich.console import Console

console = Console()

EXPECTED_GIT_LOG_PARTS = 4


class GitCommitInfo(NamedTuple):
    """Information about a git commit."""

    hash: str
    author: str
    date: str
    msg: str


class GitManager:
    @staticmethod
    def get_commits(limit: int = 30) -> list[GitCommitInfo]:
        cmd = ["git", "log", "-n", str(limit), "--pretty=format:%h|%an|%ar|%s"]
        try:
            result = subprocess.check_output(cmd, encoding="utf-8")
        except Exception as e:
            console.print(f"[red]Error fetching commits: {e}[/red]")
            return []
        else:
            commits: list[GitCommitInfo] = []
            for line in result.splitlines():
                if "|" in line:
                    parts = line.split("|", 3)
                    if len(parts) == EXPECTED_GIT_LOG_PARTS:
                        h, auth, date, msg = parts
                        commits.append(
                            GitCommitInfo(hash=h, author=auth, date=date, msg=msg)
                        )
            return commits

    @staticmethod
    def get_diff(commit_hash: str) -> str:
        try:
            return subprocess.check_output(
                ["git", "show", commit_hash], encoding="utf-8"
            )
        except Exception as e:
            return f"Error fetching diff: {e}"

    @staticmethod
    def reword_commit(commit_hash: str, new_message: str) -> bool:
        try:
            head_hash = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], encoding="utf-8"
            ).strip()
            if commit_hash == head_hash:
                subprocess.check_call(["git", "commit", "--amend", "-m", new_message])
                return True
        except Exception as e:
            console.print(f"[red]Failed to reword: {e}[/red]")
            return False
        else:
            msg = "Rewording older commits requires rebase. Not implemented."
            console.print(f"[yellow]{msg}[/yellow]")
            return False


def analyze_diff(commit_hash: str, diff_text: str) -> Path:
    output_dir = Path("output/metadata")
    output_dir.mkdir(parents=True, exist_ok=True)
    file_path = output_dir / f"{commit_hash}.md"

    with open(file_path, "w") as f:
        f.write(f"# Commit Analysis: {commit_hash}\n\n")
        f.write("## Raw Diff\n\n```diff\n")
        f.write(diff_text)
        f.write("\n```\n")

    return file_path


def main() -> None:
    while True:
        commits = GitManager.get_commits()
        if not commits:
            console.print("[red]No commits found.[/red]")
            break

        choices: list[Any] = [
            f"{c.hash} - {c.msg} ({c.author}, {c.date})" for c in commits
        ]
        choices.append("Exit")

        selected = questionary.select(
            "Select a commit to examine:", choices=choices
        ).ask()

        if selected == "Exit" or not selected:
            break

        commit_hash = selected.split(" ")[0]
        diff = GitManager.get_diff(commit_hash)

        console.clear()
        console.print(f"[bold blue]Commit: {commit_hash}[/bold blue]")

        action = questionary.select(
            "Action:",
            choices=["View Diff", "Analyze (Save to MD)", "Reword Message", "Back"],
        ).ask()

        if action == "View Diff":
            console.print(diff)
            questionary.press_any_key_to_continue().ask()

        elif action == "Analyze (Save to MD)":
            path = analyze_diff(commit_hash, diff)
            console.print(f"[green]Analysis saved to {path}[/green]")
            questionary.press_any_key_to_continue().ask()

        elif action == "Reword Message":
            new_msg = questionary.text("Enter new commit message:").ask()
            if new_msg:
                if GitManager.reword_commit(commit_hash, new_msg):
                    console.print("[green]Message updated successfully.[/green]")
                questionary.press_any_key_to_continue().ask()


if __name__ == "__main__":
    main()
