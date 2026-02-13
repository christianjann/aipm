
setup the to be developed tool aipm in this repository

configure uv, ruff and ty for this workspace

add the following libs to the project:
  - https://github.com/pycontribs/jira
  - https://github.com/PyGithub/PyGithub
  - https://github.com/github/copilot-sdk
    - pip install github-copilot-sdk (via uv for sure)


implement

`aipm init`: Initiialize a new project (querry name and description)
  -> create folder structure: 
    tickets : for synced tickets
    milestones.md: for project plan
    goals.md: project goals
    README.md: with project sumary and links too structure
    aipm.toml: store config in aipm.toml in the workspace of the initialized project
    generated/: folder for generted files, like plan.html, milestones.html, kanban., week.html, month.html. year.html

`aipm add jira <URL>`: Add a Jira Project
  aks for filter
`aipm add github <URL>`: Addd GitHub Project


3) `aipm sync`: AIPM sync the issues to the tickets directory
  make a folder structure under tickets/<projectname>/<number>_<snatized_and shortened_name>.md
  if nothing is staged, stage the newly added/updated, else let the user decide
4) `aipm diff`: Uses git and copilot to sumarize the changes current staged for commit (based on the tickets and project plan)
5) `aipm plan`: Update the plan based on the status updates on the tickets
6) `aipm summary [day|_week_|month|year] [_all_|me|username]`: give a highlevel summary of the next tasks and goals to achive
7) `aipm commit`: commit the updated tickets and plan
