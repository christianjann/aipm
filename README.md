# The AI Project Manager

A tool to manage lagre projects distributed over multiple issue trackers and tools

Workflow:

1) `aipm init`: Initiialize a new project
2) `aipm add jira <URL>`: Add a Jira Project
    - Alternatives: `aipm add github <URL>`: Addd GitHub Project
3) `aipm sync`: AIPM sync the issues to the tickets directory
4) `aipm diff`: Uses git and copilot to sumarize the changes current staged for commit (based on the tickets and project plan)
5) `aipm plan`: Update the plan based on the status updates on the tickets
6) `aipm summary [day|_week_|month|year] [_all_|me|username]`: give a highlevel summary of the next tasks and goals to achive
7) `aipm commit`: commit the updated tickets and plan
