"""Demo users and groups (stand-in for SSO). Confidential pages are restricted by group."""

USERS = {
    "asha": {"username": "asha", "name": "Asha Rao", "title": "Software Engineer",
             "groups": ["employees", "engineering"]},
    "ravi": {"username": "ravi", "name": "Ravi Menon", "title": "HR Business Partner",
             "groups": ["employees", "hr"]},
    "meera": {"username": "meera", "name": "Meera Iyer", "title": "Security Lead",
              "groups": ["employees", "security", "engineering"]},
    "arjun": {"username": "arjun", "name": "Arjun Shah", "title": "Finance Manager",
              "groups": ["employees", "finance"]},
}

DEFAULT_USER = "asha"


def get_user(username: str | None) -> dict:
    return USERS.get(username or DEFAULT_USER, USERS[DEFAULT_USER])
