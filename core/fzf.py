import subprocess
from typing import List, Optional


FZF_OPTS = [
    "--height=100%",
    "--layout=reverse",
    "--border=sharp",
    "--info=inline",
    "--pointer=▶",
    "--marker=▸",
    "--prompt=❯ ",
    "--bind=ctrl-p:preview-up,ctrl-n:preview-down",
    "--bind=alt-v:toggle-preview",
    "--bind=ctrl-a:select-all",
    "--bind=ctrl-d:deselect-all",
    "--bind=ctrl-t:toggle-all",
    "--bind=?:toggle-preview",
    "--color=fg:#d0d0d0,fg+:#ffffff",
    "--color=hl:#7aa2f7,hl+:#7aa2f7,info:#565f89,marker:#9ece6a",
    "--color=prompt:#7aa2f7,spinner:#7aa2f7,pointer:#7aa2f7",
    "--color=header:#565f89,border:#414868,label:#7aa2f7",
    "--color=query:#d0d0d0,separator:#414868",
    "--scroll-off=5",
    "--no-mouse",
]


class FZF:

    @staticmethod
    def menu(items: List[str], prompt: str = "Select: ",
             header: str = "") -> Optional[str]:
        if not items:
            return None
        opts = FZF_OPTS + [f"--prompt={prompt}"]
        if header:
            opts.append(f"--header={header}")

        try:
            proc = subprocess.run(
		 ["fzf"] + opts,
    		 input="\n".join(items),
   		 text=True,
   		 stdout=subprocess.PIPE,
	    )
            return proc.stdout.strip() or None if proc.returncode == 0 else None
        except FileNotFoundError:
            print("fzf not found.")
            return None

    @staticmethod
    def confirm(prompt_text: str = "Are you sure?") -> bool:
        result = FZF.menu(["Yes", "No"], prompt=f"{prompt_text} > ")
        return result == "Yes"
