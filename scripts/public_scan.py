"""Scan only tracked release files and commit contents; never print matches."""
import re
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    "credential_token":re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16})"),
    "private_absolute_path":re.compile(r"/(?:Users|Volumes)/[^\s\"'<>]+"),
    "private_key":re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential_assignment":re.compile(r'(?im)^\s*(?:AI_GATEWAY_API_KEY|OPENAI_API_KEY|GH_TOKEN|GITHUB_TOKEN)\s*=\s*["\']?[A-Za-z0-9_-]{16,}'),
}
FORBIDDEN={".env","data","models",".venv","__pycache__","evidence","work"}

def inspect(name,text):
    issues=[]
    # The scanner contains the private-path expression itself, not an actual path.
    for kind,pattern in PATTERNS.items():
        if pattern.search(text): issues.append({"file":name,"kind":kind})
    return issues

def main():
    result=subprocess.run(["git","ls-files","-z"],cwd=ROOT,capture_output=True,check=True)
    names=[n for n in result.stdout.decode().split('\0') if n]
    if not names: raise SystemExit("没有已纳入发布的文件；先准备 Git 索引。")
    issues=[]
    for name in names:
        path=ROOT/name
        if any(part in FORBIDDEN for part in Path(name).parts) or path.is_symlink():
            issues.append({"file":name,"kind":"excluded_or_symlink"});continue
        if path.stat().st_size>2*1024*1024:
            issues.append({"file":name,"kind":"oversize"});continue
        issues+=inspect(name,path.read_text())
    history=subprocess.run(["git","rev-list","--all"],cwd=ROOT,capture_output=True,text=True)
    commits=history.stdout.splitlines() if history.returncode==0 else []
    for commit in commits:
        tree=subprocess.check_output(["git","ls-tree","-r","--name-only",commit],cwd=ROOT,text=True).splitlines()
        for name in tree:
            if any(part in FORBIDDEN for part in Path(name).parts):
                issues.append({"file":name,"kind":"history_excluded"});continue
            content=subprocess.check_output(["git","show",f"{commit}:{name}"],cwd=ROOT,text=True)
            issues+=inspect(name,content)
    if issues:
        for item in issues: print(item["file"]+": "+item["kind"])
        raise SystemExit(1)
    print(f"PASS: {len(names)} release files; {len(commits)} commits; no prohibited patterns. Matches are never printed.")

if __name__=="__main__":main()
