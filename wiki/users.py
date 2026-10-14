"""Demo users and groups (stand-in for company SSO).

Visibility rules (see db.can_view):
  public       -> everyone who is signed in
  internal     -> group "employees"
  confidential -> only the groups listed in the page's restricted_to
  group "admins" can see every page
"""

USERS = {
    "karthik": {
        "username": "karthik", "name": "Karthik Kumar", "title": "Platform Admin (DevOps/SRE)",
        "groups": ["employees", "engineering", "admins"],
        "access": "Main admin - every page, including all confidential pages",
    },
    "asha": {
        "username": "asha", "name": "Asha Rao", "title": "Software Engineer",
        "groups": ["employees", "engineering"],
        "access": "Public and internal pages",
    },
    "ravi": {
        "username": "ravi", "name": "Ravi Menon", "title": "HR Business Partner",
        "groups": ["employees", "hr"],
        "access": "Public, internal and Salary Bands 2026",
    },
    "meera": {
        "username": "meera", "name": "Meera Iyer", "title": "Security Lead",
        "groups": ["employees", "security", "engineering"],
        "access": "Public, internal and Penetration Test Report 2026",
    },
    "arjun": {
        "username": "arjun", "name": "Arjun Shah", "title": "Finance Manager",
        "groups": ["employees", "finance"],
        "access": "Public, internal and Budget FY2026",
    },
    "neha": {
        "username": "neha", "name": "Neha Kapoor", "title": "Product Manager",
        "groups": ["employees", "product"],
        "access": "Public and internal pages",
    },
    "vikram": {
        "username": "vikram", "name": "Vikram Singh", "title": "External Contractor",
        "groups": ["contractors"],
        "access": "Public pages only - no editing, no AI assistant",
    },
}


def get_user(username: str | None) -> dict | None:
    return USERS.get(username) if username else None


def is_employee(user: dict) -> bool:
    return "employees" in user["groups"]


def is_admin(user: dict) -> bool:
    return "admins" in user["groups"]


def can_use_assistant(user: dict) -> bool:
    # The assistant indexes internal pages, so only users who may read them can ask it
    return is_employee(user)
